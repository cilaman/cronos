"""
backend/app/api/harnesses — FastAPI router for the harness data layer.

Exposes five CRUD endpoints under /api/spaces/{space_id}/harnesses.

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


def _get_space_dir(request: Request, space_id: str) -> str:
    """Resolve space_id to its filesystem path via the SpaceStore."""
    space_store = request.app.state.space_store
    space = space_store.get(space_id)
    if space is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Space {space_id!r} not found",
        )
    # SpaceStore stores spaces at spaces_dir / space_id.
    return str(space_store.spaces_dir / space_id)


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
    try:
        harness = Harness(
            name=body.name,
            description=body.description,
            nodes=body.nodes,
            edges=body.edges,
            variables=body.variables,
            version=body.version,
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
    """Delete a harness by name."""
    space_dir = _get_space_dir(request, space_id)
    store = _get_store(request)
    try:
        await store.delete(space_dir, name)
    except HarnessNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
