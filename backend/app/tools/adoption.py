from __future__ import annotations

import hashlib
import logging
import os
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

log = logging.getLogger(__name__)

_DATA_DIR = Path(os.environ.get("CRONOS_DATA_DIR", "/data"))
SPACES_DIR = _DATA_DIR / "spaces"
DISCOVERY_DB_PATH = _DATA_DIR / "cronos-index.db"
DISCOVERY_BASE = Path("/data/.cronos/discovery_sources")


class AdoptionError(Exception):
    pass


class AlreadyAdopted(AdoptionError):
    pass


class NotAdopted(AdoptionError):
    pass


class ItemNotFound(AdoptionError):
    pass


class AdoptionManifest(BaseModel):
    source_url: str
    source_slug: str
    source_path: str    # relative path within the source repo
    source_sha: str     # git commit SHA of source at adoption time
    adopted_at: datetime
    base_sha: str       # sha256 of files at adoption; baseline for drift detection
    local_sha: str      # current sha256 of local files
    evolved: bool = False  # True when local_sha != base_sha
    kind: str
    name: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _adopt_dir(space_id: str, kind: str, name: str, *, spaces_dir: Path) -> Path:
    return spaces_dir / space_id / ".cronos" / "tools" / kind / name


def _manifest_path(space_id: str, kind: str, name: str, *, spaces_dir: Path) -> Path:
    return _adopt_dir(space_id, kind, name, spaces_dir=spaces_dir) / "manifest.yml"


def _compute_sha(adopt_dir: Path) -> str:
    """SHA256 of all non-manifest files in adopt_dir, sorted by relative path."""
    files = sorted(
        p for p in adopt_dir.rglob("*")
        if p.is_file() and p.name != "manifest.yml"
    )
    h = hashlib.sha256()
    for f in files:
        h.update(str(f.relative_to(adopt_dir)).encode("utf-8"))
        h.update(b"\x00")
        h.update(f.read_bytes())
        h.update(b"\x00")
    return h.hexdigest()


def _write_manifest(path: Path, manifest: AdoptionManifest) -> None:
    """Atomically write AdoptionManifest as YAML via tmpfile + os.replace."""
    data = {
        "source_url": manifest.source_url,
        "source_slug": manifest.source_slug,
        "source_path": manifest.source_path,
        "source_sha": manifest.source_sha,
        "adopted_at": manifest.adopted_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_sha": manifest.base_sha,
        "local_sha": manifest.local_sha,
        "evolved": manifest.evolved,
        "kind": manifest.kind,
        "name": manifest.name,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp.{secrets.token_hex(4)}")
    try:
        tmp.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _read_manifest(path: Path) -> AdoptionManifest:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AdoptionManifest.model_validate(data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def adopt(
    space_id: str,
    source_slug: str,
    kind: str,
    name: str,
    *,
    spaces_dir: Path | None = None,
    discovery_base: Path | None = None,
    db_path: Path | None = None,
) -> AdoptionManifest:
    """Copy a discovered tool into the space's adopted-tools directory.

    Directory layout after adoption::

        {space}/.cronos/tools/{kind}/{name}/
            manifest.yml          ← metadata
            {name}.md             ← flat file (agent / command)
            SKILL.md              ← skill dir entry-point (skills only)
            ...                   ← other skill dir files

    Raises AlreadyAdopted if manifest.yml already exists in the destination.
    Raises ItemNotFound if the item is not in the discovery index or the
    source clone is missing.
    """
    _spaces = spaces_dir or SPACES_DIR
    _disc_base = discovery_base or DISCOVERY_BASE
    _db = db_path or DISCOVERY_DB_PATH

    dest = _adopt_dir(space_id, kind, name, spaces_dir=_spaces)
    if (dest / "manifest.yml").exists():
        raise AlreadyAdopted(f"{kind}/{name!r} already adopted in space {space_id!r}")

    from .index import list_discovered
    try:
        items = list_discovered(_db, kind=kind, source_slug=source_slug)
    except Exception as exc:
        raise ItemNotFound(
            f"Discovery DB unavailable or item {kind!r}/{name!r} from {source_slug!r} not found"
        ) from exc

    item = next((i for i in items if i.name == name), None)
    if item is None:
        raise ItemNotFound(
            f"No discovered {kind!r} named {name!r} from source {source_slug!r}"
        )

    source_path = _disc_base / source_slug / item.relative_path
    if not source_path.exists():
        raise ItemNotFound(
            f"Source path {item.relative_path!r} not found in clone {_disc_base / source_slug}"
        )

    dest.mkdir(parents=True, exist_ok=True)
    try:
        if source_path.is_dir():
            shutil.copytree(source_path, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(source_path, dest / f"{name}.md")
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise

    local_sha = _compute_sha(dest)
    manifest = AdoptionManifest(
        source_url=item.source_url,
        source_slug=source_slug,
        source_path=item.relative_path,
        source_sha=item.source_sha,
        adopted_at=datetime.now(tz=UTC),
        base_sha=local_sha,
        local_sha=local_sha,
        evolved=False,
        kind=kind,
        name=name,
    )
    _write_manifest(dest / "manifest.yml", manifest)
    log.info("Adopted %s/%s from %s into space %s", kind, name, source_slug, space_id)
    return manifest


async def unadopt(
    space_id: str,
    kind: str,
    name: str,
    *,
    spaces_dir: Path | None = None,
) -> None:
    """Soft-delete an adopted tool by moving it to the tools trash.

    Destination: ``{space}/.cronos/tools/.trash/{kind}/{name}-{ISO_STAMP}/``

    Raises NotAdopted if the item is not currently adopted.
    """
    _spaces = spaces_dir or SPACES_DIR
    dest = _adopt_dir(space_id, kind, name, spaces_dir=_spaces)
    if not (dest / "manifest.yml").exists():
        raise NotAdopted(f"{kind}/{name!r} is not adopted in space {space_id!r}")

    trash_root = _spaces / space_id / ".cronos" / "tools" / ".trash" / kind
    trash_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    trash_dest = trash_root / f"{name}-{stamp}"
    os.replace(dest, trash_dest)
    log.info(
        "Unadopted %s/%s in space %s → .trash/%s/%s-%s",
        kind, name, space_id, kind, name, stamp,
    )


def recompute_local_sha(
    space_id: str,
    kind: str,
    name: str,
    *,
    spaces_dir: Path | None = None,
) -> AdoptionManifest:
    """Recompute local_sha for an adopted tool and persist the updated manifest.

    Returns the (possibly unchanged) manifest.
    Raises NotAdopted if the item is not currently adopted.
    """
    _spaces = spaces_dir or SPACES_DIR
    mpath = _manifest_path(space_id, kind, name, spaces_dir=_spaces)
    if not mpath.exists():
        raise NotAdopted(f"{kind}/{name!r} is not adopted in space {space_id!r}")

    adopt_dir = _adopt_dir(space_id, kind, name, spaces_dir=_spaces)
    local_sha = _compute_sha(adopt_dir)
    manifest = _read_manifest(mpath)

    if manifest.local_sha == local_sha:
        return manifest

    updated = manifest.model_copy(update={
        "local_sha": local_sha,
        "evolved": local_sha != manifest.base_sha,
    })
    _write_manifest(mpath, updated)
    log.debug(
        "Updated local_sha for %s/%s in space %s: %s",
        kind, name, space_id, local_sha[:8],
    )
    return updated


def finalize_merge(
    space_id: str,
    kind: str,
    name: str,
    upstream_source_sha: str,
    *,
    spaces_dir: Path | None = None,
) -> AdoptionManifest:
    """Update manifest after a merge task resolves an upstream advance.

    Sets local_sha = sha256(resolved content), base_sha = local_sha,
    source_sha = upstream_source_sha, evolved = False.

    Raises NotAdopted if the item is not currently adopted.
    """
    _spaces = spaces_dir or SPACES_DIR
    mpath = _manifest_path(space_id, kind, name, spaces_dir=_spaces)
    if not mpath.exists():
        raise NotAdopted(f"{kind}/{name!r} is not adopted in space {space_id!r}")

    adopt_dir = _adopt_dir(space_id, kind, name, spaces_dir=_spaces)
    local_sha = _compute_sha(adopt_dir)
    manifest = _read_manifest(mpath)

    updated = manifest.model_copy(update={
        "source_sha": upstream_source_sha,
        "base_sha": local_sha,
        "local_sha": local_sha,
        "evolved": False,
    })
    _write_manifest(mpath, updated)
    log.info(
        "Finalized merge for %s/%s in space %s → source_sha=%s",
        kind, name, space_id, upstream_source_sha[:8],
    )
    return updated
