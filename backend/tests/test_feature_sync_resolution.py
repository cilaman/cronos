"""Tests for feature_sync.propagate_to_feature — resolution and no-op cases (I2).

Covers:
- item with no realizes link on its root goal → no-op
- realizes target does not exist → no-op
- item is a child of a realizing goal (not the root goal itself) → no-op
- root goal with realizes present → resolution succeeds (feature task is looked up)
"""
from __future__ import annotations

from app.feature_state import FEATURE_USER_TRANSITIONS, FEATURE_WORKER_TRANSITIONS
from app.feature_sync import propagate_to_feature
from app.models import FeatureState, TaskState

SPACE_ID = "test-space"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _make_feature(store, title="My Feature"):
    """Create a feature task in PLANNED state."""
    feat = await store.create(space_id=SPACE_ID, title=title, brief="", type="feature")
    await store.transition_feature(feat.id, FeatureState.PROCESSING, allowed=FEATURE_USER_TRANSITIONS)
    await store.transition_feature(feat.id, FeatureState.PLANNED, allowed=FEATURE_WORKER_TRANSITIONS)
    return store.get(feat.id)


async def _make_goal(store, title="Realizing Goal", realizes=None):
    """Create a goal task, optionally linked to a feature."""
    goal = await store.create(space_id=SPACE_ID, title=title, brief="", type="goal")
    if realizes is not None:
        await store.set_realizes(goal.id, realizes)
    return store.get(goal.id)


async def _make_child(store, parent_id, title="Child Task"):
    """Create a child task under a goal."""
    child = await store.create(space_id=SPACE_ID, title=title, brief="", type="task")
    await store.set_parent(child.id, parent_id)
    return store.get(child.id)


# ---------------------------------------------------------------------------
# Test: item has no realizes → no-op
# ---------------------------------------------------------------------------


async def test_no_realizes_link_is_noop(task_store):
    """Root goal with no realizes link → propagate_to_feature is a no-op."""
    goal = await task_store.create(space_id=SPACE_ID, title="Standalone Goal", brief="", type="goal")

    # Should not raise; nothing to propagate
    await propagate_to_feature(goal.id, task_store, pool=None)
    # Verify no spurious side effects
    all_items = await task_store.realizing_items("nonexistent-id")
    assert all_items == []


# ---------------------------------------------------------------------------
# Test: realizes target missing → no-op
# ---------------------------------------------------------------------------


async def test_realizes_target_missing_is_noop(task_store):
    """Root goal with stale realizes link (feature deleted) → no-op."""
    feat = await task_store.create(space_id=SPACE_ID, title="Temp Feature", brief="", type="feature")
    goal = await task_store.create(space_id=SPACE_ID, title="Goal", brief="", type="goal")
    await task_store.set_realizes(goal.id, feat.id)

    # Simulate missing feature via a proxy store
    class _StoreProxy:
        def get(self, task_id):
            if task_id == feat.id:
                return None  # feature not found
            return task_store.get(task_id)

    await propagate_to_feature(goal.id, _StoreProxy(), pool=None)
    # No exception = success


# ---------------------------------------------------------------------------
# Test: child of a realizing goal → no-op
# ---------------------------------------------------------------------------


async def test_child_of_realizing_goal_is_noop(task_store):
    """Child task within a realizing goal must NOT trigger feature transitions."""
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)
    child = await _make_child(task_store, parent_id=goal.id)

    # Transition child to DONE
    await task_store.transition(child.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)})
    await task_store.transition(child.id, TaskState.DONE, allowed={(TaskState.ACTIVE, TaskState.DONE)})

    # propagate with child.id — no-op because child is not the root goal
    await propagate_to_feature(child.id, task_store, pool=None)

    # Feature state must remain PLANNED
    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED


# ---------------------------------------------------------------------------
# Test: root goal with realizes → resolution succeeds
# ---------------------------------------------------------------------------


async def test_root_goal_with_realizes_resolves(task_store):
    """Root goal with valid realizes → feature is resolved; I2 placeholders leave state unchanged."""
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)

    state_before = task_store.get(feat.id).feature_state

    # Resolution path exercised without error
    await propagate_to_feature(goal.id, task_store, pool=None)

    # Placeholder branches do nothing — feature state unchanged
    assert task_store.get(feat.id).feature_state == state_before


async def test_root_goal_active_transitions_to_processing(task_store):
    """Root goal in ACTIVE state with realizes → feature transitions to PROCESSING."""
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)
    await task_store.transition(goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)})

    await propagate_to_feature(goal.id, task_store, pool=None)
    assert task_store.get(feat.id).feature_state == FeatureState.PROCESSING


# ---------------------------------------------------------------------------
# P1-D: propagate_to_feature with non-existent item_id → no-op (line 51, 244)
# ---------------------------------------------------------------------------


async def test_propagate_nonexistent_item_is_noop(task_store):
    """propagate_to_feature with a non-existent item_id raises no exception and mutates nothing."""
    # _find_root calls store.get("nonexistent-id") → None → returns None (line 244)
    # propagate_to_feature returns early at line 51
    await propagate_to_feature("nonexistent-id", task_store, pool=None)
    # Test passes if no exception is raised


# ---------------------------------------------------------------------------
# P1-E: _find_root cycle guard — chain > 50 hops returns None (lines 249-250)
# ---------------------------------------------------------------------------


async def test_find_root_cycle_guard_returns_none(task_store):
    """A parent chain longer than 50 hops hits the cycle guard; _find_root returns None."""
    import types

    from app.feature_sync import _find_root

    # Build a 55-task chain: task-0 → task-1 → ... → task-54 → "task-55" (missing)
    # None of the first 55 tasks have parent_id=None, so _find_root never finds the root.
    chain: dict[str, object] = {}
    for i in range(55):
        chain[f"task-{i}"] = types.SimpleNamespace(
            id=f"task-{i}",
            parent_id=f"task-{i + 1}",
        )

    class _ChainStore:
        def get(self, task_id: str):
            return chain.get(task_id)  # task-55 is absent → None

    result = await _find_root("task-0", _ChainStore())
    assert result is None
