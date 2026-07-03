"""delivery_workflow.outcome — the closed run-outcome taxonomy (R10b, 01 §5.6).

``Outcome`` is the ONLY view of a finished (or parked) run a host consumes —
hosts translate one well-defined Outcome into their own domain (Cronos:
``TaskState`` + structured waiting metadata) and never inspect
``WorkflowState.nodes``.  The taxonomy is closed:

======================  =====================================================
kind                    payload
======================  =====================================================
``done``                —
``stalled``             ``reason`` + ``stall`` (the run-level stall record)
``failed``              ``node_id`` + ``reason``
``blocked``             ``node_id`` + ``question`` (the pending sign-off)
``escalated``           ``escalation`` (loop/timed_wait/iteration_cap/budget)
                        + ``node_id`` + ``reason``
``cancelled``           —
``running``             — (non-terminal; see below)
======================  =====================================================

``running`` is deliberately NOT part of the §5.6 goal-mapping table — it is
included here only because ``DeliveryRun.outcome()`` is a *pure read* a UI may
issue while a run is mid-flight (or after a crash that left ``status:
running``); a host mapping table treats it as "no action".  Every other kind
is terminal-until-resumed.

``outcome_from_state`` derives the Outcome PURELY from a ``WorkflowState``
(plus, optionally, the ``IRGraph`` for richer blocked/escalated payloads).
It reads run-level fields first (``status``, ``stall``) and touches
``state.nodes`` only to pin the node a ``failed``/``blocked``/``escalated``
run halted on — that lookup lives HERE, in the package, precisely so hosts
never have to do it (03-remediation anti-pattern: "the moment a host needs
node internals, the package is missing an event").

No app.* imports allowed (enforced by .importlinter).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from delivery_workflow.state_types import WorkflowState

if TYPE_CHECKING:  # pragma: no cover — typing only
    from delivery_workflow.ir import IRGraph

OutcomeKind = Literal[
    "done", "stalled", "failed", "blocked", "escalated", "cancelled", "running"
]

#: Escalation discriminators (mirrors events.RunEscalated.kind).
EscalationKind = Literal["loop", "timed_wait", "iteration_cap", "budget"]


@dataclass(frozen=True)
class Outcome:
    """Closed run-outcome taxonomy (01-state-model.md §5.6)."""

    kind: OutcomeKind
    #: failed/blocked/escalated: the node the run halted on (best-effort for
    #: pre-facade state files; None when it cannot be pinned).
    node_id: str | None = None
    #: Human-readable, actionable detail (stalled reason / failed reason /
    #: escalated detail).
    reason: str | None = None
    #: blocked only: the pending sign-off question.
    question: str | None = None
    #: stalled only: the full machine-readable stall record
    #: (``{"kind": ..., "nodes": [...], "reason": ...[, "dead_ends": ...]}``).
    stall: dict[str, Any] | None = None
    #: escalated only: the escalation discriminator.
    escalation: EscalationKind | None = None

    @property
    def is_terminal(self) -> bool:
        """True for every kind except the pure-read ``running``."""
        return self.kind != "running"


def outcome_from_state(
    state: WorkflowState, graph: "IRGraph | None" = None
) -> Outcome:
    """Derive the Outcome for *state* — pure, no I/O, no host knowledge.

    *graph* is optional but recommended: with it, a ``blocked`` outcome pins
    the parked node via the same human-node query ``resume()`` uses
    (``runner.resume.blocked_human_nodes``) and recovers the sign-off question
    from the node's spec ``prompt`` when the persisted fields lack one.
    """
    status = state.status

    if status == "done":
        return Outcome(kind="done")
    if status == "cancelled":
        return Outcome(kind="cancelled")
    if status == "running":
        return Outcome(kind="running")

    if status == "stalled":
        stall = state.stall if isinstance(state.stall, dict) else None
        nodes = list((stall or {}).get("nodes") or [])
        return Outcome(
            kind="stalled",
            node_id=str(nodes[0]) if nodes else None,
            reason=str((stall or {}).get("reason") or "") or None,
            stall=stall,
        )

    if status == "failed":
        node_id = _first_node_with_status(state, "failed")
        reason = None
        if node_id is not None:
            ns = state.nodes.get(node_id)
            raw = (ns.fields or {}).get("error") if ns is not None else None
            reason = str(raw) if raw else f"node '{node_id}' failed"
        return Outcome(kind="failed", node_id=node_id, reason=reason)

    if status == "blocked":
        node_id, question = _blocked_park_point(state, graph)
        return Outcome(kind="blocked", node_id=node_id, question=question)

    if status == "escalated":
        node_id, escalation, reason = _escalation_detail(state, graph)
        return Outcome(
            kind="escalated", node_id=node_id, escalation=escalation, reason=reason
        )

    # Unknown persisted status (corrupted/foreign state file): never guess
    # success — surface it as failed with the raw status in the reason.
    return Outcome(kind="failed", reason=f"unknown run status: {status!r}")


# ---------------------------------------------------------------------------
# Internal node-pinning helpers — the ONE place run-halting nodes are looked
# up from state, so hosts never have to.
# ---------------------------------------------------------------------------


def _first_node_with_status(state: WorkflowState, status: str) -> str | None:
    matches = sorted(nid for nid, ns in state.nodes.items() if ns.status == status)
    return matches[0] if matches else None


def _blocked_park_point(
    state: WorkflowState, graph: "IRGraph | None"
) -> tuple[str | None, str | None]:
    """(node_id, question) for a blocked run.

    With a graph, ``node_id`` is the HUMAN park point a ``HumanAnswer`` may
    legally target (the same query resume() validates against) — ``None``
    means the run is blocked on a non-sign-off node (an agent self-reported
    ``blocked``): no HumanAnswer applies and the host should render a
    diagnostic instead of an approve affordance.  Without a graph the node
    kinds are unknown, so the first blocked node is pinned best-effort.
    """
    if graph is not None:
        from delivery_workflow.runner.resume import blocked_human_nodes

        humans = blocked_human_nodes(graph, state)
        node_id = humans[0] if humans else None
    else:
        node_id = _first_node_with_status(state, "blocked")
    if node_id is None:
        return None, None

    ns = state.nodes.get(node_id)
    question = (ns.fields or {}).get("prompt") if ns is not None else None
    if not question and graph is not None:
        node = next((n for n in graph.nodes if n.id == node_id), None)
        if node is not None:
            question = (node.data or {}).get("prompt")
    return node_id, (str(question) if question else None)


def _escalation_detail(
    state: WorkflowState, graph: "IRGraph | None"
) -> tuple[str | None, EscalationKind, str | None]:
    """(node_id, escalation kind, reason) for an escalated run.

    Discrimination mirrors the runner's escalation writers: a ``wait`` node
    with ``mode: timed`` escalates as ``timed_wait`` (its ``fields.mode`` is
    persisted by dispatch); any other escalated node is a loop exhaust; no
    escalated node at all means the global iteration cap tripped (the cap
    writes run status only — ``__runner__`` is not a state node).
    """
    node_id = _first_node_with_status(state, "escalated")
    if node_id is None:
        return None, "iteration_cap", "global iteration cap exceeded"
    ns = state.nodes.get(node_id)
    mode = (ns.fields or {}).get("mode") if ns is not None else None
    if mode == "timed":
        return node_id, "timed_wait", f"timed wait '{node_id}' deferred to the host"
    if mode is None and graph is not None:
        node = next((n for n in graph.nodes if n.id == node_id), None)
        if node is not None and node.kind == "wait" and (
            (node.data or {}).get("mode", "human") == "timed"
        ):
            return node_id, "timed_wait", f"timed wait '{node_id}' deferred to the host"
    return node_id, "loop", f"loop exhausted on node '{node_id}'"
