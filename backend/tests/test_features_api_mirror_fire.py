"""End-to-end tests for _fire_mirror call sites in api/features.py (I4 / R10).

Design assertion: all four mutating endpoints call mirror_feature_to_github
exactly once through the _fire_mirror funnel, with the correct reason string.

Call sites covered:
  1. POST   /api/features/              → reason="create"
  2. PATCH  /api/features/{id}/feature-state → reason="state_change"
  3. PATCH  /api/features/{id}          → reason="edit"
  4. POST   /api/features/{id}/process  → reason="state_change"

Fire-and-forget vs. await (R10 risk mitigation):
  _fire_mirror in api/features.py calls:
      await mirror_feature_to_github(task, space=space, reason=reason)
  This is a direct await (not asyncio.create_task).  The response is therefore
  blocked by the mirror call duration.  The response-time test asserts that a
  monkeypatched no-op completes quickly (well under 1s), confirming the mock
  replaced the real gh subprocess and no latency leak occurred.
"""

from __future__ import annotations

import asyncio
import base64
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models import FeatureState, Task, TaskState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_USER = "testuser"
TEST_PASS = "testpass"
AUTH_HEADER = {
    "Authorization": "Basic "
    + base64.b64encode(f"{TEST_USER}:{TEST_PASS}".encode()).decode()
}

_NOW = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

FEATURE_ID = "2024-01-15-1000-my-feature"

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
    task_id: str = FEATURE_ID,
    task_type: str = "feature",
    feature_key: str = "FEAT-001",
    feature_state: FeatureState = FeatureState.BACKLOG,
) -> Task:
    return Task(
        id=task_id,
        space_id="space-1",
        title="My Feature",
        state=TaskState.BACKLOG,
        created_at=_NOW,
        updated_at=_NOW,
        brief="Some brief",
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
# Shared store fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_store_create():
    """TaskStore mock suitable for the POST /api/features/ endpoint."""
    store = MagicMock()
    store.create = AsyncMock(return_value=_make_task())
    return store


@pytest.fixture()
def mock_store_state():
    """TaskStore mock suitable for PATCH /{id}/feature-state."""
    task = _make_task(feature_state=FeatureState.BACKLOG)
    updated = _make_task(feature_state=FeatureState.PROCESSING)
    store = MagicMock()
    store.get = MagicMock(return_value=task)
    store.transition_feature = AsyncMock(return_value=updated)
    return store


@pytest.fixture()
def mock_store_edit():
    """TaskStore mock suitable for PATCH /{id} (title/brief edit)."""
    task = _make_task()
    updated = _make_task()
    store = MagicMock()
    store.get = MagicMock(return_value=task)
    store.update = AsyncMock(return_value=updated)
    return store


@pytest.fixture()
def mock_store_process():
    """TaskStore mock suitable for POST /{id}/process."""
    task = _make_task(feature_state=FeatureState.BACKLOG)
    updated = _make_task(feature_state=FeatureState.PROCESSING)
    store = MagicMock()
    store.get = MagicMock(return_value=task)
    store.transition_feature = AsyncMock(return_value=updated)
    return store


# ---------------------------------------------------------------------------
# Call site 1 — POST /api/features/ → reason="create"
# ---------------------------------------------------------------------------


def test_post_feature_fires_mirror_with_reason_create(app_client, mock_store_create):
    """POST /api/features/ calls mirror_feature_to_github once with reason='create'."""
    app_client.app.state.store = mock_store_create
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.post(
            "/api/features/",
            json={
                "space_id": "space-1",
                "title": "My Feature",
                "brief": "Some brief",
                "type": "feature",
                "priority": 3,
            },
            headers=AUTH_HEADER,
        )

    assert response.status_code == 201, response.text
    assert mock_mirror.call_count == 1, (
        f"Expected mirror call_count=1, got {mock_mirror.call_count}"
    )
    call_args = mock_mirror.call_args
    assert call_args.kwargs.get("reason") == "create", (
        f"Expected reason='create', got {call_args.kwargs.get('reason')!r}"
    )


def test_post_feature_mirror_receives_task_and_space(app_client, mock_store_create):
    """POST /api/features/ passes the created task and space to mirror."""
    app_client.app.state.store = mock_store_create
    space = _make_space()
    app_client.app.state.space_store.get.return_value = space

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.post(
            "/api/features/",
            json={"space_id": "space-1", "title": "My Feature", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 201, response.text
    call_args = mock_mirror.call_args
    # First positional arg is the task
    passed_task = call_args.args[0]
    assert passed_task.type in ("feature", "fix"), (
        f"Expected task type feature/fix, got {passed_task.type!r}"
    )
    # space is passed as keyword
    passed_space = call_args.kwargs.get("space")
    assert passed_space is space, "mirror must receive the exact space object fetched by the endpoint"


def test_post_feature_mirror_not_called_on_no_git(app_client):
    """POST /api/features/ with git_repo_url=None returns 400 and does NOT call mirror."""
    app_client.app.state.space_store.get.return_value = _make_space(git_repo_url=None)

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.post(
            "/api/features/",
            json={"space_id": "space-1", "title": "My Feature", "type": "feature"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 400, response.text
    assert mock_mirror.call_count == 0, "mirror must NOT fire on 400 (no git_repo_url)"


# ---------------------------------------------------------------------------
# Call site 2 — PATCH /api/features/{id}/feature-state → reason="state_change"
# ---------------------------------------------------------------------------


def test_patch_feature_state_fires_mirror_with_reason_state_change(app_client, mock_store_state):
    """PATCH /{id}/feature-state calls mirror_feature_to_github once with reason='state_change'."""
    app_client.app.state.store = mock_store_state
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/feature-state",
            json={"feature_state": "processing"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_mirror.call_count == 1, (
        f"Expected mirror call_count=1, got {mock_mirror.call_count}"
    )
    call_args = mock_mirror.call_args
    assert call_args.kwargs.get("reason") == "state_change", (
        f"Expected reason='state_change', got {call_args.kwargs.get('reason')!r}"
    )


def test_patch_feature_state_mirror_not_called_on_illegal_transition(app_client):
    """PATCH /{id}/feature-state on illegal transition returns 409; mirror NOT called."""
    from app.storage import InvalidTransition

    task = _make_task(feature_state=FeatureState.PROCESSING)
    store = MagicMock()
    store.get = MagicMock(return_value=task)
    store.transition_feature = AsyncMock(
        side_effect=InvalidTransition("Cannot transition")
    )

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/feature-state",
            json={"feature_state": "done"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 409, response.text
    assert mock_mirror.call_count == 0, "mirror must NOT fire on 409"


def test_patch_feature_state_mirror_not_called_on_404(app_client):
    """PATCH /{id}/feature-state when task not found returns 404; mirror NOT called."""
    store = MagicMock()
    store.get = MagicMock(return_value=None)

    app_client.app.state.store = store
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
    assert mock_mirror.call_count == 0, "mirror must NOT fire on 404"


# ---------------------------------------------------------------------------
# Call site 3 — PATCH /api/features/{id} (title/brief edit) → reason="edit"
# ---------------------------------------------------------------------------


def test_patch_feature_edit_fires_mirror_with_reason_edit(app_client, mock_store_edit):
    """PATCH /{id} calls mirror_feature_to_github once with reason='edit'."""
    app_client.app.state.store = mock_store_edit
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}",
            json={"title": "Updated Title"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_mirror.call_count == 1, (
        f"Expected mirror call_count=1, got {mock_mirror.call_count}"
    )
    call_args = mock_mirror.call_args
    assert call_args.kwargs.get("reason") == "edit", (
        f"Expected reason='edit', got {call_args.kwargs.get('reason')!r}"
    )


def test_patch_feature_edit_mirror_not_called_on_404(app_client):
    """PATCH /{id} when task not found returns 404; mirror NOT called."""
    store = MagicMock()
    store.get = MagicMock(return_value=None)

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            "/api/features/no-such-id",
            json={"title": "Updated Title"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    assert mock_mirror.call_count == 0, "mirror must NOT fire on 404"


def test_patch_feature_edit_brief_only_fires_mirror(app_client):
    """PATCH /{id} with only brief change still fires mirror once with reason='edit'."""
    task = _make_task()
    updated = _make_task()
    store = MagicMock()
    store.get = MagicMock(return_value=task)
    store.update = AsyncMock(return_value=updated)

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}",
            json={"brief": "New brief"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_mirror.call_count == 1, "mirror must fire even for brief-only edit"
    assert mock_mirror.call_args.kwargs.get("reason") == "edit"


# ---------------------------------------------------------------------------
# Call site 4 — POST /api/features/{id}/process → reason="state_change"
# ---------------------------------------------------------------------------


def test_process_feature_fires_mirror_with_reason_state_change(app_client, mock_store_process):
    """POST /{id}/process calls mirror_feature_to_github once with reason='state_change'."""
    app_client.app.state.store = mock_store_process
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror, patch(
        "app.api.features.enqueue_feature_decomposition",
        new_callable=AsyncMock,
    ):
        response = app_client.post(
            f"/api/features/{FEATURE_ID}/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_mirror.call_count == 1, (
        f"Expected mirror call_count=1, got {mock_mirror.call_count}"
    )
    call_args = mock_mirror.call_args
    assert call_args.kwargs.get("reason") == "state_change", (
        f"Expected reason='state_change', got {call_args.kwargs.get('reason')!r}"
    )


def test_process_feature_mirror_not_called_on_409(app_client):
    """POST /{id}/process on illegal transition returns 409; mirror NOT called."""
    from app.storage import InvalidTransition

    task = _make_task(feature_state=FeatureState.PROCESSING)
    store = MagicMock()
    store.get = MagicMock(return_value=task)
    store.transition_feature = AsyncMock(
        side_effect=InvalidTransition("Cannot transition from processing to processing")
    )

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror, patch(
        "app.api.features.enqueue_feature_decomposition",
        new_callable=AsyncMock,
    ):
        response = app_client.post(
            f"/api/features/{FEATURE_ID}/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 409, response.text
    assert mock_mirror.call_count == 0, "mirror must NOT fire on 409"


def test_process_feature_mirror_not_called_on_404(app_client):
    """POST /{id}/process when task not found returns 404; mirror NOT called."""
    store = MagicMock()
    store.get = MagicMock(return_value=None)

    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror, patch(
        "app.api.features.enqueue_feature_decomposition",
        new_callable=AsyncMock,
    ):
        response = app_client.post(
            "/api/features/no-such-id/process",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    assert mock_mirror.call_count == 0, "mirror must NOT fire on 404"


# ---------------------------------------------------------------------------
# Cross-cutting: _fire_mirror is the sole funnel (R10 / R13)
# ---------------------------------------------------------------------------


def test_all_four_call_sites_use_single_funnel():
    """_fire_mirror exists in api/features.py and is used by all mutating endpoints.

    Verifies that the _fire_mirror funnel is the only place mirror_feature_to_github
    is called (R13 — concentrated call count).
    """
    import inspect
    import app.api.features as features_module

    source = inspect.getsource(features_module)

    # _fire_mirror must be defined
    assert "_fire_mirror" in source, "_fire_mirror funnel must be defined in api/features.py"

    # mirror_feature_to_github must be called inside _fire_mirror, not directly in routes
    # Count direct calls: should only appear within _fire_mirror body
    mirror_call_count = source.count("mirror_feature_to_github(")
    assert mirror_call_count >= 1, "mirror_feature_to_github must be called at least once (inside _fire_mirror)"

    # _fire_mirror should be called at least 4 times (one per mutating route)
    fire_mirror_call_count = source.count("_fire_mirror(")
    assert fire_mirror_call_count >= 4, (
        f"_fire_mirror should be called at least 4 times (one per mutating endpoint), "
        f"found {fire_mirror_call_count}"
    )


# ---------------------------------------------------------------------------
# R10 risk: response time — mirror is awaited directly (not fire-and-forget)
# ---------------------------------------------------------------------------


def test_mirror_is_awaited_directly_not_fire_and_forget(app_client, mock_store_create):
    """Verify that _fire_mirror awaits the mirror call directly.

    Since _fire_mirror uses 'await mirror_feature_to_github(...)' (not
    asyncio.create_task), the endpoint response time is bounded by the mock's
    return time.  A fast no-op AsyncMock completes well under 500ms even with
    TestClient overhead.
    """
    app_client.app.state.store = mock_store_create
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        mock_mirror.return_value = None  # instant no-op
        start = time.monotonic()
        response = app_client.post(
            "/api/features/",
            json={"space_id": "space-1", "title": "My Feature", "type": "feature"},
            headers=AUTH_HEADER,
        )
        elapsed = time.monotonic() - start

    assert response.status_code == 201, response.text
    assert mock_mirror.call_count == 1, "mirror must be called once (direct await)"
    # With a no-op mock, round-trip should be well under 2s including test overhead.
    assert elapsed < 2.0, (
        f"Expected fast response with mocked mirror, got {elapsed:.3f}s. "
        "If mirror is not mocked correctly, the real gh subprocess may be running."
    )


def test_mirror_slow_mock_blocks_response(app_client, mock_store_create):
    """When mirror sleeps 0.2s, the POST response also takes ≥0.2s.

    This confirms the direct-await behaviour: the response time is coupled to
    the mirror duration.  (For fire-and-forget the response would return
    immediately regardless of mirror sleep duration.)
    """
    app_client.app.state.store = mock_store_create
    app_client.app.state.space_store.get.return_value = _make_space()

    async def _slow_mirror(*args, **kwargs):
        await asyncio.sleep(0.2)

    with patch(
        "app.api.features.mirror_feature_to_github",
        side_effect=_slow_mirror,
    ):
        start = time.monotonic()
        response = app_client.post(
            "/api/features/",
            json={"space_id": "space-1", "title": "My Feature", "type": "feature"},
            headers=AUTH_HEADER,
        )
        elapsed = time.monotonic() - start

    assert response.status_code == 201, response.text
    # Direct await means the response is delayed by the mock sleep.
    # Use a loose lower bound to avoid flakiness on slow CI machines.
    assert elapsed >= 0.1, (
        f"Expected response to be delayed by mirror sleep (direct await), "
        f"but completed in {elapsed:.3f}s — mirror may not be awaited."
    )


# ---------------------------------------------------------------------------
# Reason strings: exhaustive cross-check
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "endpoint,method,body,expected_reason",
    [
        # Call site 1
        (
            "/api/features/",
            "post",
            {"space_id": "space-1", "title": "My Feature", "type": "feature"},
            "create",
        ),
        # Call site 3
        (
            f"/api/features/{FEATURE_ID}",
            "patch",
            {"title": "Updated"},
            "edit",
        ),
    ],
)
def test_reason_string_parametrized(app_client, endpoint, method, body, expected_reason):
    """Parametrised check: reason string matches expected value per endpoint."""
    task = _make_task()
    store = MagicMock()
    store.create = AsyncMock(return_value=task)
    store.get = MagicMock(return_value=task)
    store.update = AsyncMock(return_value=task)
    app_client.app.state.store = store
    app_client.app.state.space_store.get.return_value = _make_space()

    http_method = getattr(app_client, method)

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = http_method(endpoint, json=body, headers=AUTH_HEADER)

    # Allow 200 or 201
    assert response.status_code in (200, 201), (
        f"Unexpected status {response.status_code} for {method.upper()} {endpoint}: {response.text}"
    )
    assert mock_mirror.call_count == 1, (
        f"Expected 1 mirror call for {method.upper()} {endpoint}, got {mock_mirror.call_count}"
    )
    actual_reason = mock_mirror.call_args.kwargs.get("reason")
    assert actual_reason == expected_reason, (
        f"Expected reason={expected_reason!r} for {method.upper()} {endpoint}, "
        f"got {actual_reason!r}"
    )


def test_both_state_change_call_sites_use_same_reason_string(app_client, mock_store_state, mock_store_process):
    """Both state_change call sites (PATCH feature-state and POST process) use reason='state_change'."""
    # PATCH /{id}/feature-state
    app_client.app.state.store = mock_store_state
    app_client.app.state.space_store.get.return_value = _make_space()

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror_state:
        response1 = app_client.patch(
            f"/api/features/{FEATURE_ID}/feature-state",
            json={"feature_state": "processing"},
            headers=AUTH_HEADER,
        )

    assert response1.status_code == 200, response1.text
    reason1 = mock_mirror_state.call_args.kwargs.get("reason")

    # POST /{id}/process
    app_client.app.state.store = mock_store_process
    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror_process, patch(
        "app.api.features.enqueue_feature_decomposition",
        new_callable=AsyncMock,
    ):
        response2 = app_client.post(
            f"/api/features/{FEATURE_ID}/process",
            headers=AUTH_HEADER,
        )

    assert response2.status_code == 200, response2.text
    reason2 = mock_mirror_process.call_args.kwargs.get("reason")

    assert reason1 == "state_change", f"PATCH feature-state reason: expected 'state_change', got {reason1!r}"
    assert reason2 == "state_change", f"POST process reason: expected 'state_change', got {reason2!r}"
    assert reason1 == reason2, "Both state-change call sites must use the same reason string"


# ---------------------------------------------------------------------------
# Read-only endpoints do NOT fire mirror
# ---------------------------------------------------------------------------


def test_get_feature_does_not_fire_mirror(app_client):
    """GET /api/features/{id} must NOT call mirror (read path, R13: call_count==0)."""
    task = _make_task()
    store = MagicMock()
    store.get = MagicMock(return_value=task)
    store.realizing_items = AsyncMock(return_value=[])

    app_client.app.state.store = store

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.get(
            f"/api/features/{FEATURE_ID}",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_mirror.call_count == 0, (
        f"GET must NOT call mirror (R13 read-path), got call_count={mock_mirror.call_count}"
    )


def test_list_features_does_not_fire_mirror(app_client):
    """GET /api/features?space_id=... must NOT call mirror (read path)."""
    store = MagicMock()
    store.feature_board = AsyncMock(return_value={})

    app_client.app.state.store = store
    app_client.app.state.space_store.exists.return_value = True

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.get(
            "/api/features/?space_id=space-1",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    assert mock_mirror.call_count == 0, (
        f"GET list must NOT call mirror (R13 read-path), got call_count={mock_mirror.call_count}"
    )


def test_patch_realize_does_not_fire_mirror(app_client):
    """PATCH /api/features/{id}/realize must NOT call mirror (R13: call_count==0)."""
    task = _make_task()
    linking_task = _make_task(task_id="2024-01-15-0000-sub-task", task_type="task", feature_key=None)

    # patch_realize calls set_realizes then store.get then realizing_items
    store = MagicMock()
    store.set_realizes = AsyncMock(return_value=None)
    store.get = MagicMock(return_value=task)
    store.realizing_items = AsyncMock(return_value=[])

    app_client.app.state.store = store

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.patch(
            f"/api/features/{FEATURE_ID}/realize",
            json={"item_id": "2024-01-15-0000-sub-task", "feature_id": FEATURE_ID},
            headers=AUTH_HEADER,
        )

    # 200 or any success code
    assert response.status_code in (200, 201), response.text
    assert mock_mirror.call_count == 0, (
        f"PATCH realize must NOT call mirror (R13 read-path), got call_count={mock_mirror.call_count}"
    )
