"""R9 regression tests — single writer per node field (kills D11).

Defect (00-assessment.md §2 D11): gate node status was written TWICE with
conflicting values — the adapter wrote ``done``/``needs_fix`` out-of-band
inside ``runGate`` (adapter.py) and the runner then unconditionally overwrote
with ``done`` (runner/dispatch.py + core.py).  The event log recorded a
phantom ``needs_fix→done`` transition, ``needs_fix`` was unreachable in final
state via the runner path, and the driver had to dig gate decisions out of
node internals (the basis of the deleted stalled-gate workaround).

Contract (01-state-model.md §5.1 + §5.8, 03-remediation-plan.md §R9):
  1. Node ``status/attempt/artifact_paths/gate/fields`` are written ONLY by
     the runner through StateOps.  ``CronosAdapter.runGate``/``runExec``
     return GateResult/ExecResult and perform ZERO StateOps writes.
  2. A gate's non-proceed decision is written once, by the runner, as the
     REAL node status ``needs_fix`` with the decision detail in ``gate``.
  3. Event-log honesty (the acceptance): a failing gate produces EXACTLY ONE
     node transition (→needs_fix) — no phantom needs_fix→done.  A full
     fix-loop cycle reads ``needs_fix → pending (reset) → done`` — real
     transitions only.
  4. ``lib.gate._write_gate_result`` stays available for standalone CLI use
     but is never combined with a runner-managed state.json (the adapter does
     not pass ``state_path``).

Zero app imports — this suite runs on the bare package.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

_PKG = Path(__file__).parent.parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

import runner as workflow_runner  # noqa: E402
from adapters.cronos.adapter import CronosAdapter, CronosStateOps  # noqa: E402
from ir import IREdge, IRGraph, IRNode, LoopPolicy  # noqa: E402
from lib.state.events import EventLog  # noqa: E402
from lib.state.store import StateStore  # noqa: E402
from results import AgentResult, GateResult, TelemetryData  # noqa: E402
from state_types import BudgetState, WorkflowState  # noqa: E402


# ---------------------------------------------------------------------------
# Test doubles.
# ---------------------------------------------------------------------------


def _agent_done(**fields: Any) -> AgentResult:
    return AgentResult(
        status="done",
        artifact_paths=[],
        produces="",
        fields=dict(fields),
        open_questions=[],
        telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
    )


class RecordingExecutor:
    """Scripted ExecutorInterface; gate script entries may be lists (FIFO)."""

    def __init__(
        self,
        agent_script: dict[str, Any] | None = None,
        gate_script: dict[str, Any] | None = None,
    ) -> None:
        self.dispatched: list[str] = []
        self.escalations: list[tuple[str, str]] = []
        self._agent_script = dict(agent_script or {})
        self._gate_script = dict(gate_script or {})
        self.state = None
        self.telemetry = self

    def emit(self, node_id: str, data: dict) -> None:  # TelemetryOps
        pass

    def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult:
        node_id = inputs["node_id"]
        self.dispatched.append(node_id)
        entry = self._agent_script.get(node_id)
        if isinstance(entry, list):
            return copy.deepcopy(entry[0] if len(entry) == 1 else entry.pop(0))
        return copy.deepcopy(entry) if entry is not None else _agent_done()

    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult:
        node_id = gate["id"]
        self.dispatched.append(node_id)
        entry = self._gate_script.get(node_id)
        if isinstance(entry, list):
            return copy.deepcopy(entry[0] if len(entry) == 1 else entry.pop(0))
        if entry is not None:
            return copy.deepcopy(entry)
        return GateResult(decision="proceed", errors=[])

    def runExec(self, node_id: str, command: str, inputs: dict[str, Any]):
        from results import ExecResult

        self.dispatched.append(node_id)
        return ExecResult(
            status="done", exit_code=0, artifact_path=f"/tmp/{node_id}-output.md"
        )

    def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool:
        from lib.conditions import eval_condition

        return eval_condition(expr, scope)

    def escalate(self, node_id: str, reason: str) -> None:
        self.escalations.append((node_id, reason))
        if self.state is not None:
            self.state.write({"status": "blocked"})


class SpyStateOps:
    """StateOps proxy recording every write() patch verbatim."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.writes: list[dict[str, Any]] = []

    def read(self) -> WorkflowState:
        return self._inner.read()

    def write(self, patch: dict[str, Any]) -> None:
        self.writes.append(copy.deepcopy(patch))
        self._inner.write(patch)


def _node(nid: str, kind: str = "agent", data: dict | None = None, loop=None) -> IRNode:
    return IRNode(id=nid, kind=kind, data=data or {}, loop=loop)


def _state_ops(tmp_path: Path) -> CronosStateOps:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    ops = CronosStateOps(StateStore(run_dir), EventLog(run_dir))
    ops.bootstrap_if_absent(spec="r9", run_id="run-r9", usd_ceiling=0.0)
    return ops


def _gate_fix_loop_graph(max_iter: int = 3) -> IRGraph:
    """producer → gate(loop max) → sink | gate → producer on non-proceed."""
    return IRGraph(
        nodes=[
            _node("producer"),
            _node(
                "gate", kind="gate", data={"checks": []},
                loop=LoopPolicy(
                    until="gate.decision == 'proceed'",
                    max=max_iter, on_exhaust="escalate", stall=[],
                ),
            ),
            _node("sink"),
        ],
        edges=[
            IREdge(source="producer", target="gate", when="", port=None),
            IREdge(source="gate", target="sink",
                   when="gate.decision == 'proceed'", port=None),
            IREdge(source="gate", target="producer",
                   when="gate.decision != 'proceed'", port=None),
        ],
        metadata={}, variables={},
    )


def _gate_transitions(run_dir: Path, node_id: str = "gate") -> list[str]:
    return [
        e["status"]
        for e in EventLog(run_dir).read_all()
        if e.get("type") == "node_transition" and e.get("node_id") == node_id
    ]


# ---------------------------------------------------------------------------
# 1. Event-log honesty (the R9 acceptance).
# ---------------------------------------------------------------------------


class TestEventLogHonesty:
    def test_failing_gate_logs_exactly_one_transition(self, tmp_path):
        """A gate whose decision never proceeds transitions →needs_fix exactly
        once per evaluation — no phantom needs_fix→done overwrite (D11)."""
        g = IRGraph(
            nodes=[_node("producer"), _node("gate", kind="gate", data={"checks": []})],
            edges=[IREdge(source="producer", target="gate", when="", port=None)],
            metadata={}, variables={},
        )
        ops = _state_ops(tmp_path)
        ex = RecordingExecutor(
            gate_script={"gate": GateResult(decision="needs_fix", errors=["bad"])},
        )
        ex.state = ops
        state = workflow_runner.run(graph=g, executor=ex, state_ops=ops)

        assert _gate_transitions(tmp_path / "run") == ["needs_fix"], (
            "the event log for a failing gate must contain EXACTLY ONE "
            "transition (→needs_fix); a trailing 'done' is the D11 phantom"
        )
        assert state.nodes["gate"].status == "needs_fix"
        assert state.nodes["gate"].gate["decision"] == "needs_fix"

    def test_fix_loop_cycle_logs_real_transitions_only(self, tmp_path):
        """Full fix cycle: gate needs_fix → fix edge resets the gate (pending)
        → re-run proceeds (done).  The event log reads exactly that."""
        ops = _state_ops(tmp_path)
        ex = RecordingExecutor(
            gate_script={"gate": [
                GateResult(decision="needs_fix", errors=["fix me"]),
                GateResult(decision="proceed", errors=[]),
            ]},
        )
        ex.state = ops
        state = workflow_runner.run(
            graph=_gate_fix_loop_graph(3), executor=ex, state_ops=ops
        )

        assert state.status == "done"
        assert state.nodes["gate"].status == "done"
        assert _gate_transitions(tmp_path / "run") == [
            "needs_fix",  # first evaluation: non-proceed IS the node status
            "pending",    # fix edge fired → back-edge reset (R8 path)
            "done",       # re-run after the producer's fix: proceed
        ], "a fix-loop cycle must read needs_fix → pending → done — real transitions only"

    def test_proceeding_gate_logs_single_done(self, tmp_path):
        ops = _state_ops(tmp_path)
        ex = RecordingExecutor()
        ex.state = ops
        state = workflow_runner.run(
            graph=_gate_fix_loop_graph(3), executor=ex, state_ops=ops
        )
        assert state.status == "done"
        assert _gate_transitions(tmp_path / "run") == ["done"]

    def test_exhausted_gate_final_status_is_needs_fix(self, tmp_path):
        """After gate fix-loop exhaustion the run stalls (R6) and the gate's
        persisted status is the honest terminal `needs_fix` — pre-R9 it read
        `done` while the run claimed the gate had failed."""
        ops = _state_ops(tmp_path)
        ex = RecordingExecutor(
            gate_script={"gate": GateResult(decision="needs_fix", errors=["still bad"])},
        )
        ex.state = ops
        state = workflow_runner.run(
            graph=_gate_fix_loop_graph(2), executor=ex, state_ops=ops
        )

        assert state.status == "stalled"
        assert state.stall["kind"] == "gate_exhausted"
        assert state.nodes["gate"].status == "needs_fix"
        persisted = ops.read()
        assert persisted.nodes["gate"].status == "needs_fix"
        # Two evaluations (max=2): needs_fix, reset, needs_fix — never 'done'.
        assert _gate_transitions(tmp_path / "run") == [
            "needs_fix", "pending", "needs_fix",
        ]


# ---------------------------------------------------------------------------
# 2. The runner is the single writer of node fields.
# ---------------------------------------------------------------------------


class TestRunnerSingleWriter:
    def test_gate_node_fields_written_once_per_evaluation(self, tmp_path):
        """Exactly one StateOps node write per gate evaluation, carrying
        status + gate detail together — never two writes for one outcome."""
        g = IRGraph(
            nodes=[_node("producer"), _node("gate", kind="gate", data={"checks": []})],
            edges=[IREdge(source="producer", target="gate", when="", port=None)],
            metadata={}, variables={},
        )
        spy = SpyStateOps(_state_ops(tmp_path))
        ex = RecordingExecutor(
            gate_script={"gate": GateResult(decision="needs_fix", errors=["bad"])},
        )
        ex.state = spy
        workflow_runner.run(graph=g, executor=ex, state_ops=spy)

        gate_node_writes = [
            p["nodes"]["gate"] for p in spy.writes if "gate" in p.get("nodes", {})
        ]
        assert len(gate_node_writes) == 1, (
            f"gate node written {len(gate_node_writes)}× for one evaluation: "
            f"{gate_node_writes!r}"
        )
        write = gate_node_writes[0]
        assert write["status"] == "needs_fix"
        assert write["gate"]["decision"] == "needs_fix"
        assert write["fields"] == {"decision": "needs_fix"}

    def test_exec_node_fields_written_once(self, tmp_path):
        """The exec node's status/artifact_paths/exit_code are persisted by
        exactly one runner write, built from the returned ExecResult (the
        adapter's own runExec write is deleted — R9)."""
        g = IRGraph(
            nodes=[_node("testrun", kind="exec", data={"command": "echo ok"})],
            edges=[],
            metadata={}, variables={},
        )
        spy = SpyStateOps(_state_ops(tmp_path))
        ex = RecordingExecutor()
        ex.state = spy
        state = workflow_runner.run(graph=g, executor=ex, state_ops=spy)

        assert state.status == "done"
        exec_writes = [
            p["nodes"]["testrun"] for p in spy.writes if "testrun" in p.get("nodes", {})
        ]
        assert len(exec_writes) == 1, (
            f"exec node written {len(exec_writes)}× for one run: {exec_writes!r}"
        )
        write = exec_writes[0]
        assert write["status"] == "done"
        assert write["artifact_paths"] == ["/tmp/testrun-output.md"]
        assert write["fields"] == {"exit_code": 0}
        transitions = _gate_transitions(tmp_path / "run", node_id="testrun")
        assert transitions == ["done"], (
            f"exec node event log must show one real transition, got {transitions!r}"
        )

    def test_needs_fix_gate_decision_routes_fix_edge(self, tmp_path):
        """The needs_fix node status keeps routing: the fix edge fires off the
        gate decision in scope, the producer re-runs, and the loop/join
        arithmetic (R8 reset path) is undisturbed."""
        ops = _state_ops(tmp_path)
        ex = RecordingExecutor(
            gate_script={"gate": [
                GateResult(decision="needs_fix", errors=["fix me"]),
                GateResult(decision="proceed", errors=[]),
            ]},
        )
        ex.state = ops
        state = workflow_runner.run(
            graph=_gate_fix_loop_graph(3), executor=ex, state_ops=ops
        )

        assert state.status == "done"
        assert ex.dispatched == ["producer", "gate", "producer", "gate", "sink"]
        assert state.nodes["gate"].attempt == 2


# ---------------------------------------------------------------------------
# 3. Adapter returns results ONLY — zero StateOps writes in runGate/runExec.
# ---------------------------------------------------------------------------


class TestAdapterReturnsOnly:
    def _adapter(self, tmp_path: Path) -> tuple[CronosAdapter, SpyStateOps]:
        space_dir = tmp_path / "space"
        run_dir = space_dir / ".cronos" / "delivery-runs" / "g1"
        run_dir.mkdir(parents=True)
        StateStore(run_dir).write(WorkflowState(
            spec="r9", run_id="run-r9", status="running",
            budget=BudgetState(usd_ceiling=0.0),
        ))
        adapter = CronosAdapter(
            store=object(),
            trace_store=object(),
            space_id="s1",
            run_dir=run_dir,
            space_dir=space_dir,
        )
        spy = SpyStateOps(adapter.state)
        adapter.state = spy
        return adapter, spy

    def test_run_gate_performs_zero_state_writes(self, tmp_path):
        adapter, spy = self._adapter(tmp_path)
        # Empty check list → real lib.gate.runGate → proceed.
        result = adapter.runGate({"id": "g-scout", "checks": []}, [])
        assert result.decision == "proceed"
        assert spy.writes == [], (
            f"runGate must return the GateResult ONLY; it wrote {spy.writes!r} "
            "(the runner is the single writer of node fields — R9/D11)"
        )

    def test_run_gate_failing_gate_performs_zero_state_writes(self, tmp_path):
        adapter, spy = self._adapter(tmp_path)
        # Unknown check type → decision 'fail' from the real gate engine.
        result = adapter.runGate(
            {"id": "g-x", "checks": [{"type": "no-such-check"}]}, []
        )
        assert result.decision == "fail"
        assert spy.writes == []

    def test_run_exec_performs_zero_state_writes(self, tmp_path):
        adapter, spy = self._adapter(tmp_path)
        result = adapter.runExec("testrun", "echo ok", {})
        assert result.status == "done"
        assert result.exit_code == 0
        # The artifact file is the exec node's OUTPUT, not node state.
        assert result.artifact_path is not None
        assert Path(result.artifact_path).exists()
        assert spy.writes == [], (
            f"runExec must return the ExecResult ONLY; it wrote {spy.writes!r}"
        )

    def test_run_gate_never_passes_state_path_to_lib_gate(self, tmp_path):
        """lib.gate._write_gate_result is CLI-standalone only: combined with a
        runner-managed state.json it would be a second writer (and its partial,
        statusless entry corrupts StateStore reads)."""
        from unittest.mock import patch

        adapter, spy = self._adapter(tmp_path)
        captured: dict[str, Any] = {}

        def _fake_run_gate(gate, paths, *, space, gate_id, state_path=None):
            captured["state_path"] = state_path
            return GateResult(decision="proceed", errors=[])

        with patch("lib.gate.runGate", side_effect=_fake_run_gate):
            adapter.runGate({"id": "g-scout", "checks": []}, [])
        assert captured["state_path"] is None
        assert spy.writes == []
