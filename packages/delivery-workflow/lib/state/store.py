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
        )
    return WorkflowState(
        spec=data["spec"],
        run_id=data["run_id"],
        status=data["status"],
        budget=budget,
        nodes=nodes,
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
        nodes[nid] = entry
    return {
        "spec": state.spec,
        "run_id": state.run_id,
        "status": state.status,
        "budget": {
            "usd_ceiling": state.budget.usd_ceiling,
            "usd_spent": state.budget.usd_spent,
        },
        "nodes": nodes,
    }


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
