"""backend/app/delivery_driver.py — Cronos delivery-workflow driver.

The delivery driver is the integration point between the Cronos worker and the
portable delivery-workflow runner package.  When the worker detects a goal whose
brief contains the delivery-workflow sentinel, it calls ``run_delivery_goal``
instead of the normal ``_topo_children_local`` path.

Design decisions (from SG4 architecture):
  DD-DRV-01  This module is the only app.* file that imports from the runner package.
  DD-DRV-02  run_delivery_goal is an async def (called with await by RunExecutor).
  DD-DRV-03  Exceptions from the runner are caught; the goal is parked to WAITING.
  DD-DRV-04  CronosAdapter is constructed here; tracker task = goal_id.
  DD-DRV-05  Child task briefs are tagged with DELIVERY_NODE_SENTINEL (R8).

Sentinel constants (must be byte-identical in driver, worker, and tests):
  DELIVERY_WORKFLOW_SENTINEL  — found in goal brief, value is the spec path
  DELIVERY_NODE_SENTINEL      — appended to each child task brief
"""
from __future__ import annotations

import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from .storage import TaskStore

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# sys.path bootstrap — make the portable delivery-workflow package importable
# (adapters, runner, compiler_a, spec_loader, ir, lib, ...). The package lives
# outside the backend tree; its location differs between the repo checkout and
# the container image, so probe known candidates and add the first that exists.
# In the container PYTHONPATH also covers this (see backend/Dockerfile), but the
# probe keeps local dev / tests working without any env setup.
# ---------------------------------------------------------------------------
_here = Path(__file__).resolve()
for _cand in (
    _here.parents[2] / "packages" / "delivery-workflow",  # repo: backend/app/.. -> root
    Path("/app/packages/delivery-workflow"),              # container image layout
):
    _c = str(_cand)
    if _cand.is_dir() and _c not in sys.path:
        sys.path.insert(0, _c)

# ---------------------------------------------------------------------------
# Sentinel constants — must be byte-identical in delivery_driver.py, I7 worker
# routing, and all tests (design cross-iteration invariant).
# ---------------------------------------------------------------------------

#: Sentinel format embedded in the root goal brief by the user/spec.
#: Strict line-anchored regex (see _detect_delivery_workflow_spec).
DELIVERY_WORKFLOW_SENTINEL_PATTERN = re.compile(
    r"^<!--\s*delivery-workflow:\s*([^\s>]+)\s*-->$",
    re.MULTILINE,
)

#: Tag appended to each child task brief for board correlation (R8).
DELIVERY_NODE_SENTINEL = "<!-- delivery-node: {node_id} -->"


def detect_delivery_workflow_spec(brief: str) -> str | None:
    """Return the spec_path from the delivery-workflow sentinel in *brief*.

    Searches for a line matching ``<!-- delivery-workflow: {spec_path} -->``.
    Returns the spec_path (relative to space root) or None if absent.

    The regex is strict (line-anchored, no substring) to prevent false matches
    from HTML comments in ordinary goal briefs.
    """
    if not brief:
        return None
    m = DELIVERY_WORKFLOW_SENTINEL_PATTERN.search(brief)
    if m:
        return m.group(1).strip()
    return None


async def run_delivery_goal(
    goal_id: str,
    spec_path: str,
    store: "TaskStore",
    trace_store: Any,
    space_id: str,
    space_dir: Path,
    run_dir: Path,
    *,
    run_child: "Callable[..., Awaitable[Any]] | None" = None,
    cancel_event: "asyncio.Event | None" = None,
    goal_context: str = "",
    user_message: str | None = None,
    verdict: str | None = None,
) -> None:
    """Execute (or resume) a delivery-workflow goal via the portable runner.

    Parameters
    ----------
    goal_id:
        The Cronos task id of the root goal being executed.
    spec_path:
        Path to the delivery.workflow.yaml, resolved relative to space_dir.
    store:
        The Cronos TaskStore for child task creation and state queries.
    trace_store:
        The Cronos TraceStore for loading run traces after dispatch.
    space_id:
        Space identifier (passed to CronosAdapter).
    space_dir:
        Absolute path to the space root (for resolving spec_path).
    run_dir:
        Directory for run state persistence (state.json, events.jsonl).
    run_child:
        Coroutine ``run_child(goal_id, agent_ref, inputs, *, cancel_event,
        goal_context) -> RunTrace | None`` that creates and executes one delivery
        child task inline on the main event loop (``RunExecutor.run_delivery_child``).
        The synchronous runner runs in a worker thread and calls back into this
        coroutine via ``asyncio.run_coroutine_threadsafe``, dissolving the
        single-worker-per-space deadlock and streaming child output live.
    cancel_event:
        The goal's cancellation event; checked before each child dispatch.
    goal_context:
        The composed goal brief handed to each child agent as context.
    user_message:
        The reply text that re-activated a parked (WAITING) delivery goal, if
        any.  On a run parked ``blocked`` (human sign-off) it becomes the
        ``HumanAnswer`` text — landing in the sign-off node's ``fields.answer``
        (OD-2) and flowing into downstream briefs.
    verdict:
        Explicit sign-off verdict from the UI: ``'approve'`` or ``'reject'``.
        ``None`` with a non-empty message means **approve** (the documented
        backward-compatible default for plain replies); the text is preserved
        either way.  ``None`` with NO message (a backend restart, goal-sync
        propagation, or board drag re-activated the goal without anyone
        answering) is **no answer**: the sign-off stays pending and the goal
        re-parks WAITING (kind='signoff') — silence never becomes a yes (D10).

    Resume mapping (R7 — the driver holds NO resume heuristics; it translates
    the persisted run status + the user's action into exactly one package
    ``runner.resume()`` event and trusts the returned terminal):

    ==========  ========================================================
    persisted   package event
    ==========  ========================================================
    running     (fresh run / crash mid-run) plain ``runner.run()``
    blocked     ``HumanAnswer(node, text=user_message, verdict)`` — the
                parked sign-off node comes from the package query
                ``runner.blocked_human_nodes``; NO event when there is no
                reply text and no explicit verdict (the goal re-parks
                WAITING kind='signoff' — an automatic re-entry never
                approves, D10); a run blocked on a non-sign-off node (agent
                self-reported ``blocked``) parks WAITING with a diagnostic
                (no legal event exists yet)
    failed      ``RetryFailed('all')`` — the retry ceiling lives in
                package state (``resume_retries``), not a driver sidecar
    escalated   ``Nothing()`` first (completes served timed waits, re-
                enters iteration-cap halts); if the run re-derives
                ``escalated`` without progress, one ``RetryFailed('all')``
                (re-arms loop-exhausted nodes, again ceiling-bounded).
                Budget escalations are NOT auto-raised (conservative
                choice): the bounded RetryFailed path eventually parks
                the goal WAITING with the runner's reason and the user
                decides — ``RaiseBudget`` stays reserved for an explicit
                future control.
    stalled     stays parked (R6: a stalled run needs spec/state surgery)
                EXCEPT ``kind='rejected'``: a NEW user message re-arms the
                rejected sign-off via ``RetryFailed(stall.nodes)`` — the
                workflow re-parks on the sign-off and asks again
    ==========  ========================================================
    """
    from adapters.cronos.adapter import CronosAdapter
    import compiler_a
    import runner as workflow_runner
    from spec_loader import load_spec

    abs_spec_path = (space_dir / spec_path).resolve()
    log.info(
        "delivery_driver: running delivery goal %s with spec %s",
        goal_id, abs_spec_path,
    )

    try:
        spec = load_spec(abs_spec_path)
    except Exception as exc:
        log.error("delivery_driver: failed to load spec %s: %s", abs_spec_path, exc)
        await _park_goal_waiting(store, goal_id, f"Failed to load delivery spec: {exc}")
        return

    try:
        graph = compiler_a.compile(spec)
    except Exception as exc:
        # Catch *any* compiler failure (not just ValueError) so a malformed spec
        # never leaves the goal stuck ACTIVE with an empty conversation.
        log.exception("delivery_driver: compiler_a failed for %s", goal_id)
        await _park_goal_waiting(store, goal_id, f"Delivery spec compiler error: {exc}")
        return

    # Everything from here (setup, runner, finalization) is guarded so that ANY
    # unexpected exception parks the goal WAITING with a diagnostic instead of
    # bubbling out and leaving it ACTIVE forever.
    try:
        budget_meta = graph.metadata.get("budget", {})
        usd_ceiling = float(budget_meta.get("usd_ceiling", 0.0))

        run_dir.mkdir(parents=True, exist_ok=True)

        # Bridge the synchronous runner (which runs in a worker thread) back to
        # the main event loop so it can create and execute child agent-tasks inline.
        main_loop = asyncio.get_running_loop()

        def run_child_sync(agent_ref: str, inputs: dict) -> Any:
            """Called from the runner thread; runs one child on the main loop."""
            if run_child is None:
                return None
            if cancel_event is not None and cancel_event.is_set():
                return None
            fut = asyncio.run_coroutine_threadsafe(
                run_child(
                    goal_id,
                    agent_ref,
                    inputs,
                    cancel_event=cancel_event,
                    goal_context=goal_context,
                ),
                main_loop,
            )
            return fut.result()

        # Slug this goal's artifacts are keyed by (== slugify(goal.title), which
        # is also the goal_id minus its date-time prefix). Threaded into the
        # adapter (B2 fallback-scan scoping) and into each child brief (B4).
        from .storage import slugify

        _goal = store.get(goal_id)
        goal_slug = slugify(_goal.title) if _goal is not None else None

        adapter = CronosAdapter(
            store=store,
            trace_store=trace_store,
            space_id=space_id,
            run_dir=run_dir,
            tracking_task_id=goal_id,
            usd_ceiling=usd_ceiling,
            run_child=run_child_sync,
            main_loop=main_loop,
            space_dir=space_dir,
            goal_slug=goal_slug,
        )

        # Seed state.json before the run so the runner's resume path can read it
        # and skip already-`done` nodes instead of re-dispatching them (B1).
        # Idempotent: a resumed run leaves the existing state untouched.
        # bootstrap_if_absent is a CronosStateOps concern (not part of the StateOps
        # protocol); test/synthetic adapters manage their own state, so guard it.
        _bootstrap = getattr(adapter.state, "bootstrap_if_absent", None)
        if callable(_bootstrap):
            _bootstrap(
                spec=graph.metadata.get("name", ""),
                run_id=goal_id,
                usd_ceiling=usd_ceiling,
            )

        # R7: a persisted halted run is re-entered ONLY through the package
        # resume() API — the driver translates the persisted status + the
        # user's action into one typed event (see the resume-mapping table in
        # the docstring) and never touches WorkflowState.nodes itself.
        persisted = _read_persisted_state(adapter)
        persisted_status = getattr(persisted, "status", None)

        # Run the synchronous work-list walker / resume off the event loop so
        # its callbacks into run_coroutine_threadsafe don't deadlock the loop
        # they depend on.  Passing state_ops enables persistence + resume +
        # cancel-race detection.
        if persisted_status in _RESUMABLE_STATUSES:
            final_state, park_reason, park_kind, park_node_id = await asyncio.to_thread(
                _resume_persisted_run,
                graph, adapter, persisted, user_message, verdict, goal_id,
            )
            if final_state is None:
                await _park_goal_waiting(
                    store, goal_id, park_reason or "",
                    waiting_kind=park_kind, waiting_node_id=park_node_id,
                )
                return
        else:
            final_state = await asyncio.to_thread(
                workflow_runner.run,
                graph=graph,
                executor=adapter,
                state_ops=adapter.state,
            )
    except Exception as exc:
        log.exception("delivery_driver: runner setup/run raised for goal %s", goal_id)
        await _park_goal_waiting(store, goal_id, f"Delivery runner error: {exc}")
        return

    log.info(
        "delivery_driver: goal %s finished with runner status=%s",
        goal_id, final_state.status,
    )

    if final_state.status == "done":
        # R6: "done" now carries the runner's completeness proof — every node
        # either executed to a terminal status or excluded with proof — so the
        # driver trusts it outright.  The old post-hoc gate inspection
        # (_stalled_gate_ids) and its D12 false positive (a verdict-routed run
        # past a needs_fix gate decision parked WAITING at completion) are gone:
        # dead-ended runs no longer reach this branch, they arrive as "stalled".
        await _finalize_goal_done(store, goal_id)
    elif final_state.status == "stalled":
        # The runner proved the run incomplete (starved nodes, an exhausted
        # gate fix-loop, a rejected sign-off without a route, or an exhausted
        # resume-retry ceiling) and put the machine-readable detail at RUN
        # level (final_state.stall).  Render it into an actionable WAITING
        # message — the driver never digs through WorkflowState.nodes for this.
        await _park_goal_waiting(
            store, goal_id, _stall_reason(final_state), waiting_kind="stalled",
        )
    elif final_state.status == "failed":
        # A node failed and the runner halted — park for attention.  The next
        # user re-entry resumes via RetryFailed('all') (package-bounded).
        await _park_goal_waiting(
            store,
            goal_id,
            "Delivery workflow failed — a node returned status=failed. "
            "Reply to retry the failed node(s).",
            waiting_kind="node_failed",
        )
    elif final_state.status == "blocked":
        # Parked on a sign-off: the adapter's escalate() already parked the
        # goal WAITING with the node's question — stamp the structured wait
        # meta (§5.6) so the UI shows the Approve/Reject affordance, and park
        # defensively if the adapter could not.
        human_ids = _blocked_human_ids(graph, final_state)
        await _park_goal_waiting(
            store,
            goal_id,
            "Delivery workflow paused on a sign-off (runner status=blocked).",
            only_if_active=True,
            waiting_kind="signoff" if human_ids else None,
            waiting_node_id=human_ids[0] if human_ids else None,
        )
    else:
        # escalated / any other non-terminal status. The adapter's escalate()
        # normally parks the goal (e.g. a timed wait), but never leave it
        # ACTIVE: park it WAITING if it isn't already in a resting state.
        log.info(
            "delivery_driver: goal %s ended with runner status=%s", goal_id, final_state.status,
        )
        await _park_goal_waiting(
            store,
            goal_id,
            f"Delivery workflow paused (runner status={final_state.status}). "
            "Reply to resume.",
            only_if_active=True,
            waiting_kind="escalated",
        )


#: Persisted run statuses the driver re-enters via the package resume() API.
#: Everything else (fresh 'running', crash mid-run, or a completed 'done')
#: goes through plain runner.run().
_RESUMABLE_STATUSES = ("blocked", "failed", "escalated", "stalled")


def _read_persisted_state(adapter: Any) -> Any:
    """Best-effort read of the persisted WorkflowState via ``adapter.state``.

    Returns ``None`` when the adapter's state is absent or a test double whose
    ``read()`` does not yield a real WorkflowState — the caller then falls back
    to a plain ``runner.run()``.
    """
    state_ops = getattr(adapter, "state", None)
    if state_ops is None or not hasattr(state_ops, "read"):
        return None
    try:
        return state_ops.read()
    except Exception:
        return None


def _blocked_human_ids(graph: Any, state: Any) -> list[str]:
    """Package query for the sign-off node(s) a blocked run is parked on.

    Delegates to ``runner.blocked_human_nodes`` (the driver never reads
    ``WorkflowState.nodes`` itself); defensive against test doubles.
    """
    try:
        from runner import blocked_human_nodes

        return blocked_human_nodes(graph, state)
    except Exception:
        return []


def _resume_persisted_run(
    graph: Any,
    adapter: Any,
    persisted: Any,
    user_message: str | None,
    verdict: str | None,
    goal_id: str,
) -> "tuple[Any, str | None, str | None, str | None]":
    """Re-enter a persisted halted run through ``runner.resume()`` (R7).

    Translates the persisted run status + the user's action into exactly one
    package resume event (mapping documented on ``run_delivery_goal``) and
    returns ``(final_state, None, None, None)``.  When no legal event applies
    — or the package rejects the event — returns ``(None, park_reason,
    waiting_kind, waiting_node_id)`` and the caller parks the goal WAITING
    with the actionable reason and the structured §5.6 wait metadata
    (``'signoff'`` + node id for sign-off parks, ``'stalled'`` for stall
    re-derives), so re-parked goals keep their UI affordance.

    Runs synchronously in the runner worker thread (it may dispatch children).
    """
    import runner as workflow_runner
    from runner import HumanAnswer, Nothing, ResumeError, RetryFailed

    status = getattr(persisted, "status", None)
    text = (user_message or "").strip()

    def _resume(event: Any) -> Any:
        return workflow_runner.resume(graph, adapter, adapter.state, event)

    if status == "blocked":
        human_ids = _blocked_human_ids(graph, persisted)
        if not human_ids:
            return None, (
                "Delivery run is parked 'blocked' on a non-sign-off node (an "
                "agent reported itself blocked). No resume event applies — "
                "inspect the node's child task, fix the blocker, and start a "
                "fresh run (or adjust the workflow spec)."
            ), None, None
        if len(human_ids) > 1:
            log.warning(
                "delivery_driver: goal %s has %d blocked sign-off nodes %s — "
                "answering the first.", goal_id, len(human_ids), human_ids,
            )
        if not text and verdict not in ("approve", "reject"):
            # No answer was given: a message-less re-entry (backend restart,
            # goal-sync propagation, board drag) must NOT approve the pending
            # sign-off — silence never becomes a yes (D10).  Re-park with the
            # signoff metadata so the Approve/Reject affordance survives.
            log.info(
                "delivery_driver: goal %s re-entered blocked sign-off %r "
                "without an answer — re-parking WAITING.",
                goal_id, human_ids[0],
            )
            reason = (
                f"Delivery workflow is still waiting on sign-off "
                f"'{human_ids[0]}' — reply (or use Approve/Reject) to continue."
            )
            return None, reason, "signoff", human_ids[0]
        chosen_verdict = verdict if verdict in ("approve", "reject") else "approve"
        event = HumanAnswer(node_id=human_ids[0], text=text, verdict=chosen_verdict)
        log.info(
            "delivery_driver: goal %s resuming blocked sign-off %r "
            "(verdict=%s, answer=%d chars).",
            goal_id, human_ids[0], chosen_verdict, len(text),
        )
        try:
            return _resume(event), None, None, None
        except ResumeError as exc:
            return (
                None,
                f"Delivery sign-off resume rejected: {exc}",
                "signoff",
                human_ids[0],
            )

    if status == "failed":
        # Package-bounded: the per-node retry ceiling lives in state
        # (WorkflowState.resume_retries); exhaustion terminates 'stalled'
        # (kind=retry_exhausted) which the caller renders via _stall_reason.
        log.info("delivery_driver: goal %s resuming failed run (RetryFailed all).", goal_id)
        try:
            return _resume(RetryFailed("all")), None, None, None
        except ResumeError as exc:
            return None, f"Delivery run could not be resumed: {exc}", "node_failed", None

    if status == "escalated":
        # Nothing() is the external-mitigation re-entry: it completes served
        # timed waits and re-enters iteration-cap halts.  If the run re-derives
        # 'escalated' without progress, the halt is pinned to failed/escalated
        # node(s) (e.g. a loop-exhausted agent) — re-arm them once via
        # RetryFailed('all'); the package ceiling bounds repetition.
        log.info("delivery_driver: goal %s resuming escalated run (Nothing()).", goal_id)
        try:
            final = _resume(Nothing())
        except ResumeError as exc:
            return None, f"Delivery run could not be resumed: {exc}", "escalated", None
        if getattr(final, "status", None) == "escalated":
            log.info(
                "delivery_driver: goal %s re-derived 'escalated' — "
                "re-arming via RetryFailed('all').", goal_id,
            )
            try:
                final = _resume(RetryFailed("all"))
            except ResumeError:
                # Nothing retryable — keep the escalated terminal; the caller
                # parks the goal WAITING with the runner's status.
                pass
        return final, None, None, None

    # stalled — stays parked (R6: needs spec/state surgery), EXCEPT a rejected
    # sign-off: a NEW user message legitimately re-opens it by re-arming the
    # rejected (needs_fix) node — the workflow re-parks on the sign-off and
    # asks again, so the user can approve or reject-with-route this time.
    stall = getattr(persisted, "stall", None) or {}
    if stall.get("kind") == "rejected" and text:
        nodes = [str(n) for n in (stall.get("nodes") or [])]
        log.info(
            "delivery_driver: goal %s re-opening rejected sign-off %s.",
            goal_id, nodes,
        )
        try:
            return _resume(RetryFailed(nodes)), None, None, None
        except ResumeError as exc:
            return (
                None,
                f"Delivery sign-off could not be re-opened: {exc}",
                "stalled",
                None,
            )
    return None, _stall_reason(persisted), "stalled", None


def _stall_reason(final_state: Any) -> str:
    """Render the runner's RUN-LEVEL stall detail into an actionable WAITING
    reason (R6).

    Reads ONLY ``final_state.stall`` — the machine-readable record the runner
    writes with ``status="stalled"`` (``{"kind": "starved_nodes" |
    "gate_exhausted", "nodes": [...], "reason": str[, "dead_ends": [...]]}``).
    The driver never digs through ``WorkflowState.nodes`` to explain a stall;
    if the record is missing (defensive), a generic-but-honest message is
    produced.
    """
    stall = getattr(final_state, "stall", None)
    if not isinstance(stall, dict) or not stall:
        return (
            "Delivery workflow stalled — the run drained without completing "
            "all nodes (no stall detail available). Inspect the run state and "
            "re-run, or adjust the workflow edges."
        )
    kind = str(stall.get("kind") or "")
    nodes = ", ".join(str(n) for n in (stall.get("nodes") or [])) or "?"
    reason = str(stall.get("reason") or "")
    if kind == "gate_exhausted":
        msg = f"Delivery workflow stalled: gate {nodes} exhausted its fix-loop"
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
        msg = f"Delivery workflow stalled: node(s) {nodes} keep failing"
        tail = (
            " The resume retry ceiling was reached — fix the root cause (an "
            "agent exiting -9 was killed out of memory: lower "
            "CRONOS_MAX_CONCURRENT_AGENTS or raise the container "
            "mem_limit/swap) before starting a fresh run."
        )
    else:
        msg = (
            f"Delivery workflow stalled: node(s) {nodes} were never reached"
        )
        tail = (
            " Fix the upstream routing fields/conditions and re-run, or "
            "adjust the workflow edges."
        )
    if reason:
        msg += f" — {reason}."
    else:
        msg += "."
    return msg + tail


async def _finalize_goal_done(store: "TaskStore", goal_id: str) -> None:
    """Finalize *goal_id* to DONE after a successful runner completion."""
    from .models import TaskState

    try:
        task = store.get(goal_id)
        if task is not None and task.state not in (TaskState.DONE, TaskState.ARCHIVED):
            await store.finalize_run(
                goal_id,
                new_state=TaskState.DONE,
                session_id=None,
                waiting_question=None,
                history_entry="[delivery_driver] Delivery workflow completed successfully.",
            )
    except Exception as exc:
        log.error("delivery_driver: failed to finalize goal %s to DONE: %s", goal_id, exc)


async def _park_goal_waiting(
    store: "TaskStore",
    goal_id: str,
    reason: str,
    *,
    only_if_active: bool = False,
    waiting_kind: str | None = None,
    waiting_node_id: str | None = None,
) -> None:
    """Park *goal_id* to WAITING with *reason* as the waiting_question.

    When *only_if_active* is True, only park a goal that is still ACTIVE/BACKLOG —
    used as a safety net that must NOT clobber a goal already parked WAITING by the
    adapter's escalate() (e.g. a human-signoff node with its own question).

    ``waiting_kind``/``waiting_node_id`` carry the structured wait metadata
    (§5.6).  A goal that is ALREADY WAITING keeps its question but still gets
    the metadata stamped (via ``set_waiting_meta``) — that is how the sign-off
    park created by the adapter's escalate() mid-run learns it is a sign-off.
    """
    from .models import TaskState

    try:
        task = store.get(goal_id)
        if task is None:
            return
        if task.state == TaskState.WAITING:
            if waiting_kind is not None:
                await store.set_waiting_meta(
                    goal_id,
                    waiting_kind=waiting_kind,
                    waiting_node_id=waiting_node_id,
                )
            return
        if only_if_active and task.state not in (
            TaskState.ACTIVE, TaskState.BACKLOG
        ):
            return
        await store.finalize_run(
            goal_id,
            new_state=TaskState.WAITING,
            session_id=None,
            waiting_question=reason,
            history_entry=f"[delivery_driver] {reason}",
            waiting_kind=waiting_kind,
            waiting_node_id=waiting_node_id,
        )
    except Exception as exc:
        log.error("delivery_driver: failed to park goal %s to WAITING: %s", goal_id, exc)
