"""Tests for feature/fix data model extensions (I1 reserved names).

Covers FeatureState enum, Task/TaskSummary feature fields, TaskType extension,
and feature_state.py transition tables.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.models import FeatureState, Task, TaskSummary, TaskState


# ---------------------------------------------------------------------------
# I1: FeatureState enum
# ---------------------------------------------------------------------------


def test_feature_state_enum():
    members = {fs.value for fs in FeatureState}
    assert members == {"backlog", "processing", "planned", "waiting", "done"}
    # FeatureState is a str enum — values must be strings
    assert all(isinstance(fs.value, str) for fs in FeatureState)
    # Distinct from TaskState — no identity overlap
    assert FeatureState is not TaskState


def test_task_type_extended():
    """TaskType literal must include 'feature' and 'fix'."""
    from app.models import TaskType
    import typing

    # Build a task with each new type to confirm Pydantic accepts it
    base = dict(
        id="t1",
        space_id="s",
        title="x",
        state=TaskState.BACKLOG,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    feat = Task(**base, type="feature")
    fix = Task(**base, type="fix")
    assert feat.type == "feature"
    assert fix.type == "fix"


def test_task_feature_fields():
    """Task model must carry all six optional feature/fix fields."""
    base = dict(
        id="t1",
        space_id="s",
        title="x",
        state=TaskState.BACKLOG,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    # Default: all None
    t = Task(**base)
    assert t.feature_state is None
    assert t.feature_key is None
    assert t.realizes is None
    assert t.issue_number is None
    assert t.issue_url is None
    assert t.proposed_issue_path is None

    # Populated feature task
    t2 = Task(
        **base,
        type="feature",
        feature_state=FeatureState.BACKLOG,
        feature_key="FEAT-001",
        realizes=None,
        issue_number=42,
        issue_url="https://github.com/x/y/issues/42",
        proposed_issue_path=".cronos/issues/FEAT-001.md",
    )
    assert t2.feature_state == FeatureState.BACKLOG
    assert t2.feature_key == "FEAT-001"
    assert t2.issue_number == 42
    assert t2.issue_url == "https://github.com/x/y/issues/42"
    assert t2.proposed_issue_path == ".cronos/issues/FEAT-001.md"


def test_task_summary_feature_fields():
    """TaskSummary must carry the same six optional feature/fix fields."""
    base = dict(
        id="t1",
        space_id="s",
        title="x",
        state=TaskState.BACKLOG,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    ts = TaskSummary(**base)
    assert ts.feature_state is None
    assert ts.feature_key is None
    assert ts.realizes is None
    assert ts.issue_number is None
    assert ts.issue_url is None
    assert ts.proposed_issue_path is None

    ts2 = TaskSummary(
        **base,
        type="fix",
        feature_state=FeatureState.PLANNED,
        feature_key="FIX-003",
        realizes="feat-id-123",
        issue_number=7,
        issue_url="https://github.com/x/y/issues/7",
        proposed_issue_path=".cronos/issues/FIX-003.md",
    )
    assert ts2.feature_state == FeatureState.PLANNED
    assert ts2.feature_key == "FIX-003"
    assert ts2.realizes == "feat-id-123"
    assert ts2.issue_number == 7


# ---------------------------------------------------------------------------
# I4: transition tables (feature_state.py)
# ---------------------------------------------------------------------------


def test_feature_user_transitions():
    """FEATURE_USER_TRANSITIONS must include all 7 allowed user-initiated moves."""
    from app.feature_state import FEATURE_USER_TRANSITIONS

    FS = FeatureState
    expected = frozenset(
        {
            (FS.BACKLOG, FS.PROCESSING),
            (FS.PROCESSING, FS.BACKLOG),
            (FS.PLANNED, FS.PROCESSING),
            (FS.WAITING, FS.PROCESSING),
            (FS.WAITING, FS.PLANNED),
            (FS.PLANNED, FS.DONE),
            (FS.DONE, FS.BACKLOG),
        }
    )
    assert FEATURE_USER_TRANSITIONS == expected
    # Must be typed correctly — each element is a tuple of FeatureState
    for pair in FEATURE_USER_TRANSITIONS:
        assert len(pair) == 2
        assert all(isinstance(s, FeatureState) for s in pair)


def test_feature_worker_transitions():
    """FEATURE_WORKER_TRANSITIONS must include all 5 allowed worker-initiated moves."""
    from app.feature_state import FEATURE_WORKER_TRANSITIONS

    FS = FeatureState
    expected = frozenset(
        {
            (FS.PROCESSING, FS.PLANNED),
            (FS.PROCESSING, FS.WAITING),
            (FS.PLANNED, FS.WAITING),
            (FS.WAITING, FS.PLANNED),
            (FS.PLANNED, FS.DONE),
        }
    )
    assert FEATURE_WORKER_TRANSITIONS == expected
    for pair in FEATURE_WORKER_TRANSITIONS:
        assert len(pair) == 2
        assert all(isinstance(s, FeatureState) for s in pair)
