"""Tests for feature_totals aggregation in GET /api/spaces.

Four cases:
 (a) No feature tasks → feature_totals is an empty dict.
 (b) Single feature task in backlog state → feature_totals == {"backlog": 1}.
 (c) Mixed backlog + done → both keys present with correct counts.
 (d) Regression: totals still contains all 5 TaskState keys with correct counts.
"""
from __future__ import annotations

import pytest

from app.models import FeatureState, TaskState
from app.feature_state import FEATURE_USER_TRANSITIONS, FEATURE_WORKER_TRANSITIONS

from .conftest import SPACE_ID


# ---------------------------------------------------------------------------
# (a) No feature tasks → feature_totals is empty
# ---------------------------------------------------------------------------


async def test_feature_totals_empty_when_no_feature_tasks(async_client):
    """GET /api/spaces returns feature_totals={} when no feature/fix tasks exist."""
    resp = await async_client.get("/api/spaces")
    assert resp.status_code == 200
    data = resp.json()
    assert "feature_totals" in data
    assert data["feature_totals"] == {}


# ---------------------------------------------------------------------------
# (b) Single feature task in backlog
# ---------------------------------------------------------------------------


async def test_feature_totals_single_backlog(async_client, task_store):
    """A single feature task in backlog is counted under feature_totals['backlog']."""
    # Create a feature task via task_store directly (type="feature" → feature_state=BACKLOG)
    await task_store.create(
        space_id=SPACE_ID,
        title="Feature A",
        brief="",
        type="feature",
    )

    spaces_resp = await async_client.get("/api/spaces")
    assert spaces_resp.status_code == 200
    ft = spaces_resp.json()["feature_totals"]
    assert ft.get("backlog") == 1


# ---------------------------------------------------------------------------
# (c) Mixed backlog + done
# ---------------------------------------------------------------------------


async def test_feature_totals_mixed_backlog_and_done(async_client, task_store):
    """Two feature tasks: one in backlog, one transitioned to done."""
    # Create two feature tasks (both start as backlog)
    task1 = await task_store.create(
        space_id=SPACE_ID,
        title="Feature B",
        brief="",
        type="feature",
    )
    await task_store.create(
        space_id=SPACE_ID,
        title="Feature C",
        brief="",
        type="feature",
    )

    # Transition task1: BACKLOG → PROCESSING → PLANNED → DONE
    await task_store.transition_feature(
        task1.id, FeatureState.PROCESSING, allowed=FEATURE_USER_TRANSITIONS
    )
    await task_store.transition_feature(
        task1.id, FeatureState.PLANNED, allowed=FEATURE_WORKER_TRANSITIONS
    )
    await task_store.transition_feature(
        task1.id, FeatureState.DONE, allowed=FEATURE_USER_TRANSITIONS
    )

    spaces_resp = await async_client.get("/api/spaces")
    assert spaces_resp.status_code == 200
    ft = spaces_resp.json()["feature_totals"]
    assert ft.get("backlog") == 1
    assert ft.get("done") == 1


# ---------------------------------------------------------------------------
# (d) Regression: totals still contains all 5 TaskState keys
# ---------------------------------------------------------------------------


async def test_feature_totals_does_not_break_totals(async_client):
    """Adding feature_totals must not alter the existing totals dict structure.

    totals must contain all 5 TaskState keys; a regular task in backlog
    must appear in totals["backlog"].
    """
    # Create a regular task so totals["backlog"] > 0
    resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Regular Task", "brief": ""},
    )
    assert resp.status_code == 201

    spaces_resp = await async_client.get("/api/spaces")
    assert spaces_resp.status_code == 200
    data = spaces_resp.json()
    totals = data["totals"]

    # All 5 TaskState keys must be present
    expected_keys = {s.value for s in TaskState}
    assert set(totals.keys()) == expected_keys, (
        f"totals keys {set(totals.keys())} != expected {expected_keys}"
    )
    # The regular task we created must appear in backlog
    assert totals["backlog"] >= 1
