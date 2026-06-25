"""Tests for DELETE /api/features/{id} — 501 stub (P1-C, line 374).

Verifies that the delete endpoint returns 501 Not Implemented.
"""

from __future__ import annotations

import base64
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

TEST_USER = "testuser"
TEST_PASS = "testpass"
AUTH_HEADER = {
    "Authorization": "Basic "
    + base64.b64encode(f"{TEST_USER}:{TEST_PASS}".encode()).decode()
}


@pytest.fixture()
def app_client(monkeypatch, tmp_path):
    """TestClient with auth activated and app.state wired to mocks."""
    monkeypatch.delenv("CRONOS_BASIC_AUTH_HASH", raising=False)
    monkeypatch.delenv("CRONOS_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", TEST_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", TEST_PASS)
    monkeypatch.setenv("CRONOS_DATA_DIR", str(tmp_path))

    from app.main import app

    app.state.store = MagicMock()
    app.state.space_store = MagicMock()
    app.state.worker_pool = MagicMock()
    app.state.harness_store = MagicMock()
    app.state.memory_store = MagicMock()
    app.state.stats_store = MagicMock()
    app.state.trace_store = MagicMock()
    app.state.test_report_store = MagicMock()

    client = TestClient(app, raise_server_exceptions=False)
    return client


def test_delete_feature_returns_501(app_client):
    """DELETE /api/features/{id} must return 501 Not Implemented (line 374)."""
    response = app_client.delete("/api/features/feat-001", headers=AUTH_HEADER)
    assert response.status_code == 501


def test_delete_feature_unauthenticated_returns_401(app_client):
    """DELETE /api/features/{id} without auth returns 401."""
    response = app_client.delete("/api/features/feat-001")
    assert response.status_code == 401


def test_delete_feature_501_for_any_id(app_client):
    """DELETE /api/features/{id} returns 501 regardless of the feature id."""
    for feat_id in ("feat-001", "nonexistent-id", "FIX-999"):
        response = app_client.delete(f"/api/features/{feat_id}", headers=AUTH_HEADER)
        assert response.status_code == 501, f"Expected 501 for id={feat_id!r}, got {response.status_code}"
