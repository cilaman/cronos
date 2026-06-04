"""Tests for feature/fix numbering (_next_feature_key, create assigns key) — I6 reserved names."""
from __future__ import annotations

import pytest

from app.models import FeatureState, TaskState

SPACE_ID = "test-space"


async def _make_feature(store, title="Feature", *, type="feature"):
    return await store.create(space_id=SPACE_ID, title=title, brief="", type=type)


async def _make_fix(store, title="Fix"):
    return await store.create(space_id=SPACE_ID, title=title, brief="", type="fix")


# ---------------------------------------------------------------------------
# I6: _next_feature_key / create() numbering
# ---------------------------------------------------------------------------


async def test_create_feature_assigns_key(task_store):
    """create() must assign feature_key=FEAT-001 to the first feature in a space."""
    feat = await _make_feature(task_store)
    assert feat.feature_key == "FEAT-001"
    assert feat.feature_state == FeatureState.BACKLOG
    assert feat.type == "feature"


async def test_next_feature_key(task_store):
    """Sequential features in the same space get incrementing FEAT-NNN keys."""
    f1 = await _make_feature(task_store, "First")
    f2 = await _make_feature(task_store, "Second")
    f3 = await _make_feature(task_store, "Third")
    assert f1.feature_key == "FEAT-001"
    assert f2.feature_key == "FEAT-002"
    assert f3.feature_key == "FEAT-003"


async def test_fix_counter_independent(task_store):
    """FIX-NNN counter is independent of FEAT-NNN counter."""
    feat = await _make_feature(task_store, "Feat one")
    fix1 = await _make_fix(task_store, "Fix one")
    fix2 = await _make_fix(task_store, "Fix two")
    feat2 = await _make_feature(task_store, "Feat two")

    assert feat.feature_key == "FEAT-001"
    assert fix1.feature_key == "FIX-001"
    assert fix2.feature_key == "FIX-002"
    assert feat2.feature_key == "FEAT-002"


async def test_feat_per_space_isolation(tmp_spaces_dir, space_store, task_store):
    """FEAT counter is isolated per space — creating a feature in space-2 does not affect space-1."""
    # Create a second space
    await space_store.create(
        name="Space Two",
        color="#000000",
        icon=None,
        description="",
        space_id="space-two",
    )

    feat_s1 = await _make_feature(task_store, "Space-1 feature")
    feat_s2 = await task_store.create(space_id="space-two", title="Space-2 feature", brief="", type="feature")

    assert feat_s1.feature_key == "FEAT-001"
    # space-two starts its own counter at 001
    assert feat_s2.feature_key == "FEAT-001"
    # Creating another in space-1 picks up at 002
    feat_s1b = await _make_feature(task_store, "Space-1 feature 2")
    assert feat_s1b.feature_key == "FEAT-002"


async def test_non_feature_no_key(task_store):
    """Regular task, goal, and issue types must NOT get a feature_key or feature_state."""
    for task_type in ("task", "goal", "issue"):
        t = await task_store.create(space_id=SPACE_ID, title=f"A {task_type}", brief="", type=task_type)
        assert t.feature_key is None, f"{task_type} should not have feature_key"
        assert t.feature_state is None, f"{task_type} should not have feature_state"
