"""delivery_workflow.interface — the two ports of the package boundary (R10b).

02-package-boundary.md §2.2 splits the old ``ExecutorInterface`` (which
conflated *executing node work* with *talking to the host*) into:

``NodeExecutor`` (per node-kind capability, package-defined)
    ``dispatchAgent`` / ``runGate`` / ``runExec`` — and NOTHING else.
    ``evalCondition`` left this surface entirely: condition evaluation is
    runner-internal semantics (typed scalars, ``exists()`` — see
    ``delivery_workflow.lib.conditions``), not a host capability.  Hosts were
    only ever asked to implement it because the grammar once lived in
    ``app.harnesses.decision``; that module now *delegates to* the same
    ``lib.conditions`` evaluator, so harness edge-condition semantics are
    preserved by construction.
    ``escalate`` is gone too — host notification flows through ``HostPort``.

``HostPort`` (host-defined, package-consumed)
    ``on_event(RunEvent)`` — the single notification channel (typed events in
    ``delivery_workflow.events``), replacing ``escalate(node_id, reason)`` and
    its host-side reason-prefix sniffing.

``StateOps`` is unchanged: the persistence port with the round-trip law
(01 §5.4), enforced by ``lib.state.conformance``.

``TelemetryOps`` is unchanged: per-node metric emission.

Hosts normally touch none of these directly — they construct a
``DeliveryRun`` facade (``delivery_workflow.delivery_run``) with one object
per port and consume ``Outcome``/``RunEvent`` only.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from delivery_workflow.results import AgentResult, ExecResult, GateResult
from delivery_workflow.state_types import WorkflowState

if TYPE_CHECKING:  # pragma: no cover — typing only
    from delivery_workflow.events import RunEvent


@runtime_checkable
class StateOps(Protocol):
    def read(self) -> WorkflowState: ...
    def write(self, patch: dict[str, Any]) -> None: ...


@runtime_checkable
class TelemetryOps(Protocol):
    def emit(self, node_id: str, data: dict[str, float]) -> None: ...


@runtime_checkable
class NodeExecutor(Protocol):
    """Executes node work; knows NOTHING about the host (R10b port split)."""

    def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult: ...
    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult: ...
    def runExec(self, node_id: str, command: str, inputs: dict[str, Any]) -> ExecResult: ...


@runtime_checkable
class HostPort(Protocol):
    """Receives typed run events; the package's only channel TO the host."""

    def on_event(self, event: "RunEvent") -> None: ...


#: Deprecated alias (R10b): the pre-split protocol name.  The old surface
#: additionally demanded ``evalCondition``/``escalate`` and ``state``/
#: ``telemetry`` attributes; the runner requires none of those anymore.
#: Kept one release so old imports resolve; new code names ``NodeExecutor``.
ExecutorInterface = NodeExecutor
