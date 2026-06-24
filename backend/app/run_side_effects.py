"""backend/app/run_side_effects.py — Stats, trace, and memory recording for agent runs.

Extracted from Worker._finalize and Worker._finalize_child.
RunSideEffects is a stateless helper: it takes store references at __init__
and records telemetry after each agent run.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger("cronos.run_side_effects")


class RunSideEffects:
    """Records run statistics, traces, and memory items after an agent run completes.

    Accepted stores may be None — RunSideEffects skips the corresponding recording
    gracefully in that case.
    """

    def __init__(self, stats_store, trace_store, memory_store, store) -> None:
        self.stats_store = stats_store
        self.trace_store = trace_store
        self.memory_store = memory_store
        self.store = store

    async def record_telemetry(
        self,
        task_id: str,
        space_id: str,
        result: Any,
        started_at: datetime,
        ended_at: datetime,
        exit_reason: str,
        memory_injected: list[str] | None,
        run_index: int,
        real_model: str | None,
        usage: dict,
    ) -> None:
        """Record run statistics and trace for a completed agent run.

        Extracts the trace, builds RunStats, appends to stats_store, and saves
        to trace_store.  All errors are caught and logged without propagating.
        """
        from .stats import (
            RunStats,
            _tier_from_real_model,
            compute_adopted_tool_uses,
            compute_cost,
        )
        from .trace_parser import extract_run_trace

        task = self.store.get(task_id)
        if task is None:
            return

        # Pre-compute run trace for memory_hit_rate, adopted_tool_uses, or saving.
        computed_trace = None
        if self.trace_store is not None or bool(memory_injected) or self.stats_store is not None:
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
                    started_at=started_at,
                    ended_at=ended_at,
                    exit_reason=exit_reason,
                    session_id=result.session_id,
                    had_crash=result.exit_code != 0 and not result.stopped,
                    memory_injected=memory_injected or [],
                    adopted_index=adopted_idx or None,
                )
            except Exception:
                log.exception("Failed to compute trace for %s", task_id)

        # Persist run statistics.
        if self.stats_store is not None:
            try:
                _started = started_at
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

        # Persist run trace.
        if self.trace_store is not None and computed_trace is not None:
            try:
                await self.trace_store.save_run(task.space_id, task_id, computed_trace)
            except Exception:
                log.exception("Failed to save trace for %s", task_id)

    async def save_memory_blocks(
        self,
        task_id: str,
        final_text: str,
        run_index: int,
    ) -> None:
        """Parse MEMORY: blocks from *final_text* and persist as unconfirmed items."""
        from .memory_parser import parse_memory_blocks

        if self.memory_store is None or not final_text:
            return
        blocks = parse_memory_blocks(final_text)
        if not blocks:
            return
        task = self.store.get(task_id)
        if task is None:
            return
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

    async def save_cronos_remember_blocks(
        self,
        final_text: str,
        *,
        space_id: str,
        sources: list[str],
        log_id: str,
    ) -> None:
        """Parse CRONOS_REMEMBER blocks from *final_text* and persist as unconfirmed items.

        Field mapping (design R3): name->title, type->kind, description+body->body,
        metadata->links=[json.dumps(metadata)].
        """
        from .memory_parser import parse_cronos_remember_blocks

        if self.memory_store is None or not final_text:
            return
        cr_blocks = parse_cronos_remember_blocks(final_text)
        for block in cr_blocks:
            try:
                body = (
                    f"{block.description}\n\n{block.body}" if block.body else block.description
                )
                links = [json.dumps(block.metadata)] if block.metadata else []
                await self.memory_store.create(
                    scope=f"space:{space_id}",
                    kind=block.type,
                    title=block.name,
                    body=body,
                    confirmed=False,
                    sources=sources,
                    links=links,
                )
            except Exception:
                log.exception("Failed to save CRONOS_REMEMBER block for %s", log_id)
