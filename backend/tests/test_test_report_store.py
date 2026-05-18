from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.test_report import TestCase, TestReport, TestSuite
from app.test_report_store import TestReportStore

from .conftest import SPACE_ID

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_report(
    report_id: str = "rpt-001",
    space_id: str = SPACE_ID,
    task_id: str | None = None,
    report_type: str = "space",
    exit_code: int = 0,
    started_at: datetime | None = None,
) -> TestReport:
    now = started_at or datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    tc = TestCase(id="tc-1", name="test_foo", status="passed", duration_seconds=0.1)
    suite = TestSuite(
        name="suite_a",
        tests=[tc],
        passed=1,
        failed=0,
        errors=0,
        skipped=0,
        duration_seconds=0.1,
    )
    return TestReport(
        id=report_id,
        space_id=space_id,
        task_id=task_id,
        report_type=report_type,  # type: ignore[arg-type]
        triggered_by="agent",
        started_at=now,
        ended_at=now,
        suites=[suite],
        total_passed=1,
        total_failed=0,
        total_errors=0,
        total_skipped=0,
        total_tests=1,
        exit_code=exit_code,
        raw_output=".",
        framework="pytest",
    )


# ---------------------------------------------------------------------------
# save / get
# ---------------------------------------------------------------------------


async def test_save_and_get(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    report = _make_report("rpt-001")
    await store.save(SPACE_ID, report)
    loaded = await store.get(SPACE_ID, "rpt-001")
    assert loaded is not None
    assert loaded.id == "rpt-001"
    assert loaded.total_passed == 1


async def test_get_nonexistent(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    result = await store.get(SPACE_ID, "no-such-id")
    assert result is None


async def test_save_overwrites_same_id(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    report = _make_report("rpt-dup", exit_code=0)
    await store.save(SPACE_ID, report)
    # Save updated version with same id (same timestamp → same path)
    updated = report.model_copy(update={"total_passed": 5, "total_tests": 5})
    await store.save(SPACE_ID, updated)
    loaded = await store.get(SPACE_ID, "rpt-dup")
    assert loaded is not None
    assert loaded.total_passed == 5


# ---------------------------------------------------------------------------
# list_space
# ---------------------------------------------------------------------------


async def test_list_space_empty(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    results = await store.list_space(SPACE_ID)
    assert results == []


async def test_list_space_returns_summaries(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    r1 = _make_report("rpt-a", started_at=datetime(2025, 1, 1, 10, 0, tzinfo=UTC))
    r2 = _make_report("rpt-b", started_at=datetime(2025, 1, 1, 11, 0, tzinfo=UTC))
    await store.save(SPACE_ID, r1)
    await store.save(SPACE_ID, r2)
    results = await store.list_space(SPACE_ID)
    assert len(results) == 2
    # summaries should not have raw_output or coverage_data fields
    for summary in results:
        assert not hasattr(summary, "raw_output")
        assert not hasattr(summary, "coverage_data")


async def test_list_space_sorted_chronologically(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    r1 = _make_report("rpt-early", started_at=datetime(2025, 1, 1, 8, 0, tzinfo=UTC))
    r2 = _make_report("rpt-late", started_at=datetime(2025, 1, 1, 20, 0, tzinfo=UTC))
    await store.save(SPACE_ID, r2)
    await store.save(SPACE_ID, r1)
    results = await store.list_space(SPACE_ID)
    assert results[0].id == "rpt-early"
    assert results[1].id == "rpt-late"


async def test_list_space_respects_limit(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    for i in range(5):
        r = _make_report(
            f"rpt-{i:03d}",
            started_at=datetime(2025, 1, i + 1, 12, 0, tzinfo=UTC),
        )
        await store.save(SPACE_ID, r)
    results = await store.list_space(SPACE_ID, limit=3)
    assert len(results) == 3


# ---------------------------------------------------------------------------
# list_for_task
# ---------------------------------------------------------------------------


async def test_list_for_task_filters_by_task(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    r_task = _make_report("rpt-task", task_id="task-1", report_type="task")
    r_space = _make_report("rpt-space", task_id=None, report_type="space")
    await store.save(SPACE_ID, r_task)
    await store.save(SPACE_ID, r_space)
    results = await store.list_for_task(SPACE_ID, "task-1")
    assert len(results) == 1
    assert results[0].id == "rpt-task"


async def test_list_for_task_empty(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    results = await store.list_for_task(SPACE_ID, "no-such-task")
    assert results == []


# ---------------------------------------------------------------------------
# get_latest_for_space
# ---------------------------------------------------------------------------


async def test_get_latest_for_space_none_when_empty(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    result = await store.get_latest_for_space(SPACE_ID)
    assert result is None


async def test_get_latest_for_space_returns_newest(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    r_old = _make_report("rpt-old", started_at=datetime(2025, 1, 1, 10, 0, tzinfo=UTC))
    r_new = _make_report("rpt-new", started_at=datetime(2025, 1, 1, 14, 0, tzinfo=UTC))
    await store.save(SPACE_ID, r_old)
    await store.save(SPACE_ID, r_new)
    result = await store.get_latest_for_space(SPACE_ID)
    assert result is not None
    assert result.id == "rpt-new"


# ---------------------------------------------------------------------------
# get_latest_for_task
# ---------------------------------------------------------------------------


async def test_get_latest_for_task_none_when_no_match(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    r_space = _make_report("rpt-space", task_id=None, report_type="space")
    await store.save(SPACE_ID, r_space)
    result = await store.get_latest_for_task(SPACE_ID, "task-99")
    assert result is None


async def test_get_latest_for_task_returns_newest_for_task(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    r1 = _make_report(
        "rpt-t1-early",
        task_id="task-1",
        report_type="task",
        started_at=datetime(2025, 1, 1, 9, 0, tzinfo=UTC),
    )
    r2 = _make_report(
        "rpt-t1-late",
        task_id="task-1",
        report_type="task",
        started_at=datetime(2025, 1, 1, 18, 0, tzinfo=UTC),
    )
    r_other = _make_report(
        "rpt-t2",
        task_id="task-2",
        report_type="task",
        started_at=datetime(2025, 1, 1, 20, 0, tzinfo=UTC),
    )
    await store.save(SPACE_ID, r1)
    await store.save(SPACE_ID, r2)
    await store.save(SPACE_ID, r_other)
    result = await store.get_latest_for_task(SPACE_ID, "task-1")
    assert result is not None
    assert result.id == "rpt-t1-late"


# ---------------------------------------------------------------------------
# Atomic write — file integrity
# ---------------------------------------------------------------------------


async def test_report_round_trips_all_fields(tmp_spaces_dir):
    store = TestReportStore(tmp_spaces_dir)
    report = _make_report("rpt-full")
    report = report.model_copy(update={"coverage_pct": 87.5, "coverage_data": {"app/main.py": 90.0}})
    await store.save(SPACE_ID, report)
    loaded = await store.get(SPACE_ID, "rpt-full")
    assert loaded is not None
    assert loaded.coverage_pct == 87.5
    assert loaded.coverage_data == {"app/main.py": 90.0}
    assert loaded.raw_output == "."
