"""I1: Verify that async TaskStore methods dispatch SQLite I/O via asyncio.to_thread."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.storage import TaskStore


@pytest.fixture()
def store(tmp_path: Path) -> TaskStore:
    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir()
    s = TaskStore(spaces_dir)
    s._ensure_db_schema()
    return s


# ---- reindex_path dispatches _reindex_locked via asyncio.to_thread ----

@pytest.mark.asyncio
async def test_reindex_path_uses_to_thread(store: TaskStore, tmp_path: Path) -> None:
    path = tmp_path / "spaces" / "s1" / ".cronos" / "tasks" / "t1.md"
    dispatched: list[tuple] = []

    async def fake_to_thread(fn, *args, **kwargs):
        dispatched.append((fn, args))
        return None

    with patch("asyncio.to_thread", side_effect=fake_to_thread):
        await store.reindex_path(path)

    assert len(dispatched) == 1
    fn, args = dispatched[0]
    assert fn == store._reindex_locked
    assert args == (path,)


# ---- delete dispatches _db_delete via asyncio.to_thread ----

@pytest.mark.asyncio
async def test_delete_uses_to_thread_for_db_delete(store: TaskStore, tmp_path: Path) -> None:
    """delete() must await asyncio.to_thread(self._db_delete, ...) not call directly."""
    from app.storage import atomic_write, dump_task, parse_file
    from app.models import Task, TaskState
    from datetime import datetime, UTC

    space_id = "s1"
    space_dir = tmp_path / "spaces" / space_id
    tasks_dir = space_dir / ".cronos" / "tasks"
    tasks_dir.mkdir(parents=True)

    task_id = "2026-01-01-0000-test-task"
    task = Task(
        id=task_id,
        space_id=space_id,
        title="Test Task",
        state=TaskState.BACKLOG,
        type="task",
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    path = tasks_dir / f"{task_id}.md"
    atomic_write(path, dump_task(task))

    # Reload so the store knows about this task
    await store.reload_all()

    dispatched_db_delete: list[str] = []

    original_to_thread = asyncio.to_thread

    async def tracking_to_thread(fn, *args, **kwargs):
        if fn == store._db_delete:
            dispatched_db_delete.append(args[0] if args else None)
        return await original_to_thread(fn, *args, **kwargs)

    with patch("asyncio.to_thread", side_effect=tracking_to_thread):
        await store.delete(task_id)

    assert task_id in dispatched_db_delete, (
        f"_db_delete was not dispatched via asyncio.to_thread for task {task_id!r}"
    )
