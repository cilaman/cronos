from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from .test_report import TestReport, TestReportSummary

log = logging.getLogger("cronos.test_report_store")

CRONOS_SUBDIR = ".cronos"
REPORTS_SUBDIR = "test-reports"


class TestReportStore:
    """Persist test reports as JSON files.

    Reports are stored at:
        {spaces_dir}/{space_id}/.cronos/test-reports/{YYYY-MM-DD-HHmm}-{id}.json

    Filenames encode the timestamp so sorted glob order gives chronological order.
    """

    def __init__(self, spaces_dir: Path) -> None:
        self._spaces_dir = spaces_dir
        self._lock = asyncio.Lock()

    def _reports_dir(self, space_id: str) -> Path:
        return self._spaces_dir / space_id / CRONOS_SUBDIR / REPORTS_SUBDIR

    def _report_path(self, space_id: str, report: TestReport) -> Path:
        prefix = report.started_at.strftime("%Y-%m-%d-%H%M")
        return self._reports_dir(space_id) / f"{prefix}-{report.id}.json"

    def _find_by_id(self, space_id: str, report_id: str) -> Path | None:
        reports_dir = self._reports_dir(space_id)
        if not reports_dir.is_dir():
            return None
        matches = list(reports_dir.glob(f"*-{report_id}.json"))
        return matches[0] if matches else None

    async def save(self, space_id: str, report: TestReport) -> None:
        async with self._lock:
            path = self._report_path(space_id, report)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            try:
                tmp.write_text(
                    json.dumps(report.model_dump(mode="json"), indent=2),
                    encoding="utf-8",
                )
                os.replace(tmp, path)
            except Exception:
                log.exception("Failed to write test report %s/%s", space_id, report.id)
                tmp.unlink(missing_ok=True)
                raise

    async def list_space(self, space_id: str, limit: int = 50) -> list[TestReportSummary]:
        reports_dir = self._reports_dir(space_id)
        if not reports_dir.is_dir():
            return []
        paths = sorted(reports_dir.glob("*.json"))[-limit:]
        results: list[TestReportSummary] = []
        for path in paths:
            try:
                text = await asyncio.to_thread(path.read_text, encoding="utf-8")
                report = TestReport.model_validate_json(text)
                results.append(_to_summary(report))
            except Exception:
                log.warning("Skipping unreadable test report file %s", path)
        return results

    async def list_for_task(
        self, space_id: str, task_id: str, limit: int = 20
    ) -> list[TestReportSummary]:
        all_summaries = await self.list_space(space_id, limit=500)
        task_summaries = [s for s in all_summaries if s.task_id == task_id]
        return task_summaries[-limit:]

    async def get(self, space_id: str, report_id: str) -> TestReport | None:
        path = self._find_by_id(space_id, report_id)
        if path is None:
            return None
        try:
            text = await asyncio.to_thread(path.read_text, encoding="utf-8")
            return TestReport.model_validate_json(text)
        except Exception:
            log.exception("Failed to load test report %s/%s", space_id, report_id)
            return None

    async def get_latest_for_space(self, space_id: str) -> TestReport | None:
        reports_dir = self._reports_dir(space_id)
        if not reports_dir.is_dir():
            return None
        paths = sorted(reports_dir.glob("*.json"))
        if not paths:
            return None
        try:
            text = await asyncio.to_thread(paths[-1].read_text, encoding="utf-8")
            return TestReport.model_validate_json(text)
        except Exception:
            log.exception("Failed to load latest test report for space %s", space_id)
            return None

    async def get_latest_for_task(
        self, space_id: str, task_id: str
    ) -> TestReport | None:
        reports_dir = self._reports_dir(space_id)
        if not reports_dir.is_dir():
            return None
        paths = sorted(reports_dir.glob("*.json"))
        # Walk newest-first to find the latest for this task
        for path in reversed(paths):
            try:
                text = await asyncio.to_thread(path.read_text, encoding="utf-8")
                report = TestReport.model_validate_json(text)
                if report.task_id == task_id:
                    return report
            except Exception:
                log.warning("Skipping unreadable test report file %s", path)
        return None


def _to_summary(report: TestReport) -> TestReportSummary:
    return TestReportSummary(
        id=report.id,
        space_id=report.space_id,
        task_id=report.task_id,
        report_type=report.report_type,
        triggered_by=report.triggered_by,
        started_at=report.started_at,
        ended_at=report.ended_at,
        total_passed=report.total_passed,
        total_failed=report.total_failed,
        total_errors=report.total_errors,
        total_skipped=report.total_skipped,
        total_tests=report.total_tests,
        coverage_pct=report.coverage_pct,
        exit_code=report.exit_code,
        framework=report.framework,
    )
