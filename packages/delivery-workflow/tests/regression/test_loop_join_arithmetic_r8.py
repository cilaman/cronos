"""R8 regression tests — loop and join arithmetic (kills D8, D9).

Defects (00-assessment.md §2):
  D8 — loop attempt double-increment: dispatch set ``attempt = old + 1``
       (runner/dispatch.py) and the loop-back path incremented AGAIN
       (historically runner/loop.py:98), so ``loop.max=4`` yielded only 3
       executions with the counter overshooting to 5.  Loop budgets were
       roughly halved and gates/reviews escalated prematurely.
  D9 — loop-back re-execution double-decremented successors' ``in_degree``
       (clamped at 0), so a join fired before all of its predecessors ran —
       a node executed with missing inputs.

Contract (01-state-model.md §5.5):
  1. Single ``attempt`` owner — dispatch increments once per execution; the
     loop-back path never touches it.  ``loop.max=N`` ⇒ exactly N executions
     with final ``attempt == N``.
  2. Joins tracked by a fired-edge set keyed ``(edge, target generation)``
     instead of decrement-with-clamp: re-firing the same edge cannot
     double-satisfy a join.  The set is in-memory; resume seeding rebuilds it
     from persisted-``done`` nodes (R5's edge replay will own persistence).
  3. ``reset_downstream_nodes`` is wired from the loop-back/back-edge path:
     a re-execution resets downstream stale NodeState (status/artifacts/
     fields/gate) both in memory and through StateOps — with fields
     persisting (R2), the staleness would otherwise survive a park/resume.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_PKG = Path(__file__).parent.parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

import runner as workflow_runner  # noqa: E402
from adapters.cronos.adapter import CronosStateOps  # noqa: E402
from ir import IREdge, IRGraph, IRNode, LoopPolicy  # noqa: E402
from lib.state.events import EventLog  # noqa: E402
from lib.state.store import StateStore  # noqa: E402
from results import AgentResult, GateResult, TelemetryData  # noqa: E402
from runner.loop import reset_downstream_nodes  # noqa: E402
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
    """Scripted ExecutorInterface recording dispatches and their attempts.

    ``agent_script`` maps node_id → AgentResult or list thereof (consumed one
    per dispatch, last repeats).  ``gate_script`` likewise for GateResult.
    ``cond_script`` maps a condition expression to a bool or a list of bools
    (consumed one per evaluation, last repeats); unmatched expressions fall
    through to the real ``lib.conditions.eval_condition``.
    """

    def __init__(
        self,
        agent_script: dict[str, Any] | None = None,
        gate_script: dict[str, Any] | None = None,
        cond_script: dict[str, Any] | None = None,
    ) -> None:
        self.dispatched: list[tuple[str, int]] = []  # (node_id, attempt)
        self.scopes: dict[str, list[dict[str, Any]]] = {}  # node_id → scopes seen
        self.escalations: list[tuple[str, str]] = []
        self._agent_script = dict(agent_script or {})
        self._gate_script = dict(gate_script or {})
        self._cond_script = dict(cond_script or {})
        self.state = None  # optional StateOps, mirrored from CronosAdapter
        self.telemetry = self

    def emit(self, node_id: str, data: dict) -> None:  # TelemetryOps
        pass

    @staticmethod
    def _next(script: dict[str, Any], key: str, default: Any) -> Any:
        entry = script.get(key)
        if entry is None:
            return default
        if isinstance(entry, list):
            value = entry[0] if len(entry) == 1 else entry.pop(0)
            return value
        return entry

    def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult:
        node_id = inputs["node_id"]
        self.dispatched.append((node_id, inputs["attempt"]))
        self.scopes.setdefault(node_id, []).append(dict(inputs.get("scope") or {}))
        return self._next(self._agent_script, node_id, _agent_done())

    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult:
        node_id = gate["id"]
        # Gate attempts are read back from the runner's state write, so record
        # attempt=0 here and let per-test asserts read WorkflowState instead.
        self.dispatched.append((node_id, 0))
        return self._next(self._gate_script, node_id, GateResult(decision="proceed", errors=[]))

    def runExec(self, node_id: str, command: str, inputs: dict[str, Any]):
        raise NotImplementedError

    def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool:
        if expr in self._cond_script:
            return bool(self._next(self._cond_script, expr, False))
        from lib.conditions import eval_condition

        return eval_condition(expr, scope)

    def escalate(self, node_id: str, reason: str) -> None:
        self.escalations.append((node_id, reason))
        if self.state is not None:
            self.state.write({"status": "blocked"})

    # -- helpers -------------------------------------------------------------

    def executions(self, node_id: str) -> list[int]:
        """Attempt values recorded for *node_id*, in dispatch order."""
        return [att for nid, att in self.dispatched if nid == node_id]

    def count(self, node_id: str) -> int:
        return len(self.executions(node_id))


def _fresh_state(**nodes: NodeState) -> WorkflowState:
    return WorkflowState(
        spec="r8",
        run_id="run-r8",
        status="running",
        budget=BudgetState(usd_ceiling=0.0),
        nodes=dict(nodes),
    )


class _MergeStateOps:
    """Replica of the backend harness ``_StateOps`` semantics (no app import):

    - ``read()`` returns THE SAME WorkflowState object the runner mutates.
    - ``write(patch)`` MERGES ``fields`` (``{**existing, **patch}``) instead
      of replacing them — the divergence the R8 downstream reset must survive
      (the in-memory mutation clears the shared object first, so merging the
      explicit ``{}`` lands on already-cleared fields).
    """

    def __init__(self, initial: WorkflowState) -> None:
        self._state = initial

    def read(self) -> WorkflowState:
        return self._state

    def write(self, patch: dict[str, Any]) -> None:
        if "status" in patch:
            self._state.status = patch["status"]
        for nid, np in patch.get("nodes", {}).items():
            ns = self._state.nodes.get(nid)
            if ns is None:
                ns = NodeState(status=np.get("status", "pending"))
                self._state.nodes[nid] = ns
            if "status" in np:
                ns.status = np["status"]
            if "attempt" in np:
                ns.attempt = int(np["attempt"])
            if "artifact_paths" in np:
                ns.artifact_paths = list(np["artifact_paths"])
            if "gate" in np:
                ns.gate = np["gate"]
            if "fields" in np:
                ns.fields = {**(ns.fields or {}), **np["fields"]}


def _store_ops(tmp_path: Path) -> CronosStateOps:
    """Real replace-style persistence: StateStore + EventLog on disk."""
    ops = CronosStateOps(StateStore(tmp_path), EventLog(tmp_path))
    ops.bootstrap_if_absent(spec="r8", run_id="run-r8", usd_ceiling=0.0)
    return ops


# ===========================================================================
# 1. Single attempt owner (D8)
# ===========================================================================


class TestLoopBudget:
    def test_loop_max_yields_exactly_max_executions(self):
        """loop.max=4, until never met, on_exhaust=stop ⇒ 4 executions,
        final attempt=4 (D8 yielded 3 executions with attempt=5)."""
        g = IRGraph(
            nodes=[IRNode(
                id="r", kind="agent",
                loop=LoopPolicy(until="r.fields.verdict == 'pass'", max=4, on_exhaust="stop"),
            )],
        )
        ex = RecordingExecutor(agent_script={"r": _agent_done(verdict="fail")})
        state = workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert ex.count("r") == 4, f"loop.max=4 must yield 4 executions, got {ex.count('r')}"
        assert state.nodes["r"].attempt == 4, "final attempt must equal loop.max"
        assert state.status == "done"  # on_exhaust=stop drains without escalating
        assert ex.escalations == []

    def test_attempt_monotonic_single_increment(self):
        """The attempt handed to the executor increments by exactly 1 per
        execution: 1, 2, 3, 4 — never skipping (the double-increment produced
        1, 3, 5)."""
        g = IRGraph(
            nodes=[IRNode(
                id="r", kind="agent",
                loop=LoopPolicy(until="r.fields.verdict == 'pass'", max=4, on_exhaust="stop"),
            )],
        )
        ex = RecordingExecutor(agent_script={"r": _agent_done(verdict="fail")})
        workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert ex.executions("r") == [1, 2, 3, 4]

    def test_loop_exhaust_escalates_after_full_budget(self):
        """on_exhaust=escalate fires only after the FULL budget was spent."""
        g = IRGraph(
            nodes=[IRNode(
                id="r", kind="agent",
                loop=LoopPolicy(until="r.fields.verdict == 'pass'", max=3, on_exhaust="escalate"),
            )],
        )
        ex = RecordingExecutor(agent_script={"r": _agent_done(verdict="fail")})
        workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert ex.count("r") == 3
        assert len(ex.escalations) == 1
        assert ex.escalations[0][0] == "r"

    def test_until_met_exits_loop_with_correct_attempt(self):
        """needs_fix, needs_fix, pass ⇒ 3 executions, attempt=3, loop exits."""
        g = IRGraph(
            nodes=[IRNode(
                id="r", kind="agent",
                loop=LoopPolicy(until="r.fields.verdict == 'pass'", max=5, on_exhaust="escalate"),
            )],
        )
        ex = RecordingExecutor(agent_script={"r": [
            _agent_done(verdict="needs_fix"),
            _agent_done(verdict="needs_fix"),
            _agent_done(verdict="pass"),
        ]})
        state = workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert ex.executions("r") == [1, 2, 3]
        assert state.nodes["r"].attempt == 3
        assert state.status == "done"
        assert ex.escalations == []


# ===========================================================================
# 2. Join arithmetic (D9)
# ===========================================================================


def _d9_graph() -> IRGraph:
    """The D9 repro shape: r loops back once via a self back-edge; the join j
    needs BOTH r and s, but s is starved behind a never-true condition."""
    return IRGraph(
        nodes=[IRNode(id="r", kind="agent"), IRNode(id="s", kind="agent"),
               IRNode(id="j", kind="agent")],
        edges=[
            IREdge(source="r", target="r", when="LOOP_ONCE"),
            IREdge(source="r", target="j"),
            IREdge(source="s", target="j"),
            IREdge(source="r", target="s", when="NEVER"),
        ],
    )


class TestJoinArithmetic:
    def test_join_waits_for_all_predecessors_across_loop_back(self):
        """r executes twice (self back-edge) and re-fires r→j twice; the join
        must NOT fire — s never ran (D9: the double decrement made j execute
        with missing inputs)."""
        ex = RecordingExecutor(cond_script={"LOOP_ONCE": [True, False], "NEVER": False})
        workflow_runner.run(graph=_d9_graph(), executor=ex, state_ops=None)

        assert ex.count("r") == 2
        assert ex.count("s") == 0
        assert ex.count("j") == 0, (
            "join fired although predecessor 's' never ran (D9 double-satisfy)"
        )

    def test_join_fires_exactly_once_when_all_predecessors_ran(self):
        """Positive control: with both predecessors running (one of them via a
        loop-back re-fire), the join fires exactly once."""
        g = IRGraph(
            nodes=[IRNode(id="s", kind="agent"), IRNode(id="r", kind="agent"),
                   IRNode(id="j", kind="agent")],
            edges=[
                IREdge(source="s", target="j"),
                IREdge(source="r", target="r", when="LOOP_ONCE"),
                IREdge(source="r", target="j"),
            ],
        )
        ex = RecordingExecutor(cond_script={"LOOP_ONCE": [True, False]})
        state = workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert ex.count("s") == 1
        assert ex.count("r") == 2
        assert ex.count("j") == 1, "join must fire exactly once, not per re-fire"
        assert state.status == "done"

    def test_plain_diamond_join_still_fires(self):
        """No loops at all: a→(b,c)→j must still execute j exactly once."""
        g = IRGraph(
            nodes=[IRNode(id="a", kind="agent"), IRNode(id="b", kind="agent"),
                   IRNode(id="c", kind="agent"), IRNode(id="j", kind="agent")],
            edges=[
                IREdge(source="a", target="b"),
                IREdge(source="a", target="c"),
                IREdge(source="b", target="j"),
                IREdge(source="c", target="j"),
            ],
        )
        ex = RecordingExecutor()
        state = workflow_runner.run(graph=g, executor=ex, state_ops=None)

        assert ex.count("j") == 1
        assert state.status == "done"

    def test_resume_seeding_rebuilds_fired_edges_from_done_nodes(self):
        """The fired-edge set is in-memory; on resume it is rebuilt by
        replaying forward out-edges of persisted-done nodes, so a join whose
        predecessors are all done is seeded ready."""
        g = IRGraph(
            nodes=[IRNode(id="b", kind="agent"), IRNode(id="c", kind="agent"),
                   IRNode(id="j", kind="agent")],
            edges=[IREdge(source="b", target="j"), IREdge(source="c", target="j")],
        )
        seeded = _fresh_state(
            b=NodeState(status="done", attempt=1),
            c=NodeState(status="done", attempt=1),
        )
        ops = _MergeStateOps(seeded)
        ex = RecordingExecutor()
        ex.state = ops
        state = workflow_runner.run(graph=g, executor=ex, state_ops=ops)

        assert ex.count("b") == 0 and ex.count("c") == 0  # done → skipped
        assert ex.count("j") == 1
        assert state.status == "done"

    def test_resume_join_waits_when_one_predecessor_not_done(self):
        """On resume with only ONE of two join predecessors done, the join
        waits for the other predecessor's live execution (no blanket
        over-satisfaction from the single done node)."""
        g = IRGraph(
            nodes=[IRNode(id="b", kind="agent"), IRNode(id="c", kind="agent"),
                   IRNode(id="j", kind="agent")],
            edges=[IREdge(source="b", target="j"), IREdge(source="c", target="j")],
        )
        seeded = _fresh_state(b=NodeState(status="done", attempt=1))
        ops = _MergeStateOps(seeded)
        ex = RecordingExecutor()
        ex.state = ops
        state = workflow_runner.run(graph=g, executor=ex, state_ops=ops)

        dispatch_order = [nid for nid, _ in ex.dispatched]
        assert dispatch_order == ["c", "j"], (
            "j must run after (and only after) the not-yet-done predecessor c"
        )
        assert state.status == "done"


# ===========================================================================
# 3. Downstream reset wired from the loop-back / back-edge path
# ===========================================================================


def _stale_branch_graph() -> IRGraph:
    """p → branch (conditional), p → gate(loop max=3), gate → sink | back to p.

    Iteration 1 takes the branch (stale fields written) and the gate says
    needs_fix (back-edge to p).  Iteration 2 skips the branch and proceeds.
    Without the wired downstream reset, `branch` keeps its iteration-1 fields
    forever — persistently, now that fields persist (R2).
    """
    return IRGraph(
        nodes=[
            IRNode(id="p", kind="agent"),
            IRNode(id="branch", kind="agent"),
            IRNode(
                id="gate", kind="gate",
                loop=LoopPolicy(until="gate.decision == 'proceed'", max=3),
            ),
            IRNode(id="sink", kind="agent"),
        ],
        edges=[
            IREdge(source="p", target="branch", when="p.fields.take_branch == 'yes'"),
            IREdge(source="p", target="gate"),
            IREdge(source="gate", target="sink", when="gate.decision == 'proceed'"),
            IREdge(source="gate", target="p", when="gate.decision != 'proceed'"),
        ],
    )


def _stale_branch_executor() -> RecordingExecutor:
    return RecordingExecutor(
        agent_script={
            "p": [_agent_done(take_branch="yes"), _agent_done(take_branch="no")],
            "branch": _agent_done(stale="iteration-one"),
        },
        gate_script={"gate": [
            GateResult(decision="needs_fix", errors=["fix"]),
            GateResult(decision="proceed", errors=[]),
        ]},
    )


class TestDownstreamResetOnBackEdge:
    def test_back_edge_fire_clears_downstream_stale_fields(self):
        """The gate's back-edge fire to p must reset p's forward-downstream
        nodes: `branch` (not re-taken in iteration 2) ends the run cleared —
        status pending, fields/artifacts/gate zeroed — instead of leaking its
        iteration-1 fields into scope and state."""
        ex = _stale_branch_executor()
        state = workflow_runner.run(graph=_stale_branch_graph(), executor=ex, state_ops=None)

        assert state.status == "done"
        assert ex.count("p") == 2
        assert ex.count("branch") == 1  # taken only in iteration 1
        assert ex.count("sink") == 1

        branch = state.nodes["branch"]
        assert branch.status == "pending", "stale branch must be reset, not left 'done'"
        assert branch.fields == {}, f"stale fields survived the back-edge reset: {branch.fields}"
        assert branch.artifact_paths == []

        # And the stale value must be gone from the scope of every dispatch
        # AFTER the back-edge fire (p's 2nd run, the gate re-check, sink).
        for later_scope in ex.scopes["p"][1:] + ex.scopes["sink"]:
            assert "branch.fields.stale" not in later_scope, (
                "iteration-1 fields leaked into a post-reset scope"
            )

    def test_back_edge_reset_persisted_through_replace_style_stateops(self, tmp_path):
        """Replace-style StateOps (StateStore + CronosStateOps, the delivery
        driver's persistence): the reset must be WRITTEN, so the staleness
        cannot survive a park/resume (fields persist since R2)."""
        ops = _store_ops(tmp_path)
        ex = _stale_branch_executor()
        ex.state = ops
        state = workflow_runner.run(graph=_stale_branch_graph(), executor=ex, state_ops=ops)

        assert state.status == "done"
        persisted = ops.read()
        assert persisted.nodes["branch"].status == "pending"
        assert persisted.nodes["branch"].fields == {}, (
            "stale fields survived ON DISK — the reset was not persisted"
        )

    def test_back_edge_reset_identical_under_merge_style_stateops(self):
        """Merge-style StateOps (the backend harness ``_StateOps`` semantics —
        shares the state object with the runner, merges `fields` on write)
        must end with the same cleared values as the replace-style one."""
        ops = _MergeStateOps(_fresh_state())
        ex = _stale_branch_executor()
        ex.state = ops
        state = workflow_runner.run(graph=_stale_branch_graph(), executor=ex, state_ops=ops)

        assert state.status == "done"
        persisted = ops.read()
        assert persisted.nodes["branch"].status == "pending"
        assert persisted.nodes["branch"].fields == {}, (
            "merge-style StateOps diverged from replace-style on the reset"
        )

    def test_loop_policy_loop_back_resets_downstream_stale_state(self):
        """Site: a node's OWN LoopPolicy loop-back.  A downstream node holding
        persisted stale state (resumed run) is reset when the loop re-enqueues,
        and the looping node's later scopes no longer see the stale fields."""
        g = IRGraph(
            nodes=[
                IRNode(
                    id="L", kind="agent",
                    loop=LoopPolicy(until="L.fields.verdict == 'pass'", max=3),
                ),
                IRNode(id="d", kind="agent"),
            ],
            edges=[IREdge(source="L", target="d")],
        )
        # Resumed state: d holds stale fields from a previous life; L not run.
        seeded = _fresh_state(
            d=NodeState(status="done", attempt=1, fields={"stale": "old"}),
        )
        ops = _MergeStateOps(seeded)
        ex = RecordingExecutor(agent_script={"L": [
            _agent_done(verdict="needs_fix"),
            _agent_done(verdict="pass"),
        ]})
        ex.state = ops
        state = workflow_runner.run(graph=g, executor=ex, state_ops=ops)

        assert state.status == "done"
        assert ex.executions("L") == [1, 2]
        # L's loop-back reset d; the forward fire then re-executed it.
        assert ex.count("d") == 1
        assert "d.fields.stale" not in ex.scopes["L"][1], (
            "stale downstream fields leaked into the loop's second iteration"
        )
        assert state.nodes["d"].fields == {}  # re-run wrote fresh (empty) fields

    def test_resume_reexecutes_persisted_pending_chain(self):
        """A chain reset-then-parked (b persisted 'pending' with attempt>0)
        resumes by re-dispatching b (attempt continues) and proceeding to c —
        the persisted reset is resumable, not a dead node."""
        g = IRGraph(
            nodes=[IRNode(id="a", kind="agent"), IRNode(id="b", kind="agent"),
                   IRNode(id="c", kind="agent")],
            edges=[IREdge(source="a", target="b"), IREdge(source="b", target="c")],
        )
        seeded = _fresh_state(
            a=NodeState(status="done", attempt=1),
            b=NodeState(status="pending", attempt=2),  # reset before the park
        )
        ops = _MergeStateOps(seeded)
        ex = RecordingExecutor()
        ex.state = ops
        state = workflow_runner.run(graph=g, executor=ex, state_ops=ops)

        assert ex.executions("b") == [3], "attempt must continue from the persisted value"
        assert ex.count("c") == 1
        assert state.status == "done"


# ===========================================================================
# 4. reset_downstream_nodes unit behavior (return value, skip, persistence)
# ===========================================================================


class TestResetDownstreamNodesUnit:
    def test_returns_reset_ids_and_writes_through_stateops(self):
        state = _fresh_state(
            stale=NodeState(status="done", fields={"v": "1"}, artifact_paths=["a.md"],
                            gate={"decision": "proceed"}, attempt=2),
            clear=NodeState(status="pending"),
        )
        ops = _MergeStateOps(state)
        reset = reset_downstream_nodes("src", state, ["stale", "clear", "missing"], state_ops=ops)

        assert reset == ["stale"]  # clear → skipped, missing → skipped
        ns = state.nodes["stale"]
        assert (ns.status, ns.artifact_paths, ns.fields, ns.gate) == ("pending", [], {}, None)
        assert ns.attempt == 2, "attempt must survive the reset (dispatch owns it)"

    def test_persists_reset_via_replace_style_stateops(self, tmp_path):
        ops = _store_ops(tmp_path)
        ops.write({"nodes": {"stale": {
            "status": "done", "attempt": 1, "artifact_paths": ["x.md"],
            "gate": {"decision": "needs_fix"}, "fields": {"v": "old"},
        }}})
        state = ops.read()
        reset = reset_downstream_nodes("src", state, ["stale"], state_ops=ops)

        assert reset == ["stale"]
        persisted = ops.read()
        ns = persisted.nodes["stale"]
        assert (ns.status, ns.artifact_paths, ns.fields, ns.gate) == ("pending", [], {}, None)
        assert ns.attempt == 1

    def test_no_stateops_still_resets_in_memory(self):
        state = _fresh_state(stale=NodeState(status="done", fields={"v": "1"}))
        reset = reset_downstream_nodes("src", state, ["stale"])
        assert reset == ["stale"]
        assert state.nodes["stale"].status == "pending"
        assert state.nodes["stale"].fields == {}
