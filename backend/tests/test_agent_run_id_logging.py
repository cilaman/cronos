"""Tests: run_id / task_id propagates through run_agent (I3)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.logging_config import configure_logging, _run_id_var, _task_id_var


@pytest.fixture(autouse=True)
def json_logging():
    configure_logging()
    yield


def _make_task(task_id: str = "t-agent-1", space_id: str = "sp1") -> MagicMock:
    task = MagicMock()
    task.id = task_id
    task.space_id = space_id
    task.agent_model = "default"
    task.agent_mode = "auto"
    task.brief = "do something"
    task.title = "test task"
    task.pending_messages = []
    task.claude_session_id = None
    return task


class TestRunAgentRunIdBinding:
    @pytest.mark.asyncio
    async def test_run_agent_binds_run_id(self):
        """run_agent wraps its body with bind_run_context; run_id is set inside."""
        captured: list[str | None] = []
        task = _make_task("t-abc")

        async def fake_body(tsk, **kwargs):
            captured.append(_run_id_var.get())
            return MagicMock()

        with patch("app.agent._run_agent_body", fake_body):
            from app.agent import run_agent
            await run_agent(task, user_message=None, on_event=AsyncMock())

        assert captured and captured[0] == "t-abc"

    @pytest.mark.asyncio
    async def test_run_agent_binds_task_id(self):
        """task_id is also bound when run_agent is called."""
        captured: list[str | None] = []
        task = _make_task("t-xyz")

        async def fake_body(tsk, **kwargs):
            captured.append(_task_id_var.get())
            return MagicMock()

        with patch("app.agent._run_agent_body", fake_body):
            from app.agent import run_agent
            await run_agent(task, user_message=None, on_event=AsyncMock())

        assert captured and captured[0] == "t-xyz"

    @pytest.mark.asyncio
    async def test_run_id_reset_after_run_agent(self):
        """run_id is reset to None after run_agent returns."""
        task = _make_task("t-reset")

        async def fake_body(tsk, **kwargs):
            return MagicMock()

        with patch("app.agent._run_agent_body", fake_body):
            from app.agent import run_agent
            await run_agent(task, user_message=None, on_event=AsyncMock())

        assert _run_id_var.get() is None
        assert _task_id_var.get() is None

    @pytest.mark.asyncio
    async def test_run_id_reset_on_exception(self):
        """run_id is reset even if _run_agent_body raises."""
        task = _make_task("t-exc")

        async def raise_body(tsk, **kwargs):
            raise RuntimeError("agent crashed")

        with patch("app.agent._run_agent_body", raise_body):
            from app.agent import run_agent
            with pytest.raises(RuntimeError):
                await run_agent(task, user_message=None, on_event=AsyncMock())

        assert _run_id_var.get() is None

    @pytest.mark.asyncio
    async def test_no_leak_to_concurrent_task(self):
        """run_id in run_agent does not leak to a concurrent sibling task."""
        leaked: list[str | None] = []

        task = _make_task("t-leak")

        async def fake_body(tsk, **kwargs):
            await asyncio.sleep(0)
            return MagicMock()

        async def sibling():
            await asyncio.sleep(0)
            leaked.append(_run_id_var.get())

        with patch("app.agent._run_agent_body", fake_body):
            from app.agent import run_agent
            await asyncio.gather(
                run_agent(task, user_message=None, on_event=AsyncMock()),
                sibling(),
            )

        assert None in leaked, "Sibling should see no run_id binding"
