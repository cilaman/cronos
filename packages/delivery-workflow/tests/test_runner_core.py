"""Tests for runner/core.py (I3)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ir import IREdge, IRGraph, IRNode, LoopPolicy
from results import AgentResult, GateResult, TelemetryData
from runner import run
from state_types import BudgetState, NodeState, WorkflowState


# ---------------------------------------------------------------------------
# Minimal test runtime
# ---------------------------------------------------------------------------

class _RecordingRuntime:
    """Minimal ExecutorInterface that records calls and returns pre-configured results."""

    def __init__(self, outcomes: dict | None = None) -> None:
        self.dispatched: list[tuple[str, dict]] = []
        self.escalated: list[tuple[str, str]] = []
        self.gate_calls: list[tuple[dict, list]] = []
        self.conditions_evaluated: list[tuple[str, dict]] = []
        self._outcomes: dict = outcomes or {}  # node_id → AgentResult

    def dispatchAgent(self, agent_ref: str, inputs: dict) -> AgentResult:
        node_id = inputs.get("node_id", agent_ref)
        self.dispatched.append((agent_ref, inputs))
        result = self._outcomes.get(node_id)
        if result is None:
            result = AgentResult(
                status="done",
                artifact_paths=[],
                produces="",
                fields={},
                open_questions=[],
                telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
            )
        return result

    def runGate(self, gate: dict, artifact_paths: list) -> GateResult:
        self.gate_calls.append((gate, artifact_paths))
        return GateResult(decision="proceed", errors=[])

    def evalCondition(self, expr: str, scope: dict) -> bool:
        self.conditions_evaluated.append((expr, scope))
        # Simple literal evaluations for tests.
        if expr == "":
            return True
        # Support "key == 'value'" style for tests.
        try:
            from lib.conditions import eval_condition
            return eval_condition(expr, scope)
        except Exception:
            return False

    def escalate(self, node_id: str, reason: str) -> None:
        self.escalated.append((node_id, reason))

    class _NullState:
        def read(self):
            raise NotImplementedError
        def write(self, patch):
            raise NotImplementedError

    class _NullTelemetry:
        def emit(self, node_id, data):
            pass

    @property
    def state(self):
        return self._NullState()

    @property
    def telemetry(self):
        return self._NullTelemetry()


def _simple_graph(n_nodes: int = 1) -> IRGraph:
    """Build a linear graph with n agent nodes."""
    nodes = [IRNode(id=f"n{i}", kind="agent") for i in range(n_nodes)]
    edges = [IREdge(source=f"n{i}", target=f"n{i+1}") for i in range(n_nodes - 1)]
    return IRGraph(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunBasic:
    def test_single_node_done(self):
        g = _simple_graph(1)
        rt = _RecordingRuntime()
        state = run(g, rt)
        assert state.status == "done"
        assert "n0" in state.nodes
        assert state.nodes["n0"].status == "done"

    def test_linear_chain_all_done(self):
        g = _simple_graph(3)
        rt = _RecordingRuntime()
        state = run(g, rt)
        assert state.status == "done"
        for i in range(3):
            assert state.nodes[f"n{i}"].status == "done"

    def test_dispatch_order_entry_first(self):
        g = _simple_graph(3)
        rt = _RecordingRuntime()
        run(g, rt)
        dispatched_ids = [inp["node_id"] for _, inp in rt.dispatched]
        assert dispatched_ids.index("n0") < dispatched_ids.index("n1")
        assert dispatched_ids.index("n1") < dispatched_ids.index("n2")

    def test_gate_node_dispatched(self):
        g = IRGraph(
            nodes=[
                IRNode(id="scout", kind="agent"),
                IRNode(id="g-scout", kind="gate", data={"checks": []}),
            ],
            edges=[IREdge(source="scout", target="g-scout")],
        )
        rt = _RecordingRuntime()
        state = run(g, rt)
        assert state.status == "done"
        assert len(rt.gate_calls) == 1
        assert state.nodes["g-scout"].gate is not None
        assert state.nodes["g-scout"].gate["decision"] == "proceed"

    def test_trigger_node_immediate_done(self):
        g = IRGraph(
            nodes=[IRNode(id="start", kind="trigger")],
        )
        rt = _RecordingRuntime()
        state = run(g, rt)
        assert state.status == "done"
        assert state.nodes["start"].status == "done"

    def test_decision_node_no_dispatch(self):
        g = IRGraph(
            nodes=[
                IRNode(id="a", kind="agent"),
                IRNode(id="dec", kind="decision"),
                IRNode(id="b", kind="agent"),
            ],
            edges=[
                IREdge(source="a", target="dec"),
                IREdge(source="dec", target="b"),
            ],
        )
        rt = _RecordingRuntime()
        state = run(g, rt)
        assert state.status == "done"
        # decision node done with no external dispatch call.
        assert state.nodes["dec"].status == "done"
        # Only "a" and "b" agent nodes are actually dispatched.
        dispatched_agents = [agent_ref for agent_ref, _ in rt.dispatched]
        assert "dec" not in dispatched_agents

    def test_human_node_blocks_run(self):
        g = IRGraph(
            nodes=[IRNode(id="release", kind="human", data={"prompt": "Sign off?"})],
        )
        rt = _RecordingRuntime()
        state = run(g, rt)
        assert state.status == "blocked"
        assert state.nodes["release"].status == "blocked"
        assert len(rt.escalated) == 1

    def test_conditional_edge_skips_unreachable_node(self):
        """If g-scout.decision != 'proceed', the analyze node should not run."""
        rt = _RecordingRuntime()
        rt._outcomes["g-scout"] = None  # gate always returns "proceed" via runGate

        # Manually override runGate to return needs_fix.
        orig_runGate = rt.runGate

        def failing_gate(gate, paths):
            return GateResult(decision="needs_fix", errors=["schema violation"])

        rt.runGate = failing_gate

        g = IRGraph(
            nodes=[
                IRNode(id="scout", kind="agent"),
                IRNode(id="g-scout", kind="gate"),
                IRNode(id="analyze", kind="agent"),
            ],
            edges=[
                IREdge(source="scout", target="g-scout"),
                IREdge(source="g-scout", target="analyze", when="g-scout.decision == 'proceed'"),
            ],
        )
        state = run(g, rt)
        # analyze should not run because the condition is not met.
        assert "analyze" not in state.nodes or state.nodes.get("analyze", NodeState(status="")).status != "done"

    def test_empty_graph_returns_done(self):
        g = IRGraph()
        rt = _RecordingRuntime()
        state = run(g, rt)
        assert state.status == "done"


class TestCancelRaceGuard:
    def test_cancel_race_at_worklist_boundary(self):
        """If StateOps signals cancelled, runner halts before next dispatch."""

        class _CancelStateOps:
            def __init__(self, cancel_after: int):
                self._tick = 0
                self._cancel_after = cancel_after
                self._state = WorkflowState(
                    spec="test", run_id="r1", status="running",
                    budget=BudgetState(usd_ceiling=0.0),
                )

            def read(self) -> WorkflowState:
                self._tick += 1
                if self._tick > self._cancel_after:
                    self._state.status = "cancelled"
                return self._state

            def write(self, patch: dict) -> None:
                if "status" in patch:
                    self._state.status = patch["status"]
                nodes_patch = patch.get("nodes", {})
                for nid, np in nodes_patch.items():
                    if nid not in self._state.nodes:
                        self._state.nodes[nid] = NodeState(status=np.get("status", "pending"))
                    else:
                        ns = self._state.nodes[nid]
                        if "status" in np:
                            ns.status = np["status"]

        g = _simple_graph(5)
        rt = _RecordingRuntime()
        state_ops = _CancelStateOps(cancel_after=1)
        state = run(g, rt, state_ops=state_ops)
        # Should have halted early (not all 5 nodes dispatched).
        assert state.status == "cancelled"
        # At most 1 node should have been dispatched before cancellation.
        assert len(rt.dispatched) <= 1


class TestResumeSkipsDoneNodes:
    def test_resume_skips_already_done(self):
        """Nodes already done in the WorkflowState are not re-dispatched."""

        class _PreloadedStateOps:
            def __init__(self, preloaded: WorkflowState):
                self._state = preloaded

            def read(self) -> WorkflowState:
                return self._state

            def write(self, patch: dict) -> None:
                if "status" in patch:
                    self._state.status = patch["status"]
                for nid, np in patch.get("nodes", {}).items():
                    if nid not in self._state.nodes:
                        self._state.nodes[nid] = NodeState(status=np.get("status", "pending"))
                    else:
                        ns = self._state.nodes[nid]
                        for k, v in np.items():
                            setattr(ns, k, v)

        preloaded = WorkflowState(
            spec="test", run_id="r1", status="running",
            budget=BudgetState(usd_ceiling=0.0),
            nodes={"n0": NodeState(status="done")},
        )
        g = _simple_graph(3)
        rt = _RecordingRuntime()
        state = run(g, rt, state_ops=_PreloadedStateOps(preloaded))
        # n0 was already done — should not be re-dispatched.
        dispatched_ids = [inp["node_id"] for _, inp in rt.dispatched]
        assert "n0" not in dispatched_ids
        assert state.status == "done"


class TestSelfLoopCapFires:
    def test_self_loop_cap_fires_before_exhaustion(self):
        """A self-looping node must hit the loop cap and escalate."""
        g = IRGraph(
            nodes=[
                IRNode(
                    id="review",
                    kind="agent",
                    loop=LoopPolicy(until="review.fields.verdict == 'pass'", max=3),
                ),
            ],
        )

        # Agent always returns verdict=needs_fix — loop never exits naturally.
        rt = _RecordingRuntime(outcomes={
            "review": AgentResult(
                status="done",
                artifact_paths=[],
                produces="",
                fields={"verdict": "needs_fix"},
                open_questions=[],
                telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
            )
        })
        state = run(g, rt)
        # Should have escalated after max=3 iterations.
        assert len(rt.escalated) >= 1
        # Escalated with a message about max iterations.
        reason = rt.escalated[0][1]
        assert "max" in reason.lower() or "iterations" in reason.lower() or "Loop" in reason
