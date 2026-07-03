import pytest

from delivery_workflow.events import NullHost, RunBlocked
from delivery_workflow.interface import (
    ExecutorInterface,
    HostPort,
    NodeExecutor,
    StateOps,
    TelemetryOps,
)
from delivery_workflow.null_runtime import NullRuntime
from delivery_workflow.results import AgentResult, GateResult, TelemetryData
from delivery_workflow.state_types import BudgetState, NodeState, WorkflowState


# ---------------------------------------------------------------------------
# R5 — isinstance / Protocol conformance
# ---------------------------------------------------------------------------


def test_null_runtime_satisfies_executor_interface():
    runtime = NullRuntime()
    assert isinstance(runtime, NodeExecutor)
    # Deprecated alias kept one release (R10b) — same protocol object.
    assert ExecutorInterface is NodeExecutor


def test_null_host_satisfies_host_port():
    host = NullHost()
    assert isinstance(host, HostPort)
    # Swallows every event without effect.
    host.on_event(RunBlocked(node_id="signoff", question="ok?"))


def test_null_state_satisfies_state_ops():
    assert isinstance(NullRuntime().state, StateOps)


def test_null_telemetry_satisfies_telemetry_ops():
    assert isinstance(NullRuntime().telemetry, TelemetryOps)


# ---------------------------------------------------------------------------
# R5 — every op raises NotImplementedError
# ---------------------------------------------------------------------------


def test_dispatch_agent_raises():
    with pytest.raises(NotImplementedError):
        NullRuntime().dispatchAgent("scout", {})


def test_run_gate_raises():
    with pytest.raises(NotImplementedError):
        NullRuntime().runGate({"type": "schema"}, [])


def test_eval_condition_and_escalate_left_the_executor_surface():
    """R10b port split: condition evaluation is runner-internal and host
    notification is HostPort.on_event — NodeExecutor stubs carry neither."""
    assert not hasattr(NullRuntime, "evalCondition")
    assert not hasattr(NullRuntime, "escalate")


def test_state_read_raises():
    with pytest.raises(NotImplementedError):
        NullRuntime().state.read()


def test_state_write_raises():
    with pytest.raises(NotImplementedError):
        NullRuntime().state.write({})


def test_telemetry_emit_raises():
    with pytest.raises(NotImplementedError):
        NullRuntime().telemetry.emit("scout", {"tokens": 100.0, "usd": 0.01, "seconds": 5.0})


# ---------------------------------------------------------------------------
# Result and state dataclasses
# ---------------------------------------------------------------------------


def test_telemetry_data_fields():
    t = TelemetryData(tokens=1000, usd=0.5, seconds=30.0)
    assert t.tokens == 1000
    assert t.usd == 0.5
    assert t.seconds == 30.0


def test_agent_result_construction():
    result = AgentResult(
        status="done",
        artifact_paths=["path/to/report.md"],
        produces="research",
        fields={"has_ui": False},
        open_questions=[],
        telemetry=TelemetryData(tokens=100, usd=0.01, seconds=5.0),
    )
    assert result.status == "done"
    assert result.produces == "research"
    assert result.telemetry.tokens == 100


def test_gate_result_construction():
    result = GateResult(decision="proceed", errors=[], evidence={"checks_passed": 2})
    assert result.decision == "proceed"
    assert result.evidence["checks_passed"] == 2


def test_gate_result_default_evidence():
    result = GateResult(decision="needs_fix", errors=["schema mismatch"])
    assert result.evidence == {}


def test_budget_state_defaults():
    b = BudgetState(usd_ceiling=25.0)
    assert b.usd_spent == 0.0


def test_budget_state_explicit_spent():
    b = BudgetState(usd_ceiling=25.0, usd_spent=4.31)
    assert b.usd_spent == 4.31


def test_node_state_defaults():
    node = NodeState(status="running")
    assert node.attempt == 0
    assert node.gate is None
    assert node.artifact_paths == []
    assert node.telemetry is None


def test_node_state_full():
    node = NodeState(
        status="looping",
        attempt=2,
        gate={"decision": "needs_fix", "errors": []},
        artifact_paths=["report.md"],
        telemetry={"tokens": 41233.0, "usd": 0.62, "seconds": 88.0},
    )
    assert node.attempt == 2
    assert node.gate is not None


def test_workflow_state_empty_nodes():
    state = WorkflowState(
        spec="delivery/v1",
        run_id="abc123",
        status="running",
        budget=BudgetState(usd_ceiling=25.0),
    )
    assert state.nodes == {}
    assert state.spec == "delivery/v1"


def test_workflow_state_with_nodes():
    state = WorkflowState(
        spec="delivery/v1",
        run_id="run-001",
        status="done",
        budget=BudgetState(usd_ceiling=10.0, usd_spent=3.5),
        nodes={"scout": NodeState(status="done")},
    )
    assert "scout" in state.nodes
    assert state.nodes["scout"].status == "done"
