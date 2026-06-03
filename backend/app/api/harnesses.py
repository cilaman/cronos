"""
backend/app/api/harnesses — FastAPI router for the harness data layer.

Exposes five CRUD endpoints under /api/spaces/{space_id}/harnesses plus three
run-management endpoints:
  POST   /api/spaces/{space_id}/harnesses/{name}/run   — manual trigger
  GET    /api/spaces/{space_id}/harnesses/{name}/runs  — run history list
  DELETE /api/spaces/{space_id}/harnesses/{name}       — blocks if runs active

Concurrency contract (R13 — last-writer-wins):
  This router does NOT implement optimistic locking.  All mutations are
  serialised by the HarnessStore's internal asyncio.Lock but concurrent
  requests that each hold a Harness reference across an await boundary may
  observe a stale model.  Callers MUST re-fetch from HarnessStore.get after
  every await boundary; do not pass Harness models across async hops by
  reference.  A future executor phase will add optimistic-locking; this is
  explicitly deferred per the analysis report.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ValidationError

from ..harnesses import (
    Harness,
    HarnessEdge,
    HarnessGraphError,
    HarnessNameConflict,
    HarnessNode,
    HarnessNotFound,
    HarnessStore,
)
from ..harnesses import run_index
from ..harnesses.run_index import RunSummary
from ..storage import TaskStore, USER_TRANSITIONS
from ..models import TaskState
from ..worker_pool import WorkerPool

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/spaces/{space_id}/harnesses",
    tags=["harnesses"],
)


# ---------------------------------------------------------------------------
# Request body schemas
# ---------------------------------------------------------------------------


class HarnessCreate(BaseModel):
    """Request body for POST /api/spaces/{space_id}/harnesses."""

    name: str
    description: str = ""
    nodes: list[HarnessNode] = []
    edges: list[HarnessEdge] = []
    variables: dict = {}
    version: str = "1.0"


class HarnessUpdate(BaseModel):
    """Request body for PUT /api/spaces/{space_id}/harnesses/{name}."""

    name: str
    description: str = ""
    nodes: list[HarnessNode] = []
    edges: list[HarnessEdge] = []
    variables: dict = {}
    version: str = "1.0"


# ---------------------------------------------------------------------------
# DI helpers
# ---------------------------------------------------------------------------


def _get_store(request: Request) -> HarnessStore:
    return request.app.state.harness_store


def _get_task_store(request: Request) -> TaskStore:
    return request.app.state.store


def _get_worker_pool(request: Request) -> WorkerPool:
    return request.app.state.worker_pool


def _get_space_dir(request: Request, space_id: str) -> Path:
    """Resolve space_id to its filesystem path via the SpaceStore."""
    space_store = request.app.state.space_store
    space = space_store.get(space_id)
    if space is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Space {space_id!r} not found",
        )
    # SpaceStore stores spaces at spaces_dir / space_id.
    return space_store.spaces_dir / space_id


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[Harness])
async def list_harnesses(space_id: str, request: Request) -> list[Harness]:
    """List all harnesses in a space."""
    space_dir = _get_space_dir(request, space_id)
    store = _get_store(request)
    return await store.list(space_dir)


@router.post("", response_model=Harness, status_code=status.HTTP_201_CREATED)
async def create_harness(
    space_id: str, body: HarnessCreate, request: Request
) -> Harness:
    """Create a new harness in a space."""
    space_dir = _get_space_dir(request, space_id)
    store = _get_store(request)
    now = datetime.now(tz=UTC)
    try:
        harness = Harness(
            name=body.name,
            description=body.description,
            nodes=body.nodes,
            edges=body.edges,
            variables=body.variables,
            version=body.version,
            created_at=now,
            updated_at=now,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    try:
        created = await store.create(space_dir, harness)
    except HarnessNameConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except HarnessGraphError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return created


@router.get("/{name}", response_model=Harness)
async def get_harness(space_id: str, name: str, request: Request) -> Harness:
    """Fetch a single harness by name."""
    space_dir = _get_space_dir(request, space_id)
    store = _get_store(request)
    try:
        return await store.get(space_dir, name)
    except HarnessNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.put("/{name}", response_model=Harness)
async def update_harness(
    space_id: str, name: str, body: HarnessUpdate, request: Request
) -> Harness:
    """Replace the harness identified by *name* with the request body."""
    space_dir = _get_space_dir(request, space_id)
    store = _get_store(request)
    now = datetime.now(tz=UTC)
    # Fetch the existing harness so we can preserve its original created_at.
    try:
        existing = await store.get(space_dir, name)
    except HarnessNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    try:
        harness = Harness(
            name=body.name,
            description=body.description,
            nodes=body.nodes,
            edges=body.edges,
            variables=body.variables,
            version=body.version,
            created_at=existing.created_at,
            updated_at=now,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    try:
        updated = await store.update(space_dir, name, harness)
    except HarnessNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except HarnessGraphError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return updated


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_harness(space_id: str, name: str, request: Request) -> None:
    """Delete a harness by name.

    Returns 409 if any run for this harness is currently in 'running' status.
    """
    space_dir = _get_space_dir(request, space_id)
    store = _get_store(request)

    # Guard: reject deletion if any run is still active.
    existing_runs = await run_index.read_index(space_dir, name)
    active_run_ids = [r.run_id for r in existing_runs if r.status == "running"]
    if active_run_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "harness has active runs", "active_run_ids": active_run_ids},
        )

    try:
        await store.delete(space_dir, name)
    except HarnessNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Run management endpoints
# ---------------------------------------------------------------------------


@router.post("/{name}/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_harness_run(
    space_id: str, name: str, request: Request
) -> dict:
    """Manually trigger a harness run.

    Creates a task in the space's task store, appends a RunSummary to the
    per-harness run index, registers the run_id in the worker's reverse-lookup
    cache, transitions the task to ACTIVE, and enqueues it on the worker.

    Returns 202 with run_id, harness_id, and triggered_at.
    """
    space_dir = _get_space_dir(request, space_id)
    harness_store = _get_store(request)
    task_store = _get_task_store(request)
    pool = _get_worker_pool(request)

    # Verify the harness exists before creating a run task.
    try:
        await harness_store.get(space_dir, name)
    except HarnessNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    now_iso = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Create the harness run task. run_id == task.id per design constraint.
    try:
        task = await task_store.create(
            space_id=space_id,
            title=f"Harness run: {name}",
            brief=f"Automated harness run triggered via API for harness '{name}'.",
            type="task",
        )
    except Exception as exc:
        log.exception("Failed to create harness run task for harness %r in space %r", name, space_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create run task: {exc}",
        ) from exc

    run_id = task.id

    # Append to the run index.
    summary = RunSummary(
        run_id=run_id,
        harness_id=name,
        status="running",
        triggered_at=now_iso,
    )
    await run_index.append_run(space_dir, name, summary)

    # Register in the worker reverse-lookup cache (O(1) for GET /harness-runs/{run_id}).
    worker = pool.get(space_id)
    if worker is not None:
        worker.register_run(run_id, space_id)

    # Transition task to ACTIVE and enqueue on the worker.
    try:
        await task_store.transition(run_id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    except Exception:
        log.warning("Could not transition harness run task %s to ACTIVE", run_id)

    if worker is not None:
        await worker.enqueue(run_id)

    return {"run_id": run_id, "harness_id": name, "triggered_at": now_iso}


@router.get("/{name}/runs")
async def list_harness_runs(space_id: str, name: str, request: Request) -> list[dict]:
    """Return run history for a harness, newest first.

    Returns an empty list when no runs exist.
    """
    space_dir = _get_space_dir(request, space_id)

    entries = await run_index.read_index(space_dir, name)
    # read_index returns ascending order; reverse for newest-first.
    return [e.to_dict() for e in reversed(entries)]
