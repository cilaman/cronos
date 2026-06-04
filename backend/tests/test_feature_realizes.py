"""Tests for set_realizes, realizing_items, validate_realizes — I8 reserved names."""
from __future__ import annotations

import pytest

from app.storage import CycleError, InvalidTransition, TaskNotFound

SPACE_ID = "test-space"


async def _make_feat(store, title="Feature"):
    return await store.create(space_id=SPACE_ID, title=title, brief="", type="feature")


async def _make_task(store, title="Task"):
    return await store.create(space_id=SPACE_ID, title=title, brief="", type="task")


# ---------------------------------------------------------------------------
# I8: set_realizes / realizing_items / validate_realizes
# ---------------------------------------------------------------------------


async def test_set_realizes(task_store):
    """set_realizes must set task.realizes to the feature id."""
    feat = await _make_feat(task_store, "Widget feature")
    task = await _make_task(task_store, "Impl task")

    updated = await task_store.set_realizes(task.id, feat.id)
    assert updated.realizes == feat.id


async def test_realizing_items(task_store):
    """realizing_items must return all tasks that realize the given feature."""
    feat = await _make_feat(task_store)
    t1 = await _make_task(task_store, "Task 1")
    t2 = await _make_task(task_store, "Task 2")
    other = await _make_task(task_store, "Unrelated")

    await task_store.set_realizes(t1.id, feat.id)
    await task_store.set_realizes(t2.id, feat.id)

    items = await task_store.realizing_items(feat.id)
    item_ids = {s.id for s in items}
    assert t1.id in item_ids
    assert t2.id in item_ids
    assert other.id not in item_ids


async def test_validate_realizes(task_store):
    """validate_realizes must reject cross-space, non-feature target, and self-reference."""
    feat = await _make_feat(task_store, "Feature")
    task = await _make_task(task_store, "Task")
    regular = await _make_task(task_store, "Regular")

    # Self-reference: item realizes itself
    with pytest.raises((CycleError, Exception)):
        await task_store.set_realizes(feat.id, feat.id)

    # Target is not feature or fix (regular task)
    with pytest.raises(Exception):
        await task_store.set_realizes(task.id, regular.id)

    # Clearing (None) must always succeed
    updated = await task_store.set_realizes(task.id, None)
    assert updated.realizes is None


async def test_set_realizes_clears(task_store):
    """set_realizes(id, None) must clear the realizes field."""
    feat = await _make_feat(task_store)
    task = await _make_task(task_store)

    await task_store.set_realizes(task.id, feat.id)
    cleared = await task_store.set_realizes(task.id, None)
    assert cleared.realizes is None

    items = await task_store.realizing_items(feat.id)
    assert all(s.id != task.id for s in items)
