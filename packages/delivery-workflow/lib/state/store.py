from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from state_types import BudgetState, NodeState, WorkflowState


def _deserialize(data: dict[str, Any]) -> WorkflowState:
    budget_raw = data.get("budget", {})
    budget = BudgetState(
        usd_ceiling=float(budget_raw.get("usd_ceiling", 0.0)),
        usd_spent=float(budget_raw.get("usd_spent", 0.0)),
    )
    nodes: dict[str, NodeState] = {}
    for node_id, ns in data.get("nodes", {}).items():
        # `status` defaults to "pending" rather than being required: lib.gate's
        # standalone `_write_gate_result` writes a partial node entry
        # ({"gate": {...}} with no status) directly into state.json, and a
        # subsequent StateStore.read() must not KeyError on it. The status is
        # then set by the caller's read-modify-write (e.g. CronosStateOps.write).
        nodes[node_id] = NodeState(
            status=ns.get("status", "pending"),
            attempt=int(ns.get("attempt", 0)),
            gate=ns.get("gate"),
            artifact_paths=list(ns.get("artifact_paths", [])),
            telemetry=ns.get("telemetry"),
            fields=dict(ns.get("fields", {})),
        )
    return WorkflowState(
        spec=data["spec"],
        run_id=data["run_id"],
        status=data["status"],
        budget=budget,
        nodes=nodes,
        # Round-trip law (R5/D1): the edge-evaluation record proves which
        # forward edges fired / were excluded; dropping it would force resume
        # to re-evaluate conditions (correct but the record must survive when
        # written — everything the runner writes reads back identically).
        edges_evaluated=dict(data.get("edges_evaluated", {})),
        # Round-trip law (R6/D5): the run-level stall detail — hosts read it
        # instead of digging through nodes.  Pre-R6 state.json has no key →
        # None (never crash on legacy files).
        stall=data.get("stall"),
        # Round-trip law (R7): the resume-retry counters that bound
        # RetryFailed re-arms — dropping them would resurrect the unbounded
        # crash-loop the deleted failed_resumes.json sidecar papered over.
        resume_retries=dict(data.get("resume_retries", {})),
    )


def _serialize(state: WorkflowState) -> dict[str, Any]:
    nodes: dict[str, Any] = {}
    for nid, ns in state.nodes.items():
        entry: dict[str, Any] = {
            "status": ns.status,
            "attempt": ns.attempt,
            "artifact_paths": ns.artifact_paths,
        }
        if ns.gate is not None:
            entry["gate"] = ns.gate
        if ns.telemetry is not None:
            entry["telemetry"] = ns.telemetry
        # Round-trip law (R2/D2): `fields` carry routing data (has_ui, verdict,
        # finding_class, loop.until inputs) — dropping them kills all
        # field-based routing after any resume.
        if ns.fields:
            entry["fields"] = ns.fields
        nodes[nid] = entry
    data: dict[str, Any] = {
        "spec": state.spec,
        "run_id": state.run_id,
        "status": state.status,
        "budget": {
            "usd_ceiling": state.budget.usd_ceiling,
            "usd_spent": state.budget.usd_spent,
        },
        "nodes": nodes,
    }
    # Round-trip law (R5/D1): persist the edge-evaluation record when present.
    if state.edges_evaluated:
        data["edges_evaluated"] = state.edges_evaluated
    # Round-trip law (R6/D5): persist the run-level stall detail when present
    # (omitted when None, so a completed run's state.json carries no key).
    if state.stall is not None:
        data["stall"] = state.stall
    # Round-trip law (R7): persist the resume-retry counters when present
    # (omitted when empty, so a never-resumed run's state.json carries no key).
    if state.resume_retries:
        data["resume_retries"] = state.resume_retries
    return data


def resume_node_status(node_state: NodeState | None) -> str:
    """
    Resume policy for a node.
    Returns 'skip' (done), 're-dispatch' (torn run), or 'dispatch' (absent).
    """
    if node_state is None:
        return "dispatch"
    if node_state.status == "done":
        return "skip"
    return "re-dispatch"


class StateStore:
    """Manages state.json reads and atomic writes for a workflow run directory."""

    def __init__(self, run_dir: Path) -> None:
        self._path = run_dir / "state.json"

    def exists(self) -> bool:
        return self._path.exists()

    def read(self) -> WorkflowState:
        data = json.loads(self._path.read_text())
        return _deserialize(data)

    def write(self, state: WorkflowState) -> None:
        """Atomic write via tempfile + os.replace — no torn reads on crash."""
        content = json.dumps(_serialize(state), indent=2)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(content)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def patch(self, updates: dict[str, Any]) -> WorkflowState:
        """Read-modify-write: merge top-level keys then persist atomically."""
        state = self.read()
        data = _serialize(state)
        data.update(updates)
        new_state = _deserialize(data)
        self.write(new_state)
        return new_state
