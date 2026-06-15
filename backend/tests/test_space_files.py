from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import SPACE_ID

WORKSPACE_NAME = "task-abc123"


def _make_workspace_file(tmp_spaces_dir: Path, rel: str, content: str = "hello") -> Path:
    target = tmp_spaces_dir / SPACE_ID / ".cronos" / "workspaces" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return target


# ---------------------------------------------------------------------------
# GET /api/spaces/{space_id}/files
# ---------------------------------------------------------------------------


async def test_list_space_files_happy_path(async_client, tmp_spaces_dir):
    _make_workspace_file(tmp_spaces_dir, f"{WORKSPACE_NAME}/report.md", "# Report")
    _make_workspace_file(tmp_spaces_dir, f"{WORKSPACE_NAME}/code.py", "print('hi')")

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/files")
    assert resp.status_code == 200
    entries = resp.json()
    assert isinstance(entries, list)
    paths = {e["path"] for e in entries}
    assert f"{WORKSPACE_NAME}/report.md" in paths
    assert f"{WORKSPACE_NAME}/code.py" in paths
    for e in entries:
        assert "name" in e
        assert "path" in e
        assert "size" in e
        assert "modified_at" in e
        assert "is_dir" in e
        assert "category" in e


async def test_list_space_files_paths_relative_to_workspaces_root(async_client, tmp_spaces_dir):
    _make_workspace_file(tmp_spaces_dir, f"{WORKSPACE_NAME}/notes.txt", "hi")

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/files")
    assert resp.status_code == 200
    entries = resp.json()
    for e in entries:
        # No absolute paths, no leading slash
        assert not e["path"].startswith("/")
        # Paths must start with workspace name, not with the spaces dir or space_id prefix
        assert e["path"].startswith(WORKSPACE_NAME) or e["is_dir"]


async def test_list_space_files_empty_workspaces_dir(async_client, tmp_spaces_dir):
    # Ensure workspaces dir exists but is empty
    ws_dir = tmp_spaces_dir / SPACE_ID / ".cronos" / "workspaces"
    ws_dir.mkdir(parents=True, exist_ok=True)

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/files")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_space_files_no_workspaces_dir(async_client):
    # No workspaces directory at all — returns empty list
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/files")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_space_files_unknown_space(async_client):
    resp = await async_client.get("/api/spaces/no-such-space/files")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/spaces/{space_id}/files/{file_path:path}
# ---------------------------------------------------------------------------


async def test_get_space_file_inline(async_client, tmp_spaces_dir):
    _make_workspace_file(tmp_spaces_dir, f"{WORKSPACE_NAME}/hello.txt", "world")

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/files/{WORKSPACE_NAME}/hello.txt")
    assert resp.status_code == 200
    assert resp.content == b"world"
    assert "attachment" not in resp.headers.get("content-disposition", "")


async def test_get_space_file_download_header(async_client, tmp_spaces_dir):
    _make_workspace_file(tmp_spaces_dir, f"{WORKSPACE_NAME}/data.csv", "a,b\n1,2")

    resp = await async_client.get(
        f"/api/spaces/{SPACE_ID}/files/{WORKSPACE_NAME}/data.csv",
        params={"download": "true"},
    )
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert "data.csv" in cd


async def test_get_space_file_not_found(async_client, tmp_spaces_dir):
    # Workspaces dir exists but the file does not
    ws_dir = tmp_spaces_dir / SPACE_ID / ".cronos" / "workspaces"
    ws_dir.mkdir(parents=True, exist_ok=True)

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/files/{WORKSPACE_NAME}/missing.txt")
    assert resp.status_code == 404


async def test_get_space_file_path_traversal_rejected(async_client, tmp_spaces_dir):
    # Ensure the workspaces directory exists so only the traversal is the rejection cause
    ws_dir = tmp_spaces_dir / SPACE_ID / ".cronos" / "workspaces"
    ws_dir.mkdir(parents=True, exist_ok=True)

    # Use percent-encoded ".." so httpx doesn't normalize the URL; FastAPI decodes it
    # and resolve_safe() must reject it with 400.
    resp = await async_client.get(
        f"/api/spaces/{SPACE_ID}/files/%2e%2e/%2e%2e/etc/passwd"
    )
    assert resp.status_code == 400
    body = resp.json()
    # Error must not leak real path details
    assert "passwd" not in body.get("detail", "").lower()


async def test_get_space_file_path_traversal_encoded(async_client, tmp_spaces_dir):
    ws_dir = tmp_spaces_dir / SPACE_ID / ".cronos" / "workspaces"
    ws_dir.mkdir(parents=True, exist_ok=True)

    # Fully percent-encoded traversal segments
    resp = await async_client.get(
        f"/api/spaces/{SPACE_ID}/files/%2e%2e%2fetc%2fpasswd"
    )
    # Either 400 (traversal) or 404 (file not found) — must not be 200
    assert resp.status_code in (400, 404)


async def test_get_space_file_unknown_space(async_client):
    resp = await async_client.get("/api/spaces/no-such-space/files/foo.txt")
    assert resp.status_code == 404


async def test_get_space_file_directory_rejected(async_client, tmp_spaces_dir):
    # Requesting a directory path (not a file) returns 404
    ws_dir = tmp_spaces_dir / SPACE_ID / ".cronos" / "workspaces" / WORKSPACE_NAME
    ws_dir.mkdir(parents=True, exist_ok=True)

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/files/{WORKSPACE_NAME}")
    assert resp.status_code == 404
