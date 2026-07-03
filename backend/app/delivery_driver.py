"""backend/app/delivery_driver.py — Cronos delivery-workflow driver (R10d).

Detect the delivery sentinel → build the Cronos adapter (NodeExecutor +
HostPort) → drive the package ``DeliveryRun`` facade → translate the returned
``Outcome`` into ``TaskState`` via the shared table in
``app.delivery_outcomes`` — the SAME table the harness runner path uses, so
both hosts interpret every run terminal identically (01-state-model.md §5.6;
kills D16).

The driver holds NO resume heuristics and reads NO ``WorkflowState``
internals: a persisted halted run is re-entered ONLY through the package
resume() API — ``_resume_persisted_run`` translates the persisted run status
plus the user's action into exactly one typed event and trusts the returned
Outcome:

==========  ==========================================================
persisted   package event
==========  ==========================================================
running     (fresh run / crash mid-run) plain ``DeliveryRun.start()``
blocked     ``HumanAnswer(node, text=user_message, verdict)`` — the
            parked sign-off comes from ``runner.blocked_human_nodes``;
            NO event when there is no reply and no explicit verdict
            (silence never becomes a yes, D10 — the goal re-parks
            WAITING kind='signoff')
failed      ``RetryFailed('all')`` (ceiling lives in package state)
escalated   ``Nothing()`` first; if 'escalated' re-derives without
            progress, one ``RetryFailed('all')``.  Budget escalations
            are NOT auto-raised — ``RaiseBudget`` stays an explicit
            future control
stalled     stays parked (R6: needs spec/state surgery) EXCEPT
            kind='rejected' + a NEW message: ``RetryFailed(stall.nodes)``
            re-opens the rejected sign-off
==========  ==========================================================

Sentinel constants (byte-identical in driver, worker, and tests):
  DELIVERY_WORKFLOW_SENTINEL — in the goal brief, value is the spec path
  DELIVERY_NODE_SENTINEL     — appended to each child task brief (R8)
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from .delivery_outcomes import apply_outcome_to_task, park_task_waiting

if TYPE_CHECKING:
    from delivery_workflow.delivery_run import DeliveryRun as _DeliveryRun

    from .storage import TaskStore

log = logging.getLogger(__name__)

#: Sentinel in the root goal brief; strict line-anchored (no substring match).
DELIVERY_WORKFLOW_SENTINEL_PATTERN = re.compile(
    r"^<!--\s*delivery-workflow:\s*([^\s>]+)\s*-->$",
    re.MULTILINE,
)

#: Tag appended to each child task brief for board correlation (R8).
DELIVERY_NODE_SENTINEL = "<!-- delivery-node: {node_id} -->"

#: Persisted run statuses re-entered via the package resume() API; everything
#: else (fresh run, crash mid-'running', completed 'done') goes to start().
_RESUMABLE_STATUSES = ("blocked", "failed", "escalated", "stalled")

#: R10a legacy remap: goals created before the src-layout restructure carry a
#: sentinel pointing at the old canonical spec path (deleted by the git-mv).
#: When the old path no longer exists, resolve to the new canonical location
#: so parked pre-restructure delivery goals stay resumable after upgrade.
_LEGACY_SPEC_PATH_REMAP: dict[str, str] = {
    "packages/delivery-workflow/delivery.workflow.yaml": (
        "packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml"
    ),
}


def detect_delivery_workflow_spec(brief: str) -> str | None:
    """Return the spec_path from the delivery-workflow sentinel in *brief*."""
    if not brief:
        return None
    m = DELIVERY_WORKFLOW_SENTINEL_PATTERN.search(brief)
    return m.group(1).strip() if m else None


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
    """Execute (or resume) a delivery-workflow goal via the DeliveryRun facade.

    ``user_message``/``verdict`` carry the user action that re-activated a
    parked goal (verdict ``None`` + text = approve, the documented default;
    neither = no answer).  Any failure to even reach the runner parks the
    goal WAITING with a diagnostic — never leaves it ACTIVE.
    """
    from app.delivery_adapter import CronosAdapter
    from delivery_workflow import DeliveryRun, compiler_a
    from delivery_workflow.spec_loader import load_spec

    abs_spec_path = (space_dir / spec_path).resolve()
    if not abs_spec_path.exists():
        # Legacy remap (R10a): a pre-restructure sentinel names the old
        # canonical spec path; resolve to the relocated one when it exists so
        # in-flight parked goals survive the upgrade without brief surgery.
        _remapped = _LEGACY_SPEC_PATH_REMAP.get(spec_path.strip().lstrip("./"))
        if _remapped is not None and (space_dir / _remapped).exists():
            log.info(
                "delivery_driver: goal %s uses legacy spec path %r — "
                "remapped to %r (R10a restructure).",
                goal_id, spec_path, _remapped,
            )
            abs_spec_path = (space_dir / _remapped).resolve()
    log.info("delivery_driver: goal %s, spec %s", goal_id, abs_spec_path)
    try:
        graph = compiler_a.compile(load_spec(abs_spec_path))
    except Exception as exc:
        log.exception("delivery_driver: spec load/compile failed for %s", goal_id)
        await park_task_waiting(
            store, goal_id, f"Delivery spec load/compiler error: {exc}",
            source="delivery_driver",
        )
        return

    try:
        usd_ceiling = float(graph.metadata.get("budget", {}).get("usd_ceiling", 0.0))
        run_dir.mkdir(parents=True, exist_ok=True)
        # Bridge the synchronous runner (worker thread) back to the main loop
        # so it can create and execute child agent-tasks inline.
        main_loop = asyncio.get_running_loop()

        def run_child_sync(agent_ref: str, inputs: dict) -> Any:
            if run_child is None:
                return None
            if cancel_event is not None and cancel_event.is_set():
                return None
            fut = asyncio.run_coroutine_threadsafe(
                run_child(goal_id, agent_ref, inputs,
                          cancel_event=cancel_event, goal_context=goal_context),
                main_loop,
            )
            return fut.result()

        from .storage import slugify

        _goal = store.get(goal_id)
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
            goal_slug=slugify(_goal.title) if _goal is not None else None,
        )
        # The adapter implements BOTH ports: NodeExecutor (node work) and
        # HostPort (typed RunEvents park the goal mid-run with the question).
        run = DeliveryRun(
            graph, executor=adapter, state_ops=adapter.state,
            host=adapter, run_id=goal_id,
        )

        # R7: a persisted halted run re-enters ONLY through resume() — the
        # runner (and any resume dispatches) run off the event loop so their
        # run_coroutine_threadsafe callbacks don't deadlock the loop.
        persisted = _read_persisted_state(adapter)
        if getattr(persisted, "status", None) in _RESUMABLE_STATUSES:
            outcome, park_reason, park_kind, park_node = await asyncio.to_thread(
                _resume_persisted_run, run, persisted, user_message, verdict, goal_id,
            )
            if outcome is None:
                await park_task_waiting(
                    store, goal_id, park_reason or "",
                    waiting_kind=park_kind, waiting_node_id=park_node,
                    source="delivery_driver",
                )
                return
        else:
            outcome = await asyncio.to_thread(run.start)
    except Exception as exc:
        log.exception("delivery_driver: runner setup/run raised for goal %s", goal_id)
        await park_task_waiting(
            store, goal_id, f"Delivery runner error: {exc}", source="delivery_driver",
        )
        return

    # R11: real cancellation.  A user stop sets cancel_event mid-run; the
    # child dispatch returns None and the runner derives 'failed' — but that
    # work was deliberately aborted, not broken.  Persist 'cancelled' through
    # the facade so the run is sealed (start() halts, resume() raises
    # ResumeError) and the goal parks via the cancelled row instead of a
    # silently-retryable node_failed.
    if (
        cancel_event is not None
        and cancel_event.is_set()
        and outcome.kind not in ("done", "cancelled")
    ):
        log.info(
            "delivery_driver: goal %s was cancelled by the user (runner "
            "outcome was %r) — persisting run status 'cancelled'.",
            goal_id, outcome.kind,
        )
        try:
            outcome = await asyncio.to_thread(run.cancel)
        except Exception:
            log.exception(
                "delivery_driver: failed to persist cancellation for goal %s",
                goal_id,
            )

    log.info("delivery_driver: goal %s finished with outcome=%s", goal_id, outcome.kind)
    # R10d: the ONE shared Outcome → TaskState table (delivery + harness hosts).
    await apply_outcome_to_task(
        store, goal_id, outcome, subject="Delivery workflow", source="delivery_driver",
    )


def _read_persisted_state(adapter: Any) -> Any:
    """Best-effort read of the persisted WorkflowState via ``adapter.state``.

    ``None`` when state is absent (fresh run) or the adapter is a test double
    without a readable state — the caller then falls back to ``start()``.
    """
    state_ops = getattr(adapter, "state", None)
    if state_ops is None or not hasattr(state_ops, "read"):
        return None
    try:
        return state_ops.read()
    except Exception:
        return None


def _blocked_human_ids(graph: Any, state: Any) -> list[str]:
    """Package query for the sign-off node(s) a blocked run is parked on."""
    try:
        from delivery_workflow.runner import blocked_human_nodes

        return blocked_human_nodes(graph, state)
    except Exception:
        return []


def _resume_persisted_run(
    run: "_DeliveryRun",
    persisted: Any,
    user_message: str | None,
    verdict: str | None,
    goal_id: str,
) -> "tuple[Any, str | None, str | None, str | None]":
    """Re-enter a persisted halted run through the facade's resume() (R7).

    Translates the persisted run status + the user's action into exactly one
    package resume event (table in the module docstring) and returns
    ``(outcome, None, None, None)``.  When no legal event applies — or the
    package rejects it — returns ``(None, park_reason, waiting_kind,
    waiting_node_id)`` so the caller re-parks with the §5.6 metadata intact.

    Runs synchronously in the runner worker thread (it may dispatch children).
    """
    from delivery_workflow.runner import HumanAnswer, Nothing, ResumeError, RetryFailed

    status = getattr(persisted, "status", None)
    text = (user_message or "").strip()

    if status == "blocked":
        human_ids = _blocked_human_ids(run.graph, persisted)
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
            # No answer (restart, goal-sync, board drag): silence never
            # becomes a yes (D10) — re-park with the sign-off metadata.
            return None, (
                f"Delivery workflow is still waiting on sign-off "
                f"'{human_ids[0]}' — reply (or use Approve/Reject) to continue."
            ), "signoff", human_ids[0]
        chosen = verdict if verdict in ("approve", "reject") else "approve"
        log.info(
            "delivery_driver: goal %s resuming sign-off %r (verdict=%s).",
            goal_id, human_ids[0], chosen,
        )
        try:
            event = HumanAnswer(node_id=human_ids[0], text=text, verdict=chosen)
            return run.resume(event), None, None, None
        except ResumeError as exc:
            return (None, f"Delivery sign-off resume rejected: {exc}",
                    "signoff", human_ids[0])

    if status == "failed":
        log.info("delivery_driver: goal %s resuming failed run (RetryFailed all).", goal_id)
        try:
            return run.resume(RetryFailed("all")), None, None, None
        except ResumeError as exc:
            return None, f"Delivery run could not be resumed: {exc}", "node_failed", None

    if status == "escalated":
        # Nothing() completes served timed waits / re-enters cap halts; a
        # re-derived 'escalated' without progress is re-armed once via
        # RetryFailed('all') (package ceiling bounds repetition).
        log.info("delivery_driver: goal %s resuming escalated run (Nothing()).", goal_id)
        try:
            outcome = run.resume(Nothing())
        except ResumeError as exc:
            return None, f"Delivery run could not be resumed: {exc}", "escalated", None
        if outcome.kind == "escalated":
            try:
                outcome = run.resume(RetryFailed("all"))
            except ResumeError:
                pass  # nothing retryable — keep the escalated terminal
        return outcome, None, None, None

    # stalled — stays parked (R6) EXCEPT a rejected sign-off re-opened by a
    # NEW user message: RetryFailed(stall.nodes) re-arms it and asks again.
    stall = getattr(persisted, "stall", None) or {}
    if stall.get("kind") == "rejected" and text:
        nodes = [str(n) for n in (stall.get("nodes") or [])]
        log.info("delivery_driver: goal %s re-opening rejected sign-off %s.", goal_id, nodes)
        try:
            return run.resume(RetryFailed(nodes)), None, None, None
        except ResumeError as exc:
            return (None, f"Delivery sign-off could not be re-opened: {exc}",
                    "stalled", None)
    from .delivery_outcomes import render_stall_message

    return None, render_stall_message(stall or None), "stalled", None
