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
import json
import logging
import os
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

        # Resume past a human sign-off (blocked run).
        #
        # A human/wait node parks the run with state.status="blocked" and its own
        # node status="blocked" (CronosAdapter.escalate + runner dispatch), and the
        # goal is parked WAITING with the sign-off question.  Answering the question
        # is the *only* way a parked delivery goal returns to ACTIVE and re-enters
        # this function.  But the runner reads the persisted "blocked" status on its
        # first tick (cancel-race guard) and halts before dispatching anything, so
        # without this the run can never progress past the sign-off — it just
        # re-parks WAITING ("Please continue" loops forever).
        #
        # Treat re-entry on a blocked run as "human approved": mark the blocked
        # human/wait node(s) done and reset the run status to running so the runner
        # routes to their successors.
        _resume_from_blocked(adapter, graph, goal_id)

        # Bound re-dispatch of a persisted `failed` node.  A crash produces no
        # artifact fence → node status="failed" → runner halts → goal parked
        # WAITING; on the next re-activation the runner's resume seeding
        # re-dispatches the same failed node with no ceiling, so a persistent
        # failure (classically an OOM: exit -9) loops OOM→WAITING→resume→OOM.
        # Count re-dispatch attempts and, past the cap, park the goal WAITING
        # with a diagnostic and skip the runner entirely instead of looping.
        _failed_park = _resume_from_failed(adapter, goal_id, run_dir)
        if _failed_park is not None:
            await _park_goal_waiting(store, goal_id, _failed_park)
            return

        # Run the synchronous work-list walker off the event loop so its callbacks
        # into run_coroutine_threadsafe don't deadlock the loop they depend on.
        # Passing state_ops enables persistence + resume + cancel-race detection.
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
        # A "done" run is only a real success when it drained its work-list by
        # reaching terminal nodes — not when it dead-ended.  A gate whose only
        # outgoing edge requires ``decision == 'proceed'`` routes nowhere on a
        # ``needs_fix``/``fail`` decision; the runner then empties its work-list
        # and reports "done", which would silently mark the goal DONE even though
        # the gate blocked progress.  Detect that and park WAITING instead.
        stalled = _stalled_gate_ids(final_state)
        if stalled:
            await _park_goal_waiting(
                store,
                goal_id,
                "Delivery workflow stalled at gate(s) "
                f"{', '.join(stalled)} (decision != 'proceed'). Fix the upstream "
                "artifact and re-run, or adjust the gate routing.",
            )
        else:
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


def _resume_from_blocked(adapter: Any, graph: Any, goal_id: str) -> None:
    """Clear a persisted ``blocked`` run so it resumes past a human sign-off.

    Reads the persisted WorkflowState via ``adapter.state``.  When the run is
    ``blocked`` (parked on a human/wait node awaiting sign-off), mark the blocked
    human/wait node(s) ``done`` (the user answered → approved) and reset the run
    status to ``running`` so the runner's cancel-race guard does not halt on the
    first tick and instead routes to the approved node's successors.

    A no-op on a fresh run (status ``running``) or when the adapter's state is a
    test double whose ``read()`` does not yield a real WorkflowState.
    """
    state_ops = getattr(adapter, "state", None)
    if state_ops is None or not hasattr(state_ops, "read"):
        return
    try:
        persisted = state_ops.read()
    except Exception:
        return
    if getattr(persisted, "status", None) != "blocked":
        return

    # Only human / human-mode wait nodes legitimately park a run "blocked".
    human_ids = {
        n.id
        for n in getattr(graph, "nodes", [])
        if getattr(n, "kind", None) == "human"
        or (
            getattr(n, "kind", None) == "wait"
            and (getattr(n, "data", None) or {}).get("mode", "human") == "human"
        )
    }
    approved = {
        nid: {"status": "done"}
        for nid, ns in getattr(persisted, "nodes", {}).items()
        if getattr(ns, "status", None) == "blocked" and nid in human_ids
    }

    patch: dict[str, Any] = {"status": "running"}
    if approved:
        patch["nodes"] = approved
    try:
        state_ops.write(patch)
    except Exception:
        log.exception("delivery_driver: failed to clear blocked state for %s", goal_id)
        return
    log.info(
        "delivery_driver: goal %s resuming from blocked; approved human node(s)=%s",
        goal_id, sorted(approved) or "(none)",
    )


# Max times a persisted `failed` node may be re-dispatched across resumes before
# the driver stops looping and parks the goal WAITING for manual intervention.
_MAX_FAILED_RESUMES = 2


def _resume_from_failed(adapter: Any, goal_id: str, run_dir: Path) -> str | None:
    """Bound re-dispatch of a persisted ``failed`` node across resumes.

    The runner re-dispatches any non-``done`` node on resume with no attempt
    ceiling, so a node that keeps failing (classically an OOM: exit -9) loops
    OOM→WAITING→resume→OOM.  Since ``CronosStateOps.write`` does not persist node
    ``fields`` and the runner overwrites node ``attempt`` on each dispatch, the
    attempt count is kept in a sidecar file in ``run_dir``.

    Returns a park reason (the caller parks the goal WAITING and skips the runner)
    once a failed node exceeds ``_MAX_FAILED_RESUMES``; otherwise ``None`` (let the
    runner retry).  Best-effort and exception-tolerant — a bookkeeping error never
    blocks a run.
    """
    state_ops = getattr(adapter, "state", None)
    if state_ops is None or not hasattr(state_ops, "read"):
        return None
    try:
        persisted = state_ops.read()
    except Exception:
        return None
    if getattr(persisted, "status", None) != "failed":
        return None
    failed = [
        nid
        for nid, ns in getattr(persisted, "nodes", {}).items()
        if getattr(ns, "status", None) == "failed"
    ]
    if not failed:
        return None

    counter_path = Path(run_dir) / "failed_resumes.json"
    try:
        raw = json.loads(counter_path.read_text())
        prev = raw if isinstance(raw, dict) else {}
    except (FileNotFoundError, OSError, ValueError):
        prev = {}

    # Keep only currently-failed nodes (prune stale entries for nodes that have
    # since progressed) and increment their attempt count.
    counts = {nid: int(prev.get(nid, 0)) + 1 for nid in failed}
    exhausted = sorted(nid for nid, c in counts.items() if c > _MAX_FAILED_RESUMES)

    try:
        tmp = counter_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(counts))
        os.replace(tmp, counter_path)
    except OSError:
        log.warning(
            "delivery_driver: could not persist failed-resume counter for %s", goal_id
        )

    if exhausted:
        return (
            f"Delivery node(s) {', '.join(exhausted)} failed on "
            f"{_MAX_FAILED_RESUMES + 1} consecutive attempts — halting to avoid a "
            "crash loop. Fix the root cause (if the agent exited -9 it was killed "
            "out of memory: lower CRONOS_MAX_CONCURRENT_AGENTS or raise the "
            "container mem_limit/swap) before resuming."
        )
    log.info(
        "delivery_driver: goal %s retrying failed node(s) %s (attempts=%s)",
        goal_id, sorted(failed), counts,
    )
    return None


def _stalled_gate_ids(final_state: Any) -> list[str]:
    """Return gate node ids that ended on a non-'proceed' decision (dead-end).

    A gate whose only outgoing edge requires ``decision == 'proceed'`` routes
    nowhere when the decision is ``needs_fix``/``fail``; the runner then empties
    its work-list and reports ``status='done'``.  These ids let the driver park
    the goal WAITING with a diagnostic rather than marking it DONE.  Gates that
    proceeded (including loop-backs that eventually resolved to ``proceed``) are
    not flagged, so a genuinely-complete run reports no stall.
    """
    stalled: list[str] = []
    for nid, ns in getattr(final_state, "nodes", {}).items():
        gate = getattr(ns, "gate", None)
        if isinstance(gate, dict):
            decision = gate.get("decision")
            if decision is not None and decision != "proceed":
                stalled.append(nid)
    return stalled


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
