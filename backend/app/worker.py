from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time as _time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import autopilot_pr  # kept for test patches: patch("app.worker.autopilot_pr...")
from .agent import AgentResult, CRONOS_SUBDIR, DATA_DIR, Status, run_agent
from .event_bus import DONE_SENTINEL, RUN_BUFFER_CAP, EventBus
from .finalizer import Finalizer
from .run_executor import RunExecutor
from .run_side_effects import RunSideEffects
from . import feature_sync  # kept for test patches: patch("app.worker.feature_sync...")
from . import goal_sync  # kept for test patches: patch("app.worker.goal_sync...")
from . import memory_retrieval
from .logging_config import bind_run_context
from .notifier import notify_state_change
from .memory_store import MemoryStore
from .feature_state import FeatureState
from .models import AiToolEntry, TaskState
from .space_storage import SpaceStore
from .stats import RunStats
from .stats_store import StatsStore
from .storage import InvalidTransition, TaskStore, USER_TRANSITIONS
from .trace_parser import RunTrace
from .trace_store import TraceStore

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .worker_pool import WorkerPool
    from .harnesses.store import HarnessStore

log = logging.getLogger("cronos.worker")

_CLAUDE_PROJECTS_DIR = Path(os.environ.get("CLAUDE_PROJECTS_DIR", "/root/.claude/projects"))

# Lease / heartbeat constants (env-overridable).
LEASE_TTL = float(os.environ.get("CRONOS_LEASE_TTL", "300"))
HEARTBEAT_INTERVAL = float(os.environ.get("CRONOS_HEARTBEAT_INTERVAL", "15"))

_MERGE_META_RE = re.compile(
    r"<!--\s*merge-meta\s*\n"
    r"space_id:\s*(?P<space_id>\S+)\s*\n"
    r"kind:\s*(?P<kind>\S+)\s*\n"
    r"name:\s*(?P<name>\S+)\s*\n"
    r"upstream_source_sha:\s*(?P<upstream_source_sha>\S+)\s*\n"
    r"-->",
    re.MULTILINE,
)


def _parse_merge_meta(brief: str) -> dict | None:
    """Extract merge metadata from a task brief. Returns None if not a merge task."""
    m = _MERGE_META_RE.search(brief)
    return m.groupdict() if m is not None else None


def _memory_injected_for_workspace(workspace: Path) -> list[str]:
    """Return sorted .md filenames from the Claude memory dir for a workspace."""
    project_key = str(workspace).replace("/", "-").replace(".", "-")
    memory_dir = _CLAUDE_PROJECTS_DIR / project_key / "memory"
    if not memory_dir.is_dir():
        return []
    return sorted(f.name for f in memory_dir.iterdir() if f.is_file() and f.suffix == ".md")


# Keep local aliases for backward-compatibility with any caller that references
# the module-level names. The canonical definitions live in event_bus.py.
_DONE_SENTINEL = DONE_SENTINEL
_RUN_BUFFER_CAP = RUN_BUFFER_CAP


# Backward-compat alias — canonical implementation lives in harnesses/adapter.py.
# Tests that import ``from app.worker import _WorkerProtocolAdapter`` continue to
# work; the class body is no longer duplicated here (R4 compliance).
from .harnesses.adapter import WorkerAdapter as _WorkerProtocolAdapter


def _topo_children(goal_id: str, store: TaskStore) -> list[str]:
    """Return direct child IDs of goal_id in dependency order (sibling deps only).

    Only depends_on links between siblings are considered for ordering; deps on
    external tasks are enforced by store.transition() when the child is activated.
    Falls back to manual_order sort if a cycle is detected among siblings.
    """
    children = {t.id: t for t in store.all() if t.parent_id == goal_id}
    if not children:
        return []

    dependents: dict[str, list[str]] = {cid: [] for cid in children}
    in_degree: dict[str, int] = {cid: 0 for cid in children}
    for cid, child in children.items():
        for dep_id in child.depends_on:
            if dep_id in children:
                dependents[dep_id].append(cid)
                in_degree[cid] += 1

    queue: deque[str] = deque(
        sorted(
            (cid for cid, deg in in_degree.items() if deg == 0),
            key=lambda cid: (children[cid].manual_order, cid),
        )
    )
    result: list[str] = []
    while queue:
        cid = queue.popleft()
        result.append(cid)
        for dep_cid in sorted(dependents[cid], key=lambda c: (children[c].manual_order, c)):
            in_degree[dep_cid] -= 1
            if in_degree[dep_cid] == 0:
                queue.append(dep_cid)

    if len(result) != len(children):
        log.warning("Cycle in goal %s children deps; falling back to manual order", goal_id)
        return sorted(children.keys(), key=lambda cid: (children[cid].manual_order, cid))

    return result


def resolve_tool(
    space_claude_dir: Path,
    global_claude_dir: Path,
    agent_ref: str,
) -> AiToolEntry | None:
    """Resolve an agent_ref to an AiToolEntry by scanning .claude directories.

    Scans space scope first (agents → skills → commands → context), then global
    scope in the same order. Returns the first name match, or None.
    """
    if not agent_ref:
        return None

    from app.tools.scanner import _scan_category, _scan_skills
    from app.api.tools import _scan_context  # lazy import to avoid circular dependency

    for claude_dir, scope in [(space_claude_dir, "space"), (global_claude_dir, "global")]:
        entries = (
            _scan_category(claude_dir, "agents", scope)
            + _scan_skills(claude_dir, scope)
            + _scan_category(claude_dir, "commands", scope, recursive=True)
            + _scan_context(claude_dir, scope)
        )
        for entry in entries:
            if entry.name == agent_ref:
                return entry

    return None


class Worker:
    """Single-agent serial worker.

    Tasks enqueued via `start(task_id)` are processed one at a time. While a
    task runs, the worker publishes claude's stream-json events plus its own
    lifecycle events (`run_start`, `run_end`) to any subscribers attached via
    `subscribe(task_id)`.

    Execution logic is delegated to collaborator modules:
    - RunExecutor  — task/goal/feature-decompose execution (exit reasons: DONE,
      STOPPED, CRASHED, NO_CRONOS_STATUS, WAIT, BLOCKED)
    - Finalizer    — post-run state machine
    - RunSideEffects — stats/trace/memory I/O
    - EventBus     — SSE pub/sub and harness run-id cache
    """

    def __init__(
        self,
        store: TaskStore,
        space_store: SpaceStore | None = None,
        stats_store: StatsStore | None = None,
        trace_store: TraceStore | None = None,
        memory_store: MemoryStore | None = None,
        on_idle: Callable[[Worker], Awaitable[None]] | None = None,
        pool: "WorkerPool | None" = None,
        harness_store: "HarnessStore | None" = None,
        *,
        on_task_state_change: Callable[[str, str, str, str], Awaitable[None]] | None = None,
    ) -> None:
        self.store = store
        self.space_store = space_store
        self.stats_store = stats_store
        self.trace_store = trace_store
        self.memory_store = memory_store
        self.harness_store = harness_store
        self.on_idle = on_idle
        self._on_task_state_change = on_task_state_change
        self._space_id: str | None = None
        self._pool = pool
        self._queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
        # EventBus owns all pub/sub state; Worker delegates to it.
        self._bus = EventBus()
        self._current_id: str | None = None
        # Set to the child task ID when _run_goal is executing a child.
        self._current_child_id: str | None = None
        self._current_cancel: asyncio.Event | None = None
        self._loop_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        # Track consecutive auto-resumes per task to prevent infinite loops.
        # Initialized as empty; loaded from DB below. Finalizer holds a reference
        # to this same dict so mutations (pop/update) are shared automatically.
        self._auto_resume_counts: dict[str, int] = {}
        self._rebuild_run_id_cache()
        # RunSideEffects handles stats/trace/memory recording after each run.
        self._side_effects = RunSideEffects(stats_store, trace_store, memory_store, store)
        # Finalizer handles post-run state machine for regular tasks and child tasks.
        # enqueue_fn is a lambda to avoid binding before the method is defined on the instance.
        self._finalizer = Finalizer(
            store=store,
            event_bus=self._bus,
            side_effects=self._side_effects,
            space_store=space_store,
            pool=pool,
            on_task_state_change=on_task_state_change,
            auto_resume_counts=self._auto_resume_counts,
            enqueue_fn=lambda task_id, user_message=None: self.enqueue(task_id, user_message),
            done_sentinel=_DONE_SENTINEL,
        )
        # RunExecutor handles task/goal/feature/harness execution.
        self._executor = RunExecutor(
            worker=self,
            store=store,
            event_bus=self._bus,
            finalizer=self._finalizer,
            space_store=space_store,
            harness_store=harness_store,
            memory_store=memory_store,
            done_sentinel=_DONE_SENTINEL,
            lease_ttl=LEASE_TTL,
            heartbeat_interval=HEARTBEAT_INTERVAL,
            memory_retrieval=memory_retrieval,
        )
        # Unique owner token for lease acquisition (per Worker instance / process).
        self._owner_id = str(uuid4())
        # Load durable auto-resume counts from SQLite on startup (update in-place).
        try:
            loaded = store.load_auto_resume_counts()
            self._auto_resume_counts.update(loaded)
        except Exception:
            log.exception("Failed to load auto_resume_counts from DB; starting fresh")

    # ---- run_id cache (delegates to EventBus) ----

    def _rebuild_run_id_cache(self) -> None:
        """Populate _bus._run_id_to_space_id by scanning known spaces' harness-run index files.

        Delegates to EventBus.rebuild_run_id_cache().
        """
        self._bus.rebuild_run_id_cache(DATA_DIR / "spaces", DATA_DIR)

    def register_run(self, run_id: str, space_id: str) -> None:
        """Register a new harness run in the reverse-lookup cache."""
        self._bus.register_run(run_id, space_id)

    def lookup_space_id(self, run_id: str) -> str | None:
        """Return the space_id for *run_id*, or None if not in the cache."""
        return self._bus.lookup_space_id(run_id)

    # ---- backward-compat shims for tests that access internal state directly ----
    # Tests that call Worker.__new__(Worker) then assign these attributes directly
    # need the setters to auto-create _bus if it doesn't exist yet.

    def _ensure_bus(self) -> "EventBus":
        """Return self._bus, creating a fresh EventBus if not yet initialised."""
        try:
            return object.__getattribute__(self, "_bus")
        except AttributeError:
            bus = EventBus()
            object.__setattr__(self, "_bus", bus)
            return bus

    def _ensure_executor(self) -> "RunExecutor":
        """Return self._executor, creating a minimal RunExecutor if not yet initialised.

        Needed when Worker is constructed via __new__ in tests (skipping __init__).
        """
        try:
            return object.__getattribute__(self, "_executor")
        except AttributeError:
            from . import memory_retrieval as _mr
            executor = RunExecutor(
                worker=self,
                store=getattr(self, "store", None),
                event_bus=self._ensure_bus(),
                finalizer=getattr(self, "_finalizer", None),
                space_store=getattr(self, "space_store", None),
                harness_store=getattr(self, "harness_store", None),
                memory_store=getattr(self, "memory_store", None),
                done_sentinel=_DONE_SENTINEL,
                lease_ttl=LEASE_TTL,
                heartbeat_interval=HEARTBEAT_INTERVAL,
                memory_retrieval=_mr,
            )
            object.__setattr__(self, "_executor", executor)
            return executor

    @property
    def _run_buffer(self) -> dict:
        """Backward-compat shim: expose EventBus's _run_buffer directly."""
        return self._ensure_bus()._run_buffer

    @_run_buffer.setter
    def _run_buffer(self, value: dict) -> None:
        self._ensure_bus()._run_buffer = value

    @property
    def _subscribers(self) -> dict:
        """Backward-compat shim: expose EventBus's _subscribers directly."""
        return self._ensure_bus()._subscribers

    @_subscribers.setter
    def _subscribers(self, value: dict) -> None:
        self._ensure_bus()._subscribers = value

    @property
    def _space_subscribers(self) -> list:
        """Backward-compat shim: expose EventBus's _space_subscribers directly."""
        return self._ensure_bus()._space_subscribers

    @_space_subscribers.setter
    def _space_subscribers(self, value: list) -> None:
        self._ensure_bus()._space_subscribers = value

    @property
    def _run_id_to_space_id(self) -> dict:
        """Backward-compat shim: expose EventBus's _run_id_to_space_id directly."""
        return self._ensure_bus()._run_id_to_space_id

    @_run_id_to_space_id.setter
    def _run_id_to_space_id(self, value: dict) -> None:
        self._ensure_bus()._run_id_to_space_id = value

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

        Delegates to EventBus.subscribe().
        """
        return self._bus.subscribe(task_id)

    def unsubscribe(self, task_id: str, q: asyncio.Queue[dict]) -> None:
        self._bus.unsubscribe(task_id, q)

    def subscribe_space(self) -> asyncio.Queue[dict]:
        """Subscribe to run_start/run_end events for any task in this space."""
        return self._bus.subscribe_space()

    def unsubscribe_space(self, q: asyncio.Queue[dict]) -> None:
        self._bus.unsubscribe_space(q)

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
                if (
                    self._queue.empty()
                    and self.on_idle is not None
                    and not self._stop.is_set()
                ):
                    try:
                        await self.on_idle(self)
                    except Exception:
                        log.exception("on_idle hook error for space %s", self._space_id)
        log.info("Worker loop stopped")

    async def _run_one(self, task_id: str, user_message: str | None) -> None:
        task = self.store.get(task_id)
        if task is None:
            log.warning("Skipping unknown task %s", task_id)
            return
        if task.type == "goal":
            await self._run_goal(task_id, user_message)
        elif task.type in ("feature", "fix") and task.feature_state == FeatureState.PROCESSING:
            await self._run_feature_decompose(task_id, user_message)
        else:
            await self._run_task(task_id, user_message)

    async def _run_feature_decompose(self, task_id: str, user_message: str | None = None) -> None:
        """Decompose a feature/fix task — delegates to RunExecutor.run_feature_decompose."""
        ex = self._ensure_executor()
        ex.space_store = self.space_store
        await ex.run_feature_decompose(task_id, user_message)

    async def __run_feature_decompose_inner(self, task_id: str, user_message: str | None, task) -> None:
        """Backward-compat shim — delegates to RunExecutor.run_feature_decompose_inner."""
        ex = self._ensure_executor()
        ex.space_store = self.space_store
        await ex.run_feature_decompose_inner(task_id, user_message, task)

    async def _execute_harness_run(
        self,
        task_id: str,
        harness_id: str,
        space_id: str,
        *,
        initial_run: bool,
    ) -> bool:
        """Execute (or resume) a harness run — delegates to RunExecutor.execute_harness_run."""
        ex = self._ensure_executor()
        ex.space_store = self.space_store
        ex.harness_store = self.harness_store
        return await ex.execute_harness_run(
            task_id, harness_id, space_id, initial_run=initial_run
        )

    async def __execute_harness_run_body(self, task_id: str, harness_id: str, space_id: str, *, initial_run: bool, space) -> bool:
        """Backward-compat shim — delegates to RunExecutor.execute_harness_run_body."""
        ex = self._ensure_executor()
        ex.space_store = self.space_store
        ex.harness_store = self.harness_store
        return await ex.execute_harness_run_body(
            task_id, harness_id, space_id, initial_run=initial_run, space=space
        )

    async def _resume_harness_run(self, task_id: str) -> bool:
        """Resume a WAITING harness run — delegates to RunExecutor.resume_harness_run."""
        ex = self._ensure_executor()
        ex.space_store = self.space_store
        ex.harness_store = self.harness_store
        return await ex.resume_harness_run(task_id)

    async def _run_initial_harness_run(self, task_id: str) -> bool:
        """Execute a freshly-triggered harness run — delegates to RunExecutor."""
        ex = self._ensure_executor()
        ex.space_store = self.space_store
        ex.harness_store = self.harness_store
        return await ex.run_initial_harness_run(task_id)

    async def _run_task(self, task_id: str, user_message: str | None) -> None:
        task = self.store.get(task_id)
        if task is None:
            log.warning("Skipping unknown task %s", task_id)
            return

        async with bind_run_context(run_id=task_id, task_id=task_id):
            await self.__run_task_body(task_id, user_message, task)

    async def __run_task_body(self, task_id: str, user_message: str | None, task) -> None:
        """Backward-compat shim — delegates to RunExecutor.run_task_body."""
        ex = self._ensure_executor()
        ex.space_store = self.space_store
        await ex.run_task_body(task_id, user_message, task)

    async def _finalize(
        self,
        task_id: str,
        result: AgentResult,
        *,
        started_at: datetime | None = None,
        memory_injected: list[str] | None = None,
    ) -> None:
        """Backward-compat shim — delegates to Finalizer.finalize.

        Synchronises space_store and pool from Worker to Finalizer so that
        test-time monkeypatches on worker.space_store are respected.

        Exit-reason values passed to Finalizer: DONE, STOPPED, CRASHED,
        NO_CRONOS_STATUS (no STATUS marker from agent), WAIT, BLOCKED.
        """
        self._finalizer.space_store = self.space_store
        self._finalizer.pool = self._pool
        await self._finalizer.finalize(
            task_id, result, started_at=started_at, memory_injected=memory_injected
        )

    async def _persist_cronos_remember_blocks(
        self,
        final_text: str,
        *,
        space_id: str,
        sources: list[str],
        log_id: str,
    ) -> None:
        """Backward-compat shim — delegates to RunSideEffects.save_cronos_remember_blocks."""
        await self._side_effects.save_cronos_remember_blocks(
            final_text,
            space_id=space_id,
            sources=sources,
            log_id=log_id,
        )

    async def _finalize_child(
        self,
        child_id: str,
        result: AgentResult | None,
        run_exception: str | None,
        *,
        started_at: datetime,
        memory_injected: list[str] | None = None,
    ) -> TaskState:
        """Backward-compat shim — delegates to Finalizer.finalize_child.

        Exit-reason values: DONE, STOPPED, CRASHED, NO_CRONOS_STATUS, WAIT, BLOCKED.
        """
        return await self._finalizer.finalize_child(
            child_id, result, run_exception,
            started_at=started_at, memory_injected=memory_injected,
        )

    async def _run_goal(self, goal_id: str, user_message: str | None) -> None:
        """Orchestrate a goal — delegates to RunExecutor.run_goal."""
        ex = self._ensure_executor()
        ex.space_store = self.space_store
        await ex.run_goal(goal_id, user_message)

    async def _publish(self, task_id: str, event: dict) -> None:
        """Publish *event* via the EventBus. Thin async wrapper for await callers."""
        self._bus.publish(task_id, event)


def _extract_subagent_types(events: list[dict]) -> list[str]:
    """Return ordered-unique lowercase subagent types from Agent tool calls in the event stream."""
    seen: list[str] = []
    seen_set: set[str] = set()
    for event in events:
        if event.get("type") != "assistant":
            continue
        msg = event.get("message")
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use" or block.get("name") != "Agent":
                continue
            inp = block.get("input")
            if not isinstance(inp, dict):
                continue
            subtype = inp.get("subagent_type")
            if isinstance(subtype, str) and subtype:
                key = subtype.lower()
                if key not in seen_set:
                    seen_set.add(key)
                    seen.append(key)
    return seen


async def sse_events(task_id: str, worker: Worker) -> AsyncIterator[str]:
    """Yields formatted SSE lines for a subscriber on `task_id`."""
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


async def sse_space_events(worker: Worker) -> AsyncIterator[str]:
    """Yields run_start/run_end SSE events for all tasks in a worker's space.

    Stays open indefinitely; the client disconnects when done.
    """
    q = worker.subscribe_space()
    try:
        yield ": ok\n\n"
        while True:
            event = await q.get()
            if event is _DONE_SENTINEL:
                return
            yield f"data: {json.dumps(event)}\n\n"
    finally:
        worker.unsubscribe_space(q)
