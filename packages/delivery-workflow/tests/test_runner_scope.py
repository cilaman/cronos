"""Tests for runner/scope.py (I3)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from runner.scope import build_scope
from state_types import BudgetState, NodeState, WorkflowState


def _state(*node_pairs: tuple[str, NodeState]) -> WorkflowState:
    """Construct a minimal WorkflowState with the given node pairs."""
    return WorkflowState(
        spec="test",
        run_id="r1",
        status="running",
        budget=BudgetState(usd_ceiling=10.0),
        nodes=dict(node_pairs),
    )


class TestBuildScope:
    def test_empty_state_returns_empty(self):
        state = _state()
        scope = build_scope(state)
        assert scope == {}

    def test_only_done_nodes_appear(self):
        state = _state(
            ("done_node", NodeState(status="done")),
            ("pending_node", NodeState(status="pending")),
            ("failed_node", NodeState(status="failed")),
        )
        scope = build_scope(state)
        assert "done_node.status" in scope
        assert "pending_node.status" not in scope
        assert "failed_node.status" not in scope

    def test_status_key_format(self):
        state = _state(("my_node", NodeState(status="done")))
        scope = build_scope(state)
        assert scope["my_node.status"] == "done"

    def test_gate_decision_key(self):
        ns = NodeState(status="done", gate={"decision": "proceed", "errors": []})
        state = _state(("g-review", ns))
        scope = build_scope(state)
        assert scope["g-review.decision"] == "proceed"

    def test_gate_no_decision_key_absent(self):
        ns = NodeState(status="done", gate={"errors": []})  # no decision
        state = _state(("g-review", ns))
        scope = build_scope(state)
        assert "g-review.decision" not in scope

    def test_fields_emitted(self):
        ns = NodeState(status="done", fields={"verdict": "pass", "count": "3"})
        state = _state(("review", ns))
        scope = build_scope(state)
        assert scope["review.fields.verdict"] == "pass"
        assert scope["review.fields.count"] == "3"

    def test_fields_non_string_coerced(self):
        ns = NodeState(status="done", fields={"count": 42, "flag": True})
        state = _state(("n", ns))
        scope = build_scope(state)
        assert scope["n.fields.count"] == "42"
        assert scope["n.fields.flag"] == "True"

    def test_scope_base_merged(self):
        state = _state()
        base = {"env": "prod", "version": "1.0"}
        scope = build_scope(state, scope_base=base)
        assert scope["env"] == "prod"

    def test_node_output_overrides_scope_base(self):
        ns = NodeState(status="done", fields={"env": "staging"})
        state = _state(("n", ns))
        scope = build_scope(state, scope_base={"env": "prod"})
        # node field takes precedence.
        assert scope["n.fields.env"] == "staging"
        # base variable still present under its original key.
        assert scope["env"] == "prod"

    def test_rebuild_from_scratch_after_back_edge_reset(self):
        """After a back-edge reset, stale fields should not appear."""
        # Initial state: review node has fields from a previous attempt.
        ns_before = NodeState(
            status="done",
            fields={"verdict": "needs_fix"},
        )
        state = _state(("review", ns_before))
        scope1 = build_scope(state)
        assert scope1["review.fields.verdict"] == "needs_fix"

        # Simulate back-edge reset: clear fields.
        ns_before.fields = {}
        ns_before.status = "pending"
        scope2 = build_scope(state)
        # After reset, the review node is pending — should not appear in scope.
        assert "review.fields.verdict" not in scope2

    def test_multiple_done_nodes(self):
        state = _state(
            ("scout", NodeState(status="done", fields={"produces": "research"})),
            ("g-scout", NodeState(status="done", gate={"decision": "proceed"})),
        )
        scope = build_scope(state)
        assert scope["scout.status"] == "done"
        assert scope["g-scout.decision"] == "proceed"
        assert scope["scout.fields.produces"] == "research"

    def test_resume_after_back_edge_clears_stale_scope(self):
        """Design risk mitigation test: stale outputs must not survive a back-edge."""
        # First pass: review was done with verdict=needs_fix.
        review_ns = NodeState(status="done", fields={"verdict": "needs_fix"})
        state = _state(("review", review_ns))
        scope = build_scope(state)
        assert scope["review.fields.verdict"] == "needs_fix"

        # Back-edge fires: reset review node.
        review_ns.status = "pending"
        review_ns.fields = {}

        # Second pass scope must NOT see the old verdict.
        scope2 = build_scope(state)
        assert "review.fields.verdict" not in scope2
