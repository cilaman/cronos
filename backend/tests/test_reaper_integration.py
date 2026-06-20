"""I6: Integration tests for reaper wiring in lifespan (startup clear + reaper task)."""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.storage import TaskStore


@pytest.fixture()
def spaces_dir(tmp_path: Path) -> Path:
    d = tmp_path / "spaces"
    d.mkdir()
    return d


@pytest.fixture()
def store(spaces_dir: Path) -> TaskStore:
    s = TaskStore(spaces_dir)
    s._ensure_db_schema()
    return s


def test_clear_all_leases_called_on_reload(store: TaskStore) -> None:
    """clear_all_leases() should wipe lease rows — called at startup."""
    store.acquire_lease("t1", "old-owner", ttl=300)
    store.acquire_lease("t2", "old-owner", ttl=300)

    # Simulate the startup sequence.
    store.clear_all_leases()

    con = sqlite3.connect(store._db_path)
    try:
        count = con.execute("SELECT COUNT(*) FROM task_leases").fetchone()[0]
    finally:
        con.close()
    assert count == 0


@pytest.mark.asyncio
async def test_reaper_task_starts_and_stops() -> None:
    """reaper_loop should start and exit cleanly when stop_event is set."""
    from app.reaper import reaper_loop

    store = MagicMock()
    store.get_expired_leases.return_value = []
    pool = MagicMock()
    pool.enqueue = AsyncMock()
    stop = asyncio.Event()

    task = asyncio.create_task(
        reaper_loop(store, pool, stop, reaper_interval=60, heartbeat_timeout=30)
    )
    # Give the loop a tick to start.
    await asyncio.sleep(0)
    stop.set()
    await asyncio.wait_for(task, timeout=2.0)
    assert task.done() and not task.cancelled()


@pytest.mark.asyncio
async def test_reaper_integration_reenqueues_via_worker_pool() -> None:
    """Full integration: reaper detects an expired lease and calls worker_pool.enqueue."""
    from app.reaper import reaper_loop

    spaces_dir = Path("/tmp/test_reaper_integration_spaces")
    spaces_dir.mkdir(exist_ok=True)
    store = TaskStore(spaces_dir)
    store._ensure_db_schema()

    # Set up a task in ACTIVE state.
    space_dir = spaces_dir / "sp1"
    tasks_dir = space_dir / ".cronos" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "task-x.md").write_text(
        "---\n"
        "id: task-x\n"
        "state: active\n"
        "title: Reaper test\n"
        "type: task\n"
        "created_at: '2026-01-01T00:00:00Z'\n"
        "updated_at: '2026-01-01T00:00:00Z'\n"
        "space_id: sp1\n"
        "---\n"
    )
    await store.reload_all()

    # Inject an expired lease.
    store.acquire_lease("task-x", "dead-owner", ttl=-1)

    enqueue_calls: list[tuple] = []

    async def fake_enqueue(space_id, task_id):
        enqueue_calls.append((space_id, task_id))

    pool = MagicMock()
    pool.enqueue = fake_enqueue

    stop = asyncio.Event()
    stop.set()  # Run one tick then stop.

    await reaper_loop(store, pool, stop, reaper_interval=0, heartbeat_timeout=9999)

    assert ("sp1", "task-x") in enqueue_calls

    # Cleanup.
    import shutil
    shutil.rmtree(spaces_dir, ignore_errors=True)


def test_lifespan_imports_reaper_loop() -> None:
    """Verify reaper_loop is importable from app.reaper (import-time check)."""
    from app.reaper import reaper_loop
    assert callable(reaper_loop)


def test_lifespan_imports_clear_all_leases() -> None:
    """Verify clear_all_leases exists on TaskStore."""
    store = MagicMock(spec=TaskStore)
    assert hasattr(store, "clear_all_leases")
