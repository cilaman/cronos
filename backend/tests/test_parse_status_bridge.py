"""Sentinel Bridge tests (R7 + R8) — parse_status 4-tier precedence.

Covers:
- 5 vocab values × 2 bridge tiers (node_status + delivery_status) → R1/R2
- 4-tier precedence chain with all signals present → R3
- needs_fix dual-branch (is_runner_task) → R4
- is_runner_task=False default, keyword-only signature → R5
- context (summary) wiring for tiers 1/3 → R6
- R5 deprecation-warning preservation
- R8 finalizer-path integration simulation
- malformed-JSON fall-through for both bridge tiers
- no-signal returns (None, None)
"""
from __future__ import annotations

import logging

import pytest

from app.agent import Status, parse_status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node_status(status: str, summary: str | None = None) -> str:
    payload = f'{{"status": "{status}"}}'
    if summary is not None:
        payload = f'{{"status": "{status}", "summary": "{summary}"}}'
    return f"```node_status\n{payload}\n```"


def _delivery_status(status: str, summary: str | None = None) -> str:
    payload = f'{{"status": "{status}"}}'
    if summary is not None:
        payload = f'{{"status": "{status}", "summary": "{summary}"}}'
    return f"```delivery_status\n{payload}\n```"


def _cronos_status(status: str, summary: str | None = None) -> str:
    payload = f'{{"status": "{status}"}}'
    if summary is not None:
        payload = f'{{"status": "{status}", "summary": "{summary}"}}'
    return f"```cronos_status\n{payload}\n```"


# ---------------------------------------------------------------------------
# R2: node_status tier (tier 1) — 5 vocab values
# ---------------------------------------------------------------------------


class TestNodeStatusTier:
    def test_done_maps_to_done(self) -> None:
        status, ctx = parse_status(_node_status("done"))
        assert status == Status.DONE

    def test_done_uppercase_maps_to_done(self) -> None:
        status, ctx = parse_status(_node_status("DONE"))
        assert status == Status.DONE

    def test_wait_maps_to_wait(self) -> None:
        status, ctx = parse_status(_node_status("wait"))
        assert status == Status.WAIT

    def test_blocked_maps_to_blocked(self) -> None:
        status, ctx = parse_status(_node_status("blocked"))
        assert status == Status.BLOCKED

    def test_failed_maps_to_blocked(self) -> None:
        status, ctx = parse_status(_node_status("failed"))
        assert status == Status.BLOCKED

    def test_needs_fix_default_maps_to_blocked(self) -> None:
        status, ctx = parse_status(_node_status("needs_fix"))
        assert status == Status.BLOCKED

    def test_needs_fix_runner_maps_to_done(self) -> None:
        status, ctx = parse_status(_node_status("needs_fix"), is_runner_task=True)
        assert status == Status.DONE

    def test_unknown_vocab_falls_through_to_tier4(self) -> None:
        text = _node_status("custom_value") + "\nSTATUS: DONE"
        status, ctx = parse_status(text)
        assert status == Status.DONE

    def test_summary_wired_as_context(self) -> None:
        status, ctx = parse_status(_node_status("done", "node finished ok"))
        assert status == Status.DONE
        assert ctx == "node finished ok"

    def test_summary_none_when_absent(self) -> None:
        status, ctx = parse_status(_node_status("done"))
        assert ctx is None

    def test_malformed_json_falls_through(self) -> None:
        text = "```node_status\n{bad json\n```\n" + _cronos_status("DONE", "cronos wins")
        status, ctx = parse_status(text)
        assert status == Status.DONE
        assert ctx == "cronos wins"


# ---------------------------------------------------------------------------
# R1: delivery_status tier (tier 3) — 5 vocab values
# ---------------------------------------------------------------------------


class TestDeliveryStatusTier:
    def test_done_maps_to_done(self) -> None:
        status, ctx = parse_status(_delivery_status("done"))
        assert status == Status.DONE

    def test_done_uppercase_maps_to_done(self) -> None:
        status, ctx = parse_status(_delivery_status("DONE"))
        assert status == Status.DONE

    def test_wait_maps_to_wait(self) -> None:
        status, ctx = parse_status(_delivery_status("wait"))
        assert status == Status.WAIT

    def test_blocked_maps_to_blocked(self) -> None:
        status, ctx = parse_status(_delivery_status("blocked"))
        assert status == Status.BLOCKED

    def test_failed_maps_to_blocked(self) -> None:
        status, ctx = parse_status(_delivery_status("failed"))
        assert status == Status.BLOCKED

    def test_needs_fix_default_maps_to_blocked(self) -> None:
        status, ctx = parse_status(_delivery_status("needs_fix"))
        assert status == Status.BLOCKED

    def test_needs_fix_runner_maps_to_done(self) -> None:
        status, ctx = parse_status(_delivery_status("needs_fix"), is_runner_task=True)
        assert status == Status.DONE

    def test_unknown_vocab_falls_through_to_tier4(self) -> None:
        text = _delivery_status("custom_value") + "\nSTATUS: DONE"
        status, ctx = parse_status(text)
        assert status == Status.DONE

    def test_summary_wired_as_context(self) -> None:
        status, ctx = parse_status(_delivery_status("done", "delivery finished"))
        assert status == Status.DONE
        assert ctx == "delivery finished"

    def test_summary_none_when_absent(self) -> None:
        status, ctx = parse_status(_delivery_status("done"))
        assert ctx is None

    def test_malformed_json_falls_through(self) -> None:
        text = "```delivery_status\n{bad json\n```\nSTATUS: DONE"
        status, ctx = parse_status(text)
        assert status == Status.DONE


# ---------------------------------------------------------------------------
# R3: 4-tier precedence chain — first non-None Status wins
# ---------------------------------------------------------------------------


class TestTierPrecedence:
    def test_node_status_beats_all_others(self) -> None:
        text = (
            _node_status("done", "node wins")
            + "\n"
            + _cronos_status("WAIT", "cronos loses")
            + "\n"
            + _delivery_status("blocked", "delivery loses")
            + "\nSTATUS: WAIT"
        )
        status, ctx = parse_status(text)
        assert status == Status.DONE
        assert ctx == "node wins"

    def test_cronos_status_beats_delivery_and_free_text(self) -> None:
        # No node_status block, so tier 2 wins
        text = (
            _cronos_status("WAIT", "cronos wins")
            + "\n"
            + _delivery_status("done", "delivery loses")
            + "\nSTATUS: DONE"
        )
        status, ctx = parse_status(text)
        assert status == Status.WAIT
        assert ctx == "cronos wins"

    def test_delivery_status_beats_free_text(self) -> None:
        # No node_status or cronos_status
        text = _delivery_status("blocked", "delivery wins") + "\nSTATUS: DONE"
        status, ctx = parse_status(text)
        assert status == Status.BLOCKED
        assert ctx == "delivery wins"

    def test_free_text_is_last_resort(self) -> None:
        # No structured blocks at all
        text = "Some output\nSTATUS: WAIT"
        status, _ = parse_status(text)
        assert status == Status.WAIT

    def test_node_status_unknown_vocab_skips_to_tier2(self) -> None:
        # node_status has unknown vocab → tier 1 skips → tier 2 wins
        text = _node_status("custom") + "\n" + _cronos_status("BLOCKED", "tier2 wins")
        status, ctx = parse_status(text)
        assert status == Status.BLOCKED
        assert ctx == "tier2 wins"

    def test_node_status_malformed_skips_to_tier2(self) -> None:
        text = "```node_status\n{broken\n```\n" + _cronos_status("DONE", "cronos wins")
        status, ctx = parse_status(text)
        assert status == Status.DONE
        assert ctx == "cronos wins"

    def test_node_status_beats_delivery_status_without_cronos(self) -> None:
        # I3 coexistence: tier-1 (node_status) wins over tier-3 (delivery_status)
        # even when tier-2 (cronos_status) is absent.
        text = (
            _node_status("blocked", "node blocked")
            + "\n"
            + _delivery_status("done", "delivery done")
        )
        status, ctx = parse_status(text)
        assert status == Status.BLOCKED
        assert ctx == "node blocked"

    def test_delivery_status_active_when_no_node_status(self) -> None:
        # I3 coexistence: when node_status is absent, tier-3 delivery_status applies.
        text = _delivery_status("done", "delivery wins")
        status, ctx = parse_status(text)
        assert status == Status.DONE
        assert ctx == "delivery wins"


# ---------------------------------------------------------------------------
# R4: needs_fix dual-branch
# ---------------------------------------------------------------------------


class TestNeedsFixMapping:
    def test_is_runner_task_false_default_node_status(self) -> None:
        status, _ = parse_status(_node_status("needs_fix"))
        assert status == Status.BLOCKED

    def test_is_runner_task_true_node_status(self) -> None:
        status, _ = parse_status(_node_status("needs_fix"), is_runner_task=True)
        assert status == Status.DONE

    def test_is_runner_task_false_default_delivery_status(self) -> None:
        status, _ = parse_status(_delivery_status("needs_fix"))
        assert status == Status.BLOCKED

    def test_is_runner_task_true_delivery_status(self) -> None:
        status, _ = parse_status(_delivery_status("needs_fix"), is_runner_task=True)
        assert status == Status.DONE


# ---------------------------------------------------------------------------
# R5: backward compat — keyword-only signature, existing callers unaffected
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_positional_arg_still_works(self) -> None:
        # parse_status(text) — no keyword arg, should not break
        text = _cronos_status("DONE", "ok")
        status, ctx = parse_status(text)
        assert status == Status.DONE

    def test_is_runner_task_is_keyword_only(self) -> None:
        # Passing is_runner_task as positional should raise TypeError
        with pytest.raises(TypeError):
            parse_status(_node_status("done"), True)  # type: ignore[call-arg]

    def test_existing_cronos_status_callers_unaffected(self) -> None:
        # Simulate existing finalizer / run_executor call sites (positional only)
        text = _cronos_status("BLOCKED", "unresolved dependency")
        status, ctx = parse_status(text)
        assert status == Status.BLOCKED
        assert ctx == "unresolved dependency"

    def test_deprecation_warning_still_fires_for_free_text(self) -> None:
        # Deprecation warning is emitted via log.warning (not Python warnings.warn).
        # The actual log assertion lives in test_free_text_status_emits_log_warning.
        # This test just confirms the function continues to return a result.
        text = "doing work\nSTATUS: DONE"
        status, ctx = parse_status(text)
        assert status == Status.DONE


# ---------------------------------------------------------------------------
# R5: deprecation warning emitted via log.warning
# ---------------------------------------------------------------------------


def test_free_text_status_emits_log_warning(caplog: pytest.LogCaptureFixture) -> None:
    text = "doing work\nSTATUS: DONE"
    with caplog.at_level(logging.WARNING, logger="cronos.agent"):
        parse_status(text)
    assert any("deprecated" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# No-signal cases
# ---------------------------------------------------------------------------


def test_no_signal_returns_none_none() -> None:
    assert parse_status("") == (None, None)
    assert parse_status(None) == (None, None)  # type: ignore[arg-type]
    assert parse_status("nothing here at all") == (None, None)


# ---------------------------------------------------------------------------
# R8: finalizer-path integration simulation
# ---------------------------------------------------------------------------


class TestFinalizerIntegration:
    """Simulate finalizer / run_executor call-site behavior after the bridge.

    These tests reproduce the bug #2 scenario: a Delivery/v2 agent emits
    delivery_status:done or node_status:done and the Cronos worker must see
    Status.DONE (not WAITING / None).
    """

    def test_delivery_status_done_resolves_to_done(self) -> None:
        """Bug #2 regression: delivery_status:done must NOT parse as WAITING."""
        agent_output = (
            "Reviewed the PR and found no issues.\n\n"
            "```delivery_status\n"
            '{"status": "done", "summary": "review passed"}\n'
            "```"
        )
        status, ctx = parse_status(agent_output)
        assert status == Status.DONE
        assert ctx == "review passed"

    def test_node_status_done_resolves_to_done(self) -> None:
        """Bug #2 variant: node_status:done must also resolve to DONE."""
        agent_output = (
            "Node execution completed successfully.\n\n"
            "```node_status\n"
            '{"status": "done", "summary": "all tasks completed"}\n'
            "```"
        )
        status, ctx = parse_status(agent_output)
        assert status == Status.DONE
        assert ctx == "all tasks completed"

    def test_delivery_status_done_with_cronos_status_absent(self) -> None:
        """No cronos_status block — delivery_status must be the signal source."""
        agent_output = (
            "```delivery_status\n"
            '{"status": "done"}\n'
            "```\n\n"
            "All work is complete."
        )
        status, ctx = parse_status(agent_output)
        assert status == Status.DONE

    def test_node_status_wait_routes_to_wait(self) -> None:
        agent_output = (
            "Waiting for external approval.\n\n"
            "```node_status\n"
            '{"status": "wait", "summary": "need sign-off"}\n'
            "```"
        )
        status, ctx = parse_status(agent_output)
        assert status == Status.WAIT
        assert ctx == "need sign-off"

    def test_delivery_status_failed_routes_to_blocked(self) -> None:
        agent_output = (
            "```delivery_status\n"
            '{"status": "failed", "summary": "security scan error"}\n'
            "```"
        )
        status, ctx = parse_status(agent_output)
        assert status == Status.BLOCKED
        assert ctx == "security scan error"
