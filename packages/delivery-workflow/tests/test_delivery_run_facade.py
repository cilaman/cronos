"""R10b — DeliveryRun facade, Outcome taxonomy, RunEvent grammar, cancel().

Pins the §2.2 boundary contract:
- hosts call ONLY the facade (start / resume / outcome / cancel) and receive
  the closed ``Outcome`` taxonomy;
- the runner notifies the host through typed ``RunEvent``s (HostPort);
- ``cancel()`` writes the previously-phantom ``cancelled`` status, it
  round-trips persistence, ``outcome()`` reports it, ``resume()`` refuses it
  and ``start()`` seals it (no dispatch);
- the top-level package exports the whole host surface.
"""
from __future__ import annotations

from typing import Any

import pytest

import delivery_workflow as dw
from delivery_workflow import (
    DeliveryRun,
    HumanAnswer,
    NodeFinished,
    NodeStarted,
    Outcome,
    ResumeError,
    RunBlocked,
    RunStalled,
    outcome_from_state,
)
from delivery_workflow.ir import IREdge, IRGraph, IRNode
from delivery_workflow.results import AgentResult, TelemetryData
from delivery_workflow.state_types import BudgetState, NodeState, WorkflowState


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class MemStateOps:
    """Minimal in-memory StateOps obeying the §5.4 write semantics."""

    def __init__(self, initial: WorkflowState | None = None) -> None:
        self._state = initial or WorkflowState(
            spec="facade-test",
            run_id="run-facade",
            status="running",
            budget=BudgetState(usd_ceiling=0.0),
        )

    def read(self) -> WorkflowState:
        return self._state

    def write(self, patch: dict[str, Any]) -> None:
        s = self._state
        if "status" in patch:
            s.status = patch["status"]
        if "edges_evaluated" in patch:
            s.edges_evaluated = dict(patch["edges_evaluated"] or {})
        if "stall" in patch:
            s.stall = patch["stall"]
        if "resume_retries" in patch:
            s.resume_retries = dict(patch["resume_retries"] or {})
        if "budget" in patch and isinstance(patch["budget"], dict):
            if "usd_ceiling" in patch["budget"]:
                s.budget.usd_ceiling = float(patch["budget"]["usd_ceiling"])
        for nid, np in (patch.get("nodes") or {}).items():
            ns = s.nodes.get(nid)
            if ns is None:
                ns = NodeState(status=np.get("status", "pending"))
                s.nodes[nid] = ns
            if "status" in np:
                ns.status = np["status"]
            if "attempt" in np:
                ns.attempt = int(np["attempt"])
            if "artifact_paths" in np:
                ns.artifact_paths = list(np["artifact_paths"])
            if "gate" in np:
                ns.gate = np["gate"]
            if "fields" in np:
                ns.fields = dict(np["fields"])


class RecordingHost:
    def __init__(self) -> None:
        self.events: list[Any] = []

    def on_event(self, event: Any) -> None:
        self.events.append(event)


class OkExecutor:
    """NodeExecutor: every agent succeeds with the scripted fields."""

    def __init__(self, fields_by_node: dict[str, dict[str, Any]] | None = None) -> None:
        self.dispatched: list[str] = []
        self._fields = fields_by_node or {}

    def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult:
        node_id = inputs["node_id"]
        self.dispatched.append(node_id)
        return AgentResult(
            status="done",
            artifact_paths=[],
            produces="",
            fields=dict(self._fields.get(node_id, {})),
            open_questions=[],
            telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
        )

    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]):
        raise NotImplementedError

    def runExec(self, node_id: str, command: str, inputs: dict[str, Any]):
        raise NotImplementedError


def _node(nid: str, kind: str = "agent", **data: Any) -> IRNode:
    return IRNode(id=nid, kind=kind, data=data)


def _linear_graph() -> IRGraph:
    """a → sign (human, prompt) → b."""
    return IRGraph(
        nodes=[
            _node("a"),
            _node("sign", kind="human", prompt="ship it?"),
            _node("b"),
        ],
        edges=[
            IREdge(source="a", target="sign", when="", port=None),
            IREdge(source="sign", target="b", when="", port=None),
        ],
        metadata={"name": "facade-spec"},
        variables={},
    )


def _agents_only_graph() -> IRGraph:
    return IRGraph(
        nodes=[_node("a"), _node("b")],
        edges=[IREdge(source="a", target="b", when="", port=None)],
        metadata={"name": "facade-spec"},
        variables={},
    )


# ---------------------------------------------------------------------------
# Facade lifecycle
# ---------------------------------------------------------------------------


class TestFacadeLifecycle:
    def test_start_returns_done_outcome(self):
        ops = MemStateOps()
        run = DeliveryRun(_agents_only_graph(), executor=OkExecutor(), state_ops=ops)
        outcome = run.start()
        assert isinstance(outcome, Outcome)
        assert outcome.kind == "done"
        assert outcome.is_terminal
        assert ops.read().status == "done"

    def test_park_resume_via_facade(self):
        ops = MemStateOps()
        executor = OkExecutor()
        host = RecordingHost()
        run = DeliveryRun(_linear_graph(), executor=executor, state_ops=ops, host=host)

        parked = run.start()
        assert parked.kind == "blocked"
        assert parked.node_id == "sign"
        assert parked.question == "ship it?"

        # outcome() is a pure read — same Outcome, no dispatch.
        before = list(executor.dispatched)
        assert run.outcome() == parked
        assert executor.dispatched == before

        done = run.resume(HumanAnswer(node_id="sign", text="yes", verdict="approve"))
        assert done.kind == "done"
        assert executor.dispatched == ["a", "b"]

    def test_host_receives_typed_events(self):
        ops = MemStateOps()
        host = RecordingHost()
        run = DeliveryRun(
            _linear_graph(), executor=OkExecutor(), state_ops=ops, host=host
        )
        run.start()

        kinds = [type(e).__name__ for e in host.events]
        assert kinds[:2] == ["NodeStarted", "NodeFinished"]  # node a
        blocked = [e for e in host.events if isinstance(e, RunBlocked)]
        assert blocked == [RunBlocked(node_id="sign", question="ship it?")]
        started = [e for e in host.events if isinstance(e, NodeStarted)]
        assert started[0] == NodeStarted(node_id="a", attempt=1)
        finished = [e for e in host.events if isinstance(e, NodeFinished)]
        assert finished[0] == NodeFinished(node_id="a", status="done")
        # The parked human node also persists a NodeFinished(blocked).
        assert NodeFinished(node_id="sign", status="blocked") in finished

    def test_raising_host_never_breaks_the_run(self):
        class ExplodingHost:
            def on_event(self, event: Any) -> None:
                raise RuntimeError("host bug")

        ops = MemStateOps()
        run = DeliveryRun(
            _agents_only_graph(),
            executor=OkExecutor(),
            state_ops=ops,
            host=ExplodingHost(),
        )
        assert run.start().kind == "done"

    def test_spec_path_constructor_loads_and_compiles(self):
        from tests.conformance.harness import SPEC_PATH

        run = DeliveryRun(
            SPEC_PATH, executor=OkExecutor(), state_ops=MemStateOps()
        )
        assert {n.id for n in run.graph.nodes} >= {"scout", "signoff-scope"}

    def test_state_ops_required(self):
        with pytest.raises(ValueError):
            DeliveryRun(_agents_only_graph(), executor=OkExecutor(), state_ops=None)


# ---------------------------------------------------------------------------
# cancel() — the previously-phantom status becomes real (R11 recommendation)
# ---------------------------------------------------------------------------


class TestCancel:
    def test_cancel_round_trips_and_outcome_reports_it(self):
        ops = MemStateOps()
        run = DeliveryRun(_linear_graph(), executor=OkExecutor(), state_ops=ops)
        assert run.start().kind == "blocked"

        cancelled = run.cancel()
        assert cancelled.kind == "cancelled"
        assert ops.read().status == "cancelled"          # persisted
        assert run.outcome().kind == "cancelled"         # pure read reports it

    def test_cancelled_is_sealed_for_start(self):
        ops = MemStateOps()
        executor = OkExecutor()
        run = DeliveryRun(_linear_graph(), executor=executor, state_ops=ops)
        run.start()
        run.cancel()
        before = list(executor.dispatched)
        sealed = run.start()
        assert sealed.kind == "cancelled"
        assert executor.dispatched == before, "start() dispatched work on a cancelled run"

    def test_resume_refuses_cancelled(self):
        ops = MemStateOps()
        run = DeliveryRun(_linear_graph(), executor=OkExecutor(), state_ops=ops)
        run.start()
        run.cancel()
        with pytest.raises(ResumeError, match="cancelled"):
            run.resume(HumanAnswer(node_id="sign", text="yes", verdict="approve"))

    def test_cancel_is_idempotent(self):
        ops = MemStateOps()
        run = DeliveryRun(_linear_graph(), executor=OkExecutor(), state_ops=ops)
        run.start()
        assert run.cancel().kind == "cancelled"
        assert run.cancel().kind == "cancelled"

    def test_cancel_refused_on_done(self):
        ops = MemStateOps()
        run = DeliveryRun(_agents_only_graph(), executor=OkExecutor(), state_ops=ops)
        assert run.start().kind == "done"
        with pytest.raises(ResumeError, match="completed"):
            run.cancel()
        assert ops.read().status == "done"


# ---------------------------------------------------------------------------
# Outcome derivation (pure)
# ---------------------------------------------------------------------------


def _state(status: str, **nodes: NodeState) -> WorkflowState:
    return WorkflowState(
        spec="s", run_id="r", status=status,  # type: ignore[arg-type]
        budget=BudgetState(usd_ceiling=0.0), nodes=dict(nodes),
    )


class TestOutcomeFromState:
    def test_done_cancelled_running(self):
        assert outcome_from_state(_state("done")).kind == "done"
        assert outcome_from_state(_state("cancelled")).kind == "cancelled"
        running = outcome_from_state(_state("running"))
        assert running.kind == "running"
        assert not running.is_terminal

    def test_stalled_carries_record(self):
        s = _state("stalled")
        s.stall = {"kind": "gate_exhausted", "nodes": ["g-build"], "reason": "boom"}
        o = outcome_from_state(s)
        assert o.kind == "stalled"
        assert o.node_id == "g-build"
        assert o.reason == "boom"
        assert o.stall == s.stall

    def test_failed_pins_node_and_reason(self):
        o = outcome_from_state(_state(
            "failed",
            impl=NodeState(status="failed", fields={"error": "exit -9"}),
        ))
        assert o == Outcome(kind="failed", node_id="impl", reason="exit -9")

    def test_blocked_prefers_human_node_with_graph(self):
        graph = _linear_graph()
        s = _state(
            "blocked",
            sign=NodeState(status="blocked", fields={"prompt": "ship it?"}),
        )
        o = outcome_from_state(s, graph)
        assert o.kind == "blocked"
        assert o.node_id == "sign"
        assert o.question == "ship it?"

    def test_blocked_on_agent_yields_no_signoff_target_with_graph(self):
        graph = _agents_only_graph()
        s = _state("blocked", a=NodeState(status="blocked"))
        o = outcome_from_state(s, graph)
        # No human node is parked — hosts must not offer Approve/Reject; the
        # graph-less fallback (state only) still pins the blocked node.
        assert o.kind == "blocked"
        assert o.node_id is None
        assert outcome_from_state(s).node_id == "a"

    def test_escalated_discriminates_timed_wait_and_loop(self):
        timed = outcome_from_state(_state(
            "escalated", w=NodeState(status="escalated", fields={"mode": "timed"}),
        ))
        assert timed.kind == "escalated"
        assert timed.escalation == "timed_wait"
        assert timed.node_id == "w"

        loop = outcome_from_state(_state(
            "escalated", review=NodeState(status="escalated"),
        ))
        assert loop.escalation == "loop"
        assert loop.node_id == "review"

        cap = outcome_from_state(_state("escalated"))
        assert cap.escalation == "iteration_cap"
        assert cap.node_id is None

    def test_unknown_status_never_guesses_success(self):
        o = outcome_from_state(_state("banana"))
        assert o.kind == "failed"
        assert "banana" in (o.reason or "")


# ---------------------------------------------------------------------------
# Top-level exports (§2.2 acceptance: package exports DeliveryRun + Outcome +
# events from the delivery_workflow top level)
# ---------------------------------------------------------------------------


def test_top_level_exports_cover_the_host_surface():
    for name in (
        "DeliveryRun", "Outcome", "outcome_from_state",
        "NodeStarted", "NodeFinished", "RunBlocked", "RunStalled",
        "RunFailed", "RunEscalated", "RunEvent", "NullHost",
        "NodeExecutor", "HostPort", "StateOps",
        "HumanAnswer", "RetryFailed", "RaiseBudget", "Nothing", "ResumeError",
    ):
        assert hasattr(dw, name), f"delivery_workflow must export {name}"
        assert name in dw.__all__


def test_runner_has_no_executor_evalcondition_or_escalate():
    """Acceptance grep, executable: no executor.evalCondition / executor.escalate
    remains anywhere in the runner (condition evaluation is runner-internal;
    host notification is HostPort.on_event)."""
    from pathlib import Path

    import delivery_workflow.runner as runner_pkg

    runner_dir = Path(runner_pkg.__file__).resolve().parent
    offenders: list[str] = []
    for path in sorted(runner_dir.glob("*.py")):
        text = path.read_text()
        for needle in ("executor.evalCondition", "executor.escalate"):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert offenders == []


def test_run_stalled_event_carries_detail():
    """A completeness stall emits RunStalled with the machine-readable record."""
    ops = MemStateOps()
    host = RecordingHost()
    # a routes nowhere: its only out-edge condition is false → dead-end → stalled.
    graph = IRGraph(
        nodes=[_node("a"), _node("b")],
        edges=[IREdge(source="a", target="b", when="a.fields.go == yes", port=None)],
        metadata={"name": "stall-spec"},
        variables={},
    )
    run = DeliveryRun(
        graph, executor=OkExecutor({"a": {"go": "no"}}), state_ops=ops, host=host
    )
    outcome = run.start()
    assert outcome.kind == "stalled"
    stalled = [e for e in host.events if isinstance(e, RunStalled)]
    assert len(stalled) == 1
    assert stalled[0].detail == outcome.stall
    assert outcome.stall["kind"] == "starved_nodes"
