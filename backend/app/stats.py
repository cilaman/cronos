from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, computed_field

# ---------------------------------------------------------------------------
# Token pricing table (USD per million tokens, approximate)
# ---------------------------------------------------------------------------

_PRICING: dict[str, dict[str, float]] = {
    "default": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "sonnet":  {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "opus":    {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
    "haiku":   {"input": 0.80, "output": 4.0,  "cache_read": 0.08, "cache_write": 1.0},
}


def _tier_from_real_model(real_model: str | None, configured_model: str) -> str:
    """Map actual model ID to pricing tier, falling back to configured tier."""
    if not real_model:
        return configured_model
    lowered = real_model.lower()
    if "opus" in lowered:
        return "opus"
    if "haiku" in lowered:
        return "haiku"
    if "sonnet" in lowered:
        return "sonnet"
    return configured_model


def compute_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int,
) -> float:
    p = _PRICING.get(model, _PRICING["default"])
    return round(
        input_tokens * p["input"] / 1_000_000
        + output_tokens * p["output"] / 1_000_000
        + cache_read_tokens * p["cache_read"] / 1_000_000
        + cache_creation_tokens * p["cache_write"] / 1_000_000,
        6,
    )


def extract_tokens_and_tools(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Parse stream-json events from a Claude CLI run and extract usage stats."""
    tool_uses: dict[str, int] = {}
    error_count = 0
    real_model: str | None = None

    # Accumulators from assistant events (fallback if no result event)
    asst_input = 0
    asst_output = 0
    asst_cache_read = 0
    asst_cache_creation = 0

    # Authoritative totals from the result event (preferred)
    result_input: int | None = None
    result_output: int | None = None
    result_cache_read: int | None = None
    result_cache_creation: int | None = None

    for event in events:
        if not isinstance(event, dict):
            continue
        etype = event.get("type")

        if etype == "result":
            usage = event.get("usage") or {}
            if usage:
                result_input = usage.get("input_tokens", 0)
                result_output = usage.get("output_tokens", 0)
                result_cache_read = usage.get("cache_read_input_tokens", 0)
                result_cache_creation = usage.get("cache_creation_input_tokens", 0)

        elif etype == "assistant":
            msg = event.get("message") or {}
            if real_model is None:
                real_model = msg.get("model") or None
            usage = msg.get("usage") or {}
            if usage:
                # input_tokens is cumulative per turn; take the max
                asst_input = max(asst_input, usage.get("input_tokens", 0))
                asst_output += usage.get("output_tokens", 0)
                asst_cache_read = max(asst_cache_read, usage.get("cache_read_input_tokens", 0))
                asst_cache_creation = max(asst_cache_creation, usage.get("cache_creation_input_tokens", 0))

            content = msg.get("content") or []
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        name = str(block.get("name") or "unknown")
                        tool_uses[name] = tool_uses.get(name, 0) + 1

        elif etype == "user":
            msg = event.get("message") or {}
            content = msg.get("content") or []
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        if block.get("is_error"):
                            error_count += 1

    return {
        "input_tokens": result_input if result_input is not None else asst_input,
        "output_tokens": result_output if result_output is not None else asst_output,
        "cache_read_tokens": result_cache_read if result_cache_read is not None else asst_cache_read,
        "cache_creation_tokens": result_cache_creation if result_cache_creation is not None else asst_cache_creation,
        "tool_uses": tool_uses,
        "error_count": error_count,
        "real_model": real_model,
    }


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class RunStats(BaseModel):
    run_index: int
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    model: str   # "default" | "sonnet" | "opus" | "haiku"
    real_model: str | None = None  # actual model ID from the API, e.g. "claude-sonnet-4-6-20250620"
    mode: str    # "plan" | "auto" | "ask"
    exit_reason: str  # "DONE" | "WAIT" | "BLOCKED" | "STOPPED" | "CRASHED"
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    tool_uses: dict[str, int] = Field(default_factory=dict)
    error_count: int = 0
    had_crash: bool = False
    memory_hit_rate: float | None = None  # None when no memory was injected


class TaskStats(BaseModel):
    task_id: str
    space_id: str
    title: str
    runs: list[RunStats] = Field(default_factory=list)

    @computed_field
    @property
    def total_runs(self) -> int:
        return len(self.runs)

    @computed_field
    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.runs)

    @computed_field
    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.runs)

    @computed_field
    @property
    def total_cache_tokens(self) -> int:
        return sum(r.cache_read_tokens + r.cache_creation_tokens for r in self.runs)

    @computed_field
    @property
    def total_cost_usd(self) -> float:
        return round(sum(r.cost_usd for r in self.runs), 6)

    @computed_field
    @property
    def total_duration_seconds(self) -> float:
        return sum(r.duration_seconds for r in self.runs)

    @computed_field
    @property
    def tool_use_summary(self) -> dict[str, int]:
        summary: dict[str, int] = {}
        for run in self.runs:
            for tool, count in run.tool_uses.items():
                summary[tool] = summary.get(tool, 0) + count
        return summary

    @computed_field
    @property
    def exit_reason_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for run in self.runs:
            counts[run.exit_reason] = counts.get(run.exit_reason, 0) + 1
        return counts

    @computed_field
    @property
    def avg_tokens_per_run(self) -> float:
        if not self.runs:
            return 0.0
        total = self.total_input_tokens + self.total_output_tokens
        return round(total / len(self.runs), 1)

    @computed_field
    @property
    def crash_rate(self) -> float:
        if not self.runs:
            return 0.0
        crashes = sum(1 for r in self.runs if r.had_crash)
        return round(crashes / len(self.runs), 4)

    @computed_field
    @property
    def avg_memory_hit_rate(self) -> float | None:
        rates = [r.memory_hit_rate for r in self.runs if r.memory_hit_rate is not None]
        if not rates:
            return None
        return round(sum(rates) / len(rates), 4)

    def to_file_dict(self) -> dict[str, Any]:
        """Serialise only stored fields (no computed aggregates) for disk writes."""
        return {
            "task_id": self.task_id,
            "space_id": self.space_id,
            "title": self.title,
            "runs": [r.model_dump(mode="json") for r in self.runs],
        }


class GlobalStats(BaseModel):
    total_tasks_with_stats: int = 0
    total_runs: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0
    tool_use_summary: dict[str, int] = Field(default_factory=dict)
    exit_reason_counts: dict[str, int] = Field(default_factory=dict)
    avg_tokens_per_run: float = 0.0
    avg_memory_hit_rate: float | None = None


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def filter_task_stats(
    ts: TaskStats,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> TaskStats | None:
    """Return a copy of ts with only runs whose started_at falls in [from_dt, to_dt].

    Returns None when the filtered run list is empty (task excluded from aggregations).
    Returns ts unchanged when no filter is specified.
    """
    if from_dt is None and to_dt is None:
        return ts
    from_utc = _to_utc(from_dt) if from_dt is not None else None
    to_utc = _to_utc(to_dt) if to_dt is not None else None
    runs = [
        r for r in ts.runs
        if (from_utc is None or _to_utc(r.started_at) >= from_utc)
        and (to_utc is None or _to_utc(r.started_at) <= to_utc)
    ]
    if not runs:
        return None
    return TaskStats(task_id=ts.task_id, space_id=ts.space_id, title=ts.title, runs=runs)


def aggregate_global(all_stats: list[TaskStats]) -> GlobalStats:
    tool_summary: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    total_tokens = 0
    total_runs = 0
    memory_rates: list[float] = []

    g = GlobalStats(total_tasks_with_stats=len(all_stats))
    for ts in all_stats:
        g.total_runs += ts.total_runs
        g.total_input_tokens += ts.total_input_tokens
        g.total_output_tokens += ts.total_output_tokens
        g.total_cache_tokens += ts.total_cache_tokens
        g.total_cost_usd += ts.total_cost_usd
        g.total_duration_seconds += ts.total_duration_seconds
        for tool, count in ts.tool_use_summary.items():
            tool_summary[tool] = tool_summary.get(tool, 0) + count
        for reason, count in ts.exit_reason_counts.items():
            reason_counts[reason] = reason_counts.get(reason, 0) + count
        total_tokens += ts.total_input_tokens + ts.total_output_tokens
        total_runs += ts.total_runs
        for run in ts.runs:
            if run.memory_hit_rate is not None:
                memory_rates.append(run.memory_hit_rate)

    g.tool_use_summary = tool_summary
    g.exit_reason_counts = reason_counts
    g.total_cost_usd = round(g.total_cost_usd, 6)
    g.avg_tokens_per_run = round(total_tokens / total_runs, 1) if total_runs else 0.0
    g.avg_memory_hit_rate = round(sum(memory_rates) / len(memory_rates), 4) if memory_rates else None
    return g
