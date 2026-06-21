"""backend/app/run_executor.py — Task, goal, feature, and harness run execution.

Extracted from Worker._run_task, Worker._run_goal, Worker._run_feature_decompose,
and the harness run helpers. RunExecutor holds references to the stores and
collaborators it needs; Worker keeps thin shim methods for backward-compatibility
with existing tests and callers.

RunExecutor deliberately does NOT subclass Worker; it accesses Worker state
through an explicit ``worker`` reference to avoid circular imports and tight
coupling.
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
from datetime import UTC, datetime
from pathlib import Path

from .agent import AgentResult, CRONOS_SUBDIR
from .event_bus import EventBus
from .logging_config import bind_run_context
from .models import AiToolEntry, TaskState
from .storage import InvalidTransition, TaskStore, USER_TRANSITIONS

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .finalizer import Finalizer
    from .space_storage import SpaceStore
    from .harnesses.store import HarnessStore

log = logging.getLogger("cronos.worker")


def _topo_children_local(goal_id: str, store: TaskStore) -> list[str]:
    """Import-free copy of _topo_children to avoid importing from worker.py."""
    from collections import deque

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


class RunExecutor:
    """Executes task runs, goal orchestration, feature decomposition, and harness runs.

    Extracted from Worker to reduce worker.py to ≤800 LOC.  The *worker*
    argument provides access to the mutable Worker state that tests and callers
    depend on (``_current_id``, ``_current_cancel``, ``_bus``, etc.).  All
    methods on RunExecutor exactly mirror the corresponding Worker methods; Worker
    keeps thin shim wrappers that delegate here.
    """

    def __init__(
        self,
        worker: Any,
        store: TaskStore,
        event_bus: EventBus,
        finalizer: "Finalizer",
        space_store: "SpaceStore | None",
        harness_store: "HarnessStore | None",
        memory_store: Any,
        done_sentinel: dict,
        lease_ttl: float,
        heartbeat_interval: float,
        memory_retrieval: Any,
    ) -> None:
        self._worker = worker
        self.store = store
        self._bus = event_bus
        self._finalizer = finalizer
        self.space_store = space_store
        self.harness_store = harness_store
        self.memory_store = memory_store
        self._done_sentinel = done_sentinel
        self._lease_ttl = lease_ttl
        self._heartbeat_interval = heartbeat_interval
        self._memory_retrieval = memory_retrieval

    @staticmethod
    def _run_agent_fn():
        """Return the run_agent callable from app.worker (supports test-time monkeypatching).

        Tests patch ``app.worker.run_agent`` so we must look it up from that module
        at call time rather than importing it at module load time (which would create
        a separate reference that patches do not reach).
        """
        import app.worker as _wm
        return _wm.run_agent

    @staticmethod
    def _data_dir():
        """Return app.worker.DATA_DIR at call time (supports test-time monkeypatching).

        Tests patch ``app.worker.DATA_DIR`` so we must look it up from that module
        at call time.
        """
        import app.worker as _wm
        return _wm.DATA_DIR

    # Convenience: delegate publish through Worker's thin async wrapper.
    # Must call self._worker._publish (not self._bus.publish directly) so that
    # tests that patch worker._publish can intercept all events.
    async def _publish(self, task_id: str, event: dict) -> None:
        await self._worker._publish(task_id, event)

    # ---- feature decompose ----

    async def run_feature_decompose(self, task_id: str, user_message: str | None = None) -> None:
        """Run the feature-decompose skill for a feature/fix task."""
        task = self.store.get(task_id)
        if task is None:
            log.warning("_run_feature_decompose: unknown task %s", task_id)
            return

        async with bind_run_context(run_id=task_id, task_id=task_id):
            # Call through Worker mangled name so tests can patch _Worker__run_feature_decompose_inner.
            await self._worker._Worker__run_feature_decompose_inner(task_id, user_message, task)

    async def run_feature_decompose_inner(
        self, task_id: str, user_message: str | None, task: Any
    ) -> None:
        from .storage import FEATURE_WORKER_TRANSITIONS
        from .feature_state import FeatureState

        w = self._worker
        w._current_id = task_id
        cancel_event = asyncio.Event()
        w._current_cancel = cancel_event
        self._bus.clear_buffer(task_id)
        started_at = datetime.now(tz=UTC)
        await self._publish(task_id, {"type": "run_start", "task_id": task_id})

        async def on_event(event: dict) -> None:
            await self._publish(task_id, event)

        space = self.space_store.get(task.space_id) if self.space_store else None

        decompose_prompt = (
            "Use the feature-decompose skill to decompose this feature request "
            "into a goal and child tasks.\n\n"
        )
        if user_message:
            decompose_prompt += user_message

        run_exception: str | None = None
        result = None
        try:
            result = await self._run_agent_fn()(
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
            w._current_cancel = None

        ended_at = datetime.now(tz=UTC)
        timestamp = ended_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        if run_exception is not None:
            waiting_question = "Decomposition agent crashed"
            history_entry = (
                f"```\n{timestamp} [agent]\n(agent error: {run_exception})\n```"
            )
            new_task_state = TaskState.WAITING
            new_feature_state = FeatureState.WAITING
        else:
            body = result.final_text.strip() or "(no assistant text)"
            if result.exit_code != 0:
                body += f"\n\n(exit code {result.exit_code}; stderr tail: {result.stderr_tail.strip()})"
            history_entry = f"```\n{timestamp} [agent]\n{body}\n```"

            items: list = []
            try:
                items = await self.store.realizing_items(task_id)
            except Exception:
                log.exception("Failed to fetch realizing_items for %s", task_id)

            if result.status is not None:
                from .agent import Status
                if result.status == Status.DONE and len(items) >= 1:
                    waiting_question = None
                    new_task_state = TaskState.DONE
                    new_feature_state = FeatureState.PLANNED
                elif result.status == Status.DONE and len(items) == 0:
                    waiting_question = "Decomposition agent completed but created no tasks"
                    new_task_state = TaskState.WAITING
                    new_feature_state = FeatureState.WAITING
                elif result.status == Status.WAIT:
                    waiting_question = result.context or "Agent requested human input"
                    new_task_state = TaskState.WAITING
                    new_feature_state = FeatureState.WAITING
                elif result.status == Status.BLOCKED:
                    waiting_question = "Decomposition blocked"
                    new_task_state = TaskState.WAITING
                    new_feature_state = FeatureState.WAITING
                elif result.exit_code != 0:
                    waiting_question = "Decomposition agent crashed"
                    new_task_state = TaskState.WAITING
                    new_feature_state = FeatureState.WAITING
                else:
                    waiting_question = "No STATUS marker from decomposition agent"
                    new_task_state = TaskState.WAITING
                    new_feature_state = FeatureState.WAITING
            elif result.exit_code != 0:
                waiting_question = "Decomposition agent crashed"
                new_task_state = TaskState.WAITING
                new_feature_state = FeatureState.WAITING
            else:
                waiting_question = "No STATUS marker from decomposition agent"
                new_task_state = TaskState.WAITING
                new_feature_state = FeatureState.WAITING

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
        self._bus.drain_subscribers(task_id, self._done_sentinel)

    # ---- harness execution ----

    async def execute_harness_run(
        self,
        task_id: str,
        harness_id: str,
        space_id: str,
        *,
        initial_run: bool,
    ) -> bool:
        """Execute (initial_run=True) or resume (initial_run=False) a harness run."""
        if self.harness_store is None or self.space_store is None:
            return False

        space = self.space_store.get(space_id)
        if space is None:
            log.warning(
                "_execute_harness_run: space %r not found for run %s", space_id, task_id
            )
            return False

        async with bind_run_context(run_id=task_id, task_id=task_id):
            # Call through Worker mangled name so tests can patch _Worker__execute_harness_run_body.
            return await self._worker._Worker__execute_harness_run_body(
                task_id, harness_id, space_id, initial_run=initial_run, space=space
            )

    async def execute_harness_run_body(
        self, task_id: str, harness_id: str, space_id: str, *, initial_run: bool, space: Any
    ) -> bool:
        space_dir = str(self.space_store.spaces_dir / space_id)
        try:
            harness = await self.harness_store.get(space_dir, harness_id)
        except Exception:
            log.exception(
                "Failed to load harness %r for task %s; cannot %s harness run.",
                harness_id, task_id, "start" if initial_run else "resume",
            )
            return False

        from .harnesses.executor import HarnessExecutor
        from .harnesses.adapter import WorkerAdapter
        from .worker import resolve_tool

        def _tools_resolver(space_id: str, agent_ref: str) -> AiToolEntry | None:
            space_claude_dir = self.space_store.spaces_dir / space_id / ".claude"
            global_claude_dir = Path.home() / ".claude"
            return resolve_tool(space_claude_dir, global_claude_dir, agent_ref)

        _adapter = WorkerAdapter(self._worker)
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
            return True

        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        if result_state.waiting_node_id is not None:
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

    async def resume_harness_run(self, task_id: str) -> bool:
        """Resume a WAITING harness run (waiting_node_id is set in run-state)."""
        if self.harness_store is None or self.space_store is None:
            return False

        task = self.store.get(task_id)
        if task is None:
            return False

        run_state_path = (
            self._data_dir() / "spaces" / task.space_id / ".cronos" / "harness-runs" / f"{task_id}.json"
        )
        if not run_state_path.exists():
            return False

        try:
            from .harnesses.run_state import load as load_run_state
            run_state = load_run_state(run_state_path)
        except Exception:
            log.exception("Failed to load harness run state for %s", task_id)
            return False

        if run_state is None or run_state.waiting_node_id is None:
            return False

        async with bind_run_context(run_id=task_id, task_id=task_id):
            return await self._worker._execute_harness_run(
                task_id,
                run_state.harness_id,
                task.space_id,
                initial_run=False,
            )

    async def run_initial_harness_run(self, task_id: str) -> bool:
        """Execute a freshly-triggered harness run for the first time."""
        space_id = self._bus.lookup_space_id(task_id)
        if space_id is None:
            return False

        if self.harness_store is None or self.space_store is None:
            return False

        harness_id: str | None = None
        index_dir = self._data_dir() / "spaces" / space_id / ".cronos" / "harness-runs"
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

        return await self._worker._execute_harness_run(
            task_id,
            harness_id,
            space_id,
            initial_run=True,
        )

    # ---- task run ----

    async def run_task(self, task_id: str, user_message: str | None) -> None:
        task = self.store.get(task_id)
        if task is None:
            log.warning("Skipping unknown task %s", task_id)
            return

        async with bind_run_context(run_id=task_id, task_id=task_id):
            # Call through Worker mangled name so tests can patch _Worker__run_task_body.
            await self._worker._Worker__run_task_body(task_id, user_message, task)

    async def run_task_body(self, task_id: str, user_message: str | None, task: Any) -> None:
        w = self._worker
        handled = await self.resume_harness_run(task_id)
        if handled:
            log.info("Task %s handled as harness resume; skipping run_agent.", task_id)
            await self._publish(task_id, {
                "type": "run_end",
                "task_id": task_id,
                "status": None,
                "new_state": None,
            })
            return

        handled = await self.run_initial_harness_run(task_id)
        if handled:
            log.info("Task %s handled as initial harness run; skipping run_agent.", task_id)
            await self._publish(task_id, {
                "type": "run_end",
                "task_id": task_id,
                "status": None,
                "new_state": None,
            })
            return

        owner = f"{task.space_id}:{w._owner_id}"
        lease_won = self.store.acquire_lease(task_id, owner, ttl=self._lease_ttl)
        if not lease_won:
            log.info(
                "Task %s already leased by another worker; skipping this run", task_id
            )
            return

        w._current_id = task_id
        cancel_event = asyncio.Event()
        w._current_cancel = cancel_event
        self._bus.clear_buffer(task_id)
        started_at = datetime.now(tz=UTC)
        await self._publish(task_id, {"type": "run_start", "task_id": task_id})

        async def on_event(event: dict) -> None:
            await self._publish(task_id, event)

        async def _heartbeat_loop() -> None:
            try:
                while True:
                    await asyncio.sleep(self._heartbeat_interval)
                    self.store.heartbeat_lease(task_id, owner)
            except asyncio.CancelledError:
                pass

        heartbeat_task = asyncio.create_task(_heartbeat_loop(), name=f"hb-{task_id}")

        space = self.space_store.get(task.space_id) if self.space_store else None
        workspace_path = self._data_dir() / task.space_id / CRONOS_SUBDIR / "workspaces" / task.id
        from .worker import _memory_injected_for_workspace
        memory_injected = _memory_injected_for_workspace(workspace_path)
        retrieved_memory = None
        if self.memory_store is not None:
            try:
                retrieved_memory = await self._memory_retrieval.retrieve(
                    task, task.space_id, self.memory_store
                ) or None
            except Exception:
                log.exception("Failed to retrieve memory for %s", task_id)
        run_exception: str | None = None
        result = None
        try:
            result = await self._run_agent_fn()(
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
            w._current_cancel = None
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            self.store.release_lease(task_id, owner)

        if run_exception is not None:
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
            self._bus.drain_subscribers(task_id, self._done_sentinel)
            return

        # Sync space_store/pool from Worker to Finalizer (may be patched in tests).
        self._finalizer.space_store = self.space_store
        self._finalizer.pool = w._pool
        await self._finalizer.finalize(task_id, result, started_at=started_at, memory_injected=memory_injected)

    # ---- goal orchestration ----

    async def run_goal(self, goal_id: str, user_message: str | None) -> None:
        """Orchestrate a goal by running its child tasks sequentially in dep order."""
        goal = self.store.get(goal_id)
        if goal is None:
            log.warning("Skipping unknown goal %s", goal_id)
            return
        if goal.state == TaskState.DONE:
            log.info("Skipping already-done goal %s", goal_id)
            return

        w = self._worker
        w._current_id = goal_id
        cancel_event = asyncio.Event()
        w._current_cancel = cancel_event
        self._bus.clear_buffer(goal_id)
        started_at = datetime.now(tz=UTC)

        await self._publish(goal_id, {"type": "run_start", "task_id": goal_id})

        ordered_child_ids = _topo_children_local(goal_id, self.store)
        goal_context = f"# Goal: {goal.title}\n\n{goal.brief}"

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

                if child.state == TaskState.ACTIVE:
                    failed_child_id = child_id
                    fail_reason = None
                    break
                elif child.state != TaskState.BACKLOG:
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
                            ordered_child_ids = _topo_children_local(goal_id, self.store)
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

                if child.type == "goal":
                    await self._publish(goal_id, {
                        "type": "goal_child_start",
                        "child_id": child_id,
                        "title": child.title,
                    })
                    await self.run_goal(child_id, user_message=None)
                    # Restore parent context overwritten by the recursive call.
                    w._current_id = goal_id
                    w._current_cancel = cancel_event
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

                w._current_child_id = child_id
                self._bus.clear_buffer(child_id)
                await self._publish(child_id, {"type": "run_start", "task_id": child_id})

                async def on_child_event(event: dict, _cid: str = child_id) -> None:
                    await self._publish(_cid, event)
                    await self._publish(goal_id, event)

                space = self.space_store.get(child.space_id) if self.space_store else None
                child_result: AgentResult | None = None
                run_exception: str | None = None
                child_started_at = datetime.now(tz=UTC)
                from .worker import _memory_injected_for_workspace
                child_memory_injected = _memory_injected_for_workspace(
                    self._data_dir() / child.space_id / CRONOS_SUBDIR / "workspaces" / child_id
                )
                child_memory = None
                if self.memory_store is not None:
                    try:
                        child_memory = await self._memory_retrieval.retrieve(
                            child, child.space_id, self.memory_store
                        ) or None
                    except Exception:
                        log.exception("Failed to retrieve memory for child %s", child_id)

                try:
                    child_result = await self._run_agent_fn()(
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

                w._current_child_id = None
                # Sync space_store/pool from Worker to Finalizer (may be patched in tests).
                self._finalizer.space_store = self.space_store
                self._finalizer.pool = w._pool
                child_new_state = await self._finalizer.finalize_child(
                    child_id, child_result, run_exception, started_at=child_started_at,
                    memory_injected=child_memory_injected,
                )

                await self._publish(child_id, {
                    "type": "run_end",
                    "task_id": child_id,
                    "status": child_result.status.value if child_result and child_result.status else None,
                    "new_state": child_new_state.value,
                })
                self._bus.drain_subscribers(child_id, self._done_sentinel)

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
            if fail_reason:
                summary = (
                    f"Paused: {fail_reason} "
                    f"Completed {len(completed)}, skipped {len(skipped)} already-done."
                )
            else:
                summary = (
                    f"Waiting for in-flight child task to complete. "
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

        goal_exit_reason = (
            "STOPPED" if stopped
            else ("DONE" if goal_new_state == TaskState.DONE else "WAITING")
        )
        goal_task = self.store.get(goal_id)
        if goal_task is not None and (w.trace_store is not None or w.stats_store is not None):
            try:
                from .stats import RunStats
                from .trace_parser import RunTrace

                run_index = 0
                if w.stats_store is not None:
                    existing = await w.stats_store.load(goal_task.space_id, goal_id)
                    run_index = len(existing.runs) if existing else 0
                elif w.trace_store is not None:
                    run_index = await w.trace_store.count_runs(goal_task.space_id, goal_id)

                if w.stats_store is not None:
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
                        await w.stats_store.append_run(
                            goal_task.space_id, goal_id, goal_task.title, run_stats
                        )
                    except Exception:
                        log.exception("Failed to save stats for goal %s", goal_id)

                if w.trace_store is not None:
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
                        await w.trace_store.save_run(goal_task.space_id, goal_id, goal_trace)
                    except Exception:
                        log.exception("Failed to save trace for goal %s", goal_id)
            except Exception:
                log.exception("Failed to record telemetry for goal %s", goal_id)

        w._current_cancel = None

        await self._publish(goal_id, {
            "type": "run_end",
            "task_id": goal_id,
            "status": "DONE" if goal_new_state == TaskState.DONE else None,
            "new_state": goal_new_state.value,
        })
        self._bus.drain_subscribers(goal_id, self._done_sentinel)
