"""I2: Tests for TaskStore lease and auto-resume-count CRUD methods."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.storage import TaskStore


@pytest.fixture()
def store(tmp_path: Path) -> TaskStore:
    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir()
    s = TaskStore(spaces_dir)
    s._ensure_db_schema()
    return s


# ---- acquire_lease ----

def test_acquire_lease_wins_on_empty(store: TaskStore) -> None:
    assert store.acquire_lease("t1", "owner-A", ttl=300) is True


def test_acquire_lease_idempotent_same_owner(store: TaskStore) -> None:
    # Same owner acquiring again fails (existing row, not expired).
    store.acquire_lease("t1", "owner-A", ttl=300)
    result = store.acquire_lease("t1", "owner-A", ttl=300)
    assert result is False  # row already exists


def test_acquire_lease_blocked_by_live_lease(store: TaskStore) -> None:
    store.acquire_lease("t1", "owner-A", ttl=300)
    assert store.acquire_lease("t1", "owner-B", ttl=300) is False


def test_acquire_lease_steals_expired(store: TaskStore) -> None:
    # Lease with TTL -1 is already expired.
    store.acquire_lease("t1", "owner-A", ttl=-1)
    assert store.acquire_lease("t1", "owner-B", ttl=300) is True


# ---- heartbeat_lease ----

def test_heartbeat_lease_updates_timestamp(store: TaskStore) -> None:
    import sqlite3
    store.acquire_lease("t1", "owner-A", ttl=300)
    before = time.time()
    store.heartbeat_lease("t1", "owner-A")
    con = sqlite3.connect(store._db_path)
    try:
        row = con.execute(
            "SELECT heartbeat_at FROM task_leases WHERE task_id = ?", ("t1",)
        ).fetchone()
    finally:
        con.close()
    assert row is not None
    assert row[0] >= before


def test_heartbeat_lease_noop_wrong_owner(store: TaskStore) -> None:
    import sqlite3
    store.acquire_lease("t1", "owner-A", ttl=300)
    con = sqlite3.connect(store._db_path)
    try:
        before = con.execute(
            "SELECT heartbeat_at FROM task_leases WHERE task_id = ?", ("t1",)
        ).fetchone()[0]
    finally:
        con.close()
    store.heartbeat_lease("t1", "owner-B")  # wrong owner, must be no-op
    con = sqlite3.connect(store._db_path)
    try:
        after = con.execute(
            "SELECT heartbeat_at FROM task_leases WHERE task_id = ?", ("t1",)
        ).fetchone()[0]
    finally:
        con.close()
    assert after == before


# ---- release_lease ----

def test_release_lease_removes_row(store: TaskStore) -> None:
    import sqlite3
    store.acquire_lease("t1", "owner-A", ttl=300)
    store.release_lease("t1", "owner-A")
    con = sqlite3.connect(store._db_path)
    try:
        row = con.execute(
            "SELECT 1 FROM task_leases WHERE task_id = ?", ("t1",)
        ).fetchone()
    finally:
        con.close()
    assert row is None


def test_release_lease_noop_wrong_owner(store: TaskStore) -> None:
    import sqlite3
    store.acquire_lease("t1", "owner-A", ttl=300)
    store.release_lease("t1", "owner-B")  # wrong owner
    con = sqlite3.connect(store._db_path)
    try:
        row = con.execute(
            "SELECT 1 FROM task_leases WHERE task_id = ?", ("t1",)
        ).fetchone()
    finally:
        con.close()
    assert row is not None  # row still exists


# ---- get_expired_leases ----

def test_get_expired_leases_by_expiry(store: TaskStore) -> None:
    store.acquire_lease("t1", "owner-A", ttl=-1)  # already expired
    store.acquire_lease("t2", "owner-B", ttl=300)  # still live
    expired = store.get_expired_leases(time.time(), heartbeat_timeout=9999)
    task_ids = {r[0] for r in expired}
    assert "t1" in task_ids
    assert "t2" not in task_ids


def test_get_expired_leases_by_stale_heartbeat(store: TaskStore) -> None:
    store.acquire_lease("t1", "owner-A", ttl=300)  # live expiry
    # Manually backdate heartbeat_at so it appears stale.
    import sqlite3
    con = sqlite3.connect(store._db_path)
    try:
        con.execute(
            "UPDATE task_leases SET heartbeat_at = ? WHERE task_id = ?",
            (time.time() - 1000, "t1"),
        )
        con.commit()
    finally:
        con.close()
    expired = store.get_expired_leases(time.time(), heartbeat_timeout=30)
    assert any(r[0] == "t1" for r in expired)


def test_get_expired_leases_empty_on_live(store: TaskStore) -> None:
    store.acquire_lease("t1", "owner-A", ttl=300)
    expired = store.get_expired_leases(time.time(), heartbeat_timeout=9999)
    assert expired == []


# ---- delete_expired_lease ----

def test_delete_expired_lease_removes_row(store: TaskStore) -> None:
    import sqlite3
    store.acquire_lease("t1", "owner-A", ttl=300)
    store.delete_expired_lease("t1")
    con = sqlite3.connect(store._db_path)
    try:
        row = con.execute(
            "SELECT 1 FROM task_leases WHERE task_id = ?", ("t1",)
        ).fetchone()
    finally:
        con.close()
    assert row is None


# ---- clear_all_leases ----

def test_clear_all_leases(store: TaskStore) -> None:
    import sqlite3
    store.acquire_lease("t1", "owner-A", ttl=300)
    store.acquire_lease("t2", "owner-B", ttl=300)
    store.clear_all_leases()
    con = sqlite3.connect(store._db_path)
    try:
        count = con.execute("SELECT COUNT(*) FROM task_leases").fetchone()[0]
    finally:
        con.close()
    assert count == 0


# ---- auto_resume_counts ----

def test_load_auto_resume_counts_empty(store: TaskStore) -> None:
    assert store.load_auto_resume_counts() == {}


def test_upsert_and_load_auto_resume_count(store: TaskStore) -> None:
    store.upsert_auto_resume_count("t1", 2)
    result = store.load_auto_resume_counts()
    assert result == {"t1": 2}


def test_upsert_auto_resume_count_updates(store: TaskStore) -> None:
    store.upsert_auto_resume_count("t1", 1)
    store.upsert_auto_resume_count("t1", 3)
    assert store.load_auto_resume_counts()["t1"] == 3


def test_delete_auto_resume_count(store: TaskStore) -> None:
    store.upsert_auto_resume_count("t1", 2)
    store.delete_auto_resume_count("t1")
    assert store.load_auto_resume_counts() == {}


def test_delete_auto_resume_count_noop_missing(store: TaskStore) -> None:
    store.delete_auto_resume_count("nonexistent")  # should not raise
