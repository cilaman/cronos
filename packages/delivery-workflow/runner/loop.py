"""
runner/loop.py — LoopPolicy evaluation for the cyclic work-list runner.

Evaluates LoopPolicy.until against the current scope to determine if the
work-list should loop back (re-execute) a node.  Enforces LoopPolicy.max.

Attempt ownership (R8, kills D8): ``NodeState.attempt`` has a SINGLE writer —
``runner/dispatch.py`` increments it once per execution (``attempt = old + 1``).
The loop-back path must never touch it; the historical second increment here
roughly halved every loop budget (``max=4`` yielded 3 executions with the
counter overshooting to 5).  ``loop.max=N`` now yields exactly N executions
with final ``attempt == N``.

Back-edge reset: when a node is re-enqueued (by its own LoopPolicy or by a
back-edge fire), all downstream NodeState entries derived from its previous
run are reset to 'pending' (zeroing artifact_paths, fields and gate) to
prevent stale-scope bugs.  Since fields persist (R2), the reset is also
written through StateOps when provided — otherwise the staleness would be
*persistent* across a park/resume.

No app.* imports allowed (enforced by .importlinter).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ir import IRNode
from state_types import NodeState, WorkflowState

if TYPE_CHECKING:
    from interface import ExecutorInterface, StateOps

log = logging.getLogger(__name__)


def should_loop_back(
    node: IRNode,
    state: WorkflowState,
    scope: dict[str, Any],
    executor: "ExecutorInterface",
) -> bool:
    """Return True if this node should loop back (be re-executed).

    Evaluates ``node.loop.until`` against *scope*.  If the condition is True,
    the loop exits (no loop-back).  If False and the attempt count has not
    reached the max, the node is re-enqueued.

    Side effects when True (loop-back):
    - Zeros artifact_paths and fields on the node's own NodeState so that
      the next run starts clean.  ``attempt`` is NOT touched — dispatch is the
      single attempt owner (R8/D8); it increments once per execution.
    - Downstream stale state is reset by the caller (runner/core.py) via
      ``reset_downstream_nodes``.

    When the loop is exhausted (attempt >= max):
    - Calls ``executor.escalate(node.id, reason)`` or stops (per on_exhaust).
    - Returns False (the runner will see status=escalated/done and halt naturally
      after the next state write).
    """
    if node.loop is None:
        return False

    loop = node.loop

    # Evaluate the until condition.
    until_met: bool = False
    if loop.until:
        try:
            until_met = executor.evalCondition(loop.until, scope)
        except Exception as exc:
            log.warning("should_loop_back: evalCondition raised %s — defaulting to False", exc)

    if until_met:
        # Condition satisfied — do NOT loop back.
        log.debug("Loop node %r: until-condition met — exiting loop.", node.id)
        return False

    # Condition not yet satisfied — check attempt count.
    current_ns = state.nodes.get(node.id)
    current_attempt = current_ns.attempt if current_ns else 0

    if current_attempt >= loop.max:
        # Max iterations reached.
        log.warning(
            "Loop node %r: max iterations (%d) reached — %s.",
            node.id, loop.max, loop.on_exhaust,
        )
        if loop.on_exhaust == "escalate":
            executor.escalate(
                node.id,
                f"Loop max iterations reached for node {node.id!r} "
                f"(max={loop.max}); condition={loop.until!r}",
            )
            # Update state to escalated so the caller halts.
            if current_ns is not None:
                current_ns.status = "escalated"
            else:
                state.nodes[node.id] = NodeState(status="escalated", attempt=current_attempt)
        # on_exhaust='stop': leave status='done' and exit without escalating.
        return False

    # Loop back: zero the node's own transient state.  The attempt counter is
    # deliberately NOT incremented here — dispatch owns it (R8/D8: the second
    # increment halved loop budgets and overshot the cap).
    log.debug(
        "Loop node %r: looping back (attempt %d of max %d).",
        node.id, current_attempt, loop.max,
    )
    if current_ns is not None:
        current_ns.artifact_paths = []
        current_ns.fields = {}
    else:
        # Defensive: the runner always writes the node's outcome before the
        # loop check, so this branch is unreachable in the normal walk.
        state.nodes[node.id] = NodeState(status="done", attempt=current_attempt)

    return True


def reset_downstream_nodes(
    node_id: str,
    state: WorkflowState,
    downstream_ids: list[str],
    state_ops: "StateOps | None" = None,
) -> list[str]:
    """Zero the NodeState for all downstream nodes of *node_id*.

    Called by the runner (runner/core.py) when a node is re-enqueued for
    another execution — by its own LoopPolicy loop-back or by a back-edge
    fire — to prevent stale artifact_paths, fields and gate decisions from
    surfacing via scope.py.  With fields persisting (R2), the reset is also
    written through *state_ops* so the staleness cannot survive a park/resume:
    the in-memory mutation covers merge-style StateOps (which share the state
    object with the runner) and the explicit write covers replace-style ones
    (which read-modify-write from storage) — both end with the same cleared
    values.

    Nodes with no state, or whose state is already clear, are skipped (keeps
    the persisted event log free of no-op pending→pending transitions).

    Parameters
    ----------
    node_id:
        The node being re-enqueued (used for logging only).
    state:
        WorkflowState mutated in-place.
    downstream_ids:
        List of all node ids transitively reachable from *node_id* via
        forward edges (computed by the caller from the IRGraph edge list).
    state_ops:
        Optional StateOps; when provided, the resets are persisted.

    Returns
    -------
    list[str]
        The node ids that actually held stale state and were reset.
    """
    reset_ids: list[str] = []
    for did in downstream_ids:
        ns = state.nodes.get(did)
        if ns is None:
            continue
        if (
            ns.status == "pending"
            and not ns.artifact_paths
            and not ns.fields
            and ns.gate is None
        ):
            continue  # already clear — nothing stale to reset
        ns.status = "pending"
        ns.artifact_paths = []
        ns.fields = {}
        ns.gate = None
        reset_ids.append(did)

    if state_ops is not None and reset_ids:
        state_ops.write({
            "nodes": {
                did: {
                    "status": "pending",
                    "artifact_paths": [],
                    "fields": {},
                    "gate": None,
                }
                for did in reset_ids
            }
        })
    if reset_ids:
        log.debug(
            "reset_downstream_nodes: %r re-enqueued — reset stale state on %s",
            node_id, reset_ids,
        )
    return reset_ids
