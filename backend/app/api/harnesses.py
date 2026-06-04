"""
backend/app/api/harnesses — FastAPI router for the harness data layer.

Exposes five CRUD endpoints under /api/spaces/{space_id}/harnesses plus four
run-management endpoints:
  POST   /api/spaces/{space_id}/harnesses/{name}/run      — manual trigger
  GET    /api/spaces/{space_id}/harnesses/{name}/runs     — run history list
  DELETE /api/spaces/{space_id}/harnesses/{name}          — blocks if runs active
  POST   /api/spaces/{space_id}/harnesses/{name}/webhook  — event trigger via HTTP

Concurrency contract (R13 — last-writer-wins):
  This router does NOT implement optimistic locking.  All mutations are
  serialised by the HarnessStore's internal asyncio.Lock but concurrent
  requests that each hold a Harness reference across an await boundary may
  observe a stale model.  Callers MUST re-fetch from HarnessStore.get after
  every await boundary; do not pass Harness models across async hops by
  reference.  A future executor phase will add optimistic-locking; this is
  explicitly deferred per the analysis report.

Security note — plaintext Bearer tokens (R7 trade-off)
---------------------------------------------------------
Webhook auth_tokens are stored in plaintext inside harness YAML files.  Any
principal with read access to the space's .cronos/harnesses/ directory can
extract the token and replay webhook calls.  We accept this trade-off for the
initial iteration because:
  1. Cronos spaces are personal, single-user, and access-controlled via Caddy
     HTTP Basic Auth at the edge.
  2. Harness YAML files are treated as confidential operator configuration;
     they are not exposed through the public API.
  3. Constant-time comparison (secrets.compare_digest) prevents timing attacks
     even with plaintext storage.
A secrets-API migration is flagged as a follow-up goal (see Open questions in
the design report and impl-report).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
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
from ..harnesses.run_trigger import enqueue_harness_run
from ..harnesses.triggers import EventBusEvent, fan_out_to_harnesses
from ..harnesses.validator import _apply_trigger_defaults
from ..storage import TaskStore
from ..worker_pool import WorkerPool

# ---------------------------------------------------------------------------
# Short-token warning guard — emit at most once per process (R7 mitigation).
# ---------------------------------------------------------------------------
_SHORT_TOKEN_WARNED: set[str] = set()  # keyed by (space_id, harness_name)

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

    Verifies the harness exists, then delegates task creation, run-index
    appending, worker registration, and enqueueing to
    ``harnesses.run_trigger.enqueue_harness_run``.

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

    try:
        summary = await enqueue_harness_run(
            task_store,
            harness_store,
            pool,
            space_id,
            space_dir,
            name,
            brief=f"Automated harness run triggered via API for harness '{name}'.",
            triggered_at=now_iso,
        )
    except Exception as exc:
        log.exception("Failed to enqueue harness run for harness %r in space %r", name, space_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create run task: {exc}",
        ) from exc

    return {"run_id": summary.run_id, "harness_id": name, "triggered_at": now_iso}


@router.get("/{name}/runs")
async def list_harness_runs(space_id: str, name: str, request: Request) -> list[dict]:
    """Return run history for a harness, newest first.

    Returns an empty list when no runs exist.
    """
    space_dir = _get_space_dir(request, space_id)

    entries = await run_index.read_index(space_dir, name)
    # read_index returns ascending order; reverse for newest-first.
    return [e.to_dict() for e in reversed(entries)]


# ---------------------------------------------------------------------------
# Webhook trigger endpoint
# ---------------------------------------------------------------------------


@router.post("/{name}/webhook", status_code=status.HTTP_202_ACCEPTED)
async def trigger_webhook(
    space_id: str, name: str, request: Request
) -> dict:
    """Receive an authenticated HTTP webhook and fan out to matching harnesses.

    Authentication
    --------------
    The caller must supply an ``Authorization: Bearer <token>`` header whose
    token matches the ``auth_token`` field of the harness's webhook trigger
    node.  Comparison uses ``secrets.compare_digest()`` to prevent timing
    side-channels.  Returns 401 if the header is absent or the token is wrong.

    Event deduplication
    -------------------
    The event_id is built from the harness's ``webhook_path`` and a SHA-256
    hash of the raw request body::

        event_id = f"webhook:{space_id}:{webhook_path}:{sha256(body)[:16]}"

    Identical payloads arriving within the harness's ``debounce_seconds``
    window (default 0.5 s) return HTTP 202 with an empty ``run_ids`` list —
    the event is acknowledged but not re-dispatched.

    Returns
    -------
    HTTP 202 with ``{"run_ids": [...]}`` listing every newly-enqueued run_id.
    An empty list means the event was deduplicated (no run created).

    Error responses
    ---------------
    401: Authorization header missing or Bearer token does not match.
    404: Harness not found, or harness has no webhook trigger node.
    """
    # ------------------------------------------------------------------
    # 1. Extract Bearer token from Authorization header.
    # ------------------------------------------------------------------
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header; expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    supplied_token = auth_header[len("Bearer "):]

    # ------------------------------------------------------------------
    # 2. Look up the harness (404 if not found).
    # ------------------------------------------------------------------
    space_dir = _get_space_dir(request, space_id)
    harness_store = _get_store(request)
    try:
        harness = await harness_store.get(space_dir, name)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Harness {name!r} not found in space {space_id!r}",
        )

    # ------------------------------------------------------------------
    # 3. Find the harness's single webhook trigger node (404 if absent).
    # ------------------------------------------------------------------
    webhook_nodes = [
        node
        for node in harness.nodes
        if node.type.value == "trigger" and node.data.get("kind") == "webhook"
    ]
    if not webhook_nodes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Harness {name!r} has no webhook trigger node",
        )
    trigger_node = webhook_nodes[0]

    # ------------------------------------------------------------------
    # 4. Apply defaults to get the effective trigger config.
    # ------------------------------------------------------------------
    effective_data = _apply_trigger_defaults("webhook", trigger_node.data)

    # ------------------------------------------------------------------
    # 5. Short-token warning — emit once per process for weak tokens (R7).
    # ------------------------------------------------------------------
    auth_token = effective_data.get("auth_token", "")
    warn_key = f"{space_id}:{name}"
    if len(auth_token) < 16 and warn_key not in _SHORT_TOKEN_WARNED:
        _SHORT_TOKEN_WARNED.add(warn_key)
        log.warning(
            "Harness %r in space %r has a webhook auth_token shorter than 16 "
            "characters (%d chars).  Short tokens are weak; consider using a "
            "cryptographically random token of at least 32 characters.",
            name,
            space_id,
            len(auth_token),
        )

    # ------------------------------------------------------------------
    # 6. Compare token using constant-time digest (401 on mismatch).
    # ------------------------------------------------------------------
    if not secrets.compare_digest(supplied_token, auth_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ------------------------------------------------------------------
    # 7. Read raw request body and compute content hash for event_id.
    # ------------------------------------------------------------------
    body_bytes = await request.body()
    body_hash = hashlib.sha256(body_bytes).hexdigest()[:16]

    try:
        import json as _json
        body_json: dict = _json.loads(body_bytes) if body_bytes else {}
    except Exception:
        body_json = {"raw": body_bytes.decode("utf-8", errors="replace")}

    webhook_path = effective_data.get("webhook_path", name)
    event_id = f"webhook:{space_id}:{webhook_path}:{body_hash}"
    now_iso = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ------------------------------------------------------------------
    # 8. Build EventBusEvent and fan out to matching harnesses.
    # ------------------------------------------------------------------
    event = EventBusEvent(
        event_id=event_id,
        kind="webhook",
        space_id=space_id,
        payload=body_json,
        timestamp=now_iso,
    )

    task_store = _get_task_store(request)
    worker_pool = _get_worker_pool(request)

    run_ids = await fan_out_to_harnesses(
        event,
        harness_store=harness_store,
        task_store=task_store,
        worker_pool=worker_pool,
        space_dir=space_dir,
    )

    return {"run_ids": run_ids}
