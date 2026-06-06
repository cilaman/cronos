"""Features/fixes API router.

Auth-parity: this router is registered in main.py with
``app.include_router(features_router, dependencies=_auth)`` — identical to the
tasks_router registration — so every endpoint inherits the same require_auth
dependency and returns 401 for unauthenticated requests.

Mirror funnel: all ``mirror_feature_to_github`` calls go through
``_fire_mirror()`` so the call count is concentrated in one code path
(required by R13).
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ..feature_hooks import enqueue_feature_decomposition, mirror_feature_to_github
from ..feature_state import FEATURE_USER_TRANSITIONS
from ..models import (
    CreateFeatureBody,
    FeatureBoard,
    FeatureRead,
    FeatureState,
    PatchFeatureBody,
    PatchFeatureStateBody,
    PatchRealizeBody,
    Space,
    Task,
    TaskSummary,
)
from ..storage import CycleError, StorageError, TaskNotFound, UnknownSpace

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/features", tags=["features"])


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _get_store(request: Request):
    return request.app.state.store


def _get_space_store(request: Request):
    return request.app.state.space_store


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fire_mirror(
    task: Task,
    space: Space,
    reason: str,
) -> None:
    """Single funnel for all mirror_feature_to_github calls (R13).

    Concentrating the call here ensures exactly one mirror fire per
    mutating endpoint and makes the call_count easy to assert in tests.

    Fire-and-forget: schedules mirror_feature_to_github as a background
    asyncio task so the response is not blocked on the gh subprocess
    (design risk #6 mitigation).  Any exception raised by the mirror
    coroutine is caught by the done-callback and logged at ERROR level.
    """
    def _log_mirror_error(fut: asyncio.Future) -> None:
        exc = fut.exception()
        if exc is not None:
            log.error(
                "mirror_feature_to_github background task failed for task=%s reason=%s: %s",
                task.id,
                reason,
                exc,
                exc_info=exc,
            )

    coro = mirror_feature_to_github(task, space=space, reason=reason)  # type: ignore[arg-type]
    bg_task = asyncio.create_task(coro)
    bg_task.add_done_callback(_log_mirror_error)


def _build_feature_read(task: Task, realizing_items: list[TaskSummary] | None = None) -> FeatureRead:
    """Build a FeatureRead response from a Task and optional realizing items."""
    return FeatureRead(
        **{k: v for k, v in task.model_dump().items() if k in FeatureRead.model_fields},
        realizing_items=realizing_items or [],
    )


# ---------------------------------------------------------------------------
# Route stubs — all return 501 until the corresponding iteration fills them in
# ---------------------------------------------------------------------------

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501,
    content={"detail": "Not implemented yet"},
)


@router.post("", response_model=FeatureRead, status_code=status.HTTP_201_CREATED)
async def create_feature(body: CreateFeatureBody, request: Request) -> FeatureRead:
    """POST /api/features — create a new feature or fix (I5).

    Returns 400 when the space has no git_repo_url (R11).
    Allocates a feature_key (FEAT-NNN / FIX-NNN), writes the MD file via
    store.create(), then fires one mirror call (R13).
    """
    store = _get_store(request)
    space_store = _get_space_store(request)

    space = space_store.get(body.space_id)
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {body.space_id} not found")

    if space.git_repo_url is None:
        raise HTTPException(
            status_code=400,
            detail="Space is not linked to a git repository; cannot create feature/fix",
        )

    try:
        task = await store.create(
            space_id=body.space_id,
            title=body.title,
            brief=body.brief,
            priority=body.priority,
            type=body.type,
        )
    except UnknownSpace:
        raise HTTPException(status_code=404, detail=f"Space {body.space_id} not found") from None
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    _fire_mirror(task, space, "create")

    return _build_feature_read(task)


@router.get("", response_model=FeatureBoard, status_code=200)
async def list_features(
    request: Request,
    space_id: str = "",
) -> FeatureBoard:
    """GET /api/features?space_id= — return FeatureBoard (I6).

    Returns a FeatureBoard with five lanes (backlog, processing, planned,
    waiting, done) populated from store.feature_board(space_id).
    Items with feature_state=None are omitted by the store query.
    No mirror call on this read path (R13: call_count == 0).
    """
    store = _get_store(request)
    space_store = _get_space_store(request)

    if not space_id:
        raise HTTPException(status_code=422, detail="space_id query parameter is required")

    if not space_store.exists(space_id):
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

    buckets: dict[FeatureState, list[TaskSummary]] = await store.feature_board(space_id)

    return FeatureBoard(
        backlog=buckets.get(FeatureState.BACKLOG, []),
        processing=buckets.get(FeatureState.PROCESSING, []),
        planned=buckets.get(FeatureState.PLANNED, []),
        waiting=buckets.get(FeatureState.WAITING, []),
        done=buckets.get(FeatureState.DONE, []),
    )


@router.get("/{feature_id}", response_model=FeatureRead, status_code=200)
async def get_feature(feature_id: str, request: Request) -> FeatureRead:
    """GET /api/features/{id} — return FeatureRead with realizing_items (I7).

    Returns 404 when the feature_id is not found, or when the task exists but
    has type not in ("feature", "fix").
    Populates realizing_items from store.realizing_items(feature_id).
    No mirror call on this read path (R13: call_count == 0).
    """
    store = _get_store(request)

    task = store.get(feature_id)
    if task is None or task.type not in ("feature", "fix"):
        raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

    items: list[TaskSummary] = await store.realizing_items(feature_id)
    return _build_feature_read(task, items)


@router.patch("/{feature_id}/feature-state", response_model=FeatureRead, status_code=200)
async def patch_feature_state(
    feature_id: str,
    body: PatchFeatureStateBody,
    request: Request,
) -> FeatureRead:
    """PATCH /api/features/{id}/feature-state — transition feature_state (I8).

    Enforces allowed transitions via FEATURE_USER_TRANSITIONS imported from
    feature_state.py (never redeclared locally — see R-risk: transitions divergence).
    Returns 409 on an illegal transition (StorageError / InvalidTransition).
    Returns 404 when feature_id is not found or has wrong type.
    Fires one mirror call with reason='state_change' on success (R13).
    feature_key is unchanged across the transition (R12).
    """
    store = _get_store(request)
    space_store = _get_space_store(request)

    # Verify existence and correct type before attempting transition
    task = store.get(feature_id)
    if task is None or task.type not in ("feature", "fix"):
        raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

    # Resolve space for mirror call
    space = space_store.get(task.space_id)
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {task.space_id} not found")

    try:
        updated_task = await store.transition_feature(
            feature_id,
            body.feature_state,
            allowed=FEATURE_USER_TRANSITIONS,
        )
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found") from None
    except StorageError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None

    _fire_mirror(updated_task, space, "state_change")
    return _build_feature_read(updated_task)


@router.patch("/{feature_id}", response_model=FeatureRead, status_code=200)
async def patch_feature(
    feature_id: str,
    body: PatchFeatureBody,
    request: Request,
) -> FeatureRead:
    """PATCH /api/features/{id} — edit title/brief (I9).

    Updates title and/or brief; updated_at is bumped automatically by
    store.update(). feature_key is unchanged (R12).
    Returns 404 when feature_id is not found or has wrong type.
    Fires one mirror call with reason='edit' on success (R13).
    """
    store = _get_store(request)
    space_store = _get_space_store(request)

    # Verify existence and correct type before attempting update
    task = store.get(feature_id)
    if task is None or task.type not in ("feature", "fix"):
        raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

    # Resolve space for mirror call
    space = space_store.get(task.space_id)
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {task.space_id} not found")

    try:
        updated_task = await store.update(
            feature_id,
            title=body.title,
            brief=body.brief,
        )
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found") from None
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    _fire_mirror(updated_task, space, "edit")
    return _build_feature_read(updated_task)


@router.patch("/{feature_id}/realize", response_model=FeatureRead, status_code=200)
async def patch_realize(
    feature_id: str,
    body: PatchRealizeBody,
    request: Request,
) -> FeatureRead:
    """PATCH /api/features/{id}/realize — link/unlink a task to this feature (I10).

    Calls store.set_realizes(body.item_id, body.feature_id or None).

    Body fields:
    - item_id: the task/item being linked to the feature (required)
    - feature_id: the feature to link to; None or omitted = unlink

    Error mapping:
    - 404 if item_id is not found (TaskNotFound)
    - 400 if validation fails — self-reference, cross-space, wrong target type
      (CycleError / StorageError from validate_realizes)

    No mirror call on this endpoint (R13: call_count == 0).
    After a successful link, GET /api/features/{feature_id} will reflect the
    new item in realizing_items.
    """
    store = _get_store(request)

    try:
        await store.set_realizes(body.item_id, body.feature_id)
    except TaskNotFound:
        raise HTTPException(
            status_code=404,
            detail=f"Item {body.item_id} not found",
        ) from None
    except CycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    # Return the updated feature view so the caller can see the new
    # realizing_items without a follow-up GET.
    task = store.get(feature_id)
    if task is None or task.type not in ("feature", "fix"):
        raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

    items: list[TaskSummary] = await store.realizing_items(feature_id)
    return _build_feature_read(task, items)


@router.post("/{feature_id}/process", response_model=FeatureRead, status_code=200)
async def process_feature(feature_id: str, request: Request) -> FeatureRead:
    """POST /api/features/{id}/process — transition to PROCESSING + S4 enqueue (I11).

    Calls store.transition_feature(feature_id, FeatureState.PROCESSING,
    allowed=FEATURE_USER_TRANSITIONS), then awaits enqueue_feature_decomposition(task).
    Returns 409 when the feature is already PROCESSING (PROCESSING→PROCESSING is not
    in FEATURE_USER_TRANSITIONS) or on any other illegal transition.
    Returns 404 on missing IDs or wrong task type.
    Fires exactly one mirror call via _fire_mirror with reason='state_change' (R13).
    """
    store = _get_store(request)
    space_store = _get_space_store(request)

    # Verify existence and correct type before attempting transition
    task = store.get(feature_id)
    if task is None or task.type not in ("feature", "fix"):
        raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

    # Resolve space for mirror call
    space = space_store.get(task.space_id)
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {task.space_id} not found")

    try:
        updated_task = await store.transition_feature(
            feature_id,
            FeatureState.PROCESSING,
            allowed=FEATURE_USER_TRANSITIONS,
        )
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found") from None
    except StorageError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None

    _fire_mirror(updated_task, space, "state_change")
    await enqueue_feature_decomposition(updated_task)

    return _build_feature_read(updated_task)


@router.delete("/{feature_id}", status_code=501)
async def delete_feature(feature_id: str, request: Request):
    """DELETE /api/features/{id} — soft-delete / archive feature (future iteration)."""
    return _NOT_IMPLEMENTED
