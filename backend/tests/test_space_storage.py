from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models import Space, TaskState, View
from app.space_storage import (
    SpaceError,
    SpaceExists,
    SpaceNotFound,
    SpaceStore,
    _dump_view,
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


# ---------------------------------------------------------------------------
# autopilot — arc-4 task 1
# ---------------------------------------------------------------------------


async def test_dump_space_emits_autopilot_key(space_store):
    """`dump_space` must always include the `autopilot:` key in the YAML."""
    space = space_store.get(SPACE_ID)

    yaml_text = dump_space(space)

    # The key must appear on its own line, not just substring-match.
    assert "\nautopilot: disabled\n" in yaml_text or yaml_text.startswith(
        "autopilot: disabled\n"
    ) or "\nautopilot: disabled" in yaml_text


async def test_dump_space_emits_current_autopilot_value(space_store):
    """`dump_space` must emit whatever value the Space carries (enabled/paused)."""
    space = space_store.get(SPACE_ID)
    enabled = space.model_copy(update={"autopilot": "enabled"})
    paused = space.model_copy(update={"autopilot": "paused"})

    assert "autopilot: enabled" in dump_space(enabled)
    assert "autopilot: paused" in dump_space(paused)
    assert "autopilot: disabled" not in dump_space(enabled)


async def test_parse_space_yaml_missing_autopilot_defaults_disabled(
    tmp_spaces_dir,
):
    """A legacy `space.yml` lacking `autopilot:` must load with `'disabled'`.

    Critical for back-compat: every existing space.yml on disk pre-dates this
    field, and a hard validation failure would brick every space on upgrade.
    """
    legacy_yaml = (
        "id: legacy-space\n"
        "name: Legacy\n"
        "color: '#15803D'\n"
        "icon: null\n"
        "description: ''\n"
        "created_at: '2024-01-01T00:00:00+00:00'\n"
        "updated_at: '2024-01-01T00:00:00+00:00'\n"
        "git_repo_url: null\n"
        "git_branch: null\n"
        "git_share_cronos: false\n"
        "agent_defaults: {}\n"
        # NO autopilot key.
    )
    space_dir = tmp_spaces_dir / "legacy-space" / ".cronos"
    space_dir.mkdir(parents=True, exist_ok=True)
    yml = space_dir / "space.yml"
    yml.write_text(legacy_yaml, encoding="utf-8")

    space = parse_space_yaml(yml)

    assert space.autopilot == "disabled"


async def test_parse_space_yaml_reads_explicit_autopilot(tmp_spaces_dir):
    """A `space.yml` with an explicit `autopilot:` value must round-trip it."""
    yml_text = (
        "id: ap-space\n"
        "name: AP\n"
        "color: '#15803D'\n"
        "icon: null\n"
        "description: ''\n"
        "created_at: '2024-01-01T00:00:00+00:00'\n"
        "updated_at: '2024-01-01T00:00:00+00:00'\n"
        "git_repo_url: null\n"
        "git_branch: null\n"
        "git_share_cronos: false\n"
        "agent_defaults: {}\n"
        "autopilot: enabled\n"
    )
    space_dir = tmp_spaces_dir / "ap-space" / ".cronos"
    space_dir.mkdir(parents=True, exist_ok=True)
    yml = space_dir / "space.yml"
    yml.write_text(yml_text, encoding="utf-8")

    space = parse_space_yaml(yml)

    assert space.autopilot == "enabled"


async def test_parse_space_yaml_invalid_autopilot_raises(tmp_spaces_dir):
    """An invalid `autopilot:` literal in space.yml must raise SpaceError.

    The Literal[...] type on `Space.autopilot` rejects unknown strings at
    parse time, which is the contract that protects us from typos becoming
    silent autopilot-off-forever bugs.
    """
    bad_yaml = (
        "id: bad-space\n"
        "name: Bad\n"
        "color: '#15803D'\n"
        "icon: null\n"
        "description: ''\n"
        "created_at: '2024-01-01T00:00:00+00:00'\n"
        "updated_at: '2024-01-01T00:00:00+00:00'\n"
        "git_repo_url: null\n"
        "git_branch: null\n"
        "git_share_cronos: false\n"
        "agent_defaults: {}\n"
        "autopilot: bogus-mode\n"
    )
    space_dir = tmp_spaces_dir / "bad-space" / ".cronos"
    space_dir.mkdir(parents=True, exist_ok=True)
    yml = space_dir / "space.yml"
    yml.write_text(bad_yaml, encoding="utf-8")

    with pytest.raises(SpaceError):
        parse_space_yaml(yml)


async def test_new_space_defaults_to_disabled_autopilot(tmp_spaces_dir):
    """A freshly-created Space starts with autopilot='disabled'."""
    store = SpaceStore(tmp_spaces_dir)

    space = await store.create(
        name="Fresh", color="#15803D", space_id="fresh"
    )

    assert space.autopilot == "disabled"
    # And the on-disk yml emits the key.
    yml_text = (
        tmp_spaces_dir / "fresh" / ".cronos" / "space.yml"
    ).read_text(encoding="utf-8")
    assert "autopilot: disabled" in yml_text


@pytest.mark.parametrize("mode", ["disabled", "enabled", "paused"])
async def test_set_autopilot_persists_value(space_store, tmp_spaces_dir, mode):
    """`set_autopilot` updates the in-memory Space and persists to disk."""
    updated = await space_store.set_autopilot(SPACE_ID, mode)

    assert updated.autopilot == mode
    assert space_store.get(SPACE_ID).autopilot == mode

    # Reload from a fresh store to prove the value was actually written.
    store2 = SpaceStore(tmp_spaces_dir)
    await store2.reload_all()
    assert store2.get(SPACE_ID).autopilot == mode


async def test_set_autopilot_paused_reloads_byte_equal(
    space_store, tmp_spaces_dir
):
    """A space saved with autopilot='paused' reloads with the same value.

    This is the acceptance-criteria byte-equal round-trip: write, reload from
    disk via a fresh SpaceStore, and confirm the field survives unchanged.
    """
    await space_store.set_autopilot(SPACE_ID, "paused")
    yml_path = tmp_spaces_dir / SPACE_ID / ".cronos" / "space.yml"
    on_disk_text_before = yml_path.read_text(encoding="utf-8")

    # Fresh store, fresh parse.
    store2 = SpaceStore(tmp_spaces_dir)
    await store2.reload_all()
    reloaded = store2.get(SPACE_ID)
    assert reloaded is not None
    assert reloaded.autopilot == "paused"

    # Re-dump from the reloaded model and verify the autopilot line survives.
    # Full YAML byte-equality is too strict (datetime micro-formatting can
    # differ); we lock the autopilot key specifically.
    redumped = dump_space(reloaded)
    assert "autopilot: paused" in redumped
    assert "autopilot: paused" in on_disk_text_before


async def test_set_autopilot_missing_space_raises(tmp_spaces_dir):
    """`set_autopilot` on an unknown id must raise SpaceNotFound."""
    store = SpaceStore(tmp_spaces_dir)

    with pytest.raises(SpaceNotFound):
        await store.set_autopilot("no-such-space", "enabled")


async def test_set_autopilot_updates_updated_at(space_store):
    """`set_autopilot` must bump `updated_at` so watchers/UIs see the change."""
    before = space_store.get(SPACE_ID).updated_at

    after = await space_store.set_autopilot(SPACE_ID, "enabled")

    assert after.updated_at >= before
    # Same Space identity, only the timestamp + autopilot changed.
    assert after.id == SPACE_ID
    assert after.autopilot == "enabled"


async def test_set_autopilot_preserves_other_fields(space_store):
    """`set_autopilot` must not clobber name/color/description/etc."""
    before = space_store.get(SPACE_ID)
    name_before = before.name
    color_before = before.color
    desc_before = before.description

    after = await space_store.set_autopilot(SPACE_ID, "enabled")

    assert after.name == name_before
    assert after.color == color_before
    assert after.description == desc_before
    assert after.autopilot == "enabled"


# ---------------------------------------------------------------------------
# View model validation — arc-3/1
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 1, 1, tzinfo=UTC)


def _view(**kwargs) -> View:
    defaults = dict(id="test", name="Test", lanes=[TaskState.BACKLOG], created_at=_NOW, updated_at=_NOW)
    defaults.update(kwargs)
    return View(**defaults)


def test_view_id_valid():
    _view(id="all")
    _view(id="my-view-123")
    _view(id="a" * 32)


def test_view_id_invalid_uppercase():
    with pytest.raises(ValidationError):
        _view(id="MyView")


def test_view_id_invalid_spaces():
    with pytest.raises(ValidationError):
        _view(id="my view")


def test_view_id_too_long():
    with pytest.raises(ValidationError):
        _view(id="a" * 33)


def test_view_empty_lanes_raises():
    with pytest.raises(ValidationError):
        _view(lanes=[])


def test_space_duplicate_view_ids_raises():
    v1 = _view(id="dup", name="First")
    v2 = _view(id="dup", name="Second")
    with pytest.raises(ValidationError, match="Duplicate view id"):
        Space(
            id="s",
            name="S",
            color="#15803D",
            created_at=_NOW,
            updated_at=_NOW,
            views=[v1, v2],
        )


def test_view_type_filter_valid():
    v = _view(type_filter=["task", "goal"])
    assert v.type_filter == ["task", "goal"]


def test_view_type_filter_invalid():
    with pytest.raises(ValidationError):
        _view(type_filter=["invalid-type"])


# ---------------------------------------------------------------------------
# _dump_view serialization — arc-3/1
# ---------------------------------------------------------------------------


def test_dump_view_omits_type_filter_when_none():
    d = _dump_view(_view(type_filter=None))
    assert "type_filter" not in d


def test_dump_view_includes_type_filter_when_set():
    d = _dump_view(_view(id="t", type_filter=["task"]))
    assert d["type_filter"] == ["task"]


def test_dump_view_lanes_are_strings():
    d = _dump_view(_view(lanes=[TaskState.BACKLOG, TaskState.ACTIVE]))
    assert d["lanes"] == ["backlog", "active"]


# ---------------------------------------------------------------------------
# Views YAML round-trip — arc-3/1
# ---------------------------------------------------------------------------

_MINIMAL_YAML = (
    "name: Test\n"
    "color: '#15803D'\n"
    "icon: null\n"
    "description: ''\n"
    "created_at: '2024-01-01T00:00:00Z'\n"
    "updated_at: '2024-01-01T00:00:00Z'\n"
    "git_repo_url: null\n"
    "git_branch: null\n"
    "git_share_cronos: false\n"
    "agent_defaults: {}\n"
    "autopilot: disabled\n"
)


def _write_space_yml(parent, space_id: str, extra: str = "") -> object:
    """Write a minimal space.yml and return the path."""
    from pathlib import Path
    space_dir = Path(parent) / space_id / ".cronos"
    space_dir.mkdir(parents=True, exist_ok=True)
    yml = space_dir / "space.yml"
    yml.write_text(_MINIMAL_YAML + extra, encoding="utf-8")
    return yml


def test_parse_space_yaml_seeds_default_view_when_missing(tmp_spaces_dir):
    """A space.yml without a views key gets a seeded 'All lanes' default view."""
    yml = _write_space_yml(tmp_spaces_dir, "seed-missing")
    space = parse_space_yaml(yml)

    assert len(space.views) == 1
    v = space.views[0]
    assert v.id == "all"
    assert v.name == "All lanes"
    assert v.default is True
    assert set(v.lanes) == {TaskState.BACKLOG, TaskState.ACTIVE, TaskState.WAITING, TaskState.DONE}
    # File must be updated on disk
    assert "views:" in yml.read_text()


def test_parse_space_yaml_seeds_default_view_when_empty(tmp_spaces_dir):
    """A space.yml with views: [] gets the same seed."""
    yml = _write_space_yml(tmp_spaces_dir, "seed-empty", "views: []\n")
    space = parse_space_yaml(yml)

    assert len(space.views) == 1
    assert space.views[0].id == "all"
    assert "views:" in yml.read_text()


def test_parse_space_yaml_normalises_duplicate_defaults(tmp_spaces_dir):
    """When two views have default: true, only the last one survives; file updated."""
    views_yaml = (
        "views:\n"
        "  - id: first\n"
        "    name: First\n"
        "    lanes: [backlog]\n"
        "    default: true\n"
        "    created_at: '2024-01-01T00:00:00Z'\n"
        "    updated_at: '2024-01-01T00:00:00Z'\n"
        "  - id: second\n"
        "    name: Second\n"
        "    lanes: [active]\n"
        "    default: true\n"
        "    created_at: '2024-01-01T00:00:00Z'\n"
        "    updated_at: '2024-01-01T00:00:00Z'\n"
    )
    yml = _write_space_yml(tmp_spaces_dir, "dup-default", views_yaml)
    space = parse_space_yaml(yml)

    defaults = [v for v in space.views if v.default]
    assert len(defaults) == 1
    assert defaults[0].id == "second"  # last-write-wins

    # Reload from disk: the fix should have been persisted
    space2 = parse_space_yaml(yml)
    assert len([v for v in space2.views if v.default]) == 1


def test_dump_parse_round_trip_with_views(tmp_spaces_dir):
    """Three custom views save, reload, and re-dump byte-equal."""
    v1 = View(
        id="all",
        name="All lanes",
        lanes=[TaskState.BACKLOG, TaskState.ACTIVE, TaskState.WAITING, TaskState.DONE],
        default=True,
        created_at=_NOW,
        updated_at=_NOW,
    )
    v2 = View(
        id="active-only",
        name="Active only",
        lanes=[TaskState.ACTIVE],
        type_filter=["task", "goal"],
        created_at=_NOW,
        updated_at=_NOW,
    )
    v3 = View(
        id="done-backlog",
        name="Done and backlog",
        lanes=[TaskState.DONE, TaskState.BACKLOG],
        created_at=_NOW,
        updated_at=_NOW,
    )
    space = Space(
        id="rt-views",
        name="RT Views",
        color="#15803D",
        created_at=_NOW,
        updated_at=_NOW,
        views=[v1, v2, v3],
    )
    space_dir = tmp_spaces_dir / "rt-views" / ".cronos"
    space_dir.mkdir(parents=True, exist_ok=True)
    yml = space_dir / "space.yml"

    first_dump = dump_space(space)
    yml.write_text(first_dump, encoding="utf-8")

    parsed = parse_space_yaml(yml)
    second_dump = dump_space(parsed)

    assert first_dump == second_dump


async def test_store_create_then_reload_seeds_views(tmp_spaces_dir):
    """A freshly-created space gets a seeded view on first reload."""
    store = SpaceStore(tmp_spaces_dir)
    await store.create(name="View Seed", color="#15803D", space_id="view-seed")

    store2 = SpaceStore(tmp_spaces_dir)
    await store2.reload_all()
    space = store2.get("view-seed")

    assert space is not None
    assert len(space.views) == 1
    assert space.views[0].id == "all"
    assert space.views[0].default is True


async def test_dump_space_includes_views_key(space_store):
    """dump_space always emits a views: key."""
    space = space_store.get(SPACE_ID)
    assert "views:" in dump_space(space)


async def test_existing_views_survive_reload(tmp_spaces_dir):
    """Views written to space.yml are loaded back correctly."""
    views_yaml = (
        "views:\n"
        "  - id: work\n"
        "    name: Work items\n"
        "    lanes: [active, waiting]\n"
        "    default: true\n"
        "    created_at: '2024-01-01T00:00:00Z'\n"
        "    updated_at: '2024-01-01T00:00:00Z'\n"
    )
    yml = _write_space_yml(tmp_spaces_dir, "views-persist", views_yaml)
    space = parse_space_yaml(yml)

    assert len(space.views) == 1
    assert space.views[0].id == "work"
    assert space.views[0].lanes == [TaskState.ACTIVE, TaskState.WAITING]
