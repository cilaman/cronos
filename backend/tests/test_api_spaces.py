from __future__ import annotations

import pytest

from .conftest import SPACE_ID


# ---------------------------------------------------------------------------
# GET /api/spaces
# ---------------------------------------------------------------------------


async def test_list_spaces_returns_response(async_client):
    resp = await async_client.get("/api/spaces")
    assert resp.status_code == 200
    data = resp.json()
    assert "spaces" in data
    assert "totals" in data


async def test_list_spaces_contains_seeded_space(async_client):
    resp = await async_client.get("/api/spaces")
    spaces = resp.json()["spaces"]
    ids = [s["id"] for s in spaces]
    assert SPACE_ID in ids


async def test_list_spaces_totals_structure(async_client):
    resp = await async_client.get("/api/spaces")
    totals = resp.json()["totals"]
    assert "backlog" in totals
    assert "active" in totals
    assert "done" in totals


async def test_list_spaces_task_counts_after_create(async_client):
    await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Count Me", "brief": ""},
    )
    resp = await async_client.get("/api/spaces")
    spaces = resp.json()["spaces"]
    space = next(s for s in spaces if s["id"] == SPACE_ID)
    assert space["task_counts"]["backlog"] == 1


# ---------------------------------------------------------------------------
# GET /api/spaces/{space_id}
# ---------------------------------------------------------------------------


async def test_get_space_success(async_client):
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == SPACE_ID
    assert data["name"] == "Test Space"


async def test_get_space_not_found(async_client):
    resp = await async_client.get("/api/spaces/no-such-space")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/spaces
# ---------------------------------------------------------------------------


async def test_create_space_success(async_client):
    resp = await async_client.post(
        "/api/spaces",
        json={"name": "New Space", "color": "#ABCDEF"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "New Space"
    assert data["color"] == "#ABCDEF"
    assert data["id"]


async def test_create_space_custom_id(async_client):
    resp = await async_client.post(
        "/api/spaces",
        json={"name": "Custom ID", "color": "#123456", "space_id": "my-custom-id"},
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == "my-custom-id"


async def test_create_space_duplicate_id_returns_409(async_client):
    await async_client.post(
        "/api/spaces",
        json={"name": "First", "color": "#000000", "space_id": "dup-space"},
    )
    resp = await async_client.post(
        "/api/spaces",
        json={"name": "Second", "color": "#111111", "space_id": "dup-space"},
    )
    assert resp.status_code == 409


async def test_create_space_invalid_color_returns_400(async_client):
    # Must be 7 chars to pass Pydantic length check; non-hex fails SpaceStore validation → 400
    resp = await async_client.post(
        "/api/spaces",
        json={"name": "X", "color": "#ZZZZZZ"},
    )
    assert resp.status_code == 400


async def test_create_space_missing_name_returns_422(async_client):
    resp = await async_client.post(
        "/api/spaces",
        json={"color": "#123456"},
    )
    assert resp.status_code == 422


async def test_create_space_repo_without_branch_returns_400(async_client):
    resp = await async_client.post(
        "/api/spaces",
        json={
            "name": "Repo Space",
            "color": "#123456",
            "repo_url": "https://github.com/example/repo",
        },
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PATCH /api/spaces/{space_id}
# ---------------------------------------------------------------------------


async def test_update_space_name(async_client):
    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}", json={"name": "Renamed"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


async def test_update_space_color(async_client):
    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}", json={"color": "#FF0000"}
    )
    assert resp.status_code == 200
    assert resp.json()["color"] == "#FF0000"


async def test_update_space_description(async_client):
    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}", json={"description": "Updated desc"}
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated desc"


async def test_update_space_no_fields_returns_400(async_client):
    resp = await async_client.patch(f"/api/spaces/{SPACE_ID}", json={})
    assert resp.status_code == 400


async def test_update_space_not_found_returns_404(async_client):
    resp = await async_client.patch(
        "/api/spaces/nonexistent", json={"name": "X"}
    )
    assert resp.status_code == 404


async def test_update_space_invalid_color_returns_400(async_client):
    # Must be 7 chars to pass Pydantic length check; non-hex fails handler → 400
    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}", json={"color": "#ZZZZZZ"}
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/spaces/{space_id}
# ---------------------------------------------------------------------------


async def test_delete_space_empty_success(async_client):
    # Create a second space so we don't orphan the fixture
    await async_client.post(
        "/api/spaces",
        json={"name": "Temp", "color": "#000000", "space_id": "temp-delete"},
    )
    resp = await async_client.delete("/api/spaces/temp-delete")
    assert resp.status_code == 204


async def test_delete_space_with_tasks_no_cascade_returns_409(async_client):
    # Create task in the test space
    await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Blocking Task", "brief": ""},
    )
    resp = await async_client.delete(f"/api/spaces/{SPACE_ID}")
    assert resp.status_code == 409


async def test_delete_space_with_tasks_cascade_succeeds(async_client):
    await async_client.post(
        "/api/spaces",
        json={"name": "Cascade Space", "color": "#000000", "space_id": "cascade-del"},
    )
    await async_client.post(
        "/api/tasks",
        json={"space_id": "cascade-del", "title": "Task", "brief": ""},
    )
    resp = await async_client.delete("/api/spaces/cascade-del?cascade=true")
    assert resp.status_code == 204


async def test_delete_space_not_found_returns_404(async_client):
    resp = await async_client.delete("/api/spaces/no-such-space")
    assert resp.status_code == 404


async def test_delete_space_then_get_returns_404(async_client):
    await async_client.post(
        "/api/spaces",
        json={"name": "Gone", "color": "#000000", "space_id": "gone-space"},
    )
    await async_client.delete("/api/spaces/gone-space")
    resp = await async_client.get("/api/spaces/gone-space")
    assert resp.status_code == 404
