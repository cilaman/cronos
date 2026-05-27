from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.stats import (
    GlobalStats,
    RunStats,
    TaskStats,
    aggregate_global,
    compute_cost,
    extract_tokens_and_tools,
)
from app.stats_store import StatsStore

from .conftest import SPACE_ID


# ---------------------------------------------------------------------------
# compute_cost
# ---------------------------------------------------------------------------


def test_compute_cost_default_model():
    cost = compute_cost("default", 1_000_000, 0, 0, 0)
    assert cost == pytest.approx(3.0, rel=1e-6)


def test_compute_cost_output_tokens():
    cost = compute_cost("default", 0, 1_000_000, 0, 0)
    assert cost == pytest.approx(15.0, rel=1e-6)


def test_compute_cost_opus():
    cost = compute_cost("opus", 1_000_000, 1_000_000, 0, 0)
    assert cost == pytest.approx(90.0, rel=1e-6)  # 15 + 75


def test_compute_cost_haiku():
    cost = compute_cost("haiku", 1_000_000, 1_000_000, 0, 0)
    assert cost == pytest.approx(4.8, rel=1e-6)  # 0.8 + 4.0


def test_compute_cost_cache_read():
    cost = compute_cost("default", 0, 0, 1_000_000, 0)
    assert cost == pytest.approx(0.30, rel=1e-6)


def test_compute_cost_cache_creation():
    cost = compute_cost("default", 0, 0, 0, 1_000_000)
    assert cost == pytest.approx(3.75, rel=1e-6)


def test_compute_cost_zero():
    assert compute_cost("default", 0, 0, 0, 0) == 0.0


def test_compute_cost_unknown_model_falls_back_to_default():
    cost_unknown = compute_cost("unknown-model", 1_000_000, 0, 0, 0)
    cost_default = compute_cost("default", 1_000_000, 0, 0, 0)
    assert cost_unknown == cost_default


# ---------------------------------------------------------------------------
# extract_tokens_and_tools
# ---------------------------------------------------------------------------


def _make_assistant_event(
    model: str = "claude-sonnet-4-6",
    input_tokens: int = 100,
    output_tokens: int = 50,
    tool_names: list[str] | None = None,
) -> dict:
    content = []
    if tool_names:
        for name in tool_names:
            content.append({"type": "tool_use", "name": name, "id": "tu-1", "input": {}})
    return {
        "type": "assistant",
        "message": {
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            "content": content,
        },
    }


def _make_result_event(
    input_tokens: int = 200,
    output_tokens: int = 80,
    cache_read: int = 0,
    cache_creation: int = 0,
) -> dict:
    return {
        "type": "result",
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_creation,
        },
    }


def _make_tool_error_event() -> dict:
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "is_error": True, "tool_use_id": "tu-1"}
            ]
        },
    }


def test_extract_tokens_prefers_result_event():
    events = [
        _make_assistant_event(input_tokens=100, output_tokens=50),
        _make_result_event(input_tokens=200, output_tokens=80),
    ]
    result = extract_tokens_and_tools(events)
    assert result["input_tokens"] == 200
    assert result["output_tokens"] == 80


def test_extract_tokens_falls_back_to_assistant():
    events = [_make_assistant_event(input_tokens=100, output_tokens=50)]
    result = extract_tokens_and_tools(events)
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 50


def test_extract_tokens_accumulates_output_across_turns():
    events = [
        _make_assistant_event(input_tokens=100, output_tokens=30),
        _make_assistant_event(input_tokens=100, output_tokens=40),
    ]
    result = extract_tokens_and_tools(events)
    # output is accumulated, input takes the max
    assert result["output_tokens"] == 70
    assert result["input_tokens"] == 100


def test_extract_tool_uses():
    events = [
        _make_assistant_event(tool_names=["Read", "Read", "Write"]),
    ]
    result = extract_tokens_and_tools(events)
    assert result["tool_uses"]["Read"] == 2
    assert result["tool_uses"]["Write"] == 1


def test_extract_error_count():
    events = [
        _make_assistant_event(tool_names=["Read"]),
        _make_tool_error_event(),
        _make_tool_error_event(),
    ]
    result = extract_tokens_and_tools(events)
    assert result["error_count"] == 2


def test_extract_real_model():
    events = [_make_assistant_event(model="claude-sonnet-4-6-20250620")]
    result = extract_tokens_and_tools(events)
    assert result["real_model"] == "claude-sonnet-4-6-20250620"


def test_extract_empty_events():
    result = extract_tokens_and_tools([])
    assert result["input_tokens"] == 0
    assert result["output_tokens"] == 0
    assert result["tool_uses"] == {}
    assert result["error_count"] == 0


def test_extract_ignores_non_dict():
    result = extract_tokens_and_tools(["not-a-dict", 42, None])
    assert result["input_tokens"] == 0


# ---------------------------------------------------------------------------
# TaskStats aggregations
# ---------------------------------------------------------------------------


def _make_run(
    run_index: int = 0,
    input_tokens: int = 1000,
    output_tokens: int = 500,
    cost_usd: float = 0.01,
    had_crash: bool = False,
    exit_reason: str = "DONE",
    tool_uses: dict | None = None,
    duration: float = 60.0,
    memory_hit_rate: float | None = None,
) -> RunStats:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    return RunStats(
        run_index=run_index,
        started_at=now,
        ended_at=now,
        duration_seconds=duration,
        model="default",
        mode="auto",
        exit_reason=exit_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        had_crash=had_crash,
        tool_uses=tool_uses or {},
        memory_hit_rate=memory_hit_rate,
    )


def test_task_stats_total_runs():
    ts = TaskStats(
        task_id="t1",
        space_id=SPACE_ID,
        title="T",
        runs=[_make_run(0), _make_run(1)],
    )
    assert ts.total_runs == 2


def test_task_stats_total_cost():
    ts = TaskStats(
        task_id="t1",
        space_id=SPACE_ID,
        title="T",
        runs=[_make_run(cost_usd=0.01), _make_run(cost_usd=0.02)],
    )
    assert ts.total_cost_usd == pytest.approx(0.03, rel=1e-6)


def test_task_stats_crash_rate():
    ts = TaskStats(
        task_id="t1",
        space_id=SPACE_ID,
        title="T",
        runs=[_make_run(had_crash=True), _make_run(had_crash=False)],
    )
    assert ts.crash_rate == pytest.approx(0.5, rel=1e-6)


def test_task_stats_avg_tokens_per_run():
    ts = TaskStats(
        task_id="t1",
        space_id=SPACE_ID,
        title="T",
        runs=[_make_run(input_tokens=1000, output_tokens=500)],
    )
    assert ts.avg_tokens_per_run == pytest.approx(1500.0, rel=1e-6)


def test_task_stats_tool_use_summary():
    ts = TaskStats(
        task_id="t1",
        space_id=SPACE_ID,
        title="T",
        runs=[
            _make_run(tool_uses={"Read": 2, "Write": 1}),
            _make_run(tool_uses={"Read": 3}),
        ],
    )
    assert ts.tool_use_summary["Read"] == 5
    assert ts.tool_use_summary["Write"] == 1


def test_task_stats_exit_reason_counts():
    ts = TaskStats(
        task_id="t1",
        space_id=SPACE_ID,
        title="T",
        runs=[
            _make_run(exit_reason="DONE"),
            _make_run(exit_reason="DONE"),
            _make_run(exit_reason="WAIT"),
        ],
    )
    assert ts.exit_reason_counts["DONE"] == 2
    assert ts.exit_reason_counts["WAIT"] == 1


def test_task_stats_empty():
    ts = TaskStats(task_id="t1", space_id=SPACE_ID, title="T")
    assert ts.total_runs == 0
    assert ts.avg_tokens_per_run == 0.0
    assert ts.crash_rate == 0.0


def test_task_stats_to_file_dict_excludes_computed():
    ts = TaskStats(
        task_id="t1",
        space_id=SPACE_ID,
        title="T",
        runs=[_make_run()],
    )
    d = ts.to_file_dict()
    assert "task_id" in d
    assert "runs" in d
    assert "total_runs" not in d


def test_run_stats_memory_hit_rate_none_by_default():
    run = _make_run()
    assert run.memory_hit_rate is None


def test_run_stats_memory_hit_rate_stored():
    run = _make_run(memory_hit_rate=0.75)
    assert run.memory_hit_rate == pytest.approx(0.75)


def test_task_stats_avg_memory_hit_rate_none_when_no_memory():
    ts = TaskStats(
        task_id="t1",
        space_id=SPACE_ID,
        title="T",
        runs=[_make_run(), _make_run()],
    )
    assert ts.avg_memory_hit_rate is None


def test_task_stats_avg_memory_hit_rate_excludes_none_runs():
    ts = TaskStats(
        task_id="t1",
        space_id=SPACE_ID,
        title="T",
        runs=[
            _make_run(memory_hit_rate=0.8),
            _make_run(memory_hit_rate=None),  # no memory active
            _make_run(memory_hit_rate=0.6),
        ],
    )
    # Average of 0.8 and 0.6 only
    assert ts.avg_memory_hit_rate == pytest.approx(0.7, rel=1e-4)


def test_task_stats_avg_memory_hit_rate_single_run():
    ts = TaskStats(
        task_id="t1",
        space_id=SPACE_ID,
        title="T",
        runs=[_make_run(memory_hit_rate=1.0)],
    )
    assert ts.avg_memory_hit_rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# aggregate_global
# ---------------------------------------------------------------------------


def test_aggregate_global_empty():
    g = aggregate_global([])
    assert g.total_tasks_with_stats == 0
    assert g.total_runs == 0
    assert g.avg_tokens_per_run == 0.0


def test_aggregate_global_sums_costs():
    ts1 = TaskStats(
        task_id="t1", space_id=SPACE_ID, title="T1",
        runs=[_make_run(cost_usd=0.05)],
    )
    ts2 = TaskStats(
        task_id="t2", space_id=SPACE_ID, title="T2",
        runs=[_make_run(cost_usd=0.10)],
    )
    g = aggregate_global([ts1, ts2])
    assert g.total_cost_usd == pytest.approx(0.15, rel=1e-6)
    assert g.total_tasks_with_stats == 2
    assert g.total_runs == 2


def test_aggregate_global_tool_summary():
    ts = TaskStats(
        task_id="t1", space_id=SPACE_ID, title="T",
        runs=[_make_run(tool_uses={"Read": 3, "Write": 1})],
    )
    g = aggregate_global([ts])
    assert g.tool_use_summary["Read"] == 3
    assert g.tool_use_summary["Write"] == 1


def test_aggregate_global_avg_memory_hit_rate_none_when_no_memory():
    ts = TaskStats(
        task_id="t1", space_id=SPACE_ID, title="T",
        runs=[_make_run(), _make_run()],
    )
    g = aggregate_global([ts])
    assert g.avg_memory_hit_rate is None


def test_aggregate_global_avg_memory_hit_rate_across_tasks():
    ts1 = TaskStats(
        task_id="t1", space_id=SPACE_ID, title="T1",
        runs=[_make_run(memory_hit_rate=1.0), _make_run(memory_hit_rate=0.5)],
    )
    ts2 = TaskStats(
        task_id="t2", space_id=SPACE_ID, title="T2",
        runs=[_make_run(memory_hit_rate=0.0), _make_run()],  # one run has no memory
    )
    g = aggregate_global([ts1, ts2])
    # Average of 1.0, 0.5, 0.0 = 0.5; the None run is excluded
    assert g.avg_memory_hit_rate == pytest.approx(0.5, rel=1e-4)


# ---------------------------------------------------------------------------
# StatsStore
# ---------------------------------------------------------------------------


async def test_stats_store_append_run(tmp_spaces_dir):
    store = StatsStore(tmp_spaces_dir)
    run = _make_run()
    ts = await store.append_run(SPACE_ID, "task-1", "My Task", run)
    assert ts.total_runs == 1
    assert ts.task_id == "task-1"


async def test_stats_store_append_run_accumulates(tmp_spaces_dir):
    store = StatsStore(tmp_spaces_dir)
    run1 = _make_run(0)
    run2 = _make_run(1)
    (tmp_spaces_dir / SPACE_ID / ".cronos" / "stats").mkdir(parents=True, exist_ok=True)
    await store.append_run(SPACE_ID, "task-1", "T", run1)
    ts = await store.append_run(SPACE_ID, "task-1", "T", run2)
    assert ts.total_runs == 2


async def test_stats_store_load_nonexistent(tmp_spaces_dir):
    store = StatsStore(tmp_spaces_dir)
    result = await store.load(SPACE_ID, "no-such-task")
    assert result is None


async def test_stats_store_list_space_empty(tmp_spaces_dir):
    store = StatsStore(tmp_spaces_dir)
    results = await store.list_space(SPACE_ID)
    assert results == []


async def test_stats_store_list_space(tmp_spaces_dir):
    store = StatsStore(tmp_spaces_dir)
    (tmp_spaces_dir / SPACE_ID / ".cronos" / "stats").mkdir(parents=True, exist_ok=True)
    await store.append_run(SPACE_ID, "task-a", "Task A", _make_run())
    await store.append_run(SPACE_ID, "task-b", "Task B", _make_run())
    results = await store.list_space(SPACE_ID)
    assert len(results) == 2
    task_ids = {r.task_id for r in results}
    assert task_ids == {"task-a", "task-b"}
