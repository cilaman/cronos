"""Tests for PATCH /api/features/{id}/realize — set_realizes link/unlink (I10).

Acceptance criteria (from design report I10):
  - Calls store.set_realizes(body.item_id, body.feature_id or None).
  - Self-reference (item_id == feature_id) → 400.
  - Cross-space attempt → 400.
  - mirror_feature_to_github call_count == 0 (R13: no mirror on realize).
  - After link, GET /api/features/{F} realizing_items reflects the new item.
  - 404 when item_id is not found (TaskNotFound).

Auth pattern mirrors test_features_read.py: CRONOS_BASIC_AUTH_USER +
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

SPACE_ID = "space-realize-1"
FEATURE_ID = "2024-03-01-1200-feat-one"
ITEM_ID = "2024-03-01-1300-task-item"
OTHER_ITEM_ID = "2024-03-01-1400-task-other"

_NOW = datetime(2024, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature(
    *,
    task_id: str = FEATURE_ID,
    task_type: str = "feature",
    feature_key: str | None = "FEAT-001",
) -> "app.models.Task":
    from app.models import Task

    return Task(
        id=task_id,
        space_id=SPACE_ID,
        title="Feature One",
        state=TaskState.BACKLOG,
        created_at=_NOW,
        updated_at=_NOW,
        type=task_type,
        feature_state=FeatureState.BACKLOG,
        feature_key=feature_key,
    )


def _make_item(
    *,
    task_id: str = ITEM_ID,
    realizes: str | None = None,
) -> "app.models.Task":
    from app.models import Task

    return Task(
        id=task_id,
        space_id=SPACE_ID,
        title="Item Task",
        state=TaskState.BACKLOG,
        created_at=_NOW,
        updated_at=_NOW,
        type="task",
        realizes=realizes,
    )


def _make_summary(
    *,
    task_id: str = ITEM_ID,
    title: str = "Item Task",
    realizes: str | None = FEATURE_ID,
) -> TaskSummary:
    return TaskSummary(
        id=task_id,
        space_id=SPACE_ID,
        title=title,
        state=TaskState.BACKLOG,
        created_at=_NOW,
        updated_at=_NOW,
        type="task",
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
# Success path — link an item to a feature
# ---------------------------------------------------------------------------


def test_realize_link_returns_200(app_client):
    """PATCH /realize with a valid item_id and feature_id returns 200."""
    feature = _make_feature()
    item = _make_item(realizes=FEATURE_ID)
    summary = _make_summary()

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(return_value=item)
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[summary])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID, "feature_id": FEATURE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == FEATURE_ID
    assert data["type"] == "feature"
    # R13: no mirror call on realize endpoint
    assert mock_mirror.call_count == 0


def test_realize_link_realizing_items_reflects_new_item(app_client):
    """After link, realizing_items in the response contains the linked item."""
    feature = _make_feature()
    item_after = _make_item(realizes=FEATURE_ID)
    summary = _make_summary(task_id=ITEM_ID, realizes=FEATURE_ID)

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(return_value=item_after)
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[summary])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID, "feature_id": FEATURE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    data = response.json()
    realizing_ids = [item["id"] for item in data["realizing_items"]]
    assert ITEM_ID in realizing_ids, f"Expected {ITEM_ID} in realizing_items; got {realizing_ids}"


def test_realize_set_realizes_called_with_correct_args(app_client):
    """store.set_realizes is called with (body.item_id, body.feature_id)."""
    feature = _make_feature()
    item = _make_item(realizes=FEATURE_ID)

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(return_value=item)
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID, "feature_id": FEATURE_ID},
            headers=AUTH_HEADER,
        )

    mock_store.set_realizes.assert_called_once_with(ITEM_ID, FEATURE_ID)


# ---------------------------------------------------------------------------
# Unlink path (feature_id = None)
# ---------------------------------------------------------------------------


def test_realize_unlink_returns_200(app_client):
    """PATCH /realize with feature_id=None (unlink) returns 200."""
    feature = _make_feature()
    item_after = _make_item(realizes=None)

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(return_value=item_after)
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID, "feature_id": None},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["realizing_items"] == []
    # R13: no mirror on unlink either
    assert mock_mirror.call_count == 0


def test_realize_unlink_omit_feature_id_returns_200(app_client):
    """PATCH /realize with feature_id omitted (defaults to None) returns 200."""
    feature = _make_feature()
    item_after = _make_item(realizes=None)

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(return_value=item_after)
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_mirror.call_count == 0


def test_realize_unlink_set_realizes_called_with_none(app_client):
    """When feature_id=None, store.set_realizes is called with (item_id, None)."""
    feature = _make_feature()
    item_after = _make_item(realizes=None)

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(return_value=item_after)
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID, "feature_id": None},
            headers=AUTH_HEADER,
        )

    mock_store.set_realizes.assert_called_once_with(ITEM_ID, None)


# ---------------------------------------------------------------------------
# Error paths — TaskNotFound → 404
# ---------------------------------------------------------------------------


def test_realize_item_not_found_returns_404(app_client):
    """PATCH /realize returns 404 when item_id does not exist (TaskNotFound)."""
    from app.storage import TaskNotFound

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(side_effect=TaskNotFound("missing-id"))
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": "missing-id", "feature_id": FEATURE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    # R13: no mirror even on error
    assert mock_mirror.call_count == 0


# ---------------------------------------------------------------------------
# Error paths — CycleError → 400 (self-reference, cross-space, wrong type)
# ---------------------------------------------------------------------------


def test_realize_self_reference_returns_400(app_client):
    """Self-reference (item_id == feature_id) raises CycleError → 400."""
    from app.storage import CycleError

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(
        side_effect=CycleError(f"{FEATURE_ID} cannot realize itself")
    )
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": FEATURE_ID, "feature_id": FEATURE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 400, response.text
    assert "cannot realize itself" in response.json()["detail"]
    # R13: no mirror on validation failure
    assert mock_mirror.call_count == 0


def test_realize_cross_space_returns_400(app_client):
    """Cross-space attempt raises CycleError → 400."""
    from app.storage import CycleError

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(
        side_effect=CycleError(f"Feature {FEATURE_ID!r} not found in space 'other-space'")
    )
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID, "feature_id": FEATURE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 400, response.text
    assert mock_mirror.call_count == 0


def test_realize_wrong_target_type_returns_400(app_client):
    """Pointing realizes at a non-feature/fix task raises CycleError → 400."""
    from app.storage import CycleError

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(
        side_effect=CycleError("Target 'some-task' has type 'task'; realizes must point to a feature or fix")
    )
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID, "feature_id": "some-task"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 400, response.text
    assert mock_mirror.call_count == 0


def test_realize_storage_error_returns_400(app_client):
    """A generic StorageError from set_realizes → 400."""
    from app.storage import StorageError

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(side_effect=StorageError("generic storage problem"))
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID, "feature_id": FEATURE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 400, response.text
    assert mock_mirror.call_count == 0


# ---------------------------------------------------------------------------
# R13 mirror count == 0 — explicit assertion across all paths
# ---------------------------------------------------------------------------


def test_realize_mirror_call_count_zero_on_success(app_client):
    """R13: mirror_feature_to_github is never called by the realize endpoint."""
    feature = _make_feature()
    item = _make_item(realizes=FEATURE_ID)
    summary = _make_summary()

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(return_value=item)
    mock_store.get.return_value = feature
    mock_store.realizing_items = AsyncMock(return_value=[summary])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID, "feature_id": FEATURE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_mirror.call_count == 0, (
        f"R13 violation: mirror was called {mock_mirror.call_count} times on realize endpoint"
    )


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_realize_missing_item_id_returns_422(app_client):
    """PATCH /realize without item_id in body → 422 (schema validation)."""
    mock_store = MagicMock()
    app_client.app.state.store = mock_store

    response = app_client.patch(
        f"/api/features/{FEATURE_ID}/realize",
        json={"feature_id": FEATURE_ID},
        headers=AUTH_HEADER,
    )

    assert response.status_code == 422, response.text


def test_realize_empty_body_returns_422(app_client):
    """PATCH /realize with empty body → 422 (item_id required)."""
    mock_store = MagicMock()
    app_client.app.state.store = mock_store

    response = app_client.patch(
        f"/api/features/{FEATURE_ID}/realize",
        json={},
        headers=AUTH_HEADER,
    )

    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


def test_realize_unauthenticated_returns_401(app_client):
    """PATCH /realize without credentials → 401."""
    mock_store = MagicMock()
    app_client.app.state.store = mock_store

    response = app_client.patch(
        f"/api/features/{FEATURE_ID}/realize",
        json={"item_id": ITEM_ID, "feature_id": FEATURE_ID},
    )

    assert response.status_code == 401, response.text


# ---------------------------------------------------------------------------
# P2-E: feature not found after set_realizes succeeds → 404 (line 324)
# ---------------------------------------------------------------------------


def test_realize_feature_not_found_after_set_realizes_returns_404(app_client):
    """Returns 404 when feature is not found after set_realizes succeeds (TOCTOU, line 324)."""
    mock_store = MagicMock()
    # set_realizes succeeds (returns normally)
    mock_store.set_realizes = AsyncMock(return_value=None)
    # Feature deleted between set_realizes and the subsequent get
    mock_store.get.return_value = None

    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID, "feature_id": FEATURE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    assert mock_mirror.call_count == 0


def test_realize_wrong_type_after_set_realizes_returns_404(app_client):
    """Returns 404 when feature ID resolves to a non-feature task after set_realizes (line 324)."""
    from app.models import Task

    non_feature = Task(
        id=FEATURE_ID,
        space_id=SPACE_ID,
        title="Regular Task",
        state=TaskState.BACKLOG,
        created_at=_NOW,
        updated_at=_NOW,
        type="task",  # not feature or fix
    )

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(return_value=None)
    mock_store.get.return_value = non_feature

    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID, "feature_id": FEATURE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    assert mock_mirror.call_count == 0


# ---------------------------------------------------------------------------
# Fix type also works
# ---------------------------------------------------------------------------


def test_realize_works_with_fix_type(app_client):
    """PATCH /realize also returns the FeatureRead when target is type='fix'."""
    fix = _make_feature(task_id=FEATURE_ID, task_type="fix", feature_key="FIX-001")
    item = _make_item(realizes=FEATURE_ID)
    summary = _make_summary()

    mock_store = MagicMock()
    mock_store.set_realizes = AsyncMock(return_value=item)
    mock_store.get.return_value = fix
    mock_store.realizing_items = AsyncMock(return_value=[summary])
    app_client.app.state.store = mock_store

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": ITEM_ID, "feature_id": FEATURE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["type"] == "fix"
    assert mock_mirror.call_count == 0
