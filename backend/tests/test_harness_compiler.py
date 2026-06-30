"""
tests/test_harness_compiler.py — Unit tests for backend/app/harnesses/compiler.py

Covers:
  - R1: 1:1 node/edge/variable/metadata mapping
  - R2: Wait-node mode→kind disambiguation (human→'human', timed→'wait', absent→'wait'+warning)
  - R3: LoopPolicy construction (default max=10)
  - R13: Import boundary (compiler only imports from .model and ir)
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path
from datetime import datetime, timezone

import pytest

# ---------------------------------------------------------------------------
# Ensure packages/delivery-workflow is importable.
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).parent.parent  # backend/
_SPACE_ROOT = _BACKEND_DIR.parent            # cronos-development/
_DW_PKG = str(_SPACE_ROOT / "packages" / "delivery-workflow")
if _DW_PKG not in sys.path:
    sys.path.insert(0, _DW_PKG)

from ir import IREdge, IRGraph, IRNode, LoopPolicy  # noqa: E402

from app.harnesses.model import (  # noqa: E402
    Harness,
    HarnessEdge,
    HarnessNode,
    NodeRef,
    NodeType,
    Position,
)
from app.harnesses.compiler import compile as harness_compile  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pos() -> Position:
    return Position(x=0.0, y=0.0)


def _make_node(
    node_id: str,
    node_type: NodeType,
    data: dict | None = None,
    ports: dict | None = None,
    label: str = "",
) -> HarnessNode:
    return HarnessNode(
        id=node_id,
        type=node_type,
        position=_pos(),
        data=data or {},
        ports=ports or {"in": {}, "out": {}},
        label=label,
    )


def _make_edge(
    edge_id: str,
    src_node: str,
    tgt_node: str,
    src_port: str = "out",
    tgt_port: str = "in",
    condition: str | None = None,
) -> HarnessEdge:
    return HarnessEdge(
        id=edge_id,
        source=NodeRef(node_id=src_node, port_id=src_port),
        target=NodeRef(node_id=tgt_node, port_id=tgt_port),
        condition=condition,
    )


def _make_harness(
    nodes: list[HarnessNode],
    edges: list[HarnessEdge] | None = None,
    variables: dict | None = None,
    name: str = "test-harness",
) -> Harness:
    return Harness(
        name=name,
        nodes=nodes,
        edges=edges or [],
        variables=variables or {},
    )


# ---------------------------------------------------------------------------
# R1: 1:1 node mapping
# ---------------------------------------------------------------------------


class TestNodeMapping:
    """R1: each node type maps to the correct IR kind."""

    @pytest.mark.parametrize(
        "node_type, expected_kind",
        [
            (NodeType.agent, "agent"),
            (NodeType.trigger, "trigger"),
            (NodeType.decision, "decision"),
            (NodeType.aggregator, "aggregator"),
        ],
    )
    def test_simple_node_type_mapping(self, node_type: NodeType, expected_kind: str) -> None:
        node = _make_node("n1", node_type)
        harness = _make_harness([node])
        graph = harness_compile(harness)
        assert len(graph.nodes) == 1
        assert graph.nodes[0].id == "n1"
        assert graph.nodes[0].kind == expected_kind

    def test_node_id_preserved(self) -> None:
        nodes = [
            _make_node("alpha", NodeType.agent),
            _make_node("beta", NodeType.trigger),
        ]
        harness = _make_harness(nodes)
        graph = harness_compile(harness)
        ids = [n.id for n in graph.nodes]
        assert ids == ["alpha", "beta"]

    def test_node_data_passed_through(self) -> None:
        data = {"agent_ref": "my-agent", "prompt_template": "hello ${x}"}
        node = _make_node("n1", NodeType.agent, data=data)
        harness = _make_harness([node])
        graph = harness_compile(harness)
        assert graph.nodes[0].data["agent_ref"] == "my-agent"
        assert graph.nodes[0].data["prompt_template"] == "hello ${x}"

    def test_node_order_preserved(self) -> None:
        """Compiler must preserve the order of nodes from the harness."""
        node_ids = ["z-node", "a-node", "m-node"]
        nodes = [_make_node(nid, NodeType.agent) for nid in node_ids]
        harness = _make_harness(nodes)
        graph = harness_compile(harness)
        assert [n.id for n in graph.nodes] == node_ids

    def test_empty_harness(self) -> None:
        harness = _make_harness([])
        graph = harness_compile(harness)
        assert graph.nodes == []
        assert graph.edges == []


# ---------------------------------------------------------------------------
# R1: 1:1 edge mapping
# ---------------------------------------------------------------------------


class TestEdgeMapping:
    """R1: each edge maps correctly to IREdge."""

    def test_unconditional_edge(self) -> None:
        nodes = [_make_node("a", NodeType.agent), _make_node("b", NodeType.agent)]
        edges = [_make_edge("e1", "a", "b", condition=None)]
        harness = _make_harness(nodes, edges)
        graph = harness_compile(harness)
        assert len(graph.edges) == 1
        e = graph.edges[0]
        assert e.source == "a"
        assert e.target == "b"
        assert e.when == ""  # None condition → "" (unconditional in runner)

    def test_conditional_edge(self) -> None:
        nodes = [
            _make_node("d", NodeType.decision, ports={"in": {}, "yes": {}, "no": {}}),
            _make_node("pass", NodeType.agent),
        ]
        edges = [_make_edge("e1", "d", "pass", src_port="yes", condition="result == 'pass'")]
        harness = _make_harness(nodes, edges)
        graph = harness_compile(harness)
        assert graph.edges[0].when == "result == 'pass'"

    def test_edge_port_encodes_source_port_id(self) -> None:
        """OQ-1: IREdge.port encodes source.port_id only."""
        nodes = [
            _make_node("d", NodeType.decision, ports={"in": {}, "yes": {}, "no": {}}),
            _make_node("x", NodeType.agent),
        ]
        edges = [_make_edge("e1", "d", "x", src_port="yes")]
        harness = _make_harness(nodes, edges)
        graph = harness_compile(harness)
        assert graph.edges[0].port == "yes"

    def test_edge_order_preserved(self) -> None:
        nodes = [
            _make_node("a", NodeType.agent, ports={"out1": {}, "out2": {}, "in": {}}),
            _make_node("b", NodeType.agent),
            _make_node("c", NodeType.agent),
        ]
        edges = [
            _make_edge("e2", "a", "c", src_port="out2"),
            _make_edge("e1", "a", "b", src_port="out1"),
        ]
        harness = _make_harness(nodes, edges)
        graph = harness_compile(harness)
        assert [e.source for e in graph.edges] == ["a", "a"]
        assert [e.target for e in graph.edges] == ["c", "b"]

    def test_multiple_edges(self) -> None:
        nodes = [
            _make_node("t", NodeType.trigger),
            _make_node("a1", NodeType.agent),
            _make_node("a2", NodeType.agent),
        ]
        edges = [
            _make_edge("e1", "t", "a1"),
            _make_edge("e2", "t", "a2"),
        ]
        harness = _make_harness(nodes, edges)
        graph = harness_compile(harness)
        assert len(graph.edges) == 2


# ---------------------------------------------------------------------------
# R1: Variables and metadata mapping
# ---------------------------------------------------------------------------


class TestVariablesAndMetadata:
    """R1: variables and metadata round-trip without loss."""

    def test_variables_copied(self) -> None:
        harness = _make_harness([], variables={"env": "prod", "budget": "100"})
        graph = harness_compile(harness)
        assert graph.variables == {"env": "prod", "budget": "100"}

    def test_empty_variables(self) -> None:
        harness = _make_harness([])
        graph = harness_compile(harness)
        assert graph.variables == {}

    def test_variables_not_aliased(self) -> None:
        """Mutation of the harness variables should not affect the IRGraph."""
        vars_dict = {"x": "1"}
        harness = _make_harness([], variables=vars_dict)
        graph = harness_compile(harness)
        vars_dict["y"] = "2"
        assert "y" not in graph.variables

    def test_metadata_name(self) -> None:
        harness = _make_harness([], name="my-harness")
        graph = harness_compile(harness)
        assert graph.metadata["name"] == "my-harness"

    def test_metadata_description(self) -> None:
        harness = Harness(name="h", description="some description", nodes=[], edges=[])
        graph = harness_compile(harness)
        assert graph.metadata["description"] == "some description"

    def test_metadata_version(self) -> None:
        harness = Harness(name="h", version="2.0", nodes=[], edges=[])
        graph = harness_compile(harness)
        assert graph.metadata["version"] == "2.0"

    def test_metadata_timestamps_present(self) -> None:
        harness = _make_harness([])
        graph = harness_compile(harness)
        assert "created_at" in graph.metadata
        assert "updated_at" in graph.metadata


# ---------------------------------------------------------------------------
# R2: Wait-node mode→kind disambiguation
# ---------------------------------------------------------------------------


class TestWaitNodeDisambiguation:
    """R2: explicit mode→kind table with correct fallback behaviour."""

    def test_wait_human_mode_maps_to_human(self) -> None:
        node = _make_node("w", NodeType.wait, data={"mode": "human", "max_wait_seconds": 3600})
        harness = _make_harness([node])
        graph = harness_compile(harness)
        assert graph.nodes[0].kind == "human"

    def test_wait_timed_mode_maps_to_wait(self) -> None:
        node = _make_node("w", NodeType.wait, data={"mode": "timed", "duration_seconds": 60})
        harness = _make_harness([node])
        graph = harness_compile(harness)
        assert graph.nodes[0].kind == "wait"

    def test_wait_absent_mode_defaults_to_wait(self, caplog: pytest.LogCaptureFixture) -> None:
        """Absent mode: kind='wait', warning logged."""
        node = _make_node("w", NodeType.wait, data={})
        harness = _make_harness([node])
        with caplog.at_level(logging.WARNING, logger="app.harnesses.compiler"):
            graph = harness_compile(harness)
        assert graph.nodes[0].kind == "wait"
        assert any("no 'mode'" in msg for msg in caplog.messages)

    def test_wait_unknown_mode_defaults_to_wait(self, caplog: pytest.LogCaptureFixture) -> None:
        """Unknown mode value: kind='wait', warning logged."""
        node = _make_node("w", NodeType.wait, data={"mode": "interval"})
        harness = _make_harness([node])
        with caplog.at_level(logging.WARNING, logger="app.harnesses.compiler"):
            graph = harness_compile(harness)
        assert graph.nodes[0].kind == "wait"
        assert any("unrecognised" in msg for msg in caplog.messages)

    def test_wait_data_preserved_in_ir_node(self) -> None:
        """Wait node data (e.g. duration_seconds) passes through to IRNode.data."""
        data = {"mode": "timed", "duration_seconds": 120}
        node = _make_node("w", NodeType.wait, data=data)
        harness = _make_harness([node])
        graph = harness_compile(harness)
        assert graph.nodes[0].data["duration_seconds"] == 120


# ---------------------------------------------------------------------------
# R3: LoopPolicy construction
# ---------------------------------------------------------------------------


class TestLoopPolicy:
    """R3: LoopPolicy is constructed with default max=10 (not runner's 5)."""

    def test_agent_with_no_loop_has_no_loop_policy(self) -> None:
        node = _make_node("a", NodeType.agent, data={"agent_ref": "impl"})
        harness = _make_harness([node])
        graph = harness_compile(harness)
        assert graph.nodes[0].loop is None

    def test_agent_with_loop_stanza(self) -> None:
        loop_data = {
            "until": "result.status == 'pass'",
            "stall": ["recurring_findings"],
            "max": 5,
            "on_exhaust": "escalate",
        }
        data = {"agent_ref": "review", "loop": loop_data}
        node = _make_node("r", NodeType.agent, data=data)
        harness = _make_harness([node])
        graph = harness_compile(harness)
        lp = graph.nodes[0].loop
        assert lp is not None
        assert lp.until == "result.status == 'pass'"
        assert lp.stall == ["recurring_findings"]
        assert lp.max == 5
        assert lp.on_exhaust == "escalate"

    def test_loop_default_max_is_10(self) -> None:
        """Default max is 10 (R3), NOT the runner's default of 5."""
        data = {"agent_ref": "impl", "loop": {"until": "done == true"}}
        node = _make_node("a", NodeType.agent, data=data)
        harness = _make_harness([node])
        graph = harness_compile(harness)
        lp = graph.nodes[0].loop
        assert lp is not None
        assert lp.max == 10, "Default loop max must be 10 (Cronos-layer default, not runner's 5)"

    def test_loop_default_on_exhaust_is_escalate(self) -> None:
        data = {"agent_ref": "impl", "loop": {"until": "done == true"}}
        node = _make_node("a", NodeType.agent, data=data)
        harness = _make_harness([node])
        graph = harness_compile(harness)
        lp = graph.nodes[0].loop
        assert lp is not None
        assert lp.on_exhaust == "escalate"

    def test_loop_empty_stall_list(self) -> None:
        data = {"agent_ref": "impl", "loop": {"until": "done"}}
        node = _make_node("a", NodeType.agent, data=data)
        harness = _make_harness([node])
        graph = harness_compile(harness)
        lp = graph.nodes[0].loop
        assert lp is not None
        assert lp.stall == []

    def test_non_agent_node_never_has_loop(self) -> None:
        """Control-flow nodes never get a LoopPolicy (runner doesn't support it)."""
        for node_type in (NodeType.trigger, NodeType.decision, NodeType.aggregator):
            # Put a "loop" key in data to confirm it is not parsed for non-agent nodes.
            data = {"loop": {"until": "true", "max": 3}}
            node = _make_node("n", node_type, data=data)
            harness = _make_harness([node])
            graph = harness_compile(harness)
            assert graph.nodes[0].loop is None, (
                f"Node type {node_type} should never produce a LoopPolicy"
            )

    def test_wait_node_never_has_loop(self) -> None:
        data = {"mode": "timed", "duration_seconds": 10, "loop": {"until": "true"}}
        node = _make_node("w", NodeType.wait, data=data)
        harness = _make_harness([node])
        graph = harness_compile(harness)
        assert graph.nodes[0].loop is None


# ---------------------------------------------------------------------------
# R13: Import boundary
# ---------------------------------------------------------------------------


class TestImportBoundary:
    """R13: compiler module imports only from .model and ir; no app.* pollutants."""

    def test_compiler_does_not_import_app_worker(self) -> None:
        import app.harnesses.compiler as comp_mod  # noqa: PLC0415
        # Inspect the module's __dict__ for forbidden imports.
        forbidden_prefixes = ("app.worker", "app.agent", "app.storage", "app.run_executor")
        for name in sys.modules:
            if any(name.startswith(pfx) for pfx in forbidden_prefixes):
                assert name not in vars(comp_mod), (
                    f"compiler imported forbidden module: {name}"
                )

    def test_compiler_module_imports_only_allowed_symbols(self) -> None:
        """Verify the compiler's own import list does not include runner, lib, or adapters."""
        import importlib  # noqa: PLC0415
        import importlib.util  # noqa: PLC0415

        compiler_path = Path(__file__).parent.parent / "app" / "harnesses" / "compiler.py"
        source = compiler_path.read_text()

        # Forbidden substrings in import statements.
        forbidden = [
            "from runner",
            "import runner",
            "from lib.",
            "import lib.",
            "from adapters",
            "import adapters",
            "from app.worker",
            "from app.agent",
            "from app.storage",
            "from app.run_executor",
        ]
        for phrase in forbidden:
            assert phrase not in source, (
                f"compiler.py contains forbidden import: {phrase!r}"
            )


# ---------------------------------------------------------------------------
# Integration: IRGraph structural invariants
# ---------------------------------------------------------------------------


class TestIRGraphStructuralInvariants:
    """Verify the produced IRGraph satisfies runner structural contracts."""

    def test_returns_irgraph_instance(self) -> None:
        harness = _make_harness([])
        graph = harness_compile(harness)
        assert isinstance(graph, IRGraph)

    def test_nodes_are_irnodes(self) -> None:
        nodes = [_make_node("a", NodeType.agent)]
        harness = _make_harness(nodes)
        graph = harness_compile(harness)
        for n in graph.nodes:
            assert isinstance(n, IRNode)

    def test_edges_are_iredges(self) -> None:
        nodes = [_make_node("a", NodeType.agent), _make_node("b", NodeType.agent)]
        edges = [_make_edge("e1", "a", "b")]
        harness = _make_harness(nodes, edges)
        graph = harness_compile(harness)
        for e in graph.edges:
            assert isinstance(e, IREdge)

    def test_entry_nodes_on_linear_graph(self) -> None:
        """IRGraph.entry_nodes should return the trigger node for a linear harness."""
        nodes = [
            _make_node("trigger", NodeType.trigger),
            _make_node("agent", NodeType.agent),
        ]
        edges = [_make_edge("e1", "trigger", "agent")]
        harness = _make_harness(nodes, edges)
        graph = harness_compile(harness)
        assert graph.entry_nodes == ["trigger"]

    def test_full_pipeline_harness(self) -> None:
        """Compile a representative trigger → agent → decision → two-agent harness."""
        nodes = [
            _make_node("t", NodeType.trigger),
            _make_node("impl", NodeType.agent, data={"agent_ref": "implementor"}),
            _make_node("d", NodeType.decision, ports={"in": {}, "yes": {}, "no": {}}),
            _make_node("pass-node", NodeType.agent, data={"agent_ref": "finalizer"}),
            _make_node("fail-node", NodeType.agent, data={"agent_ref": "escalator"}),
        ]
        edges = [
            _make_edge("e1", "t", "impl"),
            _make_edge("e2", "impl", "d"),
            _make_edge("e3", "d", "pass-node", src_port="yes", condition="verdict == 'pass'"),
            _make_edge("e4", "d", "fail-node", src_port="no", condition="verdict != 'pass'"),
        ]
        harness = _make_harness(nodes, edges, name="pipeline-harness")
        graph = harness_compile(harness)

        assert len(graph.nodes) == 5
        assert len(graph.edges) == 4
        assert graph.nodes[0].kind == "trigger"
        assert graph.nodes[1].kind == "agent"
        assert graph.nodes[2].kind == "decision"
        # Conditional edges have when set.
        yes_edge = next(e for e in graph.edges if e.port == "yes")
        assert yes_edge.when == "verdict == 'pass'"
        no_edge = next(e for e in graph.edges if e.port == "no")
        assert no_edge.when == "verdict != 'pass'"

    def test_aggregator_harness(self) -> None:
        """Compile a harness with both 'all' and 'any' aggregator nodes."""
        nodes = [
            _make_node("t", NodeType.trigger),
            _make_node("a1", NodeType.agent),
            _make_node("a2", NodeType.agent),
            _make_node("agg", NodeType.aggregator, data={"mode": "all"}),
            _make_node("final", NodeType.agent),
        ]
        edges = [
            _make_edge("e1", "t", "a1"),
            _make_edge("e2", "t", "a2"),
            _make_edge("e3", "a1", "agg"),
            _make_edge("e4", "a2", "agg"),
            _make_edge("e5", "agg", "final"),
        ]
        harness = _make_harness(nodes, edges)
        graph = harness_compile(harness)
        assert len(graph.nodes) == 5
        agg_node = next(n for n in graph.nodes if n.id == "agg")
        assert agg_node.kind == "aggregator"
        assert agg_node.data["mode"] == "all"

    def test_wait_human_in_pipeline(self) -> None:
        """Human-wait node in a pipeline compiles to kind='human'."""
        nodes = [
            _make_node("t", NodeType.trigger),
            _make_node("w", NodeType.wait, data={"mode": "human", "max_wait_seconds": 7200}),
            _make_node("a", NodeType.agent),
        ]
        edges = [
            _make_edge("e1", "t", "w"),
            _make_edge("e2", "w", "a"),
        ]
        harness = _make_harness(nodes, edges)
        graph = harness_compile(harness)
        wait_ir = next(n for n in graph.nodes if n.id == "w")
        assert wait_ir.kind == "human"
        assert wait_ir.loop is None

    def test_loop_agent_in_pipeline(self) -> None:
        """Agent with a loop stanza compiles to IRNode with LoopPolicy."""
        loop_data = {"until": "review.fields.verdict == 'pass'", "max": 3}
        nodes = [
            _make_node("t", NodeType.trigger),
            _make_node("r", NodeType.agent, data={"agent_ref": "reviewer", "loop": loop_data}),
        ]
        edges = [_make_edge("e1", "t", "r")]
        harness = _make_harness(nodes, edges)
        graph = harness_compile(harness)
        reviewer = next(n for n in graph.nodes if n.id == "r")
        assert reviewer.loop is not None
        assert reviewer.loop.max == 3
        assert reviewer.loop.until == "review.fields.verdict == 'pass'"
