from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.test_report import TestCase, TestReport, TestSuite

from .conftest import SPACE_ID

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)


def _make_report_payload(
    report_id: str = "rpt-001",
    space_id: str = SPACE_ID,
    task_id: str | None = None,
    report_type: str = "space",
    total_passed: int = 3,
    total_failed: int = 1,
    exit_code: int = 1,
) -> dict:
    tc_pass = {
        "id": "tc-1", "name": "test_alpha", "status": "passed",
        "duration_seconds": 0.05,
    }
    tc_fail = {
        "id": "tc-2", "name": "test_beta", "status": "failed",
        "duration_seconds": 0.12, "error_message": "AssertionError: expected 1",
    }
    suite = {
        "name": "suite_main",
        "tests": [tc_pass, tc_fail],
        "passed": total_passed,
        "failed": total_failed,
        "errors": 0,
        "skipped": 0,
        "duration_seconds": 0.17,
    }
    return {
        "id": report_id,
        "space_id": space_id,
        "task_id": task_id,
        "report_type": report_type,
        "triggered_by": "agent",
        "started_at": NOW.isoformat(),
        "ended_at": NOW.isoformat(),
        "suites": [suite],
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_errors": 0,
        "total_skipped": 0,
        "total_tests": total_passed + total_failed,
        "exit_code": exit_code,
        "raw_output": "FAILED tests/test_beta.py::test_beta - AssertionError",
        "framework": "pytest",
    }


# ---------------------------------------------------------------------------
# POST /api/spaces/{space_id}/test-reports
# ---------------------------------------------------------------------------


async def test_ingest_report_returns_201(async_client):
    payload = _make_report_payload()
    resp = await async_client.post(
        f"/api/spaces/{SPACE_ID}/test-reports", json=payload
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "rpt-001"
    assert data["space_id"] == SPACE_ID
    assert data["total_passed"] == 3
    assert data["total_failed"] == 1


async def test_ingest_report_persists_and_retrievable(async_client):
    payload = _make_report_payload("rpt-persist")
    await async_client.post(f"/api/spaces/{SPACE_ID}/test-reports", json=payload)

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/test-reports/rpt-persist")
    assert resp.status_code == 200
    assert resp.json()["id"] == "rpt-persist"


async def test_ingest_mismatched_space_id_returns_422(async_client):
    payload = _make_report_payload(space_id="other-space")
    resp = await async_client.post(
        f"/api/spaces/{SPACE_ID}/test-reports", json=payload
    )
    assert resp.status_code == 422


async def test_ingest_report_with_task_id(async_client):
    payload = _make_report_payload(
        report_id="rpt-task-scoped", task_id="task-abc", report_type="task"
    )
    resp = await async_client.post(
        f"/api/spaces/{SPACE_ID}/test-reports", json=payload
    )
    assert resp.status_code == 201
    assert resp.json()["task_id"] == "task-abc"


# ---------------------------------------------------------------------------
# GET /api/spaces/{space_id}/test-reports
# ---------------------------------------------------------------------------


async def test_list_reports_empty(async_client):
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/test-reports")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_reports_returns_summaries(async_client):
    for i in range(3):
        await async_client.post(
            f"/api/spaces/{SPACE_ID}/test-reports",
            json=_make_report_payload(f"rpt-{i:03d}"),
        )
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/test-reports")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    # Summaries should not contain raw_output or suites
    assert "raw_output" not in data[0]
    assert "suites" not in data[0]


async def test_list_reports_respects_limit(async_client):
    for i in range(5):
        await async_client.post(
            f"/api/spaces/{SPACE_ID}/test-reports",
            json=_make_report_payload(f"rpt-lim-{i}"),
        )
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/test-reports?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# GET /api/spaces/{space_id}/test-reports/latest
# ---------------------------------------------------------------------------


async def test_latest_report_404_when_none(async_client):
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/test-reports/latest")
    assert resp.status_code == 404


async def test_latest_report_returns_most_recent(async_client):
    old_payload = _make_report_payload("rpt-old")
    old_payload["started_at"] = datetime(2025, 1, 1, 8, 0, tzinfo=UTC).isoformat()
    old_payload["ended_at"] = old_payload["started_at"]
    await async_client.post(f"/api/spaces/{SPACE_ID}/test-reports", json=old_payload)

    new_payload = _make_report_payload("rpt-new")
    new_payload["started_at"] = datetime(2025, 6, 1, 18, 0, tzinfo=UTC).isoformat()
    new_payload["ended_at"] = new_payload["started_at"]
    await async_client.post(f"/api/spaces/{SPACE_ID}/test-reports", json=new_payload)

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/test-reports/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "rpt-new"
    # Full report includes suites and raw_output
    assert "suites" in data
    assert "raw_output" in data


# ---------------------------------------------------------------------------
# GET /api/spaces/{space_id}/test-reports/{report_id}
# ---------------------------------------------------------------------------


async def test_get_report_by_id(async_client):
    payload = _make_report_payload("rpt-byid")
    await async_client.post(f"/api/spaces/{SPACE_ID}/test-reports", json=payload)

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/test-reports/rpt-byid")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "rpt-byid"
    assert data["framework"] == "pytest"
    assert len(data["suites"]) == 1
    assert len(data["suites"][0]["tests"]) == 2


async def test_get_report_by_id_not_found(async_client):
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/test-reports/no-such-id")
    assert resp.status_code == 404


async def test_get_report_includes_full_suite_detail(async_client):
    payload = _make_report_payload("rpt-detail")
    await async_client.post(f"/api/spaces/{SPACE_ID}/test-reports", json=payload)

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/test-reports/rpt-detail")
    assert resp.status_code == 200
    suite = resp.json()["suites"][0]
    failing = next(tc for tc in suite["tests"] if tc["status"] == "failed")
    assert failing["error_message"] == "AssertionError: expected 1"
