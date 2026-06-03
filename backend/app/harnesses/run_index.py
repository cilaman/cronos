"""
Append-only run index for a single harness.

Index path: {space_dir}/.cronos/harness-runs/{harness_id}-index.json
The file is a JSON array of RunSummary objects (newest-first when returned by read_index).
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# RunSummary dataclass
# ---------------------------------------------------------------------------


@dataclass
class RunSummary:
    """A lightweight summary of one harness run stored in the per-harness index."""

    run_id: str
    harness_id: str
    status: str  # 'running' | 'done' | 'failed' | 'cancelled'
    triggered_at: str  # ISO-8601 UTC
    finished_at: str | None = None

    def to_dict(self) -> dict:
        """Return a plain dict suitable for JSON serialisation."""
        return {
            "run_id": self.run_id,
            "harness_id": self.harness_id,
            "status": self.status,
            "triggered_at": self.triggered_at,
            "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunSummary":
        """Reconstruct a RunSummary from the plain dict produced by to_dict()."""
        return cls(
            run_id=data["run_id"],
            harness_id=data["harness_id"],
            status=data["status"],
            triggered_at=data["triggered_at"],
            finished_at=data.get("finished_at"),
        )


# ---------------------------------------------------------------------------
# Per-file asyncio locks
# ---------------------------------------------------------------------------

_index_locks: dict[Path, asyncio.Lock] = {}


def _get_lock(path: Path) -> asyncio.Lock:
    """Return (lazily creating) the asyncio.Lock for the given index file path."""
    if path not in _index_locks:
        _index_locks[path] = asyncio.Lock()
    return _index_locks[path]


# ---------------------------------------------------------------------------
# Path helper
# ---------------------------------------------------------------------------


def _index_path(space_dir: Path, harness_id: str) -> Path:
    """Return the canonical path for the given harness's run index file."""
    return space_dir / ".cronos" / "harness-runs" / f"{harness_id}-index.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def read_index(space_dir: Path, harness_id: str) -> list[RunSummary]:
    """
    Read the run index for *harness_id* from *space_dir*.

    Returns an empty list (never raises) when the index file does not exist.
    Entries are returned in ascending insertion order (i.e. oldest first —
    the same order they were appended to the file).
    """
    path = _index_path(space_dir, harness_id)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        raw: list[dict] = json.load(fh)
    return [RunSummary.from_dict(entry) for entry in raw]


async def append_run(space_dir: Path, harness_id: str, summary: RunSummary) -> None:
    """
    Append *summary* to the run index for *harness_id*.

    Acquires the per-file asyncio lock before loading and releases it after
    the atomic save, guaranteeing that concurrent calls from multiple coroutines
    do not corrupt the index file.
    """
    path = _index_path(space_dir, harness_id)
    lock = _get_lock(path)
    async with lock:
        # Load existing entries (or start with an empty list).
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                entries: list[dict] = json.load(fh)
        else:
            entries = []

        entries.append(summary.to_dict())
        _save_atomic(path, entries)


async def update_run_status(
    space_dir: Path,
    harness_id: str,
    run_id: str,
    status: str,
    finished_at: str | None = None,
) -> None:
    """
    Update the *status* (and optionally *finished_at*) of the run matching
    *run_id* in the index.

    If no entry with *run_id* is found the function does nothing (idempotent).
    Acquires the per-file asyncio lock around load-mutate-save.
    """
    path = _index_path(space_dir, harness_id)
    lock = _get_lock(path)
    async with lock:
        if not path.exists():
            return

        with path.open("r", encoding="utf-8") as fh:
            entries: list[dict] = json.load(fh)

        found = False
        for entry in entries:
            if entry.get("run_id") == run_id:
                entry["status"] = status
                if finished_at is not None:
                    entry["finished_at"] = finished_at
                found = True
                break

        if not found:
            return  # idempotent — nothing to do

        _save_atomic(path, entries)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _save_atomic(path: Path, entries: list[dict]) -> None:
    """
    Atomically write *entries* to *path* as a JSON array.

    Uses a sibling temporary file + os.replace() so readers always see a
    complete file — even if the process is killed mid-write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(entries, indent=2, ensure_ascii=False)

    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".run_index_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
