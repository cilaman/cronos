# tests/test_cron_loop.py
# Integration tests for app.harnesses.cron.cron_loop.
#
# Design notes
# ------------
# cron_loop has an injectable `now` callable so tests can drive a controlled
# clock without any real wall-clock dependency (design report risk #5).
# Tests use interval_seconds=0.05 so the loop ticks frequently.
# asyncio.wait_for with a 5s budget guards against infinite hangs.
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses.cron import cron_loop
from app.harnesses.model import Harness, HarnessNode, NodeType, Position
from app.harnesses.run_index import RunSummary, append_run, read_index


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------


def _make_trigger_harness(name: str = "test-harness", expression: str = "*/1 * * * *"):
    """Build a minimal Harness with a single trigger node."""
    node = HarnessNode(
        id="trigger-1",
        type=NodeType.trigger,
        position=Position(x=0.0, y=0.0),
        data={"expression": expression, "timezone": "UTC"},
    )
    return Harness(name=name, nodes=[node])


def _make_space(space_id: str = "space-cron-test"):
    """Return a minimal mock Space object with only the .id attribute."""
    space = MagicMock()
    space.id = space_id
    return space


def _make_mocks(space: object = None, harnesses: list | None = None):
    """Return (harness_store, space_store, task_store, worker_pool) mocks."""
    if space is None:
        space = _make_space()

    harness_store = MagicMock()
    if harnesses is None:
        harnesses = []
    harness_store.list = AsyncMock(return_value=harnesses)

    space_store = MagicMock()
    space_store.list_all = MagicMock(return_value=[space])

    task_store = MagicMock()
    fake_task = MagicMock()
    fake_task.id = "task-run-mock"
    task_store.create = AsyncMock(return_value=fake_task)
    task_store.transition = AsyncMock()

    worker_pool = MagicMock()
    worker_pool.get = MagicMock(return_value=None)

    return harness_store, space_store, task_store, worker_pool


# ---------------------------------------------------------------------------
# R7 — fires at scheduled time
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_loop_fires_at_scheduled_time(tmp_path: Path):
    """
    R7: cron_loop calls enqueue_harness_run when the clock advances past
    the next scheduled cron-minute for a trigger node.

    Clock strategy:
    - T0 = a minute boundary (00:00:00 UTC).
    - Advance to T0 + 65s (past the next "*/1 * * * *" fire at T0+60s).
    - The loop should detect the fire and call enqueue_harness_run exactly once.
    """
    space_id = "space-r7"
    space_dir = tmp_path / space_id
    space_dir.mkdir(parents=True, exist_ok=True)

    harness = _make_trigger_harness("cron-harness", "*/1 * * * *")
    space = _make_space(space_id)
    harness_store, space_store, task_store, worker_pool = _make_mocks(space, [harness])

    # Controlled clock: starts at T0, advances to T0+65s on each call.
    T0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    _calls = [0]

    def controlled_now() -> datetime:
        _calls[0] += 1
        if _calls[0] <= 1:
            # First call in cron_loop sets prev_tick; return T0.
            return T0
        else:
            # Subsequent calls return T0+65s, past the next cron-minute.
            return T0 + timedelta(seconds=65)

    stop_event = asyncio.Event()
    enqueue_calls = []

    async def fake_enqueue(task_store_, harness_store_, worker_pool_,
                           space_id_, space_dir_, harness_name_, *,
                           brief, triggered_at):
        enqueue_calls.append({
            "space_id": space_id_,
            "harness_name": harness_name_,
        })
        # Write a RunSummary to the real index so the run is observable.
        summary = RunSummary(
            run_id="run-r7",
            harness_id=harness_name_,
            status="running",
            triggered_at=triggered_at,
        )
        await append_run(space_dir_, harness_name_, summary)
        return summary

    async def run_and_stop():
        # Give the loop a few ticks to fire, then stop it.
        await asyncio.sleep(0.3)
        stop_event.set()

    with patch("app.harnesses.run_trigger.enqueue_harness_run", side_effect=fake_enqueue):
        await asyncio.wait_for(
            asyncio.gather(
                cron_loop(
                    harness_store,
                    space_store,
                    tmp_path,
                    interval_seconds=0.05,
                    stop_event=stop_event,
                    task_store=task_store,
                    worker_pool=worker_pool,
                    now=controlled_now,
                ),
                run_and_stop(),
            ),
            timeout=5.0,
        )

    assert len(enqueue_calls) >= 1, (
        "Expected at least one enqueue_harness_run call; got none"
    )
    assert enqueue_calls[0]["harness_name"] == "cron-harness"
    assert enqueue_calls[0]["space_id"] == space_id


# ---------------------------------------------------------------------------
# R8 — overlap guard (tick during active run is skipped)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_loop_skips_when_active_run_exists(tmp_path: Path):
    """
    R8: cron_loop does NOT call enqueue_harness_run when the harness already
    has a run with status='running' in the run index.
    """
    space_id = "space-r8"
    space_dir = tmp_path / space_id
    space_dir.mkdir(parents=True, exist_ok=True)

    harness_name = "overlap-harness"
    harness = _make_trigger_harness(harness_name, "*/1 * * * *")
    space = _make_space(space_id)
    harness_store, space_store, task_store, worker_pool = _make_mocks(space, [harness])

    # Pre-populate the run index with a 'running' entry to simulate an active run.
    await append_run(
        tmp_path / space_id,
        harness_name,
        RunSummary(
            run_id="pre-existing-run",
            harness_id=harness_name,
            status="running",
            triggered_at="2026-06-01T12:00:00Z",
        ),
    )

    # Clock that always shows the cron-minute has elapsed.
    T0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    _tick = [0]

    def controlled_now() -> datetime:
        _tick[0] += 1
        if _tick[0] <= 1:
            return T0
        return T0 + timedelta(seconds=65)

    stop_event = asyncio.Event()
    enqueue_calls = []

    async def fake_enqueue(*args, **kwargs):
        enqueue_calls.append(True)
        return RunSummary("new-run", harness_name, "running", "2026-06-01T12:01:00Z")

    async def run_and_stop():
        # Let the loop tick a few times.
        await asyncio.sleep(0.3)
        stop_event.set()

    with patch("app.harnesses.run_trigger.enqueue_harness_run", side_effect=fake_enqueue):
        await asyncio.wait_for(
            asyncio.gather(
                cron_loop(
                    harness_store,
                    space_store,
                    tmp_path,
                    interval_seconds=0.05,
                    stop_event=stop_event,
                    task_store=task_store,
                    worker_pool=worker_pool,
                    now=controlled_now,
                ),
                run_and_stop(),
            ),
            timeout=5.0,
        )

    assert len(enqueue_calls) == 0, (
        f"Expected no enqueue calls due to overlap guard; got {len(enqueue_calls)}"
    )


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_loop_exits_when_stop_event_is_set(tmp_path: Path):
    """cron_loop must exit cleanly when stop_event is set."""
    harness_store, space_store, task_store, worker_pool = _make_mocks()

    stop_event = asyncio.Event()

    async def set_stop():
        await asyncio.sleep(0.1)
        stop_event.set()

    now_fixed = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

    # Should complete well within 5s once the stop event fires.
    await asyncio.wait_for(
        asyncio.gather(
            cron_loop(
                harness_store,
                space_store,
                tmp_path,
                interval_seconds=0.05,
                stop_event=stop_event,
                task_store=task_store,
                worker_pool=worker_pool,
                now=lambda: now_fixed,
            ),
            set_stop(),
        ),
        timeout=5.0,
    )
    # If we reach here without TimeoutError, the loop exited correctly.


# ---------------------------------------------------------------------------
# Malformed expression — loop continues without crashing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_loop_continues_after_malformed_expression(tmp_path: Path):
    """cron_loop must not crash when a trigger node has an invalid cron expression."""
    space_id = "space-malformed"
    harness = _make_trigger_harness("malformed-harness", "this-is-not-valid")
    space = _make_space(space_id)
    harness_store, space_store, task_store, worker_pool = _make_mocks(space, [harness])

    T0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    _tick = [0]

    def controlled_now() -> datetime:
        _tick[0] += 1
        return T0 + timedelta(seconds=_tick[0] * 2)

    stop_event = asyncio.Event()

    async def run_and_stop():
        await asyncio.sleep(0.25)
        stop_event.set()

    # No crash expected — the loop should log and continue.
    await asyncio.wait_for(
        asyncio.gather(
            cron_loop(
                harness_store,
                space_store,
                tmp_path,
                interval_seconds=0.05,
                stop_event=stop_event,
                task_store=task_store,
                worker_pool=worker_pool,
                now=controlled_now,
            ),
            run_and_stop(),
        ),
        timeout=5.0,
    )
    # Reaching here without TimeoutError or unhandled exception means the loop
    # survived the malformed expression gracefully.


# ---------------------------------------------------------------------------
# No-trigger-node harness — loop runs without errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_loop_handles_harness_with_no_trigger_nodes(tmp_path: Path):
    """cron_loop must run without errors when a harness has no trigger nodes."""
    space_id = "space-notrigger"
    # A harness with zero nodes (no trigger nodes).
    harness = Harness(name="no-trigger-harness", nodes=[])
    space = _make_space(space_id)
    harness_store, space_store, task_store, worker_pool = _make_mocks(space, [harness])

    T0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    _tick = [0]

    def controlled_now() -> datetime:
        _tick[0] += 1
        return T0 + timedelta(seconds=_tick[0])

    stop_event = asyncio.Event()
    enqueue_calls = []

    async def fake_enqueue(*args, **kwargs):
        enqueue_calls.append(True)

    async def run_and_stop():
        await asyncio.sleep(0.2)
        stop_event.set()

    with patch("app.harnesses.run_trigger.enqueue_harness_run", side_effect=fake_enqueue):
        await asyncio.wait_for(
            asyncio.gather(
                cron_loop(
                    harness_store,
                    space_store,
                    tmp_path,
                    interval_seconds=0.05,
                    stop_event=stop_event,
                    task_store=task_store,
                    worker_pool=worker_pool,
                    now=controlled_now,
                ),
                run_and_stop(),
            ),
            timeout=5.0,
        )

    assert len(enqueue_calls) == 0, (
        "No enqueue calls expected when harness has no trigger nodes"
    )


# ---------------------------------------------------------------------------
# Empty space list — loop runs without errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_loop_handles_empty_space_list(tmp_path: Path):
    """cron_loop runs cleanly when space_store.list_all() returns an empty list."""
    harness_store = MagicMock()
    harness_store.list = AsyncMock(return_value=[])
    space_store = MagicMock()
    space_store.list_all = MagicMock(return_value=[])
    task_store = MagicMock()
    worker_pool = MagicMock()

    now_fixed = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    stop_event = asyncio.Event()

    async def set_stop():
        await asyncio.sleep(0.1)
        stop_event.set()

    await asyncio.wait_for(
        asyncio.gather(
            cron_loop(
                harness_store,
                space_store,
                tmp_path,
                interval_seconds=0.05,
                stop_event=stop_event,
                task_store=task_store,
                worker_pool=worker_pool,
                now=lambda: now_fixed,
            ),
            set_stop(),
        ),
        timeout=5.0,
    )
    # Reaching here without error confirms graceful handling of empty space list.
