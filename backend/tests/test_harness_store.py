"""
Tests for backend/app/harnesses/store.py — HarnessStore async CRUD,
YAML round-trip type preservation, slug collision handling, and error paths.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from app.harnesses.model import Harness, HarnessEdge, HarnessNode, NodeRef, NodeType, Position
from app.harnesses.store import (
    HarnessNameConflict,
    HarnessNotFound,
    HarnessStore,
    slugify_name,
    _harnesses_dir,
)
from app.harnesses.validator import HarnessGraphError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _make_simple_harness(name: str = "My Harness") -> Harness:
    """Return a minimal valid harness (two nodes, one edge, no cycle)."""
    node_a = HarnessNode(
        id="node-a",
        type=NodeType.trigger,
        position=Position(x=0.0, y=0.0),
        ports={"out": {"direction": "output"}},
        label="A",
    )
    node_b = HarnessNode(
        id="node-b",
        type=NodeType.agent,
        position=Position(x=100.0, y=0.0),
        ports={"in": {"direction": "input"}},
        label="B",
    )
    edge_ab = HarnessEdge(
        id="edge-ab",
        source=NodeRef(node_id="node-a", port_id="out"),
        target=NodeRef(node_id="node-b", port_id="in"),
    )
    return Harness(
        name=name,
        description="A simple test harness",
        nodes=[node_a, node_b],
        edges=[edge_ab],
        created_at=_now(),
        updated_at=_now(),
    )


def _make_empty_harness(name: str = "Empty Harness") -> Harness:
    """Return a valid harness with no nodes or edges."""
    return Harness(name=name, created_at=_now(), updated_at=_now())


# ---------------------------------------------------------------------------
# slugify_name unit tests
# ---------------------------------------------------------------------------


class TestSlugifyName:
    def test_lowercase(self):
        assert slugify_name("MyFlow") == "myflow"

    def test_spaces_become_hyphens(self):
        assert slugify_name("my flow") == "my-flow"

    def test_special_chars_become_hyphens(self):
        assert slugify_name("My Flow!") == "my-flow"

    def test_multiple_special_chars_collapse(self):
        assert slugify_name("my---flow") == "my-flow"

    def test_leading_trailing_stripped(self):
        assert slugify_name("!flow!") == "flow"

    def test_empty_string(self):
        assert slugify_name("") == "harness"

    def test_all_special_chars(self):
        assert slugify_name("!!!") == "harness"

    def test_my_flow_exclamation_and_my_flow_same(self):
        assert slugify_name("My Flow!") == slugify_name("my flow")


# ---------------------------------------------------------------------------
# HarnessStore — basic CRUD
# ---------------------------------------------------------------------------


class TestHarnessStoreCRUD:
    @pytest.fixture()
    def store(self):
        return HarnessStore()

    @pytest.fixture()
    def space(self, tmp_path):
        return tmp_path / "my-space"

    def test_create_and_get(self, store, space):
        harness = _make_simple_harness()
        created = asyncio.run(store.create(space, harness))
        assert created.name == harness.name

        fetched = asyncio.run(store.get(space, harness.name))
        assert fetched.name == harness.name
        assert fetched.description == harness.description

    def test_create_writes_yaml_to_disk(self, store, space):
        harness = _make_simple_harness("Disk Test")
        asyncio.run(store.create(space, harness))
        hdir = _harnesses_dir(space)
        yaml_files = list(hdir.glob("*.yml"))
        assert len(yaml_files) == 1

    def test_list_empty(self, store, space):
        result = asyncio.run(store.list(space))
        assert result == []

    def test_list_returns_all(self, store, space):
        asyncio.run(store.create(space, _make_simple_harness("Alpha")))
        asyncio.run(store.create(space, _make_simple_harness("Beta")))
        result = asyncio.run(store.list(space))
        names = {h.name for h in result}
        assert names == {"Alpha", "Beta"}

    def test_update_basic(self, store, space):
        harness = _make_simple_harness("Updatable")
        asyncio.run(store.create(space, harness))

        updated = harness.model_copy(
            update={"description": "updated desc", "updated_at": _now()}
        )
        result = asyncio.run(store.update(space, "Updatable", updated))
        assert result.description == "updated desc"

        fetched = asyncio.run(store.get(space, "Updatable"))
        assert fetched.description == "updated desc"

    def test_update_reflects_on_disk(self, store, space):
        harness = _make_simple_harness("PersistUpdate")
        asyncio.run(store.create(space, harness))

        updated = harness.model_copy(
            update={"description": "on-disk updated", "updated_at": _now()}
        )
        asyncio.run(store.update(space, "PersistUpdate", updated))

        hdir = _harnesses_dir(space)
        yaml_files = list(hdir.glob("*.yml"))
        assert len(yaml_files) == 1
        raw = yaml.safe_load(yaml_files[0].read_text())
        assert raw["description"] == "on-disk updated"

    def test_delete_removes_from_memory(self, store, space):
        asyncio.run(store.create(space, _make_simple_harness("ToDelete")))
        asyncio.run(store.delete(space, "ToDelete"))
        with pytest.raises(HarnessNotFound):
            asyncio.run(store.get(space, "ToDelete"))

    def test_delete_removes_yaml_from_disk(self, store, space):
        asyncio.run(store.create(space, _make_simple_harness("DiskDelete")))
        hdir = _harnesses_dir(space)
        assert len(list(hdir.glob("*.yml"))) == 1

        asyncio.run(store.delete(space, "DiskDelete"))
        assert len(list(hdir.glob("*.yml"))) == 0

    def test_list_after_delete_is_empty(self, store, space):
        asyncio.run(store.create(space, _make_empty_harness("Temp")))
        asyncio.run(store.delete(space, "Temp"))
        assert asyncio.run(store.list(space)) == []


# ---------------------------------------------------------------------------
# HarnessStore — error paths
# ---------------------------------------------------------------------------


class TestHarnessStoreErrors:
    @pytest.fixture()
    def store(self):
        return HarnessStore()

    @pytest.fixture()
    def space(self, tmp_path):
        return tmp_path / "err-space"

    def test_create_duplicate_raises_conflict(self, store, space):
        h = _make_empty_harness("Dup")
        asyncio.run(store.create(space, h))
        with pytest.raises(HarnessNameConflict):
            asyncio.run(store.create(space, _make_empty_harness("Dup")))

    def test_get_nonexistent_raises_not_found(self, store, space):
        with pytest.raises(HarnessNotFound):
            asyncio.run(store.get(space, "ghost"))

    def test_update_nonexistent_raises_not_found(self, store, space):
        with pytest.raises(HarnessNotFound):
            asyncio.run(store.update(space, "ghost", _make_empty_harness("ghost")))

    def test_delete_nonexistent_raises_not_found(self, store, space):
        with pytest.raises(HarnessNotFound):
            asyncio.run(store.delete(space, "ghost"))

    def test_create_with_cycle_raises_graph_error(self, store, space):
        node_a = HarnessNode(
            id="n1",
            type=NodeType.agent,
            position=Position(x=0, y=0),
            ports={"p1": {}, "p2": {}},
        )
        node_b = HarnessNode(
            id="n2",
            type=NodeType.agent,
            position=Position(x=1, y=0),
            ports={"p1": {}, "p2": {}},
        )
        edge_ab = HarnessEdge(
            id="e1",
            source=NodeRef(node_id="n1", port_id="p1"),
            target=NodeRef(node_id="n2", port_id="p1"),
        )
        edge_ba = HarnessEdge(
            id="e2",
            source=NodeRef(node_id="n2", port_id="p2"),
            target=NodeRef(node_id="n1", port_id="p2"),
        )
        cyclic = Harness(
            name="Cyclic",
            nodes=[node_a, node_b],
            edges=[edge_ab, edge_ba],
            created_at=_now(),
            updated_at=_now(),
        )
        with pytest.raises(HarnessGraphError):
            asyncio.run(store.create(space, cyclic))

    def test_update_with_cycle_raises_graph_error(self, store, space):
        h = _make_empty_harness("CyclicUpdate")
        asyncio.run(store.create(space, h))

        # Build a cyclic harness with the same name
        node_a = HarnessNode(
            id="x1",
            type=NodeType.agent,
            position=Position(x=0, y=0),
            ports={"out": {}, "in": {}},
        )
        edge_self = HarnessEdge(
            id="e-self",
            source=NodeRef(node_id="x1", port_id="out"),
            target=NodeRef(node_id="x1", port_id="in"),
        )
        cyclic = Harness(
            name="CyclicUpdate",
            nodes=[node_a],
            edges=[edge_self],
            created_at=_now(),
            updated_at=_now(),
        )
        with pytest.raises(HarnessGraphError):
            asyncio.run(store.update(space, "CyclicUpdate", cyclic))


# ---------------------------------------------------------------------------
# YAML round-trip type preservation
# ---------------------------------------------------------------------------


class TestYamlRoundTrip:
    """R8: YAML serialisation must preserve int/float/bool/str scalar types.

    We dump a Harness whose ``data`` and ``variables`` contain all four
    primitive types, reload from disk, reconstruct a Harness, and assert
    type equality via ``isinstance`` — not just value equality.
    """

    @pytest.fixture()
    def store(self):
        return HarnessStore()

    @pytest.fixture()
    def space(self, tmp_path):
        return tmp_path / "roundtrip-space"

    def _mixed_type_harness(self) -> Harness:
        node = HarnessNode(
            id="rt-node",
            type=NodeType.agent,
            position=Position(x=1.5, y=2.7),
            ports={"p": {}},
            data={
                "count": 42,
                "ratio": 3.14,
                "enabled": True,
                "label": "hello",
            },
        )
        return Harness(
            name="RoundTrip",
            variables={
                "int_var": 7,
                "float_var": 0.5,
                "bool_var": False,
                "str_var": "world",
            },
            nodes=[node],
            edges=[],
            created_at=_now(),
            updated_at=_now(),
        )

    def test_yaml_round_trip_from_disk(self, store, space):
        """Load YAML from disk after create and check scalar types."""
        harness = self._mixed_type_harness()
        asyncio.run(store.create(space, harness))

        hdir = _harnesses_dir(space)
        yaml_files = list(hdir.glob("*.yml"))
        assert len(yaml_files) == 1

        raw = yaml.safe_load(yaml_files[0].read_text())

        # variables
        assert isinstance(raw["variables"]["int_var"], int)
        assert isinstance(raw["variables"]["float_var"], float)
        assert isinstance(raw["variables"]["bool_var"], bool)
        assert isinstance(raw["variables"]["str_var"], str)

        # node data
        node_data = raw["nodes"][0]["data"]
        assert isinstance(node_data["count"], int)
        assert isinstance(node_data["ratio"], float)
        assert isinstance(node_data["enabled"], bool)
        assert isinstance(node_data["label"], str)

    def test_yaml_round_trip_model_reconstruct(self, store, space):
        """Reconstruct a Harness from disk YAML and assert type equality."""
        harness = self._mixed_type_harness()
        asyncio.run(store.create(space, harness))

        hdir = _harnesses_dir(space)
        yaml_files = list(hdir.glob("*.yml"))
        raw = yaml.safe_load(yaml_files[0].read_text())
        reloaded = Harness.model_validate(raw)

        # variables
        assert isinstance(reloaded.variables["int_var"], int)
        assert isinstance(reloaded.variables["float_var"], float)
        assert isinstance(reloaded.variables["bool_var"], bool)
        assert isinstance(reloaded.variables["str_var"], str)

        # node data
        node_data = reloaded.nodes[0].data
        assert isinstance(node_data["count"], int)
        assert isinstance(node_data["ratio"], float)
        assert isinstance(node_data["enabled"], bool)
        assert isinstance(node_data["label"], str)

    def test_yaml_values_preserved(self, store, space):
        """Values must survive the round-trip unchanged."""
        harness = self._mixed_type_harness()
        asyncio.run(store.create(space, harness))

        hdir = _harnesses_dir(space)
        raw = yaml.safe_load(list(hdir.glob("*.yml"))[0].read_text())

        assert raw["variables"]["int_var"] == 7
        assert abs(raw["variables"]["float_var"] - 0.5) < 1e-9
        assert raw["variables"]["bool_var"] is False
        assert raw["variables"]["str_var"] == "world"

        assert raw["nodes"][0]["data"]["count"] == 42
        assert abs(raw["nodes"][0]["data"]["ratio"] - 3.14) < 1e-9
        assert raw["nodes"][0]["data"]["enabled"] is True
        assert raw["nodes"][0]["data"]["label"] == "hello"


# ---------------------------------------------------------------------------
# Slug collision handling
# ---------------------------------------------------------------------------


class TestSlugCollision:
    """Harnesses whose names slugify identically must get distinct disk filenames."""

    @pytest.fixture()
    def store(self):
        return HarnessStore()

    @pytest.fixture()
    def space(self, tmp_path):
        return tmp_path / "slug-space"

    def test_collision_produces_distinct_filenames(self, store, space):
        """'My Flow!' and 'my flow' slugify identically; must get distinct files."""
        h1 = _make_empty_harness("My Flow!")
        h2 = _make_empty_harness("my flow")
        asyncio.run(store.create(space, h1))
        asyncio.run(store.create(space, h2))

        hdir = _harnesses_dir(space)
        yaml_files = {p.name for p in hdir.glob("*.yml")}
        # Both must be on disk.
        assert len(yaml_files) == 2
        # They must be distinct filenames.
        filenames = list(yaml_files)
        assert filenames[0] != filenames[1]

    def test_collision_slug_has_suffix(self, store, space):
        """Second harness with colliding slug gets a -2 suffix."""
        h1 = _make_empty_harness("My Flow!")
        h2 = _make_empty_harness("my flow")
        asyncio.run(store.create(space, h1))
        asyncio.run(store.create(space, h2))

        hdir = _harnesses_dir(space)
        filenames = {p.stem for p in hdir.glob("*.yml")}
        # Base slug is "my-flow"; second should be "my-flow-2".
        assert "my-flow" in filenames
        assert "my-flow-2" in filenames

    def test_collision_both_retrievable(self, store, space):
        """Both harnesses remain independently retrievable."""
        asyncio.run(store.create(space, _make_empty_harness("My Flow!")))
        asyncio.run(store.create(space, _make_empty_harness("my flow")))

        result = asyncio.run(store.list(space))
        names = {h.name for h in result}
        assert names == {"My Flow!", "my flow"}

    def test_triple_collision(self, store, space):
        """Three harnesses with the same slug each get distinct filenames."""
        asyncio.run(store.create(space, _make_empty_harness("a b")))
        asyncio.run(store.create(space, _make_empty_harness("a!b")))
        asyncio.run(store.create(space, _make_empty_harness("a-b")))

        hdir = _harnesses_dir(space)
        yaml_files = list(hdir.glob("*.yml"))
        assert len(yaml_files) == 3
        stems = {p.stem for p in yaml_files}
        assert len(stems) == 3


# ---------------------------------------------------------------------------
# Atomic write (file appears via os.replace, not partial write)
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    @pytest.fixture()
    def store(self):
        return HarnessStore()

    @pytest.fixture()
    def space(self, tmp_path):
        return tmp_path / "atomic-space"

    def test_no_tmp_files_after_create(self, store, space):
        """No .tmp.* files should remain after a successful create."""
        asyncio.run(store.create(space, _make_simple_harness("AtomicTest")))
        hdir = _harnesses_dir(space)
        tmp_files = list(hdir.glob("*.tmp.*"))
        assert tmp_files == []

    def test_no_tmp_files_after_update(self, store, space):
        """No .tmp.* files should remain after a successful update."""
        h = _make_simple_harness("AtomicUpdate")
        asyncio.run(store.create(space, h))
        updated = h.model_copy(update={"description": "updated", "updated_at": _now()})
        asyncio.run(store.update(space, "AtomicUpdate", updated))
        hdir = _harnesses_dir(space)
        tmp_files = list(hdir.glob("*.tmp.*"))
        assert tmp_files == []

    def test_yaml_file_is_valid_after_create(self, store, space):
        """The persisted YAML must be parseable by yaml.safe_load."""
        asyncio.run(store.create(space, _make_simple_harness("ValidYaml")))
        hdir = _harnesses_dir(space)
        for f in hdir.glob("*.yml"):
            parsed = yaml.safe_load(f.read_text())
            assert isinstance(parsed, dict)
            assert parsed["name"] == "ValidYaml"


# ---------------------------------------------------------------------------
# Isolated spaces (different space_dir paths are independent)
# ---------------------------------------------------------------------------


class TestSpaceIsolation:
    @pytest.fixture()
    def store(self):
        return HarnessStore()

    def test_different_spaces_are_independent(self, tmp_path):
        store = HarnessStore()
        space_a = tmp_path / "space-a"
        space_b = tmp_path / "space-b"

        asyncio.run(store.create(space_a, _make_empty_harness("Shared Name")))
        asyncio.run(store.create(space_b, _make_empty_harness("Shared Name")))

        a_list = asyncio.run(store.list(space_a))
        b_list = asyncio.run(store.list(space_b))
        assert len(a_list) == 1
        assert len(b_list) == 1

    def test_delete_from_one_space_leaves_other(self, tmp_path):
        store = HarnessStore()
        space_a = tmp_path / "space-a"
        space_b = tmp_path / "space-b"

        asyncio.run(store.create(space_a, _make_empty_harness("X")))
        asyncio.run(store.create(space_b, _make_empty_harness("X")))
        asyncio.run(store.delete(space_a, "X"))

        with pytest.raises(HarnessNotFound):
            asyncio.run(store.get(space_a, "X"))
        fetched = asyncio.run(store.get(space_b, "X"))
        assert fetched.name == "X"
