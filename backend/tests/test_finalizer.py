"""Tests for app.finalizer.Finalizer — post-run state machine."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.finalizer import Finalizer, _extract_subagent_types, _parse_merge_meta
from app.agent import Status
from app.models import TaskState


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_store(task=None) -> MagicMock:
    store = MagicMock()
    store.get = MagicMock(return_value=task)
    store.finalize_run = AsyncMock()
    store.drain_pending = AsyncMock(return_value=[])
    store.increment_run_index = MagicMock(return_value=0)
    store.spaces_dir = MagicMock()
    return store


def _make_event_bus() -> MagicMock:
    bus = MagicMock()
    bus.publish = MagicMock()
    bus.clear_buffer = MagicMock()
    bus.drain_subscribers = MagicMock()
    return bus


def _make_side_effects() -> MagicMock:
    se = MagicMock()
    se.stats_store = None
    se.trace_store = None
    se.memory_store = None
    se.record_telemetry = AsyncMock()
    se.save_memory_blocks = AsyncMock()
    se.save_cronos_remember_blocks = AsyncMock()
    return se


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
    t.pending_messages = []
    t.run_count = 0
    return t


def _make_result(
    status: Status | None = Status.DONE,
    exit_code: int = 0,
    stopped: bool = False,
    final_text: str = "done",
) -> MagicMock:
    r = MagicMock()
    r.status = status
    r.exit_code = exit_code
    r.stopped = stopped
    r.final_text = final_text
    r.context = None
    r.session_id = "sess-1"
    r.raw_events = []
    r.stderr_tail = ""
    return r


def _make_finalizer(task=None, store=None, auto_resume_counts=None) -> tuple[Finalizer, MagicMock, MagicMock]:
    if store is None:
        store = _make_store(task)
    bus = _make_event_bus()
    se = _make_side_effects()
    fn = Finalizer(
        store=store,
        event_bus=bus,
        side_effects=se,
        space_store=None,
        pool=None,
        on_task_state_change=None,
        auto_resume_counts=auto_resume_counts or {},
        enqueue_fn=AsyncMock(),
        done_sentinel={"type": "stream_end"},
    )
    return fn, store, bus


# ── _parse_merge_meta ─────────────────────────────────────────────────────────

def test_parse_merge_meta_returns_none_for_no_meta():
    assert _parse_merge_meta("no merge meta here") is None


def test_parse_merge_meta_extracts_fields():
    brief = (
        "<!-- merge-meta\n"
        "space_id: myspace\n"
        "kind: tool\n"
        "name: my-tool\n"
        "upstream_source_sha: abc123\n"
        "-->"
    )
    meta = _parse_merge_meta(brief)
    assert meta is not None
    assert meta["space_id"] == "myspace"
    assert meta["kind"] == "tool"
    assert meta["name"] == "my-tool"
    assert meta["upstream_source_sha"] == "abc123"


# ── _extract_subagent_types ───────────────────────────────────────────────────

def test_extract_subagent_types_empty():
    assert _extract_subagent_types([]) == []


def test_extract_subagent_types_extracts_unique_lower():
    events = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Agent",
                        "input": {"subagent_type": "Tester"},
                    },
                    {
                        "type": "tool_use",
                        "name": "Agent",
                        "input": {"subagent_type": "Tester"},  # duplicate
                    },
                    {
                        "type": "tool_use",
                        "name": "Agent",
                        "input": {"subagent_type": "Reviewer"},
                    },
                ]
            },
        }
    ]
    result = _extract_subagent_types(events)
    assert result == ["tester", "reviewer"]


def test_extract_subagent_types_skips_non_agent_tools():
    events = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Bash", "input": {}},
                ]
            },
        }
    ]
    assert _extract_subagent_types(events) == []


def test_extract_subagent_types_skips_non_assistant_events():
    events = [{"type": "user", "message": {"content": [{"type": "tool_use", "name": "Agent", "input": {"subagent_type": "X"}}]}}]
    assert _extract_subagent_types(events) == []


def test_extract_subagent_types_skips_non_dict_content_blocks():
    events = [
        {
            "type": "assistant",
            "message": {
                "content": ["not a dict", None],
            },
        }
    ]
    assert _extract_subagent_types(events) == []


# ── finalize (regular task) ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_finalize_done_transitions_to_done():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    with patch("app.finalizer.goal_sync.propagate_to_parent", new=AsyncMock()), \
         patch("app.finalizer.feature_sync.propagate_to_feature", new=AsyncMock()):
        await fn.finalize("t1", _make_result(Status.DONE), started_at=datetime.now(tz=UTC))
    store.finalize_run.assert_called_once()
    call_kwargs = store.finalize_run.call_args.kwargs
    assert call_kwargs["new_state"] == TaskState.DONE


@pytest.mark.asyncio
async def test_finalize_wait_transitions_to_waiting():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    result = _make_result(Status.WAIT)
    result.context = "Need input"
    with patch("app.finalizer.goal_sync.propagate_to_parent", new=AsyncMock()), \
         patch("app.finalizer.feature_sync.propagate_to_feature", new=AsyncMock()):
        await fn.finalize("t1", result, started_at=datetime.now(tz=UTC))
    call_kwargs = store.finalize_run.call_args.kwargs
    assert call_kwargs["new_state"] == TaskState.WAITING
    assert "Need input" in (call_kwargs.get("waiting_question") or "")


@pytest.mark.asyncio
async def test_finalize_blocked_transitions_to_waiting():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    with patch("app.finalizer.goal_sync.propagate_to_parent", new=AsyncMock()), \
         patch("app.finalizer.feature_sync.propagate_to_feature", new=AsyncMock()):
        await fn.finalize("t1", _make_result(Status.BLOCKED), started_at=datetime.now(tz=UTC))
    call_kwargs = store.finalize_run.call_args.kwargs
    assert call_kwargs["new_state"] == TaskState.WAITING


@pytest.mark.asyncio
async def test_finalize_stopped_transitions_to_waiting():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    result = _make_result(Status.DONE)
    result.stopped = True
    with patch("app.finalizer.goal_sync.propagate_to_parent", new=AsyncMock()), \
         patch("app.finalizer.feature_sync.propagate_to_feature", new=AsyncMock()):
        await fn.finalize("t1", result, started_at=datetime.now(tz=UTC))
    call_kwargs = store.finalize_run.call_args.kwargs
    assert call_kwargs["new_state"] == TaskState.WAITING


@pytest.mark.asyncio
async def test_finalize_nonzero_exit_transitions_to_waiting():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    # status=None means no STATUS marker, exit_code=1 means crash.
    result = _make_result(status=None, exit_code=1)
    with patch("app.finalizer.goal_sync.propagate_to_parent", new=AsyncMock()), \
         patch("app.finalizer.feature_sync.propagate_to_feature", new=AsyncMock()):
        await fn.finalize("t1", result, started_at=datetime.now(tz=UTC))
    call_kwargs = store.finalize_run.call_args.kwargs
    assert call_kwargs["new_state"] == TaskState.WAITING


@pytest.mark.asyncio
async def test_finalize_no_status_marker_transitions_to_waiting():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    result = _make_result(status=None)  # no STATUS marker
    with patch("app.finalizer.goal_sync.propagate_to_parent", new=AsyncMock()), \
         patch("app.finalizer.feature_sync.propagate_to_feature", new=AsyncMock()):
        await fn.finalize("t1", result, started_at=datetime.now(tz=UTC))
    call_kwargs = store.finalize_run.call_args.kwargs
    assert call_kwargs["new_state"] == TaskState.WAITING


@pytest.mark.asyncio
async def test_finalize_drains_subscribers():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    with patch("app.finalizer.goal_sync.propagate_to_parent", new=AsyncMock()), \
         patch("app.finalizer.feature_sync.propagate_to_feature", new=AsyncMock()):
        await fn.finalize("t1", _make_result(Status.DONE), started_at=datetime.now(tz=UTC))
    bus.drain_subscribers.assert_called()


@pytest.mark.asyncio
async def test_finalize_publishes_run_end():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    published = []
    bus.publish.side_effect = lambda tid, event: published.append(event)
    with patch("app.finalizer.goal_sync.propagate_to_parent", new=AsyncMock()), \
         patch("app.finalizer.feature_sync.propagate_to_feature", new=AsyncMock()):
        await fn.finalize("t1", _make_result(Status.DONE), started_at=datetime.now(tz=UTC))
    event_types = [e.get("type") for e in published]
    assert "run_end" in event_types


@pytest.mark.asyncio
async def test_finalize_swallows_finalize_run_exception():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    store.finalize_run.side_effect = RuntimeError("db error")
    with patch("app.finalizer.goal_sync.propagate_to_parent", new=AsyncMock()), \
         patch("app.finalizer.feature_sync.propagate_to_feature", new=AsyncMock()):
        # Should not propagate.
        await fn.finalize("t1", _make_result(Status.DONE), started_at=datetime.now(tz=UTC))


@pytest.mark.asyncio
async def test_finalize_on_task_state_change_called():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    cb = AsyncMock()
    fn._on_task_state_change = cb
    with patch("app.finalizer.goal_sync.propagate_to_parent", new=AsyncMock()), \
         patch("app.finalizer.feature_sync.propagate_to_feature", new=AsyncMock()):
        await fn.finalize("t1", _make_result(Status.DONE), started_at=datetime.now(tz=UTC))
    cb.assert_called_once()


# ── finalize_child ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_finalize_child_done_returns_done():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    result = _make_result(Status.DONE)
    state = await fn.finalize_child(
        "t1", result, None, started_at=datetime.now(tz=UTC)
    )
    assert state == TaskState.DONE


@pytest.mark.asyncio
async def test_finalize_child_wait_returns_waiting():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    result = _make_result(Status.WAIT)
    state = await fn.finalize_child(
        "t1", result, None, started_at=datetime.now(tz=UTC)
    )
    assert state == TaskState.WAITING


@pytest.mark.asyncio
async def test_finalize_child_run_exception_returns_waiting():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    state = await fn.finalize_child(
        "t1", None, "agent crashed", started_at=datetime.now(tz=UTC)
    )
    assert state == TaskState.WAITING


@pytest.mark.asyncio
async def test_finalize_child_stopped_returns_waiting():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    result = _make_result(Status.DONE)
    result.stopped = True
    state = await fn.finalize_child(
        "t1", result, None, started_at=datetime.now(tz=UTC)
    )
    assert state == TaskState.WAITING


@pytest.mark.asyncio
async def test_finalize_child_swallows_finalize_run_exception():
    task = _make_task()
    fn, store, bus = _make_finalizer(task)
    store.finalize_run.side_effect = RuntimeError("error")
    # Should not propagate.
    state = await fn.finalize_child(
        "t1", _make_result(Status.DONE), None, started_at=datetime.now(tz=UTC)
    )
    # Returns DONE despite the exception because we swallow errors in finalize_run.
    # (The state is determined before finalize_run is called.)
    assert isinstance(state, TaskState)
