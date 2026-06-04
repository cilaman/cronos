"""Tests for mirror_feature_to_github — I3 acceptance criteria.

Covers:
- R6: MD write strictly before gh_issue_upsert (ordering test).
- R6: set_issue_refs called with correct args per branch (create/edit/none).
- R7: gh_issue_close fires only when reason=state_change + DONE + issue_number set.
- R8: exceptions swallowed; WARNING logged.
- R9: git_repo_url=None still writes MD + persists proposed_issue_path.
- R11: stale issue_number → gh returns (None, None) → set_issue_refs(None, None, md_path).

Tests use:
- Real tmp_path for the space directory.
- AsyncMock for git_issues.gh_issue_upsert and git_issues.gh_issue_close.
- AsyncMock for store.set_issue_refs injected via feature_hooks._task_store.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

import app.feature_hooks as fh
from app.models import FeatureState, Space, Task, TaskState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(**kwargs) -> Task:
    defaults = dict(
        id="task-001",
        space_id="test-space",
        title="My Feature",
        state=TaskState.BACKLOG,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
        type="feature",
        feature_state=FeatureState.BACKLOG,
        feature_key="FEAT-001",
        brief="Some description.",
        issue_number=None,
        issue_url=None,
    )
    defaults.update(kwargs)
    return Task(**defaults)


def _make_space(*, space_id: str = "test-space", **kwargs) -> Space:
    defaults = dict(
        id=space_id,
        name="Test Space",
        color="#15803D",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
        git_repo_url="https://github.com/owner/repo.git",
    )
    defaults.update(kwargs)
    return Space(**defaults)


def _make_mock_store() -> MagicMock:
    """Return a MagicMock that looks like a TaskStore with async set_issue_refs."""
    store = MagicMock()
    store.set_issue_refs = AsyncMock()
    return store


# ---------------------------------------------------------------------------
# Fixture: patch _SPACES_DIR so the hook writes into tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_spaces_dir(tmp_path, monkeypatch):
    """Redirect _SPACES_DIR to tmp_path so tests don't touch /data/spaces."""
    monkeypatch.setattr(fh, "_SPACES_DIR", tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def reset_task_store(monkeypatch):
    """Always reset _task_store to None between tests."""
    monkeypatch.setattr(fh, "_task_store", None)


# ---------------------------------------------------------------------------
# Helpers that patch git_issues functions inside feature_hooks namespace
# ---------------------------------------------------------------------------


def _patch_upsert(return_value, monkeypatch=None):
    """Return a context manager that patches git_issues.gh_issue_upsert."""
    return patch("app.git_issues.gh_issue_upsert", new=AsyncMock(return_value=return_value))


def _patch_close(return_value=True, monkeypatch=None):
    return patch("app.git_issues.gh_issue_close", new=AsyncMock(return_value=return_value))


# ---------------------------------------------------------------------------
# R6: Ordering — MD write BEFORE gh_issue_upsert
# ---------------------------------------------------------------------------


async def test_md_written_before_gh_upsert(tmp_path):
    """R6: write_text must be called strictly before gh_issue_upsert."""
    task = _make_task()
    space = _make_space(space_id=task.space_id)
    store = _make_mock_store()
    fh._task_store = store

    call_order: list[str] = []

    async def mock_upsert(*args, **kwargs):
        call_order.append("upsert")
        return (42, "https://github.com/owner/repo/issues/42")

    original_write_text = Path.write_text

    def tracking_write_text(self, *args, **kwargs):
        call_order.append("write_text")
        return original_write_text(self, *args, **kwargs)

    with (
        patch("app.git_issues.gh_issue_upsert", new=mock_upsert),
        patch("app.git_issues.gh_issue_close", new=AsyncMock(return_value=True)),
        patch.object(Path, "write_text", tracking_write_text),
    ):
        result = await fh.mirror_feature_to_github(task, space=space, reason="create")

    assert result is None
    assert "write_text" in call_order
    assert "upsert" in call_order
    write_idx = call_order.index("write_text")
    upsert_idx = call_order.index("upsert")
    assert write_idx < upsert_idx, (
        f"write_text (idx={write_idx}) must precede upsert (idx={upsert_idx}); "
        f"actual order: {call_order}"
    )


# ---------------------------------------------------------------------------
# Create path: issue_number=None, gh returns (42, url)
# ---------------------------------------------------------------------------


async def test_create_path_calls_set_issue_refs_with_number_and_url(tmp_path):
    """R6 create branch: gh returns (42, url) → set_issue_refs(42, url, None)."""
    task = _make_task(issue_number=None)
    space = _make_space(space_id=task.space_id)
    store = _make_mock_store()
    fh._task_store = store

    issue_url = "https://github.com/owner/repo/issues/42"

    with (
        patch("app.git_issues.gh_issue_upsert", new=AsyncMock(return_value=(42, issue_url))),
        patch("app.git_issues.gh_issue_close", new=AsyncMock(return_value=True)),
    ):
        await fh.mirror_feature_to_github(task, space=space, reason="create")

    store.set_issue_refs.assert_awaited_once_with(
        task.id,
        issue_number=42,
        issue_url=issue_url,
        proposed_issue_path=None,
    )


# ---------------------------------------------------------------------------
# Edit path: issue_number=5, gh returns (5, None)
# ---------------------------------------------------------------------------


async def test_edit_path_calls_set_issue_refs_with_number_no_url(tmp_path):
    """R6 edit branch: gh returns (5, None) → set_issue_refs(5, None, None)."""
    task = _make_task(issue_number=5)
    space = _make_space(space_id=task.space_id)
    store = _make_mock_store()
    fh._task_store = store

    with (
        patch("app.git_issues.gh_issue_upsert", new=AsyncMock(return_value=(5, None))),
        patch("app.git_issues.gh_issue_close", new=AsyncMock(return_value=True)),
    ):
        await fh.mirror_feature_to_github(task, space=space, reason="edit")

    store.set_issue_refs.assert_awaited_once_with(
        task.id,
        issue_number=5,
        issue_url=None,
        proposed_issue_path=None,
    )


# ---------------------------------------------------------------------------
# R11: Stale issue_number — gh edit returns (None, None)
# ---------------------------------------------------------------------------


async def test_stale_issue_number_clears_and_uses_md_path(tmp_path):
    """R11: task.issue_number=5, gh returns (None, None) → set_issue_refs(None, None, md_path)."""
    task = _make_task(issue_number=5)
    space = _make_space(space_id=task.space_id)
    store = _make_mock_store()
    fh._task_store = store

    expected_md_path = tmp_path / task.space_id / ".cronos" / "issues" / f"{task.id}.md"

    with (
        patch("app.git_issues.gh_issue_upsert", new=AsyncMock(return_value=(None, None))),
        patch("app.git_issues.gh_issue_close", new=AsyncMock(return_value=True)),
    ):
        await fh.mirror_feature_to_github(task, space=space, reason="edit")

    store.set_issue_refs.assert_awaited_once_with(
        task.id,
        issue_number=None,
        issue_url=None,
        proposed_issue_path=str(expected_md_path),
    )


# ---------------------------------------------------------------------------
# R9: git_repo_url=None — MD still written + proposed_issue_path set
# ---------------------------------------------------------------------------


async def test_git_repo_url_none_writes_md_and_persists_path(tmp_path):
    """R9: git_repo_url=None → gh returns (None, None) → MD written + proposed_issue_path set."""
    task = _make_task(issue_number=None)
    space = _make_space(space_id=task.space_id, git_repo_url=None)
    store = _make_mock_store()
    fh._task_store = store

    expected_md_path = tmp_path / task.space_id / ".cronos" / "issues" / f"{task.id}.md"

    with (
        patch("app.git_issues.gh_issue_upsert", new=AsyncMock(return_value=(None, None))),
        patch("app.git_issues.gh_issue_close", new=AsyncMock(return_value=True)),
    ):
        await fh.mirror_feature_to_github(task, space=space, reason="create")

    # MD file must exist
    assert expected_md_path.exists(), "MD fallback file must be written"

    # set_issue_refs must be called with proposed_issue_path
    store.set_issue_refs.assert_awaited_once_with(
        task.id,
        issue_number=None,
        issue_url=None,
        proposed_issue_path=str(expected_md_path),
    )


# ---------------------------------------------------------------------------
# R7: Close on state_change + DONE + issue_number set
# ---------------------------------------------------------------------------


async def test_close_fires_on_state_change_done_with_issue_number(tmp_path):
    """R7: reason=state_change, feature_state=DONE, issue_number=5 → gh_issue_close called."""
    task = _make_task(
        issue_number=5,
        feature_state=FeatureState.DONE,
    )
    space = _make_space(space_id=task.space_id)
    store = _make_mock_store()
    fh._task_store = store

    mock_close = AsyncMock(return_value=True)
    with (
        patch("app.git_issues.gh_issue_upsert", new=AsyncMock(return_value=(5, None))),
        patch("app.git_issues.gh_issue_close", new=mock_close),
    ):
        await fh.mirror_feature_to_github(task, space=space, reason="state_change")

    space_dir = tmp_path / task.space_id
    mock_close.assert_awaited_once_with(space_dir, 5)


# ---------------------------------------------------------------------------
# R7 negative: No close when reason != state_change
# ---------------------------------------------------------------------------


async def test_no_close_when_reason_is_edit(tmp_path):
    """R7 neg: reason=edit, feature_state=DONE → gh_issue_close NOT called."""
    task = _make_task(
        issue_number=5,
        feature_state=FeatureState.DONE,
    )
    space = _make_space(space_id=task.space_id)
    store = _make_mock_store()
    fh._task_store = store

    mock_close = AsyncMock(return_value=True)
    with (
        patch("app.git_issues.gh_issue_upsert", new=AsyncMock(return_value=(5, None))),
        patch("app.git_issues.gh_issue_close", new=mock_close),
    ):
        await fh.mirror_feature_to_github(task, space=space, reason="edit")

    mock_close.assert_not_awaited()


# ---------------------------------------------------------------------------
# R7 negative: No close when issue_number is None
# ---------------------------------------------------------------------------


async def test_no_close_when_issue_number_is_none(tmp_path):
    """R7 neg: reason=state_change, feature_state=DONE, issue_number=None → no close."""
    task = _make_task(
        issue_number=None,
        feature_state=FeatureState.DONE,
    )
    space = _make_space(space_id=task.space_id)
    store = _make_mock_store()
    fh._task_store = store

    mock_close = AsyncMock(return_value=True)
    with (
        patch("app.git_issues.gh_issue_upsert", new=AsyncMock(return_value=(None, None))),
        patch("app.git_issues.gh_issue_close", new=mock_close),
    ):
        await fh.mirror_feature_to_github(task, space=space, reason="state_change")

    mock_close.assert_not_awaited()


# ---------------------------------------------------------------------------
# R8: Exception swallowed — returns None, WARNING logged
# ---------------------------------------------------------------------------


async def test_exception_swallowed_returns_none(tmp_path, caplog):
    """R8: gh_issue_upsert raises RuntimeError → function returns None, no re-raise."""
    task = _make_task()
    space = _make_space(space_id=task.space_id)
    store = _make_mock_store()
    fh._task_store = store

    with (
        patch(
            "app.git_issues.gh_issue_upsert",
            new=AsyncMock(side_effect=RuntimeError("simulated gh failure")),
        ),
        patch("app.git_issues.gh_issue_close", new=AsyncMock(return_value=True)),
        caplog.at_level(logging.WARNING, logger="app.feature_hooks"),
    ):
        result = await fh.mirror_feature_to_github(task, space=space, reason="create")

    assert result is None

    # Must have emitted a WARNING
    warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warning_records, "Expected at least one WARNING log record after exception"
    # task.id should appear in the message
    assert any(task.id in r.message for r in warning_records), (
        f"Expected task.id={task.id!r} in WARNING message; got: "
        + "; ".join(r.message for r in warning_records)
    )


# ---------------------------------------------------------------------------
# task.type not in ("feature", "fix") — early return, no MD, no gh calls
# ---------------------------------------------------------------------------


async def test_early_return_for_non_feature_type(tmp_path):
    """task.type=backlog-equivalent (type='task') → immediate return, no side effects."""
    task = _make_task(type="task", feature_state=None, feature_key=None)
    space = _make_space(space_id=task.space_id)
    store = _make_mock_store()
    fh._task_store = store

    mock_upsert = AsyncMock(return_value=(None, None))
    mock_close = AsyncMock(return_value=True)

    with (
        patch("app.git_issues.gh_issue_upsert", new=mock_upsert),
        patch("app.git_issues.gh_issue_close", new=mock_close),
    ):
        result = await fh.mirror_feature_to_github(task, space=space, reason="create")

    assert result is None
    mock_upsert.assert_not_awaited()
    mock_close.assert_not_awaited()
    store.set_issue_refs.assert_not_awaited()

    # No MD file should be written
    issues_dir = tmp_path / task.space_id / ".cronos" / "issues"
    md_path = issues_dir / f"{task.id}.md"
    assert not md_path.exists(), "MD file must NOT be written for non-feature/fix tasks"


# ---------------------------------------------------------------------------
# MD content is correct
# ---------------------------------------------------------------------------


async def test_md_content_format(tmp_path):
    """The MD fallback has the correct format: # {feature_key}: {title}\\n\\n{brief}\\n"""
    task = _make_task(
        feature_key="FEAT-007",
        title="My Important Feature",
        brief="Brief description here.",
        issue_number=None,
    )
    space = _make_space(space_id=task.space_id)
    store = _make_mock_store()
    fh._task_store = store

    with (
        patch("app.git_issues.gh_issue_upsert", new=AsyncMock(return_value=(None, None))),
        patch("app.git_issues.gh_issue_close", new=AsyncMock(return_value=True)),
    ):
        await fh.mirror_feature_to_github(task, space=space, reason="create")

    md_path = tmp_path / task.space_id / ".cronos" / "issues" / f"{task.id}.md"
    assert md_path.exists()
    content = md_path.read_text(encoding="utf-8")
    expected = "# FEAT-007: My Important Feature\n\nBrief description here.\n"
    assert content == expected, f"MD content mismatch:\n  got: {content!r}\n  want: {expected!r}"


# ---------------------------------------------------------------------------
# "fix" type is also mirrored (type guard allows both feature and fix)
# ---------------------------------------------------------------------------


async def test_fix_type_is_mirrored(tmp_path):
    """task.type='fix' must also trigger the mirror (not just 'feature')."""
    task = _make_task(type="fix", feature_key="FIX-003", issue_number=None)
    space = _make_space(space_id=task.space_id)
    store = _make_mock_store()
    fh._task_store = store

    mock_upsert = AsyncMock(return_value=(None, None))
    with (
        patch("app.git_issues.gh_issue_upsert", new=mock_upsert),
        patch("app.git_issues.gh_issue_close", new=AsyncMock(return_value=True)),
    ):
        await fh.mirror_feature_to_github(task, space=space, reason="create")

    mock_upsert.assert_awaited_once()
