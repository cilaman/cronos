from __future__ import annotations

import pytest

from app.space_storage import (
    SpaceError,
    SpaceExists,
    SpaceNotFound,
    SpaceStore,
    dump_space,
    parse_space_yaml,
    validate_color,
    validate_space_id,
)

from .conftest import SPACE_ID


# ---------------------------------------------------------------------------
# validate_space_id
# ---------------------------------------------------------------------------


def test_validate_space_id_valid():
    validate_space_id("my-project")
    validate_space_id("abc123")
    validate_space_id("a")


def test_validate_space_id_invalid_uppercase():
    with pytest.raises(SpaceError):
        validate_space_id("MyProject")


def test_validate_space_id_starts_with_dash():
    with pytest.raises(SpaceError):
        validate_space_id("-bad")


def test_validate_space_id_too_long():
    with pytest.raises(SpaceError):
        validate_space_id("a" * 41)


def test_validate_space_id_reserved():
    with pytest.raises(SpaceError):
        validate_space_id(".trash")


# ---------------------------------------------------------------------------
# validate_color
# ---------------------------------------------------------------------------


def test_validate_color_valid():
    validate_color("#15803D")
    validate_color("#000000")
    validate_color("#FFFFFF")


def test_validate_color_missing_hash():
    with pytest.raises(SpaceError):
        validate_color("15803D")


def test_validate_color_too_short():
    with pytest.raises(SpaceError):
        validate_color("#1234")


def test_validate_color_invalid_chars():
    with pytest.raises(SpaceError):
        validate_color("#ZZZZZZ")


# ---------------------------------------------------------------------------
# SpaceStore.create
# ---------------------------------------------------------------------------


async def test_space_store_create(tmp_spaces_dir):
    store = SpaceStore(tmp_spaces_dir)
    space = await store.create(
        name="My Project",
        color="#15803D",
        space_id="my-project",
    )
    assert space.id == "my-project"
    assert space.name == "My Project"
    assert space.color == "#15803D"
    assert space.git_repo_url is None


async def test_space_store_create_persists_yaml(tmp_spaces_dir):
    store = SpaceStore(tmp_spaces_dir)
    await store.create(name="Alpha", color="#000000", space_id="alpha")
    yml = tmp_spaces_dir / "alpha" / ".cronos" / "space.yml"
    assert yml.exists()


async def test_space_store_create_makes_tasks_dir(tmp_spaces_dir):
    store = SpaceStore(tmp_spaces_dir)
    await store.create(name="Alpha", color="#000000", space_id="alpha")
    tasks_dir = tmp_spaces_dir / "alpha" / ".cronos" / "tasks"
    assert tasks_dir.is_dir()


async def test_space_store_create_duplicate_raises(tmp_spaces_dir):
    store = SpaceStore(tmp_spaces_dir)
    await store.create(name="A", color="#000000", space_id="dup")
    with pytest.raises(SpaceExists):
        await store.create(name="B", color="#111111", space_id="dup")


async def test_space_store_create_invalid_color_raises(tmp_spaces_dir):
    store = SpaceStore(tmp_spaces_dir)
    with pytest.raises(SpaceError):
        await store.create(name="X", color="bad-color", space_id="x-space")


async def test_space_store_create_slugifies_name(tmp_spaces_dir):
    store = SpaceStore(tmp_spaces_dir)
    space = await store.create(name="My Cool Project", color="#123456")
    assert space.id == "my-cool-project"


# ---------------------------------------------------------------------------
# SpaceStore reads
# ---------------------------------------------------------------------------


async def test_space_store_get(space_store):
    space = space_store.get(SPACE_ID)
    assert space is not None
    assert space.id == SPACE_ID


async def test_space_store_get_missing(space_store):
    assert space_store.get("nonexistent") is None


async def test_space_store_exists(space_store):
    assert space_store.exists(SPACE_ID)
    assert not space_store.exists("nope")


async def test_space_store_count(space_store):
    assert space_store.count() == 1


async def test_space_store_list_all(space_store):
    spaces = space_store.list_all()
    assert len(spaces) == 1
    assert spaces[0].id == SPACE_ID


# ---------------------------------------------------------------------------
# SpaceStore.reload_all
# ---------------------------------------------------------------------------


async def test_space_store_reload_all(tmp_spaces_dir):
    store = SpaceStore(tmp_spaces_dir)
    await store.create(name="A", color="#000000", space_id="space-a")
    await store.create(name="B", color="#111111", space_id="space-b")
    store2 = SpaceStore(tmp_spaces_dir)
    await store2.reload_all()
    assert store2.count() == 2
    assert store2.exists("space-a")
    assert store2.exists("space-b")


async def test_space_store_reload_all_empty_dir(tmp_spaces_dir):
    tmp_spaces_dir.mkdir(parents=True, exist_ok=True)
    store = SpaceStore(tmp_spaces_dir)
    await store.reload_all()
    assert store.count() == 0


# ---------------------------------------------------------------------------
# SpaceStore.update
# ---------------------------------------------------------------------------


async def test_space_store_update_name(space_store):
    updated = await space_store.update(SPACE_ID, name="Renamed Space")
    assert updated.name == "Renamed Space"
    assert space_store.get(SPACE_ID).name == "Renamed Space"


async def test_space_store_update_color(space_store):
    updated = await space_store.update(SPACE_ID, color="#ABCDEF")
    assert updated.color == "#ABCDEF"


async def test_space_store_update_description(space_store):
    updated = await space_store.update(SPACE_ID, description="New desc")
    assert updated.description == "New desc"


async def test_space_store_update_clear_icon(space_store):
    await space_store.update(SPACE_ID, icon="🚀")
    updated = await space_store.update(SPACE_ID, clear_icon=True)
    assert updated.icon is None


async def test_space_store_update_missing_raises(tmp_spaces_dir):
    store = SpaceStore(tmp_spaces_dir)
    with pytest.raises(SpaceNotFound):
        await store.update("no-such-space", name="X")


async def test_space_store_update_persists(space_store, tmp_spaces_dir):
    await space_store.update(SPACE_ID, name="Saved")
    store2 = SpaceStore(tmp_spaces_dir)
    await store2.reload_all()
    assert store2.get(SPACE_ID).name == "Saved"


# ---------------------------------------------------------------------------
# SpaceStore.delete
# ---------------------------------------------------------------------------


async def test_space_store_delete_removes_from_index(space_store):
    await space_store.delete(SPACE_ID)
    assert not space_store.exists(SPACE_ID)
    assert space_store.count() == 0


async def test_space_store_delete_moves_to_trash(space_store, tmp_spaces_dir):
    await space_store.delete(SPACE_ID)
    trash_dir = tmp_spaces_dir / ".trash"
    trashed = list(trash_dir.iterdir())
    assert len(trashed) == 1
    assert trashed[0].name.startswith(SPACE_ID)


async def test_space_store_delete_missing_raises(tmp_spaces_dir):
    store = SpaceStore(tmp_spaces_dir)
    with pytest.raises(SpaceNotFound):
        await store.delete("nonexistent")


# ---------------------------------------------------------------------------
# parse_space_yaml / dump_space round-trip
# ---------------------------------------------------------------------------


async def test_parse_dump_round_trip(tmp_spaces_dir):
    store = SpaceStore(tmp_spaces_dir)
    original = await store.create(
        name="Round Trip",
        color="#DEADBE",
        description="testing",
        space_id="round-trip",
    )
    yml = tmp_spaces_dir / "round-trip" / ".cronos" / "space.yml"
    parsed = parse_space_yaml(yml)
    assert parsed.id == original.id
    assert parsed.name == original.name
    assert parsed.color == original.color
    assert parsed.description == original.description
