"""End-to-end integration test for the feature decomposition lifecycle.

Drives a feature task through the full lifecycle:
  PROCESSING → PLANNED (after decompose) → WAITING (realizing goal waits)
  → PLANNED (resume) → DONE (all realizing items terminal, branch absent)

Mocks:
- agent run (_run_feature_decompose) to simulate success with ≥1 realizing item
- fetch_origin to avoid network calls
- branch_exists_on_origin to control done-detection outcome
- gh_issue_close to verify it is called when issue_number is set

I10 acceptance criteria (design report):
- Mocks the agent run to simulate the decomposition skill creating a realizing
  goal with realizes=<feature_id>.
- Drives the feature task PROCESSING→PLANNED→WAITING→PLANNED→DONE.
- Asserts gh_issue_close is invoked when issue_number is set.
- Scope: only backend/tests/test_feature_decompose_e2e.py is written.
"""
from __future__ import annotations

import asyncio
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


def _make_agent_result(
    *,
    status: Status = Status.DONE,
    exit_code: int = 0,
    final_text: str = "Decomposed successfully.",
    context: str | None = None,
) -> AgentResult:
    return AgentResult(
        exit_code=exit_code,
        session_id="sess-e2e-001",
        final_text=final_text,
        stderr_tail="",
        status=status,
        context=context,
        raw_events=[],
    )


def _make_worker(store) -> Worker:
    """Build a minimal Worker with real TaskStore and no optional extras."""
    return Worker(store=store, space_store=None, pool=None)


async def _create_feature_processing(store, *, issue_number: int | None = None) -> object:
    """Create a feature task and advance it to PROCESSING state."""
    feat = await store.create(
        space_id=SPACE_ID,
        title="Add OAuth login",
        brief="Allow users to log in with Google OAuth.",
        type="feature",
    )
    # BACKLOG → PROCESSING (user-initiated)
    await store.transition_feature(
        feat.id,
        FeatureState.PROCESSING,
        allowed=FEATURE_USER_TRANSITIONS,
    )
    if issue_number is not None:
        await store.set_issue_refs(
            feat.id,
            issue_number=issue_number,
            issue_url=None,
            proposed_issue_path=None,
        )
    # Also transition the task state to ACTIVE so _run_feature_decompose works.
    await store.transition(
        feat.id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )
    return store.get(feat.id)


async def _create_realizing_goal(store, feature_id: str) -> object:
    """Create a goal that realizes the given feature, in ACTIVE state."""
    goal = await store.create(
        space_id=SPACE_ID,
        title="Implement OAuth login flow",
        brief="",
        type="goal",
    )
    await store.set_realizes(goal.id, feature_id)
    await store.transition(
        goal.id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )
    return store.get(goal.id)


def _inject_git_ops_stubs() -> None:
    """Ensure app.git_ops has fetch_origin and branch_exists_on_origin (no-op stubs).

    Previous iterations may have already added these; safe to call multiple times.
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
# E2E test: full feature lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_feature_lifecycle(task_store):
    """Drive a feature task through the complete lifecycle end-to-end.

    PROCESSING → PLANNED (after decompose) → WAITING (realizing goal WAITING)
    → PLANNED (realizing goal ACTIVE again) → DONE (all terminal, branch absent)
    with gh_issue_close called.
    """
    import app.git_ops
    import app.git_issues

    _inject_git_ops_stubs()

    # Step a: create feature task in PROCESSING with issue_number=42.
    feat = await _create_feature_processing(task_store, issue_number=42)
    assert task_store.get(feat.id).feature_state == FeatureState.PROCESSING
    feature_id = feat.id

    # Step b+c: simulate _run_feature_decompose by mocking run_agent to succeed,
    # then manually creating the realizing goal (simulating what the decompose
    # skill does: call set_realizes then create child tasks).

    worker = _make_worker(task_store)

    # We need to call set_realizes before finalize_run fires (race guard).
    # We patch run_agent and inject set_realizes in the patch so the store
    # already has the realizes link when realizing_items() is called by worker.
    decompose_result = _make_agent_result(status=Status.DONE)

    realizing_goal_id: list[str] = []  # mutable container for closure

    async def _mock_run_agent_with_realizes(task, *, user_message, **kwargs):
        """Simulate the feature-decompose skill: register realizes link then return."""
        # skill: POST goal then set_realizes (ordering per design invariant #2).
        goal = await task_store.create(
            space_id=SPACE_ID,
            title="OAuth login implementation goal",
            brief="",
            type="goal",
        )
        await task_store.set_realizes(goal.id, task.id)
        # Activate the goal so it is a non-terminal realizing item.
        await task_store.transition(
            goal.id,
            TaskState.ACTIVE,
            allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
        )
        realizing_goal_id.append(goal.id)
        return decompose_result

    with patch("app.worker.run_agent", new=_mock_run_agent_with_realizes):
        await worker._run_feature_decompose(feature_id, user_message=None)

    # After decompose: feature_state must be PLANNED (≥1 realizing item, STATUS=DONE).
    feat_after_decompose = task_store.get(feature_id)
    assert feat_after_decompose.feature_state == FeatureState.PLANNED, (
        f"Expected PLANNED after decompose, got {feat_after_decompose.feature_state}"
    )

    # Also verify the realizing goal was created.
    assert len(realizing_goal_id) == 1
    goal_id = realizing_goal_id[0]
    realizing_goal = task_store.get(goal_id)
    assert realizing_goal is not None
    assert realizing_goal.realizes == feature_id

    # Verify the feature task (the decomposed task itself) moved to DONE state.
    feat_task_state = task_store.get(feature_id)
    assert feat_task_state.state == TaskState.DONE, (
        f"Feature task.state expected DONE after decompose, got {feat_task_state.state}"
    )

    # Step d: transition the realizing goal to WAITING, then call propagate_to_feature.
    # This simulates the realizing goal entering a WAITING state (e.g. waiting for user input).
    from app import feature_sync

    await task_store.transition(
        goal_id,
        TaskState.WAITING,
        allowed={(TaskState.ACTIVE, TaskState.WAITING)},
    )

    mock_fetch = AsyncMock(return_value=None)
    mock_branch = AsyncMock(return_value=True)  # branch still present; no DONE yet

    with (
        patch.object(app.git_ops, "fetch_origin", mock_fetch),
        patch.object(app.git_ops, "branch_exists_on_origin", mock_branch),
    ):
        await feature_sync.propagate_to_feature(goal_id, task_store, pool=None)

    # feature_state must be WAITING now.
    feat_waiting = task_store.get(feature_id)
    assert feat_waiting.feature_state == FeatureState.WAITING, (
        f"Expected WAITING after realizing goal → WAITING, got {feat_waiting.feature_state}"
    )

    # Step e: resume — transition the realizing goal back to ACTIVE.
    await task_store.transition(
        goal_id,
        TaskState.ACTIVE,
        allowed={(TaskState.WAITING, TaskState.ACTIVE)},
    )

    with (
        patch.object(app.git_ops, "fetch_origin", mock_fetch),
        patch.object(app.git_ops, "branch_exists_on_origin", mock_branch),
    ):
        await feature_sync.propagate_to_feature(goal_id, task_store, pool=None)

    # feature_state must be PLANNED again.
    feat_resumed = task_store.get(feature_id)
    assert feat_resumed.feature_state == FeatureState.PLANNED, (
        f"Expected PLANNED after realizing goal resumed ACTIVE, got {feat_resumed.feature_state}"
    )

    # Step f: all realizing items DONE, branch absent → feature → DONE + issue closed.
    await task_store.transition(
        goal_id,
        TaskState.DONE,
        allowed={(TaskState.ACTIVE, TaskState.DONE)},
    )

    mock_fetch_f = AsyncMock(return_value=None)
    mock_branch_f = AsyncMock(return_value=False)  # branch merged and deleted
    mock_close = AsyncMock(return_value=True)

    with (
        patch.object(app.git_ops, "fetch_origin", mock_fetch_f),
        patch.object(app.git_ops, "branch_exists_on_origin", mock_branch_f),
        patch.object(app.git_issues, "gh_issue_close", mock_close),
    ):
        await feature_sync.propagate_to_feature(goal_id, task_store, pool=None)

    # feature_state must be DONE.
    feat_done = task_store.get(feature_id)
    assert feat_done.feature_state == FeatureState.DONE, (
        f"Expected DONE after all realizing items terminal + branch absent, "
        f"got {feat_done.feature_state}"
    )

    # gh_issue_close must have been called with issue_number=42.
    mock_close.assert_awaited_once()
    call_args = mock_close.call_args
    assert call_args.args[1] == 42, (
        f"Expected gh_issue_close called with issue_number=42, got {call_args.args[1]}"
    )


# ---------------------------------------------------------------------------
# E2E: no issue_number — gh_issue_close not called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_lifecycle_no_issue_number(task_store):
    """When issue_number is None, gh_issue_close is NOT called."""
    import app.git_ops
    import app.git_issues

    _inject_git_ops_stubs()

    feat = await _create_feature_processing(task_store, issue_number=None)
    feature_id = feat.id

    worker = _make_worker(task_store)
    decompose_result = _make_agent_result(status=Status.DONE)

    async def _mock_run_agent(task, *, user_message, **kwargs):
        goal = await task_store.create(
            space_id=SPACE_ID,
            title="Goal without issue",
            brief="",
            type="goal",
        )
        await task_store.set_realizes(goal.id, task.id)
        await task_store.transition(
            goal.id,
            TaskState.ACTIVE,
            allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
        )
        return decompose_result

    with patch("app.worker.run_agent", new=_mock_run_agent):
        await worker._run_feature_decompose(feature_id, user_message=None)

    feat_planned = task_store.get(feature_id)
    assert feat_planned.feature_state == FeatureState.PLANNED

    # Get the realizing goal ID.
    items = await task_store.realizing_items(feature_id)
    assert len(items) == 1
    goal_id = items[0].id

    # Transition realizing goal to DONE.
    await task_store.transition(
        goal_id,
        TaskState.DONE,
        allowed={(TaskState.ACTIVE, TaskState.DONE)},
    )

    from app import feature_sync

    mock_fetch = AsyncMock(return_value=None)
    mock_branch = AsyncMock(return_value=False)
    mock_close = AsyncMock(return_value=True)

    with (
        patch.object(app.git_ops, "fetch_origin", mock_fetch),
        patch.object(app.git_ops, "branch_exists_on_origin", mock_branch),
        patch.object(app.git_issues, "gh_issue_close", mock_close),
    ):
        await feature_sync.propagate_to_feature(goal_id, task_store, pool=None)

    feat_done = task_store.get(feature_id)
    assert feat_done.feature_state == FeatureState.DONE

    # gh_issue_close must NOT have been called (no issue_number set).
    mock_close.assert_not_awaited()


# ---------------------------------------------------------------------------
# E2E: decompose fails (agent returns WAIT) → PROCESSING stays WAITING
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decompose_failure_feature_stays_waiting(task_store):
    """If the decompose agent returns WAIT, the feature transitions to WAITING."""
    _inject_git_ops_stubs()

    feat = await _create_feature_processing(task_store, issue_number=None)
    feature_id = feat.id

    worker = _make_worker(task_store)
    wait_result = _make_agent_result(
        status=Status.WAIT,
        context="Which authentication provider should I use?",
    )

    with patch("app.worker.run_agent", new=AsyncMock(return_value=wait_result)):
        await worker._run_feature_decompose(feature_id, user_message=None)

    feat_after = task_store.get(feature_id)
    assert feat_after.feature_state == FeatureState.WAITING, (
        f"Expected WAITING after WAIT decompose, got {feat_after.feature_state}"
    )
    # The feature task state itself should be WAITING too.
    assert feat_after.state == TaskState.WAITING, (
        f"Expected task.state=WAITING after WAIT decompose, got {feat_after.state}"
    )


# ---------------------------------------------------------------------------
# E2E: branch still present → feature stays PLANNED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_branch_present_feature_stays_planned(task_store):
    """When branch exists on origin after all realizing items DONE, feature stays PLANNED."""
    import app.git_ops

    _inject_git_ops_stubs()

    feat = await _create_feature_processing(task_store, issue_number=None)
    feature_id = feat.id

    worker = _make_worker(task_store)
    decompose_result = _make_agent_result(status=Status.DONE)

    async def _mock_run_agent(task, *, user_message, **kwargs):
        goal = await task_store.create(
            space_id=SPACE_ID,
            title="Goal for branch test",
            brief="",
            type="goal",
        )
        await task_store.set_realizes(goal.id, task.id)
        await task_store.transition(
            goal.id,
            TaskState.ACTIVE,
            allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
        )
        return decompose_result

    with patch("app.worker.run_agent", new=_mock_run_agent):
        await worker._run_feature_decompose(feature_id, user_message=None)

    feat_planned = task_store.get(feature_id)
    assert feat_planned.feature_state == FeatureState.PLANNED

    items = await task_store.realizing_items(feature_id)
    goal_id = items[0].id

    await task_store.transition(
        goal_id,
        TaskState.DONE,
        allowed={(TaskState.ACTIVE, TaskState.DONE)},
    )

    from app import feature_sync

    mock_fetch = AsyncMock(return_value=None)
    # Branch is still present — should NOT transition to DONE.
    mock_branch = AsyncMock(return_value=True)

    with (
        patch.object(app.git_ops, "fetch_origin", mock_fetch),
        patch.object(app.git_ops, "branch_exists_on_origin", mock_branch),
    ):
        await feature_sync.propagate_to_feature(goal_id, task_store, pool=None)

    feat_still_planned = task_store.get(feature_id)
    assert feat_still_planned.feature_state == FeatureState.PLANNED, (
        f"Expected PLANNED (branch still on origin), got {feat_still_planned.feature_state}"
    )
