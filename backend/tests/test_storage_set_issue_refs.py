"""Tests for TaskStore.set_issue_refs — I2 of featurefix-github-issues."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.storage import TaskNotFound, TaskStore
from app.models import Task

from .conftest import SPACE_ID


# ---------------------------------------------------------------------------
# TaskStore.set_issue_refs
# ---------------------------------------------------------------------------


async def test_set_issue_refs_issue_number_and_url(task_store):
    """Setting issue_number + issue_url (gh success case) persists both fields."""
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")

    updated = await task_store.set_issue_refs(
        task.id,
        issue_number=42,
        issue_url="https://github.com/foo/bar/issues/42",
        proposed_issue_path=None,
    )

    assert updated.issue_number == 42
    assert updated.issue_url == "https://github.com/foo/bar/issues/42"
    assert updated.proposed_issue_path is None
    # In-memory index must also reflect new values.
    refreshed = task_store.get(task.id)
    assert refreshed.issue_number == 42
    assert refreshed.issue_url == "https://github.com/foo/bar/issues/42"


async def test_set_issue_refs_proposed_path_only(task_store):
    """Setting proposed_issue_path only (fallback case) persists path; number and url are None."""
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")

    updated = await task_store.set_issue_refs(
        task.id,
        issue_number=None,
        issue_url=None,
        proposed_issue_path="/tmp/issues/my-task.md",
    )

    assert updated.issue_number is None
    assert updated.issue_url is None
    assert updated.proposed_issue_path == "/tmp/issues/my-task.md"


async def test_set_issue_refs_all_three_fields(task_store):
    """Setting all three fields at once stores all of them."""
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")

    updated = await task_store.set_issue_refs(
        task.id,
        issue_number=7,
        issue_url="https://github.com/x/y/issues/7",
        proposed_issue_path="/cronos/issues/t.md",
    )

    assert updated.issue_number == 7
    assert updated.issue_url == "https://github.com/x/y/issues/7"
    assert updated.proposed_issue_path == "/cronos/issues/t.md"


async def test_set_issue_refs_raises_task_not_found(task_store):
    """Unknown task_id raises TaskNotFound."""
    with pytest.raises(TaskNotFound):
        await task_store.set_issue_refs(
            "nonexistent-task-id",
            issue_number=1,
            issue_url="https://github.com/x/y/issues/1",
            proposed_issue_path=None,
        )


async def test_set_issue_refs_updates_updated_at(task_store):
    """updated_at is bumped by set_issue_refs."""
    from datetime import UTC, datetime

    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")
    before = task.updated_at

    updated = await task_store.set_issue_refs(
        task.id,
        issue_number=1,
        issue_url=None,
        proposed_issue_path=None,
    )

    assert updated.updated_at >= before


async def test_set_issue_refs_persists_to_disk(task_store, tmp_spaces_dir):
    """After set_issue_refs, a fresh TaskStore.reload_all() sees the new values."""
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")
    await task_store.set_issue_refs(
        task.id,
        issue_number=99,
        issue_url="https://github.com/a/b/issues/99",
        proposed_issue_path=None,
    )

    fresh = TaskStore(tmp_spaces_dir)
    await fresh.reload_all()

    reloaded = fresh.get(task.id)
    assert reloaded is not None
    assert reloaded.issue_number == 99
    assert reloaded.issue_url == "https://github.com/a/b/issues/99"
    assert reloaded.proposed_issue_path is None


async def test_set_issue_refs_clears_previous_values(task_store):
    """Passing issue_number=None and issue_url=None clears previously set values."""
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")
    # First: set real values.
    await task_store.set_issue_refs(
        task.id,
        issue_number=5,
        issue_url="https://github.com/x/y/issues/5",
        proposed_issue_path=None,
    )

    # Then: clear them.
    cleared = await task_store.set_issue_refs(
        task.id,
        issue_number=None,
        issue_url=None,
        proposed_issue_path=None,
    )

    assert cleared.issue_number is None
    assert cleared.issue_url is None
    assert cleared.proposed_issue_path is None
    # In-memory index must also be cleared.
    assert task_store.get(task.id).issue_number is None
