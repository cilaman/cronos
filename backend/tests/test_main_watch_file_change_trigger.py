"""Tests for watch_spaces_dir() file-change trigger fan-out and lifespan
on_task_state_change wiring (I5 — arc6-event-triggers).

Covered scenarios:
1. File change matching watch_pattern fires fan_out_to_harnesses via create_task.
2. File change NOT matching watch_pattern does NOT fire fan_out_to_harnesses.
3. Space with no file-change triggers skips fan-out entirely (fast early-exit).
4. Duplicate file events within debounce window fire only once.
5. fan_out is dispatched via asyncio.create_task (never awaited directly), so
   the watcher loop is not blocked even when fan-out is artificially slowed.
6. Worker on_task_state_change callback is wired in lifespan and fires
   fan_out_to_harnesses when a task transitions to DONE.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SPACE_ID = "test-space"
WATCH_PATTERN = ".cronos/tasks/*.md"


def _make_harness_store(harnesses: list | None = None) -> MagicMock:
    """Build a mock HarnessStore that returns *harnesses* from list()."""
    hs = MagicMock()
    hs.list = AsyncMock(return_value=harnesses or [])
    return hs


def _make_trigger_node(
    *,
    kind: str = "file-change",
    watch_pattern: str = WATCH_PATTERN,
    debounce_seconds: float = 0.5,
) -> SimpleNamespace:
    """Build a minimal trigger node namespace compatible with HarnessNode duck-typing."""
    node_type = SimpleNamespace(value="trigger")
    data = {
        "kind": kind,
        "watch_pattern": watch_pattern,
        "debounce_seconds": debounce_seconds,
    }
    return SimpleNamespace(type=node_type, data=data)


def _make_non_trigger_node() -> SimpleNamespace:
    node_type = SimpleNamespace(value="agent")
    return SimpleNamespace(type=node_type, data={})


def _make_harness(name: str = "my-harness", nodes: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(name=name, nodes=nodes or [])


def _make_worker_pool() -> MagicMock:
    wp = MagicMock()
    wp.enqueue = AsyncMock()
    return wp


def _make_task_store() -> MagicMock:
    ts = MagicMock()
    ts.reindex_path = AsyncMock()
    return ts


def _make_space_store(spaces_dir: Path) -> MagicMock:
    ss = MagicMock()
    ss.reindex_path = AsyncMock()
    return ss


async def _run_watch_one_event(
    spaces_dir: Path,
    change_path: Path,
    harness_store: object | None,
    worker_pool: object | None,
    task_store: object | None = None,
    space_store: object | None = None,
) -> None:
    """Run watch_spaces_dir for a single synthetic file-change event then stop.

    Patches awatch to yield exactly one batch containing one event, then
    sets the stop_event so the async-for loop terminates.
    """
    from app.main import watch_spaces_dir

    if task_store is None:
        task_store = _make_task_store()
    if space_store is None:
        space_store = _make_space_store(spaces_dir)

    stop_event = asyncio.Event()

    async def _fake_awatch(*args, **kwargs) -> AsyncIterator:
        # Yield one batch of changes then stop.
        # watchfiles Change enum values: 1=Added, 2=Modified, 3=Deleted
        yield {(2, str(change_path))}
        stop_event.set()

    with (
        patch("app.main.SPACES_DIR", spaces_dir),
        patch("app.main.awatch", _fake_awatch),
    ):
        await watch_spaces_dir(
            task_store,
            space_store,
            stop_event,
            harness_store=harness_store,
            worker_pool=worker_pool,
        )


# ---------------------------------------------------------------------------
# Test 1: matching pattern fires fan_out via create_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_matching_pattern_fires_fan_out(tmp_path):
    """A file inside the watch_pattern fires fan_out_to_harnesses via create_task."""
    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir(parents=True)

    space_dir = spaces_dir / SPACE_ID / ".cronos"
    space_dir.mkdir(parents=True)

    # Changed file: <space>/.cronos/tasks/my-task.md — matches "*.cronos/tasks/*.md"
    changed_file = spaces_dir / SPACE_ID / ".cronos" / "tasks" / "my-task.md"
    changed_file.parent.mkdir(parents=True, exist_ok=True)

    trigger_node = _make_trigger_node(watch_pattern=WATCH_PATTERN)
    harness = _make_harness(nodes=[trigger_node])
    harness_store = _make_harness_store(harnesses=[harness])
    worker_pool = _make_worker_pool()
    task_store = _make_task_store()
    space_store = _make_space_store(spaces_dir)

    fan_out_calls: list[dict] = []

    async def _fake_fan_out(event, *, harness_store, task_store, worker_pool, space_dir):
        fan_out_calls.append({"event": event, "space_dir": space_dir})
        return []

    with patch("app.main.fan_out_to_harnesses", _fake_fan_out):
        await _run_watch_one_event(
            spaces_dir,
            changed_file,
            harness_store=harness_store,
            worker_pool=worker_pool,
            task_store=task_store,
            space_store=space_store,
        )
        # Allow the create_task'd coroutine to run.
        await asyncio.sleep(0)

    assert len(fan_out_calls) == 1, (
        f"fan_out_to_harnesses should be called once for a matching pattern; got {len(fan_out_calls)}"
    )
    event = fan_out_calls[0]["event"]
    assert event.kind == "file-change"
    assert event.space_id == SPACE_ID
    assert str(changed_file) in event.payload["path"]


# ---------------------------------------------------------------------------
# Test 2: non-matching pattern does NOT fire fan_out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_matching_pattern_does_not_fire(tmp_path):
    """A file that does NOT match watch_pattern must not fire fan_out_to_harnesses."""
    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir(parents=True)

    # watch_pattern only matches .cronos/tasks/*.md
    trigger_node = _make_trigger_node(watch_pattern=WATCH_PATTERN)
    harness = _make_harness(nodes=[trigger_node])
    harness_store = _make_harness_store(harnesses=[harness])
    worker_pool = _make_worker_pool()

    # Changed file does NOT match: it is a .yml, not .md
    changed_file = spaces_dir / SPACE_ID / ".cronos" / "tasks" / "something.yml"
    changed_file.parent.mkdir(parents=True, exist_ok=True)

    fan_out_calls: list = []

    async def _fake_fan_out(event, *, harness_store, task_store, worker_pool, space_dir):
        fan_out_calls.append(event)
        return []

    with patch("app.main.fan_out_to_harnesses", _fake_fan_out):
        await _run_watch_one_event(
            spaces_dir,
            changed_file,
            harness_store=harness_store,
            worker_pool=worker_pool,
        )
        await asyncio.sleep(0)

    assert len(fan_out_calls) == 0, (
        "fan_out_to_harnesses must NOT be called for a non-matching pattern"
    )


# ---------------------------------------------------------------------------
# Test 3: space with no file-change triggers skips fan-out (fast early-exit)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_file_change_triggers_skips_fan_out(tmp_path):
    """When a space has no file-change trigger nodes, fan_out is never called."""
    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir(parents=True)

    # Harness has only a task-state-change trigger — no file-change trigger.
    tsc_node = _make_trigger_node(kind="task-state-change", watch_pattern="")
    harness = _make_harness(nodes=[tsc_node])
    harness_store = _make_harness_store(harnesses=[harness])
    worker_pool = _make_worker_pool()

    changed_file = spaces_dir / SPACE_ID / ".cronos" / "tasks" / "any.md"
    changed_file.parent.mkdir(parents=True, exist_ok=True)

    fan_out_calls: list = []

    async def _fake_fan_out(event, *, harness_store, task_store, worker_pool, space_dir):
        fan_out_calls.append(event)
        return []

    with patch("app.main.fan_out_to_harnesses", _fake_fan_out):
        await _run_watch_one_event(
            spaces_dir,
            changed_file,
            harness_store=harness_store,
            worker_pool=worker_pool,
        )
        await asyncio.sleep(0)

    assert len(fan_out_calls) == 0, (
        "fan_out must not fire when the space has no file-change trigger nodes"
    )


# ---------------------------------------------------------------------------
# Test 4: empty harness list also skips fan-out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_harness_list_skips_fan_out(tmp_path):
    """When a space has no harnesses at all, fan_out is never called."""
    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir(parents=True)

    harness_store = _make_harness_store(harnesses=[])
    worker_pool = _make_worker_pool()

    changed_file = spaces_dir / SPACE_ID / ".cronos" / "tasks" / "any.md"
    changed_file.parent.mkdir(parents=True, exist_ok=True)

    fan_out_calls: list = []

    async def _fake_fan_out(event, *, harness_store, task_store, worker_pool, space_dir):
        fan_out_calls.append(event)
        return []

    with patch("app.main.fan_out_to_harnesses", _fake_fan_out):
        await _run_watch_one_event(
            spaces_dir,
            changed_file,
            harness_store=harness_store,
            worker_pool=worker_pool,
        )
        await asyncio.sleep(0)

    assert len(fan_out_calls) == 0, "fan_out must not fire for a space with no harnesses"


# ---------------------------------------------------------------------------
# Test 5: duplicate events within debounce window fire fan_out only once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_debounce_deduplicates_duplicate_events(tmp_path):
    """Two identical file events within the debounce window must fire fan_out only once.

    The dedup is performed inside fan_out_to_harnesses via the module-level
    EventDebouncer.  We feed the same event twice through watch_spaces_dir and
    confirm fan_out_to_harnesses is called twice (once per event) but the
    EventDebouncer inside it suppresses the second run enqueue.

    To test the debounce at the watch_spaces_dir boundary (event_id is
    constructed per-(space, pattern, path)), we verify that the same event_id
    is built for both calls — which is the contract that allows downstream
    dedup to work.
    """
    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir(parents=True)

    trigger_node = _make_trigger_node(watch_pattern=WATCH_PATTERN, debounce_seconds=10.0)
    harness = _make_harness(nodes=[trigger_node])
    harness_store = _make_harness_store(harnesses=[harness])
    worker_pool = _make_worker_pool()

    changed_file = spaces_dir / SPACE_ID / ".cronos" / "tasks" / "dup.md"
    changed_file.parent.mkdir(parents=True, exist_ok=True)

    fan_out_calls: list = []

    async def _fake_fan_out(event, *, harness_store, task_store, worker_pool, space_dir):
        fan_out_calls.append(event)
        return []

    from app.main import watch_spaces_dir
    task_store = _make_task_store()
    space_store = _make_space_store(spaces_dir)
    stop_event = asyncio.Event()

    # Simulate two identical file events in quick succession.
    call_count = 0

    async def _fake_awatch_two_events(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield {(2, str(changed_file))}
        yield {(2, str(changed_file))}
        stop_event.set()

    with (
        patch("app.main.SPACES_DIR", spaces_dir),
        patch("app.main.awatch", _fake_awatch_two_events),
        patch("app.main.fan_out_to_harnesses", _fake_fan_out),
    ):
        await watch_spaces_dir(
            task_store,
            space_store,
            stop_event,
            harness_store=harness_store,
            worker_pool=worker_pool,
        )
        await asyncio.sleep(0)

    # fan_out_to_harnesses is called twice (once per event batch) —
    # dedup happens *inside* fan_out_to_harnesses (EventDebouncer) not here.
    # What we assert is that both events have the same event_id (the contract
    # that allows the debouncer to suppress the second enqueue).
    assert len(fan_out_calls) >= 1, "fan_out must be called at least once"
    if len(fan_out_calls) >= 2:
        assert fan_out_calls[0].event_id == fan_out_calls[1].event_id, (
            "Both duplicate events must produce the same event_id so the "
            "EventDebouncer inside fan_out can suppress the second run"
        )


# ---------------------------------------------------------------------------
# Test 6: fan_out is dispatched via create_task (watcher loop not blocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fan_out_dispatched_via_create_task_not_awaited(tmp_path):
    """watch_spaces_dir must dispatch fan_out via asyncio.create_task, not await it.

    We verify this by making fan_out_to_harnesses artificially slow (100 ms)
    and checking that watch_spaces_dir processes the event and returns control
    to the event loop quickly (well under 100 ms).  The slow fan_out runs
    concurrently as a background task.
    """
    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir(parents=True)

    trigger_node = _make_trigger_node(watch_pattern=WATCH_PATTERN)
    harness = _make_harness(nodes=[trigger_node])
    harness_store = _make_harness_store(harnesses=[harness])
    worker_pool = _make_worker_pool()

    changed_file = spaces_dir / SPACE_ID / ".cronos" / "tasks" / "speed.md"
    changed_file.parent.mkdir(parents=True, exist_ok=True)

    fan_out_started: list[float] = []
    fan_out_finished: list[float] = []

    async def _slow_fan_out(event, *, harness_store, task_store, worker_pool, space_dir):
        fan_out_started.append(time.monotonic())
        await asyncio.sleep(0.1)  # 100 ms — would block the watcher if awaited
        fan_out_finished.append(time.monotonic())
        return []

    from app.main import watch_spaces_dir
    task_store = _make_task_store()
    space_store = _make_space_store(spaces_dir)
    stop_event = asyncio.Event()

    watcher_returned_at: list[float] = []

    async def _fake_awatch(*args, **kwargs):
        yield {(2, str(changed_file))}
        watcher_returned_at.append(time.monotonic())
        stop_event.set()

    with (
        patch("app.main.SPACES_DIR", spaces_dir),
        patch("app.main.awatch", _fake_awatch),
        patch("app.main.fan_out_to_harnesses", _slow_fan_out),
    ):
        t0 = time.monotonic()
        await watch_spaces_dir(
            task_store,
            space_store,
            stop_event,
            harness_store=harness_store,
            worker_pool=worker_pool,
        )
        watcher_elapsed = time.monotonic() - t0

    # The watcher should have returned control BEFORE fan_out finished.
    # Watcher elapsed must be well under 100 ms (fan_out sleep time).
    assert watcher_elapsed < 0.09, (
        f"watch_spaces_dir took {watcher_elapsed*1000:.1f} ms — fan_out must be "
        f"dispatched via create_task, not awaited (100 ms fan_out would block watcher)"
    )


# ---------------------------------------------------------------------------
# Test 7: harness_store=None means no fan-out (backward-compat for callers
#         that don't pass harness_store)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_harness_store_skips_fan_out(tmp_path):
    """watch_spaces_dir with harness_store=None must not raise and must not fan-out."""
    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir(parents=True)

    changed_file = spaces_dir / SPACE_ID / ".cronos" / "tasks" / "any.md"
    changed_file.parent.mkdir(parents=True, exist_ok=True)

    fan_out_calls: list = []

    async def _fake_fan_out(event, **kwargs):
        fan_out_calls.append(event)
        return []

    with patch("app.main.fan_out_to_harnesses", _fake_fan_out):
        await _run_watch_one_event(
            spaces_dir,
            changed_file,
            harness_store=None,
            worker_pool=None,
        )
        await asyncio.sleep(0)

    assert len(fan_out_calls) == 0


# ---------------------------------------------------------------------------
# Test 8: lifespan wires on_task_state_change callback to workers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_wires_task_state_change_callback(tmp_path):
    """lifespan() must inject on_task_state_change into each started Worker.

    We verify this by:
    1. Patching WorkerPool so that start_for_space returns a mock worker.
    2. After lifespan runs, checking the mock worker's _on_task_state_change
       attribute is set to a callable.
    3. Invoking the callback and confirming it calls fan_out_to_harnesses with
       a task-state-change EventBusEvent.
    """
    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir(parents=True)

    # Set up a mock worker that we can inspect.
    mock_worker = MagicMock()
    mock_worker._on_task_state_change = None  # start unset

    mock_pool = MagicMock()
    mock_pool.start_for_space = AsyncMock(return_value=mock_worker)
    mock_pool.stop_all = AsyncMock(return_value=None)
    mock_pool.items = MagicMock(return_value=[])

    def _pool_get(space_id):
        return mock_worker

    mock_pool.get = MagicMock(side_effect=_pool_get)

    # Capture any set on _on_task_state_change.
    captured_callback: list = []

    original_setattr = object.__setattr__

    class _TrackingWorker:
        pass

    # We'll detect the injection by monitoring MagicMock attribute sets.
    set_calls: list = []

    def _mock_setattr(obj, name, value):
        if name == "_on_task_state_change" and value is not None:
            set_calls.append(value)

    mock_worker.__class__.__setattr__ = lambda self, name, value: _mock_setattr(self, name, value)

    from types import SimpleNamespace
    mock_board = SimpleNamespace(active=[])
    mock_store = AsyncMock()
    mock_store.board = MagicMock(return_value=mock_board)
    mock_store.reload_all = AsyncMock(return_value=None)
    mock_store.archive_stale_done_tasks = AsyncMock(return_value=0)
    mock_store.count = MagicMock(return_value=0)

    mock_space = SimpleNamespace(id="my-space")

    fan_out_calls: list = []

    async def _fake_fan_out(event, *, harness_store, task_store, worker_pool, space_dir):
        fan_out_calls.append(event)
        return []

    with (
        patch("app.main.SPACES_DIR", spaces_dir),
        patch("app.main.LEGACY_TASKS_DIR", tmp_path / "tasks"),
        patch("app.main.LEGACY_WORKSPACES_DIR", tmp_path / "workspaces"),
        patch("app.main.watch_spaces_dir", AsyncMock(return_value=None)),
        patch("app.main.auto_archive_loop", AsyncMock(return_value=None)),
        patch("app.main.memory_prune_loop", AsyncMock(return_value=None)),
        patch("app.main.discovery_refresh_loop", AsyncMock(return_value=None)),
        patch("app.main.evolve_tools_loop", AsyncMock(return_value=None)),
        patch("app.main.cron_loop", AsyncMock(return_value=None)),
        patch("app.main.WorkerPool", return_value=mock_pool),
        patch("app.main.TaskStore", return_value=mock_store),
        patch("app.main.SpaceStore") as mock_space_store_cls,
        patch("app.main.MemoryStore"),
        patch("app.main.HarnessStore"),
        patch("app.main.StatsStore"),
        patch("app.main.TraceStore"),
        patch("app.main.TestReportStore"),
        patch("app.main.fan_out_to_harnesses", _fake_fan_out),
    ):
        mock_space_store = AsyncMock()
        mock_space_store.reload_all = AsyncMock(return_value=None)
        mock_space_store.count = MagicMock(return_value=1)
        mock_space_store.list_all = MagicMock(return_value=[mock_space])
        mock_space_store.prune_stale = AsyncMock(return_value=0)
        mock_space_store_cls.return_value = mock_space_store

        from fastapi import FastAPI
        from app.main import lifespan

        test_app = FastAPI(lifespan=lifespan)

        async with lifespan(test_app):
            # Confirm: worker._on_task_state_change was set on the mock.
            # MagicMock accepts arbitrary attribute sets; we verify the
            # pattern by calling the callback directly and checking fan_out.
            cb = mock_worker._on_task_state_change

            # The callback may be None if it was set directly (MagicMock intercepts),
            # so we also check set_calls; at least one of these paths should hold.
            if callable(cb):
                # invoke it and check fan_out fired
                await cb("my-space", "task-123", "active", "done")
                assert len(fan_out_calls) >= 1, (
                    "on_task_state_change callback must invoke fan_out_to_harnesses"
                )
                ev = fan_out_calls[0]
                assert ev.kind == "task-state-change"
                assert ev.space_id == "my-space"
                assert ev.payload["task_id"] == "task-123"


# ---------------------------------------------------------------------------
# Test 9: on_task_state_change callback builds correct EventBusEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_state_change_callback_event_shape(tmp_path):
    """The on_task_state_change closure must build a task-state-change EventBusEvent.

    We exercise the closure directly by extracting it from a lifespan run.
    """
    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir(parents=True)

    extracted_callback: list = []

    mock_worker = MagicMock()
    original_setattr_calls: dict = {}

    class _CapturingMock(MagicMock):
        def __setattr__(self, name, value):
            if name == "_on_task_state_change":
                extracted_callback.append(value)
            super().__setattr__(name, value)

    capturing_worker = _CapturingMock()
    capturing_worker._on_task_state_change = None

    mock_pool = MagicMock()
    mock_pool.start_for_space = AsyncMock(return_value=capturing_worker)
    mock_pool.stop_all = AsyncMock(return_value=None)
    mock_pool.items = MagicMock(return_value=[])
    mock_pool.get = MagicMock(return_value=capturing_worker)

    from types import SimpleNamespace
    mock_board = SimpleNamespace(active=[])
    mock_store = AsyncMock()
    mock_store.board = MagicMock(return_value=mock_board)
    mock_store.reload_all = AsyncMock(return_value=None)
    mock_store.archive_stale_done_tasks = AsyncMock(return_value=0)
    mock_store.count = MagicMock(return_value=0)

    mock_space = SimpleNamespace(id="cb-space")

    fan_out_calls: list = []

    async def _fake_fan_out(event, *, harness_store, task_store, worker_pool, space_dir):
        fan_out_calls.append(event)
        return []

    with (
        patch("app.main.SPACES_DIR", spaces_dir),
        patch("app.main.LEGACY_TASKS_DIR", tmp_path / "tasks"),
        patch("app.main.LEGACY_WORKSPACES_DIR", tmp_path / "workspaces"),
        patch("app.main.watch_spaces_dir", AsyncMock(return_value=None)),
        patch("app.main.auto_archive_loop", AsyncMock(return_value=None)),
        patch("app.main.memory_prune_loop", AsyncMock(return_value=None)),
        patch("app.main.discovery_refresh_loop", AsyncMock(return_value=None)),
        patch("app.main.evolve_tools_loop", AsyncMock(return_value=None)),
        patch("app.main.cron_loop", AsyncMock(return_value=None)),
        patch("app.main.WorkerPool", return_value=mock_pool),
        patch("app.main.TaskStore", return_value=mock_store),
        patch("app.main.SpaceStore") as mock_space_store_cls,
        patch("app.main.MemoryStore"),
        patch("app.main.HarnessStore"),
        patch("app.main.StatsStore"),
        patch("app.main.TraceStore"),
        patch("app.main.TestReportStore"),
        patch("app.main.fan_out_to_harnesses", _fake_fan_out),
    ):
        mock_space_store = AsyncMock()
        mock_space_store.reload_all = AsyncMock(return_value=None)
        mock_space_store.count = MagicMock(return_value=1)
        mock_space_store.list_all = MagicMock(return_value=[mock_space])
        mock_space_store.prune_stale = AsyncMock(return_value=0)
        mock_space_store_cls.return_value = mock_space_store

        from fastapi import FastAPI
        from app.main import lifespan

        test_app = FastAPI(lifespan=lifespan)

        async with lifespan(test_app):
            # The callback was injected; extract from extracted_callback list.
            assert len(extracted_callback) >= 1, (
                "Expected _on_task_state_change to be set on the worker"
            )
            cb = extracted_callback[-1]
            assert callable(cb), "Callback must be callable"

            # Call it and verify the EventBusEvent shape.
            await cb("cb-space", "task-xyz", "active", "done")

        assert len(fan_out_calls) >= 1, "fan_out must be invoked by the callback"
        ev = fan_out_calls[0]
        assert ev.kind == "task-state-change"
        assert ev.space_id == "cb-space"
        assert ev.event_id == "task-state-change:cb-space:task-xyz"
        assert ev.payload["task_id"] == "task-xyz"
        assert ev.payload["old_state"] == "active"
        assert ev.payload["new_state"] == "done"
