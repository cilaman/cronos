"""
Tests for backend/app/harnesses/model.py (I1).

Covers: valid harness construction, NodeType enum values, duplicate node/edge
IDs (R1/R2), edge references to non-existent nodes (R3) and ports (R4),
Pydantic v2 default_factory patterns, tz-aware UTC timestamps, package
re-exports, and ``data`` dict conventions for Wait / Aggregator nodes.
"""

import pytest
from pydantic import ValidationError

from app.harnesses.model import (
    Harness,
    HarnessEdge,
    HarnessNode,
    NodeRef,
    NodeType,
    Position,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(node_id: str, ports: dict | None = None) -> HarnessNode:
    return HarnessNode(id=node_id, type=NodeType.agent, position=Position(x=0.0, y=0.0), ports=ports or {})


def _edge(eid: str, sn: str, sp: str, tn: str, tp: str, cond: str | None = None) -> HarnessEdge:
    return HarnessEdge(id=eid, source=NodeRef(node_id=sn, port_id=sp), target=NodeRef(node_id=tn, port_id=tp), condition=cond)


def _two_node_harness(**overrides) -> Harness:
    return Harness(
        name="test-h",
        nodes=[_node("n1", {"out": {}}), _node("n2", {"in": {}})],
        edges=[_edge("e1", "n1", "out", "n2", "in")],
        **overrides,
    )


# ---------------------------------------------------------------------------
# NodeType enum
# ---------------------------------------------------------------------------

class TestNodeTypeEnum:
    def test_all_values(self):
        assert {e.value for e in NodeType} == {"agent", "trigger", "decision", "wait", "aggregator"}

    def test_string_coercion(self):
        node = HarnessNode(id="x", type="trigger", position=Position(x=0, y=0))
        assert node.type is NodeType.trigger

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            HarnessNode(id="x", type="unknown", position=Position(x=0, y=0))


# ---------------------------------------------------------------------------
# HarnessNode defaults (Pydantic v2 Field(default_factory=dict))
# ---------------------------------------------------------------------------

class TestHarnessNodeDefaults:
    def test_defaults(self):
        n = _node("a")
        assert n.ports == {} and n.data == {} and n.label == ""

    def test_ports_default_factory_isolates_instances(self):
        n1, n2 = _node("n1"), _node("n2")
        n1.ports["x"] = {}
        assert "x" not in n2.ports

    def test_data_default_factory_isolates_instances(self):
        n1, n2 = _node("n1"), _node("n2")
        n1.data["k"] = "v"
        assert "k" not in n2.data

    def test_rich_node(self):
        n = HarnessNode(
            id="rich", type=NodeType.decision, position=Position(x=10.5, y=-3.2),
            ports={"p1": {"direction": "input"}}, data={"threshold": 0.5}, label="Branch",
        )
        assert n.label == "Branch" and n.data["threshold"] == 0.5


# ---------------------------------------------------------------------------
# HarnessEdge
# ---------------------------------------------------------------------------

class TestHarnessEdge:
    def test_condition_defaults_none(self):
        assert _edge("e1", "n1", "out", "n2", "in").condition is None

    def test_condition_stored(self):
        assert _edge("e2", "a", "p", "b", "q", "x == 1").condition == "x == 1"


# ---------------------------------------------------------------------------
# Valid Harness construction
# ---------------------------------------------------------------------------

class TestValidHarness:
    def test_empty_harness(self):
        h = Harness(name="empty")
        assert h.nodes == [] and h.edges == [] and h.variables == {} and h.version == "1.0"

    def test_created_at_tz_aware_utc(self):
        h = Harness(name="ts")
        assert h.created_at.tzinfo is not None
        assert h.created_at.tzinfo.utcoffset(h.created_at).total_seconds() == 0

    def test_updated_at_tz_aware(self):
        assert Harness(name="ts").updated_at.tzinfo is not None

    def test_full_harness(self):
        h = _two_node_harness()
        assert len(h.nodes) == 2 and len(h.edges) == 1

    def test_variables_default_factory(self):
        h1, h2 = Harness(name="h1"), Harness(name="h2")
        h1.variables["x"] = 1
        assert "x" not in h2.variables

    def test_three_node_two_edge(self):
        n1 = _node("n1", {"out": {}})
        n2 = _node("n2", {"in": {}, "out": {}})
        n3 = _node("n3", {"in": {}})
        h = Harness(name="three", nodes=[n1, n2, n3], edges=[_edge("e1", "n1", "out", "n2", "in"), _edge("e2", "n2", "out", "n3", "in")])
        assert len(h.nodes) == 3 and len(h.edges) == 2

    def test_harness_no_edges(self):
        assert Harness(name="solo", nodes=[_node("a")]).edges == []


# ---------------------------------------------------------------------------
# R1 — Duplicate node IDs
# ---------------------------------------------------------------------------

class TestDuplicateNodeIds:
    def test_duplicate_raises_with_message(self):
        with pytest.raises(ValidationError) as exc_info:
            Harness(name="dup", nodes=[_node("dup"), _node("dup")])
        msg = str(exc_info.value)
        assert "duplicate node id" in msg and "'dup'" in msg

    def test_non_adjacent_duplicate_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            Harness(name="x", nodes=[_node("a"), _node("b"), _node("a")])
        assert "duplicate node id" in str(exc_info.value)

    def test_unique_ids_ok(self):
        Harness(name="ok", nodes=[_node("x"), _node("y"), _node("z")])


# ---------------------------------------------------------------------------
# R2 — Duplicate edge IDs
# ---------------------------------------------------------------------------

class TestDuplicateEdgeIds:
    def test_duplicate_raises_with_message(self):
        n1, n2 = _node("n1", {"out": {}}), _node("n2", {"in": {}})
        with pytest.raises(ValidationError) as exc_info:
            Harness(name="de", nodes=[n1, n2], edges=[_edge("e", "n1", "out", "n2", "in"), _edge("e", "n1", "out", "n2", "in")])
        msg = str(exc_info.value)
        assert "duplicate edge id" in msg and "'e'" in msg

    def test_unique_edge_ids_ok(self):
        n1, n2 = _node("n1", {"out": {}}), _node("n2", {"in": {}})
        Harness(name="ok", nodes=[n1, n2], edges=[_edge("e1", "n1", "out", "n2", "in"), _edge("e2", "n1", "out", "n2", "in")])


# ---------------------------------------------------------------------------
# R3 — Edge referencing non-existent node
# ---------------------------------------------------------------------------

class TestEdgeUnknownNode:
    def test_unknown_source_node_raises(self):
        n1, n2 = _node("n1", {"out": {}}), _node("n2", {"in": {}})
        with pytest.raises(ValidationError) as exc_info:
            Harness(name="x", nodes=[n1, n2], edges=[_edge("e1", "GHOST", "out", "n2", "in")])
        msg = str(exc_info.value)
        assert "unknown node id" in msg and "'GHOST'" in msg

    def test_unknown_target_node_raises(self):
        n1, n2 = _node("n1", {"out": {}}), _node("n2", {"in": {}})
        with pytest.raises(ValidationError) as exc_info:
            Harness(name="x", nodes=[n1, n2], edges=[_edge("e1", "n1", "out", "GHOST", "in")])
        msg = str(exc_info.value)
        assert "unknown node id" in msg and "'GHOST'" in msg

    def test_valid_refs_ok(self):
        _two_node_harness()


# ---------------------------------------------------------------------------
# R4 — Edge referencing non-existent port
# ---------------------------------------------------------------------------

class TestEdgeUnknownPort:
    def test_unknown_source_port_raises(self):
        n1, n2 = _node("n1", {"real_out": {}}), _node("n2", {"in": {}})
        with pytest.raises(ValidationError) as exc_info:
            Harness(name="x", nodes=[n1, n2], edges=[_edge("e1", "n1", "ghost_port", "n2", "in")])
        msg = str(exc_info.value)
        assert "unknown port" in msg and "'ghost_port'" in msg and "'n1'" in msg

    def test_unknown_target_port_raises(self):
        n1, n2 = _node("n1", {"out": {}}), _node("n2", {"real_in": {}})
        with pytest.raises(ValidationError) as exc_info:
            Harness(name="x", nodes=[n1, n2], edges=[_edge("e1", "n1", "out", "n2", "ghost_port")])
        msg = str(exc_info.value)
        assert "unknown port" in msg and "'ghost_port'" in msg and "'n2'" in msg

    def test_valid_ports_ok(self):
        n1, n2 = _node("n1", {"out": {"direction": "output"}}), _node("n2", {"in": {"direction": "input"}})
        h = Harness(name="ok", nodes=[n1, n2], edges=[_edge("e1", "n1", "out", "n2", "in")])
        assert len(h.edges) == 1


# ---------------------------------------------------------------------------
# Package re-exports
# ---------------------------------------------------------------------------

class TestPackageReExports:
    def test_all_symbols_importable(self):
        from app.harnesses import Harness as H, HarnessEdge, HarnessNode, NodeRef, NodeType, Position  # noqa: F401
        from app.harnesses.model import Harness as HModel
        assert H is HModel

    def test_all_in_package_namespace(self):
        import app.harnesses as pkg
        for name in ("Harness", "HarnessEdge", "HarnessNode", "NodeRef", "NodeType", "Position"):
            assert hasattr(pkg, name), f"{name} missing from app.harnesses"


# ---------------------------------------------------------------------------
# Wait node data conventions (documented in model.py module docstring)
# ---------------------------------------------------------------------------

def _wait_node(node_id: str, data: dict | None = None) -> HarnessNode:
    """Build a minimal Wait HarnessNode with the given id and optional data."""
    return HarnessNode(
        id=node_id,
        type=NodeType.wait,
        position=Position(x=0.0, y=0.0),
        data=data or {},
    )


class TestWaitNodeDataConventions:
    """Model-level tests for Wait node ``data`` dict.

    The model itself does not enforce field presence (that is validator.py's
    job); these tests confirm that valid data dicts are accepted and round-trip
    correctly through Pydantic serialisation.
    """

    def test_human_wait_with_max_wait_seconds_accepted(self):
        """A human Wait node with all required fields is accepted."""
        node = _wait_node(
            "w1",
            data={"mode": "human", "max_wait_seconds": 3600, "waiting_question": "Ready?"},
        )
        assert node.type is NodeType.wait
        assert node.data["mode"] == "human"
        assert node.data["max_wait_seconds"] == 3600

    def test_human_wait_without_max_wait_seconds_accepted_at_model_level(self):
        """The model layer does NOT reject a human Wait lacking max_wait_seconds.

        Enforcement is in validator.py (R6).  This confirms the model stays
        open so the validator can produce a clear error message.
        """
        node = _wait_node("w2", data={"mode": "human"})
        assert node.data == {"mode": "human"}

    def test_timed_wait_accepted(self):
        """A timed Wait node with duration_seconds is accepted."""
        node = _wait_node("w3", data={"mode": "timed", "duration_seconds": 30.0})
        assert node.data["mode"] == "timed"
        assert node.data["duration_seconds"] == 30.0

    def test_timed_wait_without_max_wait_seconds_accepted(self):
        """Timed Wait nodes do NOT require max_wait_seconds."""
        node = _wait_node("w4", data={"mode": "timed", "duration_seconds": 10.0})
        assert "max_wait_seconds" not in node.data

    def test_wait_data_isolated_across_instances(self):
        """data dict uses default_factory — instances don't share state."""
        n1, n2 = _wait_node("w5"), _wait_node("w6")
        n1.data["x"] = 1
        assert "x" not in n2.data

    def test_wait_node_in_harness_accepted(self):
        """A Wait node with human mode and max_wait_seconds fits in a Harness."""
        w = _wait_node("w1", data={"mode": "human", "max_wait_seconds": 60})
        h = Harness(name="wh", nodes=[w])
        assert h.nodes[0].type is NodeType.wait


# ---------------------------------------------------------------------------
# Aggregator node data conventions (documented in model.py module docstring)
# ---------------------------------------------------------------------------

def _aggregator_node(node_id: str, data: dict | None = None) -> HarnessNode:
    """Build a minimal Aggregator HarnessNode."""
    return HarnessNode(
        id=node_id,
        type=NodeType.aggregator,
        position=Position(x=0.0, y=0.0),
        data=data or {},
    )


class TestAggregatorNodeDataConventions:
    """Model-level tests for Aggregator node ``data`` dict."""

    def test_aggregator_mode_all_accepted(self):
        """An Aggregator with mode='all' is accepted."""
        node = _aggregator_node("agg1", data={"mode": "all"})
        assert node.type is NodeType.aggregator
        assert node.data["mode"] == "all"

    def test_aggregator_mode_any_accepted(self):
        """An Aggregator with mode='any' is accepted."""
        node = _aggregator_node("agg2", data={"mode": "any"})
        assert node.data["mode"] == "any"

    def test_aggregator_no_data_accepted_at_model_level(self):
        """The model layer does NOT reject Aggregators without mode.

        Enforcement is validator.py's responsibility.
        """
        node = _aggregator_node("agg3")
        assert node.data == {}

    def test_aggregator_node_in_harness_accepted(self):
        """An Aggregator node fits in a Harness."""
        agg = _aggregator_node("agg1", data={"mode": "all"})
        h = Harness(name="ah", nodes=[agg])
        assert h.nodes[0].type is NodeType.aggregator
