"""Tests for feature/fix transition_feature and _next_feature_key (I5 reserved names).

Covers transition_feature method, feature_state unchanged after transition,
and basic create() integration with feature_key assignment.
"""
from __future__ import annotations

import pytest

from app.feature_state import FEATURE_USER_TRANSITIONS, FEATURE_WORKER_TRANSITIONS
from app.models import FeatureState, TaskState
from app.storage import InvalidTransition, TaskNotFound

SPACE_ID = "test-space"


async def _create_feature(task_store, *, title="Test feature", task_type="feature"):
    return await task_store.create(
        space_id=SPACE_ID,
        title=title,
        brief="",
        type=task_type,
    )


# ---------------------------------------------------------------------------
# I5: transition_feature
# ---------------------------------------------------------------------------


async def test_transition_feature(task_store):
    """transition_feature must move feature_state and leave task.state unchanged."""
    task = await _create_feature(task_store)
    assert task.feature_state == FeatureState.BACKLOG
    initial_task_state = task.state

    # BACKLOG → PROCESSING is in FEATURE_USER_TRANSITIONS
    updated = await task_store.transition_feature(
        task.id,
        FeatureState.PROCESSING,
        allowed=FEATURE_USER_TRANSITIONS,
    )
    assert updated.feature_state == FeatureState.PROCESSING
    # task.state (TaskState) must not have been mutated
    assert updated.state == initial_task_state, (
        f"task.state changed from {initial_task_state} to {updated.state} — must stay unchanged"
    )


async def test_feature_state_unchanged_task_state(task_store):
    """After any transition_feature call, task.state (TaskState) is always the same as before."""
    task = await _create_feature(task_store)
    original_state = task.state

    # Perform a chain of valid transitions
    t1 = await task_store.transition_feature(task.id, FeatureState.PROCESSING, allowed=FEATURE_USER_TRANSITIONS)
    assert t1.state == original_state, "task.state changed after BACKLOG→PROCESSING"

    t2 = await task_store.transition_feature(task.id, FeatureState.PLANNED, allowed=FEATURE_WORKER_TRANSITIONS)
    assert t2.state == original_state, "task.state changed after PROCESSING→PLANNED"

    t3 = await task_store.transition_feature(task.id, FeatureState.DONE, allowed=FEATURE_USER_TRANSITIONS)
    assert t3.state == original_state, "task.state changed after PLANNED→DONE"


async def test_transition_feature_invalid_transition_rejected(task_store):
    """transition_feature must raise InvalidTransition for disallowed moves."""
    task = await _create_feature(task_store)
    # BACKLOG → DONE is not in FEATURE_USER_TRANSITIONS
    with pytest.raises(InvalidTransition):
        await task_store.transition_feature(task.id, FeatureState.DONE, allowed=FEATURE_USER_TRANSITIONS)


async def test_transition_feature_wrong_type_rejected(task_store):
    """transition_feature must raise InvalidTransition for non-feature/fix tasks."""
    regular = await task_store.create(
        space_id=SPACE_ID, title="Regular task", brief="", type="task"
    )
    with pytest.raises(InvalidTransition):
        await task_store.transition_feature(regular.id, FeatureState.PROCESSING, allowed=FEATURE_USER_TRANSITIONS)


async def test_transition_feature_not_found(task_store):
    """transition_feature must raise TaskNotFound for unknown task ids."""
    with pytest.raises(TaskNotFound):
        await task_store.transition_feature("no-such-id", FeatureState.PROCESSING, allowed=FEATURE_USER_TRANSITIONS)
