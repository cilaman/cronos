from __future__ import annotations

"""Integration tests for stats, traces, and activity API endpoints."""

from datetime import UTC, datetime

import pytest

from app.stats import RunStats
from app.trace_parser import RunTrace

from .conftest import SPACE_ID

_NOW = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
_TASK_ID = "2025-01-01-0000-test-task"


def _make_run_stats(run_index: int = 0) -> RunStats:
    return RunStats(
        run_index=run_index,
        started_at=_NOW,
        ended_at=_NOW,
        duration_seconds=30.0,
        model="default",
        mode="auto",
        exit_reason="DONE",
        input_tokens=500,
        output_tokens=200,
        cost_usd=0.005,
    )


def _make_trace(run_index: int = 0) -> RunTrace:
    return RunTrace(
        task_id=_TASK_ID,
        space_id=SPACE_ID,
        run_index=run_index,
        session_id=None,
        model="default",
        mode="auto",
        started_at=_NOW,
        ended_at=_NOW,
        duration_seconds=30.0,
        exit_reason="DONE",
    )


# ---------------------------------------------------------------------------
# Activity — GET /api/activity
# ---------------------------------------------------------------------------


async def test_list_activity_empty(async_client):
    resp = await async_client.get("/api/activity")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_activity_after_task_created(async_client):
    await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Activity Task", "brief": ""},
    )
    resp = await async_client.get("/api/activity")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["title"] == "Activity Task"
    assert items[0]["state"] == "backlog"


async def test_list_activity_most_recent_first(async_client):
    await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "First Task", "brief": ""},
    )
    await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Second Task", "brief": ""},
    )
    resp = await async_client.get("/api/activity")
    items = resp.json()
    assert len(items) == 2
    titles = [i["title"] for i in items]
    assert "First Task" in titles
    assert "Second Task" in titles
    # verify descending updated_at order
    from datetime import datetime
    t0 = datetime.fromisoformat(items[0]["updated_at"])
    t1 = datetime.fromisoformat(items[1]["updated_at"])
    assert t0 >= t1


async def test_list_activity_filter_by_space(async_client):
    await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Filtered", "brief": ""},
    )
    resp = await async_client.get(f"/api/activity?space_id={SPACE_ID}")
    assert resp.status_code == 200
    items = resp.json()
    assert all(i["space_id"] == SPACE_ID for i in items)


async def test_list_activity_unknown_space_returns_404(async_client):
    resp = await async_client.get("/api/activity?space_id=no-such-space")
    assert resp.status_code == 404


async def test_list_activity_respects_limit(async_client):
    for i in range(5):
        await async_client.post(
            "/api/tasks",
            json={"space_id": SPACE_ID, "title": f"Task {i}", "brief": ""},
        )
    resp = await async_client.get("/api/activity?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# Stats — GET /api/stats
# ---------------------------------------------------------------------------


async def test_get_global_stats_empty(async_client):
    resp = await async_client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_runs"] == 0
    assert data["total_tasks_with_stats"] == 0
    assert data["total_cost_usd"] == pytest.approx(0.0)


async def test_get_global_stats_with_runs(async_client, tmp_spaces_dir):
    from app.stats_store import StatsStore
    stats_store = StatsStore(tmp_spaces_dir)
    (tmp_spaces_dir / SPACE_ID / ".cronos" / "stats").mkdir(parents=True, exist_ok=True)
    await stats_store.append_run(SPACE_ID, "task-x", "Task X", _make_run_stats())
    # inject the store so the API uses it
    from app.main import app
    app.state.stats_store = stats_store

    resp = await async_client.get("/api/stats")
    assert resp.status_code == 200
    assert resp.json()["total_runs"] == 1


# ---------------------------------------------------------------------------
# Stats — GET /api/tasks/{task_id}/stats
# ---------------------------------------------------------------------------


async def test_get_task_stats_no_runs(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Stats Task", "brief": ""},
    )
    task_id = create_resp.json()["id"]
    resp = await async_client.get(f"/api/tasks/{task_id}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task_id
    assert data["total_runs"] == 0


async def test_get_task_stats_not_found(async_client):
    resp = await async_client.get("/api/tasks/nonexistent/stats")
    assert resp.status_code == 404


async def test_get_task_stats_with_runs(async_client, tmp_spaces_dir):
    from app.stats_store import StatsStore
    from app.main import app

    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Run Task", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    stats_store = StatsStore(tmp_spaces_dir)
    (tmp_spaces_dir / SPACE_ID / ".cronos" / "stats").mkdir(parents=True, exist_ok=True)
    await stats_store.append_run(SPACE_ID, task_id, "Run Task", _make_run_stats())
    app.state.stats_store = stats_store

    resp = await async_client.get(f"/api/tasks/{task_id}/stats")
    assert resp.status_code == 200
    assert resp.json()["total_runs"] == 1


# ---------------------------------------------------------------------------
# Stats — GET /api/spaces/{space_id}/stats
# ---------------------------------------------------------------------------


async def test_get_space_stats_empty(async_client):
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/stats")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_space_stats_with_data(async_client, tmp_spaces_dir):
    from app.stats_store import StatsStore
    from app.main import app

    stats_store = StatsStore(tmp_spaces_dir)
    (tmp_spaces_dir / SPACE_ID / ".cronos" / "stats").mkdir(parents=True, exist_ok=True)
    await stats_store.append_run(SPACE_ID, "task-a", "Task A", _make_run_stats())
    app.state.stats_store = stats_store

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/stats")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["task_id"] == "task-a"


# ---------------------------------------------------------------------------
# Traces — GET /api/tasks/{task_id}/traces
# ---------------------------------------------------------------------------


async def test_list_task_traces_empty(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Trace Task", "brief": ""},
    )
    task_id = create_resp.json()["id"]
    resp = await async_client.get(f"/api/tasks/{task_id}/traces")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_task_traces_not_found(async_client):
    resp = await async_client.get("/api/tasks/nonexistent/traces")
    assert resp.status_code == 404


async def test_list_task_traces_with_data(async_client, tmp_spaces_dir):
    from app.trace_store import TraceStore
    from app.main import app

    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Traced", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    trace_store = TraceStore(tmp_spaces_dir)
    t0 = _make_trace(0)
    t0 = t0.model_copy(update={"task_id": task_id})
    t1 = _make_trace(1)
    t1 = t1.model_copy(update={"task_id": task_id})
    await trace_store.save_run(SPACE_ID, task_id, t0)
    await trace_store.save_run(SPACE_ID, task_id, t1)
    app.state.trace_store = trace_store

    resp = await async_client.get(f"/api/tasks/{task_id}/traces")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    # endpoint returns in reverse order
    assert items[0]["run_index"] == 1
    assert items[1]["run_index"] == 0


# ---------------------------------------------------------------------------
# Traces — GET /api/tasks/{task_id}/traces/latest
# ---------------------------------------------------------------------------


async def test_get_latest_trace_no_traces_returns_404(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "No Traces", "brief": ""},
    )
    task_id = create_resp.json()["id"]
    resp = await async_client.get(f"/api/tasks/{task_id}/traces/latest")
    assert resp.status_code == 404


async def test_get_latest_trace_success(async_client, tmp_spaces_dir):
    from app.trace_store import TraceStore
    from app.main import app

    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Latest Trace", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    trace_store = TraceStore(tmp_spaces_dir)
    for i in range(3):
        t = _make_trace(i)
        t = t.model_copy(update={"task_id": task_id})
        await trace_store.save_run(SPACE_ID, task_id, t)
    app.state.trace_store = trace_store

    resp = await async_client.get(f"/api/tasks/{task_id}/traces/latest")
    assert resp.status_code == 200
    assert resp.json()["run_index"] == 2


# ---------------------------------------------------------------------------
# Traces — GET /api/tasks/{task_id}/traces/{run_index}
# ---------------------------------------------------------------------------


async def test_get_task_trace_by_index(async_client, tmp_spaces_dir):
    from app.trace_store import TraceStore
    from app.main import app

    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Indexed Trace", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    trace_store = TraceStore(tmp_spaces_dir)
    t = _make_trace(5)
    t = t.model_copy(update={"task_id": task_id})
    await trace_store.save_run(SPACE_ID, task_id, t)
    app.state.trace_store = trace_store

    resp = await async_client.get(f"/api/tasks/{task_id}/traces/5")
    assert resp.status_code == 200
    assert resp.json()["run_index"] == 5


async def test_get_task_trace_missing_run_returns_404(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "T", "brief": ""},
    )
    task_id = create_resp.json()["id"]
    resp = await async_client.get(f"/api/tasks/{task_id}/traces/99")
    assert resp.status_code == 404
