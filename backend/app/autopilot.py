from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .models import Task, TaskState
from .storage import TaskStore, USER_TRANSITIONS, unmet_deps

if TYPE_CHECKING:
    from .models import Space
    from .worker import Worker

log = logging.getLogger("cronos.autopilot")


def eligible_backlog(space_id: str, store: TaskStore) -> list[Task]:
    """Return BACKLOG tasks in space_id whose all depends_on are DONE or ARCHIVED.

    Excludes type=goal tasks.
    """
    all_tasks = store.all()
    by_id = {t.id: t for t in all_tasks}
    return [
        t for t in all_tasks
        if t.space_id == space_id
        and t.state == TaskState.BACKLOG
        and t.type != "goal"
        and not unmet_deps(t, by_id)
    ]


def rank(tasks: list[Task]) -> list[Task]:
    """Sort by priority ASC, manual_order ASC, created_at ASC."""
    return sorted(tasks, key=lambda t: (t.priority, t.manual_order, t.created_at))


async def pickup_next(space: Space | None, store: TaskStore) -> Task | None:
    """Return the first eligible ranked backlog task, or None if autopilot != enabled."""
    if space is None or space.autopilot != "enabled":
        return None
    eligible = eligible_backlog(space.id, store)
    ranked = rank(eligible)
    return ranked[0] if ranked else None


async def start_picked(task: Task, store: TaskStore, worker: Worker) -> None:
    """Transition task to ACTIVE and enqueue it in the worker."""
    await store.transition(task.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    log.info("autopilot.picked task=%s space=%s", task.id, task.space_id)
    await worker.enqueue(task.id)
