"""Tests for feature/fix parse_file and dump_task serialization (I3 reserved names).

Covers type guard widening, feature field round-trip, and legacy MD backward compat.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import frontmatter
import pytest

from app.models import FeatureState, Task, TaskState
from app.storage import dump_task, parse_file


_BASE_META = {
    "id": "2026-01-01-1200-feat-widget",
    "space_id": "spc1",
    "title": "Widget feature",
    "state": "backlog",
    "created_at": "2026-01-01T12:00:00",
    "updated_at": "2026-01-01T12:00:00",
    "type": "feature",
    "feature_state": "backlog",
    "feature_key": "FEAT-001",
}


def _write_md(tmp_path: Path, meta: dict, body: str = "") -> Path:
    p = tmp_path / f"{meta['id']}.md"
    post = frontmatter.Post(body, **meta)
    p.write_text(frontmatter.dumps(post) + "\n")
    return p


def test_parse_file_feature(tmp_path):
    """parse_file must read all six feature fields from frontmatter."""
    meta = {
        **_BASE_META,
        "feature_state": "processing",
        "feature_key": "FEAT-007",
        "realizes": None,
        "issue_number": 42,
        "issue_url": "https://github.com/x/y/issues/42",
        "proposed_issue_path": ".cronos/issues/FEAT-007.md",
    }
    path = _write_md(tmp_path, meta)
    task = parse_file(path, "spc1")

    assert task.type == "feature"
    assert task.feature_state == FeatureState.PROCESSING
    assert task.feature_key == "FEAT-007"
    assert task.realizes is None
    assert task.issue_number == 42
    assert task.issue_url == "https://github.com/x/y/issues/42"
    assert task.proposed_issue_path == ".cronos/issues/FEAT-007.md"


def test_dump_task_feature(tmp_path):
    """dump_task must serialize all six feature fields into frontmatter."""
    task = Task(
        id="t1",
        space_id="spc1",
        title="My fix",
        state=TaskState.BACKLOG,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        type="fix",
        feature_state=FeatureState.PLANNED,
        feature_key="FIX-003",
        realizes="feat-42",
        issue_number=7,
        issue_url="https://github.com/x/y/issues/7",
        proposed_issue_path=".cronos/issues/FIX-003.md",
    )
    md = dump_task(task)
    post = frontmatter.loads(md)
    assert post.metadata["feature_state"] == "planned"
    assert post.metadata["feature_key"] == "FIX-003"
    assert post.metadata["realizes"] == "feat-42"
    assert post.metadata["issue_number"] == 7
    assert post.metadata["issue_url"] == "https://github.com/x/y/issues/7"
    assert post.metadata["proposed_issue_path"] == ".cronos/issues/FIX-003.md"


def test_feature_round_trip(tmp_path):
    """dump_task → write → parse_file must preserve all feature fields exactly."""
    task = Task(
        id="2026-01-01-1200-round-trip",
        space_id="spc1",
        title="Round-trip feature",
        state=TaskState.BACKLOG,
        created_at=datetime(2026, 1, 1, 12, 0),
        updated_at=datetime(2026, 1, 1, 12, 0),
        type="feature",
        feature_state=FeatureState.WAITING,
        feature_key="FEAT-099",
        realizes=None,
        issue_number=99,
        issue_url="https://example.com/99",
        proposed_issue_path=".cronos/issues/FEAT-099.md",
    )
    path = tmp_path / f"{task.id}.md"
    path.write_text(dump_task(task))

    loaded = parse_file(path, "spc1")
    assert loaded.feature_state == FeatureState.WAITING
    assert loaded.feature_key == "FEAT-099"
    assert loaded.realizes is None
    assert loaded.issue_number == 99
    assert loaded.issue_url == "https://example.com/99"
    assert loaded.proposed_issue_path == ".cronos/issues/FEAT-099.md"
    assert loaded.type == "feature"


def test_legacy_md_backward_compat(tmp_path):
    """Old MD files without feature fields must load without error; fields default to None."""
    # Minimal legacy frontmatter — no feature_* keys at all
    meta = {
        "id": "old-task-1",
        "space_id": "spc1",
        "title": "Old task",
        "state": "backlog",
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
        "type": "task",
    }
    path = _write_md(tmp_path, meta)
    task = parse_file(path, "spc1")

    assert task.feature_state is None
    assert task.feature_key is None
    assert task.realizes is None
    assert task.issue_number is None
    assert task.issue_url is None
    assert task.proposed_issue_path is None
    assert task.type == "task"

    # Also verify unknown type coerces to "task" (not a raise)
    meta_bad_type = {**meta, "id": "old-task-2", "type": "sprocket"}
    path2 = _write_md(tmp_path, meta_bad_type)
    task2 = parse_file(path2, "spc1")
    assert task2.type == "task", "Unknown type must coerce to 'task', not raise"
