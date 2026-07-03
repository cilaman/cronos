"""R4 conformance harness — scripted executor + host park/resume simulation.

The executable countermeasure to "548 green tests coexisting with nine broken
behaviors" (00-assessment.md §3): the existing package tests drive synthetic
graphs with in-memory doubles in a single process, so everything that breaks
*across* the persistence/resume/host seams is invisible to them.  This harness
closes those three blind spots at once:

1. **The shipped spec, not a synthetic graph** — ``load_shipped_graph()`` runs
   ``delivery.workflow.yaml`` through the real ``spec_loader.load_spec`` →
   ``compiler_a.compile`` path, exactly as ``backend/app/delivery_driver.py``
   does in production.
2. **Real persistence, not in-memory doubles** — state lives in a tmp-dir
   ``state.json`` behind the production trio ``StateStore`` + ``EventLog`` +
   ``StateStoreOps`` (``lib/state/store.py``, ``lib/state/ops.py``),
   wrapped in a ``MirrorStateOps`` oracle for the round-trip law.
3. **Multi-process lifecycle, not single-process** — every human node parks the
   run ``blocked``; ``drive_with_host_resumes`` then re-enters through the
   R10b package FACADE (``DeliveryRun.start`` / ``DeliveryRun.resume`` — the
   ONLY surface hosts call since 02-package-boundary.md §2.2), so
   park→resume composition is under test exactly as a host composes it.

R10b port split: the scripted executor implements ``NodeExecutor``
(dispatchAgent/runGate/runExec) and ``HostPort`` (``on_event`` receives the
typed RunEvents — ``RunBlocked``/``RunEscalated`` mirror the Cronos host adapter's
park behavior by writing run status ``blocked`` through StateOps).  Edge
conditions are evaluated runner-internally (``lib.conditions``); scripted
executors no longer implement ``evalCondition``.

Zero ``app.*`` / backend imports anywhere in this package's tests — the
delivery-workflow CI job installs only this package (``pip install -e .[dev]``).
"""
from __future__ import annotations

import copy
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from delivery_workflow import compiler_a
from delivery_workflow.delivery_run import DeliveryRun
from delivery_workflow.lib.state.ops import StateStoreOps
from delivery_workflow.events import RunBlocked, RunEscalated, RunEvent
from delivery_workflow.interface import StateOps
from delivery_workflow.ir import IRGraph
from delivery_workflow.lib.state.events import EventLog
from delivery_workflow.lib.state.store import StateStore
from delivery_workflow.outcome import Outcome
from delivery_workflow.results import AgentResult, ExecResult, GateResult, TelemetryData
from delivery_workflow.runner import HumanAnswer
from delivery_workflow.spec_loader import load_spec
from delivery_workflow.state_types import NodeState, WorkflowState

# ---------------------------------------------------------------------------
# Shipped spec — loaded through the REAL loader + compiler (same call chain as
# backend/app/delivery_driver.py: load_spec(...) → compiler_a.compile(...)).
# ---------------------------------------------------------------------------

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = PACKAGE_ROOT / "src" / "delivery_workflow" / "delivery.workflow.yaml"


def load_shipped_graph() -> IRGraph:
    """Load and compile the shipped delivery.workflow.yaml."""
    return compiler_a.compile(load_spec(SPEC_PATH))


# ---------------------------------------------------------------------------
# Node universe of the shipped spec, pinned as explicit expectations.  A spec
# edit must consciously update these constants (guarded by
# test_conformance_spec_universe), keeping the scenario expectations honest.
# ---------------------------------------------------------------------------

AGENT_NODES = frozenset({
    "scout", "analyze", "frontend", "architect", "testarch", "implement",
    "review", "security", "doc", "retro", "improve",
})
GATE_NODES = frozenset({
    "g-scout", "g-analysis", "g-design", "g-build", "g-review", "g-security",
    "g-tests", "g-doc", "g-retro",
})
EXEC_NODES = frozenset({"testrun"})
HUMAN_NODES = frozenset({"signoff-scope", "signoff-design", "release"})

ALL_NODES = AGENT_NODES | GATE_NODES | EXEC_NODES | HUMAN_NODES


# ---------------------------------------------------------------------------
# Canned-result helpers for scripting scenarios.
# ---------------------------------------------------------------------------


def agent_done(**fields: Any) -> AgentResult:
    """A successful agent result carrying *fields* (typed scalars allowed)."""
    return AgentResult(
        status="done",
        artifact_paths=[],
        produces="",
        fields=dict(fields),
        open_questions=[],
        telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
    )


def agent_failed(*open_questions: str) -> AgentResult:
    """A failed agent result (e.g. an OOM-killed child with no fence)."""
    return AgentResult(
        status="failed",
        artifact_paths=[],
        produces="",
        fields={},
        open_questions=list(open_questions) or ["No node_status fence found"],
        telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
    )


def gate_decision(decision: str, errors: list[str] | None = None) -> GateResult:
    return GateResult(decision=decision, errors=list(errors or []))  # type: ignore[arg-type]


def exec_exit(exit_code: int = 0) -> ExecResult:
    return ExecResult(
        status="done" if exit_code == 0 else "failed",
        exit_code=exit_code,
    )


class ScriptedExecutor:
    """NodeExecutor + HostPort driven by per-node canned results (R10b).

    ``script`` maps node_id → a canned result (``AgentResult`` / ``GateResult``
    / ``ExecResult``) or a *list* of them consumed one per dispatch (the last
    entry repeats once exhausted — e.g. ``[needs_fix, needs_fix, pass]`` for a
    fix-loop).  Unscripted nodes get benign defaults: agents succeed with empty
    fields, gates ``proceed``, exec nodes exit 0.

    Recorded per scenario (cumulative across park→resume cycles, mirroring how
    the production driver re-enters the facade with fresh adapters but one
    underlying state):

    - ``calls``  — Counter of work dispatches keyed by node_id
      (dispatchAgent / runGate / runExec).
    - ``events`` — every typed RunEvent received via ``on_event`` (in order).
    - ``parks``  — ordered ``(node_id, question_or_detail)`` for the park
      events only (``RunBlocked`` / ``RunEscalated``).
    - ``agent_inputs`` — per agent node, the full ``inputs`` dict of every
      dispatch (deep-copied), so scenarios can assert what the child brief
      would see — e.g. that a reject answer reached the re-run's
      ``inputs['scope']`` (R7/OD-2).

    ``on_event`` mirrors the Cronos host adapter: a ``RunBlocked`` or
    ``RunEscalated`` event writes ``{"status": "blocked"}`` through StateOps
    (the production adapter parks 'blocked' for every escalation cause; the
    runner overrides with the precise terminal where needed — see
    runner/core.py loop-exhaust handling).
    """

    def __init__(
        self,
        script: dict[str, Any] | None = None,
        state_ops: "StateOps | None" = None,
    ) -> None:
        self.state = state_ops
        self.calls: Counter[str] = Counter()
        self.events: list[RunEvent] = []
        self.parks: list[tuple[str, str]] = []
        self.agent_inputs: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._script: dict[str, Any] = dict(script or {})
        self._cursor: dict[str, int] = defaultdict(int)

    # -- script resolution --------------------------------------------------

    def _next(self, node_id: str, default: Any) -> Any:
        entry = self._script.get(node_id)
        if entry is None:
            return copy.deepcopy(default)
        if isinstance(entry, list):
            idx = min(self._cursor[node_id], len(entry) - 1)
            self._cursor[node_id] += 1
            return copy.deepcopy(entry[idx])
        return copy.deepcopy(entry)

    # -- NodeExecutor ---------------------------------------------------------

    def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult:
        node_id = inputs["node_id"]
        self.calls[node_id] += 1
        self.agent_inputs[node_id].append(copy.deepcopy(inputs))
        return self._next(node_id, agent_done())

    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult:
        node_id = gate["id"]
        self.calls[node_id] += 1
        return self._next(node_id, gate_decision("proceed"))

    def runExec(self, node_id: str, command: str, inputs: dict[str, Any]) -> ExecResult:
        self.calls[node_id] += 1
        return self._next(node_id, exec_exit(0))

    # -- HostPort ---------------------------------------------------------------

    def on_event(self, event: RunEvent) -> None:
        self.events.append(event)
        if isinstance(event, RunBlocked):
            self.parks.append((event.node_id, event.question))
            if self.state is not None:
                # Mirrors the host adapter's on_event/escalate (DD-10): the run is
                # parked "blocked" regardless of the escalation cause.
                self.state.write({"status": "blocked"})
        elif isinstance(event, RunEscalated):
            self.parks.append((event.node_id, event.detail))
            if self.state is not None:
                self.state.write({"status": "blocked"})

    # -- assertion helpers ----------------------------------------------------

    def executed_nodes(self) -> set[str]:
        """Every node that did work or parked the run as a human sign-off."""
        human_parked = {
            e.node_id for e in self.events if isinstance(e, RunBlocked)
        }
        return set(self.calls) | human_parked

    def human_park_sequence(self) -> list[str]:
        return [e.node_id for e in self.events if isinstance(e, RunBlocked)]


# ---------------------------------------------------------------------------
# Real persistence: tmp-dir StateStore + EventLog behind StateStoreOps —
# the exact production StateOps the delivery driver hands to the facade —
# wrapped in a MirrorStateOps oracle for the round-trip law.
# ---------------------------------------------------------------------------


class MirrorStateOps:
    """StateOps proxy keeping an INDEPENDENT in-memory mirror of every write.

    Since the suite drives the ``DeliveryRun`` facade (which returns
    ``Outcome``, not the runner's in-memory ``WorkflowState``), the round-trip
    law needs its own oracle: every ``write(patch)`` is applied to an
    in-memory mirror using the LAW's semantics (01 §5.4 — full-snapshot
    replacement for ``status``/``edges_evaluated``/``stall``/
    ``resume_retries``, per-key ``budget``, per-node field replacement for
    node patches, which for the runner's snapshot-superset writes is
    equivalent to a merge).  The mirror is deliberately implemented HERE, in
    test infrastructure, independent of the production merge code — a shared
    implementation would let a merge bug cancel itself out.

    ``assert_state_roundtrip`` then compares the mirror (what the runner
    wrote) against a fresh disk read (what persisted).
    """

    def __init__(self, inner: StateStoreOps) -> None:
        self._inner = inner
        self.mirror: WorkflowState | None = None

    # StateOps -----------------------------------------------------------

    def read(self) -> WorkflowState:
        state = self._inner.read()
        if self.mirror is None:
            self.mirror = copy.deepcopy(state)
        return state

    def write(self, patch: dict[str, Any]) -> None:
        self._inner.write(patch)
        m = self._require_mirror()
        if "status" in patch:
            m.status = patch["status"]
        if "edges_evaluated" in patch:
            m.edges_evaluated = copy.deepcopy(dict(patch["edges_evaluated"] or {}))
        if "stall" in patch:
            m.stall = copy.deepcopy(patch["stall"])
        if "resume_retries" in patch:
            m.resume_retries = dict(patch["resume_retries"] or {})
        if "budget" in patch and isinstance(patch["budget"], dict):
            if "usd_ceiling" in patch["budget"]:
                m.budget.usd_ceiling = float(patch["budget"]["usd_ceiling"])
            if "usd_spent" in patch["budget"]:
                m.budget.usd_spent = float(patch["budget"]["usd_spent"])
        for node_id, ns_patch in (patch.get("nodes") or {}).items():
            node = m.nodes.get(node_id)
            if node is None:
                node = NodeState(status=ns_patch.get("status", "pending"))
                m.nodes[node_id] = node
            if "status" in ns_patch:
                node.status = ns_patch["status"]
            if "attempt" in ns_patch:
                node.attempt = int(ns_patch["attempt"])
            if "artifact_paths" in ns_patch:
                node.artifact_paths = list(ns_patch["artifact_paths"])
            if "gate" in ns_patch:
                node.gate = copy.deepcopy(ns_patch["gate"])
            if "fields" in ns_patch:
                node.fields = copy.deepcopy(dict(ns_patch["fields"]))

    # Bootstrap passthrough (duck-typed by DeliveryRun.start) -------------

    def bootstrap_if_absent(self, **kwargs: Any) -> None:
        self._inner.bootstrap_if_absent(**kwargs)
        if self.mirror is None:
            self.mirror = copy.deepcopy(self._inner.read())

    # Oracle ---------------------------------------------------------------

    def _require_mirror(self) -> WorkflowState:
        if self.mirror is None:
            self.mirror = copy.deepcopy(self._inner.read())
        return self.mirror


def make_state_ops(
    run_dir: Path, graph: IRGraph, run_id: str = "run-conformance"
) -> MirrorStateOps:
    """Mirror-wrapped StateStore-backed StateOps for *run_dir*.

    Bootstrap is left to ``DeliveryRun.start()`` (the facade duck-types
    ``bootstrap_if_absent`` exactly as the pre-R10b driver did); calling it
    here too is harmless — it is idempotent — and keeps scenarios that read
    state before starting the run working.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    ops = MirrorStateOps(StateStoreOps(StateStore(run_dir), EventLog(run_dir)))
    budget_meta = graph.metadata.get("budget", {})
    ops.bootstrap_if_absent(
        spec=graph.metadata.get("name", ""),
        run_id=run_id,
        usd_ceiling=float(budget_meta.get("usd_ceiling", 0.0)),
    )
    return ops


def make_delivery_run(
    graph: IRGraph, executor: ScriptedExecutor, state_ops: "StateOps"
) -> DeliveryRun:
    """The facade wired exactly as a host wires it: executor + host + state."""
    return DeliveryRun(
        graph, executor=executor, state_ops=state_ops, host=executor
    )


# ---------------------------------------------------------------------------
# Host resume simulation.
# ---------------------------------------------------------------------------


def blocked_human_ids(state: WorkflowState, graph: IRGraph) -> list[str]:
    """Sorted ids of blocked human / human-mode wait nodes in *state* — the
    park points a ``HumanAnswer`` resume can legally address."""
    human_ids = {
        n.id
        for n in graph.nodes
        if n.kind == "human"
        or (n.kind == "wait" and (n.data or {}).get("mode", "human") == "human")
    }
    return sorted(
        nid
        for nid, ns in state.nodes.items()
        if ns.status == "blocked" and nid in human_ids
    )


@dataclass
class DriveOutcome:
    """Terminal observation of a scripted park→resume lifecycle."""

    #: The facade's terminal Outcome (closed taxonomy — what a host consumes).
    outcome: Outcome
    #: The in-memory mirror of everything the runner wrote (round-trip oracle).
    final: WorkflowState
    #: One entry per host resume: the human node ids approved by that resume.
    resumes: list[list[str]] = field(default_factory=list)


def drive_with_host_resumes(
    graph: IRGraph,
    executor: ScriptedExecutor,
    state_ops: "MirrorStateOps",
    max_resumes: int = 6,
    answer_text: str = "approved",
) -> DriveOutcome:
    """Run the workflow to a terminal via the FACADE, approving human parks.

    Each cycle mirrors one production re-entry of the delivery driver since
    R10b: ``DeliveryRun.start()`` against persisted state; while the Outcome
    is ``blocked`` on a human node, re-enter through
    ``DeliveryRun.resume(HumanAnswer(node, answer_text, 'approve'))`` — the
    only legal re-entry for a parked run.  Stops at a non-blocked terminal,
    when the run is blocked with NO blocked human node (nothing a HumanAnswer
    could address — e.g. an agent self-reporting blocked; hosts park with a
    diagnostic there), or after *max_resumes* cycles (defensive bound; the
    shipped spec needs 3).
    """
    run = make_delivery_run(graph, executor, state_ops)
    result = DriveOutcome(
        outcome=run.start(), final=state_ops._require_mirror()
    )
    while result.outcome.kind == "blocked" and len(result.resumes) < max_resumes:
        # Outcome.node_id pins the parked sign-off (the facade computes it via
        # the same blocked-human query resume() validates against); None means
        # no HumanAnswer applies.
        node_id = result.outcome.node_id
        if node_id is None or node_id not in blocked_human_ids(
            state_ops.read(), graph
        ):
            break
        result.outcome = run.resume(
            HumanAnswer(node_id=node_id, text=answer_text, verdict="approve")
        )
        result.resumes.append([node_id])
    result.final = state_ops._require_mirror()
    return result


# ---------------------------------------------------------------------------
# Round-trip law (item 4c) — state read back from disk equals the in-memory
# mirror of everything the runner wrote.  Field-by-field for actionable
# diffs; the same law lib/state/conformance.py enforces per-write, asserted
# here per-scenario at the terminal.
# ---------------------------------------------------------------------------


def assert_state_roundtrip(state_ops: "StateOps", final: WorkflowState) -> None:
    persisted = state_ops.read()
    assert persisted.status == final.status, (
        f"run status round-trip: in-memory {final.status!r}, disk {persisted.status!r}"
    )
    assert persisted.edges_evaluated == final.edges_evaluated, (
        "edges_evaluated round-trip: in-memory "
        f"{final.edges_evaluated!r}, disk {persisted.edges_evaluated!r} "
        "(R5 — resume edge replay would not be idempotent)"
    )
    assert persisted.stall == final.stall, (
        f"stall round-trip: in-memory {final.stall!r}, disk {persisted.stall!r} "
        "(R6 — the host could not render an actionable park message)"
    )
    assert persisted.resume_retries == final.resume_retries, (
        "resume_retries round-trip: in-memory "
        f"{final.resume_retries!r}, disk {persisted.resume_retries!r} "
        "(R7 — the RetryFailed ceiling would not bind across restarts)"
    )
    assert set(persisted.nodes) == set(final.nodes), (
        f"node-set round-trip: in-memory {sorted(final.nodes)}, "
        f"disk {sorted(persisted.nodes)}"
    )
    for nid, ns in final.nodes.items():
        got = persisted.nodes[nid]
        assert got.status == ns.status, f"{nid}.status: {ns.status!r} vs disk {got.status!r}"
        assert got.attempt == ns.attempt, f"{nid}.attempt: {ns.attempt!r} vs disk {got.attempt!r}"
        assert got.artifact_paths == ns.artifact_paths, (
            f"{nid}.artifact_paths: {ns.artifact_paths!r} vs disk {got.artifact_paths!r}"
        )
        assert got.gate == ns.gate, f"{nid}.gate: {ns.gate!r} vs disk {got.gate!r}"
        assert got.fields == ns.fields, (
            f"{nid}.fields: {ns.fields!r} vs disk {got.fields!r} (D2 regression)"
        )
