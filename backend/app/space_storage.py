from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import Space
from .storage import _iso, atomic_write, slugify

log = logging.getLogger(__name__)

_SPACE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# Top-level directory entries inside `/data/spaces/` that are NOT real spaces.
RESERVED_SPACE_DIRS: frozenset[str] = frozenset({".trash", ".imports"})


class SpaceError(Exception):
    """Raised for invalid space operations."""


class SpaceNotFound(SpaceError):
    pass


class SpaceExists(SpaceError):
    pass


def validate_space_id(space_id: str) -> None:
    if not _SPACE_ID_RE.match(space_id):
        raise SpaceError(
            f"Invalid space id {space_id!r}: must be kebab-case, 1-40 chars, "
            "start with [a-z0-9]"
        )
    if space_id in RESERVED_SPACE_DIRS:
        raise SpaceError(f"Space id {space_id!r} is reserved")


def validate_color(color: str) -> None:
    if not _HEX_RE.match(color):
        raise SpaceError(f"Invalid color {color!r}: must be #RRGGBB hex")


def parse_space_yaml(path: Path) -> Space:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    # Authoritative id comes from the parent directory, not the yaml content.
    data["id"] = path.parent.name
    try:
        return Space.model_validate(data)
    except ValidationError as e:
        raise SpaceError(f"Invalid space file {path}: {e}") from e


def dump_space(space: Space) -> str:
    data = {
        "id": space.id,
        "name": space.name,
        "color": space.color,
        "icon": space.icon,
        "description": space.description,
        "created_at": _iso(space.created_at),
        "updated_at": _iso(space.updated_at),
        "git_repo_url": space.git_repo_url,
        "git_branch": space.git_branch,
        "agent_defaults": dict(space.agent_defaults),
    }
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


class SpaceStore:
    """In-memory index over `/data/spaces/{space_id}/space.yml` files.

    Mirrors the shape of `TaskStore`: async-locked mutations, atomic writes,
    soft-delete to `.trash/`. Path-based discovery — the on-disk directory
    name is the authoritative space id.
    """

    def __init__(self, spaces_dir: Path) -> None:
        self.spaces_dir = spaces_dir
        self.trash_dir = spaces_dir / ".trash"
        self.imports_dir = spaces_dir / ".imports"
        self._by_id: dict[str, Space] = {}
        self._lock = asyncio.Lock()

    # ---- index ----

    async def reload_all(self) -> None:
        async with self._lock:
            self._by_id.clear()
            if not self.spaces_dir.exists():
                log.info("Spaces dir %s does not exist yet", self.spaces_dir)
                return
            for child in sorted(self.spaces_dir.iterdir()):
                if not child.is_dir() or child.name in RESERVED_SPACE_DIRS:
                    continue
                yml = child / "space.yml"
                if not yml.exists():
                    log.warning("Skipping %s (no space.yml)", child)
                    continue
                try:
                    space = parse_space_yaml(yml)
                except SpaceError as e:
                    log.warning("Skipping invalid space: %s", e)
                    continue
                self._by_id[space.id] = space
            log.info("Loaded %d spaces from %s", len(self._by_id), self.spaces_dir)

    async def reindex_path(self, path: Path) -> None:
        async with self._lock:
            self._reindex_locked(path)

    def _reindex_locked(self, path: Path) -> None:
        # Only react to `{spaces_dir}/{id}/space.yml`.
        try:
            rel = path.relative_to(self.spaces_dir)
        except ValueError:
            return
        if rel.parts and rel.parts[0] in RESERVED_SPACE_DIRS:
            return
        if len(rel.parts) != 2 or rel.parts[1] != "space.yml":
            return
        space_id = rel.parts[0]
        if not path.exists():
            if space_id in self._by_id:
                self._by_id.pop(space_id, None)
                log.info("Removed space %s (file deleted)", space_id)
            return
        try:
            space = parse_space_yaml(path)
        except SpaceError as e:
            log.warning("Skipping invalid space: %s", e)
            return
        self._by_id[space.id] = space

    # ---- reads ----

    def get(self, space_id: str) -> Space | None:
        return self._by_id.get(space_id)

    def list_all(self) -> list[Space]:
        return sorted(self._by_id.values(), key=lambda s: s.created_at)

    def count(self) -> int:
        return len(self._by_id)

    def exists(self, space_id: str) -> bool:
        return space_id in self._by_id

    # ---- mutations ----

    async def create(
        self,
        *,
        name: str,
        color: str,
        icon: str | None = None,
        description: str = "",
        space_id: str | None = None,
    ) -> Space:
        validate_color(color)
        async with self._lock:
            sid = space_id or slugify(name)
            if not sid:
                raise SpaceError("Empty space id")
            validate_space_id(sid)
            if sid in self._by_id:
                raise SpaceExists(sid)
            now = datetime.now(tz=UTC)
            space = Space(
                id=sid,
                name=name.strip(),
                color=color,
                icon=(icon or None),
                description=description.strip(),
                created_at=now,
                updated_at=now,
            )
            space_dir = self.spaces_dir / sid
            (space_dir / "tasks").mkdir(parents=True, exist_ok=True)
            (space_dir / "workspaces").mkdir(parents=True, exist_ok=True)
            atomic_write(space_dir / "space.yml", dump_space(space))
            self._by_id[sid] = space
            log.info("Created space %s", sid)
            return space

    async def update(
        self,
        space_id: str,
        *,
        name: str | None = None,
        color: str | None = None,
        icon: str | None = None,
        description: str | None = None,
        clear_icon: bool = False,
    ) -> Space:
        if color is not None:
            validate_color(color)
        async with self._lock:
            space = self._by_id.get(space_id)
            if space is None:
                raise SpaceNotFound(space_id)
            updated = space.model_copy(
                update={
                    "name": name.strip() if name is not None else space.name,
                    "color": color if color is not None else space.color,
                    "icon": None if clear_icon else (icon if icon is not None else space.icon),
                    "description": (
                        description.strip() if description is not None else space.description
                    ),
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            atomic_write(self.spaces_dir / space_id / "space.yml", dump_space(updated))
            self._by_id[space_id] = updated
            return updated

    async def delete(self, space_id: str) -> None:
        """Soft-delete by moving the entire space directory into `.trash/`."""
        async with self._lock:
            if space_id not in self._by_id:
                raise SpaceNotFound(space_id)
            src = self.spaces_dir / space_id
            self.trash_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
            dest = self.trash_dir / f"{space_id}.{stamp}"
            os.replace(src, dest)
            self._by_id.pop(space_id, None)
            log.info("Trashed space %s -> %s", space_id, dest.name)

    # ---- helpers ----

    def space_dir(self, space_id: str) -> Path:
        return self.spaces_dir / space_id

    def tasks_dir(self, space_id: str) -> Path:
        return self.spaces_dir / space_id / "tasks"

    def workspaces_dir(self, space_id: str) -> Path:
        return self.spaces_dir / space_id / "workspaces"

    def ensure_dirs(self) -> None:
        self.spaces_dir.mkdir(parents=True, exist_ok=True)

    def free_imports_dir(self) -> Path:
        self.imports_dir.mkdir(parents=True, exist_ok=True)
        return self.imports_dir
