# tests/test_cron_eval.py
# Full test suite for app.harnesses.cron — should_fire and has_active_run helpers.
# I3 created the initial 4-test stub; I5 expands to complete coverage.
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses.cron import should_fire, has_active_run
from app.harnesses.run_index import RunSummary, append_run

UTC = timezone.utc


def make_dt(y, mo, d, h, mi, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=UTC)


# ---------------------------------------------------------------------------
# should_fire — basic behaviour (carried over from I3 stub)
# ---------------------------------------------------------------------------


def test_should_fire_returns_true_when_expr_matches():
    # prev_tick is 1 minute before the scheduled fire time
    # expr = "*/1 * * * *" (every minute)
    prev_tick = make_dt(2026, 6, 1, 12, 0, 0)
    now = make_dt(2026, 6, 1, 12, 1, 5)
    assert should_fire("*/1 * * * *", "UTC", prev_tick, now) is True


def test_should_fire_returns_false_same_cron_minute():
    # prev_tick is already past the scheduled fire time in the same minute
    prev_tick = make_dt(2026, 6, 1, 12, 0, 30)  # 30s into the minute
    now = make_dt(2026, 6, 1, 12, 0, 45)        # 45s into the same minute
    # next fire for "*/1 * * * *" from prev_tick is 12:01:00 which is > now
    assert should_fire("*/1 * * * *", "UTC", prev_tick, now) is False


def test_should_fire_malformed_expression():
    prev_tick = make_dt(2026, 6, 1, 12, 0, 0)
    now = make_dt(2026, 6, 1, 12, 1, 5)
    assert should_fire("not-a-cron-expr", "UTC", prev_tick, now) is False


def test_should_fire_unknown_timezone():
    prev_tick = make_dt(2026, 6, 1, 12, 0, 0)
    now = make_dt(2026, 6, 1, 12, 1, 5)
    # Unknown timezone falls back to UTC; should still evaluate correctly
    result = should_fire("*/1 * * * *", "Invalid/Timezone", prev_tick, now)
    # Should return True (with UTC fallback) or False (no fire) — either is acceptable
    # but must not raise an exception
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# should_fire — expanded coverage (I5)
# ---------------------------------------------------------------------------


def test_should_fire_hourly_expression_fires_at_top_of_hour():
    """'0 * * * *' fires at the top of each hour."""
    prev_tick = make_dt(2026, 6, 1, 11, 59, 55)
    now = make_dt(2026, 6, 1, 12, 0, 5)
    assert should_fire("0 * * * *", "UTC", prev_tick, now) is True


def test_should_fire_hourly_expression_does_not_fire_early():
    """'0 * * * *' does NOT fire when less than an hour has elapsed."""
    prev_tick = make_dt(2026, 6, 1, 12, 0, 1)
    now = make_dt(2026, 6, 1, 12, 30, 0)
    assert should_fire("0 * * * *", "UTC", prev_tick, now) is False


def test_should_fire_daily_expression_fires_at_midnight():
    """'0 0 * * *' fires once a day at midnight."""
    prev_tick = make_dt(2026, 6, 1, 23, 59, 50)
    now = make_dt(2026, 6, 2, 0, 0, 5)
    assert should_fire("0 0 * * *", "UTC", prev_tick, now) is True


def test_should_fire_specific_weekday_fires_on_correct_day():
    """'0 9 * * 1' fires Mondays at 09:00 UTC.
    2026-06-01 is a Monday, so should fire after 08:59:59 Sunday."""
    # prev_tick: Sunday 31 May 2026 at 09:05 UTC (past the previous Monday slot)
    prev_tick = make_dt(2026, 5, 31, 9, 5, 0)
    now = make_dt(2026, 6, 1, 9, 0, 5)  # Monday 01 Jun at 09:00:05 UTC
    assert should_fire("0 9 * * 1", "UTC", prev_tick, now) is True


def test_should_fire_double_fire_prevention_across_multiple_polls():
    """Within the same cron-minute, should_fire must return False on subsequent polls.

    This covers the 'sub-minute poll interval can fire same cron-minute twice'
    risk from the design report (risk #2 / high-severity).
    """
    # First poll: prev_tick is just before the minute; fires True.
    prev_tick = make_dt(2026, 6, 1, 12, 0, 0)
    now_first = make_dt(2026, 6, 1, 12, 1, 5)
    assert should_fire("*/1 * * * *", "UTC", prev_tick, now_first) is True

    # Second poll within the same cron-minute: now=12:01:10 but prev_tick has
    # advanced to 12:01:05 (the value after the first fire).
    # The next fire from croniter(prev_tick=12:01:05) is 12:02:00, which is > now.
    prev_tick_2 = now_first  # loop updates prev_tick to the last tick's now
    now_second = make_dt(2026, 6, 1, 12, 1, 10)
    assert should_fire("*/1 * * * *", "UTC", prev_tick_2, now_second) is False


def test_should_fire_iana_timezone_america_new_york():
    """should_fire correctly handles an IANA timezone ('America/New_York').

    09:00 ET = 14:00 UTC (during EDT, UTC-4 in summer 2026).
    When prev_tick is just before 14:00 UTC and now is just after, it fires.
    """
    try:
        from dateutil import tz as dateutil_tz
        ny_tz = dateutil_tz.gettz("America/New_York")
        if ny_tz is None:
            pytest.skip("dateutil.tz cannot resolve America/New_York in this environment")
    except ImportError:
        pytest.skip("dateutil not available")

    # During EDT (summer), New York is UTC-4.
    # '0 9 * * *' fires at 09:00 ET = 13:00 UTC.
    prev_tick = make_dt(2026, 6, 1, 12, 59, 55)  # UTC
    now = make_dt(2026, 6, 1, 13, 0, 5)           # UTC
    result = should_fire("0 9 * * *", "America/New_York", prev_tick, now)
    # Must be a bool and not raise
    assert isinstance(result, bool)
    assert result is True


def test_should_fire_unknown_timezone_returns_bool_without_raise():
    """Unknown timezone must return bool (True or False), never raise an exception."""
    prev_tick = make_dt(2026, 6, 1, 12, 0, 0)
    now = make_dt(2026, 6, 1, 12, 1, 5)
    result = should_fire("*/1 * * * *", "Bogus/Zone", prev_tick, now)
    assert isinstance(result, bool)


def test_should_fire_malformed_expression_logs_and_returns_false(caplog):
    """Malformed expression must return False and emit a warning log."""
    import logging
    prev_tick = make_dt(2026, 6, 1, 12, 0, 0)
    now = make_dt(2026, 6, 1, 12, 1, 5)
    with caplog.at_level(logging.WARNING, logger="app.harnesses.cron"):
        result = should_fire("this-is-not-valid", "UTC", prev_tick, now)
    assert result is False
    # A warning about the malformed expression must appear in the log
    assert any("malformed" in rec.message or "malformed" in rec.getMessage()
               for rec in caplog.records)


# ---------------------------------------------------------------------------
# has_active_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_has_active_run_returns_true_when_running_run_exists(tmp_path: Path):
    """has_active_run returns True when at least one run with status='running'."""
    harness_name = "h-running"
    summary = RunSummary(
        run_id="run-1",
        harness_id=harness_name,
        status="running",
        triggered_at="2026-06-01T12:00:00Z",
    )
    await append_run(tmp_path, harness_name, summary)

    result = await has_active_run(tmp_path, harness_name)
    assert result is True


@pytest.mark.asyncio
async def test_has_active_run_returns_false_when_all_runs_done(tmp_path: Path):
    """has_active_run returns False when all runs have a terminal status."""
    harness_name = "h-done"
    for run_id, status in [("run-a", "done"), ("run-b", "failed"), ("run-c", "cancelled")]:
        summary = RunSummary(
            run_id=run_id,
            harness_id=harness_name,
            status=status,
            triggered_at="2026-06-01T12:00:00Z",
        )
        await append_run(tmp_path, harness_name, summary)

    result = await has_active_run(tmp_path, harness_name)
    assert result is False


@pytest.mark.asyncio
async def test_has_active_run_returns_false_when_no_runs_exist(tmp_path: Path):
    """has_active_run returns False for a harness with no run index at all."""
    result = await has_active_run(tmp_path, "harness-with-no-runs")
    assert result is False


@pytest.mark.asyncio
async def test_has_active_run_returns_false_on_exception():
    """has_active_run returns False gracefully when run_index.read_index raises."""
    with patch(
        "app.harnesses.cron.run_index.read_index",
        new_callable=AsyncMock,
        side_effect=OSError("simulated disk error"),
    ):
        result = await has_active_run(Path("/nonexistent"), "any-harness")
    assert result is False


@pytest.mark.asyncio
async def test_has_active_run_false_mixed_running_and_done_only_done(tmp_path: Path):
    """has_active_run returns True if at least one running entry exists among done ones."""
    harness_name = "h-mixed"
    # First add a done run, then add a running run
    await append_run(
        tmp_path, harness_name,
        RunSummary("run-done", harness_name, "done", "2026-06-01T10:00:00Z"),
    )
    await append_run(
        tmp_path, harness_name,
        RunSummary("run-running", harness_name, "running", "2026-06-01T11:00:00Z"),
    )

    result = await has_active_run(tmp_path, harness_name)
    assert result is True
