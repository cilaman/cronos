"""Tests for runner/dispatch.py — all 8 node-kind dispatch handlers (I4)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ir import IRNode
from results import AgentResult, ExecResult, GateResult, TelemetryData
from runner.dispatch import NodeOutcome, dispatch_node
from state_types import BudgetState, NodeState, WorkflowState


# ---------------------------------------------------------------------------
# Minimal test runtime that records calls
# ---------------------------------------------------------------------------

class _MockRuntime:
    def __init__(self):
        self.dispatched: list[tuple[str, dict]] = []
        self.gate_calls: list[tuple[dict, list]] = []
        self.escalated: list[tuple[str, str]] = []
        self._agent_result: AgentResult | None = None
        self._gate_result: GateResult | None = None

    def set_agent_result(self, r: AgentResult) -> None:
        self._agent_result = r

    def set_gate_result(self, r: GateResult) -> None:
        self._gate_result = r

    def dispatchAgent(self, agent_ref: str, inputs: dict) -> AgentResult:
        self.dispatched.append((agent_ref, inputs))
        if self._agent_result:
            return self._agent_result
        return AgentResult(
            status="done",
            artifact_paths=["out/report.md"],
            produces="research",
            fields={"verdict": "pass"},
            open_questions=[],
            telemetry=TelemetryData(tokens=100, usd=0.01, seconds=5.0),
        )

    def runGate(self, gate: dict, artifact_paths: list) -> GateResult:
        self.gate_calls.append((gate, artifact_paths))
        if self._gate_result:
            return self._gate_result
        return GateResult(decision="proceed", errors=[])

    def set_exec_result(self, r: ExecResult) -> None:
        self._exec_result = r

    def runExec(self, node_id: str, command: str, inputs: dict) -> ExecResult:
        if not hasattr(self, "exec_calls"):
            self.exec_calls = []
        self.exec_calls.append((node_id, command, inputs))
        if getattr(self, "_exec_result", None):
            return self._exec_result
        return ExecResult(status="done", exit_code=0, artifact_path="out/testrun-output.md")

    def evalCondition(self, expr: str, scope: dict) -> bool:
        return False

    def escalate(self, node_id: str, reason: str) -> None:
        self.escalated.append((node_id, reason))

    @property
    def state(self):
        class _S:
            def read(self): return None
            def write(self, p): pass
        return _S()

    @property
    def telemetry(self):
        class _T:
            def emit(self, nid, d): pass
        return _T()


def _empty_state() -> WorkflowState:
    return WorkflowState(
        spec="test", run_id="r1", status="running",
        budget=BudgetState(usd_ceiling=0.0),
    )


# ---------------------------------------------------------------------------
# Agent node
# ---------------------------------------------------------------------------

class TestDispatchAgent:
    def test_agent_done_returns_done_outcome(self):
        rt = _MockRuntime()
        node = IRNode(id="scout", kind="agent", data={"agent": "scout"})
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "done"
        assert outcome.artifact_paths == ["out/report.md"]
        assert outcome.fields == {"verdict": "pass"}

    def test_agent_blocked_returns_blocked(self):
        rt = _MockRuntime()
        rt.set_agent_result(AgentResult(
            status="blocked",
            artifact_paths=[],
            produces="",
            fields={},
            open_questions=["need human"],
            telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
        ))
        node = IRNode(id="n", kind="agent")
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "blocked"

    def test_agent_failed_returns_failed(self):
        rt = _MockRuntime()
        rt.set_agent_result(AgentResult(
            status="failed",
            artifact_paths=[],
            produces="",
            fields={},
            open_questions=[],
            telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
        ))
        node = IRNode(id="n", kind="agent")
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "failed"

    def test_agent_attempt_incremented(self):
        rt = _MockRuntime()
        state = _empty_state()
        state.nodes["n"] = NodeState(status="done", attempt=2)
        node = IRNode(id="n", kind="agent")
        outcome = dispatch_node(node, {}, rt, state)
        assert outcome.attempt == 3

    def test_agent_ref_from_data(self):
        rt = _MockRuntime()
        node = IRNode(id="my-node", kind="agent", data={"agent": "my-custom-agent"})
        dispatch_node(node, {}, rt, _empty_state())
        agent_ref, _ = rt.dispatched[0]
        assert agent_ref == "my-custom-agent"

    def test_agent_raises_returns_failed(self):
        rt = _MockRuntime()
        def boom(*args, **kwargs):
            raise RuntimeError("dispatch failed")
        rt.dispatchAgent = boom
        node = IRNode(id="n", kind="agent")
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "failed"


# ---------------------------------------------------------------------------
# Gate node
# ---------------------------------------------------------------------------

class TestDispatchGate:
    def test_gate_proceed_returns_done(self):
        rt = _MockRuntime()
        node = IRNode(id="g-scout", kind="gate", data={"checks": [{"type": "schema"}]})
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "done"
        assert outcome.gate is not None
        assert outcome.gate["decision"] == "proceed"
        assert outcome.fields == {"decision": "proceed"}

    def test_gate_needs_fix_still_done(self):
        """Gate node returns status=done regardless of gate decision."""
        rt = _MockRuntime()
        rt.set_gate_result(GateResult(decision="needs_fix", errors=["fail"]))
        node = IRNode(id="g", kind="gate")
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "done"
        assert outcome.gate["decision"] == "needs_fix"

    def test_gate_id_passed(self):
        rt = _MockRuntime()
        node = IRNode(id="g-review", kind="gate", data={})
        dispatch_node(node, {}, rt, _empty_state())
        gate_config, _ = rt.gate_calls[0]
        assert gate_config["id"] == "g-review"


# ---------------------------------------------------------------------------
# Human node
# ---------------------------------------------------------------------------

class TestDispatchHuman:
    def test_human_returns_blocked(self):
        rt = _MockRuntime()
        node = IRNode(id="release", kind="human", data={"prompt": "Release?"})
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "blocked"

    def test_human_calls_escalate(self):
        rt = _MockRuntime()
        node = IRNode(id="signoff", kind="human", data={"prompt": "OK?"})
        dispatch_node(node, {}, rt, _empty_state())
        assert len(rt.escalated) == 1
        node_id, reason = rt.escalated[0]
        assert node_id == "signoff"
        assert "OK?" in reason


# ---------------------------------------------------------------------------
# Decision node
# ---------------------------------------------------------------------------

class TestDispatchDecision:
    def test_decision_returns_done_no_call(self):
        rt = _MockRuntime()
        node = IRNode(id="dec", kind="decision")
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "done"
        # No external calls made.
        assert rt.dispatched == []
        assert rt.gate_calls == []
        assert rt.escalated == []


# ---------------------------------------------------------------------------
# Wait node
# ---------------------------------------------------------------------------

class TestDispatchWait:
    def test_wait_human_blocks(self):
        rt = _MockRuntime()
        node = IRNode(id="wt", kind="wait", data={"mode": "human", "prompt": "Wait."})
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "blocked"
        assert len(rt.escalated) == 1

    def test_wait_timed_escalates(self):
        rt = _MockRuntime()
        node = IRNode(id="wt", kind="wait", data={"mode": "timed", "max_wait_seconds": 30})
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "escalated"
        assert len(rt.escalated) == 1

    def test_wait_default_mode_is_human(self):
        rt = _MockRuntime()
        node = IRNode(id="wt", kind="wait")  # no mode specified
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "blocked"


# ---------------------------------------------------------------------------
# Aggregator node
# ---------------------------------------------------------------------------

class TestDispatchAggregator:
    def test_aggregator_all_done(self):
        state = _empty_state()
        state.nodes["a"] = NodeState(status="done")
        state.nodes["b"] = NodeState(status="done")
        rt = _MockRuntime()
        node = IRNode(id="agg", kind="aggregator", data={"mode": "all", "inputs": {"from": ["a", "b"]}})
        outcome = dispatch_node(node, {}, rt, state)
        assert outcome.status == "done"

    def test_aggregator_all_one_failed(self):
        state = _empty_state()
        state.nodes["a"] = NodeState(status="done")
        state.nodes["b"] = NodeState(status="failed")
        rt = _MockRuntime()
        node = IRNode(id="agg", kind="aggregator", data={"mode": "all", "inputs": {"from": ["a", "b"]}})
        outcome = dispatch_node(node, {}, rt, state)
        assert outcome.status == "failed"

    def test_aggregator_any_one_done(self):
        state = _empty_state()
        state.nodes["a"] = NodeState(status="failed")
        state.nodes["b"] = NodeState(status="done")
        rt = _MockRuntime()
        node = IRNode(id="agg", kind="aggregator", data={"mode": "any", "inputs": {"from": ["a", "b"]}})
        outcome = dispatch_node(node, {}, rt, state)
        assert outcome.status == "done"

    def test_aggregator_any_all_failed(self):
        state = _empty_state()
        state.nodes["a"] = NodeState(status="failed")
        state.nodes["b"] = NodeState(status="failed")
        rt = _MockRuntime()
        node = IRNode(id="agg", kind="aggregator", data={"mode": "any", "inputs": {"from": ["a", "b"]}})
        outcome = dispatch_node(node, {}, rt, state)
        assert outcome.status == "failed"

    def test_aggregator_no_preds_done(self):
        rt = _MockRuntime()
        node = IRNode(id="agg", kind="aggregator", data={})
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "done"


# ---------------------------------------------------------------------------
# Trigger node
# ---------------------------------------------------------------------------

class TestDispatchTrigger:
    def test_trigger_immediate_done(self):
        rt = _MockRuntime()
        node = IRNode(id="start", kind="trigger")
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "done"
        assert rt.dispatched == []
        assert rt.gate_calls == []

    def test_trigger_attempt_incremented(self):
        rt = _MockRuntime()
        state = _empty_state()
        state.nodes["start"] = NodeState(status="done", attempt=0)
        node = IRNode(id="start", kind="trigger")
        outcome = dispatch_node(node, {}, rt, state)
        assert outcome.attempt == 1


# ---------------------------------------------------------------------------
# Unknown kind
# ---------------------------------------------------------------------------

class TestDispatchUnknownKind:
    def test_unknown_kind_returns_failed(self):
        rt = _MockRuntime()
        node = IRNode(id="x", kind="agent")  # type: ignore[arg-type]
        # Manually override kind to something invalid.
        object.__setattr__(node, "kind", "totally-unknown")
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "failed"


# ---------------------------------------------------------------------------
# Exec node (P1 Embodiment A)
# ---------------------------------------------------------------------------

class TestDispatchExec:
    def test_exec_done_returns_done_with_artifact(self):
        rt = _MockRuntime()
        node = IRNode(
            id="testrun", kind="exec",
            data={"command": "python -m pytest", "produces": {"class": "test"}},
        )
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "done"
        assert outcome.artifact_paths == ["out/testrun-output.md"]
        # The command and node id are forwarded to runExec.
        node_id, command, inputs = rt.exec_calls[0]
        assert node_id == "testrun"
        assert command == "python -m pytest"
        assert inputs["fail_on_nonzero"] is True

    def test_exec_failed_status_maps_to_failed(self):
        rt = _MockRuntime()
        rt.set_exec_result(ExecResult(status="failed", exit_code=1, artifact_path="out/o.md"))
        node = IRNode(id="build", kind="exec", data={"command": "make"})
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "failed"
        assert outcome.fields == {"exit_code": 1}

    def test_exec_missing_command_fails_without_dispatch(self):
        rt = _MockRuntime()
        node = IRNode(id="n", kind="exec", data={})
        outcome = dispatch_node(node, {}, rt, _empty_state())
        assert outcome.status == "failed"
        assert not hasattr(rt, "exec_calls")

    def test_exec_fail_on_nonzero_flag_forwarded(self):
        rt = _MockRuntime()
        node = IRNode(
            id="testrun", kind="exec",
            data={"command": "pytest", "fail_on_nonzero": False},
        )
        dispatch_node(node, {}, rt, _empty_state())
        _, _, inputs = rt.exec_calls[0]
        assert inputs["fail_on_nonzero"] is False
