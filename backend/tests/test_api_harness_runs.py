"""
Tests for backend/app/api/harness_runs.py

Covers the cross-space harness run endpoints mounted at /api/harness-runs.

Endpoints tested:
  GET  /api/harness-runs/{run_id}         — get run state
  POST /api/harness-runs/{run_id}/cancel  — cancel a run

Error cases: 404 (unknown run_id, missing state file), 409 (already terminal).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import Depends, FastAPI

from app.api.harness_runs import harness_runs_router
from app.auth import require_auth
from app.harnesses.run_state import NodeState, RunState, save_atomic
from app.space_storage import SpaceStore

# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

_auth = [Depends(require_auth)]

SPACE_ID = "test-space"
RUN_ID = "test-run-001"


def _make_harness_runs_app(
    space_store: SpaceStore,
    worker_pool: object,
) -> FastAPI:
    """Create a minimal FastAPI app with only the harness_runs router registered."""
    _app = FastAPI()
    _app.include_router(harness_runs_router, dependencies=_auth)
    _app.state.space_store = space_store
    _app.state.worker_pool = worker_pool
    return _app


def _make_mock_pool_with_run(space_id: str, run_id: str) -> MagicMock:
    """Build a WorkerPool mock where lookup_space_id returns space_id for run_id."""
    mock_worker = MagicMock()
    mock_worker.lookup_space_id = MagicMock(return_value=space_id)
    mock_worker.stop_current = MagicMock(return_value=True)

    mock_pool = MagicMock()
    mock_pool.all_workers = MagicMock(return_value=[mock_worker])
    return mock_pool


def _make_mock_pool_without_run() -> MagicMock:
    """Build a WorkerPool mock where no run is found."""
    mock_worker = MagicMock()
    mock_worker.lookup_space_id = MagicMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.all_workers = MagicMock(return_value=[mock_worker])
    return mock_pool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def space_store(tmp_path):
    store = SpaceStore(tmp_path / "spaces")
    await store.create(
        name="Test Space",
        color="#15803D",
        space_id=SPACE_ID,
    )
    return store


@pytest.fixture
def run_state_path(space_store) -> Path:
    """Return the canonical path for the test run's state file."""
    space_dir = space_store.spaces_dir / SPACE_ID
    return space_dir / ".cronos" / "harness-runs" / f"{RUN_ID}.json"


def _write_run_state(path: Path, status: str = "running") -> RunState:
    """Create and persist a minimal RunState at *path*."""
    state = RunState(
        run_id=RUN_ID,
        harness_id="test-harness",
        goal_task_id=RUN_ID,
        status=status,
    )
    save_atomic(path, state)
    return state


# ---------------------------------------------------------------------------
# GET /api/harness-runs/{run_id} — get run status
# ---------------------------------------------------------------------------


async def test_get_harness_run_not_found(space_store):
    """Unknown run_id returns 404."""
    pool = _make_mock_pool_without_run()
    _app = _make_harness_runs_app(space_store, pool)

    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/harness-runs/unknown-run-id")

    assert resp.status_code == 404


async def test_get_harness_run_returns_state(space_store, run_state_path):
    """GET returns the RunState dict for a known run."""
    _write_run_state(run_state_path, status="running")

    pool = _make_mock_pool_with_run(SPACE_ID, RUN_ID)
    _app = _make_harness_runs_app(space_store, pool)

    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/harness-runs/{RUN_ID}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == RUN_ID
    assert body["harness_id"] == "test-harness"
    assert body["status"] == "running"


# ---------------------------------------------------------------------------
# POST /api/harness-runs/{run_id}/cancel — cancel a run
# ---------------------------------------------------------------------------


async def test_cancel_harness_run_not_found(space_store):
    """Unknown run_id returns 404."""
    pool = _make_mock_pool_without_run()
    _app = _make_harness_runs_app(space_store, pool)

    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/harness-runs/unknown-run-id/cancel")

    assert resp.status_code == 404


async def test_cancel_harness_run_success(space_store, run_state_path):
    """Cancel a running run — response status=cancelled, file updated."""
    # Seed a running state with one pending node.
    state = RunState(
        run_id=RUN_ID,
        harness_id="test-harness",
        goal_task_id=RUN_ID,
        status="running",
        nodes_executed={"n1": NodeState(status="pending")},
    )
    save_atomic(run_state_path, state)

    pool = _make_mock_pool_with_run(SPACE_ID, RUN_ID)
    _app = _make_harness_runs_app(space_store, pool)

    from unittest.mock import patch, AsyncMock

    # Patch run_index.update_run_status to avoid touching real index files.
    with patch("app.api.harness_runs._run_index.update_run_status", new_callable=AsyncMock):
        transport = httpx.ASGITransport(app=_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/harness-runs/{RUN_ID}/cancel")

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == RUN_ID
    assert body["status"] == "cancelled"

    # Verify the state file was updated on disk.
    updated = json.loads(run_state_path.read_text(encoding="utf-8"))
    assert updated["status"] == "cancelled"
    # The pending node should have been marked failed.
    assert updated["nodes_executed"]["n1"]["status"] == "failed"
    assert updated["nodes_executed"]["n1"]["reason"] == "cancelled"


async def test_cancel_harness_run_already_done_returns_409(space_store, run_state_path):
    """Cancelling an already-done run returns 409."""
    _write_run_state(run_state_path, status="done")

    pool = _make_mock_pool_with_run(SPACE_ID, RUN_ID)
    _app = _make_harness_runs_app(space_store, pool)

    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/api/harness-runs/{RUN_ID}/cancel")

    assert resp.status_code == 409
