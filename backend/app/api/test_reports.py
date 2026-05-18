from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..storage import TaskStore
from ..test_report import TestReport, TestReportSummary
from ..test_report_store import TestReportStore

router = APIRouter()


def _get_store(request: Request) -> TestReportStore:
    store: TestReportStore | None = getattr(request.app.state, "test_report_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Test report store not available")
    return store


def _get_task_store(request: Request) -> TaskStore:
    return request.app.state.store


@router.get("/api/spaces/{space_id}/test-reports", response_model=list[TestReportSummary])
async def list_space_test_reports(
    space_id: str, request: Request, limit: int = 50
) -> list[TestReportSummary]:
    store = _get_store(request)
    return await store.list_space(space_id, limit=limit)


@router.get("/api/spaces/{space_id}/test-reports/latest", response_model=TestReport)
async def get_latest_space_test_report(space_id: str, request: Request) -> TestReport:
    store = _get_store(request)
    report = await store.get_latest_for_space(space_id)
    if report is None:
        raise HTTPException(status_code=404, detail="No test reports found for this space")
    return report


@router.get("/api/spaces/{space_id}/test-reports/{report_id}", response_model=TestReport)
async def get_space_test_report(
    space_id: str, report_id: str, request: Request
) -> TestReport:
    store = _get_store(request)
    report = await store.get(space_id, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Test report not found")
    return report


@router.post("/api/spaces/{space_id}/test-reports", response_model=TestReport, status_code=201)
async def ingest_test_report(
    space_id: str, report: TestReport, request: Request
) -> TestReport:
    if report.space_id != space_id:
        raise HTTPException(
            status_code=422,
            detail="space_id in body must match path parameter",
        )
    store = _get_store(request)
    await store.save(space_id, report)
    return report


@router.get("/api/tasks/{task_id}/test-reports", response_model=list[TestReportSummary])
async def list_task_test_reports(
    task_id: str, request: Request, limit: int = 20
) -> list[TestReportSummary]:
    task_store = _get_task_store(request)
    task = task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    store = _get_store(request)
    return await store.list_for_task(task.space_id, task_id, limit=limit)


@router.get("/api/tasks/{task_id}/test-reports/latest", response_model=TestReport)
async def get_latest_task_test_report(task_id: str, request: Request) -> TestReport:
    task_store = _get_task_store(request)
    task = task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    store = _get_store(request)
    report = await store.get_latest_for_task(task.space_id, task_id)
    if report is None:
        raise HTTPException(status_code=404, detail="No test reports found for this task")
    return report
