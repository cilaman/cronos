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

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    except ValueError as exc:
        log.error("delivery_driver: compiler_a failed for %s: %s", goal_id, exc)
        await _park_goal_waiting(store, goal_id, f"Delivery spec compiler error: {exc}")
        return

    budget_meta = graph.metadata.get("budget", {})
    usd_ceiling = float(budget_meta.get("usd_ceiling", 0.0))

    run_dir.mkdir(parents=True, exist_ok=True)

    adapter = CronosAdapter(
        store=store,
        trace_store=trace_store,
        space_id=space_id,
        run_dir=run_dir,
        tracking_task_id=goal_id,
        usd_ceiling=usd_ceiling,
    )

    try:
        final_state = workflow_runner.run(graph=graph, executor=adapter)
    except Exception as exc:
        log.exception("delivery_driver: runner.run raised for goal %s", goal_id)
        await _park_goal_waiting(store, goal_id, f"Delivery runner error: {exc}")
        return

    log.info(
        "delivery_driver: goal %s finished with runner status=%s",
        goal_id, final_state.status,
    )

    if final_state.status in ("blocked", "escalated"):
        # The adapter's escalate() should have already parked the goal.
        # Log for diagnostics; do not double-park.
        log.info(
            "delivery_driver: goal %s is %s — adapter should have already parked it.",
            goal_id, final_state.status,
        )


async def _park_goal_waiting(store: "TaskStore", goal_id: str, reason: str) -> None:
    """Park *goal_id* to WAITING with *reason* as the waiting_question."""
    from .models import TaskState

    try:
        task = store.get(goal_id)
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
