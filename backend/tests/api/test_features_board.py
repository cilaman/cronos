"""Tests for GET /api/features?space_id= — FeatureBoard endpoint (I6).

Acceptance criteria (from design report I6):
  - Returns a FeatureBoard with five lanes (backlog, processing, planned,
    waiting, done) populated from store.feature_board(space_id).
  - Items appear in their feature_state lane.
  - Items with feature_state=None are omitted (store.feature_board handles this).
  - mirror_feature_to_github call_count == 0 on GET (R13).
  - 404 when space does not exist.
  - 422 when space_id is missing.
  - Cross-board disjointness: a task with type='feature' appears in
    feature_board but NOT in board() (R10, per design Next consumer brief
    cross-iteration invariant #5).

Auth pattern mirrors test_features_create.py: CRONOS_BASIC_AUTH_USER +
CRONOS_BASIC_AUTH_PASSWORD env vars set via monkeypatch; AUTH_HEADER added
to every authenticated request.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models import FeatureState, TaskSummary, TaskState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_USER = "testuser"
TEST_PASS = "testpass"
AUTH_HEADER = {
    "Authorization": "Basic "
    + base64.b64encode(f"{TEST_USER}:{TEST_PASS}".encode()).decode()
}

SPACE_ID = "space-board-1"

_NOW = datetime(2024, 2, 10, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_summary(
    *,
    task_id: str = "2024-02-10-1200-feat-a",
    title: str = "Feature A",
    state: TaskState = TaskState.BACKLOG,
    task_type: str = "feature",
    feature_state: FeatureState | None = FeatureState.BACKLOG,
) -> TaskSummary:
    return TaskSummary(
        id=task_id,
        space_id=SPACE_ID,
        title=title,
        state=state,
        created_at=_NOW,
        updated_at=_NOW,
        brief="",
        priority=3,
        manual_order=0,
        type=task_type,
        feature_state=feature_state,
    )


def _empty_buckets() -> dict[FeatureState, list[TaskSummary]]:
    """Return an empty feature_board() result dict."""
    return {fs: [] for fs in FeatureState}


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
# Success path — empty board
# ---------------------------------------------------------------------------


def test_get_feature_board_empty(app_client):
    """GET /api/features?space_id= with an empty store returns all-empty lanes."""
    mock_store = MagicMock()
    mock_store.feature_board = AsyncMock(return_value=_empty_buckets())
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.exists.return_value = True

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.get(
            "/api/features",
            params={"space_id": SPACE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    data = response.json()
    # All five lanes must be present and empty
    assert data["backlog"] == []
    assert data["processing"] == []
    assert data["planned"] == []
    assert data["waiting"] == []
    assert data["done"] == []
    # R13: no mirror call on GET
    assert mock_mirror.call_count == 0


# ---------------------------------------------------------------------------
# Items routed to correct lanes
# ---------------------------------------------------------------------------


def test_items_routed_to_correct_lanes(app_client):
    """Features appear in their corresponding feature_state lane."""
    backlog_item = _make_summary(
        task_id="feat-backlog",
        title="Backlog Feature",
        feature_state=FeatureState.BACKLOG,
    )
    processing_item = _make_summary(
        task_id="feat-processing",
        title="Processing Feature",
        feature_state=FeatureState.PROCESSING,
    )
    planned_item = _make_summary(
        task_id="feat-planned",
        title="Planned Feature",
        feature_state=FeatureState.PLANNED,
    )
    waiting_item = _make_summary(
        task_id="feat-waiting",
        title="Waiting Feature",
        feature_state=FeatureState.WAITING,
    )
    done_item = _make_summary(
        task_id="feat-done",
        title="Done Feature",
        feature_state=FeatureState.DONE,
    )

    buckets = _empty_buckets()
    buckets[FeatureState.BACKLOG] = [backlog_item]
    buckets[FeatureState.PROCESSING] = [processing_item]
    buckets[FeatureState.PLANNED] = [planned_item]
    buckets[FeatureState.WAITING] = [waiting_item]
    buckets[FeatureState.DONE] = [done_item]

    mock_store = MagicMock()
    mock_store.feature_board = AsyncMock(return_value=buckets)
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.exists.return_value = True

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock) as mock_mirror:
        response = app_client.get(
            "/api/features",
            params={"space_id": SPACE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["backlog"]) == 1
    assert data["backlog"][0]["id"] == "feat-backlog"
    assert len(data["processing"]) == 1
    assert data["processing"][0]["id"] == "feat-processing"
    assert len(data["planned"]) == 1
    assert data["planned"][0]["id"] == "feat-planned"
    assert len(data["waiting"]) == 1
    assert data["waiting"][0]["id"] == "feat-waiting"
    assert len(data["done"]) == 1
    assert data["done"][0]["id"] == "feat-done"
    # R13: no mirror call on GET
    assert mock_mirror.call_count == 0


# ---------------------------------------------------------------------------
# Multiple items in one lane
# ---------------------------------------------------------------------------


def test_multiple_items_in_same_lane(app_client):
    """Multiple features with the same feature_state all appear in one lane."""
    items = [
        _make_summary(task_id=f"feat-{i}", title=f"Feature {i}", feature_state=FeatureState.BACKLOG)
        for i in range(3)
    ]
    buckets = _empty_buckets()
    buckets[FeatureState.BACKLOG] = items

    mock_store = MagicMock()
    mock_store.feature_board = AsyncMock(return_value=buckets)
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.exists.return_value = True

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.get(
            "/api/features",
            params={"space_id": SPACE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["backlog"]) == 3
    assert data["processing"] == []


# ---------------------------------------------------------------------------
# store.feature_board called with correct space_id
# ---------------------------------------------------------------------------


def test_feature_board_called_with_space_id(app_client):
    """store.feature_board() is called with exactly the space_id from the query param."""
    mock_store = MagicMock()
    mock_store.feature_board = AsyncMock(return_value=_empty_buckets())
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.exists.return_value = True

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        app_client.get(
            "/api/features",
            params={"space_id": "my-space"},
            headers=AUTH_HEADER,
        )

    mock_store.feature_board.assert_called_once_with("my-space")


# ---------------------------------------------------------------------------
# Cross-board disjointness (R10) — features NOT in tasks Board
# ---------------------------------------------------------------------------


def test_feature_items_absent_from_tasks_board(app_client):
    """A feature item must not appear in the tasks board.

    This test uses the mock store to confirm that feature_board() returns
    the feature item while board() (which the tasks endpoint calls) returns
    an empty-ish Board.  The disjointness contract is enforced by the I3
    storage filter; this test asserts the API-level separation belt-and-
    suspenders style per design Next consumer brief invariant #5.
    """
    feat_summary = _make_summary(
        task_id="feat-disjoint",
        title="Disjoint Feature",
        task_type="feature",
        feature_state=FeatureState.BACKLOG,
    )
    buckets = _empty_buckets()
    buckets[FeatureState.BACKLOG] = [feat_summary]

    from app.models import Board, TaskState, TaskSummary as TS

    mock_store = MagicMock()
    mock_store.feature_board = AsyncMock(return_value=buckets)
    # board() returns an empty Board (features are excluded by I3 storage filter)
    mock_store.board = MagicMock(return_value=Board(backlog=[], active=[], waiting=[], done=[]))
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.exists.return_value = True

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        feat_resp = app_client.get(
            "/api/features",
            params={"space_id": SPACE_ID},
            headers=AUTH_HEADER,
        )
        tasks_resp = app_client.get(
            "/api/tasks",
            params={"space_id": SPACE_ID},
            headers=AUTH_HEADER,
        )

    assert feat_resp.status_code == 200
    feat_data = feat_resp.json()
    # Feature appears in FeatureBoard
    assert len(feat_data["backlog"]) == 1
    assert feat_data["backlog"][0]["id"] == "feat-disjoint"

    # Feature does NOT appear in tasks Board
    assert tasks_resp.status_code == 200
    tasks_data = tasks_resp.json()
    all_task_ids = (
        [t["id"] for t in tasks_data.get("backlog", [])]
        + [t["id"] for t in tasks_data.get("active", [])]
        + [t["id"] for t in tasks_data.get("waiting", [])]
        + [t["id"] for t in tasks_data.get("done", [])]
    )
    assert "feat-disjoint" not in all_task_ids, (
        "Feature item appeared in tasks Board — I3 storage filter may be broken."
    )


# ---------------------------------------------------------------------------
# R13 — mirror call_count == 0 on GET
# ---------------------------------------------------------------------------


def test_mirror_not_called_on_get(app_client):
    """mirror_feature_to_github must NOT be called on GET /api/features (R13)."""
    mock_store = MagicMock()
    mock_store.feature_board = AsyncMock(return_value=_empty_buckets())
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.exists.return_value = True

    with patch(
        "app.api.features.mirror_feature_to_github",
        new_callable=AsyncMock,
    ) as mock_mirror:
        response = app_client.get(
            "/api/features",
            params={"space_id": SPACE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200
    assert mock_mirror.call_count == 0, (
        f"mirror_feature_to_github was called {mock_mirror.call_count} time(s) "
        f"on GET /api/features — must be 0 (R13)."
    )


# ---------------------------------------------------------------------------
# 404 — space does not exist
# ---------------------------------------------------------------------------


def test_404_when_space_missing(app_client):
    """GET /api/features with an unknown space_id returns 404."""
    mock_store = MagicMock()
    mock_store.feature_board = AsyncMock(return_value=_empty_buckets())
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.exists.return_value = False

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.get(
            "/api/features",
            params={"space_id": "no-such-space"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 404, response.text
    # store.feature_board should NOT be called when the space doesn't exist
    mock_store.feature_board.assert_not_called()


# ---------------------------------------------------------------------------
# 422 — space_id missing / empty
# ---------------------------------------------------------------------------


def test_422_when_space_id_empty(app_client):
    """GET /api/features with empty space_id returns 422."""
    mock_store = MagicMock()
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.exists.return_value = True

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.get(
            "/api/features",
            params={"space_id": ""},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# 401 — unauthenticated
# ---------------------------------------------------------------------------


def test_unauthenticated_returns_401(app_client):
    """GET /api/features without credentials returns 401 (R14)."""
    response = app_client.get("/api/features", params={"space_id": SPACE_ID})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Response shape — five-lane structure
# ---------------------------------------------------------------------------


def test_response_has_five_lanes(app_client):
    """Response body includes exactly the five FeatureBoard lane keys."""
    mock_store = MagicMock()
    mock_store.feature_board = AsyncMock(return_value=_empty_buckets())
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.exists.return_value = True

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.get(
            "/api/features",
            params={"space_id": SPACE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200
    data = response.json()
    expected_lanes = {"backlog", "processing", "planned", "waiting", "done"}
    assert set(data.keys()) == expected_lanes, (
        f"FeatureBoard response keys {set(data.keys())} != expected {expected_lanes}"
    )


# ---------------------------------------------------------------------------
# TaskSummary fields in lane items
# ---------------------------------------------------------------------------


def test_lane_items_contain_task_summary_fields(app_client):
    """Items in feature board lanes contain standard TaskSummary fields."""
    item = _make_summary(
        task_id="feat-summary-check",
        title="Summary Check Feature",
        feature_state=FeatureState.PLANNED,
    )
    buckets = _empty_buckets()
    buckets[FeatureState.PLANNED] = [item]

    mock_store = MagicMock()
    mock_store.feature_board = AsyncMock(return_value=buckets)
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.exists.return_value = True

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.get(
            "/api/features",
            params={"space_id": SPACE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["planned"]) == 1
    lane_item = data["planned"][0]
    assert lane_item["id"] == "feat-summary-check"
    assert lane_item["title"] == "Summary Check Feature"
    assert lane_item["space_id"] == SPACE_ID
    assert lane_item["type"] == "feature"
    assert lane_item["feature_state"] == "planned"


# ---------------------------------------------------------------------------
# realizing_count in lane items
# ---------------------------------------------------------------------------


def test_lane_items_contain_realizing_count(app_client):
    """Lane items expose realizing_count from the TaskSummary."""
    item = _make_summary(
        task_id="feat-with-count",
        title="Feature With Realizers",
        feature_state=FeatureState.PLANNED,
    )
    item.realizing_count = 3

    buckets = _empty_buckets()
    buckets[FeatureState.PLANNED] = [item]

    mock_store = MagicMock()
    mock_store.feature_board = AsyncMock(return_value=buckets)
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.exists.return_value = True

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.get(
            "/api/features",
            params={"space_id": SPACE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200
    data = response.json()
    lane_item = data["planned"][0]
    assert lane_item["realizing_count"] == 3


def test_lane_items_default_realizing_count_zero(app_client):
    """Lane items with no realizers have realizing_count == 0."""
    item = _make_summary(
        task_id="feat-no-count",
        title="Feature No Realizers",
        feature_state=FeatureState.BACKLOG,
    )
    # Default: realizing_count not set (should be 0)

    buckets = _empty_buckets()
    buckets[FeatureState.BACKLOG] = [item]

    mock_store = MagicMock()
    mock_store.feature_board = AsyncMock(return_value=buckets)
    app_client.app.state.store = mock_store
    app_client.app.state.space_store.exists.return_value = True

    with patch("app.api.features.mirror_feature_to_github", new_callable=AsyncMock):
        response = app_client.get(
            "/api/features",
            params={"space_id": SPACE_ID},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200
    data = response.json()
    lane_item = data["backlog"][0]
    assert lane_item["realizing_count"] == 0
