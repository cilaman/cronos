"""
backend/app/harnesses/validator — DAG cycle and self-loop validator.

This module provides pure-function cycle detection and structural validation
for a harness graph.  It is completely independent of storage.py and only
imports from the harnesses model module.

Validation rules enforced here:
  R5: the harness edge graph is a DAG — no cycles and no self-loops.
  R6: human Wait nodes must supply ``max_wait_seconds`` in their ``data``
      dict.  A missing field would cause the harness to park in WAITING
      indefinitely if no reply ever arrives.

The cycle detection algorithm is adapted from storage.py::_dep_cycle_path
(BFS through depends_on links) but traverses *outbound edges per node*
instead of node.depends_on.  The adjacency graph is built from
HarnessEdge.source.node_id → HarnessEdge.target.node_id pairs.
"""

from __future__ import annotations

from collections import deque

from app.harnesses.model import Harness, HarnessEdge, HarnessNode, NodeType


class HarnessValidationError(Exception):
    """Raised when validate_graph detects a structural rule violation (R6, etc.)."""


class HarnessGraphError(HarnessValidationError):
    """Raised when validate_graph detects a cycle or self-loop in the edge graph."""


def find_cycle(
    nodes: list[HarnessNode],
    edges: list[HarnessEdge],
) -> list[str] | None:
    """
    Detect a cycle in the directed graph described by *nodes* and *edges*.

    Traverses outbound edges per node using BFS.  If a cycle is found,
    returns the cycle path as a list of node_ids (first == last).
    Returns None when the graph is acyclic.

    Self-loops (source.node_id == target.node_id) are detected first so
    the returned path is always a well-formed cycle (e.g. ["A", "A"]).

    Parameters
    ----------
    nodes:
        All nodes in the harness.  Only their ids are used to build the
        canonical node set.
    edges:
        All directed edges.  Each edge contributes one arc
        source.node_id → target.node_id to the adjacency graph.

    Returns
    -------
    list[str] | None
        Cycle path (node_ids, first repeated at end) or None.
    """
    # Build adjacency list: node_id -> list of successor node_ids.
    # Parallel edges (A→B appearing twice) are fine — we just add two entries
    # to the adjacency list, which the BFS deduplicates via *came_from*.
    node_ids: set[str] = {n.id for n in nodes}
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}

    for edge in edges:
        src = edge.source.node_id
        tgt = edge.target.node_id
        # Self-loop: immediately return a two-element cycle path.
        if src == tgt:
            return [src, src]
        # Only add arcs whose endpoints are known nodes (R3/R4 is enforced by
        # the Pydantic model_validator before we get here).
        if src in adj:
            adj[src].append(tgt)

    # BFS cycle detection: for each unvisited node, try to reach it again
    # by following outbound edges.  We run a separate BFS per start node
    # to produce a clean, minimal cycle path — mirroring _dep_cycle_path.
    globally_visited: set[str] = set()

    for start_id in node_ids:
        if start_id in globally_visited:
            continue

        # BFS state: came_from maps node_id -> predecessor in BFS tree.
        came_from: dict[str, str | None] = {start_id: None}
        queue: deque[str] = deque([start_id])

        while queue:
            current = queue.popleft()
            for successor in adj.get(current, []):
                if successor == start_id:
                    # Found a path back to start_id — reconstruct cycle.
                    path = [start_id]
                    curr: str | None = current
                    while curr is not None:
                        path.append(curr)
                        curr = came_from.get(curr)
                    path.append(start_id)
                    path.reverse()
                    return path
                if successor not in came_from:
                    came_from[successor] = current
                    queue.append(successor)

        # Mark all nodes reachable from start_id as globally visited so we
        # don't re-explore them as start nodes (avoids redundant BFS passes).
        globally_visited.update(came_from.keys())

    return None


def _validate_wait_nodes(harness: Harness) -> None:
    """
    Enforce R6: every human Wait node must supply ``max_wait_seconds`` in its
    ``data`` dict.

    Parameters
    ----------
    harness:
        The harness to inspect.

    Raises
    ------
    HarnessValidationError
        If any human Wait node is missing ``max_wait_seconds``.  The error
        message includes the offending node id and the exact field name so
        operators can fix the harness definition quickly.
    """
    for node in harness.nodes:
        if node.type is NodeType.wait and node.data.get("mode") == "human":
            if "max_wait_seconds" not in node.data:
                raise HarnessValidationError(
                    f"node '{node.id}': human Wait node requires 'max_wait_seconds'"
                    " in data (R6 guardrail — prevents indefinite WAITING park)"
                )


def validate_graph(harness: Harness) -> None:
    """
    Validate the structural integrity of *harness*.

    Currently checks:
      - R5: the edge graph is a DAG (no cycles, no self-loops).
      - R6: human Wait nodes supply ``max_wait_seconds``.

    Raises
    ------
    HarnessGraphError
        If a self-loop or cycle is found.  The error message includes the
        cycle path (node_ids joined by " -> ") for actionable diagnostics.
    HarnessValidationError
        If a structural rule other than R5 is violated (e.g. R6 missing
        ``max_wait_seconds`` on a human Wait node).
    """
    _validate_wait_nodes(harness)
    cycle = find_cycle(harness.nodes, harness.edges)
    if cycle is not None:
        path_str = " -> ".join(cycle)
        raise HarnessGraphError(
            f"harness '{harness.name}' contains a cycle: {path_str}"
        )
