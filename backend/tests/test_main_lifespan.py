"""Tests verifying that the cron background task is wired into the lifespan.

These tests confirm:
- lifespan creates a background asyncio task named "cron"
- the cron task is cancelled (via stop_event) on shutdown
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Async helpers (factories — each call creates a fresh coroutine)
# ---------------------------------------------------------------------------


async def _noop_coro(*args, **kwargs):
    """Coroutine that returns immediately."""
    return


async def _sleeping_coro(*args, **kwargs):
    """Coroutine that sleeps until cancelled (simulates a real background task)."""
    try:
        await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_creates_cron_task(tmp_path):
    """lifespan() must create an asyncio task named 'cron'."""
    created_task_names: list[str] = []
    original_create_task = asyncio.create_task

    def tracking_create_task(coro, *, name=None, **kwargs):
        t = original_create_task(coro, name=name, **kwargs)
        if name is not None:
            created_task_names.append(name)
        return t

    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir(parents=True, exist_ok=True)

    mock_pool = AsyncMock()
    mock_pool.start_for_space = AsyncMock(return_value=None)
    mock_pool.stop_all = AsyncMock(return_value=None)
    mock_pool.list_all = MagicMock(return_value=[])

    # board() needs to return something with .active
    from types import SimpleNamespace
    mock_board = SimpleNamespace(active=[])
    mock_store = AsyncMock()
    mock_store.board = MagicMock(return_value=mock_board)
    mock_store.reload_all = AsyncMock(return_value=None)
    mock_store.archive_stale_done_tasks = AsyncMock(return_value=0)
    mock_store.count = MagicMock(return_value=0)

    with (
        patch("app.main.SPACES_DIR", spaces_dir),
        patch("app.main.LEGACY_TASKS_DIR", tmp_path / "tasks"),
        patch("app.main.LEGACY_WORKSPACES_DIR", tmp_path / "workspaces"),
        patch("app.main.asyncio.create_task", side_effect=tracking_create_task),
        patch("app.main.watch_spaces_dir", _noop_coro),
        patch("app.main.auto_archive_loop", _noop_coro),
        patch("app.main.memory_prune_loop", _noop_coro),
        patch("app.main.discovery_refresh_loop", _noop_coro),
        patch("app.main.evolve_tools_loop", _noop_coro),
        patch("app.main.cron_loop", _noop_coro),
        patch("app.main.WorkerPool", return_value=mock_pool),
        patch("app.main.TaskStore", return_value=mock_store),
        patch("app.main.SpaceStore") as mock_space_store_cls,
        patch("app.main.MemoryStore"),
        patch("app.main.HarnessStore"),
        patch("app.main.StatsStore"),
        patch("app.main.TraceStore"),
        patch("app.main.TestReportStore"),
    ):
        mock_space_store = AsyncMock()
        mock_space_store.reload_all = AsyncMock(return_value=None)
        mock_space_store.count = MagicMock(return_value=1)
        mock_space_store.list_all = MagicMock(return_value=[])
        mock_space_store_cls.return_value = mock_space_store

        from fastapi import FastAPI
        from app.main import lifespan

        test_app = FastAPI(lifespan=lifespan)

        async with lifespan(test_app):
            pass

    assert "cron" in created_task_names, (
        f"Expected 'cron' task in created tasks; got: {created_task_names}"
    )


@pytest.mark.asyncio
async def test_lifespan_cron_task_cancelled_on_shutdown(tmp_path):
    """The cron asyncio task must be done (cancelled or stopped) after lifespan exits."""
    cron_task_holder: list[asyncio.Task] = []
    original_create_task = asyncio.create_task

    def tracking_create_task(coro, *, name=None, **kwargs):
        t = original_create_task(coro, name=name, **kwargs)
        if name == "cron":
            cron_task_holder.append(t)
        return t

    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir(parents=True, exist_ok=True)

    mock_pool = AsyncMock()
    mock_pool.start_for_space = AsyncMock(return_value=None)
    mock_pool.stop_all = AsyncMock(return_value=None)
    mock_pool.list_all = MagicMock(return_value=[])

    from types import SimpleNamespace
    mock_board = SimpleNamespace(active=[])
    mock_store = AsyncMock()
    mock_store.board = MagicMock(return_value=mock_board)
    mock_store.reload_all = AsyncMock(return_value=None)
    mock_store.count = MagicMock(return_value=0)

    with (
        patch("app.main.SPACES_DIR", spaces_dir),
        patch("app.main.LEGACY_TASKS_DIR", tmp_path / "tasks"),
        patch("app.main.LEGACY_WORKSPACES_DIR", tmp_path / "workspaces"),
        patch("app.main.asyncio.create_task", side_effect=tracking_create_task),
        patch("app.main.watch_spaces_dir", _noop_coro),
        patch("app.main.auto_archive_loop", _noop_coro),
        patch("app.main.memory_prune_loop", _noop_coro),
        patch("app.main.discovery_refresh_loop", _noop_coro),
        patch("app.main.evolve_tools_loop", _noop_coro),
        patch("app.main.cron_loop", _noop_coro),
        patch("app.main.WorkerPool", return_value=mock_pool),
        patch("app.main.TaskStore", return_value=mock_store),
        patch("app.main.SpaceStore") as mock_space_store_cls,
        patch("app.main.MemoryStore"),
        patch("app.main.HarnessStore"),
        patch("app.main.StatsStore"),
        patch("app.main.TraceStore"),
        patch("app.main.TestReportStore"),
    ):
        mock_space_store = AsyncMock()
        mock_space_store.reload_all = AsyncMock(return_value=None)
        mock_space_store.count = MagicMock(return_value=1)
        mock_space_store.list_all = MagicMock(return_value=[])
        mock_space_store_cls.return_value = mock_space_store

        from fastapi import FastAPI
        from app.main import lifespan

        test_app = FastAPI(lifespan=lifespan)

        async with lifespan(test_app):
            pass  # exit triggers finally block → stop_event.set() + task cancellation

    assert cron_task_holder, "Expected a 'cron' asyncio.Task to be created"
    cron_task = cron_task_holder[0]
    assert cron_task.done(), "cron task should be done after lifespan exits"


# ---------------------------------------------------------------------------
# Missing import guard
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock  # noqa: E402 — after local helpers
