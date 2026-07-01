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
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .agent import AgentResult, CRONOS_SUBDIR
from .delivery_driver import detect_delivery_workflow_spec, run_delivery_goal
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


# ---------------------------------------------------------------------------
# Executor-variant helpers (R10 / R12)
# ---------------------------------------------------------------------------
# RunState.to_dict() uses dataclasses.asdict() which only serialises declared
# fields.  ``executor_variant`` is stored as an extra top-level key in the raw
# JSON rather than as a declared RunState field, so it survives round-trips
# through save_atomic() without requiring a change to run_state.py.
# ---------------------------------------------------------------------------

_EXECUTOR_VARIANT_KEY = "executor_variant"
_DEFAULT_EXECUTOR_VARIANT = "bfs"

# Runner delivery_status values (mirrors lib.delivery_status.DeliveryStatus).
_DELIVERY_STATUSES = ("done", "blocked", "needs_fix", "failed")


def _parse_frontmatter(text: str) -> dict | None:
    """Return the YAML frontmatter dict of a CC-v1 artifact, or None.

    A CC-v1 report starts with a ``---`` fenced YAML block. Kept dependency-light
    (no lib import) so it works wherever run_executor is loaded.
    """
    import yaml

    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        header = yaml.safe_load(parts[1])
    except Exception:
        return None
    return header if isinstance(header, dict) else None


def _cc_delivery_from_report(pipeline_root: Path, since: datetime, produces) -> dict | None:
    """Bridge the newest CC-v1 report under *pipeline_root* into a delivery dict.

    Cronos pipeline agents write ``{phase}-report-{slug}.md`` with a YAML
    frontmatter header (``status``, ``outputs_produced``, and phase-specific
    routing fields like ``has_ui`` / ``verdict`` / ``finding_class``). The runner
    routes on ``<node>.fields.<key>`` and gates on ``artifact_paths`` — so map:
      status          <- header['status']  (done/blocked/needs_fix/failed)
      artifact_paths  <- header['outputs_produced'] (fallback: the report path)
      produces        <- node's produces class
      fields          <- the whole header (so fields.has_ui / fields.verdict work)

    Because the runner dispatches agents sequentially (one at a time via the
    blocking bridge), the newest report modified at/after *since* is this child's.
    Returns None when no fresh report is found (→ adapter falls back to the
    delivery_status fence).
    """
    if not pipeline_root.is_dir():
        return None
    reports = list(pipeline_root.rglob("*.md"))
    if not reports:
        return None
    newest = max(reports, key=lambda p: p.stat().st_mtime)
    # Guard against picking a stale report from an earlier phase/run. Allow a
    # small clock skew margin.
    mtime = datetime.fromtimestamp(newest.stat().st_mtime, tz=UTC)
    if mtime < since - timedelta(seconds=5):
        return None

    header = _parse_frontmatter(newest.read_text(encoding="utf-8", errors="replace"))
    if header is None:
        return None

    status = header.get("status")
    if status not in _DELIVERY_STATUSES:
        status = "done"  # a valid report with an odd/blank status → treat as done

    outputs = header.get("outputs_produced") or []
    if not isinstance(outputs, list) or not outputs:
        outputs = [str(newest)]

    produces_class = ""
    if isinstance(produces, dict):
        produces_class = str(produces.get("class", ""))
    elif produces:
        produces_class = str(produces)

    return {
        "status": status,
        "artifact_paths": [str(p) for p in outputs],
        "produces": produces_class,
        "fields": {k: v for k, v in header.items()},
        "open_questions": list(header.get("blockers") or []),
    }


def _read_executor_variant(run_state_path: Path) -> str:
    """Read the executor variant from the run-state JSON file.

    Returns ``'bfs'`` (backward-compatible default) if:
    - the file does not exist,
    - the file cannot be parsed, or
    - the ``executor_variant`` key is absent (files written before SG5).
    """
    if not run_state_path.exists():
        return _DEFAULT_EXECUTOR_VARIANT
    try:
        with run_state_path.open("r", encoding="utf-8") as fh:
            data = _json.load(fh)
        return str(data.get(_EXECUTOR_VARIANT_KEY, _DEFAULT_EXECUTOR_VARIANT))
    except Exception:
        log.debug(
            "_read_executor_variant: failed to read %s; defaulting to %r",
            run_state_path, _DEFAULT_EXECUTOR_VARIANT,
        )
        return _DEFAULT_EXECUTOR_VARIANT


def _write_executor_variant(
    run_state_path: Path,
    variant: str,
    run_id: str,
    harness_id: str,
) -> None:
    """Persist *variant* as the ``executor_variant`` key in the run-state JSON.

    If the file does not yet exist (initial run before the BFS/runner path has
    created it), this function writes a minimal stub JSON containing only the
    identity fields and the variant.  The BFS/runner path will later overwrite
    the file with a full RunState.

    If the file already exists, the function patches it in-place (read → add
    key → write atomically via os.replace).
    """
    import os as _os
    import tempfile

    run_state_path.parent.mkdir(parents=True, exist_ok=True)

    if run_state_path.exists():
        try:
            with run_state_path.open("r", encoding="utf-8") as fh:
                data = _json.load(fh)
        except Exception:
            log.debug(
                "_write_executor_variant: could not parse %s; creating stub.", run_state_path
            )
            data = {"run_id": run_id, "harness_id": harness_id, "goal_task_id": run_id,
                    "nodes_executed": {}}
    else:
        data = {"run_id": run_id, "harness_id": harness_id, "goal_task_id": run_id,
                "nodes_executed": {}}

    data[_EXECUTOR_VARIANT_KEY] = variant

    payload = _json.dumps(data, indent=2, ensure_ascii=False)
    fd, tmp_path = tempfile.mkstemp(
        dir=run_state_path.parent, prefix=".exec_variant_", suffix=".tmp"
    )
    try:
        with _os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        _os.replace(tmp_path, run_state_path)
    except Exception:
        try:
            _os.unlink(tmp_path)
        except OSError:
            pass
        log.exception("_write_executor_variant: atomic write failed for %s", run_state_path)


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
            assert result is not None
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
        space_store = self.space_store
        harness_store = self.harness_store
        if space_store is None or harness_store is None:
            log.error("execute_harness_run_body: space_store or harness_store not configured")
            return False
        space_dir = str(space_store.spaces_dir / space_id)
        try:
            harness = await harness_store.get(space_dir, harness_id)
        except Exception:
            log.exception(
                "Failed to load harness %r for task %s; cannot %s harness run.",
                harness_id, task_id, "start" if initial_run else "resume",
            )
            return False

        # ------------------------------------------------------------------
        # Executor-variant selection (R10 / R12)
        # ------------------------------------------------------------------
        # The run-state JSON may carry an ``executor_variant`` key written by a
        # prior execution of this function (either 'bfs' or 'runner').  On
        # initial-run path we determine the variant from the env flag and
        # persist it so that a later resume always dispatches to the same path,
        # regardless of the current env-flag value.  On resume path we read the
        # stored variant (NOT the env flag).
        run_state_path = (
            self._data_dir() / "spaces" / space_id / ".cronos" / "harness-runs" / f"{task_id}.json"
        )

        if initial_run:
            import os as _os
            _flag = _os.environ.get("CRONOS_HARNESS_RUNNER", "")
            executor_variant: str = "runner" if _flag == "1" else "bfs"
            # Persist the variant so resume reads it from the stored JSON.
            _write_executor_variant(run_state_path, executor_variant, task_id, harness_id)
            log.info(
                "execute_harness_run_body: initial run %r; executor_variant=%r (CRONOS_HARNESS_RUNNER=%r).",
                task_id, executor_variant, _flag,
            )
        else:
            # Resume: read stored variant from the JSON file.  Default to 'bfs'
            # for backward-compat with files written before SG5.
            executor_variant = _read_executor_variant(run_state_path)
            log.info(
                "execute_harness_run_body: resume run %r; executor_variant=%r (from stored state).",
                task_id, executor_variant,
            )

        # ------------------------------------------------------------------
        # Runner path (CRONOS_HARNESS_RUNNER=1 on initial run, or stored
        # executor_variant == 'runner' on resume)
        # ------------------------------------------------------------------
        if executor_variant == "runner":
            return await self._execute_harness_run_runner(
                task_id, harness_id, space_id, initial_run=initial_run,
                space=space, run_state_path=run_state_path, harness=harness,
            )

        # ------------------------------------------------------------------
        # Default BFS path — old HarnessExecutor preserved verbatim (R12)
        # ------------------------------------------------------------------
        from .harnesses.executor import HarnessExecutor
        from .harnesses.adapter import WorkerAdapter
        from .worker import resolve_tool

        def _tools_resolver(space_id: str, agent_ref: str) -> AiToolEntry | None:
            space_claude_dir = space_store.spaces_dir / space_id / ".claude"
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
            "%s harness run %r (harness=%r) via executor.execute() [bfs].",
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

    async def _execute_harness_run_runner(
        self,
        task_id: str,
        harness_id: str,
        space_id: str,
        *,
        initial_run: bool,
        space: Any,
        run_state_path: Path,
        harness: Any,
    ) -> bool:
        """Execute a harness run via the delivery-workflow runner (R11).

        Called when ``executor_variant == 'runner'``.  Compiles the Harness to
        an IRGraph, constructs a HarnessExecutorAdapter, calls
        ``runner.core.run()``, and maps the resulting WorkflowState back to a
        RunState for finalization.

        The existing BFS HarnessExecutor is NOT touched (R12 — it remains
        importable and unchanged).
        """
        from .harnesses.compiler import compile as compile_harness
        from .harnesses.executor_adapter import HarnessExecutorAdapter
        from .harnesses.run_state import RunState, load as load_run_state, save_atomic
        from .harnesses.state_mapping import workflowstate_to_runstate
        from .harnesses.adapter import WorkerAdapter

        space_store = self.space_store
        assert space_store is not None  # checked by caller

        log.info(
            "%s harness run %r (harness=%r) via runner.core.run() [runner].",
            "Starting" if initial_run else "Resuming",
            task_id,
            harness_id,
        )

        # ------------------------------------------------------------------
        # 1. Load existing RunState (resume) or build a fresh one (initial).
        # ------------------------------------------------------------------
        if run_state_path.exists():
            try:
                base_run_state = load_run_state(run_state_path)
            except Exception:
                log.exception(
                    "_execute_harness_run_runner: failed to load RunState for %s; starting fresh.",
                    task_id,
                )
                base_run_state = None
        else:
            base_run_state = None

        if base_run_state is None:
            base_run_state = RunState(
                run_id=task_id,
                harness_id=harness_id,
                goal_task_id=task_id,
            )

        # ------------------------------------------------------------------
        # 2. Compile Harness → IRGraph (pure, no I/O).
        # ------------------------------------------------------------------
        try:
            ir_graph = compile_harness(harness)
        except Exception:
            log.exception(
                "_execute_harness_run_runner: compile() failed for harness %r run %s.",
                harness_id, task_id,
            )
            return False

        # ------------------------------------------------------------------
        # 3. Build HarnessExecutorAdapter.
        # ------------------------------------------------------------------
        _worker_adapter = WorkerAdapter(self._worker)

        def _publish_cb(tid: str, event: dict) -> None:
            # Fire-and-forget; we're in a sync call from runner.core.run().
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._publish(tid, event))
                else:
                    loop.run_until_complete(self._publish(tid, event))
            except Exception:
                log.debug("_publish_cb: failed to publish event %r for %s", event, tid)

        adapter = HarnessExecutorAdapter(
            worker_adapter=_worker_adapter,
            run_state=base_run_state,
            harness_id=harness_id,
            goal_task_id=task_id,
            publish_cb=_publish_cb,
        )

        # ------------------------------------------------------------------
        # 4. Run the runner (synchronous; runner.core.run() is not async).
        # ------------------------------------------------------------------
        import sys
        import os as _os
        _SPACE_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
        _DW_PKG = _os.path.join(_SPACE_ROOT, "packages", "delivery-workflow")
        if _DW_PKG not in sys.path:
            sys.path.insert(0, _DW_PKG)

        try:
            from runner.core import run as runner_run  # noqa: PLC0415
            workflow_state = runner_run(ir_graph, adapter, state_ops=adapter.state)
        except Exception:
            log.exception(
                "_execute_harness_run_runner: runner.core.run() failed for harness run %s.",
                task_id,
            )
            return True

        # ------------------------------------------------------------------
        # 5. Map WorkflowState → RunState and persist.
        # ------------------------------------------------------------------
        result_run_state = workflowstate_to_runstate(workflow_state, base_run_state)

        try:
            save_atomic(run_state_path, result_run_state)
            # Re-write executor_variant after save_atomic (asdict() doesn't include it).
            _write_executor_variant(run_state_path, "runner", task_id, harness_id)
        except Exception:
            log.exception(
                "_execute_harness_run_runner: failed to persist RunState for %s.", task_id
            )

        # ------------------------------------------------------------------
        # 6. Finalize the Cronos task based on outcome.
        # ------------------------------------------------------------------
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        wf_status = workflow_state.status

        if wf_status == "blocked":
            # Human-wait park: the adapter set waiting_node_id on the run state.
            # Read it back from the persisted state.
            waiting_node_id = result_run_state.waiting_node_id
            log.info(
                "Harness run %r parked at waiting_node_id=%r (runner path).",
                task_id, waiting_node_id,
            )
            history_entry = (
                f"```\n{timestamp} [harness]\n"
                f"Waiting at node: {waiting_node_id}\n```"
            )
            try:
                await self.store.finalize_run(
                    task_id,
                    new_state=TaskState.WAITING,
                    session_id=None,
                    waiting_question=f"Harness waiting at node: {waiting_node_id}",
                    history_entry=history_entry,
                )
            except Exception:
                log.exception("Failed to finalize harness run %s to WAITING (runner)", task_id)
        else:
            log.info("Harness run %r completed with status=%r (runner path).", task_id, wf_status)
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
                log.exception("Failed to finalize harness run %s to DONE (runner)", task_id)

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
        assert result is not None
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

        # ---------------------------------------------------------------
        # Delivery-workflow pre-dispatch: detect sentinel and delegate.
        # ---------------------------------------------------------------
        _spec_path = detect_delivery_workflow_spec(goal.brief or "")
        if _spec_path is not None:
            log.info(
                "run_goal: sentinel detected in goal %s — delegating to delivery_driver",
                goal_id,
            )
            _space_id = goal.space_id
            _space_dir = self.space_store.spaces_dir / _space_id
            _run_dir = _space_dir / CRONOS_SUBDIR / "delivery-runs" / goal_id
            _goal_context = f"# Goal: {goal.title}\n\n{goal.brief}"
            _delivery_error: str | None = None
            try:
                await run_delivery_goal(
                    goal_id=goal_id,
                    spec_path=_spec_path,
                    store=self.store,
                    trace_store=w.trace_store,
                    space_id=_space_id,
                    space_dir=_space_dir,
                    run_dir=_run_dir,
                    run_child=self.run_delivery_child,
                    cancel_event=cancel_event,
                    goal_context=_goal_context,
                )
            except Exception as _exc:
                log.exception("Delivery goal %s failed in run_delivery_goal", goal_id)
                _delivery_error = str(_exc) or _exc.__class__.__name__
            finally:
                # Safety net: the delivery driver is responsible for finalizing the
                # goal (DONE / WAITING).  If it left the goal ACTIVE/BACKLOG — e.g.
                # it raised before finalizing — park it WAITING so the parent goal
                # doesn't report "ended in active state" and the user sees the cause.
                w._current_cancel = None
                goal_after = self.store.get(goal_id)
                goal_state = goal_after.state if goal_after is not None else TaskState.WAITING
                if goal_state in (TaskState.ACTIVE, TaskState.BACKLOG):
                    reason = (
                        f"Delivery workflow error: {_delivery_error}"
                        if _delivery_error
                        else "Delivery workflow ended without finalizing the goal."
                    )
                    try:
                        await self.store.finalize_run(
                            goal_id,
                            new_state=TaskState.WAITING,
                            session_id=None,
                            waiting_question=reason,
                            history_entry=f"[delivery] {reason}",
                        )
                        goal_state = TaskState.WAITING
                    except Exception:
                        log.exception("Failed to park delivery goal %s WAITING", goal_id)
                # Always close the goal's SSE stream so the frontend leaves "Live".
                await self._publish(goal_id, {
                    "type": "run_end",
                    "task_id": goal_id,
                    "status": "DONE" if goal_state == TaskState.DONE else None,
                    "new_state": goal_state.value,
                })
                self._bus.drain_subscribers(goal_id, self._done_sentinel)
            return
        # ---------------------------------------------------------------

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
        elif not ordered_child_ids:
            # Goal has no child tasks at all — do NOT silently mark it DONE.
            # A childless goal that self-completes cascades up a nested-goal tree
            # ("start parent → everything jumps to DONE" without any work).  Park
            # it for attention instead so the user can decompose it.
            goal_new_state = TaskState.WAITING
            goal_waiting_question = (
                "Goal has no child tasks to execute — decompose it into child "
                "tasks (or delete it) before starting."
            )
            summary = "No child tasks to execute — goal parked for decomposition."
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

    # ---- delivery-workflow child execution ----

    async def run_delivery_child(
        self,
        goal_id: str,
        agent_ref: str,
        inputs: dict[str, Any],
        *,
        cancel_event: asyncio.Event,
        goal_context: str,
    ) -> Any:
        """Create and execute one delivery-workflow child task inline.

        This is the delivery-workflow analogue of ``run_goal``'s leaf-child path
        (create → ACTIVE → run agent → finalize).  Unlike the deprecated
        create-and-poll adapter flow, the agent runs *on the current event loop*
        via ``_run_agent_fn``, streaming its output to both the child's and the
        goal's SSE streams.  It is invoked from the delivery runner thread via
        ``asyncio.run_coroutine_threadsafe`` (see ``delivery_driver``), so it is a
        normal coroutine that returns the child's loaded ``RunTrace`` (or ``None``)
        for the adapter to parse the delivery_status fence from.
        """
        from .delivery_driver import DELIVERY_NODE_SENTINEL
        from .worker import _memory_injected_for_workspace

        w = self._worker

        # 1. Build the brief (mirrors the former adapter flow, R8 sentinel) and
        #    create the child task.
        artifact_lines = "\n".join(
            f"- {p}" for p in inputs.get("artifact_paths", [])
        )
        node_id = inputs.get("node_id", agent_ref)
        sentinel = DELIVERY_NODE_SENTINEL.format(node_id=node_id)
        brief = f"# Agent: {agent_ref}\n\n{artifact_lines}\n\n{sentinel}".strip()
        depends_on = inputs.get("depends_on") or None

        goal = self.store.get(goal_id)
        if goal is None:
            log.error("run_delivery_child: goal %s not found; cannot create child", goal_id)
            return None
        space_id = goal.space_id

        child = await self.store.create(
            space_id=space_id,
            title=f"[delivery] {agent_ref}",
            brief=brief,
            type="task",
            parent_id=goal_id,
            depends_on=list(depends_on) if depends_on else None,
        )
        child_id = child.id

        await self._publish(goal_id, {
            "type": "goal_child_start",
            "child_id": child_id,
            "title": child.title,
        })

        # 2. Transition the child BACKLOG → ACTIVE (no-op if already active).
        try:
            await self.store.transition(child_id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
        except InvalidTransition:
            log.debug("run_delivery_child: child %s already active or non-startable", child_id)

        child = self.store.get(child_id)
        if child is None:
            await self._publish(goal_id, {
                "type": "goal_child_end",
                "child_id": child_id,
                "title": f"[delivery] {agent_ref}",
                "new_state": TaskState.WAITING.value,
            })
            return None

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
                log.exception("Failed to retrieve memory for delivery child %s", child_id)

        # 3. Run the agent (unless already cancelled).
        if cancel_event.is_set():
            run_exception = "cancelled before start"
        else:
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
                log.exception("Agent error on delivery child %s", child_id)

        w._current_child_id = None
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

        # 4. Load the child's trace (telemetry) and derive the node result.
        #    Cronos CC-v1 agents emit a YAML-frontmatter report artifact (status,
        #    outputs_produced, has_ui/verdict/… fields) — NOT a delivery_status
        #    JSON fence.  Bridge that frontmatter into the runner's expected shape
        #    here; the adapter falls back to delivery_status-fence parsing when no
        #    CC-v1 report is found (non-CC-v1 agents).
        trace = None
        if w.trace_store is not None:
            try:
                trace = await w.trace_store.load_latest(child.space_id, child_id)
            except Exception:
                log.exception("Failed to load trace for delivery child %s", child_id)

        delivery = None
        try:
            _spaces_dir = getattr(self.space_store, "spaces_dir", None)
            if _spaces_dir is not None:
                # CC-v1 agents may write to either .cronos/pipeline/ (classic path)
                # or .cronos/delivery/ (delivery-workflow context). Try both.
                #
                # For .cronos/pipeline/ the staleness guard (mtime >= child_started_at)
                # is appropriate because that dir holds reports from many pipeline runs.
                #
                # For .cronos/delivery/ the dir is per-slug (not per-run), so a valid
                # report written by any previous run of the same goal is usable — pass
                # epoch as 'since' to bypass the staleness guard.
                pipeline_root = Path(_spaces_dir) / child.space_id / CRONOS_SUBDIR / "pipeline"
                delivery = _cc_delivery_from_report(
                    pipeline_root, child_started_at, inputs.get("produces")
                )
                if delivery is None:
                    delivery_root = Path(_spaces_dir) / child.space_id / CRONOS_SUBDIR / "delivery"
                    delivery = _cc_delivery_from_report(
                        delivery_root, datetime.fromtimestamp(0, tz=UTC), inputs.get("produces")
                    )
        except Exception:
            log.exception("Failed to derive CC-v1 delivery result for child %s", child_id)

        return {"trace": trace, "delivery": delivery}
