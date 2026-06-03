from __future__ import annotations

import asyncio
import sqlite3
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import yaml

import app.api.discovery as disc
from app.main import app
from app.space_storage import SpaceStore
from app.stats_store import StatsStore
from app.storage import TaskStore
from app.test_report_store import TestReportStore
from app.trace_store import TraceStore
from app.tools.discovery import DiscoveredItem

from .conftest import _MockWorkerPool, SPACE_ID

# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS discovered_tools (
    source_url TEXT NOT NULL,
    source_slug TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    description TEXT,
    source_sha TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (source_slug, kind, name)
);
CREATE INDEX IF NOT EXISTS idx_discovered_tools_kind ON discovered_tools(kind);
"""


def _make_db(path: Path) -> Path:
    con = sqlite3.connect(path)
    try:
        con.executescript(_DDL)
        con.commit()
    finally:
        con.close()
    return path


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return _make_db(tmp_path / "cronos-index.db")


@pytest.fixture(autouse=True)
def reset_discovery_globals():
    """Reset module-level refresh lock and timestamp before every test."""
    disc._last_refresh_at = None
    disc._refresh_lock = asyncio.Lock()
    yield
    disc._last_refresh_at = None
    disc._refresh_lock = asyncio.Lock()


@pytest.fixture
async def discovery_client(tmp_path: Path, db: Path, space_store, task_store):
    spaces_dir = tmp_path / "spaces"

    app.state.store = task_store
    app.state.space_store = space_store
    app.state.stats_store = StatsStore(spaces_dir)
    app.state.trace_store = TraceStore(spaces_dir)
    app.state.test_report_store = TestReportStore(spaces_dir)
    app.state.worker_pool = _MockWorkerPool()
    app.state.discovery_db_path = db
    app.state.discovery_sources_path = tmp_path / "tool_sources.yml"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _write_sources(path: Path, sources: list[dict]) -> None:
    path.write_text(yaml.dump({"sources": sources}), encoding="utf-8")


def _fake_item(slug: str, kind: str = "agent", name: str = "reviewer") -> DiscoveredItem:
    return DiscoveredItem(
        source_url=f"https://{slug}",
        source_slug=slug,
        kind=kind,
        name=name,
        relative_path=f".claude/{kind}s/{name}.md",
        description="A description",
        source_sha="abc123",
    )


# ---------------------------------------------------------------------------
# GET /api/discovery/sources
# ---------------------------------------------------------------------------


async def test_list_sources_empty_when_no_file(discovery_client) -> None:
    r = await discovery_client.get("/api/discovery/sources")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_sources_returns_entries(tmp_path, discovery_client) -> None:
    sources_path = tmp_path / "tool_sources.yml"
    _write_sources(sources_path, [
        {"url": "https://github.com/foo/bar", "enabled": True, "label": "Foo Bar"},
        {"url": "https://github.com/baz/qux", "enabled": False},
    ])
    app.state.discovery_sources_path = sources_path

    r = await discovery_client.get("/api/discovery/sources")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["url"] == "https://github.com/foo/bar"
    assert data[0]["label"] == "Foo Bar"
    assert data[0]["enabled"] is True
    assert data[1]["enabled"] is False


# ---------------------------------------------------------------------------
# GET /api/discovery/tools
# ---------------------------------------------------------------------------


async def test_list_tools_empty_db(discovery_client) -> None:
    r = await discovery_client.get("/api/discovery/tools")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_tools_returns_indexed_items(tmp_path, db, discovery_client) -> None:
    from app.tools.index import upsert_discovered
    upsert_discovered(db, [_fake_item("github.com-foo-bar", "agent", "reviewer")])

    r = await discovery_client.get("/api/discovery/tools")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "reviewer"
    assert data[0]["kind"] == "agent"


async def test_list_tools_filter_by_kind(tmp_path, db, discovery_client) -> None:
    from app.tools.index import upsert_discovered
    upsert_discovered(db, [
        _fake_item("github.com-foo-bar", "agent", "reviewer"),
        _fake_item("github.com-foo-bar", "skill", "design"),
    ])

    r = await discovery_client.get("/api/discovery/tools?kind=skill")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["kind"] == "skill"
    assert data[0]["name"] == "design"


async def test_list_tools_filter_by_source_slug(tmp_path, db, discovery_client) -> None:
    from app.tools.index import upsert_discovered
    upsert_discovered(db, [
        _fake_item("github.com-acme-tools", "agent", "checker"),
        _fake_item("github.com-other-repo", "agent", "linter"),
    ])

    r = await discovery_client.get(
        "/api/discovery/tools?source_slug=github.com-acme-tools"
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["source_slug"] == "github.com-acme-tools"


# ---------------------------------------------------------------------------
# POST /api/discovery/refresh — missing sources file
# ---------------------------------------------------------------------------


async def test_refresh_returns_empty_when_no_sources_file(
    discovery_client,
) -> None:
    r = await discovery_client.post("/api/discovery/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["refreshed"] == 0
    assert body["items"] == []


# ---------------------------------------------------------------------------
# POST /api/discovery/refresh — two fixture sources
# ---------------------------------------------------------------------------


async def test_refresh_clones_and_indexes_two_sources(
    tmp_path, db, discovery_client, monkeypatch
) -> None:
    sources_path = tmp_path / "tool_sources.yml"
    _write_sources(sources_path, [
        {"url": "https://github.com/acme/tools", "enabled": True},
        {"url": "https://github.com/beta/suite", "enabled": True},
    ])
    app.state.discovery_sources_path = sources_path

    items_a = [_fake_item("github.com-acme-tools", "agent", "reviewer")]
    items_b = [
        _fake_item("github.com-beta-suite", "skill", "formatter"),
        _fake_item("github.com-beta-suite", "agent", "linter"),
    ]
    call_count = {"n": 0}

    async def fake_refresh(source):
        call_count["n"] += 1
        return tmp_path / "clone"

    async def fake_walk(path):
        n = call_count["n"]
        return items_a if n == 1 else items_b

    monkeypatch.setattr(disc, "refresh_source", fake_refresh)
    monkeypatch.setattr(disc, "walk_source", fake_walk)

    r = await discovery_client.post("/api/discovery/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["refreshed"] == 2
    assert len(body["items"]) == 3

    # Items are also persisted in the DB.
    r2 = await discovery_client.get("/api/discovery/tools")
    assert len(r2.json()) == 3


async def test_refresh_skips_disabled_sources(
    tmp_path, discovery_client, monkeypatch
) -> None:
    sources_path = tmp_path / "tool_sources.yml"
    _write_sources(sources_path, [
        {"url": "https://github.com/acme/tools", "enabled": True},
        {"url": "https://github.com/beta/suite", "enabled": False},
    ])
    app.state.discovery_sources_path = sources_path

    refreshed_urls: list[str] = []

    async def fake_refresh(source):
        refreshed_urls.append(source.url)
        return tmp_path / "clone"

    async def fake_walk(path):
        return []

    monkeypatch.setattr(disc, "refresh_source", fake_refresh)
    monkeypatch.setattr(disc, "walk_source", fake_walk)

    r = await discovery_client.post("/api/discovery/refresh")
    assert r.status_code == 200
    assert r.json()["refreshed"] == 1
    assert refreshed_urls == ["https://github.com/acme/tools"]


async def test_refresh_continues_on_source_error(
    tmp_path, discovery_client, monkeypatch
) -> None:
    sources_path = tmp_path / "tool_sources.yml"
    _write_sources(sources_path, [
        {"url": "https://github.com/acme/tools", "enabled": True},
        {"url": "https://github.com/beta/suite", "enabled": True},
    ])
    app.state.discovery_sources_path = sources_path

    call_count = {"n": 0}

    async def fake_refresh(source):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("network error")
        return tmp_path / "clone"

    async def fake_walk(path):
        return [_fake_item("github.com-beta-suite", "agent", "ok")]

    monkeypatch.setattr(disc, "refresh_source", fake_refresh)
    monkeypatch.setattr(disc, "walk_source", fake_walk)

    r = await discovery_client.post("/api/discovery/refresh")
    assert r.status_code == 200
    body = r.json()
    # Only the second source succeeded
    assert body["refreshed"] == 1
    assert len(body["items"]) == 1


# ---------------------------------------------------------------------------
# 60-min lock
# ---------------------------------------------------------------------------


async def test_refresh_locked_while_in_progress(
    discovery_client, monkeypatch
) -> None:
    """Second POST during an ongoing refresh must return 409."""
    gate = asyncio.Event()
    started = asyncio.Event()

    async def slow_refresh(source):
        started.set()
        await gate.wait()  # Blocks until we release
        return Path("/fake")

    async def fake_walk(path):
        return []

    monkeypatch.setattr(disc, "refresh_source", slow_refresh)
    monkeypatch.setattr(disc, "walk_source", fake_walk)

    # Write a sources file so the refresh doesn't short-circuit on empty.
    sources_path = app.state.discovery_sources_path.parent / "tool_sources.yml"
    _write_sources(sources_path, [{"url": "https://github.com/acme/tools", "enabled": True}])
    app.state.discovery_sources_path = sources_path

    # Start the first refresh in the background.
    first = asyncio.create_task(discovery_client.post("/api/discovery/refresh"))
    await asyncio.wait_for(started.wait(), timeout=2.0)

    # Second request hits the 409.
    r2 = await discovery_client.post("/api/discovery/refresh")
    assert r2.status_code == 409

    # Let the first finish.
    gate.set()
    r1 = await first
    assert r1.status_code == 200


async def test_refresh_locked_for_60_min_after_completion(
    discovery_client, monkeypatch
) -> None:
    """POST /refresh within 60 min of last run returns 409."""
    async def fake_refresh(source):
        return Path("/fake")

    async def fake_walk(path):
        return []

    monkeypatch.setattr(disc, "refresh_source", fake_refresh)
    monkeypatch.setattr(disc, "walk_source", fake_walk)

    sources_path = app.state.discovery_sources_path.parent / "tool_sources.yml"
    _write_sources(sources_path, [{"url": "https://github.com/acme/tools", "enabled": True}])
    app.state.discovery_sources_path = sources_path

    # First refresh succeeds
    r1 = await discovery_client.post("/api/discovery/refresh")
    assert r1.status_code == 200

    # Immediate second refresh → 409
    r2 = await discovery_client.post("/api/discovery/refresh")
    assert r2.status_code == 409
    assert "retry" in r2.json()["detail"].lower()


async def test_refresh_allowed_after_lock_expires(
    discovery_client, monkeypatch
) -> None:
    """POST /refresh succeeds once the cooldown has elapsed."""
    async def fake_refresh(source):
        return Path("/fake")

    async def fake_walk(path):
        return []

    monkeypatch.setattr(disc, "refresh_source", fake_refresh)
    monkeypatch.setattr(disc, "walk_source", fake_walk)

    sources_path = app.state.discovery_sources_path.parent / "tool_sources.yml"
    _write_sources(sources_path, [{"url": "https://github.com/acme/tools", "enabled": True}])
    app.state.discovery_sources_path = sources_path

    # Simulate a completed refresh 61 minutes ago.
    disc._last_refresh_at = datetime.now(timezone.utc) - timedelta(seconds=3601)

    r = await discovery_client.post("/api/discovery/refresh")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Periodic scheduler — run_refresh_if_unlocked
# ---------------------------------------------------------------------------


async def test_run_refresh_if_unlocked_returns_none_when_locked(
    tmp_path, db, monkeypatch
) -> None:
    """If the lock is already held, run_refresh_if_unlocked returns None."""
    await disc._refresh_lock.acquire()  # Simulate a held lock
    try:
        result = await disc.run_refresh_if_unlocked(db, tmp_path / "tool_sources.yml")
        assert result is None
    finally:
        disc._refresh_lock.release()


async def test_run_refresh_if_unlocked_returns_none_in_cooldown(
    tmp_path, db
) -> None:
    disc._last_refresh_at = datetime.now(timezone.utc) - timedelta(seconds=100)

    result = await disc.run_refresh_if_unlocked(db, tmp_path / "tool_sources.yml")
    assert result is None


async def test_run_refresh_if_unlocked_runs_when_no_sources(
    tmp_path, db
) -> None:
    result = await disc.run_refresh_if_unlocked(db, tmp_path / "tool_sources.yml")
    assert result is not None
    assert result["refreshed"] == 0
    assert result["items"] == []


async def test_run_refresh_if_unlocked_runs_after_cooldown(
    tmp_path, db, monkeypatch
) -> None:
    disc._last_refresh_at = datetime.now(timezone.utc) - timedelta(seconds=3601)

    async def fake_refresh(source):
        return Path("/fake")

    async def fake_walk(path):
        return [_fake_item("github.com-acme-tools")]

    monkeypatch.setattr(disc, "refresh_source", fake_refresh)
    monkeypatch.setattr(disc, "walk_source", fake_walk)

    sources_path = tmp_path / "tool_sources.yml"
    _write_sources(sources_path, [{"url": "https://github.com/acme/tools", "enabled": True}])

    result = await disc.run_refresh_if_unlocked(db, sources_path)
    assert result is not None
    assert result["refreshed"] == 1


# ---------------------------------------------------------------------------
# Periodic scheduler — discovery_refresh_loop fires and back-offs on error
# ---------------------------------------------------------------------------


async def test_discovery_refresh_loop_fires_at_interval(
    tmp_path, db, monkeypatch
) -> None:
    from app.main import discovery_refresh_loop

    calls: list[str] = []

    async def fake_run_refresh_if_unlocked(db_path, sources_path):
        calls.append("refresh")
        return {"refreshed": 0, "items": []}

    monkeypatch.setattr(disc, "run_refresh_if_unlocked", fake_run_refresh_if_unlocked)
    # Import after patch so the loop uses the monkeypatched version.
    import importlib
    import app.main as main_mod
    monkeypatch.setattr(
        "app.main.discovery_refresh_loop",
        discovery_refresh_loop,
    )

    stop = asyncio.Event()
    # Use a very short interval (0.01 hours = 36 ms) to trigger quickly.
    task = asyncio.create_task(
        discovery_refresh_loop(db, tmp_path / "tool_sources.yml", 0.00001, stop)
    )
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=1.0)

    assert len(calls) >= 1


async def test_discovery_refresh_loop_does_not_crash_on_error(
    tmp_path, db, monkeypatch
) -> None:
    from app.main import discovery_refresh_loop

    call_count = {"n": 0}

    async def failing_refresh(db_path, sources_path):
        call_count["n"] += 1
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(disc, "run_refresh_if_unlocked", failing_refresh)

    stop = asyncio.Event()
    task = asyncio.create_task(
        discovery_refresh_loop(db, tmp_path / "tool_sources.yml", 0.00001, stop)
    )
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=1.0)

    # Loop survived despite repeated errors
    assert call_count["n"] >= 1
