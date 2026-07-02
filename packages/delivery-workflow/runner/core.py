"""
runner/core.py — Cyclic work-list walker for the delivery-workflow runner.

Implements the main execution loop described in the SG4 design:
- Seeds entry nodes (in-degree == 0) into the work-list.
- On each tick: cancel-race guard, scope rebuild, node dispatch, edge evaluation.
- Supports back-edges (loop iterations) via LoopPolicy (handled by loop.py).
- Enforces a global iteration cap to prevent infinite loops.
- Resume: skips nodes already done in the provided WorkflowState.
- Terminal state is written via state_ops.write on exit.

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
    from runner.loop import should_loop_back
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

    # Successors: node_id → list of IREdge (outgoing)
    outgoing: dict[str, list[IREdge]] = {n.id: [] for n in graph.nodes}
    # Predecessors: node_id → list of source node ids (incoming), in edge-
    # declaration order.  Used to hand a gate node its upstream producer's
    # artifact_paths (a gate produces none of its own).
    incoming: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    # Forward-edge in_degree only (back-edges excluded to avoid deadlock in
    # cyclic graphs).  A back-edge is one where the source position >= target
    # position in the nodes list (i.e. it points "backwards").
    in_degree: dict[str, int] = {n.id: 0 for n in graph.nodes}
    for edge in graph.edges:
        outgoing[edge.source].append(edge)
        incoming.setdefault(edge.target, []).append(edge.source)
        # Only count forward edges in initial in_degree.
        src_pos = node_pos.get(edge.source, 0)
        tgt_pos = node_pos.get(edge.target, len(graph.nodes))
        if src_pos < tgt_pos:
            in_degree[edge.target] += 1

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

    # Resume: mark already-done nodes as dispatched and adjust forward in_degree.
    for node_id, ns in state.nodes.items():
        if ns.status == "done":
            dispatched.add(node_id)
            for edge in outgoing.get(node_id, []):
                src_pos = node_pos.get(node_id, 0)
                tgt_pos = node_pos.get(edge.target, len(graph.nodes))
                if src_pos < tgt_pos:  # only forward edges counted in in_degree
                    in_degree[edge.target] = max(0, in_degree[edge.target] - 1)

    # Seed every ready node (forward in_degree 0) that is not already dispatched.
    # On a fresh run this is exactly graph.entry_nodes (both derive from the same
    # forward-edge in_degree).  On resume it ALSO includes nodes whose
    # predecessors are already `done` — their in_degree was decremented above —
    # so the run progresses past the resumed frontier instead of finishing early
    # with an empty work-list (B1 resume fix).
    for node in graph.nodes:
        nid = node.id
        if nid not in dispatched and in_degree.get(nid, 0) == 0:
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
                    # Back-edge: re-enqueue this node; dispatched flag cleared.
                    dispatched.discard(node_id)
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
            in_degree=in_degree,
            work_list=work_list,
            executor=executor,
            scope=build_scope(state, scope_base=dict(graph.variables)),
        )

    # -----------------------------------------------------------------------
    # Work-list exhausted — workflow done.
    # -----------------------------------------------------------------------
    state.status = "done"
    if state_ops is not None:
        state_ops.write({"status": "done"})
    return state


def _enqueue_successors(
    node_id: str,
    outgoing: dict[str, list[IREdge]],
    state: WorkflowState,
    dispatched: set[str],
    in_degree: dict[str, int],
    work_list: list[str],
    executor: "ExecutorInterface",
    scope: dict[str, str],
) -> None:
    """Evaluate outgoing edges from *node_id* and enqueue ready successors.

    Back-edge handling: when a condition fires to an already-dispatched node
    (a cyclic loop-back), the target is reset to 'pending' and re-enqueued
    directly, bypassing the forward-only in_degree counter.
    """
    for edge in outgoing.get(node_id, []):
        target = edge.target

        # Evaluate edge condition.
        if edge.when == "" or edge.when is None:
            condition_met = True
        else:
            condition_met = executor.evalCondition(edge.when, scope)

        if not condition_met:
            continue

        if target in dispatched:
            # Back-edge (loop-back): target was already executed.  Reset and
            # re-enqueue it for another execution pass.
            dispatched.discard(target)
            ns = state.nodes.get(target)
            if ns is not None:
                ns.status = "pending"
                ns.artifact_paths = []
                ns.fields = {}
                ns.gate = None
            if target not in work_list:
                work_list.append(target)
        else:
            # Forward edge: decrement in_degree and enqueue when ready.
            in_degree[target] = max(0, in_degree.get(target, 1) - 1)
            if in_degree[target] == 0 and target not in work_list:
                work_list.append(target)
