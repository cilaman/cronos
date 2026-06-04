"""
Tests for trigger-node validation in backend/app/harnesses/validator.py

Covers R7 rules enforced by _validate_trigger_nodes() and the pure helper
_apply_trigger_defaults():

  - Valid webhook trigger node (with webhook_path + auth_token) passes
  - Valid file-change trigger node (with watch_pattern) passes; default
    debounce_seconds is applied in the merged dict
  - Valid task-state-change trigger node passes; default watched_state applied
  - Invalid webhook trigger (missing webhook_path) → HarnessValidationError
  - Invalid webhook trigger (missing auth_token) → HarnessValidationError
  - Invalid file-change trigger (missing watch_pattern) → HarnessValidationError
  - Defaults are applied without mutating the input dict (_apply_trigger_defaults
    is a pure function)
  - Unknown trigger kind → HarnessValidationError
  - Non-trigger nodes with a ``kind`` key in data are ignored
  - Cron trigger nodes (no ``kind`` field in data) are ignored by R7 check
  - validate_graph() calls _validate_trigger_nodes() (integration smoke test)
"""

import pytest

from app.harnesses.model import (
    Harness,
    HarnessEdge,
    HarnessNode,
    NodeRef,
    NodeType,
    Position,
)
from app.harnesses.validator import (
    HarnessValidationError,
    _apply_trigger_defaults,
    _validate_trigger_nodes,
    validate_graph,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trigger_node(nid: str, data: dict) -> HarnessNode:
    """Build a minimal trigger HarnessNode with the given data dict."""
    return HarnessNode(
        id=nid,
        type=NodeType.trigger,
        position=Position(x=0.0, y=0.0),
        data=data,
    )


def _agent_node(nid: str, data: dict | None = None) -> HarnessNode:
    """Build a minimal agent HarnessNode."""
    return HarnessNode(
        id=nid,
        type=NodeType.agent,
        position=Position(x=0.0, y=0.0),
        data=data or {},
    )


def _harness_with_nodes(*nodes: HarnessNode) -> Harness:
    """Build a Harness containing the given nodes and no edges."""
    return Harness(name="test-harness", nodes=list(nodes), edges=[])


# ---------------------------------------------------------------------------
# Tests for _apply_trigger_defaults() — pure helper, no mutation
# ---------------------------------------------------------------------------

class TestApplyTriggerDefaults:
    """Unit tests for the pure _apply_trigger_defaults() helper."""

    def test_file_change_adds_debounce_seconds_when_absent(self):
        original = {"kind": "file-change", "watch_pattern": "*.md"}
        merged = _apply_trigger_defaults("file-change", original)
        assert merged["debounce_seconds"] == 0.5

    def test_file_change_does_not_override_explicit_debounce_seconds(self):
        original = {"kind": "file-change", "watch_pattern": "*.md", "debounce_seconds": 2.0}
        merged = _apply_trigger_defaults("file-change", original)
        assert merged["debounce_seconds"] == 2.0

    def test_task_state_change_adds_watched_state_when_absent(self):
        original = {"kind": "task-state-change"}
        merged = _apply_trigger_defaults("task-state-change", original)
        assert merged["watched_state"] == "DONE"

    def test_task_state_change_does_not_override_explicit_watched_state(self):
        original = {"kind": "task-state-change", "watched_state": "ACTIVE"}
        merged = _apply_trigger_defaults("task-state-change", original)
        assert merged["watched_state"] == "ACTIVE"

    def test_webhook_has_no_defaults(self):
        original = {"kind": "webhook", "webhook_path": "/hook", "auth_token": "secret123456789"}
        merged = _apply_trigger_defaults("webhook", original)
        # Merged dict must equal original — no extra keys injected
        assert merged == original

    def test_does_not_mutate_input_dict(self):
        """_apply_trigger_defaults must be a pure function — no in-place mutation."""
        original = {"kind": "file-change", "watch_pattern": "**/*.md"}
        original_copy = dict(original)
        _apply_trigger_defaults("file-change", original)
        assert original == original_copy, (
            "_apply_trigger_defaults mutated the caller's data dict"
        )

    def test_does_not_mutate_input_dict_task_state_change(self):
        original = {"kind": "task-state-change"}
        original_copy = dict(original)
        _apply_trigger_defaults("task-state-change", original)
        assert original == original_copy, (
            "_apply_trigger_defaults mutated the caller's data dict"
        )

    def test_unknown_kind_returns_shallow_copy_of_data(self):
        original = {"kind": "future-kind", "foo": "bar"}
        merged = _apply_trigger_defaults("future-kind", original)
        assert merged == original
        # Must be a distinct object (copy, not same reference)
        assert merged is not original


# ---------------------------------------------------------------------------
# Tests for _validate_trigger_nodes() — per-kind field rules
# ---------------------------------------------------------------------------

class TestValidateTriggerNodes:
    """Direct unit tests for the _validate_trigger_nodes() private helper."""

    # ---- webhook -----------------------------------------------------------

    def test_valid_webhook_trigger_passes(self):
        node = _trigger_node("t1", {
            "kind": "webhook",
            "webhook_path": "/api/hook/my-harness",
            "auth_token": "supersecrettoken1234",
        })
        harness = _harness_with_nodes(node)
        # Must not raise
        _validate_trigger_nodes(harness)

    def test_webhook_missing_webhook_path_raises(self):
        node = _trigger_node("t1", {
            "kind": "webhook",
            "auth_token": "supersecrettoken1234",
        })
        harness = _harness_with_nodes(node)
        with pytest.raises(HarnessValidationError, match="webhook_path"):
            _validate_trigger_nodes(harness)

    def test_webhook_missing_auth_token_raises(self):
        node = _trigger_node("t1", {
            "kind": "webhook",
            "webhook_path": "/api/hook/my-harness",
        })
        harness = _harness_with_nodes(node)
        with pytest.raises(HarnessValidationError, match="auth_token"):
            _validate_trigger_nodes(harness)

    def test_webhook_missing_both_required_fields_raises(self):
        node = _trigger_node("t1", {"kind": "webhook"})
        harness = _harness_with_nodes(node)
        with pytest.raises(HarnessValidationError):
            _validate_trigger_nodes(harness)

    def test_webhook_error_message_includes_node_id(self):
        node = _trigger_node("webhook-node-42", {
            "kind": "webhook",
            "auth_token": "supersecrettoken1234",
            # missing webhook_path
        })
        harness = _harness_with_nodes(node)
        with pytest.raises(HarnessValidationError, match="webhook-node-42"):
            _validate_trigger_nodes(harness)

    # ---- file-change -------------------------------------------------------

    def test_valid_file_change_trigger_passes(self):
        node = _trigger_node("t2", {
            "kind": "file-change",
            "watch_pattern": ".cronos/tasks/*.md",
        })
        harness = _harness_with_nodes(node)
        _validate_trigger_nodes(harness)

    def test_file_change_missing_watch_pattern_raises(self):
        node = _trigger_node("t2", {"kind": "file-change"})
        harness = _harness_with_nodes(node)
        with pytest.raises(HarnessValidationError, match="watch_pattern"):
            _validate_trigger_nodes(harness)

    def test_file_change_error_message_includes_node_id(self):
        node = _trigger_node("file-watch-node-7", {"kind": "file-change"})
        harness = _harness_with_nodes(node)
        with pytest.raises(HarnessValidationError, match="file-watch-node-7"):
            _validate_trigger_nodes(harness)

    # ---- task-state-change -------------------------------------------------

    def test_valid_task_state_change_trigger_passes(self):
        node = _trigger_node("t3", {"kind": "task-state-change"})
        harness = _harness_with_nodes(node)
        _validate_trigger_nodes(harness)

    def test_task_state_change_with_explicit_watched_state_passes(self):
        node = _trigger_node("t3", {
            "kind": "task-state-change",
            "watched_state": "ACTIVE",
        })
        harness = _harness_with_nodes(node)
        _validate_trigger_nodes(harness)

    # ---- unknown kind ------------------------------------------------------

    def test_unknown_kind_raises(self):
        node = _trigger_node("t4", {"kind": "never-seen-before"})
        harness = _harness_with_nodes(node)
        with pytest.raises(HarnessValidationError, match="never-seen-before"):
            _validate_trigger_nodes(harness)

    # ---- non-trigger nodes are ignored -------------------------------------

    def test_agent_node_with_kind_field_is_ignored(self):
        """A non-trigger node with a ``kind`` key in data must not be validated."""
        node = _agent_node("a1", data={"kind": "webhook"})  # agent, not trigger
        harness = _harness_with_nodes(node)
        # Must not raise even though agent node has no webhook_path / auth_token
        _validate_trigger_nodes(harness)

    # ---- cron trigger nodes (no kind field) are ignored --------------------

    def test_cron_trigger_without_kind_field_is_ignored(self):
        """Legacy cron triggers have no ``kind``; R7 must leave them alone."""
        node = _trigger_node("cron1", {
            "expression": "0 * * * *",
            "timezone": "UTC",
        })
        harness = _harness_with_nodes(node)
        # Must not raise
        _validate_trigger_nodes(harness)

    # ---- multiple trigger nodes --------------------------------------------

    def test_multiple_valid_trigger_nodes_pass(self):
        n1 = _trigger_node("wh", {"kind": "webhook", "webhook_path": "/h", "auth_token": "tok_abcdef1234567"})
        n2 = _trigger_node("fc", {"kind": "file-change", "watch_pattern": "*.md"})
        n3 = _trigger_node("ts", {"kind": "task-state-change"})
        harness = _harness_with_nodes(n1, n2, n3)
        _validate_trigger_nodes(harness)

    def test_first_invalid_trigger_among_many_raises(self):
        valid = _trigger_node("fc", {"kind": "file-change", "watch_pattern": "*.md"})
        invalid = _trigger_node("wh", {"kind": "webhook", "auth_token": "tok"})  # missing webhook_path
        harness = _harness_with_nodes(valid, invalid)
        with pytest.raises(HarnessValidationError, match="webhook_path"):
            _validate_trigger_nodes(harness)


# ---------------------------------------------------------------------------
# Integration: validate_graph() calls _validate_trigger_nodes()
# ---------------------------------------------------------------------------

class TestValidateGraphTriggerIntegration:
    """Smoke tests confirming validate_graph() enforces R7 alongside R5/R6."""

    def test_valid_harness_with_webhook_trigger_passes(self):
        node = _trigger_node("t1", {
            "kind": "webhook",
            "webhook_path": "/api/hook/x",
            "auth_token": "a-very-long-secret-token",
        })
        harness = _harness_with_nodes(node)
        validate_graph(harness)  # must not raise

    def test_invalid_webhook_trigger_raises_from_validate_graph(self):
        node = _trigger_node("t1", {"kind": "webhook", "auth_token": "secret"})
        harness = _harness_with_nodes(node)
        with pytest.raises(HarnessValidationError, match="webhook_path"):
            validate_graph(harness)

    def test_invalid_file_change_trigger_raises_from_validate_graph(self):
        node = _trigger_node("t1", {"kind": "file-change"})
        harness = _harness_with_nodes(node)
        with pytest.raises(HarnessValidationError, match="watch_pattern"):
            validate_graph(harness)

    def test_defaults_applied_for_file_change_via_apply_trigger_defaults(self):
        """Validate that defaults are accessible via the pure helper even when
        validate_graph() itself does not return them (it only validates)."""
        data = {"kind": "file-change", "watch_pattern": ".cronos/**/*.md"}
        merged = _apply_trigger_defaults("file-change", data)
        assert merged["debounce_seconds"] == 0.5
        # Original dict was not mutated
        assert "debounce_seconds" not in data

    def test_defaults_applied_for_task_state_change_via_apply_trigger_defaults(self):
        data = {"kind": "task-state-change"}
        merged = _apply_trigger_defaults("task-state-change", data)
        assert merged["watched_state"] == "DONE"
        assert "watched_state" not in data
