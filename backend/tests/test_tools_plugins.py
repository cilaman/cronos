"""Tests for backend/app/tools/plugins.py (I2)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.plugins import (
    LIST_MARKETPLACES_CMD,
    LIST_PLUGINS_CMD,
    MARKETPLACE_NAME_PATTERN,
    MARKETPLACE_SOURCE_PATTERN,
    PLUGIN_ID_PATTERN,
    PluginCliError,
    _plugin_mutation_lock,
    _run_plugin_cmd,
    add_marketplace,
    disable,
    enable,
    install,
    list_marketplaces,
    list_plugins,
    plugin_components,
    remove_marketplace,
    uninstall,
)
from app.models import MarketplaceEntry, PluginsResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Return an async mock subprocess."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(
        return_value=(stdout.encode(), stderr.encode())
    )
    return proc


# ---------------------------------------------------------------------------
# Input-validation regex tests
# ---------------------------------------------------------------------------

class TestPluginIdPattern:
    def test_valid_simple(self):
        assert PLUGIN_ID_PATTERN.fullmatch("myplugin")
        assert PLUGIN_ID_PATTERN.fullmatch("my-plugin")
        assert PLUGIN_ID_PATTERN.fullmatch("my_plugin")

    def test_valid_with_marketplace(self):
        assert PLUGIN_ID_PATTERN.fullmatch("myplugin@mymarket")
        assert PLUGIN_ID_PATTERN.fullmatch("my-plugin@official")

    def test_invalid_spaces(self):
        assert not PLUGIN_ID_PATTERN.fullmatch("my plugin")

    def test_invalid_semicolon(self):
        assert not PLUGIN_ID_PATTERN.fullmatch("myplugin; rm -rf /")

    def test_invalid_double_at(self):
        assert not PLUGIN_ID_PATTERN.fullmatch("myplugin@@market")

    def test_empty(self):
        assert not PLUGIN_ID_PATTERN.fullmatch("")


class TestMarketplaceSourcePattern:
    def test_valid_https(self):
        assert MARKETPLACE_SOURCE_PATTERN.fullmatch("https://example.com/plugins")

    def test_valid_file(self):
        assert MARKETPLACE_SOURCE_PATTERN.fullmatch("file:///home/user/plugins")

    def test_invalid_http(self):
        assert not MARKETPLACE_SOURCE_PATTERN.fullmatch("http://example.com/plugins")

    def test_invalid_no_scheme(self):
        assert not MARKETPLACE_SOURCE_PATTERN.fullmatch("example.com/plugins")

    def test_invalid_with_space(self):
        assert not MARKETPLACE_SOURCE_PATTERN.fullmatch("https://example.com/pl ugins")


class TestMarketplaceNamePattern:
    def test_valid(self):
        assert MARKETPLACE_NAME_PATTERN.fullmatch("official")
        assert MARKETPLACE_NAME_PATTERN.fullmatch("my-market")
        assert MARKETPLACE_NAME_PATTERN.fullmatch("my_market")

    def test_invalid_space(self):
        assert not MARKETPLACE_NAME_PATTERN.fullmatch("my market")

    def test_invalid_slash(self):
        assert not MARKETPLACE_NAME_PATTERN.fullmatch("my/market")

    def test_empty(self):
        assert not MARKETPLACE_NAME_PATTERN.fullmatch("")


# ---------------------------------------------------------------------------
# PluginCliError tests
# ---------------------------------------------------------------------------

class TestPluginCliError:
    def test_attributes(self):
        err = PluginCliError(command=["claude", "plugin", "list"], returncode=1, stderr="not found")
        assert err.command == ["claude", "plugin", "list"]
        assert err.returncode == 1
        assert err.stderr == "not found"
        assert "exit 1" in str(err)

    def test_is_exception(self):
        with pytest.raises(PluginCliError):
            raise PluginCliError(command=["claude"], returncode=2, stderr="err")


# ---------------------------------------------------------------------------
# _run_plugin_cmd tests
# ---------------------------------------------------------------------------

class TestRunPluginCmd:
    async def test_success(self):
        proc = _make_proc(stdout='{"ok": true}', returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            stdout, stderr = await _run_plugin_cmd(["claude", "plugin", "list", "--json"])
        assert stdout == '{"ok": true}'
        assert stderr == ""

    async def test_non_zero_raises(self):
        proc = _make_proc(stdout="", stderr="not installed", returncode=1)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(PluginCliError) as exc_info:
                await _run_plugin_cmd(["claude", "plugin", "install", "myplugin"])
        assert exc_info.value.returncode == 1
        assert "not installed" in exc_info.value.stderr

    def test_non_claude_raises(self):
        with pytest.raises(AssertionError):
            asyncio.run(_run_plugin_cmd(["sh", "-c", "echo bad"]))

    def test_empty_list_raises(self):
        with pytest.raises(AssertionError):
            asyncio.run(_run_plugin_cmd([]))

    async def test_no_shell(self):
        """Ensure subprocess is never called with shell=True."""
        proc = _make_proc(stdout="[]", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await _run_plugin_cmd(["claude", "plugin", "marketplace", "list", "--json"])
        # create_subprocess_exec is not create_subprocess_shell — shell=True never reached
        mock_exec.assert_called_once()
        _, kwargs = mock_exec.call_args
        assert "shell" not in kwargs


# ---------------------------------------------------------------------------
# list_marketplaces tests
# ---------------------------------------------------------------------------

class TestListMarketplaces:
    async def test_empty(self):
        proc = _make_proc(stdout="[]", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await list_marketplaces()
        assert result == []

    async def test_parses_entries(self):
        payload = json.dumps([{"name": "official", "source": "https://example.com/plugins"}])
        proc = _make_proc(stdout=payload, returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await list_marketplaces()
        assert len(result) == 1
        assert result[0].name == "official"
        assert result[0].source == "https://example.com/plugins"

    async def test_cli_error_propagates(self):
        proc = _make_proc(stdout="", stderr="fail", returncode=1)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(PluginCliError):
                await list_marketplaces()

    async def test_json_parse_error(self):
        proc = _make_proc(stdout="not-json", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(PluginCliError) as exc_info:
                await list_marketplaces()
        assert "JSON parse error" in exc_info.value.stderr


# ---------------------------------------------------------------------------
# list_plugins tests
# ---------------------------------------------------------------------------

class TestListPlugins:
    async def test_empty(self):
        empty_plugins = json.dumps({"installed": [], "available": []})
        empty_markets = json.dumps([])

        call_count = 0

        async def fake_run(args):
            nonlocal call_count
            call_count += 1
            if "--available" in args:
                return empty_plugins, ""
            return empty_markets, ""

        with patch("app.tools.plugins._run_plugin_cmd", side_effect=fake_run):
            result = await list_plugins()
        assert isinstance(result, PluginsResponse)
        assert result.installed == []
        assert result.available == []
        assert result.marketplaces == []
        assert call_count == 2  # list_plugins + list_marketplaces

    async def test_parses_installed_and_available(self):
        plugins_payload = json.dumps({
            "installed": [{"id": "p1@official", "name": "p1", "enabled": True}],
            "available": [{"pluginId": "p2", "name": "p2", "installCount": 10}],
        })
        markets_payload = json.dumps([{"name": "official", "source": "https://example.com"}])

        async def fake_run(args):
            if "--available" in args:
                return plugins_payload, ""
            return markets_payload, ""

        with patch("app.tools.plugins._run_plugin_cmd", side_effect=fake_run):
            result = await list_plugins()
        assert len(result.installed) == 1
        assert result.installed[0].id == "p1@official"
        assert len(result.available) == 1
        assert result.available[0].installCount == 10
        assert len(result.marketplaces) == 1

    async def test_json_parse_error(self):
        async def fake_run(args):
            if "--available" in args:
                return "bad json", ""
            return "[]", ""

        with patch("app.tools.plugins._run_plugin_cmd", side_effect=fake_run):
            with pytest.raises(PluginCliError):
                await list_plugins()


# ---------------------------------------------------------------------------
# plugin_components tests
# ---------------------------------------------------------------------------

class TestPluginComponents:
    async def test_missing_dir_returns_empty(self):
        result = await plugin_components("/nonexistent/path", "myplugin")
        assert result == []

    async def test_scans_agents_and_skills(self, tmp_path: Path):
        plugin_dir = tmp_path / "myplugin"
        agents_dir = plugin_dir / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "myagent.md").write_text("# My Agent\nDescription here.")

        skills_dir = plugin_dir / "skills" / "myskill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("# My Skill")

        result = await plugin_components(str(plugin_dir), "myplugin")
        names = [e.name for e in result]
        assert "myplugin:myagent" in names
        assert "myplugin:myskill" in names

    async def test_scope_is_plugin(self, tmp_path: Path):
        plugin_dir = tmp_path / "myplugin"
        agents_dir = plugin_dir / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "agent1.md").write_text("# Agent 1")

        result = await plugin_components(str(plugin_dir), "myplugin")
        assert all(e.scope == "plugin" for e in result)

    async def test_namespaced_names(self, tmp_path: Path):
        plugin_dir = tmp_path / "myplugin"
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir(parents=True)
        (commands_dir / "cmd1.md").write_text("# Cmd 1")

        result = await plugin_components(str(plugin_dir), "myplugin")
        for entry in result:
            assert entry.name.startswith("myplugin:")


# ---------------------------------------------------------------------------
# Mutation function tests (install, uninstall, enable, disable)
# ---------------------------------------------------------------------------

class TestMutationFunctions:
    async def test_install_valid_id(self):
        empty_response = PluginsResponse()
        with patch("app.tools.plugins._run_plugin_cmd", new_callable=AsyncMock) as mock_cmd, \
             patch("app.tools.plugins.list_plugins", new_callable=AsyncMock, return_value=empty_response):
            await install("myplugin")
        mock_cmd.assert_called_once_with(["claude", "plugin", "install", "myplugin"])

    async def test_install_invalid_id_raises(self):
        with pytest.raises(ValueError, match="Invalid plugin_id"):
            await install("bad plugin; rm -rf /")

    async def test_uninstall_valid_id(self):
        empty_response = PluginsResponse()
        with patch("app.tools.plugins._run_plugin_cmd", new_callable=AsyncMock), \
             patch("app.tools.plugins.list_plugins", new_callable=AsyncMock, return_value=empty_response):
            result = await uninstall("myplugin@official")
        assert isinstance(result, PluginsResponse)

    async def test_uninstall_invalid_id_raises(self):
        with pytest.raises(ValueError, match="Invalid plugin_id"):
            await uninstall("bad plugin")

    async def test_enable_valid_id(self):
        empty_response = PluginsResponse()
        with patch("app.tools.plugins._run_plugin_cmd", new_callable=AsyncMock) as mock_cmd, \
             patch("app.tools.plugins.list_plugins", new_callable=AsyncMock, return_value=empty_response):
            await enable("myplugin")
        mock_cmd.assert_called_once_with(["claude", "plugin", "enable", "myplugin"])

    async def test_enable_invalid_id_raises(self):
        with pytest.raises(ValueError):
            await enable("bad/plugin")

    async def test_disable_valid_id(self):
        empty_response = PluginsResponse()
        with patch("app.tools.plugins._run_plugin_cmd", new_callable=AsyncMock) as mock_cmd, \
             patch("app.tools.plugins.list_plugins", new_callable=AsyncMock, return_value=empty_response):
            await disable("myplugin")
        mock_cmd.assert_called_once_with(["claude", "plugin", "disable", "myplugin"])

    async def test_disable_invalid_id_raises(self):
        with pytest.raises(ValueError):
            await disable("../evil")


# ---------------------------------------------------------------------------
# Marketplace mutation tests
# ---------------------------------------------------------------------------

class TestMarketplaceMutations:
    async def test_add_marketplace_valid(self):
        markets = [MarketplaceEntry(name="m", source="https://m.example.com")]
        with patch("app.tools.plugins._run_plugin_cmd", new_callable=AsyncMock) as mock_cmd, \
             patch("app.tools.plugins.list_marketplaces", new_callable=AsyncMock, return_value=markets):
            result = await add_marketplace("https://example.com/plugins")
        mock_cmd.assert_called_once_with(
            ["claude", "plugin", "marketplace", "add", "https://example.com/plugins"]
        )
        assert result == markets

    async def test_add_marketplace_invalid_source(self):
        with pytest.raises(ValueError, match="Invalid marketplace source"):
            await add_marketplace("http://example.com/plugins")  # http:// not allowed

    async def test_add_marketplace_no_scheme(self):
        with pytest.raises(ValueError):
            await add_marketplace("example.com/plugins")

    async def test_remove_marketplace_valid(self):
        with patch("app.tools.plugins._run_plugin_cmd", new_callable=AsyncMock) as mock_cmd, \
             patch("app.tools.plugins.list_marketplaces", new_callable=AsyncMock, return_value=[]):
            await remove_marketplace("official")
        mock_cmd.assert_called_once_with(
            ["claude", "plugin", "marketplace", "remove", "official"]
        )

    async def test_remove_marketplace_invalid_name(self):
        with pytest.raises(ValueError, match="Invalid marketplace name"):
            await remove_marketplace("bad name; echo evil")


# ---------------------------------------------------------------------------
# Concurrency / lock serialization test
# ---------------------------------------------------------------------------

class TestMutationLockSerialization:
    async def test_concurrent_installs_serialized(self):
        """Two concurrent install() calls must serialize subprocess invocations."""
        call_order: list[str] = []
        empty_response = PluginsResponse()

        async def fake_run(args):
            # record which plugin_id this call is for
            plugin_id = args[-1] if args else "unknown"
            call_order.append(f"start:{plugin_id}")
            await asyncio.sleep(0)  # yield to event loop
            call_order.append(f"end:{plugin_id}")

        with patch("app.tools.plugins._run_plugin_cmd", side_effect=fake_run), \
             patch("app.tools.plugins.list_plugins", new_callable=AsyncMock, return_value=empty_response):
            await asyncio.gather(
                install("plugin-a"),
                install("plugin-b"),
            )

        # With serialization, one plugin fully completes before the other starts
        # start:plugin-a, end:plugin-a, start:plugin-b, end:plugin-b (or reverse order)
        assert len(call_order) == 4
        # Each start must be immediately followed by its own end (no interleaving)
        for i in range(0, 4, 2):
            assert call_order[i].startswith("start:")
            assert call_order[i + 1].startswith("end:")
            assert call_order[i].split(":")[1] == call_order[i + 1].split(":")[1]
