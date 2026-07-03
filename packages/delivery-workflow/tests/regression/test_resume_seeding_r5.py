"""R5 regression tests — condition-aware resume seeding + exclusion (kills D1).

Defect (00-assessment.md §2, D1): resume seeding fired ALL forward out-edges
of every persisted-``done`` node without evaluating ``when`` conditions, so
every conditional branch downstream of a human sign-off fired unconditionally
after the park→resume cycle (on the shipped spec, ``frontend`` ran regardless
of ``has_ui``).

Contract (01-state-model.md §5.2/§5.3 + 03-remediation-plan.md §R5):
  1. Resume seeding replays each done node's outgoing ``when`` conditions
     against the rebuilt typed scope and fires only edges that evaluate true.
  2. Fired AND evaluated-false (excluded) edges are recorded in the persisted
     ``edges_evaluated`` map so replay is idempotent across multiple resumes.
  3. Transitive exclusion: an evaluated-false edge is excluded; a node ALL of
     whose forward in-edges are excluded is excluded; an excluded node's own
     outgoing forward edges are excluded in turn (recorded, not evaluated).
     A join fires when all its NON-EXCLUDED in-edges have fired.
  4. The same exclusion mechanism runs at fire time (forward execution) and
     at resume seeding — routing past a false branch behaves identically
     with and without an intervening park.
  5. Backward compatibility: pre-R5 state.json (no ``edges_evaluated``) and
     StateOps that ignore the new key degrade to condition re-evaluation from
     the rebuilt scope — never crash, never mis-route.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

_PKG = Path(__file__).parent.parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

import runner as workflow_runner  # noqa: E402
from adapters.cronos.adapter import CronosStateOps  # noqa: E402
from ir import IREdge, IRGraph, IRNode  # noqa: E402
from lib.state.events import EventLog  # noqa: E402
from lib.state.store import StateStore  # noqa: E402
from results import AgentResult, TelemetryData  # noqa: E402
from state_types import BudgetState, NodeState, WorkflowState  # noqa: E402


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
    """Scripted ExecutorInterface recording dispatch order and conditions."""

    def __init__(self, agent_script: dict[str, Any] | None = None) -> None:
        self.dispatched: list[str] = []
        self.evaluated: list[str] = []  # condition expressions, in eval order
        self.escalations: list[tuple[str, str]] = []
        self._agent_script = dict(agent_script or {})
        self.state = None  # optional StateOps, mirrored from CronosAdapter
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

    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]):
        raise NotImplementedError

    def runExec(self, node_id: str, command: str, inputs: dict[str, Any]):
        raise NotImplementedError

    def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool:
        self.evaluated.append(expr)
        from lib.conditions import eval_condition

        return eval_condition(expr, scope)

    def escalate(self, node_id: str, reason: str) -> None:
        self.escalations.append((node_id, reason))
        if self.state is not None:
            self.state.write({"status": "blocked"})

    def count(self, node_id: str) -> int:
        return self.dispatched.count(node_id)


def _fresh_state(**nodes: NodeState) -> WorkflowState:
    return WorkflowState(
        spec="r5",
        run_id="run-r5",
        status="running",
        budget=BudgetState(usd_ceiling=0.0),
        nodes=dict(nodes),
    )


class LossyStateOps:
    """In-memory StateOps that IGNORES ``edges_evaluated`` writes — the
    degradation target: absent records must fall back to condition
    re-evaluation from the rebuilt scope (mirrors the repro script's
    MemStateOps and any pre-R5 embedder)."""

    def __init__(self, initial: WorkflowState) -> None:
        self._state = copy.deepcopy(initial)
        self.edge_writes = 0  # observability: the runner DID try to persist

    def read(self) -> WorkflowState:
        return copy.deepcopy(self._state)

    def write(self, patch: dict[str, Any]) -> None:
        if "edges_evaluated" in patch:
            self.edge_writes += 1  # dropped on purpose
        if "status" in patch:
            self._state.status = patch["status"]
        for nid, ns_patch in patch.get("nodes", {}).items():
            node = self._state.nodes.setdefault(nid, NodeState(status="pending"))
            if "status" in ns_patch:
                node.status = ns_patch["status"]
            if "attempt" in ns_patch:
                node.attempt = int(ns_patch["attempt"])
            if "artifact_paths" in ns_patch:
                node.artifact_paths = list(ns_patch["artifact_paths"])
            if "gate" in ns_patch:
                node.gate = ns_patch["gate"]
            if "fields" in ns_patch:
                node.fields = dict(ns_patch["fields"])


def _store_ops(run_dir: Path) -> CronosStateOps:
    """Real replace-style persistence: StateStore + EventLog on disk."""
    run_dir.mkdir(parents=True, exist_ok=True)
    ops = CronosStateOps(StateStore(run_dir), EventLog(run_dir))
    ops.bootstrap_if_absent(spec="r5", run_id="run-r5", usd_ceiling=0.0)
    return ops


# ---------------------------------------------------------------------------
# The D1 diamond: analyze → signoff(human) → {frontend | architect} with the
# unconditional frontend → architect join edge (shipped-spec shape).
# ---------------------------------------------------------------------------


def _diamond_graph() -> IRGraph:
    return IRGraph(
        nodes=[
            IRNode(id="analyze", kind="agent"),
            IRNode(id="signoff", kind="human", data={"prompt": "ok?"}),
            IRNode(id="frontend", kind="agent"),
            IRNode(id="architect", kind="agent"),
            IRNode(id="tail", kind="agent"),
        ],
        edges=[
            IREdge(source="analyze", target="signoff"),
            IREdge(source="signoff", target="frontend",
                   when="analyze.fields.has_ui == true"),
            IREdge(source="signoff", target="architect",
                   when="analyze.fields.has_ui == false"),
            IREdge(source="frontend", target="architect"),
            IREdge(source="architect", target="tail"),
        ],
    )


def _approve_signoff(ops) -> None:
    """The host resume patch (_resume_from_blocked semantics)."""
    ops.write({"status": "running", "nodes": {"signoff": {"status": "done"}}})


# ===========================================================================
# 1. Exclusion propagation on the diamond — park→resume (the D1 kill shot)
# ===========================================================================


class TestDiamondExclusionOnResume:
    def test_has_ui_false_resume_runs_architect_not_frontend(self, tmp_path):
        ops = _store_ops(tmp_path)
        ex1 = RecordingExecutor({"analyze": _agent_done(has_ui=False)})
        ex1.state = ops
        first = workflow_runner.run(graph=_diamond_graph(), executor=ex1, state_ops=ops)
        assert first.status == "blocked" and ex1.dispatched == ["analyze"]

        _approve_signoff(ops)
        ex2 = RecordingExecutor()
        ex2.state = ops
        final = workflow_runner.run(graph=_diamond_graph(), executor=ex2, state_ops=ops)

        assert "frontend" not in ex2.dispatched, (
            "has_ui=false, yet frontend dispatched on resume (D1)"
        )
        assert ex2.dispatched == ["architect", "tail"]
        assert final.status == "done"
        # The record proves the routing: fired architect edge, excluded
        # frontend edge AND the transitively-excluded frontend→architect edge.
        record = ops.read().edges_evaluated
        assert "frontend" in record["excluded"]
        assert "architect" in record["excluded"], (
            "transitive exclusion of frontend→architect not recorded"
        )

    def test_has_ui_true_resume_runs_frontend_then_architect(self, tmp_path):
        ops = _store_ops(tmp_path)
        ex1 = RecordingExecutor({"analyze": _agent_done(has_ui=True)})
        ex1.state = ops
        workflow_runner.run(graph=_diamond_graph(), executor=ex1, state_ops=ops)

        _approve_signoff(ops)
        ex2 = RecordingExecutor()
        ex2.state = ops
        final = workflow_runner.run(graph=_diamond_graph(), executor=ex2, state_ops=ops)

        # architect must WAIT for frontend (the join is not dropped when only
        # the false branch is excluded).
        assert ex2.dispatched == ["frontend", "architect", "tail"]
        assert final.status == "done"


# ===========================================================================
# 2. Forward-vs-resume equivalence — same routing with and without a park
# ===========================================================================


def _no_human_diamond() -> IRGraph:
    """The diamond with the sign-off replaced by a plain agent: forward
    execution reaches the conditional edges without any park."""
    g = _diamond_graph()
    nodes = [
        IRNode(id="signoff", kind="agent") if n.id == "signoff" else n
        for n in g.nodes
    ]
    return IRGraph(nodes=nodes, edges=g.edges)


class TestForwardResumeEquivalence:
    def test_forward_execution_routes_identically_to_resume(self, tmp_path):
        """has_ui=false routed forward (no park) and via park→resume must
        produce the same executed set — the two paths share the exclusion
        mechanism (the disease R5 cures is exactly their divergence)."""
        # Forward path: no human node, single run() call.
        fwd_ops = _store_ops(tmp_path / "fwd")
        fwd = RecordingExecutor({"analyze": _agent_done(has_ui=False)})
        fwd.state = fwd_ops
        fwd_final = workflow_runner.run(
            graph=_no_human_diamond(), executor=fwd, state_ops=fwd_ops
        )
        assert fwd_final.status == "done"

        # Park→resume path on the human-node variant of the same graph.
        res_ops = _store_ops(tmp_path / "res")
        ex1 = RecordingExecutor({"analyze": _agent_done(has_ui=False)})
        ex1.state = res_ops
        workflow_runner.run(graph=_diamond_graph(), executor=ex1, state_ops=res_ops)
        _approve_signoff(res_ops)
        ex2 = RecordingExecutor()
        ex2.state = res_ops
        res_final = workflow_runner.run(
            graph=_diamond_graph(), executor=ex2, state_ops=res_ops
        )
        assert res_final.status == "done"

        # Same executed set (modulo the sign-off, which is an agent in the
        # forward variant and a host-approved human node in the resume one).
        fwd_set = set(fwd.dispatched) - {"signoff"}
        resume_set = set(ex1.dispatched) | set(ex2.dispatched)
        assert fwd_set == resume_set, (
            f"forward {sorted(fwd_set)} vs resume {sorted(resume_set)} diverged"
        )
        assert "frontend" not in fwd_set
        # The persisted record must also be path-INDEPENDENT: resume replay
        # never re-records a fire into an already-done node at its post-run
        # generation (the two graph variants share the same edge list, so the
        # fingerprints agree and the records are directly comparable).
        fwd_record = fwd_ops.read().edges_evaluated
        res_record = res_ops.read().edges_evaluated
        assert fwd_record == res_record, (
            f"edges_evaluated diverged across paths:\n"
            f"  forward {fwd_record!r}\n  resume  {res_record!r}"
        )

    def test_forward_false_edge_recorded_excluded(self, tmp_path):
        """Fire-time exclusion feeds the same persisted record as seeding."""
        ops = _store_ops(tmp_path)
        ex = RecordingExecutor({"analyze": _agent_done(has_ui=False)})
        ex.state = ops
        final = workflow_runner.run(
            graph=_no_human_diamond(), executor=ex, state_ops=ops
        )
        assert final.status == "done"
        record = ops.read().edges_evaluated
        assert "frontend" in record["excluded"]
        assert record == final.edges_evaluated  # in-memory/disk agreement


# ===========================================================================
# 3. Multi-resume idempotency — each edge fires once across repeated parks
# ===========================================================================


def _two_park_graph() -> IRGraph:
    """analyze → signoff → {frontend|architect} → signoff2 → tail."""
    return IRGraph(
        nodes=[
            IRNode(id="analyze", kind="agent"),
            IRNode(id="signoff", kind="human", data={"prompt": "scope?"}),
            IRNode(id="frontend", kind="agent"),
            IRNode(id="architect", kind="agent"),
            IRNode(id="signoff2", kind="human", data={"prompt": "design?"}),
            IRNode(id="tail", kind="agent"),
        ],
        edges=[
            IREdge(source="analyze", target="signoff"),
            IREdge(source="signoff", target="frontend",
                   when="analyze.fields.has_ui == true"),
            IREdge(source="signoff", target="architect",
                   when="analyze.fields.has_ui == false"),
            IREdge(source="frontend", target="architect"),
            IREdge(source="architect", target="signoff2"),
            IREdge(source="signoff2", target="tail"),
        ],
    )


class TestMultiResumeIdempotency:
    def _drive(self, ops, graph) -> list[str]:
        """park → resume → park → resume until terminal; returns dispatches."""
        dispatched: list[str] = []
        for _ in range(6):  # defensive bound; this graph needs 3 cycles
            ex = RecordingExecutor({"analyze": _agent_done(has_ui=False)})
            ex.state = ops
            state = workflow_runner.run(graph=graph, executor=ex, state_ops=ops)
            dispatched.extend(ex.dispatched)
            if state.status != "blocked":
                assert state.status == "done"
                return dispatched
            persisted = ops.read()
            approved = {
                nid: {"status": "done"}
                for nid, ns in persisted.nodes.items()
                if ns.status == "blocked"
            }
            ops.write({"status": "running", "nodes": approved})
        raise AssertionError("run did not reach a terminal within 6 cycles")

    def test_each_node_executes_once_across_two_parks(self, tmp_path):
        ops = _store_ops(tmp_path)
        dispatched = self._drive(ops, _two_park_graph())
        assert dispatched == ["analyze", "architect", "tail"], (
            f"multi-resume replay double-fired or mis-routed: {dispatched}"
        )
        # The record survived both resumes with each edge decided exactly once.
        record = ops.read().edges_evaluated
        frontend_entries = record["excluded"].get("frontend", [])
        assert len(frontend_entries) == 1, (
            f"excluded edge re-recorded across resumes: {frontend_entries}"
        )

    def test_lossy_stateops_multi_resume_still_routes_once(self, tmp_path):
        """A StateOps that drops the record must degrade to re-evaluation and
        still execute each node exactly once across repeated resumes."""
        ops = LossyStateOps(_fresh_state())
        dispatched = self._drive(ops, _two_park_graph())
        assert dispatched == ["analyze", "architect", "tail"]
        assert ops.edge_writes > 0, "runner never attempted to persist the record"
        assert ops.read().edges_evaluated == {}, "test double must stay lossy"


# ===========================================================================
# 4. Pre-R5 state.json compatibility — no edges_evaluated on disk
# ===========================================================================


class TestPreR5StateCompatibility:
    def test_resume_from_pre_r5_state_json(self, tmp_path):
        """A hand-written pre-R5 state.json (no edges_evaluated key anywhere)
        must resume cleanly: conditions re-evaluated from the persisted typed
        scope, the false branch excluded, the join not starved."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "state.json").write_text(json.dumps({
            "spec": "r5", "run_id": "run-pre-r5", "status": "running",
            "budget": {"usd_ceiling": 0.0, "usd_spent": 0.0},
            "nodes": {
                "analyze": {"status": "done", "attempt": 1,
                            "artifact_paths": [], "fields": {"has_ui": False}},
                "signoff": {"status": "done", "attempt": 1,
                            "artifact_paths": []},
            },
        }, indent=2))
        ops = CronosStateOps(StateStore(run_dir), EventLog(run_dir))
        ex = RecordingExecutor()
        ex.state = ops
        final = workflow_runner.run(graph=_diamond_graph(), executor=ex, state_ops=ops)

        assert ex.dispatched == ["architect", "tail"]
        assert final.status == "done"
        # The rebuilt record is now persisted for the next resume.
        assert "frontend" in ops.read().edges_evaluated["excluded"]

    def test_malformed_edges_evaluated_record_is_tolerated(self, tmp_path):
        """A corrupt record degrades to re-evaluation instead of crashing."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "state.json").write_text(json.dumps({
            "spec": "r5", "run_id": "run-corrupt", "status": "running",
            "budget": {"usd_ceiling": 0.0, "usd_spent": 0.0},
            "edges_evaluated": {"fired": "not-a-dict", "excluded": {"x": [["a"]]}},
            "nodes": {
                "analyze": {"status": "done", "attempt": 1,
                            "artifact_paths": [], "fields": {"has_ui": False}},
                "signoff": {"status": "done", "attempt": 1,
                            "artifact_paths": []},
            },
        }, indent=2))
        ops = CronosStateOps(StateStore(run_dir), EventLog(run_dir))
        ex = RecordingExecutor()
        ex.state = ops
        final = workflow_runner.run(graph=_diamond_graph(), executor=ex, state_ops=ops)
        assert ex.dispatched == ["architect", "tail"]
        assert final.status == "done"


# ===========================================================================
# 4b. Graph-fingerprint guard — spec edited between park and resume
# ===========================================================================


class TestGraphFingerprintGuard:
    def test_stale_record_from_edited_graph_cannot_satisfy_join(self, tmp_path):
        """The record keys edges by positional index.  If the spec is edited
        while the run is parked, a persisted fire from old edge k would denote
        a DIFFERENT edge after recompilation — here it would pre-satisfy the
        join j on behalf of b, which never ran.  The fingerprint mismatch must
        discard the record and fall back to condition re-evaluation."""
        v1 = IRGraph(
            nodes=[
                IRNode(id="a", kind="agent"),
                IRNode(id="sign", kind="human", data={"prompt": "ok?"}),
                IRNode(id="sign2", kind="human", data={"prompt": "sure?"}),
                IRNode(id="b", kind="agent"),
                IRNode(id="j", kind="agent"),
            ],
            edges=[
                IREdge(source="a", target="sign"),
                IREdge(source="sign", target="sign2"),
                IREdge(source="sign2", target="b"),
                IREdge(source="a", target="j"),      # idx 3 in v1
                IREdge(source="b", target="j"),      # idx 4 in v1
            ],
        )
        # Same graph with the two j-edges swapped: old idx 3 (recorded as a
        # fired in-edge of j) now denotes b→j.
        v2 = IRGraph(
            nodes=v1.nodes,
            edges=[
                v1.edges[0], v1.edges[1], v1.edges[2],
                IREdge(source="b", target="j"),      # idx 3 in v2
                IREdge(source="a", target="j"),      # idx 4 in v2
            ],
        )

        ops = _store_ops(tmp_path)
        ex1 = RecordingExecutor()
        ex1.state = ops
        first = workflow_runner.run(graph=v1, executor=ex1, state_ops=ops)
        assert first.status == "blocked" and ex1.dispatched == ["a"]
        assert ops.read().edges_evaluated.get("graph_fingerprint")

        _approve_signoff_node(ops, "sign")
        ex2 = RecordingExecutor()
        ex2.state = ops
        second = workflow_runner.run(graph=v2, executor=ex2, state_ops=ops)

        # Still parked at sign2 — and j must NOT have run: without the
        # fingerprint discard, the stale (3, 0) fire (a→j in v1, b→j in v2)
        # plus the replayed a→j fire completes j's join while b is still
        # unreached behind the second sign-off.
        assert second.status == "blocked"
        assert "j" not in ex2.dispatched, (
            "stale positional edge record from the edited graph satisfied "
            "the join for a predecessor that never ran"
        )


def _approve_signoff_node(ops, node_id: str) -> None:
    ops.write({"status": "running", "nodes": {node_id: {"status": "done"}}})


# ===========================================================================
# 5. Exclusion + loop interaction
# ===========================================================================


class TestExclusionLoopInteraction:
    def test_excluded_branch_inside_fix_loop_stays_excluded(self, tmp_path):
        """p loops via its LoopPolicy and settles on iteration 2 with
        take_branch='no': the branch (and transitively its edge into the
        sink join) is excluded, the sink joined on {p, branch} fires exactly
        once, and the loop's own re-enqueue never enters the exclusion
        accounting (back-edges/LoopPolicy are out of scope for it)."""
        from ir import LoopPolicy

        g = IRGraph(
            nodes=[
                IRNode(id="p", kind="agent",
                       loop=LoopPolicy(until="p.fields.verdict == 'pass'", max=3)),
                IRNode(id="branch", kind="agent"),
                IRNode(id="sink", kind="agent"),
            ],
            edges=[
                IREdge(source="p", target="branch",
                       when="p.fields.take_branch == 'yes'"),
                IREdge(source="p", target="sink"),
                IREdge(source="branch", target="sink"),
            ],
        )
        ops = _store_ops(tmp_path)
        ex = RecordingExecutor({"p": [
            _agent_done(verdict="needs_fix", take_branch="no"),
            _agent_done(verdict="pass", take_branch="no"),
        ]})
        ex.state = ops
        final = workflow_runner.run(graph=g, executor=ex, state_ops=ops)

        assert final.status == "done"
        assert ex.count("p") == 2
        assert ex.count("branch") == 0
        assert ex.count("sink") == 1, (
            "sink starved or double-fired across the loop with an excluded branch"
        )
        assert "branch" in ops.read().edges_evaluated["excluded"]

    def test_branch_excluded_then_taken_on_later_iteration(self):
        """Iteration 1 (cyclic back-edge loop, chk routes back to p) excludes
        the branch; iteration 2 takes it: the fired edge must win over the
        stale same-generation exclusion record and the branch must execute."""
        g = IRGraph(
            nodes=[
                IRNode(id="p", kind="agent"),
                IRNode(id="branch", kind="agent"),
                IRNode(id="chk", kind="agent"),
            ],
            edges=[
                IREdge(source="p", target="branch",
                       when="p.fields.take_branch == 'yes'"),
                IREdge(source="p", target="chk"),
                # Back-edge (chk pos 2 → p pos 0): drives the second iteration.
                IREdge(source="chk", target="p",
                       when="chk.fields.loop == 'yes'"),
            ],
        )
        ex = RecordingExecutor({
            "p": [
                _agent_done(take_branch="no"),   # iteration 1: branch excluded
                _agent_done(take_branch="yes"),  # iteration 2: branch fires
            ],
            "chk": [
                _agent_done(loop="yes"),
                _agent_done(loop="no"),
            ],
        })
        final = workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert final.status == "done"
        assert ex.count("p") == 2
        assert ex.count("chk") == 2
        assert ex.count("branch") == 1, (
            "a stale exclusion from iteration 1 suppressed the fired branch"
        )


# ===========================================================================
# 6. Seeding still skips done nodes and joins wait for live predecessors
#    (guard: the R5 rewrite must not regress the R8/B1 seeding behaviors)
# ===========================================================================


class TestSeedingGuards:
    def test_resume_join_still_waits_for_live_predecessor(self):
        """One of two join predecessors done on resume: the join waits for the
        other's live execution — exclusion applies only to evaluated-false
        edges, not to not-yet-run predecessors."""
        g = IRGraph(
            nodes=[IRNode(id="b", kind="agent"), IRNode(id="c", kind="agent"),
                   IRNode(id="j", kind="agent")],
            edges=[IREdge(source="b", target="j"), IREdge(source="c", target="j")],
        )
        ops = LossyStateOps(_fresh_state(b=NodeState(status="done", attempt=1)))
        ex = RecordingExecutor()
        ex.state = ops
        final = workflow_runner.run(graph=g, executor=ex, state_ops=ops)

        assert ex.dispatched == ["c", "j"]
        assert final.status == "done"

    def test_resume_all_predecessors_done_seeds_join(self):
        g = IRGraph(
            nodes=[IRNode(id="b", kind="agent"), IRNode(id="c", kind="agent"),
                   IRNode(id="j", kind="agent")],
            edges=[IREdge(source="b", target="j"), IREdge(source="c", target="j")],
        )
        ops = LossyStateOps(_fresh_state(
            b=NodeState(status="done", attempt=1),
            c=NodeState(status="done", attempt=1),
        ))
        ex = RecordingExecutor()
        ex.state = ops
        final = workflow_runner.run(graph=g, executor=ex, state_ops=ops)

        assert ex.dispatched == ["j"]
        assert final.status == "done"
