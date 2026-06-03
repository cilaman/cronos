from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from ..tools.discovery import DiscoveredItem, refresh_source, walk_source
from ..tools.index import list_discovered, upsert_discovered
from ..tools.sources import load_sources

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discovery", tags=["discovery"])

_refresh_lock = asyncio.Lock()
_last_refresh_at: datetime | None = None
_LOCK_TTL_SECONDS = 3600  # 60 minutes


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


async def _run_refresh(db_path: Path, sources_path: Path) -> dict:
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

    return {"refreshed": refreshed, "items": [_item_dict(i) for i in all_items]}


async def run_refresh_if_unlocked(db_path: Path, sources_path: Path) -> dict | None:
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
        return await _run_refresh(db_path, sources_path)


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

    async with _refresh_lock:
        _last_refresh_at = datetime.now(timezone.utc)
        return await _run_refresh(db_path, sources_path)


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
