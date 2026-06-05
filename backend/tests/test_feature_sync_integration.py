"""Integration tests for I8: feature_sync wiring in worker._finalize and tasks.py reply path.

Acceptance criteria (from I8 design):
1. A realizing goal child transition (via _finalize) triggers
   feature_sync.propagate_to_feature from worker._finalize.
2. An API reply on a realizing item triggers feature_sync.propagate_to_feature
   from the reply path in tasks.py.
3. Errors in propagate_to_feature do NOT abort either caller.

Implementation notes
--------------------
- Tests 1 & 3a use the real Worker._finalize by constructing a Worker with a
  real TaskStore.  feature_sync is patched at the module level where needed.
- Tests 2 & 3b use the async_client fixture (ASGI test client) to call
  POST /api/tasks/{id}/reply.  The "realizing item" in the API path is a
  plain task (type="task") that has ``realizes`` set on itself so it passes
  through the non-goal reply branch and reaches the feature_sync call.
- The state-change tests (test_finalize_propagate_updates_feature_state,
  test_reply_path_propagate_updates_feature_state) run the real feature_sync
  with git_ops stubs to avoid network calls.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agent import AgentResult, Status
from app.feature_state import FEATURE_USER_TRANSITIONS, FEATURE_WORKER_TRANSITIONS
from app.models import FeatureState, TaskState
from app.worker import Worker

SPACE_ID = "test-space"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_feature_planned(store) -> object:
    """Create a feature task in PLANNED state."""
    feat = await store.create(
        space_id=SPACE_ID,
        title="My Feature",
        brief="Feature brief.",
        type="feature",
    )
    await store.transition_feature(
        feat.id, FeatureState.PROCESSING, allowed=FEATURE_USER_TRANSITIONS
    )
    await store.transition_feature(
        feat.id, FeatureState.PLANNED, allowed=FEATURE_WORKER_TRANSITIONS
    )
    return store.get(feat.id)


async def _make_realizing_goal(store, feature_id: str) -> object:
    """Create a goal that realizes the given feature, put it in ACTIVE state."""
    goal = await store.create(
        space_id=SPACE_ID,
        title="Realizing Goal",
        brief="",
        type="goal",
    )
    await store.set_realizes(goal.id, feature_id)
    # BACKLOG → ACTIVE
    await store.transition(
        goal.id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )
    return store.get(goal.id)


async def _make_realizing_task(store, feature_id: str) -> object:
    """Create a plain task (type='task') with realizes=feature_id.

    Used for API reply path tests: the non-goal reply branch handles any
    non-goal task type, so using type='task' lets us exercise that code path.
    """
    task = await store.create(
        space_id=SPACE_ID,
        title="Realizing Task",
        brief="",
        type="task",
    )
    await store.set_realizes(task.id, feature_id)
    return store.get(task.id)


def _make_agent_result(
    *,
    status: Status | None = Status.DONE,
    exit_code: int = 0,
) -> AgentResult:
    return AgentResult(
        exit_code=exit_code,
        session_id="sess-001",
        final_text="Done.",
        stderr_tail="",
        status=status,
        context=None,
        raw_events=[],
    )


def _make_worker(store) -> Worker:
    """Build a minimal Worker with a real store and no optional extras."""
    return Worker(store=store, space_store=None, pool=None)


def _inject_git_ops_stubs() -> None:
    """Ensure app.git_ops has the I1 additions (fetch_origin, branch_exists_on_origin).

    The feature worktree's git_ops.py may predate the I1 additions.  We inject
    stubs so feature_sync's lazy imports succeed.  Safe to call multiple times.
    """
    import app.git_ops

    if not hasattr(app.git_ops, "fetch_origin"):
        async def _stub_fetch(space_dir) -> None:
            pass
        app.git_ops.fetch_origin = _stub_fetch  # type: ignore[attr-defined]

    if not hasattr(app.git_ops, "branch_exists_on_origin"):
        async def _stub_branch(space_dir, branch: str) -> bool:
            return False
        app.git_ops.branch_exists_on_origin = _stub_branch  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Test 1: worker._finalize calls feature_sync.propagate_to_feature
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_calls_feature_sync_propagate(task_store):
    """worker._finalize calls feature_sync.propagate_to_feature after goal_sync."""
    feat = await _make_feature_planned(task_store)
    goal = await _make_realizing_goal(task_store, feat.id)

    worker = _make_worker(task_store)
    result = _make_agent_result(status=Status.DONE)

    mock_propagate = AsyncMock()
    with patch("app.worker.feature_sync.propagate_to_feature", mock_propagate):
        await worker._finalize(goal.id, result)

    mock_propagate.assert_awaited_once()
    call_args = mock_propagate.call_args
    # First positional arg is the task_id
    assert call_args.args[0] == goal.id


@pytest.mark.asyncio
async def test_finalize_propagate_updates_feature_state(task_store):
    """When _finalize transitions a realizing goal → DONE, feature_sync runs and feature → DONE.

    Uses real feature_sync with git_ops patched to avoid network calls.
    On DONE with branch absent, feature transitions to DONE.
    """
    import app.git_ops

    _inject_git_ops_stubs()

    feat = await _make_feature_planned(task_store)
    goal = await _make_realizing_goal(task_store, feat.id)

    worker = _make_worker(task_store)
    result = _make_agent_result(status=Status.DONE)

    mock_fetch = AsyncMock(return_value=None)
    mock_branch = AsyncMock(return_value=False)
    with (
        patch.object(app.git_ops, "fetch_origin", mock_fetch),
        patch.object(app.git_ops, "branch_exists_on_origin", mock_branch),
    ):
        await worker._finalize(goal.id, result)

    # After finalize, the goal is DONE.
    final_goal = task_store.get(goal.id)
    assert final_goal.state == TaskState.DONE

    # feature_sync.propagate_to_feature should have detected all realizing items
    # are DONE and the branch is absent → feature transitions to DONE.
    final_feat = task_store.get(feat.id)
    assert final_feat.feature_state == FeatureState.DONE


# ---------------------------------------------------------------------------
# Test 2: tasks.py non-goal reply path calls feature_sync.propagate_to_feature
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reply_path_calls_feature_sync_propagate(async_client, task_store):
    """POST /api/tasks/{id}/reply (non-goal task) triggers feature_sync.propagate_to_feature."""
    feat = await _make_feature_planned(task_store)
    # Use a plain task (type='task') so the non-goal reply branch handles it.
    task = await _make_realizing_task(task_store, feat.id)

    # Ensure task is in BACKLOG (default) — reply will move it to ACTIVE.
    assert task_store.get(task.id).state == TaskState.BACKLOG

    mock_propagate = AsyncMock()
    with patch("app.api.tasks.feature_sync.propagate_to_feature", mock_propagate):
        resp = await async_client.post(
            f"/api/tasks/{task.id}/reply", json={"message": "start it"}
        )

    assert resp.status_code == 200
    mock_propagate.assert_awaited_once()
    call_args = mock_propagate.call_args
    assert call_args.args[0] == task.id


@pytest.mark.asyncio
async def test_reply_path_propagate_updates_feature_state(async_client, task_store):
    """POST /api/tasks/{id}/reply on a WAITING realizing task updates feature state.

    When the realizing task is WAITING and feature is WAITING, replying
    (WAITING→ACTIVE) triggers feature_sync(item→ACTIVE, feature→WAITING) → feature→PLANNED.
    """
    import app.git_ops

    _inject_git_ops_stubs()

    feat = await _make_feature_planned(task_store)
    # Manually put feature into WAITING.
    await task_store.transition_feature(
        feat.id, FeatureState.WAITING, allowed=FEATURE_WORKER_TRANSITIONS
    )
    assert task_store.get(feat.id).feature_state == FeatureState.WAITING

    # Create a realizing task and put it in WAITING state.
    task = await _make_realizing_task(task_store, feat.id)
    await task_store.transition(
        task.id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )
    await task_store.transition(
        task.id,
        TaskState.WAITING,
        allowed={(TaskState.ACTIVE, TaskState.WAITING)},
    )
    assert task_store.get(task.id).state == TaskState.WAITING

    # Reply → task ACTIVE; feature_sync sees ACTIVE + WAITING → PLANNED.
    resp = await async_client.post(
        f"/api/tasks/{task.id}/reply", json={"message": "continue"}
    )
    assert resp.status_code == 200

    final_feat = task_store.get(feat.id)
    assert final_feat.feature_state == FeatureState.PLANNED


# ---------------------------------------------------------------------------
# Test 3a: errors in propagate_to_feature do NOT abort worker._finalize
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_feature_sync_error_does_not_abort(task_store):
    """If feature_sync.propagate_to_feature raises, _finalize continues normally."""
    feat = await _make_feature_planned(task_store)
    goal = await _make_realizing_goal(task_store, feat.id)

    worker = _make_worker(task_store)
    result = _make_agent_result(status=Status.DONE)

    exploding_propagate = AsyncMock(side_effect=RuntimeError("simulated feature_sync crash"))
    with patch("app.worker.feature_sync.propagate_to_feature", exploding_propagate):
        # Must not raise — _finalize swallows the exception.
        await worker._finalize(goal.id, result)

    # _finalize should have completed normally: task state is DONE.
    final_goal = task_store.get(goal.id)
    assert final_goal.state == TaskState.DONE


# ---------------------------------------------------------------------------
# Test 3b: errors in propagate_to_feature do NOT abort the reply path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reply_path_feature_sync_error_does_not_abort(async_client, task_store):
    """If feature_sync.propagate_to_feature raises in the reply path, reply still succeeds."""
    feat = await _make_feature_planned(task_store)
    task = await _make_realizing_task(task_store, feat.id)

    # Put task in WAITING so reply transitions it to ACTIVE.
    await task_store.transition(
        task.id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )
    await task_store.transition(
        task.id,
        TaskState.WAITING,
        allowed={(TaskState.ACTIVE, TaskState.WAITING)},
    )
    assert task_store.get(task.id).state == TaskState.WAITING

    exploding_propagate = AsyncMock(side_effect=RuntimeError("simulated crash"))
    with patch("app.api.tasks.feature_sync.propagate_to_feature", exploding_propagate):
        resp = await async_client.post(
            f"/api/tasks/{task.id}/reply", json={"message": "continue"}
        )

    # Despite the propagate crash, the reply endpoint must return 200.
    assert resp.status_code == 200
    body = resp.json()
    assert "task" in body
    # task should now be ACTIVE (reply worked, transitioning from WAITING)
    assert body["task"]["state"] == "active"
