from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from .agent import AgentResult, Status, run_agent
from .models import TaskState
from .space_storage import SpaceStore
from .storage import TaskStore

log = logging.getLogger("cronos.worker")

# Sentinel event signalling end-of-stream on a subscriber queue.
_DONE_SENTINEL: dict = {"type": "stream_end"}

# Per-task replay buffer cap. Covers a typical Claude turn; older events
# are dropped FIFO when exceeded.
_RUN_BUFFER_CAP = 2000


class Worker:
    """Single-agent serial worker.

    Tasks enqueued via `start(task_id)` are processed one at a time. While a
    task runs, the worker publishes claude's stream-json events plus its own
    lifecycle events (`run_start`, `run_end`) to any subscribers attached via
    `subscribe(task_id)`.
    """

    def __init__(self, store: TaskStore, space_store: SpaceStore | None = None) -> None:
        self.store = store
        self.space_store = space_store
        self._queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
        self._subscribers: dict[str, list[asyncio.Queue[dict]]] = defaultdict(list)
        # Snapshot of the current run's published events per task. Lets a
        # newly-connected SSE client replay what already happened so a
        # mid-run page refresh doesn't show an empty conversation.
        self._run_buffer: dict[str, list[dict]] = defaultdict(list)
        self._current_id: str | None = None
        self._current_cancel: asyncio.Event | None = None
        self._loop_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    # ---- public api ----

    async def enqueue(self, task_id: str, user_message: str | None = None) -> None:
        await self._queue.put((task_id, user_message))
        log.info("Enqueued task %s (queue size=%d)", task_id, self._queue.qsize())

    def current(self) -> str | None:
        return self._current_id

    def is_alive(self) -> bool:
        """True if the worker loop task is running (or pending start)."""
        return self._loop_task is not None and not self._loop_task.done()

    def stop_current(self, task_id: str) -> bool:
        """Request cancellation of the currently running task.

        Returns True if the cancel event was raised; False if the task is
        not the currently-active one (or nothing is running).
        """
        if self._current_id == task_id and self._current_cancel is not None:
            self._current_cancel.set()
            return True
        return False

    def subscribe(self, task_id: str) -> tuple[list[dict], asyncio.Queue[dict]]:
        """Subscribe to live events plus a snapshot of the current run.

        Returns `(replay, queue)`. `replay` is the list of events already
        published during the current run (drained immediately by the caller),
        `queue` receives all events from now on. Snapshot is taken before the
        queue is registered to avoid double-delivery races with `_publish`.
        """
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=256)
        replay = list(self._run_buffer.get(task_id, []))
        self._subscribers[task_id].append(q)
        return replay, q

    def unsubscribe(self, task_id: str, q: asyncio.Queue[dict]) -> None:
        if q in self._subscribers.get(task_id, []):
            self._subscribers[task_id].remove(q)
        if not self._subscribers.get(task_id):
            self._subscribers.pop(task_id, None)

    # ---- lifecycle ----

    def start(self) -> None:
        if self._loop_task is None:
            self._loop_task = asyncio.create_task(self._run_forever(), name="worker-loop")

    async def stop(self) -> None:
        self._stop.set()
        # Push a poison pill so the queue.get() unblocks.
        await self._queue.put(("__stop__", None))
        if self._loop_task is not None:
            try:
                await asyncio.wait_for(self._loop_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._loop_task.cancel()

    # ---- internals ----

    async def _run_forever(self) -> None:
        log.info("Worker loop started")
        while not self._stop.is_set():
            task_id, user_message = await self._queue.get()
            if task_id == "__stop__":
                break
            try:
                await self._run_one(task_id, user_message)
            except Exception:
                log.exception("Unhandled error processing task %s", task_id)
            finally:
                self._current_id = None
        log.info("Worker loop stopped")

    async def _run_one(self, task_id: str, user_message: str | None) -> None:
        task = self.store.get(task_id)
        if task is None:
            log.warning("Skipping unknown task %s", task_id)
            return

        self._current_id = task_id
        cancel_event = asyncio.Event()
        self._current_cancel = cancel_event
        self._run_buffer[task_id] = []
        await self._publish(task_id, {"type": "run_start", "task_id": task_id})

        async def on_event(event: dict) -> None:
            await self._publish(task_id, event)

        space = self.space_store.get(task.space_id) if self.space_store else None
        try:
            result = await run_agent(
                task,
                user_message=user_message,
                on_event=on_event,
                cancel_event=cancel_event,
                space=space,
            )
        except FileNotFoundError as e:
            await self._publish(
                task_id,
                {"type": "run_error", "error": f"claude binary not found: {e}"},
            )
            log.exception("Failed to spawn claude for %s", task_id)
            self._current_cancel = None
            return
        except Exception as e:
            await self._publish(task_id, {"type": "run_error", "error": str(e)})
            log.exception("Agent error on %s", task_id)
            self._current_cancel = None
            return

        self._current_cancel = None
        await self._finalize(task_id, result)

    async def _finalize(self, task_id: str, result: AgentResult) -> None:
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        prefix = f"```\n{timestamp} [agent]\n"
        body = result.final_text.strip() or "(no assistant text)"
        if result.stopped:
            body += "\n\n(stopped by user)"
        elif result.exit_code != 0:
            body += f"\n\n(exit code {result.exit_code}; stderr tail: {result.stderr_tail.strip()})"
        history_entry = prefix + body + "\n```"

        if result.stopped:
            new_state = TaskState.WAITING
            waiting_question = "Stopped by user."
        elif result.exit_code != 0 or result.status is None:
            # Crash or missing STATUS marker — keep the task in waiting so a
            # human notices it and can decide how to recover.
            new_state = TaskState.WAITING
            waiting_question = (
                "Agent did not finish cleanly (no STATUS marker)."
                if result.exit_code == 0
                else f"Agent crashed with exit code {result.exit_code}."
            )
        elif result.status == Status.DONE:
            new_state = TaskState.DONE
            waiting_question = None
        elif result.status == Status.WAIT:
            new_state = TaskState.WAITING
            waiting_question = result.context or "(agent asked to wait but gave no question)"
        elif result.status == Status.BLOCKED:
            new_state = TaskState.WAITING
            waiting_question = f"Blocked: {result.context or '(no reason)'}"
        else:
            new_state = TaskState.WAITING
            waiting_question = "Unknown STATUS marker."

        # Only persist the session id from a successful run. A crashed run
        # often emits a fresh session id that claude never actually stored on
        # disk — saving it would make every subsequent `--resume` fail with
        # "No conversation found with session ID …".
        session_id_to_persist = (
            result.session_id if result.exit_code == 0 and not result.stopped else None
        )
        try:
            await self.store.finalize_run(
                task_id,
                new_state=new_state,
                session_id=session_id_to_persist,
                waiting_question=waiting_question,
                history_entry=history_entry,
            )
        except Exception:
            log.exception("Failed to persist finalize for %s", task_id)

        await self._publish(
            task_id,
            {
                "type": "run_end",
                "task_id": task_id,
                "status": result.status.value if result.status else None,
                "new_state": new_state.value,
            },
        )
        # Tear down active subscribers so the SSE response returns.
        for q in list(self._subscribers.get(task_id, [])):
            try:
                q.put_nowait(_DONE_SENTINEL)
            except asyncio.QueueFull:
                pass

        # If messages were queued mid-run, flush them as a new turn.
        try:
            pending = await self.store.drain_pending(task_id)
        except Exception:
            log.exception("Failed to drain pending messages for %s", task_id)
            pending = []
        if pending and not result.stopped:
            combined = "\n\n".join(pending)
            try:
                # Force back to active even from DONE so the next turn runs.
                await self.store.resume_with_message(task_id)
            except Exception:
                log.exception("Failed to resume %s for pending messages", task_id)
                return
            await self.enqueue(task_id, user_message=combined)

    async def _publish(self, task_id: str, event: dict) -> None:
        buf = self._run_buffer.setdefault(task_id, [])
        buf.append(event)
        if len(buf) > _RUN_BUFFER_CAP:
            del buf[: len(buf) - _RUN_BUFFER_CAP]
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


async def sse_events(task_id: str, worker: Worker) -> AsyncIterator[str]:
    """Yields formatted SSE lines for a subscriber on `task_id`."""
    import json

    replay, q = worker.subscribe(task_id)
    try:
        # Flush headers + force EventSource.onopen to fire even when no
        # events are flowing yet (defeats proxy/gzip body buffering).
        yield ": ok\n\n"
        for event in replay:
            yield f"data: {json.dumps(event)}\n\n"
        # Keep the stream open until the run ends; if no run is active, the
        # subscriber will simply idle (no events). The client can disconnect.
        while True:
            event = await q.get()
            if event is _DONE_SENTINEL:
                yield "event: end\ndata: {}\n\n"
                return
            yield f"data: {json.dumps(event)}\n\n"
    finally:
        worker.unsubscribe(task_id, q)
