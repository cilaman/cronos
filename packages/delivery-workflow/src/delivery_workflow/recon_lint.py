"""
Reference implementation of the R11 edge-condition lint for delivery/v1.

Rule: every root identifier in an edges[].when condition must resolve to a node id
from nodes[*].id. Since recon output has no node id, any attempt to reference it in
an edge condition fails this check.

This module is the reference implementation for G0.3 (spec_loader adoption). The
test in tests/test_recon_edge_lint.py pins the contract so G0.3 can adopt the
behaviour without re-deriving it.
"""

import re


class LintError(ValueError):
    """Raised when an edge condition references an unknown (non-node) identifier."""


def extract_root_identifiers(condition_str: str) -> set:
    """
    Parse a condition string and return the root identifiers (the left side of
    the first dot in each dotted-path expression).

    Examples:
        "g-scout.decision == 'proceed'"         -> {"g-scout"}
        "review.fields.verdict == 'pass'"       -> {"review"}
        "analyze.fields.has_ui == true"         -> {"analyze"}
        "review.fields.verdict == 'needs_fix' && review.fields.finding_class == 'local'"
                                                -> {"review"}

    Strategy: split on && / || operators to get individual clauses, then from each
    clause extract the leading dotted-path root with a re.match (anchored to start).
    This avoids false positives from sub-paths like `fields` in `review.fields.verdict`.
    """
    tokens = set()
    # Split on && and || (with optional surrounding whitespace) to get atomic clauses
    clauses = re.split(r'\s*(?:&&|\|\|)\s*', condition_str)
    for clause in clauses:
        clause = clause.strip()
        # The root identifier is the leftmost dotted-path start of the clause
        m = re.match(r'([A-Za-z][A-Za-z0-9_-]*)\.', clause)
        if m:
            tokens.add(m.group(1))
    return tokens


def lint_edge_conditions(spec: dict) -> None:
    """
    Assert that every root identifier in edges[].when conditions is a known DAG node id.

    Raises LintError on the first unknown identifier found.

    Args:
        spec: A parsed delivery/v1 workflow spec dict with 'nodes' and 'edges' keys.

    Raises:
        LintError: If any edge's when-condition references an identifier that is not
            a node id. Message includes the edge, the unknown token, and a reminder
            that recon output is not a DAG node.
    """
    node_ids = {n["id"] for n in spec.get("nodes", [])}
    for edge in spec.get("edges", []):
        condition = edge.get("when")
        if not condition:
            continue
        for token in extract_root_identifiers(condition):
            if token not in node_ids:
                raise LintError(
                    f"Edge {edge['from']!r}->{edge['to']!r}: unknown identifier "
                    f"{token!r} in when-condition {condition!r}. "
                    f"Recon output is not a DAG node and cannot be referenced in "
                    f"edge conditions. Known node ids: {sorted(node_ids)}"
                )
