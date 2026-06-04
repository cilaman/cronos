"""
Tests for backend/app/harnesses/run_trigger.py

Covers enqueue_harness_run() in isolation — verifying that:
  1. A task is created in the task_store with the expected title and brief.
  2. A RunSummary is appended to the run index under the correct harness name.
  3. The run_id is registered in the worker's reverse-lookup cache.
  4. The function works correctly when the WorkerPool has no worker for the
     space (worker is None).
  5. The returned RunSummary has the correct fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses.run_trigger import enqueue_harness_run
from app.harnesses.run_index import RunSummary, read_index


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SPACE_ID = "space-trigger-test"
HARNESS_NAME = "my-harness"
TRIGGERED_AT = "2026-01-01T12:00:00Z"
BRIEF = "Test brief for harness run."
FAKE_RUN_ID = "task-run-001"


@pytest.fixture
def fake_task():
    t = MagicMock()
    t.id = FAKE_RUN_ID
    return t


@pytest.fixture
def task_store(fake_task):
    """Mock TaskStore that returns fake_task from create() and succeeds on transition()."""
    store = MagicMock()
    store.create = AsyncMock(return_value=fake_task)
    store.transition = AsyncMock(return_value=fake_task)
    return store


@pytest.fixture
def mock_worker():
    """Mock Worker with register_run and enqueue stubs."""
    worker = MagicMock()
    worker.register_run = MagicMock()
    worker.enqueue = AsyncMock()
    return worker


@pytest.fixture
def worker_pool(mock_worker):
    """Mock WorkerPool that returns mock_worker for any space_id."""
    pool = MagicMock()
    pool.get = MagicMock(return_value=mock_worker)
    return pool


@pytest.fixture
def worker_pool_no_worker():
    """Mock WorkerPool that returns None (space has no worker)."""
    pool = MagicMock()
    pool.get = MagicMock(return_value=None)
    return pool


@pytest.fixture
def space_dir(tmp_path) -> Path:
    """A temporary space directory (the .cronos subdirs are created on demand)."""
    d = tmp_path / SPACE_ID
    d.mkdir()
    return d


@pytest.fixture
def harness_store():
    """Minimal harness_store mock (not called by run_trigger directly)."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_enqueue_creates_task_with_correct_title(
    task_store, harness_store, worker_pool, space_dir
):
    """enqueue_harness_run calls task_store.create with the canonical title."""
    await enqueue_harness_run(
        task_store,
        harness_store,
        worker_pool,
        SPACE_ID,
        space_dir,
        HARNESS_NAME,
        brief=BRIEF,
        triggered_at=TRIGGERED_AT,
    )

    task_store.create.assert_awaited_once()
    call_kwargs = task_store.create.call_args.kwargs
    assert call_kwargs["title"] == f"Harness run: {HARNESS_NAME}"
    assert call_kwargs["brief"] == BRIEF
    assert call_kwargs["space_id"] == SPACE_ID


async def test_enqueue_appends_run_to_index(
    task_store, harness_store, worker_pool, space_dir
):
    """enqueue_harness_run appends a RunSummary to the run index for harness_name."""
    await enqueue_harness_run(
        task_store,
        harness_store,
        worker_pool,
        SPACE_ID,
        space_dir,
        HARNESS_NAME,
        brief=BRIEF,
        triggered_at=TRIGGERED_AT,
    )

    entries = await read_index(space_dir, HARNESS_NAME)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.run_id == FAKE_RUN_ID
    assert entry.harness_id == HARNESS_NAME
    assert entry.status == "running"
    assert entry.triggered_at == TRIGGERED_AT


async def test_enqueue_registers_run_in_worker_cache(
    task_store, harness_store, worker_pool, mock_worker, space_dir
):
    """enqueue_harness_run registers the run_id in the worker's reverse-lookup cache."""
    await enqueue_harness_run(
        task_store,
        harness_store,
        worker_pool,
        SPACE_ID,
        space_dir,
        HARNESS_NAME,
        brief=BRIEF,
        triggered_at=TRIGGERED_AT,
    )

    mock_worker.register_run.assert_called_once_with(FAKE_RUN_ID, SPACE_ID)
    mock_worker.enqueue.assert_awaited_once_with(FAKE_RUN_ID)


async def test_enqueue_with_no_worker_does_not_raise(
    task_store, harness_store, worker_pool_no_worker, space_dir
):
    """enqueue_harness_run succeeds gracefully when the space has no worker."""
    summary = await enqueue_harness_run(
        task_store,
        harness_store,
        worker_pool_no_worker,
        SPACE_ID,
        space_dir,
        HARNESS_NAME,
        brief=BRIEF,
        triggered_at=TRIGGERED_AT,
    )

    # The run index must still be populated even without a worker.
    entries = await read_index(space_dir, HARNESS_NAME)
    assert len(entries) == 1
    assert entries[0].run_id == FAKE_RUN_ID
    assert entries[0].status == "running"

    # The returned summary should be valid.
    assert isinstance(summary, RunSummary)
    assert summary.run_id == FAKE_RUN_ID


async def test_enqueue_returns_run_summary_with_correct_fields(
    task_store, harness_store, worker_pool, space_dir
):
    """enqueue_harness_run returns a RunSummary with run_id, harness_id, status, triggered_at."""
    summary = await enqueue_harness_run(
        task_store,
        harness_store,
        worker_pool,
        SPACE_ID,
        space_dir,
        HARNESS_NAME,
        brief=BRIEF,
        triggered_at=TRIGGERED_AT,
    )

    assert isinstance(summary, RunSummary)
    assert summary.run_id == FAKE_RUN_ID
    assert summary.harness_id == HARNESS_NAME
    assert summary.status == "running"
    assert summary.triggered_at == TRIGGERED_AT
    assert summary.finished_at is None


async def test_enqueue_transitions_task_to_active(
    task_store, harness_store, worker_pool, space_dir
):
    """enqueue_harness_run transitions the created task to ACTIVE state."""
    from app.models import TaskState
    from app.storage import USER_TRANSITIONS

    await enqueue_harness_run(
        task_store,
        harness_store,
        worker_pool,
        SPACE_ID,
        space_dir,
        HARNESS_NAME,
        brief=BRIEF,
        triggered_at=TRIGGERED_AT,
    )

    task_store.transition.assert_awaited_once_with(
        FAKE_RUN_ID, TaskState.ACTIVE, allowed=USER_TRANSITIONS
    )


async def test_enqueue_with_transition_failure_still_returns_summary(
    task_store, harness_store, worker_pool, space_dir
):
    """enqueue_harness_run logs and continues if the ACTIVE transition fails."""
    task_store.transition = AsyncMock(side_effect=Exception("transition error"))

    summary = await enqueue_harness_run(
        task_store,
        harness_store,
        worker_pool,
        SPACE_ID,
        space_dir,
        HARNESS_NAME,
        brief=BRIEF,
        triggered_at=TRIGGERED_AT,
    )

    # Function must return a RunSummary despite the transition failure.
    assert isinstance(summary, RunSummary)
    assert summary.run_id == FAKE_RUN_ID
    assert summary.status == "running"
