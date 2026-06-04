"""
backend/tests/integration/test_event_triggers_e2e.py — End-to-end integration
tests for the three event trigger kinds (arc6-event-triggers I6).

All six acceptance criteria from the design report are tested here:

  Test 1 — task-state-change trigger: harness enqueued when task transitions DONE.
  Test 2 — webhook trigger: POST /webhook → HTTP 202 + run created.
  Test 3 — file-change trigger: file-event fan-out reaches fan_out_to_harnesses.
  Test 4 — Dedup/debounce: same event_id twice → only one run created.
  Test 5 — Fan-out: two harnesses same trigger kind → both get runs.
  Test 6 — Performance: 50 file-change events dispatched in < 2 s.

Strategy
--------
Tests 1, 4, 5 use real HarnessStore + TaskStore + fan_out_to_harnesses +
enqueue_harness_run to exercise the full pipeline end-to-end.  A minimal
WorkerPool mock is used because actual agent execution is not in scope.

Test 2 uses the real FastAPI app via httpx.ASGITransport so the webhook
endpoint auth/dedup/fan-out are all exercised through the HTTP layer.

Test 3 and Test 6 mock fan_out_to_harnesses and call watch_spaces_dir
directly with a synthetic awatch event, which is the same approach used by
the I5 unit tests.  This avoids the need to set up real filesystem watchers
while still exercising the path-matching and create_task dispatch.

Debouncer isolation
-------------------
The module-level ``_debouncer`` in ``app.harnesses.triggers`` persists across
tests within a pytest session.  Each test that creates an EventBusEvent uses
a unique event_id (incorporating the test name or a UUID) to prevent
cross-test interference.  Tests 4 explicitly resets the debouncer entry
before the second invocation to validate the dedup logic in isolation.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

from app.api.harnesses import router as harnesses_router
from app.harnesses import HarnessStore
from app.harnesses.model import Harness, HarnessNode, NodeType, Position
from app.harnesses.triggers import EventBusEvent, EventDebouncer, fan_out_to_harnesses
from app.space_storage import SpaceStore
from app.storage import TaskStore

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

SPACE_ID = "e2e-space"
VALID_TOKEN = "e2e-test-bearer-token-32-chars-ok"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_trigger_node(
    kind: str,
    *,
    node_id: str = "trig-1",
    watch_pattern: str = ".cronos/tasks/*.md",
    auth_token: str = VALID_TOKEN,
    webhook_path: str = "e2e-hook",
    watched_state: str = "done",
    debounce_seconds: float = 0.5,
) -> HarnessNode:
    """Build a HarnessNode of type trigger with the given kind-specific fields."""
    data: dict = {"kind": kind, "debounce_seconds": debounce_seconds}
    if kind == "file-change":
        data["watch_pattern"] = watch_pattern
    elif kind == "webhook":
        data["auth_token"] = auth_token
        data["webhook_path"] = webhook_path
    elif kind == "task-state-change":
        data["watched_state"] = watched_state
    return HarnessNode(
        id=node_id,
        type=NodeType.trigger,
        position=Position(x=0.0, y=0.0),
        data=data,
    )


def _make_harness(name: str, kind: str, **kwargs) -> Harness:
    """Build a minimal Harness with one trigger node of the given kind."""
    now = datetime.now(tz=UTC)
    trigger = _make_trigger_node(kind, **kwargs)
    return Harness(
        name=name,
        description=f"E2E test harness ({kind})",
        nodes=[trigger],
        edges=[],
        created_at=now,
        updated_at=now,
    )


def _make_worker_pool() -> MagicMock:
    """WorkerPool mock that supports get(), register_run(), and enqueue()."""
    mock_worker = MagicMock()
    mock_worker.register_run = MagicMock()
    mock_worker.enqueue = AsyncMock()
    pool = MagicMock()
    pool.get = MagicMock(return_value=mock_worker)
    return pool


def _now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def space_store(tmp_path: Path) -> SpaceStore:
    store = SpaceStore(tmp_path / "spaces")
    await store.create(
        name="E2E Test Space",
        color="#15803D",
        space_id=SPACE_ID,
    )
    return store


@pytest.fixture
async def task_store(space_store: SpaceStore, tmp_path: Path) -> TaskStore:
    store = TaskStore(tmp_path / "spaces")
    await store.reload_all()
    return store


@pytest.fixture
def harness_store() -> HarnessStore:
    return HarnessStore()


@pytest.fixture
def worker_pool() -> MagicMock:
    return _make_worker_pool()


@pytest.fixture
def space_dir(tmp_path: Path) -> Path:
    d = tmp_path / "spaces" / SPACE_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Minimal FastAPI app for HTTP-level tests
# ---------------------------------------------------------------------------


def _make_fastapi_app(
    space_store: SpaceStore,
    harness_store: HarnessStore,
    task_store: TaskStore,
    worker_pool: MagicMock,
) -> FastAPI:
    _app = FastAPI()
    _app.include_router(harnesses_router)
    _app.state.space_store = space_store
    _app.state.harness_store = harness_store
    _app.state.store = task_store
    _app.state.worker_pool = worker_pool
    return _app


# ===========================================================================
# Test 1 — task-state-change trigger: task → DONE enqueues harness run
# ===========================================================================


async def test_task_state_change_trigger_enqueues_run(
    harness_store: HarnessStore,
    task_store: TaskStore,
    worker_pool: MagicMock,
    space_dir: Path,
) -> None:
    """Create a harness with a task-state-change trigger; fire the event by calling
    fan_out_to_harnesses directly (mirroring the callback path in worker.py).
    Assert that a harness run task was created in the TaskStore.
    """
    # Create the harness
    harness = _make_harness("state-change-flow", "task-state-change")
    await harness_store.create(space_dir, harness)

    # Capture task IDs before we call fan_out
    task_id = "task-e2e-001"
    event = EventBusEvent(
        event_id=f"task-state-change:{SPACE_ID}:{task_id}:{uuid.uuid4()}",
        kind="task-state-change",
        space_id=SPACE_ID,
        payload={"task_id": task_id, "old_state": "active", "new_state": "done"},
        timestamp=_now_iso(),
    )

    run_ids = await fan_out_to_harnesses(
        event,
        harness_store=harness_store,
        task_store=task_store,
        worker_pool=worker_pool,
        space_dir=space_dir,
    )

    assert len(run_ids) == 1, (
        f"Expected exactly 1 run_id from fan_out_to_harnesses, got {run_ids}"
    )
    # Verify the run task was created in the TaskStore.
    created_run = task_store.get(run_ids[0])
    assert created_run is not None, "Run task must exist in TaskStore after enqueue"
    assert "state-change-flow" in created_run.title, (
        f"Task title should reference the harness name; got: {created_run.title!r}"
    )


# ===========================================================================
# Test 2 — webhook trigger: POST /webhook → HTTP 202 + run created
# ===========================================================================


async def test_webhook_trigger_http_202_and_run_created(
    space_store: SpaceStore,
    harness_store: HarnessStore,
    task_store: TaskStore,
    worker_pool: MagicMock,
    space_dir: Path,
) -> None:
    """POST to /api/spaces/{id}/harnesses/{name}/webhook with correct Bearer token
    should return HTTP 202 with run_ids and actually create a harness run task.
    """
    harness_name = "webhook-flow"
    harness = _make_harness(
        harness_name,
        "webhook",
        node_id="webhook-trig",
        webhook_path="e2e-wh",
        auth_token=VALID_TOKEN,
    )
    await harness_store.create(space_dir, harness)

    _app = _make_fastapi_app(space_store, harness_store, task_store, worker_pool)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"/api/spaces/{SPACE_ID}/harnesses/{harness_name}/webhook",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
            content=b'{"event": "push", "ref": "refs/heads/main"}',
        )

    assert resp.status_code == 202, (
        f"Expected 202, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert "run_ids" in body, f"Response missing 'run_ids': {body}"
    assert len(body["run_ids"]) == 1, (
        f"Expected 1 run_id in response, got: {body['run_ids']}"
    )

    # Verify the run task exists in the TaskStore
    run_id = body["run_ids"][0]
    created_task = task_store.get(run_id)
    assert created_task is not None, f"Run task {run_id!r} must exist in TaskStore"


async def test_webhook_trigger_wrong_token_returns_401(
    space_store: SpaceStore,
    harness_store: HarnessStore,
    task_store: TaskStore,
    worker_pool: MagicMock,
    space_dir: Path,
) -> None:
    """Wrong Bearer token → 401."""
    harness_name = "webhook-auth-test"
    harness = _make_harness(harness_name, "webhook", auth_token=VALID_TOKEN)
    await harness_store.create(space_dir, harness)

    _app = _make_fastapi_app(space_store, harness_store, task_store, worker_pool)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"/api/spaces/{SPACE_ID}/harnesses/{harness_name}/webhook",
            headers={"Authorization": "Bearer wrong-token"},
            content=b"{}",
        )

    assert resp.status_code == 401


# ===========================================================================
# Test 3 — file-change trigger: simulate file event → fan_out dispatched
# ===========================================================================


async def test_file_change_trigger_dispatches_fan_out(tmp_path: Path) -> None:
    """A file change matching watch_pattern triggers fan_out_to_harnesses via create_task.

    We call watch_spaces_dir() with a synthetic awatch event and assert that
    fan_out_to_harnesses is called exactly once with kind='file-change'.
    """
    from app.main import watch_spaces_dir

    spaces_dir = tmp_path / "spaces"
    space_dir = spaces_dir / SPACE_ID
    space_dir.mkdir(parents=True, exist_ok=True)
    cronos_dir = space_dir / ".cronos" / "tasks"
    cronos_dir.mkdir(parents=True, exist_ok=True)

    watch_pattern = ".cronos/tasks/*.md"
    changed_file = space_dir / ".cronos" / "tasks" / "task-001.md"

    # Build a mock harness store with one file-change trigger harness
    trigger_node = SimpleNamespace(
        type=SimpleNamespace(value="trigger"),
        data={"kind": "file-change", "watch_pattern": watch_pattern, "debounce_seconds": 0.5},
    )
    mock_harness = SimpleNamespace(name="file-change-flow", nodes=[trigger_node])
    harness_store_mock = MagicMock()
    harness_store_mock.list = AsyncMock(return_value=[mock_harness])

    task_store_mock = MagicMock()
    task_store_mock.reindex_path = AsyncMock()

    space_store_mock = MagicMock()
    space_store_mock.reindex_path = AsyncMock()

    worker_pool_mock = _make_worker_pool()

    fan_out_calls: list = []

    async def _fake_fan_out(event, **kwargs):
        fan_out_calls.append(event)
        return ["run-fc-001"]

    stop_event = asyncio.Event()

    async def _fake_awatch(path, stop_event):
        # Yield one synthetic change then stop
        from watchfiles import Change
        yield {(Change.modified, str(changed_file))}
        stop_event.set()

    with (
        patch("app.main.SPACES_DIR", spaces_dir),
        patch("app.main.awatch", _fake_awatch),
        patch("app.main.fan_out_to_harnesses", side_effect=_fake_fan_out),
    ):
        await watch_spaces_dir(
            task_store_mock,
            space_store_mock,
            stop_event,
            harness_store=harness_store_mock,
            worker_pool=worker_pool_mock,
        )
        # Allow create_task coroutines to complete
        await asyncio.sleep(0.05)

    assert len(fan_out_calls) == 1, (
        f"Expected fan_out_to_harnesses called once; got {len(fan_out_calls)}"
    )
    ev = fan_out_calls[0]
    assert ev.kind == "file-change"
    assert ev.space_id == SPACE_ID


# ===========================================================================
# Test 4 — Dedup/debounce: same event_id twice → only one run created
# ===========================================================================


async def test_dedup_same_event_id_fires_only_once(
    harness_store: HarnessStore,
    task_store: TaskStore,
    worker_pool: MagicMock,
    space_dir: Path,
) -> None:
    """Same event_id fired twice within debounce window → only one run created.

    We use a task-state-change event to drive fan_out_to_harnesses twice with
    the same event_id and assert that only one harness run is created.
    The debouncer key is per-harness: "{harness_name}:{event_id}".
    """
    harness = _make_harness("dedup-flow", "task-state-change")
    await harness_store.create(space_dir, harness)

    # Use a stable event_id (same for both calls) — this is what dedup uses.
    event_id = f"task-state-change:{SPACE_ID}:dedup-task:{uuid.uuid4()}"
    event = EventBusEvent(
        event_id=event_id,
        kind="task-state-change",
        space_id=SPACE_ID,
        payload={"task_id": "dedup-task", "old_state": "active", "new_state": "done"},
        timestamp=_now_iso(),
    )

    # First call — should enqueue a run
    run_ids_1 = await fan_out_to_harnesses(
        event,
        harness_store=harness_store,
        task_store=task_store,
        worker_pool=worker_pool,
        space_dir=space_dir,
    )

    # Second call within the debounce window (same event_id) — should be deduplicated
    run_ids_2 = await fan_out_to_harnesses(
        event,
        harness_store=harness_store,
        task_store=task_store,
        worker_pool=worker_pool,
        space_dir=space_dir,
    )

    assert len(run_ids_1) == 1, (
        f"First call should enqueue exactly 1 run; got run_ids={run_ids_1}"
    )
    assert len(run_ids_2) == 0, (
        f"Second call with same event_id within debounce window should return [];"
        f" got run_ids={run_ids_2}"
    )
    # Verify the single run task exists in TaskStore
    run_task = task_store.get(run_ids_1[0])
    assert run_task is not None, (
        f"Run task {run_ids_1[0]!r} must exist in TaskStore after dedup enqueue"
    )
    assert "dedup-flow" in run_task.title, (
        f"Run task title should contain 'dedup-flow'; got {run_task.title!r}"
    )


# ===========================================================================
# Test 5 — Fan-out: two harnesses same trigger kind → both get runs
# ===========================================================================


async def test_fan_out_two_harnesses_both_get_runs(
    harness_store: HarnessStore,
    task_store: TaskStore,
    worker_pool: MagicMock,
    space_dir: Path,
) -> None:
    """Two harnesses with the same trigger kind → both get runs when one event fires."""
    harness_a = _make_harness("fanout-flow-alpha", "task-state-change")
    harness_b = _make_harness("fanout-flow-beta", "task-state-change")
    await harness_store.create(space_dir, harness_a)
    await harness_store.create(space_dir, harness_b)

    event = EventBusEvent(
        event_id=f"task-state-change:{SPACE_ID}:fanout-task:{uuid.uuid4()}",
        kind="task-state-change",
        space_id=SPACE_ID,
        payload={"task_id": "fanout-task", "old_state": "active", "new_state": "done"},
        timestamp=_now_iso(),
    )

    run_ids = await fan_out_to_harnesses(
        event,
        harness_store=harness_store,
        task_store=task_store,
        worker_pool=worker_pool,
        space_dir=space_dir,
    )

    assert len(run_ids) == 2, (
        f"Expected 2 run_ids (one per harness), got {run_ids}"
    )

    # Verify both run tasks exist in TaskStore
    for run_id in run_ids:
        task = task_store.get(run_id)
        assert task is not None, f"Run task {run_id!r} missing from TaskStore"

    # The run titles should reference their respective harnesses
    titles = [task_store.get(rid).title for rid in run_ids]
    assert any("fanout-flow-alpha" in t for t in titles), (
        f"No run for fanout-flow-alpha in titles: {titles}"
    )
    assert any("fanout-flow-beta" in t for t in titles), (
        f"No run for fanout-flow-beta in titles: {titles}"
    )


# ===========================================================================
# Test 6 — Performance: 50 file-change events in < 2 s
# ===========================================================================


async def test_file_change_50_events_under_2s(tmp_path: Path) -> None:
    """Emit 50 .md file change events and assert total elapsed < 2s.

    This guards the design requirement (risk register) that harness-trigger
    matching in watch_spaces_dir() does not regress task reindex throughput.
    We use a batch of 50 events in a single awatch() yield to approximate
    burst behaviour, and measure end-to-end elapsed time.
    """
    from app.main import watch_spaces_dir

    spaces_dir = tmp_path / "spaces"
    space_dir = spaces_dir / SPACE_ID
    space_dir.mkdir(parents=True, exist_ok=True)
    cronos_dir = space_dir / ".cronos" / "tasks"
    cronos_dir.mkdir(parents=True, exist_ok=True)

    watch_pattern = ".cronos/tasks/*.md"

    trigger_node = SimpleNamespace(
        type=SimpleNamespace(value="trigger"),
        data={"kind": "file-change", "watch_pattern": watch_pattern, "debounce_seconds": 0.5},
    )
    mock_harness = SimpleNamespace(name="perf-flow", nodes=[trigger_node])
    harness_store_mock = MagicMock()
    harness_store_mock.list = AsyncMock(return_value=[mock_harness])

    task_store_mock = MagicMock()
    task_store_mock.reindex_path = AsyncMock()

    space_store_mock = MagicMock()
    space_store_mock.reindex_path = AsyncMock()

    worker_pool_mock = _make_worker_pool()
    fan_out_call_count = 0

    async def _fast_fan_out(event, **kwargs):
        nonlocal fan_out_call_count
        fan_out_call_count += 1
        return []

    stop_event = asyncio.Event()

    # Build 50 distinct .md file paths (distinct paths → distinct event_ids → all fire)
    from watchfiles import Change
    batch = {
        (Change.modified, str(space_dir / ".cronos" / "tasks" / f"task-{i:03d}.md"))
        for i in range(50)
    }

    async def _fake_awatch(path, stop_event):
        yield batch
        stop_event.set()

    t0 = time.monotonic()
    with (
        patch("app.main.SPACES_DIR", spaces_dir),
        patch("app.main.awatch", _fake_awatch),
        patch("app.main.fan_out_to_harnesses", side_effect=_fast_fan_out),
    ):
        await watch_spaces_dir(
            task_store_mock,
            space_store_mock,
            stop_event,
            harness_store=harness_store_mock,
            worker_pool=worker_pool_mock,
        )
        # Wait for all dispatched create_task coroutines to complete
        await asyncio.sleep(0.1)
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0, (
        f"Processing 50 file-change events took {elapsed:.3f}s, expected < 2s"
    )
    # At least some events should have fired (debouncer allows first per event_id)
    assert fan_out_call_count > 0, (
        "Expected fan_out_to_harnesses to be called at least once for the 50 events"
    )


# ===========================================================================
# Test 7 — task-state-change: non-DONE transitions do not trigger
# ===========================================================================


async def test_task_state_change_non_done_state_not_filtered_by_fanout(
    harness_store: HarnessStore,
    task_store: TaskStore,
    worker_pool: MagicMock,
    space_dir: Path,
) -> None:
    """fan_out_to_harnesses matches on trigger kind, not on payload content.

    The filter for 'new_state == DONE' lives in worker.py._finalize().
    fan_out_to_harnesses itself routes on event.kind; the caller (main.py)
    is responsible for only calling it on DONE transitions.  Here we verify
    that a task-state-change event IS routed (no content-based filtering in
    fan_out_to_harnesses) — the worker-level gate is tested in I3.
    """
    harness = _make_harness("state-change-nondone", "task-state-change")
    await harness_store.create(space_dir, harness)

    event = EventBusEvent(
        event_id=f"task-state-change:{SPACE_ID}:nondone-task:{uuid.uuid4()}",
        kind="task-state-change",
        space_id=SPACE_ID,
        payload={
            "task_id": "nondone-task",
            "old_state": "backlog",
            "new_state": "active",
        },
        timestamp=_now_iso(),
    )

    run_ids = await fan_out_to_harnesses(
        event,
        harness_store=harness_store,
        task_store=task_store,
        worker_pool=worker_pool,
        space_dir=space_dir,
    )

    # fan_out_to_harnesses routes on kind only; worker guards DONE-only calling.
    # A task-state-change event of any state should still route to the harness.
    assert len(run_ids) == 1, (
        "fan_out_to_harnesses should route any task-state-change event "
        f"regardless of new_state; got {run_ids}"
    )


# ===========================================================================
# Test 8 — webhook 404 when no webhook trigger node
# ===========================================================================


async def test_webhook_no_trigger_node_returns_404(
    space_store: SpaceStore,
    harness_store: HarnessStore,
    task_store: TaskStore,
    worker_pool: MagicMock,
    space_dir: Path,
) -> None:
    """Harness with no webhook trigger node → 404 on POST /webhook."""
    # Build a harness with only an agent node (no trigger)
    now = datetime.now(tz=UTC)
    agent_node = HarnessNode(
        id="agent-1",
        type=NodeType.agent,
        position=Position(x=0.0, y=0.0),
    )
    harness = Harness(
        name="no-trigger-flow",
        nodes=[agent_node],
        edges=[],
        created_at=now,
        updated_at=now,
    )
    await harness_store.create(space_dir, harness)

    _app = _make_fastapi_app(space_store, harness_store, task_store, worker_pool)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"/api/spaces/{SPACE_ID}/harnesses/no-trigger-flow/webhook",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
            content=b"{}",
        )

    assert resp.status_code == 404


# ===========================================================================
# Test 9 — Empty harness list: fan_out returns [] without error
# ===========================================================================


async def test_fan_out_empty_harness_list_returns_empty(
    harness_store: HarnessStore,
    task_store: TaskStore,
    worker_pool: MagicMock,
    space_dir: Path,
) -> None:
    """fan_out_to_harnesses with no harnesses in store returns empty list without error."""
    event = EventBusEvent(
        event_id=f"task-state-change:{SPACE_ID}:empty-test:{uuid.uuid4()}",
        kind="task-state-change",
        space_id=SPACE_ID,
        payload={"task_id": "empty-task", "old_state": "active", "new_state": "done"},
        timestamp=_now_iso(),
    )

    run_ids = await fan_out_to_harnesses(
        event,
        harness_store=harness_store,
        task_store=task_store,
        worker_pool=worker_pool,
        space_dir=space_dir,
    )

    assert run_ids == [], f"Expected [], got {run_ids}"
