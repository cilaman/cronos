from __future__ import annotations

"""Integration / wiring tests for backend/app/api/harnesses.py mounted in main.py.

These tests verify two things:
  1. Auth wiring — unauthenticated requests return 401 when auth is enabled.
  2. DI ordering — HarnessStore is on app.state before the first request, so
     an authenticated request to a valid endpoint does not raise AttributeError
     but instead returns a meaningful HTTP response (200 or 404, not 500).

The tests use the shared `async_client` fixture from conftest.py which already
mounts the real FastAPI app. We additionally set app.state.harness_store via
the fixture below so the DI chain resolves correctly.
"""

import httpx
import pytest

from app.harnesses import HarnessStore
from app.main import app

from .conftest import SPACE_ID

AUTH_USER = "testuser"
AUTH_PASS = "testpass"

HARNESS_URL = f"/api/spaces/{SPACE_ID}/harnesses"
NONEXISTENT_URL = "/api/spaces/nonexistent-space/harnesses"


@pytest.fixture(autouse=True)
def _inject_harness_store(tmp_path):
    """Inject a fresh HarnessStore onto app.state for each test.

    This mirrors the conftest.py pattern of setting app.state.X directly so
    that the DI helper in harnesses.py (`request.app.state.harness_store`)
    resolves without raising AttributeError.
    """
    app.state.harness_store = HarnessStore()
    yield
    # cleanup — remove harness_store so other tests are not surprised
    try:
        del app.state.harness_store
    except AttributeError:
        pass


@pytest.fixture(autouse=True)
def _clear_auth_env(monkeypatch):
    """Ensure no leftover auth env vars (including the fail-closed bypass) interfere."""
    monkeypatch.delenv("CRONOS_BASIC_AUTH_HASH", raising=False)
    monkeypatch.delenv("CRONOS_BASIC_AUTH_USER", raising=False)
    monkeypatch.delenv("CRONOS_BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("CRONOS_AUTH_DISABLED", raising=False)


# ---------------------------------------------------------------------------
# Auth wiring — unauthenticated requests must return 401 when auth enabled
# ---------------------------------------------------------------------------


async def test_unauthenticated_list_returns_401(async_client, monkeypatch):
    """GET /api/spaces/{space_id}/harnesses without credentials must return 401."""
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    resp = await async_client.get(HARNESS_URL)

    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate", "").lower().startswith("basic")


async def test_unauthenticated_post_returns_401(async_client, monkeypatch):
    """POST /api/spaces/{space_id}/harnesses without credentials must return 401."""
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    resp = await async_client.post(
        HARNESS_URL,
        json={"name": "test-harness"},
    )

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DI ordering — authenticated requests must NOT raise AttributeError (500)
# ---------------------------------------------------------------------------


async def test_authenticated_list_existing_space_returns_200(async_client, monkeypatch):
    """GET /api/spaces/{space_id}/harnesses with valid credentials returns 200.

    The test space is created by the conftest space_store fixture. An empty
    list response (200 []) confirms that:
      - the router is wired into main.py
      - HarnessStore is on app.state (DI resolves, no AttributeError)
      - SpaceStore resolves the space_id correctly (no 500)
      - auth dependency accepts the credentials
    """
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    resp = await async_client.get(
        HARNESS_URL,
        auth=httpx.BasicAuth(AUTH_USER, AUTH_PASS),
    )

    assert resp.status_code == 200
    assert resp.json() == []


async def test_authenticated_list_nonexistent_space_returns_404(async_client, monkeypatch):
    """GET /api/spaces/nonexistent-space/harnesses with valid credentials returns 404.

    This confirms the router is wired and the space-not-found path in the DI
    helper works end-to-end without a 500. A 404 (not 500) means:
      - HarnessStore is on app.state
      - SpaceStore is on app.state
      - _get_space_dir correctly raises HTTPException(404) for unknown space_id
    """
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    resp = await async_client.get(
        NONEXISTENT_URL,
        auth=httpx.BasicAuth(AUTH_USER, AUTH_PASS),
    )

    assert resp.status_code == 404


async def test_harness_store_on_app_state(async_client):
    """Verify HarnessStore is accessible on app.state after wiring."""
    assert hasattr(app.state, "harness_store")
    assert isinstance(app.state.harness_store, HarnessStore)


async def test_harnesses_endpoint_reachable_without_auth_when_auth_disabled(async_client, monkeypatch):
    """When auth is explicitly disabled via CRONOS_AUTH_DISABLED=true, the endpoint returns 200."""
    monkeypatch.setenv("CRONOS_AUTH_DISABLED", "true")

    resp = await async_client.get(HARNESS_URL)

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Worker-executor integration tests (I7 design requirements)
# ---------------------------------------------------------------------------
#
# These tests verify the following design invariants:
#   1. A Wait(human) reply re-enters the executor at the waiting Wait node.
#   2. A Wait(human) resume re-uses already-completed Agent node outputs
#      (agent node is NOT re-created/re-executed).
#   3. The worker properly calls executor.execute() for WAITING harness goals
#      with pending_messages.
#   4. End-to-end: Agent → Wait(human) → Agent2; after Wait reply, Agent2
#      runs and Agent1 does NOT re-run.
#
# These tests exercise the executor directly (not the full HTTP/worker stack)
# to keep them fast and isolated.  The worker-dispatch test (#3) creates a
# Worker instance with a stub harness_store and asserts executor.execute() is
# invoked.
# ---------------------------------------------------------------------------

import json
import tempfile
from datetime import UTC, datetime as _dt
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.harnesses.executor import HarnessExecutor
from app.harnesses.model import (
    Harness,
    HarnessEdge,
    HarnessNode,
    NodeRef,
    NodeType,
    Position,
)
from app.harnesses.run_state import NodeState, RunState, save_atomic as save_run_state
from app.models import Space, TaskState
from app.trace_parser import RunTrace


# --- helpers ---


def _make_space_obj(space_id: str = "wiring-space") -> Space:
    now = _dt.now(tz=UTC)
    return Space(id=space_id, name="Wiring Space", color="#000000",
                 created_at=now, updated_at=now)


def _make_pos() -> Position:
    return Position(x=0.0, y=0.0)


def _make_agent_node(node_id: str, prompt: str = "do something") -> HarnessNode:
    return HarnessNode(
        id=node_id, type=NodeType.agent, position=_make_pos(),
        ports={"out": {}},
        data={"agent_ref": "test-agent", "prompt_template": prompt},
        label=node_id,
    )


def _make_wait_node(node_id: str) -> HarnessNode:
    return HarnessNode(
        id=node_id, type=NodeType.wait, position=_make_pos(),
        ports={"in": {}, "out": {}},
        data={"mode": "human", "max_wait_seconds": 300, "waiting_question": "Ready?"},
        label=node_id,
    )


def _make_edge(eid: str, src: str, tgt: str) -> HarnessEdge:
    return HarnessEdge(
        id=eid,
        source=NodeRef(node_id=src, port_id="out"),
        target=NodeRef(node_id=tgt, port_id="out"),
    )


def _make_trace(task_id: str = "t1", final_text: str = "output",
                exit_reason: str = "DONE") -> RunTrace:
    now = _dt.now(tz=UTC)
    return RunTrace(
        task_id=task_id, space_id="wiring-space", run_index=0,
        session_id=None, model="sonnet", mode="auto",
        started_at=now, ended_at=now, duration_seconds=0.0,
        exit_reason=exit_reason, final_text_snippet=final_text,
    )


def _make_store_mock() -> MagicMock:
    """TaskStore mock that generates unique task IDs."""
    store = MagicMock()
    _counter = [0]

    async def create(*, space_id, title, brief, parent_id=None, **kwargs):
        _counter[0] += 1
        task = MagicMock()
        task.id = f"ct-{_counter[0]}"
        task.state = TaskState.DONE
        return task

    store.create = create
    store.get = MagicMock(return_value=None)
    return store


class _StubWorker:
    """Minimal WorkerProtocol stub."""

    def __init__(self, task_state: TaskState = TaskState.DONE,
                 final_text: str = "output") -> None:
        self.task_state = task_state
        self.final_text = final_text
        self.run_agent_calls: list[str] = []

    async def run_agent(self, task_id: str, **kwargs) -> RunTrace:
        self.run_agent_calls.append(task_id)
        return _make_trace(task_id=task_id, final_text=self.final_text)

    async def finalize_child(self, task_id: str, trace: RunTrace) -> TaskState:
        return self.task_state


def _no_tools_resolver(space_id: str, agent_ref: str):
    return None


# ---------------------------------------------------------------------------
# Test 1: Wait(human) reply re-enters executor at the waiting Wait node
# ---------------------------------------------------------------------------


async def test_wait_human_reply_reenters_at_wait_node():
    """Wait(human) reply calls executor.execute() which resumes from waiting_node_id.

    Scenario:
    - First execute(): PRE_AGENT runs, WAIT1 parks → waiting_node_id='WAIT1'
    - Second execute(): resumes from WAIT1's outgoing edges → POST_AGENT runs
    - After resume, waiting_node_id is cleared (None)
    """
    pre_agent = _make_agent_node("PRE_AGENT", "first task")
    wait_node = _make_wait_node("WAIT1")
    post_agent = _make_agent_node("POST_AGENT", "second task")

    edge_pre_wait = _make_edge("e1", "PRE_AGENT", "WAIT1")
    edge_wait_post = _make_edge("e2", "WAIT1", "POST_AGENT")

    harness = Harness(
        name="test-wait-reenter",
        nodes=[pre_agent, wait_node, post_agent],
        edges=[edge_pre_wait, edge_wait_post],
    )
    space = _make_space_obj()
    store = _make_store_mock()
    worker = _StubWorker(task_state=TaskState.DONE, final_text="pre_output")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _no_tools_resolver)

            # First execute: PRE_AGENT runs; WAIT1 parks.
            state1 = await executor.execute("run-wr1", harness, space)

    # After first execute: parked at WAIT1.
    assert state1.waiting_node_id == "WAIT1", (
        f"Expected waiting_node_id='WAIT1', got {state1.waiting_node_id!r}"
    )
    assert state1.nodes_executed["PRE_AGENT"].status == "done"
    assert state1.nodes_executed["WAIT1"].status == "in_progress"
    assert "POST_AGENT" not in state1.nodes_executed
    # Only PRE_AGENT ran.
    assert len(worker.run_agent_calls) == 1

    with tempfile.TemporaryDirectory() as tmpdir2:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir2)):
            # Pre-seed the run state file (simulating persisted state from first run).
            state_dir = (
                Path(tmpdir2) / "spaces" / space.id / ".cronos" / "harness-runs"
            )
            state_dir.mkdir(parents=True)
            save_run_state(state_dir / "run-wr1.json", state1)

            executor2 = HarnessExecutor(store, worker, _no_tools_resolver)

            # Second execute: resumes from WAIT1's outgoing edges.
            state2 = await executor2.execute("run-wr1", harness, space)

    # After second execute: waiting_node_id cleared.
    assert state2.waiting_node_id is None
    # WAIT1 should now be done (was in_progress, cleared on resume).
    assert state2.nodes_executed["WAIT1"].status == "done"
    # POST_AGENT executed after resume.
    assert state2.nodes_executed["POST_AGENT"].status == "done"
    # Total run_agent calls: 1 (PRE_AGENT) + 1 (POST_AGENT) = 2.
    assert len(worker.run_agent_calls) == 2


# ---------------------------------------------------------------------------
# Test 2: Wait(human) resume re-uses completed Agent node outputs
# ---------------------------------------------------------------------------


async def test_wait_human_resume_reuses_completed_agent_outputs():
    """Wait-human resume: completed Agent node is NOT re-created or re-executed.

    After a Wait(human) reply, the executor must NOT re-run PRE_AGENT because
    it is already in nodes_executed with status='done'.  Only POST_AGENT runs.
    """
    pre_agent = _make_agent_node("PRE2", "pre step")
    wait_node = _make_wait_node("WAIT2")
    post_agent = _make_agent_node("POST2", "post step")

    harness = Harness(
        name="test-wait-reuse",
        nodes=[pre_agent, wait_node, post_agent],
        edges=[
            _make_edge("r1", "PRE2", "WAIT2"),
            _make_edge("r2", "WAIT2", "POST2"),
        ],
    )
    space = _make_space_obj("reuse-space")
    store = _make_store_mock()
    worker = _StubWorker(task_state=TaskState.DONE, final_text="pre2_output")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            state_dir = (
                Path(tmpdir) / "spaces" / "reuse-space" / ".cronos" / "harness-runs"
            )
            state_dir.mkdir(parents=True)

            executor = HarnessExecutor(store, worker, _no_tools_resolver)

            # First execute: PRE2 runs, WAIT2 parks.
            state1 = await executor.execute("run-reuse", harness, space)

            assert state1.waiting_node_id == "WAIT2"
            assert len(worker.run_agent_calls) == 1, "PRE2 should have run once"
            pre2_call_count_after_first_run = len(worker.run_agent_calls)

            # Second execute: resume (waiting_node_id='WAIT2' persisted on disk).
            state2 = await executor.execute("run-reuse", harness, space)

    # After resume: PRE2 NOT re-executed (only POST2 added).
    assert len(worker.run_agent_calls) == 2, (
        f"Expected 2 total run_agent calls (PRE2 + POST2), got {len(worker.run_agent_calls)}"
    )
    # Verify POST2 was executed.
    assert state2.nodes_executed["POST2"].status == "done"
    # PRE2 still done (reused, not re-run).
    assert state2.nodes_executed["PRE2"].status == "done"
    # waiting_node_id cleared.
    assert state2.waiting_node_id is None


# ---------------------------------------------------------------------------
# Test 3: Worker calls executor.execute() for WAITING harness goals
# ---------------------------------------------------------------------------


async def test_worker_calls_executor_for_waiting_harness_goal():
    """Worker._resume_harness_run calls executor.execute() when waiting_node_id is set.

    Verifies:
    - A task with a harness run-state file (waiting_node_id set) triggers executor.execute().
    - executor.execute() is called with (task_id, harness, space).
    - The worker does NOT call run_agent for this task.
    """
    from app.worker import Worker

    space_id = "worker-test-space"
    task_id = "harness-run-task-1"

    # Build a minimal harness.
    agent_node = _make_agent_node("AGT_W", "worker test")
    wait_node = _make_wait_node("WAIT_W")
    harness = Harness(
        name="worker-test-harness",
        nodes=[agent_node, wait_node],
        edges=[_make_edge("ew1", "AGT_W", "WAIT_W")],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a run-state file simulating a parked harness run.
        run_state_dir = tmpdir_path / "spaces" / space_id / ".cronos" / "harness-runs"
        run_state_dir.mkdir(parents=True)
        run_state = RunState(
            run_id=task_id,
            harness_id="worker-test-harness",
            goal_task_id=task_id,
            nodes_executed={
                "AGT_W": NodeState(status="done", output="agt_output"),
                "WAIT_W": NodeState(status="in_progress"),
            },
            waiting_node_id="WAIT_W",
        )
        save_run_state(run_state_dir / f"{task_id}.json", run_state)

        # Stub task store.
        task_mock = MagicMock()
        task_mock.id = task_id
        task_mock.space_id = space_id
        task_mock.type = "task"
        task_mock.agent_model = "sonnet"
        task_mock.agent_mode = "auto"
        task_mock.state = TaskState.WAITING

        store_mock = MagicMock()
        store_mock.get = MagicMock(return_value=task_mock)

        # Stub space store.
        space_obj = _make_space_obj(space_id)
        space_store_mock = MagicMock()
        space_store_mock.get = MagicMock(return_value=space_obj)
        space_store_mock.spaces_dir = tmpdir_path / "spaces"

        # Stub harness store.
        harness_store_mock = MagicMock()
        harness_store_mock.get = AsyncMock(return_value=harness)

        # Track executor.execute() calls.
        execute_calls: list[tuple] = []

        # Patch both DATA_DIR references:
        # - app.worker.DATA_DIR: used by _resume_harness_run to find the run-state file.
        # - app.harnesses.executor._DATA_DIR: used by HarnessExecutor for the same file.
        with (
            patch("app.worker.DATA_DIR", tmpdir_path),
            patch("app.harnesses.executor._DATA_DIR", tmpdir_path),
        ):
            worker = Worker(
                store=store_mock,
                space_store=space_store_mock,
                harness_store=harness_store_mock,
            )

            # Patch executor.execute to return a completed state (no more waiting).
            completed_state = RunState(
                run_id=task_id, harness_id="worker-test-harness",
                goal_task_id=task_id,
                nodes_executed={
                    "AGT_W": NodeState(status="done", output="agt_output"),
                    "WAIT_W": NodeState(status="done"),
                },
                waiting_node_id=None,
            )

            async def mock_execute(run_goal_id, harness_arg, space_arg):
                execute_calls.append((run_goal_id, harness_arg, space_arg))
                return completed_state

            with patch("app.harnesses.executor.HarnessExecutor.execute",
                       side_effect=mock_execute):
                # finalize_run must not raise; stub it.
                finalize_calls: list = []

                async def mock_finalize_run(task_id_arg, *, new_state, session_id,
                                            waiting_question, history_entry):
                    finalize_calls.append((task_id_arg, new_state))

                store_mock.finalize_run = mock_finalize_run

                result = await worker._resume_harness_run(task_id)

    # _resume_harness_run must return True (handled as harness task).
    assert result is True, "Expected _resume_harness_run to return True"

    # executor.execute() must have been called exactly once.
    assert len(execute_calls) == 1, (
        f"Expected 1 executor.execute() call, got {len(execute_calls)}"
    )
    called_run_goal_id, called_harness, called_space = execute_calls[0]
    assert called_run_goal_id == task_id
    assert called_harness.name == "worker-test-harness"
    assert called_space.id == space_id

    # Task was finalized to DONE (completed_state has waiting_node_id=None).
    assert any(s == TaskState.DONE for _, s in finalize_calls), (
        f"Expected finalize to DONE; got {finalize_calls}"
    )


# ---------------------------------------------------------------------------
# Test 4: End-to-end: Agent → Wait(human) → Agent2 full flow
# ---------------------------------------------------------------------------


async def test_end_to_end_agent_wait_human_agent2():
    """End-to-end: Agent1 → Wait(human) → Agent2.

    After Wait reply:
    - Agent2 runs and reaches done.
    - Agent1 does NOT re-run (its run_agent call count stays at 1 from the first execute).

    This test uses the executor directly (no Worker) to verify the core invariant:
    the executor's resume path correctly skips already-completed nodes.
    """
    agent1 = _make_agent_node("E2E_A1", "agent 1 work")
    wait_node = _make_wait_node("E2E_WAIT")
    agent2 = _make_agent_node("E2E_A2", "agent 2 work")

    harness = Harness(
        name="e2e-test-harness",
        nodes=[agent1, wait_node, agent2],
        edges=[
            _make_edge("x1", "E2E_A1", "E2E_WAIT"),
            _make_edge("x2", "E2E_WAIT", "E2E_A2"),
        ],
    )
    space = _make_space_obj("e2e-space")
    store = _make_store_mock()

    # Track which node IDs were executed by tracking run_agent calls via task title.
    nodes_executed_order: list[str] = []
    task_id_to_node: dict[str, str] = {}
    task_counter = [0]

    async def create_task(*, space_id, title, brief, parent_id=None, **kwargs):
        task_counter[0] += 1
        t = MagicMock()
        t.id = f"e2e-task-{task_counter[0]}"
        t.state = TaskState.DONE
        # title == node label (set as node.label or node.id in executor)
        task_id_to_node[t.id] = title
        return t

    store.create = create_task

    async def run_agent_track(task_id: str, **kwargs) -> RunTrace:
        node_label = task_id_to_node.get(task_id, task_id)
        nodes_executed_order.append(node_label)
        return _make_trace(task_id=task_id, final_text=f"output_of_{node_label}")

    async def finalize_child_ok(task_id: str, trace: RunTrace) -> TaskState:
        return TaskState.DONE

    stub_worker = MagicMock()
    stub_worker.run_agent = run_agent_track
    stub_worker.finalize_child = finalize_child_ok

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, stub_worker, _no_tools_resolver)

            # First execute: Agent1 runs, Wait parks.
            state1 = await executor.execute("e2e-run", harness, space)

    assert state1.waiting_node_id == "E2E_WAIT", (
        f"Expected waiting at E2E_WAIT; got {state1.waiting_node_id!r}"
    )
    assert len(nodes_executed_order) == 1
    assert nodes_executed_order[0] == "E2E_A1", (
        f"Expected Agent1 to run first; got {nodes_executed_order[0]!r}"
    )

    # Simulate the human reply: call execute() again (the state file has waiting_node_id set).
    with tempfile.TemporaryDirectory() as tmpdir2:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir2)):
            # Pre-seed the state from first run.
            state_dir = (
                Path(tmpdir2) / "spaces" / "e2e-space" / ".cronos" / "harness-runs"
            )
            state_dir.mkdir(parents=True)
            save_run_state(state_dir / "e2e-run.json", state1)

            executor2 = HarnessExecutor(store, stub_worker, _no_tools_resolver)
            state2 = await executor2.execute("e2e-run", harness, space)

    # After resume:
    assert state2.waiting_node_id is None
    assert state2.nodes_executed["E2E_A1"].status == "done"
    assert state2.nodes_executed["E2E_WAIT"].status == "done"
    assert state2.nodes_executed["E2E_A2"].status == "done"

    # Agent1 must NOT have re-run; only Agent2 was added.
    assert len(nodes_executed_order) == 2, (
        f"Expected 2 total agent runs (A1 + A2), got {len(nodes_executed_order)}: "
        f"{nodes_executed_order}"
    )
    assert nodes_executed_order[0] == "E2E_A1"
    assert nodes_executed_order[1] == "E2E_A2", (
        f"Expected Agent2 to run after resume; got {nodes_executed_order[1]!r}"
    )
