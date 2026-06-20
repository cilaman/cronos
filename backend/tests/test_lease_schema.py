"""I1: Verify that _ensure_db_schema() creates task_leases and auto_resume_counts tables."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.storage import TaskStore


def _table_names(db_path: Path) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        con.close()


def _column_names(db_path: Path, table: str) -> list[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
        return [r[1] for r in rows]
    finally:
        con.close()


@pytest.fixture()
def spaces_dir(tmp_path: Path) -> Path:
    d = tmp_path / "spaces"
    d.mkdir()
    return d


def test_task_leases_table_created(spaces_dir: Path) -> None:
    store = TaskStore(spaces_dir)
    store._ensure_db_schema()
    tables = _table_names(store._db_path)
    assert "task_leases" in tables


def test_auto_resume_counts_table_created(spaces_dir: Path) -> None:
    store = TaskStore(spaces_dir)
    store._ensure_db_schema()
    tables = _table_names(store._db_path)
    assert "auto_resume_counts" in tables


def test_task_leases_columns(spaces_dir: Path) -> None:
    store = TaskStore(spaces_dir)
    store._ensure_db_schema()
    cols = _column_names(store._db_path, "task_leases")
    assert "task_id" in cols
    assert "owner" in cols
    assert "lease_expiry" in cols
    assert "heartbeat_at" in cols


def test_auto_resume_counts_columns(spaces_dir: Path) -> None:
    store = TaskStore(spaces_dir)
    store._ensure_db_schema()
    cols = _column_names(store._db_path, "auto_resume_counts")
    assert "task_id" in cols
    assert "count" in cols


def test_ensure_db_schema_idempotent(spaces_dir: Path) -> None:
    store = TaskStore(spaces_dir)
    store._ensure_db_schema()
    store._ensure_db_schema()  # second call must not raise
    tables = _table_names(store._db_path)
    assert "task_leases" in tables
    assert "auto_resume_counts" in tables


def test_task_leases_pk_is_task_id(spaces_dir: Path) -> None:
    store = TaskStore(spaces_dir)
    store._ensure_db_schema()
    con = sqlite3.connect(store._db_path)
    try:
        rows = con.execute("PRAGMA table_info(task_leases)").fetchall()
        pk_cols = [r[1] for r in rows if r[5] == 1]
    finally:
        con.close()
    assert pk_cols == ["task_id"]
