"""backend/app/delivery_outcomes.py — the ONE Outcome → TaskState table (R10d).

Both delivery-workflow hosts — the delivery driver (goal path,
``app.delivery_driver``) and the harness runner path
(``app.run_executor._execute_harness_run_runner``) — translate a package
``Outcome`` (``delivery_workflow.outcome``, the closed 01-state-model.md §5.6
taxonomy) into Cronos task semantics through THIS module and nothing else.

That single table kills D16 by construction: two hosts can no longer
interpret the same run terminal differently (the harness path's old
``failed``/``escalated`` → DONE collapse is gone — a failed workflow now
parks its tracking task WAITING kind='node_failed' on both paths).

The §5.6 mapping (kind → task action):

============  ==========================================================
Outcome kind  Task action
============  ==========================================================
done          DONE
stalled       WAITING, kind='stalled'      (actionable stall message)
failed        WAITING, kind='node_failed'  (reply retries via RetryFailed)
blocked       WAITING, kind='signoff' + node_id  (Approve/Reject UI);
              a run blocked on a NON-sign-off node (agent self-reported
              blocked — Outcome.node_id is None) parks with a diagnostic
              and no sign-off affordance
escalated     WAITING, kind='budget' (budget ceiling) / 'loop' (loop or
              iteration-cap exhaust) / 'escalated' (timed wait & other).
              NOTE: the 'budget' row is RESERVED — no production path emits
              ``Outcome(escalation='budget')`` yet (neither host wires
              telemetry accumulation through ``TelemetryOps.emit``, so
              ``BudgetExceededSignal`` never fires and ``outcome_from_state``
              cannot classify an escalation as budget).  The row stays in the
              table so the taxonomy is total; it becomes live the moment a
              host wires telemetry + a discriminable budget escalation record
cancelled     WAITING (no kind) — mirrors Cronos "Stopped by user."
              semantics: a user-cancelled run parks for acknowledgment;
              DONE would goal-sync-propagate success for work that was
              deliberately aborted
running       WAITING (defensive, only-if-active) — ``running`` is the
              non-terminal pure-read kind; reaching the apply path with
              it means the runner returned without a terminal, which must
              never leave the task ACTIVE forever nor count as success
============  ==========================================================

Hosts never see ``WorkflowState`` internals — they receive the Outcome from
``DeliveryRun.start()/resume()/outcome()`` and hand it to
``apply_outcome_to_task``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .models import TaskState

if TYPE_CHECKING:  # pragma: no cover — typing only
    from delivery_workflow.outcome import Outcome

    from .storage import TaskStore

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutcomeAction:
    """One row of the shared Outcome → TaskState table."""

    task_state: TaskState
    waiting_kind: str | None
    waiting_node_id: str | None
    #: waiting_question for WAITING rows; completion note for the DONE row.
    message: str
    #: True for parks the host adapter may have already made mid-run with a
    #: richer question (RunBlocked/RunEscalated → escalate bridge): the apply
    #: step must not clobber that park — it only stamps the structured wait
    #: metadata on an already-WAITING task.
    only_if_active: bool = False


def action_for_outcome(
    outcome: "Outcome", *, subject: str = "Delivery workflow"
) -> OutcomeAction:
    """The total §5.6 mapping — pure, host-shared, no I/O.

    *subject* is the display noun for messages ("Delivery workflow" for the
    goal path, "Harness run" for the harness path); it never changes the
    resulting ``TaskState``/``waiting_kind`` — those are identical for both
    hosts by construction.
    """
    kind = outcome.kind

    if kind == "done":
        return OutcomeAction(
            TaskState.DONE, None, None, f"{subject} completed successfully."
        )

    if kind == "stalled":
        return OutcomeAction(
            TaskState.WAITING,
            "stalled",
            None,
            render_stall_message(outcome.stall, subject=subject),
        )

    if kind == "failed":
        node = f"node '{outcome.node_id}'" if outcome.node_id else "a node"
        detail = f" ({outcome.reason})" if outcome.reason else ""
        return OutcomeAction(
            TaskState.WAITING,
            "node_failed",
            outcome.node_id,
            f"{subject} failed — {node} returned status=failed{detail}. "
            "Reply to retry the failed node(s).",
        )

    if kind == "blocked":
        if outcome.node_id is None:
            # Blocked on a non-sign-off node (an agent reported itself
            # blocked): no HumanAnswer applies — diagnostic, no affordance.
            return OutcomeAction(
                TaskState.WAITING,
                None,
                None,
                f"{subject} is parked 'blocked' on a non-sign-off node (an "
                "agent reported itself blocked). Inspect the node's child "
                "task, fix the blocker, and start a fresh run (or adjust "
                "the workflow spec).",
                only_if_active=True,
            )
        question = outcome.question or (
            f"{subject} paused on sign-off '{outcome.node_id}' — reply (or "
            "use Approve/Reject) to continue."
        )
        return OutcomeAction(
            TaskState.WAITING,
            "signoff",
            outcome.node_id,
            question,
            only_if_active=True,
        )

    if kind == "escalated":
        waiting_kind = {
            "budget": "budget",
            "loop": "loop",
            "iteration_cap": "loop",
        }.get(outcome.escalation or "", "escalated")
        reason = outcome.reason or "policy limit hit"
        return OutcomeAction(
            TaskState.WAITING,
            waiting_kind,
            outcome.node_id,
            f"{subject} paused ({reason}). Reply to resume.",
            only_if_active=True,
        )

    if kind == "cancelled":
        return OutcomeAction(
            TaskState.WAITING,
            None,
            None,
            f"{subject} was cancelled. Start a fresh run to re-execute it.",
        )

    # 'running' (the pure-read non-terminal kind) or a future unknown kind:
    # defensive — never DONE, never left ACTIVE.
    return OutcomeAction(
        TaskState.WAITING,
        None,
        None,
        f"{subject} ended without a terminal outcome (kind={kind!r}) — "
        "inspect the run state and re-run.",
        only_if_active=True,
    )


def render_stall_message(
    stall: dict[str, Any] | None, *, subject: str = "Delivery workflow"
) -> str:
    """Render the runner's RUN-LEVEL stall record into an actionable message.

    Reads ONLY the machine-readable ``Outcome.stall`` record the runner wrote
    with ``status='stalled'`` (``{"kind": "starved_nodes" | "gate_exhausted"
    | "rejected" | "retry_exhausted", "nodes": [...], "reason": str
    [, "dead_ends": [...]]}``).  Hosts never dig through run internals to
    explain a stall; if the record is missing (defensive), a
    generic-but-honest message is produced.
    """
    if not isinstance(stall, dict) or not stall:
        return (
            f"{subject} stalled — the run drained without completing all "
            "nodes (no stall detail available). Inspect the run state and "
            "re-run, or adjust the workflow edges."
        )
    kind = str(stall.get("kind") or "")
    nodes = ", ".join(str(n) for n in (stall.get("nodes") or [])) or "?"
    reason = str(stall.get("reason") or "")
    if kind == "gate_exhausted":
        msg = f"{subject} stalled: gate {nodes} exhausted its fix-loop"
        tail = (
            " Fix the named check/artifact and adjust the gate routing or its "
            "loop max in the workflow spec, or start a fresh run — re-running "
            "keeps the park (an exhausted gate is not blindly retried)."
        )
    elif kind == "rejected":
        msg = f"Delivery sign-off {nodes} was rejected"
        tail = (
            " The workflow declares no on_reject route for this sign-off, so "
            "the run is parked. Reply with a message to re-open the sign-off "
            "(the workflow will ask again), or add an on_reject route to the "
            "spec so a rejection re-runs the right node."
        )
    elif kind == "retry_exhausted":
        msg = f"{subject} stalled: node(s) {nodes} keep failing"
        tail = (
            " The resume retry ceiling was reached — fix the root cause (an "
            "agent exiting -9 was killed out of memory: lower "
            "CRONOS_MAX_CONCURRENT_AGENTS or raise the container "
            "mem_limit/swap) before starting a fresh run."
        )
    else:
        msg = f"{subject} stalled: node(s) {nodes} were never reached"
        tail = (
            " Fix the upstream routing fields/conditions and re-run, or "
            "adjust the workflow edges."
        )
    if reason:
        msg += f" — {reason}."
    else:
        msg += "."
    return msg + tail


async def apply_outcome_to_task(
    store: "TaskStore",
    task_id: str,
    outcome: "Outcome",
    *,
    subject: str = "Delivery workflow",
    source: str = "delivery",
) -> TaskState | None:
    """Apply the shared table to *task_id* — the ONLY finalization both hosts use.

    Returns the TaskState the task was finalized to, or ``None`` when the
    apply was a no-op (already parked / already terminal / task missing).
    """
    action = action_for_outcome(outcome, subject=subject)
    if action.task_state == TaskState.DONE:
        return await _finalize_task_done(
            store, task_id, action.message, source=source
        )
    return await park_task_waiting(
        store,
        task_id,
        action.message,
        waiting_kind=action.waiting_kind,
        waiting_node_id=action.waiting_node_id,
        only_if_active=action.only_if_active,
        source=source,
    )


async def _finalize_task_done(
    store: "TaskStore", task_id: str, message: str, *, source: str
) -> TaskState | None:
    """Finalize *task_id* to DONE after a successful runner completion."""
    try:
        task = store.get(task_id)
        if task is not None and task.state not in (
            TaskState.DONE, TaskState.ARCHIVED
        ):
            await store.finalize_run(
                task_id,
                new_state=TaskState.DONE,
                session_id=None,
                waiting_question=None,
                history_entry=f"[{source}] {message}",
            )
            return TaskState.DONE
    except Exception as exc:
        log.error(
            "delivery_outcomes: failed to finalize %s to DONE: %s", task_id, exc
        )
    return None


async def park_task_waiting(
    store: "TaskStore",
    task_id: str,
    reason: str,
    *,
    only_if_active: bool = False,
    waiting_kind: str | None = None,
    waiting_node_id: str | None = None,
    source: str = "delivery",
) -> TaskState | None:
    """Park *task_id* to WAITING with *reason* as the waiting_question.

    When *only_if_active* is True, only park a task that is still
    ACTIVE/BACKLOG — a safety net that must NOT clobber a task already parked
    WAITING by the host adapter's mid-run event handling (e.g. a human
    sign-off with its own question).

    ``waiting_kind``/``waiting_node_id`` carry the structured wait metadata
    (§5.6).  A task that is ALREADY WAITING keeps its question but still gets
    the metadata stamped (via ``set_waiting_meta``) — that is how a sign-off
    park created by the adapter mid-run learns it is a sign-off.
    """
    try:
        task = store.get(task_id)
        if task is None:
            return None
        if task.state == TaskState.WAITING:
            if waiting_kind is not None:
                await store.set_waiting_meta(
                    task_id,
                    waiting_kind=waiting_kind,
                    waiting_node_id=waiting_node_id,
                )
            return None
        if only_if_active and task.state not in (
            TaskState.ACTIVE, TaskState.BACKLOG
        ):
            return None
        await store.finalize_run(
            task_id,
            new_state=TaskState.WAITING,
            session_id=None,
            waiting_question=reason,
            history_entry=f"[{source}] {reason}",
            waiting_kind=waiting_kind,
            waiting_node_id=waiting_node_id,
        )
        return TaskState.WAITING
    except Exception as exc:
        log.error(
            "delivery_outcomes: failed to park %s to WAITING: %s", task_id, exc
        )
    return None
