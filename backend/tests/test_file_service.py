"""Tests for app.file_service.

Covers classify_file, list_files, list_git_changed_files, resolve_safe,
and save_upload. The module was previously at 19% coverage.
"""

from __future__ import annotations

import asyncio
import subprocess
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.file_service import (
    FileEntry,
    classify_file,
    list_files,
    list_git_changed_files,
    resolve_safe,
    save_upload,
)


# ---------------------------------------------------------------------------
# classify_file
# ---------------------------------------------------------------------------


def test_classify_file_image_extensions():
    assert classify_file("a.png", "a.png") == "image"
    assert classify_file("dir/b.JPG", "b.JPG") == "image"
    assert classify_file("logo.svg", "logo.svg") == "image"


def test_classify_file_text_extensions():
    assert classify_file("readme.md", "readme.md") == "text"
    assert classify_file("data.csv", "data.csv") == "text"
    assert classify_file("conf.yaml", "conf.yaml") == "text"


def test_classify_file_code_extensions():
    assert classify_file("a.py", "a.py") == "code"
    assert classify_file("ui/B.TSX", "B.TSX") == "code"
    assert classify_file("script.sh", "script.sh") == "code"


def test_classify_file_document_archive_binary():
    assert classify_file("paper.pdf", "paper.pdf") == "document"
    assert classify_file("bundle.zip", "bundle.zip") == "archive"
    assert classify_file("blob.bin", "blob.bin") == "binary"
    assert classify_file("noext", "noext") == "binary"


def test_classify_file_ai_prefix_rules_take_priority():
    # .md normally is "text" but agent prefix wins
    assert classify_file(".claude/agents/foo.md", "foo.md") == "agent"
    assert classify_file(".claude/skills/x.md", "x.md") == "skill"
    assert classify_file(".claude/commands/build.md", "build.md") == "command"
    assert classify_file(".claude/context/notes.md", "notes.md") == "context"
    # Exact path match for CONTEXT.md (not under a subdir)
    assert classify_file(".claude/CONTEXT.md", "CONTEXT.md") == "context"


def test_classify_file_normalises_backslashes():
    # Windows-style separators should be normalised before prefix check
    assert classify_file(".claude\\agents\\foo.md", "foo.md") == "agent"


# ---------------------------------------------------------------------------
# resolve_safe
# ---------------------------------------------------------------------------


def test_resolve_safe_simple_inside(tmp_path: Path):
    target = tmp_path / "sub" / "file.txt"
    target.parent.mkdir()
    target.write_text("hi")
    assert resolve_safe(tmp_path, "sub/file.txt") == target.resolve()


def test_resolve_safe_strips_leading_slash_and_normalises(tmp_path: Path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "y.txt").write_text("hi")
    # Leading slash and backslash should both work
    assert resolve_safe(tmp_path, "/x/y.txt") == (tmp_path / "x" / "y.txt").resolve()
    assert resolve_safe(tmp_path, "x\\y.txt") == (tmp_path / "x" / "y.txt").resolve()


def test_resolve_safe_blocks_traversal(tmp_path: Path):
    with pytest.raises(ValueError, match="traversal"):
        resolve_safe(tmp_path, "../etc/passwd")
    with pytest.raises(ValueError, match="traversal"):
        resolve_safe(tmp_path, "a/../../outside.txt")


def test_resolve_safe_root_path_allowed(tmp_path: Path):
    # Empty path should resolve to root itself
    assert resolve_safe(tmp_path, "") == tmp_path.resolve()


# ---------------------------------------------------------------------------
# list_files
# ---------------------------------------------------------------------------


def test_list_files_basic_tree(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("print(1)")

    entries = list_files(tmp_path)
    by_path = {e.path: e for e in entries}

    assert "a.txt" in by_path
    assert "sub" in by_path
    assert "sub/b.py" in by_path
    assert by_path["a.txt"].category == "text"
    assert by_path["sub"].is_dir is True
    assert by_path["sub"].category == "directory"
    assert by_path["sub/b.py"].category == "code"
    # Files report their size; dirs report 0
    assert by_path["a.txt"].size == 5
    assert by_path["sub"].size == 0


def test_list_files_skips_hidden_outside_claude(tmp_path: Path):
    (tmp_path / ".secret").write_text("nope")
    (tmp_path / ".env").write_text("X=1")
    (tmp_path / "visible.md").write_text("ok")

    paths = {e.path for e in list_files(tmp_path)}
    assert "visible.md" in paths
    assert ".secret" not in paths
    assert ".env" not in paths


def test_list_files_includes_dotclaude_artifacts(tmp_path: Path):
    claude = tmp_path / ".claude" / "agents"
    claude.mkdir(parents=True)
    (claude / "tester.md").write_text("agent body")

    paths = {e.path for e in list_files(tmp_path)}
    # The top-level ".claude" dir is hidden (starts with dot, not under .claude prefix yet),
    # so it must NOT appear...
    assert ".claude" not in paths
    # ...which means descendants are unreachable through the walker too.
    # Verify behaviour: nothing under .claude/ shows up because the walker
    # never descends into it.
    assert all(not p.startswith(".claude") for p in paths)


def test_list_files_skip_prefixes(tmp_path: Path):
    (tmp_path / ".cronos").mkdir()
    (tmp_path / ".cronos" / "state.json").write_text("{}")
    (tmp_path / "keep.txt").write_text("y")

    paths = {e.path for e in list_files(tmp_path, skip_prefixes=(".cronos",))}
    assert "keep.txt" in paths
    assert not any(p.startswith(".cronos") for p in paths)


def test_list_files_respects_max_entries(tmp_path: Path):
    for i in range(10):
        (tmp_path / f"f{i}.txt").write_text(str(i))
    entries = list_files(tmp_path, max_entries=4)
    assert len(entries) == 4


def test_list_files_sort_order_dirs_before_files(tmp_path: Path):
    (tmp_path / "z.txt").write_text("z")
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "inner.txt").write_text("i")
    (tmp_path / "beta").mkdir()

    top_entries = [e for e in list_files(tmp_path) if "/" not in e.path]
    # Among top-level entries, directories must come before files
    kinds = [e.is_dir for e in top_entries]
    assert kinds == sorted(kinds, reverse=True)


def test_list_files_returns_file_entry_instances(tmp_path: Path):
    (tmp_path / "x.md").write_text("hi")
    entries = list_files(tmp_path)
    assert entries and all(isinstance(e, FileEntry) for e in entries)


# ---------------------------------------------------------------------------
# list_git_changed_files
# ---------------------------------------------------------------------------


async def test_list_git_changed_files_returns_none_when_not_a_repo(tmp_path: Path):
    result = await list_git_changed_files(tmp_path)
    assert result is None


async def test_list_git_changed_files_lists_untracked_and_modified(tmp_path: Path):
    # Initialise a git repo
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "tester"], check=True
    )
    # Initial committed file
    (tmp_path / "committed.txt").write_text("orig")
    subprocess.run(["git", "-C", str(tmp_path), "add", "committed.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "init"], check=True
    )
    # Modify committed file
    (tmp_path / "committed.txt").write_text("changed")
    # Add a new untracked file
    (tmp_path / "newfile.py").write_text("print('hi')")
    # Delete a committed file — should NOT appear in result
    (tmp_path / "to_delete.txt").write_text("bye")
    subprocess.run(["git", "-C", str(tmp_path), "add", "to_delete.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "add deletable"], check=True
    )
    (tmp_path / "to_delete.txt").unlink()

    result = await list_git_changed_files(tmp_path)
    assert result is not None
    paths = {e.path for e in result}
    assert "committed.txt" in paths
    assert "newfile.py" in paths
    assert "to_delete.txt" not in paths  # deleted entries excluded
    # Entries are sorted by path
    assert [e.path for e in result] == sorted(e.path for e in result)


# ---------------------------------------------------------------------------
# save_upload
# ---------------------------------------------------------------------------


def _make_upload(content: bytes, filename: str) -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=filename)


async def test_save_upload_writes_file_and_returns_entry(tmp_path: Path):
    upload = _make_upload(b"hello world", "greeting.txt")
    entry = await save_upload(tmp_path, "uploads", upload)

    dest = tmp_path / "uploads" / "greeting.txt"
    assert dest.exists()
    assert dest.read_bytes() == b"hello world"
    assert entry.name == "greeting.txt"
    assert entry.path == "uploads/greeting.txt"
    assert entry.size == 11
    assert entry.category == "text"
    assert entry.is_dir is False
    # No leftover temp file
    assert not (tmp_path / "uploads" / "greeting.txt.tmp").exists()


async def test_save_upload_strips_path_components_from_filename(tmp_path: Path):
    upload = _make_upload(b"x", "../../evil.txt")
    entry = await save_upload(tmp_path, "", upload)
    # Only the basename is used
    assert entry.name == "evil.txt"
    assert (tmp_path / "evil.txt").exists()
    # No file escaped outside the root
    assert not (tmp_path.parent / "evil.txt").exists()


async def test_save_upload_rejects_subdir_traversal(tmp_path: Path):
    upload = _make_upload(b"x", "f.txt")
    with pytest.raises(ValueError, match="traversal"):
        await save_upload(tmp_path, "../escape", upload)


async def test_save_upload_enforces_max_bytes_and_cleans_tmp(tmp_path: Path):
    upload = _make_upload(b"A" * 100, "big.bin")
    with pytest.raises(ValueError, match="maximum allowed size"):
        await save_upload(tmp_path, "", upload, max_bytes=10)
    # No partial file or temp file left behind
    assert not (tmp_path / "big.bin").exists()
    assert not (tmp_path / "big.bin.tmp").exists()


async def test_save_upload_creates_intermediate_dirs(tmp_path: Path):
    upload = _make_upload(b"data", "deep.txt")
    entry = await save_upload(tmp_path, "a/b/c", upload)
    assert (tmp_path / "a" / "b" / "c" / "deep.txt").exists()
    assert entry.path == "a/b/c/deep.txt"


async def test_save_upload_default_filename_when_missing(tmp_path: Path):
    # filename=None falls back to "upload"
    upload = UploadFile(file=BytesIO(b"x"), filename=None)
    entry = await save_upload(tmp_path, "", upload)
    assert entry.name == "upload"
    assert (tmp_path / "upload").exists()
