"""Tests for GET /api/info build-metadata endpoint (I3).

Covers:
1. Env vars PRESENT  → HTTP 200, fields match the set values.
2. Env vars ABSENT   → HTTP 200, all three fields are null.
3. Response shape    → exactly the three expected keys.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENV_VARS = ("BUILD_COMMIT", "BUILD_TIME", "BUILD_REPO_URL")


def _get_info():
    response = client.get("/api/info")
    return response


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_info_env_vars_present(monkeypatch):
    """When BUILD_* vars are set, the endpoint reflects them in the response."""
    monkeypatch.setenv("BUILD_COMMIT", "abc1234")
    monkeypatch.setenv("BUILD_TIME", "2026-05-31T15:00:00Z")
    monkeypatch.setenv("BUILD_REPO_URL", "https://github.com/example/cronos")

    response = _get_info()

    assert response.status_code == 200
    data = response.json()
    assert data["commit_sha"] == "abc1234"
    assert data["build_time"] == "2026-05-31T15:00:00Z"
    assert data["repo_url"] == "https://github.com/example/cronos"


def test_info_env_vars_absent(monkeypatch):
    """When BUILD_* vars are absent, the endpoint returns HTTP 200 with null fields."""
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    response = _get_info()

    assert response.status_code == 200
    data = response.json()
    assert data["commit_sha"] is None
    assert data["build_time"] is None
    assert data["repo_url"] is None


def test_info_response_shape(monkeypatch):
    """Response must contain exactly commit_sha, build_time, and repo_url keys."""
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    response = _get_info()

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"commit_sha", "build_time", "repo_url"}
