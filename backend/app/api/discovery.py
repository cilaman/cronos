from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from ..tools.discovery import DiscoveredItem, refresh_source, walk_source
from ..tools.index import list_discovered, upsert_discovered
from ..tools.sources import load_sources

if TYPE_CHECKING:
    from ..storage import TaskStore

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discovery", tags=["discovery"])

_refresh_lock = asyncio.Lock()
_last_refresh_at: datetime | None = None
_LOCK_TTL_SECONDS = 3600  # 60 minutes

_MERGE_TITLE_FMT = "Merge upstream changes to {kind}/{name}"


def _item_dict(item: DiscoveredItem) -> dict:
    return {
        "source_url": item.source_url,
        "source_slug": item.source_slug,
        "kind": item.kind,
        "name": item.name,
        "relative_path": item.relative_path,
        "description": item.description,
        "source_sha": item.source_sha,
    }


def _build_diff(upstream_path: Path, local_path: Path) -> str:
    """Return unified diff output between upstream and local paths via git diff --no-index."""
    try:
        result = subprocess.run(
            ["git", "diff", "--no-index", "--", str(upstream_path), str(local_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # exit 0 = identical, exit 1 = differences found (not an error)
        if result.returncode <= 1:
            return result.stdout.strip() or "(no differences)"
        log.warning("git diff --no-index failed (rc=%d): %s", result.returncode, result.stderr)
        return f"(diff unavailable: {result.stderr.strip()})"
    except Exception as exc:
        return f"(diff unavailable: {exc})"


def _build_merge_brief(
    *,
    space_id: str,
    kind: str,
    name: str,
    source_url: str,
    current_source_sha: str,
    upstream_source_sha: str,
    diff: str,
) -> str:
    return (
        f"## Upstream has advanced for {kind}/{name}\n\n"
        f"**Source:** {source_url}  \n"
        f"**Current source_sha:** `{current_source_sha[:12]}`  \n"
        f"**Upstream source_sha:** `{upstream_source_sha[:12]}`  \n"
        f"**Local has edits:** `local_sha != base_sha` — manual merge required.\n\n"
        f"### Diff (upstream vs local)\n\n"
        f"```diff\n{diff}\n```\n\n"
        f"### Resolve Protocol\n\n"
        f"1. Edit the vendored file at `.cronos/tools/{kind}/{name}/` to incorporate the upstream changes.\n"
        f"2. Mark this task **DONE** — Cronos will bump `base_sha` and `source_sha` automatically.\n\n"
        f"<!-- merge-meta\n"
        f"space_id: {space_id}\n"
        f"kind: {kind}\n"
        f"name: {name}\n"
        f"upstream_source_sha: {upstream_source_sha}\n"
        f"-->"
    )


async def _auto_upgrade_tool(
    space_id: str,
    kind: str,
    name: str,
    manifest: object,
    upstream: DiscoveredItem,
    adopt_dir: Path,
    discovery_base: Path,
) -> None:
    """Auto-upgrade a pristine adopted tool to the new upstream version."""
    from ..tools.adoption import _compute_sha, _write_manifest

    upstream_source = discovery_base / upstream.source_slug / upstream.relative_path
    if not upstream_source.exists():
        log.warning(
            "auto-upgrade skipped for %s/%s in space %s: upstream path %s not found",
            kind, name, space_id, upstream_source,
        )
        return

    try:
        if upstream_source.is_dir():
            shutil.copytree(upstream_source, adopt_dir, dirs_exist_ok=True)
        else:
            shutil.copy2(upstream_source, adopt_dir / f"{name}.md")
    except Exception:
        log.exception("auto-upgrade copy failed for %s/%s in space %s", kind, name, space_id)
        return

    new_sha = _compute_sha(adopt_dir)
    mpath = adopt_dir / "manifest.yml"
    updated = manifest.model_copy(update={
        "source_sha": upstream.source_sha,
        "base_sha": new_sha,
        "local_sha": new_sha,
        "evolved": False,
    })
    _write_manifest(mpath, updated)
    log.info(
        "tool.auto-upgraded: %s/%s in space %s → source_sha=%s",
        kind, name, space_id, upstream.source_sha[:8],
    )


async def _upsert_merge_task(
    space_id: str,
    kind: str,
    name: str,
    manifest: object,
    upstream: DiscoveredItem,
    adopt_dir: Path,
    discovery_base: Path,
    task_store: "TaskStore",
) -> None:
    """Create or update a merge task for a locally-edited tool with an upstream advance."""
    title = _MERGE_TITLE_FMT.format(kind=kind, name=name)

    upstream_source = discovery_base / upstream.source_slug / upstream.relative_path
    diff = _build_diff(upstream_source, adopt_dir)

    brief = _build_merge_brief(
        space_id=space_id,
        kind=kind,
        name=name,
        source_url=manifest.source_url,
        current_source_sha=manifest.source_sha,
        upstream_source_sha=upstream.source_sha,
        diff=diff,
    )

    # Duplicate guard: find non-DONE merge task for this (space, kind, name)
    existing = next(
        (
            t for t in task_store.all()
            if t.space_id == space_id
            and t.title == title
            and t.state.value not in ("done", "archived")
        ),
        None,
    )

    if existing is not None:
        await task_store.update(existing.id, brief=brief)
        log.info(
            "Updated existing merge task %s for %s/%s in space %s",
            existing.id, kind, name, space_id,
        )
    else:
        new_task = await task_store.create(
            space_id=space_id,
            title=title,
            brief=brief,
            type="task",
            agent_mode="plan",
        )
        log.info(
            "Created merge task %s for %s/%s in space %s",
            new_task.id, kind, name, space_id,
        )


async def _scan_adopted_after_refresh(
    all_items: list[DiscoveredItem],
    task_store: "TaskStore",
    spaces_dir: Path,
    discovery_base: Path,
) -> None:
    """Scan adopted manifests and handle upstream advances.

    For each adopted tool whose upstream source_sha has changed:
    - Pristine (local_sha == base_sha): auto-upgrade silently.
    - Locally edited: create or update a merge task.
    """
    from ..tools.adoption import _adopt_dir, _read_manifest

    if not all_items or not spaces_dir.is_dir():
        return

    # Build lookup: (source_url, relative_path) → DiscoveredItem
    discovered: dict[tuple[str, str], DiscoveredItem] = {
        (item.source_url, item.relative_path): item
        for item in all_items
    }

    for space_dir in spaces_dir.iterdir():
        if not space_dir.is_dir() or space_dir.name.startswith("."):
            continue
        space_id = space_dir.name
        tools_dir = space_dir / ".cronos" / "tools"
        if not tools_dir.is_dir():
            continue

        for manifest_path in tools_dir.rglob("manifest.yml"):
            # Expected: tools_dir / {kind} / {name} / manifest.yml
            try:
                parts = manifest_path.relative_to(tools_dir).parts
            except ValueError:
                continue
            if len(parts) != 3:
                continue
            kind, name = parts[0], parts[1]
            if kind.startswith("."):  # skip .trash
                continue

            try:
                manifest = _read_manifest(manifest_path)
            except Exception:
                log.exception("Failed to read manifest %s", manifest_path)
                continue

            key = (manifest.source_url, manifest.source_path)
            upstream = discovered.get(key)
            if upstream is None:
                continue  # not in this refresh batch
            if upstream.source_sha == manifest.source_sha:
                continue  # no upstream advance

            adopt_dir = _adopt_dir(space_id, kind, name, spaces_dir=spaces_dir)

            if manifest.local_sha == manifest.base_sha:
                # Pristine: auto-upgrade
                await _auto_upgrade_tool(
                    space_id, kind, name, manifest, upstream, adopt_dir, discovery_base,
                )
            else:
                # Locally edited: create or update merge task
                await _upsert_merge_task(
                    space_id, kind, name, manifest, upstream, adopt_dir, discovery_base, task_store,
                )


async def _run_refresh(
    db_path: Path,
    sources_path: Path,
    *,
    task_store: "TaskStore | None" = None,
    spaces_dir: Path | None = None,
    discovery_base: Path | None = None,
) -> dict:
    from ..tools.adoption import DISCOVERY_BASE as _DEFAULT_DISCOVERY_BASE
    _disc_base = discovery_base or _DEFAULT_DISCOVERY_BASE

    sources = load_sources(sources_path)
    enabled = [s for s in sources if s.enabled]

    if not enabled:
        return {"refreshed": 0, "items": []}

    all_items: list[DiscoveredItem] = []
    refreshed = 0

    for source in enabled:
        try:
            path = await refresh_source(source)
            items = await walk_source(path)
            upsert_discovered(db_path, items)
            all_items.extend(items)
            refreshed += 1
        except Exception:
            log.exception("Failed to refresh source %s", source.url)

    if all_items and task_store is not None and spaces_dir is not None:
        try:
            await _scan_adopted_after_refresh(all_items, task_store, spaces_dir, _disc_base)
        except Exception:
            log.exception("Failed to scan adopted manifests after refresh")

    return {"refreshed": refreshed, "items": [_item_dict(i) for i in all_items]}


async def run_refresh_if_unlocked(
    db_path: Path,
    sources_path: Path,
    *,
    task_store: "TaskStore | None" = None,
    spaces_dir: Path | None = None,
    discovery_base: Path | None = None,
) -> dict | None:
    """Try to run a refresh; returns None if locked or within the 60-min cooldown.

    Used by the periodic background task so it skips gracefully instead of
    raising when a manual refresh ran recently.
    """
    global _last_refresh_at

    if _refresh_lock.locked():
        return None

    now = datetime.now(timezone.utc)
    if _last_refresh_at is not None:
        if (now - _last_refresh_at).total_seconds() < _LOCK_TTL_SECONDS:
            return None

    async with _refresh_lock:
        _last_refresh_at = datetime.now(timezone.utc)
        return await _run_refresh(
            db_path,
            sources_path,
            task_store=task_store,
            spaces_dir=spaces_dir,
            discovery_base=discovery_base,
        )


@router.post("/refresh")
async def post_refresh(request: Request) -> dict:
    """Refresh all enabled sources and index the discovered tools.

    Returns {refreshed, items}. Rejects with 409 if a refresh is already
    in progress or one completed within the last 60 minutes.
    """
    global _last_refresh_at

    if _refresh_lock.locked():
        raise HTTPException(status_code=409, detail="Refresh already in progress")

    now = datetime.now(timezone.utc)
    if _last_refresh_at is not None:
        elapsed = (now - _last_refresh_at).total_seconds()
        if elapsed < _LOCK_TTL_SECONDS:
            remaining = int(_LOCK_TTL_SECONDS - elapsed)
            raise HTTPException(
                status_code=409,
                detail=f"Refresh locked; retry in {remaining}s",
            )

    db_path: Path = request.app.state.discovery_db_path
    sources_path: Path = request.app.state.discovery_sources_path
    task_store = getattr(request.app.state, "store", None)
    spaces_dir = getattr(task_store, "spaces_dir", None)

    async with _refresh_lock:
        _last_refresh_at = datetime.now(timezone.utc)
        return await _run_refresh(
            db_path,
            sources_path,
            task_store=task_store,
            spaces_dir=spaces_dir,
        )


@router.get("/tools")
async def list_tools(
    request: Request,
    kind: Optional[str] = Query(None),
    source_slug: Optional[str] = Query(None),
) -> list[dict]:
    """Query the discovered_tools index, optionally filtered by kind/source_slug."""
    db_path: Path = request.app.state.discovery_db_path
    items = list_discovered(db_path, kind=kind, source_slug=source_slug)
    return [_item_dict(i) for i in items]


@router.get("/sources")
async def list_sources(request: Request) -> list[dict]:
    """Return the parsed tool_sources.yml entries."""
    sources_path: Path = request.app.state.discovery_sources_path
    sources = load_sources(sources_path)
    return [
        {
            "url": s.url,
            "branch": s.branch,
            "enabled": s.enabled,
            "label": s.label,
        }
        for s in sources
    ]
