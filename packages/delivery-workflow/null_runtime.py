from __future__ import annotations

from typing import Any

from results import AgentResult, GateResult
from state_types import WorkflowState


class _NullState:
    def read(self) -> WorkflowState:
        raise NotImplementedError

    def write(self, patch: dict[str, Any]) -> None:
        raise NotImplementedError


class _NullTelemetry:
    def emit(self, node_id: str, data: dict[str, float]) -> None:
        raise NotImplementedError


class NullRuntime:
    """Protocol-conformant stub that raises NotImplementedError on every op (R5)."""

    def __init__(self) -> None:
        self.state = _NullState()
        self.telemetry = _NullTelemetry()

    def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult:
        raise NotImplementedError

    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult:
        raise NotImplementedError

    def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool:
        raise NotImplementedError

    def escalate(self, node_id: str, reason: str) -> None:
        raise NotImplementedError
