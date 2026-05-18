from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..stats import GlobalStats, TaskStats, aggregate_global
from ..stats_store import StatsStore
from ..storage import TaskStore

router = APIRouter()


def _get_stores(request: Request) -> tuple[TaskStore, StatsStore]:
    store: TaskStore = request.app.state.store
    stats_store: StatsStore | None = getattr(request.app.state, "stats_store", None)
    if stats_store is None:
        raise HTTPException(status_code=503, detail="Stats store not available")
    return store, stats_store


@router.get("/api/tasks/{task_id}/stats", response_model=TaskStats)
async def get_task_stats(task_id: str, request: Request) -> TaskStats:
    store, stats_store = _get_stores(request)
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    stats = await stats_store.load(task.space_id, task_id)
    if stats is None:
        # Return empty stats object — task exists but has no runs yet
        return TaskStats(task_id=task_id, space_id=task.space_id, title=task.title)
    return stats


@router.get("/api/spaces/{space_id}/stats", response_model=list[TaskStats])
async def get_space_stats(space_id: str, request: Request) -> list[TaskStats]:
    _, stats_store = _get_stores(request)
    return await stats_store.list_space(space_id)


@router.get("/api/stats", response_model=GlobalStats)
async def get_global_stats(request: Request) -> GlobalStats:
    store, stats_store = _get_stores(request)
    space_store = request.app.state.space_store
    space_ids = [s.id for s in space_store.list_all()]
    all_stats = await stats_store.list_all(space_ids)
    return aggregate_global(all_stats)
