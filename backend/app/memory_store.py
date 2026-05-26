from __future__ import annotations

import logging
from pathlib import Path

from .models import MemoryItem

log = logging.getLogger("cronos.memory_store")

_CRONOS_SUBDIR = ".cronos"


class MemoryStore:
    """File-backed store for MemoryItem objects.

    Global items live under ``global_root/``.
    Per-space items live under ``{spaces_root}/{space_id}/.cronos/memory/``.
    Each item is one JSON file named ``{id}.json``.
    """

    def __init__(self, spaces_root: Path, global_root: Path) -> None:
        self._spaces_root = spaces_root
        self._global_root = global_root
        self._global_root.mkdir(parents=True, exist_ok=True)

    def _space_dir(self, space_id: str) -> Path:
        return self._spaces_root / space_id / _CRONOS_SUBDIR / "memory"

    def _path_for(self, scope: str, item_id: str) -> Path:
        if scope == "global":
            return self._global_root / f"{item_id}.json"
        space_id = scope.removeprefix("space:")
        return self._space_dir(space_id) / f"{item_id}.json"

    def list_scope(self, scope: str) -> list[MemoryItem]:
        if scope == "global":
            d = self._global_root
        else:
            space_id = scope.removeprefix("space:")
            d = self._space_dir(space_id)
        if not d.exists():
            return []
        items: list[MemoryItem] = []
        for p in d.glob("*.json"):
            try:
                items.append(MemoryItem.model_validate_json(p.read_text()))
            except Exception:
                log.warning("Skipping malformed memory file %s", p)
        return items

    def create(self, item: MemoryItem) -> None:
        path = self._path_for(item.scope, item.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item.model_dump_json())

    def get(self, scope: str, item_id: str) -> MemoryItem | None:
        path = self._path_for(scope, item_id)
        if not path.exists():
            return None
        try:
            return MemoryItem.model_validate_json(path.read_text())
        except Exception:
            log.warning("Failed to parse memory item %s/%s", scope, item_id)
            return None

    def update(self, item: MemoryItem) -> None:
        self.create(item)

    def delete(self, scope: str, item_id: str) -> bool:
        path = self._path_for(scope, item_id)
        if path.exists():
            path.unlink()
            return True
        return False
