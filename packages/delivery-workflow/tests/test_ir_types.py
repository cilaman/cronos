"""Tests for packages/delivery-workflow/ir.py — IR type definitions (I1)."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the package root is on sys.path for direct module imports.

from delivery_workflow.ir import IREdge, IRGraph, IRNode, LoopPolicy


class TestLoopPolicy:
    def test_defaults(self):
        lp = LoopPolicy(until="review.fields.verdict == 'pass'")
        assert lp.until == "review.fields.verdict == 'pass'"
        assert lp.stall == []
        assert lp.max == 5
        assert lp.on_exhaust == "escalate"

    def test_custom_values(self):
        lp = LoopPolicy(
            until="x == 'done'",
            stall=["recurring_findings"],
            max=3,
            on_exhaust="stop",
        )
        assert lp.max == 3
        assert lp.on_exhaust == "stop"
        assert lp.stall == ["recurring_findings"]


class TestIRNode:
    def test_minimal(self):
        node = IRNode(id="scout", kind="agent")
        assert node.id == "scout"
        assert node.kind == "agent"
        assert node.data == {}
        assert node.loop is None

    def test_all_kinds(self):
        kinds = ["agent", "gate", "human", "decision", "wait", "aggregator", "trigger"]
        for kind in kinds:
            node = IRNode(id=f"n-{kind}", kind=kind)  # type: ignore[arg-type]
            assert node.kind == kind

    def test_with_loop_policy(self):
        lp = LoopPolicy(until="review.status == 'done'", max=3)
        node = IRNode(id="review", kind="agent", loop=lp)
        assert node.loop is not None
        assert node.loop.max == 3

    def test_data_dict(self):
        data = {"agent": "reviewer", "model": "opus"}
        node = IRNode(id="review", kind="agent", data=data)
        assert node.data["agent"] == "reviewer"


class TestIREdge:
    def test_minimal(self):
        edge = IREdge(source="a", target="b")
        assert edge.source == "a"
        assert edge.target == "b"
        assert edge.when == ""
        assert edge.port is None

    def test_with_condition(self):
        edge = IREdge(
            source="g-review",
            target="implement",
            when="review.fields.verdict == 'needs_fix'",
        )
        assert edge.when == "review.fields.verdict == 'needs_fix'"

    def test_with_port(self):
        edge = IREdge(source="decision", target="yes-path", port="yes")
        assert edge.port == "yes"


class TestIRGraph:
    def _make_linear(self):
        """A → B → C with no back-edges."""
        nodes = [
            IRNode(id="a", kind="agent"),
            IRNode(id="b", kind="gate"),
            IRNode(id="c", kind="agent"),
        ]
        edges = [
            IREdge(source="a", target="b"),
            IREdge(source="b", target="c"),
        ]
        return IRGraph(nodes=nodes, edges=edges)

    def test_entry_nodes_linear(self):
        g = self._make_linear()
        assert g.entry_nodes == ["a"]

    def test_entry_nodes_no_edges(self):
        g = IRGraph(nodes=[IRNode(id="x", kind="agent"), IRNode(id="y", kind="agent")])
        # Both have in-degree 0.
        assert set(g.entry_nodes) == {"x", "y"}

    def test_entry_nodes_cyclic(self):
        """Back-edge from c back to b; entry is still a."""
        nodes = [
            IRNode(id="a", kind="agent"),
            IRNode(id="b", kind="agent"),
            IRNode(id="c", kind="agent"),
        ]
        edges = [
            IREdge(source="a", target="b"),
            IREdge(source="b", target="c"),
            IREdge(source="c", target="b"),  # back-edge — cycle is legal in IR
        ]
        g = IRGraph(nodes=nodes, edges=edges)
        assert g.entry_nodes == ["a"]

    def test_entry_nodes_preserves_order(self):
        """entry_nodes order matches nodes list order."""
        nodes = [
            IRNode(id="trigger", kind="trigger"),
            IRNode(id="agent1", kind="agent"),
        ]
        g = IRGraph(nodes=nodes)
        assert g.entry_nodes == ["trigger", "agent1"]

    def test_metadata_and_variables(self):
        g = IRGraph(
            metadata={"budget": {"usd_ceiling": 25.0}},
            variables={"env": "prod"},
        )
        assert g.metadata["budget"]["usd_ceiling"] == 25.0
        assert g.variables["env"] == "prod"

    def test_empty_graph(self):
        g = IRGraph()
        assert g.nodes == []
        assert g.edges == []
        assert g.entry_nodes == []
