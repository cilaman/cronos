"""I3: TaskStore.board() excludes tasks with type in ('feature', 'fix').

Verifies that the tasks board is disjoint from the FeatureBoard — a regular
task appears in board() while feature and fix tasks are absent from all four
lanes (backlog, active, waiting, done).
"""
from __future__ import annotations

import pytest

SPACE_ID = "test-space"


async def _make(store, title, *, type="task"):
    return await store.create(space_id=SPACE_ID, title=title, brief="", type=type)


@pytest.mark.asyncio
async def test_board_excludes_feature_type(task_store):
    """board() must not include tasks with type='feature' in any lane."""
    feat = await _make(task_store, "A feature item", type="feature")
    task = await _make(task_store, "A regular task", type="task")

    board = task_store.board(SPACE_ID)
    all_ids = {s.id for lane in [board.backlog, board.active, board.waiting, board.done] for s in lane}

    assert feat.id not in all_ids, "feature task must not appear in board()"
    assert task.id in all_ids, "regular task must appear in board()"


@pytest.mark.asyncio
async def test_board_excludes_fix_type(task_store):
    """board() must not include tasks with type='fix' in any lane."""
    fix = await _make(task_store, "A fix item", type="fix")
    task = await _make(task_store, "A regular task", type="task")

    board = task_store.board(SPACE_ID)
    all_ids = {s.id for lane in [board.backlog, board.active, board.waiting, board.done] for s in lane}

    assert fix.id not in all_ids, "fix task must not appear in board()"
    assert task.id in all_ids, "regular task must appear in board()"


@pytest.mark.asyncio
async def test_board_excludes_feature_and_fix_keeps_task(task_store):
    """board() with one task, one feature, one fix — only the task appears."""
    task = await _make(task_store, "Regular task", type="task")
    feat = await _make(task_store, "Feature item", type="feature")
    fix = await _make(task_store, "Fix item", type="fix")

    board = task_store.board(SPACE_ID)
    all_ids = {s.id for lane in [board.backlog, board.active, board.waiting, board.done] for s in lane}

    assert task.id in all_ids, "regular task must appear in board()"
    assert feat.id not in all_ids, "feature must not appear in board()"
    assert fix.id not in all_ids, "fix must not appear in board()"


@pytest.mark.asyncio
async def test_board_empty_when_only_features_and_fixes(task_store):
    """board() returns all-empty lanes when the space contains only feature/fix tasks."""
    await _make(task_store, "Feature A", type="feature")
    await _make(task_store, "Feature B", type="feature")
    await _make(task_store, "Fix A", type="fix")

    board = task_store.board(SPACE_ID)
    total = sum(
        len(lane) for lane in [board.backlog, board.active, board.waiting, board.done]
    )
    assert total == 0, f"Expected 0 tasks in board(), got {total}"
