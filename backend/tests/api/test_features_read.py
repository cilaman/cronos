"""Tests for GET /api/features/{id} — FeatureRead endpoint (I7).

Acceptance criteria (from design report I7):
  - Returns FeatureRead with realizing_items populated from store.realizing_items(id).
  - 404 when feature_id is not found (store.get returns None).
  - 404 when the task exists but type not in ("feature", "fix").
  - mirror_feature_to_github call_count == 0 on GET (R13).
  - Test creates feature F with two tasks T1, T2 having realizes=F; asserts
    realizing_items length == 2.

Auth pattern mirrors test_features_board.py: CRONOS_BASIC_AUTH_USER +
CRONOS_BASIC_AUTH_PASSWORD env vars set via monkeypatch; AUTH_HEADER added
to every authenticated request.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models import FeatureState, TaskState, TaskSummary

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_USER = "testuser"
TEST_PASS = "testpass"
AUTH_HEADER = {
    "Authorization": "Basic "
    + base64.b64encode(f"{TEST_USER}:{TEST_PASS}".encode()).decode()
}

SPACE_ID = "space-read-1"
FEATURE_ID = "2024-02-10-1200-feat-alpha"
FIX_ID = "2024-02-10-1201-fix-beta"
TASK_ID = "2024-02-10-1202-task-ordinary"

_NOW = datetime(2024, 2, 10, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(
    *,
    task_id: str = FEATURE_ID,
    title: str = "Feature Alpha",
    task_type: str = "feature",
    feature_state: FeatureState | None = FeatureState.BACKLOG,
    feature_key: str | None = "FEAT-001",
    realizes: str | None = None,
):
    """Build a minimal Task-like MagicMock with the fields the router accesses."""
    from app.models import Task

    return Task(
        id=task_id,
        space_id=SPACE_ID,
        title=title,
        state=TaskState.BACKLOG,
        created_at=_NOW,
        updated_at=_NOW,
        type=task_type,
        feature_state=feature_state,
        feature_key=feature_key,
        realizes=realizes,
    )


def _make_summary(
    *,
    task_id: str,
    title: str = "Realizing Task",
    task_type: str = "task",
    realizes: str | None = FEATURE_ID,
) -> TaskSummary:
    return TaskSummary(
        id=task_id,
        space_id=SPACE_ID,
        title=title,
        state=TaskState.BACKLOG,
        created_at=_NOW,
        updated_at=_NOW,
        type=task_type,
        realizes=realizes,
    )


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_client(monkeypatch, tmp_path):
    """TestClient with auth activated and minimal app.state wired."""
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", TEST_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", TEST_PASS)
    monkeypatch.setenv("CRONOS_DATA_DIR", str(tmp_path))

    from app.main import app

    app.state.space_store = MagicMock()
    app.state.worker_pool = MagicMock()
    app.state.harness_store = MagicMock()
    app.state.memory_store = MagicMock()
    app.state.stats_store = MagicMock()
    app.state.trace_store = MagicMock()
    app.state.test_report_store = MagicMock()

    client = TestClient(app, raise_server_exceptions=False)
    return client


# ---------------------------------------------------------------------------
# Success path — feature with two realizing items
# ---------------------------------------------------------------------------


def test_get_feature_returns_feature_read(app_client):
    """GET /api/features/{id} returns 200 with a FeatureRead body."""
    feature = _make_task(task_id=FEATURE_ID, task_type="feature")
    mock_store = MagicMock()
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.get(f"/api/features/{FEATURE_ID}", headers=AUTH_HEADER)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == FEATURE_ID
    assert data["type"] == "feature"
    assert data["feature_key"] == "FEAT-001"
    assert data["realizing_items"] == []
    # R13: no mirror call on GET
    assert mock_mirror.call_count == 0


def test_get_feature_with_two_realizing_items(app_client):
    """GET /api/features/{id} returns realizing_items with length 2 (design acceptance criterion)."""
    feature = _make_task(task_id=FEATURE_ID, task_type="feature")
    t1 = _make_summary(task_id="2024-02-10-1300-task-t1", title="Task T1", realizes=FEATURE_ID)
    t2 = _make_summary(task_id="2024-02-10-1301-task-t2", title="Task T2", realizes=FEATURE_ID)

    mock_store = MagicMock()
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[t1, t2])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.get(f"/api/features/{FEATURE_ID}", headers=AUTH_HEADER)

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["realizing_items"]) == 2, (
        f"Expected 2 realizing items, got {len(data['realizing_items'])}"
    )
    item_ids = {item["id"] for item in data["realizing_items"]}
    assert "2024-02-10-1300-task-t1" in item_ids
    assert "2024-02-10-1301-task-t2" in item_ids
    # R13: no mirror call on GET
    assert mock_mirror.call_count == 0


def test_get_fix_returns_feature_read(app_client):
    """GET /api/features/{id} also works when the task has type='fix'."""
    fix = _make_task(task_id=FIX_ID, task_type="fix", feature_key="FIX-001")
    mock_store = MagicMock()
    mock_store.get.return_value = fix
    mock_store.realizing_items = AsyncMock(return_value=[])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.get(f"/api/features/{FIX_ID}", headers=AUTH_HEADER)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["type"] == "fix"
    assert data["feature_key"] == "FIX-001"


# ---------------------------------------------------------------------------
# store.realizing_items called with correct feature_id
# ---------------------------------------------------------------------------


def test_realizing_items_called_with_feature_id(app_client):
    """store.realizing_items() is called with exactly the feature_id path param."""
    feature = _make_task(task_id=FEATURE_ID, task_type="feature")
    mock_store = MagicMock()
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        app_client.get(f"/api/features/{FEATURE_ID}", headers=AUTH_HEADER)

    mock_store.realizing_items.assert_called_once_with(FEATURE_ID)


# ---------------------------------------------------------------------------
# 404 — feature not found (store.get returns None)
# ---------------------------------------------------------------------------


def test_404_when_feature_not_found(app_client):
    """GET /api/features/{id} returns 404 when the ID does not exist."""
    mock_store = MagicMock()
    mock_store.get.return_value = None
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.get("/api/features/nonexistent-id", headers=AUTH_HEADER)

    assert response.status_code == 404, response.text
    # R13: no mirror call on 404
    assert mock_mirror.call_count == 0


# ---------------------------------------------------------------------------
# 404 — task exists but type is not "feature" or "fix"
# ---------------------------------------------------------------------------


def test_404_when_task_type_is_task(app_client):
    """GET /api/features/{id} returns 404 when the task has type='task'."""
    ordinary_task = _make_task(
        task_id=TASK_ID,
        title="Ordinary Task",
        task_type="task",
        feature_state=None,
        feature_key=None,
    )
    mock_store = MagicMock()
    mock_store.get.return_value = ordinary_task
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.get(f"/api/features/{TASK_ID}", headers=AUTH_HEADER)

    assert response.status_code == 404, response.text
    # store.realizing_items should NOT be called when the type guard fails
    mock_store.realizing_items.assert_not_called()
    # R13: no mirror call on 404
    assert mock_mirror.call_count == 0


def test_404_when_task_type_is_goal(app_client):
    """GET /api/features/{id} returns 404 when the task has type='goal'."""
    goal_task = _make_task(
        task_id="2024-02-10-1400-goal-foo",
        title="Goal Foo",
        task_type="goal",
        feature_state=None,
        feature_key=None,
    )
    mock_store = MagicMock()
    mock_store.get.return_value = goal_task
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.get("/api/features/2024-02-10-1400-goal-foo", headers=AUTH_HEADER)

    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# R13 — mirror call_count == 0 on GET /{id}
# ---------------------------------------------------------------------------


def test_mirror_not_called_on_get_by_id(app_client):
    """mirror_feature_to_github must NOT be called on GET /api/features/{id} (R13)."""
    feature = _make_task(task_id=FEATURE_ID, task_type="feature")
    mock_store = MagicMock()
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[])
    app_client.app.state.store = mock_store

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.get(f"/api/features/{FEATURE_ID}", headers=AUTH_HEADER)

    assert response.status_code == 200
    assert mock_mirror.call_count == 0, (
        f"mirror_feature_to_github was called {mock_mirror.call_count} time(s) "
        f"on GET /api/features/{{id}} — must be 0 (R13)."
    )


# ---------------------------------------------------------------------------
# 401 — unauthenticated
# ---------------------------------------------------------------------------


def test_unauthenticated_returns_401(app_client):
    """GET /api/features/{id} without credentials returns 401 (R14)."""
    response = app_client.get(f"/api/features/{FEATURE_ID}")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Response shape — FeatureRead fields
# ---------------------------------------------------------------------------


def test_response_contains_feature_read_fields(app_client):
    """Response body includes standard FeatureRead fields."""
    feature = _make_task(
        task_id=FEATURE_ID,
        title="Alpha Feature",
        task_type="feature",
        feature_state=FeatureState.PLANNED,
        feature_key="FEAT-042",
    )
    mock_store = MagicMock()
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.get(f"/api/features/{FEATURE_ID}", headers=AUTH_HEADER)

    assert response.status_code == 200, response.text
    data = response.json()
    # Core FeatureRead fields
    assert data["id"] == FEATURE_ID
    assert data["space_id"] == SPACE_ID
    assert data["title"] == "Alpha Feature"
    assert data["type"] == "feature"
    assert data["feature_state"] == "planned"
    assert data["feature_key"] == "FEAT-042"
    assert "realizing_items" in data


def test_realizing_items_contain_task_summary_fields(app_client):
    """Items in realizing_items contain standard TaskSummary fields."""
    feature = _make_task(task_id=FEATURE_ID, task_type="feature")
    t1 = _make_summary(task_id="2024-02-10-1500-task-check", title="Check Task", realizes=FEATURE_ID)
    mock_store = MagicMock()
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[t1])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.get(f"/api/features/{FEATURE_ID}", headers=AUTH_HEADER)

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["realizing_items"]) == 1
    item = data["realizing_items"][0]
    assert item["id"] == "2024-02-10-1500-task-check"
    assert item["title"] == "Check Task"
    assert item["space_id"] == SPACE_ID
    assert item["realizes"] == FEATURE_ID
