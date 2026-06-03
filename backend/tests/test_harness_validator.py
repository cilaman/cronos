"""
Tests for backend/app/harnesses/validator.py

Covers:
  - Self-loop A->A raises HarnessGraphError
  - Two-node cycle A->B->A raises HarnessGraphError
  - Three-node cycle A->B->C->A raises HarnessGraphError
  - Parallel edges A->B + A->B (duplicate) with no cycle → passes
  - Fan-out A->B + A->C with no cycle → passes
  - Valid DAG passes (no exception)
  - Error messages are informative (contain cycle node_ids)
  - find_cycle() returns None for acyclic graphs
  - find_cycle() returns a cycle path for cyclic graphs
"""

import pytest

from app.harnesses.model import (
    Harness,
    HarnessEdge,
    HarnessNode,
    NodeRef,
    NodeType,
    Position,
)
from app.harnesses.validator import HarnessGraphError, find_cycle, validate_graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(nid: str, ports: dict | None = None) -> HarnessNode:
    """Build a minimal HarnessNode with the given id and optional ports."""
    return HarnessNode(
        id=nid,
        type=NodeType.agent,
        position=Position(x=0.0, y=0.0),
        ports=ports if ports is not None else {"out": {}, "in": {}},
    )


def _edge(eid: str, src_node: str, tgt_node: str, src_port: str = "out", tgt_port: str = "in") -> HarnessEdge:
    """Build a HarnessEdge connecting src_node.src_port → tgt_node.tgt_port."""
    return HarnessEdge(
        id=eid,
        source=NodeRef(node_id=src_node, port_id=src_port),
        target=NodeRef(node_id=tgt_node, port_id=tgt_port),
    )


def _harness(name: str, nodes: list[HarnessNode], edges: list[HarnessEdge]) -> Harness:
    """Build a Harness bypassing the Pydantic model_validator cycle check (cycles
    are tested at the validator level, not the model level)."""
    # We build the Harness normally; the model_validator checks R1-R4 (ref
    # integrity) but NOT cycles (R5, deferred to validator.py).
    return Harness(name=name, nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Tests for find_cycle()
# ---------------------------------------------------------------------------

class TestFindCycle:
    """Unit tests for the pure find_cycle() function."""

    def test_empty_graph_returns_none(self):
        assert find_cycle([], []) is None

    def test_single_node_no_edges_returns_none(self):
        nodes = [_node("A")]
        assert find_cycle(nodes, []) is None

    def test_self_loop_returns_cycle(self):
        """A self-loop A->A is detected immediately."""
        nodes = [_node("A")]
        # We bypass Pydantic validation for the edge because R3 would catch
        # the self-loop before validator.py gets a chance to (port must exist
        # on same node).  We use find_cycle directly with raw-constructed edges.
        edges = [HarnessEdge(
            id="e1",
            source=NodeRef(node_id="A", port_id="out"),
            target=NodeRef(node_id="A", port_id="in"),
        )]
        result = find_cycle(nodes, edges)
        assert result is not None
        assert result == ["A", "A"]

    def test_two_node_cycle_detected(self):
        """A->B->A cycle is detected."""
        nodes = [_node("A"), _node("B")]
        edges = [
            HarnessEdge(id="e1", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="B", port_id="in")),
            HarnessEdge(id="e2", source=NodeRef(node_id="B", port_id="out"), target=NodeRef(node_id="A", port_id="in")),
        ]
        result = find_cycle(nodes, edges)
        assert result is not None
        # cycle path starts and ends with the same node
        assert result[0] == result[-1]
        # both A and B appear in the cycle path
        assert "A" in result
        assert "B" in result

    def test_three_node_cycle_detected(self):
        """A->B->C->A cycle is detected."""
        nodes = [_node("A"), _node("B"), _node("C")]
        edges = [
            HarnessEdge(id="e1", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="B", port_id="in")),
            HarnessEdge(id="e2", source=NodeRef(node_id="B", port_id="out"), target=NodeRef(node_id="C", port_id="in")),
            HarnessEdge(id="e3", source=NodeRef(node_id="C", port_id="out"), target=NodeRef(node_id="A", port_id="in")),
        ]
        result = find_cycle(nodes, edges)
        assert result is not None
        assert result[0] == result[-1]
        assert "A" in result
        assert "B" in result
        assert "C" in result

    def test_parallel_edges_no_cycle_returns_none(self):
        """A->B + A->B (duplicate) with no back-edge: acyclic."""
        nodes = [_node("A"), _node("B")]
        edges = [
            HarnessEdge(id="e1", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="B", port_id="in")),
            HarnessEdge(id="e2", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="B", port_id="in")),
        ]
        result = find_cycle(nodes, edges)
        assert result is None

    def test_fan_out_no_cycle_returns_none(self):
        """A->B + A->C with no back-edges: acyclic."""
        nodes = [_node("A"), _node("B"), _node("C")]
        edges = [
            HarnessEdge(id="e1", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="B", port_id="in")),
            HarnessEdge(id="e2", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="C", port_id="in")),
        ]
        result = find_cycle(nodes, edges)
        assert result is None

    def test_linear_dag_returns_none(self):
        """A->B->C (linear chain) is acyclic."""
        nodes = [_node("A"), _node("B"), _node("C")]
        edges = [
            HarnessEdge(id="e1", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="B", port_id="in")),
            HarnessEdge(id="e2", source=NodeRef(node_id="B", port_id="out"), target=NodeRef(node_id="C", port_id="in")),
        ]
        result = find_cycle(nodes, edges)
        assert result is None

    def test_diamond_dag_returns_none(self):
        """Diamond A->B->D + A->C->D is acyclic."""
        nodes = [_node("A"), _node("B"), _node("C"), _node("D")]
        edges = [
            HarnessEdge(id="e1", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="B", port_id="in")),
            HarnessEdge(id="e2", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="C", port_id="in")),
            HarnessEdge(id="e3", source=NodeRef(node_id="B", port_id="out"), target=NodeRef(node_id="D", port_id="in")),
            HarnessEdge(id="e4", source=NodeRef(node_id="C", port_id="out"), target=NodeRef(node_id="D", port_id="in")),
        ]
        result = find_cycle(nodes, edges)
        assert result is None

    def test_isolated_nodes_no_edges_returns_none(self):
        """Multiple isolated nodes with no edges — acyclic."""
        nodes = [_node("A"), _node("B"), _node("C")]
        result = find_cycle(nodes, [])
        assert result is None

    def test_cycle_path_first_equals_last(self):
        """The returned cycle path always has path[0] == path[-1]."""
        nodes = [_node("X"), _node("Y")]
        edges = [
            HarnessEdge(id="e1", source=NodeRef(node_id="X", port_id="out"), target=NodeRef(node_id="Y", port_id="in")),
            HarnessEdge(id="e2", source=NodeRef(node_id="Y", port_id="out"), target=NodeRef(node_id="X", port_id="in")),
        ]
        result = find_cycle(nodes, edges)
        assert result is not None
        assert result[0] == result[-1]


# ---------------------------------------------------------------------------
# Tests for validate_graph()
# ---------------------------------------------------------------------------

class TestValidateGraph:
    """Integration tests using full Harness objects via validate_graph()."""

    def test_valid_dag_does_not_raise(self):
        """A valid DAG harness passes without raising."""
        nodes = [_node("A"), _node("B"), _node("C")]
        edges = [
            _edge("e1", "A", "B"),
            _edge("e2", "B", "C"),
        ]
        harness = _harness("linear", nodes, edges)
        # Should not raise
        validate_graph(harness)

    def test_empty_harness_does_not_raise(self):
        """A harness with no nodes and no edges is trivially acyclic."""
        harness = Harness(name="empty")
        validate_graph(harness)

    def test_nodes_only_no_edges_does_not_raise(self):
        """Nodes with no edges are acyclic."""
        nodes = [_node("A"), _node("B")]
        harness = _harness("isolated", nodes, [])
        validate_graph(harness)

    def test_self_loop_raises_harness_graph_error(self):
        """A self-loop A->A raises HarnessGraphError."""
        # Build a single-node harness then inject the self-loop edge manually
        # to test the validator directly (Pydantic allows same-node source/target
        # as long as R3/R4 are satisfied, which they are when ports exist).
        node_a = _node("A")
        self_loop_edge = HarnessEdge(
            id="e1",
            source=NodeRef(node_id="A", port_id="out"),
            target=NodeRef(node_id="A", port_id="in"),
        )
        harness = Harness(name="self-loop", nodes=[node_a], edges=[self_loop_edge])
        with pytest.raises(HarnessGraphError) as exc_info:
            validate_graph(harness)
        assert "A" in str(exc_info.value)

    def test_two_node_cycle_raises_harness_graph_error(self):
        """A->B->A raises HarnessGraphError with informative message."""
        nodes = [_node("A"), _node("B")]
        # Build the cyclic edges directly (bypassing Pydantic — R3/R4 allow this
        # since both nodes and ports exist; R5 is the validator.py concern).
        cycle_edges = [
            HarnessEdge(id="e1", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="B", port_id="in")),
            HarnessEdge(id="e2", source=NodeRef(node_id="B", port_id="out"), target=NodeRef(node_id="A", port_id="in")),
        ]
        harness = Harness(name="two-cycle", nodes=nodes, edges=cycle_edges)
        with pytest.raises(HarnessGraphError) as exc_info:
            validate_graph(harness)
        msg = str(exc_info.value)
        assert "A" in msg
        assert "B" in msg
        # Message should include the harness name
        assert "two-cycle" in msg

    def test_three_node_cycle_raises_harness_graph_error(self):
        """A->B->C->A raises HarnessGraphError."""
        nodes = [_node("A"), _node("B"), _node("C")]
        cycle_edges = [
            HarnessEdge(id="e1", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="B", port_id="in")),
            HarnessEdge(id="e2", source=NodeRef(node_id="B", port_id="out"), target=NodeRef(node_id="C", port_id="in")),
            HarnessEdge(id="e3", source=NodeRef(node_id="C", port_id="out"), target=NodeRef(node_id="A", port_id="in")),
        ]
        harness = Harness(name="three-cycle", nodes=nodes, edges=cycle_edges)
        with pytest.raises(HarnessGraphError) as exc_info:
            validate_graph(harness)
        msg = str(exc_info.value)
        assert "A" in msg
        assert "B" in msg
        assert "C" in msg
        assert "three-cycle" in msg

    def test_parallel_edges_no_cycle_does_not_raise(self):
        """Parallel edges A->B + A->B (duplicate) with no back-edge: acyclic."""
        nodes = [_node("A"), _node("B")]
        # Use distinct edge IDs to pass R2 (unique edge ids); parallel arcs are
        # still tested by using the same source/target combination.
        parallel_edges = [
            HarnessEdge(id="e1", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="B", port_id="in")),
            HarnessEdge(id="e2", source=NodeRef(node_id="A", port_id="out"), target=NodeRef(node_id="B", port_id="in")),
        ]
        harness = Harness(name="parallel", nodes=nodes, edges=parallel_edges)
        validate_graph(harness)  # must not raise

    def test_fan_out_no_cycle_does_not_raise(self):
        """A->B + A->C with no back-edges: acyclic."""
        nodes = [_node("A"), _node("B"), _node("C")]
        fan_edges = [
            _edge("e1", "A", "B"),
            _edge("e2", "A", "C"),
        ]
        harness = _harness("fan-out", nodes, fan_edges)
        validate_graph(harness)  # must not raise

    def test_error_message_contains_arrow_separator(self):
        """Error message uses ' -> ' to separate cycle path nodes."""
        nodes = [_node("P"), _node("Q")]
        cycle_edges = [
            HarnessEdge(id="e1", source=NodeRef(node_id="P", port_id="out"), target=NodeRef(node_id="Q", port_id="in")),
            HarnessEdge(id="e2", source=NodeRef(node_id="Q", port_id="out"), target=NodeRef(node_id="P", port_id="in")),
        ]
        harness = Harness(name="pq-cycle", nodes=nodes, edges=cycle_edges)
        with pytest.raises(HarnessGraphError) as exc_info:
            validate_graph(harness)
        assert " -> " in str(exc_info.value)

    def test_error_message_contains_cycle_keyword(self):
        """Error message explicitly mentions 'cycle' for clarity."""
        nodes = [_node("M"), _node("N")]
        cycle_edges = [
            HarnessEdge(id="e1", source=NodeRef(node_id="M", port_id="out"), target=NodeRef(node_id="N", port_id="in")),
            HarnessEdge(id="e2", source=NodeRef(node_id="N", port_id="out"), target=NodeRef(node_id="M", port_id="in")),
        ]
        harness = Harness(name="mn-cycle", nodes=nodes, edges=cycle_edges)
        with pytest.raises(HarnessGraphError) as exc_info:
            validate_graph(harness)
        assert "cycle" in str(exc_info.value).lower()

    def test_diamond_dag_does_not_raise(self):
        """Diamond A->B->D + A->C->D is a valid DAG."""
        nodes = [_node("A"), _node("B"), _node("C"), _node("D")]
        edges = [
            _edge("e1", "A", "B"),
            _edge("e2", "A", "C"),
            _edge("e3", "B", "D"),
            _edge("e4", "C", "D"),
        ]
        harness = _harness("diamond", nodes, edges)
        validate_graph(harness)

    def test_harness_graph_error_is_exception(self):
        """HarnessGraphError inherits from Exception."""
        assert issubclass(HarnessGraphError, Exception)

    def test_harness_graph_error_can_be_raised_directly(self):
        """HarnessGraphError can be raised and caught independently."""
        with pytest.raises(HarnessGraphError, match="test error"):
            raise HarnessGraphError("test error")
