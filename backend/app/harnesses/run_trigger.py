"""
backend/app/harnesses/run_trigger — shared harness-run enqueueing helper.

Provides a single coroutine, `enqueue_harness_run`, that extracts the
task-create + run-index-append + worker-register + worker-enqueue logic that
was previously inlined in `api/harnesses.py`'s `trigger_harness_run` endpoint.

Both the HTTP endpoint (api/harnesses.py) and the scheduled cron loop
(harnesses/cron.py) call this helper with the same signature so that the
observable side-effects are identical regardless of how a run was triggered.

Circular-import avoidance
--------------------------
The `harness_store` parameter is accepted in the signature but the caller is
responsible for validating that the harness exists *before* calling this
function.  The helper itself does NOT call `harness_store.get()` — keeping
HarnessStore out of the hot-path and avoiding a cron-on-the-import-graph
dependency from api/harnesses.py.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..harnesses import run_index
from ..harnesses.run_index import RunSummary
from ..models import TaskState
from ..storage import TaskStore, USER_TRANSITIONS

log = logging.getLogger(__name__)


async def enqueue_harness_run(
    task_store: TaskStore,
    harness_store: object,
    worker_pool: object,
    space_id: str,
    space_dir: Path,
    harness_name: str,
    *,
    brief: str,
    triggered_at: str,
) -> RunSummary:
    """Create a harness run task, record it in the run index, and enqueue it.

    Parameters
    ----------
    task_store:
        The space's TaskStore instance (used to create and transition the task).
    harness_store:
        Accepted for signature symmetry with cron.py callers; not used inside
        this helper.  The caller is responsible for verifying the harness exists.
    worker_pool:
        A WorkerPool instance whose ``get(space_id)`` method returns the Worker
        for the space (or None if no worker is running for that space).
    space_id:
        The Cronos space identifier string.
    space_dir:
        Absolute filesystem path of the space root (used to locate the run index
        at ``{space_dir}/.cronos/harness-runs/``).
    harness_name:
        Name of the harness being triggered.
    brief:
        Agent brief text to attach to the created task.
    triggered_at:
        ISO-8601 UTC timestamp string (e.g. ``"2026-01-01T00:00:00Z"``) recording
        when this run was requested.

    Returns
    -------
    RunSummary
        The summary appended to the run index, with ``status="running"``.
    """
    # Create the harness run task. run_id == task.id per design constraint.
    task = await task_store.create(
        space_id=space_id,
        title=f"Harness run: {harness_name}",
        brief=brief,
        type="task",
    )
    run_id = task.id

    # Append to the run index.
    summary = RunSummary(
        run_id=run_id,
        harness_id=harness_name,
        status="running",
        triggered_at=triggered_at,
    )
    await run_index.append_run(space_dir, harness_name, summary)

    # Register in the worker reverse-lookup cache (O(1) for GET /harness-runs/{run_id}).
    worker = worker_pool.get(space_id)
    if worker is not None:
        worker.register_run(run_id, space_id)

    # Transition task to ACTIVE and enqueue on the worker.
    try:
        await task_store.transition(run_id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    except Exception:
        log.warning("Could not transition harness run task %s to ACTIVE", run_id)

    if worker is not None:
        await worker.enqueue(run_id)

    return summary
