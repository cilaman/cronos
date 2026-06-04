"""
backend/app/harnesses/triggers — EventBusEvent, EventDebouncer, and fan_out_to_harnesses.

This module is the central event-routing layer for harness trigger nodes.
It is called from three sites:

  1. ``worker.py`` (via an injected callback) — fires ``task-state-change`` events
     after a run transitions to DONE.
  2. ``api/harnesses.py`` — fires ``webhook`` events from an authenticated
     HTTP POST to ``/api/spaces/{space_id}/harnesses/{name}/webhook``.
  3. ``main.py::watch_spaces_dir()`` — fires ``file-change`` events when an
     awatch() notification arrives for a path in a Cronos space.

EventDebouncer in-memory state
-------------------------------
``EventDebouncer`` keeps an in-memory ``dict[str, float]`` keyed by event_id.
This state is **per-process**: if the backend restarts mid-debounce window,
the next occurrence of the same event_id will pass the ``should_fire()`` check
as if it had never fired.  Because default debounce windows are 0.5 s (and at
most a few seconds for file-change triggers), the post-restart duplicate-fire
window is negligible in practice.  Persistent cross-restart dedup is deferred
to a future arc.

Event-id construction convention
---------------------------------
Event IDs are constructed by the *caller* before building an ``EventBusEvent``;
the convention is::

    f"{kind}:{space_id}:{stable_key}"

where ``stable_key`` is:
  - ``task_id`` for ``task-state-change`` events,
  - ``webhook_path + ":" + content_hash`` for ``webhook`` events (so duplicate
    bodies within the debounce window are collapsed),
  - ``watch_pattern + ":" + file_path`` for ``file-change`` events.

``fan_out_to_harnesses()`` applies per-harness dedup using
``EventDebouncer.should_fire()`` on the event's ``event_id``; the
``debounce_seconds`` for each harness comes from its trigger node's
``data.get("debounce_seconds", 0.5)``.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from typing import Literal

from ..harnesses.run_trigger import enqueue_harness_run

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class EventBusEvent(BaseModel):
    """Immutable event envelope passed through the trigger fan-out pipeline.

    Fields
    ------
    event_id:
        Caller-constructed stable identifier for dedup; see module docstring
        for the construction convention.
    kind:
        One of the three supported trigger kinds.  Literal values use hyphens
        (``task-state-change``, ``webhook``, ``file-change``); do NOT use the
        underscore variants.
    space_id:
        The Cronos space identifier (e.g. ``"my-space"``).
    payload:
        Kind-specific detail dict.  For ``task-state-change``:
        ``{task_id, old_state, new_state}``; for ``webhook``: the raw request
        body; for ``file-change``: ``{path, watch_pattern}``.
    timestamp:
        ISO-8601 UTC string (e.g. ``"2026-01-01T00:00:00Z"``).
    """

    event_id: str
    kind: Literal["task-state-change", "webhook", "file-change"]
    space_id: str
    payload: dict = Field(default_factory=dict)
    timestamp: str


# ---------------------------------------------------------------------------
# Debouncer
# ---------------------------------------------------------------------------


class EventDebouncer:
    """In-memory per-event-id debounce guard.

    Uses ``time.monotonic()`` for sub-second precision.  The internal dict
    is lazily swept of expired entries on every ``should_fire()`` call
    (amortised O(n) over the lifetime of the process, negligible for typical
    harness counts ≤ 10 per space).

    Thread-safety: this class is **not** thread-safe.  It is designed for use
    from a single asyncio event loop; no locking is provided.
    """

    def __init__(self) -> None:
        # Maps event_id -> monotonic timestamp at which it was last accepted.
        self._last_fired: dict[str, float] = {}

    def should_fire(self, event_id: str, debounce_seconds: float) -> bool:
        """Return True if *event_id* should trigger a harness run now.

        The first call for a given ``event_id`` always returns True.
        Subsequent calls within ``debounce_seconds`` of the last accepted call
        return False (the event is suppressed / deduplicated).

        Also performs a lazy expiry sweep on each call, removing entries whose
        debounce window has elapsed, so the dict does not grow unboundedly.
        """
        now = time.monotonic()

        # Lazy expiry sweep — remove entries whose debounce window is well
        # past.  We use 2× the supplied debounce_seconds as the sweep
        # threshold; for simplicity we sweep all keys every call (dict is
        # small in practice).
        expired = [
            k for k, t in self._last_fired.items() if now - t > debounce_seconds * 2
        ]
        for k in expired:
            del self._last_fired[k]

        last = self._last_fired.get(event_id)
        if last is None or (now - last) >= debounce_seconds:
            self._last_fired[event_id] = now
            return True
        return False

    def reset(self, event_id: str) -> None:
        """Remove the debounce entry for *event_id*, if present.

        Exposed for testing.
        """
        self._last_fired.pop(event_id, None)


# ---------------------------------------------------------------------------
# Fan-out
# ---------------------------------------------------------------------------

# Module-level singleton debouncer shared across all fan-out calls.
# Per-harness dedup key is: f"{harness_name}:{event_id}"
_debouncer = EventDebouncer()


async def fan_out_to_harnesses(
    event: EventBusEvent,
    *,
    harness_store: object,
    task_store: object,
    worker_pool: object,
    space_dir: "Path",
) -> list[str]:
    """Route *event* to all harnesses that have a matching trigger node.

    For each harness in *harness_store* for the event's space, the function
    looks for a trigger node whose ``data["kind"] == event.kind``.  When found,
    it applies per-harness dedup via the module-level ``_debouncer`` (keyed by
    ``f"{harness_name}:{event.event_id}"``), using the node's
    ``data.get("debounce_seconds", 0.5)`` as the window.

    Matching harnesses that pass the dedup guard are launched via
    ``enqueue_harness_run()``.

    Parameters
    ----------
    event:
        The ``EventBusEvent`` to route.
    harness_store:
        A ``HarnessStore`` instance.  Typed as ``object`` to avoid a circular
        import at module level; runtime duck-typed via ``.list()``.
    task_store:
        A ``TaskStore`` instance.  Passed through to ``enqueue_harness_run()``.
    worker_pool:
        A ``WorkerPool`` instance.  Passed through to ``enqueue_harness_run()``.
    space_dir:
        Absolute ``Path`` to the space root.  Passed through to
        ``enqueue_harness_run()``.

    Returns
    -------
    list[str]
        The ``run_id`` strings for every harness run that was enqueued.
        Returns an empty list when no harness matched or all were deduplicated.
    """
    run_ids: list[str] = []

    try:
        harnesses = await harness_store.list(space_dir)
    except Exception:
        log.exception(
            "fan_out_to_harnesses: failed to list harnesses for space %s", event.space_id
        )
        return run_ids

    for harness in harnesses:
        # Find trigger nodes whose kind matches the event kind.
        trigger_nodes = [
            node
            for node in harness.nodes
            if node.type.value == "trigger"
            and node.data.get("kind") == event.kind
        ]
        if not trigger_nodes:
            continue

        # Use the first matching trigger node for debounce config.
        trigger_node = trigger_nodes[0]
        debounce_seconds: float = float(trigger_node.data.get("debounce_seconds", 0.5))

        # Per-harness dedup key combines harness name and event_id.
        dedup_key = f"{harness.name}:{event.event_id}"
        if not _debouncer.should_fire(dedup_key, debounce_seconds):
            log.debug(
                "fan_out_to_harnesses: deduplicated event %s for harness %s",
                event.event_id,
                harness.name,
            )
            continue

        # Build a brief for the harness run task.
        brief = (
            f"Triggered by event kind={event.kind!r} space={event.space_id!r} "
            f"event_id={event.event_id!r}\npayload: {event.payload}"
        )

        try:
            summary = await enqueue_harness_run(
                task_store=task_store,
                harness_store=harness_store,
                worker_pool=worker_pool,
                space_id=event.space_id,
                space_dir=space_dir,
                harness_name=harness.name,
                brief=brief,
                triggered_at=event.timestamp,
            )
            run_ids.append(summary.run_id)
            log.info(
                "fan_out_to_harnesses: enqueued run %s for harness %s (event %s)",
                summary.run_id,
                harness.name,
                event.event_id,
            )
        except Exception:
            log.exception(
                "fan_out_to_harnesses: failed to enqueue run for harness %s (event %s)",
                harness.name,
                event.event_id,
            )

    return run_ids
