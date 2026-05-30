"""Pipeline state writer for CC-v1 pipeline orchestration.

Writes
  {space}/.cronos/pipeline/{goal_slug}/pipeline-state.json
and appends
  {space}/.cronos/pipeline/{goal_slug}/phases-log.jsonl

Metrics (duration_s, token_spend, tool_calls) are sourced from RunTrace objects
rather than from agent-written headers — per the CC-v1 TRACE_OWNED_METRICS split
in ``app.pipeline.contract``.

Usage pattern::

    from app.pipeline.state_writer import (
        init_pipeline, record_phase_log, update_phase, finalize_pipeline,
        PhaseEntry, PhaseMetrics, PhaseVerifyResult,
    )
    from app.trace_parser import RunTrace

    # Phase 0 — create state + empty log
    init_pipeline(space_dir, goal_slug)

    # After each phase completes and the trace is saved:
    trace: RunTrace = ...  # loaded from TraceStore
    metrics = PhaseMetrics.from_trace(trace)
    phase = PhaseEntry(
        phase="scout",
        status="done",
        agent="pipeline-scout",
        task_id=task_id,
        run_index=trace.run_index,
        artifact_path=artifact_path,
        verify_result=PhaseVerifyResult(passed=True, gate_decision="proceed"),
        metrics=metrics,
    )
    update_phase(space_dir, goal_slug, phase)
    record_phase_log(space_dir, goal_slug,
        phase="scout", status="done", gate_decision="proceed",
        task_id=task_id, run_index=trace.run_index)

    # Phase 8 — mark complete
    finalize_pipeline(space_dir, goal_slug, status="completed")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.pipeline.contract import CC_VERSION
from app.trace_parser import RunTrace

PIPELINE_STATE_FILENAME = "pipeline-state.json"
PHASES_LOG_FILENAME = "phases-log.jsonl"

PIPELINE_STATUSES = frozenset({
    "running",
    "completed",
    "failed",
    "escalated",
    "awaiting_approval",
    "cancelled",
})

GATE_DECISIONS = frozenset({"proceed", "retry", "escalate", "fail"})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PhaseMetrics:
    """Per-phase metrics sourced from the run trace (never from the agent artifact)."""
    duration_s: float = 0.0
    token_spend: int = 0
    tool_calls: int = 0
    files_read: int = 0
    memory_hits: int = 0

    @classmethod
    def from_trace(cls, trace: RunTrace) -> PhaseMetrics:
        """Extract phase metrics from a RunTrace.

        token_spend sums all token categories (input, output, cache_read,
        cache_creation) because each contributes to billing.
        memory_hits counts unique memory files actually read during the run.
        """
        token_spend = sum(
            t.input_tokens + t.output_tokens + t.cache_read_tokens + t.cache_creation_tokens
            for t in trace.turns
        )
        return cls(
            duration_s=round(trace.duration_seconds, 2),
            token_spend=token_spend,
            tool_calls=trace.total_tool_calls,
            files_read=trace.read_tool_calls,
            memory_hits=len(trace.memory_used),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_s": self.duration_s,
            "token_spend": self.token_spend,
            "tool_calls": self.tool_calls,
            "files_read": self.files_read,
            "memory_hits": self.memory_hits,
        }


@dataclass
class PhaseVerifyResult:
    """Gate verification result recorded for a phase."""
    passed: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalize_fixes: list[str] = field(default_factory=list)
    gate_decision: str = "fail"
    gate_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "normalize_fixes": list(self.normalize_fixes),
            "gate_decision": self.gate_decision,
            "gate_reason": self.gate_reason,
        }


@dataclass
class PhaseEntry:
    """Full state entry for one pipeline phase to be written into pipeline-state.json."""
    phase: str
    status: str
    agent: str = ""
    task_id: str = ""
    run_index: int = 0
    gate: str = "auto"
    started_at: str = ""
    completed_at: str = ""
    artifact_path: str = ""
    verify_result: PhaseVerifyResult = field(default_factory=PhaseVerifyResult)
    metrics: PhaseMetrics = field(default_factory=PhaseMetrics)
    header_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "status": self.status,
            "agent": self.agent,
            "task_id": self.task_id,
            "run_index": self.run_index,
            "gate": self.gate,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "artifact_path": self.artifact_path,
            "verify_result": self.verify_result.to_dict(),
            "metrics": self.metrics.to_dict(),
            "header_summary": dict(self.header_summary),
        }


# ---------------------------------------------------------------------------
# Telemetry aggregation (recomputed from phases on every write)
# ---------------------------------------------------------------------------

def _compute_telemetry(phases: dict[str, Any]) -> dict[str, Any]:
    """Recompute rolling telemetry by summing metrics across all phases.

    Always recalculated from the full phases dict so repeated updates are
    idempotent (no double-counting risk).
    """
    total_duration_s = 0.0
    total_token_spend = 0
    total_tool_calls = 0
    total_files_read = 0
    total_memory_hits = 0
    phases_completed = 0
    phases_escalated = 0
    phases_retried = 0
    phases_failed = 0

    for phase_data in phases.values():
        m = phase_data.get("metrics", {})
        total_duration_s += m.get("duration_s", 0.0)
        total_token_spend += m.get("token_spend", 0)
        total_tool_calls += m.get("tool_calls", 0)
        total_files_read += m.get("files_read", 0)
        total_memory_hits += m.get("memory_hits", 0)

        gate = phase_data.get("verify_result", {}).get("gate_decision", "")
        if gate == "proceed":
            phases_completed += 1
        elif gate == "escalate":
            phases_escalated += 1
        elif gate == "retry":
            phases_retried += 1
        elif gate == "fail":
            phases_failed += 1

    return {
        "total_duration_s": round(total_duration_s, 2),
        "total_token_spend": total_token_spend,
        "total_tool_calls": total_tool_calls,
        "total_files_read": total_files_read,
        "total_memory_hits": total_memory_hits,
        "phases_completed": phases_completed,
        "phases_escalated": phases_escalated,
        "phases_retried": phases_retried,
        "phases_failed": phases_failed,
    }


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def pipeline_dir(space: str | Path, goal_slug: str) -> Path:
    """Return the pipeline directory for the given goal slug."""
    return Path(space) / ".cronos" / "pipeline" / goal_slug


def state_path(space: str | Path, goal_slug: str) -> Path:
    return pipeline_dir(space, goal_slug) / PIPELINE_STATE_FILENAME


def log_path(space: str | Path, goal_slug: str) -> Path:
    return pipeline_dir(space, goal_slug) / PHASES_LOG_FILENAME


# ---------------------------------------------------------------------------
# Atomic I/O
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_pipeline(
    space: str | Path,
    goal_slug: str,
    *,
    status: str = "running",
    created_at: str | None = None,
    request_text: str | None = None,
) -> dict[str, Any]:
    """Initialise pipeline-state.json and create an empty phases-log.jsonl.

    Must be called exactly once (Phase 0) before any ``update_phase`` or
    ``record_phase_log`` calls for this goal.  Safe to call again — if the
    state file already exists it is overwritten with fresh state.

    Returns the written state dict.
    """
    now = created_at or _iso_now()
    state: dict[str, Any] = {
        "cc_version": CC_VERSION,
        "goal_slug": goal_slug,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "request_text": request_text,
        "phases": {},
        "telemetry": _compute_telemetry({}),
    }

    _atomic_write_json(state_path(space, goal_slug), state)

    lp = log_path(space, goal_slug)
    lp.parent.mkdir(parents=True, exist_ok=True)
    if not lp.exists():
        lp.write_text("", encoding="utf-8")

    return state


def record_phase_log(
    space: str | Path,
    goal_slug: str,
    *,
    phase: str,
    status: str,
    gate_decision: str,
    task_id: str,
    run_index: int,
    timestamp: str | None = None,
) -> None:
    """Append one JSON line to phases-log.jsonl for the completed phase.

    Implements Fix A.4 from the Delivery Notes orchestrator: write only a
    one-line event here instead of re-reading + rewriting the full
    pipeline-state.json after every phase.  Use ``load_last_phase_log()``
    to quickly check "did the previous phase succeed?" without loading the
    full state.
    """
    entry = {
        "phase": phase,
        "status": status,
        "gate_decision": gate_decision,
        "task_id": task_id,
        "run_index": run_index,
        "timestamp": timestamp or _iso_now(),
    }
    lp = log_path(space, goal_slug)
    lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def update_phase(
    space: str | Path,
    goal_slug: str,
    phase: PhaseEntry,
) -> dict[str, Any]:
    """Write or overwrite a phase entry in pipeline-state.json.

    Also recomputes the rolling ``telemetry`` block from all stored phases.
    Raises ``FileNotFoundError`` if ``init_pipeline`` has not been called yet.

    Returns the updated state dict.
    """
    sp = state_path(space, goal_slug)
    if not sp.exists():
        raise FileNotFoundError(
            f"pipeline-state.json not found at {sp}; call init_pipeline first"
        )

    state = json.loads(sp.read_text(encoding="utf-8"))
    state["phases"][phase.phase] = phase.to_dict()
    state["telemetry"] = _compute_telemetry(state["phases"])
    state["updated_at"] = _iso_now()
    _atomic_write_json(sp, state)
    return state


def finalize_pipeline(
    space: str | Path,
    goal_slug: str,
    *,
    status: str = "completed",
) -> dict[str, Any]:
    """Set the top-level pipeline status and do a final write of pipeline-state.json.

    Called at Phase 8 completion, escalation, or failure.
    Raises ``FileNotFoundError`` if ``init_pipeline`` has not been called yet.

    Returns the updated state dict.
    """
    sp = state_path(space, goal_slug)
    if not sp.exists():
        raise FileNotFoundError(
            f"pipeline-state.json not found at {sp}; call init_pipeline first"
        )

    state = json.loads(sp.read_text(encoding="utf-8"))
    state["status"] = status
    state["updated_at"] = _iso_now()
    _atomic_write_json(sp, state)
    return state


def load_state(space: str | Path, goal_slug: str) -> dict[str, Any] | None:
    """Load pipeline-state.json, returning None if it does not exist."""
    sp = state_path(space, goal_slug)
    if not sp.exists():
        return None
    try:
        return json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_last_phase_log(space: str | Path, goal_slug: str) -> dict[str, Any] | None:
    """Return the last entry from phases-log.jsonl, or None if the log is empty.

    Implements the Fix A.4 read pattern: check only the final line instead of
    loading the full pipeline-state.json when verifying the previous phase.
    """
    lp = log_path(space, goal_slug)
    if not lp.exists():
        return None
    try:
        lines = [
            line.strip()
            for line in lp.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return json.loads(lines[-1]) if lines else None
    except Exception:
        return None
