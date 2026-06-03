"""Tests for GET /api/spaces/{id}/tools/{kind}/{name}/telemetry."""
from __future__ import annotations

import pytest
from datetime import UTC, datetime, timedelta

from app.stats import AdoptedToolRunStats, RunStats
from app.stats_store import StatsStore

from .conftest import SPACE_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(
    adopted_tool_uses: dict | None = None,
    exit_reason: str = "DONE",
    started_at: datetime | None = None,
) -> RunStats:
    now = started_at or datetime(2025, 6, 1, tzinfo=UTC)
    return RunStats(
        run_index=0,
        started_at=now,
        ended_at=now,
        duration_seconds=60.0,
        model="default",
        mode="auto",
        exit_reason=exit_reason,
        adopted_tool_uses=adopted_tool_uses or {},
    )


def _agent_entry(calls: int = 1, errors: int = 0, human_rescue: bool = False) -> AdoptedToolRunStats:
    return AdoptedToolRunStats(calls=calls, errors=errors, kind="agent", human_rescue=human_rescue)


# ---------------------------------------------------------------------------
# Acceptance: 3 fixture runs (2 clean, 1 error) → calls=3, errors=1, avg≈0.67
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telemetry_three_runs_two_clean_one_error(async_client, tmp_spaces_dir):
    stats_store = StatsStore(tmp_spaces_dir)
    await stats_store.append_run(SPACE_ID, "task-1", "T1", _make_run({"my-agent": _agent_entry(calls=1, errors=0)}))
    await stats_store.append_run(SPACE_ID, "task-2", "T2", _make_run({"my-agent": _agent_entry(calls=1, errors=0)}))
    await stats_store.append_run(SPACE_ID, "task-3", "T3", _make_run({"my-agent": _agent_entry(calls=1, errors=1)}))

    from app.main import app
    app.state.stats_store = stats_store

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools/agent/my-agent/telemetry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["calls"] == 3
    assert data["errors"] == 1
    assert data["avg_success_rate"] == pytest.approx(1 - 1 / 3, rel=1e-3)
    assert data["kind"] == "agent"
    assert data["name"] == "my-agent"


# ---------------------------------------------------------------------------
# Empty history → zeros, no 500
# ---------------------------------------------------------------------------


async def test_telemetry_empty_history(async_client):
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools/agent/nonexistent/telemetry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["calls"] == 0
    assert data["errors"] == 0
    assert data["avg_success_rate"] == 0.0
    assert data["human_rescue_count"] == 0


# ---------------------------------------------------------------------------
# window param filters by started_at
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telemetry_window_filters_old_runs(async_client, tmp_spaces_dir):
    stats_store = StatsStore(tmp_spaces_dir)
    old_dt = datetime.now(UTC) - timedelta(days=60)
    recent_dt = datetime.now(UTC) - timedelta(days=5)

    await stats_store.append_run(
        SPACE_ID, "task-old", "Old",
        _make_run({"my-agent": _agent_entry(calls=1, errors=1)}, started_at=old_dt),
    )
    await stats_store.append_run(
        SPACE_ID, "task-new", "New",
        _make_run({"my-agent": _agent_entry(calls=1, errors=0)}, started_at=recent_dt),
    )

    from app.main import app
    app.state.stats_store = stats_store

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools/agent/my-agent/telemetry?window=30d")
    assert resp.status_code == 200
    data = resp.json()
    assert data["calls"] == 1   # only recent run
    assert data["errors"] == 0
    assert data["avg_success_rate"] == pytest.approx(1.0)


async def test_telemetry_no_window_includes_all_runs(async_client, tmp_spaces_dir):
    stats_store = StatsStore(tmp_spaces_dir)
    old_dt = datetime.now(UTC) - timedelta(days=200)
    await stats_store.append_run(
        SPACE_ID, "task-old", "Old",
        _make_run({"my-agent": _agent_entry(calls=2, errors=1)}, started_at=old_dt),
    )

    from app.main import app
    app.state.stats_store = stats_store

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools/agent/my-agent/telemetry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["calls"] == 2  # old run still included


# ---------------------------------------------------------------------------
# Kind filtering
# ---------------------------------------------------------------------------


async def test_telemetry_filters_by_kind(async_client, tmp_spaces_dir):
    stats_store = StatsStore(tmp_spaces_dir)
    # Same name, different kinds
    await stats_store.append_run(
        SPACE_ID, "task-a", "A",
        _make_run({"shared-name": AdoptedToolRunStats(calls=1, errors=0, kind="agent")}),
    )
    await stats_store.append_run(
        SPACE_ID, "task-b", "B",
        _make_run({"shared-name": AdoptedToolRunStats(calls=1, errors=1, kind="skill")}),
    )

    from app.main import app
    app.state.stats_store = stats_store

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools/agent/shared-name/telemetry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["calls"] == 1
    assert data["errors"] == 0


# ---------------------------------------------------------------------------
# human_rescue_count
# ---------------------------------------------------------------------------


async def test_telemetry_human_rescue_count(async_client, tmp_spaces_dir):
    stats_store = StatsStore(tmp_spaces_dir)
    await stats_store.append_run(
        SPACE_ID, "task-1", "T1",
        _make_run({"my-agent": _agent_entry(calls=1, errors=0, human_rescue=True)}),
    )
    await stats_store.append_run(
        SPACE_ID, "task-2", "T2",
        _make_run({"my-agent": _agent_entry(calls=1, errors=0, human_rescue=False)}),
    )

    from app.main import app
    app.state.stats_store = stats_store

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools/agent/my-agent/telemetry")
    assert resp.status_code == 200
    assert resp.json()["human_rescue_count"] == 1


# ---------------------------------------------------------------------------
# 404 for unknown space
# ---------------------------------------------------------------------------


async def test_telemetry_unknown_space(async_client):
    resp = await async_client.get("/api/spaces/no-such-space/tools/agent/foo/telemetry")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Invalid window format → 422
# ---------------------------------------------------------------------------


async def test_telemetry_invalid_window(async_client):
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools/agent/foo/telemetry?window=bad")
    assert resp.status_code == 422
