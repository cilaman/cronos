"""
Tests for backend/app/api/harnesses.py

Covers all five REST endpoints via an isolated FastAPI test app that mounts
the harnesses router with HarnessStore + SpaceStore on app.state.  The main
app singleton (main.py) is NOT used here because wiring main.py is I5's scope.

Endpoints tested:
  GET    /api/spaces/{space_id}/harnesses
  POST   /api/spaces/{space_id}/harnesses
  GET    /api/spaces/{space_id}/harnesses/{name}
  PUT    /api/spaces/{space_id}/harnesses/{name}
  DELETE /api/spaces/{space_id}/harnesses/{name}
  POST   /api/spaces/{space_id}/harnesses/{name}/run
  GET    /api/spaces/{space_id}/harnesses/{name}/runs

Error cases: 404, 409, 422 (cycle, dangling edge), 401 (auth).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import Depends, FastAPI

from app.api.harnesses import router as harnesses_router
from app.auth import require_auth
from app.harnesses import HarnessStore
from app.harnesses.run_index import RunSummary
from app.space_storage import SpaceStore
from app.storage import TaskStore

# ---------------------------------------------------------------------------
# Isolated test app — does NOT touch main.py (that is I5's scope)
# ---------------------------------------------------------------------------

_auth = [Depends(require_auth)]

SPACE_ID = "test-space"
_BASE_URL = f"/api/spaces/{SPACE_ID}/harnesses"


def _make_test_app(
    space_store: SpaceStore,
    harness_store: HarnessStore,
    task_store: "TaskStore | None" = None,
    worker_pool: "object | None" = None,
) -> FastAPI:
    """Create a minimal FastAPI app with only the harnesses router registered."""
    _app = FastAPI()
    _app.include_router(harnesses_router, dependencies=_auth)
    _app.state.space_store = space_store
    _app.state.harness_store = harness_store
    if task_store is not None:
        _app.state.store = task_store
    if worker_pool is not None:
        _app.state.worker_pool = worker_pool
    return _app


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
def harness_store():
    return HarnessStore()


@pytest.fixture
async def h_client(space_store, harness_store):
    """AsyncClient backed by an isolated test app with harnesses router."""
    _app = _make_test_app(space_store, harness_store)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------

_NODE = {
    "id": "n1",
    "type": "agent",
    "position": {"x": 0.0, "y": 0.0},
    "ports": {"out": {"direction": "output"}},
    "label": "Node 1",
}

_HARNESS_PAYLOAD = {
    "name": "My Flow",
    "description": "A test harness",
    "nodes": [_NODE],
    "edges": [],
}

_TWO_NODES = [
    {"id": "a", "type": "agent", "position": {"x": 0, "y": 0}, "ports": {"out": {}, "in": {}}},
    {"id": "b", "type": "agent", "position": {"x": 1, "y": 0}, "ports": {"out": {}, "in": {}}},
]

_CYCLE_EDGES = [
    {"id": "e1", "source": {"node_id": "a", "port_id": "out"}, "target": {"node_id": "b", "port_id": "in"}},
    {"id": "e2", "source": {"node_id": "b", "port_id": "out"}, "target": {"node_id": "a", "port_id": "in"}},
]


# ---------------------------------------------------------------------------
# GET list — initially empty
# ---------------------------------------------------------------------------


async def test_list_harnesses_empty(h_client):
    resp = await h_client.get(_BASE_URL)
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# POST create + GET fetch round-trip
# ---------------------------------------------------------------------------


async def test_create_and_get_round_trip(h_client):
    create_resp = await h_client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == "My Flow"
    assert created["description"] == "A test harness"
    assert len(created["nodes"]) == 1
    assert "created_at" in created and "updated_at" in created

    get_resp = await h_client.get(f"{_BASE_URL}/My Flow")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "My Flow"


async def test_list_after_create_returns_one(h_client):
    await h_client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
    resp = await h_client.get(_BASE_URL)
    items = resp.json()
    assert resp.status_code == 200
    assert len(items) == 1
    assert items[0]["name"] == "My Flow"


# ---------------------------------------------------------------------------
# 404 — get nonexistent
# ---------------------------------------------------------------------------


async def test_get_nonexistent_returns_404(h_client):
    assert (await h_client.get(f"{_BASE_URL}/does-not-exist")).status_code == 404


async def test_get_unknown_space_returns_404(h_client):
    assert (await h_client.get("/api/spaces/no-such-space/harnesses/any")).status_code == 404


# ---------------------------------------------------------------------------
# 409 — duplicate name
# ---------------------------------------------------------------------------


async def test_create_duplicate_name_returns_409(h_client):
    await h_client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
    assert (await h_client.post(_BASE_URL, json=_HARNESS_PAYLOAD)).status_code == 409


# ---------------------------------------------------------------------------
# 422 — cycle (A → B → A)
# ---------------------------------------------------------------------------


async def test_create_with_cycle_returns_422(h_client):
    payload = {"name": "Cycle Flow", "nodes": _TWO_NODES, "edges": _CYCLE_EDGES}
    assert (await h_client.post(_BASE_URL, json=payload)).status_code == 422


# ---------------------------------------------------------------------------
# 422 — dangling edge (references nonexistent node)
# ---------------------------------------------------------------------------


async def test_create_with_dangling_edge_returns_422(h_client):
    payload = {
        "name": "Dangling Flow",
        "nodes": [{"id": "n1", "type": "agent", "position": {"x": 0, "y": 0}, "ports": {"out": {}}}],
        "edges": [
            {"id": "e1",
             "source": {"node_id": "n1", "port_id": "out"},
             "target": {"node_id": "nonexistent", "port_id": "in"}},
        ],
    }
    assert (await h_client.post(_BASE_URL, json=payload)).status_code == 422


# ---------------------------------------------------------------------------
# PUT — update
# ---------------------------------------------------------------------------


async def test_update_harness(h_client):
    await h_client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
    update = {
        "name": "My Flow",
        "description": "Updated",
        "nodes": [dict(_NODE, label="Updated Node")],
        "edges": [],
        "variables": {"key": "val"},
        "version": "1.1",
    }
    resp = await h_client.put(f"{_BASE_URL}/My Flow", json=update)
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "Updated"
    assert body["version"] == "1.1"
    assert body["variables"] == {"key": "val"}
    assert body["nodes"][0]["label"] == "Updated Node"


async def test_update_preserves_created_at(h_client):
    """PUT must not re-stamp created_at; only updated_at should advance."""
    await h_client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
    first_get = (await h_client.get(f"{_BASE_URL}/My Flow")).json()
    original_created_at = first_get["created_at"]
    original_updated_at = first_get["updated_at"]

    update = {
        "name": "My Flow",
        "description": "Changed description",
        "nodes": [_NODE],
        "edges": [],
    }
    put_resp = await h_client.put(f"{_BASE_URL}/My Flow", json=update)
    assert put_resp.status_code == 200

    second_get = (await h_client.get(f"{_BASE_URL}/My Flow")).json()
    assert second_get["created_at"] == original_created_at, (
        "created_at must be preserved across PUT"
    )
    # updated_at should be >= original (may be equal in fast tests, never earlier)
    assert second_get["updated_at"] >= original_updated_at, (
        "updated_at must not regress"
    )


async def test_update_nonexistent_returns_404(h_client):
    resp = await h_client.put(f"{_BASE_URL}/no-such", json={"name": "no-such", "nodes": [], "edges": []})
    assert resp.status_code == 404


async def test_update_with_cycle_returns_422(h_client):
    await h_client.post(_BASE_URL, json={"name": "Two Nodes", "nodes": _TWO_NODES, "edges": []})
    update = {"name": "Two Nodes", "nodes": _TWO_NODES, "edges": _CYCLE_EDGES}
    assert (await h_client.put(f"{_BASE_URL}/Two Nodes", json=update)).status_code == 422


async def test_update_on_unknown_space_returns_404(h_client):
    resp = await h_client.put(
        "/api/spaces/no-such-space/harnesses/any",
        json={"name": "any", "nodes": [], "edges": []},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE — removes harness
# ---------------------------------------------------------------------------


async def test_delete_harness(h_client):
    await h_client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
    assert (await h_client.delete(f"{_BASE_URL}/My Flow")).status_code == 204
    assert (await h_client.get(f"{_BASE_URL}/My Flow")).status_code == 404


async def test_delete_nonexistent_returns_404(h_client):
    assert (await h_client.delete(f"{_BASE_URL}/no-such")).status_code == 404


async def test_delete_removes_from_list(h_client):
    await h_client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
    await h_client.delete(f"{_BASE_URL}/My Flow")
    assert (await h_client.get(_BASE_URL)).json() == []


async def test_delete_on_unknown_space_returns_404(h_client):
    assert (await h_client.delete("/api/spaces/no-such-space/harnesses/any")).status_code == 404


# ---------------------------------------------------------------------------
# POST create on unknown space returns 404
# ---------------------------------------------------------------------------


async def test_create_on_unknown_space_returns_404(h_client):
    resp = await h_client.post("/api/spaces/no-such-space/harnesses", json=_HARNESS_PAYLOAD)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth: unauthenticated request returns 401 when credentials are configured
# ---------------------------------------------------------------------------


async def test_unauthenticated_returns_401(space_store, harness_store, monkeypatch):
    """Missing credentials return 401 when auth env vars are set."""
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", "admin")
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", "secret")
    _app = _make_test_app(space_store, harness_store)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(_BASE_URL)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /{name}/run — manual trigger
# ---------------------------------------------------------------------------


async def test_trigger_harness_run_returns_202(space_store, harness_store, tmp_path):
    """POST /run returns 202 with run_id and harness_id."""
    from unittest.mock import AsyncMock, MagicMock
    from app.models import Task, TaskState
    from datetime import UTC, datetime

    # Build a minimal mock task.
    fake_task = MagicMock(spec=Task)
    fake_task.id = "run-task-123"

    # Mock TaskStore.create and TaskStore.transition.
    task_store = MagicMock()
    task_store.create = AsyncMock(return_value=fake_task)
    task_store.transition = AsyncMock(return_value=fake_task)

    # Mock worker.
    mock_worker = MagicMock()
    mock_worker.register_run = MagicMock()
    mock_worker.enqueue = AsyncMock()
    mock_worker.lookup_space_id = MagicMock(return_value=None)

    # Mock WorkerPool.
    mock_pool = MagicMock()
    mock_pool.get = MagicMock(return_value=mock_worker)

    _app = _make_test_app(space_store, harness_store, task_store=task_store, worker_pool=mock_pool)

    # Create a harness first so the endpoint finds it.
    with patch("app.api.harnesses.run_index.append_run", new_callable=AsyncMock):
        transport = httpx.ASGITransport(app=_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Create harness
            create_resp = await client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
            assert create_resp.status_code == 201

            # Trigger run
            run_resp = await client.post(f"{_BASE_URL}/My Flow/run")

    assert run_resp.status_code == 202
    body = run_resp.json()
    assert body["run_id"] == "run-task-123"
    assert body["harness_id"] == "My Flow"
    assert "triggered_at" in body


# ---------------------------------------------------------------------------
# GET /{name}/runs — run history list
# ---------------------------------------------------------------------------


async def test_list_harness_runs_empty(space_store, harness_store):
    """GET /runs returns [] when no runs exist."""
    _app = _make_test_app(space_store, harness_store)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create harness first
        await client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
        resp = await client.get(f"{_BASE_URL}/My Flow/runs")

    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_harness_runs_after_trigger(space_store, harness_store, tmp_path):
    """GET /runs returns the triggered run summary."""
    from unittest.mock import AsyncMock, MagicMock
    from app.models import Task, TaskState

    fake_task = MagicMock(spec=Task)
    fake_task.id = "run-abc"

    task_store = MagicMock()
    task_store.create = AsyncMock(return_value=fake_task)
    task_store.transition = AsyncMock(return_value=fake_task)

    mock_worker = MagicMock()
    mock_worker.register_run = MagicMock()
    mock_worker.enqueue = AsyncMock()
    mock_worker.lookup_space_id = MagicMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.get = MagicMock(return_value=mock_worker)

    _app = _make_test_app(space_store, harness_store, task_store=task_store, worker_pool=mock_pool)

    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
        # Trigger a real run (with real run_index writing to tmp space_dir).
        await client.post(f"{_BASE_URL}/My Flow/run")
        resp = await client.get(f"{_BASE_URL}/My Flow/runs")

    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run-abc"
    assert runs[0]["harness_id"] == "My Flow"
    assert runs[0]["status"] == "running"


# ---------------------------------------------------------------------------
# DELETE — active run guard
# ---------------------------------------------------------------------------


async def test_delete_harness_with_no_runs(space_store, harness_store):
    """DELETE proceeds when read_index returns [] (no index file yet)."""
    _app = _make_test_app(space_store, harness_store)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
        resp = await client.delete(f"{_BASE_URL}/My Flow")

    # Should succeed because read_index returns [] when file absent.
    assert resp.status_code == 204


async def test_delete_harness_blocked_when_run_active(space_store, harness_store):
    """DELETE returns 409 when a run is currently running."""
    _app = _make_test_app(space_store, harness_store)

    # Seed a running run in the index.
    from app.harnesses import run_index as ri
    space_dir = space_store.spaces_dir / SPACE_ID
    summary = RunSummary(
        run_id="active-run-1",
        harness_id="My Flow",
        status="running",
        triggered_at="2026-01-01T00:00:00Z",
    )
    await ri.append_run(space_dir, "My Flow", summary)

    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
        resp = await client.delete(f"{_BASE_URL}/My Flow")

    assert resp.status_code == 409
    body = resp.json()
    assert "active_run_ids" in body["detail"]
    assert "active-run-1" in body["detail"]["active_run_ids"]
