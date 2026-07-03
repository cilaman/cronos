#!/usr/bin/env python3
"""Empirical repros for delivery/v2 defects, run against the REAL package code
at HEAD (8118f5b). Each section prints PASS (defect confirmed) or the observed
behavior. No Cronos backend needed except D6 (trace_parser)."""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

# Repo root: first CLI arg > CRONOS_REPO env > current directory.
# Usage from a cronos checkout:  python3 repro_delivery_v2.py .
_arg = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CRONOS_REPO", ".")
REPO = Path(_arg).resolve()
if not (REPO / "packages" / "delivery-workflow").is_dir():
    sys.exit(f"error: {REPO} does not look like a cronos checkout "
             "(pass the repo root as the first argument)")
sys.path.insert(0, str(REPO / "packages" / "delivery-workflow"))
sys.path.insert(0, str(REPO / "backend"))

from ir import IREdge, IRGraph, IRNode  # noqa: E402
from state_types import BudgetState, NodeState, WorkflowState  # noqa: E402
from results import AgentResult, TelemetryData  # noqa: E402
import runner as workflow_runner  # noqa: E402
from runner.scope import build_scope  # noqa: E402
from lib.conditions import eval_condition  # noqa: E402
from lib.node_status import parse_node_status  # noqa: E402


def hr(title: str) -> None:
    print(f"\n{'='*74}\n{title}\n{'='*74}")


# ---------------------------------------------------------------------------
# Shared test doubles: honest executor + persistent StateOps.
# The executor records every dispatch so we can see WHICH nodes ran.
# ---------------------------------------------------------------------------
class RecordingExecutor:
    def __init__(self, agent_results: dict[str, AgentResult] | None = None,
                 cond_script: dict[str, bool] | None = None):
        self.dispatched: list[str] = []
        self.escalations: list[tuple[str, str]] = []
        self._agent_results = agent_results or {}
        self._cond_script = cond_script  # None => use real lib.conditions
        self.state = None   # filled by attach
        self.telemetry = self

    def emit(self, node_id, data):
        pass

    def dispatchAgent(self, agent_ref, inputs):
        nid = inputs["node_id"]
        self.dispatched.append(nid)
        return self._agent_results.get(nid, AgentResult(
            status="done", artifact_paths=[f"/tmp/{nid}.md"], produces="x",
            fields={}, open_questions=[],
            telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0)))

    def runGate(self, gate, artifact_paths):
        raise NotImplementedError

    def runExec(self, node_id, command, inputs):
        raise NotImplementedError

    def evalCondition(self, expr, scope):
        if self._cond_script is not None and expr in self._cond_script:
            return self._cond_script[expr]
        # mirrors CronosAdapter.evalCondition (R3: typed pass-through, no str() coercion)
        return eval_condition(expr, scope)

    def escalate(self, node_id, reason):
        self.escalations.append((node_id, reason))
        if self.state is not None:                      # mirrors CronosAdapter.escalate
            self.state.write({"status": "blocked"})


class MemStateOps:
    """In-memory StateOps that mimics CronosStateOps.write field-handling
    faithfully when drop_fields=True (status/attempt/artifact_paths/gate only,
    per adapter.py CronosStateOps.write + lib/state/store.py _serialize)."""

    def __init__(self, initial: WorkflowState, drop_fields: bool = True):
        self._state = copy.deepcopy(initial)
        self.drop_fields = drop_fields

    def read(self) -> WorkflowState:
        return copy.deepcopy(self._state)

    def write(self, patch):
        if "status" in patch:
            self._state.status = patch["status"]
        if "stall" in patch:  # R6 run-level stall detail (mirrors CronosStateOps)
            self._state.stall = patch["stall"]
        if "resume_retries" in patch:  # R7 RetryFailed counters (mirrors CronosStateOps)
            self._state.resume_retries = dict(patch["resume_retries"] or {})
        if "budget" in patch and isinstance(patch["budget"], dict):  # R7 RaiseBudget
            if "usd_ceiling" in patch["budget"]:
                self._state.budget.usd_ceiling = float(patch["budget"]["usd_ceiling"])
            if "usd_spent" in patch["budget"]:
                self._state.budget.usd_spent = float(patch["budget"]["usd_spent"])
        for nid, ns_patch in patch.get("nodes", {}).items():
            node = self._state.nodes.setdefault(nid, NodeState(status="pending"))
            if "status" in ns_patch:
                node.status = ns_patch["status"]
            if "artifact_paths" in ns_patch:
                node.artifact_paths = list(ns_patch["artifact_paths"])
            if "gate" in ns_patch:
                node.gate = ns_patch["gate"]
            if "attempt" in ns_patch:
                node.attempt = int(ns_patch["attempt"])
            if not self.drop_fields and "fields" in ns_patch:
                node.fields = dict(ns_patch["fields"])


def fresh_state() -> WorkflowState:
    return WorkflowState(spec="t", run_id="r", status="running",
                         budget=BudgetState(usd_ceiling=0.0))


def node(nid, kind="agent", data=None, loop=None):
    return IRNode(id=nid, kind=kind, data=data or {}, loop=loop)


# ===========================================================================
# D1 — Resume seeding fires conditional edges unconditionally
#      (wrong nodes spawned after every human sign-off / park+resume)
# ===========================================================================
hr("D1  Resume seeding ignores edge conditions (runner/core.py:116-134)")
g = IRGraph(
    nodes=[node("analyze"), node("signoff", kind="human", data={"prompt": "ok?"}),
           node("frontend"), node("architect")],
    edges=[IREdge(source="analyze", target="signoff", when="", port=None),
           IREdge(source="signoff", target="frontend",
                  when="analyze.fields.has_ui == 'yes'", port=None),
           IREdge(source="signoff", target="architect",
                  when="analyze.fields.has_ui == 'no'", port=None),
           IREdge(source="frontend", target="architect", when="", port=None)],
    metadata={}, variables={})

# Run 1: analyze says has_ui = 'no' (string, so conditions CAN work here).
ex1 = RecordingExecutor(agent_results={"analyze": AgentResult(
    status="done", artifact_paths=[], produces="analysis",
    fields={"has_ui": "no"}, open_questions=[],
    telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0))})
ops = MemStateOps(fresh_state(), drop_fields=False)  # keep fields: isolate D1 from D2
ex1.state = ops
s = workflow_runner.run(graph=g, executor=ex1, state_ops=ops)
print(f"run 1: dispatched={ex1.dispatched}  run.status={s.status}  "
      f"(human node blocked as expected)")

# Simulate delivery_driver._resume_from_blocked verbatim: blocked human -> done,
# run status -> running.  (delivery_driver.py:318-367)
ops.write({"status": "running", "nodes": {"signoff": {"status": "done"}}})

ex2 = RecordingExecutor()
ex2.state = ops
s = workflow_runner.run(graph=g, executor=ex2, state_ops=ops)
print(f"run 2 (resume): dispatched={ex2.dispatched}  run.status={s.status}")
wrong = "frontend" in ex2.dispatched
print(f"--> has_ui='no', yet frontend dispatched on resume: {wrong}  "
      f"{'DEFECT CONFIRMED' if wrong else 'not reproduced'}")

# ===========================================================================
# D2 — NodeState.fields are dropped by persistence
#      (lib/state/store.py:_serialize + CronosStateOps.write)
# ===========================================================================
hr("D2  fields not persisted by the real StateStore (lib/state/store.py:41-63)")
import tempfile  # noqa: E402
from lib.state.store import StateStore  # noqa: E402
from lib.state.events import EventLog  # noqa: E402
sys.path.insert(0, str(REPO / "packages" / "delivery-workflow" / "adapters" / "cronos"))
from adapters.cronos.adapter import CronosStateOps  # noqa: E402

with tempfile.TemporaryDirectory() as td:
    st = StateStore(Path(td))
    st.write(fresh_state())
    cops = CronosStateOps(st, EventLog(Path(td)))
    cops.write({"nodes": {"analyze": {
        "status": "done", "attempt": 1, "artifact_paths": ["a.md"],
        "gate": None, "fields": {"has_ui": "no", "verdict": "pass"}}}})
    back = cops.read()
    print(f"wrote fields={{'has_ui': 'no', 'verdict': 'pass'}}; "
          f"read back fields={back.nodes['analyze'].fields!r}")
    scope = build_scope(back)
    print(f"scope after reload: {scope}")
    lost = back.nodes["analyze"].fields == {} and "analyze.fields.verdict" not in scope
    print(f"--> all field-based routing dead after any resume: {lost}  "
          f"{'DEFECT CONFIRMED' if lost else 'not reproduced'}")

# ===========================================================================
# D3 — JSON booleans must route through the typed scope/condition path.
# R3 mechanism change: build_scope keeps typed scalars and
# CronosAdapter.evalCondition passes the scope through UN-coerced (the old
# {k: str(v)} coercion produced 'True', matching neither spec branch).
# This section exercises the NEW path end-to-end: typed scope from
# build_scope -> eval_condition, '== true' branch match plus an exists()
# presence guard.  DEFECT CONFIRMED = has_ui routing still dead.
# ===========================================================================
hr("D3  JSON boolean routing via typed scope (scope.py + conditions.py + adapter.evalCondition)")
ns = NodeState(status="done", fields={"has_ui": True})
ws = fresh_state()
ws.nodes["analyze"] = ns
scope = build_scope(ws)  # typed scope — adapter.evalCondition passes it through as-is
t = eval_condition("analyze.fields.has_ui == true", scope)
f = eval_condition("analyze.fields.has_ui == false", scope)
present = eval_condition("exists(analyze.fields.has_ui)", scope)
absent = eval_condition("exists(analyze.fields.missing)", scope)
missing_ne = eval_condition("analyze.fields.missing != x", scope)  # v1 footgun: was True
print(f"fields={{'has_ui': True}} (JSON bool per agents/analyst.md:29) -> "
      f"scope value {scope['analyze.fields.has_ui']!r}")
print(f"'== true' -> {t}   '== false' -> {f}   exists(has_ui) -> {present}   "
      f"exists(missing) -> {absent}   missing '!=' -> {missing_ne}")
broken = not (t and not f and present and not absent and not missing_ne)
print(f"--> has_ui spec-branch routing (delivery.workflow.yaml:212-213) dead: "
      f"{broken}  {'DEFECT CONFIRMED' if broken else 'not reproduced'}")

# ===========================================================================
# D4 — Unknown fence status must never classify as done.
# R1 mechanism change: the fence TRANSPORT stays open (lib/node_status.py),
# but CronosAdapter.dispatchAgent now closes the vocabulary at the boundary —
# a status outside {done, blocked, needs_fix, failed} maps to failed with an
# 'unknown_status:<raw>' marker, and the runner never sees the raw string.
# This section exercises the NEW path: a trace whose structured node_status
# says "WAIT" goes through the real adapter, and the resulting AgentResult is
# fed to the runner.  DEFECT CONFIRMED = 'WAIT' still ends up node/run done.
# ===========================================================================
hr("D4  Unknown agent status via adapter closed-vocabulary boundary (adapter.py dispatchAgent)")
from types import SimpleNamespace as _NS  # noqa: E402
from adapters.cronos.adapter import CronosAdapter  # noqa: E402

blk = parse_node_status('```node_status\n{"status": "WAIT", "artifact_paths": [],'
                        ' "produces": "x", "fields": {}, "open_questions": []}\n```')
print(f"fence status accepted by transport parser: {blk.status!r} (transport stays open)")

trace4 = _NS(turns=[], duration_seconds=0.0, final_text_snippet="",
             node_status={"status": "WAIT", "artifact_paths": [], "produces": "x",
                          "fields": {}, "open_questions": []})
with tempfile.TemporaryDirectory() as td4:
    ad4 = CronosAdapter(store=object(), trace_store=object(), space_id="s",
                        run_dir=Path(td4), run_child=lambda ref, inp: trace4)
    res4 = ad4.dispatchAgent("a", {"node_id": "a"})
marker4 = any(str(q).startswith("unknown_status:") for q in res4.open_questions)
print(f"adapter-boundary AgentResult: status={res4.status!r} "
      f"open_questions={res4.open_questions!r}")

ex4 = RecordingExecutor(agent_results={"a": res4})
g4 = IRGraph(nodes=[node("a")], edges=[], metadata={}, variables={})
s4 = workflow_runner.run(graph=g4, executor=ex4, state_ops=None)
print(f"agent said 'WAIT'; node status recorded: {s4.nodes['a'].status!r}; "
      f"run status: {s4.status!r}")
ok = (res4.status == "done" or s4.nodes["a"].status == "done"
      or s4.status == "done" or not marker4)
print(f"--> agent 'WAIT' classified as workflow success (or marker missing): {ok}  "
      f"{'DEFECT CONFIRMED' if ok else 'not reproduced'}")

# ===========================================================================
# D5 — No completeness invariant: starved node, run still 'done'.
# R6 mechanism change: at work-list drain the runner PROVES completeness —
# every node executed or excluded-with-proof (an evaluated-false edge counts
# only if its source routed somewhere) — else it terminates 'stalled' with
# machine-readable run-level detail in state.stall ({kind, nodes, reason}).
# Same defect scenario: a's only edge condition is false, a routed nowhere,
# b is starved.  DEFECT CONFIRMED = the partial run still reports 'done'.
# ===========================================================================
hr("D5  Condition-starved node -> completeness invariant at drain (runner/core.py)")
g5 = IRGraph(
    nodes=[node("a"), node("b")],
    edges=[IREdge(source="a", target="b", when="a.fields.go == 'yes'", port=None)],
    metadata={}, variables={})
ex5 = RecordingExecutor(agent_results={"a": AgentResult(
    status="done", artifact_paths=[], produces="x", fields={"go": "no"},
    open_questions=[], telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0))})
s5 = workflow_runner.run(graph=g5, executor=ex5, state_ops=None)
print(f"dispatched={ex5.dispatched}; 'b' never ran; run status={s5.status!r}; "
      f"'b' in state.nodes: {'b' in s5.nodes}")
print(f"run-level stall detail: {getattr(s5, 'stall', None)!r}")
ok = s5.status == "done" and "b" not in ex5.dispatched
print(f"--> partial execution reported as success: {ok}  "
      f"{'DEFECT CONFIRMED' if ok else 'not reproduced'}")

# ===========================================================================
# D6 — Loop attempt double-increment: max=4 yields fewer executions.
# R8 mechanism change: dispatch is the SINGLE attempt owner (attempt=old+1
# once per execution); the loop-back second increment in runner/loop.py is
# deleted.  Same defect scenario, same runner entry point — loop.max=4 must
# yield exactly 4 executions with final attempt=4.
# DEFECT CONFIRMED = the loop budget is still cut short.
# ===========================================================================
hr("D6  Loop attempt double-increment (single owner in dispatch.py since R8)")
from ir import LoopPolicy  # noqa: E402
g6 = IRGraph(
    nodes=[node("r", loop=LoopPolicy(until="r.fields.verdict == 'pass'",
                                     max=4, on_exhaust="stop", stall=[]))],
    edges=[], metadata={}, variables={})
ex6 = RecordingExecutor(agent_results={"r": AgentResult(
    status="done", artifact_paths=[], produces="x", fields={"verdict": "fail"},
    open_questions=[], telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0))})
s6 = workflow_runner.run(graph=g6, executor=ex6, state_ops=None)
print(f"loop.max=4, until never met -> executions={len(ex6.dispatched)}, "
      f"final attempt={s6.nodes['r'].attempt}")
ok = len(ex6.dispatched) < 4
print(f"--> loop budget halved by double increment: {ok}  "
      f"{'DEFECT CONFIRMED (' + str(len(ex6.dispatched)) + ' of 4)' if ok else 'not reproduced'}")

# ===========================================================================
# D7 — Loop-back re-fire double-satisfies a join: join fires prematurely.
# R8 mechanism change: the in_degree decrement-with-clamp is replaced by a
# fired-edge set keyed (edge, target generation), so re-firing the same edge
# de-duplicates.
# R5 mechanism change: a forward edge that evaluates FALSE now records an
# EXCLUSION that propagates transitively (runner/core.py _apply_exclusion) —
# a predecessor gated behind a never-true edge is provably excluded and the
# join's requirement drops to its non-excluded in-edges (the same rule that
# routes the shipped spec's signoff→frontend/architect diamond).  "j ran
# although s never ran" therefore stopped being a defect observable when s is
# excluded; the join defect is checked two ways instead:
#   (a) ordering with a FIRING sibling: a loop-back re-fire must not satisfy
#       the join on s's behalf — j must dispatch after s (D9 double-decrement
#       dispatched j first);
#   (b) exclusion contract: with s excluded, j must run exactly once, after
#       the loop settles, and s must never run (a starved join here means the
#       R5 exclusion propagation regressed).
# DEFECT CONFIRMED = either check violated.
# ===========================================================================
hr("D7  Premature join after loop-back (fired-edge set + R5 exclusion, core.py)")
loop_calls = {"n": 0}
class LoopOnceExec(RecordingExecutor):
    def evalCondition(self, expr, scope):
        if expr == "LOOP_ONCE":
            loop_calls["n"] += 1
            return loop_calls["n"] == 1   # loop back exactly once
        if expr == "NEVER":
            return False
        return super().evalCondition(expr, scope)

# (a) firing sibling: s fires late; a double-satisfied join dispatches j early.
g7a = IRGraph(
    nodes=[node("r"), node("s"), node("j")],
    edges=[IREdge(source="r", target="r", when="LOOP_ONCE", port=None),
           IREdge(source="r", target="j", when="", port=None),
           IREdge(source="s", target="j", when="", port=None),
           IREdge(source="r", target="s", when="", port=None)],
    metadata={}, variables={})
ex7a = LoopOnceExec()
workflow_runner.run(graph=g7a, executor=ex7a, state_ops=None)
print(f"(a) firing sibling: dispatched={ex7a.dispatched}")
premature = (ex7a.dispatched.count("j") != 1
             or "s" not in ex7a.dispatched
             or ex7a.dispatched.index("j") < ex7a.dispatched.index("s"))

# (b) excluded sibling: NEVER-gated s is excluded; join must not starve.
loop_calls["n"] = 0
g7b = IRGraph(
    nodes=[node("r"), node("s"), node("j")],
    edges=[IREdge(source="r", target="r", when="LOOP_ONCE", port=None),
           IREdge(source="r", target="j", when="", port=None),
           IREdge(source="s", target="j", when="", port=None),
           # s is gated behind a condition that never fires -> excluded (R5):
           IREdge(source="r", target="s", when="NEVER", port=None)],
    metadata={}, variables={})
ex7b = LoopOnceExec()
workflow_runner.run(graph=g7b, executor=ex7b, state_ops=None)
print(f"(b) excluded sibling: dispatched={ex7b.dispatched}")
excl_broken = (ex7b.dispatched.count("j") != 1
               or "s" in ex7b.dispatched
               or ex7b.dispatched.count("r") != 2
               or ex7b.dispatched[-1] != "j")

ok = premature or excl_broken
print(f"--> premature join (a): {premature}; exclusion contract broken (b): "
      f"{excl_broken}  {'DEFECT CONFIRMED' if ok else 'not reproduced'}")

# ===========================================================================
# D8 — Fence after long prose must survive classification.
# R1 mechanism change: the envelope is parsed from the FULL final assistant
# text at trace-extraction time into the structured RunTrace.node_status
# field, and CronosAdapter.dispatchAgent reads THAT field — final_text_snippet
# (still head-truncated to 2,000 chars, unchanged) is a UI nicety, no longer
# load-bearing.  This section runs the same defect scenario (long prose, fence
# at the very end) through the NEW path end-to-end: raw events →
# extract_run_trace → real adapter classification.
# DEFECT CONFIRMED = the successful agent is still classified failed.
# ===========================================================================
hr("D8  Long prose + fence at end via RunTrace.node_status (trace_parser + adapter)")
from datetime import UTC, datetime as _dt  # noqa: E402
from app.trace_parser import extract_run_trace  # noqa: E402
fence = ('```node_status\n{"status": "done", "artifact_paths": ["r.md"], '
         '"produces": "research", "fields": {}, "open_questions": []}\n```')
final_text = ("Summary of the work I did.\n" * 400) + fence   # ~10.8k chars prose first
events8 = [{"type": "assistant",
            "message": {"usage": {}, "content": [{"type": "text", "text": final_text}]}}]
t8 = extract_run_trace(events8, task_id="t", space_id="s", run_index=0, model="m",
                       mode="auto", started_at=_dt.now(tz=UTC), ended_at=_dt.now(tz=UTC),
                       exit_reason="DONE", session_id=None, had_crash=False)
print(f"final_text={len(final_text)} chars, fence at end; snippet keeps HEAD "
      f"{len(t8.final_text_snippet)} chars; fence in snippet: "
      f"{parse_node_status(t8.final_text_snippet) is not None}; "
      f"trace.node_status parsed: {t8.node_status is not None}")
with tempfile.TemporaryDirectory() as td8:
    ad8 = CronosAdapter(store=object(), trace_store=object(), space_id="s",
                        run_dir=Path(td8), run_child=lambda ref, inp: t8)
    res8 = ad8.dispatchAgent("a", {"node_id": "a"})
print(f"adapter classification of the successful agent: {res8.status!r}")
ok = res8.status != "done"
print(f"--> successful agent classified {res8.status!r} (fence lost): {ok}  "
      f"{'DEFECT CONFIRMED' if ok else 'not reproduced'}")

# ===========================================================================
# D9 — Persisted 'escalated' run can never resume (livelock).
# R7 mechanism change: the halt on BARE run() is now CORRECT, SEALED behavior
# (top-of-run guard, runner/core.py) — the defect was that no legal re-entry
# existed.  runner/resume.py is that re-entry: resume(state_ops, graph, event)
# applies one typed event (HumanAnswer / RetryFailed / RaiseBudget / Nothing)
# and flips the run back to 'running' before delegating to run().  This
# section runs BOTH halves: bare run() must still halt without dispatching
# (sealed), and resume(RaiseBudget) — the external-mitigation event for a
# policy/budget escalation — must make real progress.
# DEFECT CONFIRMED = the sealed halt broke OR the resume re-entry makes no
# progress (the pre-R7 answer→halt→WAITING-forever livelock).
# ===========================================================================
hr("D9  'escalated' resume re-entry (runner/resume.py; bare run() stays sealed)")
from runner import RaiseBudget, resume as workflow_resume  # noqa: E402

g9 = IRGraph(nodes=[node("a")], edges=[], metadata={}, variables={})
st9 = fresh_state()
st9.status = "escalated"
ops9 = MemStateOps(st9)
ex9 = RecordingExecutor()
ex9.state = ops9

# Half 1 — bare run() on the persisted escalation: sealed, no dispatch.
s9 = workflow_runner.run(graph=g9, executor=ex9, state_ops=ops9)
sealed_ok = ex9.dispatched == [] and s9.status == "escalated"
print(f"bare run(): dispatched={ex9.dispatched}, returned status={s9.status!r} "
      f"(sealed halt intact: {sealed_ok})")

# Half 2 — the legal re-entry: RaiseBudget lifts the persisted ceiling and
# re-enters; the runner must dispatch the pending work and finish.
s9r = workflow_resume(g9, ex9, ops9, RaiseBudget(10.0))
resumed_ok = ex9.dispatched == ["a"] and s9r.status == "done"
print(f"resume(RaiseBudget(10.0)): dispatched={ex9.dispatched}, "
      f"final status={s9r.status!r}, persisted ceiling="
      f"{ops9.read().budget.usd_ceiling}")
ok = not (sealed_ok and resumed_ok)
print(f"--> escalated trap without a legal re-entry: {ok}  "
      f"{'DEFECT CONFIRMED' if ok else 'not reproduced'}")

print("\nAll repros complete.")
