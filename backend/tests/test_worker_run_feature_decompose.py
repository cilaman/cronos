"""Tests for worker._run_feature_decompose — I7 acceptance criteria.

Covers all 5 outcome branches:
1. success-with-items: status=DONE AND realizing_items >= 1 → feature_state=PLANNED, task.state=DONE
2. success-zero-items: status=DONE AND realizing_items == 0 → feature_state=WAITING, task.state=WAITING
3. WAIT: status=WAIT → feature_state=WAITING, task.state=WAITING
4. BLOCKED: status=BLOCKED → feature_state=WAITING, task.state=WAITING
5. crash: agent raises Exception → feature_state=WAITING, task.state=WAITING

Also verifies:
- Prompt is prefixed with "Use the feature-decompose skill ..."
- finalize_run is called to persist task state + history + waiting_question
- transition_feature is called with FEATURE_WORKER_TRANSITIONS
- run_start and run_end events are published
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.agent import AgentResult, Status
from app.feature_state import FeatureState, FEATURE_WORKER_TRANSITIONS
from app.models import Task, TaskState
from app.storage import TaskSummary
from app.worker import Worker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature_task(
    *,
    task_id: str = "feat-001",
    space_id: str = "space-abc",
    task_type: str = "feature",
    feature_state: FeatureState = FeatureState.PROCESSING,
    title: str = "Add OAuth login",
    brief: str = "Allow users to log in with Google.",
) -> Task:
    """Build a minimal feature/fix Task in ACTIVE state."""
    return Task(
        id=task_id,
        space_id=space_id,
        title=title,
        brief=brief,
        state=TaskState.ACTIVE,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
        type=task_type,
        feature_state=feature_state,
    )


def _make_agent_result(
    *,
    status: Status | None = Status.DONE,
    final_text: str = "Decomposed successfully.",
    exit_code: int = 0,
    session_id: str | None = "sess-abc",
    context: str | None = None,
) -> AgentResult:
    """Build a minimal AgentResult."""
    return AgentResult(
        exit_code=exit_code,
        session_id=session_id,
        final_text=final_text,
        stderr_tail="",
        status=status,
        context=context,
        raw_events=[],
    )


def _make_task_summary(task_id: str = "goal-001") -> TaskSummary:
    """Build a minimal TaskSummary (realizing item)."""
    now = datetime(2024, 1, 1)
    return TaskSummary(
        id=task_id,
        space_id="space-abc",
        title="Realizing goal",
        state=TaskState.ACTIVE,
        type="goal",
        priority=3,
        parent_id=None,
        created_at=now,
        updated_at=now,
    )


def _make_worker(
    task: Task | None,
    *,
    realizing_items: list | None = None,
) -> tuple[Worker, MagicMock]:
    """Build a Worker with mocked store, returning (worker, mock_store)."""
    mock_store = MagicMock()
    mock_store.get = MagicMock(return_value=task)
    mock_store.finalize_run = AsyncMock()
    mock_store.transition_feature = AsyncMock()
    mock_store.realizing_items = AsyncMock(return_value=realizing_items or [])

    worker = Worker(store=mock_store)
    worker.space_store = None  # no space_store needed for unit tests
    return worker, mock_store


# ---------------------------------------------------------------------------
# Branch 1: success-with-items — DONE + >= 1 realizing item → PLANNED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_with_items_transitions_to_planned():
    """DONE status + 1 realizing item → feature_state=PLANNED, task.state=DONE."""
    task = _make_feature_task()
    items = [_make_task_summary()]
    worker, mock_store = _make_worker(task, realizing_items=items)

    result = _make_agent_result(status=Status.DONE)

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        await worker._run_feature_decompose(task.id, None)

    mock_store.finalize_run.assert_called_once()
    call_kwargs = mock_store.finalize_run.call_args
    assert call_kwargs.kwargs["new_state"] == TaskState.DONE
    assert call_kwargs.kwargs["waiting_question"] is None

    mock_store.transition_feature.assert_called_once_with(
        task.id,
        FeatureState.PLANNED,
        allowed=FEATURE_WORKER_TRANSITIONS,
    )


@pytest.mark.asyncio
async def test_success_with_items_preserves_session_id():
    """On success, the session_id from the agent result is passed to finalize_run."""
    task = _make_feature_task()
    items = [_make_task_summary()]
    worker, mock_store = _make_worker(task, realizing_items=items)

    result = _make_agent_result(status=Status.DONE, session_id="sess-xyz")

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        await worker._run_feature_decompose(task.id, None)

    call_kwargs = mock_store.finalize_run.call_args
    assert call_kwargs.kwargs["session_id"] == "sess-xyz"


@pytest.mark.asyncio
async def test_success_with_multiple_items_transitions_to_planned():
    """DONE + 3 realizing items → PLANNED (multi-item success)."""
    task = _make_feature_task()
    items = [_make_task_summary(f"goal-{i}") for i in range(3)]
    worker, mock_store = _make_worker(task, realizing_items=items)

    result = _make_agent_result(status=Status.DONE)

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        await worker._run_feature_decompose(task.id, None)

    call_kwargs = mock_store.transition_feature.call_args
    assert call_kwargs.args[1] == FeatureState.PLANNED


# ---------------------------------------------------------------------------
# Branch 2: success-zero-items — DONE but no realizing items → WAITING
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_zero_items_transitions_to_waiting():
    """DONE status + 0 realizing items → feature_state=WAITING, task.state=WAITING."""
    task = _make_feature_task()
    worker, mock_store = _make_worker(task, realizing_items=[])

    result = _make_agent_result(status=Status.DONE)

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        await worker._run_feature_decompose(task.id, None)

    call_kwargs = mock_store.finalize_run.call_args
    assert call_kwargs.kwargs["new_state"] == TaskState.WAITING
    assert "no tasks" in (call_kwargs.kwargs["waiting_question"] or "").lower()

    mock_store.transition_feature.assert_called_once_with(
        task.id,
        FeatureState.WAITING,
        allowed=FEATURE_WORKER_TRANSITIONS,
    )


# ---------------------------------------------------------------------------
# Branch 3: WAIT — agent requests human input → WAITING
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_status_transitions_to_waiting():
    """STATUS: WAIT → feature_state=WAITING, task.state=WAITING."""
    task = _make_feature_task()
    worker, mock_store = _make_worker(task, realizing_items=[])

    result = _make_agent_result(
        status=Status.WAIT,
        context="Which authentication provider should I target?",
    )

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        await worker._run_feature_decompose(task.id, None)

    call_kwargs = mock_store.finalize_run.call_args
    assert call_kwargs.kwargs["new_state"] == TaskState.WAITING
    assert call_kwargs.kwargs["waiting_question"] is not None

    mock_store.transition_feature.assert_called_once_with(
        task.id,
        FeatureState.WAITING,
        allowed=FEATURE_WORKER_TRANSITIONS,
    )


@pytest.mark.asyncio
async def test_wait_status_uses_context_as_waiting_question():
    """STATUS: WAIT with context → waiting_question == context."""
    task = _make_feature_task()
    worker, mock_store = _make_worker(task, realizing_items=[])

    result = _make_agent_result(
        status=Status.WAIT,
        context="Need clarification on scope",
    )

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        await worker._run_feature_decompose(task.id, None)

    call_kwargs = mock_store.finalize_run.call_args
    assert call_kwargs.kwargs["waiting_question"] == "Need clarification on scope"


@pytest.mark.asyncio
async def test_wait_status_no_context_fallback():
    """STATUS: WAIT without context → waiting_question is a non-empty fallback."""
    task = _make_feature_task()
    worker, mock_store = _make_worker(task, realizing_items=[])

    result = _make_agent_result(status=Status.WAIT, context=None)

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        await worker._run_feature_decompose(task.id, None)

    call_kwargs = mock_store.finalize_run.call_args
    q = call_kwargs.kwargs["waiting_question"]
    assert q is not None and len(q) > 0


# ---------------------------------------------------------------------------
# Branch 4: BLOCKED — agent is blocked → WAITING
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocked_status_transitions_to_waiting():
    """STATUS: BLOCKED → feature_state=WAITING, task.state=WAITING."""
    task = _make_feature_task()
    worker, mock_store = _make_worker(task, realizing_items=[])

    result = _make_agent_result(status=Status.BLOCKED, context="Duplicate feature detected")

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        await worker._run_feature_decompose(task.id, None)

    call_kwargs = mock_store.finalize_run.call_args
    assert call_kwargs.kwargs["new_state"] == TaskState.WAITING
    assert "blocked" in (call_kwargs.kwargs["waiting_question"] or "").lower()

    mock_store.transition_feature.assert_called_once_with(
        task.id,
        FeatureState.WAITING,
        allowed=FEATURE_WORKER_TRANSITIONS,
    )


# ---------------------------------------------------------------------------
# Branch 5: crash — agent raises Exception → WAITING
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crash_exception_transitions_to_waiting():
    """Agent raises Exception → feature_state=WAITING, task.state=WAITING."""
    task = _make_feature_task()
    worker, mock_store = _make_worker(task, realizing_items=[])

    with patch("app.worker.run_agent", new=AsyncMock(side_effect=RuntimeError("claude crashed"))):
        await worker._run_feature_decompose(task.id, None)

    call_kwargs = mock_store.finalize_run.call_args
    assert call_kwargs.kwargs["new_state"] == TaskState.WAITING
    assert call_kwargs.kwargs["waiting_question"] is not None
    # session_id must be None on crash
    assert call_kwargs.kwargs["session_id"] is None

    mock_store.transition_feature.assert_called_once_with(
        task.id,
        FeatureState.WAITING,
        allowed=FEATURE_WORKER_TRANSITIONS,
    )


@pytest.mark.asyncio
async def test_crash_file_not_found_transitions_to_waiting():
    """FileNotFoundError (claude binary missing) → feature_state=WAITING."""
    task = _make_feature_task()
    worker, mock_store = _make_worker(task, realizing_items=[])

    with patch(
        "app.worker.run_agent",
        new=AsyncMock(side_effect=FileNotFoundError("claude not found")),
    ):
        await worker._run_feature_decompose(task.id, None)

    call_kwargs = mock_store.finalize_run.call_args
    assert call_kwargs.kwargs["new_state"] == TaskState.WAITING
    mock_store.transition_feature.assert_called_once_with(
        task.id,
        FeatureState.WAITING,
        allowed=FEATURE_WORKER_TRANSITIONS,
    )


# ---------------------------------------------------------------------------
# No-STATUS marker branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_status_marker_transitions_to_waiting():
    """Agent exits 0 but produces no STATUS marker → feature_state=WAITING."""
    task = _make_feature_task()
    worker, mock_store = _make_worker(task, realizing_items=[])

    result = _make_agent_result(status=None, exit_code=0)

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        await worker._run_feature_decompose(task.id, None)

    call_kwargs = mock_store.finalize_run.call_args
    assert call_kwargs.kwargs["new_state"] == TaskState.WAITING
    assert "no status" in (call_kwargs.kwargs["waiting_question"] or "").lower()

    mock_store.transition_feature.assert_called_once_with(
        task.id,
        FeatureState.WAITING,
        allowed=FEATURE_WORKER_TRANSITIONS,
    )


# ---------------------------------------------------------------------------
# Prompt prefix verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_prefix_contains_feature_decompose_skill():
    """The user_message passed to run_agent must contain the skill invocation prefix."""
    task = _make_feature_task()
    items = [_make_task_summary()]
    worker, mock_store = _make_worker(task, realizing_items=items)

    result = _make_agent_result(status=Status.DONE)
    captured: list[str] = []

    async def capture_run_agent(t, *, user_message, **kwargs):
        captured.append(user_message or "")
        return result

    with patch("app.worker.run_agent", new=capture_run_agent):
        await worker._run_feature_decompose(task.id, None)

    assert len(captured) == 1
    assert "feature-decompose" in captured[0], (
        f"Expected 'feature-decompose' in prompt, got: {captured[0]!r}"
    )


@pytest.mark.asyncio
async def test_prompt_prefix_includes_skill_instruction():
    """The user_message must contain 'Use the feature-decompose skill' verbatim."""
    task = _make_feature_task()
    items = [_make_task_summary()]
    worker, mock_store = _make_worker(task, realizing_items=items)

    result = _make_agent_result(status=Status.DONE)
    captured: list[str] = []

    async def capture_run_agent(t, *, user_message, **kwargs):
        captured.append(user_message or "")
        return result

    with patch("app.worker.run_agent", new=capture_run_agent):
        await worker._run_feature_decompose(task.id, None)

    assert "Use the feature-decompose skill" in captured[0]


# ---------------------------------------------------------------------------
# SSE events published
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_start_event_published():
    """_run_feature_decompose must publish a run_start event before the agent call."""
    task = _make_feature_task()
    items = [_make_task_summary()]
    worker, mock_store = _make_worker(task, realizing_items=items)

    result = _make_agent_result(status=Status.DONE)
    published: list[dict] = []

    async def capture_publish(tid, event):
        published.append(event)

    worker._publish = AsyncMock(side_effect=capture_publish)  # type: ignore[method-assign]

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        await worker._run_feature_decompose(task.id, None)

    event_types = [e.get("type") for e in published]
    assert "run_start" in event_types


@pytest.mark.asyncio
async def test_run_end_event_published():
    """_run_feature_decompose must publish a run_end event after completion."""
    task = _make_feature_task()
    items = [_make_task_summary()]
    worker, mock_store = _make_worker(task, realizing_items=items)

    result = _make_agent_result(status=Status.DONE)
    published: list[dict] = []

    async def capture_publish(tid, event):
        published.append(event)

    worker._publish = AsyncMock(side_effect=capture_publish)  # type: ignore[method-assign]

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        await worker._run_feature_decompose(task.id, None)

    event_types = [e.get("type") for e in published]
    assert "run_end" in event_types


# ---------------------------------------------------------------------------
# Unknown task_id: graceful no-op
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_task_id_no_op():
    """Unknown task_id must return without calling run_agent, finalize_run, or transition_feature."""
    worker, mock_store = _make_worker(task=None)
    mock_store.get = MagicMock(return_value=None)

    with patch("app.worker.run_agent", new=AsyncMock()) as mock_run_agent:
        await worker._run_feature_decompose("nonexistent", None)

    mock_run_agent.assert_not_called()
    mock_store.finalize_run.assert_not_called()
    mock_store.transition_feature.assert_not_called()


# ---------------------------------------------------------------------------
# finalize_run / transition_feature fault tolerance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_run_exception_does_not_abort():
    """Exception in finalize_run must be swallowed — transition_feature still called."""
    task = _make_feature_task()
    items = [_make_task_summary()]
    worker, mock_store = _make_worker(task, realizing_items=items)

    mock_store.finalize_run.side_effect = RuntimeError("DB write failed")

    result = _make_agent_result(status=Status.DONE)

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        # Must not raise
        await worker._run_feature_decompose(task.id, None)

    # transition_feature is still called even if finalize_run raised
    mock_store.transition_feature.assert_called_once()


@pytest.mark.asyncio
async def test_transition_feature_exception_does_not_abort():
    """Exception in transition_feature must be swallowed — does not propagate."""
    task = _make_feature_task()
    items = [_make_task_summary()]
    worker, mock_store = _make_worker(task, realizing_items=items)

    mock_store.transition_feature.side_effect = RuntimeError("state transition failed")

    result = _make_agent_result(status=Status.DONE)

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        # Must not raise
        await worker._run_feature_decompose(task.id, None)

    # finalize_run was called before the transition failure
    mock_store.finalize_run.assert_called_once()


# ---------------------------------------------------------------------------
# fix type (not just feature)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fix_type_success_with_items_transitions_to_planned():
    """task.type == 'fix' behaves identically to 'feature' on success."""
    task = _make_feature_task(task_type="fix")
    items = [_make_task_summary()]
    worker, mock_store = _make_worker(task, realizing_items=items)

    result = _make_agent_result(status=Status.DONE)

    with patch("app.worker.run_agent", new=AsyncMock(return_value=result)):
        await worker._run_feature_decompose(task.id, None)

    mock_store.transition_feature.assert_called_once_with(
        task.id,
        FeatureState.PLANNED,
        allowed=FEATURE_WORKER_TRANSITIONS,
    )
