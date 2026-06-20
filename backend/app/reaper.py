"""Lease reaper — periodically scans for expired/stale leases and re-enqueues tasks.

Architecture note: lease rows are disposable index-side coordination only. The reaper
always re-derives "is this still my work" from markdown (task_store.get().state == ACTIVE)
before acting, so a task moved to DONE/WAITING/archived between reaper passes is never
erroneously re-queued.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .storage import TaskStore
    from .worker_pool import WorkerPool

log = logging.getLogger("cronos.reaper")

# How often the reaper wakes up and scans expired leases.
REAPER_INTERVAL = float(os.environ.get("CRONOS_REAPER_INTERVAL", "30"))

# A lease is considered dead if its heartbeat_at is older than this many seconds.
# Default is 2 × HEARTBEAT_INTERVAL (worker default 15s → 30s timeout).
HEARTBEAT_TIMEOUT = float(os.environ.get("CRONOS_HEARTBEAT_TIMEOUT", "30"))


async def reaper_loop(
    task_store: "TaskStore",
    worker_pool: "WorkerPool",
    stop_event: asyncio.Event,
    *,
    reaper_interval: float = REAPER_INTERVAL,
    heartbeat_timeout: float = HEARTBEAT_TIMEOUT,
) -> None:
    """Background coroutine that detects and recovers from wedged/crashed workers.

    On each tick:
    1. Fetch all lease rows where lease_expiry < now OR heartbeat_at is stale.
    2. For each expired row:
       a. Check markdown state — only re-enqueue if state == ACTIVE.
       b. Delete the lease row BEFORE re-enqueuing (prevents double re-enqueue
          on back-to-back reaper passes while the task is still queued).
       c. Re-enqueue via worker_pool.enqueue(space_id, task_id).
    """
    from .models import TaskState

    log.info(
        "Reaper started (interval=%.0fs, heartbeat_timeout=%.0fs)",
        reaper_interval, heartbeat_timeout,
    )
    while True:
        # Scan first so that a stop_event set before the first tick still allows
        # recovery of any expired leases already present on startup.
        now = time.time()
        try:
            expired = task_store.get_expired_leases(now, heartbeat_timeout)
            if not isinstance(expired, list):
                expired = []
        except Exception:
            log.exception("Reaper: failed to query expired leases")
            expired = []

        for task_id, owner in expired:
            try:
                task = task_store.get(task_id)
                if task is None or task.state != TaskState.ACTIVE:
                    # Task no longer active per markdown — just clean up the stale row.
                    task_store.delete_expired_lease(task_id)
                    log.debug(
                        "Reaper: removed stale lease for %s (state=%s)",
                        task_id,
                        task.state.value if task is not None else "missing",
                    )
                    continue

                # Delete the lease BEFORE re-enqueuing to avoid double re-queue on
                # the next reaper pass while the task is still sitting in the queue.
                task_store.delete_expired_lease(task_id)
                log.info(
                    "Reaper: re-enqueuing task %s (space=%s, stale owner=%s)",
                    task_id, task.space_id, owner,
                )
                await worker_pool.enqueue(task.space_id, task_id)
            except Exception:
                log.exception("Reaper: error processing expired lease for task %s", task_id)

        # Wait for the next interval or a stop signal.
        # Check is_set() synchronously first to avoid a race with timeout=0.
        if stop_event.is_set():
            break
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=reaper_interval)
            break  # stop_event was set; exit cleanly
        except asyncio.TimeoutError:
            pass  # Normal tick — loop again.

    log.info("Reaper stopped")
