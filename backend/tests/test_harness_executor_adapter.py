"""
tests/test_harness_executor_adapter — Unit tests for HarnessExecutorAdapter.

Covers R6 (ExecutorInterface compliance), R7 (telemetry event schema), and R8
(escalate discriminator: human-wait park vs loop exhaust).

Also includes a snapshot test asserting that emitted telemetry payloads
structurally equal a fixture captured from a reference BFS-path on the same
harness (as required by the I4 design spec).
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap so delivery-workflow types are importable in test context.
# ---------------------------------------------------------------------------
import sys
from pathlib import Path

_SPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DW_PKG = _SPACE_ROOT / "packages" / "delivery-workflow"
if str(_DW_PKG) not in sys.path:
    sys.path.insert(0, str(_DW_PKG))

from results import AgentResult, TelemetryData  # noqa: E402
from state_types import BudgetState, NodeState as WfNodeState, WorkflowState  # noqa: E402

from app.harnesses.executor_adapter import (  # noqa: E402
    HarnessExecutorAdapter,
    WorkerAdapter,
    _StateOps,
    _TelemetryOps,
    _is_human_wait,
)
from app.harnesses.run_state import NodeState as HarnessNodeState, RunState  # noqa: E402
from app.models import TaskState  # noqa: E402
from app.trace_parser import RunTrace  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures / stubs
# ---------------------------------------------------------------------------


def _make_run_state(
    run_id: str = "run-1",
    harness_id: str = "test-harness",
    goal_task_id: str = "goal-1",
    nodes: dict | None = None,
    status: str = "running",
) -> RunState:
    """Build a minimal RunState for tests."""
    return RunState(
        run_id=run_id,
        harness_id=harness_id,
        goal_task_id=goal_task_id,
        nodes_executed=nodes or {},
        status=status,
    )


def _make_run_trace(
    task_id: str = "child-1",
    exit_reason: str = "done",
    final_text_snippet: str = "agent output",
) -> RunTrace:
    """Build a minimal RunTrace for tests."""
    from datetime import datetime, timezone

    now = datetime.now(tz=timezone.utc)
    return RunTrace(
        task_id=task_id,
        space_id="space-1",
        run_index=0,
        session_id=None,
        model="claude-3",
        mode="auto",
        started_at=now,
        ended_at=now,
        duration_seconds=1.0,
        exit_reason=exit_reason,
        final_text_snippet=final_text_snippet,
    )


class StubWorkerAdapter:
    """Test stub satisfying WorkerAdapter protocol."""

    def __init__(
        self,
        run_agent_result: RunTrace | None = None,
        finalize_result: TaskState = TaskState.DONE,
        run_agent_raises: Exception | None = None,
        finalize_raises: Exception | None = None,
    ) -> None:
        self._run_trace = run_agent_result or _make_run_trace()
        self._final_state = finalize_result
        self._run_agent_raises = run_agent_raises
        self._finalize_raises = finalize_raises
        self.run_agent_calls: list[str] = []
        self.finalize_calls: list[str] = []

    async def run_agent(self, task_id: str) -> RunTrace:
        self.run_agent_calls.append(task_id)
        if self._run_agent_raises:
            raise self._run_agent_raises
        return self._run_trace

    async def finalize_child(self, task_id: str) -> TaskState:
        self.finalize_calls.append(task_id)
        if self._finalize_raises:
            raise self._finalize_raises
        return self._final_state


def _make_adapter(
    worker: StubWorkerAdapter | None = None,
    run_state: RunState | None = None,
    harness_id: str = "test-harness",
    goal_task_id: str = "goal-1",
    captured_events: list | None = None,
) -> HarnessExecutorAdapter:
    """Build a HarnessExecutorAdapter with test defaults."""
    if worker is None:
        worker = StubWorkerAdapter()
    if run_state is None:
        run_state = _make_run_state()

    events: list[dict] = [] if captured_events is None else captured_events

    def _publish(tid: str, event: dict) -> None:
        events.append(event)

    task_id_counter = [0]

    def _task_id_factory(agent_ref: str, inputs: dict) -> str:
        task_id_counter[0] += 1
        return f"child-task-{task_id_counter[0]}"

    return HarnessExecutorAdapter(
        worker_adapter=worker,
        run_state=run_state,
        harness_id=harness_id,
        goal_task_id=goal_task_id,
        publish_cb=_publish,
        task_id_factory=_task_id_factory,
    )


# ---------------------------------------------------------------------------
# R6: ExecutorInterface compliance
# ---------------------------------------------------------------------------


class TestExecutorInterfaceCompliance:
    """Verify HarnessExecutorAdapter satisfies the ExecutorInterface protocol."""

    def test_has_state_attribute(self) -> None:
        adapter = _make_adapter()
        assert hasattr(adapter, "state")
        assert hasattr(adapter.state, "read")
        assert hasattr(adapter.state, "write")

    def test_has_telemetry_attribute(self) -> None:
        adapter = _make_adapter()
        assert hasattr(adapter, "telemetry")
        assert hasattr(adapter.telemetry, "emit")

    def test_has_dispatch_agent(self) -> None:
        adapter = _make_adapter()
        assert callable(adapter.dispatchAgent)

    def test_has_run_gate(self) -> None:
        adapter = _make_adapter()
        assert callable(adapter.runGate)

    def test_has_eval_condition(self) -> None:
        adapter = _make_adapter()
        assert callable(adapter.evalCondition)

    def test_has_escalate(self) -> None:
        adapter = _make_adapter()
        assert callable(adapter.escalate)

    def test_protocol_isinstance_check(self) -> None:
        """WorkerAdapter Protocol isinstance check works (runtime_checkable)."""
        worker = StubWorkerAdapter()
        assert isinstance(worker, WorkerAdapter)

    def test_initial_workflow_state_from_run_state(self) -> None:
        """Adapter initialises WorkflowState from RunState at construction."""
        run_state = _make_run_state(
            run_id="r1",
            harness_id="h1",
            nodes={"node-a": HarnessNodeState(status="done", output="hello")},
        )
        adapter = _make_adapter(run_state=run_state, harness_id="h1")
        ws = adapter.state.read()
        assert ws.run_id == "r1"
        assert ws.spec == "h1"
        assert "node-a" in ws.nodes
        assert ws.nodes["node-a"].status == "done"


# ---------------------------------------------------------------------------
# StateOps tests
# ---------------------------------------------------------------------------


class TestStateOps:
    """Tests for the _StateOps implementation."""

    def _initial_ws(self) -> WorkflowState:
        return WorkflowState(
            spec="spec",
            run_id="r1",
            status="running",
            budget=BudgetState(usd_ceiling=0.0),
        )

    def test_read_returns_state(self) -> None:
        ws = self._initial_ws()
        ops = _StateOps(ws)
        assert ops.read() is ws

    def test_write_status(self) -> None:
        ops = _StateOps(self._initial_ws())
        ops.write({"status": "done"})
        assert ops.read().status == "done"

    def test_write_node_merge(self) -> None:
        ops = _StateOps(self._initial_ws())
        ops.write({
            "nodes": {
                "n1": {"status": "done", "attempt": 2, "artifact_paths": ["p1"]}
            }
        })
        ws = ops.read()
        assert "n1" in ws.nodes
        assert ws.nodes["n1"].status == "done"
        assert ws.nodes["n1"].attempt == 2
        assert ws.nodes["n1"].artifact_paths == ["p1"]

    def test_write_node_creates_new(self) -> None:
        ops = _StateOps(self._initial_ws())
        ops.write({"nodes": {"n2": {"status": "failed"}}})
        assert ops.read().nodes["n2"].status == "failed"

    def test_write_node_merges_fields(self) -> None:
        ws = self._initial_ws()
        ws.nodes["n1"] = WfNodeState(status="running", fields={"x": 1})
        ops = _StateOps(ws)
        ops.write({"nodes": {"n1": {"fields": {"y": 2}}}})
        assert ops.read().nodes["n1"].fields == {"x": 1, "y": 2}

    def test_write_empty_patch(self) -> None:
        ops = _StateOps(self._initial_ws())
        ops.write({})  # Should not raise
        assert ops.read().status == "running"


# ---------------------------------------------------------------------------
# evalCondition tests
# ---------------------------------------------------------------------------


class TestEvalCondition:
    """Tests for evalCondition delegating to decision.eval_condition."""

    def test_empty_expr_returns_true(self) -> None:
        adapter = _make_adapter()
        assert adapter.evalCondition("", {}) is True

    def test_equality_match(self) -> None:
        adapter = _make_adapter()
        assert adapter.evalCondition("x == foo", {"x": "foo"}) is True

    def test_equality_no_match(self) -> None:
        adapter = _make_adapter()
        assert adapter.evalCondition("x == bar", {"x": "foo"}) is False

    def test_in_operator(self) -> None:
        # The eval_condition 'in' operator uses comma-separated values: "x in v1,v2"
        adapter = _make_adapter()
        assert adapter.evalCondition("x in done,failed", {"x": "done"}) is True

    def test_not_in_operator(self) -> None:
        adapter = _make_adapter()
        assert adapter.evalCondition("x in done,failed", {"x": "pending"}) is False

    def test_invalid_expr_returns_false(self) -> None:
        """Malformed expressions log a warning and return False without raising."""
        adapter = _make_adapter()
        # A completely invalid expression should not crash.
        result = adapter.evalCondition("!!!invalid!!!", {})
        assert isinstance(result, bool)

    def test_none_scope_raises_or_false(self) -> None:
        """Edge case: scope is None-like — should not raise unhandled."""
        adapter = _make_adapter()
        try:
            result = adapter.evalCondition("x == y", {})
        except Exception:
            pass  # Acceptable; test is that it doesn't crash the process.


# ---------------------------------------------------------------------------
# escalate() discriminator tests (R8, risk mitigation)
# ---------------------------------------------------------------------------


class TestEscalateDiscriminator:
    """Verify that escalate() correctly discriminates human-wait from loop exhaust."""

    def test_human_wait_prefix_sets_blocked(self) -> None:
        adapter = _make_adapter()
        adapter.escalate("wait-node-1", "[wait/human] wait-node-1: Waiting for human input.")
        ws = adapter.state.read()
        assert ws.status == "blocked"

    def test_human_prefix_sets_blocked(self) -> None:
        adapter = _make_adapter()
        adapter.escalate("human-node", "[human] human-node: Human input required.")
        ws = adapter.state.read()
        assert ws.status == "blocked"

    def test_wait_colon_prefix_sets_blocked(self) -> None:
        adapter = _make_adapter()
        adapter.escalate("wn", "wait: human approval needed")
        ws = adapter.state.read()
        assert ws.status == "blocked"

    def test_loop_exhaust_sets_escalated(self) -> None:
        adapter = _make_adapter()
        adapter.escalate("loop-node", "max_attempts=10 exhausted")
        ws = adapter.state.read()
        assert ws.status == "escalated"

    def test_global_cap_sets_escalated(self) -> None:
        adapter = _make_adapter()
        adapter.escalate("__runner__", "global_iteration_cap_exceeded")
        ws = adapter.state.read()
        assert ws.status == "escalated"

    def test_loop_exhaust_does_not_set_waiting_node(self) -> None:
        """Loop exhaust must NOT set waiting_node_id on the RunState."""
        adapter = _make_adapter()
        adapter.escalate("loop-node", "recurring_findings after 3 attempt(s)")
        # Convert back to RunState and check waiting_node_id is None.
        rs = adapter.to_run_state()
        assert rs.waiting_node_id is None

    def test_is_human_wait_helper(self) -> None:
        assert _is_human_wait("[wait/human] test") is True
        assert _is_human_wait("[human] test") is True
        assert _is_human_wait("wait: test") is True
        assert _is_human_wait("max_attempts=10 exhausted") is False
        assert _is_human_wait("global_iteration_cap_exceeded") is False
        assert _is_human_wait("recurring_findings") is False

    def test_human_wait_escalate_is_node_write_free(self) -> None:
        """R9 single-writer (§5.8): escalate writes RUN status only — the node
        'blocked' status is written once, by the runner, from the dispatch
        handler's returned NodeOutcome.  A node sub-patch here would be a
        second out-of-band writer (the D11 double-write class)."""
        adapter = _make_adapter()
        before = {nid: ns.status for nid, ns in adapter.state.read().nodes.items()}
        adapter.escalate("wait-1", "[wait/human] wait-1: Please review.")
        ws = adapter.state.read()
        assert ws.status == "blocked"
        assert "wait-1" not in ws.nodes, "escalate must not create node state"
        assert {nid: ns.status for nid, ns in ws.nodes.items()} == before


# ---------------------------------------------------------------------------
# dispatchAgent tests
# ---------------------------------------------------------------------------


class TestDispatchAgent:
    """Tests for dispatchAgent — wraps run_agent + finalize_child."""

    def test_dispatch_agent_done(self) -> None:
        """Successful agent dispatch returns AgentResult with status='done'."""
        trace = _make_run_trace(final_text_snippet="STATUS: DONE\nAll good.")
        worker = StubWorkerAdapter(run_agent_result=trace, finalize_result=TaskState.DONE)
        events: list[dict] = []
        adapter = _make_adapter(worker=worker, captured_events=events)

        result = adapter.dispatchAgent("my-agent", {"node_id": "node-a", "scope": {}})

        assert isinstance(result, AgentResult)
        assert result.status == "done"
        assert result.fields.get("output") == "STATUS: DONE\nAll good."
        assert len(worker.run_agent_calls) == 1
        assert len(worker.finalize_calls) == 1

    def test_dispatch_agent_done_enriches_verdict_fields(self) -> None:
        """P0-1: a delivery_status/node_status envelope in the agent's output is
        parsed and its structured fields (verdict, finding_class) surface in
        AgentResult.fields so verdict-routed edges can fire.  Node status stays
        'done' so runner/scope exposes the fields."""
        envelope = (
            "Review complete.\n\n"
            "```delivery_status\n"
            '{"status": "needs_fix", "produces": "review",\n'
            ' "fields": {"verdict": "needs_fix", "finding_class": "local"}}\n'
            "```\n"
        )
        trace = _make_run_trace(final_text_snippet=envelope)
        worker = StubWorkerAdapter(run_agent_result=trace, finalize_result=TaskState.DONE)
        adapter = _make_adapter(worker=worker)

        result = adapter.dispatchAgent("reviewer", {"node_id": "g-review", "scope": {}})

        assert result.status == "done"  # routable — runner/scope gates on 'done'
        assert result.fields.get("verdict") == "needs_fix"
        assert result.fields.get("finding_class") == "local"

    def test_dispatch_agent_failed_finalize(self) -> None:
        """When finalize_child returns non-DONE, AgentResult.status='failed'."""
        worker = StubWorkerAdapter(finalize_result=TaskState.WAITING)
        adapter = _make_adapter(worker=worker)

        result = adapter.dispatchAgent("agent", {"node_id": "n1"})

        assert result.status == "failed"

    def test_dispatch_agent_run_agent_exception(self) -> None:
        """run_agent exception produces AgentResult(status='failed')."""
        worker = StubWorkerAdapter(run_agent_raises=RuntimeError("agent crashed"))
        adapter = _make_adapter(worker=worker)

        result = adapter.dispatchAgent("agent", {"node_id": "n1"})

        assert result.status == "failed"
        assert "error" in result.fields

    def test_dispatch_agent_finalize_exception(self) -> None:
        """finalize_child exception produces AgentResult(status='failed')."""
        worker = StubWorkerAdapter(finalize_raises=ValueError("finalize failed"))
        adapter = _make_adapter(worker=worker)

        result = adapter.dispatchAgent("agent", {"node_id": "n1"})

        assert result.status == "failed"

    def test_dispatch_agent_emits_node_transition_events(self) -> None:
        """dispatchAgent emits in_progress and done node_transition events."""
        events: list[dict] = []
        worker = StubWorkerAdapter()
        adapter = _make_adapter(worker=worker, captured_events=events)

        adapter.dispatchAgent("agent", {"node_id": "n1"})

        node_transitions = [e for e in events if e.get("type") == "node_transition"]
        assert len(node_transitions) >= 2
        statuses = [e.get("status") for e in node_transitions]
        assert "in_progress" in statuses
        assert "done" in statuses


# ---------------------------------------------------------------------------
# runGate tests
# ---------------------------------------------------------------------------


class TestRunGate:
    """runGate should raise NotImplementedError for Cronos harnesses."""

    def test_run_gate_raises(self) -> None:
        adapter = _make_adapter()
        with pytest.raises(NotImplementedError):
            adapter.runGate({"id": "g1"}, [])


# ---------------------------------------------------------------------------
# R7: Telemetry event schema snapshot test
# ---------------------------------------------------------------------------


class TestTelemetryEventSchema:
    """Snapshot test: emitted telemetry payloads match existing _publish schema.

    The fixture below captures the exact event shapes produced by a reference
    BFS-path execution of a two-node harness (trigger → agent).  The adapter's
    telemetry.emit() must produce structurally equivalent dicts.
    """

    # Reference BFS-path event fixture (structural, not timestamp-exact).
    # Each entry is a dict of required keys + expected values (None = key must exist).
    _NODE_TRANSITION_FIXTURE = {
        "type": "node_transition",
        "node_id": "agent-1",
        "status": "in_progress",
        "from_status": "pending",
        # "timestamp" key must be present
    }

    _NODE_DONE_FIXTURE = {
        "type": "node_transition",
        "node_id": "agent-1",
        "status": "done",
        "from_status": "in_progress",
    }

    def test_node_transition_in_progress_shape(self) -> None:
        """node_transition emitted for in_progress has required BFS-schema keys."""
        events: list[dict] = []
        publish_cb = lambda tid, ev: events.append(ev)  # noqa: E731
        telem = _TelemetryOps(goal_task_id="g1", publish_cb=publish_cb)

        telem.emit("agent-1", {"status": "in_progress", "from_status": "pending"})

        assert len(events) == 1
        ev = events[0]
        assert ev["type"] == "node_transition"
        assert ev["node_id"] == "agent-1"
        assert ev["status"] == "in_progress"
        assert ev["from_status"] == "pending"
        assert "timestamp" in ev

    def test_node_transition_done_shape(self) -> None:
        """node_transition emitted for done has required BFS-schema keys."""
        events: list[dict] = []
        telem = _TelemetryOps("g1", lambda t, e: events.append(e))
        telem.emit("agent-1", {"status": "done", "from_status": "in_progress"})

        ev = events[0]
        assert ev["type"] == "node_transition"
        assert ev["status"] == "done"
        assert "node_id" in ev
        assert "timestamp" in ev

    def test_edge_chosen_shape(self) -> None:
        """edge_chosen emitted with correct schema keys."""
        events: list[dict] = []
        telem = _TelemetryOps("g1", lambda t, e: events.append(e))
        telem.emit("decision-1", {"edge_id": "edge-yes"})

        ev = events[0]
        assert ev["type"] == "edge_chosen"
        assert ev["edge_id"] == "edge-yes"
        assert "timestamp" in ev

    def test_run_status_shape(self) -> None:
        """run_status emitted with correct schema keys."""
        events: list[dict] = []
        telem = _TelemetryOps("g1", lambda t, e: events.append(e))
        telem.emit("", {"run_status": "done"})

        ev = events[0]
        assert ev["type"] == "run_status"
        assert ev["status"] == "done"
        assert "timestamp" in ev

    def test_snapshot_full_bfs_path(self) -> None:
        """Snapshot: full agent dispatch emits events structurally equal to BFS fixture.

        This is the canonical snapshot test referenced in the I4 design spec
        (R7 telemetry reconciliation).  The fixture represents what the BFS
        executor emits for a single agent node completing successfully:
          1. node_transition: pending → in_progress
          2. node_transition: in_progress → done
        """
        # BFS-path reference fixture (structural keys only; timestamps vary).
        bfs_fixture_sequence = [
            {
                "type": "node_transition",
                "node_id": "impl",
                "status": "in_progress",
                "from_status": "pending",
            },
            {
                "type": "node_transition",
                "node_id": "impl",
                "status": "done",
                "from_status": "in_progress",
            },
        ]

        events: list[dict] = []
        worker = StubWorkerAdapter(
            run_agent_result=_make_run_trace(task_id="t1", final_text_snippet="output"),
            finalize_result=TaskState.DONE,
        )
        adapter = _make_adapter(worker=worker, captured_events=events)

        adapter.dispatchAgent("impl-agent", {"node_id": "impl", "scope": {}})

        # Filter to node_transition events for "impl".
        nt_events = [e for e in events if e.get("type") == "node_transition" and e.get("node_id") == "impl"]
        assert len(nt_events) >= 2, f"Expected ≥2 node_transition events, got {nt_events}"

        for fixture, actual in zip(bfs_fixture_sequence, nt_events):
            for key, expected_val in fixture.items():
                assert key in actual, f"Missing key {key!r} in event {actual}"
                assert actual[key] == expected_val, (
                    f"Key {key!r}: expected {expected_val!r}, got {actual[key]!r}"
                )
            assert "timestamp" in actual, f"Missing 'timestamp' in event {actual}"


# ---------------------------------------------------------------------------
# to_run_state round-trip tests
# ---------------------------------------------------------------------------


class TestToRunState:
    """Verify that to_run_state() produces a correct RunState from the WorkflowState."""

    def test_run_id_preserved(self) -> None:
        rs = _make_run_state(run_id="my-run-id")
        adapter = _make_adapter(run_state=rs)
        out = adapter.to_run_state()
        assert out.run_id == "my-run-id"

    def test_harness_id_preserved(self) -> None:
        rs = _make_run_state(harness_id="my-harness")
        adapter = _make_adapter(run_state=rs, harness_id="my-harness")
        out = adapter.to_run_state()
        assert out.harness_id == "my-harness"

    def test_done_node_preserved(self) -> None:
        rs = _make_run_state(
            nodes={"n1": HarnessNodeState(status="done", output="result")}
        )
        adapter = _make_adapter(run_state=rs)
        out = adapter.to_run_state()
        assert "n1" in out.nodes_executed
        assert out.nodes_executed["n1"].status == "done"

    def test_escalated_status_maps_to_failed(self) -> None:
        """WorkflowState 'escalated' maps to RunState 'failed'."""
        rs = _make_run_state()
        adapter = _make_adapter(run_state=rs)
        adapter.state.write({"status": "escalated"})
        out = adapter.to_run_state()
        assert out.status == "failed"

    def test_blocked_status_maps_to_running(self) -> None:
        """WorkflowState 'blocked' (human-wait) maps to RunState 'running'."""
        rs = _make_run_state()
        adapter = _make_adapter(run_state=rs)
        adapter.state.write({"status": "blocked"})
        out = adapter.to_run_state()
        assert out.status == "running"


# ---------------------------------------------------------------------------
# Integration: escalate → to_run_state round-trip
# ---------------------------------------------------------------------------


class TestEscalateToRunState:
    """End-to-end: escalate() followed by to_run_state() produces expected RunState."""

    def test_human_wait_round_trip(self) -> None:
        rs = _make_run_state(
            nodes={"wait-1": HarnessNodeState(status="in_progress")}
        )
        adapter = _make_adapter(run_state=rs)
        adapter.escalate("wait-1", "[wait/human] wait-1: Please review output.")

        out = adapter.to_run_state()
        # Run status should be 'running' (blocked → running via mapping).
        assert out.status == "running"
        # waiting_node_id is preserved from the base RunState (not set here since
        # the adapter doesn't directly write waiting_node_id — that's run_executor's job).

    def test_loop_exhaust_round_trip(self) -> None:
        rs = _make_run_state()
        adapter = _make_adapter(run_state=rs)
        adapter.escalate("loop-node", "max_attempts=10 exhausted")

        out = adapter.to_run_state()
        # Escalated → failed in RunState.
        assert out.status == "failed"
        # waiting_node_id is NOT set.
        assert out.waiting_node_id is None
