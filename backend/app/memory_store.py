from __future__ import annotations

import asyncio
import logging
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import frontmatter

from .models import MemoryItem, MemoryKind, MemoryScope

log = logging.getLogger(__name__)

_VALID_KINDS: frozenset[str] = frozenset({"fact", "procedure", "observation", "reference"})


# ---------------------------------------------------------------------------
# Serialization utilities
# ---------------------------------------------------------------------------

def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def dump_memory_item(item: MemoryItem) -> str:
    """Serialize a MemoryItem to markdown with YAML frontmatter."""
    meta: dict[str, Any] = {
        "id": item.id,
        "scope": item.scope,
        "kind": item.kind,
        "title": item.title,
        "confirmed": item.confirmed,
        "confidence": item.confidence,
        "score": item.score,
        "last_used_at": _iso(item.last_used_at),
        "ref_count": item.ref_count,
        "ttl_until": _iso(item.ttl_until) if item.ttl_until is not None else None,
        "sources": list(item.sources),
        "links": list(item.links),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }
    post = frontmatter.Post(item.body, **meta)
    return frontmatter.dumps(post) + "\n"


def parse_memory_item(path: Path) -> MemoryItem:
    """Parse a MemoryItem from a markdown file with YAML frontmatter."""
    post = frontmatter.load(str(path))
    meta = dict(post.metadata)
    kind = meta.get("kind", "fact")
    if kind not in _VALID_KINDS:
        kind = "fact"
    sources = meta.get("sources") or []
    if not isinstance(sources, list):
        sources = []
    links = meta.get("links") or []
    if not isinstance(links, list):
        links = []
    ttl_raw = meta.get("ttl_until")
    ttl_until = _parse_dt(ttl_raw) if ttl_raw is not None else None
    try:
        return MemoryItem(
            id=meta.get("id") or path.stem,
            scope=meta.get("scope", "global"),
            kind=kind,
            title=meta["title"],
            body=post.content,
            confirmed=bool(meta.get("confirmed", False)),
            confidence=float(meta.get("confidence", 0.5)),
            score=float(meta.get("score", 1.0)),
            last_used_at=_parse_dt(meta["last_used_at"]),
            ref_count=int(meta.get("ref_count", 0)),
            ttl_until=ttl_until,
            sources=[str(s) for s in sources],
            links=[str(lnk) for lnk in links],
            created_at=_parse_dt(meta["created_at"]),
            updated_at=_parse_dt(meta["updated_at"]),
        )
    except (KeyError, ValueError) as e:
        raise ValueError(f"Invalid memory file {path.name}: {e}") from e


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{secrets.token_hex(4)}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _build_index(items: list[MemoryItem], scope: MemoryScope) -> str:
    """Build a Karpathy-style index.md for the given scope."""
    lines = [f"# Memory Index — {scope}", ""]
    if not items:
        lines.append("_No entries yet._")
    else:
        for item in sorted(items, key=lambda i: i.title.lower()):
            lines.append(f"- [{item.title}](items/{item.id}.md) `{item.kind}`")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------

class MemoryNotFound(Exception):
    pass


class MemoryStore:
    """Async-locked store for MemoryItems persisted as markdown+frontmatter files.

    Storage layout:
      global scope  → /data/memory/items/{id}.md
      space scope   → /data/spaces/{space_id}/.cronos/memory/items/{id}.md

    Uses the same async lock + atomic tmpfile + os.replace pattern as
    trace_store.py and stats_store.py.
    """

    def __init__(self, data_dir: Path, spaces_dir: Path) -> None:
        self._data_dir = data_dir
        self._spaces_dir = spaces_dir
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _items_dir(self, scope: MemoryScope) -> Path:
        if scope == "global":
            return self._data_dir / "memory" / "items"
        if scope.startswith("space:"):
            space_id = scope[len("space:"):]
            return self._spaces_dir / space_id / ".cronos" / "memory" / "items"
        raise ValueError(f"Unknown scope format: {scope!r}")

    def _item_path(self, scope: MemoryScope, item_id: str) -> Path:
        return self._items_dir(scope) / f"{item_id}.md"

    def _index_path(self, scope: MemoryScope) -> Path:
        return self._items_dir(scope).parent / "index.md"

    # ------------------------------------------------------------------
    # Internal sync I/O (run inside asyncio.to_thread or under lock)
    # ------------------------------------------------------------------

    def _read_all_sync(self, scope: MemoryScope) -> list[MemoryItem]:
        items_dir = self._items_dir(scope)
        if not items_dir.is_dir():
            return []
        results: list[MemoryItem] = []
        for path in sorted(items_dir.glob("*.md")):
            try:
                results.append(parse_memory_item(path))
            except Exception:
                log.warning("Skipping unreadable memory file %s", path)
        return results

    def _read_one_sync(self, scope: MemoryScope, item_id: str) -> MemoryItem | None:
        path = self._item_path(scope, item_id)
        if not path.exists():
            return None
        try:
            return parse_memory_item(path)
        except Exception:
            log.exception("Failed to parse memory item %s", path)
            return None

    def _write_sync(self, scope: MemoryScope, item: MemoryItem) -> None:
        path = self._item_path(scope, item.id)
        _atomic_write(path, dump_memory_item(item))

    def _delete_sync(self, path: Path) -> None:
        path.unlink(missing_ok=True)

    def _regenerate_index_sync(self, scope: MemoryScope) -> None:
        items = self._read_all_sync(scope)
        index_path = self._index_path(scope)
        _atomic_write(index_path, _build_index(items, scope))

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def get_all(self, scope: MemoryScope) -> list[MemoryItem]:
        """Return all MemoryItems for the given scope."""
        return await asyncio.to_thread(self._read_all_sync, scope)

    async def get_by_id(self, scope: MemoryScope, item_id: str) -> MemoryItem | None:
        """Return a single MemoryItem by id, or None if not found."""
        return await asyncio.to_thread(self._read_one_sync, scope, item_id)

    async def create(self, scope: MemoryScope, item: MemoryItem) -> MemoryItem:
        """Persist a new MemoryItem and return it."""
        async with self._lock:
            existing = await asyncio.to_thread(self._read_one_sync, scope, item.id)
            if existing is not None:
                raise ValueError(f"Memory item {item.id!r} already exists in scope {scope!r}")
            await asyncio.to_thread(self._write_sync, scope, item)
            await asyncio.to_thread(self._regenerate_index_sync, scope)
        return item

    async def update(
        self, scope: MemoryScope, item_id: str, patch: dict[str, Any]
    ) -> MemoryItem:
        """Apply patch fields to an existing MemoryItem and return the updated item."""
        async with self._lock:
            existing = await asyncio.to_thread(self._read_one_sync, scope, item_id)
            if existing is None:
                raise MemoryNotFound(f"Memory item {item_id!r} not found in scope {scope!r}")
            updated_data = existing.model_dump()
            for key, value in patch.items():
                if key in updated_data:
                    updated_data[key] = value
            updated_data["updated_at"] = datetime.now(UTC)
            updated = MemoryItem(**updated_data)
            await asyncio.to_thread(self._write_sync, scope, updated)
            await asyncio.to_thread(self._regenerate_index_sync, scope)
        return updated

    async def delete(self, scope: MemoryScope, item_id: str) -> None:
        """Delete a MemoryItem by id."""
        async with self._lock:
            path = self._item_path(scope, item_id)
            if not path.exists():
                raise MemoryNotFound(f"Memory item {item_id!r} not found in scope {scope!r}")
            await asyncio.to_thread(self._delete_sync, path)
            await asyncio.to_thread(self._regenerate_index_sync, scope)
