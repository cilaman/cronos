"""Tests for git_ops.branch_exists_on_origin.

Covers the four cases from the I1 acceptance criteria:
  - branch present on origin → True
  - branch absent from origin → False
  - invalid branch name       → False (no git call made)
  - subprocess raises         → False (no exception escapes)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.git_ops import branch_exists_on_origin


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_SPACE = Path("/fake/space")


async def _mock_run_exit(code: int):
    """Return an async mock that simulates _run returning (code, '', '')."""
    return (code, "", "")


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_branch_exists_returns_true_when_exit_zero():
    """When git rev-parse exits 0, branch_exists_on_origin returns True."""
    with patch("app.git_ops._run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, "abc123\n", "")
        result = await branch_exists_on_origin(_SPACE, "feature/my-feature")
    assert result is True
    mock_run.assert_awaited_once_with(
        "rev-parse", "--verify", "origin/feature/my-feature", cwd=_SPACE
    )


@pytest.mark.asyncio
async def test_branch_absent_returns_false_when_exit_nonzero():
    """When git rev-parse exits non-zero, branch_exists_on_origin returns False."""
    with patch("app.git_ops._run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (128, "", "fatal: Needed a single revision")
        result = await branch_exists_on_origin(_SPACE, "feature/nonexistent")
    assert result is False
    mock_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_branch_name_returns_false_without_git_call():
    """Invalid branch names (e.g. starting with '-') return False immediately.

    validate_branch raises GitError for unsafe names; branch_exists_on_origin
    must catch that and return False without ever calling git.
    """
    with patch("app.git_ops._run", new_callable=AsyncMock) as mock_run:
        result = await branch_exists_on_origin(_SPACE, "-bad-branch")
    assert result is False
    mock_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_subprocess_raises_returns_false():
    """If the underlying _run coroutine raises, branch_exists_on_origin returns False."""
    with patch("app.git_ops._run", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = OSError("no such process")
        result = await branch_exists_on_origin(_SPACE, "feature/something")
    assert result is False


@pytest.mark.asyncio
async def test_does_not_call_fetch_origin():
    """branch_exists_on_origin must NOT call fetch_origin internally."""
    with patch("app.git_ops._run", new_callable=AsyncMock) as mock_run, \
         patch("app.git_ops.fetch_origin", new_callable=AsyncMock) as mock_fetch:
        mock_run.return_value = (0, "abc123\n", "")
        await branch_exists_on_origin(_SPACE, "main")
    mock_fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_branch_name_with_slashes_is_valid():
    """branch_exists_on_origin handles branch names with slashes (e.g. feature/foo)."""
    with patch("app.git_ops._run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, "deadbeef\n", "")
        result = await branch_exists_on_origin(_SPACE, "feature/foo-bar")
    assert result is True
    # Check the ref passed to git includes the full origin/<branch>
    call_args = mock_run.call_args
    assert "origin/feature/foo-bar" in call_args.args


@pytest.mark.asyncio
async def test_empty_branch_name_returns_false():
    """An empty branch name is invalid; returns False without git call."""
    with patch("app.git_ops._run", new_callable=AsyncMock) as mock_run:
        result = await branch_exists_on_origin(_SPACE, "")
    assert result is False
    mock_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_branch_with_dotdot_returns_false():
    """A branch name containing '..' is invalid; returns False without git call."""
    with patch("app.git_ops._run", new_callable=AsyncMock) as mock_run:
        result = await branch_exists_on_origin(_SPACE, "feat..bad")
    assert result is False
    mock_run.assert_not_awaited()
