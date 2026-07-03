from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class BudgetState:
    usd_ceiling: float
    usd_spent: float = 0.0


#: Closed node-status vocabulary (01-state-model.md §5.1).  ``needs_fix`` is a
#: REAL node status with a single writer (R9/D11): the runner persists a
#: gate's non-proceed decision once, as this status, with the decision detail
#: in ``NodeState.gate``.  ``running`` appears only via host snapshots (the
#: Cronos harness mapping); the sync runner itself writes terminals plus
#: ``pending`` on back-edge resets.
NodeStatus = Literal[
    "pending", "running", "done", "needs_fix", "blocked", "failed", "escalated"
]


@dataclass
class NodeState:
    status: NodeStatus
    attempt: int = 0
    gate: dict[str, Any] | None = None
    artifact_paths: list[str] = field(default_factory=list)
    telemetry: dict[str, float] | None = None
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowState:
    spec: str
    run_id: str
    status: Literal["running", "done", "stalled", "failed", "blocked", "escalated"]
    budget: BudgetState
    nodes: dict[str, NodeState] = field(default_factory=dict)
    #: Edge-evaluation record (R5/D1, 01-state-model.md §5.2 ``edges_evaluated``).
    #: Shape: ``{"fired": {target: [[edge_index, target_generation], ...]},
    #:           "excluded": {target: [[edge_index, target_generation], ...]}}``
    #: — the forward edges the runner evaluated true (fired) or false/
    #: transitively-excluded (excluded).  Written by the runner through
    #: StateOps so resume edge replay is idempotent; an absent/empty record
    #: (pre-R5 state.json, lossy StateOps) makes resume re-evaluate conditions
    #: from the rebuilt typed scope instead.  R6 uses it as the completeness
    #: proof at drain time.
    edges_evaluated: dict[str, Any] = field(default_factory=dict)
    #: Run-level stall detail (R6/D5+OD-3, 01-state-model.md §5.2).  Only
    #: meaningful when ``status == "stalled"``; ``None`` otherwise (and on
    #: every pre-R6 state.json).  Machine-readable so hosts NEVER have to dig
    #: through ``nodes`` to explain a stall.  Shape:
    #:   {"kind": "starved_nodes" | "gate_exhausted",
    #:    "nodes": [node_id, ...],   # actionable frontier / exhausted gate
    #:    "reason": str,             # human-readable, actionable
    #:    "dead_ends": [node_id, ...]}  # starved_nodes only: done nodes that
    #:                                  # routed nowhere (may be absent)
    #: Written by the runner through ``state_ops.write({"status": "stalled",
    #: "stall": ...})``; cleared (``None``) when a later resume completes.
    stall: dict[str, Any] | None = None
