from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class BudgetState:
    usd_ceiling: float
    usd_spent: float = 0.0


@dataclass
class NodeState:
    status: str
    attempt: int = 0
    gate: dict[str, Any] | None = None
    artifact_paths: list[str] = field(default_factory=list)
    telemetry: dict[str, float] | None = None
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowState:
    spec: str
    run_id: str
    status: Literal["running", "done", "failed", "blocked", "escalated"]
    budget: BudgetState
    nodes: dict[str, NodeState] = field(default_factory=dict)
    #: Edge-evaluation record (R5/D1, 01-state-model.md §5.2 ``edges_evaluated``).
    #: Shape: ``{"fired": {target: [[edge_index, target_generation], ...]},
    #:           "excluded": {target: [[edge_index, target_generation], ...]}}``
    #: — the forward edges the runner evaluated true (fired) or false/
    #: transitively-excluded (excluded).  Written by the runner through
    #: StateOps so resume edge replay is idempotent; an absent/empty record
    #: (pre-R5 state.json, lossy StateOps) makes resume re-evaluate conditions
    #: from the rebuilt typed scope instead.  R6 will use it as the
    #: completeness proof at drain time.
    edges_evaluated: dict[str, Any] = field(default_factory=dict)
