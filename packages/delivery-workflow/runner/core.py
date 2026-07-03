"""
runner/core.py — Cyclic work-list walker for the delivery-workflow runner.

Implements the main execution loop described in the SG4 design:
- Seeds entry nodes (no forward in-edges) into the work-list.
- On each tick: cancel-race guard, scope rebuild, node dispatch, edge evaluation.
- Supports back-edges (loop iterations) via LoopPolicy (handled by loop.py).
- Enforces a global iteration cap to prevent infinite loops.
- Resume: skips nodes already done in the provided WorkflowState.
- Terminal state is written via state_ops.write on exit.

Join arithmetic (R8, kills D9): forward-edge joins are tracked by a fired-edge
set keyed ``(edge_index, target_generation)`` instead of the historical
decrement-with-clamp in-degree counter.  A target is ready when every one of
its NON-EXCLUDED forward in-edges has fired in the target's CURRENT generation
(its ``attempt`` at fire time), so a looping source re-firing the same edge
cannot double-satisfy a join, and fires recorded before a downstream reset
cannot satisfy the next iteration.

Exclusion propagation (R5, kills D1): a forward edge whose ``when`` condition
evaluates false is recorded *excluded*; a node ALL of whose forward in-edges
are excluded (and none fired) is excluded, and its own outgoing forward edges
are excluded in turn (recorded, not evaluated).  A join therefore fires once
every non-excluded in-edge has fired — an excluded branch (e.g. ``frontend``
when ``has_ui == false``) drops out of the join requirement instead of
starving it.  The same mechanism runs at fire time (``_enqueue_successors``)
and at resume seeding, so a run that routes past a false branch without a park
behaves identically to one that parks.  Back-edges are NOT part of exclusion
accounting (they are excluded from the join in-degree already).

Both edge sets are persisted as the ``edges_evaluated`` record (target §5.2)
through ``state_ops.write({"edges_evaluated": …})`` so resume edge replay is
idempotent across multiple resumes.  The record carries a ``graph_fingerprint``
(hash of the edge list): entries are keyed by positional edge index, so a
record written against a *different* graph (spec/harness edited between park
and resume) would misattribute fired/excluded entries to shifted edges — on
fingerprint mismatch the record is discarded and seeding falls back to
condition re-evaluation.  When the record is absent (pre-R5 state.json,
StateOps that ignore the key), resume seeding rebuilds it by re-evaluating
each done node's outgoing ``when`` conditions against the rebuilt typed scope
(complete since R2+R3) — idempotent by construction.  Replay never re-records
a fire into an already-``done`` target (the target ran — re-recording at its
post-run generation would make the record path-dependent between a
straight-through run and a parked+resumed one).

No app.* imports allowed (enforced by .importlinter).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ir import IREdge, IRGraph, IRNode
from state_types import BudgetState, NodeState, WorkflowState

if TYPE_CHECKING:
    from interface import ExecutorInterface, StateOps

log = logging.getLogger(__name__)

# Sentinel used as a module-level constant to avoid inline magic strings.
_DELIVERY_NODE_SENTINEL = "<!-- delivery-node: {node_id} -->"


def run(
    graph: IRGraph,
    executor: "ExecutorInterface",
    state_ops: "StateOps | None" = None,
) -> WorkflowState:
    """Execute *graph* against *executor*; return the final WorkflowState.

    Parameters
    ----------
    graph:
        The compiled IRGraph (output of compiler_a.compile).
    executor:
        A concrete ExecutorInterface (CronosAdapter or NullRuntime subclass).
    state_ops:
        Optional StateOps for persistence and cancel-race detection.  When
        None a simple in-memory state is used (unit-test mode).

    Returns
    -------
    WorkflowState
        The final state after all reachable nodes have been executed (or the
        run was cancelled / blocked / escalated).
    """
    from runner.dispatch import NodeOutcome, dispatch_node
    from runner.loop import reset_downstream_nodes, should_loop_back
    from runner.scope import build_scope

    # -----------------------------------------------------------------------
    # Initialise or reload WorkflowState.
    # -----------------------------------------------------------------------
    if state_ops is not None:
        state = state_ops.read()
    else:
        budget_meta = graph.metadata.get("budget", {})
        ceiling = float(budget_meta.get("usd_ceiling", 0.0))
        state = WorkflowState(
            spec=graph.metadata.get("name", ""),
            run_id="",
            status="running",
            budget=BudgetState(usd_ceiling=ceiling),
        )

    # -----------------------------------------------------------------------
    # Build graph structures.
    # -----------------------------------------------------------------------
    node_by_id: dict[str, IRNode] = {n.id: n for n in graph.nodes}
    node_pos: dict[str, int] = {n.id: i for i, n in enumerate(graph.nodes)}

    # Successors: node_id → list of (edge_index, IREdge) (outgoing).  The edge
    # index identifies the edge in the fired-edge bookkeeping (two declared
    # edges between the same node pair stay distinct).
    outgoing: dict[str, list[tuple[int, IREdge]]] = {n.id: [] for n in graph.nodes}
    # Predecessors: node_id → list of source node ids (incoming), in edge-
    # declaration order.  Used to hand a gate node its upstream producer's
    # artifact_paths (a gate produces none of its own).
    incoming: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    # Forward in-edges per target (back-edges excluded to avoid deadlock in
    # cyclic graphs).  A back-edge is one where the source position >= target
    # position in the nodes list (i.e. it points "backwards").
    forward_in_edges: dict[str, set[int]] = {n.id: set() for n in graph.nodes}
    # Forward adjacency (source → forward targets) for downstream resets.
    forward_adjacency: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for edge_idx, edge in enumerate(graph.edges):
        outgoing[edge.source].append((edge_idx, edge))
        incoming.setdefault(edge.target, []).append(edge.source)
        src_pos = node_pos.get(edge.source, 0)
        tgt_pos = node_pos.get(edge.target, len(graph.nodes))
        if src_pos < tgt_pos:
            forward_in_edges.setdefault(edge.target, set()).add(edge_idx)
            forward_adjacency.setdefault(edge.source, []).append(edge.target)

    # Edge-evaluation sets (R8/D9 + R5/D1): target → {(edge_index, target_
    # generation)}.  `fired_edges` records forward edges whose condition
    # evaluated true; `excluded_edges` records forward edges that evaluated
    # false or were transitively excluded.  Both are persisted as the
    # `edges_evaluated` record and reloaded here; an absent record — or one
    # written against a different graph (fingerprint mismatch) — degrades to
    # condition re-evaluation in the resume seeding below.
    graph_fingerprint = _graph_fingerprint(graph)
    fired_edges, excluded_edges = _load_edge_record(
        state.edges_evaluated, graph_fingerprint
    )

    # -----------------------------------------------------------------------
    # Global iteration cap: sum(max loop iterations) * 2 or 200, whichever
    # is larger.  Prevents infinite loops on never-True edge conditions.
    # -----------------------------------------------------------------------
    max_loop_sum = sum(
        (n.loop.max if n.loop else 1) for n in graph.nodes
    )
    global_cap = max(200, max_loop_sum * 2)

    # -----------------------------------------------------------------------
    # Seed work-list with entry nodes; skip already-done nodes (resume path).
    # -----------------------------------------------------------------------
    # Work-list holds node ids that are ready to execute.
    work_list: list[str] = []
    # Track which nodes we've dispatched (to avoid double-dispatch on resume).
    dispatched: set[str] = set()

    # Resume: mark already-done nodes as dispatched, then replay their forward
    # out-edges CONDITION-AWARE (R5, kills D1).  For every forward out-edge of
    # a persisted-`done` node not already covered by the persisted
    # `edges_evaluated` record (in the target's current generation), evaluate
    # its `when` condition against the rebuilt typed scope: true → fired,
    # false → excluded (with transitive exclusion propagation).  Replay is
    # idempotent: recorded edges are skipped, and re-evaluation from the
    # persisted scope reproduces the same result when the record was lost.
    done_node_ids = [nid for nid, ns in state.nodes.items() if ns.status == "done"]
    dispatched.update(done_node_ids)
    if done_node_ids:
        resume_scope = build_scope(state, scope_base=dict(graph.variables))
        for node_id in done_node_ids:
            for edge_idx, edge in outgoing.get(node_id, []):
                if edge_idx not in forward_in_edges.get(edge.target, ()):
                    continue  # back-edge — loops re-enter via live fires only
                gen = _generation(state, edge.target)
                if (edge_idx, gen) in fired_edges.get(edge.target, ()):
                    continue  # persisted record: already fired
                if (edge_idx, gen) in excluded_edges.get(edge.target, ()):
                    continue  # persisted record: evaluated false / excluded
                if edge.when == "" or edge.when is None:
                    condition_met = True
                else:
                    condition_met = executor.evalCondition(edge.when, resume_scope)
                if condition_met:
                    target_ns = state.nodes.get(edge.target)
                    if target_ns is not None and target_ns.status == "done":
                        # Target already ran — the fire proves nothing, and
                        # re-recording it at the target's post-run generation
                        # would make the persisted record path-dependent
                        # (parked+resumed vs straight-through divergence).
                        continue
                    _record_edge_fire(fired_edges, edge_idx, edge.target, state)
                else:
                    _apply_exclusion(
                        edge_idx,
                        edge.target,
                        fired_edges=fired_edges,
                        excluded_edges=excluded_edges,
                        forward_in_edges=forward_in_edges,
                        outgoing=outgoing,
                        state=state,
                        dispatched=dispatched,
                        work_list=work_list,
                    )
        _persist_edge_record(
            state, state_ops, fired_edges, excluded_edges, graph_fingerprint
        )

    # Seed every ready node (all non-excluded forward in-edges fired, or none
    # declared) that is not already dispatched.  On a fresh run this is exactly
    # graph.entry_nodes (both derive from the same forward-edge rule).  On
    # resume it ALSO includes nodes whose predecessors are already `done` —
    # their in-edges were replayed above — so the run progresses past the
    # resumed frontier instead of finishing early with an empty work-list (B1
    # resume fix).  Nodes already enqueued by exclusion propagation are kept.
    for node in graph.nodes:
        nid = node.id
        if (
            nid not in dispatched
            and nid not in work_list
            and _join_satisfied(
                fired_edges, excluded_edges, forward_in_edges, state, nid
            )
        ):
            work_list.append(nid)

    global_iterations = 0

    # -----------------------------------------------------------------------
    # Main work-list loop.
    # -----------------------------------------------------------------------
    while work_list:
        # Cancel-race guard: reload state and check for cancellation.
        if state_ops is not None:
            current = state_ops.read()
            if current.status in ("cancelled", "blocked", "escalated"):
                log.info("Runner: cancel/block signal detected — halting.")
                return current

        if global_iterations >= global_cap:
            log.error(
                "Runner: global iteration cap %d exceeded — escalating.", global_cap
            )
            executor.escalate("__runner__", "global_iteration_cap_exceeded")
            state.status = "escalated"
            if state_ops is not None:
                state_ops.write({"status": "escalated"})
            return state

        global_iterations += 1

        # Pop next node from work-list (FIFO for determinism).
        node_id = work_list.pop(0)

        if node_id in dispatched and state.nodes.get(node_id, NodeState(status="")).status == "done":
            # Already completed (can happen after a back-edge re-seed with stale entry).
            continue

        node = node_by_id.get(node_id)
        if node is None:
            log.warning("Runner: unknown node_id %r in work-list; skipping.", node_id)
            continue

        # ----------------------------------------------------------------
        # Settle guard (R8/D9 corollary): a FORWARD-ancestor of this node is
        # still queued — a back-edge reset re-enqueued it after this node
        # became ready (e.g. an exclusion-completed join enqueued mid-loop).
        # Dispatching now would run the node on pre-settle scope, and the
        # ancestor's re-fire would then reset and run it AGAIN — whether that
        # happens depends only on edge declaration order.  Defer to the back
        # of the list instead: forward edges form a DAG, so the queue always
        # contains a node with no queued ancestor and deferral terminates
        # (each deferral consumes one global iteration, bounded by the cap).
        # ----------------------------------------------------------------
        if any(
            node_id in _forward_downstream(forward_adjacency, queued)
            for queued in work_list
        ):
            log.debug(
                "Runner: deferring %r — a queued forward-ancestor has not settled.",
                node_id,
            )
            work_list.append(node_id)
            continue

        # ----------------------------------------------------------------
        # Build scope from all currently-done nodes.
        # ----------------------------------------------------------------
        scope = build_scope(state, scope_base=dict(graph.variables))

        # ----------------------------------------------------------------
        # Dispatch the node.
        # ----------------------------------------------------------------
        log.debug("Runner: dispatching node %r (kind=%s)", node_id, node.kind)
        outcome: NodeOutcome = dispatch_node(
            node=node,
            scope=scope,
            executor=executor,
            state=state,
            incoming=incoming,
        )

        # ----------------------------------------------------------------
        # Persist outcome into state.
        # ----------------------------------------------------------------
        ns = NodeState(
            status=outcome.status,
            attempt=outcome.attempt,
            artifact_paths=outcome.artifact_paths,
            gate=outcome.gate,
            fields=outcome.fields,
        )
        state.nodes[node_id] = ns
        if state_ops is not None:
            state_ops.write({"nodes": {node_id: {
                "status": ns.status,
                "attempt": ns.attempt,
                "artifact_paths": ns.artifact_paths,
                "gate": ns.gate,
                "fields": ns.fields,
            }}})

        # ----------------------------------------------------------------
        # Handle non-done outcomes.
        # ----------------------------------------------------------------
        if outcome.status == "blocked":
            log.info("Runner: node %r blocked — halting run.", node_id)
            state.status = "blocked"
            if state_ops is not None:
                state_ops.write({"status": "blocked"})
            return state

        if outcome.status == "failed":
            log.error("Runner: node %r failed — halting run.", node_id)
            state.status = "failed"
            if state_ops is not None:
                state_ops.write({"status": "failed"})
            return state

        if outcome.status == "escalated":
            log.info("Runner: node %r escalated — halting run.", node_id)
            state.status = "escalated"
            if state_ops is not None:
                state_ops.write({"status": "escalated"})
            return state

        # Node is done — mark dispatched.
        dispatched.add(node_id)

        # ----------------------------------------------------------------
        # Check loop-back (LoopPolicy) — may reset and re-enqueue.
        # ----------------------------------------------------------------
        if node.loop is not None:
            if node.kind == "gate":
                # Gate fix-loop: the loop BOUNDS the fix back-edge; it does NOT
                # self-retry the gate (that would only re-check unchanged
                # upstream output → same decision → burn the whole budget, and
                # `continue`ing here would skip _enqueue_successors so the
                # non-proceed fix edge to the producer never fires).  Instead we
                # fall through to _enqueue_successors so a non-proceed decision
                # routes back to the producing agent (a forward edge to an
                # already-dispatched producer is handled as a back-edge there),
                # and cap the number of gate evaluations by loop.max via the
                # gate's attempt counter.
                decision = (ns.gate or {}).get("decision")
                if decision != "proceed" and ns.attempt >= node.loop.max:
                    # Fix-loop exhausted.  Dead-end (skip _enqueue_successors) so
                    # the run drains to status="done" with the gate's non-proceed
                    # decision persisted, and the driver parks the goal WAITING
                    # with the actionable _stalled_gate_reason.  We deliberately
                    # do NOT executor.escalate() — that parks a generic message
                    # and blocks the actionable one.
                    log.info(
                        "Runner: gate %r fix-loop exhausted (attempt %d >= max %d, "
                        "decision=%s) — dead-ending for WAITING park.",
                        node_id, ns.attempt, node.loop.max, decision,
                    )
                    continue
                # else: fall through to _enqueue_successors (routes fix edge on
                # non-proceed, forward edge on proceed).
            else:
                # Rebuild scope with this node's just-written outcome.
                updated_scope = build_scope(state, scope_base=dict(graph.variables))
                loop_back = should_loop_back(node, state, updated_scope, executor)
                if loop_back:
                    # Loop-back: re-enqueue this node; dispatched flag cleared.
                    # Downstream nodes that consumed the previous iteration's
                    # output are reset (in state AND storage) so their stale
                    # fields/gates cannot leak into scope or survive a park.
                    dispatched.discard(node_id)
                    reset_downstream_nodes(
                        node_id,
                        state,
                        _forward_downstream(forward_adjacency, node_id),
                        state_ops=state_ops,
                    )
                    work_list.insert(0, node_id)
                    continue

        # ----------------------------------------------------------------
        # Evaluate outgoing edges and enqueue ready successors.
        # ----------------------------------------------------------------
        _enqueue_successors(
            node_id=node_id,
            outgoing=outgoing,
            state=state,
            dispatched=dispatched,
            fired_edges=fired_edges,
            excluded_edges=excluded_edges,
            forward_in_edges=forward_in_edges,
            forward_adjacency=forward_adjacency,
            work_list=work_list,
            executor=executor,
            scope=build_scope(state, scope_base=dict(graph.variables)),
            state_ops=state_ops,
        )

        # Persist the edge-evaluation record (R5): fired + excluded forward
        # edges, so a park/resume replays them instead of re-deciding routing.
        _persist_edge_record(
            state, state_ops, fired_edges, excluded_edges, graph_fingerprint
        )

    # -----------------------------------------------------------------------
    # Work-list exhausted — workflow done.
    # -----------------------------------------------------------------------
    state.status = "done"
    if state_ops is not None:
        state_ops.write({"status": "done"})
    return state


def _generation(state: WorkflowState, node_id: str) -> int:
    """A node's generation = its attempt count (number of completed runs).

    Fired edges are keyed by the TARGET's generation at fire time: fires
    accumulated for one upcoming run of the target all share its current
    generation, and once the target re-runs (or is reset for re-execution,
    which preserves ``attempt``) older fires no longer satisfy it.
    """
    ns = state.nodes.get(node_id)
    return ns.attempt if ns is not None else 0


def _record_edge_fire(
    fired_edges: dict[str, set[tuple[int, int]]],
    edge_idx: int,
    target: str,
    state: WorkflowState,
) -> None:
    """Record a forward-edge fire keyed ``(edge_index, target_generation)``.

    Re-firing the same edge in the same generation (a looping source, D9)
    de-duplicates in the set and therefore cannot double-satisfy a join.
    """
    fired_edges.setdefault(target, set()).add((edge_idx, _generation(state, target)))


def _join_satisfied(
    fired_edges: dict[str, set[tuple[int, int]]],
    excluded_edges: dict[str, set[tuple[int, int]]],
    forward_in_edges: dict[str, set[int]],
    state: WorkflowState,
    target: str,
) -> bool:
    """True when every NON-EXCLUDED forward in-edge of *target* fired in its
    current generation (R5): excluded edges drop out of the join requirement,
    but at least one in-edge must have actually fired — a node all of whose
    in-edges are excluded is excluded, not ready."""
    need = forward_in_edges.get(target, set())
    if not need:
        return True  # entry node — no forward in-edges to wait for
    gen = _generation(state, target)
    have_fired = {idx for (idx, g) in fired_edges.get(target, ()) if g == gen}
    if not have_fired:
        return False  # nothing fired — either not ready yet, or excluded
    have_excluded = {idx for (idx, g) in excluded_edges.get(target, ()) if g == gen}
    return need <= (have_fired | have_excluded)


def _node_excluded(
    fired_edges: dict[str, set[tuple[int, int]]],
    excluded_edges: dict[str, set[tuple[int, int]]],
    forward_in_edges: dict[str, set[int]],
    state: WorkflowState,
    target: str,
) -> bool:
    """True when ALL forward in-edges of *target* are excluded and none fired
    in its current generation (R5 transitive exclusion).  Entry nodes are
    never excluded; a fired in-edge always wins over exclusion records."""
    need = forward_in_edges.get(target, set())
    if not need:
        return False
    gen = _generation(state, target)
    if any(g == gen for (_, g) in fired_edges.get(target, ())):
        return False
    have_excluded = {idx for (idx, g) in excluded_edges.get(target, ()) if g == gen}
    return need <= have_excluded


def _apply_exclusion(
    edge_idx: int,
    target: str,
    *,
    fired_edges: dict[str, set[tuple[int, int]]],
    excluded_edges: dict[str, set[tuple[int, int]]],
    forward_in_edges: dict[str, set[int]],
    outgoing: dict[str, list[tuple[int, IREdge]]],
    state: WorkflowState,
    dispatched: set[str],
    work_list: list[str],
) -> None:
    """Record an evaluated-false forward edge and propagate exclusion (R5/D1).

    Shared by resume seeding and forward execution (``_enqueue_successors``)
    so both paths route identically:

    - the edge is recorded excluded for the target's current generation;
    - a node ALL of whose forward in-edges are excluded (and none fired) is
      excluded, and its own outgoing forward edges are excluded in turn
      (recorded, not evaluated) — transitively;
    - a join whose remaining non-excluded in-edges have all fired becomes
      ready and is enqueued (the exclusion completed the join).

    The walk follows forward edges only (a DAG by the positional back-edge
    rule), so it terminates; already-dispatched targets get the record but no
    propagation (they executed — their out-edges were evaluated for real).
    """
    stack: list[tuple[int, str]] = [(edge_idx, target)]
    while stack:
        idx, tgt = stack.pop()
        excluded_edges.setdefault(tgt, set()).add((idx, _generation(state, tgt)))
        if tgt in dispatched:
            continue
        if _node_excluded(fired_edges, excluded_edges, forward_in_edges, state, tgt):
            for out_idx, out_edge in outgoing.get(tgt, []):
                if out_idx not in forward_in_edges.get(out_edge.target, ()):
                    continue  # back-edges never participate in exclusion
                entry = (out_idx, _generation(state, out_edge.target))
                if entry not in excluded_edges.get(out_edge.target, set()):
                    stack.append((out_idx, out_edge.target))
        elif (
            _join_satisfied(fired_edges, excluded_edges, forward_in_edges, state, tgt)
            and tgt not in work_list
        ):
            work_list.append(tgt)


def _graph_fingerprint(graph: IRGraph) -> str:
    """Stable hash of the graph's edge list (source, target, when).

    The ``edges_evaluated`` record keys entries by positional edge index; the
    fingerprint detects a spec/harness edit between park and resume (edge
    inserted, removed or reordered), where the same index would denote a
    DIFFERENT edge and the record would silently misroute the resumed run.
    """
    import hashlib

    payload = "\n".join(
        f"{e.source}->{e.target}?{e.when or ''}" for e in graph.edges
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _load_edge_record(
    record: dict[str, Any] | None,
    graph_fingerprint: str,
) -> tuple[dict[str, set[tuple[int, int]]], dict[str, set[tuple[int, int]]]]:
    """Rebuild the in-memory (fired, excluded) edge sets from a persisted
    ``edges_evaluated`` record.  Tolerant: an absent/malformed record yields
    empty sets (resume seeding then re-evaluates conditions instead).  A
    record written against a different graph (``graph_fingerprint`` present
    and mismatched) is discarded wholesale — its positional edge indices
    would misattribute fired/excluded entries to different edges."""
    fired: dict[str, set[tuple[int, int]]] = {}
    excluded: dict[str, set[tuple[int, int]]] = {}
    if not isinstance(record, dict):
        return fired, excluded
    recorded_fp = record.get("graph_fingerprint")
    if isinstance(recorded_fp, str) and recorded_fp != graph_fingerprint:
        log.warning(
            "Runner: edges_evaluated record was written against a different "
            "graph (fingerprint %r != %r) — discarding; resume seeding "
            "re-evaluates edge conditions from the persisted scope.",
            recorded_fp, graph_fingerprint,
        )
        return fired, excluded
    for key, dest in (("fired", fired), ("excluded", excluded)):
        entries = record.get(key)
        if not isinstance(entries, dict):
            continue
        for target, pairs in entries.items():
            try:
                dest[str(target)] = {(int(i), int(g)) for i, g in pairs}
            except (TypeError, ValueError):
                log.warning(
                    "Runner: malformed edges_evaluated entry for %r — ignored.",
                    target,
                )
    return fired, excluded


def _persist_edge_record(
    state: WorkflowState,
    state_ops: "StateOps | None",
    fired_edges: dict[str, set[tuple[int, int]]],
    excluded_edges: dict[str, set[tuple[int, int]]],
    graph_fingerprint: str,
) -> None:
    """Serialize the edge sets into ``state.edges_evaluated`` and persist the
    full snapshot through StateOps (no-op when nothing changed).  The record
    carries the graph fingerprint so a later resume against an edited graph
    discards it instead of misattributing positional edge indices."""
    record: dict[str, Any] = {}
    for key, source in (("fired", fired_edges), ("excluded", excluded_edges)):
        serialized = {
            tgt: sorted([list(entry) for entry in entries])
            for tgt, entries in sorted(source.items())
            if entries
        }
        if serialized:
            record[key] = serialized
    if record:
        record["graph_fingerprint"] = graph_fingerprint
    if record == state.edges_evaluated:
        return
    state.edges_evaluated = record
    if state_ops is not None:
        state_ops.write({"edges_evaluated": record})


def _forward_downstream(
    forward_adjacency: dict[str, list[str]], start: str
) -> list[str]:
    """Node ids transitively reachable from *start* via forward edges (excl. start)."""
    seen: set[str] = set()
    stack = list(forward_adjacency.get(start, ()))
    while stack:
        nid = stack.pop()
        if nid in seen or nid == start:
            continue
        seen.add(nid)
        stack.extend(forward_adjacency.get(nid, ()))
    return sorted(seen)


def _enqueue_successors(
    node_id: str,
    outgoing: dict[str, list[tuple[int, IREdge]]],
    state: WorkflowState,
    dispatched: set[str],
    fired_edges: dict[str, set[tuple[int, int]]],
    excluded_edges: dict[str, set[tuple[int, int]]],
    forward_in_edges: dict[str, set[int]],
    forward_adjacency: dict[str, list[str]],
    work_list: list[str],
    executor: "ExecutorInterface",
    scope: dict[str, Any],
    state_ops: "StateOps | None" = None,
) -> None:
    """Evaluate outgoing edges from *node_id* and enqueue ready successors.

    Forward edges are recorded in the fired-edge set and the target enqueued
    only once EVERY one of its non-excluded forward in-edges has fired in its
    current generation (R8/D9 — a looping source re-firing one edge cannot
    satisfy a join on behalf of predecessors that never ran).

    A forward edge whose condition evaluates FALSE is recorded excluded and
    exclusion propagates transitively (R5/D1, ``_apply_exclusion``) — the same
    mechanism resume seeding uses, so routing past a false branch behaves
    identically with and without an intervening park.

    Back-edge handling: when a condition fires to an already-dispatched node
    (a cyclic loop-back), the target AND its forward-downstream nodes are
    reset to 'pending' (stale fields/artifacts/gates cleared in state and
    storage — see ``reset_downstream_nodes``) and the target is re-enqueued
    directly, bypassing the join bookkeeping.  A back-edge evaluating false is
    NOT an exclusion (back-edges never participate in exclusion accounting).
    """
    from runner.loop import reset_downstream_nodes

    for edge_idx, edge in outgoing.get(node_id, []):
        target = edge.target

        # Evaluate edge condition.
        if edge.when == "" or edge.when is None:
            condition_met = True
        else:
            condition_met = executor.evalCondition(edge.when, scope)

        if not condition_met:
            if edge_idx in forward_in_edges.get(target, ()):
                # Forward edge evaluated false — record + propagate exclusion.
                _apply_exclusion(
                    edge_idx,
                    target,
                    fired_edges=fired_edges,
                    excluded_edges=excluded_edges,
                    forward_in_edges=forward_in_edges,
                    outgoing=outgoing,
                    state=state,
                    dispatched=dispatched,
                    work_list=work_list,
                )
            continue

        if target in dispatched:
            # Back-edge (loop-back): target was already executed.  Reset it and
            # everything forward-downstream of it (their state derives from the
            # target's previous run and is now stale — persistently so since
            # fields persist, R2), then re-enqueue it for another pass.
            dispatched.discard(target)
            reset_downstream_nodes(
                target,
                state,
                [target, *_forward_downstream(forward_adjacency, target)],
                state_ops=state_ops,
            )
            if target not in work_list:
                work_list.append(target)
        else:
            # Forward edge: record the fire; enqueue once the join is complete
            # (every non-excluded forward in-edge fired, R5).
            _record_edge_fire(fired_edges, edge_idx, target, state)
            if (
                _join_satisfied(
                    fired_edges, excluded_edges, forward_in_edges, state, target
                )
                and target not in work_list
            ):
                work_list.append(target)
