from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ..models import AiToolEntry, HookEntry, PermissionEntry

log = logging.getLogger(__name__)


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
        for line in lines[1:]:
            stripped = line.strip()
            if stripped == "---":
                break
            if stripped.startswith("description:"):
                value = stripped[len("description:"):].strip().strip('"').strip("'")
                if value:
                    return value

    # Fall back to first non-empty, non-heading, non-frontmatter line
    in_front = lines[0].strip() == "---"
    past_front = not in_front
    for i, line in enumerate(lines):
        stripped = line.strip()
        if in_front:
            if stripped == "---" and i > 0:
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
        rel = md_file.relative_to(claude_dir.parent)
        entries.append(AiToolEntry(
            name=md_file.stem,
            path=str(rel).replace("\\", "/"),
            description=_extract_description(md_file),
            scope=scope,
            modified_at=_mtime_iso(md_file),
        ))
    return entries


def _scan_skills(claude_dir: Path, scope: str) -> list[AiToolEntry]:
    """Scan .claude/skills/ for flat *.md files and directory-based skills (dir/SKILL.md)."""
    target = claude_dir / "skills"
    if not target.is_dir():
        return []

    entries: list[AiToolEntry] = []
    seen: set[str] = set()

    # Flat *.md files (e.g. skills/my-skill.md)
    for md_file in sorted(target.glob("*.md")):
        if not md_file.is_file():
            continue
        rel = md_file.relative_to(claude_dir.parent)
        entries.append(AiToolEntry(
            name=md_file.stem,
            path=str(rel).replace("\\", "/"),
            description=_extract_description(md_file),
            scope=scope,
            modified_at=_mtime_iso(md_file),
        ))
        seen.add(md_file.stem)

    # Directory-based skills (e.g. skills/frontend-design/SKILL.md)
    for skill_dir in sorted(target.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name in seen:
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue
        rel = skill_file.relative_to(claude_dir.parent)
        entries.append(AiToolEntry(
            name=skill_dir.name,
            path=str(rel).replace("\\", "/"),
            description=_extract_description(skill_file),
            scope=scope,
            modified_at=_mtime_iso(skill_file),
        ))

    return entries


def _parse_settings(
    settings_path: Path,
    scope: str,
) -> tuple[list[HookEntry], list[PermissionEntry]]:
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

    # Hooks: {"hooks": {"EventName": [{"matcher": "...", "hooks": [...]}]}}
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
