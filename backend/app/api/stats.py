from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from ..stats import GlobalStats, TaskStats, aggregate_global, filter_task_stats
from ..stats_store import StatsStore
from ..storage import TaskStore

router = APIRouter()

_FromDt = Annotated[datetime | None, Query(description="Inclusive lower bound on run started_at (ISO 8601)")]
_ToDt = Annotated[datetime | None, Query(description="Inclusive upper bound on run started_at (ISO 8601)")]


def _get_stores(request: Request) -> tuple[TaskStore, StatsStore]:
    store: TaskStore = request.app.state.store
    stats_store: StatsStore | None = getattr(request.app.state, "stats_store", None)
    if stats_store is None:
        raise HTTPException(status_code=503, detail="Stats store not available")
    return store, stats_store


def _validate_range(from_dt: datetime | None, to_dt: datetime | None) -> None:
    if from_dt is not None and to_dt is not None and from_dt > to_dt:
        raise HTTPException(status_code=422, detail="from_dt must be less than or equal to to_dt")


@router.get("/api/tasks/{task_id}/stats", response_model=TaskStats)
async def get_task_stats(
    task_id: str,
    request: Request,
    from_dt: _FromDt = None,
    to_dt: _ToDt = None,
) -> TaskStats:
    _validate_range(from_dt, to_dt)
    store, stats_store = _get_stores(request)
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    stats = await stats_store.load(task.space_id, task_id)
    if stats is None:
        return TaskStats(task_id=task_id, space_id=task.space_id, title=task.title)
    filtered = filter_task_stats(stats, from_dt, to_dt)
    return filtered if filtered is not None else TaskStats(task_id=task_id, space_id=task.space_id, title=task.title)


@router.get("/api/spaces/{space_id}/stats", response_model=list[TaskStats])
async def get_space_stats(
    space_id: str,
    request: Request,
    from_dt: _FromDt = None,
    to_dt: _ToDt = None,
) -> list[TaskStats]:
    _validate_range(from_dt, to_dt)
    _, stats_store = _get_stores(request)
    all_stats = await stats_store.list_space(space_id)
    if from_dt is None and to_dt is None:
        return all_stats
    return [f for ts in all_stats if (f := filter_task_stats(ts, from_dt, to_dt)) is not None]


@router.get("/api/stats", response_model=GlobalStats)
async def get_global_stats(
    request: Request,
    from_dt: _FromDt = None,
    to_dt: _ToDt = None,
) -> GlobalStats:
    _validate_range(from_dt, to_dt)
    store, stats_store = _get_stores(request)
    space_store = request.app.state.space_store
    space_ids = [s.id for s in space_store.list_all()]
    all_stats = await stats_store.list_all(space_ids)
    if from_dt is not None or to_dt is not None:
        all_stats = [f for ts in all_stats if (f := filter_task_stats(ts, from_dt, to_dt)) is not None]
    return aggregate_global(all_stats)
