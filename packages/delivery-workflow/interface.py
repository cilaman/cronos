from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from results import AgentResult, ExecResult, GateResult
from state_types import WorkflowState


@runtime_checkable
class StateOps(Protocol):
    def read(self) -> WorkflowState: ...
    def write(self, patch: dict[str, Any]) -> None: ...


@runtime_checkable
class TelemetryOps(Protocol):
    def emit(self, node_id: str, data: dict[str, float]) -> None: ...


@runtime_checkable
class ExecutorInterface(Protocol):
    state: StateOps
    telemetry: TelemetryOps

    def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult: ...
    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult: ...
    def runExec(self, node_id: str, command: str, inputs: dict[str, Any]) -> ExecResult: ...
    def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool: ...
    def escalate(self, node_id: str, reason: str) -> None: ...
