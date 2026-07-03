"""
backend/app/harnesses/state_mapping — RunState ↔ WorkflowState mapping.

Pure functions with no app-runtime imports.  Standalone testable.

Status mapping (node-level)
---------------------------
Harness RunState NodeState statuses:
    'pending'     — not yet started
    'in_progress' — currently executing
    'done'        — finished successfully
    'failed'      — finished with an error
    'skipped'     — bypassed by control-flow (treated as done for the runner)

Delivery-workflow WorkflowState NodeState statuses:
    'running'    — currently executing
    'done'       — finished successfully
    'failed'     — finished with an error
    'blocked'    — waiting / not yet started
    'escalated'  — loop exhausted or hard failure requiring human escalation

Forward mapping  (harness → runner):
    'pending'     → 'blocked'
    'in_progress' → 'running'
    'done'        → 'done'
    'failed'      → 'failed'
    'skipped'     → 'done'   (skipped is terminal; runner treats it as success)

Reverse mapping  (runner → harness):
    'running'    → 'in_progress'
    'done'       → 'done'
    'failed'     → 'failed'
    'blocked'    → 'pending'
    'escalated'  → 'failed'  (loop exhausted is a hard failure for RunState)

Run-level status mapping
------------------------
Forward (RunState.status → WorkflowState.status):
    'running'   → 'running'
    'done'      → 'done'
    'failed'    → 'failed'
    'cancelled' → 'failed'   (no cancelled concept in WorkflowState)

Reverse (WorkflowState.status → RunState.status):
    'running'   → 'running'
    'done'      → 'done'
    'failed'    → 'failed'
    'blocked'   → 'running'  (parked waiting, harness is still running)
    'escalated' → 'failed'

Loop bookkeeping
----------------
NodeState.attempt is stored directly on WfNodeState.attempt (same field name).
NodeState.prior_finding_ids is stored in WfNodeState.fields['prior_finding_ids'].

Routing-field and edge-record fidelity (R5)
-------------------------------------------
The runner path stores agent envelope fields (``verdict``, ``exit_reason``, …)
in ``WfNodeState.fields`` and its fired/excluded forward-edge record in
``WorkflowState.edges_evaluated``.  Both MUST survive the RunState mapping:
without them, R5's condition-aware resume seeding re-evaluates routing
conditions against missing keys → every branch False → transitive exclusion
→ the run finishes 'done' with the downstream tail silently never executed.
Non-reserved ``WfNodeState.fields`` keys round-trip via
``HarnessNodeState.fields``; ``edges_evaluated`` round-trips verbatim on the
run level.

Round-trip contract
-------------------
runstate_to_workflowstate(rs, hid) followed by workflowstate_to_runstate(ws, rs)
must produce a RunState equal to the original for all fields in NodeState,
including ``fields`` extras and the run-level ``edges_evaluated`` record.
"""
from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Import boundary: bring delivery-workflow package into the path without
# importing any app-runtime modules.
# ---------------------------------------------------------------------------
_DELIVERY_WF = Path(__file__).parent.parent.parent.parent / "packages" / "delivery-workflow"
if str(_DELIVERY_WF) not in sys.path:
    sys.path.insert(0, str(_DELIVERY_WF))

from state_types import BudgetState  # noqa: E402
from state_types import NodeState as WfNodeState  # noqa: E402
from state_types import WorkflowState  # noqa: E402

from app.harnesses.run_state import NodeState as HarnessNodeState  # noqa: E402
from app.harnesses.run_state import RunState  # noqa: E402

# ---------------------------------------------------------------------------
# Status translation tables
# ---------------------------------------------------------------------------

_HARNESS_TO_WF_NODE: dict[str, str] = {
    "pending": "blocked",
    "in_progress": "running",
    "done": "done",
    "failed": "failed",
    "skipped": "done",
}

_WF_TO_HARNESS_NODE: dict[str, str] = {
    "running": "in_progress",
    "done": "done",
    "failed": "failed",
    "blocked": "pending",
    "escalated": "failed",
}

_HARNESS_TO_WF_RUN: dict[str, str] = {
    "running": "running",
    "done": "done",
    "failed": "failed",
    "cancelled": "failed",
}

_WF_TO_HARNESS_RUN: dict[str, str] = {
    "running": "running",
    "done": "done",
    "failed": "failed",
    "blocked": "running",
    "escalated": "failed",
}

# Sentinel budget used when constructing a WorkflowState from a RunState that
# has no budget information.  Zero ceiling, zero spent.
_ZERO_BUDGET = BudgetState(usd_ceiling=0.0, usd_spent=0.0)

# WfNodeState.fields keys owned by the mapping itself (canonical attributes on
# HarnessNodeState plus the status sentinel).  Everything else is a routing/
# envelope extra (e.g. ``verdict``) that round-trips via HarnessNodeState.fields.
_RESERVED_FIELD_KEYS = frozenset({
    "prior_finding_ids",
    "child_task_id",
    "output",
    "reason",
    "started_at",
    "ended_at",
    "wake_at",
    "_harness_status",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def runstate_to_workflowstate(run_state: RunState, harness_id: str) -> WorkflowState:
    """Convert a harness RunState snapshot into a runner WorkflowState.

    Parameters
    ----------
    run_state:
        The harness executor's current RunState.
    harness_id:
        The harness identifier, used as the ``spec`` field of the resulting
        WorkflowState.

    Returns
    -------
    WorkflowState
        A new WorkflowState reflecting the same execution progress.
        Loop-bookkeeping fields are preserved:
        - ``WfNodeState.attempt`` ← ``HarnessNodeState.attempt``
        - ``WfNodeState.fields['prior_finding_ids']`` ← ``HarnessNodeState.prior_finding_ids``
        - ``WfNodeState.fields['child_task_id']`` ← ``HarnessNodeState.child_task_id``
        - ``WfNodeState.fields['output']`` ← ``HarnessNodeState.output``
        - ``WfNodeState.fields['reason']`` ← ``HarnessNodeState.reason``
        - ``WfNodeState.fields['started_at']`` ← ``HarnessNodeState.started_at``
        - ``WfNodeState.fields['ended_at']`` ← ``HarnessNodeState.ended_at``
        - ``WfNodeState.fields['wake_at']`` ← ``HarnessNodeState.wake_at``
        - non-reserved ``HarnessNodeState.fields`` extras (e.g. ``verdict``)
          are merged into ``WfNodeState.fields`` (R5 routing-field fidelity)
        - ``WorkflowState.edges_evaluated`` ← ``RunState.edges_evaluated``
    """
    run_status = _HARNESS_TO_WF_RUN.get(run_state.status, "running")

    nodes: dict[str, WfNodeState] = {}
    for node_id, ns in run_state.nodes_executed.items():
        wf_status = _HARNESS_TO_WF_NODE.get(ns.status, "blocked")
        wf_node = WfNodeState(
            status=wf_status,
            attempt=ns.attempt,
            fields={
                # Envelope/routing extras first — canonical keys below win.
                **dict(ns.fields),
                "prior_finding_ids": list(ns.prior_finding_ids),
                "child_task_id": ns.child_task_id,
                "output": ns.output,
                "reason": ns.reason,
                "started_at": ns.started_at,
                "ended_at": ns.ended_at,
                "wake_at": ns.wake_at,
                # Preserve the original harness status so reverse mapping
                # can reconstruct skipped nodes faithfully.
                "_harness_status": ns.status,
            },
        )
        nodes[node_id] = wf_node

    return WorkflowState(
        spec=harness_id,
        run_id=run_state.run_id,
        status=run_status,  # type: ignore[arg-type]
        budget=_ZERO_BUDGET,
        nodes=nodes,
        edges_evaluated=dict(run_state.edges_evaluated),
    )


def workflowstate_to_runstate(
    workflow_state: WorkflowState,
    base_run_state: RunState,
) -> RunState:
    """Convert a runner WorkflowState back into a harness RunState.

    The ``base_run_state`` supplies immutable identity fields (``run_id``,
    ``harness_id``, ``goal_task_id``, ``waiting_node_id``) that are not
    encoded in WorkflowState.  All node execution data is taken from
    ``workflow_state.nodes``.

    Round-trip guarantee
    --------------------
    ``workflowstate_to_runstate(runstate_to_workflowstate(rs, hid), rs) == rs``
    for any well-formed RunState ``rs``.

    Parameters
    ----------
    workflow_state:
        The runner's current WorkflowState.
    base_run_state:
        The original RunState used to supply identity and routing fields.

    Returns
    -------
    RunState
        A new RunState reflecting the runner's updated execution progress.
    """
    run_status = _WF_TO_HARNESS_RUN.get(workflow_state.status, "running")

    nodes: dict[str, HarnessNodeState] = {}
    for node_id, wf_node in workflow_state.nodes.items():
        fields = wf_node.fields or {}

        # Prefer the stored original harness status for perfect round-trip
        # fidelity (e.g. 'skipped' which maps to 'done' in the forward pass).
        harness_status = fields.get("_harness_status") or _WF_TO_HARNESS_NODE.get(
            wf_node.status, "pending"
        )

        h_node = HarnessNodeState(
            status=harness_status,
            child_task_id=fields.get("child_task_id"),
            output=fields.get("output"),
            reason=fields.get("reason"),
            started_at=fields.get("started_at"),
            ended_at=fields.get("ended_at"),
            wake_at=fields.get("wake_at"),
            attempt=wf_node.attempt,
            prior_finding_ids=list(fields.get("prior_finding_ids") or []),
            # Routing/envelope extras (e.g. ``verdict``) — everything the
            # runner stored beyond the reserved canonical keys (R5).
            fields={
                k: v for k, v in fields.items() if k not in _RESERVED_FIELD_KEYS
            },
        )
        nodes[node_id] = h_node

    return RunState(
        run_id=base_run_state.run_id,
        harness_id=base_run_state.harness_id,
        goal_task_id=base_run_state.goal_task_id,
        nodes_executed=nodes,
        status=run_status,
        waiting_node_id=base_run_state.waiting_node_id,
        edges_evaluated=dict(workflow_state.edges_evaluated),
    )
