"""
runner/loop.py — LoopPolicy evaluation for the cyclic work-list runner.

Evaluates LoopPolicy.until against the current scope to determine if the
work-list should loop back (re-execute) a node.  Enforces LoopPolicy.max.

Back-edge reset: when a node is re-enqueued by loop, all downstream NodeState
entries that were derived from this node's previous run are reset to 'pending'
(zeroing artifact_paths and fields) to prevent stale-scope bugs.

No app.* imports allowed (enforced by .importlinter).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ir import IRNode
from state_types import NodeState, WorkflowState

if TYPE_CHECKING:
    from interface import ExecutorInterface

log = logging.getLogger(__name__)


def should_loop_back(
    node: IRNode,
    state: WorkflowState,
    scope: dict[str, str],
    executor: "ExecutorInterface",
) -> bool:
    """Return True if this node should loop back (be re-executed).

    Evaluates ``node.loop.until`` against *scope*.  If the condition is True,
    the loop exits (no loop-back).  If False and the attempt count has not
    reached the max, the node is re-enqueued.

    Side effects when True (loop-back):
    - Increments ``state.nodes[node.id].attempt``.
    - Zeros artifact_paths and fields on the node's own NodeState so that
      the next run starts clean.
    - Zeroes NodeState fields on all downstream nodes that transitively depended
      on this node (prevents stale-scope bugs described in the risk register).

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

    # Loop back: increment attempt and zero downstream state.
    log.debug(
        "Loop node %r: looping back (attempt %d → %d).", node.id, current_attempt, current_attempt + 1
    )
    if current_ns is not None:
        current_ns.attempt = current_attempt + 1
        current_ns.artifact_paths = []
        current_ns.fields = {}
    else:
        state.nodes[node.id] = NodeState(status="done", attempt=current_attempt + 1)

    return True


def reset_downstream_nodes(
    node_id: str,
    state: WorkflowState,
    downstream_ids: list[str],
) -> None:
    """Zero the NodeState for all downstream nodes of *node_id*.

    Called by the runner before re-enqueuing a looping node to prevent
    stale artifact_paths and fields from surfacing via scope.py.

    Parameters
    ----------
    node_id:
        The node that is looping back (its direct successors are reset).
    state:
        WorkflowState mutated in-place.
    downstream_ids:
        List of all node ids transitively reachable from *node_id* (computed
        by the caller from the IRGraph edge list).
    """
    for did in downstream_ids:
        ns = state.nodes.get(did)
        if ns is not None:
            ns.status = "pending"
            ns.artifact_paths = []
            ns.fields = {}
            ns.gate = None
