"""
Tests for the SSE endpoint in backend/app/api/harness_runs.py

Endpoint under test:
  GET  /api/harness-runs/{run_id}/stream  — Server-Sent Events stream

Tests:
  1. test_stream_unknown_run_id_returns_404
  2. test_stream_replays_buffered_events
  3. test_stream_emits_buffer_truncated_when_overflow
  4. test_stream_event_names_are_correct
  5. test_legacy_task_events_pass_through_unchanged
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI

from app.api.harness_runs import harness_runs_router
from app.auth import require_auth
from fastapi import Depends
from app.worker import _DONE_SENTINEL, _RUN_BUFFER_CAP

# ---------------------------------------------------------------------------
# Helpers / shared constants
# ---------------------------------------------------------------------------

RUN_ID = "sse-test-run-001"
SPACE_ID = "sse-test-space"

_auth = [Depends(require_auth)]


def _make_app(worker_pool: object) -> FastAPI:
    """Minimal FastAPI test app with only the harness_runs router."""
    app = FastAPI()
    app.include_router(harness_runs_router, dependencies=_auth)
    app.state.worker_pool = worker_pool
    # space_store is not needed for stream endpoint (no space resolution required
    # beyond the reverse-lookup cache on the worker)
    app.state.space_store = MagicMock()
    return app


def _make_worker_mock(
    run_id: str,
    space_id: str,
    buffered_events: list[dict],
    *,
    overflow: bool = False,
) -> MagicMock:
    """Build a Worker mock that replays *buffered_events* then emits stream_end.

    The mock implements subscribe() to return (replay_list, asyncio.Queue)
    and unsubscribe() as a no-op.  A stream_end sentinel is pre-loaded into
    the live queue so the SSE generator terminates immediately after replay.

    Parameters
    ----------
    run_id:
        The run ID that this mock recognises.
    space_id:
        The space ID returned by lookup_space_id().
    buffered_events:
        Events to return as the replay buffer.
    overflow:
        If True, the replay list length is padded to _RUN_BUFFER_CAP so the
        SSE generator emits a ``buffer_truncated`` event.
    """
    # Build the replay list — optionally pad to trigger overflow detection.
    if overflow:
        # Fill to capacity: the endpoint checks len(replay) >= _RUN_BUFFER_CAP.
        padding = _RUN_BUFFER_CAP - len(buffered_events)
        pad_events = [{"type": "node_transition", "node_id": f"pad-{i}"} for i in range(padding)]
        replay = pad_events + buffered_events
    else:
        replay = list(buffered_events)

    # Live queue: only the sentinel (stream ends immediately after replay).
    live_q: asyncio.Queue[dict] = asyncio.Queue()
    live_q.put_nowait(_DONE_SENTINEL)

    worker = MagicMock()
    worker.lookup_space_id = MagicMock(
        side_effect=lambda rid: space_id if rid == run_id else None
    )
    worker.subscribe = MagicMock(return_value=(replay, live_q))
    worker.unsubscribe = MagicMock()
    return worker


def _make_pool(workers: list[MagicMock]) -> MagicMock:
    pool = MagicMock()
    pool.all_workers = MagicMock(return_value=workers)
    return pool


def _make_pool_no_run() -> MagicMock:
    """Pool where no worker recognises any run_id."""
    worker = MagicMock()
    worker.lookup_space_id = MagicMock(return_value=None)
    pool = MagicMock()
    pool.all_workers = MagicMock(return_value=[worker])
    return pool


# ---------------------------------------------------------------------------
# 1. Unknown run_id → 404
# ---------------------------------------------------------------------------


async def test_stream_unknown_run_id_returns_404():
    """GET /stream on an unknown run_id must return 404."""
    app = _make_app(_make_pool_no_run())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/harness-runs/no-such-run/stream")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. Buffered events are replayed
# ---------------------------------------------------------------------------


async def test_stream_replays_buffered_events():
    """Mock worker with buffered node_transition + edge_chosen events; both appear in the SSE body."""
    events = [
        {"type": "node_transition", "node_id": "n1", "status": "in_progress"},
        {"type": "edge_chosen", "from": "n1", "to": "n2"},
    ]
    worker = _make_worker_mock(RUN_ID, SPACE_ID, events)
    app = _make_app(_make_pool([worker]))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/harness-runs/{RUN_ID}/stream")

    assert resp.status_code == 200
    body = resp.text

    # Both events should appear in the SSE response body.
    assert "node_transition" in body
    assert "edge_chosen" in body
    assert "n1" in body
    assert "n2" in body


# ---------------------------------------------------------------------------
# 3. buffer_truncated synthetic event on overflow
# ---------------------------------------------------------------------------


async def test_stream_emits_buffer_truncated_when_overflow():
    """When the replay buffer is at capacity, a buffer_truncated event is emitted first."""
    # One real event — the mock will pad to _RUN_BUFFER_CAP.
    events = [{"type": "run_status", "status": "running"}]
    worker = _make_worker_mock(RUN_ID, SPACE_ID, events, overflow=True)
    app = _make_app(_make_pool([worker]))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/harness-runs/{RUN_ID}/stream")

    assert resp.status_code == 200
    body = resp.text

    # buffer_truncated event must appear.
    assert "buffer_truncated" in body
    assert "history truncated due to buffer capacity" in body

    # The real event must still appear after the truncation notice.
    assert "run_status" in body

    # buffer_truncated must come before run_status in the stream.
    assert body.index("buffer_truncated") < body.index("run_status")


# ---------------------------------------------------------------------------
# 4. SSE event: field names are correct
# ---------------------------------------------------------------------------


async def test_stream_event_names_are_correct():
    """The SSE event: field must match the event type field value."""
    events = [
        {"type": "node_transition", "node_id": "n1", "status": "done"},
        {"type": "edge_chosen", "from": "n1", "to": "n2"},
    ]
    worker = _make_worker_mock(RUN_ID, SPACE_ID, events)
    app = _make_app(_make_pool([worker]))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/harness-runs/{RUN_ID}/stream")

    assert resp.status_code == 200
    body = resp.text

    # Exact SSE field assertions — these lines must appear in the stream body.
    assert "event: node_transition" in body
    assert "event: edge_chosen" in body


# ---------------------------------------------------------------------------
# 5. Legacy task events pass through unchanged
# ---------------------------------------------------------------------------


async def test_legacy_task_events_pass_through_unchanged():
    """Legacy run_start / run_end events must appear in the SSE body alongside harness events.

    The discriminated envelope is additive — it must not filter out or rename
    existing task lifecycle events that non-harness SSE consumers rely on.
    """
    events = [
        {"type": "run_start", "task_id": RUN_ID},
        {"type": "node_transition", "node_id": "n1", "status": "in_progress"},
        {"type": "run_end", "task_id": RUN_ID, "status": "DONE", "new_state": "done"},
    ]
    worker = _make_worker_mock(RUN_ID, SPACE_ID, events)
    app = _make_app(_make_pool([worker]))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/harness-runs/{RUN_ID}/stream")

    assert resp.status_code == 200
    body = resp.text

    # Harness event.
    assert "event: node_transition" in body
    # Legacy events must appear with correct event: names.
    assert "event: run_start" in body
    assert "event: run_end" in body
    # Payload data must be present.
    assert RUN_ID in body
