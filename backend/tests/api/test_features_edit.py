"""Tests for PATCH /api/features/{id} — edit title/brief (I9).

Acceptance criteria:
  - 200 with updated FeatureRead on success.
  - updated_at is bumped after edit.
  - feature_key is unchanged (R12).
  - mirror_feature_to_github called exactly once with reason='edit' on success (R13).
  - mirror_feature_to_github NOT called on 404 paths (R13: call_count == 0).
  - 404 when feature_id does not exist.
  - 404 when task exists but type is not 'feature' or 'fix'.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models import FeatureState, Task, TaskState
from app.storage import TaskNotFound

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

TEST_USER = "testuser"
TEST_PASS = "testpass"
AUTH_HEADER = {
    "Authorization": "Basic "
    + base64.b64encode(f"{TEST_USER}:{TEST_PASS}".encode()).decode()
}

_NOW = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
_UPDATED = _NOW + timedelta(seconds=5)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_space(*, git_repo_url: str | None = "https://github.com/test/repo") -> MagicMock:
    space = MagicMock()
    space.id = "space-1"
    space.name = "Test Space"
    space.color = "#15803D"
    space.icon = None
    space.git_repo_url = git_repo_url
    return space


def _make_task(
    *,
    task_id: str = "2024-01-15-1000-my-feature",
    task_type: str = "feature",
    feature_key: str = "FEAT-001",
    title: str = "Original Title",
    brief: str = "Original brief",
    updated_at: datetime = _NOW,
) -> Task:
    return Task(
        id=task_id,
        space_id="space-1",
        title=title,
        state=TaskState.BACKLOG,
        created_at=_NOW,
        updated_at=updated_at,
        brief=brief,
        type=task_type,
        priority=3,
        feature_key=feature_key,
        feature_state=FeatureState.BACKLOG,
    )


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_client(monkeypatch, tmp_path):
    """TestClient with auth activated and app.state wired to mocks."""
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
# Store fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_store():
    """MagicMock TaskStore with get() and update() stubs."""
    store = MagicMock()
    original = _make_task()
    updated = _make_task(
        title="New Title",
        brief="New brief",
        updated_at=_UPDATED,
    )
    store.get = MagicMock(return_value=original)
    store.update = AsyncMock(return_value=updated)
    return store


@pytest.fixture()
def git_linked_space():
    return _make_space(git_repo_url="https://github.com/test/repo")


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_patch_feature_title_and_brief_success(app_client, mock_store, git_linked_space):
    """PATCH /api/features/{id} with both title and brief returns 200 with updated FeatureRead."""
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature",
            json={"title": "New Title", "brief": "New brief"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["title"] == "New Title"
    assert data["brief"] == "New brief"
    assert mock_mirror.call_count == 1, "mirror must fire exactly once on success (R13)"


def test_patch_feature_title_only(app_client, git_linked_space):
    """PATCH with only title updates title; brief is preserved by store."""
    updated = _make_task(title="Title Only", brief="Original brief", updated_at=_UPDATED)
    store = MagicMock()
    store.get = MagicMock(return_value=_make_task())
    store.update = AsyncMock(return_value=updated)

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature",
            json={"title": "Title Only"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Title Only"


def test_patch_feature_brief_only(app_client, git_linked_space):
    """PATCH with only brief updates brief; title is preserved by store."""
    updated = _make_task(title="Original Title", brief="Brief only", updated_at=_UPDATED)
    store = MagicMock()
    store.get = MagicMock(return_value=_make_task())
    store.update = AsyncMock(return_value=updated)

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature",
            json={"brief": "Brief only"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert response.json()["brief"] == "Brief only"


def test_patch_feature_key_unchanged(app_client, mock_store, git_linked_space):
    """feature_key must be identical before and after PATCH (R12)."""
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature",
            json={"title": "New Title"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert response.json()["feature_key"] == "FEAT-001", "feature_key must not change (R12)"


def test_patch_feature_updated_at_bumped(app_client, git_linked_space):
    """updated_at in response is newer than original updated_at."""
    original = _make_task(updated_at=_NOW)
    updated = _make_task(title="New Title", updated_at=_UPDATED)

    store = MagicMock()
    store.get = MagicMock(return_value=original)
    store.update = AsyncMock(return_value=updated)

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature",
            json={"title": "New Title"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    from datetime import datetime as dt, timezone as tz
    returned_updated_at = dt.fromisoformat(response.json()["updated_at"])
    assert returned_updated_at > _NOW, "updated_at must be newer than original"


def test_patch_feature_mirror_reason_is_edit(app_client, mock_store, git_linked_space):
    """mirror_feature_to_github must be called with reason='edit'."""
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature",
            json={"title": "New Title"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_mirror.call_count == 1
    _, kwargs = mock_mirror.call_args
    assert kwargs.get("reason") == "edit", f"Expected reason='edit', got {kwargs}"


def test_patch_fix_type_succeeds(app_client, git_linked_space):
    """PATCH also works for tasks of type='fix'."""
    fix_task = _make_task(task_type="fix", feature_key="FIX-001")
    updated = _make_task(task_type="fix", feature_key="FIX-001", title="Updated Fix")

    store = MagicMock()
    store.get = MagicMock(return_value=fix_task)
    store.update = AsyncMock(return_value=updated)

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature",
            json={"title": "Updated Fix"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert response.json()["type"] == "fix"


# ---------------------------------------------------------------------------
# 404 paths
# ---------------------------------------------------------------------------


def test_patch_feature_not_found_returns_404(app_client, git_linked_space):
    """Returns 404 when feature_id does not exist; mirror NOT called (R13)."""
    store = MagicMock()
    store.get = MagicMock(return_value=None)

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            "/api/features/nonexistent-id",
            json={"title": "New Title"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    assert mock_mirror.call_count == 0, "mirror must NOT fire on 404 (R13)"


def test_patch_wrong_type_returns_404(app_client, git_linked_space):
    """Returns 404 when task exists but type is not 'feature' or 'fix'; mirror NOT called."""
    regular_task = Task(
        id="2024-01-15-1000-regular",
        space_id="space-1",
        title="Regular Task",
        state=TaskState.BACKLOG,
        created_at=_NOW,
        updated_at=_NOW,
        type="task",
        priority=3,
    )

    store = MagicMock()
    store.get = MagicMock(return_value=regular_task)

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            "/api/features/2024-01-15-1000-regular",
            json={"title": "New Title"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    assert mock_mirror.call_count == 0, "mirror must NOT fire on 404 (R13)"


def test_patch_feature_task_not_found_from_update_returns_404(app_client, git_linked_space):
    """Returns 404 when store.update() raises TaskNotFound (race condition)."""
    original = _make_task()
    store = MagicMock()
    store.get = MagicMock(return_value=original)
    store.update = AsyncMock(side_effect=TaskNotFound("2024-01-15-1000-my-feature"))

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature",
            json={"title": "New Title"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    assert mock_mirror.call_count == 0, "mirror must NOT fire when update raises TaskNotFound"


# ---------------------------------------------------------------------------
# Auth checks
# ---------------------------------------------------------------------------


def test_patch_feature_unauthenticated_returns_401(app_client, mock_store, git_linked_space):
    """PATCH /api/features/{id} without auth returns 401."""
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    response = app_client.patch(
        "/api/features/2024-01-15-1000-my-feature",
        json={"title": "New Title"},
        # No AUTH_HEADER
    )
    assert response.status_code == 401, response.text


# ---------------------------------------------------------------------------
# Null/empty body
# ---------------------------------------------------------------------------


def test_patch_feature_empty_body_succeeds(app_client, git_linked_space):
    """PATCH with no fields in body succeeds (no-op update); mirror still fires once."""
    original = _make_task()
    store = MagicMock()
    store.get = MagicMock(return_value=original)
    store.update = AsyncMock(return_value=original)

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature",
            json={},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_mirror.call_count == 1, "mirror must still fire once even on empty-body PATCH"


def test_patch_feature_response_has_realizing_items(app_client, mock_store, git_linked_space):
    """Response FeatureRead includes realizing_items field (defaulting to empty list)."""
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature",
            json={"title": "New Title"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert "realizing_items" in response.json()
