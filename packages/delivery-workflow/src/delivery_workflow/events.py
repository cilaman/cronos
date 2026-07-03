"""delivery_workflow.events — the typed RunEvent grammar (R10b, 02-package-boundary §2.2).

The package talks TO the host through exactly one channel: ``HostPort.on_event``
(see ``delivery_workflow.interface``).  Each event is a small frozen dataclass
carrying structured data — hosts never parse reason strings or dig through
``WorkflowState`` internals to learn what happened.  This replaces the old
``ExecutorInterface.escalate(node_id, reason)`` hook, whose free-text ``reason``
prefixes (``[human]``, ``[wait/human]``, …) hosts had to sniff to distinguish a
sign-off park from a loop exhaust.

Event vocabulary (derived from the pre-split escalate() call sites plus the
node-transition SSE synthesis the Cronos harness adapter performed host-side):

``NodeStarted(node_id, attempt)``
    The runner is about to dispatch *node_id* (attempt is 1-based).

``NodeFinished(node_id, status)``
    The runner persisted the node's terminal outcome — *status* is one of the
    closed NodeStatus vocabulary (``done``/``needs_fix``/``blocked``/
    ``failed``/``escalated``).

``RunBlocked(node_id, question)``
    A human node (kind ``human``, or ``wait`` with ``mode: human``) parked the
    run awaiting a ``HumanAnswer`` resume.  *question* is the node's prompt.

``RunStalled(detail)``
    The run terminated ``stalled``; *detail* is the machine-readable run-level
    stall record (``{"kind": ..., "nodes": [...], "reason": ...}``) — the same
    value written to ``WorkflowState.stall``.

``RunFailed(node_id, reason)``
    A node failed and the runner halted the run ``failed``.

``RunEscalated(kind, node_id, detail)``
    The run halted ``escalated``.  ``kind`` discriminates the cause:
    ``"loop"`` (LoopPolicy exhausted with ``on_exhaust=escalate``),
    ``"timed_wait"`` (a timed wait defers its sleep to the host),
    ``"iteration_cap"`` (the runner's global iteration cap tripped),
    ``"budget"`` (reserved for host-side budget-ceiling escalations).

Events are notifications, not control flow: the runner never depends on a
host's reaction, and a raising ``on_event`` is logged and swallowed
(``safe_emit``) so a broken host callback cannot corrupt a run.

No app.* imports allowed (enforced by .importlinter).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Union

if TYPE_CHECKING:  # pragma: no cover — typing only
    from delivery_workflow.interface import HostPort

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NodeStarted:
    """The runner is about to dispatch *node_id* (1-based *attempt*)."""

    node_id: str
    attempt: int


@dataclass(frozen=True)
class NodeFinished:
    """The runner persisted *node_id*'s outcome as *status* (closed vocab)."""

    node_id: str
    status: str


@dataclass(frozen=True)
class RunBlocked:
    """A human node parked the run awaiting a ``HumanAnswer`` resume."""

    node_id: str
    question: str


@dataclass(frozen=True)
class RunStalled:
    """The run terminated ``stalled``; *detail* is the run-level stall record."""

    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunFailed:
    """A node failed and the runner halted the run ``failed``."""

    node_id: str
    reason: str


@dataclass(frozen=True)
class RunEscalated:
    """The run halted ``escalated`` (loop/timed_wait/iteration_cap/budget)."""

    kind: Literal["loop", "timed_wait", "iteration_cap", "budget"]
    node_id: str
    detail: str


RunEvent = Union[
    NodeStarted, NodeFinished, RunBlocked, RunStalled, RunFailed, RunEscalated
]


class NullHost:
    """HostPort that ignores every event — the default for host-less runs."""

    def on_event(self, event: RunEvent) -> None:  # noqa: ARG002
        pass


def safe_emit(host: "HostPort | None", event: RunEvent) -> None:
    """Deliver *event* to *host* (no-op when ``None``); never raise.

    A host callback raising must not corrupt the run — mirrors the pre-split
    behavior where ``executor.escalate`` calls were wrapped in try/except.
    """
    if host is None:
        return
    try:
        host.on_event(event)
    except Exception as exc:  # noqa: BLE001 — deliberate isolation boundary
        log.warning("host.on_event(%r) raised %s — ignored.", event, exc)
