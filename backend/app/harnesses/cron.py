"""
backend/app/harnesses/cron — Stateless cron-trigger loop for harnesses.

Design notes
------------
No back-fill of missed ticks across restart — only the current time is evaluated
each tick.  If the process was offline when a scheduled firing was due, that
firing is silently skipped.

Per-tick cost: O(n_spaces * n_harnesses).  Each tick reads the run index once
per harness (one disk read per harness) to check for an already-active run.
These reads are issued concurrently, bounded by an asyncio.Semaphore (default 16)
to prevent runaway I/O fan-out on spaces with many harnesses.

A debug log line is emitted per tick with the tick duration so regressions in
wall-clock cost are visible in logs without needing a profiler.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from dateutil import tz as dateutil_tz

from . import run_index
from .model import NodeType

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def should_fire(
    expression: str,
    timezone_name: str,
    prev_tick: datetime,
    now: datetime,
) -> bool:
    """Return True if the cron *expression* fires in the window (prev_tick, now].

    Uses ``croniter`` to find the first scheduled time strictly after *prev_tick*
    and returns True when that time is at or before *now*.  This means that if
    the poll interval is sub-minute, the same cron-minute cannot fire twice —
    once *prev_tick* moves past the scheduled second, the next fire from
    ``croniter`` is a full minute away.

    Parameters
    ----------
    expression:
        Standard 5-field cron expression (e.g. ``'0 * * * *'``).  Malformed
        expressions log a warning and return False without raising.
    timezone_name:
        IANA timezone name (e.g. ``'Europe/Prague'``).  Unresolvable names log
        a warning and fall back to UTC for evaluation.
    prev_tick:
        The timestamp of the previous tick (loop-local, not per-harness).
    now:
        The current wall-clock time for this tick.

    Returns
    -------
    bool
        True if the harness trigger should fire this tick, False otherwise.
    """
    # Resolve timezone; fall back to UTC if unknown.
    tzinfo = dateutil_tz.gettz(timezone_name)
    if tzinfo is None:
        log.warning(
            "cron: unknown timezone %r for expression %r — falling back to UTC",
            timezone_name,
            expression,
        )
        tzinfo = UTC

    # Convert prev_tick to the target timezone for croniter evaluation.
    prev_tick_tz = prev_tick.astimezone(tzinfo)

    try:
        from croniter import croniter  # local import avoids module-level dep at import time

        next_fire = croniter(expression, prev_tick_tz).get_next(datetime)
        # next_fire may be tz-naive depending on croniter version; ensure UTC-aware.
        if next_fire.tzinfo is None:
            next_fire = next_fire.replace(tzinfo=UTC)
        return next_fire <= now
    except Exception:
        log.warning(
            "cron: malformed expression %r (timezone=%r) — skipping",
            expression,
            timezone_name,
        )
        return False


async def has_active_run(space_dir: Path, harness_name: str) -> bool:
    """Return True if *harness_name* in *space_dir* has a run with status='running'.

    Reads the run index from disk on each call (no caching).  Returns False on
    any exception so a corrupted or missing index does not block firing.
    """
    try:
        summaries = await run_index.read_index(space_dir, harness_name)
        return any(s.status == "running" for s in summaries)
    except Exception:
        log.warning(
            "cron: could not read run index for harness %r in %s — assuming no active run",
            harness_name,
            space_dir,
        )
        return False


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def cron_loop(
    harness_store: object,
    space_store: object,
    spaces_dir: Path,
    interval_seconds: float,
    stop_event: asyncio.Event,
    *,
    task_store: object,
    worker_pool: object,
    now: Callable[[], datetime] | None = None,
) -> None:
    """Background loop that evaluates cron trigger nodes each tick.

    The loop fires harness runs by delegating to
    ``harnesses.run_trigger.enqueue_harness_run`` so the observable side-effects
    are identical to a manual HTTP-triggered run.

    Parameters
    ----------
    harness_store:
        ``HarnessStore`` instance; ``list(space_dir)`` is called each tick.
    space_store:
        ``SpaceStorage`` instance; ``list_all()`` is called each tick.
    spaces_dir:
        Filesystem root under which per-space directories live
        (``spaces_dir / space.id``).
    interval_seconds:
        Seconds to sleep between ticks.  Tests typically pass a sub-second value.
    stop_event:
        Awaiting this event (with a timeout) produces the inter-tick sleep;
        setting it causes the loop to exit cleanly after the current tick.
    task_store:
        Passed through to ``enqueue_harness_run``.
    worker_pool:
        Passed through to ``enqueue_harness_run``.
    now:
        Optional callable returning the current UTC datetime.  Defaults to
        ``lambda: datetime.now(UTC)`` so tests can inject a controlled clock.
    """
    if now is None:
        now = lambda: datetime.now(UTC)  # noqa: E731

    # Semaphore caps concurrent per-harness disk reads within a single tick.
    _sem = asyncio.Semaphore(16)

    prev_tick: datetime = now()
    log.debug("cron_loop started; prev_tick=%s interval=%ss", prev_tick, interval_seconds)

    try:
        while not stop_event.is_set():
            current_now = now()
            tick_start = current_now  # use same timestamp for duration calc

            try:
                await _process_tick(
                    harness_store=harness_store,
                    space_store=space_store,
                    spaces_dir=spaces_dir,
                    task_store=task_store,
                    worker_pool=worker_pool,
                    prev_tick=prev_tick,
                    current_now=current_now,
                    sem=_sem,
                )
            except Exception:
                log.exception("cron_loop: unhandled exception during tick — continuing")

            prev_tick = current_now

            # Compute elapsed using real wall-clock time for the debug log.
            elapsed = (datetime.now(UTC) - tick_start).total_seconds()
            log.debug("cron_loop tick completed in %.3fs", elapsed)

            # Sleep until next tick or until stop_event fires.
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                # stop_event fired — exit the loop.
                break
            except asyncio.TimeoutError:
                # Normal path: interval elapsed, go to next tick.
                pass

    except asyncio.CancelledError:
        log.debug("cron_loop cancelled — shutting down cleanly")
        raise

    log.debug("cron_loop stopped")


async def _process_tick(
    *,
    harness_store: object,
    space_store: object,
    spaces_dir: Path,
    task_store: object,
    worker_pool: object,
    prev_tick: datetime,
    current_now: datetime,
    sem: asyncio.Semaphore,
) -> None:
    """Evaluate all harness trigger nodes for every space in a single tick."""
    # Avoid circular import: run_trigger imports from harnesses subpackage,
    # which is fine, but we delay the import to keep module-level deps clean.
    from .run_trigger import enqueue_harness_run

    spaces = space_store.list_all()

    for space in spaces:
        space_dir = spaces_dir / space.id
        try:
            harnesses = await harness_store.list(space_dir)
        except Exception:
            log.exception(
                "cron_loop: failed to list harnesses for space %r — skipping", space.id
            )
            continue

        # Build one coroutine per harness and run them concurrently, bounded by sem.
        async def _eval_harness(harness: object) -> None:
            try:
                await _eval_harness_triggers(
                    harness=harness,
                    space_id=space.id,
                    space_dir=space_dir,
                    task_store=task_store,
                    harness_store=harness_store,
                    worker_pool=worker_pool,
                    prev_tick=prev_tick,
                    current_now=current_now,
                    sem=sem,
                    enqueue_harness_run=enqueue_harness_run,
                )
            except Exception:
                log.exception(
                    "cron_loop: unhandled exception evaluating harness %r in space %r",
                    getattr(harness, "name", "?"),
                    space.id,
                )

        await asyncio.gather(*(_eval_harness(h) for h in harnesses))


async def _eval_harness_triggers(
    *,
    harness: object,
    space_id: str,
    space_dir: Path,
    task_store: object,
    harness_store: object,
    worker_pool: object,
    prev_tick: datetime,
    current_now: datetime,
    sem: asyncio.Semaphore,
    enqueue_harness_run: object,
) -> None:
    """Check trigger nodes in *harness* and enqueue a run if the expression fires."""
    async with sem:
        trigger_nodes = [n for n in harness.nodes if n.type == NodeType.trigger]
        for node in trigger_nodes:
            expression = node.data.get("expression", "")
            timezone_name = node.data.get("timezone", "UTC")

            if not should_fire(expression, timezone_name, prev_tick, current_now):
                continue

            if await has_active_run(space_dir, harness.name):
                log.debug(
                    "cron: harness %r already has an active run — skipping trigger node %r",
                    harness.name,
                    node.id,
                )
                continue

            triggered_at = current_now.strftime("%Y-%m-%dT%H:%M:%SZ")
            brief = (
                f"Cron-triggered harness run for '{harness.name}'"
                f" (expr: {expression!r})"
            )
            try:
                await enqueue_harness_run(
                    task_store,
                    harness_store,
                    worker_pool,
                    space_id,
                    space_dir,
                    harness.name,
                    brief=brief,
                    triggered_at=triggered_at,
                )
                log.info(
                    "cron: triggered run for harness %r in space %r (expr=%r)",
                    harness.name,
                    space_id,
                    expression,
                )
            except Exception:
                log.exception(
                    "cron: failed to enqueue run for harness %r in space %r",
                    harness.name,
                    space_id,
                )
