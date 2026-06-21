"""I3: Tests for worker lease lifecycle in _run_task."""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import TaskState
from app.storage import TaskStore
from app.worker import Worker, LEASE_TTL


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


def _make_worker(store: TaskStore) -> Worker:
    return Worker(store)


def _lease_count(store: TaskStore, task_id: str) -> int:
    con = sqlite3.connect(store._db_path)
    try:
        return con.execute(
            "SELECT COUNT(*) FROM task_leases WHERE task_id = ?", (task_id,)
        ).fetchone()[0]
    finally:
        con.close()


def _lease_row(store: TaskStore, task_id: str):
    con = sqlite3.connect(store._db_path)
    try:
        return con.execute(
            "SELECT task_id, owner FROM task_leases WHERE task_id = ?", (task_id,)
        ).fetchone()
    finally:
        con.close()


@pytest.mark.asyncio
async def test_run_task_acquires_lease(store: TaskStore, spaces_dir: Path) -> None:
    """Worker should acquire a lease before running the agent."""
    # Set up a minimal task in the store.
    from app.models import Task
    space_dir = spaces_dir / "s1"
    space_dir.mkdir()
    tasks_dir = space_dir / ".cronos" / "tasks"
    tasks_dir.mkdir(parents=True)
    task_file = tasks_dir / "t1.md"
    task_file.write_text(
        "---\n"
        "id: t1\n"
        "state: active\n"
        "title: Test\n"
        "type: task\n"
        "created_at: '2026-01-01T00:00:00Z'\n"
        "updated_at: '2026-01-01T00:00:00Z'\n"
        "space_id: s1\n"
        "---\n"
    )
    await store.reload_all()

    worker = _make_worker(store)
    worker._space_id = "s1"

    acquired_owners: list[str] = []
    original_acquire = store.acquire_lease

    def spy_acquire(task_id, owner, ttl):
        acquired_owners.append(owner)
        return original_acquire(task_id, owner, ttl)

    run_called = asyncio.Event()

    async def fake_run_agent(*args, **kwargs):
        run_called.set()
        from app.agent import AgentResult, Status
        return AgentResult(
            status=Status.DONE,
            exit_code=0,
            final_text="STATUS: DONE",
            session_id="ses1",
            stopped=False,
            result_subtype=None,
            context=None,
            raw_events=[],
            stderr_tail="",
        )

    with (
        patch.object(store, "acquire_lease", side_effect=spy_acquire),
        patch("app.worker.run_agent", side_effect=fake_run_agent),
        patch.object(store, "finalize_run", new_callable=AsyncMock),
        patch.object(store, "drain_pending", new_callable=AsyncMock, return_value=[]),
    ):
        await worker._run_task("t1", None)

    assert len(acquired_owners) == 1
    assert "s1" in acquired_owners[0]


@pytest.mark.asyncio
async def test_run_task_skips_if_lease_held(store: TaskStore, spaces_dir: Path) -> None:
    """If another owner already holds the lease, the worker should skip the task."""
    from app.models import Task
    space_dir = spaces_dir / "s1"
    space_dir.mkdir()
    tasks_dir = space_dir / ".cronos" / "tasks"
    tasks_dir.mkdir(parents=True)
    task_file = tasks_dir / "t1.md"
    task_file.write_text(
        "---\n"
        "id: t1\n"
        "state: active\n"
        "title: Test\n"
        "type: task\n"
        "created_at: '2026-01-01T00:00:00Z'\n"
        "updated_at: '2026-01-01T00:00:00Z'\n"
        "space_id: s1\n"
        "---\n"
    )
    await store.reload_all()

    # Pre-acquire lease with a different owner and long TTL.
    store.acquire_lease("t1", "other-worker", ttl=300)

    worker = _make_worker(store)
    worker._space_id = "s1"

    run_called = False

    async def fake_run_agent(*args, **kwargs):
        nonlocal run_called
        run_called = True
        from app.agent import AgentResult, Status
        return AgentResult(
            status=Status.DONE,
            exit_code=0,
            final_text="STATUS: DONE",
            session_id="ses1",
            stopped=False,
            result_subtype=None,
            context=None,
            raw_events=[],
            stderr_tail="",
        )

    with patch("app.worker.run_agent", side_effect=fake_run_agent):
        await worker._run_task("t1", None)

    assert not run_called, "run_agent should not be called if lease is held by another worker"


@pytest.mark.asyncio
async def test_run_task_releases_lease_after_run(store: TaskStore, spaces_dir: Path) -> None:
    """Lease should be released in the finally block after agent run completes."""
    space_dir = spaces_dir / "s1"
    space_dir.mkdir()
    tasks_dir = space_dir / ".cronos" / "tasks"
    tasks_dir.mkdir(parents=True)
    task_file = tasks_dir / "t1.md"
    task_file.write_text(
        "---\n"
        "id: t1\n"
        "state: active\n"
        "title: Test\n"
        "type: task\n"
        "created_at: '2026-01-01T00:00:00Z'\n"
        "updated_at: '2026-01-01T00:00:00Z'\n"
        "space_id: s1\n"
        "---\n"
    )
    await store.reload_all()

    worker = _make_worker(store)
    worker._space_id = "s1"

    async def fake_run_agent(*args, **kwargs):
        from app.agent import AgentResult, Status
        return AgentResult(
            status=Status.DONE,
            exit_code=0,
            final_text="STATUS: DONE",
            session_id="ses1",
            stopped=False,
            result_subtype=None,
            context=None,
            raw_events=[],
            stderr_tail="",
        )

    with (
        patch("app.worker.run_agent", side_effect=fake_run_agent),
        patch.object(store, "finalize_run", new_callable=AsyncMock),
        patch.object(store, "drain_pending", new_callable=AsyncMock, return_value=[]),
    ):
        await worker._run_task("t1", None)

    # Lease must be gone after the run.
    assert _lease_count(store, "t1") == 0


@pytest.mark.asyncio
async def test_run_task_releases_lease_on_exception(store: TaskStore, spaces_dir: Path) -> None:
    """Lease should be released even if run_agent raises an exception."""
    space_dir = spaces_dir / "s1"
    space_dir.mkdir()
    tasks_dir = space_dir / ".cronos" / "tasks"
    tasks_dir.mkdir(parents=True)
    task_file = tasks_dir / "t1.md"
    task_file.write_text(
        "---\n"
        "id: t1\n"
        "state: active\n"
        "title: Test\n"
        "type: task\n"
        "created_at: '2026-01-01T00:00:00Z'\n"
        "updated_at: '2026-01-01T00:00:00Z'\n"
        "space_id: s1\n"
        "---\n"
    )
    await store.reload_all()

    worker = _make_worker(store)
    worker._space_id = "s1"

    async def exploding_agent(*args, **kwargs):
        raise RuntimeError("crash!")

    with (
        patch("app.worker.run_agent", side_effect=exploding_agent),
        patch.object(store, "finalize_run", new_callable=AsyncMock),
        patch.object(store, "drain_pending", new_callable=AsyncMock, return_value=[]),
    ):
        await worker._run_task("t1", None)

    assert _lease_count(store, "t1") == 0
