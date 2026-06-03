from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request

from ..models import AdoptedToolEntry, AiToolDetail, AiToolEntry, SpaceToolsResponse
from ..space_storage import SpaceStore
from ..tools.adoption import _read_manifest
from ..tools.scanner import (
    _extract_description,
    _mtime_iso,
    _parse_settings,
    _scan_category,
    _scan_skills,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spaces", tags=["tools"])

GLOBAL_CLAUDE_DIR = Path.home() / ".claude"


def _get_space_store(request: Request) -> SpaceStore:
    return request.app.state.space_store


def _scan_context(claude_dir: Path, scope: str) -> list[AiToolEntry]:
    """Collect .claude/context/ files and .claude/CONTEXT.md."""
    entries: list[AiToolEntry] = []

    context_md = claude_dir / "CONTEXT.md"
    if context_md.is_file():
        entries.append(AiToolEntry(
            name="CONTEXT",
            path=str(context_md.relative_to(claude_dir.parent)).replace("\\", "/"),
            description=_extract_description(context_md),
            scope=scope,
            modified_at=_mtime_iso(context_md),
        ))

    context_dir = claude_dir / "context"
    if context_dir.is_dir():
        for f in sorted(context_dir.iterdir()):
            if f.is_file():
                rel = str(f.relative_to(claude_dir.parent)).replace("\\", "/")
                entries.append(AiToolEntry(
                    name=f.stem if f.suffix else f.name,
                    path=rel,
                    description=_extract_description(f) if f.suffix == ".md" else None,
                    scope=scope,
                    modified_at=_mtime_iso(f),
                ))
    return entries


def _derive_status(evolved: bool, local_sha: str, base_sha: str) -> str:
    if evolved:
        return "evolved"
    if local_sha != base_sha:
        return "edited"
    return "pristine"


def _scan_adopted(space_dir: Path) -> list[AdoptedToolEntry]:
    tools_dir = space_dir / ".cronos" / "tools"
    if not tools_dir.is_dir():
        return []
    entries: list[AdoptedToolEntry] = []
    for kind_dir in sorted(tools_dir.iterdir()):
        if not kind_dir.is_dir() or kind_dir.name.startswith("."):
            continue
        for item_dir in sorted(kind_dir.iterdir()):
            if not item_dir.is_dir():
                continue
            manifest_path = item_dir / "manifest.yml"
            if not manifest_path.is_file():
                continue
            try:
                m = _read_manifest(manifest_path)
            except Exception:
                log.warning("Failed to read manifest at %s", manifest_path)
                continue
            entries.append(AdoptedToolEntry(
                source_url=m.source_url,
                source_slug=m.source_slug,
                source_path=m.source_path,
                source_sha=m.source_sha,
                adopted_at=m.adopted_at,
                base_sha=m.base_sha,
                local_sha=m.local_sha,
                evolved=m.evolved,
                kind=m.kind,
                name=m.name,
                status=_derive_status(m.evolved, m.local_sha, m.base_sha),
            ))
    return entries


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
    skills = _scan_skills(space_claude, "space")
    context_files = _scan_context(space_claude, "space")

    s_hooks, s_perms = _parse_settings(space_claude / "settings.json", "space")
    s_hooks2, s_perms2 = _parse_settings(space_claude / "settings.local.json", "space")
    s_hooks += s_hooks2
    s_perms += s_perms2

    # Scan global ~/.claude/
    g_agents = _scan_category(GLOBAL_CLAUDE_DIR, "agents", "global")
    g_commands = _scan_category(GLOBAL_CLAUDE_DIR, "commands", "global", recursive=True)
    g_skills = _scan_skills(GLOBAL_CLAUDE_DIR, "global")
    g_context = _scan_context(GLOBAL_CLAUDE_DIR, "global")

    g_hooks, g_perms = _parse_settings(GLOBAL_CLAUDE_DIR / "settings.json", "global")
    g_hooks2, g_perms2 = _parse_settings(GLOBAL_CLAUDE_DIR / "settings.local.json", "global")
    g_hooks += g_hooks2
    g_perms += g_perms2

    has_claude_md = (space_dir / "CLAUDE.md").is_file()
    adopted = _scan_adopted(space_dir)

    return SpaceToolsResponse(
        space_id=space_id,
        agents=agents + g_agents,
        commands=commands + g_commands,
        skills=skills + g_skills,
        context_files=context_files + g_context,
        hooks=s_hooks + g_hooks,
        permissions=s_perms + g_perms,
        has_claude_md=has_claude_md,
        adopted=adopted,
    )


@router.get("/{space_id}/tool-content", response_model=AiToolDetail)
async def get_tool_content(
    space_id: str,
    path: str,
    scope: Literal["space", "global"],
    request: Request,
) -> AiToolDetail:
    space_store = _get_space_store(request)
    space = space_store.get(space_id)
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

    if scope == "space":
        space_dir = space_store.space_dir(space_id)
        allowed_root = (space_dir / ".claude").resolve()
        resolved = (space_dir / path).resolve()
    else:
        if path.startswith("~"):
            resolved = Path(path).expanduser().resolve()
        else:
            resolved = (Path.home() / path).resolve()
        allowed_root = GLOBAL_CLAUDE_DIR.resolve()

    if not resolved.is_relative_to(allowed_root):
        raise HTTPException(status_code=400, detail="Path is outside the allowed directory")

    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError:
        raise HTTPException(status_code=404, detail="File not found")

    path_str = str(resolved)
    if "/.claude/agents/" in path_str:
        category: Literal["agent", "command", "skill", "context"] = "agent"
    elif "/.claude/commands/" in path_str:
        category = "command"
    elif "/.claude/skills/" in path_str:
        category = "skill"
    else:
        category = "context"

    return AiToolDetail(
        name=resolved.stem,
        path=path,
        description=_extract_description(resolved),
        scope=scope,
        modified_at=_mtime_iso(resolved),
        category=category,
        content=content,
    )
