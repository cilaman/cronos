from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..models import AiToolEntry, HookEntry, PermissionEntry, SpaceToolsResponse
from ..space_storage import SpaceStore

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spaces", tags=["tools"])

GLOBAL_CLAUDE_DIR = Path.home() / ".claude"


def _get_space_store(request: Request) -> SpaceStore:
    return request.app.state.space_store


def _mtime_iso(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except OSError:
        return datetime.now(tz=timezone.utc).isoformat()


def _extract_description(path: Path) -> str | None:
    """Read a markdown file and extract a description.

    Tries YAML frontmatter `description:` field first, then falls back to the
    first non-empty, non-heading paragraph line.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    lines = text.splitlines()
    if not lines:
        return None

    # Try YAML frontmatter
    if lines[0].strip() == "---":
        in_frontmatter = True
        for line in lines[1:]:
            stripped = line.strip()
            if stripped == "---":
                break
            if stripped.startswith("description:"):
                value = stripped[len("description:"):].strip().strip('"').strip("'")
                if value:
                    return value
        in_frontmatter = False  # noqa: F841 — consumed above

    # Fall back to first non-empty, non-heading, non-frontmatter line
    in_front = lines[0].strip() == "---"
    past_front = not in_front
    for line in lines:
        stripped = line.strip()
        if in_front:
            if stripped == "---" and line != lines[0]:
                past_front = True
                in_front = False
            continue
        if not past_front:
            continue
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("---"):
            continue
        return stripped[:200]

    return None


def _scan_category(
    claude_dir: Path,
    subfolder: str,
    scope: str,
    recursive: bool = False,
) -> list[AiToolEntry]:
    """Scan a .claude/<subfolder>/ directory for markdown files."""
    target = claude_dir / subfolder
    if not target.is_dir():
        return []

    entries: list[AiToolEntry] = []
    pattern = "**/*.md" if recursive else "*.md"
    for md_file in sorted(target.glob(pattern)):
        if not md_file.is_file():
            continue
        rel = md_file.relative_to(claude_dir)
        entries.append(AiToolEntry(
            name=md_file.stem,
            path=str(rel).replace("\\", "/"),
            description=_extract_description(md_file),
            scope=scope,
            modified_at=_mtime_iso(md_file),
        ))
    return entries


def _scan_context(claude_dir: Path, scope: str) -> list[AiToolEntry]:
    """Collect .claude/context/ files and .claude/CONTEXT.md."""
    entries: list[AiToolEntry] = []

    context_md = claude_dir / "CONTEXT.md"
    if context_md.is_file():
        entries.append(AiToolEntry(
            name="CONTEXT",
            path="CONTEXT.md",
            description=_extract_description(context_md),
            scope=scope,
            modified_at=_mtime_iso(context_md),
        ))

    context_dir = claude_dir / "context"
    if context_dir.is_dir():
        for f in sorted(context_dir.iterdir()):
            if f.is_file():
                rel = f".claude/context/{f.name}"
                entries.append(AiToolEntry(
                    name=f.stem if f.suffix else f.name,
                    path=rel,
                    description=_extract_description(f) if f.suffix == ".md" else None,
                    scope=scope,
                    modified_at=_mtime_iso(f),
                ))
    return entries


def _parse_settings(settings_path: Path, scope: str) -> tuple[list[HookEntry], list[PermissionEntry]]:
    """Parse a Claude Code settings.json for hooks and permissions."""
    hooks: list[HookEntry] = []
    permissions: list[PermissionEntry] = []

    if not settings_path.is_file():
        return hooks, permissions

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return hooks, permissions

    # Permissions: {"permissions": {"allow": [...], "deny": [...]}}
    perms = data.get("permissions", {})
    for pattern in perms.get("allow", []):
        if isinstance(pattern, str):
            permissions.append(PermissionEntry(pattern=pattern, allowed=True, scope=scope))
    for pattern in perms.get("deny", []):
        if isinstance(pattern, str):
            permissions.append(PermissionEntry(pattern=pattern, allowed=False, scope=scope))

    # Hooks: {"hooks": {"EventName": [{"matcher": "...", "hooks": [{"type": "command", "command": "..."}]}]}}
    raw_hooks = data.get("hooks", {})
    for event, hook_groups in raw_hooks.items():
        if not isinstance(hook_groups, list):
            continue
        for group in hook_groups:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher") or None
            for hook in group.get("hooks", []):
                if not isinstance(hook, dict):
                    continue
                command = hook.get("command", "")
                if command:
                    hooks.append(HookEntry(
                        event=event,
                        matcher=matcher,
                        command=command,
                        scope=scope,
                    ))

    return hooks, permissions


@router.get("/{space_id}/tools", response_model=SpaceToolsResponse)
async def get_space_tools(space_id: str, request: Request) -> SpaceToolsResponse:
    space_store = _get_space_store(request)
    space = space_store.get(space_id)
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

    space_dir = space_store.space_dir(space_id)

    # Scan space-local .claude/
    space_claude = space_dir / ".claude"
    agents = _scan_category(space_claude, "agents", "space")
    commands = _scan_category(space_claude, "commands", "space", recursive=True)
    skills = _scan_category(space_claude, "skills", "space")
    context_files = _scan_context(space_claude, "space")

    s_hooks, s_perms = _parse_settings(space_claude / "settings.json", "space")
    s_hooks2, s_perms2 = _parse_settings(space_claude / "settings.local.json", "space")
    s_hooks += s_hooks2
    s_perms += s_perms2

    # Scan global ~/.claude/
    g_agents = _scan_category(GLOBAL_CLAUDE_DIR, "agents", "global")
    g_commands = _scan_category(GLOBAL_CLAUDE_DIR, "commands", "global", recursive=True)
    g_skills = _scan_category(GLOBAL_CLAUDE_DIR, "skills", "global")
    g_context = _scan_context(GLOBAL_CLAUDE_DIR, "global")

    g_hooks, g_perms = _parse_settings(GLOBAL_CLAUDE_DIR / "settings.json", "global")
    g_hooks2, g_perms2 = _parse_settings(GLOBAL_CLAUDE_DIR / "settings.local.json", "global")
    g_hooks += g_hooks2
    g_perms += g_perms2

    has_claude_md = (space_dir / "CLAUDE.md").is_file()

    return SpaceToolsResponse(
        space_id=space_id,
        agents=agents + g_agents,
        commands=commands + g_commands,
        skills=skills + g_skills,
        context_files=context_files + g_context,
        hooks=s_hooks + g_hooks,
        permissions=s_perms + g_perms,
        has_claude_md=has_claude_md,
    )
