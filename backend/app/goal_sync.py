from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .models import TaskState
from .storage import InvalidTransition, TaskStore

if TYPE_CHECKING:
    from .worker_pool import WorkerPool

log = logging.getLogger("cronos.goal_sync")

# Separate from USER_TRANSITIONS / WORKER_TRANSITIONS so the intent is explicit:
# this is a synchronization action, not a user or post-run-worker action.
GOAL_SYNC_TRANSITIONS: set[tuple[TaskState, TaskState]] = {
    (TaskState.WAITING, TaskState.ACTIVE),
}


async def propagate_to_parent(
    child_id: str,
    store: TaskStore,
    worker_pool: WorkerPool | None,
) -> None:
    """Propagate a child's new state to its parent goal.

    Called after apply_reply (API layer) and after _finalize (worker).
    No-op when the child has no parent or the parent is not a goal.
    """
    child = store.get(child_id)
    if child is None or child.parent_id is None:
        return

    parent = store.get(child.parent_id)
    if parent is None or parent.type != "goal":
        return

    child_state = child.state
    parent_state = parent.state

    if child_state == TaskState.ACTIVE and parent_state == TaskState.WAITING:
        # Child resumed → surface the goal in the Active lane.
        try:
            await store.transition(
                child.parent_id, TaskState.ACTIVE, allowed=GOAL_SYNC_TRANSITIONS
            )
            log.info("Goal %s → ACTIVE (child %s became active)", child.parent_id, child_id)
        except InvalidTransition:
            pass  # already transitioned concurrently — idempotent
        except Exception:
            log.exception("Failed to activate parent goal %s", child.parent_id)

    elif child_state in (TaskState.DONE, TaskState.ARCHIVED) and parent_state in (
        TaskState.WAITING,
        TaskState.ACTIVE,
    ):
        # Child completed → ensure goal is ACTIVE and re-enqueue so orchestration resumes.
        # _run_goal skips already-done children, so it will pick the next eligible one.
        # parent_state == ACTIVE happens when a child was run standalone after the goal was
        # surfaced as ACTIVE by the ACTIVE-child branch above; in that case we skip the
        # redundant transition and go straight to enqueue.
        if parent_state == TaskState.WAITING:
            try:
                await store.transition(
                    child.parent_id, TaskState.ACTIVE, allowed=GOAL_SYNC_TRANSITIONS
                )
                log.info("Goal %s → ACTIVE (child %s finished)", child.parent_id, child_id)
            except InvalidTransition:
                return  # already active or terminal
            except Exception:
                log.exception("Failed to activate parent goal %s", child.parent_id)
                return

        if worker_pool is not None:
            worker = worker_pool.get(parent.space_id)
            # Don't re-enqueue if _run_goal is already orchestrating this goal.
            if worker is None or worker.current() != child.parent_id:
                try:
                    await worker_pool.enqueue(parent.space_id, child.parent_id)
                    log.info(
                        "Goal %s re-enqueued to continue after child %s",
                        child.parent_id,
                        child_id,
                    )
                except Exception:
                    log.exception("Failed to re-enqueue goal %s", child.parent_id)

    # Child → WAITING while parent ACTIVE: no-op — _run_goal's own loop handles it.
