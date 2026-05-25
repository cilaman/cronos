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


async def test_list_tasks_board_summary_includes_agent_mode(async_client):
    """Board summaries must surface agent_mode so the frontend can render
    the mode badge on cards without re-fetching the full task."""
    await async_client.post(
        "/api/tasks",
        json={
            "space_id": SPACE_ID,
            "title": "Plan Mode Task",
            "brief": "",
            "agent_mode": "plan",
        },
    )
    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    assert resp.status_code == 200
    board = resp.json()
    assert len(board["backlog"]) == 1
    assert board["backlog"][0]["agent_mode"] == "plan"


async def test_list_tasks_board_summary_defaults_agent_mode_to_auto(async_client):
    """Tasks created without agent_mode should appear in the board
    summary with agent_mode=='auto'."""
    await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Default Mode", "brief": ""},
    )
    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    board = resp.json()
    assert board["backlog"][0]["agent_mode"] == "auto"


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


# ---------------------------------------------------------------------------
# Hierarchy fields (type / parent_id / depends_on) over HTTP — arc-1 task 1
# ---------------------------------------------------------------------------


async def test_create_task_with_hierarchy_fields(async_client):
    """POST /api/tasks accepts and echoes type, parent_id, depends_on."""
    resp = await async_client.post(
        "/api/tasks",
        json={
            "space_id": SPACE_ID,
            "title": "Child Task",
            "brief": "",
            "type": "goal",
            "parent_id": "parent-1",
            "depends_on": ["dep-a", "dep-b"],
        },
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "goal"
    assert data["parent_id"] == "parent-1"
    assert data["depends_on"] == ["dep-a", "dep-b"]


async def test_create_task_defaults_hierarchy_fields(async_client):
    """Omitting the new fields yields type='task', parent_id=None, depends_on=[]."""
    resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Defaults", "brief": ""},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "task"
    assert data["parent_id"] is None
    assert data["depends_on"] == []


async def test_create_task_invalid_type_returns_422(async_client):
    """Pydantic Literal validation rejects unknown type values at the API edge."""
    resp = await async_client.post(
        "/api/tasks",
        json={
            "space_id": SPACE_ID,
            "title": "Bad",
            "brief": "",
            "type": "epic",
        },
    )

    assert resp.status_code == 422


async def test_update_task_hierarchy_fields(async_client):
    """PATCH /api/tasks/{id} updates type, parent_id, depends_on."""
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Will Mutate", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.patch(
        f"/api/tasks/{task_id}",
        json={
            "type": "issue",
            "parent_id": "new-parent",
            "depends_on": ["d1"],
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "issue"
    assert data["parent_id"] == "new-parent"
    assert data["depends_on"] == ["d1"]


async def test_update_task_only_type_succeeds(async_client):
    """Updating just `type` (no other fields) is allowed and persists."""
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Type Only", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.patch(
        f"/api/tasks/{task_id}", json={"type": "goal"}
    )

    assert resp.status_code == 200
    assert resp.json()["type"] == "goal"


async def test_update_task_only_depends_on_succeeds(async_client):
    """Updating just `depends_on` is a valid request — exercises the
    PATCH 'no fields' guard (it should NOT trigger when depends_on is set)."""
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Deps Only", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.patch(
        f"/api/tasks/{task_id}", json={"depends_on": ["x", "y"]}
    )

    assert resp.status_code == 200
    assert resp.json()["depends_on"] == ["x", "y"]


async def test_get_task_includes_hierarchy_fields(async_client):
    """GET /api/tasks/{id} round-trips the new fields through the read model."""
    create_resp = await async_client.post(
        "/api/tasks",
        json={
            "space_id": SPACE_ID,
            "title": "Fetch Hier",
            "brief": "",
            "type": "issue",
            "parent_id": "p",
            "depends_on": ["a"],
        },
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.get(f"/api/tasks/{task_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "issue"
    assert data["parent_id"] == "p"
    assert data["depends_on"] == ["a"]


async def test_board_summary_includes_type_and_parent_id(async_client):
    """Board card summaries expose type + parent_id (depends_on is intentionally NOT on summary)."""
    await async_client.post(
        "/api/tasks",
        json={
            "space_id": SPACE_ID,
            "title": "Goal On Board",
            "brief": "",
            "type": "goal",
            "parent_id": "root",
        },
    )

    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")

    assert resp.status_code == 200
    summary = resp.json()["backlog"][0]
    assert summary["type"] == "goal"
    assert summary["parent_id"] == "root"


async def test_update_task_invalid_type_returns_422(async_client):
    """PATCH with an unknown type is rejected at the Pydantic boundary."""
    create_resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "T", "brief": ""},
    )
    task_id = create_resp.json()["id"]

    resp = await async_client.patch(
        f"/api/tasks/{task_id}", json={"type": "epic"}
    )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Dependency / child gating over HTTP — arc-1 task 3
# ---------------------------------------------------------------------------


async def _create(async_client, **fields) -> dict:
    """Helper: POST a task and return the response body, asserting 201."""
    payload = {"space_id": SPACE_ID, "title": "T", "brief": "", **fields}
    resp = await async_client.post("/api/tasks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---- POST /api/tasks/{id}/start ----


async def test_start_task_blocked_by_unmet_dependencies_returns_409(async_client):
    """POST /start must refuse to start a task whose deps are still open."""
    dep = await _create(async_client, title="Dep")
    blocked = await _create(async_client, title="Blocked", depends_on=[dep["id"]])

    resp = await async_client.post(f"/api/tasks/{blocked['id']}/start")

    assert resp.status_code == 409
    body = resp.json()
    # Error message must surface the offending dep id so the UI can render it.
    detail = body.get("detail", "")
    assert "unmet dependencies" in detail
    assert dep["id"] in detail

    # Task must remain in backlog — no side effect from a refused start.
    get_resp = await async_client.get(f"/api/tasks/{blocked['id']}")
    assert get_resp.json()["state"] == "backlog"


async def test_start_task_succeeds_after_dependency_moved_to_done(async_client, task_store):
    """Once all blockers reach `done`, POST /start returns 200 and activates."""
    from app.storage import USER_TRANSITIONS as _UT, WORKER_TRANSITIONS as _WT

    dep = await _create(async_client, title="Dep")
    blocked = await _create(async_client, title="Will Run", depends_on=[dep["id"]])

    # Drive dep to done via the storage layer (active->done is worker-only).
    await task_store.transition(dep["id"], TaskState.ACTIVE, allowed=_UT)
    await task_store.transition(dep["id"], TaskState.DONE, allowed=_WT)

    resp = await async_client.post(f"/api/tasks/{blocked['id']}/start")

    assert resp.status_code == 200
    assert resp.json()["state"] == "active"


async def test_start_task_succeeds_with_no_dependencies(async_client):
    """Happy path: a task with depends_on=[] starts cleanly."""
    task = await _create(async_client, title="Simple")

    resp = await async_client.post(f"/api/tasks/{task['id']}/start")

    assert resp.status_code == 200
    assert resp.json()["state"] == "active"


async def test_start_task_succeeds_when_dep_is_archived(async_client, task_store):
    """An archived dep is terminal and must not block start."""
    from app.storage import USER_TRANSITIONS as _UT, WORKER_TRANSITIONS as _WT

    dep = await _create(async_client, title="Dep")
    blocked = await _create(async_client, title="Will Run", depends_on=[dep["id"]])

    await task_store.transition(dep["id"], TaskState.ACTIVE, allowed=_UT)
    await task_store.transition(dep["id"], TaskState.DONE, allowed=_WT)
    await task_store.transition(dep["id"], TaskState.ARCHIVED, allowed=_UT)

    resp = await async_client.post(f"/api/tasks/{blocked['id']}/start")

    assert resp.status_code == 200
    assert resp.json()["state"] == "active"


async def test_start_task_not_found_returns_404(async_client):
    """Unknown task id under /start is a 404, not a 409."""
    resp = await async_client.post("/api/tasks/no-such-task/start")
    assert resp.status_code == 404


async def test_start_task_already_active_returns_409(async_client):
    """Only backlog tasks can be started — calling /start twice is rejected."""
    task = await _create(async_client, title="Started")
    first = await async_client.post(f"/api/tasks/{task['id']}/start")
    assert first.status_code == 200

    second = await async_client.post(f"/api/tasks/{task['id']}/start")
    assert second.status_code == 409


# ---- PATCH /api/tasks/{id}/state -> done on a goal ----


async def test_state_done_on_goal_blocked_by_open_children_returns_409(
    async_client, task_store
):
    """PATCH /state {"state":"done"} on a goal with open children -> 409.

    The goal must be in WAITING for the user transition to DONE to be legal
    (USER_TRANSITIONS allows waiting->done but not active->done). We force
    the state through the storage layer to reach the gate.
    """
    from app.models import Task as TaskModel
    from datetime import datetime as _dt, timezone as _tz

    goal = await _create(async_client, title="Goal", type="goal")
    child = await _create(async_client, title="Child", parent_id=goal["id"])

    # Force-set the goal to WAITING so the user can attempt waiting -> done.
    # Bypass the state-machine to set up the test scenario.
    stored = task_store.get(goal["id"])
    task_store._by_id[goal["id"]] = stored.model_copy(
        update={"state": TaskState.WAITING, "updated_at": _dt.now(tz=_tz.utc)}
    )

    resp = await async_client.patch(
        f"/api/tasks/{goal['id']}/state", json={"state": "done"}
    )

    assert resp.status_code == 409
    detail = resp.json().get("detail", "")
    assert "open children" in detail
    assert child["id"] in detail
    # Goal stays in waiting.
    assert task_store.get(goal["id"]).state == TaskState.WAITING


async def test_state_done_on_goal_allowed_after_children_done(
    async_client, task_store
):
    """Once every child reaches done, the user can close the goal via /state."""
    from app.storage import USER_TRANSITIONS as _UT, WORKER_TRANSITIONS as _WT
    from datetime import datetime as _dt, timezone as _tz

    goal = await _create(async_client, title="Goal", type="goal")
    child = await _create(async_client, title="Child", parent_id=goal["id"])

    # Walk child to done.
    await task_store.transition(child["id"], TaskState.ACTIVE, allowed=_UT)
    await task_store.transition(child["id"], TaskState.DONE, allowed=_WT)

    # Force-set goal to WAITING so the user transition to DONE is legal.
    stored = task_store.get(goal["id"])
    task_store._by_id[goal["id"]] = stored.model_copy(
        update={"state": TaskState.WAITING, "updated_at": _dt.now(tz=_tz.utc)}
    )

    resp = await async_client.patch(
        f"/api/tasks/{goal['id']}/state", json={"state": "done"}
    )

    assert resp.status_code == 200
    assert resp.json()["state"] == "done"


async def test_state_done_on_non_goal_not_blocked_by_open_children(
    async_client, task_store
):
    """A regular task (type='task') with open children is NOT a goal — gate must
    not fire. This guards against a future regression that widens the gate
    to all parents.
    """
    from datetime import datetime as _dt, timezone as _tz

    parent = await _create(async_client, title="Parent Task", type="task")
    await _create(async_client, title="Child", parent_id=parent["id"])

    # Force-set parent to WAITING so the user-DONE transition is legal.
    stored = task_store.get(parent["id"])
    task_store._by_id[parent["id"]] = stored.model_copy(
        update={"state": TaskState.WAITING, "updated_at": _dt.now(tz=_tz.utc)}
    )

    resp = await async_client.patch(
        f"/api/tasks/{parent['id']}/state", json={"state": "done"}
    )

    assert resp.status_code == 200
    assert resp.json()["state"] == "done"


# ---- TaskRead.unmet_dependencies ----


async def test_get_task_unmet_dependencies_empty_for_no_deps(async_client):
    """The DTO carries an empty list when the task has no deps at all."""
    task = await _create(async_client, title="Lonely")

    resp = await async_client.get(f"/api/tasks/{task['id']}")

    assert resp.status_code == 200
    assert resp.json()["unmet_dependencies"] == []


async def test_get_task_unmet_dependencies_lists_open_blockers(async_client):
    """When deps are open, the DTO surfaces them in `unmet_dependencies`."""
    d1 = await _create(async_client, title="D1")
    d2 = await _create(async_client, title="D2")
    blocked = await _create(
        async_client, title="Blocked", depends_on=[d1["id"], d2["id"]]
    )

    resp = await async_client.get(f"/api/tasks/{blocked['id']}")

    assert resp.status_code == 200
    body = resp.json()
    # Both deps are still backlog -> both blocking.
    assert set(body["unmet_dependencies"]) == {d1["id"], d2["id"]}


async def test_get_task_unmet_dependencies_empty_once_deps_done(async_client, task_store):
    """The DTO's `unmet_dependencies` shrinks as deps move to terminal."""
    from app.storage import USER_TRANSITIONS as _UT, WORKER_TRANSITIONS as _WT

    dep = await _create(async_client, title="Dep")
    blocked = await _create(async_client, title="B", depends_on=[dep["id"]])

    # Initially blocked.
    initial = await async_client.get(f"/api/tasks/{blocked['id']}")
    assert initial.json()["unmet_dependencies"] == [dep["id"]]

    # Move dep to done.
    await task_store.transition(dep["id"], TaskState.ACTIVE, allowed=_UT)
    await task_store.transition(dep["id"], TaskState.DONE, allowed=_WT)

    final = await async_client.get(f"/api/tasks/{blocked['id']}")
    assert final.json()["unmet_dependencies"] == []


async def test_get_task_unmet_dependencies_reports_missing_dep_id(async_client):
    """A dangling dep id (target never existed) is reported as unmet.

    Echoes the storage-layer contract — defensive against silent skips when
    a dependency was deleted out from under a task.
    """
    blocked = await _create(async_client, title="Dangling", depends_on=["ghost-id"])

    resp = await async_client.get(f"/api/tasks/{blocked['id']}")

    assert resp.status_code == 200
    assert resp.json()["unmet_dependencies"] == ["ghost-id"]


async def test_create_task_response_includes_unmet_dependencies(async_client):
    """POST /api/tasks response also carries unmet_dependencies (TaskRead shape)."""
    dep = await _create(async_client, title="Dep")
    resp = await async_client.post(
        "/api/tasks",
        json={
            "space_id": SPACE_ID,
            "title": "WithDeps",
            "brief": "",
            "depends_on": [dep["id"]],
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["unmet_dependencies"] == [dep["id"]]


async def test_start_response_includes_unmet_dependencies(async_client):
    """POST /start success response also surfaces unmet_dependencies (empty when
    the task could start — i.e. all deps were satisfied)."""
    task = await _create(async_client, title="SoloStart")

    resp = await async_client.post(f"/api/tasks/{task['id']}/start")

    assert resp.status_code == 200
    body = resp.json()
    # The field must be present on the TaskRead shape regardless of whether
    # any blockers existed. A successful start implies an empty list.
    assert "unmet_dependencies" in body
    assert body["unmet_dependencies"] == []


async def test_patch_state_response_includes_unmet_dependencies(async_client, task_store):
    """PATCH /state response carries unmet_dependencies (TaskRead shape).

    Regression guard: every endpoint returning TaskRead must include the new
    field. PATCH /state previously called _build_task_read without `store=`,
    which would have returned an empty list even when blockers existed.
    """
    from app.storage import USER_TRANSITIONS as _UT, WORKER_TRANSITIONS as _WT

    dep = await _create(async_client, title="Dep")
    # Drive the dep to done so the gate doesn't block our subject transition.
    await task_store.transition(dep["id"], TaskState.ACTIVE, allowed=_UT)
    await task_store.transition(dep["id"], TaskState.DONE, allowed=_WT)

    task = await _create(async_client, title="HasDoneDep", depends_on=[dep["id"]])

    resp = await async_client.patch(
        f"/api/tasks/{task['id']}/state", json={"state": "active"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "unmet_dependencies" in body
    assert body["unmet_dependencies"] == []


async def test_patch_task_response_includes_unmet_dependencies(async_client):
    """PATCH /api/tasks/{id} (field updates) response carries unmet_dependencies.

    Regression: a previous version of `_build_task_read` would have returned
    an empty list here even with open blockers. Asserts the store wiring on
    this code path.
    """
    dep = await _create(async_client, title="StillOpen")
    blocked = await _create(async_client, title="BlockedX")

    # Update the blocked task to add a dep that's still in backlog.
    resp = await async_client.patch(
        f"/api/tasks/{blocked['id']}", json={"depends_on": [dep["id"]]}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["unmet_dependencies"] == [dep["id"]]


async def test_reply_response_includes_unmet_dependencies(async_client, task_store):
    """POST /api/tasks/{id}/reply response carries unmet_dependencies.

    The reply succeeds (active task), and the resulting TaskRead must include
    an `unmet_dependencies` list. With no deps on the reply target, the list
    is empty — but its presence is the assertion.
    """
    task = await _create(async_client, title="ActiveReplyTarget")
    # Drive it active so the reply path takes the ACTIVE branch (append to
    # pending_messages, no transition involved — so the dep gate doesn't fire).
    await async_client.post(f"/api/tasks/{task['id']}/start")

    resp = await async_client.post(
        f"/api/tasks/{task['id']}/reply", json={"message": "ping"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "unmet_dependencies" in body
    assert body["unmet_dependencies"] == []


# ---------------------------------------------------------------------------
# GET /api/tasks/{id}/tree — arc-1 task 4
# ---------------------------------------------------------------------------


async def test_get_tree_returns_root_only_for_leaf(async_client):
    """A leaf task with no children returns a single-element list (just itself)."""
    task = await _create(async_client, title="Leaf")

    resp = await async_client.get(f"/api/tasks/{task['id']}/tree")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == task["id"]


async def test_get_tree_returns_root_with_direct_children(async_client):
    """Acceptance #1: promote a task, set parent on two others, GET /tree
    returns the goal plus both children.

    Drives the whole flow through the API (no direct store access) — verifies
    that promote, /parent, and /tree compose correctly.
    """
    goal = await _create(async_client, title="Goal")
    child_a = await _create(async_client, title="Child A")
    child_b = await _create(async_client, title="Child B")

    # 1) Promote the goal via the API.
    promote_resp = await async_client.post(f"/api/tasks/{goal['id']}/promote")
    assert promote_resp.status_code == 200
    assert promote_resp.json()["type"] == "goal"

    # 2) Set parent on each child via the API.
    p1 = await async_client.patch(
        f"/api/tasks/{child_a['id']}/parent", json={"parent_id": goal["id"]}
    )
    p2 = await async_client.patch(
        f"/api/tasks/{child_b['id']}/parent", json={"parent_id": goal["id"]}
    )
    assert p1.status_code == 200 and p2.status_code == 200

    # 3) GET /tree returns the goal + both children.
    resp = await async_client.get(f"/api/tasks/{goal['id']}/tree")

    assert resp.status_code == 200
    body = resp.json()
    ids = [t["id"] for t in body]
    assert ids[0] == goal["id"]  # BFS: root first
    assert set(ids) == {goal["id"], child_a["id"], child_b["id"]}


async def test_get_tree_includes_grandchildren_bfs(async_client):
    """The /tree endpoint walks multiple levels (BFS) — verifies recursion."""
    root = await _create(async_client, title="Root", type="goal")
    child = await _create(async_client, title="Child", parent_id=root["id"])
    grand = await _create(async_client, title="Grand", parent_id=child["id"])

    resp = await async_client.get(f"/api/tasks/{root['id']}/tree")

    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()]
    assert set(ids) == {root["id"], child["id"], grand["id"]}
    # BFS: child appears before its grandchild.
    assert ids.index(child["id"]) < ids.index(grand["id"])


async def test_get_tree_not_found_returns_404(async_client):
    """Unknown root id -> 404 (not an empty list)."""
    resp = await async_client.get("/api/tasks/no-such-id/tree")

    assert resp.status_code == 404


async def test_get_tree_excludes_unrelated_tasks(async_client):
    """Tasks in the same space that are NOT descendants must not leak in."""
    root = await _create(async_client, title="Root", type="goal")
    await _create(async_client, title="Child", parent_id=root["id"])
    unrelated = await _create(async_client, title="Unrelated")

    resp = await async_client.get(f"/api/tasks/{root['id']}/tree")

    ids = {t["id"] for t in resp.json()}
    assert unrelated["id"] not in ids


async def test_get_tree_responses_carry_unmet_dependencies(async_client):
    """Each TaskRead in /tree carries the unmet_dependencies field (DTO shape)."""
    dep = await _create(async_client, title="OpenDep")
    root = await _create(async_client, title="Root", type="goal", depends_on=[dep["id"]])

    resp = await async_client.get(f"/api/tasks/{root['id']}/tree")

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["unmet_dependencies"] == [dep["id"]]


# ---------------------------------------------------------------------------
# POST /api/tasks/{id}/promote — arc-1 task 4
# ---------------------------------------------------------------------------


async def test_promote_flips_type_to_goal(async_client):
    """POST /promote turns a task into a goal."""
    task = await _create(async_client, title="To Promote")
    assert task["type"] == "task"

    resp = await async_client.post(f"/api/tasks/{task['id']}/promote")

    assert resp.status_code == 200
    assert resp.json()["type"] == "goal"


async def test_promote_is_idempotent(async_client):
    """Promoting an already-goal returns 200 with type='goal' (no error)."""
    goal = await _create(async_client, title="Already Goal", type="goal")

    resp = await async_client.post(f"/api/tasks/{goal['id']}/promote")

    assert resp.status_code == 200
    assert resp.json()["type"] == "goal"


async def test_promote_not_found_returns_404(async_client):
    """Unknown id -> 404 (not 500)."""
    resp = await async_client.post("/api/tasks/no-such/promote")

    assert resp.status_code == 404


async def test_promote_persists_for_subsequent_get(async_client):
    """A follow-up GET sees the new type — proof the change was persisted."""
    task = await _create(async_client, title="P")
    await async_client.post(f"/api/tasks/{task['id']}/promote")

    resp = await async_client.get(f"/api/tasks/{task['id']}")

    assert resp.json()["type"] == "goal"


async def test_promote_response_includes_unmet_dependencies(async_client):
    """The TaskRead response carries unmet_dependencies (DTO contract)."""
    dep = await _create(async_client, title="Dep")
    task = await _create(async_client, title="Pendant", depends_on=[dep["id"]])

    resp = await async_client.post(f"/api/tasks/{task['id']}/promote")

    assert resp.status_code == 200
    body = resp.json()
    assert "unmet_dependencies" in body
    assert body["unmet_dependencies"] == [dep["id"]]


# ---------------------------------------------------------------------------
# PATCH /api/tasks/{id}/parent — arc-1 task 4
# ---------------------------------------------------------------------------


async def test_set_parent_assigns_parent_id(async_client):
    """PATCH /parent sets parent_id and the change is reflected in the response."""
    parent = await _create(async_client, title="Parent", type="goal")
    child = await _create(async_client, title="Child")

    resp = await async_client.patch(
        f"/api/tasks/{child['id']}/parent", json={"parent_id": parent["id"]}
    )

    assert resp.status_code == 200
    assert resp.json()["parent_id"] == parent["id"]


async def test_set_parent_clear_with_null_persists(async_client):
    """Acceptance #3: removing a parent (parent_id=null) works and persists."""
    parent = await _create(async_client, title="Parent", type="goal")
    child = await _create(async_client, title="Child", parent_id=parent["id"])
    assert child["parent_id"] == parent["id"]

    # Clear it via the API.
    clear_resp = await async_client.patch(
        f"/api/tasks/{child['id']}/parent", json={"parent_id": None}
    )
    assert clear_resp.status_code == 200
    assert clear_resp.json()["parent_id"] is None

    # Persisted — a subsequent GET sees None as well.
    get_resp = await async_client.get(f"/api/tasks/{child['id']}")
    assert get_resp.json()["parent_id"] is None


async def test_set_parent_self_reference_returns_409(async_client):
    """A task cannot become its own parent (CycleError -> 409)."""
    task = await _create(async_client, title="T")

    resp = await async_client.patch(
        f"/api/tasks/{task['id']}/parent", json={"parent_id": task["id"]}
    )

    assert resp.status_code == 409
    # Message must reference the cycle for UX.
    assert task["id"] in resp.json().get("detail", "")


async def test_set_parent_creates_cycle_returns_409(async_client):
    """Setting A.parent=B when B already chains to A returns 409 with detail."""
    a = await _create(async_client, title="A", type="goal")
    b = await _create(async_client, title="B", type="goal", parent_id=a["id"])

    resp = await async_client.patch(
        f"/api/tasks/{a['id']}/parent", json={"parent_id": b["id"]}
    )

    assert resp.status_code == 409
    assert "detail" in resp.json()


async def test_set_parent_unknown_task_returns_404(async_client):
    """Unknown subject id -> 404 (not 409)."""
    resp = await async_client.patch(
        "/api/tasks/no-such-task/parent", json={"parent_id": None}
    )

    assert resp.status_code == 404


async def test_set_parent_unknown_parent_returns_409(async_client):
    """Pointing at a parent id that doesn't exist is a 409 (not 404 of the task)."""
    task = await _create(async_client, title="T")

    resp = await async_client.patch(
        f"/api/tasks/{task['id']}/parent", json={"parent_id": "ghost-parent"}
    )

    assert resp.status_code == 409


async def test_set_parent_missing_body_field_returns_422(async_client):
    """ParentBody requires parent_id (string|None) — omitting it -> 422."""
    task = await _create(async_client, title="T")

    resp = await async_client.patch(f"/api/tasks/{task['id']}/parent", json={})

    assert resp.status_code == 422


async def test_set_parent_response_includes_unmet_dependencies(async_client):
    """TaskRead DTO shape: unmet_dependencies present on /parent response."""
    parent = await _create(async_client, title="P", type="goal")
    dep = await _create(async_client, title="D")
    child = await _create(async_client, title="C", depends_on=[dep["id"]])

    resp = await async_client.patch(
        f"/api/tasks/{child['id']}/parent", json={"parent_id": parent["id"]}
    )

    assert resp.status_code == 200
    assert resp.json()["unmet_dependencies"] == [dep["id"]]


# ---------------------------------------------------------------------------
# PATCH /api/tasks/{id}/depends_on — arc-1 task 4
# ---------------------------------------------------------------------------


async def test_set_depends_on_assigns_list(async_client):
    """PATCH /depends_on sets the list and the change is reflected immediately."""
    d1 = await _create(async_client, title="D1")
    d2 = await _create(async_client, title="D2")
    task = await _create(async_client, title="T")

    resp = await async_client.patch(
        f"/api/tasks/{task['id']}/depends_on",
        json={"depends_on": [d1["id"], d2["id"]]},
    )

    assert resp.status_code == 200
    assert resp.json()["depends_on"] == [d1["id"], d2["id"]]


async def test_set_depends_on_empty_list_clears(async_client):
    """Passing depends_on=[] clears the existing list."""
    d = await _create(async_client, title="D")
    task = await _create(async_client, title="T", depends_on=[d["id"]])

    resp = await async_client.patch(
        f"/api/tasks/{task['id']}/depends_on", json={"depends_on": []}
    )

    assert resp.status_code == 200
    assert resp.json()["depends_on"] == []


async def test_set_depends_on_self_reference_returns_409(async_client):
    """Acceptance #2: a self-cycle on depends_on returns 409 with detail."""
    task = await _create(async_client, title="T")

    resp = await async_client.patch(
        f"/api/tasks/{task['id']}/depends_on",
        json={"depends_on": [task["id"]]},
    )

    assert resp.status_code == 409
    detail = resp.json().get("detail", "")
    assert task["id"] in detail


async def test_set_depends_on_cycle_returns_409(async_client):
    """Acceptance #2: a transitive cycle on depends_on returns 409 with detail."""
    a = await _create(async_client, title="A")
    b = await _create(async_client, title="B", depends_on=[a["id"]])

    # B->A already exists; setting A->B would form a cycle.
    resp = await async_client.patch(
        f"/api/tasks/{a['id']}/depends_on", json={"depends_on": [b["id"]]}
    )

    assert resp.status_code == 409
    # Detail should describe the cycle (-> arrows show the chain).
    assert "detail" in resp.json()


async def test_set_depends_on_unknown_dep_returns_409(async_client):
    """A dep id that doesn't resolve to an existing task -> 409."""
    task = await _create(async_client, title="T")

    resp = await async_client.patch(
        f"/api/tasks/{task['id']}/depends_on",
        json={"depends_on": ["no-such-dep"]},
    )

    assert resp.status_code == 409


async def test_set_depends_on_unknown_task_returns_404(async_client):
    """Subject task must exist."""
    resp = await async_client.patch(
        "/api/tasks/no-such-task/depends_on", json={"depends_on": []}
    )

    assert resp.status_code == 404


async def test_set_depends_on_missing_body_field_uses_default_empty(async_client):
    """DependsOnBody.depends_on defaults to [] — omitting it succeeds as a clear."""
    d = await _create(async_client, title="D")
    task = await _create(async_client, title="T", depends_on=[d["id"]])

    resp = await async_client.patch(f"/api/tasks/{task['id']}/depends_on", json={})

    assert resp.status_code == 200
    assert resp.json()["depends_on"] == []


async def test_set_depends_on_response_includes_unmet_dependencies(async_client):
    """The TaskRead response surfaces unmet_dependencies for the new dep list."""
    d = await _create(async_client, title="StillOpen")
    task = await _create(async_client, title="T")

    resp = await async_client.patch(
        f"/api/tasks/{task['id']}/depends_on", json={"depends_on": [d["id"]]}
    )

    assert resp.status_code == 200
    body = resp.json()
    # Dep is in BACKLOG (non-terminal) -> still unmet.
    assert body["unmet_dependencies"] == [d["id"]]


# ---------------------------------------------------------------------------
# Board DTO — acceptance #4: depends_on + unmet_dependencies on summary
# ---------------------------------------------------------------------------


async def test_board_summary_includes_depends_on(async_client):
    """Acceptance #4 (a): board() summaries echo the task's depends_on."""
    d = await _create(async_client, title="Dep")
    await _create(async_client, title="HasDep", depends_on=[d["id"]])

    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")

    assert resp.status_code == 200
    summaries = resp.json()["backlog"]
    has_dep = next(s for s in summaries if s["title"] == "HasDep")
    assert has_dep["depends_on"] == [d["id"]]


async def test_board_summary_includes_unmet_dependencies(async_client):
    """Acceptance #4 (b): board summary has unmet_dependencies populated."""
    d = await _create(async_client, title="OpenDep")
    blocked = await _create(async_client, title="Blocked", depends_on=[d["id"]])

    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")

    summaries = resp.json()["backlog"]
    summary = next(s for s in summaries if s["id"] == blocked["id"])
    assert summary["unmet_dependencies"] == [d["id"]]


async def test_board_summary_unmet_dependencies_empty_when_no_deps(async_client):
    """A task with no depends_on must have unmet_dependencies=[] on summary."""
    task = await _create(async_client, title="Lonely")

    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")

    summary = next(s for s in resp.json()["backlog"] if s["id"] == task["id"])
    assert summary["unmet_dependencies"] == []
    assert summary["depends_on"] == []


async def test_board_summary_unmet_dependencies_drops_done_deps(
    async_client, task_store
):
    """Once a dep transitions to done, the board summary unmet_deps shrinks."""
    from app.storage import USER_TRANSITIONS as _UT, WORKER_TRANSITIONS as _WT

    dep = await _create(async_client, title="Dep")
    blocked = await _create(async_client, title="B", depends_on=[dep["id"]])

    # Initially blocked.
    initial = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    initial_summary = next(
        s for s in initial.json()["backlog"] if s["id"] == blocked["id"]
    )
    assert initial_summary["unmet_dependencies"] == [dep["id"]]

    # Drive dep to done via storage.
    await task_store.transition(dep["id"], TaskState.ACTIVE, allowed=_UT)
    await task_store.transition(dep["id"], TaskState.DONE, allowed=_WT)

    final = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    # The dep moved to the done lane; the blocked task is still in backlog.
    blocked_summary = next(
        s for s in final.json()["backlog"] if s["id"] == blocked["id"]
    )
    assert blocked_summary["unmet_dependencies"] == []
    assert blocked_summary["depends_on"] == [dep["id"]]


async def test_list_archived_summary_includes_unmet_dependencies(
    async_client, task_store
):
    """The /archived endpoint now includes unmet_dependencies in each summary.

    Setup walks the task to ARCHIVED with no deps, then retroactively adds an
    open dep via the API to exercise the summary's unmet_dependencies field
    on an archived row.
    """
    from app.storage import USER_TRANSITIONS as _UT, WORKER_TRANSITIONS as _WT

    dep = await _create(async_client, title="DepStillOpen")
    archived = await _create(async_client, title="ToArchive")

    # Walk archived task to ARCHIVED (no deps yet so the gate doesn't fire).
    await task_store.transition(archived["id"], TaskState.ACTIVE, allowed=_UT)
    await task_store.transition(archived["id"], TaskState.DONE, allowed=_WT)
    await task_store.transition(archived["id"], TaskState.ARCHIVED, allowed=_UT)

    # Retroactively add an open dep via the new PATCH /depends_on endpoint.
    set_resp = await async_client.patch(
        f"/api/tasks/{archived['id']}/depends_on",
        json={"depends_on": [dep["id"]]},
    )
    assert set_resp.status_code == 200

    resp = await async_client.get(f"/api/tasks/archived?space_id={SPACE_ID}")

    assert resp.status_code == 200
    summaries = resp.json()
    target = next(s for s in summaries if s["id"] == archived["id"])
    # Dep is still in BACKLOG -> unmet from this archived task's POV.
    assert target["unmet_dependencies"] == [dep["id"]]
    assert target["depends_on"] == [dep["id"]]


# ---------------------------------------------------------------------------
# _enrich_summary — denormalized space fields (arc-4/5)
# ---------------------------------------------------------------------------


async def test_board_summary_includes_space_autopilot_disabled_by_default(async_client):
    """Tasks in a freshly created space surface space_autopilot='disabled'.

    The frontend Card uses this field to render the AUTO pill. If the API
    forgot to set it the pill would never appear, even when autopilot is on.
    """
    await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "AutopilotDefault", "brief": ""},
    )
    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    board = resp.json()
    assert board["backlog"][0]["space_autopilot"] == "disabled"


async def test_board_summary_reflects_space_autopilot_enabled(async_client):
    """After PATCHing autopilot=enabled, tasks in that space carry the new value."""
    # Create a task and then flip the space autopilot.
    await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "AutoEnabled", "brief": ""},
    )
    patch = await async_client.patch(
        f"/api/spaces/{SPACE_ID}", json={"autopilot": "enabled"}
    )
    assert patch.status_code == 200

    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    board = resp.json()
    assert len(board["backlog"]) == 1
    assert board["backlog"][0]["space_autopilot"] == "enabled"


async def test_board_summary_reflects_space_autopilot_paused(async_client):
    """Card's AUTO pill must NOT light up on 'paused' — verify the API field flows."""
    await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "PausedTask", "brief": ""},
    )
    await async_client.patch(
        f"/api/spaces/{SPACE_ID}", json={"autopilot": "paused"}
    )

    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    board = resp.json()
    assert board["backlog"][0]["space_autopilot"] == "paused"


async def test_board_summary_includes_pr_url_when_set(async_client, task_store):
    """A DONE task with pr_url surfaces it on the board summary so the
    Card can render the GitPullRequest icon link without a Detail fetch.
    """
    create = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "PR set", "brief": ""},
    )
    task_id = create.json()["id"]
    await task_store.set_pr_refs(
        task_id,
        pr_url="https://github.com/owner/repo/pull/77",
        proposed_pr_path=None,
    )

    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    board = resp.json()
    matches = [t for t in board["backlog"] if t["id"] == task_id]
    assert len(matches) == 1
    assert matches[0]["pr_url"] == "https://github.com/owner/repo/pull/77"
    assert matches[0]["proposed_pr_path"] is None


async def test_board_summary_includes_proposed_pr_path_when_set(async_client, task_store):
    """A task with proposed_pr_path (no GitHub remote) surfaces the path so
    the Card can render the FileText copy-path button.
    """
    create = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Proposed PR", "brief": ""},
    )
    task_id = create.json()["id"]
    await task_store.set_pr_refs(
        task_id,
        pr_url=None,
        proposed_pr_path="/repo/.cronos/pull_requests/p.md",
    )

    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    board = resp.json()
    matches = [t for t in board["backlog"] if t["id"] == task_id]
    assert len(matches) == 1
    assert matches[0]["pr_url"] is None
    assert matches[0]["proposed_pr_path"] == "/repo/.cronos/pull_requests/p.md"


async def test_board_summary_pr_fields_default_to_none(async_client):
    """A freshly created task has both pr fields = None (not absent / not empty string).

    The frontend treats `null` as the falsy signal to hide the PR icons.
    An empty string ("") would render an icon with an empty href — bug.
    """
    create = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": "Fresh", "brief": ""},
    )
    task_id = create.json()["id"]

    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    board = resp.json()
    target = next(t for t in board["backlog"] if t["id"] == task_id)
    assert target["pr_url"] is None
    assert target["proposed_pr_path"] is None
