"""
Tests for backend/app/harnesses/decision.py

Covers:
  - Each signal layer in isolation (status, exit_reason, regex, variable)
  - Layered precedence: Status present AND a regex edge also matches → Status wins
  - Missing-signal fallback for each layer
  - Default edge fallback when no condition matches
  - Variable comparison operators (==, !=, in)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.harnesses.decision import (
    edge_matches,
    evaluate_decision,
    resolve_signal,
)
from app.harnesses.model import HarnessEdge, HarnessNode, NodeRef, NodeType, Position
from app.harnesses.run_state import NodeState
from app.trace_parser import RunTrace


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_trace(
    *,
    exit_reason: str = "done",
    final_text_snippet: str = "",
) -> RunTrace:
    now = _utcnow()
    return RunTrace(
        task_id="t1",
        space_id="s1",
        run_index=0,
        session_id=None,
        model="claude-opus-4",
        mode="one-shot",
        started_at=now,
        ended_at=now,
        duration_seconds=0.0,
        exit_reason=exit_reason,
        final_text_snippet=final_text_snippet,
    )


def _make_edge(
    edge_id: str,
    source_node: str = "n_decision",
    condition: str | None = None,
) -> HarnessEdge:
    return HarnessEdge(
        id=edge_id,
        source=NodeRef(node_id=source_node, port_id="out"),
        target=NodeRef(node_id="n_target", port_id="in"),
        condition=condition,
    )


def _make_decision_node(node_id: str = "n_decision") -> HarnessNode:
    return HarnessNode(
        id=node_id,
        type=NodeType.decision,
        position=Position(x=0, y=0),
        ports={"out": {}, "in": {}},
    )


def _make_agent_node(node_id: str = "n_agent") -> HarnessNode:
    return HarnessNode(
        id=node_id,
        type=NodeType.agent,
        position=Position(x=0, y=0),
        ports={"out": {}, "in": {}},
    )


# ---------------------------------------------------------------------------
# resolve_signal tests
# ---------------------------------------------------------------------------


class TestResolveSignalStatus:
    """Layer 1 — STATUS marker in predecessor output."""

    def test_status_extracted_from_done_predecessor(self) -> None:
        ns = NodeState(status="done", output="Some text\nSTATUS: DONE\nmore")
        layer, value = resolve_signal({"agent1": ns}, run_trace=None)
        assert layer == "status"
        assert value == "DONE"

    def test_status_takes_precedence_over_exit_reason(self) -> None:
        ns = NodeState(status="done", output="STATUS: SUCCESS")
        trace = _make_trace(exit_reason="error")
        layer, value = resolve_signal({"agent1": ns}, run_trace=trace)
        assert layer == "status"
        assert value == "SUCCESS"

    def test_status_takes_precedence_over_regex(self) -> None:
        ns = NodeState(status="done", output="STATUS: DONE")
        trace = _make_trace(final_text_snippet="some matching text")
        layer, value = resolve_signal({"agent1": ns}, run_trace=trace)
        assert layer == "status"
        assert value == "DONE"

    def test_status_not_extracted_from_failed_predecessor(self) -> None:
        """Only done predecessors contribute a STATUS signal."""
        ns = NodeState(status="failed", output="STATUS: DONE")
        trace = _make_trace(exit_reason="error", final_text_snippet="")
        layer, value = resolve_signal({"agent1": ns}, run_trace=trace)
        assert layer == "exit_reason"
        assert value == "error"

    def test_status_not_extracted_when_output_is_none(self) -> None:
        ns = NodeState(status="done", output=None)
        trace = _make_trace(exit_reason="done")
        layer, value = resolve_signal({"agent1": ns}, run_trace=trace)
        assert layer == "exit_reason"
        assert value == "done"

    def test_status_not_extracted_when_no_marker(self) -> None:
        ns = NodeState(status="done", output="No status marker here")
        trace = _make_trace(exit_reason="done")
        layer, value = resolve_signal({"agent1": ns}, run_trace=trace)
        assert layer == "exit_reason"
        assert value == "done"

    def test_status_marker_case_sensitive_on_keyword(self) -> None:
        """'status:' (lowercase) is NOT a valid STATUS marker."""
        ns = NodeState(status="done", output="status: done")
        trace = _make_trace(exit_reason="done")
        layer, value = resolve_signal({"agent1": ns}, run_trace=trace)
        assert layer == "exit_reason"  # status layer not triggered

    def test_multiple_predecessors_first_done_with_status_wins(self) -> None:
        """The first done predecessor with a STATUS marker wins."""
        # Python dicts preserve insertion order (3.7+)
        ns_no_status = NodeState(status="done", output="no marker")
        ns_with_status = NodeState(status="done", output="STATUS: PASS")
        layer, value = resolve_signal(
            {"agent1": ns_no_status, "agent2": ns_with_status},
            run_trace=None,
        )
        # agent2 has a STATUS marker → should be found on second iteration
        assert layer == "status"
        assert value == "PASS"


class TestResolveSignalExitReason:
    """Layer 2 — RunTrace.exit_reason."""

    def test_exit_reason_used_when_no_status(self) -> None:
        ns = NodeState(status="done", output="no marker")
        trace = _make_trace(exit_reason="timeout")
        layer, value = resolve_signal({"agent1": ns}, run_trace=trace)
        assert layer == "exit_reason"
        assert value == "timeout"

    def test_exit_reason_used_with_empty_predecessors(self) -> None:
        trace = _make_trace(exit_reason="error")
        layer, value = resolve_signal({}, run_trace=trace)
        assert layer == "exit_reason"
        assert value == "error"

    def test_exit_reason_not_used_when_trace_is_none(self) -> None:
        trace = _make_trace(exit_reason="done", final_text_snippet="hello world")
        # override to None
        layer, value = resolve_signal({}, run_trace=None)
        assert layer == "variable"  # falls through all layers

    def test_exit_reason_empty_string_skips_to_next_layer(self) -> None:
        """An empty exit_reason falls through to the regex layer."""
        trace = _make_trace(exit_reason="", final_text_snippet="match me")
        # Build RunTrace with empty exit_reason
        now = _utcnow()
        trace_empty = RunTrace(
            task_id="t1",
            space_id="s1",
            run_index=0,
            session_id=None,
            model="m",
            mode="one-shot",
            started_at=now,
            ended_at=now,
            duration_seconds=0.0,
            exit_reason="",
            final_text_snippet="match me",
        )
        layer, value = resolve_signal({}, run_trace=trace_empty)
        assert layer == "regex"
        assert value == "match me"


class TestResolveSignalRegex:
    """Layer 3 — RunTrace.final_text_snippet."""

    def test_regex_layer_used_when_no_status_no_exit_reason(self) -> None:
        now = _utcnow()
        trace = RunTrace(
            task_id="t1",
            space_id="s1",
            run_index=0,
            session_id=None,
            model="m",
            mode="one-shot",
            started_at=now,
            ended_at=now,
            duration_seconds=0.0,
            exit_reason="",
            final_text_snippet="Task completed successfully",
        )
        layer, value = resolve_signal({}, run_trace=trace)
        assert layer == "regex"
        assert "completed" in value

    def test_regex_layer_skipped_when_snippet_empty(self) -> None:
        now = _utcnow()
        trace = RunTrace(
            task_id="t1",
            space_id="s1",
            run_index=0,
            session_id=None,
            model="m",
            mode="one-shot",
            started_at=now,
            ended_at=now,
            duration_seconds=0.0,
            exit_reason="",
            final_text_snippet="",
        )
        layer, value = resolve_signal({}, run_trace=trace)
        assert layer == "variable"


class TestResolveSignalVariable:
    """Layer 4 — scope variable fallback."""

    def test_variable_layer_returned_when_nothing_else_available(self) -> None:
        layer, value = resolve_signal({}, run_trace=None)
        assert layer == "variable"
        assert value is None


# ---------------------------------------------------------------------------
# edge_matches tests
# ---------------------------------------------------------------------------


class TestEdgeMatchesStatus:
    """Status layer — case-sensitive exact match."""

    def test_exact_match(self) -> None:
        edge = _make_edge("e1", condition="DONE")
        assert edge_matches(edge, ("status", "DONE"), {}) is True

    def test_no_match_different_case(self) -> None:
        edge = _make_edge("e1", condition="done")
        assert edge_matches(edge, ("status", "DONE"), {}) is False

    def test_no_match_different_value(self) -> None:
        edge = _make_edge("e1", condition="SUCCESS")
        assert edge_matches(edge, ("status", "DONE"), {}) is False

    def test_default_edge_never_matches(self) -> None:
        edge = _make_edge("e_default", condition=None)
        assert edge_matches(edge, ("status", "DONE"), {}) is False


class TestEdgeMatchesExitReason:
    """Exit-reason layer — case-sensitive exact match."""

    def test_exact_match(self) -> None:
        edge = _make_edge("e1", condition="timeout")
        assert edge_matches(edge, ("exit_reason", "timeout"), {}) is True

    def test_no_match(self) -> None:
        edge = _make_edge("e1", condition="done")
        assert edge_matches(edge, ("exit_reason", "error"), {}) is False

    def test_case_sensitive(self) -> None:
        edge = _make_edge("e1", condition="Done")
        assert edge_matches(edge, ("exit_reason", "done"), {}) is False


class TestEdgeMatchesRegex:
    """Regex layer — re.search with Python inline flags."""

    def test_simple_pattern_matches(self) -> None:
        edge = _make_edge("e1", condition="completed")
        assert edge_matches(edge, ("regex", "Task completed successfully"), {}) is True

    def test_pattern_no_match(self) -> None:
        edge = _make_edge("e1", condition="failed")
        assert edge_matches(edge, ("regex", "Task completed successfully"), {}) is False

    def test_inline_case_insensitive_flag(self) -> None:
        edge = _make_edge("e1", condition="(?i)success")
        assert edge_matches(edge, ("regex", "Task completed SUCCESSFULLY"), {}) is True

    def test_anchored_pattern(self) -> None:
        edge = _make_edge("e1", condition="^STATUS:")
        assert edge_matches(edge, ("regex", "STATUS: DONE"), {}) is True

    def test_invalid_regex_returns_false(self) -> None:
        edge = _make_edge("e1", condition="[invalid(")
        assert edge_matches(edge, ("regex", "some text"), {}) is False

    def test_empty_snippet_no_match(self) -> None:
        edge = _make_edge("e1", condition="success")
        assert edge_matches(edge, ("regex", ""), {}) is False


class TestEdgeMatchesVariable:
    """Variable layer — whitelisted grammar, no eval."""

    def test_equals_match(self) -> None:
        edge = _make_edge("e1", condition="result == success")
        assert edge_matches(edge, ("variable", None), {"result": "success"}) is True

    def test_equals_no_match(self) -> None:
        edge = _make_edge("e1", condition="result == success")
        assert edge_matches(edge, ("variable", None), {"result": "failure"}) is False

    def test_not_equals_match(self) -> None:
        edge = _make_edge("e1", condition="status != error")
        assert edge_matches(edge, ("variable", None), {"status": "done"}) is True

    def test_not_equals_no_match(self) -> None:
        edge = _make_edge("e1", condition="status != error")
        assert edge_matches(edge, ("variable", None), {"status": "error"}) is False

    def test_in_operator_match(self) -> None:
        edge = _make_edge("e1", condition="color in red,green,blue")
        assert edge_matches(edge, ("variable", None), {"color": "green"}) is True

    def test_in_operator_no_match(self) -> None:
        edge = _make_edge("e1", condition="color in red,green,blue")
        assert edge_matches(edge, ("variable", None), {"color": "yellow"}) is False

    def test_quoted_rhs(self) -> None:
        edge = _make_edge("e1", condition='result == "my value"')
        assert edge_matches(edge, ("variable", None), {"result": "my value"}) is True

    def test_single_quoted_rhs(self) -> None:
        edge = _make_edge("e1", condition="result == 'passed'")
        assert edge_matches(edge, ("variable", None), {"result": "passed"}) is True

    def test_missing_variable_equals_fails(self) -> None:
        edge = _make_edge("e1", condition="result == success")
        # variable not in scope → lhs is None, rhs is "success"
        assert edge_matches(edge, ("variable", None), {}) is False

    def test_missing_variable_not_equals_true(self) -> None:
        """None != 'something' → True (variable is absent, which differs from value)."""
        edge = _make_edge("e1", condition="result != success")
        assert edge_matches(edge, ("variable", None), {}) is True

    def test_invalid_grammar_returns_false(self) -> None:
        edge = _make_edge("e1", condition="result > 5")
        assert edge_matches(edge, ("variable", None), {"result": "10"}) is False


# ---------------------------------------------------------------------------
# evaluate_decision integration tests
# ---------------------------------------------------------------------------


class TestEvaluateDecisionStatusLayer:
    """Decision evaluates STATUS layer correctly."""

    def test_status_match_selects_edge(self) -> None:
        node = _make_decision_node()
        ns = NodeState(status="done", output="STATUS: SUCCESS")
        edges = [
            _make_edge("e_success", condition="SUCCESS"),
            _make_edge("e_fail", condition="FAIL"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {"a": ns}, {}, run_trace=None, outgoing_edges=edges)
        assert chosen == "e_success"

    def test_status_no_match_falls_to_default(self) -> None:
        node = _make_decision_node()
        ns = NodeState(status="done", output="STATUS: UNKNOWN")
        edges = [
            _make_edge("e_success", condition="SUCCESS"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {"a": ns}, {}, run_trace=None, outgoing_edges=edges)
        assert chosen == "e_default"


class TestEvaluateDecisionExitReasonLayer:
    """Decision evaluates exit_reason layer correctly."""

    def test_exit_reason_match_selects_edge(self) -> None:
        node = _make_decision_node()
        ns = NodeState(status="done", output="no STATUS marker")
        trace = _make_trace(exit_reason="timeout")
        edges = [
            _make_edge("e_timeout", condition="timeout"),
            _make_edge("e_done", condition="done"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {"a": ns}, {}, run_trace=trace, outgoing_edges=edges)
        assert chosen == "e_timeout"

    def test_exit_reason_no_match_falls_to_default(self) -> None:
        node = _make_decision_node()
        trace = _make_trace(exit_reason="error")
        edges = [
            _make_edge("e_done", condition="done"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {}, {}, run_trace=trace, outgoing_edges=edges)
        assert chosen == "e_default"


class TestEvaluateDecisionRegexLayer:
    """Decision evaluates regex layer correctly."""

    def test_regex_match_selects_edge(self) -> None:
        node = _make_decision_node()
        now = _utcnow()
        trace = RunTrace(
            task_id="t1",
            space_id="s1",
            run_index=0,
            session_id=None,
            model="m",
            mode="one-shot",
            started_at=now,
            ended_at=now,
            duration_seconds=0.0,
            exit_reason="",
            final_text_snippet="Task completed successfully",
        )
        edges = [
            _make_edge("e_success", condition="completed"),
            _make_edge("e_fail", condition="failed"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {}, {}, run_trace=trace, outgoing_edges=edges)
        assert chosen == "e_success"

    def test_regex_case_insensitive_inline_flag(self) -> None:
        node = _make_decision_node()
        now = _utcnow()
        trace = RunTrace(
            task_id="t1",
            space_id="s1",
            run_index=0,
            session_id=None,
            model="m",
            mode="one-shot",
            started_at=now,
            ended_at=now,
            duration_seconds=0.0,
            exit_reason="",
            final_text_snippet="COMPLETED",
        )
        edges = [
            _make_edge("e_success", condition="(?i)completed"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {}, {}, run_trace=trace, outgoing_edges=edges)
        assert chosen == "e_success"

    def test_regex_no_match_falls_to_default(self) -> None:
        node = _make_decision_node()
        now = _utcnow()
        trace = RunTrace(
            task_id="t1",
            space_id="s1",
            run_index=0,
            session_id=None,
            model="m",
            mode="one-shot",
            started_at=now,
            ended_at=now,
            duration_seconds=0.0,
            exit_reason="",
            final_text_snippet="Nothing relevant here",
        )
        edges = [
            _make_edge("e_success", condition="completed"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {}, {}, run_trace=trace, outgoing_edges=edges)
        assert chosen == "e_default"


class TestEvaluateDecisionVariableLayer:
    """Decision evaluates variable layer correctly."""

    def test_variable_equals_match(self) -> None:
        node = _make_decision_node()
        scope = {"env": "production"}
        edges = [
            _make_edge("e_prod", condition="env == production"),
            _make_edge("e_other", condition="env == staging"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {}, scope, run_trace=None, outgoing_edges=edges)
        assert chosen == "e_prod"

    def test_variable_in_match(self) -> None:
        node = _make_decision_node()
        scope = {"tier": "gold"}
        edges = [
            _make_edge("e_premium", condition="tier in gold,platinum"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {}, scope, run_trace=None, outgoing_edges=edges)
        assert chosen == "e_premium"

    def test_variable_no_match_falls_to_default(self) -> None:
        node = _make_decision_node()
        scope = {"env": "dev"}
        edges = [
            _make_edge("e_prod", condition="env == production"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {}, scope, run_trace=None, outgoing_edges=edges)
        assert chosen == "e_default"


class TestEvaluateDecisionDefaultEdge:
    """Default edge fallback behavior."""

    def test_default_edge_used_when_no_conditions_match(self) -> None:
        node = _make_decision_node()
        edges = [
            _make_edge("e_a", condition="DONE"),
            _make_edge("e_b", condition="FAIL"),
            _make_edge("e_default", condition=None),
        ]
        trace = _make_trace(exit_reason="unknown")
        chosen = evaluate_decision(node, {}, {}, run_trace=trace, outgoing_edges=edges)
        assert chosen == "e_default"

    def test_raises_when_no_default_edge_and_no_match(self) -> None:
        node = _make_decision_node()
        edges = [
            _make_edge("e_done", condition="done"),
        ]
        trace = _make_trace(exit_reason="error")
        with pytest.raises(ValueError, match="no default edge"):
            evaluate_decision(node, {}, {}, run_trace=trace, outgoing_edges=edges)

    def test_only_default_edge_is_used(self) -> None:
        """When only a default edge exists it is always chosen."""
        node = _make_decision_node()
        edges = [_make_edge("e_default", condition=None)]
        chosen = evaluate_decision(node, {}, {}, run_trace=None, outgoing_edges=edges)
        assert chosen == "e_default"


class TestEvaluateDecisionLayerPrecedence:
    """Layered precedence: Status wins over regex when both are present."""

    def test_status_wins_over_regex(self) -> None:
        """STATUS marker present AND a regex condition also matches — Status wins."""
        node = _make_decision_node()
        # predecessor has a STATUS: DONE marker in output
        ns = NodeState(status="done", output="STATUS: DONE\nTask completed successfully")
        # trace has final_text_snippet that matches the regex edge
        trace = _make_trace(
            exit_reason="done",
            final_text_snippet="Task completed successfully",
        )
        edges = [
            # Regex edge that would match the snippet
            _make_edge("e_regex", condition="completed"),
            # Status edge that matches the STATUS marker
            _make_edge("e_status_done", condition="DONE"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {"a": ns}, {}, run_trace=trace, outgoing_edges=edges)
        # Status layer wins → STATUS: DONE → condition "DONE" matches → e_status_done
        assert chosen == "e_status_done"

    def test_exit_reason_wins_over_regex(self) -> None:
        """exit_reason available AND a regex condition would also match — exit_reason wins."""
        node = _make_decision_node()
        trace = _make_trace(exit_reason="error", final_text_snippet="error occurred")
        edges = [
            # Regex edge that would match the snippet
            _make_edge("e_regex", condition="error occurred"),
            # exit_reason exact-match edge
            _make_edge("e_error", condition="error"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {}, {}, run_trace=trace, outgoing_edges=edges)
        # exit_reason layer wins → "error" condition matches → e_error
        assert chosen == "e_error"

    def test_status_wins_over_exit_reason(self) -> None:
        """STATUS marker present — exit_reason layer is never reached."""
        node = _make_decision_node()
        ns = NodeState(status="done", output="STATUS: PASS")
        trace = _make_trace(exit_reason="done")
        edges = [
            _make_edge("e_pass", condition="PASS"),
            _make_edge("e_done", condition="done"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {"a": ns}, {}, run_trace=trace, outgoing_edges=edges)
        # Signal is ("status", "PASS") → matches e_pass, not e_done
        assert chosen == "e_pass"

    def test_missing_status_falls_through_to_exit_reason(self) -> None:
        """No STATUS marker → falls through to exit_reason layer."""
        node = _make_decision_node()
        ns = NodeState(status="done", output="no marker here")
        trace = _make_trace(exit_reason="timeout")
        edges = [
            _make_edge("e_timeout", condition="timeout"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {"a": ns}, {}, run_trace=trace, outgoing_edges=edges)
        assert chosen == "e_timeout"


class TestEvaluateDecisionMissingSignals:
    """Missing-signal behavior for each layer."""

    def test_no_signal_at_all_uses_default(self) -> None:
        """No predecessors, no trace, empty scope → default edge."""
        node = _make_decision_node()
        edges = [
            _make_edge("e_done", condition="done"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {}, {}, run_trace=None, outgoing_edges=edges)
        assert chosen == "e_default"

    def test_status_layer_missing_falls_through(self) -> None:
        """Done predecessor with no STATUS marker → next layer used."""
        node = _make_decision_node()
        ns = NodeState(status="done", output="no STATUS here")
        trace = _make_trace(exit_reason="done")
        edges = [
            _make_edge("e_done", condition="done"),
            _make_edge("e_default", condition=None),
        ]
        chosen = evaluate_decision(node, {"a": ns}, {}, run_trace=trace, outgoing_edges=edges)
        assert chosen == "e_done"

    def test_empty_scope_variable_condition_falls_to_default(self) -> None:
        """Variable condition with missing var → None != rhs → may fall to default."""
        node = _make_decision_node()
        edges = [
            _make_edge("e_match", condition="myvar == expected"),
            _make_edge("e_default", condition=None),
        ]
        # No trace, no predecessors, empty scope → variable layer, myvar is None
        chosen = evaluate_decision(node, {}, {}, run_trace=None, outgoing_edges=edges)
        assert chosen == "e_default"
