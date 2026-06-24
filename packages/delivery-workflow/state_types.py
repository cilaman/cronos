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


@dataclass
class WorkflowState:
    spec: str
    run_id: str
    status: Literal["running", "done", "failed", "blocked", "escalated"]
    budget: BudgetState
    nodes: dict[str, NodeState] = field(default_factory=dict)
