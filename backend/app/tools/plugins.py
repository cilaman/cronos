"""Claude Code plugin CLI wrapper.

Single-process Uvicorn assumed; asyncio.Lock is sufficient for in-process
mutation serialization. Multi-worker deployments require an OS-level file
lock (flock on .claude/.plugin-mutex) — track as follow-up if deployment
topology changes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from ..models import (
    MarketplaceEntry,
    MarketplacePluginEntry,
    PluginComponent,
    PluginEntry,
    PluginsResponse,
)
from .scanner import _scan_category, _scan_skills

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input-validation regexes (defense-in-depth against CLI injection)
# ---------------------------------------------------------------------------

PLUGIN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+(@[a-zA-Z0-9_-]+)?$")
MARKETPLACE_SOURCE_PATTERN = re.compile(r"^(https|file)://[^\s]+$")
MARKETPLACE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# Verified live: `claude plugin list --available --json` returns
# {"installed": [...], "available": [...]}
LIST_PLUGINS_CMD = ["claude", "plugin", "list", "--available", "--json"]
LIST_MARKETPLACES_CMD = ["claude", "plugin", "marketplace", "list", "--json"]

# Serializes all mutation subprocess calls.
_plugin_mutation_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Structured exception
# ---------------------------------------------------------------------------

class PluginCliError(Exception):
    """Raised when a `claude plugin` CLI call exits non-zero or returns unparseable JSON."""

    def __init__(self, command: list[str], returncode: int, stderr: str) -> None:
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"Plugin CLI error (exit {returncode}): {stderr!r}"
        )


# ---------------------------------------------------------------------------
# Shared subprocess helper — the SINGLE allowed subprocess call site
# ---------------------------------------------------------------------------

async def _run_plugin_cmd(args: list[str]) -> tuple[str, str]:
    """Run a Claude CLI command and return (stdout, stderr).

    Raises PluginCliError on non-zero exit.
    Never uses shell=True; first element must be 'claude'.
    """
    assert args and args[0] == "claude", "args must be a non-empty list starting with 'claude'"
    log.debug("plugin cmd: %s", args)
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        log.debug("plugin cmd failed (exit %d): %s", proc.returncode, stderr)
        raise PluginCliError(command=args, returncode=proc.returncode, stderr=stderr)
    return stdout, stderr


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _parse_plugin_entry(raw: dict) -> PluginEntry:
    components = [
        PluginComponent(name=c.get("name", ""), kind=c.get("kind", "agent"))
        for c in raw.get("components", [])
        if c.get("name")
    ]
    return PluginEntry(
        id=raw.get("id", raw.get("name", "")),
        name=raw.get("name", ""),
        marketplace=raw.get("marketplace") or raw.get("marketplaceName"),
        version=raw.get("version"),
        scope=raw.get("scope", "user"),
        enabled=raw.get("enabled", True),
        components=components,
        installPath=raw.get("installPath"),
        installedAt=raw.get("installedAt"),
        lastUpdated=raw.get("lastUpdated"),
    )


def _parse_marketplace_plugin_entry(raw: dict) -> MarketplacePluginEntry:
    return MarketplacePluginEntry(
        pluginId=raw.get("pluginId", raw.get("id", raw.get("name", ""))),
        name=raw.get("name", ""),
        description=raw.get("description"),
        marketplaceName=raw.get("marketplaceName"),
        source=raw.get("source"),
        installCount=raw.get("installCount", 0),
    )


def _parse_marketplace_entry(raw: dict) -> MarketplaceEntry:
    return MarketplaceEntry(
        name=raw.get("name", ""),
        source=raw.get("source", ""),
    )


# ---------------------------------------------------------------------------
# Read-only operations (no lock)
# ---------------------------------------------------------------------------

async def list_marketplaces() -> list[MarketplaceEntry]:
    """Return configured marketplaces via `claude plugin marketplace list --json`."""
    stdout, _ = await _run_plugin_cmd(LIST_MARKETPLACES_CMD)
    try:
        raw_list = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise PluginCliError(
            command=LIST_MARKETPLACES_CMD, returncode=0, stderr=f"JSON parse error: {exc}"
        ) from exc
    if not isinstance(raw_list, list):
        return []
    return [_parse_marketplace_entry(item) for item in raw_list if isinstance(item, dict)]


async def list_plugins() -> PluginsResponse:
    """Return installed + available plugins and configured marketplaces.

    Calls `claude plugin list --available --json` for installed/available,
    then `list_marketplaces()` to populate the marketplaces field.
    """
    stdout, _ = await _run_plugin_cmd(LIST_PLUGINS_CMD)
    try:
        raw = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise PluginCliError(
            command=LIST_PLUGINS_CMD, returncode=0, stderr=f"JSON parse error: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raw = {}

    installed = [
        _parse_plugin_entry(item)
        for item in raw.get("installed", [])
        if isinstance(item, dict)
    ]
    available = [
        _parse_marketplace_plugin_entry(item)
        for item in raw.get("available", [])
        if isinstance(item, dict)
    ]
    marketplaces = await list_marketplaces()
    return PluginsResponse(installed=installed, available=available, marketplaces=marketplaces)


async def plugin_components(install_path: str, plugin_name: str) -> list:
    """Return AiToolEntry list for a plugin's bundled agents, skills, and commands.

    Namespaces each entry's name as `{plugin_name}:{name}` and sets scope='plugin'.
    Reuses _scan_category / _scan_skills from scanner.py.
    """
    base = Path(install_path)
    if not base.is_dir():
        return []

    entries = []

    for category_dir in ("agents", "commands"):
        for entry in _scan_category(base, category_dir, scope="plugin"):
            entry.name = f"{plugin_name}:{entry.name}"
            entries.append(entry)

    for entry in _scan_skills(base, scope="plugin"):
        entry.name = f"{plugin_name}:{entry.name}"
        entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# Mutation operations (serialized via _plugin_mutation_lock)
# ---------------------------------------------------------------------------

async def install(plugin_id: str, scope: str = "user") -> PluginsResponse:
    """Install a plugin by id; returns refreshed PluginsResponse."""
    if not PLUGIN_ID_PATTERN.fullmatch(plugin_id):
        raise ValueError(f"Invalid plugin_id: {plugin_id!r}")
    async with _plugin_mutation_lock:
        await _run_plugin_cmd(["claude", "plugin", "install", plugin_id])
        return await list_plugins()


async def uninstall(plugin_id: str) -> PluginsResponse:
    """Uninstall a plugin by id; returns refreshed PluginsResponse."""
    if not PLUGIN_ID_PATTERN.fullmatch(plugin_id):
        raise ValueError(f"Invalid plugin_id: {plugin_id!r}")
    async with _plugin_mutation_lock:
        await _run_plugin_cmd(["claude", "plugin", "uninstall", plugin_id])
        return await list_plugins()


async def enable(plugin_id: str) -> PluginsResponse:
    """Enable a disabled plugin; returns refreshed PluginsResponse."""
    if not PLUGIN_ID_PATTERN.fullmatch(plugin_id):
        raise ValueError(f"Invalid plugin_id: {plugin_id!r}")
    async with _plugin_mutation_lock:
        await _run_plugin_cmd(["claude", "plugin", "enable", plugin_id])
        return await list_plugins()


async def disable(plugin_id: str) -> PluginsResponse:
    """Disable an enabled plugin; returns refreshed PluginsResponse."""
    if not PLUGIN_ID_PATTERN.fullmatch(plugin_id):
        raise ValueError(f"Invalid plugin_id: {plugin_id!r}")
    async with _plugin_mutation_lock:
        await _run_plugin_cmd(["claude", "plugin", "disable", plugin_id])
        return await list_plugins()


async def add_marketplace(source: str) -> list[MarketplaceEntry]:
    """Add a marketplace by URL; returns refreshed list of MarketplaceEntry."""
    if not MARKETPLACE_SOURCE_PATTERN.fullmatch(source):
        raise ValueError(f"Invalid marketplace source: {source!r}")
    async with _plugin_mutation_lock:
        await _run_plugin_cmd(["claude", "plugin", "marketplace", "add", source])
        return await list_marketplaces()


async def remove_marketplace(name: str) -> list[MarketplaceEntry]:
    """Remove a marketplace by name; returns refreshed list of MarketplaceEntry."""
    if not MARKETPLACE_NAME_PATTERN.fullmatch(name):
        raise ValueError(f"Invalid marketplace name: {name!r}")
    async with _plugin_mutation_lock:
        await _run_plugin_cmd(["claude", "plugin", "marketplace", "remove", name])
        return await list_marketplaces()
