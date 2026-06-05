"""Tests for feature_sync.propagate_to_feature — done-detection branch (I4).

Covers acceptance criteria:
- All realizing items terminal + feature PLANNED + branch absent → PLANNED→DONE
- All realizing items terminal + feature PLANNED + branch present → stay PLANNED
- fetch_origin failure → stay PLANNED
- DONE transition + issue_number set → gh_issue_close called (failure still DONE)
- Zero realizing items → no-op (never attempt done-detection)
- Partial-terminal (some items not DONE/ARCHIVED) → no-op
- Feature not in PLANNED state when items are terminal → no-op
- Slug derivation strips YYYY-MM-DD-HHMM- prefix; falls back to raw id

Implementation note
-------------------
``feature_sync`` lazy-imports ``fetch_origin`` and ``branch_exists_on_origin``
from ``app.git_ops`` inside the done-detection code path.  The feature
workspace's ``app.git_ops`` may not yet have these symbols (added by I1 to the
main worktree).  We inject them as attributes on the ``app.git_ops`` module
object before each test so the ``from .git_ops import …`` lookup succeeds.
This is the same mechanism ``unittest.mock.patch`` uses internally.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import app.git_ops  # ensure the module is loaded
from app.feature_state import FEATURE_USER_TRANSITIONS, FEATURE_WORKER_TRANSITIONS
from app.feature_sync import propagate_to_feature
from app.models import FeatureState, TaskState

SPACE_ID = "test-space"

# ---------------------------------------------------------------------------
# Module-level injection: ensure app.git_ops has the symbols I4 needs even if
# the workspace's git_ops.py predates the I1 additions.
# ---------------------------------------------------------------------------

if not hasattr(app.git_ops, "fetch_origin"):
    async def _stub_fetch_origin(space_dir: Path) -> None:  # pragma: no cover
        pass
    app.git_ops.fetch_origin = _stub_fetch_origin  # type: ignore[attr-defined]

if not hasattr(app.git_ops, "branch_exists_on_origin"):
    async def _stub_branch_exists(space_dir: Path, branch: str) -> bool:  # pragma: no cover
        return False
    app.git_ops.branch_exists_on_origin = _stub_branch_exists  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _make_feature(store, title="My Feature", *, issue_number=None) -> object:
    """Create a feature task in PLANNED state."""
    feat = await store.create(space_id=SPACE_ID, title=title, brief="", type="feature")
    await store.transition_feature(
        feat.id, FeatureState.PROCESSING, allowed=FEATURE_USER_TRANSITIONS
    )
    await store.transition_feature(
        feat.id, FeatureState.PLANNED, allowed=FEATURE_WORKER_TRANSITIONS
    )
    if issue_number is not None:
        await store.set_issue_refs(
            feat.id,
            issue_number=issue_number,
            issue_url=None,
            proposed_issue_path=None,
        )
    return store.get(feat.id)


async def _make_goal(store, title="Realizing Goal", realizes=None) -> object:
    """Create a goal task, optionally linked to a feature."""
    goal = await store.create(space_id=SPACE_ID, title=title, brief="", type="goal")
    if realizes is not None:
        await store.set_realizes(goal.id, realizes)
    return store.get(goal.id)


async def _transition_goal_to_done(store, goal_id: str) -> None:
    """Drive a goal to DONE state through required intermediate states."""
    await store.transition(
        goal_id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )
    await store.transition(
        goal_id, TaskState.DONE, allowed={(TaskState.ACTIVE, TaskState.DONE)}
    )


async def _transition_goal_to_archived(store, goal_id: str) -> None:
    """Drive a goal to ARCHIVED state."""
    await store.transition(
        goal_id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )
    await store.transition(
        goal_id, TaskState.DONE, allowed={(TaskState.ACTIVE, TaskState.DONE)}
    )
    await store.transition(
        goal_id, TaskState.ARCHIVED, allowed={(TaskState.DONE, TaskState.ARCHIVED)}
    )


# ---------------------------------------------------------------------------
# Happy path 1: all realizing items DONE, branch absent → feature→DONE
# ---------------------------------------------------------------------------


async def test_all_items_done_branch_absent_transitions_to_done(task_store):
    """All realizing items terminal + branch absent → feature transitions to DONE."""
    feat = await _make_feature(task_store)
    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED

    goal = await _make_goal(task_store, realizes=feat.id)
    await _transition_goal_to_done(task_store, goal.id)

    mock_fetch = AsyncMock(return_value=None)
    mock_branch = AsyncMock(return_value=False)
    with (
        patch.object(app.git_ops, "fetch_origin", mock_fetch),
        patch.object(app.git_ops, "branch_exists_on_origin", mock_branch),
    ):
        await propagate_to_feature(goal.id, task_store, pool=None)

    mock_fetch.assert_awaited_once()
    mock_branch.assert_awaited_once()
    assert task_store.get(feat.id).feature_state == FeatureState.DONE


# ---------------------------------------------------------------------------
# Happy path 2: all realizing items ARCHIVED, branch absent → feature→DONE
# ---------------------------------------------------------------------------


async def test_all_items_archived_branch_absent_transitions_to_done(task_store):
    """All realizing items ARCHIVED + branch absent → feature transitions to DONE."""
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)
    await _transition_goal_to_archived(task_store, goal.id)

    with (
        patch.object(app.git_ops, "fetch_origin", AsyncMock(return_value=None)),
        patch.object(app.git_ops, "branch_exists_on_origin", AsyncMock(return_value=False)),
    ):
        await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.DONE


# ---------------------------------------------------------------------------
# Branch present → stay PLANNED
# ---------------------------------------------------------------------------


async def test_branch_present_stays_planned(task_store):
    """All realizing items terminal + branch still on origin → feature stays PLANNED."""
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)
    await _transition_goal_to_done(task_store, goal.id)

    with (
        patch.object(app.git_ops, "fetch_origin", AsyncMock(return_value=None)),
        patch.object(app.git_ops, "branch_exists_on_origin", AsyncMock(return_value=True)),
    ):
        await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED


# ---------------------------------------------------------------------------
# fetch_origin failure → stay PLANNED
# ---------------------------------------------------------------------------


async def test_fetch_origin_failure_stays_planned(task_store):
    """fetch_origin raises → feature stays PLANNED (safe default)."""
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)
    await _transition_goal_to_done(task_store, goal.id)

    mock_branch = AsyncMock(return_value=False)
    with (
        patch.object(
            app.git_ops,
            "fetch_origin",
            AsyncMock(side_effect=Exception("network error")),
        ),
        patch.object(app.git_ops, "branch_exists_on_origin", mock_branch),
    ):
        await propagate_to_feature(goal.id, task_store, pool=None)

    # branch_exists_on_origin must NOT be called when fetch fails.
    mock_branch.assert_not_awaited()
    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED


# ---------------------------------------------------------------------------
# gh_issue_close called when issue_number set
# ---------------------------------------------------------------------------


async def test_issue_close_called_when_issue_number_set(task_store):
    """DONE transition + issue_number set → gh_issue_close is called."""
    feat = await _make_feature(task_store, issue_number=42)
    assert task_store.get(feat.id).issue_number == 42

    goal = await _make_goal(task_store, realizes=feat.id)
    await _transition_goal_to_done(task_store, goal.id)

    mock_close = AsyncMock(return_value=True)
    with (
        patch.object(app.git_ops, "fetch_origin", AsyncMock(return_value=None)),
        patch.object(app.git_ops, "branch_exists_on_origin", AsyncMock(return_value=False)),
        patch("app.git_issues.gh_issue_close", new=mock_close),
    ):
        await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.DONE
    mock_close.assert_awaited_once()
    # Verify issue_number argument
    call_args = mock_close.call_args
    assert call_args[0][1] == 42


# ---------------------------------------------------------------------------
# gh_issue_close failure does NOT roll back DONE
# ---------------------------------------------------------------------------


async def test_gh_close_failure_still_done(task_store):
    """gh_issue_close raises → feature is still DONE (no rollback)."""
    feat = await _make_feature(task_store, issue_number=99)

    goal = await _make_goal(task_store, realizes=feat.id)
    await _transition_goal_to_done(task_store, goal.id)

    mock_close = AsyncMock(side_effect=Exception("gh not available"))
    with (
        patch.object(app.git_ops, "fetch_origin", AsyncMock(return_value=None)),
        patch.object(app.git_ops, "branch_exists_on_origin", AsyncMock(return_value=False)),
        patch("app.git_issues.gh_issue_close", new=mock_close),
    ):
        # Must not raise despite gh_issue_close failing.
        await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.DONE


# ---------------------------------------------------------------------------
# gh_issue_close NOT called when issue_number is None
# ---------------------------------------------------------------------------


async def test_no_issue_close_when_no_issue_number(task_store):
    """DONE transition but no issue_number → gh_issue_close is NOT called."""
    feat = await _make_feature(task_store)  # no issue_number
    assert task_store.get(feat.id).issue_number is None

    goal = await _make_goal(task_store, realizes=feat.id)
    await _transition_goal_to_done(task_store, goal.id)

    mock_close = AsyncMock(return_value=True)
    with (
        patch.object(app.git_ops, "fetch_origin", AsyncMock(return_value=None)),
        patch.object(app.git_ops, "branch_exists_on_origin", AsyncMock(return_value=False)),
        patch("app.git_issues.gh_issue_close", new=mock_close),
    ):
        await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.DONE
    mock_close.assert_not_awaited()


# ---------------------------------------------------------------------------
# Zero realizing items → no-op
# ---------------------------------------------------------------------------


async def test_zero_realizing_items_no_op(task_store):
    """Feature with no realizing items → done-detection skipped entirely."""
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)
    await _transition_goal_to_done(task_store, goal.id)

    # Patch realizing_items to return empty so we isolate the zero-items guard.
    original_realizing = task_store.realizing_items

    async def _empty_realizing(feature_id):
        return []

    task_store.realizing_items = _empty_realizing

    mock_fetch = AsyncMock(return_value=None)
    try:
        with patch.object(app.git_ops, "fetch_origin", mock_fetch):
            await propagate_to_feature(goal.id, task_store, pool=None)
    finally:
        task_store.realizing_items = original_realizing

    # fetch_origin must NOT be called — zero-items guard fires first.
    mock_fetch.assert_not_awaited()
    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED


# ---------------------------------------------------------------------------
# Partial-terminal → no-op
# ---------------------------------------------------------------------------


async def test_partial_terminal_is_noop(task_store):
    """Some realizing items not done → no transition attempted."""
    feat = await _make_feature(task_store)
    goal1 = await _make_goal(task_store, title="Goal 1", realizes=feat.id)
    goal2 = await _make_goal(task_store, title="Goal 2", realizes=feat.id)

    # Make goal1 DONE, leave goal2 in BACKLOG (non-terminal).
    await _transition_goal_to_done(task_store, goal1.id)

    mock_fetch = AsyncMock(return_value=None)
    with (
        patch.object(app.git_ops, "fetch_origin", mock_fetch),
        patch.object(app.git_ops, "branch_exists_on_origin", AsyncMock(return_value=False)),
    ):
        await propagate_to_feature(goal1.id, task_store, pool=None)

    # fetch_origin must NOT be called — non-terminal items guard fires first.
    mock_fetch.assert_not_awaited()
    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED


# ---------------------------------------------------------------------------
# Feature not in PLANNED when item becomes terminal → no-op
# ---------------------------------------------------------------------------


async def test_feature_not_planned_is_noop(task_store):
    """Feature in WAITING state when all items terminal → no transition."""
    feat = await _make_feature(task_store)
    # Transition feature to WAITING.
    await task_store.transition_feature(
        feat.id, FeatureState.WAITING, allowed=FEATURE_WORKER_TRANSITIONS
    )
    assert task_store.get(feat.id).feature_state == FeatureState.WAITING

    goal = await _make_goal(task_store, realizes=feat.id)
    await _transition_goal_to_done(task_store, goal.id)

    mock_fetch = AsyncMock(return_value=None)
    with (
        patch.object(app.git_ops, "fetch_origin", mock_fetch),
        patch.object(app.git_ops, "branch_exists_on_origin", AsyncMock(return_value=False)),
    ):
        await propagate_to_feature(goal.id, task_store, pool=None)

    mock_fetch.assert_not_awaited()
    assert task_store.get(feat.id).feature_state == FeatureState.WAITING


# ---------------------------------------------------------------------------
# Slug derivation: date prefix stripped correctly
# ---------------------------------------------------------------------------


async def test_slug_derivation_strips_date_prefix(task_store):
    """Branch name is feature/<stripped-slug>, verifying prefix strip is applied."""
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)
    await _transition_goal_to_done(task_store, goal.id)

    captured_branch: list[str] = []

    async def _capture_branch(space_dir, branch):
        captured_branch.append(branch)
        return False  # absent → transition to DONE

    with (
        patch.object(app.git_ops, "fetch_origin", AsyncMock(return_value=None)),
        patch.object(app.git_ops, "branch_exists_on_origin", _capture_branch),
    ):
        await propagate_to_feature(goal.id, task_store, pool=None)

    assert len(captured_branch) == 1
    branch = captured_branch[0]
    assert branch.startswith("feature/")
    # Verify the slug portion has no YYYY-MM-DD-HHMM- prefix.
    import re as _re
    slug_part = branch[len("feature/"):]
    assert not _re.match(r"^\d{4}-\d{2}-\d{2}-\d{4}-", slug_part)
    assert task_store.get(feat.id).feature_state == FeatureState.DONE
