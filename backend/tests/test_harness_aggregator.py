"""
Tests for backend/app/harnesses/aggregator.py

Coverage matrix:
  - mode='all' with all predecessors done → done
  - mode='all' with one predecessor failed → failed
  - mode='all' with one predecessor still pending → pending
  - mode='any' with first predecessor done → done
  - mode='any' with all predecessors failed → failed
  - mode='any' with no predecessors done yet → pending
  - compose_output for mode='all' done verdict
  - compose_output for mode='all' failed verdict
  - compose_output for mode='any' done verdict
  - compose_output for mode='any' failed verdict
  - compose_output for pending verdict
  - 2-Agent + Aggregator(any) skewed-completion scenario
  - Aggregator with no predecessors (edge case)
  - Unknown mode falls back to 'all' semantics
"""

from __future__ import annotations

import pytest

from app.harnesses.aggregator import AggregatorVerdict, aggregator_ready, compose_output
from app.harnesses.model import HarnessNode, NodeType, Position
from app.harnesses.run_state import NodeState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_aggregator(mode: str = "all") -> HarnessNode:
    """Return a minimal Aggregator HarnessNode."""
    return HarnessNode(
        id="agg1",
        type=NodeType.aggregator,
        position=Position(x=0, y=0),
        data={"mode": mode},
    )


def _ns(status: str, output: str | None = None, reason: str | None = None) -> NodeState:
    return NodeState(status=status, output=output, reason=reason)


# ---------------------------------------------------------------------------
# aggregator_ready — mode='all'
# ---------------------------------------------------------------------------


class TestAggregatorReadyAll:
    """Tests for aggregator_ready() with mode='all'."""

    def test_all_predecessors_done_returns_done(self):
        node = _make_aggregator("all")
        preds = {
            "a1": _ns("done", output="result-a1"),
            "a2": _ns("done", output="result-a2"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.done

    def test_one_predecessor_failed_returns_failed(self):
        node = _make_aggregator("all")
        preds = {
            "a1": _ns("done", output="result-a1"),
            "a2": _ns("failed", reason="agent-error"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.failed

    def test_all_predecessors_failed_returns_failed(self):
        node = _make_aggregator("all")
        preds = {
            "a1": _ns("failed", reason="err1"),
            "a2": _ns("failed", reason="err2"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.failed

    def test_one_predecessor_pending_returns_pending(self):
        node = _make_aggregator("all")
        preds = {
            "a1": _ns("done", output="result-a1"),
            "a2": _ns("pending"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.pending

    def test_one_predecessor_in_progress_returns_pending(self):
        node = _make_aggregator("all")
        preds = {
            "a1": _ns("done"),
            "a2": _ns("in_progress"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.pending

    def test_mixed_done_pending_failed_returns_pending(self):
        """One pending keeps verdict as pending even if one already failed."""
        node = _make_aggregator("all")
        preds = {
            "a1": _ns("done"),
            "a2": _ns("failed", reason="err"),
            "a3": _ns("pending"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.pending

    def test_single_predecessor_done_returns_done(self):
        node = _make_aggregator("all")
        preds = {"a1": _ns("done", output="result")}
        assert aggregator_ready(node, preds) == AggregatorVerdict.done

    def test_single_predecessor_failed_returns_failed(self):
        node = _make_aggregator("all")
        preds = {"a1": _ns("failed", reason="err")}
        assert aggregator_ready(node, preds) == AggregatorVerdict.failed


# ---------------------------------------------------------------------------
# aggregator_ready — mode='any'
# ---------------------------------------------------------------------------


class TestAggregatorReadyAny:
    """Tests for aggregator_ready() with mode='any'."""

    def test_first_predecessor_done_returns_done(self):
        """mode='any': fires as soon as ANY predecessor is done."""
        node = _make_aggregator("any")
        preds = {
            "a1": _ns("done", output="fast-result"),
            "a2": _ns("in_progress"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.done

    def test_any_with_all_predecessors_done_returns_done(self):
        node = _make_aggregator("any")
        preds = {
            "a1": _ns("done"),
            "a2": _ns("done"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.done

    def test_all_predecessors_failed_returns_failed(self):
        node = _make_aggregator("any")
        preds = {
            "a1": _ns("failed", reason="err1"),
            "a2": _ns("failed", reason="err2"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.failed

    def test_no_predecessors_done_yet_returns_pending(self):
        """mode='any': still waiting — nothing done yet."""
        node = _make_aggregator("any")
        preds = {
            "a1": _ns("in_progress"),
            "a2": _ns("pending"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.pending

    def test_one_failed_rest_pending_returns_pending(self):
        """mode='any': one failure does not make it failed if others are still running."""
        node = _make_aggregator("any")
        preds = {
            "a1": _ns("failed", reason="err"),
            "a2": _ns("in_progress"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.pending

    def test_done_beats_failed_returns_done(self):
        """mode='any': one done + one failed → still done (not failed)."""
        node = _make_aggregator("any")
        preds = {
            "a1": _ns("done", output="winner"),
            "a2": _ns("failed", reason="err"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.done

    def test_single_predecessor_done_returns_done(self):
        node = _make_aggregator("any")
        preds = {"a1": _ns("done", output="result")}
        assert aggregator_ready(node, preds) == AggregatorVerdict.done

    def test_single_predecessor_failed_returns_failed(self):
        node = _make_aggregator("any")
        preds = {"a1": _ns("failed", reason="err")}
        assert aggregator_ready(node, preds) == AggregatorVerdict.failed


# ---------------------------------------------------------------------------
# aggregator_ready — edge cases
# ---------------------------------------------------------------------------


class TestAggregatorReadyEdgeCases:
    """Edge cases for aggregator_ready()."""

    def test_no_predecessors_all_mode_returns_done(self):
        """With zero predecessors all conditions are vacuously satisfied."""
        node = _make_aggregator("all")
        assert aggregator_ready(node, {}) == AggregatorVerdict.done

    def test_no_predecessors_any_mode_returns_pending(self):
        """mode='any' with no predecessors: done_count=0, failed_count=0, total=0.
        The condition `failed_count == total and total > 0` is False → pending."""
        node = _make_aggregator("any")
        assert aggregator_ready(node, {}) == AggregatorVerdict.pending

    def test_unknown_mode_falls_back_to_all_semantics(self):
        """Unknown mode falls through to 'all' semantics."""
        node = HarnessNode(
            id="agg_unknown",
            type=NodeType.aggregator,
            position=Position(x=0, y=0),
            data={"mode": "unknown_mode"},
        )
        preds = {
            "a1": _ns("done"),
            "a2": _ns("done"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.done

    def test_default_mode_is_all(self):
        """No 'mode' key → defaults to 'all'."""
        node = HarnessNode(
            id="agg_nomode",
            type=NodeType.aggregator,
            position=Position(x=0, y=0),
            data={},
        )
        preds = {"a1": _ns("done"), "a2": _ns("pending")}
        assert aggregator_ready(node, preds) == AggregatorVerdict.pending


# ---------------------------------------------------------------------------
# compose_output — mode='all' done
# ---------------------------------------------------------------------------


class TestComposeOutputAllDone:
    def test_all_mode_done_merges_all_outputs(self):
        preds = {
            "a1": _ns("done", output="output-a1"),
            "a2": _ns("done", output="output-a2"),
        }
        result = compose_output(AggregatorVerdict.done, preds, "all")
        assert result["done_count"] == 2
        assert result["failed_count"] == 0
        assert result["outputs"] == {"a1": "output-a1", "a2": "output-a2"}

    def test_all_mode_done_with_none_output(self):
        preds = {
            "a1": _ns("done", output=None),
            "a2": _ns("done", output="result"),
        }
        result = compose_output(AggregatorVerdict.done, preds, "all")
        assert result["outputs"]["a1"] is None
        assert result["outputs"]["a2"] == "result"


# ---------------------------------------------------------------------------
# compose_output — mode='any' done
# ---------------------------------------------------------------------------


class TestComposeOutputAnyDone:
    def test_any_mode_done_returns_first_done_output(self):
        # Insertion-ordered: a1 is first done
        preds = {
            "a1": _ns("done", output="fast-output"),
            "a2": _ns("in_progress"),
        }
        result = compose_output(AggregatorVerdict.done, preds, "any")
        assert result["first_done_node_id"] == "a1"
        assert result["output"] == "fast-output"
        assert result["done_count"] == 1

    def test_any_mode_done_with_none_output(self):
        preds = {"a1": _ns("done", output=None)}
        result = compose_output(AggregatorVerdict.done, preds, "any")
        assert result["first_done_node_id"] == "a1"
        assert result["output"] is None

    def test_any_mode_done_multiple_done_returns_first(self):
        preds = {
            "a1": _ns("done", output="first"),
            "a2": _ns("done", output="second"),
        }
        result = compose_output(AggregatorVerdict.done, preds, "any")
        assert result["first_done_node_id"] == "a1"
        assert result["output"] == "first"
        assert result["done_count"] == 2


# ---------------------------------------------------------------------------
# compose_output — failed verdict
# ---------------------------------------------------------------------------


class TestComposeOutputFailed:
    def test_failed_verdict_includes_failure_details(self):
        preds = {
            "a1": _ns("done", output="result"),
            "a2": _ns("failed", reason="timeout"),
        }
        result = compose_output(AggregatorVerdict.failed, preds, "all")
        assert result["failed_count"] == 1
        assert result["done_count"] == 1
        assert result["failed_nodes"] == {"a2": "timeout"}

    def test_all_failed_failure_details(self):
        preds = {
            "a1": _ns("failed", reason="err1"),
            "a2": _ns("failed", reason="err2"),
        }
        result = compose_output(AggregatorVerdict.failed, preds, "any")
        assert result["failed_count"] == 2
        assert result["done_count"] == 0
        assert "a1" in result["failed_nodes"]
        assert "a2" in result["failed_nodes"]

    def test_failed_verdict_any_mode_same_structure(self):
        preds = {
            "a1": _ns("failed", reason="err"),
            "a2": _ns("failed", reason="err2"),
        }
        result = compose_output(AggregatorVerdict.failed, preds, "any")
        assert result["failed_nodes"] == {"a1": "err", "a2": "err2"}


# ---------------------------------------------------------------------------
# compose_output — pending verdict
# ---------------------------------------------------------------------------


class TestComposeOutputPending:
    def test_pending_verdict_returns_empty_dict(self):
        preds = {"a1": _ns("pending"), "a2": _ns("in_progress")}
        result = compose_output(AggregatorVerdict.pending, preds, "all")
        assert result == {}

    def test_pending_verdict_any_mode_returns_empty_dict(self):
        preds = {"a1": _ns("in_progress")}
        result = compose_output(AggregatorVerdict.pending, preds, "any")
        assert result == {}


# ---------------------------------------------------------------------------
# Skewed-completion scenario: 2-Agent + Aggregator(any)
# ---------------------------------------------------------------------------


class TestSkewedCompletionScenario:
    """
    Simulate a 2-Agent + Aggregator(any) harness where one agent completes
    much faster than the other.

    Topology:
        fast_agent ──┐
                     ├──► aggregator(mode='any')
        slow_agent ──┘

    Sequence of events:
      T0: both agents are in_progress
      T1: fast_agent completes (done); slow_agent still in_progress
          → aggregator_ready() should return 'done'
      T2: slow_agent completes (done)
          → aggregator_ready() still returns 'done'
    """

    def _setup_aggregator(self) -> HarnessNode:
        return _make_aggregator("any")

    def test_t0_both_in_progress_returns_pending(self):
        node = self._setup_aggregator()
        preds = {
            "fast_agent": _ns("in_progress"),
            "slow_agent": _ns("in_progress"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.pending

    def test_t1_fast_done_slow_in_progress_returns_done(self):
        """Aggregator fires immediately when fast_agent completes."""
        node = self._setup_aggregator()
        preds = {
            "fast_agent": _ns("done", output="fast-result"),
            "slow_agent": _ns("in_progress"),
        }
        verdict = aggregator_ready(node, preds)
        assert verdict == AggregatorVerdict.done

    def test_t1_compose_output_returns_fast_agent_result(self):
        """compose_output for mode='any' returns the first done agent's output."""
        node = self._setup_aggregator()
        preds = {
            "fast_agent": _ns("done", output="fast-result"),
            "slow_agent": _ns("in_progress"),
        }
        verdict = aggregator_ready(node, preds)
        assert verdict == AggregatorVerdict.done

        result = compose_output(verdict, preds, "any")
        assert result["first_done_node_id"] == "fast_agent"
        assert result["output"] == "fast-result"

    def test_t2_both_done_still_returns_done(self):
        """After slow_agent also completes, verdict is still done."""
        node = self._setup_aggregator()
        preds = {
            "fast_agent": _ns("done", output="fast-result"),
            "slow_agent": _ns("done", output="slow-result"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.done

    def test_fast_done_slow_failed_still_returns_done(self):
        """mode='any': one done is enough — slow_agent failure is irrelevant."""
        node = self._setup_aggregator()
        preds = {
            "fast_agent": _ns("done", output="fast-result"),
            "slow_agent": _ns("failed", reason="timeout"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.done

    def test_fast_failed_slow_done_returns_done(self):
        """mode='any': even if fast fails, slow done still fires."""
        node = self._setup_aggregator()
        preds = {
            "fast_agent": _ns("failed", reason="err"),
            "slow_agent": _ns("done", output="slow-result"),
        }
        assert aggregator_ready(node, preds) == AggregatorVerdict.done

    def test_compose_picks_first_insertion_order(self):
        """compose_output for mode='any' uses dict insertion order for first-done."""
        node = self._setup_aggregator()
        # slow_agent listed first in the dict, fast_agent second —
        # but slow_agent is still in_progress.
        preds = {
            "slow_agent": _ns("in_progress"),
            "fast_agent": _ns("done", output="fast-result"),
        }
        result = compose_output(AggregatorVerdict.done, preds, "any")
        assert result["first_done_node_id"] == "fast_agent"
        assert result["output"] == "fast-result"
