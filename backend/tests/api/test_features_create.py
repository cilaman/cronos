"""Tests for POST /api/features — create a feature or fix (I5).

Acceptance criteria:
  - 400 when space.git_repo_url is None (R11).
  - 404 when space does not exist.
  - 201 with FeatureRead body on success; feature_key matches ^FEAT-NNN$ or ^FIX-NNN$.
  - mirror_feature_to_github called exactly once with reason='create' on success (R13).
  - mirror_feature_to_github NOT called on 400 or 404 paths (R13).
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models import FeatureState, Task, TaskState

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
) -> Task:
    return Task(
        id=task_id,
        space_id="space-1",
        title="My Feature",
        state=TaskState.BACKLOG,
        created_at=_NOW,
        updated_at=_NOW,
        brief="",
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
    monkeypatch.delenv("CRONOS_BASIC_AUTH_HASH", raising=False)
    monkeypatch.delenv("CRONOS_AUTH_DISABLED", raising=False)
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_store():
    """AsyncMock-backed TaskStore with a working create()."""
    store = MagicMock()
    store.create = AsyncMock(return_value=_make_task())
    return store


@pytest.fixture()
def git_linked_space():
    return _make_space(git_repo_url="https://github.com/test/repo")


@pytest.fixture()
def no_git_space():
    return _make_space(git_repo_url=None)


# ---------------------------------------------------------------------------
# Success path — feature
# ---------------------------------------------------------------------------


def test_create_feature_success_201(app_client, mock_store, git_linked_space):
    """POST /api/features with a git-linked space returns 201 and FeatureRead."""
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.post(
            "/api/features",
            json={
                "space_id": "space-1",
                "title": "My Feature",
                "brief": "",
                "type": "feature",
                "priority": 3,
            },
            headers=AUTH_HEADER,
        )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["type"] == "feature"
    assert data["feature_key"] == "FEAT-001"
    assert data["feature_state"] == "backlog"


def test_create_feature_key_format_feat(app_client, mock_store, git_linked_space):
    """feature_key for type='feature' matches ^FEAT-\\d{3}$."""
    import re

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features",
            json={"space_id": "space-1", "title": "Feature X", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 201
    feature_key = response.json()["feature_key"]
    assert re.match(r"^FEAT-\d{3}$", feature_key), f"Bad key: {feature_key}"


def test_create_fix_key_format(app_client, git_linked_space):
    """feature_key for type='fix' matches ^FIX-\\d{3}$."""
    import re

    fix_task = _make_task(task_type="fix", feature_key="FIX-001")
    mock_store = MagicMock()
    mock_store.create = AsyncMock(return_value=fix_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features",
            json={"space_id": "space-1", "title": "Fix Y", "type": "fix"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 201
    feature_key = response.json()["feature_key"]
    assert re.match(r"^FIX-\d{3}$", feature_key), f"Bad key: {feature_key}"


# ---------------------------------------------------------------------------
# Mirror call count assertions (R13)
# ---------------------------------------------------------------------------


def test_mirror_called_once_on_success(app_client, mock_store, git_linked_space):
    """mirror_feature_to_github is called exactly once with reason='create' on success."""
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.post(
            "/api/features",
            json={"space_id": "space-1", "title": "Feat", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 201
    assert mock_mirror.call_count == 1
    _, kwargs = mock_mirror.call_args
    assert kwargs.get("reason") == "create"


def test_mirror_not_called_on_400_no_git(app_client, no_git_space):
    """mirror_feature_to_github is NOT called when space has no git_repo_url."""
    mock_store = MagicMock()
    mock_store.create = AsyncMock()

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = no_git_space

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.post(
            "/api/features",
            json={"space_id": "space-1", "title": "Feat", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 400
    assert mock_mirror.call_count == 0


def test_mirror_not_called_on_404_missing_space(app_client):
    """mirror_feature_to_github is NOT called when space doesn't exist (404)."""
    mock_store = MagicMock()
    app_client.app.state.store = mock_store
    # space_store.get() returns None → space does not exist
    app_client.app.state.space_store.get.return_value = None

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.post(
            "/api/features",
            json={"space_id": "nonexistent", "title": "Feat", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404
    assert mock_mirror.call_count == 0


# ---------------------------------------------------------------------------
# 400 — git_repo_url is None
# ---------------------------------------------------------------------------


def test_400_when_no_git_repo_url(app_client, no_git_space):
    """POST /api/features returns 400 when space.git_repo_url is None."""
    app_client.app.state.space_store.get.return_value = no_git_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features",
            json={"space_id": "space-1", "title": "Feat", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 400
    assert "git" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 404 — space does not exist
# ---------------------------------------------------------------------------


def test_404_when_space_missing(app_client):
    """POST /api/features returns 404 when space_id is unknown."""
    app_client.app.state.space_store.get.return_value = None

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features",
            json={"space_id": "no-such-space", "title": "Feat", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Validation — request body schema
# ---------------------------------------------------------------------------


def test_invalid_type_returns_422(app_client, git_linked_space):
    """POST /api/features with type='task' returns 422 (Pydantic validation)."""
    app_client.app.state.space_store.get.return_value = git_linked_space

    response = app_client.post(
        "/api/features",
        json={"space_id": "space-1", "title": "Bad", "type": "task"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 422


def test_priority_out_of_range_returns_422(app_client, git_linked_space):
    """POST /api/features with priority=10 returns 422 (Pydantic ge=1, le=5)."""
    app_client.app.state.space_store.get.return_value = git_linked_space

    response = app_client.post(
        "/api/features",
        json={"space_id": "space-1", "title": "Bad", "type": "feature", "priority": 10},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 422


def test_missing_title_returns_422(app_client, git_linked_space):
    """POST /api/features without title returns 422."""
    app_client.app.state.space_store.get.return_value = git_linked_space

    response = app_client.post(
        "/api/features",
        json={"space_id": "space-1", "type": "feature"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


def test_response_contains_feature_fields(app_client, mock_store, git_linked_space):
    """Successful response includes all FeatureRead fields."""
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features",
            json={"space_id": "space-1", "title": "My Feature", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 201
    data = response.json()
    # Verify core FeatureRead fields are present
    assert "id" in data
    assert "space_id" in data
    assert "title" in data
    assert "state" in data
    assert "feature_key" in data
    assert "feature_state" in data
    assert "realizing_items" in data
    assert isinstance(data["realizing_items"], list)


def test_response_realizing_items_empty_on_create(app_client, mock_store, git_linked_space):
    """New feature has empty realizing_items list."""
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features",
            json={"space_id": "space-1", "title": "New Feature", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 201
    assert response.json()["realizing_items"] == []


# ---------------------------------------------------------------------------
# 401 — unauthenticated
# ---------------------------------------------------------------------------


def test_unauthenticated_returns_401(app_client):
    """POST /api/features without credentials returns 401."""
    response = app_client.post(
        "/api/features",
        json={"space_id": "space-1", "title": "Feat", "type": "feature"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# store.create raises StorageError → 400
# ---------------------------------------------------------------------------


def test_storage_error_returns_400(app_client, git_linked_space):
    """If store.create() raises StorageError, endpoint returns 400."""
    from app.storage import StorageError

    failing_store = MagicMock()
    failing_store.create = AsyncMock(side_effect=StorageError("disk full"))
    app_client.app.state.store = failing_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.post(
            "/api/features",
            json={"space_id": "space-1", "title": "Feat", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 400
    assert mock_mirror.call_count == 0


# ---------------------------------------------------------------------------
# store.create raises UnknownSpace → 404 (P2-A, line 139)
# ---------------------------------------------------------------------------


def test_unknown_space_on_create_returns_404(app_client, git_linked_space):
    """If store.create() raises UnknownSpace, endpoint returns 404 (line 139)."""
    from app.storage import UnknownSpace

    failing_store = MagicMock()
    failing_store.create = AsyncMock(side_effect=UnknownSpace("space-1"))
    app_client.app.state.store = failing_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.post(
            "/api/features",
            json={"space_id": "space-1", "title": "Feat", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404
    assert mock_mirror.call_count == 0


def test_storage_error_on_create_includes_message(app_client, git_linked_space):
    """StorageError message is propagated in the 400 detail field."""
    from app.storage import StorageError

    failing_store = MagicMock()
    failing_store.create = AsyncMock(side_effect=StorageError("disk full"))
    app_client.app.state.store = failing_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features",
            json={"space_id": "space-1", "title": "Feat", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 400
    assert "disk full" in response.json()["detail"]


# ---------------------------------------------------------------------------
# _log_mirror_error callback logs ERROR when mirror raises (P1-B, line 78)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_mirror_error_callback_logs_on_exception():
    """_log_mirror_error done callback logs ERROR when mirror_feature_to_github raises (line 78)."""
    import asyncio
    import logging

    from app.api.features import _fire_mirror

    task = _make_task()
    space = _make_space()

    errors_logged: list = []

    class _ErrorCapture(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.ERROR:
                errors_logged.append(record)

    handler = _ErrorCapture()
    logger = logging.getLogger("app.api.features")
    logger.addHandler(handler)

    try:
        with patch(
            "app.api.features.mirror_feature_to_github",
            new_callable=AsyncMock,
            side_effect=RuntimeError("simulated mirror failure"),
        ):
            _fire_mirror(task, space, "create")
            # First sleep: run the asyncio task (raises RuntimeError, schedules done callbacks)
            await asyncio.sleep(0)
            # Second sleep: run the done callbacks (scheduled via call_soon after task failure)
            await asyncio.sleep(0)
    finally:
        logger.removeHandler(handler)

    assert len(errors_logged) >= 1, (
        "Expected at least one ERROR log from _log_mirror_error when mirror raises"
    )
    assert any("mirror_feature_to_github" in str(r.msg) for r in errors_logged), (
        "ERROR log must reference 'mirror_feature_to_github'"
    )


# ---------------------------------------------------------------------------
# Brief defaults and passthrough
# ---------------------------------------------------------------------------


def test_brief_passed_to_store_create(app_client, git_linked_space):
    """Brief field is passed to store.create()."""
    task_with_brief = _make_task()
    task_with_brief = task_with_brief.model_copy(update={"brief": "Detailed brief"})

    mock_store = MagicMock()
    mock_store.create = AsyncMock(return_value=task_with_brief)
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = git_linked_space

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features",
            json={
                "space_id": "space-1",
                "title": "Feat",
                "type": "feature",
                "brief": "Detailed brief",
            },
            headers=AUTH_HEADER,
        )

    assert response.status_code == 201
    # Verify store.create was called with the brief
    call_kwargs = mock_store.create.call_args.kwargs
    assert call_kwargs["brief"] == "Detailed brief"
