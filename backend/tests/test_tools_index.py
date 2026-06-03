from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.tools.discovery import DiscoveredItem
from app.tools.index import list_discovered, prune_stale, upsert_discovered

# Reproduce the discovered_tools DDL inline so these tests do not depend on
# TaskStore or _ensure_db_schema (per task setup note).
_DDL = """
CREATE TABLE IF NOT EXISTS discovered_tools (
    source_url TEXT NOT NULL,
    source_slug TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    description TEXT,
    source_sha TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (source_slug, kind, name)
);
CREATE INDEX IF NOT EXISTS idx_discovered_tools_kind ON discovered_tools(kind);
"""


@pytest.fixture
def db(tmp_path: Path) -> Path:
    """A fresh sqlite file with only the discovered_tools schema."""
    db_path = tmp_path / "discovered.sqlite"
    con = sqlite3.connect(db_path)
    try:
        con.executescript(_DDL)
        con.commit()
    finally:
        con.close()
    return db_path


def _item(
    slug: str = "github.com-acme-tools",
    kind: str = "agent",
    name: str = "reviewer",
    sha: str = "abc",
    relative_path: str | None = None,
    description: str | None = "desc",
) -> DiscoveredItem:
    return DiscoveredItem(
        source_url=f"https://{slug}",
        source_slug=slug,
        kind=kind,
        name=name,
        relative_path=relative_path or f".claude/{kind}s/{name}.md",
        description=description,
        source_sha=sha,
    )


def _stored_last_seen(db_path: Path, name: str) -> str:
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT last_seen FROM discovered_tools WHERE name = ?", (name,)
        ).fetchone()
    finally:
        con.close()
    assert row is not None, f"no row for {name}"
    return row[0]


# --------------------------------------------------------------------------
# 1. Upsert + re-run with deleted item -> pruned by prune_stale
# --------------------------------------------------------------------------


def test_prune_stale_removes_item_absent_from_rerun(db: Path) -> None:
    slug = "github.com-acme-tools"
    item_a = _item(slug=slug, name="alpha")
    item_b = _item(slug=slug, name="bravo")

    # First scan discovers both.
    upsert_discovered(db, [item_a, item_b])

    # Cutoff captured strictly after the first scan but before the second.
    cutoff = datetime.now(timezone.utc) + timedelta(seconds=1)

    # Second scan finds only A (B was deleted upstream); its last_seen advances
    # past the cutoff while B's stays behind it.
    later = (cutoff + timedelta(seconds=1)).isoformat()
    con = sqlite3.connect(db)
    try:
        con.execute(
            "UPDATE discovered_tools SET last_seen = ? WHERE name = ?",
            (later, "alpha"),
        )
        con.commit()
    finally:
        con.close()

    # Act
    deleted = prune_stale(db, slug, cutoff=cutoff)

    # Assert: B pruned, A survives.
    assert deleted == 1
    survivors = [it.name for it in list_discovered(db, source_slug=slug)]
    assert survivors == ["alpha"]


# --------------------------------------------------------------------------
# 2. Same item with new SHA -> row updated, not duplicated
# --------------------------------------------------------------------------


def test_upsert_same_key_new_sha_updates_in_place(db: Path) -> None:
    upsert_discovered(db, [_item(sha="abc")])

    # Act: re-upsert the same (slug, kind, name) with a different sha.
    upsert_discovered(db, [_item(sha="def")])

    rows = list_discovered(db)
    assert len(rows) == 1
    assert rows[0].source_sha == "def"


def test_upsert_same_key_new_sha_refreshes_last_seen(db: Path) -> None:
    upsert_discovered(db, [_item(sha="abc")])
    first_seen = _stored_last_seen(db, "reviewer")

    upsert_discovered(db, [_item(sha="def")])
    second_seen = _stored_last_seen(db, "reviewer")

    assert second_seen >= first_seen


# --------------------------------------------------------------------------
# 3. list_discovered is order-stable across calls
# --------------------------------------------------------------------------


def test_list_discovered_order_stable(db: Path) -> None:
    items = [
        _item(slug="z-repo", kind="skill", name="zeta"),
        _item(slug="a-repo", kind="command", name="alpha"),
        _item(slug="a-repo", kind="agent", name="alpha"),
        _item(slug="m-repo", kind="hook", name="mid"),
        _item(slug="a-repo", kind="agent", name="beta"),
    ]
    upsert_discovered(db, items)

    first = list_discovered(db)
    second = list_discovered(db)

    assert first == second
    # Sanity: ordering follows (source_slug, kind, name).
    keys = [(it.source_slug, it.kind, it.name) for it in first]
    assert keys == sorted(keys)


# --------------------------------------------------------------------------
# 4. list_discovered kind filter
# --------------------------------------------------------------------------


def test_list_discovered_kind_filter(db: Path) -> None:
    upsert_discovered(
        db,
        [
            _item(kind="agent", name="rev"),
            _item(kind="skill", name="build"),
            _item(kind="agent", name="plan"),
        ],
    )

    agents = list_discovered(db, kind="agent")

    assert {it.name for it in agents} == {"rev", "plan"}
    assert all(it.kind == "agent" for it in agents)


def test_list_discovered_kind_filter_no_match(db: Path) -> None:
    upsert_discovered(db, [_item(kind="agent", name="rev")])

    assert list_discovered(db, kind="hook") == []


# --------------------------------------------------------------------------
# 5. list_discovered source_slug filter
# --------------------------------------------------------------------------


def test_list_discovered_source_slug_filter(db: Path) -> None:
    upsert_discovered(
        db,
        [
            _item(slug="repo-a", name="one"),
            _item(slug="repo-b", name="two"),
            _item(slug="repo-a", name="three"),
        ],
    )

    repo_a = list_discovered(db, source_slug="repo-a")

    assert {it.name for it in repo_a} == {"one", "three"}
    assert all(it.source_slug == "repo-a" for it in repo_a)


def test_list_discovered_combined_filters(db: Path) -> None:
    upsert_discovered(
        db,
        [
            _item(slug="repo-a", kind="agent", name="one"),
            _item(slug="repo-a", kind="skill", name="two"),
            _item(slug="repo-b", kind="agent", name="three"),
        ],
    )

    result = list_discovered(db, kind="agent", source_slug="repo-a")

    assert len(result) == 1
    assert result[0].name == "one"


# --------------------------------------------------------------------------
# 6. prune_stale returns correct count
# --------------------------------------------------------------------------


def test_prune_stale_returns_count(db: Path) -> None:
    slug = "repo-a"
    # Three rows all stamped in the past relative to the cutoff.
    past = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
    upsert_discovered(
        db,
        [
            _item(slug=slug, kind="agent", name="a"),
            _item(slug=slug, kind="agent", name="b"),
            _item(slug=slug, kind="skill", name="c"),
            _item(slug="other-repo", kind="agent", name="keep"),
        ],
    )
    con = sqlite3.connect(db)
    try:
        con.execute(
            "UPDATE discovered_tools SET last_seen = ? WHERE source_slug = ?",
            (past, slug),
        )
        con.commit()
    finally:
        con.close()

    cutoff = datetime(2021, 1, 1, tzinfo=timezone.utc)
    deleted = prune_stale(db, slug, cutoff=cutoff)

    assert deleted == 3
    # The other slug is untouched even though it would not match the cutoff scope.
    assert [it.name for it in list_discovered(db, source_slug="other-repo")] == ["keep"]


def test_prune_stale_no_rows_deleted_returns_zero(db: Path) -> None:
    slug = "repo-a"
    upsert_discovered(db, [_item(slug=slug, name="fresh")])

    # Cutoff in the distant past: nothing is older than it.
    cutoff = datetime(2000, 1, 1, tzinfo=timezone.utc)
    deleted = prune_stale(db, slug, cutoff=cutoff)

    assert deleted == 0
    assert len(list_discovered(db, source_slug=slug)) == 1


def test_prune_stale_scoped_to_source_slug(db: Path) -> None:
    """Stale rows in a different slug are not pruned even past the cutoff."""
    past = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
    upsert_discovered(
        db,
        [
            _item(slug="repo-a", name="stale-a"),
            _item(slug="repo-b", name="stale-b"),
        ],
    )
    con = sqlite3.connect(db)
    try:
        con.execute("UPDATE discovered_tools SET last_seen = ?", (past,))
        con.commit()
    finally:
        con.close()

    cutoff = datetime(2021, 1, 1, tzinfo=timezone.utc)
    deleted = prune_stale(db, "repo-a", cutoff=cutoff)

    assert deleted == 1
    assert [it.name for it in list_discovered(db)] == ["stale-b"]
