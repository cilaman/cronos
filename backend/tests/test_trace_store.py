from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.trace_parser import RunTrace
from app.trace_store import TraceStore


def _make_trace(run_index: int = 0) -> RunTrace:
    now = datetime.now(tz=timezone.utc)
    return RunTrace(
        task_id="task-1",
        space_id="space-1",
        run_index=run_index,
        session_id="sess-abc",
        model="sonnet",
        real_model=None,
        mode="auto",
        started_at=now,
        ended_at=now,
        duration_seconds=1.5,
        exit_reason="done",
    )


@pytest.fixture
def store(tmp_path: Path) -> TraceStore:
    return TraceStore(tmp_path / "spaces")


# ---------------------------------------------------------------------------
# save_run / load_run round-trip
# ---------------------------------------------------------------------------


async def test_save_run_creates_file(store: TraceStore, tmp_path: Path):
    trace = _make_trace(run_index=0)
    await store.save_run("space-1", "task-1", trace)
    trace_dir = tmp_path / "spaces" / "space-1" / ".cronos" / "traces" / "task-1"
    assert (trace_dir / "0000.json").exists()


async def test_load_run_returns_saved_trace(store: TraceStore):
    trace = _make_trace(run_index=0)
    await store.save_run("space-1", "task-1", trace)
    loaded = await store.load_run("space-1", "task-1", 0)
    assert loaded is not None
    assert loaded.run_index == 0
    assert loaded.session_id == "sess-abc"
    assert loaded.exit_reason == "done"


async def test_load_run_missing_returns_none(store: TraceStore):
    result = await store.load_run("space-1", "task-missing", 0)
    assert result is None


async def test_load_run_preserves_model_fields(store: TraceStore):
    trace = _make_trace(run_index=2)
    await store.save_run("space-1", "task-1", trace)
    loaded = await store.load_run("space-1", "task-1", 2)
    assert loaded is not None
    assert loaded.model == "sonnet"
    assert loaded.mode == "auto"
    assert loaded.duration_seconds == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# load_latest
# ---------------------------------------------------------------------------


async def test_load_latest_returns_highest_run_index(store: TraceStore):
    for i in range(3):
        await store.save_run("space-1", "task-1", _make_trace(run_index=i))
    latest = await store.load_latest("space-1", "task-1")
    assert latest is not None
    assert latest.run_index == 2


async def test_load_latest_no_traces_returns_none(store: TraceStore):
    result = await store.load_latest("space-1", "no-task")
    assert result is None


async def test_load_latest_single_run(store: TraceStore):
    await store.save_run("space-1", "task-1", _make_trace(run_index=0))
    latest = await store.load_latest("space-1", "task-1")
    assert latest is not None
    assert latest.run_index == 0


# ---------------------------------------------------------------------------
# list_runs
# ---------------------------------------------------------------------------


async def test_list_runs_empty(store: TraceStore):
    runs = await store.list_runs("space-1", "ghost-task")
    assert runs == []


async def test_list_runs_count_matches_saved(store: TraceStore):
    for i in range(4):
        await store.save_run("space-1", "task-1", _make_trace(run_index=i))
    runs = await store.list_runs("space-1", "task-1")
    assert len(runs) == 4


async def test_list_runs_ordered_by_index(store: TraceStore):
    for i in [2, 0, 1]:
        await store.save_run("space-1", "task-1", _make_trace(run_index=i))
    runs = await store.list_runs("space-1", "task-1")
    assert [r.run_index for r in runs] == [0, 1, 2]


# ---------------------------------------------------------------------------
# delete_task_traces
# ---------------------------------------------------------------------------


async def test_delete_task_traces_removes_all_files(store: TraceStore, tmp_path: Path):
    for i in range(3):
        await store.save_run("space-1", "task-1", _make_trace(run_index=i))
    await store.delete_task_traces("space-1", "task-1")
    trace_dir = tmp_path / "spaces" / "space-1" / ".cronos" / "traces" / "task-1"
    assert not trace_dir.exists()


async def test_delete_task_traces_nonexistent_is_noop(store: TraceStore):
    await store.delete_task_traces("space-1", "nonexistent-task")


async def test_delete_task_traces_does_not_affect_other_tasks(store: TraceStore, tmp_path: Path):
    await store.save_run("space-1", "task-1", _make_trace(run_index=0))
    await store.save_run("space-1", "task-2", _make_trace(run_index=0))
    await store.delete_task_traces("space-1", "task-1")
    runs = await store.list_runs("space-1", "task-2")
    assert len(runs) == 1
