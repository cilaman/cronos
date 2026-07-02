"""Tests for app.run_executor.RunExecutor — task/goal/harness execution."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.run_executor import RunExecutor, _is_clean_no_status, _topo_children_local
from app.agent import AgentResult, Status
from app.models import TaskState


def _result(**kw) -> AgentResult:
    base = dict(
        exit_code=0, session_id="s", final_text="", stderr_tail="",
        status=None, context=None, raw_events=[], stopped=False, result_subtype=None,
    )
    base.update(kw)
    return AgentResult(**base)


class TestIsCleanNoStatus:
    def test_clean_no_status_matches(self):
        assert _is_clean_no_status(_result(exit_code=0, status=None)) is True

    def test_none_result_does_not_match(self):
        assert _is_clean_no_status(None) is False

    def test_crash_does_not_match(self):
        assert _is_clean_no_status(_result(exit_code=1, status=None)) is False

    def test_stopped_does_not_match(self):
        assert _is_clean_no_status(_result(stopped=True)) is False

    def test_genuine_wait_does_not_match(self):
        assert _is_clean_no_status(_result(status=Status.WAIT)) is False

    def test_genuine_done_does_not_match(self):
        assert _is_clean_no_status(_result(status=Status.DONE)) is False


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_bus() -> MagicMock:
    bus = MagicMock()
    bus.publish = MagicMock()
    bus.clear_buffer = MagicMock()
    bus.drain_subscribers = MagicMock()
    bus.lookup_space_id = MagicMock(return_value=None)
    return bus


def _make_worker() -> MagicMock:
    w = MagicMock()
    w._current_id = None
    w._current_cancel = None
    w._current_child_id = None
    w._owner_id = "test-owner"
    w._pool = None
    w.stats_store = None
    w.trace_store = None
    w.memory_store = None
    w.space_store = None
    w.harness_store = None
    w._pool = None
    # Forward _publish to bus.publish via async wrapper.
    w._publish = AsyncMock()
    return w


def _make_store(task=None) -> MagicMock:
    store = MagicMock()
    store.get = MagicMock(return_value=task)
    store.all = MagicMock(return_value=[])
    store.finalize_run = AsyncMock()
    store.transition = AsyncMock()
    store.drain_pending = AsyncMock(return_value=[])
    store.acquire_lease = MagicMock(return_value=False)
    store.release_lease = MagicMock()
    store.heartbeat_lease = MagicMock()
    return store


def _make_task(
    task_id: str = "t1",
    space_id: str = "sp1",
    state: TaskState = TaskState.ACTIVE,
    task_type: str = "task",
) -> MagicMock:
    t = MagicMock()
    t.id = task_id
    t.space_id = space_id
    t.state = state
    t.type = task_type
    t.title = "Test task"
    t.brief = ""
    t.agent_model = "default"
    t.agent_mode = "auto"
    t.parent_id = None
    t.depends_on = []
    t.manual_order = 0
    return t


def _make_finalizer() -> MagicMock:
    f = MagicMock()
    f.space_store = None
    f.pool = None
    f.finalize = AsyncMock()
    f.finalize_child = AsyncMock(return_value=TaskState.DONE)
    return f


def _make_executor(task=None, store=None) -> tuple[RunExecutor, MagicMock, MagicMock]:
    if store is None:
        store = _make_store(task)
    bus = _make_bus()
    worker = _make_worker()
    finalizer = _make_finalizer()
    from app import memory_retrieval
    ex = RunExecutor(
        worker=worker,
        store=store,
        event_bus=bus,
        finalizer=finalizer,
        space_store=None,
        harness_store=None,
        memory_store=None,
        done_sentinel={"type": "stream_end"},
        lease_ttl=30.0,
        heartbeat_interval=5.0,
        memory_retrieval=memory_retrieval,
    )
    # Wire worker._Worker__run_task_body to executor's run_task_body for delegation
    async def _worker_run_task_body(tid, msg, t):
        ex.space_store = worker.space_store
        await ex.run_task_body(tid, msg, t)
    worker._Worker__run_task_body = _worker_run_task_body

    async def _worker_run_fd_inner(tid, msg, t):
        ex.space_store = worker.space_store
        await ex.run_feature_decompose_inner(tid, msg, t)
    worker._Worker__run_feature_decompose_inner = _worker_run_fd_inner

    async def _worker_execute_harness_body(tid, hid, sid, *, initial_run, space):
        ex.space_store = worker.space_store
        ex.harness_store = worker.harness_store
        return await ex.execute_harness_run_body(tid, hid, sid, initial_run=initial_run, space=space)
    worker._Worker__execute_harness_run_body = _worker_execute_harness_body

    async def _worker_execute_harness_run(tid, hid, sid, initial_run):
        ex.space_store = worker.space_store
        ex.harness_store = worker.harness_store
        return await ex.execute_harness_run(tid, hid, sid, initial_run=initial_run)
    worker._execute_harness_run = _worker_execute_harness_run

    return ex, store, bus


# ── _topo_children_local ──────────────────────────────────────────────────────

def test_topo_children_no_children():
    store = MagicMock()
    store.all = MagicMock(return_value=[])
    result = _topo_children_local("goal-1", store)
    assert result == []


def test_topo_children_respects_dependency_order():
    from unittest.mock import MagicMock

    task_a = MagicMock()
    task_a.id = "a"
    task_a.parent_id = "goal-1"
    task_a.depends_on = []
    task_a.manual_order = 0

    task_b = MagicMock()
    task_b.id = "b"
    task_b.parent_id = "goal-1"
    task_b.depends_on = ["a"]
    task_b.manual_order = 1

    store = MagicMock()
    store.all = MagicMock(return_value=[task_a, task_b])
    result = _topo_children_local("goal-1", store)
    assert result == ["a", "b"]


# ── run_task ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_task_skips_unknown_task():
    store = _make_store(None)
    ex, _, _ = _make_executor(store=store)
    # Should log a warning and return without calling run_task_body.
    await ex.run_task("unknown-task", None)


@pytest.mark.asyncio
async def test_run_task_skips_when_lease_not_won():
    task = _make_task()
    store = _make_store(task)
    store.acquire_lease = MagicMock(return_value=False)
    ex, _, bus = _make_executor(task, store)

    # Mock harness run checkers to return False (not a harness task).
    with patch.object(ex, "resume_harness_run", AsyncMock(return_value=False)), \
         patch.object(ex, "run_initial_harness_run", AsyncMock(return_value=False)):
        await ex.run_task_body("t1", None, task)

    # finalize should NOT be called since lease wasn't won.
    ex._finalizer.finalize.assert_not_called()


@pytest.mark.asyncio
async def test_run_task_handles_harness_resume():
    task = _make_task()
    store = _make_store(task)
    ex, _, bus = _make_executor(task, store)

    with patch.object(ex, "resume_harness_run", AsyncMock(return_value=True)):
        await ex.run_task_body("t1", None, task)

    # Worker's _publish should be called with run_end.
    publishes = [call for call in ex._worker._publish.call_args_list
                 if call[0][1].get("type") == "run_end"]
    assert publishes


@pytest.mark.asyncio
async def test_run_task_handles_initial_harness_run():
    task = _make_task()
    store = _make_store(task)
    ex, _, bus = _make_executor(task, store)

    with patch.object(ex, "resume_harness_run", AsyncMock(return_value=False)), \
         patch.object(ex, "run_initial_harness_run", AsyncMock(return_value=True)):
        await ex.run_task_body("t1", None, task)

    publishes = [call for call in ex._worker._publish.call_args_list
                 if call[0][1].get("type") == "run_end"]
    assert publishes


# ── run_goal ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_goal_skips_unknown_goal():
    store = _make_store(None)
    ex, _, _ = _make_executor(store=store)
    await ex.run_goal("unknown-goal", None)


@pytest.mark.asyncio
async def test_run_goal_skips_done_goal():
    task = _make_task(state=TaskState.DONE, task_type="goal")
    ex, store, _ = _make_executor(task)
    await ex.run_goal("t1", None)
    store.finalize_run.assert_not_called()


@pytest.mark.asyncio
async def test_run_goal_with_no_children_parks_waiting():
    # A childless goal is parked WAITING (needs decomposition) rather than
    # silently DONE — see run_executor finalize guard (symptom: nested empty
    # subgoals cascading a whole tree to DONE).
    goal = _make_task(task_type="goal")
    store = _make_store(goal)
    store.all = MagicMock(return_value=[])
    ex, _, bus = _make_executor(goal, store)
    await ex.run_goal("t1", None)
    store.finalize_run.assert_called_once()
    call_kwargs = store.finalize_run.call_args.kwargs
    assert call_kwargs["new_state"] == TaskState.WAITING


@pytest.mark.asyncio
async def test_run_goal_child_in_wrong_state_pauses_goal():
    goal = _make_task("g1", task_type="goal")
    child = _make_task("c1")
    child.parent_id = "g1"
    child.state = TaskState.WAITING  # wrong state

    store = _make_store(goal)
    store.get = MagicMock(side_effect=lambda tid: goal if tid == "g1" else child)
    store.all = MagicMock(return_value=[child])
    ex, _, bus = _make_executor(store=store)
    await ex.run_goal("g1", None)
    store.finalize_run.assert_called_once()
    call_kwargs = store.finalize_run.call_args.kwargs
    assert call_kwargs["new_state"] == TaskState.WAITING


# ── run_feature_decompose ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_feature_decompose_skips_unknown_task():
    store = _make_store(None)
    ex, _, _ = _make_executor(store=store)
    await ex.run_feature_decompose("unknown", None)


@pytest.mark.asyncio
async def test_run_feature_decompose_agent_crash_transitions_to_waiting():
    task = _make_task()
    store = _make_store(task)
    store.finalize_run = AsyncMock()
    store.transition_feature = AsyncMock()
    store.realizing_items = AsyncMock(return_value=[])
    ex, _, _ = _make_executor(task, store)

    with patch("app.worker.run_agent", side_effect=RuntimeError("crash")):
        await ex.run_feature_decompose_inner("t1", None, task)

    call_kwargs = store.finalize_run.call_args.kwargs
    assert call_kwargs["new_state"] == TaskState.WAITING


# ── harness execution ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_harness_run_returns_false_when_no_harness_store():
    ex, _, _ = _make_executor()
    ex.harness_store = None
    result = await ex.execute_harness_run("t1", "h1", "sp1", initial_run=True)
    assert result is False


@pytest.mark.asyncio
async def test_execute_harness_run_returns_false_when_space_not_found():
    ex, _, _ = _make_executor()
    ex.harness_store = MagicMock()
    ex.space_store = MagicMock()
    ex.space_store.get = MagicMock(return_value=None)
    result = await ex.execute_harness_run("t1", "h1", "sp1", initial_run=True)
    assert result is False


@pytest.mark.asyncio
async def test_resume_harness_run_returns_false_when_no_harness_store():
    ex, _, _ = _make_executor()
    ex.harness_store = None
    result = await ex.resume_harness_run("t1")
    assert result is False


@pytest.mark.asyncio
async def test_resume_harness_run_returns_false_when_task_not_found():
    store = _make_store(None)
    ex, _, _ = _make_executor(store=store)
    ex.harness_store = MagicMock()
    ex.space_store = MagicMock()
    result = await ex.resume_harness_run("t1")
    assert result is False


@pytest.mark.asyncio
async def test_resume_harness_run_returns_false_when_run_state_file_missing():
    task = _make_task()
    store = _make_store(task)
    ex, _, _ = _make_executor(task, store)
    ex.harness_store = MagicMock()
    ex.space_store = MagicMock()
    # Path.exists returns False by default.
    with patch("app.run_executor.RunExecutor._data_dir") as mock_dir:
        fake_path = MagicMock()
        fake_path.__truediv__ = MagicMock(return_value=fake_path)
        fake_path.exists = MagicMock(return_value=False)
        mock_dir.return_value = fake_path
        result = await ex.resume_harness_run("t1")
    assert result is False


@pytest.mark.asyncio
async def test_run_initial_harness_run_returns_false_when_no_space_id():
    ex, _, _ = _make_executor()
    ex._bus.lookup_space_id = MagicMock(return_value=None)
    result = await ex.run_initial_harness_run("run-1")
    assert result is False


@pytest.mark.asyncio
async def test_run_initial_harness_run_returns_false_when_no_harness_store():
    ex, _, _ = _make_executor()
    ex._bus.lookup_space_id = MagicMock(return_value="sp1")
    ex.harness_store = None
    result = await ex.run_initial_harness_run("run-1")
    assert result is False
