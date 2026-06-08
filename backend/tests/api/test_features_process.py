"""Tests for POST /api/features/{id}/process — transition to PROCESSING + S4 enqueue (I11).

Acceptance criteria:
  - 200 + FeatureRead on valid transition to PROCESSING state.
  - mirror_feature_to_github called exactly once with reason='state_change' on success (R13).
  - enqueue_feature_decomposition called exactly once on success.
  - 409 on second invocation (PROCESSING→PROCESSING is not in FEATURE_USER_TRANSITIONS).
  - mirror NOT called on 409; enqueue NOT called on 409.
  - 404 on missing feature_id; mirror NOT called; enqueue NOT called.
  - 404 when task exists but type not in ('feature', 'fix').
  - 401 on unauthenticated request.
  - transition_feature called with allowed=FEATURE_USER_TRANSITIONS (same object, not redeclared).
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models import FeatureState, Task, TaskState
from app.storage import InvalidTransition, StorageError, TaskNotFound

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


def _make_space(
    *,
    space_id: str = "space-1",
    git_repo_url: str | None = "https://github.com/test/repo",
) -> MagicMock:
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
# Success path
# ---------------------------------------------------------------------------


def test_process_feature_success_200(app_client):
    """Valid process call transitions to PROCESSING and returns 200 with FeatureRead."""
    original_task = _make_task(feature_state=FeatureState.BACKLOG)
    updated_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(return_value=updated_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock), \
         patch("app.api.features.enqueue_feature_decomposition", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["feature_state"] == "processing"


def test_process_feature_response_is_feature_read(app_client):
    """Response body conforms to FeatureRead shape (has feature_key and feature_state)."""
    original_task = _make_task(feature_key="FEAT-007", feature_state=FeatureState.BACKLOG)
    updated_task = _make_task(feature_key="FEAT-007", feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(return_value=updated_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock), \
         patch("app.api.features.enqueue_feature_decomposition", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "feature_key" in data, "FeatureRead must have feature_key"
    assert "feature_state" in data, "FeatureRead must have feature_state"
    assert data["feature_key"] == "FEAT-007"


def test_process_feature_transition_called_with_processing_state(app_client):
    """transition_feature must be called with FeatureState.PROCESSING as target."""
    original_task = _make_task(feature_state=FeatureState.BACKLOG)
    updated_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(return_value=updated_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock), \
         patch("app.api.features.enqueue_feature_decomposition", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    call_args = mock_store.transition_feature.call_args
    # Second positional arg is the target state
    positional_args = call_args.args
    assert len(positional_args) >= 2, "transition_feature must be called with at least (id, state)"
    assert positional_args[1] == FeatureState.PROCESSING, (
        f"Expected FeatureState.PROCESSING, got {positional_args[1]!r}"
    )


def test_process_feature_transition_called_with_user_transitions(app_client):
    """transition_feature must be called with allowed=FEATURE_USER_TRANSITIONS (exact import)."""
    from app.feature_state import FEATURE_USER_TRANSITIONS

    original_task = _make_task(feature_state=FeatureState.BACKLOG)
    updated_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(return_value=updated_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock), \
         patch("app.api.features.enqueue_feature_decomposition", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    call_args = mock_store.transition_feature.call_args
    assert call_args.kwargs.get("allowed") is FEATURE_USER_TRANSITIONS, (
        "transition_feature must be called with allowed=FEATURE_USER_TRANSITIONS (the exact imported object)"
    )


# ---------------------------------------------------------------------------
# R13: mirror call_count == 1 on success
# ---------------------------------------------------------------------------


def test_process_feature_mirror_called_once_on_success(app_client):
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
    ) as mock_mirror, patch(
        "app.api.features.enqueue_feature_decomposition",
        new_callable=AsyncMock,
    ):
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_mirror.call_count == 1, (
        f"Expected mirror call_count=1, got {mock_mirror.call_count}"
    )
    call_kwargs = mock_mirror.call_args
    assert call_kwargs.kwargs.get("reason") == "state_change", (
        f"Expected reason='state_change', got {call_kwargs.kwargs.get('reason')!r}"
    )


# ---------------------------------------------------------------------------
# S4 enqueue: enqueue_feature_decomposition called once on success
# ---------------------------------------------------------------------------


def test_process_feature_enqueue_called_once_on_success(app_client):
    """enqueue_feature_decomposition must be called exactly once on success."""
    original_task = _make_task(feature_state=FeatureState.BACKLOG)
    updated_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(return_value=updated_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock), \
         patch(
             "app.api.features.enqueue_feature_decomposition",
             new_callable=AsyncMock,
         ) as mock_enqueue:
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_enqueue.call_count == 1, (
        f"Expected enqueue call_count=1, got {mock_enqueue.call_count}"
    )


def test_process_feature_enqueue_called_with_updated_task(app_client):
    """enqueue_feature_decomposition must receive the updated (post-transition) task."""
    original_task = _make_task(feature_state=FeatureState.BACKLOG)
    updated_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(return_value=updated_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock), \
         patch(
             "app.api.features.enqueue_feature_decomposition",
             new_callable=AsyncMock,
         ) as mock_enqueue:
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    enqueue_call_args = mock_enqueue.call_args
    passed_task = enqueue_call_args.args[0]
    assert passed_task.feature_state == FeatureState.PROCESSING, (
        "enqueue must receive the task after transition to PROCESSING, "
        f"but got feature_state={passed_task.feature_state!r}"
    )


# ---------------------------------------------------------------------------
# Error path: 409 on already PROCESSING (second invocation)
# ---------------------------------------------------------------------------


def test_process_feature_already_processing_returns_409(app_client):
    """Second invocation when already PROCESSING returns 409 (PROCESSING→PROCESSING illegal)."""
    already_processing_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = already_processing_task
    mock_store.transition_feature = AsyncMock(
        side_effect=InvalidTransition(
            "Transition from 'processing' to 'processing' is not allowed"
        )
    )

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror, patch(
        "app.api.features.enqueue_feature_decomposition",
        new_callable=AsyncMock,
    ) as mock_enqueue:
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 409, response.text
    assert mock_mirror.call_count == 0, (
        f"Mirror must NOT be called on 409; got call_count={mock_mirror.call_count}"
    )
    assert mock_enqueue.call_count == 0, (
        f"Enqueue must NOT be called on 409; got call_count={mock_enqueue.call_count}"
    )


def test_process_feature_409_includes_detail_message(app_client):
    """409 response must include a descriptive detail message."""
    already_processing_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = already_processing_task
    mock_store.transition_feature = AsyncMock(
        side_effect=InvalidTransition("Transition from 'processing' to 'processing' is not allowed")
    )

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock), \
         patch("app.api.features.enqueue_feature_decomposition", new_callable=AsyncMock):
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 409
    detail = response.json().get("detail", "")
    assert detail, "409 response must include a 'detail' field with a description"


def test_process_feature_early_guard_skips_transition_when_already_processing(app_client):
    """Early guard must short-circuit before calling transition_feature when already PROCESSING.

    This verifies F3: the explicit state check fires *before* transition_feature,
    preventing a duplicate decomposition agent from being enqueued even if
    transition_feature would silently no-op the same-state transition.
    """
    already_processing_task = _make_task(feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = already_processing_task
    # transition_feature would NOT raise — it would silently no-op — proving the 409
    # must come from the early guard, not from transition_feature.
    mock_store.transition_feature = AsyncMock(return_value=already_processing_task)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror, patch(
        "app.api.features.enqueue_feature_decomposition",
        new_callable=AsyncMock,
    ) as mock_enqueue:
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 409, response.text
    assert "already" in response.json().get("detail", "").lower(), (
        "409 detail must mention 'already' to indicate duplicate guard fired"
    )
    assert mock_store.transition_feature.call_count == 0, (
        "transition_feature must NOT be called when the early guard fires; "
        f"got call_count={mock_store.transition_feature.call_count}"
    )
    assert mock_mirror.call_count == 0
    assert mock_enqueue.call_count == 0


def test_process_feature_storage_error_returns_409(app_client):
    """A generic StorageError from transition_feature returns 409."""
    original_task = _make_task(feature_state=FeatureState.DONE)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(
        side_effect=StorageError("Some storage constraint violated")
    )

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror, patch(
        "app.api.features.enqueue_feature_decomposition",
        new_callable=AsyncMock,
    ) as mock_enqueue:
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 409
    assert mock_mirror.call_count == 0
    assert mock_enqueue.call_count == 0


# ---------------------------------------------------------------------------
# Error path: 404 on missing feature
# ---------------------------------------------------------------------------


def test_process_feature_missing_id_returns_404(app_client):
    """Missing feature_id must return 404; mirror and enqueue must NOT be called."""
    mock_store = MagicMock()
    mock_store.get.return_value = None

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror, patch(
        "app.api.features.enqueue_feature_decomposition",
        new_callable=AsyncMock,
    ) as mock_enqueue:
        response = app_client.post(
            "/api/features/no-such-id/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    assert mock_mirror.call_count == 0, (
        f"Mirror must NOT be called on 404; got call_count={mock_mirror.call_count}"
    )
    assert mock_enqueue.call_count == 0, (
        f"Enqueue must NOT be called on 404; got call_count={mock_enqueue.call_count}"
    )


def test_process_feature_wrong_type_returns_404(app_client):
    """A task with type='task' must return 404; mirror and enqueue must NOT be called."""
    regular_task = Task(
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
    mock_store.get.return_value = regular_task

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror, patch(
        "app.api.features.enqueue_feature_decomposition",
        new_callable=AsyncMock,
    ) as mock_enqueue:
        response = app_client.post(
            "/api/features/2024-01-15-1000-regular-task/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    assert mock_mirror.call_count == 0
    assert mock_enqueue.call_count == 0


def test_process_feature_task_not_found_from_transition_returns_404(app_client):
    """TaskNotFound raised by transition_feature (secondary guard) returns 404."""
    original_task = _make_task(feature_state=FeatureState.BACKLOG)

    mock_store = MagicMock()
    mock_store.get.return_value = original_task
    mock_store.transition_feature = AsyncMock(
        side_effect=TaskNotFound("2024-01-15-1000-my-feature")
    )

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror, patch(
        "app.api.features.enqueue_feature_decomposition",
        new_callable=AsyncMock,
    ) as mock_enqueue:
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    assert mock_mirror.call_count == 0
    assert mock_enqueue.call_count == 0


# ---------------------------------------------------------------------------
# Works for type='fix' as well
# ---------------------------------------------------------------------------


def test_process_fix_type_succeeds(app_client):
    """POST /process also works for type='fix' tasks."""
    original_fix = _make_task(task_type="fix", feature_key="FIX-003", feature_state=FeatureState.BACKLOG)
    updated_fix = _make_task(task_type="fix", feature_key="FIX-003", feature_state=FeatureState.PROCESSING)

    mock_store = MagicMock()
    mock_store.get.return_value = original_fix
    mock_store.transition_feature = AsyncMock(return_value=updated_fix)

    app_client.app.state.store = mock_store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror, patch(
        "app.api.features.enqueue_feature_decomposition",
        new_callable=AsyncMock,
    ) as mock_enqueue:
        response = app_client.post(
            "/api/features/2024-01-15-1000-my-feature/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert response.json()["feature_key"] == "FIX-003"
    assert mock_mirror.call_count == 1
    assert mock_enqueue.call_count == 1


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_process_feature_unauthenticated_returns_401(app_client):
    """Unauthenticated request must return 401."""
    response = app_client.post("/api/features/some-id/process")
    assert response.status_code == 401
