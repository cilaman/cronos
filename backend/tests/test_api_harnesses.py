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

Error cases: 404, 409, 422 (cycle, dangling edge), 401 (auth).
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import Depends, FastAPI

from app.api.harnesses import router as harnesses_router
from app.auth import require_auth
from app.harnesses import HarnessStore
from app.space_storage import SpaceStore

# ---------------------------------------------------------------------------
# Isolated test app — does NOT touch main.py (that is I5's scope)
# ---------------------------------------------------------------------------

_auth = [Depends(require_auth)]

SPACE_ID = "test-space"
_BASE_URL = f"/api/spaces/{SPACE_ID}/harnesses"


def _make_test_app(space_store: SpaceStore, harness_store: HarnessStore) -> FastAPI:
    """Create a minimal FastAPI app with only the harnesses router registered."""
    _app = FastAPI()
    _app.include_router(harnesses_router, dependencies=_auth)
    _app.state.space_store = space_store
    _app.state.harness_store = harness_store
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
