"""Tests for app.notifier.notify_state_change (I6)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.notifier import notify_state_change


class TestNotifyStateChange:
    @pytest.mark.asyncio
    async def test_no_op_when_url_unset(self, monkeypatch):
        """When CRONOS_NOTIFY_URL is not set, no HTTP request is made."""
        monkeypatch.delenv("CRONOS_NOTIFY_URL", raising=False)
        # Should complete without any error or HTTP call.
        with patch("httpx.AsyncClient") as mock_client:
            await notify_state_change("t1", "My Task", "waiting", "WAIT", "needs input")
        mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_op_when_url_empty(self, monkeypatch):
        """When CRONOS_NOTIFY_URL is empty string, no HTTP request is made."""
        monkeypatch.setenv("CRONOS_NOTIFY_URL", "")
        with patch("httpx.AsyncClient") as mock_client:
            await notify_state_change("t1", "My Task", "done", None, None)
        mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_posts_to_configured_url(self, monkeypatch):
        """Sends POST to CRONOS_NOTIFY_URL with correct payload."""
        monkeypatch.setenv("CRONOS_NOTIFY_URL", "http://notify.example.com/hook")
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_post = AsyncMock(return_value=mock_response)
        mock_client_instance = AsyncMock()
        mock_client_instance.post = mock_post
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            await notify_state_change("t2", "Task Two", "done", "DONE", "all good")

        mock_post.assert_called_once()
        url_arg = mock_post.call_args[0][0]
        assert url_arg == "http://notify.example.com/hook"

    @pytest.mark.asyncio
    async def test_payload_matches_r6_schema(self, monkeypatch):
        """Payload contains task_id, task_title, status, exit_reason, summary."""
        monkeypatch.setenv("CRONOS_NOTIFY_URL", "http://hook.test/")
        mock_response = MagicMock(status_code=204)

        captured_payload = {}

        async def fake_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            return mock_response

        mock_client_instance = AsyncMock()
        mock_client_instance.post = fake_post
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            await notify_state_change("t3", "Task Three", "waiting", "WAIT", "needs review")

        assert captured_payload["task_id"] == "t3"
        assert captured_payload["task_title"] == "Task Three"
        assert captured_payload["status"] == "waiting"
        assert captured_payload["exit_reason"] == "WAIT"
        assert captured_payload["summary"] == "needs review"

    @pytest.mark.asyncio
    async def test_exception_does_not_propagate(self, monkeypatch):
        """HTTP errors are swallowed; notify_state_change never raises."""
        monkeypatch.setenv("CRONOS_NOTIFY_URL", "http://unreachable.test/")

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(side_effect=ConnectionError("no route"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            # Should not raise
            await notify_state_change("t4", "Task Four", "waiting", None, None)

    @pytest.mark.asyncio
    async def test_timeout_does_not_propagate(self, monkeypatch):
        """Timeout errors are swallowed."""
        import httpx
        monkeypatch.setenv("CRONOS_NOTIFY_URL", "http://slow.test/")

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            await notify_state_change("t5", "Task Five", "done", "DONE", None)

    @pytest.mark.asyncio
    async def test_timeout_is_5_seconds(self, monkeypatch):
        """httpx.AsyncClient is constructed with timeout=5.0."""
        monkeypatch.setenv("CRONOS_NOTIFY_URL", "http://timing.test/")
        mock_response = MagicMock(status_code=200)

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client_instance) as mock_class:
            await notify_state_change("t6", "Task Six", "done", None, None)

        mock_class.assert_called_once_with(timeout=5.0)
