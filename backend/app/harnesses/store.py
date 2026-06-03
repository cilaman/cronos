"""
backend/app/harnesses/store — Async YAML-backed harness store.

Persistence layout:
  {space_dir}/.cronos/harnesses/<slugified_name>.yml

Every mutating operation acquires ``_lock`` before touching the in-memory
index or the filesystem.  Atomic writes use tmpfile + os.replace, mirroring
``storage.py::atomic_write``.

In-memory index:
  _by_space: dict[str, dict[str, Harness]]
  Keyed by (space_dir, name) where the outer key is the canonicalized
  space directory path and the inner key is the harness *name* (case-sensitive).

Concurrency note (R13):
  This store implements last-writer-wins semantics.  Callers that hold a
  ``Harness`` reference across an ``await`` boundary may observe a stale
  model.  Callers MUST re-fetch from ``HarnessStore.get`` after every
  ``await`` boundary; do not pass ``Harness`` models across async hops by
  reference.  A future executor phase will add optimistic-locking; this is
  explicitly deferred per the analysis report.
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path

import yaml

from app.harnesses.model import Harness
from app.harnesses.validator import HarnessGraphError, validate_graph

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class HarnessNotFound(Exception):
    """Raised when a harness name does not exist in the given space."""


class HarnessNameConflict(Exception):
    """Raised when attempting to create a harness whose name already exists."""


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_MULTI_HYPHEN_RE = re.compile(r"-{2,}")


def slugify_name(name: str) -> str:
    """Derive a filesystem-safe slug from a harness name.

    Rules:
    1. Lowercase.
    2. Replace all non-alphanumeric characters with a single hyphen.
    3. Collapse multiple consecutive hyphens into one.
    4. Strip leading/trailing hyphens.
    5. If the result is empty, use "harness".
    """
    slug = name.lower()
    slug = _NON_ALNUM_RE.sub("-", slug)
    slug = _MULTI_HYPHEN_RE.sub("-", slug)
    slug = slug.strip("-")
    return slug or "harness"


def _harnesses_dir(space_dir: str | Path) -> Path:
    """Return the .cronos/harnesses directory for the given space directory."""
    return Path(space_dir) / ".cronos" / "harnesses"


def _yaml_path(harnesses_dir: Path, slug: str) -> Path:
    return harnesses_dir / f"{slug}.yml"


def _harness_to_dict(harness: Harness) -> dict:
    """Serialise a Harness to a plain dict suitable for yaml.safe_dump.

    Datetime fields are emitted as ISO-8601 UTC strings so yaml.safe_load can
    reconstruct them without relying on YAML's !!python/object tags (which
    safe_load would reject).

    We use model_dump(mode='json') which converts datetimes to ISO strings and
    enums to their string values, giving us a json-serialisable dict.  We then
    re-dump it through yaml.safe_dump so it is human-readable.
    """
    return harness.model_dump(mode="json")


def _dict_to_harness(data: dict) -> Harness:
    """Deserialise a plain dict (from yaml.safe_load) back into a Harness.

    Pydantic v2 is happy to construct datetimes from ISO-8601 strings.
    """
    return Harness.model_validate(data)


def _atomic_write_yaml(path: Path, data: dict) -> None:
    """Write *data* as YAML to *path* atomically (tmpfile + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".yml.tmp.{secrets.token_hex(4)}")
    text = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# HarnessStore
# ---------------------------------------------------------------------------


class HarnessStore:
    """Async YAML-backed store for Harness objects.

    The store maintains a nested in-memory index::

        _by_space: dict[str, dict[str, Harness]]

    where the outer key is the *canonicalized absolute path* of the space
    directory (``str(Path(space_dir).resolve())``) and the inner key is the
    harness *name*.

    A separate index maps (space_key, slug) → harness name to detect slug
    collisions on disk.
    """

    def __init__(self) -> None:
        self._lock: asyncio.Lock = asyncio.Lock()
        # Outer key: canonical space dir path (str).
        # Inner key: harness name.
        self._by_space: dict[str, dict[str, Harness]] = {}
        # Tracks which disk slug is used by which harness name:
        # (space_key, slug) -> name
        self._slug_by_name: dict[str, dict[str, str]] = {}
        # Reverse: (space_key, name) -> slug
        self._name_to_slug: dict[str, dict[str, str]] = {}

    # ------------------------------------------------------------------
    # Internal helpers (must be called with _lock held)
    # ------------------------------------------------------------------

    def _space_key(self, space_dir: str | Path) -> str:
        return str(Path(space_dir).resolve())

    def _ensure_space(self, space_key: str) -> None:
        self._by_space.setdefault(space_key, {})
        self._slug_by_name.setdefault(space_key, {})
        self._name_to_slug.setdefault(space_key, {})

    def _pick_slug(
        self,
        space_key: str,
        name: str,
        harnesses_dir: Path,
    ) -> str:
        """Return a unique slug for *name* in *space_key*.

        Checks both the in-memory slug→name index AND on-disk filename
        presence to detect collisions from harnesses added outside the
        current process lifetime.
        """
        base = slugify_name(name)
        candidate = base
        suffix = 2
        slug_to_name = self._slug_by_name.get(space_key, {})
        while True:
            # Check in-memory: slug must not be taken by a *different* name.
            existing_name = slug_to_name.get(candidate)
            if existing_name is not None and existing_name != name:
                candidate = f"{base}-{suffix}"
                suffix += 1
                continue
            # Check disk: file must not exist (unless it belongs to *name*).
            disk_path = _yaml_path(harnesses_dir, candidate)
            if disk_path.exists():
                # If we already own this slug in memory it is fine.
                if existing_name == name:
                    break
                # Disk file exists but not in memory → foreign / stale file;
                # treat as occupied.
                candidate = f"{base}-{suffix}"
                suffix += 1
                continue
            break
        return candidate

    # ------------------------------------------------------------------
    # Public async CRUD
    # ------------------------------------------------------------------

    async def create(self, space_dir: str | Path, harness: Harness) -> Harness:
        """Persist a new harness.

        Parameters
        ----------
        space_dir:
            Absolute path to the space root directory.
        harness:
            The harness to create.  ``created_at`` and ``updated_at``
            are the caller's responsibility.

        Raises
        ------
        HarnessNameConflict
            If a harness with ``harness.name`` already exists in this space.
        HarnessGraphError
            If the harness graph contains a cycle or self-loop.
        """
        validate_graph(harness)
        async with self._lock:
            space_key = self._space_key(space_dir)
            self._ensure_space(space_key)
            if harness.name in self._by_space[space_key]:
                raise HarnessNameConflict(
                    f"Harness '{harness.name}' already exists in space '{space_dir}'"
                )
            harnesses_dir = _harnesses_dir(space_dir)
            slug = self._pick_slug(space_key, harness.name, harnesses_dir)
            path = _yaml_path(harnesses_dir, slug)
            _atomic_write_yaml(path, _harness_to_dict(harness))
            self._by_space[space_key][harness.name] = harness
            self._slug_by_name[space_key][slug] = harness.name
            self._name_to_slug[space_key][harness.name] = slug
        return harness

    async def get(self, space_dir: str | Path, name: str) -> Harness:
        """Return the harness with the given *name*.

        Raises
        ------
        HarnessNotFound
            If no harness with *name* exists in this space.
        """
        async with self._lock:
            space_key = self._space_key(space_dir)
            self._ensure_space(space_key)
            harness = self._by_space[space_key].get(name)
            if harness is None:
                raise HarnessNotFound(
                    f"Harness '{name}' not found in space '{space_dir}'"
                )
            return harness

    async def list(self, space_dir: str | Path) -> list[Harness]:
        """Return all harnesses in the given space (order: insertion order)."""
        async with self._lock:
            space_key = self._space_key(space_dir)
            self._ensure_space(space_key)
            return list(self._by_space[space_key].values())

    async def update(
        self,
        space_dir: str | Path,
        name: str,
        harness: Harness,
    ) -> Harness:
        """Replace the harness named *name* with *harness*.

        ``updated_at`` should be set by the caller before passing *harness*.

        Raises
        ------
        HarnessNotFound
            If no harness with *name* exists in this space.
        HarnessGraphError
            If the replacement harness graph contains a cycle or self-loop.
        """
        validate_graph(harness)
        async with self._lock:
            space_key = self._space_key(space_dir)
            self._ensure_space(space_key)
            if name not in self._by_space[space_key]:
                raise HarnessNotFound(
                    f"Harness '{name}' not found in space '{space_dir}'"
                )
            harnesses_dir = _harnesses_dir(space_dir)
            slug = self._name_to_slug[space_key][name]
            path = _yaml_path(harnesses_dir, slug)
            _atomic_write_yaml(path, _harness_to_dict(harness))
            self._by_space[space_key][name] = harness
        return harness

    async def delete(self, space_dir: str | Path, name: str) -> None:
        """Remove the harness named *name* from the store and disk.

        Raises
        ------
        HarnessNotFound
            If no harness with *name* exists in this space.
        """
        async with self._lock:
            space_key = self._space_key(space_dir)
            self._ensure_space(space_key)
            if name not in self._by_space[space_key]:
                raise HarnessNotFound(
                    f"Harness '{name}' not found in space '{space_dir}'"
                )
            slug = self._name_to_slug[space_key].pop(name)
            del self._by_space[space_key][name]
            self._slug_by_name[space_key].pop(slug, None)
            harnesses_dir = _harnesses_dir(space_dir)
            path = _yaml_path(harnesses_dir, slug)
            if path.exists():
                path.unlink()
