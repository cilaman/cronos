from __future__ import annotations

import pytest

from app.models import TaskState

from .conftest import SPACE_ID


# ---------------------------------------------------------------------------
# GET /api/tasks
# ---------------------------------------------------------------------------


async def test_list_tasks_returns_board(async_client):
    resp = await async_client.get("/api/tasks")
    assert resp.status_code == 200
    board = resp.json()
    assert "backlog" in board
    assert "active" in board
    assert "waiting" in board
    assert "done" in board


async def test_list_tasks_empty_board(async_client):
    resp = await async_client.get("/api/tasks")
    board = resp.json()
    assert board["backlog"] == []


async def test_list_tasks_filters_by_space(async_client):
    # Create a task first
    await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Filter Test", "brief": ""},
    )
    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    assert resp.status_code == 200
    board = resp.json()
    assert len(board["backlog"]) == 1


async def test_list_tasks_unknown_space_returns_404(async_client):
    resp = await async_client.get("/api/tasks?space_id=no-such-space")
    assert resp.status_code == 404


async def test_list_tasks_all_space(async_client):
    await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "All Test", "brief": ""},
    )
    resp = await async_client.get("/api/tasks?space_id=all")
    assert resp.status_code == 200
    board = resp.json()
    assert len(board["backlog"]) >= 1


# ---------------------------------------------------------------------------
# POST /api/tasks
# ---------------------------------------------------------------------------


async def test_create_task_success(async_client):
    resp = await async_client.post(
        "/api/tasks",
        json={
            "space_id": SPACE_ID,
            "title": "New Task",
            "brief": "Do something important",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "New Task"
    assert data["brief"] == "Do something important"
    assert data["state"] == "backlog"
    assert data["space_id"] == SPACE_ID


async def test_create_task_assigns_id(async_client):
    resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "ID Check", "brief": ""},
    )
    assert resp.status_code == 201
    assert resp.json()["id"]


async def test_create_task_unknown_space_returns_404(async_client):
    resp = await async_client.post(
        "/api/tasks",
        json={"space_id": "no-such-space", "title": "T", "brief": ""},
    )
    assert resp.status_code == 404


async def test_create_task_missing_title_returns_422(async_client):
    resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "brief": "no title"},
    )
    assert resp.status_code == 422


async def test_create_task_with_agent_model(async_client):
    resp = await async_client.post(
        "/api/tasks",
        json={
            "space_id": SPACE_ID,
            "title": "Opus Task",
            "brief": "",
            "agent_model": "opus",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["agent_model"] == "opus"


async def test_create_task_with_agent_mode(async_client):
    resp = await async_client.post(
        "/api/tasks",
        json={
            "space_id": SPACE_ID,
            "title": "Plan Task",
            "brief": "",
            "agent_mode": "plan",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["agent_mode"] == "plan"


# ---------------------------------------------------------------------------
# GET /api/tasks/{id}
# ---------------------------------------------------------------------------


async def test_get_task_success(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Fetch Me", "brief": "some brief"},
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == task_id
    assert data["title"] == "Fetch Me"


async def test_get_task_not_found(async_client):
    resp = await async_client.get("/api/tasks/nonexistent-task-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/tasks/{id}
# ---------------------------------------------------------------------------


async def test_update_task_title(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Old Title", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.patch(
        f"/api/tasks/{task_id}", json={"title": "New Title"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"


async def test_update_task_brief(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "T", "brief": "Old brief"},
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.patch(
        f"/api/tasks/{task_id}", json={"brief": "New brief"}
    )
    assert resp.status_code == 200
    assert resp.json()["brief"] == "New brief"


async def test_update_task_no_fields_returns_400(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "T", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.patch(f"/api/tasks/{task_id}", json={})
    assert resp.status_code == 400


async def test_update_task_not_found_returns_404(async_client):
    resp = await async_client.patch(
        "/api/tasks/nonexistent", json={"title": "X"}
    )
    assert resp.status_code == 404


async def test_update_task_agent_mode(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Mode Task", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.patch(
        f"/api/tasks/{task_id}", json={"agent_mode": "ask"}
    )
    assert resp.status_code == 200
    assert resp.json()["agent_mode"] == "ask"


# ---------------------------------------------------------------------------
# PATCH /api/tasks/{id}/state
# ---------------------------------------------------------------------------


async def test_transition_task_to_active(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Start Me", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.patch(
        f"/api/tasks/{task_id}/state", json={"state": "active"}
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "active"


async def test_transition_task_invalid_returns_409(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "T", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    # BACKLOG -> DONE is not a valid user transition
    resp = await async_client.patch(
        f"/api/tasks/{task_id}/state", json={"state": "done"}
    )
    assert resp.status_code == 409


async def test_transition_task_not_found_returns_404(async_client):
    resp = await async_client.patch(
        "/api/tasks/nonexistent/state", json={"state": "active"}
    )
    assert resp.status_code == 404


async def test_transition_task_same_state_is_noop(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "T", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.patch(
        f"/api/tasks/{task_id}/state", json={"state": "backlog"}
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "backlog"


# ---------------------------------------------------------------------------
# DELETE /api/tasks/{id}
# ---------------------------------------------------------------------------


async def test_delete_task_success(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Delete Me", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.delete(f"/api/tasks/{task_id}")
    assert resp.status_code == 204


async def test_delete_task_removes_from_board(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Gone Soon", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    await async_client.delete(f"/api/tasks/{task_id}")

    board_resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    board = board_resp.json()
    ids = [t["id"] for t in board["backlog"]]
    assert task_id not in ids


async def test_delete_task_not_found_returns_404(async_client):
    resp = await async_client.delete("/api/tasks/nonexistent-task")
    assert resp.status_code == 404


async def test_delete_task_then_get_returns_404(async_client):
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "T", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    await async_client.delete(f"/api/tasks/{task_id}")

    get_resp = await async_client.get(f"/api/tasks/{task_id}")
    assert get_resp.status_code == 404
