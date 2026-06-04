"""
backend/app/harnesses/aggregator — Aggregator node evaluator.

The Aggregator node synchronises N predecessor nodes before allowing the
harness to proceed.  Two modes are supported:

``mode='all'``
    All predecessors must reach a terminal state (``'done'`` or ``'failed'``)
    before the Aggregator fires.  If **any** predecessor failed the Aggregator
    verdict is ``'failed'`` (partial-failure semantics, R7).  If all
    predecessors are ``'done'`` the verdict is ``'done'``.  While at least one
    predecessor is still pending/in_progress the verdict is ``'pending'``.

``mode='any'``
    The Aggregator fires as soon as the **first** predecessor reaches
    ``'done'``.  Other predecessors may still be running.  The Aggregator only
    becomes ``'failed'`` if **all** predecessors have failed and none is done.
    If no predecessor is done yet (but at least one is still
    pending/in_progress) the verdict is ``'pending'``.

Predecessor discovery
---------------------
Predecessors are determined on-the-fly by reverse edge traversal:

    predecessor_ids = [
        e.source.node_id
        for e in harness.edges
        if e.target.node_id == node.id
    ]

No separate predecessor list is stored on the node — the edge graph is the
sole source of truth.

Public API
----------
``aggregator_ready(node, predecessors_state) -> AggregatorVerdict``
    Evaluate readiness for *node* given a mapping of predecessor node-ids to
    their current ``NodeState``.

``compose_output(verdict, predecessors_state, mode) -> dict``
    Compose the aggregated output dict from predecessor states once a terminal
    verdict is known.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import HarnessNode
    from .run_state import NodeState


class AggregatorVerdict(str, Enum):
    """Possible verdicts returned by ``aggregator_ready()``."""

    pending = "pending"
    done = "done"
    failed = "failed"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def aggregator_ready(
    node: "HarnessNode",
    predecessors_state: "dict[str, NodeState]",
) -> AggregatorVerdict:
    """Evaluate whether the Aggregator *node* is ready to fire.

    Parameters
    ----------
    node:
        The Aggregator ``HarnessNode``.  ``node.data['mode']`` must be
        ``'all'`` or ``'any'``.  Defaults to ``'all'`` if absent.
    predecessors_state:
        Mapping of ``node_id -> NodeState`` for each predecessor of *node*.
        Predecessor ids are obtained by the caller via reverse edge traversal:

            {
                e.source.node_id: run_state.nodes_executed[e.source.node_id]
                for e in harness.edges
                if e.target.node_id == node.id
                and e.source.node_id in run_state.nodes_executed
            }

        Predecessors not yet in ``nodes_executed`` should be represented with
        a synthetic ``NodeState(status='pending')``.

    Returns
    -------
    AggregatorVerdict
        ``done``, ``failed``, or ``pending``.
    """
    mode: str = node.data.get("mode", "all")

    done_count = 0
    failed_count = 0
    total = len(predecessors_state)

    for ns in predecessors_state.values():
        if ns.status == "done":
            done_count += 1
        elif ns.status == "failed":
            failed_count += 1
        # 'pending', 'in_progress', 'skipped' are treated as not-yet-terminal

    terminal_count = done_count + failed_count

    if mode == "all":
        # All predecessors must be terminal before we can fire.
        if terminal_count < total:
            return AggregatorVerdict.pending
        # All are terminal.  If any failed, the aggregator fails.
        if failed_count > 0:
            return AggregatorVerdict.failed
        return AggregatorVerdict.done

    elif mode == "any":
        # Fire as soon as the first predecessor is done.
        if done_count > 0:
            return AggregatorVerdict.done
        # All predecessors have failed and none is done.
        if failed_count == total and total > 0:
            return AggregatorVerdict.failed
        # Still waiting for at least one predecessor to finish.
        return AggregatorVerdict.pending

    else:
        # Unknown mode — treat as 'all' but log a warning via caller.
        if terminal_count < total:
            return AggregatorVerdict.pending
        if failed_count > 0:
            return AggregatorVerdict.failed
        return AggregatorVerdict.done


def compose_output(
    verdict: AggregatorVerdict,
    predecessors_state: "dict[str, NodeState]",
    mode: str,
) -> dict:
    """Compose an aggregated output dict from predecessor states.

    Parameters
    ----------
    verdict:
        The ``AggregatorVerdict`` already determined by ``aggregator_ready()``.
    predecessors_state:
        Same mapping passed to ``aggregator_ready()``.
    mode:
        ``'all'`` or ``'any'``.

    Returns
    -------
    dict
        For ``done`` verdict + ``mode='all'``:
            ``{'outputs': {node_id: output, ...}, 'done_count': N, 'failed_count': 0}``
        For ``done`` verdict + ``mode='any'``:
            ``{'first_done_node_id': <id>, 'output': <output>, 'done_count': N}``
        For ``failed`` verdict:
            ``{'failed_nodes': {node_id: reason, ...}, 'done_count': N, 'failed_count': M}``
        For ``pending`` verdict:
            ``{}`` (caller should not normally call compose_output while pending)
    """
    done_nodes: dict[str, str | None] = {}
    failed_nodes: dict[str, str | None] = {}
    first_done_id: str | None = None
    first_done_output: str | None = None

    for node_id, ns in predecessors_state.items():
        if ns.status == "done":
            done_nodes[node_id] = ns.output
            if first_done_id is None:
                first_done_id = node_id
                first_done_output = ns.output
        elif ns.status == "failed":
            failed_nodes[node_id] = ns.reason

    done_count = len(done_nodes)
    failed_count = len(failed_nodes)

    if verdict == AggregatorVerdict.done:
        if mode == "any":
            return {
                "first_done_node_id": first_done_id,
                "output": first_done_output,
                "done_count": done_count,
            }
        else:  # mode == 'all'
            return {
                "outputs": dict(done_nodes),
                "done_count": done_count,
                "failed_count": failed_count,
            }

    if verdict == AggregatorVerdict.failed:
        return {
            "failed_nodes": dict(failed_nodes),
            "done_count": done_count,
            "failed_count": failed_count,
        }

    # pending — return empty dict
    return {}
