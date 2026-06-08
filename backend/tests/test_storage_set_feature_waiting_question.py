"""Tests for TaskStore.set_feature_waiting_question (F1 fix).

Verifies:
- Value is persisted atomically and retrievable immediately via store.get()
- Value survives a full TaskStore reload (disk persistence)
- Clearing the value (None) works
- Errors surface instead of being swallowed (no AttributeError suppression)
- API integration: GET /api/features/{id} returns waiting_question in FeatureRead

NO importlib.reload() anywhere in this file (observation_importlib_reload_test_pollution).
"""
from __future__ import annotations

import pytest

from app.feature_state import FEATURE_USER_TRANSITIONS
from app.models import FeatureState
from app.storage import StorageError, TaskNotFound, TaskStore

SPACE_ID = "test-space"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _make_feature(store, title="My Feature", type_="feature"):
    task = await store.create(space_id=SPACE_ID, title=title, brief="", type=type_)
    await store.transition_feature(
        task.id, FeatureState.PROCESSING, allowed=FEATURE_USER_TRANSITIONS
    )
    return store.get(task.id)


# ---------------------------------------------------------------------------
# happy path — set and retrieve
# ---------------------------------------------------------------------------


async def test_set_feature_waiting_question_persists_value(task_store):
    """set_feature_waiting_question writes the question; store.get() reflects it immediately."""
    feat = await _make_feature(task_store)
    question = "Should we use OAuth or SAML?"

    result = await task_store.set_feature_waiting_question(feat.id, question)

    assert result.waiting_question == question
    assert task_store.get(feat.id).waiting_question == question


async def test_set_feature_waiting_question_survives_reload(task_store, tmp_spaces_dir):
    """set_feature_waiting_question atomically writes to disk; fresh reload sees the value."""
    feat = await _make_feature(task_store)
    question = "Approval needed before proceeding with OAuth."

    await task_store.set_feature_waiting_question(feat.id, question)

    fresh = TaskStore(tmp_spaces_dir)
    await fresh.reload_all()

    reloaded = fresh.get(feat.id)
    assert reloaded is not None
    assert reloaded.waiting_question == question


async def test_set_feature_waiting_question_clear_to_none(task_store):
    """Setting question to None clears a previously stored value."""
    feat = await _make_feature(task_store)
    await task_store.set_feature_waiting_question(feat.id, "Initial question")
    assert task_store.get(feat.id).waiting_question == "Initial question"

    await task_store.set_feature_waiting_question(feat.id, None)

    assert task_store.get(feat.id).waiting_question is None


async def test_set_feature_waiting_question_works_for_fix_type(task_store):
    """set_feature_waiting_question accepts type='fix' tasks as well as 'feature'."""
    fix_task = await _make_feature(task_store, title="My Fix", type_="fix")

    result = await task_store.set_feature_waiting_question(fix_task.id, "Fix approved?")

    assert result.waiting_question == "Fix approved?"
    assert task_store.get(fix_task.id).waiting_question == "Fix approved?"


async def test_set_feature_waiting_question_overwrites_existing(task_store):
    """Calling set_feature_waiting_question twice replaces the previous value."""
    feat = await _make_feature(task_store)

    await task_store.set_feature_waiting_question(feat.id, "First question")
    await task_store.set_feature_waiting_question(feat.id, "Updated question")

    assert task_store.get(feat.id).waiting_question == "Updated question"


# ---------------------------------------------------------------------------
# error cases — errors surface without suppression
# ---------------------------------------------------------------------------


async def test_set_feature_waiting_question_raises_task_not_found(task_store):
    """set_feature_waiting_question raises TaskNotFound for unknown task_id."""
    with pytest.raises(TaskNotFound):
        await task_store.set_feature_waiting_question("nonexistent-id", "question?")


async def test_set_feature_waiting_question_raises_for_plain_task(task_store):
    """set_feature_waiting_question raises StorageError when task type is 'task'."""
    plain = await task_store.create(
        space_id=SPACE_ID, title="Plain task", brief=""
    )

    with pytest.raises(StorageError):
        await task_store.set_feature_waiting_question(plain.id, "question?")


async def test_set_feature_waiting_question_raises_for_goal_type(task_store):
    """set_feature_waiting_question raises StorageError when task type is 'goal'."""
    goal = await task_store.create(
        space_id=SPACE_ID, title="A Goal", brief="", type="goal"
    )

    with pytest.raises(StorageError):
        await task_store.set_feature_waiting_question(goal.id, "question?")


# ---------------------------------------------------------------------------
# API integration — GET /api/features/{id} returns waiting_question
# ---------------------------------------------------------------------------


async def test_get_feature_api_returns_waiting_question(async_client, task_store):
    """GET /api/features/{id} includes waiting_question in FeatureRead response."""
    feat = await _make_feature(task_store)
    question = "Please review the proposed schema change."
    await task_store.set_feature_waiting_question(feat.id, question)

    resp = await async_client.get(f"/api/features/{feat.id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["waiting_question"] == question


async def test_get_feature_api_returns_null_waiting_question_when_not_set(
    async_client, task_store
):
    """GET /api/features/{id} returns null waiting_question when none is set."""
    feat = await _make_feature(task_store)

    resp = await async_client.get(f"/api/features/{feat.id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["waiting_question"] is None


async def test_get_feature_api_returns_waiting_question_after_propagation(
    async_client, task_store
):
    """End-to-end: waiting_question set via set_feature_waiting_question appears in GET."""
    feat = await _make_feature(task_store)
    await task_store.set_feature_waiting_question(feat.id, "Which API version to target?")

    resp = await async_client.get(f"/api/features/{feat.id}")
    assert resp.status_code == 200
    assert resp.json()["waiting_question"] == "Which API version to target?"

    # Clearing should also be reflected in the API response.
    await task_store.set_feature_waiting_question(feat.id, None)
    resp2 = await async_client.get(f"/api/features/{feat.id}")
    assert resp2.status_code == 200
    assert resp2.json()["waiting_question"] is None
