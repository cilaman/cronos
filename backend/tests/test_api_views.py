"""Tests for the Views CRUD API and the ?view board filter (arc-3/2).

Covers:
- GET    /api/spaces/{space_id}/views
- POST   /api/spaces/{space_id}/views
- PATCH  /api/spaces/{space_id}/views/{view_id}
- DELETE /api/spaces/{space_id}/views/{view_id}
- GET    /api/tasks?space_id=...&view=...

The seeded view on a fresh space (after reload-from-disk) is id="all",
name="All lanes", default=True, lanes=[backlog, active, waiting, done],
no type_filter.

NOTE: `SpaceStore.create()` writes `views: []` to disk; the default view
is only materialized when the YAML is parsed back through
`parse_space_yaml()`. Tests reload the store to mirror production state
on next startup.
"""
from __future__ import annotations

import pytest

from .conftest import SPACE_ID


# ---------------------------------------------------------------------------
# Autouse fixture: reload the SpaceStore from disk so the seeded default
# view materializes on every space (production behavior on app startup).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _seed_views(space_store, async_client):
    # Order matters: async_client must have wired app.state first so the
    # reload mutates the same instance the API sees.
    await space_store.reload_all()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _list_views(async_client, space_id: str = SPACE_ID):
    resp = await async_client.get(f"/api/spaces/{space_id}/views")
    assert resp.status_code == 200
    return resp.json()


async def _create_view(async_client, **body):
    payload = {
        "name": "My View",
        "lanes": ["backlog", "active"],
    }
    payload.update(body)
    return await async_client.post(
        f"/api/spaces/{SPACE_ID}/views", json=payload
    )


async def _create_task(async_client, *, title: str, type: str = "task"):
    resp = await async_client.post(
        "/api/tasks",
        json={"space_id": SPACE_ID, "title": title, "brief": "", "type": type},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# GET /api/spaces/{space_id}/views
# ---------------------------------------------------------------------------


async def test_list_views_returns_seeded_default_view(async_client):
    views = await _list_views(async_client)

    assert len(views) == 1
    v = views[0]
    assert v["id"] == "all"
    assert v["name"] == "All lanes"
    assert v["default"] is True
    assert set(v["lanes"]) == {"backlog", "active", "waiting", "done"}
    assert v["type_filter"] is None


async def test_list_views_unknown_space_returns_404(async_client):
    resp = await async_client.get("/api/spaces/no-such-space/views")

    assert resp.status_code == 404
    assert "no-such-space" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /api/spaces/{space_id}/views
# ---------------------------------------------------------------------------


async def test_create_view_returns_201_with_view(async_client):
    resp = await _create_view(
        async_client, name="Backlog Only", lanes=["backlog"]
    )

    assert resp.status_code == 201
    v = resp.json()
    assert v["name"] == "Backlog Only"
    assert v["lanes"] == ["backlog"]
    assert v["type_filter"] is None
    assert v["default"] is False
    assert v["id"] == "backlog-only"
    assert "created_at" in v
    assert "updated_at" in v


async def test_create_view_persists_and_visible_via_get(async_client):
    create_resp = await _create_view(
        async_client, name="Active Lane", lanes=["active"]
    )
    created = create_resp.json()

    # Act: list returns 2 views, including the new one
    views = await _list_views(async_client)

    assert len(views) == 2
    ids = [v["id"] for v in views]
    assert created["id"] in ids
    assert "all" in ids


async def test_create_view_persists_to_space_yml(async_client, space_store):
    """After POST, reloading the SpaceStore from disk shows the new view."""
    await _create_view(async_client, name="Persisted", lanes=["done"])

    await space_store.reload_all()
    space = space_store.get(SPACE_ID)
    ids = [v.id for v in space.views]
    assert "persisted" in ids


async def test_create_view_auto_slugs_id_from_name(async_client):
    resp = await _create_view(
        async_client, name="My Cool View!!!", lanes=["backlog"]
    )

    assert resp.status_code == 201
    assert resp.json()["id"] == "my-cool-view"


async def test_create_view_id_collision_appends_suffix(async_client):
    """Two views with names that slugify to the same base get distinct ids."""
    r1 = await _create_view(async_client, name="Focus", lanes=["active"])
    r2 = await _create_view(async_client, name="Focus", lanes=["active"])

    assert r1.status_code == 201
    assert r2.status_code == 201
    id1, id2 = r1.json()["id"], r2.json()["id"]
    assert id1 == "focus"
    assert id2 == "focus-1"
    assert id1 != id2


async def test_create_view_with_type_filter(async_client):
    resp = await _create_view(
        async_client,
        name="Tasks only",
        lanes=["backlog", "active"],
        type_filter=["task", "goal"],
    )

    assert resp.status_code == 201
    assert resp.json()["type_filter"] == ["task", "goal"]


async def test_create_view_default_true_clears_other_defaults(async_client):
    """Setting default=true on a new view demotes the previously-default view."""
    resp = await _create_view(
        async_client, name="New Default", lanes=["backlog"], default=True
    )
    assert resp.status_code == 201

    views = await _list_views(async_client)
    defaults = [v for v in views if v["default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == resp.json()["id"]
    # The seeded "all" view must have been demoted
    seeded = next(v for v in views if v["id"] == "all")
    assert seeded["default"] is False


async def test_create_view_default_false_leaves_existing_default(async_client):
    await _create_view(
        async_client, name="Side View", lanes=["done"], default=False
    )

    views = await _list_views(async_client)
    defaults = [v for v in views if v["default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == "all"


async def test_create_view_unknown_space_returns_404(async_client):
    resp = await async_client.post(
        "/api/spaces/no-such-space/views",
        json={"name": "X", "lanes": ["backlog"]},
    )

    assert resp.status_code == 404


async def test_create_view_empty_lanes_returns_422(async_client):
    resp = await _create_view(async_client, name="Empty", lanes=[])

    assert resp.status_code == 422


async def test_create_view_invalid_lane_returns_422(async_client):
    resp = await _create_view(
        async_client, name="Bad Lane", lanes=["bogus-state"]
    )

    assert resp.status_code == 422


async def test_create_view_invalid_type_filter_returns_422(async_client):
    resp = await _create_view(
        async_client,
        name="Bad TF",
        lanes=["backlog"],
        type_filter=["nonsense"],
    )

    assert resp.status_code == 422


async def test_create_view_empty_name_returns_422(async_client):
    resp = await _create_view(async_client, name="", lanes=["backlog"])

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/spaces/{space_id}/views/{view_id}
# ---------------------------------------------------------------------------


async def test_patch_view_updates_name(async_client):
    create = await _create_view(async_client, name="Original", lanes=["backlog"])
    vid = create.json()["id"]

    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}/views/{vid}", json={"name": "Renamed"}
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    # id and lanes untouched
    assert resp.json()["id"] == vid
    assert resp.json()["lanes"] == ["backlog"]


async def test_patch_view_updates_lanes(async_client):
    create = await _create_view(async_client, name="Lane Edit", lanes=["backlog"])
    vid = create.json()["id"]

    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}/views/{vid}",
        json={"lanes": ["active", "waiting"]},
    )

    assert resp.status_code == 200
    assert resp.json()["lanes"] == ["active", "waiting"]


async def test_patch_view_sets_type_filter(async_client):
    create = await _create_view(async_client, name="TF", lanes=["backlog"])
    vid = create.json()["id"]

    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}/views/{vid}",
        json={"type_filter": ["goal"]},
    )

    assert resp.status_code == 200
    assert resp.json()["type_filter"] == ["goal"]


async def test_patch_view_clear_type_filter_with_null(async_client):
    """Passing type_filter: null explicitly clears the filter."""
    # Arrange: view with a filter
    create = await _create_view(
        async_client, name="HasTF", lanes=["backlog"], type_filter=["task"]
    )
    vid = create.json()["id"]
    assert create.json()["type_filter"] == ["task"]

    # Act
    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}/views/{vid}",
        json={"type_filter": None},
    )

    assert resp.status_code == 200
    assert resp.json()["type_filter"] is None


async def test_patch_view_default_true_clears_other_defaults_atomically(async_client):
    """Setting default=true on one view demotes ALL others; only ONE default after."""
    # Arrange: create a 2nd and 3rd non-default view
    c1 = await _create_view(async_client, name="A", lanes=["backlog"])
    c2 = await _create_view(async_client, name="B", lanes=["active"])
    vid_b = c2.json()["id"]
    assert c1.json()["default"] is False
    assert c2.json()["default"] is False

    # Act: promote B to default
    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}/views/{vid_b}",
        json={"default": True},
    )

    assert resp.status_code == 200
    assert resp.json()["default"] is True

    # Assert: exactly one default, and it's B
    views = await _list_views(async_client)
    defaults = [v for v in views if v["default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == vid_b
    # seeded "all" demoted
    seeded = next(v for v in views if v["id"] == "all")
    assert seeded["default"] is False


async def test_patch_view_no_fields_returns_400(async_client):
    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}/views/all", json={}
    )

    assert resp.status_code == 400
    assert "No fields" in resp.json()["detail"]


async def test_patch_view_unknown_space_returns_404(async_client):
    resp = await async_client.patch(
        "/api/spaces/no-such-space/views/all", json={"name": "X"}
    )

    assert resp.status_code == 404


async def test_patch_view_unknown_view_returns_404(async_client):
    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}/views/no-such-view", json={"name": "X"}
    )

    assert resp.status_code == 404
    assert "no-such-view" in resp.json()["detail"]


async def test_patch_view_empty_lanes_returns_422(async_client):
    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}/views/all", json={"lanes": []}
    )

    assert resp.status_code == 422


async def test_patch_view_combined_fields_persist(async_client, space_store):
    create = await _create_view(async_client, name="Combo", lanes=["backlog"])
    vid = create.json()["id"]

    resp = await async_client.patch(
        f"/api/spaces/{SPACE_ID}/views/{vid}",
        json={
            "name": "Combo Renamed",
            "lanes": ["done"],
            "type_filter": ["issue"],
        },
    )
    assert resp.status_code == 200

    await space_store.reload_all()
    space = space_store.get(SPACE_ID)
    v = next(v for v in space.views if v.id == vid)
    assert v.name == "Combo Renamed"
    assert [s.value for s in v.lanes] == ["done"]
    assert v.type_filter == ["issue"]


# ---------------------------------------------------------------------------
# DELETE /api/spaces/{space_id}/views/{view_id}
# ---------------------------------------------------------------------------


async def test_delete_view_success_returns_204(async_client):
    create = await _create_view(async_client, name="ToDelete", lanes=["backlog"])
    vid = create.json()["id"]

    resp = await async_client.delete(
        f"/api/spaces/{SPACE_ID}/views/{vid}"
    )

    assert resp.status_code == 204
    # Body MUST be empty per HTTP 204 contract
    assert resp.content == b""

    # Confirm it's gone
    views = await _list_views(async_client)
    ids = [v["id"] for v in views]
    assert vid not in ids


async def test_delete_view_last_view_returns_409(async_client):
    """The seeded 'all' view is the only one; deletion must be refused."""
    resp = await async_client.delete(
        f"/api/spaces/{SPACE_ID}/views/all"
    )

    assert resp.status_code == 409
    assert "Cannot delete the last view" in resp.json()["detail"]

    # The view must still be present
    views = await _list_views(async_client)
    assert any(v["id"] == "all" for v in views)


async def test_delete_default_view_reassigns_default_alphabetically(async_client):
    """Deleting the default view picks the alphabetically-first remaining view."""
    # Create "zebra" and "apple" — both non-default; "all" stays default initially
    await _create_view(async_client, name="Zebra", lanes=["backlog"])
    await _create_view(async_client, name="Apple", lanes=["active"])

    # Act: delete the current default "all"
    resp = await async_client.delete(
        f"/api/spaces/{SPACE_ID}/views/all"
    )
    assert resp.status_code == 204

    # Assert: "apple" (alphabetically first) is now default; only one default
    views = await _list_views(async_client)
    defaults = [v for v in views if v["default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == "apple"


async def test_delete_non_default_view_leaves_default_untouched(async_client):
    """Deleting a non-default view does NOT promote anything; default unchanged."""
    create = await _create_view(async_client, name="Side", lanes=["backlog"])
    vid = create.json()["id"]

    resp = await async_client.delete(
        f"/api/spaces/{SPACE_ID}/views/{vid}"
    )
    assert resp.status_code == 204

    views = await _list_views(async_client)
    defaults = [v for v in views if v["default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == "all"


async def test_delete_view_unknown_space_returns_404(async_client):
    resp = await async_client.delete("/api/spaces/no-such-space/views/all")
    assert resp.status_code == 404


async def test_delete_view_unknown_view_returns_404(async_client):
    # Arrange: need 2 views so the "last view" guard doesn't fire first
    await _create_view(async_client, name="Anchor", lanes=["backlog"])

    resp = await async_client.delete(
        f"/api/spaces/{SPACE_ID}/views/no-such-view"
    )

    assert resp.status_code == 404
    assert "no-such-view" in resp.json()["detail"]


async def test_delete_view_persists_to_space_yml(async_client, space_store):
    create = await _create_view(async_client, name="ZapMe", lanes=["backlog"])
    vid = create.json()["id"]

    await async_client.delete(f"/api/spaces/{SPACE_ID}/views/{vid}")

    await space_store.reload_all()
    space = space_store.get(SPACE_ID)
    assert vid not in [v.id for v in space.views]


# ---------------------------------------------------------------------------
# GET /api/tasks?view=... — board filter
# ---------------------------------------------------------------------------


async def test_tasks_with_view_filters_lanes(async_client):
    """A view limited to [backlog] returns empty lists for other lanes."""
    # Arrange: one task per lane via direct creation + state transitions
    await _create_task(async_client, title="In Backlog")
    t2 = await _create_task(async_client, title="In Active")
    await async_client.patch(
        f"/api/tasks/{t2['id']}/state", json={"state": "active"}
    )

    # Sanity: without view, both lanes populated
    base = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")
    assert len(base.json()["backlog"]) == 1
    assert len(base.json()["active"]) == 1

    # Create a backlog-only view
    cv = await _create_view(
        async_client, name="Backlog Only", lanes=["backlog"]
    )
    vid = cv.json()["id"]

    # Act: query with the view
    resp = await async_client.get(
        f"/api/tasks?space_id={SPACE_ID}&view={vid}"
    )

    assert resp.status_code == 200
    board = resp.json()
    assert len(board["backlog"]) == 1
    assert board["active"] == []
    assert board["waiting"] == []
    assert board["done"] == []


async def test_tasks_with_view_default_resolves_to_default_view(async_client):
    """?view=default uses the space's default view."""
    # Arrange: create a non-default view limited to [done] only
    # Then promote it to default. The seeded "all" view will be demoted.
    cv = await _create_view(
        async_client, name="Done Only", lanes=["done"], default=True
    )
    vid = cv.json()["id"]

    # Add a backlog task — this should be HIDDEN by the new default view
    await _create_task(async_client, title="Hidden by default view")

    # Act
    resp = await async_client.get(
        f"/api/tasks?space_id={SPACE_ID}&view=default"
    )

    assert resp.status_code == 200
    board = resp.json()
    assert board["backlog"] == []
    assert board["active"] == []
    assert board["waiting"] == []
    assert board["done"] == []
    # And the chosen view actually IS our new default
    views = await _list_views(async_client)
    default = next(v for v in views if v["default"])
    assert default["id"] == vid


async def test_tasks_with_view_unknown_id_returns_404(async_client):
    resp = await async_client.get(
        f"/api/tasks?space_id={SPACE_ID}&view=no-such-view"
    )

    assert resp.status_code == 404
    assert "no-such-view" in resp.json()["detail"]


async def test_tasks_with_view_without_space_id_returns_400(async_client):
    """?view requires a specific space_id — no view across spaces."""
    resp = await async_client.get("/api/tasks?view=all")

    assert resp.status_code == 400
    assert "space_id" in resp.json()["detail"]


async def test_tasks_with_view_and_space_all_returns_400(async_client):
    """?space_id=all is normalized to cross-space (None scope); ?view forbids that."""
    resp = await async_client.get("/api/tasks?space_id=all&view=all")

    assert resp.status_code == 400


async def test_tasks_with_view_applies_type_filter(async_client):
    """Tasks whose type is not in view.type_filter are removed from results."""
    # Arrange: a task and a goal, both BACKLOG
    await _create_task(async_client, title="A task", type="task")
    await _create_task(async_client, title="A goal", type="goal")

    # View permitting backlog lane, type_filter restricted to "goal"
    cv = await _create_view(
        async_client,
        name="Goals Only",
        lanes=["backlog"],
        type_filter=["goal"],
    )
    vid = cv.json()["id"]

    # Act
    resp = await async_client.get(
        f"/api/tasks?space_id={SPACE_ID}&view={vid}"
    )

    assert resp.status_code == 200
    backlog = resp.json()["backlog"]
    assert len(backlog) == 1
    assert backlog[0]["title"] == "A goal"
    assert backlog[0]["type"] == "goal"


async def test_tasks_with_view_default_when_default_present_does_not_404(async_client):
    """Seeded space always has a default view; ?view=default never 404s out of the box."""
    resp = await async_client.get(
        f"/api/tasks?space_id={SPACE_ID}&view=default"
    )

    assert resp.status_code == 200
    # The seeded view enables all 4 lanes; with no tasks the response is empty.
    body = resp.json()
    assert body == {"backlog": [], "active": [], "waiting": [], "done": []}


async def test_tasks_with_view_unknown_space_returns_404(async_client):
    """The unknown-space check fires before the view-resolution branch."""
    resp = await async_client.get(
        "/api/tasks?space_id=no-such-space&view=all"
    )

    assert resp.status_code == 404
    assert "no-such-space" in resp.json()["detail"]


async def test_tasks_without_view_param_returns_full_board(async_client):
    """Omitting ?view never filters the board (regression guard)."""
    await _create_task(async_client, title="Visible task")

    resp = await async_client.get(f"/api/tasks?space_id={SPACE_ID}")

    assert resp.status_code == 200
    assert len(resp.json()["backlog"]) == 1
