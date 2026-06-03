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
from . import goal_sync
from . import memory_retrieval
from .memory_parser import parse_memory_blocks
from .memory_store import MemoryStore
from .models import TaskState
from .space_storage import SpaceStore
from .stats import RunStats, _tier_from_real_model, compute_cost, extract_tokens_and_tools
from .stats_store import StatsStore
from .storage import InvalidTransition, TaskStore, USER_TRANSITIONS
from .trace_parser import RunTrace, extract_run_trace
from .trace_store import TraceStore

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .worker_pool import WorkerPool

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
        pool: WorkerPool | None = None,
    ) -> None:
        self.store = store
        self.space_store = space_store
        self.stats_store = stats_store
        self.trace_store = trace_store
        self.memory_store = memory_store
        self.on_idle = on_idle
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
        else:
            await self._run_task(task_id, user_message)

    async def _run_task(self, task_id: str, user_message: str | None) -> None:
        task = self.store.get(task_id)
        if task is None:
            log.warning("Skipping unknown task %s", task_id)
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

        exit_reason = (
            "STOPPED" if result.stopped
            else (result.status.value if result.status else
                  ("CRASHED" if result.exit_code != 0 else "NO_STATUS"))
        )

        # Pre-compute run trace when needed for memory_hit_rate or for saving.
        # Doing this before RunStats lets us embed memory_hit_rate in the stats record.
        computed_trace: RunTrace | None = None
        if self.trace_store is not None or bool(memory_injected):
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
                child_id, child_result, run_exception, started_at=child_started_at
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

        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
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
