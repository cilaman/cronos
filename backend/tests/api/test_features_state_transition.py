"""Tests for PATCH /api/features/{id}/feature-state — state transition (I8).

Acceptance criteria:
  - FEATURE_USER_TRANSITIONS is imported from feature_state module, not redeclared (R-risk).
  - 200 + FeatureRead on valid transition; feature_key unchanged (R12).
  - mirror_feature_to_github called exactly once with reason='state_change' on success (R13).
  - 409 on illegal transition; mirror NOT called (R13).
  - 404 on missing feature_id; mirror NOT called (R13).
  - 404 when task exists but type not in ('feature', 'fix'); mirror NOT called.
"""

from __future__ import annotations

import base64
import importlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models import FeatureState, Task, TaskState
from app.storage import InvalidTransition, TaskNotFound

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


def _make_space(*, space_id: str = "space-1", git_repo_url: str | None = "https://github.com/test/repo") -> MagicMock:
    space = MagicMock()
    space.id = space_id
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
    feature_state: FeatureState = FeatureState.BACKLOG,
    space_id: str = "space-1",
) -> Task:
    return Task(
        id=task_id,
        space_id=space_id,
        title="My Feature",
        state=TaskState.BACKLOG,
        created_at=_NOW,
        updated_at=_NOW,
        brief="",
        type=task_type,
        priority=3,
        feature_key=feature_key,
        feature_state=feature_state,
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
# Contract: FEATURE_USER_TRANSITIONS is imported from feature_state, not local
# ---------------------------------------------------------------------------


def test_feature_user_transitions_imported_from_feature_state_module():
    """api/features.py must import FEATURE_USER_TRANSITIONS from feature_state, not redeclare."""
    import app.api.features as features_module
    import app.feature_state as fs_module

    # The constant in api.features must be the exact same object as in feature_state
    assert hasattr(features_module, "FEATURE_USER_TRANSITIONS"), (
        "FEATURE_USER_TRANSITIONS must be importable from app.api.features"
    )
    assert features_module.FEATURE_USER_TRANSITIONS is fs_module.FEATURE_USER_TRANSITIONS, (
        "FEATURE_USER_TRANSITIONS in api/features.py must be the same object as "
        "app.feature_state.FEATURE_USER_TRANSITIONS (import, not redeclare)"
    )


def test_feature_user_transitions_is_frozenset():
    """FEATURE_USER_TRANSITIONS must be a frozenset of (FeatureState, FeatureState) tuples."""
    import app.feature_state as fs_module

    assert isinstance(fs_module.FEATURE_USER_TRANSITIONS, frozenset), (
        "FEATURE_USER_TRANSITIONS must be a frozenset"
    )
    for item in fs_module.FEATURE_USER_TRANSITIONS:
        assert isinstance(item, tuple) and len(item) == 2, (
            f"Expected 2-tuple, got {item!r}"
        )
        from_state, to_state = item
        assert isinstance(from_state, FeatureState), f"Expected FeatureState, got {from_state!r}"
        assert isinstance(to_state, FeatureState), f"Expected FeatureState, got {to_state!r}"


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_patch_feature_state_success_200(app_client):
    """Valid transition returns 200 with FeatureRead body."""
    original_task = _make_task(feature_state=FeatureState.BACKLOG)
    updated_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(return_value=updated_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ):
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature/feature-state",
            json={"feature_state": "processing"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["feature_state"] == "processing"


def test_patch_feature_state_feature_key_unchanged(app_client):
    """feature_key must be unchanged after transition (R12)."""
    original_task = _make_task(feature_key="FEAT-042", feature_state=FeatureState.BACKLOG)
    updated_task = _make_task(feature_key="FEAT-042", feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(return_value=updated_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature/feature-state",
            json={"feature_state": "processing"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert response.json()["feature_key"] == "FEAT-042", "feature_key must not change on state transition"


def test_patch_feature_state_mirror_called_once_on_success(app_client):
    """mirror_feature_to_github must be called exactly once with reason='state_change' (R13)."""
    original_task = _make_task(feature_state=FeatureState.BACKLOG)
    updated_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(return_value=updated_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature/feature-state",
            json={"feature_state": "processing"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_mirror.call_count == 1, f"Expected mirror call_count=1, got {mock_mirror.call_count}"
    # Verify reason='state_change'
    call_kwargs = mock_mirror.call_args
    assert call_kwargs.kwargs.get("reason") == "state_change", (
        f"Expected reason='state_change', got {call_kwargs.kwargs.get('reason')!r}"
    )


def test_patch_feature_state_transition_feature_called_with_user_transitions(app_client):
    """transition_feature must be called with allowed=FEATURE_USER_TRANSITIONS."""
    from app.feature_state import FEATURE_USER_TRANSITIONS

    original_task = _make_task(feature_state=FeatureState.BACKLOG)
    updated_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(return_value=updated_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature/feature-state",
            json={"feature_state": "processing"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    call_args = mock_store.transition_feature.call_args
    assert call_args.kwargs.get("allowed") is FEATURE_USER_TRANSITIONS, (
        "transition_feature must be called with allowed=FEATURE_USER_TRANSITIONS (the exact imported object)"
    )


def test_patch_fix_type_transitions_successfully(app_client):
    """Feature-state transition also works for type='fix'."""
    original_task = _make_task(task_type="fix", feature_key="FIX-001", feature_state=FeatureState.BACKLOG)
    updated_task = _make_task(task_type="fix", feature_key="FIX-001", feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(return_value=updated_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature/feature-state",
            json={"feature_state": "processing"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert response.json()["feature_key"] == "FIX-001"
    assert mock_mirror.call_count == 1


# ---------------------------------------------------------------------------
# Error paths: 409 on illegal transition
# ---------------------------------------------------------------------------


def test_patch_feature_state_illegal_transition_returns_409(app_client):
    """An illegal transition must return 409 (R6)."""
    original_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(
        side_effect=InvalidTransition("Cannot move feature from 'processing' to 'done'")
    )

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature/feature-state",
            json={"feature_state": "done"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 409, response.text
    assert mock_mirror.call_count == 0, (
        f"Mirror must NOT be called on 409; got call_count={mock_mirror.call_count}"
    )


def test_patch_feature_state_illegal_transition_detail_message(app_client):
    """409 response must include a descriptive detail message."""
    original_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(
        side_effect=InvalidTransition("Cannot move feature from 'processing' to 'done'")
    )

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature/feature-state",
            json={"feature_state": "done"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 409
    detail = response.json().get("detail", "")
    assert detail, "409 response must include a 'detail' field with a description"


def test_patch_feature_state_storage_error_returns_409(app_client):
    """A generic StorageError (superclass of InvalidTransition) also returns 409."""
    from app.storage import StorageError as SE

    original_task = _make_task(feature_state=FeatureState.BACKLOG)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(
        side_effect=SE("Some storage constraint violated")
    )

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature/feature-state",
            json={"feature_state": "processing"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 409
    assert mock_mirror.call_count == 0


# ---------------------------------------------------------------------------
# Error paths: 404 on missing feature
# ---------------------------------------------------------------------------


def test_patch_feature_state_missing_feature_returns_404(app_client):
    """Missing feature_id must return 404."""
    mock_store = MagicMock()
    mock_store.get.return_value = None
    mock_store.transition_feature = AsyncMock(side_effect=TaskNotFound("no-such-id"))

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            "/api/features/no-such-id/feature-state",
            json={"feature_state": "processing"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    assert mock_mirror.call_count == 0, (
        f"Mirror must NOT be called on 404; got call_count={mock_mirror.call_count}"
    )


def test_patch_feature_state_wrong_type_returns_404(app_client):
    """A task that exists but has type='task' must return 404 (not a feature/fix)."""
    task_not_feature = Task(
        id="2024-01-15-1000-regular-task",
        space_id="space-1",
        title="Regular Task",
        state=TaskState.BACKLOG,
        created_at=_NOW,
        updated_at=_NOW,
        brief="",
        type="task",  # NOT feature or fix
        priority=3,
    )

    mock_store = MagicMock()
    mock_store.get.return_value = task_not_feature

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            "/api/features/2024-01-15-1000-regular-task/feature-state",
            json={"feature_state": "processing"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    assert mock_mirror.call_count == 0


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_patch_feature_state_invalid_state_value_returns_422(app_client):
    """An unknown feature_state value must return 422 Unprocessable Entity."""
    mock_store = MagicMock()
    mock_store.get.return_value = _make_task()

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    response = app_client.patch(
        "/api/features/2024-01-15-1000-my-feature/feature-state",
        json={"feature_state": "not_a_real_state"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 422


def test_patch_feature_state_missing_body_returns_422(app_client):
    """A missing body must return 422."""
    mock_store = MagicMock()
    mock_store.get.return_value = _make_task()

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    response = app_client.patch(
        "/api/features/2024-01-15-1000-my-feature/feature-state",
        headers=AUTH_HEADER,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_patch_feature_state_unauthenticated_returns_401(app_client):
    """Unauthenticated request must return 401."""
    response = app_client.patch(
        "/api/features/some-id/feature-state",
        json={"feature_state": "processing"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Same-state idempotency
# ---------------------------------------------------------------------------


def test_patch_feature_state_same_state_idempotent(app_client):
    """Transitioning to the current state should be idempotent (not an error)."""
    task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = task
    # transition_feature returns the unchanged task when same-state
    mock_store.transition_feature = AsyncMock(return_value=task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.patch(
            "/api/features/2024-01-15-1000-my-feature/feature-state",
            json={"feature_state": "processing"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    # Mirror is still fired once even for same-state (state "confirmed", not skipped by router)
    assert mock_mirror.call_count == 1
