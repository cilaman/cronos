"""Tests for feature/fix Pydantic request and response schemas (I1).

Covers R2: CreateFeatureBody, PatchFeatureBody, PatchFeatureStateBody,
PatchRealizeBody, FeatureBoard, FeatureRead are all importable and validate
correctly.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import (
    CreateFeatureBody,
    FeatureBoard,
    FeatureRead,
    FeatureState,
    PatchFeatureBody,
    PatchFeatureStateBody,
    PatchRealizeBody,
    TaskState,
    TaskSummary,
)


# ---------------------------------------------------------------------------
# CreateFeatureBody
# ---------------------------------------------------------------------------

class TestCreateFeatureBody:
    def test_valid_feature(self):
        body = CreateFeatureBody(
            space_id="sp1",
            title="My feature",
            brief="Details here",
            type="feature",
        )
        assert body.space_id == "sp1"
        assert body.title == "My feature"
        assert body.type == "feature"
        assert body.priority == 3  # default

    def test_valid_fix(self):
        body = CreateFeatureBody(
            space_id="sp1",
            title="My fix",
            brief="",
            type="fix",
            priority=1,
        )
        assert body.type == "fix"
        assert body.priority == 1

    def test_priority_bounds(self):
        # ge=1
        with pytest.raises(ValidationError):
            CreateFeatureBody(space_id="s", title="t", brief="", type="feature", priority=0)
        # le=5
        with pytest.raises(ValidationError):
            CreateFeatureBody(space_id="s", title="t", brief="", type="feature", priority=6)

    def test_priority_extremes_valid(self):
        b1 = CreateFeatureBody(space_id="s", title="t", brief="", type="feature", priority=1)
        b5 = CreateFeatureBody(space_id="s", title="t", brief="", type="feature", priority=5)
        assert b1.priority == 1
        assert b5.priority == 5

    def test_type_must_be_feature_or_fix(self):
        with pytest.raises(ValidationError):
            CreateFeatureBody(space_id="s", title="t", brief="", type="task")  # type: ignore[arg-type]

    def test_brief_defaults_to_empty_string(self):
        body = CreateFeatureBody(space_id="s", title="t", type="feature")
        assert body.brief == ""


# ---------------------------------------------------------------------------
# PatchFeatureBody
# ---------------------------------------------------------------------------

class TestPatchFeatureBody:
    def test_all_none(self):
        body = PatchFeatureBody()
        assert body.title is None
        assert body.brief is None

    def test_title_only(self):
        body = PatchFeatureBody(title="New title")
        assert body.title == "New title"
        assert body.brief is None

    def test_brief_only(self):
        body = PatchFeatureBody(brief="New brief")
        assert body.brief == "New brief"
        assert body.title is None

    def test_both(self):
        body = PatchFeatureBody(title="T", brief="B")
        assert body.title == "T"
        assert body.brief == "B"


# ---------------------------------------------------------------------------
# PatchFeatureStateBody
# ---------------------------------------------------------------------------

class TestPatchFeatureStateBody:
    def test_valid_state(self):
        body = PatchFeatureStateBody(feature_state=FeatureState.PROCESSING)
        assert body.feature_state == FeatureState.PROCESSING

    def test_all_valid_states(self):
        for state in FeatureState:
            body = PatchFeatureStateBody(feature_state=state)
            assert body.feature_state == state

    def test_invalid_state_string_rejected(self):
        with pytest.raises(ValidationError):
            PatchFeatureStateBody(feature_state="unknown_state")  # type: ignore[arg-type]

    def test_accepts_string_value_coercion(self):
        # Pydantic coerces string to enum when it matches a value
        body = PatchFeatureStateBody(feature_state="backlog")  # type: ignore[arg-type]
        assert body.feature_state == FeatureState.BACKLOG

    def test_rejects_wrong_case(self):
        with pytest.raises(ValidationError):
            PatchFeatureStateBody(feature_state="PROCESSING")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PatchRealizeBody
# ---------------------------------------------------------------------------

class TestPatchRealizeBody:
    def test_with_feature_id(self):
        body = PatchRealizeBody(item_id="task-1", feature_id="feat-1")
        assert body.item_id == "task-1"
        assert body.feature_id == "feat-1"

    def test_feature_id_none_for_unlink(self):
        body = PatchRealizeBody(item_id="task-1", feature_id=None)
        assert body.feature_id is None

    def test_feature_id_defaults_to_none(self):
        body = PatchRealizeBody(item_id="task-1")
        assert body.feature_id is None

    def test_item_id_required(self):
        with pytest.raises(ValidationError):
            PatchRealizeBody(feature_id="feat-1")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# FeatureBoard
# ---------------------------------------------------------------------------

def _make_summary(id_: str, state: TaskState = TaskState.BACKLOG) -> TaskSummary:
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc)
    return TaskSummary(
        id=id_,
        space_id="sp1",
        title=f"Task {id_}",
        state=state,
        created_at=now,
        updated_at=now,
    )


class TestFeatureBoard:
    def test_default_lanes_empty(self):
        board = FeatureBoard()
        assert board.backlog == []
        assert board.processing == []
        assert board.planned == []
        assert board.waiting == []
        assert board.done == []

    def test_five_lanes(self):
        # Ensure exactly 5 lane fields exist by name
        fields = set(FeatureBoard.model_fields.keys())
        assert fields == {"backlog", "processing", "planned", "waiting", "done"}

    def test_populate_lanes(self):
        t1 = _make_summary("t1")
        t2 = _make_summary("t2")
        board = FeatureBoard(backlog=[t1], processing=[t2])
        assert len(board.backlog) == 1
        assert len(board.processing) == 1
        assert board.planned == []

    def test_no_active_lane(self):
        """FeatureBoard must NOT have an 'active' lane (unlike Board)."""
        assert "active" not in FeatureBoard.model_fields


# ---------------------------------------------------------------------------
# FeatureRead
# ---------------------------------------------------------------------------

class TestFeatureRead:
    def _make(self, **kwargs) -> FeatureRead:
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        defaults = dict(
            id="feat-1",
            space_id="sp1",
            title="My Feature",
            state=TaskState.ACTIVE,
            created_at=now,
            updated_at=now,
            type="feature",
        )
        defaults.update(kwargs)
        return FeatureRead(**defaults)

    def test_minimal_valid(self):
        fr = self._make()
        assert fr.id == "feat-1"
        assert fr.realizing_items == []

    def test_realizing_items_populated(self):
        items = [_make_summary("t1"), _make_summary("t2")]
        fr = self._make(realizing_items=items)
        assert len(fr.realizing_items) == 2
        assert fr.realizing_items[0].id == "t1"

    def test_feature_state_field(self):
        fr = self._make(feature_state=FeatureState.PLANNED)
        assert fr.feature_state == FeatureState.PLANNED

    def test_feature_key_field(self):
        fr = self._make(feature_key="FEAT-001")
        assert fr.feature_key == "FEAT-001"

    def test_fix_type(self):
        fr = self._make(type="fix", feature_key="FIX-007")
        assert fr.type == "fix"
        assert fr.feature_key == "FIX-007"

    def test_optional_fields_default_none(self):
        fr = self._make()
        assert fr.feature_state is None
        assert fr.feature_key is None
        assert fr.realizes is None
        assert fr.pr_url is None

    def test_has_task_read_equivalent_fields(self):
        """FeatureRead must carry core TaskRead-equivalent fields."""
        fr = self._make()
        for field in ("id", "space_id", "title", "state", "created_at", "updated_at",
                      "brief", "priority", "type", "parent_id", "depends_on"):
            assert hasattr(fr, field), f"Missing field: {field}"
