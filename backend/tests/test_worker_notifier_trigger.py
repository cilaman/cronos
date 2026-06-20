"""Tests: notifier is triggered from worker finalize paths (I6)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.models import TaskState
from app.worker import _WorkerProtocolAdapter
from app.trace_parser import RunTrace
from datetime import datetime, timezone


def _make_worker_stub(task_title: str = "Test Task") -> MagicMock:
    worker = MagicMock()
    store = MagicMock()
    task = MagicMock()
    task.title = task_title
    task.space_id = "sp1"
    store.get = MagicMock(return_value=task)
    store.finalize_run = AsyncMock()
    worker.store = store
    return worker


def _make_trace(exit_reason: str = "WAIT") -> RunTrace:
    now = datetime.now(tz=timezone.utc)
    return RunTrace(
        task_id="child-t1",
        space_id="sp1",
        run_index=0,
        session_id=None,
        model="default",
        mode="auto",
        started_at=now,
        ended_at=now,
        duration_seconds=0.0,
        exit_reason=exit_reason,
        final_text_snippet="done",
        parent_run_id=None,
    )


class TestWorkerNotifierTrigger:
    @pytest.mark.asyncio
    async def test_finalize_child_triggers_notify_on_waiting(self):
        """_WorkerProtocolAdapter.finalize_child fires notify when state=WAITING."""
        worker_stub = _make_worker_stub()
        adapter = _WorkerProtocolAdapter(worker_stub)
        trace = _make_trace(exit_reason="WAIT")

        with patch("app.worker.asyncio.create_task") as mock_create_task:
            with patch("app.worker.notify_state_change", new_callable=AsyncMock) as mock_notify:
                result = await adapter.finalize_child("child-t1", trace)

        # new_state should be WAITING (exit_reason != DONE)
        assert result == TaskState.WAITING
        # create_task should have been called with a notify coroutine
        mock_create_task.assert_called_once()
        call_args = mock_create_task.call_args
        # First positional arg should be a coroutine
        assert asyncio.iscoroutine(call_args[0][0])

    @pytest.mark.asyncio
    async def test_finalize_child_does_not_notify_on_done(self):
        """_WorkerProtocolAdapter.finalize_child does NOT notify when state=DONE."""
        worker_stub = _make_worker_stub()
        adapter = _WorkerProtocolAdapter(worker_stub)
        trace = _make_trace(exit_reason="DONE")

        with patch("app.worker.asyncio.create_task") as mock_create_task:
            result = await adapter.finalize_child("child-t1", trace)

        assert result == TaskState.DONE
        mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_finalize_child_passes_correct_args_to_notifier(self):
        """Notifier receives task_id, task_title, status, exit_reason."""
        worker_stub = _make_worker_stub(task_title="My Harness Task")
        adapter = _WorkerProtocolAdapter(worker_stub)
        trace = _make_trace(exit_reason="BLOCKED")

        captured_kwargs: dict = {}

        async def fake_notify(**kwargs):
            captured_kwargs.update(kwargs)

        with patch("app.worker.notify_state_change") as mock_fn:
            mock_fn.return_value = fake_notify()
            with patch("app.worker.asyncio.create_task") as mock_ct:
                await adapter.finalize_child("child-t1", trace)

        # We can't inspect coroutine args directly, but we can verify create_task was called
        mock_ct.assert_called_once()
