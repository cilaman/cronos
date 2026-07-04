"""Tests for security + g-security nodes wired into delivery.workflow.yaml (REQ-005).

Verifies: both nodes present, loop (max=3, on_exhaust=escalate), the four routing
edges from g-security, rewired g-review→security, no direct g-review→testrun,
agents/security-reviewer.md exists (ties to I1), and canonical workflow validates
clean (ties to I2).
"""
from __future__ import annotations

from pathlib import Path

from delivery_workflow import spec_loader
PACKAGE_ROOT = Path(__file__).parent.parent
SPEC_PATH = PACKAGE_ROOT / "src" / "delivery_workflow" / "delivery.workflow.yaml"


def _loaded() -> dict:
    return spec_loader.load_spec(SPEC_PATH)


# ---------------------------------------------------------------------------
# Node presence
# ---------------------------------------------------------------------------


def test_security_node_present():
    """delivery.workflow.yaml must contain an agent node with id=security."""
    spec = _loaded()
    ids = {n["id"] for n in spec["nodes"]}
    assert "security" in ids, f"security node missing from nodes; found: {ids}"


def test_g_security_node_present():
    """delivery.workflow.yaml must contain a gate node with id=g-security."""
    spec = _loaded()
    ids = {n["id"] for n in spec["nodes"]}
    assert "g-security" in ids, f"g-security node missing from nodes; found: {ids}"


def test_security_node_is_agent_kind():
    spec = _loaded()
    node = next(n for n in spec["nodes"] if n["id"] == "security")
    assert node["kind"] == "agent"
    assert node["agent"] == "security-reviewer"


def test_g_security_node_is_gate_kind():
    spec = _loaded()
    node = next(n for n in spec["nodes"] if n["id"] == "g-security")
    assert node["kind"] == "gate"


# ---------------------------------------------------------------------------
# Loop config (DD-010 / REQ-005 AC2)
# ---------------------------------------------------------------------------


def test_security_loop_max_3():
    spec = _loaded()
    node = next(n for n in spec["nodes"] if n["id"] == "security")
    loop = node.get("loop", {})
    assert loop.get("max") == 3, f"Expected loop.max=3, got {loop.get('max')!r}"


def test_security_loop_on_exhaust_escalate():
    spec = _loaded()
    node = next(n for n in spec["nodes"] if n["id"] == "security")
    loop = node.get("loop", {})
    assert loop.get("on_exhaust") == "escalate", (
        f"Expected loop.on_exhaust=escalate, got {loop.get('on_exhaust')!r}"
    )


def test_security_loop_has_until():
    spec = _loaded()
    node = next(n for n in spec["nodes"] if n["id"] == "security")
    loop = node.get("loop", {})
    assert loop.get("until"), "security loop must have an 'until' condition"


def test_g_security_on_missing_scanner_is_skip():
    """The runtime image ships no semgrep/gitleaks/pip-audit; on_missing_scanner
    must be 'skip' so a missing scanner cannot hard-fail an otherwise-green run
    (it would loop g-security to exhaustion and never reach testrun/doc/release)."""
    spec = _loaded()
    node = next(n for n in spec["nodes"] if n["id"] == "g-security")
    sec_check = next(c for c in node["checks"] if c.get("type") == "security")
    assert sec_check.get("on_missing_scanner") == "skip", (
        "g-security on_missing_scanner must be 'skip' for un-shipped scanners; "
        f"got {sec_check.get('on_missing_scanner')!r}"
    )


# ---------------------------------------------------------------------------
# Routing edges (DD-002 / REQ-005 AC4)
# ---------------------------------------------------------------------------


def _edges(spec: dict) -> list[dict]:
    return spec.get("edges", [])


def test_four_routing_edges_from_g_security():
    """g-security must have exactly 4 outgoing routing edges (proceed + 3 needs_fix)."""
    spec = _loaded()
    g_sec_edges = [e for e in _edges(spec) if e["from"] == "g-security"]
    assert len(g_sec_edges) == 4, (
        f"Expected 4 edges from g-security, got {len(g_sec_edges)}: {g_sec_edges}"
    )


def test_g_security_to_testrun_edge_present():
    spec = _loaded()
    edge = next(
        (e for e in _edges(spec) if e["from"] == "g-security" and e["to"] == "testrun"),
        None,
    )
    assert edge is not None, "Missing edge g-security → testrun"
    assert "proceed" in edge.get("when", ""), (
        f"g-security→testrun edge should have proceed condition; got {edge!r}"
    )


def test_g_security_to_implement_code_edge_present():
    spec = _loaded()
    matching = [
        e for e in _edges(spec)
        if e["from"] == "g-security" and e["to"] == "implement"
        and "finding_class == 'code'" in e.get("when", "")
    ]
    assert matching, "Missing g-security → implement edge for code finding_class"


def test_g_security_to_implement_dependency_edge_present():
    spec = _loaded()
    matching = [
        e for e in _edges(spec)
        if e["from"] == "g-security" and e["to"] == "implement"
        and "finding_class == 'dependency'" in e.get("when", "")
    ]
    assert matching, "Missing g-security → implement edge for dependency finding_class"


def test_g_security_to_architect_design_edge_present():
    spec = _loaded()
    matching = [
        e for e in _edges(spec)
        if e["from"] == "g-security" and e["to"] == "architect"
        and "finding_class == 'design'" in e.get("when", "")
    ]
    assert matching, "Missing g-security → architect edge for design finding_class"


# ---------------------------------------------------------------------------
# Rewired g-review → security (DD-003 / REQ-005 AC3)
# ---------------------------------------------------------------------------


def test_g_review_to_security_edge_present():
    """g-review passes to security, not testrun (after rewire)."""
    spec = _loaded()
    edge = next(
        (e for e in _edges(spec) if e["from"] == "g-review" and e["to"] == "security"),
        None,
    )
    assert edge is not None, "Missing rewired edge g-review → security"


def test_no_direct_g_review_to_testrun_edge():
    """No direct g-review → testrun edge may remain (REQ-005 AC3)."""
    spec = _loaded()
    direct = next(
        (e for e in _edges(spec) if e["from"] == "g-review" and e["to"] == "testrun"),
        None,
    )
    assert direct is None, (
        f"Direct g-review → testrun edge must be removed; found: {direct!r}"
    )


def test_security_to_g_security_connector_present():
    spec = _loaded()
    edge = next(
        (e for e in _edges(spec) if e["from"] == "security" and e["to"] == "g-security"),
        None,
    )
    assert edge is not None, "Missing connector edge security → g-security"


# ---------------------------------------------------------------------------
# I1 tie-in: security-reviewer agent file exists
# ---------------------------------------------------------------------------


def test_security_reviewer_agent_file_exists():
    agent_path = PACKAGE_ROOT / "src" / "delivery_workflow" / "agents" / "security-reviewer.md"
    assert agent_path.exists(), (
        f"agents/security-reviewer.md not found at {agent_path}"
    )


# ---------------------------------------------------------------------------
# I2 tie-in: canonical workflow still validates clean after changes
# ---------------------------------------------------------------------------


def test_canonical_workflow_validates_clean_after_security_wiring():
    """The full delivery.workflow.yaml (now with security nodes) validates clean."""
    spec = spec_loader.load_spec(SPEC_PATH)
    # load_spec raises ValueError on invalid spec; reaching here means it passed
    assert spec["apiVersion"] == "delivery/v1"
