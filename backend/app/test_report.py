from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TestCase(BaseModel):
    id: str
    name: str
    status: Literal["passed", "failed", "error", "skipped"]
    duration_seconds: float | None = None
    error_message: str | None = None
    file_path: str | None = None
    line: int | None = None


class TestSuite(BaseModel):
    name: str
    tests: list[TestCase]
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_seconds: float


class TestReport(BaseModel):
    id: str
    space_id: str
    task_id: str | None = None
    report_type: Literal["task", "space"]
    triggered_by: str
    started_at: datetime
    ended_at: datetime
    suites: list[TestSuite]
    total_passed: int
    total_failed: int
    total_errors: int
    total_skipped: int
    total_tests: int
    coverage_pct: float | None = None
    coverage_data: dict[str, float] | None = None
    exit_code: int
    raw_output: str
    framework: str


class TestReportSummary(BaseModel):
    id: str
    space_id: str
    task_id: str | None = None
    report_type: Literal["task", "space"]
    triggered_by: str
    started_at: datetime
    ended_at: datetime
    total_passed: int
    total_failed: int
    total_errors: int
    total_skipped: int
    total_tests: int
    coverage_pct: float | None = None
    exit_code: int
    framework: str
