"""I4: Tests for durable auto-resume count persistence in worker._finalize."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.storage import TaskStore
from app.worker import Worker


_TASK_FRONTMATTER = (
    "---\n"
    "id: {tid}\n"
    "state: active\n"
    "title: Test\n"
    "type: task\n"
    "created_at: '2026-01-01T00:00:00Z'\n"
    "updated_at: '2026-01-01T00:00:00Z'\n"
    "space_id: {sid}\n"
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


def _setup_task(spaces_dir: Path, space_id: str, task_id: str) -> None:
    space_dir = spaces_dir / space_id
    tasks_dir = space_dir / ".cronos" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / f"{task_id}.md").write_text(
        _TASK_FRONTMATTER.format(tid=task_id, sid=space_id)
    )


def _make_max_turns_result():
    from app.agent import AgentResult
    return AgentResult(
        status=None,
        exit_code=0,
        final_text="",
        session_id="ses1",
        stopped=False,
        result_subtype="error_max_turns",
        context=None,
        raw_events=[],
        stderr_tail="",
    )


def _make_done_result():
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


@pytest.mark.asyncio
async def test_auto_resume_count_persisted_on_max_turns(
    store: TaskStore, spaces_dir: Path
) -> None:
    """auto_resume_count should be upserted to DB when agent hits max-turns."""
    _setup_task(spaces_dir, "s1", "t1")
    await store.reload_all()

    worker = Worker(store)
    worker._space_id = "s1"

    with (
        patch.object(store, "finalize_run", new_callable=AsyncMock),
        patch.object(store, "resume_with_message", new_callable=AsyncMock),
        patch.object(worker, "enqueue", new_callable=AsyncMock),
        patch.object(store, "drain_pending", new_callable=AsyncMock, return_value=[]),
    ):
        await worker._finalize("t1", _make_max_turns_result())

    assert store.load_auto_resume_counts().get("t1", 0) == 1


@pytest.mark.asyncio
async def test_auto_resume_count_increments_on_repeated_max_turns(
    store: TaskStore, spaces_dir: Path
) -> None:
    """Each max-turns run should increment the persisted count."""
    _setup_task(spaces_dir, "s1", "t1")
    await store.reload_all()

    worker = Worker(store)
    worker._space_id = "s1"

    with (
        patch.object(store, "finalize_run", new_callable=AsyncMock),
        patch.object(store, "resume_with_message", new_callable=AsyncMock),
        patch.object(worker, "enqueue", new_callable=AsyncMock),
        patch.object(store, "drain_pending", new_callable=AsyncMock, return_value=[]),
    ):
        await worker._finalize("t1", _make_max_turns_result())
        await worker._finalize("t1", _make_max_turns_result())

    assert store.load_auto_resume_counts().get("t1", 0) == 2


@pytest.mark.asyncio
async def test_auto_resume_count_deleted_on_done(
    store: TaskStore, spaces_dir: Path
) -> None:
    """On a DONE outcome, the auto_resume count row should be removed from DB."""
    _setup_task(spaces_dir, "s1", "t1")
    await store.reload_all()

    # Pre-seed a count.
    store.upsert_auto_resume_count("t1", 2)
    worker = Worker(store)
    worker._space_id = "s1"
    worker._auto_resume_counts["t1"] = 2

    with (
        patch.object(store, "finalize_run", new_callable=AsyncMock),
        patch.object(store, "drain_pending", new_callable=AsyncMock, return_value=[]),
    ):
        await worker._finalize("t1", _make_done_result())

    # Row should be deleted after a non-max-turns completion.
    assert "t1" not in store.load_auto_resume_counts()


@pytest.mark.asyncio
async def test_worker_loads_auto_resume_counts_from_db(
    store: TaskStore, spaces_dir: Path
) -> None:
    """Worker.__init__ should load existing auto_resume_counts from the DB."""
    store.upsert_auto_resume_count("t99", 3)
    worker = Worker(store)
    assert worker._auto_resume_counts.get("t99") == 3
