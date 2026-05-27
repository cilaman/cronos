from __future__ import annotations

"""Tests for from_dt / to_dt time-frame filtering on all three stats endpoints."""

from datetime import UTC, datetime, timedelta

from app.main import app
from app.stats import RunStats
from app.stats_store import StatsStore

from .conftest import SPACE_ID

# ---------------------------------------------------------------------------
# Fixed timestamps — deterministic across test runs
# ---------------------------------------------------------------------------

_T_OLD = datetime(2026, 1, 8, 12, 0, tzinfo=UTC)     # ~7 days before base
_T_MIDDLE = datetime(2026, 1, 14, 12, 0, tzinfo=UTC)  # ~1 day before base
_T_RECENT = datetime(2026, 1, 15, 11, 0, tzinfo=UTC)  # ~1 hour before base

# Cut points: _T_OLD < _CUT_LO < _T_MIDDLE < _CUT_HI < _T_RECENT
_CUT_LO = datetime(2026, 1, 10, 0, 0, tzinfo=UTC)
_CUT_HI = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)


def _run_at(started_at: datetime, run_index: int = 0) -> RunStats:
    return RunStats(
        run_index=run_index,
        started_at=started_at,
        ended_at=started_at + timedelta(minutes=5),
        duration_seconds=300.0,
        model="default",
        mode="auto",
        exit_reason="DONE",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
    )


async def _seed(tmp_spaces_dir, task_id: str, title: str = "TF Task") -> StatsStore:
    """Seed 3 runs at _T_OLD, _T_MIDDLE, _T_RECENT for task_id, inject into app state."""
    store = StatsStore(tmp_spaces_dir)
    (tmp_spaces_dir / SPACE_ID / ".cronos" / "stats").mkdir(parents=True, exist_ok=True)
    await store.append_run(SPACE_ID, task_id, title, _run_at(_T_OLD, 0))
    await store.append_run(SPACE_ID, task_id, title, _run_at(_T_MIDDLE, 1))
    await store.append_run(SPACE_ID, task_id, title, _run_at(_T_RECENT, 2))
    app.state.stats_store = store
    return store


async def _create_task(client) -> str:
    resp = await client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "TF Task", "brief": ""},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# GET /api/stats  (global)
# ---------------------------------------------------------------------------


async def test_global_no_filter(async_client, tmp_spaces_dir):
    """No filter returns all 3 runs."""
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    resp = await async_client.get("/api/stats")
    assert resp.status_code == 200
    assert resp.json()["total_runs"] == 3


async def test_global_from_dt_only(async_client, tmp_spaces_dir):
    """from_dt only: runs with started_at >= cutpoint."""
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    resp = await async_client.get("/api/stats", params={"from_dt": _CUT_LO.isoformat()})
    assert resp.status_code == 200
    assert resp.json()["total_runs"] == 2  # _T_MIDDLE + _T_RECENT


async def test_global_to_dt_only(async_client, tmp_spaces_dir):
    """to_dt only: runs with started_at <= cutpoint."""
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    resp = await async_client.get("/api/stats", params={"to_dt": _CUT_LO.isoformat()})
    assert resp.status_code == 200
    assert resp.json()["total_runs"] == 1  # _T_OLD only


async def test_global_both_params(async_client, tmp_spaces_dir):
    """Both params: only runs within [_CUT_LO, _CUT_HI] are included."""
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    resp = await async_client.get(
        "/api/stats",
        params={"from_dt": _CUT_LO.isoformat(), "to_dt": _CUT_HI.isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json()["total_runs"] == 1  # _T_MIDDLE only


async def test_global_empty_window(async_client, tmp_spaces_dir):
    """A window containing no runs returns zeroed GlobalStats and empty lists."""
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    gap_start = datetime(2026, 1, 9, 0, 0, tzinfo=UTC)
    gap_end = datetime(2026, 1, 13, 0, 0, tzinfo=UTC)
    resp = await async_client.get(
        "/api/stats",
        params={"from_dt": gap_start.isoformat(), "to_dt": gap_end.isoformat()},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_runs"] == 0
    assert data["total_tasks_with_stats"] == 0
    assert data["total_cost_usd"] == 0.0


async def test_global_invalid_range(async_client, tmp_spaces_dir):
    """from_dt > to_dt returns HTTP 422."""
    resp = await async_client.get(
        "/api/stats",
        params={"from_dt": _CUT_HI.isoformat(), "to_dt": _CUT_LO.isoformat()},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/spaces/{space_id}/stats
# ---------------------------------------------------------------------------


async def test_space_no_filter(async_client, tmp_spaces_dir):
    """No filter returns all tasks with all runs."""
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/stats")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["total_runs"] == 3


async def test_space_from_dt_only(async_client, tmp_spaces_dir):
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    resp = await async_client.get(
        f"/api/spaces/{SPACE_ID}/stats",
        params={"from_dt": _CUT_LO.isoformat()},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["total_runs"] == 2


async def test_space_to_dt_only(async_client, tmp_spaces_dir):
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    resp = await async_client.get(
        f"/api/spaces/{SPACE_ID}/stats",
        params={"to_dt": _CUT_LO.isoformat()},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["total_runs"] == 1


async def test_space_both_params(async_client, tmp_spaces_dir):
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    resp = await async_client.get(
        f"/api/spaces/{SPACE_ID}/stats",
        params={"from_dt": _CUT_LO.isoformat(), "to_dt": _CUT_HI.isoformat()},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["total_runs"] == 1


async def test_space_empty_window(async_client, tmp_spaces_dir):
    """Tasks with zero in-window runs are omitted from the response."""
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    gap_start = datetime(2026, 1, 9, 0, 0, tzinfo=UTC)
    gap_end = datetime(2026, 1, 13, 0, 0, tzinfo=UTC)
    resp = await async_client.get(
        f"/api/spaces/{SPACE_ID}/stats",
        params={"from_dt": gap_start.isoformat(), "to_dt": gap_end.isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_space_invalid_range(async_client):
    resp = await async_client.get(
        f"/api/spaces/{SPACE_ID}/stats",
        params={"from_dt": _CUT_HI.isoformat(), "to_dt": _CUT_LO.isoformat()},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/tasks/{task_id}/stats
# ---------------------------------------------------------------------------


async def test_task_no_filter(async_client, tmp_spaces_dir):
    """No filter returns all 3 runs."""
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    resp = await async_client.get(f"/api/tasks/{task_id}/stats")
    assert resp.status_code == 200
    assert resp.json()["total_runs"] == 3


async def test_task_from_dt_only(async_client, tmp_spaces_dir):
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    resp = await async_client.get(
        f"/api/tasks/{task_id}/stats",
        params={"from_dt": _CUT_LO.isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json()["total_runs"] == 2


async def test_task_to_dt_only(async_client, tmp_spaces_dir):
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    resp = await async_client.get(
        f"/api/tasks/{task_id}/stats",
        params={"to_dt": _CUT_LO.isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json()["total_runs"] == 1


async def test_task_both_params(async_client, tmp_spaces_dir):
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    resp = await async_client.get(
        f"/api/tasks/{task_id}/stats",
        params={"from_dt": _CUT_LO.isoformat(), "to_dt": _CUT_HI.isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json()["total_runs"] == 1


async def test_task_empty_window(async_client, tmp_spaces_dir):
    """A window with no matching runs returns a TaskStats with total_runs == 0."""
    task_id = await _create_task(async_client)
    await _seed(tmp_spaces_dir, task_id)

    gap_start = datetime(2026, 1, 9, 0, 0, tzinfo=UTC)
    gap_end = datetime(2026, 1, 13, 0, 0, tzinfo=UTC)
    resp = await async_client.get(
        f"/api/tasks/{task_id}/stats",
        params={"from_dt": gap_start.isoformat(), "to_dt": gap_end.isoformat()},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_runs"] == 0
    assert data["task_id"] == task_id


async def test_task_invalid_range(async_client, tmp_spaces_dir):
    """from_dt > to_dt returns HTTP 422 before task lookup."""
    task_id = await _create_task(async_client)
    resp = await async_client.get(
        f"/api/tasks/{task_id}/stats",
        params={"from_dt": _CUT_HI.isoformat(), "to_dt": _CUT_LO.isoformat()},
    )
    assert resp.status_code == 422
