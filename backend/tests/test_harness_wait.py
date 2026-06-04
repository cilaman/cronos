"""
Tests for backend/app/harnesses/wait.py

Coverage:
  - enter_wait() sets run_state.waiting_node_id correctly
  - enter_wait() returns WaitOutcome with WaitAction.park_waiting
  - enter_wait() populates waiting_question from node.data
  - enter_wait() handles missing waiting_question gracefully
  - await_timed_wait() sleeps for the configured duration (asyncio.sleep mocked)
  - await_timed_wait() handles missing duration_seconds (defaults to 0)
  - await_timed_wait() handles duration_seconds=0 explicitly
  - await_timed_wait() handles float duration_seconds
  - Multiple enter_wait() calls update waiting_node_id each time (last-write wins)
  - WaitOutcome.waiting_node_id matches node.id
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.harnesses.model import HarnessNode, NodeType, Position
from app.harnesses.run_state import NodeState, RunState
from app.harnesses.wait import WaitAction, WaitOutcome, await_timed_wait, enter_wait


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wait_node(
    node_id: str = "wait-1",
    mode: str = "human",
    extra_data: dict | None = None,
) -> HarnessNode:
    """Build a minimal Wait HarnessNode for testing."""
    data: dict = {"mode": mode}
    if extra_data:
        data.update(extra_data)
    return HarnessNode(
        id=node_id,
        type=NodeType.wait,
        position=Position(x=0.0, y=0.0),
        data=data,
    )


def _make_run_state(run_id: str = "run-1") -> RunState:
    """Build a minimal RunState for testing."""
    return RunState(
        run_id=run_id,
        harness_id="harness-1",
        goal_task_id="goal-1",
    )


# ---------------------------------------------------------------------------
# enter_wait() — basic behaviour
# ---------------------------------------------------------------------------


class TestEnterWait:
    def test_sets_waiting_node_id_on_run_state(self):
        node = _make_wait_node("w1")
        state = _make_run_state()
        assert state.waiting_node_id is None

        enter_wait(node, state)

        assert state.waiting_node_id == "w1"

    def test_returns_wait_outcome(self):
        node = _make_wait_node("w1")
        state = _make_run_state()

        outcome = enter_wait(node, state)

        assert isinstance(outcome, WaitOutcome)

    def test_outcome_action_is_park_waiting(self):
        node = _make_wait_node("w1")
        state = _make_run_state()

        outcome = enter_wait(node, state)

        assert outcome.action == WaitAction.park_waiting

    def test_outcome_waiting_node_id_matches_node_id(self):
        node = _make_wait_node("my-wait-node")
        state = _make_run_state()

        outcome = enter_wait(node, state)

        assert outcome.waiting_node_id == "my-wait-node"

    def test_outcome_waiting_node_id_equals_run_state_waiting_node_id(self):
        node = _make_wait_node("sync-check")
        state = _make_run_state()

        outcome = enter_wait(node, state)

        # Both the mutated run_state and the returned outcome must agree.
        assert outcome.waiting_node_id == state.waiting_node_id


# ---------------------------------------------------------------------------
# enter_wait() — waiting_question handling
# ---------------------------------------------------------------------------


class TestEnterWaitQuestion:
    def test_waiting_question_present(self):
        node = _make_wait_node(
            "w1",
            extra_data={"waiting_question": "Are you ready to continue?"},
        )
        state = _make_run_state()

        outcome = enter_wait(node, state)

        assert outcome.waiting_question == "Are you ready to continue?"

    def test_waiting_question_absent_returns_none(self):
        node = _make_wait_node("w1")  # no waiting_question key
        state = _make_run_state()

        outcome = enter_wait(node, state)

        assert outcome.waiting_question is None

    def test_waiting_question_empty_string(self):
        node = _make_wait_node("w1", extra_data={"waiting_question": ""})
        state = _make_run_state()

        outcome = enter_wait(node, state)

        # Empty string is a valid (falsy) value — distinguish from None.
        assert outcome.waiting_question == ""

    def test_waiting_question_multiline(self):
        question = "Please review the output.\nAre you satisfied?"
        node = _make_wait_node("w1", extra_data={"waiting_question": question})
        state = _make_run_state()

        outcome = enter_wait(node, state)

        assert outcome.waiting_question == question


# ---------------------------------------------------------------------------
# enter_wait() — edge cases
# ---------------------------------------------------------------------------


class TestEnterWaitEdgeCases:
    def test_multiple_calls_update_waiting_node_id(self):
        """Last enter_wait() call wins — waiting_node_id tracks the current node."""
        node_a = _make_wait_node("wait-a")
        node_b = _make_wait_node("wait-b")
        state = _make_run_state()

        enter_wait(node_a, state)
        assert state.waiting_node_id == "wait-a"

        enter_wait(node_b, state)
        assert state.waiting_node_id == "wait-b"

    def test_run_state_with_existing_nodes_executed(self):
        """enter_wait() does not disturb nodes_executed."""
        node = _make_wait_node("w1")
        state = _make_run_state()
        state.nodes_executed["prior-node"] = NodeState(status="done")

        enter_wait(node, state)

        assert "prior-node" in state.nodes_executed
        assert state.waiting_node_id == "w1"

    def test_node_data_has_max_wait_seconds_not_used_by_enter_wait(self):
        """enter_wait() does not consume max_wait_seconds — that's the validator's job."""
        node = _make_wait_node(
            "w1",
            extra_data={"max_wait_seconds": 300, "waiting_question": "Proceed?"},
        )
        state = _make_run_state()

        # Should not raise.
        outcome = enter_wait(node, state)
        assert outcome.action == WaitAction.park_waiting

    def test_node_with_no_data_does_not_raise(self):
        """A node constructed without extra data still works."""
        node = HarnessNode(
            id="bare-wait",
            type=NodeType.wait,
            position=Position(x=0.0, y=0.0),
            # data defaults to {} via Field(default_factory=dict)
        )
        state = _make_run_state()

        outcome = enter_wait(node, state)

        assert outcome.waiting_node_id == "bare-wait"
        assert outcome.waiting_question is None


# ---------------------------------------------------------------------------
# await_timed_wait() — sleep duration
# ---------------------------------------------------------------------------


class TestAwaitTimedWait:
    @pytest.mark.asyncio
    async def test_sleeps_for_duration_seconds(self):
        node = _make_wait_node("tw1", mode="timed", extra_data={"duration_seconds": 5.0})

        with patch("app.harnesses.wait.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await await_timed_wait(node)

        mock_sleep.assert_awaited_once_with(5.0)

    @pytest.mark.asyncio
    async def test_sleeps_for_integer_duration(self):
        node = _make_wait_node("tw1", mode="timed", extra_data={"duration_seconds": 10})

        with patch("app.harnesses.wait.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await await_timed_wait(node)

        mock_sleep.assert_awaited_once_with(10.0)

    @pytest.mark.asyncio
    async def test_missing_duration_seconds_defaults_to_zero(self):
        """If duration_seconds is absent the timed wait sleeps for 0 seconds."""
        node = _make_wait_node("tw1", mode="timed")
        # Remove duration_seconds key to simulate misconfiguration / edge case.
        assert "duration_seconds" not in node.data

        with patch("app.harnesses.wait.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await await_timed_wait(node)

        mock_sleep.assert_awaited_once_with(0.0)

    @pytest.mark.asyncio
    async def test_duration_seconds_zero(self):
        node = _make_wait_node("tw1", mode="timed", extra_data={"duration_seconds": 0})

        with patch("app.harnesses.wait.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await await_timed_wait(node)

        mock_sleep.assert_awaited_once_with(0.0)

    @pytest.mark.asyncio
    async def test_duration_seconds_none_defaults_to_zero(self):
        """If duration_seconds is explicitly None, treat as 0."""
        node = _make_wait_node("tw1", mode="timed")
        node.data["duration_seconds"] = None

        with patch("app.harnesses.wait.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await await_timed_wait(node)

        mock_sleep.assert_awaited_once_with(0.0)

    @pytest.mark.asyncio
    async def test_returns_none(self):
        """await_timed_wait() returns None (pure function — no verdict object)."""
        node = _make_wait_node("tw1", mode="timed", extra_data={"duration_seconds": 1.0})

        with patch("app.harnesses.wait.asyncio.sleep", new_callable=AsyncMock):
            result = await await_timed_wait(node)

        assert result is None

    @pytest.mark.asyncio
    async def test_fractional_duration(self):
        node = _make_wait_node("tw1", mode="timed", extra_data={"duration_seconds": 0.25})

        with patch("app.harnesses.wait.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await await_timed_wait(node)

        mock_sleep.assert_awaited_once_with(0.25)


# ---------------------------------------------------------------------------
# WaitAction enum sanity
# ---------------------------------------------------------------------------


class TestWaitActionEnum:
    def test_park_waiting_value(self):
        assert WaitAction.park_waiting == "park_waiting"

    def test_wait_outcome_is_dataclass(self):
        outcome = WaitOutcome(
            action=WaitAction.park_waiting,
            waiting_node_id="x",
            waiting_question="Q?",
        )
        assert outcome.action == WaitAction.park_waiting
        assert outcome.waiting_node_id == "x"
        assert outcome.waiting_question == "Q?"
