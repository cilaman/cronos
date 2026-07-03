"""
backend/app/harnesses/state_mapping — RunState ↔ WorkflowState mapping.

Pure functions with no app-runtime imports.  Standalone testable.

SCOPE (R10d)
------------
These tables exist ONLY to persist the harness UI/REST vocabulary: the
RunState JSON consumed by ``GET /api/harness-runs/{run_id}`` and the frontend
overlay (``runStatus.ts``: node 'pending|in_progress|done|failed|skipped',
run 'running|done|failed|cancelled') and to rebuild a WorkflowState on
runner-path resume.  TERMINAL interpretation does NOT flow through them:
``run_executor`` finalizes the tracking task from the package ``Outcome``
via the shared table in ``app.delivery_outcomes`` (kills D16 — the old
``failed``/``escalated`` → task-DONE collapse lived downstream of this
module and is gone).

Status mapping (node-level)
---------------------------
Harness RunState NodeState statuses:
    'pending'     — not yet started
    'in_progress' — currently executing (incl. a parked human Wait — BFS
                    convention: the node stays in_progress while WAITING)
    'done'        — finished successfully
    'failed'      — finished with an error
    'skipped'     — bypassed by control-flow (treated as done for the runner)

Delivery-workflow WorkflowState NodeState statuses:
    'running'    — currently executing
    'done'       — finished successfully
    'failed'     — finished with an error
    'blocked'    — waiting / not yet started / parked human wait
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
    'blocked'    → 'pending'      EXCEPT the parked human-wait node named by
                                  ``waiting_node_id`` → 'in_progress' (R10d:
                                  fixes the D16-note collision where the node
                                  the run is parked ON rendered identically
                                  to genuinely-unreached nodes)
    'escalated'  → 'failed'  (loop exhausted is a hard failure for RunState)
    'needs_fix'  → 'failed'  (R9: a gate's non-proceed terminal.  The harness
                              compiler emits no gate nodes, so this is
                              defensive only — mapping it to a terminal keeps
                              an unexpected needs_fix from defaulting to
                              'pending' and silently re-running the node.)

Run-level status mapping
------------------------
Forward (RunState.status → WorkflowState.status):
    'running'   → 'running'    EXCEPT when ``waiting_node_id`` names a
                               still-'in_progress' node → 'blocked' (+ that
                               node → 'blocked'): the parked human wait is
                               rebuilt so ``DeliveryRun.resume(HumanAnswer)``
                               is legal on re-entry and bare ``start()`` is
                               sealed on the park (see runstate_to_workflowstate)
    'done'      → 'done'
    'failed'    → 'failed'
    'cancelled' → 'cancelled'  (R10d: WorkflowState gained a real 'cancelled'
                                in R10b — the runner's sealed re-entry guard
                                now halts a cancelled harness run instead of
                                treating it as a retryable failure)

Reverse (WorkflowState.status → RunState.status):
    'running'   → 'running'
    'done'      → 'done'
    'failed'    → 'failed'
    'blocked'   → 'running'  (parked waiting, harness is still running —
                              and still cancellable via the cancel endpoint)
    'escalated' → 'failed'
    'cancelled' → 'cancelled'
    'stalled'   → 'failed'   (R6: the runner proved the run incomplete — starved
                              nodes or exhausted gate fix-loop.  The RunState/UI
                              vocabulary has no 'stalled' value; 'failed' is the
                              honest pill, and the machine-readable detail is
                              preserved verbatim on ``RunState.stall``.  The
                              tracking-task terminal comes from the Outcome
                              table, not from this value.)

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
run level, and so do the R7 ``resume_retries`` counters (dropping them would
unbound the RetryFailed ceiling across a harness restart).

Round-trip contract
-------------------
runstate_to_workflowstate(rs, hid) followed by workflowstate_to_runstate(ws, rs)
must produce a RunState equal to the original for all fields in NodeState,
including ``fields`` extras and the run-level ``edges_evaluated``, ``stall``
and ``resume_retries`` records.
"""
from __future__ import annotations

from delivery_workflow.state_types import BudgetState
from delivery_workflow.state_types import NodeState as WfNodeState
from delivery_workflow.state_types import WorkflowState

from app.harnesses.run_state import NodeState as HarnessNodeState
from app.harnesses.run_state import RunState

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
    # R9 defensive entry: gate-only status; unreachable via the harness
    # compiler (no gate kind) but must never default to 'pending' (re-run).
    "needs_fix": "failed",
}

_HARNESS_TO_WF_RUN: dict[str, str] = {
    "running": "running",
    "done": "done",
    "failed": "failed",
    # R10d: 'cancelled' is a real WorkflowState status since R10b — the
    # runner's sealed re-entry guard halts on it (a cancelled run stays
    # cancelled instead of being re-run as a 'failed' retry).
    "cancelled": "cancelled",
}

_WF_TO_HARNESS_RUN: dict[str, str] = {
    "running": "running",
    "done": "done",
    "failed": "failed",
    "blocked": "running",
    "escalated": "failed",
    "cancelled": "cancelled",
    # R6: a 'stalled' workflow (completeness invariant unmet / gate fix-loop
    # exhausted) has no RunState/UI vocabulary value; 'failed' is the honest
    # pill and the stall detail round-trips via RunState.stall.  The tracking
    # task's terminal comes from the shared Outcome table (R10d), not from
    # this persisted value.
    "stalled": "failed",
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

    # Rebuild the human-wait park (R10d follow-up).  The RunState/UI
    # vocabulary has no 'blocked' run status (a parked harness renders
    # 'running' and stays cancellable), so ``waiting_node_id`` IS the
    # persisted park marker: when it names a still-live ('in_progress' →
    # 'running') node on a 'running' run, the runner-facing state must show
    # run 'blocked' + node 'blocked' — otherwise a resumed run re-dispatches
    # the wait node instead of accepting a ``HumanAnswer`` (and ``start()``
    # is never sealed on the park).  ``waiting_node_id`` is only ever pinned
    # from a blocked Outcome's human node (run_executor step 5), so this
    # cannot capture an agent node.  Round-trip fidelity is preserved via
    # ``fields['_harness_status']`` (node) and 'blocked' → 'running' (run).
    if run_state.waiting_node_id is not None and run_status == "running":
        parked = nodes.get(run_state.waiting_node_id)
        if parked is not None and parked.status == "running":
            parked.status = "blocked"
            run_status = "blocked"

    return WorkflowState(
        spec=harness_id,
        run_id=run_state.run_id,
        status=run_status,  # type: ignore[arg-type]
        budget=_ZERO_BUDGET,
        nodes=nodes,
        edges_evaluated=dict(run_state.edges_evaluated),
        # R6 stall detail round-trips verbatim (run level, like edges_evaluated).
        stall=run_state.stall,
        # R7 RetryFailed counters round-trip verbatim (run level).
        resume_retries=dict(run_state.resume_retries),
    )


def workflowstate_to_runstate(
    workflow_state: WorkflowState,
    base_run_state: RunState,
    *,
    waiting_node_id: str | None = None,
) -> RunState:
    """Convert a runner WorkflowState back into a harness RunState.

    The ``base_run_state`` supplies immutable identity fields (``run_id``,
    ``harness_id``, ``goal_task_id``) that are not encoded in WorkflowState.
    All node execution data is taken from ``workflow_state.nodes``.

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
    waiting_node_id:
        The human-wait node a ``blocked`` run is parked on (R10d — the
        caller derives it from ``Outcome.node_id``).  When given, it (a)
        becomes ``RunState.waiting_node_id`` (the resume-routing key —
        ``base_run_state``'s value is used when None) and (b) maps that
        node's ``blocked`` status to ``'in_progress'`` per the BFS
        convention, so the parked node no longer renders identically to
        genuinely-unreached ``'pending'`` nodes (the D16-note collision).

    Returns
    -------
    RunState
        A new RunState reflecting the runner's updated execution progress.
    """
    run_status = _WF_TO_HARNESS_RUN.get(workflow_state.status, "running")
    effective_waiting = (
        waiting_node_id if waiting_node_id is not None
        else base_run_state.waiting_node_id
    )

    nodes: dict[str, HarnessNodeState] = {}
    for node_id, wf_node in workflow_state.nodes.items():
        fields = wf_node.fields or {}

        # Prefer the stored original harness status for perfect round-trip
        # fidelity (e.g. 'skipped' which maps to 'done' in the forward pass) —
        # but ONLY when it is still CONSISTENT with the runner-side status.
        # After a resume the runner mutates node statuses (an answered
        # sign-off goes 'blocked' → 'done'); the sentinel planted by the
        # forward pass is then stale and must not resurrect the old status.
        sentinel = fields.get("_harness_status")
        if sentinel and _HARNESS_TO_WF_NODE.get(sentinel) == wf_node.status:
            harness_status = sentinel
        elif node_id == effective_waiting and wf_node.status == "blocked":
            # The parked human-wait node itself is live, not unreached (R10d).
            harness_status = "in_progress"
        else:
            harness_status = _WF_TO_HARNESS_NODE.get(wf_node.status, "pending")

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
        waiting_node_id=effective_waiting,
        edges_evaluated=dict(workflow_state.edges_evaluated),
        # R6: preserve the runner's run-level stall detail ('stalled' itself
        # maps to 'failed' — no such RunState value — but the reason survives).
        stall=workflow_state.stall,
        # R7: preserve the RetryFailed counters — the ceiling must bind
        # across harness restarts.
        resume_retries=dict(workflow_state.resume_retries),
    )
