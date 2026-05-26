from __future__ import annotations

import asyncio
import logging

from .autopilot import pickup_next, start_picked
from .memory_store import MemoryStore
from .space_storage import SpaceStore
from .stats_store import StatsStore
from .storage import TaskStore
from .trace_store import TraceStore
from .worker import Worker

log = logging.getLogger("cronos.worker_pool")


class WorkerPool:
    """One `Worker` per space.

    Tasks in different spaces run concurrently; tasks within the same space
    stay serial (each space's worker has its own queue). Combined with the
    "no two spaces share a repo" invariant in `SpaceStore`, this guarantees
    no two concurrent processes ever touch the same git working tree.
    """

    def __init__(
        self,
        task_store: TaskStore,
        space_store: SpaceStore,
        stats_store: StatsStore | None = None,
        trace_store: TraceStore | None = None,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self._task_store = task_store
        self._space_store = space_store
        self._stats_store = stats_store
        self._trace_store = trace_store
        self._memory_store = memory_store
        self._workers: dict[str, Worker] = {}
        self._lock = asyncio.Lock()

    async def start_for_space(self, space_id: str) -> Worker:
        """Spin up a worker for `space_id` if one isn't already running.

        Idempotent: returns the existing worker if it's already started.
        """
        async with self._lock:
            existing = self._workers.get(space_id)
            if existing is not None:
                return existing

            space_store = self._space_store
            task_store = self._task_store

            async def _on_idle(worker: Worker) -> None:
                space = space_store.get(space_id)
                task = await pickup_next(space, task_store)
                if task is not None:
                    await start_picked(task, task_store, worker)

            worker = Worker(
                self._task_store,
                space_store=self._space_store,
                stats_store=self._stats_store,
                trace_store=self._trace_store,
                memory_store=self._memory_store,
                on_idle=_on_idle,
                pool=self,
            )
            worker._space_id = space_id
            worker.start()
            self._workers[space_id] = worker
            log.info("Started worker for space %s", space_id)
            return worker

    async def stop_for_space(self, space_id: str) -> None:
        """Cancel any current task and stop the worker for `space_id`.

        In-flight tasks are cancelled via the worker's existing
        `_current_cancel` event; queued tasks are dropped when the worker
        loop exits. No-op if no worker exists for this space.
        """
        async with self._lock:
            worker = self._workers.pop(space_id, None)
        if worker is None:
            return
        current = worker.current()
        if current is not None:
            worker.stop_current(current)
        await worker.stop()
        log.info("Stopped worker for space %s", space_id)

    async def enqueue(self, space_id: str, task_id: str) -> None:
        """Enqueue task_id on the worker for space_id. No-op if no worker exists."""
        worker = self._workers.get(space_id)
        if worker is None:
            log.warning("No worker for space %s, skipping enqueue of %s", space_id, task_id)
            return
        await worker.enqueue(task_id)

    def get(self, space_id: str) -> Worker | None:
        return self._workers.get(space_id)

    def get_for_task(self, task_id: str) -> Worker | None:
        """Resolve a task id to the worker for its space.

        Returns None if the task is unknown or its space has no worker.
        """
        task = self._task_store.get(task_id)
        if task is None:
            return None
        return self._workers.get(task.space_id)

    def all_workers(self) -> list[Worker]:
        return list(self._workers.values())

    def items(self) -> list[tuple[str, Worker]]:
        return list(self._workers.items())

    async def stop_all(self) -> None:
        async with self._lock:
            workers = list(self._workers.items())
            self._workers.clear()
        for space_id, worker in workers:
            current = worker.current()
            if current is not None:
                worker.stop_current(current)
            try:
                await worker.stop()
            except Exception:
                log.exception("Error stopping worker for space %s", space_id)
