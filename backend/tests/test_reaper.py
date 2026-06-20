"""I5: Tests for reaper_loop — expired lease detection and task re-enqueue."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import TaskState
from app.reaper import reaper_loop
from app.storage import TaskStore


_TASK_FRONTMATTER = (
    "---\n"
    "id: {tid}\n"
    "state: {state}\n"
    "title: Test\n"
    "type: task\n"
    "created_at: '2026-01-01T00:00:00Z'\n"
    "updated_at: '2026-01-01T00:00:00Z'\n"
    "space_id: s1\n"
    "---\n"
)


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


def _setup_task(
    spaces_dir: Path, task_id: str, state: str = "active"
) -> None:
    tasks_dir = spaces_dir / "s1" / ".cronos" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{task_id}.md").write_text(
        _TASK_FRONTMATTER.format(tid=task_id, state=state)
    )


def _make_pool(enqueue_mock: AsyncMock) -> MagicMock:
    pool = MagicMock()
    pool.enqueue = enqueue_mock
    return pool


@pytest.mark.asyncio
async def test_reaper_reenqueues_expired_active_task(
    store: TaskStore, spaces_dir: Path
) -> None:
    """An expired lease on an ACTIVE task should be re-enqueued."""
    _setup_task(spaces_dir, "t1", state="active")
    await store.reload_all()

    # Inject an expired lease.
    store.acquire_lease("t1", "dead-worker", ttl=-1)

    enqueue_mock = AsyncMock()
    pool = _make_pool(enqueue_mock)
    stop_event = asyncio.Event()

    # Run one tick then stop.
    async def _run():
        stop_event.set()  # Stop after first iteration completes.
        await reaper_loop(store, pool, asyncio.Event(), reaper_interval=0, heartbeat_timeout=9999)

    stop = asyncio.Event()
    stop.set()
    await reaper_loop(store, pool, stop, reaper_interval=0, heartbeat_timeout=9999)

    enqueue_mock.assert_awaited_once_with("s1", "t1")


@pytest.mark.asyncio
async def test_reaper_skips_done_task(store: TaskStore, spaces_dir: Path) -> None:
    """A done task with a stale lease should NOT be re-enqueued."""
    _setup_task(spaces_dir, "t1", state="done")
    await store.reload_all()

    store.acquire_lease("t1", "dead-worker", ttl=-1)

    enqueue_mock = AsyncMock()
    pool = _make_pool(enqueue_mock)
    stop = asyncio.Event()
    stop.set()
    await reaper_loop(store, pool, stop, reaper_interval=0, heartbeat_timeout=9999)

    enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_reaper_deletes_lease_before_enqueue(
    store: TaskStore, spaces_dir: Path
) -> None:
    """Lease row must be deleted before calling enqueue (prevents double re-queue)."""
    import sqlite3
    _setup_task(spaces_dir, "t1", state="active")
    await store.reload_all()

    store.acquire_lease("t1", "dead-worker", ttl=-1)

    deleted_before_enqueue = False

    async def spy_enqueue(space_id, task_id):
        nonlocal deleted_before_enqueue
        con = sqlite3.connect(store._db_path)
        try:
            row = con.execute(
                "SELECT 1 FROM task_leases WHERE task_id = ?", (task_id,)
            ).fetchone()
        finally:
            con.close()
        deleted_before_enqueue = row is None

    pool = _make_pool(spy_enqueue)
    stop = asyncio.Event()
    stop.set()
    await reaper_loop(store, pool, stop, reaper_interval=0, heartbeat_timeout=9999)

    assert deleted_before_enqueue


@pytest.mark.asyncio
async def test_reaper_handles_stale_heartbeat(
    store: TaskStore, spaces_dir: Path
) -> None:
    """A lease with a stale heartbeat (but not expired expiry) should be re-enqueued."""
    import sqlite3
    _setup_task(spaces_dir, "t1", state="active")
    await store.reload_all()

    # Lease with long expiry but stale heartbeat.
    store.acquire_lease("t1", "wedged-worker", ttl=300)
    # Backdate heartbeat.
    con = sqlite3.connect(store._db_path)
    try:
        con.execute(
            "UPDATE task_leases SET heartbeat_at = ? WHERE task_id = ?",
            (time.time() - 1000, "t1"),
        )
        con.commit()
    finally:
        con.close()

    enqueue_mock = AsyncMock()
    pool = _make_pool(enqueue_mock)
    stop = asyncio.Event()
    stop.set()
    await reaper_loop(store, pool, stop, reaper_interval=0, heartbeat_timeout=30)

    enqueue_mock.assert_awaited_once_with("s1", "t1")


@pytest.mark.asyncio
async def test_reaper_no_action_on_live_leases(
    store: TaskStore, spaces_dir: Path
) -> None:
    """A live lease with fresh heartbeat should not be touched."""
    _setup_task(spaces_dir, "t1", state="active")
    await store.reload_all()

    store.acquire_lease("t1", "healthy-worker", ttl=300)

    enqueue_mock = AsyncMock()
    pool = _make_pool(enqueue_mock)
    stop = asyncio.Event()
    stop.set()
    await reaper_loop(store, pool, stop, reaper_interval=0, heartbeat_timeout=9999)

    enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_reaper_stops_when_stop_event_set(
    store: TaskStore, spaces_dir: Path
) -> None:
    """reaper_loop should exit promptly when stop_event is set."""
    enqueue_mock = AsyncMock()
    pool = _make_pool(enqueue_mock)
    stop = asyncio.Event()
    stop.set()  # Stop immediately.

    # Should complete without hanging.
    await asyncio.wait_for(
        reaper_loop(store, pool, stop, reaper_interval=60),
        timeout=2.0,
    )


@pytest.mark.asyncio
async def test_reaper_cleans_lease_for_missing_task(
    store: TaskStore, spaces_dir: Path
) -> None:
    """A stale lease for a task that no longer exists should be deleted without re-enqueue."""
    await store.reload_all()
    store.acquire_lease("ghost-task", "dead-worker", ttl=-1)

    enqueue_mock = AsyncMock()
    pool = _make_pool(enqueue_mock)
    stop = asyncio.Event()
    stop.set()
    await reaper_loop(store, pool, stop, reaper_interval=0, heartbeat_timeout=9999)

    enqueue_mock.assert_not_awaited()
