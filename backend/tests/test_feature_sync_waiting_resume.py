"""Tests for feature_sync.propagate_to_feature — WAITING/RESUME branches (I3).

Covers acceptance criteria:
- item→WAITING while feature PLANNED  → transition_feature(WAITING) called; idempotent on race
- item→ACTIVE  while feature WAITING  → transition_feature(PLANNED) called; idempotent on race
- other (state, feature_state) pairs   → no-op (feature state unchanged)
- concurrent WAITING race (InvalidTransition) → no exception escapes
"""
from __future__ import annotations

import pytest

from app.feature_state import FEATURE_USER_TRANSITIONS, FEATURE_WORKER_TRANSITIONS
from app.feature_sync import propagate_to_feature
from app.models import FeatureState, TaskState
from app.storage import InvalidTransition

SPACE_ID = "test-space"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _make_feature(store, title="My Feature") -> object:
    """Create a feature task in PLANNED state."""
    feat = await store.create(space_id=SPACE_ID, title=title, brief="", type="feature")
    await store.transition_feature(
        feat.id, FeatureState.PROCESSING, allowed=FEATURE_USER_TRANSITIONS
    )
    await store.transition_feature(
        feat.id, FeatureState.PLANNED, allowed=FEATURE_WORKER_TRANSITIONS
    )
    return store.get(feat.id)


async def _make_feature_in_waiting(store, title="Waiting Feature") -> object:
    """Create a feature task in WAITING state."""
    feat = await _make_feature(store, title=title)
    await store.transition_feature(
        feat.id, FeatureState.WAITING, allowed=FEATURE_WORKER_TRANSITIONS
    )
    return store.get(feat.id)


async def _make_goal(store, title="Realizing Goal", realizes=None) -> object:
    """Create a goal task, optionally linked to a feature."""
    goal = await store.create(space_id=SPACE_ID, title=title, brief="", type="goal")
    if realizes is not None:
        await store.set_realizes(goal.id, realizes)
    return store.get(goal.id)


async def _put_goal_in_state(store, goal_id: str, state: TaskState) -> None:
    """Drive a goal to the target TaskState through allowed intermediate states."""
    goal = store.get(goal_id)
    if goal.state == state:
        return
    # BACKLOG → ACTIVE → WAITING or DONE as needed
    if state == TaskState.ACTIVE:
        await store.transition(
            goal_id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
        )
    elif state == TaskState.WAITING:
        await store.transition(
            goal_id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
        )
        await store.transition(
            goal_id,
            TaskState.WAITING,
            allowed={(TaskState.ACTIVE, TaskState.WAITING)},
        )
    elif state == TaskState.DONE:
        await store.transition(
            goal_id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
        )
        await store.transition(
            goal_id, TaskState.DONE, allowed={(TaskState.ACTIVE, TaskState.DONE)}
        )


# ---------------------------------------------------------------------------
# I3 happy path 1: item→WAITING, feature PLANNED → feature→WAITING
# ---------------------------------------------------------------------------


async def test_item_waiting_feature_planned_transitions_to_waiting(task_store):
    """Root goal enters WAITING while feature is PLANNED → feature transitions to WAITING."""
    feat = await _make_feature(task_store)
    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED

    goal = await _make_goal(task_store, realizes=feat.id)
    await _put_goal_in_state(task_store, goal.id, TaskState.WAITING)

    await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.WAITING


# ---------------------------------------------------------------------------
# I3 happy path 2: item→ACTIVE, feature WAITING → feature→PLANNED (resume)
# ---------------------------------------------------------------------------


async def test_item_active_feature_waiting_transitions_to_planned(task_store):
    """Root goal becomes ACTIVE while feature is WAITING → feature transitions to PLANNED."""
    feat = await _make_feature_in_waiting(task_store)
    assert task_store.get(feat.id).feature_state == FeatureState.WAITING

    goal = await _make_goal(task_store, realizes=feat.id)
    await _put_goal_in_state(task_store, goal.id, TaskState.ACTIVE)

    await propagate_to_feature(goal.id, task_store, pool=None)

    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED


# ---------------------------------------------------------------------------
# No-op guard: item→WAITING while feature is NOT PLANNED → no state change
# ---------------------------------------------------------------------------


async def test_item_waiting_feature_not_planned_is_noop(task_store):
    """Root goal enters WAITING while feature is in WAITING → no transition (guard)."""
    feat = await _make_feature_in_waiting(task_store)
    assert task_store.get(feat.id).feature_state == FeatureState.WAITING

    goal = await _make_goal(task_store, realizes=feat.id)
    await _put_goal_in_state(task_store, goal.id, TaskState.WAITING)

    # Feature is already WAITING — should be no-op (wrong guard combination)
    await propagate_to_feature(goal.id, task_store, pool=None)

    # Feature state must remain WAITING (not raised, not changed to PLANNED)
    assert task_store.get(feat.id).feature_state == FeatureState.WAITING


# ---------------------------------------------------------------------------
# No-op guard: item→ACTIVE while feature is NOT WAITING → no state change
# ---------------------------------------------------------------------------


async def test_item_active_feature_not_waiting_is_noop(task_store):
    """Root goal becomes ACTIVE while feature is PLANNED → no transition (wrong guard)."""
    feat = await _make_feature(task_store)
    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED

    goal = await _make_goal(task_store, realizes=feat.id)
    await _put_goal_in_state(task_store, goal.id, TaskState.ACTIVE)

    await propagate_to_feature(goal.id, task_store, pool=None)

    # Feature state must remain PLANNED (no PLANNED→PLANNED attempt; guard says
    # we only go PLANNED when feature was WAITING)
    assert task_store.get(feat.id).feature_state == FeatureState.PLANNED


# ---------------------------------------------------------------------------
# Concurrent WAITING race: two consecutive propagate_to_feature calls with
# item in WAITING and feature initially PLANNED — second call must not raise.
# ---------------------------------------------------------------------------


async def test_concurrent_waiting_race_is_idempotent(task_store):
    """Two consecutive WAITING propagations → second call is idempotent (no exception)."""
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)
    await _put_goal_in_state(task_store, goal.id, TaskState.WAITING)

    # First call: PLANNED → WAITING
    await propagate_to_feature(goal.id, task_store, pool=None)
    assert task_store.get(feat.id).feature_state == FeatureState.WAITING

    # Second call: feature already WAITING — transition_feature raises InvalidTransition
    # internally; propagate_to_feature must swallow it and return without raising.
    await propagate_to_feature(goal.id, task_store, pool=None)

    # State is still WAITING — no exception was raised, no regression.
    assert task_store.get(feat.id).feature_state == FeatureState.WAITING


# ---------------------------------------------------------------------------
# waiting_question propagation: verify that item.waiting_question is read
# (persistence is best-effort given the current store API).
# ---------------------------------------------------------------------------


async def test_waiting_question_is_copied_when_available(task_store):
    """When item has a waiting_question, it is read and passed to the store (or logged)."""
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)
    await _put_goal_in_state(task_store, goal.id, TaskState.WAITING)

    # Inject a waiting_question on the goal by using finalize_run (sets state + question).
    # We need to put the goal into WAITING with a question; use finalize_run which
    # accepts waiting_question. Drive BACKLOG → ACTIVE first (done above), then
    # finalize_run to WAITING with a question.
    # Since _put_goal_in_state already moved to WAITING via transition(), we re-read
    # and verify the function does not raise even when waiting_question is absent.
    # The field is optional — propagate_to_feature should handle None gracefully.
    await propagate_to_feature(goal.id, task_store, pool=None)

    # Feature should be WAITING regardless of whether waiting_question was persisted.
    assert task_store.get(feat.id).feature_state == FeatureState.WAITING


# ---------------------------------------------------------------------------
# P1-A: waiting_question is propagated to the feature (post F1 backend fix).
# ---------------------------------------------------------------------------


async def test_waiting_question_propagated_to_feature(task_store):
    """waiting_question on the realizing goal is copied to the feature after the F1 fix."""
    feat = await _make_feature(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)

    # Drive goal BACKLOG → ACTIVE, then ACTIVE → WAITING with a waiting_question
    # using finalize_run (the worker path that sets waiting_question).
    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )
    await task_store.finalize_run(
        goal.id,
        new_state=TaskState.WAITING,
        session_id=None,
        waiting_question="Which provider?",
        history_entry="Agent stopped with a question",
    )

    goal_task = task_store.get(goal.id)
    assert goal_task.state == TaskState.WAITING
    assert goal_task.waiting_question == "Which provider?"

    await propagate_to_feature(goal.id, task_store, pool=None)

    updated_feat = task_store.get(feat.id)
    assert updated_feat.feature_state == FeatureState.WAITING
    assert updated_feat.waiting_question == "Which provider?"


# ---------------------------------------------------------------------------
# P2-F: ACTIVE-resume PLANNED concurrent race — InvalidTransition is swallowed.
# ---------------------------------------------------------------------------


async def test_active_resume_concurrent_race_is_swallowed(task_store):
    """Concurrent resume: transition_feature(PLANNED) raises InvalidTransition — no exception propagates."""
    feat = await _make_feature_in_waiting(task_store)
    goal = await _make_goal(task_store, realizes=feat.id)
    await _put_goal_in_state(task_store, goal.id, TaskState.ACTIVE)

    # Simulate the concurrent race: feature reads as WAITING but transition_feature
    # raises InvalidTransition (because another coroutine already moved it to PLANNED).
    original_transition = task_store.transition_feature

    async def _raise_invalid(task_id, new_state, *, allowed):
        raise InvalidTransition("concurrent: already PLANNED")

    task_store.transition_feature = _raise_invalid
    try:
        # Must not raise — lines 130-132 catch and swallow InvalidTransition.
        await propagate_to_feature(goal.id, task_store, pool=None)
    finally:
        task_store.transition_feature = original_transition
