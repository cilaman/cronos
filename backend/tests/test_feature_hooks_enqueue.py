"""Tests for feature_hooks.enqueue_feature_decomposition — I5 acceptance criteria.

Verifies:
- Pool configured → pool.enqueue called once with correct args (space_id, task.id).
- Pool None → WARNING logged, no exception raised.
- configure_pool() wires the module-level _worker_pool.
- Signature unchanged: async def enqueue_feature_decomposition(task: "Task") -> None.
- Does NOT mutate feature_state.
"""

from __future__ import annotations

import inspect
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.feature_hooks as fh
from app.feature_hooks import enqueue_feature_decomposition
from app.models import FeatureState, Task, TaskState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(**kwargs) -> Task:
    defaults = dict(
        id="task-feat-1",
        space_id="space-abc",
        title="My feature",
        state=TaskState.ACTIVE,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
        type="feature",
        feature_state=FeatureState.PROCESSING,
        feature_key="FEAT-001",
    )
    defaults.update(kwargs)
    return Task(**defaults)


def _make_mock_pool() -> MagicMock:
    """Return a MagicMock WorkerPool with async enqueue."""
    pool = MagicMock()
    pool.enqueue = AsyncMock()
    return pool


# ---------------------------------------------------------------------------
# Signature contract
# ---------------------------------------------------------------------------


def test_enqueue_feature_decomposition_is_async():
    """enqueue_feature_decomposition must be a coroutine function."""
    assert inspect.iscoroutinefunction(enqueue_feature_decomposition), (
        "enqueue_feature_decomposition must be async def"
    )


def test_enqueue_feature_decomposition_signature():
    """Signature must accept exactly one positional arg: task."""
    sig = inspect.signature(enqueue_feature_decomposition)
    params = list(sig.parameters.keys())
    assert params == ["task"], f"Expected ['task'], got {params}"


# ---------------------------------------------------------------------------
# configure_pool and module-level _worker_pool
# ---------------------------------------------------------------------------


def test_configure_pool_sets_module_level_pool():
    """configure_pool must set fh._worker_pool to the supplied pool."""
    original = fh._worker_pool
    try:
        mock_pool = _make_mock_pool()
        fh.configure_pool(mock_pool)
        assert fh._worker_pool is mock_pool
    finally:
        fh._worker_pool = original


def test_configure_pool_is_idempotent():
    """configure_pool may be called multiple times; last call wins."""
    original = fh._worker_pool
    try:
        pool_a = _make_mock_pool()
        pool_b = _make_mock_pool()
        fh.configure_pool(pool_a)
        assert fh._worker_pool is pool_a
        fh.configure_pool(pool_b)
        assert fh._worker_pool is pool_b
    finally:
        fh._worker_pool = original


# ---------------------------------------------------------------------------
# Pool configured → enqueue called once with correct args
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_calls_pool_enqueue_with_correct_args():
    """When pool is set, pool.enqueue must be called once with (space_id, task.id)."""
    task = _make_task()
    mock_pool = _make_mock_pool()

    original = fh._worker_pool
    try:
        fh._worker_pool = mock_pool
        result = await enqueue_feature_decomposition(task)
    finally:
        fh._worker_pool = original

    mock_pool.enqueue.assert_awaited_once_with(task.space_id, task.id)
    assert result is None


@pytest.mark.asyncio
async def test_enqueue_passes_space_id_not_task_id_for_space():
    """Verify the positional order: enqueue(space_id, task.id) not reversed."""
    task = _make_task(space_id="space-xyz", id="task-999")
    mock_pool = _make_mock_pool()

    original = fh._worker_pool
    try:
        fh._worker_pool = mock_pool
        await enqueue_feature_decomposition(task)
    finally:
        fh._worker_pool = original

    call_args = mock_pool.enqueue.call_args
    # First positional arg must be the space_id
    assert call_args.args[0] == "space-xyz", (
        f"First arg should be space_id 'space-xyz', got {call_args.args[0]}"
    )
    # Second positional arg must be the task id
    assert call_args.args[1] == "task-999", (
        f"Second arg should be task.id 'task-999', got {call_args.args[1]}"
    )


@pytest.mark.asyncio
async def test_enqueue_called_exactly_once_per_invocation():
    """enqueue must be called exactly once per function invocation."""
    task = _make_task()
    mock_pool = _make_mock_pool()

    original = fh._worker_pool
    try:
        fh._worker_pool = mock_pool
        await enqueue_feature_decomposition(task)
        await enqueue_feature_decomposition(task)
    finally:
        fh._worker_pool = original

    assert mock_pool.enqueue.await_count == 2, (
        f"Expected 2 enqueue calls for 2 invocations, got {mock_pool.enqueue.await_count}"
    )


# ---------------------------------------------------------------------------
# Pool None → WARNING logged, no exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_no_op_when_pool_none(caplog):
    """When _worker_pool is None, must log WARNING and not raise."""
    task = _make_task()

    original = fh._worker_pool
    try:
        fh._worker_pool = None
        with caplog.at_level(logging.WARNING):
            result = await enqueue_feature_decomposition(task)
    finally:
        fh._worker_pool = original

    assert result is None
    # A WARNING must have been emitted
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) >= 1, "Expected at least one WARNING log when pool is None"
    # The warning message must reference the task id
    assert any(task.id in r.message for r in warning_records), (
        f"WARNING log must mention task.id={task.id!r}"
    )


@pytest.mark.asyncio
async def test_enqueue_no_exception_when_pool_none():
    """When pool is None, must complete without raising any exception."""
    task = _make_task()

    original = fh._worker_pool
    try:
        fh._worker_pool = None
        # Must not raise
        await enqueue_feature_decomposition(task)
    finally:
        fh._worker_pool = original


# ---------------------------------------------------------------------------
# feature_state not mutated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_does_not_mutate_feature_state():
    """enqueue_feature_decomposition must not change task.feature_state."""
    task = _make_task(feature_state=FeatureState.PROCESSING)
    mock_pool = _make_mock_pool()

    original_state = task.feature_state
    original = fh._worker_pool
    try:
        fh._worker_pool = mock_pool
        await enqueue_feature_decomposition(task)
    finally:
        fh._worker_pool = original

    assert task.feature_state == original_state, (
        "enqueue_feature_decomposition must not mutate task.feature_state"
    )


# ---------------------------------------------------------------------------
# configure_pool attribute exists
# ---------------------------------------------------------------------------


def test_configure_pool_function_exists():
    """configure_pool must be exported from feature_hooks."""
    assert hasattr(fh, "configure_pool"), "configure_pool must exist in feature_hooks"
    assert callable(fh.configure_pool), "configure_pool must be callable"


def test_worker_pool_attribute_exists():
    """_worker_pool module-level attribute must exist."""
    assert hasattr(fh, "_worker_pool"), "_worker_pool module attr must exist"


# ---------------------------------------------------------------------------
# P2-H: configure_store wires _task_store (feature_hooks.py line 53)
# ---------------------------------------------------------------------------


def test_configure_store_sets_module_level_store():
    """configure_store must set fh._task_store to the supplied store (line 53)."""
    from app.feature_hooks import configure_store

    original = fh._task_store
    try:
        mock_store = MagicMock()
        configure_store(mock_store)
        assert fh._task_store is mock_store, (
            "configure_store must assign the store to fh._task_store"
        )
    finally:
        fh._task_store = original


def test_configure_store_is_idempotent():
    """configure_store may be called multiple times; last call wins."""
    from app.feature_hooks import configure_store

    original = fh._task_store
    try:
        store_a = MagicMock()
        store_b = MagicMock()
        configure_store(store_a)
        assert fh._task_store is store_a
        configure_store(store_b)
        assert fh._task_store is store_b
    finally:
        fh._task_store = original


def test_configure_store_function_exists():
    """configure_store must be exported from feature_hooks."""
    assert hasattr(fh, "configure_store"), "configure_store must exist in feature_hooks"
    assert callable(fh.configure_store), "configure_store must be callable"


def test_task_store_attribute_exists():
    """_task_store module-level attribute must exist."""
    assert hasattr(fh, "_task_store"), "_task_store module attr must exist"
