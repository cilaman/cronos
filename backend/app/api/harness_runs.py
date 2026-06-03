"""
backend/app/api/harness_runs — FastAPI router for cross-space harness run operations.

Mounted at /api/harness-runs (no space_id prefix).  Uses the worker's reverse-lookup
cache (run_id → space_id) to resolve the space in O(1) without filesystem scans.

Endpoints:
  GET  /api/harness-runs/{run_id}         — get run state JSON
  POST /api/harness-runs/{run_id}/cancel  — cancel a running run
  GET  /api/harness-runs/{run_id}/stream  — SSE stream of harness events
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from ..harnesses import run_index as _run_index
from ..harnesses.run_state import RunState, load, save_atomic
from ..worker import Worker, _DONE_SENTINEL, _RUN_BUFFER_CAP
from ..worker_pool import WorkerPool

log = logging.getLogger(__name__)

harness_runs_router = APIRouter(prefix="/api/harness-runs", tags=["harness-runs"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_pool(request: Request) -> WorkerPool:
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
    return space_store.spaces_dir / space_id


def _run_state_path(space_dir: Path, run_id: str) -> Path:
    """Return the canonical path for a run state JSON file."""
    return space_dir / ".cronos" / "harness-runs" / f"{run_id}.json"


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@harness_runs_router.get("/{run_id}")
async def get_harness_run(run_id: str, request: Request) -> dict:
    """Return the RunState for *run_id* as a plain dict.

    Uses the worker's reverse-lookup cache to find the space in O(1).
    Returns 404 if the run is unknown or the state file is absent.
    """
    pool = _get_pool(request)

    # Find which space owns this run via the reverse-lookup cache.
    space_id = None
    for worker in pool.all_workers():
        sid = worker.lookup_space_id(run_id)
        if sid is not None:
            space_id = sid
            break

    if space_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id!r} not found",
        )

    space_dir = _get_space_dir(request, space_id)
    path = _run_state_path(space_dir, run_id)

    run_state = load(path)
    if run_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run state file for {run_id!r} not found",
        )

    return run_state.to_dict()


@harness_runs_router.post("/{run_id}/cancel")
async def cancel_harness_run(run_id: str, request: Request) -> dict:
    """Cancel a running harness run.

    Steps (in order to avoid race conditions):
    1. Resolve space via reverse-lookup cache.
    2. Load RunState from disk.
    3. If already terminal (done/failed/cancelled), return 409.
    4. Set status = 'cancelled' and save atomically.
    5. Call worker.stop_current(run_id) to signal the active agent.
    6. Bulk-mark pending/in_progress nodes as failed with reason='cancelled'.
    7. Save again atomically with the updated node states.
    8. Update the run index entry.
    9. Return 200 with run_id and status=cancelled.
    """
    pool = _get_pool(request)

    # Find which space owns this run via the reverse-lookup cache.
    space_id = None
    target_worker = None
    for worker in pool.all_workers():
        sid = worker.lookup_space_id(run_id)
        if sid is not None:
            space_id = sid
            target_worker = worker
            break

    if space_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id!r} not found",
        )

    space_dir = _get_space_dir(request, space_id)
    path = _run_state_path(space_dir, run_id)

    run_state = load(path)
    if run_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run state file for {run_id!r} not found",
        )

    # Reject if already in a terminal state.
    if run_state.status in ("done", "failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run {run_id!r} is already {run_state.status!r}",
        )

    harness_id = run_state.harness_id
    now_iso = _utcnow_iso()

    # Step 4: Mark run as cancelled and persist immediately (before stopping
    # the worker) to prevent the race where the executor reads status=running
    # after the worker has been stopped.
    run_state.status = "cancelled"
    save_atomic(path, run_state)

    # Step 5: Signal the worker to stop the currently running agent for this run.
    if target_worker is not None:
        target_worker.stop_current(run_id)

    # Step 6: Bulk-mark pending/in_progress nodes as failed with reason=cancelled.
    for node_id, node_state in run_state.nodes_executed.items():
        if node_state.status in ("pending", "in_progress"):
            node_state.status = "failed"
            node_state.reason = "cancelled"
            node_state.ended_at = now_iso

    # Step 7: Save updated node states atomically.
    save_atomic(path, run_state)

    # Step 8: Update the run index.
    await _run_index.update_run_status(
        space_dir, harness_id, run_id, "cancelled", finished_at=now_iso
    )

    return {"run_id": run_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------


async def _sse_harness_run_events(run_id: str, worker: Worker) -> AsyncIterator[str]:
    """Yield SSE-formatted lines for *run_id*'s harness event stream.

    Implements late-joiner replay: buffered events accumulated since the run
    started (up to the 2000-event cap) are replayed first, then live events
    follow.  The SSE ``event:`` field is set to the event's ``type`` value so
    that harness events (``node_transition``, ``edge_chosen``, ``run_status``)
    are discriminated from legacy task events (``run_start``, ``run_end``) by
    any EventSource listener that uses ``addEventListener('node_transition', …)``.

    Buffer cap: Worker._run_buffer holds at most 2000 events per task_id
    (``_RUN_BUFFER_CAP = 2000``).  When the buffer is full at subscribe time
    a synthetic ``buffer_truncated`` event is emitted first so the consumer
    can display a "history truncated" badge.
    """
    replay, q = worker.subscribe(run_id)
    try:
        # Keep-alive comment — defeats proxy buffering / forces EventSource.onopen.
        yield ": ok\n\n"

        # Emit buffer_truncated synthetic event if the replay buffer was at
        # capacity when the subscriber joined.  This signals that early events
        # were dropped by the FIFO overflow logic in Worker._publish.
        if len(replay) >= _RUN_BUFFER_CAP:
            truncated_event = {
                "type": "buffer_truncated",
                "message": "history truncated due to buffer capacity",
            }
            yield f"event: buffer_truncated\ndata: {json.dumps(truncated_event)}\n\n"

        # Replay buffered events with their discriminated event: field.
        for event in replay:
            event_type = event.get("type", "message")
            yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"

        # Stream live events until the run ends (DONE_SENTINEL received).
        while True:
            event = await q.get()
            if event is _DONE_SENTINEL:
                yield "event: end\ndata: {}\n\n"
                return
            event_type = event.get("type", "message")
            yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"
    finally:
        worker.unsubscribe(run_id, q)


@harness_runs_router.get("/{run_id}/stream")
async def stream_harness_run(run_id: str, request: Request) -> StreamingResponse:
    """Stream harness run events as Server-Sent Events.

    Uses the Worker's existing SSE infrastructure (subscribe / _run_buffer)
    keyed by *run_id* (which equals the goal task id per design).

    Late-joiner replay: buffered events from the current or last run are
    replayed immediately upon connection, followed by live events.

    Buffer overflow: if the replay buffer was at capacity (2000-event cap)
    when the client connected, a synthetic ``buffer_truncated`` event is
    emitted before the buffered history so the client can display a
    "history truncated" notice.

    SSE event field namespacing (discriminated envelope):
      - ``event: node_transition``  — harness node state change
      - ``event: edge_chosen``      — BFS edge selection
      - ``event: run_status``       — overall run status update
      - ``event: buffer_truncated`` — synthetic overflow signal
      - ``event: run_start``        — legacy task lifecycle (pass-through)
      - ``event: run_end``          — legacy task lifecycle (pass-through)

    The 2000-event per-run cap is enforced by Worker._publish; this endpoint
    does not change that limit.

    Returns 404 if *run_id* is unknown to any worker in the pool.
    """
    pool = _get_pool(request)

    # Resolve run_id → space_id via per-worker reverse-lookup cache.
    space_id = None
    target_worker: Worker | None = None
    for worker in pool.all_workers():
        sid = worker.lookup_space_id(run_id)
        if sid is not None:
            space_id = sid
            target_worker = worker
            break

    if space_id is None or target_worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id!r} not found",
        )

    return StreamingResponse(
        _sse_harness_run_events(run_id, target_worker),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
