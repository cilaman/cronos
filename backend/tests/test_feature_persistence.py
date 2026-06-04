"""Tests for feature/fix DB persistence (I9 reserved names).

Verifies that _db_upsert and reload_all correctly persist and restore feature fields.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.models import FeatureState

SPACE_ID = "test-space"


def _db_path(tmp_spaces_dir: Path) -> Path:
    return tmp_spaces_dir.parent / "cronos-index.db"


def _read_feature_row(db: Path, task_id: str) -> dict:
    con = sqlite3.connect(str(db))
    try:
        cur = con.execute(
            "SELECT feature_state, feature_key, realizes, issue_number, issue_url, proposed_issue_path "
            "FROM tasks WHERE id = ?",
            (task_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {}
        keys = ("feature_state", "feature_key", "realizes", "issue_number", "issue_url", "proposed_issue_path")
        return dict(zip(keys, row))
    finally:
        con.close()


# ---------------------------------------------------------------------------
# I9: DB persistence for feature fields
# ---------------------------------------------------------------------------


async def test_db_upsert_feature_persists(tmp_spaces_dir, task_store):
    """_db_upsert must write feature_state and feature_key to SQLite."""
    feat = await task_store.create(
        space_id=SPACE_ID, title="DB persist test", brief="", type="feature"
    )
    db = _db_path(tmp_spaces_dir)
    assert db.exists(), f"DB not found at {db}"

    row = _read_feature_row(db, feat.id)
    assert row["feature_state"] == "backlog", f"Expected 'backlog', got {row['feature_state']}"
    assert row["feature_key"] == "FEAT-001", f"Expected 'FEAT-001', got {row['feature_key']}"


async def test_reload_all_feature_persists(tmp_spaces_dir, task_store):
    """After reload_all, feature fields must still be present in the in-memory store."""
    feat = await task_store.create(
        space_id=SPACE_ID, title="Reload test", brief="", type="feature"
    )
    original_key = feat.feature_key

    # Reload the store
    await task_store.reload_all()

    reloaded = task_store.get(feat.id)
    assert reloaded is not None, "Task not found after reload_all"
    assert reloaded.feature_state == FeatureState.BACKLOG
    assert reloaded.feature_key == original_key


async def test_feature_row_after_reload(tmp_spaces_dir, task_store):
    """SQLite row must have correct feature values even after a second reload_all."""
    feat = await task_store.create(
        space_id=SPACE_ID, title="Row reload test", brief="", type="fix"
    )
    feat_id = feat.id

    # Two reloads to exercise the idempotent migration + insert path
    await task_store.reload_all()
    await task_store.reload_all()

    db = _db_path(tmp_spaces_dir)
    row = _read_feature_row(db, feat_id)
    assert row.get("feature_state") == "backlog", f"feature_state lost after reload: {row}"
    assert row.get("feature_key") == "FIX-001", f"feature_key lost after reload: {row}"
    assert row.get("realizes") is None
