"""Tests for TRUSTED_MARKETPLACE_SOURCES allowlist in plugins.py."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

import app.tools.plugins as plugins_module
from app.tools.plugins import (
    TRUSTED_MARKETPLACE_SOURCES_ENV_VAR,
    _get_trusted_sources,
    add_marketplace,
    install,
)


# ---------------------------------------------------------------------------
# _get_trusted_sources
# ---------------------------------------------------------------------------


def test_get_trusted_sources_default_unrestricted():
    """Without TRUSTED_MARKETPLACE_SOURCES set, all sources are allowed."""
    sources = _get_trusted_sources()
    assert isinstance(sources, frozenset)
    assert len(sources) == 0


def test_get_trusted_sources_empty_env(monkeypatch: pytest.MonkeyPatch):
    """Explicit empty env var means unrestricted (empty frozenset)."""
    monkeypatch.setenv(TRUSTED_MARKETPLACE_SOURCES_ENV_VAR, "")
    assert _get_trusted_sources() == frozenset()


def test_get_trusted_sources_single(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(TRUSTED_MARKETPLACE_SOURCES_ENV_VAR, "https://trusted.example.com")
    assert _get_trusted_sources() == frozenset({"https://trusted.example.com"})


def test_get_trusted_sources_multiple(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        TRUSTED_MARKETPLACE_SOURCES_ENV_VAR,
        "https://a.example.com, https://b.example.com",
    )
    assert _get_trusted_sources() == frozenset(
        {"https://a.example.com", "https://b.example.com"}
    )


# ---------------------------------------------------------------------------
# add_marketplace — source validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_marketplace_allowed_source(monkeypatch: pytest.MonkeyPatch):
    """Trusted source is accepted and CLI is invoked."""
    trusted_url = "https://trusted.marketplace.com"
    monkeypatch.setenv(TRUSTED_MARKETPLACE_SOURCES_ENV_VAR, trusted_url)
    with patch.object(
        plugins_module, "_run_plugin_cmd", new=AsyncMock(return_value=("[]", ""))
    ) as mock_cmd:
        await add_marketplace(trusted_url)
    assert mock_cmd.call_count >= 1


@pytest.mark.asyncio
async def test_add_marketplace_rejected_source(monkeypatch: pytest.MonkeyPatch):
    """Untrusted source raises ValueError with informative message."""
    monkeypatch.setenv(TRUSTED_MARKETPLACE_SOURCES_ENV_VAR, "https://trusted.example.com")
    with pytest.raises(ValueError, match="not in TRUSTED_MARKETPLACE_SOURCES"):
        await add_marketplace("https://untrusted.attacker.com")


@pytest.mark.asyncio
async def test_add_marketplace_unrestricted_when_unset(monkeypatch: pytest.MonkeyPatch):
    """Without the env var, any valid source is accepted."""
    monkeypatch.delenv(TRUSTED_MARKETPLACE_SOURCES_ENV_VAR, raising=False)
    with patch.object(
        plugins_module, "_run_plugin_cmd", new=AsyncMock(return_value=("[]", ""))
    ):
        await add_marketplace("https://any.source.example.com")


# ---------------------------------------------------------------------------
# install — source provenance check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_allowed_source(monkeypatch: pytest.MonkeyPatch):
    """Plugin whose source matches trusted list is installed successfully."""
    trusted_url = "https://trusted.marketplace.com"
    monkeypatch.setenv(TRUSTED_MARKETPLACE_SOURCES_ENV_VAR, trusted_url)
    available_json = json.dumps({
        "installed": [],
        "available": [
            {
                "pluginId": "my-plugin",
                "name": "My Plugin",
                "source": trusted_url,
                "installCount": 1,
            }
        ],
    })
    with patch.object(
        plugins_module,
        "_run_plugin_cmd",
        new=AsyncMock(side_effect=[
            (available_json, ""),   # LIST_PLUGINS_CMD for source check
            ("", ""),                # install cmd
            (available_json, ""),   # list_plugins() after install
            ("[]", ""),              # list_marketplaces()
        ]),
    ):
        result = await install("my-plugin")
    assert result is not None


@pytest.mark.asyncio
async def test_install_rejected_source(monkeypatch: pytest.MonkeyPatch):
    """Plugin from untrusted source raises ValueError."""
    monkeypatch.setenv(TRUSTED_MARKETPLACE_SOURCES_ENV_VAR, "https://trusted.example.com")
    available_json = json.dumps({
        "installed": [],
        "available": [
            {
                "pluginId": "evil-plugin",
                "name": "Evil Plugin",
                "source": "https://attacker.com/evil",
                "installCount": 0,
            }
        ],
    })
    with patch.object(
        plugins_module,
        "_run_plugin_cmd",
        new=AsyncMock(return_value=(available_json, "")),
    ):
        with pytest.raises(ValueError, match="not in TRUSTED_MARKETPLACE_SOURCES"):
            await install("evil-plugin")


@pytest.mark.asyncio
async def test_install_unknown_plugin_allowed(monkeypatch: pytest.MonkeyPatch):
    """Plugin not in available list (unknown source) is allowed through."""
    monkeypatch.setenv(TRUSTED_MARKETPLACE_SOURCES_ENV_VAR, "https://trusted.example.com")
    available_json = json.dumps({"installed": [], "available": []})
    with patch.object(
        plugins_module,
        "_run_plugin_cmd",
        new=AsyncMock(side_effect=[
            (available_json, ""),   # LIST_PLUGINS_CMD for source check
            ("", ""),                # install cmd
            (available_json, ""),   # list_plugins() after install
            ("[]", ""),              # list_marketplaces()
        ]),
    ):
        result = await install("unknown-plugin")
    assert result is not None


@pytest.mark.asyncio
async def test_install_unrestricted_when_unset(monkeypatch: pytest.MonkeyPatch):
    """Without the env var, no provenance check runs (no extra LIST_PLUGINS_CMD call)."""
    monkeypatch.delenv(TRUSTED_MARKETPLACE_SOURCES_ENV_VAR, raising=False)
    installed_json = json.dumps({"installed": [], "available": []})
    call_args_list: list[list[str]] = []

    async def mock_cmd(args: list[str]):
        call_args_list.append(args)
        return (installed_json, "")

    with patch.object(plugins_module, "_run_plugin_cmd", new=mock_cmd):
        await install("any-plugin")

    list_plugins_cmd = list(plugins_module.LIST_PLUGINS_CMD)
    # Only the post-install list_plugins() call should hit LIST_PLUGINS_CMD; not a pre-check
    list_calls = [a for a in call_args_list if a == list_plugins_cmd]
    assert len(list_calls) == 1, (
        "With no TRUSTED_MARKETPLACE_SOURCES, only one LIST_PLUGINS_CMD call expected (post-install)"
    )
