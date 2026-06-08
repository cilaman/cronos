"""Tests for TaskSummary.realized_by_count and .realizes_feature_key fields.

Covers:
- realized_by_count populated in feature_board()
- realizes_feature_key populated in board() for tasks with realizes set
- realizes_feature_key populated in realizing_items()
- R4 AC-3: missing realizes target does not raise; realizes_feature_key is None
- Cross-space: realizes_feature_key does not leak from another space in board()
- Both realizing_count and realized_by_count coexist on feature summaries
"""
from __future__ import annotations

import pytest

from app.models import FeatureState, TaskState

SPACE_ID = "test-space"
OTHER_SPACE = "other-space"


async def _make(store, title, *, space_id=SPACE_ID, type="task"):
    return await store.create(space_id=space_id, title=title, brief="", type=type)


# ---------------------------------------------------------------------------
# realized_by_count in feature_board()
# ---------------------------------------------------------------------------


async def test_realized_by_count_equals_realizing_count(task_store):
    """realized_by_count and realizing_count must be equal for feature summaries in feature_board()."""
    feat = await _make(task_store, "Feature", type="feature")
    t1 = await _make(task_store, "Task 1")
    t2 = await _make(task_store, "Task 2")
    await task_store.set_realizes(t1.id, feat.id)
    await task_store.set_realizes(t2.id, feat.id)

    board = await task_store.feature_board(SPACE_ID)
    all_summaries = {s.id: s for bucket in board.values() for s in bucket}
    s = all_summaries[feat.id]
    assert s.realizing_count == 2
    assert s.realized_by_count == 2


async def test_realized_by_count_zero_no_realizers(task_store):
    """realized_by_count is 0 when no tasks realize the feature."""
    feat = await _make(task_store, "Feature", type="feature")

    board = await task_store.feature_board(SPACE_ID)
    all_summaries = {s.id: s for bucket in board.values() for s in bucket}
    assert all_summaries[feat.id].realized_by_count == 0


# ---------------------------------------------------------------------------
# realizes_feature_key in feature_board()
# ---------------------------------------------------------------------------


async def test_feature_board_realizes_feature_key_none_when_not_set(task_store):
    """feature_board() leaves realizes_feature_key=None when realizes is None."""
    feat = await _make(task_store, "Standalone feature", type="feature")

    board = await task_store.feature_board(SPACE_ID)
    all_summaries = {s.id: s for bucket in board.values() for s in bucket}
    assert all_summaries[feat.id].realizes_feature_key is None


# ---------------------------------------------------------------------------
# realizes_feature_key in board()
# ---------------------------------------------------------------------------


async def test_board_realizes_feature_key_populated(task_store):
    """board() populates realizes_feature_key for tasks whose realizes targets a feature."""
    feat = await _make(task_store, "Feature A", type="feature")
    task = await _make(task_store, "Impl task")
    await task_store.set_realizes(task.id, feat.id)

    board = task_store.board(SPACE_ID)
    all_summaries = {
        s.id: s
        for lane in [board.backlog, board.active, board.waiting, board.done]
        for s in lane
    }
    assert task.id in all_summaries
    assert all_summaries[task.id].realizes_feature_key == feat.feature_key


async def test_board_realizes_feature_key_none_when_not_set(task_store):
    """board() leaves realizes_feature_key=None for tasks without realizes."""
    task = await _make(task_store, "Regular task")

    board = task_store.board(SPACE_ID)
    all_summaries = {
        s.id: s
        for lane in [board.backlog, board.active, board.waiting, board.done]
        for s in lane
    }
    assert all_summaries[task.id].realizes_feature_key is None


# ---------------------------------------------------------------------------
# realizes_feature_key in realizing_items()
# ---------------------------------------------------------------------------


async def test_realizing_items_realizes_feature_key(task_store):
    """realizing_items() populates realizes_feature_key on each returned summary."""
    feat = await _make(task_store, "Feature B", type="feature")
    t1 = await _make(task_store, "Task X")
    await task_store.set_realizes(t1.id, feat.id)

    items = await task_store.realizing_items(feat.id)
    assert len(items) == 1
    assert items[0].realizes_feature_key == feat.feature_key


# ---------------------------------------------------------------------------
# R4 AC-3: missing realizes target — no crash, realizes_feature_key is None
# ---------------------------------------------------------------------------


async def test_board_realizes_missing_target_no_crash(task_store):
    """board() must not raise when realizes points to a non-existent task; field is None."""
    task = await _make(task_store, "Orphan task")
    # Directly set realizes to a UUID that does not exist in the store.
    async with task_store._lock:
        task_store._by_id[task.id].realizes = "00000000-0000-0000-0000-000000000000"

    # Must not raise
    board = task_store.board(SPACE_ID)
    all_summaries = {
        s.id: s
        for lane in [board.backlog, board.active, board.waiting, board.done]
        for s in lane
    }
    assert task.id in all_summaries
    assert all_summaries[task.id].realizes_feature_key is None


async def test_feature_board_realizes_missing_target_no_crash(task_store):
    """feature_board() must not raise when a feature's realizes points to a deleted task."""
    feat = await _make(task_store, "Orphan feature", type="feature")
    async with task_store._lock:
        task_store._by_id[feat.id].realizes = "00000000-0000-0000-0000-000000000001"

    board = await task_store.feature_board(SPACE_ID)
    all_summaries = {s.id: s for bucket in board.values() for s in bucket}
    assert feat.id in all_summaries
    assert all_summaries[feat.id].realizes_feature_key is None


# ---------------------------------------------------------------------------
# Cross-space: realizes_feature_key must not leak from another space in board()
# ---------------------------------------------------------------------------


async def test_board_realizes_feature_key_no_cross_space_leak(task_store, space_store, tmp_spaces_dir):
    """A task in test-space with realizes pointing at a feature in other-space gets None."""
    # Create the other space so it has a tasks directory
    await space_store.create(
        name="Other space",
        color="#000000",
        icon=None,
        description="",
        space_id=OTHER_SPACE,
    )
    # Create feature in other-space
    feat_other = await task_store.create(
        space_id=OTHER_SPACE, title="Other-space feature", brief="", type="feature"
    )
    # Create task in test-space
    task_a = await _make(task_store, "Space-A task")

    # Wire realizes cross-space (bypassing validate_realizes guard for test purposes)
    async with task_store._lock:
        task_store._by_id[task_a.id].realizes = feat_other.id

    board = task_store.board(SPACE_ID)
    all_summaries = {
        s.id: s
        for lane in [board.backlog, board.active, board.waiting, board.done]
        for s in lane
    }
    assert task_a.id in all_summaries
    # Scoped lookup for SPACE_ID must not include other-space features → None
    assert all_summaries[task_a.id].realizes_feature_key is None


# ---------------------------------------------------------------------------
# Both count fields coexist on feature summaries (R5 regression guard)
# ---------------------------------------------------------------------------


async def test_feature_board_both_count_fields_coexist(task_store):
    """R5: realizing_count and realized_by_count must both be present and equal."""
    feat = await _make(task_store, "Feature with realizers", type="feature")
    t1 = await _make(task_store, "Task A")
    await task_store.set_realizes(t1.id, feat.id)

    board = await task_store.feature_board(SPACE_ID)
    all_summaries = {s.id: s for bucket in board.values() for s in bucket}
    s = all_summaries[feat.id]
    assert hasattr(s, "realizing_count"), "realizing_count must still exist"
    assert hasattr(s, "realized_by_count"), "realized_by_count must exist"
    assert s.realizing_count == s.realized_by_count == 1
