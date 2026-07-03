from __future__ import annotations

from typing import Any

from delivery_workflow.results import AgentResult, ExecResult, GateResult
from delivery_workflow.state_types import WorkflowState


class _NullState:
    def read(self) -> WorkflowState:
        raise NotImplementedError

    def write(self, patch: dict[str, Any]) -> None:
        raise NotImplementedError


class _NullTelemetry:
    def emit(self, node_id: str, data: dict[str, float]) -> None:
        raise NotImplementedError


class NullRuntime:
    """NodeExecutor-conformant stub that raises NotImplementedError on every op.

    R10b port split: ``evalCondition`` and ``escalate`` are no longer part of
    the executor surface — condition evaluation is runner-internal
    (``lib.conditions``) and host notification flows through
    ``HostPort.on_event`` (``delivery_workflow.events.NullHost`` is the no-op
    host).  The ``state``/``telemetry`` attributes are kept for test doubles
    that subclass this stub and wire their own ops.
    """

    def __init__(self) -> None:
        self.state = _NullState()
        self.telemetry = _NullTelemetry()

    def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult:
        raise NotImplementedError

    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult:
        raise NotImplementedError

    def runExec(self, node_id: str, command: str, inputs: dict[str, Any]) -> ExecResult:
        raise NotImplementedError
