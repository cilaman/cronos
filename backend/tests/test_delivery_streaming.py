"""Regression tests for the delivery/v2 "Live but silent" bug.

Covers the three defects fixed together:
1. RunExecutor.run_delivery_child executes a child inline and streams events to
   both the child's and the goal's SSE streams (no more silent goals).
2. run_goal's delivery path ALWAYS publishes a terminal run_end + drains the
   goal's subscribers, so the frontend leaves the "Live" state on every outcome.
3. The synchronous delivery runner runs off the event loop and bridges child
   execution back via run_coroutine_threadsafe — no "event loop is already
   running" RuntimeError, and the child agent actually runs.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_BUNDLE = Path(__file__).parent.parent.parent / "packages" / "delivery-workflow"
if str(_BUNDLE) not in sys.path:
    sys.path.insert(0, str(_BUNDLE))

from app.run_executor import RunExecutor
from app.models import TaskState


# ── shared harness ───────────────────────────────────────────────────────────

def _make_bus() -> MagicMock:
    bus = MagicMock()
    bus.publish = MagicMock()
    bus.clear_buffer = MagicMock()
    bus.drain_subscribers = MagicMock()
    bus.lookup_space_id = MagicMock(return_value=None)
    return bus


def _make_worker() -> MagicMock:
    w = MagicMock()
    w._current_id = None
    w._current_cancel = None
    w._current_child_id = None
    w._pool = None
    w.stats_store = None
    w.trace_store = None
    w.memory_store = None
    w.space_store = None
    w.harness_store = None
    w._publish = AsyncMock()
    return w


def _make_finalizer(new_state: TaskState = TaskState.DONE) -> MagicMock:
    f = MagicMock()
    f.space_store = None
    f.pool = None
    f.finalize = AsyncMock()
    f.finalize_child = AsyncMock(return_value=new_state)
    return f


def _make_executor(store: MagicMock, *, finalizer=None, worker=None) -> tuple:
    bus = _make_bus()
    worker = worker or _make_worker()
    finalizer = finalizer or _make_finalizer()
    from app import memory_retrieval
    ex = RunExecutor(
        worker=worker,
        store=store,
        event_bus=bus,
        finalizer=finalizer,
        space_store=None,
        harness_store=None,
        memory_store=None,
        done_sentinel={"type": "stream_end"},
        lease_ttl=30.0,
        heartbeat_interval=5.0,
        memory_retrieval=memory_retrieval,
    )
    return ex, bus, worker


def _published_types(worker: MagicMock, task_id: str) -> list[str]:
    """Event 'type' values published to *task_id* via worker._publish."""
    out = []
    for call in worker._publish.await_args_list:
        tid = call.args[0] if call.args else call.kwargs.get("task_id")
        event = call.args[1] if len(call.args) > 1 else call.kwargs.get("event")
        if tid == task_id and isinstance(event, dict):
            out.append(event.get("type"))
    return out


def _ds_trace(status: str = "done") -> SimpleNamespace:
    ds = {
        "status": status,
        "artifact_paths": ["reports/scout.md"],
        "produces": "research",
        "fields": {},
        "open_questions": [],
        "telemetry": {"tokens": 10, "usd": 0.0, "seconds": 1},
    }
    fence = f"```delivery_status\n{json.dumps(ds)}\n```"
    return SimpleNamespace(
        turns=[SimpleNamespace(input_tokens=5, output_tokens=5)],
        duration_seconds=1.0,
        final_text_snippet=fence,
    )


# ── 1. run_delivery_child streams + finalizes ────────────────────────────────

@pytest.mark.asyncio
async def test_run_delivery_child_streams_and_finalizes():
    goal = SimpleNamespace(id="goal-1", space_id="sp1", title="G", brief="")
    child = SimpleNamespace(
        id="child-1", space_id="sp1", title="[delivery] scout",
        state=TaskState.BACKLOG, brief="", agent_model="default", agent_mode="auto",
    )

    store = MagicMock()
    store.get = MagicMock(side_effect=lambda tid: {"goal-1": goal, "child-1": child}.get(tid))
    store.create = AsyncMock(return_value=child)
    store.transition = AsyncMock()

    trace = _ds_trace()
    worker = _make_worker()
    worker.trace_store = MagicMock()
    worker.trace_store.load_latest = AsyncMock(return_value=trace)

    ex, bus, worker = _make_executor(store, worker=worker)

    agent_result = SimpleNamespace(status=SimpleNamespace(value="done"))
    with patch("app.worker.run_agent", AsyncMock(return_value=agent_result)):
        returned = await ex.run_delivery_child(
            "goal-1", "scout", {"node_id": "scout", "artifact_paths": ["docs/x.md"]},
            cancel_event=asyncio.Event(), goal_context="# Goal: G",
        )

    # Child created + transitioned to ACTIVE.
    store.create.assert_awaited_once()
    assert store.create.await_args.kwargs["parent_id"] == "goal-1"
    _brief = store.create.await_args.kwargs["brief"]
    assert "<!-- delivery-node: scout -->" in _brief
    # B4 — the goal slug (slugify("G") == "g") is threaded into the brief so the
    # CC-v1 agent uses it verbatim instead of inventing one per retry.
    assert "slug: g" in _brief
    store.transition.assert_awaited_once()
    assert store.transition.await_args.args[1] == TaskState.ACTIVE

    # Streamed to BOTH the goal and the child.
    assert "goal_child_start" in _published_types(worker, "goal-1")
    assert "goal_child_end" in _published_types(worker, "goal-1")
    assert "run_start" in _published_types(worker, "child-1")
    assert "run_end" in _published_types(worker, "child-1")

    # Finalized + drained + returned the trace for delivery_status parsing.
    ex._finalizer.finalize_child.assert_awaited_once()
    bus.drain_subscribers.assert_any_call("child-1", {"type": "stream_end"})
    # Returns {trace, delivery}; delivery is None here (no space_store → no report).
    assert returned["trace"] is trace
    assert returned["delivery"] is None


@pytest.mark.asyncio
async def test_run_delivery_child_skips_agent_when_cancelled():
    goal = SimpleNamespace(id="goal-1", space_id="sp1", title="G", brief="")
    child = SimpleNamespace(
        id="child-1", space_id="sp1", title="[delivery] scout",
        state=TaskState.BACKLOG, brief="",
    )
    store = MagicMock()
    store.get = MagicMock(side_effect=lambda tid: {"goal-1": goal, "child-1": child}.get(tid))
    store.create = AsyncMock(return_value=child)
    store.transition = AsyncMock()

    worker = _make_worker()
    worker.trace_store = MagicMock()
    worker.trace_store.load_latest = AsyncMock(return_value=None)
    # finalize_child on a cancelled/no-result child → WAITING.
    ex, bus, worker = _make_executor(
        store, finalizer=_make_finalizer(TaskState.WAITING), worker=worker
    )

    cancelled = asyncio.Event()
    cancelled.set()
    run_agent_mock = AsyncMock()
    with patch("app.worker.run_agent", run_agent_mock):
        await ex.run_delivery_child(
            "goal-1", "scout", {"node_id": "scout"},
            cancel_event=cancelled, goal_context="",
        )
    run_agent_mock.assert_not_called()


# ── 2. run_goal delivery path always closes the stream (the reported bug) ─────

@pytest.mark.asyncio
async def test_run_goal_delivery_publishes_run_end_and_drains(tmp_path):
    goal = SimpleNamespace(
        id="goal-1", space_id="sp1", state=TaskState.ACTIVE, type="goal",
        title="Delivery Goal", brief="<!-- delivery-workflow: wf.yaml -->",
    )
    store = MagicMock()
    store.get = MagicMock(return_value=goal)

    ex, bus, worker = _make_executor(store)
    ex.space_store = SimpleNamespace(spaces_dir=tmp_path)

    with patch("app.run_executor.run_delivery_goal", AsyncMock(return_value=None)) as mock_rdg:
        await ex.run_goal("goal-1", user_message=None)

    # Delegated to the delivery driver with the new bridge kwargs.
    mock_rdg.assert_awaited_once()
    kwargs = mock_rdg.await_args.kwargs
    assert kwargs["run_child"] == ex.run_delivery_child
    assert "cancel_event" in kwargs and "goal_context" in kwargs

    # The goal stream is ALWAYS terminated so the frontend leaves "Live".
    assert "run_end" in _published_types(worker, "goal-1")
    bus.drain_subscribers.assert_any_call("goal-1", {"type": "stream_end"})


@pytest.mark.asyncio
async def test_run_goal_delivery_parks_waiting_on_driver_exception(tmp_path):
    """Safety net: if the driver raises (or otherwise leaves the goal ACTIVE), the
    goal is parked WAITING with the error surfaced — never left "ended in active
    state" — and the stream is still drained."""
    goal = SimpleNamespace(
        id="goal-1", space_id="sp1", state=TaskState.ACTIVE, type="goal",
        title="Delivery Goal", brief="<!-- delivery-workflow: wf.yaml -->",
    )
    store = MagicMock()
    store.get = MagicMock(return_value=goal)
    store.finalize_run = AsyncMock()
    ex, bus, worker = _make_executor(store)
    ex.space_store = SimpleNamespace(spaces_dir=tmp_path)

    boom = AsyncMock(side_effect=RuntimeError("driver blew up"))
    with patch("app.run_executor.run_delivery_goal", boom):
        await ex.run_goal("goal-1", user_message=None)  # must not raise

    # Parked WAITING with the real error in the waiting_question.
    store.finalize_run.assert_awaited_once()
    kwargs = store.finalize_run.await_args.kwargs
    assert kwargs["new_state"] == TaskState.WAITING
    assert "driver blew up" in kwargs["waiting_question"]

    # Stream still closed so the frontend leaves "Live".
    assert "run_end" in _published_types(worker, "goal-1")
    bus.drain_subscribers.assert_any_call("goal-1", {"type": "stream_end"})


# ── 3. thread↔loop bridge: real runner, no "loop already running" error ───────

@pytest.mark.asyncio
async def test_thread_loop_bridge_runs_child_without_loop_error(tmp_path):
    """End-to-end: the real synchronous runner dispatches one agent node whose
    execution is bridged back to the main loop. Proves defects #2 and #3 are gone."""
    from app.delivery_driver import run_delivery_goal

    spec_file = tmp_path / "wf.yaml"
    spec_file.write_text(
        "apiVersion: delivery/v1\n"
        "metadata:\n  name: bridge-test\n"
        "defaults:\n  models:\n    build: sonnet\n"
        "  budget:\n    usd_ceiling: 5.0\n    on_exceed: escalate\n"
        "nodes:\n"
        "  - id: scout\n    kind: agent\n    agent: scout\n"
        "    model: {use: build}\n    produces: {class: research}\n"
        "edges: []\n"
    )

    goal = SimpleNamespace(
        id="goal-1", state=TaskState.ACTIVE, title="T", brief="...",
        waiting_question=None,
    )
    store = MagicMock()
    store.get.return_value = goal
    store.finalize_run = AsyncMock()
    trace_store = MagicMock()

    main_loop = asyncio.get_running_loop()
    invoked = {"ran": False, "same_loop": False}

    async def fake_run_child(goal_id, agent_ref, inputs, *, cancel_event, goal_context):
        invoked["ran"] = True
        invoked["same_loop"] = asyncio.get_running_loop() is main_loop
        return _ds_trace("done")

    # No RuntimeError("event loop is already running") must escape.
    await run_delivery_goal(
        goal_id="goal-1",
        spec_path="wf.yaml",
        store=store,
        trace_store=trace_store,
        space_id="sp1",
        space_dir=tmp_path,
        run_dir=tmp_path / "run",
        run_child=fake_run_child,
        cancel_event=asyncio.Event(),
        goal_context="# Goal: T",
    )

    assert invoked["ran"], "run_child was never invoked — bridge failed"
    assert invoked["same_loop"], "run_child did not run on the main event loop"
    # Single agent node completed → runner status done → goal finalized DONE.
    store.finalize_run.assert_awaited_once()
    assert store.finalize_run.await_args.kwargs["new_state"] == TaskState.DONE
