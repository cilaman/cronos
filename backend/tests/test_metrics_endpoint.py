"""Tests: GET /api/metrics endpoint (I5)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.metrics import router as metrics_router
from app.worker_pool import WorkerPool


def _make_test_app(pool: "WorkerPool | None" = None) -> FastAPI:
    """Minimal FastAPI app with only the metrics router; no lifespan."""
    test_app = FastAPI()
    test_app.include_router(metrics_router)
    test_app.state.worker_pool = pool
    return test_app


def _make_mock_pool(*, queue_depth: int = 0, active_tasks: int = 0, auto_resume_total: int = 0):
    pool = MagicMock(spec=WorkerPool)
    workers = []
    if queue_depth > 0 or active_tasks > 0 or auto_resume_total > 0:
        w = MagicMock()
        q = MagicMock()
        q.qsize.return_value = queue_depth
        w._queue = q
        w._current_id = "some-task" if active_tasks > 0 else None
        w._auto_resume_counts = {"t": auto_resume_total} if auto_resume_total > 0 else {}
        workers.append(w)
    pool.all_workers.return_value = workers
    return pool


class TestMetricsEndpoint:
    def test_metrics_returns_200(self):
        """GET /api/metrics returns 200 OK."""
        client = TestClient(_make_test_app())
        resp = client.get("/api/metrics")
        assert resp.status_code == 200

    def test_metrics_returns_required_fields(self):
        """Response includes queue_depth, active_tasks, auto_resume_total."""
        client = TestClient(_make_test_app())
        data = client.get("/api/metrics").json()
        assert "queue_depth" in data
        assert "active_tasks" in data
        assert "auto_resume_total" in data

    def test_metrics_values_are_integers(self):
        """All numeric fields are non-negative integers."""
        client = TestClient(_make_test_app())
        data = client.get("/api/metrics").json()
        for key in ("queue_depth", "active_tasks", "auto_resume_total"):
            assert isinstance(data[key], int), f"{key} should be int"
            assert data[key] >= 0, f"{key} should be non-negative"

    def test_metrics_with_empty_pool(self):
        """All counters are zero when pool has no workers."""
        pool = _make_mock_pool()
        client = TestClient(_make_test_app(pool))
        data = client.get("/api/metrics").json()
        assert data["queue_depth"] == 0
        assert data["active_tasks"] == 0
        assert data["auto_resume_total"] == 0

    def test_metrics_aggregates_worker_state(self):
        """Counters reflect the mock pool's worker state."""
        pool = _make_mock_pool(queue_depth=3, active_tasks=1, auto_resume_total=2)
        client = TestClient(_make_test_app(pool))
        data = client.get("/api/metrics").json()
        assert data["queue_depth"] == 3
        assert data["active_tasks"] == 1
        assert data["auto_resume_total"] == 2

    def test_metrics_without_pool_returns_zeros(self):
        """If worker_pool is None on app.state, all counters are zero."""
        client = TestClient(_make_test_app(pool=None))
        data = client.get("/api/metrics").json()
        assert data["queue_depth"] == 0
        assert data["active_tasks"] == 0
        assert data["auto_resume_total"] == 0

    def test_metrics_multiple_workers_aggregated(self):
        """queue_depth and auto_resume_total sum across all workers."""
        pool = MagicMock(spec=WorkerPool)
        workers = []
        for i in range(3):
            w = MagicMock()
            q = MagicMock()
            q.qsize.return_value = 2  # 2 each × 3 workers = 6 total
            w._queue = q
            w._current_id = "t" if i < 2 else None  # 2 active
            w._auto_resume_counts = {"x": 1}  # 1 each × 3 = 3 total
            workers.append(w)
        pool.all_workers.return_value = workers
        client = TestClient(_make_test_app(pool))
        data = client.get("/api/metrics").json()
        assert data["queue_depth"] == 6
        assert data["active_tasks"] == 2
        assert data["auto_resume_total"] == 3
