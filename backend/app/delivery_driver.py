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
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from .storage import TaskStore

log = logging.getLogger(__name__)

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
) -> None:
    """Execute a delivery-workflow goal via the portable runner.

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

        adapter = CronosAdapter(
            store=store,
            trace_store=trace_store,
            space_id=space_id,
            run_dir=run_dir,
            tracking_task_id=goal_id,
            usd_ceiling=usd_ceiling,
            run_child=run_child_sync,
            main_loop=main_loop,
        )

        # Run the synchronous work-list walker off the event loop so its callbacks
        # into run_coroutine_threadsafe don't deadlock the loop they depend on.
        final_state = await asyncio.to_thread(
            workflow_runner.run, graph=graph, executor=adapter
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
        # Runner reached a terminal node with no more work — mark the goal DONE.
        # (Without this the goal is left ACTIVE forever on a successful run.)
        await _finalize_goal_done(store, goal_id)
    elif final_state.status == "failed":
        # A node failed and the runner halted — park for attention.
        await _park_goal_waiting(
            store, goal_id, "Delivery workflow failed — a node returned status=failed."
        )
    else:
        # blocked / escalated / any other non-terminal status. The adapter's
        # escalate() normally parks the goal on a human/blocked node, but never
        # leave it ACTIVE: park it WAITING if it isn't already in a resting state.
        log.info(
            "delivery_driver: goal %s ended with runner status=%s", goal_id, final_state.status,
        )
        await _park_goal_waiting(
            store,
            goal_id,
            f"Delivery workflow paused (runner status={final_state.status}).",
            only_if_active=True,
        )


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
    store: "TaskStore", goal_id: str, reason: str, *, only_if_active: bool = False
) -> None:
    """Park *goal_id* to WAITING with *reason* as the waiting_question.

    When *only_if_active* is True, only park a goal that is still ACTIVE/BACKLOG —
    used as a safety net that must NOT clobber a goal already parked WAITING by the
    adapter's escalate() (e.g. a human-signoff node with its own question).
    """
    from .models import TaskState

    try:
        task = store.get(goal_id)
        if only_if_active and task is not None and task.state not in (
            TaskState.ACTIVE, TaskState.BACKLOG
        ):
            return
        if task is not None and task.state != TaskState.WAITING:
            await store.finalize_run(
                goal_id,
                new_state=TaskState.WAITING,
                session_id=None,
                waiting_question=reason,
                history_entry=f"[delivery_driver] {reason}",
            )
    except Exception as exc:
        log.error("delivery_driver: failed to park goal %s to WAITING: %s", goal_id, exc)
