"""GET /api/metrics — lightweight observability endpoint.

Returns non-PII numeric aggregates about worker-pool state: queue depth,
active tasks, and auto-resume totals. Intentionally unauth'd (parity with
/api/health); exposes only aggregate counters, no task IDs or titles.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/api/metrics")
async def metrics(request: Request) -> dict[str, object]:
    """Return queue depth, active task count, and auto-resume totals.

    All values are non-negative integers. Fields:
    - queue_depth: total tasks waiting to be processed across all spaces.
    - active_tasks: count of tasks currently executing (at most one per space).
    - auto_resume_total: sum of auto-resume counts across all tasks.
    """
    from ..worker_pool import WorkerPool

    pool: WorkerPool | None = getattr(request.app.state, "worker_pool", None)

    queue_depth = 0
    active_tasks = 0
    auto_resume_total = 0

    if pool is not None:
        for worker in pool.all_workers():
            queue_depth += worker._queue.qsize()
            if worker._current_id is not None:
                active_tasks += 1
            auto_resume_total += sum(worker._auto_resume_counts.values())

    return {
        "queue_depth": queue_depth,
        "active_tasks": active_tasks,
        "auto_resume_total": auto_resume_total,
    }
