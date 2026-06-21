"""backend/app/harnesses/adapter.py — WorkerAdapter bridging Worker to HarnessExecutor.

Extracted from ``worker._WorkerProtocolAdapter``.  This module MUST NOT import
from ``app.worker`` to avoid circular imports at module load time.  Instead it
uses duck-typing: it accesses the worker object's public attributes and the
``worker._bus.publish`` callable at call time.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime as _dt
from typing import TYPE_CHECKING, Any

from ..agent import AgentResult, run_agent
from ..models import TaskState
from ..notifier import notify_state_change
from ..trace_parser import RunTrace

if TYPE_CHECKING:
    pass  # No Worker import — duck-typed at runtime.

log = logging.getLogger("cronos.harnesses.adapter")


class WorkerAdapter:
    """Adapts a Worker instance to satisfy harnesses.executor.WorkerProtocol.

    The HarnessExecutor requires a WorkerProtocol object with ``run_agent``,
    ``finalize_child``, and ``_publish`` methods.  This adapter bridges to the
    real Worker without causing a circular import.  It is used inside
    Worker.__execute_harness_run_body.

    The *worker* argument is typed ``Any`` to avoid importing Worker; at
    runtime it must expose:
      - ``worker.store``
      - ``worker.space_store``
      - ``worker._bus.publish(task_id, event)``
    """

    def __init__(self, worker: Any) -> None:
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
            exit_reason=result.status.value if result.status else "NO_CRONOS_STATUS",
            final_text_snippet=(result.final_text or "")[:500],
            parent_run_id=kwargs.get("parent_run_id"),
        )

    async def finalize_child(self, task_id: str, trace: RunTrace) -> TaskState:
        """Finalize a harness child task and return its new TaskState.

        Uses the trace's exit_reason to determine success (DONE) vs failure.
        """
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
            log.exception("WorkerAdapter.finalize_child failed for %s", task_id)

        # Fire-and-forget notification on WAITING (needs-human) transitions.
        if new_state == TaskState.WAITING:
            task_obj = self._worker.store.get(task_id)
            title = task_obj.title if task_obj is not None else task_id
            asyncio.create_task(
                notify_state_change(
                    task_id=task_id,
                    task_title=title,
                    status=new_state.value,
                    exit_reason=trace.exit_reason,
                    summary=waiting_question,
                ),
                name=f"notify-child-{task_id}",
            )

        return new_state

    def _publish(self, task_id: str, event: dict) -> None:
        """Sync bridge to Worker._bus.publish (WorkerProtocol._publish is sync)."""
        self._worker._bus.publish(task_id, event)
