"""Tests for feature_sync.propagate_to_feature — state transition logic.

Covers all 5 state transitions derived from realizing items:
1. PLANNED  — all realizing items in backlog
2. PROCESSING — any realizing item is active
3. WAITING  — any realizing item is waiting (none active)
4. DONE     — all realizing items done or archived
5. Mixed done + active → PROCESSING (active takes priority)
6. Empty realizing set → no-op (feature stays BACKLOG)
"""
from __future__ import annotations

import pytest

from app.feature_state import FEATURE_USER_TRANSITIONS, FEATURE_WORKER_TRANSITIONS
from app.feature_sync import propagate_to_feature
from app.models import FeatureState, TaskState
from app.storage import TaskStore

SPACE_ID = "test-space"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_TASK_TRANSITIONS = frozenset(
    {
        (TaskState.BACKLOG, TaskState.ACTIVE),
        (TaskState.BACKLOG, TaskState.WAITING),
        (TaskState.BACKLOG, TaskState.DONE),
        (TaskState.BACKLOG, TaskState.ARCHIVED),
        (TaskState.ACTIVE, TaskState.WAITING),
        (TaskState.ACTIVE, TaskState.DONE),
        (TaskState.ACTIVE, TaskState.ARCHIVED),
        (TaskState.WAITING, TaskState.ACTIVE),
        (TaskState.WAITING, TaskState.DONE),
        (TaskState.DONE, TaskState.ARCHIVED),
        (TaskState.DONE, TaskState.BACKLOG),
    }
)


async def _make_feature(store: TaskStore, *, start_state: FeatureState = FeatureState.BACKLOG) -> object:
    feat = await store.create(space_id=SPACE_ID, title="Feature", brief="", type="feature")
    if start_state != FeatureState.BACKLOG:
        await store.transition_feature(feat.id, start_state, allowed=FEATURE_WORKER_TRANSITIONS)
    return store.get(feat.id)


async def _make_goal(store: TaskStore, *, realizes: str | None = None, title: str = "Goal") -> object:
    goal = await store.create(space_id=SPACE_ID, title=title, brief="", type="goal")
    if realizes is not None:
        await store.set_realizes(goal.id, realizes)
    return store.get(goal.id)


async def _set_task_state(store: TaskStore, task_id: str, state: TaskState) -> None:
    await store.transition(task_id, state, allowed=_ALL_TASK_TRANSITIONS)


# ---------------------------------------------------------------------------
# Test 1: PLANNED — all realizing items in backlog
# ---------------------------------------------------------------------------


async def test_all_backlog_transitions_to_planned(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)
    # goal is in BACKLOG by default; propagate should move feature → PLANNED

    await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED


async def test_multiple_backlog_goals_transitions_to_planned(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store)
    goal1 = await _make_goal(task_store, realizes=feat.id, title="Goal 1")
    goal2 = await _make_goal(task_store, realizes=feat.id, title="Goal 2")
    # Both goals stay in BACKLOG

    await propagate_to_feature(goal1.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED


# ---------------------------------------------------------------------------
# Test 2: PROCESSING — any realizing item is active
# ---------------------------------------------------------------------------


async def test_any_active_item_transitions_to_processing(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store, start_state=FeatureState.PLANNED)
    goal = await _make_goal(task_store, realizes=feat.id)
    await _set_task_state(task_store, goal.id, TaskState.ACTIVE)

    await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.PROCESSING


async def test_one_active_among_many_transitions_to_processing(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store, start_state=FeatureState.PLANNED)
    goal1 = await _make_goal(task_store, realizes=feat.id, title="Goal 1")
    goal2 = await _make_goal(task_store, realizes=feat.id, title="Goal 2")

    # goal1 active, goal2 stays backlog
    await _set_task_state(task_store, goal1.id, TaskState.ACTIVE)

    await propagate_to_feature(goal1.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.PROCESSING


# ---------------------------------------------------------------------------
# Test 3: WAITING — any item waiting, none active
# ---------------------------------------------------------------------------


async def test_all_waiting_transitions_to_waiting(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store, start_state=FeatureState.PROCESSING)
    goal = await _make_goal(task_store, realizes=feat.id)
    await _set_task_state(task_store, goal.id, TaskState.WAITING)

    await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.WAITING


async def test_any_waiting_none_active_transitions_to_waiting(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store, start_state=FeatureState.PROCESSING)
    goal1 = await _make_goal(task_store, realizes=feat.id, title="Goal 1")
    goal2 = await _make_goal(task_store, realizes=feat.id, title="Goal 2")

    await _set_task_state(task_store, goal1.id, TaskState.WAITING)
    # goal2 stays backlog — waiting + backlog, no active → WAITING (any WAITING with no ACTIVE)

    await propagate_to_feature(goal1.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.WAITING


async def test_all_waiting_no_active_transitions_to_waiting(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store, start_state=FeatureState.PROCESSING)
    goal1 = await _make_goal(task_store, realizes=feat.id, title="Goal 1")
    goal2 = await _make_goal(task_store, realizes=feat.id, title="Goal 2")

    await _set_task_state(task_store, goal1.id, TaskState.WAITING)
    await _set_task_state(task_store, goal2.id, TaskState.WAITING)

    await propagate_to_feature(goal1.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.WAITING


# ---------------------------------------------------------------------------
# Test 4: DONE — all realizing items done or archived
# ---------------------------------------------------------------------------


async def test_all_done_transitions_to_done(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store, start_state=FeatureState.PROCESSING)
    goal = await _make_goal(task_store, realizes=feat.id)
    await _set_task_state(task_store, goal.id, TaskState.ACTIVE)
    await _set_task_state(task_store, goal.id, TaskState.DONE)

    await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.DONE


async def test_all_archived_transitions_to_done(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store, start_state=FeatureState.PROCESSING)
    goal = await _make_goal(task_store, realizes=feat.id)
    await _set_task_state(task_store, goal.id, TaskState.ACTIVE)
    await _set_task_state(task_store, goal.id, TaskState.DONE)
    await _set_task_state(task_store, goal.id, TaskState.ARCHIVED)

    await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.DONE


async def test_mix_done_and_archived_transitions_to_done(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store, start_state=FeatureState.PROCESSING)
    goal1 = await _make_goal(task_store, realizes=feat.id, title="Goal 1")
    goal2 = await _make_goal(task_store, realizes=feat.id, title="Goal 2")

    await _set_task_state(task_store, goal1.id, TaskState.ACTIVE)
    await _set_task_state(task_store, goal1.id, TaskState.DONE)

    await _set_task_state(task_store, goal2.id, TaskState.ACTIVE)
    await _set_task_state(task_store, goal2.id, TaskState.DONE)
    await _set_task_state(task_store, goal2.id, TaskState.ARCHIVED)

    await propagate_to_feature(goal1.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.DONE


# ---------------------------------------------------------------------------
# Test 5: Mixed done + active → PROCESSING (active takes priority)
# ---------------------------------------------------------------------------


async def test_mixed_done_and_active_transitions_to_processing(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store, start_state=FeatureState.PROCESSING)
    goal1 = await _make_goal(task_store, realizes=feat.id, title="Goal 1")
    goal2 = await _make_goal(task_store, realizes=feat.id, title="Goal 2")

    await _set_task_state(task_store, goal1.id, TaskState.ACTIVE)
    await _set_task_state(task_store, goal1.id, TaskState.DONE)

    await _set_task_state(task_store, goal2.id, TaskState.ACTIVE)

    await propagate_to_feature(goal2.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.PROCESSING


async def test_active_takes_priority_over_waiting(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store, start_state=FeatureState.PROCESSING)
    goal1 = await _make_goal(task_store, realizes=feat.id, title="Active Goal")
    goal2 = await _make_goal(task_store, realizes=feat.id, title="Waiting Goal")

    await _set_task_state(task_store, goal1.id, TaskState.ACTIVE)
    await _set_task_state(task_store, goal2.id, TaskState.WAITING)

    await propagate_to_feature(goal1.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.PROCESSING


# ---------------------------------------------------------------------------
# Test 6: Empty realizing set → no-op (feature stays BACKLOG)
# ---------------------------------------------------------------------------


async def test_empty_realizing_set_is_noop(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store)
    # Create a goal that does NOT realize the feature; link it to nothing
    goal = await _make_goal(task_store)
    # Now create a separate goal that DOES realize the feature, but immediately detach
    # via patching realizing_items to return [] to simulate the empty case

    original_realizing = task_store.realizing_items

    async def _empty_realizing(feature_id):
        return []

    # Use a goal that realizes the feature so we get past the root/realizes checks
    realizing_goal = await _make_goal(task_store, realizes=feat.id, title="Realizing Goal")
    task_store.realizing_items = _empty_realizing
    try:
        await propagate_to_feature(realizing_goal.id, task_store, pool=None)
    finally:
        task_store.realizing_items = original_realizing

    assert task_store.get(feat.id).feature_state == FeatureState.BACKLOG


async def test_no_realizes_link_is_noop(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store)  # not linked to any feature
    await _set_task_state(task_store, goal.id, TaskState.ACTIVE)

    await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.BACKLOG


# ---------------------------------------------------------------------------
# Edge: child item propagates via root goal (not directly)
# ---------------------------------------------------------------------------


async def test_child_item_propagates_via_root_goal(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store, start_state=FeatureState.PLANNED)
    root_goal = await _make_goal(task_store, realizes=feat.id)
    # child task nested under the root goal
    child = await task_store.create(
        space_id=SPACE_ID, title="Child Task", brief="", parent_id=root_goal.id
    )

    await _set_task_state(task_store, root_goal.id, TaskState.ACTIVE)

    # Propagating from child — should no-op because item_id != root_goal.id
    await propagate_to_feature(child.id, task_store, pool=None)

    # feature_state unchanged because child is not root goal
    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED


# ---------------------------------------------------------------------------
# Idempotent: same state, no transition attempted
# ---------------------------------------------------------------------------


async def test_same_state_is_idempotent(task_store: TaskStore) -> None:
    feat = await _make_feature(task_store, start_state=FeatureState.PLANNED)
    goal = await _make_goal(task_store, realizes=feat.id)
    # goal in BACKLOG → would produce PLANNED, which is already the state

    await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED
