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
   ``CronosStateOps`` (``lib/state/store.py``, ``adapters/cronos/adapter.py``).
3. **Multi-process lifecycle, not single-process** — every human node parks the
   run ``blocked``; ``drive_with_host_resumes`` then applies the same state
   patch the host applies today before re-entering ``runner.run`` (see
   ``host_resume_from_blocked``), so park→resume composition is under test.

Zero ``app.*`` / backend imports anywhere in this package's tests — the
delivery-workflow CI job installs only this package (``pip install -e .[dev]``).
"""
from __future__ import annotations

import copy
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import compiler_a
import runner as workflow_runner
from adapters.cronos.adapter import CronosStateOps
from interface import StateOps
from ir import IRGraph
from lib.conditions import eval_condition
from lib.state.events import EventLog
from lib.state.store import StateStore
from results import AgentResult, ExecResult, GateResult, TelemetryData
from spec_loader import load_spec
from state_types import WorkflowState

# ---------------------------------------------------------------------------
# Shipped spec — loaded through the REAL loader + compiler (same call chain as
# backend/app/delivery_driver.py: load_spec(...) → compiler_a.compile(...)).
# ---------------------------------------------------------------------------

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = PACKAGE_ROOT / "delivery.workflow.yaml"


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


def gate_decision(decision: str, errors: list[str] | None = None) -> GateResult:
    return GateResult(decision=decision, errors=list(errors or []))  # type: ignore[arg-type]


def exec_exit(exit_code: int = 0) -> ExecResult:
    return ExecResult(
        status="done" if exit_code == 0 else "failed",
        exit_code=exit_code,
    )


class _NullTelemetry:
    def emit(self, node_id: str, data: dict[str, float]) -> None:  # pragma: no cover
        pass


class ScriptedExecutor:
    """ExecutorInterface driven by per-node canned results.

    ``script`` maps node_id → a canned result (``AgentResult`` / ``GateResult``
    / ``ExecResult``) or a *list* of them consumed one per dispatch (the last
    entry repeats once exhausted — e.g. ``[needs_fix, needs_fix, pass]`` for a
    fix-loop).  Unscripted nodes get benign defaults: agents succeed with empty
    fields, gates ``proceed``, exec nodes exit 0.

    Recorded per scenario (cumulative across park→resume cycles, mirroring how
    the production driver re-enters ``runner.run`` with fresh adapters but one
    underlying state):

    - ``calls``  — Counter of work dispatches keyed by node_id
      (dispatchAgent / runGate / runExec).
    - ``parks``  — ordered list of ``(node_id, reason)`` escalations; human
      sign-off parks carry a ``[human]``/``[wait/...]`` reason prefix
      (``runner/dispatch.py``).

    ``evalCondition`` delegates to the real ``lib.conditions.eval_condition``
    with the typed scope passed through un-coerced, and ``escalate`` writes
    ``{"status": "blocked"}`` through StateOps — both mirroring
    ``CronosAdapter`` (DD-07 / DD-10).
    """

    def __init__(
        self,
        script: dict[str, Any] | None = None,
        state_ops: "StateOps | None" = None,
    ) -> None:
        self.state = state_ops
        self.telemetry = _NullTelemetry()
        self.calls: Counter[str] = Counter()
        self.parks: list[tuple[str, str]] = []
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

    # -- ExecutorInterface ----------------------------------------------------

    def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult:
        node_id = inputs["node_id"]
        self.calls[node_id] += 1
        return self._next(node_id, agent_done())

    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult:
        node_id = gate["id"]
        self.calls[node_id] += 1
        return self._next(node_id, gate_decision("proceed"))

    def runExec(self, node_id: str, command: str, inputs: dict[str, Any]) -> ExecResult:
        self.calls[node_id] += 1
        return self._next(node_id, exec_exit(0))

    def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool:
        # Mirrors CronosAdapter.evalCondition (DD-07): typed scope passed
        # through to lib.conditions un-coerced (R3).
        return eval_condition(expr, scope)

    def escalate(self, node_id: str, reason: str) -> None:
        self.parks.append((node_id, reason))
        if self.state is not None:
            # Mirrors CronosAdapter.escalate (DD-10): the run is parked
            # "blocked" regardless of the escalation cause.
            self.state.write({"status": "blocked"})

    # -- assertion helpers ----------------------------------------------------

    def executed_nodes(self) -> set[str]:
        """Every node that did work or parked the run as a human sign-off."""
        human_parked = {
            nid
            for nid, reason in self.parks
            if reason.startswith("[human]") or reason.startswith("[wait/")
        }
        return set(self.calls) | human_parked

    def human_park_sequence(self) -> list[str]:
        return [
            nid
            for nid, reason in self.parks
            if reason.startswith("[human]") or reason.startswith("[wait/")
        ]


# ---------------------------------------------------------------------------
# Real persistence: tmp-dir StateStore + EventLog behind CronosStateOps —
# the exact production StateOps the delivery driver hands to runner.run.
# ---------------------------------------------------------------------------


def make_state_ops(run_dir: Path, graph: IRGraph, run_id: str = "run-conformance") -> CronosStateOps:
    """StateStore-backed StateOps for *run_dir*, bootstrapped like the driver.

    Mirrors ``delivery_driver.run_delivery_goal``: ``bootstrap_if_absent`` seeds
    ``state.json`` once with the graph's budget ceiling; a resumed run leaves
    the existing file untouched.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    ops = CronosStateOps(StateStore(run_dir), EventLog(run_dir))
    budget_meta = graph.metadata.get("budget", {})
    ops.bootstrap_if_absent(
        spec=graph.metadata.get("name", ""),
        run_id=run_id,
        usd_ceiling=float(budget_meta.get("usd_ceiling", 0.0)),
    )
    return ops


# ---------------------------------------------------------------------------
# Host resume simulation.
# ---------------------------------------------------------------------------


def host_resume_from_blocked(state_ops: "StateOps", graph: IRGraph) -> list[str]:
    """Host resume simulation — replace with ``DeliveryRun.resume()`` when R7 lands.

    Package-side replica of ``delivery_driver._resume_from_blocked``
    (backend/app/delivery_driver.py:318-367), the patch the host applies today
    on every user answer before re-entering ``runner.run``: when the persisted
    run is ``blocked``, every blocked human / human-mode wait node is marked
    ``done`` ("the user answered → approved" — D10 semantics, faithfully
    reproduced) and the run status reset to ``running``.

    Returns the sorted list of approved node ids (empty when the run was not
    blocked or no blocked human node exists — i.e. no progress is possible
    through today's host resume path).
    """
    persisted = state_ops.read()
    if persisted.status != "blocked":
        return []

    human_ids = {
        n.id
        for n in graph.nodes
        if n.kind == "human"
        or (n.kind == "wait" and (n.data or {}).get("mode", "human") == "human")
    }
    approved = {
        nid: {"status": "done"}
        for nid, ns in persisted.nodes.items()
        if ns.status == "blocked" and nid in human_ids
    }

    patch: dict[str, Any] = {"status": "running"}
    if approved:
        patch["nodes"] = approved
    state_ops.write(patch)
    return sorted(approved)


@dataclass
class DriveOutcome:
    """Terminal observation of a scripted park→resume lifecycle."""

    final: WorkflowState
    #: One entry per host resume: the human node ids approved by that resume.
    resumes: list[list[str]] = field(default_factory=list)


def drive_with_host_resumes(
    graph: IRGraph,
    executor: ScriptedExecutor,
    state_ops: "StateOps",
    max_resumes: int = 6,
) -> DriveOutcome:
    """Run the workflow to a terminal, resuming past human parks like the host.

    Each cycle mirrors one production re-entry of the delivery driver: run the
    real ``runner.run`` against persisted state; while the run parks
    ``blocked``, apply ``host_resume_from_blocked`` and re-enter.  Stops when
    the run reaches a non-blocked terminal, when a resume approves no human
    node (no progress possible through today's host path — the production
    "answer → instant re-park" livelock, kept bounded here), or after
    *max_resumes* cycles (defensive bound; the shipped spec needs 3).
    """
    outcome = DriveOutcome(final=state_ops.read())
    while True:
        outcome.final = workflow_runner.run(
            graph=graph, executor=executor, state_ops=state_ops
        )
        if outcome.final.status != "blocked" or len(outcome.resumes) >= max_resumes:
            return outcome
        approved = host_resume_from_blocked(state_ops, graph)
        if not approved:
            # The replica faithfully wrote {"status": "running"} even though it
            # could approve nothing (exactly what _resume_from_blocked does),
            # so re-read: the terminal observation must include the host's last
            # action or the round-trip law would flag a stale snapshot.
            outcome.final = state_ops.read()
            return outcome
        outcome.resumes.append(approved)


# ---------------------------------------------------------------------------
# Round-trip law (item 4c) — state read back from disk equals the in-memory
# result runner.run returned.  Field-by-field for actionable diffs; the same
# law lib/state/conformance.py enforces per-write, asserted here per-scenario
# at the terminal.
# ---------------------------------------------------------------------------


def assert_state_roundtrip(state_ops: "StateOps", final: WorkflowState) -> None:
    persisted = state_ops.read()
    assert persisted.status == final.status, (
        f"run status round-trip: in-memory {final.status!r}, disk {persisted.status!r}"
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
