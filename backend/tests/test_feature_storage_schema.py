"""Tests for feature/fix storage schema additions (I2 reserved names).

Covers _ensure_db_schema column additions, index creation, and idempotency.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def _db_path(tmp_spaces_dir: Path) -> Path:
    """cronos-index.db lives one level above the spaces dir."""
    return tmp_spaces_dir.parent / "cronos-index.db"


def _column_names(db: Path) -> set[str]:
    con = sqlite3.connect(str(db))
    try:
        cur = con.execute("PRAGMA table_info(tasks)")
        return {row[1] for row in cur.fetchall()}
    finally:
        con.close()


def _index_names(db: Path) -> set[str]:
    con = sqlite3.connect(str(db))
    try:
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='index'")
        return {row[0] for row in cur.fetchall()}
    finally:
        con.close()


def test_feature_columns_present(tmp_spaces_dir, task_store):
    """All six new feature/fix columns must exist in the tasks table."""
    db = _db_path(tmp_spaces_dir)
    assert db.exists(), f"DB not found at {db}"
    cols = _column_names(db)
    for col in ("feature_state", "feature_key", "realizes", "issue_number", "issue_url", "proposed_issue_path"):
        assert col in cols, f"Expected column '{col}' missing from tasks table (found: {cols})"


def test_ensure_db_schema_feature(tmp_spaces_dir, task_store):
    """_ensure_db_schema must create the six columns with correct affinity."""
    db = _db_path(tmp_spaces_dir)
    assert db.exists(), f"DB not found at {db}"

    con = sqlite3.connect(str(db))
    try:
        info = {row[1]: row[2].upper() for row in con.execute("PRAGMA table_info(tasks)").fetchall()}
    finally:
        con.close()

    for col in ("feature_state", "feature_key", "realizes", "issue_url", "proposed_issue_path"):
        assert col in info, f"Column {col} missing"
        # SQLite normalises type declarations; just check TEXT affinity is there
        assert "TEXT" in info[col] or info[col] == "", f"Unexpected type for {col}: {info[col]}"

    assert "issue_number" in info
    assert "INTEGER" in info["issue_number"] or info["issue_number"] == "", (
        f"Unexpected type for issue_number: {info['issue_number']}"
    )


def test_idx_tasks_space_realizes(tmp_spaces_dir, task_store):
    """idx_tasks_space_realizes index must exist on (space_id, realizes)."""
    db = _db_path(tmp_spaces_dir)
    assert db.exists(), f"DB not found at {db}"
    indexes = _index_names(db)
    assert "idx_tasks_space_realizes" in indexes, (
        f"Index idx_tasks_space_realizes not found. Existing: {indexes}"
    )


async def test_migration_idempotent(tmp_spaces_dir, task_store):
    """Running reload_all (which calls _ensure_db_schema) twice must not raise."""
    await task_store.reload_all()
    db = _db_path(tmp_spaces_dir)
    assert db.exists(), "DB file should exist after second reload_all"
    cols = _column_names(db)
    assert "feature_state" in cols
    assert "idx_tasks_space_realizes" in _index_names(db)
