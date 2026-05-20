from __future__ import annotations

"""Additional spaces API tests covering link/unlink and export endpoints."""

import io
import zipfile
from pathlib import Path

import pytest

from app.api.spaces import _safe_extract
from app.models import TaskState
from app.space_storage import SpaceError, validate_color, validate_space_id
from app.storage import parse_file

from .conftest import SPACE_ID

_VALID_SPACE_YML = """\
id: imp-space
name: Imported Space
color: '#AABBCC'
icon: null
description: ''
created_at: '2024-01-01T00:00:00+00:00'
updated_at: '2024-01-01T00:00:00+00:00'
git_repo_url: null
git_branch: null
git_share_cronos: false
agent_defaults: {}
"""


# ---------------------------------------------------------------------------
# POST /api/spaces/{space_id}/unlink
# ---------------------------------------------------------------------------


async def test_unlink_space_not_linked_returns_200(async_client):
    resp = await async_client.post(f"/api/spaces/{SPACE_ID}/unlink")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == SPACE_ID
    assert data["git_repo_url"] is None


async def test_unlink_nonexistent_space_returns_404(async_client):
    resp = await async_client.post("/api/spaces/no-such-space/unlink")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/spaces/{space_id}/link
# ---------------------------------------------------------------------------


async def test_link_nonexistent_space_returns_404(async_client):
    resp = await async_client.post(
        "/api/spaces/no-such-space/link",
        json={"repo_url": "https://github.com/example/repo.git", "branch": "main"},
    )
    assert resp.status_code == 404


async def test_link_missing_fields_returns_422(async_client):
    resp = await async_client.post(
        f"/api/spaces/{SPACE_ID}/link",
        json={"repo_url": "https://github.com/example/repo.git"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/spaces/{space_id}/export
# ---------------------------------------------------------------------------


async def test_export_space_not_found_returns_404(async_client):
    resp = await async_client.get("/api/spaces/no-such-space/export")
    assert resp.status_code == 404


async def test_export_space_returns_zip(async_client):
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    content_disp = resp.headers.get("content-disposition", "")
    assert f"{SPACE_ID}.zip" in content_disp


async def test_export_space_valid_zip_content(async_client):
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/export")
    assert resp.status_code == 200
    buf = io.BytesIO(resp.content)
    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()
    assert any(SPACE_ID in n for n in names)


async def test_export_newly_created_space(async_client):
    await async_client.post(
        "/api/spaces",
        json={"name": "Export Me", "color": "#123456", "space_id": "export-test"},
    )
    resp = await async_client.get("/api/spaces/export-test/export")
    assert resp.status_code == 200
    buf = io.BytesIO(resp.content)
    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()
    assert any("export-test" in n for n in names)


# ---------------------------------------------------------------------------
# _safe_extract (unit tests via direct call)
# ---------------------------------------------------------------------------


def _make_zip(entries: dict[str, bytes]) -> io.BytesIO:
    """Create an in-memory zip with the given {arcname: content} entries."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    buf.seek(0)
    return buf


def test_safe_extract_valid_zip(tmp_path: Path):
    buf = _make_zip({
        "my-space/.cronos/space.yml": b"id: my-space\n",
        "my-space/.cronos/tasks/t1.md": b"# Task\n",
    })
    with zipfile.ZipFile(buf) as zf:
        incoming_id = _safe_extract(zf, tmp_path)
    assert incoming_id == "my-space"
    assert (tmp_path / "my-space" / ".cronos" / "space.yml").exists()


def test_safe_extract_missing_space_yml_raises(tmp_path: Path):
    buf = _make_zip({"my-space/.cronos/tasks/t1.md": b"# Task\n"})
    with zipfile.ZipFile(buf) as zf:
        with pytest.raises(SpaceError, match="space.yml"):
            _safe_extract(zf, tmp_path)


def test_safe_extract_multiple_top_level_dirs_raises(tmp_path: Path):
    buf = _make_zip({
        "space-a/.cronos/space.yml": b"",
        "space-b/.cronos/space.yml": b"",
    })
    with zipfile.ZipFile(buf) as zf:
        with pytest.raises(SpaceError, match="exactly one top-level"):
            _safe_extract(zf, tmp_path)


def test_safe_extract_dotdot_path_raises(tmp_path: Path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        info = zipfile.ZipInfo("space-a/../evil.txt")
        zf.writestr(info, b"evil")
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        with pytest.raises(SpaceError, match="Unsafe"):
            _safe_extract(zf, tmp_path)


def test_safe_extract_disallowed_subpath_raises(tmp_path: Path):
    buf = _make_zip({
        "my-space/.cronos/space.yml": b"",
        "my-space/repo-file.py": b"",
    })
    with zipfile.ZipFile(buf) as zf:
        with pytest.raises(SpaceError, match="Disallowed"):
            _safe_extract(zf, tmp_path)


def test_safe_extract_disallowed_cronos_subdir_raises(tmp_path: Path):
    buf = _make_zip({
        "my-space/.cronos/space.yml": b"",
        "my-space/.cronos/workspaces/foo/bar.txt": b"",
    })
    with zipfile.ZipFile(buf) as zf:
        with pytest.raises(SpaceError, match="Disallowed"):
            _safe_extract(zf, tmp_path)


# ---------------------------------------------------------------------------
# POST /api/spaces/import
# ---------------------------------------------------------------------------


def _make_space_zip(space_id: str, yml: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{space_id}/.cronos/space.yml", yml)
    return buf.getvalue()


async def test_import_space_success(async_client):
    zip_bytes = _make_space_zip("imp-space", _VALID_SPACE_YML)
    resp = await async_client.post(
        "/api/spaces/import",
        files={"file": ("imp-space.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "imp-space"
    assert data["name"] == "Imported Space"


async def test_import_space_conflict_returns_409(async_client):
    zip_bytes = _make_space_zip("imp-space", _VALID_SPACE_YML)
    await async_client.post(
        "/api/spaces/import",
        files={"file": ("imp-space.zip", zip_bytes, "application/zip")},
    )
    resp = await async_client.post(
        "/api/spaces/import",
        files={"file": ("imp-space.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 409


async def test_import_space_not_a_zip_returns_400(async_client):
    resp = await async_client.post(
        "/api/spaces/import",
        files={"file": ("notazip.zip", b"not a zip", "application/zip")},
    )
    assert resp.status_code == 400


async def test_import_space_with_rename(async_client):
    zip_bytes = _make_space_zip("imp-space", _VALID_SPACE_YML)
    resp = await async_client.post(
        "/api/spaces/import?rename_to=renamed-space",
        files={"file": ("imp-space.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == "renamed-space"


# ---------------------------------------------------------------------------
# Imported-task sanitization (HIGH-005)
# ---------------------------------------------------------------------------


def _task_md(
    *,
    task_id: str,
    state: str,
    claude_session_id: str | None = None,
    pending_messages: list[str] | None = None,
    waiting_question: str | None = None,
) -> str:
    """Build a frontmatter task markdown document."""
    pending = pending_messages if pending_messages is not None else []
    # YAML emits None as `null`; quote strings.
    session_yaml = "null" if claude_session_id is None else f"'{claude_session_id}'"
    wait_yaml = "null" if waiting_question is None else f"'{waiting_question}'"
    pending_yaml = "[]" if not pending else (
        "\n" + "\n".join(f"- '{m}'" for m in pending)
    )
    if isinstance(pending_yaml, str) and pending_yaml.startswith("\n"):
        pending_block = f"pending_messages:{pending_yaml}"
    else:
        pending_block = f"pending_messages: {pending_yaml}"
    return (
        "---\n"
        "agent_mode: auto\n"
        "agent_model: default\n"
        f"claude_session_id: {session_yaml}\n"
        "created_at: '2024-01-01T00:00:00Z'\n"
        f"id: {task_id}\n"
        f"{pending_block}\n"
        "priority: 3\n"
        "manual_order: 0\n"
        "space_id: imp-space\n"
        f"state: {state}\n"
        f"title: Task {task_id}\n"
        "updated_at: '2024-01-01T00:00:00Z'\n"
        f"waiting_question: {wait_yaml}\n"
        "---\n\n"
        "# Brief\n\n"
        "Body brief.\n\n"
        "# History\n\n"
    )


def _make_space_zip_with_tasks(space_id: str, yml: str, tasks: dict[str, str]) -> bytes:
    """Build a zip with the given space.yml and a {filename: markdown} task map."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{space_id}/.cronos/space.yml", yml)
        for filename, content in tasks.items():
            zf.writestr(f"{space_id}/.cronos/tasks/{filename}", content)
    return buf.getvalue()


async def test_import_active_task_is_forced_to_backlog(async_client, space_store):
    """A ZIP containing a task with state=active must arrive as state=backlog."""
    task_md = _task_md(task_id="t-active", state="active")
    zip_bytes = _make_space_zip_with_tasks(
        "imp-space",
        _VALID_SPACE_YML,
        {"t-active.md": task_md},
    )
    resp = await async_client.post(
        "/api/spaces/import",
        files={"file": ("imp-space.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 201

    # Verify on disk: the task file in the final location is backlog.
    task_path = space_store.spaces_dir / "imp-space" / ".cronos" / "tasks" / "t-active.md"
    assert task_path.exists()
    task = parse_file(task_path, "imp-space")
    assert task.state == TaskState.BACKLOG
    assert task.claude_session_id is None


async def test_import_task_with_session_id_is_stripped(async_client, space_store):
    """A ZIP containing a task with a claude_session_id must arrive with it cleared."""
    task_md = _task_md(
        task_id="t-session",
        state="backlog",  # Even backlog tasks must lose their session id.
        claude_session_id="abc-123-def-session",
    )
    zip_bytes = _make_space_zip_with_tasks(
        "imp-space",
        _VALID_SPACE_YML,
        {"t-session.md": task_md},
    )
    resp = await async_client.post(
        "/api/spaces/import",
        files={"file": ("imp-space.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 201

    task_path = space_store.spaces_dir / "imp-space" / ".cronos" / "tasks" / "t-session.md"
    assert task_path.exists()
    task = parse_file(task_path, "imp-space")
    assert task.claude_session_id is None
    assert task.state == TaskState.BACKLOG


async def test_import_clean_backlog_task_is_unchanged(async_client, space_store, caplog):
    """A backlog task with no session id should import normally with no warnings."""
    import logging as _logging

    task_md = _task_md(
        task_id="t-clean",
        state="backlog",
        claude_session_id=None,
    )
    zip_bytes = _make_space_zip_with_tasks(
        "imp-space",
        _VALID_SPACE_YML,
        {"t-clean.md": task_md},
    )

    with caplog.at_level(_logging.WARNING, logger="app.api.spaces"):
        resp = await async_client.post(
            "/api/spaces/import",
            files={"file": ("imp-space.zip", zip_bytes, "application/zip")},
        )

    assert resp.status_code == 201

    task_path = space_store.spaces_dir / "imp-space" / ".cronos" / "tasks" / "t-clean.md"
    assert task_path.exists()
    task = parse_file(task_path, "imp-space")
    assert task.state == TaskState.BACKLOG
    assert task.claude_session_id is None

    # No sanitization warning was emitted for the clean task.
    sanitize_warnings = [
        r for r in caplog.records
        if r.levelno >= _logging.WARNING and "Sanitizing imported task" in r.getMessage()
    ]
    assert sanitize_warnings == []


async def test_import_waiting_task_with_question_and_pending_is_sanitized(
    async_client, space_store
):
    """waiting state + pending_messages + waiting_question must all be cleared."""
    task_md = _task_md(
        task_id="t-waiting",
        state="waiting",
        claude_session_id="sess-xyz",
        pending_messages=["please continue", "follow up"],
        waiting_question="What is the next step?",
    )
    zip_bytes = _make_space_zip_with_tasks(
        "imp-space",
        _VALID_SPACE_YML,
        {"t-waiting.md": task_md},
    )
    resp = await async_client.post(
        "/api/spaces/import",
        files={"file": ("imp-space.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 201

    task_path = (
        space_store.spaces_dir / "imp-space" / ".cronos" / "tasks" / "t-waiting.md"
    )
    assert task_path.exists()
    task = parse_file(task_path, "imp-space")
    assert task.state == TaskState.BACKLOG
    assert task.claude_session_id is None
    assert task.pending_messages == []
    assert task.waiting_question is None


# ---------------------------------------------------------------------------
# space_storage utility functions
# ---------------------------------------------------------------------------


def test_validate_color_valid():
    validate_color("#AABBCC")


def test_validate_color_invalid_raises():
    with pytest.raises(SpaceError, match="Invalid color"):
        validate_color("not-a-color")


def test_validate_color_wrong_format_raises():
    with pytest.raises(SpaceError, match="Invalid color"):
        validate_color("AABBCC")


def test_validate_space_id_valid():
    validate_space_id("my-space-123")


def test_validate_space_id_uppercase_raises():
    with pytest.raises(SpaceError, match="Invalid space id"):
        validate_space_id("My-Space")


def test_validate_space_id_too_short_raises():
    with pytest.raises(SpaceError, match="Invalid space id"):
        validate_space_id("")
