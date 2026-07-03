"""Tests for worker._run_one branching — I6 acceptance criteria.

Verifies:
- task.type == "goal" → _run_goal is called (not _run_task, not _run_feature_decompose).
- task.type in ("feature", "fix") AND feature_state == PROCESSING →
  _run_feature_decompose is called (not _run_task, not _run_goal).
- task.type in ("feature", "fix") AND feature_state != PROCESSING →
  _run_task is called (fall-through to existing behavior).
- task.type == "task" (standard) → _run_task is called.
- Unknown task_id → early return with no method called.
- _run_feature_decompose method exists with the correct async signature.
"""

from __future__ import annotations

import inspect
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.feature_state import FeatureState
from app.models import Task, TaskState
from app.worker import Worker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(
    *,
    task_id: str = "task-001",
    space_id: str = "space-abc",
    task_type: str = "task",
    feature_state: FeatureState | None = None,
) -> Task:
    """Construct a minimal Task object for _run_one routing tests."""
    return Task(
        id=task_id,
        space_id=space_id,
        title="Test task",
        state=TaskState.ACTIVE,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
        type=task_type,
        feature_state=feature_state,
    )


def _make_worker(task: Task | None) -> Worker:
    """Build a minimal Worker with a mocked TaskStore that returns *task*."""
    mock_store = MagicMock()
    mock_store.get = MagicMock(return_value=task)

    worker = Worker(store=mock_store)
    # Patch the three routing targets to be AsyncMocks so we can assert call counts.
    worker._run_goal = AsyncMock()
    worker._run_task = AsyncMock()
    worker._run_feature_decompose = AsyncMock()
    return worker


# ---------------------------------------------------------------------------
# Signature contract
# ---------------------------------------------------------------------------


def test_run_feature_decompose_is_async():
    """_run_feature_decompose must be an async method on Worker."""
    assert inspect.iscoroutinefunction(Worker._run_feature_decompose), (
        "_run_feature_decompose must be a coroutine function (async def)"
    )


def test_run_feature_decompose_signature():
    """_run_feature_decompose must accept (self, task_id, user_message=None)."""
    sig = inspect.signature(Worker._run_feature_decompose)
    params = list(sig.parameters.keys())
    assert "task_id" in params, "task_id parameter required"
    assert "user_message" in params, "user_message parameter required"
    # user_message must have a default of None
    assert sig.parameters["user_message"].default is None, (
        "user_message must default to None"
    )


# ---------------------------------------------------------------------------
# _run_one: unknown task_id → no routing method called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_one_unknown_task_id_no_routing():
    """_run_one with unknown task_id must return without calling any routing method."""
    worker = _make_worker(task=None)
    await worker._run_one("nonexistent-id", None)

    worker._run_goal.assert_not_called()
    worker._run_task.assert_not_called()
    worker._run_feature_decompose.assert_not_called()


# ---------------------------------------------------------------------------
# _run_one: task.type == "goal" → _run_goal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_one_goal_calls_run_goal():
    """task.type == 'goal' must route to _run_goal exclusively."""
    task = _make_task(task_type="goal")
    worker = _make_worker(task)

    await worker._run_one(task.id, None)

    worker._run_goal.assert_called_once_with(task.id, None, None)
    worker._run_task.assert_not_called()
    worker._run_feature_decompose.assert_not_called()


@pytest.mark.asyncio
async def test_run_one_goal_passes_user_message():
    """_run_goal must receive the user_message argument."""
    task = _make_task(task_type="goal")
    worker = _make_worker(task)

    await worker._run_one(task.id, "hello")

    worker._run_goal.assert_called_once_with(task.id, "hello", None)


@pytest.mark.asyncio
async def test_run_one_goal_passes_verdict():
    """_run_goal must receive the sign-off verdict (R7/D10)."""
    task = _make_task(task_type="goal")
    worker = _make_worker(task)

    await worker._run_one(task.id, "no — change X", "reject")

    worker._run_goal.assert_called_once_with(task.id, "no — change X", "reject")


# ---------------------------------------------------------------------------
# _run_one: task.type == "feature" + PROCESSING → _run_feature_decompose
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_one_feature_processing_calls_run_feature_decompose():
    """feature + PROCESSING must route to _run_feature_decompose."""
    task = _make_task(task_type="feature", feature_state=FeatureState.PROCESSING)
    worker = _make_worker(task)

    await worker._run_one(task.id, None)

    worker._run_feature_decompose.assert_called_once_with(task.id, None)
    worker._run_task.assert_not_called()
    worker._run_goal.assert_not_called()


@pytest.mark.asyncio
async def test_run_one_fix_processing_calls_run_feature_decompose():
    """fix + PROCESSING must route to _run_feature_decompose (same as feature)."""
    task = _make_task(task_type="fix", feature_state=FeatureState.PROCESSING)
    worker = _make_worker(task)

    await worker._run_one(task.id, "decompose this")

    worker._run_feature_decompose.assert_called_once_with(task.id, "decompose this")
    worker._run_task.assert_not_called()
    worker._run_goal.assert_not_called()


# ---------------------------------------------------------------------------
# _run_one: task.type == "feature" + non-PROCESSING states → _run_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_one_feature_backlog_falls_through_to_run_task():
    """feature + BACKLOG must fall through to _run_task."""
    task = _make_task(task_type="feature", feature_state=FeatureState.BACKLOG)
    worker = _make_worker(task)

    await worker._run_one(task.id, None)

    worker._run_task.assert_called_once_with(task.id, None)
    worker._run_feature_decompose.assert_not_called()
    worker._run_goal.assert_not_called()


@pytest.mark.asyncio
async def test_run_one_feature_planned_falls_through_to_run_task():
    """feature + PLANNED must fall through to _run_task."""
    task = _make_task(task_type="feature", feature_state=FeatureState.PLANNED)
    worker = _make_worker(task)

    await worker._run_one(task.id, None)

    worker._run_task.assert_called_once_with(task.id, None)
    worker._run_feature_decompose.assert_not_called()
    worker._run_goal.assert_not_called()


@pytest.mark.asyncio
async def test_run_one_feature_waiting_falls_through_to_run_task():
    """feature + WAITING must fall through to _run_task."""
    task = _make_task(task_type="feature", feature_state=FeatureState.WAITING)
    worker = _make_worker(task)

    await worker._run_one(task.id, None)

    worker._run_task.assert_called_once_with(task.id, None)
    worker._run_feature_decompose.assert_not_called()
    worker._run_goal.assert_not_called()


@pytest.mark.asyncio
async def test_run_one_feature_done_falls_through_to_run_task():
    """feature + DONE must fall through to _run_task."""
    task = _make_task(task_type="feature", feature_state=FeatureState.DONE)
    worker = _make_worker(task)

    await worker._run_one(task.id, None)

    worker._run_task.assert_called_once_with(task.id, None)
    worker._run_feature_decompose.assert_not_called()
    worker._run_goal.assert_not_called()


@pytest.mark.asyncio
async def test_run_one_fix_planned_falls_through_to_run_task():
    """fix + PLANNED must fall through to _run_task."""
    task = _make_task(task_type="fix", feature_state=FeatureState.PLANNED)
    worker = _make_worker(task)

    await worker._run_one(task.id, None)

    worker._run_task.assert_called_once_with(task.id, None)
    worker._run_feature_decompose.assert_not_called()
    worker._run_goal.assert_not_called()


# ---------------------------------------------------------------------------
# _run_one: task.type == "task" → _run_task (existing behavior preserved)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_one_standard_task_calls_run_task():
    """Standard task (type='task') must route to _run_task."""
    task = _make_task(task_type="task")
    worker = _make_worker(task)

    await worker._run_one(task.id, None)

    worker._run_task.assert_called_once_with(task.id, None)
    worker._run_goal.assert_not_called()
    worker._run_feature_decompose.assert_not_called()


@pytest.mark.asyncio
async def test_run_one_issue_type_calls_run_task():
    """Issue task (type='issue') must route to _run_task (fallthrough)."""
    task = _make_task(task_type="issue")
    worker = _make_worker(task)

    await worker._run_one(task.id, None)

    worker._run_task.assert_called_once_with(task.id, None)
    worker._run_goal.assert_not_called()
    worker._run_feature_decompose.assert_not_called()
