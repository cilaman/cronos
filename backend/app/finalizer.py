"""backend/app/finalizer.py — Post-run state machine for agent runs.

Extracted from Worker._finalize and Worker._finalize_child.
Finalizer takes stores + callbacks at init and exposes two async methods.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Callable

from . import autopilot_pr
from . import feature_sync
from . import goal_sync
from .agent import AgentResult, Status
from .models import TaskState
from .notifier import notify_state_change
from .run_side_effects import RunSideEffects
from .stats import extract_tokens_and_tools
from .storage import TaskStore
from .trace_parser import RunTrace

if TYPE_CHECKING:
    from .event_bus import EventBus
    from .space_storage import SpaceStore
    from .worker_pool import WorkerPool

# Use the same logger as worker.py to maintain backward-compat with tests
# that check for specific logger names (e.g. "cronos.worker").
log = logging.getLogger("cronos.worker")


def _crash_waiting_question(exit_code: int) -> str:
    """Human-facing WAITING reason for a crashed run.

    A ``-9`` (SIGKILL) is almost always the container/cgroup OOM-killer reaping
    the run (Opus + bundled Node + any test subprocess), so surface an
    actionable OOM-specific message instead of the generic crash text.
    """
    if exit_code == -9:
        return (
            "Agent was killed (SIGKILL / exit -9) — almost certainly out of "
            "memory. Lower CRONOS_MAX_CONCURRENT_AGENTS or raise the container "
            "mem_limit/swap, then resume."
        )
    return f"Agent crashed with exit code {exit_code}."


def _parse_merge_meta(brief: str) -> dict | None:
    """Extract merge metadata from a task brief (re-import from worker to avoid circular)."""
    import re
    _MERGE_META_RE = re.compile(
        r"<!--\s*merge-meta\s*\n"
        r"space_id:\s*(?P<space_id>\S+)\s*\n"
        r"kind:\s*(?P<kind>\S+)\s*\n"
        r"name:\s*(?P<name>\S+)\s*\n"
        r"upstream_source_sha:\s*(?P<upstream_source_sha>\S+)\s*\n"
        r"-->",
        re.MULTILINE,
    )
    m = _MERGE_META_RE.search(brief)
    return m.groupdict() if m is not None else None


def _extract_subagent_types(events: list[dict]) -> list[str]:
    """Return ordered-unique lowercase subagent types from Agent tool calls."""
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


class Finalizer:
    """Post-run state machine extracted from Worker._finalize and _finalize_child.

    Handles state transitions, notifications, hooks, telemetry, and SSE drain
    after each agent run completes.
    """

    def __init__(
        self,
        store: TaskStore,
        event_bus: "EventBus",
        side_effects: RunSideEffects,
        space_store: "SpaceStore | None",
        pool: "WorkerPool | None",
        on_task_state_change: Callable | None,
        auto_resume_counts: dict,
        enqueue_fn: Callable,
        done_sentinel: dict,
    ) -> None:
        self.store = store
        self.event_bus = event_bus
        self.side_effects = side_effects
        self.space_store = space_store
        self.pool = pool
        self._on_task_state_change = on_task_state_change
        self._auto_resume_counts = auto_resume_counts
        self._enqueue_fn = enqueue_fn
        self._done_sentinel = done_sentinel

    async def finalize(
        self,
        task_id: str,
        result: AgentResult,
        *,
        started_at: datetime | None = None,
        memory_injected: list[str] | None = None,
    ) -> None:
        """Post-run state machine for a regular task (non-goal, non-child).

        Handles: state determination, finalize_run, notifications, on_task_state_change
        callback, autopilot_pr, merge hooks, goal_sync, feature_sync, telemetry,
        auto-resume, SSE drain, and pending message drain.
        """
        from .stats import RunStats

        ended_at = datetime.now(tz=UTC)
        timestamp = ended_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Pre-fetch task and extract usage early to build history entry with agent metadata.
        task_pre = self.store.get(task_id)
        usage = extract_tokens_and_tools(result.raw_events)
        real_model = usage["real_model"]

        # Determine run index before persisting so the history entry is accurate.
        run_index = 0
        if self.side_effects.stats_store is not None and task_pre is not None:
            existing = await self.side_effects.stats_store.load(task_pre.space_id, task_id)
            run_index = len(existing.runs) if existing else 0
        elif self.side_effects.trace_store is not None and task_pre is not None:
            run_index = await self.side_effects.trace_store.count_runs(task_pre.space_id, task_id)

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
            waiting_question: str | None = "Stopped by user."
        elif result.status == Status.DONE:
            new_state = TaskState.DONE
            waiting_question = None
        elif result.exit_code != 0:
            new_state = TaskState.WAITING
            waiting_question = _crash_waiting_question(result.exit_code)
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

        # Fire-and-forget push notification.
        if new_state in (TaskState.DONE, TaskState.WAITING):
            title = task_pre.title if task_pre is not None else task_id
            asyncio.create_task(
                notify_state_change(
                    task_id=task_id,
                    task_title=title,
                    status=new_state.value,
                    exit_reason=result.status.value if result and result.status else None,
                    summary=waiting_question,
                ),
                name=f"notify-{task_id}",
            )

        # on_task_state_change callback (DONE transitions only).
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
                log.exception("on_task_state_change callback failed for task %s", task_id)

        # autopilot_pr hook.
        if new_state == TaskState.DONE and self.space_store is not None:
            task_done = self.store.get(task_id)
            space_for_pr = self.space_store.get(task_done.space_id) if task_done else None
            if task_done is not None and space_for_pr is not None:
                try:
                    pr_result = await autopilot_pr.run_post_done_flow(
                        task_done, space_for_pr, self.store
                    )
                    if pr_result.pr_url:
                        self.event_bus.publish(task_id, {"type": "pr_opened", "pr_url": pr_result.pr_url})
                    elif pr_result.proposed_pr_path:
                        self.event_bus.publish(task_id, {"type": "pr_opened", "proposed_pr_path": pr_result.proposed_pr_path})
                except Exception:
                    log.exception("autopilot_pr: post-DONE flow failed for %s", task_id)

        # Adopted-tool merge hook.
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
                    except Exception as exc:
                        from .tools.adoption import NotAdopted
                        if isinstance(exc, NotAdopted):
                            log.warning(
                                "finalize_merge: %s/%s not adopted in space %s",
                                meta["kind"], meta["name"], meta["space_id"],
                            )
                        else:
                            log.exception("finalize_merge failed for task %s", task_id)

        # Goal / feature propagation.
        try:
            await goal_sync.propagate_to_parent(task_id, self.store, self.pool)
        except Exception:
            log.exception("Failed to propagate state to parent goal for %s", task_id)

        try:
            await feature_sync.propagate_to_feature(task_id, self.store, self.pool)
        except Exception:
            log.exception("feature_sync.propagate_to_feature failed for task_id=%s", task_id)

        exit_reason = (
            "STOPPED" if result.stopped
            else (result.status.value if result.status else
                  ("CRASHED" if result.exit_code != 0 else "NO_CRONOS_STATUS"))
        )

        # Telemetry.
        task_for_telemetry = self.store.get(task_id)
        if task_for_telemetry is not None:
            await self.side_effects.record_telemetry(
                task_id=task_id,
                space_id=task_for_telemetry.space_id,
                result=result,
                started_at=started_at or ended_at,
                ended_at=ended_at,
                exit_reason=exit_reason,
                memory_injected=memory_injected,
                run_index=run_index,
                real_model=real_model,
                usage=usage,
            )
            await self.side_effects.save_memory_blocks(
                task_id=task_id,
                final_text=result.final_text or "",
                run_index=run_index,
            )
            await self.side_effects.save_cronos_remember_blocks(
                result.final_text or "",
                space_id=task_for_telemetry.space_id,
                sources=[f"task:{task_id}", f"run:{run_index}"],
                log_id=task_id,
            )

        # Auto-resume logic.
        _MAX_AUTO_RESUMES = 3
        if (
            result.exit_code == 0
            and result.status is None
            and result.result_subtype == "error_max_turns"
            and not result.stopped
            and self._auto_resume_counts.get(task_id, 0) < _MAX_AUTO_RESUMES
        ):
            new_count = self._auto_resume_counts.get(task_id, 0) + 1
            self._auto_resume_counts[task_id] = new_count
            try:
                self.store.upsert_auto_resume_count(task_id, new_count)
            except Exception:
                log.exception("Failed to persist auto_resume_count for %s", task_id)
            log.info(
                "Auto-resuming %s after max-turns exit (attempt %d/%d)",
                task_id, new_count, _MAX_AUTO_RESUMES,
            )
            try:
                await self.store.resume_with_message(task_id)
                await self._enqueue_fn(task_id, user_message="Continue where you left off.")
            except Exception:
                log.exception("Failed to auto-resume %s after max-turns", task_id)
        else:
            self._auto_resume_counts.pop(task_id, None)
            try:
                self.store.delete_auto_resume_count(task_id)
            except Exception:
                log.exception("Failed to delete auto_resume_count for %s", task_id)

        self.event_bus.publish(
            task_id,
            {
                "type": "run_end",
                "task_id": task_id,
                "status": result.status.value if result.status else None,
                "new_state": new_state.value,
            },
        )
        # Drain SSE subscribers.
        self.event_bus.drain_subscribers(task_id, self._done_sentinel)

        # Flush pending messages as a new turn.
        try:
            pending = await self.store.drain_pending(task_id)
        except Exception:
            log.exception("Failed to drain pending messages for %s", task_id)
            pending = []
        if pending and not result.stopped:
            combined = "\n\n".join(pending)
            try:
                await self.store.resume_with_message(task_id)
            except Exception:
                log.exception("Failed to resume %s for pending messages", task_id)
                return
            await self._enqueue_fn(task_id, user_message=combined)

    async def finalize_child(
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
                waiting_question = _crash_waiting_question(result.exit_code)
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

        # Telemetry.
        if result is not None:
            child_task = self.store.get(child_id)
            if child_task is not None:
                exit_reason_child = (
                    "STOPPED" if result.stopped
                    else (result.status.value if result.status else
                          ("CRASHED" if result.exit_code != 0 else "NO_CRONOS_STATUS"))
                )
                usage_child = extract_tokens_and_tools(result.raw_events)
                run_index_child = 0
                if self.side_effects.stats_store is not None:
                    try:
                        existing = await self.side_effects.stats_store.load(child_task.space_id, child_id)
                        run_index_child = len(existing.runs) if existing else 0
                    except Exception:
                        pass
                elif self.side_effects.trace_store is not None:
                    try:
                        run_index_child = await self.side_effects.trace_store.count_runs(child_task.space_id, child_id)
                    except Exception:
                        pass

                await self.side_effects.record_telemetry(
                    task_id=child_id,
                    space_id=child_task.space_id,
                    result=result,
                    started_at=started_at,
                    ended_at=ended_at,
                    exit_reason=exit_reason_child,
                    memory_injected=memory_injected,
                    run_index=run_index_child,
                    real_model=usage_child["real_model"],
                    usage=usage_child,
                )
                await self.side_effects.save_memory_blocks(
                    task_id=child_id,
                    final_text=result.final_text or "",
                    run_index=run_index_child,
                )
                await self.side_effects.save_cronos_remember_blocks(
                    result.final_text or "",
                    space_id=child_task.space_id,
                    sources=[f"task:{child_id}"],
                    log_id=child_id,
                )

        return new_state
