"""Tests: run_id propagates through HarnessExecutor.execute() (I4)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.logging_config import configure_logging, _run_id_var
from app.harnesses.executor import HarnessExecutor


@pytest.fixture(autouse=True)
def json_logging():
    configure_logging()
    yield


def _make_executor() -> HarnessExecutor:
    store = MagicMock()
    worker_protocol = MagicMock()
    tools_resolver = MagicMock(return_value=None)
    return HarnessExecutor(store, worker_protocol, tools_resolver)


class TestExecutorRunIdBinding:
    @pytest.mark.asyncio
    async def test_execute_binds_run_id(self):
        """HarnessExecutor.execute() binds run_goal_id as run_id."""
        captured: list[str | None] = []
        executor = _make_executor()

        async def fake_body(run_goal_id, harness, space):
            captured.append(_run_id_var.get())
            return MagicMock()

        with patch.object(executor, "_execute_body", fake_body):
            harness = MagicMock()
            space = MagicMock()
            await executor.execute("run-goal-123", harness, space)

        assert captured and captured[0] == "run-goal-123"

    @pytest.mark.asyncio
    async def test_execute_resets_run_id_after_return(self):
        """run_id is reset to None after execute() completes."""
        executor = _make_executor()

        async def fake_body(run_goal_id, harness, space):
            return MagicMock()

        with patch.object(executor, "_execute_body", fake_body):
            await executor.execute("run-goal-456", MagicMock(), MagicMock())

        assert _run_id_var.get() is None

    @pytest.mark.asyncio
    async def test_execute_resets_run_id_on_exception(self):
        """run_id is reset even when _execute_body raises."""
        executor = _make_executor()

        async def raise_body(run_goal_id, harness, space):
            raise RuntimeError("executor crashed")

        with patch.object(executor, "_execute_body", raise_body):
            with pytest.raises(RuntimeError):
                await executor.execute("run-goal-789", MagicMock(), MagicMock())

        assert _run_id_var.get() is None

    @pytest.mark.asyncio
    async def test_execute_uses_run_goal_id_as_run_id(self):
        """The run_id key matches run_goal_id passed to execute()."""
        captured: list[str | None] = []
        executor = _make_executor()

        async def fake_body(run_goal_id, harness, space):
            captured.append(_run_id_var.get())
            return MagicMock()

        with patch.object(executor, "_execute_body", fake_body):
            await executor.execute("specific-run-id", MagicMock(), MagicMock())

        assert captured[0] == "specific-run-id"
