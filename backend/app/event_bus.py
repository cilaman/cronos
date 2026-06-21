"""backend/app/event_bus.py — Pub/sub event bus for SSE streaming.

Extracted from Worker to isolate all publish/subscribe state and operations.
Worker delegates to EventBus via self._bus = EventBus().
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

log = logging.getLogger("cronos.event_bus")

# Sentinel event signalling end-of-stream on a subscriber queue.
DONE_SENTINEL: dict = {"type": "stream_end"}

# Per-task replay buffer cap. Covers a typical Claude turn; older events
# are dropped FIFO when exceeded.
RUN_BUFFER_CAP = 2000


class EventBus:
    """Holds all pub/sub state for a single Worker instance.

    Provides synchronous ``publish`` (since the underlying operations are
    purely synchronous queue ops) plus subscribe/unsubscribe helpers.
    """

    def __init__(self) -> None:
        # Per-task-id subscriber queues.
        self._subscribers: dict[str, list[asyncio.Queue[dict]]] = defaultdict(list)
        # Per-task-id replay buffer (recent events for late-joining SSE clients).
        self._run_buffer: dict[str, list[dict]] = defaultdict(list)
        # Space-level subscribers (run_start/run_end for all tasks).
        self._space_subscribers: list[asyncio.Queue[dict]] = []
        # Reverse-lookup cache: run_id → space_id.
        self._run_id_to_space_id: dict[str, str] = {}

    # ---- publish ----

    def publish(self, task_id: str, event: dict) -> None:
        """Publish *event* to all subscribers for *task_id* and update the replay buffer.

        Synchronous — all operations are queue puts (no I/O, no awaits needed).
        Lifecycle events (run_start, run_end) are also forwarded to space subscribers.
        """
        buf = self._run_buffer.setdefault(task_id, [])
        buf.append(event)
        if len(buf) > RUN_BUFFER_CAP:
            del buf[: len(buf) - RUN_BUFFER_CAP]
        for q in list(self._subscribers.get(task_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow subscriber: drop oldest then push.
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass
        # Forward lifecycle events to space-level subscribers.
        if event.get("type") in ("run_start", "run_end"):
            for q in list(self._space_subscribers):
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        q.put_nowait(event)
                    except asyncio.QueueFull:
                        pass

    def clear_buffer(self, task_id: str) -> None:
        """Reset the replay buffer for *task_id* (called at the start of a new run)."""
        self._run_buffer[task_id] = []

    def drain_subscribers(self, task_id: str, sentinel: dict) -> None:
        """Send *sentinel* to all active subscribers for *task_id*.

        Used at run end to signal SSE clients that the stream is over.
        """
        for q in list(self._subscribers.get(task_id, [])):
            try:
                q.put_nowait(sentinel)
            except asyncio.QueueFull:
                pass

    # ---- subscribe ----

    def subscribe(self, task_id: str) -> tuple[list[dict], asyncio.Queue[dict]]:
        """Subscribe to live events and get a snapshot of the current run.

        Returns ``(replay, queue)``. ``replay`` is the list of events already
        published during the current run; ``queue`` receives future events.
        Snapshot is taken before the queue is registered to avoid double-delivery.
        """
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=256)
        replay = list(self._run_buffer.get(task_id, []))
        self._subscribers[task_id].append(q)
        return replay, q

    def unsubscribe(self, task_id: str, q: asyncio.Queue[dict]) -> None:
        """Remove *q* from the subscriber list for *task_id*."""
        if q in self._subscribers.get(task_id, []):
            self._subscribers[task_id].remove(q)
        if not self._subscribers.get(task_id):
            self._subscribers.pop(task_id, None)

    def subscribe_space(self) -> asyncio.Queue[dict]:
        """Subscribe to run_start/run_end events for all tasks in this space."""
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=256)
        self._space_subscribers.append(q)
        return q

    def unsubscribe_space(self, q: asyncio.Queue[dict]) -> None:
        """Remove *q* from the space-level subscriber list."""
        if q in self._space_subscribers:
            self._space_subscribers.remove(q)

    # ---- run_id cache ----

    def register_run(self, run_id: str, space_id: str) -> None:
        """Register a harness run in the reverse-lookup cache."""
        self._run_id_to_space_id[run_id] = space_id

    def lookup_space_id(self, run_id: str) -> str | None:
        """Return the space_id for *run_id*, or None if not in the cache."""
        return self._run_id_to_space_id.get(run_id)

    def rebuild_run_id_cache(self, spaces_root, data_dir) -> None:
        """Populate _run_id_to_space_id by scanning known spaces' harness-run index files.

        Called once at Worker construction time. Missing or malformed files are
        silently skipped.
        """
        import json as _json
        from pathlib import Path

        spaces_root_path = Path(spaces_root)
        if not spaces_root_path.is_dir():
            return
        for space_dir in spaces_root_path.iterdir():
            if not space_dir.is_dir():
                continue
            space_id = space_dir.name
            index_dir = space_dir / ".cronos" / "harness-runs"
            if not index_dir.is_dir():
                continue
            for index_file in index_dir.glob("*-index.json"):
                try:
                    with index_file.open("r", encoding="utf-8") as fh:
                        entries: list[dict] = _json.load(fh)
                    for entry in entries:
                        run_id = entry.get("run_id")
                        if run_id:
                            self._run_id_to_space_id[run_id] = space_id
                except Exception:
                    log.debug("rebuild_run_id_cache: skipping %s (read error)", index_file)
