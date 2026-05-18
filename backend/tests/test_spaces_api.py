from __future__ import annotations

"""Additional spaces API tests covering link/unlink and export endpoints."""

import io
import zipfile
from pathlib import Path

import pytest

from app.api.spaces import _safe_extract
from app.space_storage import SpaceError, validate_color, validate_space_id

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
