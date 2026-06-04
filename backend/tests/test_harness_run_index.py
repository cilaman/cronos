"""
Tests for backend/app/harnesses/run_index.py

Covers:
  - read_index returns [] when the index file is missing (not None, not raise)
  - append_run + read_index round-trip
  - multiple appends preserve insertion order
  - update_run_status updates status and finished_at
  - update_run_status with unknown run_id is a no-op (idempotent)
  - read_index returns a list instance (not None) for a missing file
  - 20 concurrent append_run calls all survive without loss (lock safety)
  - _save_atomic creates parent directories that don't exist yet
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.harnesses.run_index import (
    RunSummary,
    _index_path,
    append_run,
    read_index,
    update_run_status,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_summary(
    run_id: str = "run-001",
    harness_id: str = "h1",
    status: str = "running",
    triggered_at: str = "2026-01-01T00:00:00Z",
    finished_at: str | None = None,
) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        harness_id=harness_id,
        status=status,
        triggered_at=triggered_at,
        finished_at=finished_at,
    )


# ---------------------------------------------------------------------------
# read_index — missing file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_index_returns_empty_when_file_missing(tmp_path: Path) -> None:
    """read_index must return [] when the index file does not exist."""
    result = await read_index(tmp_path, "no-such-harness")
    assert result == []


@pytest.mark.asyncio
async def test_read_index_returns_empty_not_none_for_missing_file(tmp_path: Path) -> None:
    """read_index must return a list instance, never None, for a missing file."""
    result = await read_index(tmp_path, "nonexistent-harness")
    assert isinstance(result, list)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# append_run + read_index round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_append_and_read_round_trip(tmp_path: Path) -> None:
    """append_run followed by read_index returns the same RunSummary."""
    summary = _make_summary(
        run_id="run-abc",
        harness_id="harness-1",
        status="running",
        triggered_at="2026-06-01T12:00:00Z",
    )
    await append_run(tmp_path, "harness-1", summary)

    entries = await read_index(tmp_path, "harness-1")
    assert len(entries) == 1
    got = entries[0]
    assert got.run_id == "run-abc"
    assert got.harness_id == "harness-1"
    assert got.status == "running"
    assert got.triggered_at == "2026-06-01T12:00:00Z"
    assert got.finished_at is None


# ---------------------------------------------------------------------------
# Multiple appends preserve insertion order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_append_multiple_preserves_order(tmp_path: Path) -> None:
    """Three sequential appends are returned in insertion order by read_index."""
    harness_id = "harness-order"
    s1 = _make_summary("run-1", harness_id, triggered_at="2026-01-01T00:00:00Z")
    s2 = _make_summary("run-2", harness_id, triggered_at="2026-01-02T00:00:00Z")
    s3 = _make_summary("run-3", harness_id, triggered_at="2026-01-03T00:00:00Z")

    await append_run(tmp_path, harness_id, s1)
    await append_run(tmp_path, harness_id, s2)
    await append_run(tmp_path, harness_id, s3)

    entries = await read_index(tmp_path, harness_id)
    assert len(entries) == 3
    assert entries[0].run_id == "run-1"
    assert entries[1].run_id == "run-2"
    assert entries[2].run_id == "run-3"


# ---------------------------------------------------------------------------
# update_run_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_run_status_updates_correctly(tmp_path: Path) -> None:
    """After appending a run, update_run_status changes status and finished_at."""
    harness_id = "harness-update"
    summary = _make_summary(
        run_id="run-upd",
        harness_id=harness_id,
        status="running",
        triggered_at="2026-06-01T10:00:00Z",
    )
    await append_run(tmp_path, harness_id, summary)

    await update_run_status(
        tmp_path,
        harness_id,
        "run-upd",
        status="done",
        finished_at="2026-06-01T10:05:00Z",
    )

    entries = await read_index(tmp_path, harness_id)
    assert len(entries) == 1
    assert entries[0].status == "done"
    assert entries[0].finished_at == "2026-06-01T10:05:00Z"


@pytest.mark.asyncio
async def test_update_run_status_unknown_run_id_is_noop(tmp_path: Path) -> None:
    """update_run_status with an unknown run_id leaves the index unchanged."""
    harness_id = "harness-noop"
    summary = _make_summary(run_id="run-known", harness_id=harness_id, status="running")
    await append_run(tmp_path, harness_id, summary)

    # Updating a non-existent run_id must not raise and must not modify the index.
    await update_run_status(tmp_path, harness_id, "run-unknown", status="done")

    entries = await read_index(tmp_path, harness_id)
    assert len(entries) == 1
    assert entries[0].run_id == "run-known"
    assert entries[0].status == "running"
    assert entries[0].finished_at is None


@pytest.mark.asyncio
async def test_update_run_status_on_missing_index_is_noop(tmp_path: Path) -> None:
    """update_run_status against a missing index file does nothing (no exception)."""
    await update_run_status(tmp_path, "never-existed", "run-x", status="done")
    # No file should be created
    assert not _index_path(tmp_path, "never-existed").exists()


# ---------------------------------------------------------------------------
# Concurrent appends — asyncio.Lock safety
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_appends(tmp_path: Path) -> None:
    """
    20 concurrent append_run calls on the same harness must all survive.

    This validates that the per-file asyncio.Lock prevents lost-update
    corruption under concurrency.
    """
    harness_id = "harness-concurrent"
    n = 20

    summaries = [
        _make_summary(
            run_id=f"run-{i:03d}",
            harness_id=harness_id,
            triggered_at=f"2026-01-01T00:{i:02d}:00Z",
        )
        for i in range(n)
    ]

    await asyncio.gather(*(append_run(tmp_path, harness_id, s) for s in summaries))

    entries = await read_index(tmp_path, harness_id)
    assert len(entries) == n, (
        f"Expected {n} entries but got {len(entries)} — possible lost-update under concurrency"
    )

    # All run_ids must be present (no duplicates, no omissions)
    found_ids = {e.run_id for e in entries}
    expected_ids = {f"run-{i:03d}" for i in range(n)}
    assert found_ids == expected_ids


# ---------------------------------------------------------------------------
# Atomic save creates parent directories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_atomic_save_creates_parent_dirs(tmp_path: Path) -> None:
    """
    append_run to a harness whose index directory does not yet exist must
    succeed by creating the required parent directories.
    """
    # Use a nested space_dir that does not pre-exist
    deep_space = tmp_path / "spaces" / "my-space"
    harness_id = "harness-deep"

    assert not deep_space.exists()

    summary = _make_summary(run_id="run-deep", harness_id=harness_id)
    await append_run(deep_space, harness_id, summary)

    # The index file must now exist
    index_file = _index_path(deep_space, harness_id)
    assert index_file.exists()

    entries = await read_index(deep_space, harness_id)
    assert len(entries) == 1
    assert entries[0].run_id == "run-deep"


# ---------------------------------------------------------------------------
# RunSummary serialisation helpers
# ---------------------------------------------------------------------------


def test_run_summary_to_dict_and_from_dict() -> None:
    """to_dict / from_dict are inverses of each other."""
    original = RunSummary(
        run_id="r1",
        harness_id="h1",
        status="done",
        triggered_at="2026-06-01T00:00:00Z",
        finished_at="2026-06-01T00:05:00Z",
    )
    d = original.to_dict()
    restored = RunSummary.from_dict(d)

    assert restored.run_id == original.run_id
    assert restored.harness_id == original.harness_id
    assert restored.status == original.status
    assert restored.triggered_at == original.triggered_at
    assert restored.finished_at == original.finished_at


def test_run_summary_from_dict_missing_finished_at() -> None:
    """from_dict gracefully handles dicts without finished_at (defaults to None)."""
    data = {
        "run_id": "r2",
        "harness_id": "h2",
        "status": "running",
        "triggered_at": "2026-06-02T00:00:00Z",
    }
    rs = RunSummary.from_dict(data)
    assert rs.finished_at is None


# ---------------------------------------------------------------------------
# _index_path helper
# ---------------------------------------------------------------------------


def test_index_path_returns_correct_path(tmp_path: Path) -> None:
    """_index_path must return the canonical path under .cronos/harness-runs/."""
    p = _index_path(tmp_path, "my-harness")
    expected = tmp_path / ".cronos" / "harness-runs" / "my-harness-index.json"
    assert p == expected


# ---------------------------------------------------------------------------
# Update only updates the matching entry when multiple runs exist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_run_status_only_updates_matching_entry(tmp_path: Path) -> None:
    """update_run_status only modifies the entry with the matching run_id."""
    harness_id = "harness-selective"
    s1 = _make_summary("run-a", harness_id, status="done")
    s2 = _make_summary("run-b", harness_id, status="running")
    s3 = _make_summary("run-c", harness_id, status="running")

    await append_run(tmp_path, harness_id, s1)
    await append_run(tmp_path, harness_id, s2)
    await append_run(tmp_path, harness_id, s3)

    await update_run_status(
        tmp_path, harness_id, "run-b", status="failed", finished_at="2026-06-01T00:10:00Z"
    )

    entries = await read_index(tmp_path, harness_id)
    by_id = {e.run_id: e for e in entries}

    assert by_id["run-a"].status == "done"
    assert by_id["run-b"].status == "failed"
    assert by_id["run-b"].finished_at == "2026-06-01T00:10:00Z"
    assert by_id["run-c"].status == "running"
    assert by_id["run-c"].finished_at is None
