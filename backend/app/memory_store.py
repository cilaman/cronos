from __future__ import annotations

import asyncio
import logging
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from .memory_lifecycle import boost, should_auto_confirm
from .models import MemoryItem, MemoryKind

log = logging.getLogger("cronos.memory_store")

CRONOS_SUBDIR = ".cronos"
MEMORY_SUBDIR = "memory"
ITEMS_SUBDIR = "items"
INDEX_FILE = "index.md"

_KIND_ORDER = [
    MemoryKind.FACT,
    MemoryKind.PROCEDURE,
    MemoryKind.OBSERVATION,
    MemoryKind.REFERENCE,
]
_KIND_HEADER = {
    MemoryKind.FACT: "Facts",
    MemoryKind.PROCEDURE: "Procedures",
    MemoryKind.OBSERVATION: "Observations",
    MemoryKind.REFERENCE: "References",
}


class MemoryNotFound(Exception):
    pass


class MemoryStore:
    """Persist memory items as markdown-with-frontmatter files.

    Storage layout:
        /data/memory/items/{id}.md          global scope
        /data/memory/index.md
        /data/spaces/{space_id}/.cronos/memory/items/{id}.md  per-space scope
        /data/spaces/{space_id}/.cronos/memory/index.md
    """

    def __init__(self, data_dir: Path, spaces_dir: Path) -> None:
        self._data_dir = data_dir
        self._spaces_dir = spaces_dir
        self._lock = asyncio.Lock()

    # ---- path helpers ----

    def _scope_dir(self, scope: str) -> Path:
        if scope == "global":
            return self._data_dir / "memory"
        if scope.startswith("space:"):
            space_id = scope[len("space:"):]
            return self._spaces_dir / space_id / CRONOS_SUBDIR / MEMORY_SUBDIR
        raise ValueError(f"Invalid scope: {scope!r}")

    def _items_dir(self, scope: str) -> Path:
        return self._scope_dir(scope) / ITEMS_SUBDIR

    def _index_path(self, scope: str) -> Path:
        return self._scope_dir(scope) / INDEX_FILE

    def _item_path(self, scope: str, item_id: str) -> Path:
        return self._items_dir(scope) / f"{item_id}.md"

    # ---- serialization ----

    def _dump_item(self, item: MemoryItem) -> str:
        meta = {
            "id": item.id,
            "scope": item.scope,
            "kind": item.kind.value,
            "title": item.title,
            "confirmed": item.confirmed,
            "confidence": item.confidence,
            "score": item.score,
            "last_used_at": item.last_used_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ref_count": item.ref_count,
            "ttl_until": (
                item.ttl_until.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                if item.ttl_until
                else None
            ),
            "sources": list(item.sources),
            "links": list(item.links),
        }
        post = frontmatter.Post(item.body, **meta)
        return frontmatter.dumps(post) + "\n"

    def _load_item(self, path: Path) -> MemoryItem:
        post = frontmatter.load(path)
        meta = dict(post.metadata)

        last_used_at = meta.get("last_used_at")
        if isinstance(last_used_at, str):
            last_used_at = datetime.fromisoformat(last_used_at.replace("Z", "+00:00"))
        elif not isinstance(last_used_at, datetime):
            last_used_at = datetime.now(tz=UTC)

        ttl_until = meta.get("ttl_until")
        if isinstance(ttl_until, str):
            ttl_until = datetime.fromisoformat(ttl_until.replace("Z", "+00:00"))
        elif not isinstance(ttl_until, datetime):
            ttl_until = None

        return MemoryItem(
            id=meta["id"],
            scope=meta["scope"],
            kind=meta["kind"],
            title=meta["title"],
            body=post.content,
            confirmed=meta.get("confirmed", False),
            confidence=float(meta.get("confidence", 1.0)),
            score=float(meta.get("score", 0.0)),
            last_used_at=last_used_at,
            ref_count=int(meta.get("ref_count", 0)),
            ttl_until=ttl_until,
            sources=list(meta.get("sources") or []),
            links=list(meta.get("links") or []),
        )

    def _atomic_write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".tmp.{secrets.token_hex(4)}")
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    # ---- index ----

    def rebuild_index(self, scope: str, items: list[MemoryItem]) -> None:
        """Regenerate index.md for scope from items. Called after every write/delete."""
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        by_kind: dict[MemoryKind, list[MemoryItem]] = {k: [] for k in _KIND_ORDER}
        for item in items:
            bucket = by_kind.get(item.kind)
            if bucket is not None:
                bucket.append(item)
        for bucket in by_kind.values():
            bucket.sort(key=lambda x: x.score, reverse=True)

        lines = [
            f"# Memory Index — {scope}",
            f"Updated: {timestamp}",
            "",
        ]
        for kind in _KIND_ORDER:
            bucket = by_kind[kind]
            lines.append(f"## {_KIND_HEADER[kind]}")
            for item in bucket:
                badge = "✓" if item.confirmed else "?"
                last_used = item.last_used_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                lines.append(
                    f"- [[{item.id}]] **{item.title}** — {badge} score={item.score:.2f} last_used={last_used}"
                )
            lines.append("")

        content = "\n".join(lines)
        index_path = self._index_path(scope)
        try:
            self._atomic_write(index_path, content)
        except Exception:
            log.exception("Failed to write index for scope %s", scope)

    # ---- internal list (caller holds lock) ----

    def _list_scope_locked(self, scope: str) -> list[MemoryItem]:
        items_dir = self._items_dir(scope)
        if not items_dir.is_dir():
            return []
        result: list[MemoryItem] = []
        for path in sorted(items_dir.glob("*.md")):
            try:
                result.append(self._load_item(path))
            except Exception:
                log.warning("Skipping unreadable memory item %s", path)
        return result

    # ---- public API ----

    async def create(
        self,
        *,
        scope: str,
        kind: MemoryKind | str,
        title: str,
        body: str = "",
        confirmed: bool = False,
        confidence: float = 1.0,
        score: float = 0.0,
        last_used_at: datetime | None = None,
        ref_count: int = 0,
        ttl_until: datetime | None = None,
        sources: list[str] | None = None,
        links: list[str] | None = None,
    ) -> MemoryItem:
        if isinstance(kind, str):
            kind = MemoryKind(kind)
        async with self._lock:
            now = datetime.now(tz=UTC)
            item_id = f"mem-{now.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}"
            item = MemoryItem(
                id=item_id,
                scope=scope,
                kind=kind,
                title=title,
                body=body,
                confirmed=confirmed,
                confidence=confidence,
                score=score,
                last_used_at=last_used_at or now,
                ref_count=ref_count,
                ttl_until=ttl_until,
                sources=sources or [],
                links=links or [],
            )
            path = self._item_path(scope, item_id)
            self._atomic_write(path, self._dump_item(item))
            log.info("Created memory item %s in scope %s", item_id, scope)
            self.rebuild_index(scope, self._list_scope_locked(scope))
            return item

    async def get(self, scope: str, item_id: str) -> MemoryItem | None:
        async with self._lock:
            path = self._item_path(scope, item_id)
            if not path.exists():
                return None
            try:
                item = self._load_item(path)
            except Exception:
                log.exception("Failed to load memory item %s/%s", scope, item_id)
                return None
            now = datetime.now(tz=UTC)
            new_score, new_ttl = boost(item.score, item.ttl_until, now)
            new_ref_count = item.ref_count + 1
            boosted = item.model_copy(update={
                "score": new_score,
                "ref_count": new_ref_count,
                "last_used_at": now,
                "ttl_until": new_ttl,
            })
            if should_auto_confirm(new_ref_count):
                boosted = boosted.model_copy(update={"confirmed": True})
                log.info("Auto-confirmed memory item %s", item_id)
            self._atomic_write(path, self._dump_item(boosted))
            if boosted.confirmed != item.confirmed:
                self.rebuild_index(scope, self._list_scope_locked(scope))
            return boosted

    async def list_scope(self, scope: str) -> list[MemoryItem]:
        async with self._lock:
            return self._list_scope_locked(scope)

    async def update(
        self,
        scope: str,
        item_id: str,
        *,
        title: str | None = None,
        body: str | None = None,
        kind: MemoryKind | str | None = None,
        confirmed: bool | None = None,
        confidence: float | None = None,
        score: float | None = None,
        last_used_at: datetime | None = None,
        ref_count: int | None = None,
        ttl_until: datetime | None = None,
        sources: list[str] | None = None,
        links: list[str] | None = None,
    ) -> MemoryItem:
        async with self._lock:
            path = self._item_path(scope, item_id)
            if not path.exists():
                raise MemoryNotFound(f"{scope}/{item_id}")
            item = self._load_item(path)
            update_dict: dict = {}
            if title is not None:
                update_dict["title"] = title
            if body is not None:
                update_dict["body"] = body
            if kind is not None:
                update_dict["kind"] = MemoryKind(kind) if isinstance(kind, str) else kind
            if confirmed is not None:
                update_dict["confirmed"] = confirmed
            if confidence is not None:
                update_dict["confidence"] = confidence
            if score is not None:
                update_dict["score"] = score
            if last_used_at is not None:
                update_dict["last_used_at"] = last_used_at
            if ref_count is not None:
                update_dict["ref_count"] = ref_count
            if ttl_until is not None:
                update_dict["ttl_until"] = ttl_until
            if sources is not None:
                update_dict["sources"] = sources
            if links is not None:
                update_dict["links"] = links
            updated = item.model_copy(update=update_dict)
            self._atomic_write(path, self._dump_item(updated))
            self.rebuild_index(scope, self._list_scope_locked(scope))
            return updated

    async def delete(self, scope: str, item_id: str) -> None:
        async with self._lock:
            path = self._item_path(scope, item_id)
            if not path.exists():
                raise MemoryNotFound(f"{scope}/{item_id}")
            path.unlink()
            log.info("Deleted memory item %s from scope %s", item_id, scope)
            self.rebuild_index(scope, self._list_scope_locked(scope))

    async def read_index(self, scope: str) -> str | None:
        """Return the raw index.md content for a scope, or None if it doesn't exist."""
        index_path = self._index_path(scope)
        if not index_path.exists():
            return None
        try:
            return await asyncio.to_thread(index_path.read_text, encoding="utf-8")
        except Exception:
            log.exception("Failed to read index for scope %s", scope)
            return None
