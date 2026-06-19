"""
Regression tests: harness executor lifecycle and run index update.

Covers:
1. WorkerPool passes harness_store to Worker (not None after start_for_space)
2. _run_initial_harness_run returns True when harness_store is present
3. Run index updated to "done" after harness executor completes
4. Cron overlap guard unblocks after run finishes (has_active_run returns False)
5. Trigger node handled silently — no WARNING logged, successor agent enqueued
"""

from __future__ import annotations

import json
import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses import run_index as _run_index
from app.harnesses.cron import has_active_run
from app.harnesses.executor import HarnessExecutor
from app.harnesses.model import (
    Harness,
    HarnessEdge,
    HarnessNode,
    NodeRef,
    NodeType,
    Position,
)
from app.models import AiToolEntry, Space, TaskState
from app.trace_parser import RunTrace
from app.worker import Worker
from app.worker_pool import WorkerPool


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _make_space(space_id: str = "w-space") -> Space:
    now = _utcnow()
    return Space(
        id=space_id,
        name="Worker Integration Space",
        color="#abcdef",
        created_at=now,
        updated_at=now,
    )


def _make_trigger_node(node_id: str = "T") -> HarnessNode:
    return HarnessNode(
        id=node_id,
        type=NodeType.trigger,
        position=Position(x=0.0, y=0.0),
        ports={"out": {"direction": "output"}},
        data={},
        label=node_id,
    )


def _make_agent_node(node_id: str = "A", prompt: str = "do it") -> HarnessNode:
    return HarnessNode(
        id=node_id,
        type=NodeType.agent,
        position=Position(x=100.0, y=0.0),
        ports={"out": {"direction": "output"}},
        data={"agent_ref": "test-agent", "prompt_template": prompt},
        label=node_id,
    )


def _make_edge(edge_id: str, src: str, tgt: str) -> HarnessEdge:
    return HarnessEdge(
        id=edge_id,
        source=NodeRef(node_id=src, port_id="out"),
        target=NodeRef(node_id=tgt, port_id="out"),
    )


def _make_trace(task_id: str, space_id: str = "w-space") -> RunTrace:
    now = _utcnow()
    return RunTrace(
        task_id=task_id,
        space_id=space_id,
        run_index=0,
        session_id=None,
        model="test-model",
        mode="auto",
        started_at=now,
        ended_at=now,
        duration_seconds=0.1,
        exit_reason="DONE",
        final_text_snippet="done",
    )


def _make_task_mock(task_id: str, state: TaskState = TaskState.DONE) -> MagicMock:
    task = MagicMock()
    task.id = task_id
    task.state = state
    return task


def _no_tools_resolver(space_id: str, agent_ref: str) -> AiToolEntry | None:
    return None


def _make_store_mock() -> MagicMock:
    """Return a TaskStore mock with async create() and sync get()."""
    task_counter = [0]
    store = MagicMock()

    async def _create(*, space_id, title, brief, parent_id=None, **kwargs):
        task_counter[0] += 1
        return _make_task_mock(f"child-{task_counter[0]}")

    store.create = _create
    store.get = MagicMock(return_value=None)
    return store


def _make_worker_mock() -> MagicMock:
    """Return a WorkerProtocol stub with mock run_agent / finalize_child."""
    worker = MagicMock()
    task_counter = [0]

    async def _run_agent(task_id: str, **kwargs) -> RunTrace:
        task_counter[0] += 1
        return _make_trace(task_id)

    async def _finalize_child(task_id: str, trace: RunTrace) -> TaskState:
        return TaskState.DONE

    worker.run_agent = _run_agent
    worker.finalize_child = _finalize_child
    return worker


# ---------------------------------------------------------------------------
# Test 1: WorkerPool passes harness_store to Worker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_pool_injects_harness_store():
    """WorkerPool.start_for_space() must pass harness_store to the Worker it creates."""
    mock_harness_store = MagicMock()
    mock_task_store = MagicMock()
    mock_space_store = MagicMock()
    mock_space_store.get.return_value = None  # on_idle callback uses this

    pool = WorkerPool(
        mock_task_store,
        space_store=mock_space_store,
        harness_store=mock_harness_store,
    )

    worker = await pool.start_for_space("wi-space")
    try:
        assert worker.harness_store is mock_harness_store
        assert worker.harness_store is not None
    finally:
        await worker.stop()


# ---------------------------------------------------------------------------
# Test 2: _run_initial_harness_run proceeds when harness_store is present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_initial_harness_run_proceeds_when_store_present():
    """_run_initial_harness_run short-circuits (returns False) only when harness_store is None.

    With harness_store set, the function must proceed past the early-return guard
    and ultimately delegate to _execute_harness_run.
    """
    space_id = "wi-harness-space"
    task_id = "wi-run-task-001"
    harness_id = "wi-harness"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Write index file so _run_initial_harness_run can resolve harness_id.
        index_dir = tmp / "spaces" / space_id / ".cronos" / "harness-runs"
        index_dir.mkdir(parents=True)
        (index_dir / f"{harness_id}-index.json").write_text(
            json.dumps([{
                "run_id": task_id,
                "harness_id": harness_id,
                "status": "running",
                "triggered_at": "2026-01-01T00:00:00Z",
            }])
        )

        mock_task_store = MagicMock()
        mock_space_store = MagicMock()
        mock_harness_store = MagicMock()

        # Case 1: harness_store is None → must return False immediately.
        worker_no_store = Worker(
            mock_task_store,
            space_store=mock_space_store,
            harness_store=None,
        )
        worker_no_store._run_id_to_space_id[task_id] = space_id
        with patch("app.worker.DATA_DIR", tmp):
            result_no_store = await worker_no_store._run_initial_harness_run(task_id)
        assert result_no_store is False, (
            "Expected False when harness_store is None"
        )

        # Case 2: harness_store present → must NOT short-circuit; returns True via mock.
        worker_with_store = Worker(
            mock_task_store,
            space_store=mock_space_store,
            harness_store=mock_harness_store,
        )
        worker_with_store._run_id_to_space_id[task_id] = space_id

        with patch.object(
            worker_with_store, "_execute_harness_run", new=AsyncMock(return_value=True)
        ), patch("app.worker.DATA_DIR", tmp):
            result_with_store = await worker_with_store._run_initial_harness_run(task_id)

        assert result_with_store is True, (
            "Expected True when harness_store is set and _execute_harness_run succeeds"
        )


# ---------------------------------------------------------------------------
# Shared executor fixture for tests 3, 4, 5
# ---------------------------------------------------------------------------


async def _run_trigger_agent_harness(
    tmpdir: str, run_goal_id: str, space_id: str, harness_id: str
) -> None:
    """Run a minimal trigger→agent harness via HarnessExecutor inside tmpdir.

    Pre-seeds the run index with status='running' so executor.execute() can
    update it to 'done' at the end.
    """
    tmp = Path(tmpdir)
    space = _make_space(space_id)

    trigger = _make_trigger_node("T")
    agent = _make_agent_node("A")
    edge = _make_edge("e1", "T", "A")
    harness = Harness(name=harness_id, nodes=[trigger, agent], edges=[edge])

    store = _make_store_mock()
    worker_proto = _make_worker_mock()

    # Pre-seed index with status='running' so the executor can update it.
    index_dir = tmp / "spaces" / space_id / ".cronos" / "harness-runs"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / f"{harness_id}-index.json").write_text(
        json.dumps([{
            "run_id": run_goal_id,
            "harness_id": harness_id,
            "status": "running",
            "triggered_at": "2026-01-01T00:00:00Z",
            "finished_at": None,
        }])
    )

    with patch("app.harnesses.executor._DATA_DIR", tmp):
        executor = HarnessExecutor(store, worker_proto, _no_tools_resolver)
        await executor.execute(run_goal_id, harness, space)


# ---------------------------------------------------------------------------
# Test 3: Run index updated to "done" after harness executor completes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_index_updated_to_done_after_execution():
    """executor.execute() must update the run index entry to status='done'."""
    run_goal_id = "idx-run-001"
    space_id = "idx-space"
    harness_id = "idx-harness"

    with tempfile.TemporaryDirectory() as tmpdir:
        await _run_trigger_agent_harness(tmpdir, run_goal_id, space_id, harness_id)

        space_dir = Path(tmpdir) / "spaces" / space_id
        summaries = await _run_index.read_index(space_dir, harness_id)

    assert len(summaries) == 1, f"Expected 1 run summary, got {len(summaries)}"
    summary = summaries[0]
    assert summary.run_id == run_goal_id
    assert summary.status == "done", f"Expected 'done', got {summary.status!r}"
    assert summary.finished_at is not None, "finished_at must be set after execution"


# ---------------------------------------------------------------------------
# Test 4: Cron overlap guard unblocks after run finishes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_overlap_guard_unblocks_after_run_finishes():
    """has_active_run() must return False once the run index is updated to 'done'."""
    run_goal_id = "cron-run-001"
    space_id = "cron-space"
    harness_id = "cron-harness"

    with tempfile.TemporaryDirectory() as tmpdir:
        await _run_trigger_agent_harness(tmpdir, run_goal_id, space_id, harness_id)

        space_dir = Path(tmpdir) / "spaces" / space_id
        still_active = await has_active_run(space_dir, harness_id)

    assert still_active is False, (
        "has_active_run() must return False after executor updates index to 'done'; "
        "a True result would permanently block future cron-triggered runs"
    )


# ---------------------------------------------------------------------------
# Test 5: Trigger node handled silently — no WARNING logged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_node_no_warning_logged(caplog):
    """Trigger node must be processed as a pass-through without emitting a WARNING.

    The executor previously had no NodeType.trigger branch, logging a WARNING
    for 'unknown node type'.  This test verifies the fix: the trigger node
    transitions silently to 'done' and its successor agent node is enqueued.
    """
    run_goal_id = "trig-run-001"
    space_id = "trig-space"
    harness_id = "trig-harness"

    space = _make_space(space_id)
    trigger = _make_trigger_node("T")
    agent = _make_agent_node("A", prompt="work after trigger")
    edge = _make_edge("e1", "T", "A")
    harness = Harness(name=harness_id, nodes=[trigger, agent], edges=[edge])

    store = _make_store_mock()
    worker_proto = _make_worker_mock()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        with caplog.at_level(logging.WARNING, logger="app.harnesses.executor"):
            with patch("app.harnesses.executor._DATA_DIR", tmp):
                executor = HarnessExecutor(store, worker_proto, _no_tools_resolver)
                result = await executor.execute(run_goal_id, harness, space)

    # No WARNING should mention the trigger node T or 'unknown node type'.
    trigger_warnings = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING
        and ("unknown" in r.message.lower() or "node T" in r.message or "NodeType.trigger" in r.message)
    ]
    assert not trigger_warnings, (
        f"Unexpected WARNING(s) for trigger node: {[r.message for r in trigger_warnings]}"
    )

    # Trigger node must be recorded as 'done'.
    trigger_state = result.nodes_executed.get("T")
    assert trigger_state is not None, "Trigger node 'T' must appear in run state"
    assert trigger_state.status == "done", (
        f"Expected trigger node status 'done', got {trigger_state.status!r}"
    )

    # Agent node must also be 'done' — confirming it was enqueued after the trigger.
    agent_state = result.nodes_executed.get("A")
    assert agent_state is not None, "Agent node 'A' must appear in run state"
    assert agent_state.status == "done", (
        f"Expected agent node status 'done', got {agent_state.status!r}"
    )
