"""Tests for goal_sync.propagate_to_parent.

Covers:
- Child → ACTIVE, parent WAITING → parent transitions to ACTIVE.
- Child → DONE, parent WAITING → parent transitions to ACTIVE and goal is re-enqueued.
- Child → ARCHIVED, parent WAITING → same as DONE.
- Child → WAITING, parent ACTIVE → no-op.
- Task without parent → no-op.
- Child of non-goal parent → no-op (defensive).
- Integration: pause→resume cycle via reply + _finalize.
"""
from __future__ import annotations

import pytest

from app.goal_sync import propagate_to_parent, GOAL_SYNC_TRANSITIONS
from app.models import TaskState
from app.storage import TaskStore

SPACE_ID = "test-space"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_goal(store: TaskStore, *, title: str = "Goal") -> str:
    task = await store.create(space_id=SPACE_ID, title=title, brief="g", type="goal")
    return task.id


async def _create_child(store: TaskStore, parent_id: str, *, title: str = "Child") -> str:
    task = await store.create(space_id=SPACE_ID, title=title, brief="c", parent_id=parent_id)
    return task.id


async def _set_state(store: TaskStore, task_id: str, state: TaskState) -> None:
    """Force any state via a permissive transition set (for test setup only)."""
    all_transitions = {
        (TaskState.BACKLOG, TaskState.ACTIVE),
        (TaskState.BACKLOG, TaskState.WAITING),
        (TaskState.BACKLOG, TaskState.DONE),
        (TaskState.BACKLOG, TaskState.ARCHIVED),
        (TaskState.ACTIVE, TaskState.WAITING),
        (TaskState.ACTIVE, TaskState.DONE),
        (TaskState.ACTIVE, TaskState.ARCHIVED),
        (TaskState.WAITING, TaskState.ACTIVE),
        (TaskState.WAITING, TaskState.DONE),
        (TaskState.WAITING, TaskState.ARCHIVED),
        (TaskState.DONE, TaskState.BACKLOG),
    }
    await store.transition(task_id, state, allowed=all_transitions)


class _MockWorker:
    """Minimal Worker stand-in with configurable current()."""

    def __init__(self, current_id: str | None = None) -> None:
        self._current_id = current_id

    def current(self) -> str | None:
        return self._current_id


class _RecordingPool:
    """Minimal WorkerPool stand-in that records enqueue calls."""

    enqueued: list[tuple[str, str]]

    def __init__(self, *, current_task: str | None = None) -> None:
        self.enqueued = []
        self._worker = _MockWorker(current_task)

    def get(self, space_id: str) -> _MockWorker | None:
        return self._worker

    async def enqueue(self, space_id: str, task_id: str) -> None:
        self.enqueued.append((space_id, task_id))


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


async def test_child_active_parent_waiting_activates_parent(task_store: TaskStore) -> None:
    goal_id = await _create_goal(task_store)
    child_id = await _create_child(task_store, goal_id)

    await _set_state(task_store, goal_id, TaskState.WAITING)
    await _set_state(task_store, child_id, TaskState.ACTIVE)

    pool = _RecordingPool()
    await propagate_to_parent(child_id, task_store, pool)

    assert task_store.get(goal_id).state == TaskState.ACTIVE
    assert pool.enqueued == []  # no re-enqueue on mere activation


async def test_child_active_parent_backlog_activates_parent(task_store: TaskStore) -> None:
    # Starting a nested subgoal directly (child → ACTIVE) must surface a parent
    # that is still in BACKLOG, otherwise the parent goal stays stuck in TODO
    # while its subtree is clearly in progress.
    goal_id = await _create_goal(task_store)
    child_id = await _create_child(task_store, goal_id)

    # goal_id stays BACKLOG (default); child becomes ACTIVE.
    await _set_state(task_store, child_id, TaskState.ACTIVE)

    pool = _RecordingPool()
    await propagate_to_parent(child_id, task_store, pool)

    assert task_store.get(goal_id).state == TaskState.ACTIVE
    assert pool.enqueued == []  # activation only, no re-enqueue


async def test_child_active_surfaces_whole_ancestor_chain(task_store: TaskStore) -> None:
    # A deeply nested subgoal becoming ACTIVE should surface the entire ancestor
    # spine (grandparent included), not just the immediate parent.
    grandparent_id = await _create_goal(task_store, title="Grandparent")
    parent_id = await _create_goal(task_store, title="Parent")
    # Re-parent the parent goal under the grandparent.
    await task_store.set_parent(parent_id, grandparent_id)
    child_id = await _create_child(task_store, parent_id)

    await _set_state(task_store, child_id, TaskState.ACTIVE)

    pool = _RecordingPool()
    await propagate_to_parent(child_id, task_store, pool)

    assert task_store.get(parent_id).state == TaskState.ACTIVE
    assert task_store.get(grandparent_id).state == TaskState.ACTIVE


async def test_child_done_parent_waiting_activates_and_enqueues(task_store: TaskStore) -> None:
    goal_id = await _create_goal(task_store)
    child_id = await _create_child(task_store, goal_id)

    await _set_state(task_store, goal_id, TaskState.WAITING)
    await _set_state(task_store, child_id, TaskState.DONE)

    pool = _RecordingPool()
    await propagate_to_parent(child_id, task_store, pool)

    assert task_store.get(goal_id).state == TaskState.ACTIVE
    assert pool.enqueued == [(SPACE_ID, goal_id)]


async def test_child_archived_parent_waiting_activates_and_enqueues(task_store: TaskStore) -> None:
    goal_id = await _create_goal(task_store)
    child_id = await _create_child(task_store, goal_id)

    await _set_state(task_store, goal_id, TaskState.WAITING)
    await _set_state(task_store, child_id, TaskState.ARCHIVED)

    pool = _RecordingPool()
    await propagate_to_parent(child_id, task_store, pool)

    assert task_store.get(goal_id).state == TaskState.ACTIVE
    assert pool.enqueued == [(SPACE_ID, goal_id)]


async def test_child_waiting_parent_active_noop(task_store: TaskStore) -> None:
    goal_id = await _create_goal(task_store)
    child_id = await _create_child(task_store, goal_id)

    await _set_state(task_store, goal_id, TaskState.ACTIVE)
    await _set_state(task_store, child_id, TaskState.WAITING)

    pool = _RecordingPool()
    await propagate_to_parent(child_id, task_store, pool)

    assert task_store.get(goal_id).state == TaskState.ACTIVE
    assert pool.enqueued == []


async def test_no_parent_noop(task_store: TaskStore) -> None:
    task_id = (await task_store.create(space_id=SPACE_ID, title="Standalone", brief="b")).id
    await _set_state(task_store, task_id, TaskState.DONE)

    pool = _RecordingPool()
    await propagate_to_parent(task_id, task_store, pool)

    assert pool.enqueued == []


async def test_parent_not_goal_noop(task_store: TaskStore) -> None:
    # Parent is a regular task, not a goal.
    parent_id = (await task_store.create(space_id=SPACE_ID, title="Parent task", brief="b")).id
    child_id = await _create_child(task_store, parent_id)

    await _set_state(task_store, parent_id, TaskState.WAITING)
    await _set_state(task_store, child_id, TaskState.DONE)

    pool = _RecordingPool()
    await propagate_to_parent(child_id, task_store, pool)

    # Parent should remain WAITING — it's not a goal.
    assert task_store.get(parent_id).state == TaskState.WAITING
    assert pool.enqueued == []


async def test_child_done_parent_active_enqueues(task_store: TaskStore) -> None:
    """Child DONE while parent is already ACTIVE → goal is re-enqueued (no state transition)."""
    goal_id = await _create_goal(task_store)
    child_id = await _create_child(task_store, goal_id)

    await _set_state(task_store, goal_id, TaskState.ACTIVE)
    await _set_state(task_store, child_id, TaskState.DONE)

    pool = _RecordingPool()
    await propagate_to_parent(child_id, task_store, pool)

    assert task_store.get(goal_id).state == TaskState.ACTIVE
    assert pool.enqueued == [(SPACE_ID, goal_id)]


async def test_child_done_parent_active_running_no_enqueue(task_store: TaskStore) -> None:
    """Child DONE while _run_goal is actively running the goal → do not re-enqueue."""
    goal_id = await _create_goal(task_store)
    child_id = await _create_child(task_store, goal_id)

    await _set_state(task_store, goal_id, TaskState.ACTIVE)
    await _set_state(task_store, child_id, TaskState.DONE)

    # Worker reports it is currently running this goal.
    pool = _RecordingPool(current_task=goal_id)
    await propagate_to_parent(child_id, task_store, pool)

    assert task_store.get(goal_id).state == TaskState.ACTIVE
    assert pool.enqueued == []


async def test_none_pool_skips_enqueue(task_store: TaskStore) -> None:
    """If worker_pool is None, activation still happens but enqueue is skipped."""
    goal_id = await _create_goal(task_store)
    child_id = await _create_child(task_store, goal_id)

    await _set_state(task_store, goal_id, TaskState.WAITING)
    await _set_state(task_store, child_id, TaskState.DONE)

    await propagate_to_parent(child_id, task_store, None)

    assert task_store.get(goal_id).state == TaskState.ACTIVE


async def test_goal_sync_transitions_constant() -> None:
    """GOAL_SYNC_TRANSITIONS covers WAITING → ACTIVE and BACKLOG → ACTIVE."""
    assert GOAL_SYNC_TRANSITIONS == {
        (TaskState.WAITING, TaskState.ACTIVE),
        (TaskState.BACKLOG, TaskState.ACTIVE),
    }


async def test_child_done_parent_backlog_activates_and_enqueues(task_store: TaskStore) -> None:
    """Child DONE while parent goal is in BACKLOG → parent activates and is re-enqueued."""
    goal_id = await _create_goal(task_store)
    child_id = await _create_child(task_store, goal_id)

    # goal stays BACKLOG (default); child moves to DONE independently
    await _set_state(task_store, child_id, TaskState.DONE)

    pool = _RecordingPool()
    await propagate_to_parent(child_id, task_store, pool)

    assert task_store.get(goal_id).state == TaskState.ACTIVE
    assert pool.enqueued == [(SPACE_ID, goal_id)]


async def test_child_archived_parent_backlog_activates_and_enqueues(task_store: TaskStore) -> None:
    """Child ARCHIVED while parent goal is in BACKLOG → parent activates and is re-enqueued."""
    goal_id = await _create_goal(task_store)
    child_id = await _create_child(task_store, goal_id)

    await _set_state(task_store, child_id, TaskState.ARCHIVED)

    pool = _RecordingPool()
    await propagate_to_parent(child_id, task_store, pool)

    assert task_store.get(goal_id).state == TaskState.ACTIVE
    assert pool.enqueued == [(SPACE_ID, goal_id)]


# ---------------------------------------------------------------------------
# Integration: pause → resume cycle
# ---------------------------------------------------------------------------


async def test_integration_reply_activates_parent(task_store: TaskStore) -> None:
    """apply_reply on a WAITING child triggers propagation that activates its goal."""
    goal_id = await _create_goal(task_store, title="Integration Goal")
    child_id = await _create_child(task_store, goal_id, title="Step 1")

    # Set up: goal and child both WAITING (goal paused waiting for user input on child).
    await _set_state(task_store, goal_id, TaskState.WAITING)
    # child is BACKLOG by default; transition to WAITING to simulate a prior run
    await _set_state(task_store, child_id, TaskState.WAITING)

    # User replies to the child — apply_reply transitions child to ACTIVE.
    outcome = await task_store.apply_reply(child_id, "continue please")
    assert outcome.task.state == TaskState.ACTIVE

    # Simulate what the API endpoint does after apply_reply.
    pool = _RecordingPool()
    await propagate_to_parent(child_id, task_store, pool)

    assert task_store.get(goal_id).state == TaskState.ACTIVE
    # No re-enqueue on reply (child is merely ACTIVE; goal will be re-enqueued when child finishes).
    assert pool.enqueued == []


async def test_integration_finalize_done_requeues_goal(task_store: TaskStore) -> None:
    """When a child finishes DONE, the goal is activated and re-enqueued."""
    goal_id = await _create_goal(task_store, title="Integration Goal 2")
    child_id = await _create_child(task_store, goal_id, title="Step A")

    await _set_state(task_store, goal_id, TaskState.WAITING)
    await _set_state(task_store, child_id, TaskState.DONE)

    pool = _RecordingPool()
    await propagate_to_parent(child_id, task_store, pool)

    assert task_store.get(goal_id).state == TaskState.ACTIVE
    assert pool.enqueued == [(SPACE_ID, goal_id)]
