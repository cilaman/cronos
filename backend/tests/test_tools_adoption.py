"""Tests for app.tools.adoption — adopt / unadopt / recompute_local_sha.

All adoption functions accept keyword-only `spaces_dir`, `discovery_base`, and
`db_path` overrides, so every test drives a fully isolated tmp_path world: a
fake discovery clone, a fake discovery SQLite index, and a fake spaces dir.
No monkeypatching of module globals is required.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from app.tools.adoption import (
    AdoptionManifest,
    AlreadyAdopted,
    ItemNotFound,
    NotAdopted,
    _compute_sha,
    adopt,
    recompute_local_sha,
    unadopt,
)
from app.tools.discovery import DiscoveredItem

SPACE = "personal"
SLUG = "github-com-foo-bar"
URL = "https://github.com/foo/bar"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_db(db_path: Path, items: list[DiscoveredItem]) -> None:
    """Create a discovered_tools table and insert the given items."""
    con = sqlite3.connect(db_path)
    con.execute(
        """CREATE TABLE IF NOT EXISTS discovered_tools (
            source_url TEXT NOT NULL, source_slug TEXT NOT NULL, kind TEXT NOT NULL,
            name TEXT NOT NULL, relative_path TEXT NOT NULL, description TEXT,
            source_sha TEXT NOT NULL, last_seen TEXT NOT NULL,
            PRIMARY KEY (source_slug, kind, name))"""
    )
    now = datetime.now(timezone.utc).isoformat()
    for item in items:
        con.execute(
            "INSERT OR REPLACE INTO discovered_tools VALUES (?,?,?,?,?,?,?,?)",
            (
                item.source_url,
                item.source_slug,
                item.kind,
                item.name,
                item.relative_path,
                item.description,
                item.source_sha,
                now,
            ),
        )
    con.commit()
    con.close()


@pytest.fixture
def world(tmp_path):
    """An isolated (spaces_dir, discovery_base, db_path) triple."""
    spaces = tmp_path / "spaces"
    disc_base = tmp_path / "disc"
    db_path = tmp_path / "index.db"
    spaces.mkdir()
    disc_base.mkdir()
    return spaces, disc_base, db_path


def _flat_agent(disc_base: Path, *, body: str = "# Reviewer\nReviews code") -> DiscoveredItem:
    """Lay down a flat agent .md file in the clone and return its DB item."""
    clone = disc_base / SLUG / ".claude" / "agents"
    clone.mkdir(parents=True)
    (clone / "reviewer.md").write_text(body, encoding="utf-8")
    return DiscoveredItem(
        source_url=URL,
        source_slug=SLUG,
        kind="agent",
        name="reviewer",
        relative_path=".claude/agents/reviewer.md",
        description="Reviews code",
        source_sha="abc123",
    )


def _skill_dir(disc_base: Path) -> DiscoveredItem:
    """Lay down a skill directory (SKILL.md + extra file) in the clone."""
    skill = disc_base / SLUG / ".claude" / "skills" / "deploy"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Deploy skill", encoding="utf-8")
    (skill / "helper.py").write_text("print('hi')\n", encoding="utf-8")
    return DiscoveredItem(
        source_url=URL,
        source_slug=SLUG,
        kind="skill",
        name="deploy",
        relative_path=".claude/skills/deploy",
        description="Deploy skill",
        source_sha="def456",
    )


def _adopt_dir(spaces: Path, kind: str, name: str) -> Path:
    return spaces / SPACE / ".cronos" / "tools" / kind / name


# ---------------------------------------------------------------------------
# adopt()
# ---------------------------------------------------------------------------


async def test_adopt_flat_copies_file_and_writes_manifest(world):
    # AC-adopt-flat
    spaces, disc_base, db_path = world
    item = _flat_agent(disc_base)
    _setup_db(db_path, [item])

    manifest = await adopt(
        SPACE, SLUG, "agent", "reviewer",
        spaces_dir=spaces, discovery_base=disc_base, db_path=db_path,
    )

    dest = _adopt_dir(spaces, "agent", "reviewer")
    assert (dest / "reviewer.md").read_text(encoding="utf-8") == "# Reviewer\nReviews code"
    assert (dest / "manifest.yml").exists()

    assert manifest.kind == "agent"
    assert manifest.name == "reviewer"
    assert manifest.source_url == URL
    assert manifest.source_slug == SLUG
    assert manifest.source_path == ".claude/agents/reviewer.md"
    assert manifest.source_sha == "abc123"
    assert manifest.evolved is False
    assert manifest.base_sha == manifest.local_sha

    # Manifest on disk round-trips to the same fields.
    on_disk = yaml.safe_load((dest / "manifest.yml").read_text(encoding="utf-8"))
    assert on_disk["name"] == "reviewer"
    assert on_disk["evolved"] is False
    assert on_disk["base_sha"] == on_disk["local_sha"]


async def test_adopt_dir_copies_all_files(world):
    # AC-adopt-dir
    spaces, disc_base, db_path = world
    item = _skill_dir(disc_base)
    _setup_db(db_path, [item])

    manifest = await adopt(
        SPACE, SLUG, "skill", "deploy",
        spaces_dir=spaces, discovery_base=disc_base, db_path=db_path,
    )

    dest = _adopt_dir(spaces, "skill", "deploy")
    assert (dest / "SKILL.md").read_text(encoding="utf-8") == "# Deploy skill"
    assert (dest / "helper.py").read_text(encoding="utf-8") == "print('hi')\n"
    assert (dest / "manifest.yml").exists()
    assert manifest.kind == "skill"
    assert manifest.source_path == ".claude/skills/deploy"
    assert manifest.evolved is False


async def test_adopt_already_adopted_raises(world):
    # AC-already-adopted
    spaces, disc_base, db_path = world
    item = _flat_agent(disc_base)
    _setup_db(db_path, [item])

    await adopt(
        SPACE, SLUG, "agent", "reviewer",
        spaces_dir=spaces, discovery_base=disc_base, db_path=db_path,
    )

    with pytest.raises(AlreadyAdopted):
        await adopt(
            SPACE, SLUG, "agent", "reviewer",
            spaces_dir=spaces, discovery_base=disc_base, db_path=db_path,
        )


async def test_adopt_item_not_in_db_raises_item_not_found(world):
    # AC-item-not-found — DB exists with the table but no matching row.
    spaces, disc_base, db_path = world
    _flat_agent(disc_base)  # source exists on disk...
    _setup_db(db_path, [])  # ...but the index has no entry for it.

    with pytest.raises(ItemNotFound):
        await adopt(
            SPACE, SLUG, "agent", "reviewer",
            spaces_dir=spaces, discovery_base=disc_base, db_path=db_path,
        )


async def test_adopt_source_missing_raises_and_leaves_no_partial_dir(world):
    # AC-source-missing — item is in DB but the clone file is absent.
    spaces, disc_base, db_path = world
    item = DiscoveredItem(
        source_url=URL,
        source_slug=SLUG,
        kind="agent",
        name="ghost",
        relative_path=".claude/agents/ghost.md",
        description="not on disk",
        source_sha="abc123",
    )
    _setup_db(db_path, [item])

    with pytest.raises(ItemNotFound):
        await adopt(
            SPACE, SLUG, "agent", "ghost",
            spaces_dir=spaces, discovery_base=disc_base, db_path=db_path,
        )

    # No partial destination directory should be left behind.
    assert not _adopt_dir(spaces, "agent", "ghost").exists()


# ---------------------------------------------------------------------------
# unadopt()
# ---------------------------------------------------------------------------


async def test_unadopt_moves_to_trash(world):
    # AC-unadopt
    spaces, disc_base, db_path = world
    item = _flat_agent(disc_base)
    _setup_db(db_path, [item])
    await adopt(
        SPACE, SLUG, "agent", "reviewer",
        spaces_dir=spaces, discovery_base=disc_base, db_path=db_path,
    )
    dest = _adopt_dir(spaces, "agent", "reviewer")
    assert dest.exists()

    await unadopt(SPACE, "agent", "reviewer", spaces_dir=spaces)

    assert not dest.exists()
    trash_root = spaces / SPACE / ".cronos" / "tools" / ".trash" / "agent"
    trashed = list(trash_root.iterdir())
    assert len(trashed) == 1
    assert trashed[0].name.startswith("reviewer-")
    # The moved tree retains its files.
    assert (trashed[0] / "reviewer.md").exists()
    assert (trashed[0] / "manifest.yml").exists()


async def test_unadopt_not_adopted_raises(world):
    # AC-unadopt-not-adopted
    spaces, _disc_base, _db_path = world
    with pytest.raises(NotAdopted):
        await unadopt(SPACE, "agent", "reviewer", spaces_dir=spaces)


# ---------------------------------------------------------------------------
# recompute_local_sha()
# ---------------------------------------------------------------------------


async def test_recompute_after_edit_marks_evolved(world):
    # AC-recompute
    spaces, disc_base, db_path = world
    item = _flat_agent(disc_base)
    _setup_db(db_path, [item])
    original = await adopt(
        SPACE, SLUG, "agent", "reviewer",
        spaces_dir=spaces, discovery_base=disc_base, db_path=db_path,
    )

    dest = _adopt_dir(spaces, "agent", "reviewer")
    (dest / "reviewer.md").write_text("# Reviewer\nLOCALLY EDITED", encoding="utf-8")

    updated = recompute_local_sha(SPACE, "agent", "reviewer", spaces_dir=spaces)

    assert updated.local_sha != original.local_sha
    assert updated.base_sha == original.base_sha  # baseline unchanged
    assert updated.evolved is True

    # Persisted to disk.
    on_disk = yaml.safe_load((dest / "manifest.yml").read_text(encoding="utf-8"))
    assert on_disk["evolved"] is True
    assert on_disk["local_sha"] == updated.local_sha


async def test_recompute_no_change_returns_same_manifest(world):
    # AC-recompute-no-change
    spaces, disc_base, db_path = world
    item = _flat_agent(disc_base)
    _setup_db(db_path, [item])
    original = await adopt(
        SPACE, SLUG, "agent", "reviewer",
        spaces_dir=spaces, discovery_base=disc_base, db_path=db_path,
    )

    result = recompute_local_sha(SPACE, "agent", "reviewer", spaces_dir=spaces)

    assert result.local_sha == original.local_sha
    assert result.evolved is False


async def test_recompute_not_adopted_raises(world):
    # AC-recompute-not-adopted
    spaces, _disc_base, _db_path = world
    with pytest.raises(NotAdopted):
        recompute_local_sha(SPACE, "agent", "reviewer", spaces_dir=spaces)


# ---------------------------------------------------------------------------
# Manifest invariants & sha behavior
# ---------------------------------------------------------------------------


async def test_evolved_false_at_adoption(world):
    # AC-evolved-false
    spaces, disc_base, db_path = world
    item = _flat_agent(disc_base)
    _setup_db(db_path, [item])

    manifest = await adopt(
        SPACE, SLUG, "agent", "reviewer",
        spaces_dir=spaces, discovery_base=disc_base, db_path=db_path,
    )

    assert manifest.base_sha == manifest.local_sha
    assert manifest.evolved is False


def test_compute_sha_excludes_manifest(tmp_path):
    # AC-sha-excludes-manifest — writing/changing manifest.yml must not move the sha.
    d = tmp_path / "tool"
    d.mkdir()
    (d / "reviewer.md").write_text("content", encoding="utf-8")

    sha_before = _compute_sha(d)
    (d / "manifest.yml").write_text("base_sha: deadbeef\nevolved: true\n", encoding="utf-8")
    sha_after = _compute_sha(d)

    assert sha_before == sha_after

    # And changing a real file *does* move it (guards against a no-op stub).
    (d / "reviewer.md").write_text("changed", encoding="utf-8")
    assert _compute_sha(d) != sha_before


def test_compute_sha_includes_nested_files(tmp_path):
    # A skill dir's nested files participate in the hash.
    d = tmp_path / "tool"
    (d / "sub").mkdir(parents=True)
    (d / "SKILL.md").write_text("a", encoding="utf-8")
    sha_one = _compute_sha(d)
    (d / "sub" / "extra.py").write_text("b", encoding="utf-8")
    assert _compute_sha(d) != sha_one


def test_manifest_model_defaults_evolved_false():
    m = AdoptionManifest(
        source_url=URL,
        source_slug=SLUG,
        source_path=".claude/agents/reviewer.md",
        source_sha="abc",
        adopted_at=datetime.now(timezone.utc),
        base_sha="x",
        local_sha="x",
        kind="agent",
        name="reviewer",
    )
    assert m.evolved is False
