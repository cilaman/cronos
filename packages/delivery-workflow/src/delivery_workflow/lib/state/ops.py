"""StateStoreOps — the package-native StateOps implementation (R10c).

One class, one home: the read-modify-write + event-log logic that every host
needs lives HERE, in the package, next to the ``StateStore``/``EventLog``
primitives it wraps.  Hosts (the Cronos backend adapter, the conformance
harness, the standalone CLI) reuse or thinly wrap it — they never duplicate
the merge semantics, because those semantics carry the R2/R5/R6/R7 round-trip
laws (see ``lib/state/conformance.py``).

Design decisions carried over from the original adapter-side implementation:
  DD-08  ``write`` patches StateStore; node status transitions are appended
         to the EventLog.  Node status/attempt/artifact_paths/gate/fields are
         written ONLY by the runner through this StateOps
         (01-state-model.md §5.8).
  B1     ``bootstrap_if_absent`` seeds an initial ``state.json`` exactly once
         for a fresh run; resumed runs are left untouched so already-``done``
         nodes are skipped rather than re-dispatched.
"""
from __future__ import annotations

from typing import Any

from delivery_workflow.lib.state.events import EventLog
from delivery_workflow.lib.state.store import StateStore
from delivery_workflow.state_types import BudgetState, NodeState, WorkflowState


class StateStoreOps:
    """StateOps backed by lib/state.StateStore + EventLog (DD-08, R6)."""

    def __init__(self, store: StateStore, event_log: EventLog) -> None:
        self._store = store
        self._event_log = event_log

    def read(self) -> WorkflowState:
        return self._store.read()

    def bootstrap_if_absent(
        self, *, spec: str, run_id: str, usd_ceiling: float
    ) -> None:
        """Seed an initial ``state.json`` when the run directory has none (B1).

        The runner's resume path calls ``state_ops.read()`` unconditionally
        (``runner/core.py``), which requires ``state.json`` to already exist —
        and ``StateStore.read()`` raises ``FileNotFoundError`` otherwise.  A
        *fresh* run must therefore seed the file once; a *resumed* run (state.json
        present) is left untouched so already-``done`` nodes are skipped rather
        than re-dispatched.  Idempotent by design.
        """
        if self._store.exists():
            return
        self._store.write(
            WorkflowState(
                spec=spec,
                run_id=run_id,
                status="running",
                budget=BudgetState(usd_ceiling=usd_ceiling),
            )
        )

    def write(self, patch: dict[str, Any]) -> None:
        """Read-modify-write; appends node_transition events for status changes."""
        try:
            state = self._store.read()
        except FileNotFoundError:
            # Defensive: state.json should have been bootstrapped before the run
            # (see bootstrap_if_absent).  If a write races ahead of bootstrap,
            # start from a minimal running state rather than crashing the caller
            # (e.g. runGate's outcome write).
            state = WorkflowState(
                spec="", run_id="", status="running",
                budget=BudgetState(usd_ceiling=0.0),
            )

        # Top-level status update.
        if "status" in patch:
            state.status = patch["status"]

        # Edge-evaluation record (R5/D1): the runner writes the full snapshot
        # with each update — full replacement, round-trips identically.
        if "edges_evaluated" in patch:
            state.edges_evaluated = dict(patch["edges_evaluated"] or {})

        # Run-level stall detail (R6/D5): written together with
        # status="stalled"; a later {"stall": None} clears it (resumed run
        # that completed).  Full replacement, round-trips identically.
        if "stall" in patch:
            state.stall = patch["stall"]

        # Resume-retry counters (R7): runner.resume writes the full snapshot —
        # full replacement, round-trips identically (like edges_evaluated).
        if "resume_retries" in patch:
            state.resume_retries = dict(patch["resume_retries"] or {})

        # Budget lift (R7 RaiseBudget): runner.resume patches the persisted
        # ceiling so 'escalated'/'blocked' budget parks become resumable.
        if "budget" in patch and isinstance(patch["budget"], dict):
            budget_patch = patch["budget"]
            if "usd_ceiling" in budget_patch:
                state.budget.usd_ceiling = float(budget_patch["usd_ceiling"])
            if "usd_spent" in budget_patch:
                state.budget.usd_spent = float(budget_patch["usd_spent"])

        # Node-level patches.
        nodes_patch: dict[str, Any] = patch.get("nodes", {})
        for node_id, ns_patch in nodes_patch.items():
            if node_id not in state.nodes:
                node = NodeState(status=ns_patch.get("status", "pending"))
                if "artifact_paths" in ns_patch:
                    node.artifact_paths = list(ns_patch["artifact_paths"])
                if "gate" in ns_patch:
                    node.gate = ns_patch["gate"]
                if "attempt" in ns_patch:
                    node.attempt = int(ns_patch["attempt"])
                # Round-trip law (R2/D2): the runner writes `fields` with every
                # node outcome; dropping them kills all field-based routing
                # (has_ui, verdict, finding_class) after any resume.
                if "fields" in ns_patch:
                    node.fields = dict(ns_patch["fields"])
                # Telemetry normally arrives via TelemetrySink, but honour it
                # in patches too — everything written must read back (R2).
                if "telemetry" in ns_patch and ns_patch["telemetry"] is not None:
                    node.telemetry = dict(ns_patch["telemetry"])
                state.nodes[node_id] = node
                if "status" in ns_patch:
                    self._event_log.append(
                        {
                            "node_id": node_id,
                            "status": ns_patch["status"],
                            "type": "node_transition",
                        }
                    )
            else:
                node = state.nodes[node_id]
                if "status" in ns_patch:
                    old_status = node.status
                    node.status = ns_patch["status"]
                    if old_status != node.status:
                        self._event_log.append(
                            {
                                "node_id": node_id,
                                "status": node.status,
                                "type": "node_transition",
                            }
                        )
                if "artifact_paths" in ns_patch:
                    node.artifact_paths = list(ns_patch["artifact_paths"])
                if "gate" in ns_patch:
                    node.gate = ns_patch["gate"]
                if "attempt" in ns_patch:
                    node.attempt = int(ns_patch["attempt"])
                if "fields" in ns_patch:
                    node.fields = dict(ns_patch["fields"])
                if "telemetry" in ns_patch and ns_patch["telemetry"] is not None:
                    node.telemetry = dict(ns_patch["telemetry"])

        self._store.write(state)
