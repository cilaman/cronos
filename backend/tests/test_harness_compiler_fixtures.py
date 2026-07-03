"""
tests/test_harness_compiler_fixtures.py — Parametrised tests for Compiler B
against real .cronos/harnesses/*.yml fixture files.

Covers:
  - R4: All YAML fixtures in .cronos/harnesses/ compile to a valid IRGraph.

For each fixture, the test:
  1. Parses the YAML into a Harness model.
  2. Calls compiler.compile() → IRGraph.
  3. Asserts structural invariants on the resulting IRGraph:
     - IRGraph.nodes is non-empty (for harnesses that have nodes) OR
       compilation succeeds even for empty-node harnesses.
     - No duplicate node ids in IRGraph.nodes.
     - All edge source/target ids reference existing IRGraph node ids.
     - All IRNode.kind values are from the allowed Literal set.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import get_args

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path bootstrap — make packages/delivery-workflow importable.
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).parent.parent  # backend/
_SPACE_ROOT = _BACKEND_DIR.parent            # cronos-development/

from delivery_workflow.ir import IRGraph, IRNode  # noqa: E402

from app.harnesses.model import Harness  # noqa: E402
from app.harnesses.compiler import compile as harness_compile  # noqa: E402

# ---------------------------------------------------------------------------
# Valid IR node kinds (from IRNode.kind Literal).
# ---------------------------------------------------------------------------
_VALID_KINDS: frozenset[str] = frozenset(
    get_args(IRNode.__dataclass_fields__["kind"].type)  # type: ignore[attr-defined]
    if hasattr(IRNode, "__dataclass_fields__")
    else ["agent", "gate", "human", "decision", "wait", "aggregator", "trigger"]
)

# Explicit set as a safety net in case introspection doesn't find them.
_VALID_KINDS_EXPLICIT: frozenset[str] = frozenset(
    ["agent", "gate", "human", "decision", "wait", "aggregator", "trigger"]
)

# Use the union of introspected + explicit to be robust.
_ALL_VALID_KINDS: frozenset[str] = _VALID_KINDS | _VALID_KINDS_EXPLICIT

# ---------------------------------------------------------------------------
# Collect fixtures.
# ---------------------------------------------------------------------------
_HARNESSES_DIR = _SPACE_ROOT / ".cronos" / "harnesses"


def _collect_fixture_paths() -> list[Path]:
    """Return all *.yml files under .cronos/harnesses/, sorted for stability."""
    return sorted(_HARNESSES_DIR.glob("*.yml"))


_FIXTURE_PATHS = _collect_fixture_paths()

# Build pytest parameter ids from stem names so test names are readable.
_FIXTURE_IDS = [p.stem for p in _FIXTURE_PATHS]


# ---------------------------------------------------------------------------
# Invariant assertions (reusable across parametrise entries).
# ---------------------------------------------------------------------------


def _assert_no_duplicate_node_ids(graph: IRGraph, fixture_name: str) -> None:
    """Assert all node ids in the IRGraph are unique."""
    seen: set[str] = set()
    for node in graph.nodes:
        assert node.id not in seen, (
            f"[{fixture_name}] Duplicate node id '{node.id}' in compiled IRGraph."
        )
        seen.add(node.id)


def _assert_edge_refs_valid(graph: IRGraph, fixture_name: str) -> None:
    """Assert all edge source/target ids reference existing node ids."""
    node_ids: set[str] = {n.id for n in graph.nodes}
    for edge in graph.edges:
        assert edge.source in node_ids, (
            f"[{fixture_name}] IREdge source '{edge.source}' references unknown node id."
        )
        assert edge.target in node_ids, (
            f"[{fixture_name}] IREdge target '{edge.target}' references unknown node id."
        )


def _assert_all_kinds_valid(graph: IRGraph, fixture_name: str) -> None:
    """Assert all IRNode.kind values are in the valid Literal set."""
    for node in graph.nodes:
        assert node.kind in _ALL_VALID_KINDS, (
            f"[{fixture_name}] IRNode '{node.id}' has invalid kind '{node.kind}'. "
            f"Must be one of: {sorted(_ALL_VALID_KINDS)}"
        )


def _assert_structural_invariants(graph: IRGraph, fixture_name: str) -> None:
    """Run all structural invariant checks on a compiled IRGraph."""
    _assert_no_duplicate_node_ids(graph, fixture_name)
    _assert_edge_refs_valid(graph, fixture_name)
    _assert_all_kinds_valid(graph, fixture_name)


# ---------------------------------------------------------------------------
# Parametrised test.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_FIXTURE_IDS)
def test_fixture_compiles_to_valid_irgraph(fixture_path: Path) -> None:
    """Each .cronos/harnesses/*.yml compiles to an IRGraph satisfying structural invariants.

    The test:
    1. Reads and parses the YAML file.
    2. Constructs a Harness model (triggering Pydantic validation).
    3. Calls harness_compile(harness) → IRGraph.
    4. Asserts structural invariants on the IRGraph.

    Empty-node harnesses (nodes: []) are valid; the compiler must produce an
    IRGraph with nodes=[] and edges=[] without raising.
    """
    # Step 1 — parse YAML.
    raw = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), (
        f"Fixture {fixture_path.name} must be a YAML mapping at the top level."
    )

    # Step 2 — construct Harness (Pydantic validation).
    harness = Harness.model_validate(raw)

    fixture_name = fixture_path.stem

    # Step 3 — compile.
    graph: IRGraph = harness_compile(harness)

    # Sanity: result is an IRGraph.
    assert isinstance(graph, IRGraph), (
        f"[{fixture_name}] compile() must return an IRGraph; got {type(graph)!r}."
    )

    # Step 4 — structural invariants.
    _assert_structural_invariants(graph, fixture_name)

    # Node count must match the source harness.
    assert len(graph.nodes) == len(harness.nodes), (
        f"[{fixture_name}] IRGraph has {len(graph.nodes)} nodes but harness has "
        f"{len(harness.nodes)}. Compiler must produce one IRNode per HarnessNode (R1)."
    )

    # Edge count must match the source harness.
    assert len(graph.edges) == len(harness.edges), (
        f"[{fixture_name}] IRGraph has {len(graph.edges)} edges but harness has "
        f"{len(harness.edges)}. Compiler must produce one IREdge per HarnessEdge (R1)."
    )

    # Variables must be preserved.
    assert graph.variables == harness.variables, (
        f"[{fixture_name}] IRGraph.variables {graph.variables!r} does not match "
        f"harness.variables {harness.variables!r}. Compiler must pass variables through (R1)."
    )

    # Metadata must contain the harness name.
    assert graph.metadata.get("name") == harness.name, (
        f"[{fixture_name}] IRGraph.metadata['name'] must equal harness.name '{harness.name}'."
    )


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_FIXTURE_IDS)
def test_fixture_node_ids_preserved(fixture_path: Path) -> None:
    """IRGraph node ids must match the source HarnessNode ids in order (R1)."""
    raw = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    harness = Harness.model_validate(raw)
    graph = harness_compile(harness)

    fixture_name = fixture_path.stem
    source_ids = [n.id for n in harness.nodes]
    compiled_ids = [n.id for n in graph.nodes]

    assert compiled_ids == source_ids, (
        f"[{fixture_name}] IRGraph node ids {compiled_ids!r} differ from "
        f"source harness node ids {source_ids!r}. Order and identity must be preserved (R1)."
    )


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_FIXTURE_IDS)
def test_fixture_edge_ids_in_compiled_graph(fixture_path: Path) -> None:
    """Each compiled edge's source/target matches the source HarnessEdge node refs (R1)."""
    raw = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    harness = Harness.model_validate(raw)
    graph = harness_compile(harness)

    fixture_name = fixture_path.stem
    for he, ie in zip(harness.edges, graph.edges):
        assert ie.source == he.source.node_id, (
            f"[{fixture_name}] IREdge source '{ie.source}' != "
            f"HarnessEdge source node_id '{he.source.node_id}' (R1)."
        )
        assert ie.target == he.target.node_id, (
            f"[{fixture_name}] IREdge target '{ie.target}' != "
            f"HarnessEdge target node_id '{he.target.node_id}' (R1)."
        )
