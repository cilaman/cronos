"""
runner/resume.py — Resume as a first-class package API (R7, kills D7 + D10).

This module is THE legal way to re-enter a persisted workflow run
(01-state-model.md §5.3).  Hosts stop reverse-engineering runner semantics
with ``_resume_from_*`` heuristics and sidecar counter files; instead they
translate the user's action into one typed event and call::

    resume(graph, executor, state_ops, event) -> WorkflowState

Event grammar (§5.3)
--------------------
``HumanAnswer(node_id, text, verdict)``
    The user answered a parked human sign-off.  Legal only when the run is
    ``blocked`` AND *node_id* names a human node (kind ``human``, or ``wait``
    with ``mode: human``) whose persisted status is ``blocked``.

    * ``verdict='approve'`` → the node terminates ``done``; the answer TEXT is
      stored in the node's ``fields.answer`` (OD-2) so it flows into the typed
      scope (``<node>.fields.answer``) and downstream briefs; run status →
      ``running``; the runner resumes past the node.
    * ``verdict='reject'`` → the node terminates ``needs_fix`` — deliberately:
      ``needs_fix`` is in §5.1's closed node vocabulary, is terminal-AND-
      routable (``_ROUTED_TERMINAL``), and contributes to the scope
      (``_SCOPED_STATUSES``), so ``fields.answer``/``fields.verdict`` stay
      visible to the re-run.  The answer is stored exactly as for approve — a
      "no" never silently becomes a "yes" (D10).  Routing (OD-1): if the node
      declares an ``on_reject: <target>`` route (spec-level, optional), the
      target must be a FORWARD-ANCESTOR of the sign-off (validated by
      compiler_a at compile time and defensively here, before any write —
      the re-park machinery depends on the target's re-run path reaching the
      sign-off again), and the
      target and its forward-downstream nodes are re-armed for re-execution
      (the R8 reset path — ``reset_downstream_nodes`` + stale edge-record
      purge; the rejecting human node itself is NOT reset, it holds the
      answer) and the run resumes; the natural back-edge machinery re-parks
      the sign-off once the re-run flow reaches it again, and the reset then
      clears the consumed answer.  Without ``on_reject`` the run terminates
      ``stalled`` with ``state.stall = {kind: "rejected", …}``.

``RetryFailed(node_ids | "all")``
    Re-arm failed work for re-dispatch.  Legal when the run is ``failed``,
    ``escalated`` or ``stalled``.  Named nodes must exist in the graph and
    have persisted status ``failed``, ``escalated`` or ``needs_fix`` (the last
    covers an exhausted gate fix-loop — one more gate evaluation per retry);
    ``"all"`` selects every ``failed``/``escalated`` node (``needs_fix`` gates
    must be named explicitly: they route normally and are usually NOT stuck).
    Each re-arm increments the node's counter in
    ``WorkflowState.resume_retries`` — persisted IN STATE (§5.3; this deletes
    the driver's ``failed_resumes.json`` sidecar).  A node already re-armed
    ``max_retries`` times does not re-arm again: the run terminates
    ``stalled`` with ``state.stall = {kind: "retry_exhausted", …}`` instead of
    looping a persistent failure (classically an OOM-killed child) forever.

``RaiseBudget(new_usd_ceiling)``
    Lift the persisted budget ceiling and resume.  Legal when the run is
    ``escalated`` (policy-limit writers) or ``blocked`` (the Cronos adapter's
    ``escalate`` parks budget escalations as run ``blocked``).  The new
    ceiling must exceed the current one.

``Nothing()``
    Re-enter with no state change beyond ``status → running``.  Legal ONLY
    when the run is ``escalated`` — the "external mitigation" re-entry.  One
    deliberate exception to "no state change": an ``escalated`` ``wait``
    node with ``mode: timed`` is completed (→ ``done``).  Rationale: the
    runner's wait(timed) MVP does not sleep — it escalates and parks
    (runner/dispatch.py), delegating the wait to the host; when the host
    resumes, the wait has been served, and re-arming the node would just
    re-escalate instantly (the exact D7 livelock this module kills).  A
    loop-exhausted agent node (persisted ``escalated``, run ``escalated``) is
    NOT reset by ``Nothing()`` (use ``RetryFailed`` for counted re-arms);
    ordinary seeding re-dispatches it once and — unless its until-condition
    now passes — the run re-derives the same ``escalated`` halt, never a
    silent route past the failed loop.

Errors
------
Applying an event to a state that does not match it raises ``ResumeError``
(a ``ValueError``) with an actionable message — never silent corruption:
e.g. ``HumanAnswer`` for a node that is not blocked, ``RetryFailed`` naming a
node that did not fail, ``RaiseBudget`` that does not raise, ``Nothing()`` on
a non-escalated run.  Re-applying an already-consumed event therefore errors
(the state no longer matches), which is the multi-resume idempotency
guarantee.

Relationship to ``run()``
-------------------------
``resume()`` applies the event's state transition through StateOps and then
delegates to ``runner.run()`` (which owns the R5 condition-aware seeding).
``run()`` called DIRECTLY on a persisted ``blocked``/``escalated``/
``cancelled``/``stalled`` state halts immediately (top-of-run guard in
runner/core.py) — ``resume()`` is the only re-entry that legally flips the
status back to ``running`` after applying an event.  Sealing ``stalled``
matters for rejects specifically: the rejected node is ``needs_fix``
(routable, so its answer stays in scope), and an unsealed re-entry would
replay its out-edges — converting the recorded "no" into a routed "yes".

Host signature note: §5.3 sketches ``resume(state_ops, graph, event)``; the
executor parameter is additionally required here because ``resume()``
delegates to ``run()``, which dispatches work — a host resuming a run always
holds the same executor it would pass to ``run()``.

R10 will wrap this entry point in the ``DeliveryRun`` facade; this module
deliberately delivers ONLY the resume entry point and event grammar.

No app.* imports allowed (enforced by .importlinter).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Union

from ir import IRGraph, IRNode
from state_types import WorkflowState

if TYPE_CHECKING:
    from interface import ExecutorInterface, StateOps

log = logging.getLogger(__name__)

#: Default per-node ceiling on RetryFailed re-arms, persisted in
#: ``WorkflowState.resume_retries``.  Mirrors the deleted driver sidecar's
#: ``_MAX_FAILED_RESUMES = 2`` (a node may fail on 3 total attempts — the
#: original dispatch plus two resume-triggered retries — before the run
#: stalls with ``kind="retry_exhausted"``).
DEFAULT_MAX_RESUME_RETRIES = 2

#: Node statuses a RetryFailed event may re-arm.
_RETRYABLE_NODE_STATUSES = ("failed", "escalated", "needs_fix")


class ResumeError(ValueError):
    """The event does not match the persisted run state (or is malformed).

    Raised BEFORE any write — a rejected event leaves the persisted state
    byte-identical, so hosts can surface the message and try a different
    event without cleanup.
    """


# ---------------------------------------------------------------------------
# Event grammar (01-state-model.md §5.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HumanAnswer:
    """The user answered the human node *node_id* with *text*."""

    node_id: str
    text: str
    verdict: Literal["approve", "reject"]


@dataclass(frozen=True)
class RetryFailed:
    """Re-arm the named nodes (or ``"all"`` failed/escalated ones)."""

    node_ids: "list[str] | Literal['all']" = "all"


@dataclass(frozen=True)
class RaiseBudget:
    """Lift the persisted budget ceiling to *new_usd_ceiling*."""

    new_usd_ceiling: float


@dataclass(frozen=True)
class Nothing:
    """Re-enter with no state change beyond ``status → running``."""


ResumeEvent = Union[HumanAnswer, RetryFailed, RaiseBudget, Nothing]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def blocked_human_nodes(graph: IRGraph, state: WorkflowState) -> list[str]:
    """Host query: ids of human nodes a ``HumanAnswer`` may legally target.

    A ``blocked`` run is parked on one (or, degenerately, several) human
    node(s) — kind ``human``, or ``wait`` with ``mode: human`` — whose
    persisted node status is ``blocked``.  Hosts use THIS query to find the
    park point instead of reading ``WorkflowState.nodes`` themselves (the
    node map is package-internal; 01-state-model.md §5.3/§5.6).

    Returns a sorted list (normally length 1: the runner halts on the first
    blocked node).  Empty when the run is not parked on a human node — e.g.
    an *agent* node self-reported ``blocked``; no HumanAnswer applies there.
    """
    by_id = _node_by_id(graph)
    return sorted(
        nid
        for nid, ns in state.nodes.items()
        if ns.status == "blocked"
        and (node := by_id.get(nid)) is not None
        and _is_human_node(node)
    )


def resume(
    graph: IRGraph,
    executor: "ExecutorInterface",
    state_ops: "StateOps",
    event: ResumeEvent,
    *,
    max_retries: int = DEFAULT_MAX_RESUME_RETRIES,
) -> WorkflowState:
    """Apply *event* to the persisted run and re-enter ``runner.run()``.

    Returns the final ``WorkflowState`` of the resumed run — or, when the
    event itself terminates the run (reject without ``on_reject``; RetryFailed
    past the ceiling), the freshly-persisted terminal state WITHOUT invoking
    the runner.

    Raises
    ------
    ResumeError
        When the event does not match the persisted state (documented per
        event in the module docstring).  Nothing is written in that case.
    """
    if state_ops is None:  # defensive: resume is meaningless without persistence
        raise ResumeError("resume() requires a StateOps — there is no persisted run to resume")

    state = state_ops.read()

    if isinstance(event, HumanAnswer):
        proceed = _apply_human_answer(graph, state_ops, state, event)
    elif isinstance(event, RetryFailed):
        proceed = _apply_retry_failed(graph, state_ops, state, event, max_retries)
    elif isinstance(event, RaiseBudget):
        proceed = _apply_raise_budget(state_ops, state, event)
    elif isinstance(event, Nothing):
        proceed = _apply_nothing(graph, state_ops, state)
    else:
        raise ResumeError(f"unknown resume event type: {type(event).__name__!r}")

    if not proceed:
        return state_ops.read()

    from runner.core import run

    return run(graph=graph, executor=executor, state_ops=state_ops)


# ---------------------------------------------------------------------------
# Per-event state transitions.  Each returns True when the runner should be
# re-entered, False when the event itself terminated the run (stalled).
# ---------------------------------------------------------------------------


def _apply_human_answer(
    graph: IRGraph,
    state_ops: "StateOps",
    state: WorkflowState,
    event: HumanAnswer,
) -> bool:
    if event.verdict not in ("approve", "reject"):
        raise ResumeError(
            f"HumanAnswer.verdict must be 'approve' or 'reject', got {event.verdict!r}"
        )
    if state.status != "blocked":
        raise ResumeError(
            f"HumanAnswer requires a 'blocked' run; the persisted run status is "
            f"{state.status!r} — the answer does not match the run's park point"
        )
    node = _node_by_id(graph).get(event.node_id)
    if node is None:
        raise ResumeError(
            f"HumanAnswer names node {event.node_id!r}, which is not in the graph"
        )
    if not _is_human_node(node):
        raise ResumeError(
            f"HumanAnswer names node {event.node_id!r} of kind {node.kind!r} — "
            "only 'human' nodes (or 'wait' nodes with mode='human') take answers"
        )
    ns = state.nodes.get(event.node_id)
    if ns is None or ns.status != "blocked":
        raise ResumeError(
            f"HumanAnswer names node {event.node_id!r} whose persisted status is "
            f"{ns.status if ns is not None else '<absent>'!r}, not 'blocked' — "
            "the run is not parked on this node"
        )

    # Validate the on_reject route (when declared) BEFORE any write —
    # ResumeError must leave the persisted state byte-identical (class
    # docstring), or the run would be parked with no legal event left.
    # compiler_a validates spec-level on_reject targets; this guards
    # hand-built graphs.
    on_reject = (node.data or {}).get("on_reject")
    if event.verdict == "reject" and on_reject:
        if on_reject not in _node_by_id(graph):
            raise ResumeError(
                f"human node {event.node_id!r} declares on_reject={on_reject!r}, "
                "which is not a node in the graph"
            )
        _, _, forward_adjacency = _graph_structures(graph)
        if on_reject == event.node_id or event.node_id not in _forward_downstream(
            forward_adjacency, on_reject
        ):
            # The re-park machinery assumes the reject target's re-run path
            # reaches the sign-off again (a forward-ancestor): the reset +
            # back-edge re-park then re-asks the question.  A self/downstream/
            # sibling target never leads back through the sign-off, so the
            # rejection would silently starve (or worse, route) the approve
            # path — refuse it instead (D10).
            raise ResumeError(
                f"human node {event.node_id!r} declares on_reject={on_reject!r}, "
                "which is not a forward-ancestor of the sign-off — the reject "
                "re-run could never reach the sign-off again to re-park it; "
                "point on_reject at a node upstream of the sign-off"
            )

    # OD-2: the answer text lands in fields.answer (snapshot-superset merge —
    # the prompt and any prior fields are kept) so it flows into the typed
    # scope and downstream briefs.
    answered_fields = {
        **(ns.fields or {}),
        "answer": event.text,
        "verdict": event.verdict,
    }

    if event.verdict == "approve":
        state_ops.write({
            "status": "running",
            "nodes": {event.node_id: {"status": "done", "fields": answered_fields}},
        })
        log.info("resume: human node %r approved — run re-armed.", event.node_id)
        return True

    # reject — the node terminates needs_fix (terminal, routable, scoped:
    # fields.answer stays visible downstream), NEVER silently done (D10).
    state_ops.write({
        "nodes": {event.node_id: {"status": "needs_fix", "fields": answered_fields}},
    })

    if not on_reject:
        stall = {
            "kind": "rejected",
            "nodes": [event.node_id],
            "reason": (
                f"human node '{event.node_id}' rejected the sign-off and declares "
                f"no on_reject route: {event.text}"
            ),
        }
        state_ops.write({"status": "stalled", "stall": stall})
        log.info(
            "resume: human node %r rejected with no on_reject route — run stalled.",
            event.node_id,
        )
        return False

    # Re-arm the reject target and everything forward-downstream of it (their
    # state derives from the target's previous run) — EXCEPT the rejecting
    # human node itself, which keeps needs_fix + fields.answer so the answer
    # reaches the re-run's scope/brief.  Stale edge records produced by (or
    # through) the re-armed subtree are purged, exactly like the runner's
    # back-edge reset path (R8), so resume seeding re-evaluates them fresh.
    fresh = state_ops.read()
    _, _, forward_adjacency = _graph_structures(graph)
    reset_ids = ({on_reject} | _forward_downstream(forward_adjacency, on_reject)) - {
        event.node_id
    }
    _rearm_nodes(
        graph,
        state_ops,
        fresh,
        reset_ids=reset_ids,
        purge_sources=reset_ids | {event.node_id},
        reason=f"reject route {event.node_id}→{on_reject}",
    )
    state_ops.write({"status": "running"})
    log.info(
        "resume: human node %r rejected — on_reject target %r re-armed "
        "(reset %d node(s)).",
        event.node_id, on_reject, len(reset_ids),
    )
    return True


def _apply_retry_failed(
    graph: IRGraph,
    state_ops: "StateOps",
    state: WorkflowState,
    event: RetryFailed,
    max_retries: int,
) -> bool:
    if state.status not in ("failed", "escalated", "stalled"):
        raise ResumeError(
            f"RetryFailed requires a 'failed', 'escalated' or 'stalled' run; the "
            f"persisted run status is {state.status!r}"
        )

    node_by_id = _node_by_id(graph)
    if event.node_ids == "all":
        targets = sorted(
            nid
            for nid, ns in state.nodes.items()
            if ns.status in ("failed", "escalated") and nid in node_by_id
        )
        if not targets:
            raise ResumeError(
                "RetryFailed('all') matched no failed/escalated node — there is "
                "nothing to retry (name a needs_fix gate explicitly to re-arm it)"
            )
    else:
        targets = list(event.node_ids)
        if not targets:
            raise ResumeError("RetryFailed requires at least one node id (or 'all')")
        for nid in targets:
            if nid not in node_by_id:
                raise ResumeError(
                    f"RetryFailed names node {nid!r}, which is not in the graph"
                )
            ns = state.nodes.get(nid)
            if ns is None or ns.status not in _RETRYABLE_NODE_STATUSES:
                raise ResumeError(
                    f"RetryFailed names node {nid!r} whose persisted status is "
                    f"{ns.status if ns is not None else '<absent>'!r} — only "
                    f"{'/'.join(_RETRYABLE_NODE_STATUSES)} nodes can be re-armed"
                )

    # Retry ceiling, persisted IN STATE (§5.3 — deletes failed_resumes.json).
    # Prune counters whose node has since progressed past a retryable status.
    retries = {
        nid: int(count)
        for nid, count in (state.resume_retries or {}).items()
        if (ns := state.nodes.get(nid)) is not None
        and ns.status in _RETRYABLE_NODE_STATUSES
    }
    exhausted = sorted(nid for nid in targets if retries.get(nid, 0) >= max_retries)
    if exhausted:
        stall = {
            "kind": "retry_exhausted",
            "nodes": exhausted,
            "reason": (
                f"node(s) {', '.join(exhausted)} were already re-armed "
                f"{max_retries} time(s) by resume and keep failing — refusing to "
                "loop; fix the root cause (an agent exiting -9 was killed out of "
                "memory) before retrying or start a fresh run"
            ),
        }
        state_ops.write({
            "status": "stalled", "stall": stall, "resume_retries": retries,
        })
        log.warning(
            "resume: RetryFailed ceiling reached for %s — run stalled "
            "(retry_exhausted).", exhausted,
        )
        return False

    for nid in targets:
        retries[nid] = retries.get(nid, 0) + 1
    state_ops.write({"resume_retries": retries})

    # Re-arm: reset each target in place (status pending, stale artifact/
    # fields/gate cleared, attempt PRESERVED — the generation bump is what
    # makes resume seeding re-fire its in-edges) and purge any stale edge
    # records it sourced.  A failed node halted the run before routing, so no
    # downstream reset is needed.
    fresh = state_ops.read()
    _rearm_nodes(
        graph,
        state_ops,
        fresh,
        reset_ids=set(targets),
        purge_sources=set(targets),
        reason=f"RetryFailed({targets})",
    )
    state_ops.write({"status": "running", "stall": None})
    log.info(
        "resume: re-armed failed node(s) %s (resume_retries=%s).", targets, retries,
    )
    return True


def _apply_raise_budget(
    state_ops: "StateOps",
    state: WorkflowState,
    event: RaiseBudget,
) -> bool:
    if state.status not in ("escalated", "blocked"):
        raise ResumeError(
            f"RaiseBudget requires an 'escalated' or 'blocked' run; the persisted "
            f"run status is {state.status!r}"
        )
    new_ceiling = float(event.new_usd_ceiling)
    if not math.isfinite(new_ceiling) or new_ceiling <= 0:
        # NaN would vacuously pass the must-strictly-raise guard below and
        # persist a ceiling every future comparison ignores — budget
        # enforcement permanently disabled (and state.json non-JSON-standard).
        raise ResumeError(
            f"RaiseBudget({event.new_usd_ceiling!r}) is not a finite positive "
            "USD ceiling"
        )
    if new_ceiling <= state.budget.usd_ceiling:
        raise ResumeError(
            f"RaiseBudget({new_ceiling}) does not raise the current ceiling "
            f"({state.budget.usd_ceiling}) — nothing would change"
        )
    state_ops.write({
        "budget": {
            "usd_ceiling": new_ceiling,
            "usd_spent": state.budget.usd_spent,
        },
        "status": "running",
    })
    log.info(
        "resume: budget ceiling lifted %s → %s — run re-armed.",
        state.budget.usd_ceiling, new_ceiling,
    )
    return True


def _apply_nothing(
    graph: IRGraph,
    state_ops: "StateOps",
    state: WorkflowState,
) -> bool:
    if state.status != "escalated":
        raise ResumeError(
            f"Nothing() is only legal on an 'escalated' run (external mitigation "
            f"re-entry); the persisted run status is {state.status!r}"
        )
    # Complete served timed waits (see module docstring: re-arming them would
    # re-escalate instantly — the D7 livelock).
    completed: dict[str, Any] = {}
    for node in graph.nodes:
        if node.kind != "wait" or (node.data or {}).get("mode", "human") != "timed":
            continue
        ns = state.nodes.get(node.id)
        if ns is not None and ns.status == "escalated":
            completed[node.id] = {
                "status": "done",
                "fields": {**(ns.fields or {}), "wait_elapsed": True},
            }
    patch: dict[str, Any] = {"status": "running"}
    if completed:
        patch["nodes"] = completed
        log.info(
            "resume: Nothing() completed served timed wait(s) %s.",
            sorted(completed),
        )
    state_ops.write(patch)
    return True


# ---------------------------------------------------------------------------
# Graph/reset helpers
# ---------------------------------------------------------------------------


def _node_by_id(graph: IRGraph) -> dict[str, IRNode]:
    return {n.id: n for n in graph.nodes}


def _is_human_node(node: IRNode) -> bool:
    """A node that legally parks the run 'blocked' awaiting a HumanAnswer."""
    if node.kind == "human":
        return True
    return node.kind == "wait" and (node.data or {}).get("mode", "human") == "human"


def _graph_structures(
    graph: IRGraph,
) -> tuple[
    dict[str, list[tuple[int, Any]]],
    dict[str, set[int]],
    dict[str, list[str]],
]:
    """(outgoing, forward_in_edges, forward_adjacency) — the same positional
    back-edge rule runner/core.py uses, so resume-time resets and purges
    operate on identical structures."""
    node_pos = {n.id: i for i, n in enumerate(graph.nodes)}
    outgoing: dict[str, list[tuple[int, Any]]] = {n.id: [] for n in graph.nodes}
    forward_in_edges: dict[str, set[int]] = {n.id: set() for n in graph.nodes}
    forward_adjacency: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for edge_idx, edge in enumerate(graph.edges):
        outgoing.setdefault(edge.source, []).append((edge_idx, edge))
        src_pos = node_pos.get(edge.source, 0)
        tgt_pos = node_pos.get(edge.target, len(graph.nodes))
        if src_pos < tgt_pos:
            forward_in_edges.setdefault(edge.target, set()).add(edge_idx)
            forward_adjacency.setdefault(edge.source, []).append(edge.target)
    return outgoing, forward_in_edges, forward_adjacency


def _forward_downstream(
    forward_adjacency: dict[str, list[str]], start: str
) -> set[str]:
    seen: set[str] = set()
    stack = list(forward_adjacency.get(start, ()))
    while stack:
        nid = stack.pop()
        if nid in seen or nid == start:
            continue
        seen.add(nid)
        stack.extend(forward_adjacency.get(nid, ()))
    return seen


def _rearm_nodes(
    graph: IRGraph,
    state_ops: "StateOps",
    state: WorkflowState,
    *,
    reset_ids: set[str],
    purge_sources: set[str],
    reason: str,
) -> None:
    """Reset *reset_ids* for re-execution and purge their stale edge records.

    Uses the exact R8 machinery the runner's back-edge path uses:
    ``reset_downstream_nodes`` (status → pending, artifact/fields/gate
    cleared, ``attempt`` preserved so the generation bump invalidates old
    in-edge fires and resume seeding re-fires them) plus the fired/excluded
    record purge for edges sourced from *purge_sources* — without the purge a
    stale exclusion recorded in a previous generation would survive the reset
    and permanently starve the re-armed subtree on the next resume.
    """
    from runner.core import (
        _graph_fingerprint,
        _load_edge_record,
        _persist_edge_record,
        _purge_reset_edge_records,
    )
    from runner.loop import reset_downstream_nodes

    reset_downstream_nodes(
        f"resume:{reason}", state, sorted(reset_ids), state_ops=state_ops
    )

    outgoing, forward_in_edges, _ = _graph_structures(graph)
    fingerprint = _graph_fingerprint(graph)
    fired, excluded = _load_edge_record(state.edges_evaluated, fingerprint)
    _purge_reset_edge_records(
        set(purge_sources), outgoing, forward_in_edges, fired, excluded
    )
    _persist_edge_record(state, state_ops, fired, excluded, fingerprint)
