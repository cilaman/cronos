"""R6 regression tests — completeness invariant + ``stalled`` outcome
(kills D5 and D12; implements OD-3).

Defects (00-assessment.md §2):
  D5  — no completeness invariant: work-list drain ⇒ ``status="done"`` even
        when nodes were starved by unmet edge conditions; a goal is marked
        DONE with the pipeline tail never executed.
  D12 — the driver's post-hoc ``_stalled_gate_ids`` heuristic flagged ANY
        gate whose final decision ≠ 'proceed', parking verdict-routed runs
        WAITING at completion (spurious).

Contract (01-state-model.md §5.2 + 03-remediation-plan.md §R6):
  1. ``done`` is emitted at drain ONLY when every node is either executed to
     a terminal node-status or EXCLUDED WITH PROOF; otherwise the run is
     ``stalled`` with machine-readable run-level detail in ``state.stall``
     ({kind, nodes, reason[, dead_ends]}) — hosts never dig through nodes.
  2. Proof rule: an evaluated-false edge proves exclusion of its target ONLY
     if its source actually ROUTED somewhere (≥1 outgoing forward edge
     fired).  A done node ALL of whose outgoing forward edges evaluated
     false is a DEAD-END: its unreached descendants are starved, not
     excluded.  Transitive exclusion from a provenly-excluded node stays
     proof (R5).  ``stall.nodes`` lists the minimal actionable frontier
     (starved nodes none of whose in-edge sources are themselves starved).
  3. Exhausted GATE fix-loops terminate ``stalled`` with
     ``kind="gate_exhausted"`` — reversing the pre-R6 engineered dead-end to
     ``done`` (OD-3).  LoopPolicy until-loop exhaustion on agent nodes keeps
     its on_exhaust semantics (escalate/stop — R7 territory, unchanged).
  4. ``stalled`` + ``stall`` round-trip real persistence (StateStore), and a
     pre-R6 state.json without the ``stall`` key loads cleanly.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


from delivery_workflow import runner as workflow_runner  # noqa: E402
from delivery_workflow.ir import IREdge, IRGraph, IRNode, LoopPolicy  # noqa: E402
from delivery_workflow.lib.state.events import EventLog  # noqa: E402
from delivery_workflow.lib.state.store import StateStore  # noqa: E402
from delivery_workflow.lib.state.ops import StateStoreOps  # noqa: E402
from delivery_workflow.results import AgentResult, GateResult, TelemetryData  # noqa: E402


# ---------------------------------------------------------------------------
# Test doubles (zero app imports — this suite runs on the bare package).
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
    """Scripted ExecutorInterface recording dispatches; real lib.conditions."""

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
        raise NotImplementedError

    def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool:
        from delivery_workflow.lib.conditions import eval_condition

        return eval_condition(expr, scope)

    def escalate(self, node_id: str, reason: str) -> None:
        self.escalations.append((node_id, reason))
        if self.state is not None:
            self.state.write({"status": "blocked"})


def _node(nid: str, kind: str = "agent", data: dict | None = None, loop=None) -> IRNode:
    return IRNode(id=nid, kind=kind, data=data or {}, loop=loop)


def _state_ops(tmp_path: Path) -> StateStoreOps:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    ops = StateStoreOps(StateStore(run_dir), EventLog(run_dir))
    ops.bootstrap_if_absent(spec="r6", run_id="run-r6", usd_ceiling=0.0)
    return ops


# ---------------------------------------------------------------------------
# 1. Dead-end source → stalled with the starved frontier (D5).
# ---------------------------------------------------------------------------


class TestDeadEndStalls:
    def test_dead_end_source_stalls_with_starved_frontier(self):
        """The D5 repro shape: a→b gated on go=='yes'; a says 'no' → a routed
        nowhere → b starved → terminal 'stalled', never a silent 'done'."""
        g = IRGraph(
            nodes=[_node("a"), _node("b")],
            edges=[IREdge(source="a", target="b", when="a.fields.go == 'yes'", port=None)],
            metadata={}, variables={},
        )
        ex = RecordingExecutor(agent_script={"a": _agent_done(go="no")})
        state = workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert "b" not in ex.dispatched
        assert state.status == "stalled"
        assert state.stall is not None
        assert state.stall["kind"] == "starved_nodes"
        assert state.stall["nodes"] == ["b"]
        assert state.stall.get("dead_ends") == ["a"]
        assert "a" in state.stall["reason"] and "b" in state.stall["reason"]

    def test_starved_tail_lists_minimal_frontier_only(self):
        """Nodes unreached because an ancestor starved are starved too, but
        stall.nodes lists only the actionable frontier — not the whole tail."""
        g = IRGraph(
            nodes=[_node("a"), _node("b"), _node("c"), _node("d")],
            edges=[
                IREdge(source="a", target="b", when="a.fields.go == 'yes'", port=None),
                IREdge(source="b", target="c", when="", port=None),
                IREdge(source="c", target="d", when="", port=None),
            ],
            metadata={}, variables={},
        )
        ex = RecordingExecutor(agent_script={"a": _agent_done(go="no")})
        state = workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert state.status == "stalled"
        assert state.stall["nodes"] == ["b"], (
            "the frontier is b; c and d are implied by b's starvation"
        )
        assert state.stall.get("dead_ends") == ["a"]


# ---------------------------------------------------------------------------
# 1b. Generation skew in the completeness proof: an edge excluded at the
#     target's PRE-execution generation (the target later ran via a sibling
#     in-edge, bumping its attempt) must still count as an exclusion record —
#     never be misread as an "unrecorded true-fire" that proves routing.
# ---------------------------------------------------------------------------


class TestDeadEndGenerationSkew:
    def test_diamond_excluded_edge_into_later_executed_target_is_not_routing(self):
        """s→a, s→b unconditional; a→b and a→c conditioned on a field a never
        produces.  a runs first and records a→b excluded at b's generation 0;
        b then executes via s→b (attempt → 1).  The proof must NOT read the
        missing (idx, gen=1) record as a true-fire: a routed nowhere, c is
        starved, and the run is 'stalled' — not a false 'done' (D5 class)."""
        g = IRGraph(
            nodes=[_node("s"), _node("a"), _node("b"), _node("c")],
            edges=[
                IREdge(source="s", target="a", when="", port=None),
                IREdge(source="s", target="b", when="", port=None),
                IREdge(source="a", target="b", when="a.fields.x == 'go'", port=None),
                IREdge(source="a", target="c", when="a.fields.x == 'go'", port=None),
            ],
            metadata={}, variables={},
        )
        ex = RecordingExecutor(agent_script={"a": _agent_done(x="nope")})
        state = workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert "c" not in ex.dispatched
        assert state.status == "stalled"
        assert state.stall["kind"] == "starved_nodes"
        assert state.stall["nodes"] == ["c"]
        assert state.stall.get("dead_ends") == ["a"]

    def test_join_topology_dead_end_source_stalls_both_orderings(self):
        """S→A / S→B conditional (both false), T→A unconditional: S's excluded
        edge into A is recorded at A's generation 0; A then executes via T→A
        (attempt → 1).  S routed nowhere, so B is starved and S is the
        dead-end — in either node declaration order."""
        for order in (["s", "t", "a", "b"], ["t", "s", "a", "b"]):
            g = IRGraph(
                nodes=[_node(n) for n in order],
                edges=[
                    IREdge(source="s", target="a", when="s.fields.x == 'go'", port=None),
                    IREdge(source="s", target="b", when="s.fields.x == 'go2'", port=None),
                    IREdge(source="t", target="a", when="", port=None),
                ],
                metadata={}, variables={},
            )
            ex = RecordingExecutor(agent_script={"s": _agent_done(x="nope")})
            state = workflow_runner.run(graph=g, executor=ex, state_ops=None)

            assert "a" in ex.dispatched, order
            assert "b" not in ex.dispatched, order
            assert state.status == "stalled", order
            assert state.stall["nodes"] == ["b"], order
            assert state.stall.get("dead_ends") == ["s"], order


# ---------------------------------------------------------------------------
# 1c. Stale transitive exclusions from a gate's needs_fix pass must not
#     survive the fix-loop back-edge reset: a later park at the sign-off and
#     host approve must resume through the tail, not re-derive a stall.
# ---------------------------------------------------------------------------


class BlockingExecutor(RecordingExecutor):
    """RecordingExecutor whose scripted 'blocked' agents park the run."""

    def __init__(self, block=(), **kwargs) -> None:
        super().__init__(**kwargs)
        self._block = set(block)

    def dispatchAgent(self, agent_ref, inputs):
        node_id = inputs["node_id"]
        if node_id in self._block:
            self.dispatched.append(node_id)
            return AgentResult(
                status="blocked", artifact_paths=[], produces="",
                fields={}, open_questions=[],
                telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
            )
        return super().dispatchAgent(agent_ref, inputs)


class TestFixLoopExclusionsPurgedOnReset:
    def test_gate_needs_fix_then_park_at_signoff_resumes_to_done(self, tmp_path):
        """The shipped-spec head shape: analyze → g(loop, fix back-edge) →
        signoff(parks) → architect.  The needs_fix pass transitively records
        signoff's out-edges excluded at generation 0; the fix-loop reset must
        PURGE those records — otherwise the resume after the human approves
        the sign-off trusts the stale exclusion, starves architect, and every
        re-resume re-derives the identical stall (unrecoverable park loop)."""
        ops = _state_ops(tmp_path)
        g = IRGraph(
            nodes=[
                _node("analyze"),
                _node(
                    "g", kind="gate", data={"checks": []},
                    loop=LoopPolicy(
                        until="g.decision == 'proceed'", max=3,
                        on_exhaust="escalate", stall=[],
                    ),
                ),
                _node("signoff"),
                _node("architect"),
            ],
            edges=[
                IREdge(source="analyze", target="g", when="", port=None),
                IREdge(source="g", target="signoff",
                       when="g.decision == 'proceed'", port=None),
                IREdge(source="g", target="analyze",
                       when="g.decision != 'proceed'", port=None),
                IREdge(source="signoff", target="architect", when="", port=None),
            ],
            metadata={}, variables={},
        )
        ex = BlockingExecutor(
            block=("signoff",),
            gate_script={"g": [
                GateResult(decision="needs_fix", errors=["fix"]),
                GateResult(decision="proceed", errors=[]),
            ]},
        )
        ex.state = ops
        phase1 = workflow_runner.run(graph=g, executor=ex, state_ops=ops)
        assert phase1.status == "blocked", "precondition: run parks at the sign-off"
        assert ex.dispatched == ["analyze", "g", "analyze", "g", "signoff"]

        # Host approve: the driver marks the sign-off done and re-enters.
        ops.write({"status": "running",
                   "nodes": {"signoff": {"status": "done", "attempt": 1}}})
        ex2 = RecordingExecutor()
        ex2.state = ops
        phase2 = workflow_runner.run(graph=g, executor=ex2, state_ops=ops)

        assert "architect" in ex2.dispatched, (
            "stale gen-0 exclusion of signoff→architect starved the tail "
            "across the park/resume"
        )
        assert phase2.status == "done"
        assert phase2.stall is None


# ---------------------------------------------------------------------------
# 2. Routed source → sibling exclusion IS proof → done (the diamond).
# ---------------------------------------------------------------------------


class TestRoutedExclusionCompletes:
    def test_routed_source_sibling_exclusion_is_done(self):
        """The signoff diamond: a routes to c (fired) while a→b evaluates
        false — b's exclusion is PROVEN (a routed somewhere), b drops out of
        the b→c join, and the run completes 'done' with no stall detail."""
        g = IRGraph(
            nodes=[_node("a"), _node("b"), _node("c")],
            edges=[
                IREdge(source="a", target="b", when="a.fields.go == 'yes'", port=None),
                IREdge(source="a", target="c", when="a.fields.go == 'no'", port=None),
                IREdge(source="b", target="c", when="", port=None),
            ],
            metadata={}, variables={},
        )
        ex = RecordingExecutor(agent_script={"a": _agent_done(go="no")})
        state = workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert ex.dispatched == ["a", "c"]
        assert state.status == "done"
        assert state.stall is None

    def test_transitive_exclusion_from_proven_exclusion_stays_proof(self):
        """A whole branch behind a provenly-excluded node is excluded, not
        starved: a→b false (a routed to d), b→c transitively excluded → done."""
        g = IRGraph(
            nodes=[_node("a"), _node("b"), _node("c"), _node("d")],
            edges=[
                IREdge(source="a", target="b", when="a.fields.go == 'yes'", port=None),
                IREdge(source="a", target="d", when="a.fields.go == 'no'", port=None),
                IREdge(source="b", target="c", when="", port=None),
            ],
            metadata={}, variables={},
        )
        ex = RecordingExecutor(agent_script={"a": _agent_done(go="no")})
        state = workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert ex.dispatched == ["a", "d"]
        assert state.status == "done"
        assert state.stall is None

    def test_verdict_routed_gate_non_proceed_decision_is_done(self):
        """D12: a gate whose OWN decision is needs_fix but whose edges route on
        an upstream field completes 'done' when the verdict edge fires — the
        gate routed somewhere; its decision is detail, not a stall."""
        g = IRGraph(
            nodes=[
                _node("review"),
                _node("g-review", kind="gate", data={"checks": []}),
                _node("security"),
            ],
            edges=[
                IREdge(source="review", target="g-review", when="", port=None),
                IREdge(
                    source="g-review", target="security",
                    when="review.fields.verdict == 'pass'", port=None,
                ),
            ],
            metadata={}, variables={},
        )
        ex = RecordingExecutor(
            agent_script={"review": _agent_done(verdict="pass")},
            gate_script={"g-review": GateResult(decision="needs_fix", errors=["strict"])},
        )
        state = workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert "security" in ex.dispatched
        assert state.status == "done"
        assert state.stall is None
        assert state.nodes["g-review"].gate["decision"] == "needs_fix"


# ---------------------------------------------------------------------------
# 3. Gate fix-loop exhaustion → stalled(gate_exhausted) (OD-3).
# ---------------------------------------------------------------------------


class TestGateExhaustionStalls:
    def _gate_loop_graph(self, max_iter: int = 3) -> IRGraph:
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

    def test_exhausted_gate_stalls_with_gate_detail(self, tmp_path):
        ops = _state_ops(tmp_path)
        ex = RecordingExecutor(
            gate_script={"gate": GateResult(decision="needs_fix", errors=["bad artifact"])},
        )
        ex.state = ops
        state = workflow_runner.run(graph=self._gate_loop_graph(3), executor=ex, state_ops=ops)

        assert state.status == "stalled"
        assert state.stall["kind"] == "gate_exhausted"
        assert state.stall["nodes"] == ["gate"]
        assert "needs_fix" in state.stall["reason"]
        assert "bad artifact" in state.stall["reason"]
        # Bounded: loop.max gate evaluations, no generic escalate.
        assert ex.dispatched.count("gate") == 3
        assert "sink" not in ex.dispatched
        assert ex.escalations == []
        # The stall detail survives real persistence.
        persisted = ops.read()
        assert persisted.status == "stalled"
        assert persisted.stall == state.stall

    def test_gate_that_eventually_proceeds_completes_done(self, tmp_path):
        ops = _state_ops(tmp_path)
        ex = RecordingExecutor(
            gate_script={"gate": [
                GateResult(decision="needs_fix", errors=["fix me"]),
                GateResult(decision="proceed", errors=[]),
            ]},
        )
        ex.state = ops
        state = workflow_runner.run(graph=self._gate_loop_graph(3), executor=ex, state_ops=ops)

        assert state.status == "done"
        assert state.stall is None
        assert "sink" in ex.dispatched


# ---------------------------------------------------------------------------
# 4. Persistence: stalled round-trips; pre-R6 state.json loads.
# ---------------------------------------------------------------------------


class TestStalledPersistence:
    def test_stalled_round_trips_real_statestore(self, tmp_path):
        """The D5 shape against real StateStore persistence: the terminal
        'stalled' + stall detail read back identically (round-trip law)."""
        g = IRGraph(
            nodes=[_node("a"), _node("b")],
            edges=[IREdge(source="a", target="b", when="a.fields.go == 'yes'", port=None)],
            metadata={}, variables={},
        )
        ops = _state_ops(tmp_path)
        ex = RecordingExecutor(agent_script={"a": _agent_done(go="no")})
        ex.state = ops
        state = workflow_runner.run(graph=g, executor=ex, state_ops=ops)

        assert state.status == "stalled"
        persisted = ops.read()
        assert persisted.status == "stalled"
        assert persisted.stall == state.stall
        # The raw file carries the run-level record (hosts read run level only).
        raw = json.loads((tmp_path / "run" / "state.json").read_text())
        assert raw["status"] == "stalled"
        assert raw["stall"]["kind"] == "starved_nodes"
        assert raw["stall"]["nodes"] == ["b"]

    def test_resume_of_stalled_run_re_stalls_honestly(self, tmp_path):
        """Re-entering a stalled run (nothing changed) re-derives 'stalled'
        instead of flipping to a false 'done' — no silent self-heal."""
        g = IRGraph(
            nodes=[_node("a"), _node("b")],
            edges=[IREdge(source="a", target="b", when="a.fields.go == 'yes'", port=None)],
            metadata={}, variables={},
        )
        ops = _state_ops(tmp_path)
        ex = RecordingExecutor(agent_script={"a": _agent_done(go="no")})
        ex.state = ops
        first = workflow_runner.run(graph=g, executor=ex, state_ops=ops)
        assert first.status == "stalled"

        ex2 = RecordingExecutor()
        ex2.state = ops
        second = workflow_runner.run(graph=g, executor=ex2, state_ops=ops)
        assert ex2.dispatched == []
        assert second.status == "stalled"
        assert second.stall["kind"] == "starved_nodes"
        assert second.stall["nodes"] == ["b"]

    def test_completing_resume_clears_stall_detail(self, tmp_path):
        """A stalled run whose routing later succeeds ends 'done' with the
        stall record cleared — 'stall' is only meaningful while stalled."""
        g = IRGraph(
            nodes=[_node("a"), _node("b")],
            edges=[IREdge(source="a", target="b", when="a.fields.go == 'yes'", port=None)],
            metadata={}, variables={},
        )
        ops = _state_ops(tmp_path)
        ex = RecordingExecutor(agent_script={"a": _agent_done(go="no")})
        ex.state = ops
        assert workflow_runner.run(graph=g, executor=ex, state_ops=ops).status == "stalled"

        # Host-side repair (R7 will own this): re-run a with corrected fields.
        ops.write({
            "status": "running",
            "nodes": {"a": {"status": "pending", "fields": {}, "attempt": 0}},
            "edges_evaluated": {},
        })
        ex2 = RecordingExecutor(agent_script={"a": _agent_done(go="yes")})
        ex2.state = ops
        final = workflow_runner.run(graph=g, executor=ex2, state_ops=ops)
        assert ex2.dispatched == ["a", "b"]
        assert final.status == "done"
        assert final.stall is None
        assert ops.read().stall is None

    def test_pre_r6_state_json_loads_without_stall_key(self, tmp_path):
        """A pre-R6 state.json (no 'stall' key) loads cleanly with stall=None,
        and a resume of it completes normally."""
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True)
        (run_dir / "state.json").write_text(json.dumps({
            "spec": "legacy", "run_id": "run-legacy", "status": "running",
            "budget": {"usd_ceiling": 0.0, "usd_spent": 0.0},
            "nodes": {"a": {"status": "done", "attempt": 1,
                            "artifact_paths": [], "fields": {"go": "yes"}}},
        }))
        store = StateStore(run_dir)
        loaded = store.read()
        assert loaded.stall is None

        g = IRGraph(
            nodes=[_node("a"), _node("b")],
            edges=[IREdge(source="a", target="b", when="a.fields.go == 'yes'", port=None)],
            metadata={}, variables={},
        )
        ops = StateStoreOps(store, EventLog(run_dir))
        ex = RecordingExecutor()
        ex.state = ops
        final = workflow_runner.run(graph=g, executor=ex, state_ops=ops)
        assert ex.dispatched == ["b"]
        assert final.status == "done"
        assert final.stall is None
