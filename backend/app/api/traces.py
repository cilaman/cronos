from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..storage import TaskStore
from ..trace_parser import RunTrace
from ..trace_store import TraceStore

router = APIRouter()


def _get_stores(request: Request) -> tuple[TaskStore, TraceStore]:
    store: TaskStore = request.app.state.store
    trace_store: TraceStore | None = getattr(request.app.state, "trace_store", None)
    if trace_store is None:
        raise HTTPException(status_code=503, detail="Trace store not available")
    return store, trace_store


@router.get("/api/tasks/{task_id}/traces", response_model=list[RunTrace])
async def list_task_traces(task_id: str, request: Request) -> list[RunTrace]:
    store, trace_store = _get_stores(request)
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    runs = await trace_store.list_runs(task.space_id, task_id)
    return list(reversed(runs))


@router.get("/api/tasks/{task_id}/traces/latest", response_model=RunTrace)
async def get_latest_trace(task_id: str, request: Request) -> RunTrace:
    store, trace_store = _get_stores(request)
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    trace = await trace_store.load_latest(task.space_id, task_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="No traces found for this task")
    return trace


@router.get("/api/tasks/{task_id}/traces/{run_index}", response_model=RunTrace)
async def get_task_trace(task_id: str, run_index: int, request: Request) -> RunTrace:
    store, trace_store = _get_stores(request)
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    trace = await trace_store.load_run(task.space_id, task_id, run_index)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace run {run_index} not found")
    return trace
