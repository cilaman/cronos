"""Tests for packages/delivery-workflow/compiler_a.py (I2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


from delivery_workflow import compiler_a
from delivery_workflow.ir import IREdge, IRGraph, IRNode, LoopPolicy
from delivery_workflow.spec_loader import load_spec


MINIMAL_SPEC = {
    "apiVersion": "delivery/v1",
    "metadata": {"name": "test"},
    "defaults": {
        "models": {"build": "sonnet", "recon": "haiku"},
        "budget": {"usd_ceiling": 5.0, "on_exceed": "escalate"},
    },
    "nodes": [
        {"id": "scout", "kind": "agent", "agent": "scout", "model": {"use": "recon"}},
        {"id": "g-scout", "kind": "gate", "checks": [{"type": "schema"}]},
    ],
    "edges": [
        {"from": "scout", "to": "g-scout"},
    ],
}


class TestCompileBasic:
    def test_returns_irgraph(self):
        graph = compiler_a.compile(MINIMAL_SPEC)
        assert isinstance(graph, IRGraph)

    def test_node_count(self):
        graph = compiler_a.compile(MINIMAL_SPEC)
        assert len(graph.nodes) == 2

    def test_edge_count(self):
        graph = compiler_a.compile(MINIMAL_SPEC)
        assert len(graph.edges) == 1

    def test_node_ids(self):
        graph = compiler_a.compile(MINIMAL_SPEC)
        ids = [n.id for n in graph.nodes]
        assert ids == ["scout", "g-scout"]

    def test_node_kinds(self):
        graph = compiler_a.compile(MINIMAL_SPEC)
        kinds = {n.id: n.kind for n in graph.nodes}
        assert kinds["scout"] == "agent"
        assert kinds["g-scout"] == "gate"

    def test_entry_nodes(self):
        graph = compiler_a.compile(MINIMAL_SPEC)
        assert graph.entry_nodes == ["scout"]

    def test_metadata_includes_name(self):
        graph = compiler_a.compile(MINIMAL_SPEC)
        assert graph.metadata.get("name") == "test"

    def test_metadata_includes_budget(self):
        graph = compiler_a.compile(MINIMAL_SPEC)
        assert graph.metadata["budget"]["usd_ceiling"] == 5.0

    def test_edge_from_to(self):
        graph = compiler_a.compile(MINIMAL_SPEC)
        e = graph.edges[0]
        assert e.source == "scout"
        assert e.target == "g-scout"
        assert e.when == ""


class TestModelAliasResolution:
    def test_alias_resolved_to_concrete_model(self):
        graph = compiler_a.compile(MINIMAL_SPEC)
        scout_node = next(n for n in graph.nodes if n.id == "scout")
        # {use: recon} → haiku
        assert scout_node.data["model"] == "haiku"

    def test_bare_string_model_passes_through(self):
        spec = {
            **MINIMAL_SPEC,
            "nodes": [
                {"id": "n1", "kind": "agent", "model": "opus"},
            ],
            "edges": [],
        }
        graph = compiler_a.compile(spec)
        n1 = graph.nodes[0]
        assert n1.data["model"] == "opus"

    def test_node_without_model_has_no_model_key(self):
        spec = {
            **MINIMAL_SPEC,
            "nodes": [
                {"id": "g1", "kind": "gate", "checks": []},
            ],
            "edges": [],
        }
        graph = compiler_a.compile(spec)
        g1 = graph.nodes[0]
        assert "model" not in g1.data or g1.data.get("model") is None

    def test_undefined_alias_lists_all_offenders(self):
        spec = {
            **MINIMAL_SPEC,
            "nodes": [
                {"id": "n1", "kind": "agent", "model": {"use": "missing1"}},
                {"id": "n2", "kind": "agent", "model": {"use": "missing2"}},
                {"id": "n3", "kind": "agent", "model": {"use": "build"}},  # valid
            ],
            "edges": [],
        }
        with pytest.raises(ValueError) as exc_info:
            compiler_a.compile(spec)
        msg = str(exc_info.value)
        assert "'n1'" in msg
        assert "'missing1'" in msg
        assert "'n2'" in msg
        assert "'missing2'" in msg
        # Valid alias n3/build should not appear in the error.
        assert "n3" not in msg

    def test_undefined_alias_single(self):
        spec = {
            **MINIMAL_SPEC,
            "nodes": [
                {"id": "only", "kind": "agent", "model": {"use": "nonexistent"}},
            ],
            "edges": [],
        }
        with pytest.raises(ValueError, match="nonexistent"):
            compiler_a.compile(spec)


class TestLoopPolicy:
    def test_loop_parsed_on_node(self):
        spec = {
            **MINIMAL_SPEC,
            "nodes": [
                {
                    "id": "review",
                    "kind": "agent",
                    "model": {"use": "build"},
                    "loop": {
                        "until": "review.fields.verdict == 'pass'",
                        "stall": ["recurring_findings"],
                        "max": 3,
                        "on_exhaust": "escalate",
                    },
                }
            ],
            "edges": [],
        }
        graph = compiler_a.compile(spec)
        review = graph.nodes[0]
        assert review.loop is not None
        assert review.loop.until == "review.fields.verdict == 'pass'"
        assert review.loop.max == 3
        assert review.loop.stall == ["recurring_findings"]
        assert review.loop.on_exhaust == "escalate"

    def test_loop_removed_from_data(self):
        """loop key must not appear in IRNode.data (it's promoted to .loop)."""
        spec = {
            **MINIMAL_SPEC,
            "nodes": [
                {
                    "id": "review",
                    "kind": "agent",
                    "model": {"use": "build"},
                    "loop": {"until": "review.status == 'done'", "max": 2},
                }
            ],
            "edges": [],
        }
        graph = compiler_a.compile(spec)
        review = graph.nodes[0]
        assert "loop" not in review.data

    def test_node_without_loop_has_none(self):
        graph = compiler_a.compile(MINIMAL_SPEC)
        scout = next(n for n in graph.nodes if n.id == "scout")
        assert scout.loop is None


class TestEdgeParsing:
    def test_edge_with_when(self):
        spec = {
            **MINIMAL_SPEC,
            "edges": [
                {"from": "g-scout", "to": "scout", "when": "g-scout.decision == 'needs_fix'"},
            ],
        }
        graph = compiler_a.compile(spec)
        e = next(e for e in graph.edges if e.when)
        assert e.when == "g-scout.decision == 'needs_fix'"

    def test_back_edge_allowed(self):
        """Compiler A must accept back-edges (cyclic graphs are legal in IR)."""
        spec = {
            **MINIMAL_SPEC,
            "nodes": [
                {"id": "a", "kind": "agent"},
                {"id": "b", "kind": "agent"},
            ],
            "edges": [
                {"from": "a", "to": "b"},
                {"from": "b", "to": "a"},  # back-edge
            ],
        }
        graph = compiler_a.compile(spec)
        assert len(graph.edges) == 2

    def test_id_kind_not_in_data(self):
        """id and kind must not leak into IRNode.data."""
        graph = compiler_a.compile(MINIMAL_SPEC)
        for node in graph.nodes:
            assert "id" not in node.data
            assert "kind" not in node.data


class TestFixtureFile:
    def test_compile_minimal_fixture(self):
        """Compile the compiler_a_minimal.yaml fixture end-to-end."""
        fixture = (
            Path(__file__).parent / "fixtures" / "compiler_a_minimal.yaml"
        )
        spec = load_spec(fixture)
        graph = compiler_a.compile(spec)
        assert len(graph.nodes) == 3
        assert graph.metadata["budget"]["usd_ceiling"] == 5.0
        implement = next(n for n in graph.nodes if n.id == "implement")
        assert implement.loop is not None
        assert implement.loop.max == 3

    def test_compile_delivery_workflow_yaml(self):
        """Compile the production delivery.workflow.yaml without error."""
        prod_yaml = Path(__file__).parent.parent / "src" / "delivery_workflow" / "delivery.workflow.yaml"
        spec = load_spec(prod_yaml)
        graph = compiler_a.compile(spec)
        node_ids = [n.id for n in graph.nodes]
        assert "scout" in node_ids
        assert "implement" in node_ids
        assert "review" in node_ids
        # Budget should be present.
        assert "budget" in graph.metadata

    def test_simple_gates_have_bounded_fix_loops(self):
        """§P4: each simple gate carries a loop block AND a non-proceed fix edge
        routing back to its producing agent (so a failure doesn't hard-stall)."""
        prod_yaml = Path(__file__).parent.parent / "src" / "delivery_workflow" / "delivery.workflow.yaml"
        graph = compiler_a.compile(load_spec(prod_yaml))
        by_id = {n.id: n for n in graph.nodes}
        # gate id → producing agent it should route back to on non-proceed.
        gate_to_producer = {
            "g-scout": "scout",
            "g-analysis": "analyze",
            "g-design": "architect",
            "g-build": "implement",
            "g-doc": "doc",
            "g-retro": "retro",
        }
        for gate_id, producer in gate_to_producer.items():
            assert by_id[gate_id].loop is not None, f"{gate_id} missing loop block"
            assert by_id[gate_id].loop.max >= 1
            fix_edges = [
                e
                for e in graph.edges
                if e.source == gate_id and e.target == producer and "!= 'proceed'" in (e.when or "")
            ]
            assert fix_edges, f"{gate_id} missing '!= proceed' fix edge to {producer}"


class TestOnRejectRouteValidation:
    """OD-1/R7: on_reject must name a declared node that is a FORWARD-ANCESTOR
    of the sign-off — a self/downstream/sibling target would let a rejection
    silently route or starve the approve path (D10)."""

    @staticmethod
    def _spec(on_reject: str, extra_edges: list | None = None):
        return {
            "apiVersion": "delivery/v1",
            "metadata": {"name": "reject-route"},
            "defaults": {"models": {"build": "sonnet"}},
            "nodes": [
                {"id": "a", "kind": "agent", "agent": "a", "model": {"use": "build"}},
                {"id": "fixer", "kind": "agent", "agent": "f", "model": {"use": "build"}},
                {"id": "signoff", "kind": "human", "prompt": "ok?",
                 "on_reject": on_reject},
                {"id": "b", "kind": "agent", "agent": "b", "model": {"use": "build"}},
            ],
            "edges": [
                {"from": "a", "to": "fixer"},
                {"from": "fixer", "to": "signoff"},
                {"from": "signoff", "to": "b"},
                *(extra_edges or []),
            ],
        }

    def test_undeclared_target_rejected(self):
        with pytest.raises(ValueError, match="undeclared"):
            compiler_a.compile(self._spec("ghost"))

    def test_forward_ancestor_target_accepted(self):
        graph = compiler_a.compile(self._spec("fixer"))
        by_id = {n.id: n for n in graph.nodes}
        assert by_id["signoff"].data["on_reject"] == "fixer"

    def test_transitive_forward_ancestor_accepted(self):
        graph = compiler_a.compile(self._spec("a"))
        assert graph is not None

    def test_self_target_rejected(self):
        with pytest.raises(ValueError, match="forward-ancestor"):
            compiler_a.compile(self._spec("signoff"))

    def test_downstream_target_rejected(self):
        with pytest.raises(ValueError, match="forward-ancestor"):
            compiler_a.compile(self._spec("b"))

    def test_parallel_branch_target_rejected(self):
        """The D10-through-resume shape: a → signoff and a → fixer in
        parallel, with fixer having NO path back into the sign-off."""
        spec = {
            "apiVersion": "delivery/v1",
            "metadata": {"name": "reject-route-parallel"},
            "defaults": {"models": {"build": "sonnet"}},
            "nodes": [
                {"id": "a", "kind": "agent", "agent": "a", "model": {"use": "build"}},
                {"id": "signoff", "kind": "human", "prompt": "ok?",
                 "on_reject": "fixer"},
                {"id": "fixer", "kind": "agent", "agent": "f", "model": {"use": "build"}},
                {"id": "b", "kind": "agent", "agent": "b", "model": {"use": "build"}},
            ],
            "edges": [
                {"from": "a", "to": "signoff"},
                {"from": "a", "to": "fixer"},
                {"from": "signoff", "to": "b"},
            ],
        }
        with pytest.raises(ValueError, match="forward-ancestor"):
            compiler_a.compile(spec)

    def test_shipped_spec_routes_still_compile(self):
        prod_yaml = Path(__file__).parent.parent / "src" / "delivery_workflow" / "delivery.workflow.yaml"
        graph = compiler_a.compile(load_spec(prod_yaml))
        routes = {
            n.id: n.data["on_reject"]
            for n in graph.nodes
            if "on_reject" in (n.data or {})
        }
        assert routes == {"signoff-scope": "analyze", "signoff-design": "architect"}
