from __future__ import annotations

import dataclasses
import logging
import re
from pathlib import Path

from ..git_ops import GitError, _auth_env, _run, _run_or_raise, validate_branch, validate_repo_url
from .scanner import _extract_description, _parse_settings, _scan_category, _scan_skills
from .sources import ToolSource

log = logging.getLogger(__name__)

DISCOVERY_BASE = Path("/data/.cronos/discovery_sources")


@dataclasses.dataclass
class DiscoveredItem:
    source_url: str
    source_slug: str
    kind: str  # "agent" | "skill" | "command" | "hook"
    name: str
    relative_path: str
    description: str | None
    source_sha: str


def _make_slug(url: str) -> str:
    """Build a filesystem-safe slug from a repo URL."""
    slug = re.sub(r"^https?://", "", url)
    slug = re.sub(r"^git@", "", slug)
    slug = re.sub(r"\.git$", "", slug)
    slug = re.sub(r"[^A-Za-z0-9._-]", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


async def clone_source(source: ToolSource) -> Path:
    """Shallow-clone source repo into DISCOVERY_BASE/<slug>/.

    Returns the clone path. If the directory already exists, returns it as-is
    without re-cloning (use refresh_source to update an existing clone).
    """
    validate_repo_url(source.url)
    slug = _make_slug(source.url)
    dest = DISCOVERY_BASE / slug

    if (dest / ".git").exists():
        log.debug("clone_source: %s already cloned at %s", source.url, dest)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    env = _auth_env(source.url)

    cmd = ["clone", "--depth", "1"]
    if source.branch:
        validate_branch(source.branch)
        cmd += ["--branch", source.branch]
    cmd += [source.url, str(dest)]

    log.info("Cloning %s → %s", source.url, dest)
    await _run_or_raise(*cmd, env=env)
    return dest


async def refresh_source(source: ToolSource) -> Path:
    """Clone if missing, else fetch --depth 1 + reset --hard FETCH_HEAD."""
    validate_repo_url(source.url)
    slug = _make_slug(source.url)
    dest = DISCOVERY_BASE / slug

    if not (dest / ".git").exists():
        return await clone_source(source)

    branch = source.branch or "HEAD"
    if source.branch:
        validate_branch(source.branch)

    env = _auth_env(source.url)
    log.info("Refreshing %s at %s", source.url, dest)
    await _run_or_raise("fetch", "--depth", "1", "origin", branch, cwd=dest, env=env)
    await _run_or_raise("reset", "--hard", "FETCH_HEAD", cwd=dest)
    return dest


async def walk_source(path: Path) -> list[DiscoveredItem]:
    """Walk a cloned source repo and return all discovered items.

    Scans .claude/agents/, .claude/commands/, .claude/skills/, and
    .claude/settings.json (for hooks).
    """
    claude_dir = path / ".claude"
    if not claude_dir.is_dir():
        return []

    # Resolve source metadata from the clone itself.
    _code, url_out, _ = await _run("remote", "get-url", "origin", cwd=path)
    source_url = url_out.strip() if _code == 0 else ""
    source_slug = _make_slug(source_url) if source_url else path.name

    _code2, sha_out, _ = await _run("rev-parse", "HEAD", cwd=path)
    source_sha = sha_out.strip() if _code2 == 0 else ""

    items: list[DiscoveredItem] = []

    for entry in _scan_category(claude_dir, "agents", "discovered"):
        items.append(DiscoveredItem(
            source_url=source_url,
            source_slug=source_slug,
            kind="agent",
            name=entry.name,
            relative_path=entry.path,
            description=entry.description,
            source_sha=source_sha,
        ))

    for entry in _scan_category(claude_dir, "commands", "discovered", recursive=True):
        items.append(DiscoveredItem(
            source_url=source_url,
            source_slug=source_slug,
            kind="command",
            name=entry.name,
            relative_path=entry.path,
            description=entry.description,
            source_sha=source_sha,
        ))

    for entry in _scan_skills(claude_dir, "discovered"):
        items.append(DiscoveredItem(
            source_url=source_url,
            source_slug=source_slug,
            kind="skill",
            name=entry.name,
            relative_path=entry.path,
            description=entry.description,
            source_sha=source_sha,
        ))

    settings_path = claude_dir / "settings.json"
    hooks, _ = _parse_settings(settings_path, "discovered")
    for hook in hooks:
        hook_name = f"{hook.event}:{hook.matcher or '*'}"
        items.append(DiscoveredItem(
            source_url=source_url,
            source_slug=source_slug,
            kind="hook",
            name=hook_name,
            relative_path=".claude/settings.json",
            description=hook.command[:200],
            source_sha=source_sha,
        ))

    return items
