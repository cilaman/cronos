"""Tests for app.git_issues — one-way GitHub issue mirror helpers."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.git_issues import gh_issue_close, gh_issue_upsert


def _make_proc(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
    proc = MagicMock()
    proc.returncode = returncode
    proc.kill = MagicMock()
    proc.wait = AsyncMock(return_value=returncode)
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


def _gh_found(monkeypatch):
    monkeypatch.setattr("app.git_issues.shutil.which", lambda _: "/usr/bin/gh")


def _gh_absent(monkeypatch):
    monkeypatch.setattr("app.git_issues.shutil.which", lambda _: None)


# ---------------------------------------------------------------------------
# gh_issue_upsert — create path
# ---------------------------------------------------------------------------


async def test_upsert_create_url_only_stdout(tmp_path, monkeypatch):
    """create: stdout is just the URL → returns (number, url)."""
    _gh_found(monkeypatch)
    url = "https://github.com/owner/repo/issues/42"
    proc = _make_proc(stdout=f"{url}\n".encode())
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value="owner/repo")),
        patch("app.git_issues.asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
    ):
        num, got_url = await gh_issue_upsert(tmp_path, title="T", body="B", labels=["bug"], issue_number=None)
    assert num == 42
    assert got_url == url


async def test_upsert_create_multiline_stdout(tmp_path, monkeypatch):
    """create: multi-line stdout with URL embedded → returns (number, url)."""
    _gh_found(monkeypatch)
    url = "https://github.com/owner/repo/issues/7"
    stdout = f"Creating...\nDone!\n{url}\n".encode()
    proc = _make_proc(stdout=stdout)
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value="owner/repo")),
        patch("app.git_issues.asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
    ):
        num, got_url = await gh_issue_upsert(tmp_path, title="T", body="B", labels=[], issue_number=None)
    assert num == 7
    assert got_url == url


async def test_upsert_create_rc_nonzero(tmp_path, monkeypatch):
    """create: rc!=0 → (None, None)."""
    _gh_found(monkeypatch)
    proc = _make_proc(stderr=b"error", returncode=1)
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value="owner/repo")),
        patch("app.git_issues.asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
    ):
        assert await gh_issue_upsert(tmp_path, title="T", body="B", labels=["bug"], issue_number=None) == (None, None)


async def test_upsert_create_labels_passed(tmp_path, monkeypatch):
    """create: multiple labels are forwarded as --label args."""
    _gh_found(monkeypatch)
    url = "https://github.com/owner/repo/issues/10"
    proc = _make_proc(stdout=url.encode())
    mock_exec = AsyncMock(return_value=proc)
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value="owner/repo")),
        patch("app.git_issues.asyncio.create_subprocess_exec", new=mock_exec),
    ):
        await gh_issue_upsert(tmp_path, title="T", body="B", labels=["bug", "feature"], issue_number=None)
    args_str = " ".join(str(a) for a in mock_exec.call_args[0])
    assert "--label" in args_str and "bug" in args_str and "feature" in args_str


# ---------------------------------------------------------------------------
# gh_issue_upsert — edit path
# ---------------------------------------------------------------------------


async def test_upsert_edit_rc_zero(tmp_path, monkeypatch):
    """edit: rc==0 → (issue_number, None)."""
    _gh_found(monkeypatch)
    proc = _make_proc()
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value="owner/repo")),
        patch("app.git_issues.asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
    ):
        num, url = await gh_issue_upsert(tmp_path, title="T", body="B", labels=[], issue_number=99)
    assert num == 99
    assert url is None


async def test_upsert_edit_rc_nonzero(tmp_path, monkeypatch):
    """edit: rc!=0 (stale issue) → (None, None)."""
    _gh_found(monkeypatch)
    proc = _make_proc(stderr=b"not found", returncode=1)
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value="owner/repo")),
        patch("app.git_issues.asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
    ):
        assert await gh_issue_upsert(tmp_path, title="T", body="B", labels=[], issue_number=99) == (None, None)


# ---------------------------------------------------------------------------
# gh_issue_upsert — guard conditions
# ---------------------------------------------------------------------------


async def test_upsert_gh_absent(tmp_path, monkeypatch):
    """shutil.which returns None → (None, None), no subprocess spawned."""
    _gh_absent(monkeypatch)
    mock_exec = AsyncMock()
    with patch("app.git_issues.asyncio.create_subprocess_exec", new=mock_exec):
        assert await gh_issue_upsert(tmp_path, title="T", body="B", labels=[], issue_number=None) == (None, None)
    mock_exec.assert_not_called()


async def test_upsert_no_github_remote(tmp_path, monkeypatch):
    """detect_github_remote returns None → (None, None)."""
    _gh_found(monkeypatch)
    mock_exec = AsyncMock()
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value=None)),
        patch("app.git_issues.asyncio.create_subprocess_exec", new=mock_exec),
    ):
        assert await gh_issue_upsert(tmp_path, title="T", body="B", labels=[], issue_number=None) == (None, None)
    mock_exec.assert_not_called()


async def test_upsert_timeout(tmp_path, monkeypatch):
    """Timeout → (None, None)."""
    _gh_found(monkeypatch)
    proc = _make_proc()
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value="owner/repo")),
        patch("app.git_issues.asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
        patch("app.git_issues.asyncio.wait_for", side_effect=asyncio.TimeoutError()),
    ):
        assert await gh_issue_upsert(tmp_path, title="T", body="B", labels=[], issue_number=None) == (None, None)


async def test_upsert_file_not_found(tmp_path, monkeypatch):
    """FileNotFoundError from create_subprocess_exec → (None, None)."""
    _gh_found(monkeypatch)
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value="owner/repo")),
        patch("app.git_issues.asyncio.create_subprocess_exec", side_effect=FileNotFoundError("gh not found")),
    ):
        assert await gh_issue_upsert(tmp_path, title="T", body="B", labels=[], issue_number=None) == (None, None)


# ---------------------------------------------------------------------------
# gh_issue_close
# ---------------------------------------------------------------------------


async def test_issue_close_rc_zero(tmp_path, monkeypatch):
    """rc==0 → True."""
    _gh_found(monkeypatch)
    proc = _make_proc()
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value="owner/repo")),
        patch("app.git_issues.asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
    ):
        assert await gh_issue_close(tmp_path, 42) is True


async def test_issue_close_rc_nonzero(tmp_path, monkeypatch):
    """rc!=0 → False."""
    _gh_found(monkeypatch)
    proc = _make_proc(returncode=1)
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value="owner/repo")),
        patch("app.git_issues.asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
    ):
        assert await gh_issue_close(tmp_path, 42) is False


async def test_issue_close_gh_absent(tmp_path, monkeypatch):
    """gh not found → False, no subprocess spawned."""
    _gh_absent(monkeypatch)
    mock_exec = AsyncMock()
    with patch("app.git_issues.asyncio.create_subprocess_exec", new=mock_exec):
        assert await gh_issue_close(tmp_path, 42) is False
    mock_exec.assert_not_called()


async def test_issue_close_no_github_remote(tmp_path, monkeypatch):
    """No GitHub remote → False."""
    _gh_found(monkeypatch)
    mock_exec = AsyncMock()
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value=None)),
        patch("app.git_issues.asyncio.create_subprocess_exec", new=mock_exec),
    ):
        assert await gh_issue_close(tmp_path, 42) is False
    mock_exec.assert_not_called()


async def test_issue_close_never_raises(tmp_path, monkeypatch):
    """gh_issue_close never raises even on unexpected exception."""
    _gh_found(monkeypatch)
    with (
        patch("app.git_issues.detect_github_remote", new=AsyncMock(return_value="owner/repo")),
        patch("app.git_issues.asyncio.create_subprocess_exec", side_effect=RuntimeError("boom")),
    ):
        assert await gh_issue_close(tmp_path, 42) is False
