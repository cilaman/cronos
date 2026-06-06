from __future__ import annotations

import asyncio
import logging
import os
import re
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from . import autopilot_pr
from .agent import AgentResult, CRONOS_SUBDIR, DATA_DIR, Status, run_agent
from . import feature_sync
from . import goal_sync
from . import memory_retrieval
from .memory_parser import parse_memory_blocks
from .memory_store import MemoryStore
from .feature_state import FeatureState
from .models import AiToolEntry, TaskState
from .space_storage import SpaceStore
from .stats import (
    AdoptedToolRunStats,
    RunStats,
    _tier_from_real_model,
    compute_adopted_tool_uses,
    compute_cost,
    extract_tokens_and_tools,
)
from .stats_store import StatsStore
from .storage import InvalidTransition, TaskStore, USER_TRANSITIONS
from .trace_parser import RunTrace, extract_run_trace
from .trace_store import TraceStore

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .worker_pool import WorkerPool
    from .harnesses.store import HarnessStore

log = logging.getLogger("cronos.worker")

_CLAUDE_PROJECTS_DIR = Path(os.environ.get("CLAUDE_PROJECTS_DIR", "/root/.claude/projects"))

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


# Sentinel event signalling end-of-stream on a subscriber queue.
_DONE_SENTINEL: dict = {"type": "stream_end"}

# Per-task replay buffer cap. Covers a typical Claude turn; older events
# are dropped FIFO when exceeded.
_RUN_BUFFER_CAP = 2000


class _WorkerProtocolAdapter:
    """Adapts Worker to satisfy harnesses.executor.WorkerProtocol.

    The HarnessExecutor requires a WorkerProtocol object with ``run_agent``
    and ``finalize_child`` methods.  This adapter bridges to the real Worker
    without causing a circular-import.  It is used only during harness
    resume (_resume_harness_run).
    """

    def __init__(self, worker: "Worker") -> None:
        self._worker = worker

    async def run_agent(self, task_id: str, **kwargs) -> RunTrace:
        """Run the agent for a harness child task and return a RunTrace.

        Delegates to ``run_agent()`` from agent.py directly so the Worker
        does not need to expose a public run_agent method for protocol use.
        """
        task = self._worker.store.get(task_id)
        if task is None:
            raise RuntimeError(f"Child task {task_id!r} not found in store")
        space = (
            self._worker.space_store.get(task.space_id)
            if self._worker.space_store
            else None
        )
        result: AgentResult = await run_agent(task, user_message=None, space=space)
        # Convert AgentResult to a minimal RunTrace for the executor.
        from datetime import UTC, datetime as _dt
        now = _dt.now(tz=UTC)
        return RunTrace(
            task_id=task_id,
            space_id=task.space_id,
            run_index=0,
            session_id=result.session_id,
            model=task.agent_model,
            mode=task.agent_mode,
            started_at=now,
            ended_at=now,
            duration_seconds=0.0,
            exit_reason=result.status.value if result.status else "NO_STATUS",
            final_text_snippet=(result.final_text or "")[:500],
            parent_run_id=kwargs.get("parent_run_id"),
        )

    async def finalize_child(self, task_id: str, trace: RunTrace) -> TaskState:
        """Finalize a harness child task and return its new TaskState.

        Uses the trace's exit_reason to determine success (DONE) vs failure.
        """
        from datetime import UTC, datetime as _dt
        ts = _dt.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        if trace.exit_reason == "DONE":
            new_state = TaskState.DONE
            waiting_question = None
            history_entry = f"```\n{ts} [agent]\n{trace.final_text_snippet or '(done)'}\n```"
        else:
            new_state = TaskState.WAITING
            waiting_question = f"Agent ended with exit_reason={trace.exit_reason!r}"
            history_entry = (
                f"```\n{ts} [agent]\n"
                f"exit_reason={trace.exit_reason!r}\n{trace.final_text_snippet or ''}\n```"
            )

        try:
            await self._worker.store.finalize_run(
                task_id,
                new_state=new_state,
                session_id=trace.session_id,
                waiting_question=waiting_question,
                history_entry=history_entry,
            )
        except Exception:
            log.exception("_WorkerProtocolAdapter.finalize_child failed for %s", task_id)

        return new_state

    def _publish(self, task_id: str, event: dict) -> None:
        """Sync bridge to Worker._run_buffer (WorkerProtocol._publish is sync).

        Worker._publish is async def but its body is purely synchronous.
        This adapter replicates those operations so harness events reach
        _run_buffer and SSE subscribers without an unawaited coroutine.
        """
        worker = self._worker
        buf = worker._run_buffer.setdefault(task_id, [])
        buf.append(event)
        if len(buf) > _RUN_BUFFER_CAP:
            del buf[: len(buf) - _RUN_BUFFER_CAP]
        for q in list(worker._subscribers.get(task_id, [])):
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
        self._subscribers: dict[str, list[asyncio.Queue[dict]]] = defaultdict(list)
        # Snapshot of the current run's published events per task. Lets a
        # newly-connected SSE client replay what already happened so a
        # mid-run page refresh doesn't show an empty conversation.
        self._run_buffer: dict[str, list[dict]] = defaultdict(list)
        self._current_id: str | None = None
        # Set to the child task ID when _run_goal is executing a child.
        self._current_child_id: str | None = None
        self._current_cancel: asyncio.Event | None = None
        self._loop_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        # Track consecutive auto-resumes per task to prevent infinite loops.
        self._auto_resume_counts: dict[str, int] = {}
        # Space-level subscribers receive run_start/run_end for all tasks in
        # this worker's space (used by the space SSE stream).
        self._space_subscribers: list[asyncio.Queue[dict]] = []
        # Reverse-lookup cache: run_id → space_id.  Populated at startup by
        # _rebuild_run_id_cache() and kept current via register_run().  Used by
        # the /api/harness-runs/{run_id} endpoints (I5/I6) to resolve the space
        # without scanning every space's harness-runs index files per request.
        self._run_id_to_space_id: dict[str, str] = {}
        self._rebuild_run_id_cache()

    # ---- run_id cache ----

    def _rebuild_run_id_cache(self) -> None:
        """Populate _run_id_to_space_id by scanning known spaces' harness-run index files.

        Called once at Worker construction time.  Safe to call again to refresh.
        Each space stores per-harness index files at::

            {DATA_DIR}/spaces/{space_id}/.cronos/harness-runs/{harness_id}-index.json

        The index files are JSON arrays of RunSummary objects, each with a ``run_id``
        field.  This method scans all ``*-index.json`` files under every space directory
        to pre-populate the reverse-lookup cache used by GET /api/harness-runs/{run_id}.
        Missing or malformed files are silently skipped.
        """
        spaces_root = DATA_DIR / "spaces"
        if not spaces_root.is_dir():
            return
        import json as _json
        for space_dir in spaces_root.iterdir():
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
                    log.debug("_rebuild_run_id_cache: skipping %s (read error)", index_file)

    def register_run(self, run_id: str, space_id: str) -> None:
        """Register a new harness run in the reverse-lookup cache.

        Called by the POST /run API endpoint (I5) immediately after creating the
        index entry so that subsequent GET /api/harness-runs/{run_id} requests
        resolve the space in O(1) without re-scanning the filesystem.
        """
        self._run_id_to_space_id[run_id] = space_id

    def lookup_space_id(self, run_id: str) -> str | None:
        """Return the space_id for *run_id*, or None if not in the cache."""
        return self._run_id_to_space_id.get(run_id)

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

    def subscribe_space(self) -> asyncio.Queue[dict]:
        """Subscribe to run_start/run_end events for any task in this space."""
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=256)
        self._space_subscribers.append(q)
        return q

    def unsubscribe_space(self, q: asyncio.Queue[dict]) -> None:
        if q in self._space_subscribers:
            self._space_subscribers.remove(q)

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
        """Decompose a feature/fix task via the feature-decompose skill.

        Spawns an auto-mode agent run that invokes the feature-decompose skill.
        On completion:
        - If realizing_items >= 1 AND result.status == DONE → transition feature_state to PLANNED.
        - Otherwise → derive a waiting_question and transition feature_state to WAITING.

        The task's TaskState is updated via finalize_run (ACTIVE → DONE on success,
        ACTIVE → WAITING on failure).  feature_state is updated separately via
        transition_feature with FEATURE_WORKER_TRANSITIONS.

        OQ-D resolution: transition_feature has no waiting_question kwarg; the
        waiting_question is persisted on task.waiting_question via finalize_run,
        which is the only atomic update path available without extending storage.py
        out of scope.
        """
        from .storage import FEATURE_WORKER_TRANSITIONS

        task = self.store.get(task_id)
        if task is None:
            log.warning("_run_feature_decompose: unknown task %s", task_id)
            return

        self._current_id = task_id
        cancel_event = asyncio.Event()
        self._current_cancel = cancel_event
        self._run_buffer[task_id] = []
        started_at = datetime.now(tz=UTC)
        await self._publish(task_id, {"type": "run_start", "task_id": task_id})

        async def on_event(event: dict) -> None:
            await self._publish(task_id, event)

        space = self.space_store.get(task.space_id) if self.space_store else None

        # Construct the skill-prefixed user_message so the agent always invokes
        # the feature-decompose skill regardless of the brief contents.
        decompose_prompt = (
            "Use the feature-decompose skill to decompose this feature request "
            "into a goal and child tasks.\n\n"
        )
        if user_message:
            decompose_prompt += user_message

        run_exception: str | None = None
        result = None
        try:
            result = await run_agent(
                task,
                user_message=decompose_prompt,
                on_event=on_event,
                cancel_event=cancel_event,
                space=space,
            )
        except FileNotFoundError as e:
            run_exception = f"claude binary not found: {e}"
            await self._publish(task_id, {"type": "run_error", "error": run_exception})
            log.exception("Failed to spawn claude for feature decompose %s", task_id)
        except Exception as e:
            run_exception = str(e)
            await self._publish(task_id, {"type": "run_error", "error": run_exception})
            log.exception("Agent error on feature decompose %s", task_id)
        finally:
            self._current_cancel = None

        ended_at = datetime.now(tz=UTC)
        timestamp = ended_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        if run_exception is not None:
            # Agent crashed before producing any result.
            waiting_question = "Decomposition agent crashed"
            history_entry = (
                f"```\n{timestamp} [agent]\n(agent error: {run_exception})\n```"
            )
            new_task_state = TaskState.WAITING
            new_feature_state = FeatureState.WAITING
        else:
            # Build history entry from agent output.
            body = result.final_text.strip() or "(no assistant text)"
            if result.exit_code != 0:
                body += f"\n\n(exit code {result.exit_code}; stderr tail: {result.stderr_tail.strip()})"
            history_entry = f"```\n{timestamp} [agent]\n{body}\n```"

            # Determine outcome based on realizing items and agent status.
            items: list = []
            try:
                items = await self.store.realizing_items(task_id)
            except Exception:
                log.exception("Failed to fetch realizing_items for %s", task_id)

            if result.status == Status.DONE and len(items) >= 1:
                # Success: agent decomposed and created realizing items.
                waiting_question = None
                new_task_state = TaskState.DONE
                new_feature_state = FeatureState.PLANNED
            elif result.status == Status.DONE and len(items) == 0:
                # Agent reported DONE but created no realizing tasks.
                waiting_question = "Decomposition agent completed but created no tasks"
                new_task_state = TaskState.WAITING
                new_feature_state = FeatureState.WAITING
            elif result.status == Status.WAIT:
                # Agent needs human input.
                waiting_question = result.context or "Agent requested human input"
                new_task_state = TaskState.WAITING
                new_feature_state = FeatureState.WAITING
            elif result.status == Status.BLOCKED:
                # Agent is blocked.
                waiting_question = "Decomposition blocked"
                new_task_state = TaskState.WAITING
                new_feature_state = FeatureState.WAITING
            elif result.exit_code != 0:
                # Non-zero exit without a STATUS marker counts as crash.
                waiting_question = "Decomposition agent crashed"
                new_task_state = TaskState.WAITING
                new_feature_state = FeatureState.WAITING
            else:
                # No STATUS marker at all.
                waiting_question = "No STATUS marker from decomposition agent"
                new_task_state = TaskState.WAITING
                new_feature_state = FeatureState.WAITING

        # Persist task state + history + waiting_question atomically.
        # OQ-D: waiting_question is stored on task.waiting_question via finalize_run
        # (the only available atomic write path); transition_feature has no equivalent kwarg.
        try:
            await self.store.finalize_run(
                task_id,
                new_state=new_task_state,
                session_id=(
                    result.session_id
                    if result is not None and result.exit_code == 0
                    else None
                ),
                waiting_question=waiting_question,
                history_entry=history_entry,
            )
        except Exception:
            log.exception("Failed to finalize feature decompose run for %s", task_id)

        # Transition feature_state independently of task.state.
        try:
            await self.store.transition_feature(
                task_id,
                new_feature_state,
                allowed=FEATURE_WORKER_TRANSITIONS,
            )
        except Exception:
            log.exception(
                "Failed to transition feature_state to %r for %s", new_feature_state, task_id
            )

        status_val = result.status.value if result is not None and result.status else None
        await self._publish(
            task_id,
            {
                "type": "run_end",
                "task_id": task_id,
                "status": status_val,
                "new_state": new_task_state.value,
            },
        )
        for q in list(self._subscribers.get(task_id, [])):
            try:
                q.put_nowait(_DONE_SENTINEL)
            except asyncio.QueueFull:
                pass

    async def _execute_harness_run(
        self,
        task_id: str,
        harness_id: str,
        space_id: str,
        *,
        initial_run: bool,
    ) -> bool:
        """Execute (initial_run=True) or resume (initial_run=False) a harness run.

        Builds HarnessExecutor with event_worker=_WorkerProtocolAdapter(self) so
        all node_transition/edge_chosen/run_status events land in _run_buffer.
        Returns True if executor.execute() was called; False on setup error.
        """
        if self.harness_store is None or self.space_store is None:
            return False

        space = self.space_store.get(space_id)
        if space is None:
            log.warning(
                "_execute_harness_run: space %r not found for run %s", space_id, task_id
            )
            return False

        space_dir = str(self.space_store.spaces_dir / space_id)
        try:
            harness = await self.harness_store.get(space_dir, harness_id)
        except Exception:
            log.exception(
                "Failed to load harness %r for task %s; cannot %s harness run.",
                harness_id, task_id, "start" if initial_run else "resume",
            )
            return False

        # F2 fix: event_worker uses the adapter (not Worker directly) because
        # WorkerProtocol._publish is sync, but Worker._publish is async def.
        # Passing Worker directly would create un-awaited coroutines and drop
        # all events. The adapter's sync _publish writes to _run_buffer directly.
        from .harnesses.executor import HarnessExecutor

        def _tools_resolver(space_id: str, agent_ref: str) -> AiToolEntry | None:
            space_claude_dir = self.space_store.spaces_dir / space_id / ".claude"
            global_claude_dir = Path.home() / ".claude"
            return resolve_tool(space_claude_dir, global_claude_dir, agent_ref)

        _adapter = _WorkerProtocolAdapter(self)
        executor = HarnessExecutor(
            self.store,
            _adapter,
            _tools_resolver,
            event_worker=_adapter,
        )

        log.info(
            "%s harness run %r (harness=%r) via executor.execute().",
            "Starting" if initial_run else "Resuming",
            task_id,
            harness_id,
        )
        try:
            result_state = await executor.execute(task_id, harness, space)
        except Exception:
            log.exception("executor.execute() failed for harness run %s", task_id)
            return True  # Was a harness task — caller should not run run_agent.

        # Transition the task state based on whether execution completed or parked.
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        if result_state.waiting_node_id is not None:
            # Harness parked at a human Wait node — transition to WAITING.
            log.info(
                "Harness run %r parked at waiting_node_id=%r.",
                task_id, result_state.waiting_node_id,
            )
            history_entry = (
                f"```\n{timestamp} [harness]\n"
                f"Waiting at node: {result_state.waiting_node_id}\n```"
            )
            try:
                await self.store.finalize_run(
                    task_id,
                    new_state=TaskState.WAITING,
                    session_id=None,
                    waiting_question=f"Harness waiting at node: {result_state.waiting_node_id}",
                    history_entry=history_entry,
                )
            except Exception:
                log.exception("Failed to finalize harness run %s to WAITING", task_id)
        else:
            # Harness execution completed (all nodes done or fail-fast).
            log.info("Harness run %r completed.", task_id)
            history_entry = f"```\n{timestamp} [harness]\nHarness run completed.\n```"
            try:
                await self.store.finalize_run(
                    task_id,
                    new_state=TaskState.DONE,
                    session_id=None,
                    waiting_question=None,
                    history_entry=history_entry,
                )
            except Exception:
                log.exception("Failed to finalize harness run %s to DONE", task_id)

        return True

    async def _resume_harness_run(self, task_id: str) -> bool:
        """Resume a WAITING harness run (waiting_node_id is set in run-state).

        Returns True if executor.execute() was called; False if no harness
        run-state exists for task_id (caller should proceed with run_agent).
        """
        if self.harness_store is None or self.space_store is None:
            return False

        task = self.store.get(task_id)
        if task is None:
            return False

        # Compute the run-state file path (same formula as executor.py).
        run_state_path = (
            DATA_DIR / "spaces" / task.space_id / ".cronos" / "harness-runs" / f"{task_id}.json"
        )
        if not run_state_path.exists():
            return False

        # Load the run state to check for a pending human Wait.
        try:
            from .harnesses.run_state import load as load_run_state
            run_state = load_run_state(run_state_path)
        except Exception:
            log.exception("Failed to load harness run state for %s", task_id)
            return False

        if run_state is None or run_state.waiting_node_id is None:
            # No waiting node — not a harness resume (or harness completed).
            return False

        return await self._execute_harness_run(
            task_id,
            run_state.harness_id,
            task.space_id,
            initial_run=False,
        )

    async def _run_initial_harness_run(self, task_id: str) -> bool:
        """F1 fix: execute a freshly-triggered harness run for the first time.

        Called from _run_task when task_id is in _run_id_to_space_id (set by
        register_run() on POST /run) but no run-state JSON exists yet.
        Resolves harness_id from the index file, then delegates to
        _execute_harness_run(initial_run=True).

        Returns True if executor.execute() was called; False if task_id is
        not a known harness run (caller should fall through to run_agent).
        """
        space_id = self._run_id_to_space_id.get(task_id)
        if space_id is None:
            return False  # Not a harness run; fall through to run_agent.

        if self.harness_store is None or self.space_store is None:
            return False

        # Resolve harness_id from the run-index file (written by POST /run).
        harness_id: str | None = None
        index_dir = DATA_DIR / "spaces" / space_id / ".cronos" / "harness-runs"
        import json as _json
        if index_dir.is_dir():
            for index_file in index_dir.glob("*-index.json"):
                try:
                    with index_file.open("r", encoding="utf-8") as fh:
                        entries: list[dict] = _json.load(fh)
                    for entry in entries:
                        if entry.get("run_id") == task_id:
                            harness_id = entry.get("harness_id")
                            break
                except Exception:
                    log.debug("_run_initial_harness_run: skipping %s (read error)", index_file)
                if harness_id is not None:
                    break

        if harness_id is None:
            log.warning(
                "_run_initial_harness_run: could not find harness_id for run %s in space %s",
                task_id, space_id,
            )
            return False

        return await self._execute_harness_run(
            task_id,
            harness_id,
            space_id,
            initial_run=True,
        )

    async def _run_task(self, task_id: str, user_message: str | None) -> None:
        task = self.store.get(task_id)
        if task is None:
            log.warning("Skipping unknown task %s", task_id)
            return

        # Check if this is a WAITING harness run goal being resumed via a
        # pending_messages reply.  If so, delegate to executor.execute() and
        # skip the regular run_agent path entirely.
        handled = await self._resume_harness_run(task_id)
        if handled:
            log.info("Task %s handled as harness resume; skipping run_agent.", task_id)
            await self._publish(task_id, {
                "type": "run_end",
                "task_id": task_id,
                "status": None,
                "new_state": None,
            })
            return

        # F1 fix: check for a freshly-triggered harness run (task_id in
        # _run_id_to_space_id means POST /run registered it).  Without this
        # branch the worker falls through to run_agent on a task with no agent.
        handled = await self._run_initial_harness_run(task_id)
        if handled:
            log.info("Task %s handled as initial harness run; skipping run_agent.", task_id)
            await self._publish(task_id, {
                "type": "run_end",
                "task_id": task_id,
                "status": None,
                "new_state": None,
            })
            return

        self._current_id = task_id
        cancel_event = asyncio.Event()
        self._current_cancel = cancel_event
        self._run_buffer[task_id] = []
        started_at = datetime.now(tz=UTC)
        await self._publish(task_id, {"type": "run_start", "task_id": task_id})

        async def on_event(event: dict) -> None:
            await self._publish(task_id, event)

        space = self.space_store.get(task.space_id) if self.space_store else None
        workspace_path = DATA_DIR / task.space_id / CRONOS_SUBDIR / "workspaces" / task.id
        memory_injected = _memory_injected_for_workspace(workspace_path)
        retrieved_memory = None
        if self.memory_store is not None:
            try:
                retrieved_memory = await memory_retrieval.retrieve(task, task.space_id, self.memory_store) or None
            except Exception:
                log.exception("Failed to retrieve memory for %s", task_id)
        run_exception: str | None = None
        result = None
        try:
            result = await run_agent(
                task,
                user_message=user_message,
                on_event=on_event,
                cancel_event=cancel_event,
                space=space,
                memory_items=retrieved_memory,
            )
        except FileNotFoundError as e:
            run_exception = f"claude binary not found: {e}"
            await self._publish(
                task_id,
                {"type": "run_error", "error": run_exception},
            )
            log.exception("Failed to spawn claude for %s", task_id)
        except Exception as e:
            run_exception = str(e)
            await self._publish(task_id, {"type": "run_error", "error": run_exception})
            log.exception("Agent error on %s", task_id)
        finally:
            self._current_cancel = None

        if run_exception is not None:
            # Transition task to WAITING so it doesn't remain stuck in ACTIVE.
            ended_at = datetime.now(tz=UTC)
            timestamp = ended_at.strftime("%Y-%m-%dT%H:%M:%SZ")
            history_entry = f"```\n{timestamp} [agent]\n(agent error: {run_exception})\n```"
            try:
                await self.store.finalize_run(
                    task_id,
                    new_state=TaskState.WAITING,
                    session_id=None,
                    waiting_question=f"Agent failed to start: {run_exception}",
                    history_entry=history_entry,
                )
            except Exception:
                log.exception("Failed to finalize errored task %s", task_id)
            await self._publish(
                task_id,
                {
                    "type": "run_end",
                    "task_id": task_id,
                    "status": None,
                    "new_state": TaskState.WAITING.value,
                },
            )
            for q in list(self._subscribers.get(task_id, [])):
                try:
                    q.put_nowait(_DONE_SENTINEL)
                except asyncio.QueueFull:
                    pass
            return

        await self._finalize(task_id, result, started_at=started_at, memory_injected=memory_injected)

    async def _finalize(
        self,
        task_id: str,
        result: AgentResult,
        *,
        started_at: datetime | None = None,
        memory_injected: list[str] | None = None,
    ) -> None:
        ended_at = datetime.now(tz=UTC)
        timestamp = ended_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Pre-fetch task and extract usage early to build history entry with agent metadata.
        task_pre = self.store.get(task_id)
        usage = extract_tokens_and_tools(result.raw_events)
        real_model = usage["real_model"]

        # Determine run index before persisting anything so the history entry
        # accurately identifies which run this is.
        run_index = 0
        if self.stats_store is not None and task_pre is not None:
            existing = await self.stats_store.load(task_pre.space_id, task_id)
            run_index = len(existing.runs) if existing else 0
        elif self.trace_store is not None and task_pre is not None:
            run_index = await self.trace_store.count_runs(task_pre.space_id, task_id)

        model_label = real_model or (task_pre.agent_model if task_pre else "default")
        mode_label = task_pre.agent_mode if task_pre else "auto"
        agent_meta = f"run={run_index} model={model_label} mode={mode_label}"
        subagent_types = _extract_subagent_types(result.raw_events)
        if subagent_types:
            agent_meta += f" agents={','.join(subagent_types)}"
        prefix = f"```\n{timestamp} [agent] {agent_meta}\n"

        body = result.final_text.strip() or "(no assistant text)"
        if result.stopped:
            body += "\n\n(stopped by user)"
        elif result.exit_code != 0:
            body += f"\n\n(exit code {result.exit_code}; stderr tail: {result.stderr_tail.strip()})"
        history_entry = prefix + body + "\n```"

        if result.stopped:
            new_state = TaskState.WAITING
            waiting_question = "Stopped by user."
        elif result.status == Status.DONE:
            # Trust STATUS:DONE even with non-zero exit (e.g., killed by upgrade webhook).
            new_state = TaskState.DONE
            waiting_question = None
        elif result.exit_code != 0:
            new_state = TaskState.WAITING
            waiting_question = f"Agent crashed with exit code {result.exit_code}."
        elif result.status == Status.WAIT:
            new_state = TaskState.WAITING
            waiting_question = result.context or "(agent asked to wait but gave no question)"
        elif result.status == Status.BLOCKED:
            new_state = TaskState.WAITING
            waiting_question = f"Blocked: {result.context or '(no reason)'}"
        elif result.result_subtype == "error_max_turns":
            new_state = TaskState.WAITING
            waiting_question = (
                "Agent hit the turn limit before finishing. "
                "Reply 'continue' to resume from where it left off."
            )
        else:
            new_state = TaskState.WAITING
            waiting_question = (
                "The previous run ended without a STATUS marker. "
                "If the task is complete, reply with just 'done'. "
                "Otherwise continue where you left off."
            )

        # Only persist the session id from a successful run. A crashed run
        # often emits a fresh session id that claude never actually stored on
        # disk — saving it would make every subsequent `--resume` fail with
        # "No conversation found with session ID …".
        session_id_to_persist = (
            result.session_id if result.exit_code == 0 and not result.stopped else None
        )
        old_state_value = task_pre.state.value if task_pre is not None else ""
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

        # Invoke the optional task-state-change callback (wired by main.py to
        # fan out harness triggers).  Called only on DONE transitions so that
        # harness-trigger fans out exactly once per completed run.  Wrapped in
        # try/except so a failing callback never aborts downstream hooks.
        if new_state == TaskState.DONE and self._on_task_state_change is not None:
            task_after = self.store.get(task_id)
            space_id_for_cb = task_after.space_id if task_after is not None else (
                task_pre.space_id if task_pre is not None else ""
            )
            try:
                await self._on_task_state_change(
                    space_id_for_cb,
                    task_id,
                    old_state_value,
                    new_state.value,
                )
            except Exception:
                log.exception(
                    "on_task_state_change callback failed for task %s; continuing", task_id
                )

        if new_state == TaskState.DONE and self.space_store is not None:
            task_done = self.store.get(task_id)
            space_for_pr = self.space_store.get(task_done.space_id) if task_done else None
            if task_done is not None and space_for_pr is not None:
                try:
                    pr_result = await autopilot_pr.run_post_done_flow(
                        task_done, space_for_pr, self.store
                    )
                    if pr_result.pr_url:
                        await self._publish(
                            task_id,
                            {"type": "pr_opened", "pr_url": pr_result.pr_url},
                        )
                    elif pr_result.proposed_pr_path:
                        await self._publish(
                            task_id,
                            {"type": "pr_opened", "proposed_pr_path": pr_result.proposed_pr_path},
                        )
                except Exception:
                    log.exception("autopilot_pr: post-DONE flow failed for %s", task_id)

        # Post-DONE hook: finalize adopted-tool merge tasks.
        if new_state == TaskState.DONE:
            task_for_merge = self.store.get(task_id)
            if task_for_merge is not None and task_for_merge.title.startswith(
                "Merge upstream changes to "
            ):
                meta = _parse_merge_meta(task_for_merge.brief)
                if meta is not None:
                    try:
                        from .tools.adoption import NotAdopted, finalize_merge
                        finalize_merge(
                            meta["space_id"],
                            meta["kind"],
                            meta["name"],
                            meta["upstream_source_sha"],
                            spaces_dir=self.store.spaces_dir,
                        )
                    except NotAdopted:
                        log.warning(
                            "finalize_merge: %s/%s not adopted in space %s",
                            meta["kind"], meta["name"], meta["space_id"],
                        )
                    except Exception:
                        log.exception("finalize_merge failed for task %s", task_id)

        # Propagate new state to parent goal when this task is a child run standalone.
        try:
            await goal_sync.propagate_to_parent(task_id, self.store, self._pool)
        except Exception:
            log.exception("Failed to propagate state to parent goal for %s", task_id)

        # Propagate new state to the feature/fix this task realizes (if any).
        try:
            await feature_sync.propagate_to_feature(task_id, self.store, self._pool)
        except Exception:
            log.exception("feature_sync.propagate_to_feature failed for task_id=%s", task_id)

        exit_reason = (
            "STOPPED" if result.stopped
            else (result.status.value if result.status else
                  ("CRASHED" if result.exit_code != 0 else "NO_STATUS"))
        )

        # Pre-compute run trace when needed for memory_hit_rate, adopted_tool_uses, or saving.
        # Doing this before RunStats lets us embed derived signals in the stats record.
        computed_trace: RunTrace | None = None
        if self.trace_store is not None or bool(memory_injected) or self.stats_store is not None:
            task = self.store.get(task_id)
            if task is not None:
                try:
                    from .tools.index import adopted_index_for_space
                    adopted_idx = adopted_index_for_space(
                        task.space_id, spaces_dir=self.store.spaces_dir
                    )
                    computed_trace = extract_run_trace(
                        result.raw_events,
                        task_id=task_id,
                        space_id=task.space_id,
                        run_index=run_index,
                        model=task.agent_model,
                        mode=task.agent_mode,
                        started_at=started_at or ended_at,
                        ended_at=ended_at,
                        exit_reason=exit_reason,
                        session_id=result.session_id,
                        had_crash=result.exit_code != 0 and not result.stopped,
                        memory_injected=memory_injected or [],
                        adopted_index=adopted_idx or None,
                    )
                except Exception:
                    log.exception("Failed to compute trace for %s", task_id)

        # Persist run statistics (usage and run_index already computed above)
        if self.stats_store is not None:
            task = self.store.get(task_id)
            if task is not None:
                try:
                    _started = started_at or ended_at
                    pricing_tier = _tier_from_real_model(real_model, task.agent_model)
                    run_stats = RunStats(
                        run_index=run_index,
                        started_at=_started,
                        ended_at=ended_at,
                        duration_seconds=round((ended_at - _started).total_seconds(), 2),
                        model=task.agent_model,
                        real_model=real_model,
                        mode=task.agent_mode,
                        exit_reason=exit_reason,
                        input_tokens=usage["input_tokens"],
                        output_tokens=usage["output_tokens"],
                        cache_read_tokens=usage["cache_read_tokens"],
                        cache_creation_tokens=usage["cache_creation_tokens"],
                        cost_usd=compute_cost(
                            pricing_tier,
                            usage["input_tokens"],
                            usage["output_tokens"],
                            usage["cache_read_tokens"],
                            usage["cache_creation_tokens"],
                        ),
                        tool_uses=usage["tool_uses"],
                        error_count=usage["error_count"],
                        had_crash=result.exit_code != 0 and not result.stopped,
                        memory_hit_rate=(
                            computed_trace.memory_hit_rate
                            if computed_trace is not None and memory_injected
                            else None
                        ),
                        adopted_tool_uses=(
                            compute_adopted_tool_uses(computed_trace.tool_calls, exit_reason)
                            if computed_trace is not None
                            else {}
                        ),
                    )
                    await self.stats_store.append_run(
                        task.space_id, task_id, task.title, run_stats
                    )
                except Exception:
                    log.exception("Failed to save stats for %s", task_id)

        # Persist run trace using the pre-computed trace (if trace_store is active)
        if self.trace_store is not None and computed_trace is not None:
            task = self.store.get(task_id)
            if task is not None:
                try:
                    await self.trace_store.save_run(task.space_id, task_id, computed_trace)
                except Exception:
                    log.exception("Failed to save trace for %s", task_id)

        # Capture MEMORY: blocks from the agent's final text and persist as unconfirmed.
        if self.memory_store is not None and result.final_text:
            blocks = parse_memory_blocks(result.final_text)
            if blocks:
                task = self.store.get(task_id)
                if task is not None:
                    for block in blocks:
                        try:
                            title = block.content.splitlines()[0][:120]
                            await self.memory_store.create(
                                scope=f"space:{task.space_id}",
                                kind=block.kind_hint or "observation",
                                title=title,
                                body=block.content,
                                confirmed=False,
                                sources=[f"task:{task_id}", f"run:{run_index}"],
                            )
                        except Exception:
                            log.exception("Failed to save memory block for %s", task_id)

        # Auto-resume when the agent hit the turn limit mid-task (up to 3 times
        # per task to prevent infinite loops).
        _MAX_AUTO_RESUMES = 3
        if (
            result.exit_code == 0
            and result.status is None
            and result.result_subtype == "error_max_turns"
            and not result.stopped
            and self._auto_resume_counts.get(task_id, 0) < _MAX_AUTO_RESUMES
        ):
            self._auto_resume_counts[task_id] = self._auto_resume_counts.get(task_id, 0) + 1
            log.info(
                "Auto-resuming %s after max-turns exit (attempt %d/%d)",
                task_id, self._auto_resume_counts[task_id], _MAX_AUTO_RESUMES,
            )
            try:
                await self.store.resume_with_message(task_id)
                await self.enqueue(task_id, user_message="Continue where you left off.")
            except Exception:
                log.exception("Failed to auto-resume %s after max-turns", task_id)
            # Fall through to publish run_end so the current SSE stream closes cleanly.
        else:
            # Clear the counter on any non-max-turns outcome so it resets
            # between separate task invocations.
            self._auto_resume_counts.pop(task_id, None)

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

    async def _finalize_child(
        self,
        child_id: str,
        result: AgentResult | None,
        run_exception: str | None,
        *,
        started_at: datetime,
        memory_injected: list[str] | None = None,
    ) -> TaskState:
        """Finalize a child task run inside goal orchestration. Returns the new state."""
        ended_at = datetime.now(tz=UTC)
        timestamp = ended_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        if run_exception is not None:
            new_state = TaskState.WAITING
            waiting_question: str | None = f"Agent failed: {run_exception}"
            history_entry = f"```\n{timestamp} [agent]\n(agent error: {run_exception})\n```"
        elif result is None:
            new_state = TaskState.WAITING
            waiting_question = "Agent did not produce a result."
            history_entry = f"```\n{timestamp} [agent]\n(no result)\n```"
        else:
            body = result.final_text.strip() or "(no assistant text)"
            if result.stopped:
                body += "\n\n(stopped by user)"
            elif result.exit_code != 0:
                body += f"\n\n(exit code {result.exit_code}; stderr: {result.stderr_tail.strip()})"
            history_entry = f"```\n{timestamp} [agent]\n{body}\n```"

            if result.stopped:
                new_state = TaskState.WAITING
                waiting_question = "Stopped by user."
            elif result.status == Status.DONE:
                new_state = TaskState.DONE
                waiting_question = None
            elif result.exit_code != 0:
                new_state = TaskState.WAITING
                waiting_question = f"Agent crashed (exit code {result.exit_code})."
            elif result.status == Status.WAIT:
                new_state = TaskState.WAITING
                waiting_question = result.context or "(agent waiting)"
            elif result.status == Status.BLOCKED:
                new_state = TaskState.WAITING
                waiting_question = f"Blocked: {result.context or '(no reason)'}"
            else:
                new_state = TaskState.WAITING
                waiting_question = "Run ended without STATUS marker."

        session_id = (
            result.session_id
            if result and result.exit_code == 0 and not result.stopped
            else None
        )
        try:
            await self.store.finalize_run(
                child_id,
                new_state=new_state,
                session_id=session_id,
                waiting_question=waiting_question if new_state == TaskState.WAITING else None,
                history_entry=history_entry,
            )
        except Exception:
            log.exception("Failed to finalize child %s", child_id)

        if self.memory_store is not None and result is not None and result.final_text:
            blocks = parse_memory_blocks(result.final_text)
            if blocks:
                child_task = self.store.get(child_id)
                if child_task is not None:
                    for block in blocks:
                        try:
                            title = block.content.splitlines()[0][:120]
                            await self.memory_store.create(
                                scope=f"space:{child_task.space_id}",
                                kind=block.kind_hint or "observation",
                                title=title,
                                body=block.content,
                                confirmed=False,
                                sources=[f"task:{child_id}"],
                            )
                        except Exception:
                            log.exception("Failed to save memory block for child %s", child_id)

        if result is not None and (self.trace_store is not None or self.stats_store is not None):
            child_task = self.store.get(child_id)
            if child_task is not None:
                try:
                    usage = extract_tokens_and_tools(result.raw_events)
                    real_model = usage["real_model"]

                    run_index = 0
                    if self.stats_store is not None:
                        existing = await self.stats_store.load(child_task.space_id, child_id)
                        run_index = len(existing.runs) if existing else 0
                    elif self.trace_store is not None:
                        run_index = await self.trace_store.count_runs(child_task.space_id, child_id)

                    exit_reason = (
                        "STOPPED" if result.stopped
                        else (result.status.value if result.status else
                              ("CRASHED" if result.exit_code != 0 else "NO_STATUS"))
                    )

                    computed_trace: RunTrace | None = None
                    try:
                        from .tools.index import adopted_index_for_space
                        adopted_idx = adopted_index_for_space(
                            child_task.space_id, spaces_dir=self.store.spaces_dir
                        )
                        computed_trace = extract_run_trace(
                            result.raw_events,
                            task_id=child_id,
                            space_id=child_task.space_id,
                            run_index=run_index,
                            model=child_task.agent_model,
                            mode=child_task.agent_mode,
                            started_at=started_at,
                            ended_at=ended_at,
                            exit_reason=exit_reason,
                            session_id=result.session_id,
                            had_crash=result.exit_code != 0 and not result.stopped,
                            memory_injected=memory_injected or [],
                            adopted_index=adopted_idx or None,
                        )
                    except Exception:
                        log.exception("Failed to compute trace for child %s", child_id)

                    if self.stats_store is not None and computed_trace is not None:
                        try:
                            pricing_tier = _tier_from_real_model(real_model, child_task.agent_model)
                            run_stats = RunStats(
                                run_index=run_index,
                                started_at=started_at,
                                ended_at=ended_at,
                                duration_seconds=round((ended_at - started_at).total_seconds(), 2),
                                model=child_task.agent_model,
                                real_model=real_model,
                                mode=child_task.agent_mode,
                                exit_reason=exit_reason,
                                input_tokens=usage["input_tokens"],
                                output_tokens=usage["output_tokens"],
                                cache_read_tokens=usage["cache_read_tokens"],
                                cache_creation_tokens=usage["cache_creation_tokens"],
                                cost_usd=compute_cost(
                                    pricing_tier,
                                    usage["input_tokens"],
                                    usage["output_tokens"],
                                    usage["cache_read_tokens"],
                                    usage["cache_creation_tokens"],
                                ),
                                tool_uses=usage["tool_uses"],
                                error_count=usage["error_count"],
                                had_crash=result.exit_code != 0 and not result.stopped,
                                memory_hit_rate=(
                                    computed_trace.memory_hit_rate
                                    if memory_injected
                                    else None
                                ),
                                adopted_tool_uses=compute_adopted_tool_uses(
                                    computed_trace.tool_calls, exit_reason
                                ),
                            )
                            await self.stats_store.append_run(
                                child_task.space_id, child_id, child_task.title, run_stats
                            )
                        except Exception:
                            log.exception("Failed to save stats for child %s", child_id)

                    if self.trace_store is not None and computed_trace is not None:
                        try:
                            await self.trace_store.save_run(child_task.space_id, child_id, computed_trace)
                        except Exception:
                            log.exception("Failed to save trace for child %s", child_id)
                except Exception:
                    log.exception("Failed to record telemetry for child %s", child_id)

        return new_state

    async def _run_goal(self, goal_id: str, user_message: str | None) -> None:
        """Orchestrate a goal by running its child tasks sequentially in dep order."""
        goal = self.store.get(goal_id)
        if goal is None:
            log.warning("Skipping unknown goal %s", goal_id)
            return

        self._current_id = goal_id
        cancel_event = asyncio.Event()
        self._current_cancel = cancel_event
        self._run_buffer[goal_id] = []
        started_at = datetime.now(tz=UTC)

        await self._publish(goal_id, {"type": "run_start", "task_id": goal_id})

        ordered_child_ids = _topo_children(goal_id, self.store)
        goal_context = f"# Goal: {goal.title}\n\n{goal.brief}"

        # Drain any messages queued via goal-level reply while goal was idle.
        try:
            pending = await self.store.drain_pending(goal_id)
        except Exception:
            log.exception("Failed to drain pending messages for goal %s", goal_id)
            pending = []
        if pending:
            goal_context += "\n\n## User notes\n" + "\n".join(f"- {m}" for m in pending)

        completed: list[str] = []
        skipped: list[str] = []
        stopped = False
        failed_child_id: str | None = None
        fail_reason: str | None = None
        _repaired = False

        while True:
            _restart = False
            for child_id in ordered_child_ids:
                child = self.store.get(child_id)
                if child is None:
                    continue

                if child.state.value in ("done", "archived"):
                    skipped.append(child_id)
                    await self._publish(goal_id, {
                        "type": "goal_child_skipped",
                        "child_id": child_id,
                        "title": child.title,
                    })
                    continue

                if child.state != TaskState.BACKLOG:
                    failed_child_id = child_id
                    fail_reason = (
                        f"Child '{child.title}' is in {child.state.value} state and needs attention."
                    )
                    break

                try:
                    await self.store.transition(child_id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
                except InvalidTransition as e:
                    err = str(e)
                    if not _repaired and err.startswith("Cannot start task: unmet dependencies:"):
                        dep_ids_str = err[len("Cannot start task: unmet dependencies:"):].strip()
                        dep_ids = [d.strip() for d in dep_ids_str.split(",") if d.strip()]
                        repaired_any = False
                        child = self.store.get(child_id)
                        if child is not None:
                            for dep_id in dep_ids:
                                dep_task = self.store.get(dep_id)
                                if dep_task is None or dep_task.parent_id == goal_id:
                                    continue
                                # Walk parent chain to find the ancestor whose parent_id == goal_id.
                                sibling_id: str | None = None
                                cursor = dep_task
                                for _ in range(50):
                                    if cursor.parent_id == goal_id:
                                        sibling_id = cursor.id
                                        break
                                    if cursor.parent_id is None:
                                        break
                                    parent = self.store.get(cursor.parent_id)
                                    if parent is None:
                                        break
                                    cursor = parent
                                if sibling_id is None or sibling_id in child.depends_on:
                                    continue
                                try:
                                    await self.store.set_depends_on(
                                        child_id, child.depends_on + [sibling_id]
                                    )
                                except Exception:
                                    log.exception("Auto-repair set_depends_on failed for %s", child_id)
                                    continue
                                log.warning(
                                    "Auto-repaired missing sibling dep: %s → %s (was referencing non-sibling %s)",
                                    child_id, sibling_id, dep_id,
                                )
                                repaired_any = True
                        if repaired_any:
                            _repaired = True
                            ordered_child_ids = _topo_children(goal_id, self.store)
                            completed = []
                            skipped = []
                            failed_child_id = None
                            fail_reason = None
                            _restart = True
                            break
                    failed_child_id = child_id
                    fail_reason = str(e)
                    break

                child = self.store.get(child_id)
                if child is None:
                    continue

                # Sub-goals are orchestrated recursively instead of being sent to run_agent.
                if child.type == "goal":
                    await self._publish(goal_id, {
                        "type": "goal_child_start",
                        "child_id": child_id,
                        "title": child.title,
                    })
                    await self._run_goal(child_id, user_message=None)
                    # Restore parent context overwritten by the recursive call.
                    self._current_id = goal_id
                    self._current_cancel = cancel_event
                    child_after = self.store.get(child_id)
                    child_new_state = child_after.state if child_after is not None else TaskState.WAITING
                    await self._publish(goal_id, {
                        "type": "goal_child_end",
                        "child_id": child_id,
                        "title": child.title,
                        "new_state": child_new_state.value,
                    })
                    if cancel_event.is_set():
                        stopped = True
                        break
                    if child_new_state != TaskState.DONE:
                        failed_child_id = child_id
                        fail_reason = f"Sub-goal '{child.title}' ended in {child_new_state.value} state."
                        break
                    completed.append(child_id)
                    continue

                await self._publish(goal_id, {
                    "type": "goal_child_start",
                    "child_id": child_id,
                    "title": child.title,
                })

                self._current_child_id = child_id
                self._run_buffer[child_id] = []
                await self._publish(child_id, {"type": "run_start", "task_id": child_id})

                # Capture child_id per-iteration to avoid closure/loop-variable capture.
                async def on_child_event(event: dict, _cid: str = child_id) -> None:
                    await self._publish(_cid, event)
                    await self._publish(goal_id, event)

                space = self.space_store.get(child.space_id) if self.space_store else None
                child_result: AgentResult | None = None
                run_exception: str | None = None
                child_started_at = datetime.now(tz=UTC)
                child_memory_injected = _memory_injected_for_workspace(
                    DATA_DIR / child.space_id / CRONOS_SUBDIR / "workspaces" / child_id
                )
                child_memory = None
                if self.memory_store is not None:
                    try:
                        child_memory = await memory_retrieval.retrieve(child, child.space_id, self.memory_store) or None
                    except Exception:
                        log.exception("Failed to retrieve memory for child %s", child_id)

                try:
                    child_result = await run_agent(
                        child,
                        user_message=None,
                        on_event=on_child_event,
                        cancel_event=cancel_event,
                        space=space,
                        goal_context=goal_context,
                        memory_items=child_memory,
                    )
                except Exception as e:
                    run_exception = str(e)
                    log.exception("Agent error on child %s", child_id)

                self._current_child_id = None
                child_new_state = await self._finalize_child(
                    child_id, child_result, run_exception, started_at=child_started_at,
                    memory_injected=child_memory_injected,
                )

                await self._publish(child_id, {
                    "type": "run_end",
                    "task_id": child_id,
                    "status": child_result.status.value if child_result and child_result.status else None,
                    "new_state": child_new_state.value,
                })
                for q in list(self._subscribers.get(child_id, [])):
                    try:
                        q.put_nowait(_DONE_SENTINEL)
                    except asyncio.QueueFull:
                        pass

                await self._publish(goal_id, {
                    "type": "goal_child_end",
                    "child_id": child_id,
                    "title": child.title,
                    "new_state": child_new_state.value,
                })

                if cancel_event.is_set():
                    stopped = True
                    break

                if child_new_state != TaskState.DONE:
                    failed_child_id = child_id
                    fail_reason = f"Child '{child.title}' ended in {child_new_state.value} state."
                    break

                completed.append(child_id)

            if not _restart:
                break

        # Finalize the goal
        if stopped:
            goal_new_state = TaskState.WAITING
            goal_waiting_question: str | None = "Stopped by user."
            summary = f"Stopped. Completed {len(completed)}, skipped {len(skipped)} already-done."
        elif failed_child_id is not None:
            goal_new_state = TaskState.WAITING
            goal_waiting_question = fail_reason
            summary = (
                f"Paused: {fail_reason} "
                f"Completed {len(completed)}, skipped {len(skipped)} already-done."
            )
        else:
            goal_new_state = TaskState.DONE
            goal_waiting_question = None
            summary = (
                f"All tasks complete. "
                f"Completed {len(completed)}, skipped {len(skipped)} already-done."
            )

        ended_at = datetime.now(tz=UTC)
        timestamp = ended_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        history_entry = f"```\n{timestamp} [agent]\n{summary}\n```"

        try:
            await self.store.finalize_run(
                goal_id,
                new_state=goal_new_state,
                session_id=None,
                waiting_question=goal_waiting_question,
                history_entry=history_entry,
            )
        except Exception:
            log.exception("Failed to finalize goal %s", goal_id)

        # Record a synthetic orchestration trace and stats for the goal itself.
        goal_exit_reason = (
            "STOPPED" if stopped
            else ("DONE" if goal_new_state == TaskState.DONE else "WAITING")
        )
        goal_task = self.store.get(goal_id)
        if goal_task is not None and (self.trace_store is not None or self.stats_store is not None):
            try:
                run_index = 0
                if self.stats_store is not None:
                    existing = await self.stats_store.load(goal_task.space_id, goal_id)
                    run_index = len(existing.runs) if existing else 0
                elif self.trace_store is not None:
                    run_index = await self.trace_store.count_runs(goal_task.space_id, goal_id)

                if self.stats_store is not None:
                    run_stats = RunStats(
                        run_index=run_index,
                        started_at=started_at,
                        ended_at=ended_at,
                        duration_seconds=round((ended_at - started_at).total_seconds(), 2),
                        model=goal_task.agent_model or "default",
                        real_model=None,
                        mode=goal_task.agent_mode or "auto",
                        exit_reason=goal_exit_reason,
                        had_crash=False,
                    )
                    try:
                        await self.stats_store.append_run(
                            goal_task.space_id, goal_id, goal_task.title, run_stats
                        )
                    except Exception:
                        log.exception("Failed to save stats for goal %s", goal_id)

                if self.trace_store is not None:
                    goal_trace = RunTrace(
                        task_id=goal_id,
                        space_id=goal_task.space_id,
                        run_index=run_index,
                        session_id=None,
                        model=goal_task.agent_model or "default",
                        mode=goal_task.agent_mode or "auto",
                        started_at=started_at,
                        ended_at=ended_at,
                        duration_seconds=round((ended_at - started_at).total_seconds(), 2),
                        exit_reason=goal_exit_reason,
                        final_text_snippet=summary[:500],
                    )
                    try:
                        await self.trace_store.save_run(goal_task.space_id, goal_id, goal_trace)
                    except Exception:
                        log.exception("Failed to save trace for goal %s", goal_id)
            except Exception:
                log.exception("Failed to record telemetry for goal %s", goal_id)

        self._current_cancel = None

        await self._publish(goal_id, {
            "type": "run_end",
            "task_id": goal_id,
            "status": "DONE" if goal_new_state == TaskState.DONE else None,
            "new_state": goal_new_state.value,
        })
        for q in list(self._subscribers.get(goal_id, [])):
            try:
                q.put_nowait(_DONE_SENTINEL)
            except asyncio.QueueFull:
                pass

    async def _publish(self, task_id: str, event: dict) -> None:
        # Event ``type`` values that appear in _run_buffer:
        #   Legacy task events: "run_start", "run_end", "run_error",
        #     "goal_child_start", "goal_child_end", "goal_child_skipped", "pr_opened"
        #   Harness events (added by I3): "node_transition", "edge_chosen", "run_status"
        # Harness events are discriminated by their ``type`` field so that existing
        # SSE consumers that only recognise legacy event names silently ignore them.
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


async def sse_space_events(worker: Worker) -> AsyncIterator[str]:
    """Yields run_start/run_end SSE events for all tasks in a worker's space.

    Stays open indefinitely; the client disconnects when done.
    """
    import json

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
