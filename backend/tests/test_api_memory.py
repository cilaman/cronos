from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.main import app
from app.memory_store import MemoryStore
from app.models import MemoryKind
from app.space_storage import SpaceStore
from app.stats_store import StatsStore
from app.storage import TaskStore
from app.test_report_store import TestReportStore
from app.trace_store import TraceStore

from .conftest import SPACE_ID, _MockWorkerPool


@pytest.fixture
async def memory_client(tmp_path: Path, space_store, task_store):
    data_dir = tmp_path / "data"
    spaces_dir = tmp_path / "spaces"
    memory_store = MemoryStore(data_dir, spaces_dir)

    app.state.store = task_store
    app.state.space_store = space_store
    app.state.stats_store = StatsStore(spaces_dir)
    app.state.trace_store = TraceStore(spaces_dir)
    app.state.test_report_store = TestReportStore(spaces_dir)
    app.state.memory_store = memory_store
    app.state.worker_pool = _MockWorkerPool()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_empty(memory_client) -> None:
    r = await memory_client.get("/api/memory/global")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_after_create(memory_client) -> None:
    await memory_client.post("/api/memory/global", json={"kind": "fact", "title": "My fact"})
    r = await memory_client.get("/api/memory/global")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["title"] == "My fact"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_returns_201(memory_client) -> None:
    r = await memory_client.post(
        "/api/memory/global",
        json={"kind": "fact", "title": "New fact", "confirmed": True, "score": 0.7},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"].startswith("mem-")
    assert body["kind"] == "fact"
    assert body["confirmed"] is True
    assert body["score"] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_create_per_space_scope(memory_client) -> None:
    scope = f"space:{SPACE_ID}"
    r = await memory_client.post(
        f"/api/memory/{scope}",
        json={"kind": "procedure", "title": "Space proc"},
    )
    assert r.status_code == 201
    assert r.json()["scope"] == scope


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_existing(memory_client) -> None:
    cr = await memory_client.post("/api/memory/global", json={"kind": "fact", "title": "Gettable"})
    item_id = cr.json()["id"]
    r = await memory_client.get(f"/api/memory/global/{item_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Gettable"


@pytest.mark.asyncio
async def test_get_missing_returns_404(memory_client) -> None:
    r = await memory_client.get("/api/memory/global/no-such-id")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Update (PATCH)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_title(memory_client) -> None:
    cr = await memory_client.post("/api/memory/global", json={"kind": "fact", "title": "Original"})
    item_id = cr.json()["id"]
    r = await memory_client.patch(f"/api/memory/global/{item_id}", json={"title": "Updated"})
    assert r.status_code == 200
    assert r.json()["title"] == "Updated"


@pytest.mark.asyncio
async def test_patch_missing_returns_404(memory_client) -> None:
    r = await memory_client.patch("/api/memory/global/ghost", json={"title": "X"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_returns_204(memory_client) -> None:
    cr = await memory_client.post("/api/memory/global", json={"kind": "fact", "title": "Deletable"})
    item_id = cr.json()["id"]
    r = await memory_client.delete(f"/api/memory/global/{item_id}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_then_get_returns_404(memory_client) -> None:
    cr = await memory_client.post("/api/memory/global", json={"kind": "fact", "title": "Gone"})
    item_id = cr.json()["id"]
    await memory_client.delete(f"/api/memory/global/{item_id}")
    r = await memory_client.get(f"/api/memory/global/{item_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_missing_returns_404(memory_client) -> None:
    r = await memory_client.delete("/api/memory/global/phantom")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Index endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_endpoint_after_create(memory_client) -> None:
    await memory_client.post("/api/memory/global", json={"kind": "fact", "title": "Index me"})
    r = await memory_client.get("/api/memory/global/index.md")
    assert r.status_code == 200
    assert "Memory Index — global" in r.text
    assert "Index me" in r.text


@pytest.mark.asyncio
async def test_index_endpoint_missing_scope(memory_client) -> None:
    r = await memory_client.get("/api/memory/global/index.md")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Round-trip: all fields survive create → get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_roundtrip_full_item(memory_client) -> None:
    payload = {
        "kind": "reference",
        "title": "Round trip",
        "body": "Some body text",
        "confirmed": True,
        "confidence": 0.85,
        "score": 1.5,
        "ref_count": 3,
        "sources": ["task-abc", "task-def"],
        "links": ["mem-other"],
    }
    cr = await memory_client.post("/api/memory/global", json=payload)
    assert cr.status_code == 201
    item_id = cr.json()["id"]

    r = await memory_client.get(f"/api/memory/global/{item_id}")
    data = r.json()
    assert data["kind"] == "reference"
    assert data["title"] == "Round trip"
    assert data["body"] == "Some body text"
    assert data["confirmed"] is True
    assert data["confidence"] == pytest.approx(0.85)
    assert data["score"] == pytest.approx(1.5)
    assert data["ref_count"] == 3
    assert data["sources"] == ["task-abc", "task-def"]
    assert data["links"] == ["mem-other"]
