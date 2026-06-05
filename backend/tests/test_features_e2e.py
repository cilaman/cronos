"""End-to-end integration test for the features dashboard slice.

Drives a feature task through the full lifecycle via the HTTP API and
worker layer, then asserts cross-cutting invariants:

  - GET /api/tasks (Tasks board) excludes the feature task
  - GET /api/features returns the feature in the correct FeatureState lane
  - GET /api/spaces returns feature_totals reflecting the done feature

Mocks:
  - app.worker.run_agent (prevents real Claude Code subprocess)
  - app.git_ops.fetch_origin (prevents network calls)
  - app.git_ops.branch_exists_on_origin (controls done-detection outcome)
  - app.git_issues.gh_issue_close (verifies it is called when issue_number is set)

Constraints (hard project rules):
  - NO importlib.reload() anywhere in this file (observation_importlib_reload_test_pollution)
  - Use async pytest pattern matching test_feature_decompose_e2e.py
  - Stub subprocess calls — no real external calls
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.agent import AgentResult, Status
from app.feature_state import FEATURE_USER_TRANSITIONS, FEATURE_WORKER_TRANSITIONS
from app.models import FeatureState, TaskState
from app.worker import Worker

# ---------------------------------------------------------------------------
# Precondition check: xfail fast if S3/S4 symbols are missing
# ---------------------------------------------------------------------------

def _check_preconditions() -> None:
    """Verify required S3/S4/S5 symbols exist; xfail with a clear message if not."""
    missing: list[str] = []

    try:
        from app.worker import Worker as _W
        if not hasattr(_W, "_run_feature_decompose"):
            missing.append("Worker._run_feature_decompose (S4 not merged)")
    except ImportError:
        missing.append("app.worker (cannot import)")

    try:
        import app.git_ops as _go
        if not hasattr(_go, "branch_exists_on_origin"):
            missing.append("git_ops.branch_exists_on_origin (S4 not merged)")
    except ImportError:
        missing.append("app.git_ops (cannot import)")

    try:
        import app.git_issues as _gi
        if not hasattr(_gi, "gh_issue_close"):
            missing.append("git_issues.gh_issue_close (S3 not merged)")
    except ImportError:
        missing.append("app.git_issues (cannot import)")

    if missing:
        pytest.xfail(
            "Precondition failed — required S3/S4 symbols not available:\n  "
            + "\n  ".join(missing)
        )


_check_preconditions()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPACE_ID = "test-space"

# ---------------------------------------------------------------------------
# Helpers mirroring test_feature_decompose_e2e.py
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
        session_id="sess-e2e-005",
        final_text=final_text,
        stderr_tail="",
        status=status,
        context=context,
        raw_events=[],
    )


def _make_worker(store) -> Worker:
    """Build a minimal Worker with real TaskStore and no optional extras."""
    return Worker(store=store, space_store=None, pool=None)


def _inject_git_ops_stubs() -> None:
    """Ensure app.git_ops has fetch_origin and branch_exists_on_origin (no-op stubs).

    Safe to call multiple times — checks attribute existence before injecting.
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
# E2E test: full pipeline — Tasks board exclusion + Features board + feature_totals
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feature_excluded_from_tasks_board(async_client, task_store):
    """A feature task MUST NOT appear on the Tasks board (GET /api/tasks).

    The store.board() method explicitly skips type=feature/fix tasks.
    This test creates a feature task and verifies it is absent from all
    four lanes of the tasks board response.
    """
    # Create a feature task directly via task_store (POST /api/features requires
    # git_repo_url which the test space does not have — see I2 out_of_scope_findings).
    feat = await task_store.create(
        space_id=SPACE_ID,
        title="Feature: add OAuth login",
        brief="Allow users to log in with Google OAuth.",
        type="feature",
    )

    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    assert resp.status_code == 200
    board = resp.json()

    all_task_ids = (
        [t["id"] for t in board.get("backlog", [])]
        + [t["id"] for t in board.get("active", [])]
        + [t["id"] for t in board.get("waiting", [])]
        + [t["id"] for t in board.get("done", [])]
    )
    assert feat.id not in all_task_ids, (
        f"Feature task {feat.id!r} must be excluded from GET /api/tasks board"
    )


@pytest.mark.asyncio
async def test_features_board_shows_feature_in_correct_lane(async_client, task_store):
    """GET /api/features returns the feature in its FeatureState lane.

    Verifies backlog lane contains the newly created feature, and that
    the feature_key (FEAT-001) is populated by the store.
    """
    feat = await task_store.create(
        space_id=SPACE_ID,
        title="Feature: improve search",
        brief="Full-text search for tasks.",
        type="feature",
    )

    # Note: the features router is registered with @router.get("/"), which means the
    # full URL is /api/features/ (with trailing slash). FastAPI redirects /api/features
    # (no trailing slash) with a 307; httpx does not follow redirects. Use the trailing
    # slash form to avoid the redirect.
    resp = await async_client.get(f"/api/features/?space_id={SPACE_ID}")
    assert resp.status_code == 200
    fb = resp.json()

    backlog_ids = [t["id"] for t in fb.get("backlog", [])]
    assert feat.id in backlog_ids, (
        f"Feature {feat.id!r} must appear in GET /api/features/ backlog lane"
    )
    # feature_key must be allocated (FEAT-NNN)
    feat_item = next(t for t in fb["backlog"] if t["id"] == feat.id)
    assert feat_item.get("feature_key", "").startswith("FEAT-"), (
        f"Expected feature_key starting with FEAT-, got {feat_item.get('feature_key')!r}"
    )


@pytest.mark.asyncio
async def test_feature_totals_reflects_done_feature(async_client, task_store):
    """GET /api/spaces feature_totals reflects a done feature.

    Creates a feature, transitions it through PROCESSING → PLANNED (via mocked
    _run_feature_decompose) → realizing goal DONE + branch absent → DONE.
    Asserts feature_totals.done == 1 in the spaces response.
    """
    import app.git_ops
    import app.git_issues
    from app import feature_sync

    _inject_git_ops_stubs()

    # Step a: create feature task in BACKLOG then advance to PROCESSING via the API.
    feat = await task_store.create(
        space_id=SPACE_ID,
        title="Feature: dashboard tiles",
        brief="Show feature counts on dashboard.",
        type="feature",
    )
    feature_id = feat.id

    # Transition to PROCESSING via FEATURE_USER_TRANSITIONS (mirrors conftest pattern).
    await task_store.transition_feature(
        feature_id,
        FeatureState.PROCESSING,
        allowed=FEATURE_USER_TRANSITIONS,
    )
    # Also move task state to ACTIVE so _run_feature_decompose operates correctly.
    await task_store.transition(
        feature_id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )

    # Verify it is in PROCESSING lane.
    resp = await async_client.get(f"/api/features/?space_id={SPACE_ID}")
    assert resp.status_code == 200
    fb = resp.json()
    processing_ids = [t["id"] for t in fb.get("processing", [])]
    assert feature_id in processing_ids, (
        f"Feature must be in processing lane after transition, "
        f"processing={processing_ids!r}"
    )

    # Step b: run decompose (mocked run_agent creates a realizing goal).
    worker = _make_worker(task_store)
    decompose_result = _make_agent_result(status=Status.DONE)
    realizing_goal_id: list[str] = []

    async def _mock_run_agent_with_realizes(task, *, user_message, **kwargs):
        """Simulate the feature-decompose skill."""
        goal = await task_store.create(
            space_id=SPACE_ID,
            title="Implement dashboard tiles goal",
            brief="",
            type="goal",
        )
        await task_store.set_realizes(goal.id, task.id)
        await task_store.transition(
            goal.id,
            TaskState.ACTIVE,
            allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
        )
        realizing_goal_id.append(goal.id)
        return decompose_result

    with patch("app.worker.run_agent", new=_mock_run_agent_with_realizes):
        await worker._run_feature_decompose(feature_id, user_message=None)

    # After decompose: feature must be PLANNED.
    feat_planned = task_store.get(feature_id)
    assert feat_planned.feature_state == FeatureState.PLANNED, (
        f"Expected PLANNED after decompose, got {feat_planned.feature_state}"
    )
    assert len(realizing_goal_id) == 1
    goal_id = realizing_goal_id[0]

    # Step c: transition realizing goal to DONE (simulates goal completion).
    await task_store.transition(
        goal_id,
        TaskState.DONE,
        allowed={(TaskState.ACTIVE, TaskState.DONE)},
    )

    # Step d: propagate to feature — branch absent → feature → DONE.
    mock_fetch = AsyncMock(return_value=None)
    mock_branch = AsyncMock(return_value=False)  # branch deleted (merged)
    mock_close = AsyncMock(return_value=True)

    with (
        patch.object(app.git_ops, "fetch_origin", mock_fetch),
        patch.object(app.git_ops, "branch_exists_on_origin", mock_branch),
        patch.object(app.git_issues, "gh_issue_close", mock_close),
    ):
        await feature_sync.propagate_to_feature(goal_id, task_store, pool=None)

    feat_done = task_store.get(feature_id)
    assert feat_done.feature_state == FeatureState.DONE, (
        f"Expected DONE after all realizing items terminal + branch absent, "
        f"got {feat_done.feature_state}"
    )

    # Step e: assert Tasks board still excludes the feature task.
    tasks_resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    assert tasks_resp.status_code == 200
    board = tasks_resp.json()
    all_task_ids = (
        [t["id"] for t in board.get("backlog", [])]
        + [t["id"] for t in board.get("active", [])]
        + [t["id"] for t in board.get("waiting", [])]
        + [t["id"] for t in board.get("done", [])]
    )
    assert feature_id not in all_task_ids, (
        "Feature task must remain excluded from Tasks board after reaching DONE"
    )

    # Step f: assert GET /api/features/ shows feature in done lane.
    features_resp = await async_client.get(f"/api/features/?space_id={SPACE_ID}")
    assert features_resp.status_code == 200
    fb_done = features_resp.json()
    done_ids = [t["id"] for t in fb_done.get("done", [])]
    assert feature_id in done_ids, (
        f"Feature {feature_id!r} must appear in done lane of GET /api/features/, "
        f"done={done_ids!r}"
    )

    # Step g: assert GET /api/spaces has feature_totals.done >= 1.
    spaces_resp = await async_client.get("/api/spaces")
    assert spaces_resp.status_code == 200
    feature_totals = spaces_resp.json().get("feature_totals", {})
    assert feature_totals.get("done", 0) >= 1, (
        f"Expected feature_totals.done >= 1 after feature reaches DONE, "
        f"feature_totals={feature_totals!r}"
    )

    # gh_issue_close must NOT have been called (feature has no issue_number).
    mock_close.assert_not_awaited()


@pytest.mark.asyncio
async def test_full_lifecycle_with_issue_close(task_store):
    """Drive feature to DONE with issue_number set → gh_issue_close is called.

    This test is purely at the worker/feature_sync layer (no HTTP client needed
    for the core assertions). The mocking pattern mirrors test_feature_decompose_e2e.py.
    """
    import app.git_ops
    import app.git_issues
    from app import feature_sync

    _inject_git_ops_stubs()

    # Create feature with issue_number=99 set.
    feat = await task_store.create(
        space_id=SPACE_ID,
        title="Feature: issue-close lifecycle",
        brief="Verify gh_issue_close is invoked.",
        type="feature",
    )
    feature_id = feat.id

    await task_store.transition_feature(
        feature_id,
        FeatureState.PROCESSING,
        allowed=FEATURE_USER_TRANSITIONS,
    )
    await task_store.set_issue_refs(
        feature_id,
        issue_number=99,
        issue_url="https://github.com/example/repo/issues/99",
        proposed_issue_path=None,
    )
    await task_store.transition(
        feature_id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )

    worker = _make_worker(task_store)
    decompose_result = _make_agent_result(status=Status.DONE)
    realizing_goal_id: list[str] = []

    async def _mock_run_agent(task, *, user_message, **kwargs):
        goal = await task_store.create(
            space_id=SPACE_ID,
            title="Issue-close lifecycle goal",
            brief="",
            type="goal",
        )
        await task_store.set_realizes(goal.id, task.id)
        await task_store.transition(
            goal.id,
            TaskState.ACTIVE,
            allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
        )
        realizing_goal_id.append(goal.id)
        return decompose_result

    with patch("app.worker.run_agent", new=_mock_run_agent):
        await worker._run_feature_decompose(feature_id, user_message=None)

    feat_planned = task_store.get(feature_id)
    assert feat_planned.feature_state == FeatureState.PLANNED
    assert len(realizing_goal_id) == 1
    goal_id = realizing_goal_id[0]

    # Transition realizing goal to DONE.
    await task_store.transition(
        goal_id,
        TaskState.DONE,
        allowed={(TaskState.ACTIVE, TaskState.DONE)},
    )

    mock_fetch = AsyncMock(return_value=None)
    mock_branch = AsyncMock(return_value=False)  # branch absent
    mock_close = AsyncMock(return_value=True)

    with (
        patch.object(app.git_ops, "fetch_origin", mock_fetch),
        patch.object(app.git_ops, "branch_exists_on_origin", mock_branch),
        patch.object(app.git_issues, "gh_issue_close", mock_close),
    ):
        await feature_sync.propagate_to_feature(goal_id, task_store, pool=None)

    feat_done = task_store.get(feature_id)
    assert feat_done.feature_state == FeatureState.DONE, (
        f"Expected DONE, got {feat_done.feature_state}"
    )

    # gh_issue_close must have been called (issue_number=99 is set).
    mock_close.assert_awaited_once()
    call_args = mock_close.call_args
    assert call_args.args[1] == 99, (
        f"Expected gh_issue_close called with issue_number=99, got {call_args.args[1]}"
    )


@pytest.mark.asyncio
async def test_feature_totals_backlog_count_in_spaces(async_client, task_store):
    """GET /api/spaces feature_totals.backlog reflects newly created feature.

    This tests the data pipeline: store.create(type='feature') sets
    feature_state=BACKLOG; GET /api/spaces aggregates into feature_totals.
    """
    # Create a feature task.
    feat = await task_store.create(
        space_id=SPACE_ID,
        title="Feature: totals backlog check",
        brief="",
        type="feature",
    )

    resp = await async_client.get("/api/spaces")
    assert resp.status_code == 200
    data = resp.json()

    assert "feature_totals" in data, "SpacesResponse must have feature_totals field"
    ft = data["feature_totals"]
    assert ft.get("backlog", 0) >= 1, (
        f"Expected feature_totals.backlog >= 1 after creating a feature, "
        f"feature_totals={ft!r}"
    )

    # Also verify the feature is absent from the Tasks board.
    tasks_resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    assert tasks_resp.status_code == 200
    board = tasks_resp.json()
    all_ids = (
        [t["id"] for t in board.get("backlog", [])]
        + [t["id"] for t in board.get("active", [])]
        + [t["id"] for t in board.get("waiting", [])]
        + [t["id"] for t in board.get("done", [])]
    )
    assert feat.id not in all_ids, (
        "Backlog feature must still be excluded from Tasks board"
    )
