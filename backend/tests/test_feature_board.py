"""Tests for feature/fix board exclusion and feature_board() — I7 reserved names."""
from __future__ import annotations

import pytest

from app.models import FeatureState, TaskState

SPACE_ID = "test-space"


async def _make(store, title, *, type="task"):
    return await store.create(space_id=SPACE_ID, title=title, brief="", type=type)


# ---------------------------------------------------------------------------
# I7: board/counts exclusion + feature_board
# ---------------------------------------------------------------------------


async def test_board_excludes_feature(task_store):
    """board() must not include feature or fix tasks in any lane."""
    feat = await _make(task_store, "My feature", type="feature")
    fix = await _make(task_store, "My fix", type="fix")
    task = await _make(task_store, "Regular task", type="task")

    board = task_store.board(SPACE_ID)
    all_ids = {s.id for lane in [board.backlog, board.active, board.waiting, board.done] for s in lane}
    assert feat.id not in all_ids, "feature task must not appear in board()"
    assert fix.id not in all_ids, "fix task must not appear in board()"
    assert task.id in all_ids, "regular task must still appear in board()"


async def test_counts_by_space_excludes_feature(task_store):
    """counts_by_space() must not count feature or fix tasks."""
    await _make(task_store, "Feature", type="feature")
    await _make(task_store, "Fix", type="fix")
    await _make(task_store, "Task 1", type="task")
    await _make(task_store, "Task 2", type="task")

    counts = task_store.counts_by_space()
    space_buckets = counts.get(SPACE_ID, {})
    space_count = sum(space_buckets.values())
    # Only the 2 regular tasks count; feature and fix are excluded
    assert space_count == 2, f"Expected 2 tasks counted, got {space_count}"


async def test_feature_board_buckets(task_store):
    """feature_board() must return features/fixes bucketed by feature_state."""
    from app.feature_state import FEATURE_USER_TRANSITIONS

    feat1 = await _make(task_store, "Feature 1", type="feature")
    feat2 = await _make(task_store, "Feature 2", type="feature")
    fix1 = await _make(task_store, "Fix 1", type="fix")
    _task = await _make(task_store, "Regular task", type="task")

    # Move feat2 to PROCESSING
    await task_store.transition_feature(feat2.id, FeatureState.PROCESSING, allowed=FEATURE_USER_TRANSITIONS)

    board = await task_store.feature_board(SPACE_ID)

    # feat1 and fix1 should be in BACKLOG
    backlog_ids = {s.id for s in board[FeatureState.BACKLOG]}
    assert feat1.id in backlog_ids
    assert fix1.id in backlog_ids

    # feat2 should be in PROCESSING
    processing_ids = {s.id for s in board[FeatureState.PROCESSING]}
    assert feat2.id in processing_ids

    # Regular task must NOT appear in any bucket
    all_ids = {s.id for bucket in board.values() for s in bucket}
    assert _task.id not in all_ids, "regular task must not appear in feature_board()"
