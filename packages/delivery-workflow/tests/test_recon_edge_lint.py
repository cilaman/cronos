"""
Tests for the R11 edge-condition lint (recon_lint.py).

Contract:
  - The worked example (spec §12) passes lint_edge_conditions without error.
  - A synthetic edge referencing a hypothetical recon_output node fails with a
    clear LintError that mentions the unknown identifier.
"""

import os
import sys

import pytest

# Ensure packages/delivery-workflow is importable when run from repo root or tests dir
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recon_lint import LintError, extract_root_identifiers, lint_edge_conditions


# ---------------------------------------------------------------------------
# Spec §12 worked example (full node + edge set for lint purposes)
# ---------------------------------------------------------------------------

SPEC_12_NODES = [
    {"id": "scout"},
    {"id": "g-scout"},
    {"id": "analyze"},
    {"id": "g-analysis"},
    {"id": "signoff-scope"},
    {"id": "frontend"},
    {"id": "architect"},
    {"id": "g-design"},
    {"id": "signoff-design"},
    {"id": "testarch"},
    {"id": "implement"},
    {"id": "g-build"},
    {"id": "review"},
    {"id": "g-review"},
    {"id": "testrun"},
    {"id": "g-tests"},
    {"id": "doc"},
    {"id": "g-doc"},
    {"id": "release"},
]

SPEC_12_EDGES = [
    {"from": "scout", "to": "g-scout"},
    {"from": "g-scout", "to": "analyze", "when": "g-scout.decision == 'proceed'"},
    {"from": "analyze", "to": "g-analysis"},
    {"from": "g-analysis", "to": "signoff-scope", "when": "g-analysis.decision == 'proceed'"},
    {"from": "signoff-scope", "to": "frontend", "when": "analyze.fields.has_ui == true"},
    {"from": "signoff-scope", "to": "architect", "when": "analyze.fields.has_ui == false"},
    {"from": "frontend", "to": "architect"},
    {"from": "architect", "to": "g-design"},
    {"from": "g-design", "to": "signoff-design", "when": "g-design.decision == 'proceed'"},
    {"from": "signoff-design", "to": "testarch"},
    {"from": "signoff-design", "to": "implement"},
    {"from": "implement", "to": "g-build"},
    {"from": "g-build", "to": "review", "when": "g-build.decision == 'proceed'"},
    {"from": "review", "to": "g-review"},
    {"from": "g-review", "to": "testrun", "when": "review.fields.verdict == 'pass'"},
    {
        "from": "g-review",
        "to": "implement",
        "when": "review.fields.verdict == 'needs_fix' && review.fields.finding_class == 'local'",
    },
    {
        "from": "g-review",
        "to": "architect",
        "when": "review.fields.verdict == 'needs_fix' && review.fields.finding_class == 'architectural'",
    },
    {"from": "testrun", "to": "g-tests"},
    {"from": "g-tests", "to": "doc", "when": "g-tests.decision == 'proceed'"},
    {"from": "g-tests", "to": "implement", "when": "g-tests.decision == 'needs_fix'"},
    {"from": "doc", "to": "g-doc"},
    {"from": "g-doc", "to": "release", "when": "g-doc.decision == 'proceed'"},
]

SPEC_12 = {"nodes": SPEC_12_NODES, "edges": SPEC_12_EDGES}


# ---------------------------------------------------------------------------
# Unit tests for extract_root_identifiers
# ---------------------------------------------------------------------------


def test_extract_simple_path():
    assert extract_root_identifiers("g-scout.decision == 'proceed'") == {"g-scout"}


def test_extract_nested_path():
    # 'fields' is a sub-path — only the outermost root 'review' is returned
    assert extract_root_identifiers("review.fields.verdict == 'pass'") == {"review"}


def test_extract_compound_condition():
    result = extract_root_identifiers(
        "review.fields.verdict == 'needs_fix' && review.fields.finding_class == 'local'"
    )
    assert result == {"review"}


def test_extract_multiple_roots():
    result = extract_root_identifiers(
        "analyze.fields.has_ui == true || g-analysis.decision == 'proceed'"
    )
    assert result == {"analyze", "g-analysis"}


def test_extract_no_dot_path():
    # A bare value with no dot path returns empty set
    assert extract_root_identifiers("'pass'") == set()


# ---------------------------------------------------------------------------
# Worked example: spec §12 must pass without error
# ---------------------------------------------------------------------------


def test_spec_12_passes():
    """The full §12 worked example passes lint_edge_conditions without raising."""
    lint_edge_conditions(SPEC_12)  # must not raise


# ---------------------------------------------------------------------------
# Synthetic failure: recon_output is not a node id
# ---------------------------------------------------------------------------


def test_recon_output_edge_fails():
    """
    An edge referencing `recon_output` in its when-condition must fail with a
    LintError that names the unknown identifier and states recon is not a DAG node.
    """
    spec_bad = {
        "nodes": [
            {"id": "scout"},
            {"id": "g-scout"},
            {"id": "implement"},
        ],
        "edges": [
            {
                "from": "g-scout",
                "to": "implement",
                "when": "recon_output.summary == 'done'",
            }
        ],
    }
    with pytest.raises(LintError) as exc_info:
        lint_edge_conditions(spec_bad)
    error_msg = str(exc_info.value)
    assert "recon_output" in error_msg
    assert "not a DAG node" in error_msg


def test_unknown_identifier_fails():
    """Any identifier not in nodes[*].id fails the check."""
    spec_bad = {
        "nodes": [{"id": "scout"}, {"id": "g-scout"}],
        "edges": [
            {
                "from": "scout",
                "to": "g-scout",
                "when": "phantom_node.decision == 'proceed'",
            }
        ],
    }
    with pytest.raises(LintError) as exc_info:
        lint_edge_conditions(spec_bad)
    assert "phantom_node" in str(exc_info.value)


def test_edge_without_when_passes():
    """Edges without a when-condition are skipped (no error)."""
    spec = {
        "nodes": [{"id": "scout"}, {"id": "g-scout"}],
        "edges": [{"from": "scout", "to": "g-scout"}],
    }
    lint_edge_conditions(spec)  # must not raise


def test_empty_spec_passes():
    """An empty spec passes without error."""
    lint_edge_conditions({"nodes": [], "edges": []})
