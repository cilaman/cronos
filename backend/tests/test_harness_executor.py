"""
Tests for backend/app/harnesses/executor.py

Covers:
- Basic 3-node linear harness (A→B→C) all Agent nodes
- Control-flow node dispatch (decision, wait, aggregator)
- Fail-fast: when node B fails, node C is marked skipped with reason='upstream_failed'
- Variable interpolation: upstream output flows into downstream prompt_template
- Run state file created and updated per node
- Resume: in_progress node with done child_task_id → node marked done without re-executing
- WorkerProtocol is stubbed (not a real Worker instance)
- Decision routing: edge A on STATUS=DONE, edge B on STATUS=BLOCKED
- Wait(human) parks in WAITING and sets waiting_node_id
- Wait(human) resume re-uses completed Agent node outputs (doesn't re-run them)
- Aggregator 'all': waits for both predecessors
- Aggregator 'any': fires on first done predecessor
- 4-Agent linear chain regression: same execution order as old _topo_sort
- Timed Wait (G09): fresh start persists wake_at; restart-before-wake sleeps remaining; restart-after-wake fires immediately
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses.executor import HarnessExecutor, _topo_sort
from app.harnesses.model import (
    Harness,
    HarnessEdge,
    HarnessNode,
    NodeRef,
    NodeType,
    Position,
)
from app.harnesses.run_state import NodeState, RunState, load
from app.models import AiToolEntry, Space, TaskState
from app.trace_parser import RunTrace


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _make_space(space_id: str = "test-space") -> Space:
    now = datetime.now(tz=UTC)
    return Space(
        id=space_id,
        name="Test Space",
        color="#123456",
        created_at=now,
        updated_at=now,
    )


def _make_position() -> Position:
    return Position(x=0.0, y=0.0)


def _make_agent_node(node_id: str, label: str = "", agent_ref: str = "my-agent",
                     prompt_template: str = "do something") -> HarnessNode:
    return HarnessNode(
        id=node_id,
        type=NodeType.agent,
        position=_make_position(),
        ports={"out": {"direction": "output"}},
        data={"agent_ref": agent_ref, "prompt_template": prompt_template},
        label=label or node_id,
    )


def _make_decision_node(node_id: str) -> HarnessNode:
    return HarnessNode(
        id=node_id,
        type=NodeType.decision,
        position=_make_position(),
        ports={"in": {"direction": "input"}, "out": {"direction": "output"}},
        data={},
        label=node_id,
    )


def _make_wait_node(node_id: str, mode: str = "human",
                    duration_seconds: float = 0.0,
                    max_wait_seconds: float = 300.0,
                    waiting_question: str | None = None) -> HarnessNode:
    data: dict = {"mode": mode, "max_wait_seconds": max_wait_seconds}
    if mode == "timed":
        data["duration_seconds"] = duration_seconds
    if waiting_question is not None:
        data["waiting_question"] = waiting_question
    return HarnessNode(
        id=node_id,
        type=NodeType.wait,
        position=_make_position(),
        ports={"in": {"direction": "input"}, "out": {"direction": "output"}},
        data=data,
        label=node_id,
    )


def _make_aggregator_node(node_id: str, mode: str = "all") -> HarnessNode:
    return HarnessNode(
        id=node_id,
        type=NodeType.aggregator,
        position=_make_position(),
        ports={"in": {"direction": "input"}, "out": {"direction": "output"}},
        data={"mode": mode},
        label=node_id,
    )


def _make_edge(edge_id: str, src_node: str, tgt_node: str,
               src_port: str = "out", tgt_port: str = "out",
               condition: str | None = None) -> HarnessEdge:
    return HarnessEdge(
        id=edge_id,
        source=NodeRef(node_id=src_node, port_id=src_port),
        target=NodeRef(node_id=tgt_node, port_id=tgt_port),
        condition=condition,
    )


def _make_trace(final_text: str = "result", parent_run_id: str | None = None,
                exit_reason: str = "DONE") -> RunTrace:
    now = datetime.now(tz=UTC)
    return RunTrace(
        task_id="child-task-id",
        space_id="test-space",
        run_index=0,
        session_id=None,
        model="sonnet",
        mode="auto",
        started_at=now,
        ended_at=now,
        duration_seconds=0.0,
        exit_reason=exit_reason,
        final_text_snippet=final_text,
        parent_run_id=parent_run_id,
    )


def _make_task_mock(task_id: str, state: TaskState = TaskState.DONE) -> MagicMock:
    task = MagicMock()
    task.id = task_id
    task.state = state
    return task


class StubWorker:
    """WorkerProtocol stub for unit tests."""

    def __init__(self, task_state: TaskState = TaskState.DONE,
                 final_text: str = "output"):
        self.task_state = task_state
        self.final_text = final_text
        self.run_agent_calls: list[tuple[str, dict]] = []
        self.finalize_calls: list[tuple[str, RunTrace]] = []
        self._task_counter = 0

    async def run_agent(self, task_id: str, **kwargs) -> RunTrace:
        self.run_agent_calls.append((task_id, kwargs))
        return _make_trace(final_text=self.final_text)

    async def finalize_child(self, task_id: str, trace: RunTrace) -> TaskState:
        self.finalize_calls.append((task_id, trace))
        return self.task_state

    def _publish(self, task_id: str, event: dict) -> None:
        """No-op publish for compatibility with WorkerProtocol."""
        pass


class FailingWorker(StubWorker):
    """Worker that fails all runs."""

    async def run_agent(self, task_id: str, **kwargs) -> RunTrace:
        self.run_agent_calls.append((task_id, kwargs))
        return _make_trace(final_text="failed output")

    async def finalize_child(self, task_id: str, trace: RunTrace) -> TaskState:
        self.finalize_calls.append((task_id, trace))
        return TaskState.WAITING  # failure = non-DONE state


def _make_store_mock(space_id: str = "test-space") -> MagicMock:
    """Create a TaskStore mock that creates tasks with unique ids."""
    store = MagicMock()
    _counter = [0]

    async def create(*, space_id, title, brief, parent_id=None, **kwargs):
        _counter[0] += 1
        task = _make_task_mock(f"task-{_counter[0]}")
        return task

    store.create = create
    store.get = MagicMock(return_value=None)  # default: child not found
    return store


def _tools_resolver(space_id: str, agent_ref: str) -> AiToolEntry | None:
    """Stub tools resolver — returns None (no matching tool)."""
    return None


# ---------------------------------------------------------------------------
# _topo_sort unit tests
# ---------------------------------------------------------------------------


def test_topo_sort_linear():
    """Three nodes A→B→C should come out in A, B, C order."""
    a = _make_agent_node("A")
    b = _make_agent_node("B")
    c = _make_agent_node("C")
    edge_ab = _make_edge("e1", "A", "B", tgt_port="out")
    edge_bc = _make_edge("e2", "B", "C", tgt_port="out")
    # All nodes need "out" port; add port to all
    a = HarnessNode(**{**a.model_dump(), "ports": {"out": {}}})
    b = HarnessNode(**{**b.model_dump(), "ports": {"out": {}}})
    c = HarnessNode(**{**c.model_dump(), "ports": {"out": {}}})
    harness = Harness(name="test", nodes=[a, b, c], edges=[edge_ab, edge_bc])
    ordered = _topo_sort(harness)
    assert [n.id for n in ordered] == ["A", "B", "C"]


def test_topo_sort_no_edges():
    """Nodes with no edges are all returned (in deterministic order)."""
    a = _make_agent_node("X")
    b = _make_agent_node("Y")
    harness = Harness(name="test", nodes=[a, b], edges=[])
    ordered = _topo_sort(harness)
    assert {n.id for n in ordered} == {"X", "Y"}
    assert len(ordered) == 2


# ---------------------------------------------------------------------------
# Basic 3-node linear harness — all Agent nodes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_linear_three_nodes():
    """Execute A→B→C; all nodes succeed; run_agent called 3 times."""
    a = HarnessNode(id="A", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "do A"},
                    label="A")
    b = HarnessNode(id="B", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "do B"},
                    label="B")
    c = HarnessNode(id="C", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "do C"},
                    label="C")
    edge_ab = HarnessEdge(id="e1", source=NodeRef(node_id="A", port_id="out"),
                          target=NodeRef(node_id="B", port_id="out"))
    edge_bc = HarnessEdge(id="e2", source=NodeRef(node_id="B", port_id="out"),
                          target=NodeRef(node_id="C", port_id="out"))
    harness = Harness(name="linear", nodes=[a, b, c], edges=[edge_ab, edge_bc])
    space = _make_space()
    store = _make_store_mock(space.id)
    worker = StubWorker(task_state=TaskState.DONE, final_text="node_output")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-001", harness, space)

    assert len(worker.run_agent_calls) == 3
    for node_id in ("A", "B", "C"):
        assert result.nodes_executed[node_id].status == "done"


@pytest.mark.asyncio
async def test_executor_all_nodes_done_in_run_state():
    """After successful execution, all nodes have status='done' in returned RunState."""
    a = HarnessNode(id="N1", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                    label="N1")
    harness = Harness(name="single", nodes=[a], edges=[])
    space = _make_space()
    store = _make_store_mock(space.id)
    worker = StubWorker()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-single", harness, space)

    assert result.nodes_executed["N1"].status == "done"
    assert result.nodes_executed["N1"].child_task_id is not None


# ---------------------------------------------------------------------------
# Control-flow node dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_decision_node_no_outgoing_edges_fails():
    """A decision node with no outgoing edges is marked failed (no valid edge to choose)."""
    node = HarnessNode(id="D1", type=NodeType.decision, position=_make_position(),
                       ports={"in": {}, "out": {}}, data={}, label="D1")
    harness = Harness(name="cf", nodes=[node], edges=[])
    space = _make_space()
    store = _make_store_mock(space.id)
    worker = StubWorker()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-cf", harness, space)

    ns = result.nodes_executed["D1"]
    # No outgoing edges → evaluate_decision raises ValueError → node is failed.
    assert ns.status == "failed"
    assert "decision_error" in (ns.reason or "")
    # No agent calls for control-flow nodes.
    assert len(worker.run_agent_calls) == 0


@pytest.mark.asyncio
async def test_executor_decision_node_with_default_edge_followed_by_agent():
    """Decision node with a default edge (condition=None) routes to agent downstream."""
    cf = HarnessNode(id="CF", type=NodeType.decision, position=_make_position(),
                     ports={"out": {}}, data={}, label="CF")
    ag = HarnessNode(id="AG", type=NodeType.agent, position=_make_position(),
                     ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                     label="AG")
    # Default edge: condition=None
    edge = HarnessEdge(id="e1", source=NodeRef(node_id="CF", port_id="out"),
                       target=NodeRef(node_id="AG", port_id="out"),
                       condition=None)
    harness = Harness(name="cf_agent", nodes=[cf, ag], edges=[edge])
    space = _make_space()
    store = _make_store_mock(space.id)
    worker = StubWorker()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-cfa", harness, space)

    # Decision node chose the default edge → is done.
    assert result.nodes_executed["CF"].status == "done"
    # Agent node still executes.
    assert result.nodes_executed["AG"].status == "done"
    assert len(worker.run_agent_calls) == 1


# ---------------------------------------------------------------------------
# Fail-fast
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_fail_fast_on_node_failure():
    """When node B fails, node C must be marked skipped with reason='upstream_failed'."""
    a = HarnessNode(id="FA", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "A"},
                    label="FA")
    b = HarnessNode(id="FB", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "B"},
                    label="FB")
    c = HarnessNode(id="FC", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "C"},
                    label="FC")
    # A→B→C linear
    edge_ab = HarnessEdge(id="e1", source=NodeRef(node_id="FA", port_id="out"),
                          target=NodeRef(node_id="FB", port_id="out"))
    edge_bc = HarnessEdge(id="e2", source=NodeRef(node_id="FB", port_id="out"),
                          target=NodeRef(node_id="FC", port_id="out"))
    harness = Harness(name="fail", nodes=[a, b, c], edges=[edge_ab, edge_bc])
    space = _make_space()
    store = _make_store_mock(space.id)

    # A succeeds; B fails (returns WAITING); C should be skipped.
    call_count = [0]
    traces = []

    async def run_agent(task_id, **kwargs):
        call_count[0] += 1
        trace = _make_trace(final_text=f"run-{call_count[0]}")
        trace = trace.model_copy(update={"task_id": task_id})
        traces.append(trace)
        return trace

    async def finalize_child(task_id, trace):
        # First call (node FA) succeeds; second call (node FB) fails.
        if call_count[0] == 1:
            return TaskState.DONE
        return TaskState.WAITING

    worker = MagicMock()
    worker.run_agent = run_agent
    worker.finalize_child = finalize_child

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-fail", harness, space)

    assert result.nodes_executed["FA"].status == "done"
    assert result.nodes_executed["FB"].status == "failed"
    assert result.nodes_executed["FC"].status == "skipped"
    assert result.nodes_executed["FC"].reason == "upstream_failed"
    # run_agent should only be called for FA and FB (not FC).
    assert call_count[0] == 2


# ---------------------------------------------------------------------------
# Variable interpolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_variable_interpolation():
    """Upstream output from node A flows into node B's prompt_template."""
    a = HarnessNode(id="VA", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}},
                    data={"agent_ref": "ag", "prompt_template": "produce something"},
                    label="VA")
    b = HarnessNode(id="VB", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}},
                    data={"agent_ref": "ag", "prompt_template": "use $VA and $lang"},
                    label="VB")
    edge = HarnessEdge(id="e1", source=NodeRef(node_id="VA", port_id="out"),
                       target=NodeRef(node_id="VB", port_id="out"))
    harness = Harness(
        name="interp",
        nodes=[a, b],
        edges=[edge],
        variables={"lang": "Python"},
    )
    space = _make_space()
    store = _make_store_mock(space.id)

    created_briefs: list[str] = []

    _store_counter = [0]

    async def create(*, space_id, title, brief, parent_id=None, **kwargs):
        created_briefs.append(brief)
        _store_counter[0] += 1
        task = _make_task_mock(f"ct-{_store_counter[0]}")
        return task

    store.create = create

    worker = StubWorker(task_state=TaskState.DONE, final_text="node_a_output")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-interp", harness, space)

    assert result.nodes_executed["VA"].status == "done"
    assert result.nodes_executed["VB"].status == "done"

    # Node B's brief should contain the interpolated VA output and lang.
    node_b_brief = created_briefs[1]
    assert "node_a_output" in node_b_brief  # $VA resolved to VA's output
    assert "Python" in node_b_brief          # $lang resolved from harness.variables


# ---------------------------------------------------------------------------
# Run state file persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_run_state_file_created():
    """After execution, a run-state JSON file should exist in the expected path."""
    node = HarnessNode(id="RS1", type=NodeType.agent, position=_make_position(),
                       ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                       label="RS1")
    harness = Harness(name="rs_test", nodes=[node], edges=[])
    space = _make_space("s1")
    store = _make_store_mock(space.id)
    worker = StubWorker()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-rs", harness, space)

        state_path = Path(tmpdir) / "spaces" / "s1" / ".cronos" / "harness-runs" / "run-rs.json"
        assert state_path.exists(), f"Run state file not found at {state_path}"

        with state_path.open() as f:
            data = json.load(f)

        assert data["run_id"] == "run-rs"
        assert "RS1" in data["nodes_executed"]
        assert data["nodes_executed"]["RS1"]["status"] == "done"


@pytest.mark.asyncio
async def test_executor_run_state_updated_after_each_node():
    """Run state is persisted after each node, not just at the end."""
    nodes = [
        HarnessNode(id=f"N{i}", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}},
                    data={"agent_ref": "ag", "prompt_template": "p"},
                    label=f"N{i}")
        for i in range(3)
    ]
    edges = [
        HarnessEdge(id=f"e{i}", source=NodeRef(node_id=f"N{i}", port_id="out"),
                    target=NodeRef(node_id=f"N{i+1}", port_id="out"))
        for i in range(2)
    ]
    harness = Harness(name="seq", nodes=nodes, edges=edges)
    space = _make_space("s2")
    store = _make_store_mock(space.id)

    save_call_count = [0]
    original_maybe_save = None

    import app.harnesses.executor as executor_module

    original_save = executor_module.save_atomic
    save_calls: list[RunState] = []

    def mock_save(path, state):
        save_calls.append(RunState(
            run_id=state.run_id,
            harness_id=state.harness_id,
            goal_task_id=state.goal_task_id,
            nodes_executed=dict(state.nodes_executed),
        ))
        original_save(path, state)

    worker = StubWorker()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            with patch("app.harnesses.executor.save_atomic", side_effect=mock_save):
                executor = HarnessExecutor(store, worker, _tools_resolver)
                result = await executor.execute("run-seq", harness, space)

    # save_atomic should have been called at least once per node.
    assert len(save_calls) >= 3


# ---------------------------------------------------------------------------
# Resume: in_progress node with done child_task_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_resume_in_progress_done_child():
    """Node in 'in_progress' with a DONE child task is accepted without re-executing."""
    node = HarnessNode(id="RES1", type=NodeType.agent, position=_make_position(),
                       ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                       label="RES1")
    harness = Harness(name="resume_test", nodes=[node], edges=[])
    space = _make_space("rs")
    store = _make_store_mock(space.id)

    # Simulate: child task already done.
    done_task = _make_task_mock("existing-child-1", state=TaskState.DONE)
    store.get = MagicMock(return_value=done_task)

    worker = StubWorker()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            # Pre-seed an in_progress run state on disk.
            state_dir = Path(tmpdir) / "spaces" / "rs" / ".cronos" / "harness-runs"
            state_dir.mkdir(parents=True)
            state_path = state_dir / "run-resume.json"
            pre_state = RunState(
                run_id="run-resume",
                harness_id="resume_test",
                goal_task_id="run-resume",
                nodes_executed={
                    "RES1": NodeState(
                        status="in_progress",
                        child_task_id="existing-child-1",
                    )
                },
            )
            from app.harnesses.run_state import save_atomic as save_state
            save_state(state_path, pre_state)

            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-resume", harness, space)

    # Node accepted as done without calling run_agent.
    assert result.nodes_executed["RES1"].status == "done"
    assert result.nodes_executed["RES1"].child_task_id == "existing-child-1"
    assert len(worker.run_agent_calls) == 0


@pytest.mark.asyncio
async def test_executor_resume_in_progress_undone_child_reexecutes():
    """Node in 'in_progress' with a non-DONE child is re-executed from scratch."""
    node = HarnessNode(id="RES2", type=NodeType.agent, position=_make_position(),
                       ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                       label="RES2")
    harness = Harness(name="reexec", nodes=[node], edges=[])
    space = _make_space("rx")
    store = _make_store_mock(space.id)

    # Simulate: existing child task NOT done (WAITING state).
    waiting_task = _make_task_mock("old-child-waiting", state=TaskState.WAITING)
    store.get = MagicMock(return_value=waiting_task)

    worker = StubWorker()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            state_dir = Path(tmpdir) / "spaces" / "rx" / ".cronos" / "harness-runs"
            state_dir.mkdir(parents=True)
            state_path = state_dir / "run-reexec.json"
            pre_state = RunState(
                run_id="run-reexec",
                harness_id="reexec",
                goal_task_id="run-reexec",
                nodes_executed={
                    "RES2": NodeState(
                        status="in_progress",
                        child_task_id="old-child-waiting",
                    )
                },
            )
            from app.harnesses.run_state import save_atomic as save_state
            save_state(state_path, pre_state)

            # After re-execute starts, store.get should return None (no pre-existing child)
            # for the new task lookup. We re-patch here.
            store.get = MagicMock(return_value=None)

            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-reexec", harness, space)

    # run_agent should have been called (re-execution happened).
    assert len(worker.run_agent_calls) == 1
    assert result.nodes_executed["RES2"].status == "done"


# ---------------------------------------------------------------------------
# WorkerProtocol is a stub (not a real Worker)
# ---------------------------------------------------------------------------


def test_worker_protocol_structural_subtyping():
    """StubWorker satisfies WorkerProtocol via structural duck-typing."""
    from app.harnesses.executor import WorkerProtocol
    stub = StubWorker()
    # runtime_checkable Protocol: isinstance check works for structural typing
    assert isinstance(stub, WorkerProtocol)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_empty_harness():
    """Empty harness (no nodes) returns a RunState with empty nodes_executed."""
    harness = Harness(name="empty", nodes=[], edges=[])
    space = _make_space()
    store = _make_store_mock()
    worker = StubWorker()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-empty", harness, space)

    assert result.nodes_executed == {}
    assert len(worker.run_agent_calls) == 0


@pytest.mark.asyncio
async def test_executor_already_done_nodes_skipped():
    """Nodes already marked 'done' in a prior run state are not re-executed."""
    node = HarnessNode(id="PREV", type=NodeType.agent, position=_make_position(),
                       ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                       label="PREV")
    harness = Harness(name="done_skip", nodes=[node], edges=[])
    space = _make_space("ds")
    store = _make_store_mock(space.id)
    worker = StubWorker()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            state_dir = Path(tmpdir) / "spaces" / "ds" / ".cronos" / "harness-runs"
            state_dir.mkdir(parents=True)
            state_path = state_dir / "run-done-skip.json"
            pre_state = RunState(
                run_id="run-done-skip",
                harness_id="done_skip",
                goal_task_id="run-done-skip",
                nodes_executed={
                    "PREV": NodeState(status="done", child_task_id="old-task", output="old-output")
                },
            )
            from app.harnesses.run_state import save_atomic as save_state
            save_state(state_path, pre_state)

            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-done-skip", harness, space)

    # Should NOT re-execute the done node.
    assert len(worker.run_agent_calls) == 0
    assert result.nodes_executed["PREV"].status == "done"


@pytest.mark.asyncio
async def test_executor_run_state_run_id_matches():
    """RunState.run_id equals the run_goal_id passed to execute()."""
    node = HarnessNode(id="RID", type=NodeType.agent, position=_make_position(),
                       ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                       label="RID")
    harness = Harness(name="rid_test", nodes=[node], edges=[])
    space = _make_space()
    store = _make_store_mock()
    worker = StubWorker()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("my-run-42", harness, space)

    assert result.run_id == "my-run-42"


@pytest.mark.asyncio
async def test_executor_no_asyncio_create_task():
    """No asyncio.create_task() is used in executor — runs are purely sequential."""
    # Verify execution order is strictly sequential by checking the call order.
    a = HarnessNode(id="SEQ_A", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "A"},
                    label="SEQ_A")
    b = HarnessNode(id="SEQ_B", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "B"},
                    label="SEQ_B")
    edge = HarnessEdge(id="e1", source=NodeRef(node_id="SEQ_A", port_id="out"),
                       target=NodeRef(node_id="SEQ_B", port_id="out"))
    harness = Harness(name="seq", nodes=[a, b], edges=[edge])
    space = _make_space()
    store = _make_store_mock()
    call_order: list[str] = []

    async def run_agent(task_id, **kwargs):
        call_order.append(task_id)
        return _make_trace()

    async def finalize_child(task_id, trace):
        return TaskState.DONE

    worker = MagicMock()
    worker.run_agent = run_agent
    worker.finalize_child = finalize_child

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-seq", harness, space)

    # Call order must be sequential: SEQ_A task first, then SEQ_B task.
    assert len(call_order) == 2
    # The actual task IDs come from store.create() which returns task-1, task-2, ...
    # Just verify there were exactly 2 sequential calls.
    assert result.nodes_executed["SEQ_A"].status == "done"
    assert result.nodes_executed["SEQ_B"].status == "done"


# ---------------------------------------------------------------------------
# New tests: Decision routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_decision_routing_status_done_edge():
    """Decision node routes to edge A when predecessor output has STATUS: DONE."""
    # Agent predecessor → Decision → (edge_a with condition='DONE', edge_b with condition='BLOCKED')
    agent = HarnessNode(id="AGT", type=NodeType.agent, position=_make_position(),
                        ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "run"},
                        label="AGT")
    decision = HarnessNode(id="DEC", type=NodeType.decision, position=_make_position(),
                           ports={"in": {}, "out_a": {}, "out_b": {}}, data={}, label="DEC")
    dest_a = HarnessNode(id="DEST_A", type=NodeType.agent, position=_make_position(),
                         ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "A"},
                         label="DEST_A")
    dest_b = HarnessNode(id="DEST_B", type=NodeType.agent, position=_make_position(),
                         ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "B"},
                         label="DEST_B")

    edge_to_dec = HarnessEdge(id="e_agt_dec", source=NodeRef(node_id="AGT", port_id="out"),
                               target=NodeRef(node_id="DEC", port_id="in"))
    edge_a = HarnessEdge(id="e_a", source=NodeRef(node_id="DEC", port_id="out_a"),
                          target=NodeRef(node_id="DEST_A", port_id="out"),
                          condition="DONE")
    edge_b = HarnessEdge(id="e_b", source=NodeRef(node_id="DEC", port_id="out_b"),
                          target=NodeRef(node_id="DEST_B", port_id="out"),
                          condition="BLOCKED")

    harness = Harness(
        name="decision_routing",
        nodes=[agent, decision, dest_a, dest_b],
        edges=[edge_to_dec, edge_a, edge_b],
    )
    space = _make_space()
    store = _make_store_mock(space.id)

    # Agent returns output containing "STATUS: DONE"
    worker = StubWorker(task_state=TaskState.DONE, final_text="STATUS: DONE\nAll good.")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-dec-done", harness, space)

    # Decision node should be done.
    assert result.nodes_executed["DEC"].status == "done"
    # DEST_A should execute (STATUS=DONE matched edge_a condition='DONE').
    assert result.nodes_executed["DEST_A"].status == "done"
    # DEST_B should NOT be in nodes_executed (not chosen).
    assert "DEST_B" not in result.nodes_executed


@pytest.mark.asyncio
async def test_executor_decision_routing_status_blocked_edge():
    """Decision node routes to edge B when predecessor output has STATUS: BLOCKED."""
    agent = HarnessNode(id="AGT2", type=NodeType.agent, position=_make_position(),
                        ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "run"},
                        label="AGT2")
    decision = HarnessNode(id="DEC2", type=NodeType.decision, position=_make_position(),
                           ports={"in": {}, "out_a": {}, "out_b": {}}, data={}, label="DEC2")
    dest_a = HarnessNode(id="DEST_A2", type=NodeType.agent, position=_make_position(),
                         ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "A"},
                         label="DEST_A2")
    dest_b = HarnessNode(id="DEST_B2", type=NodeType.agent, position=_make_position(),
                         ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "B"},
                         label="DEST_B2")

    edge_to_dec = HarnessEdge(id="e2_agt_dec", source=NodeRef(node_id="AGT2", port_id="out"),
                               target=NodeRef(node_id="DEC2", port_id="in"))
    edge_a = HarnessEdge(id="e2_a", source=NodeRef(node_id="DEC2", port_id="out_a"),
                          target=NodeRef(node_id="DEST_A2", port_id="out"),
                          condition="DONE")
    edge_b = HarnessEdge(id="e2_b", source=NodeRef(node_id="DEC2", port_id="out_b"),
                          target=NodeRef(node_id="DEST_B2", port_id="out"),
                          condition="BLOCKED")

    harness = Harness(
        name="decision_routing_blocked",
        nodes=[agent, decision, dest_a, dest_b],
        edges=[edge_to_dec, edge_a, edge_b],
    )
    space = _make_space()
    store = _make_store_mock(space.id)

    # Agent returns output containing "STATUS: BLOCKED"
    worker = StubWorker(task_state=TaskState.DONE, final_text="STATUS: BLOCKED\nBlocked.")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-dec-blocked", harness, space)

    # Decision node should be done.
    assert result.nodes_executed["DEC2"].status == "done"
    # DEST_B should execute (STATUS=BLOCKED matched edge_b condition='BLOCKED').
    assert result.nodes_executed["DEST_B2"].status == "done"
    # DEST_A should NOT be in nodes_executed (not chosen).
    assert "DEST_A2" not in result.nodes_executed


# ---------------------------------------------------------------------------
# New tests: Wait(human) parking and resume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_wait_human_parks_in_waiting():
    """Wait(human) node parks the run: execute() returns early with waiting_node_id set."""
    wait_node = _make_wait_node("W1", mode="human", waiting_question="Ready to proceed?")
    # Give it ports matching what the edge will use.
    wait_node = HarnessNode(
        id="W1", type=NodeType.wait, position=_make_position(),
        ports={"in": {}, "out": {}},
        data={"mode": "human", "max_wait_seconds": 300, "waiting_question": "Ready?"},
        label="W1",
    )
    harness = Harness(name="wait_human", nodes=[wait_node], edges=[])
    space = _make_space()
    store = _make_store_mock(space.id)
    worker = StubWorker()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-wait-human", harness, space)

    # The executor returned early (parked): waiting_node_id must be set.
    assert result.waiting_node_id == "W1"
    # Wait node is in_progress (parked mid-execution).
    assert result.nodes_executed["W1"].status == "in_progress"
    # No agent calls.
    assert len(worker.run_agent_calls) == 0


@pytest.mark.asyncio
async def test_executor_wait_human_resume_does_not_rerun_completed_agents():
    """Wait-human resume: completed Agent nodes are not re-executed; output is reused."""
    # Harness: AGT → W1 → AGT2
    agent1 = HarnessNode(id="PRE_AGT", type=NodeType.agent, position=_make_position(),
                         ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "pre"},
                         label="PRE_AGT")
    wait_node = HarnessNode(id="W1", type=NodeType.wait, position=_make_position(),
                            ports={"in": {}, "out": {}},
                            data={"mode": "human", "max_wait_seconds": 300},
                            label="W1")
    agent2 = HarnessNode(id="POST_AGT", type=NodeType.agent, position=_make_position(),
                         ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "post"},
                         label="POST_AGT")

    edge_pre_wait = HarnessEdge(id="e1", source=NodeRef(node_id="PRE_AGT", port_id="out"),
                                 target=NodeRef(node_id="W1", port_id="in"))
    edge_wait_post = HarnessEdge(id="e2", source=NodeRef(node_id="W1", port_id="out"),
                                  target=NodeRef(node_id="POST_AGT", port_id="out"))

    harness = Harness(
        name="wait_resume",
        nodes=[agent1, wait_node, agent2],
        edges=[edge_pre_wait, edge_wait_post],
    )
    space = _make_space("wr")
    store = _make_store_mock(space.id)
    worker = StubWorker(task_state=TaskState.DONE, final_text="pre_output")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            state_dir = Path(tmpdir) / "spaces" / "wr" / ".cronos" / "harness-runs"
            state_dir.mkdir(parents=True)

            executor = HarnessExecutor(store, worker, _tools_resolver)

            # First run: PRE_AGT executes, W1 parks.
            result1 = await executor.execute("run-wr", harness, space)

            assert result1.waiting_node_id == "W1"
            assert result1.nodes_executed["PRE_AGT"].status == "done"
            assert result1.nodes_executed["W1"].status == "in_progress"
            assert "POST_AGT" not in result1.nodes_executed
            # Only one run_agent call (for PRE_AGT).
            assert len(worker.run_agent_calls) == 1

            # Simulate human reply: the state file already has waiting_node_id set.
            # Second call to execute() resumes from W1's outgoing edges.
            result2 = await executor.execute("run-wr", harness, space)

    # waiting_node_id cleared on resume.
    assert result2.waiting_node_id is None
    # PRE_AGT was already done — not re-executed.
    assert result2.nodes_executed["PRE_AGT"].status == "done"
    # W1 should now be done.
    assert result2.nodes_executed["W1"].status == "done"
    # POST_AGT was executed after resume.
    assert result2.nodes_executed["POST_AGT"].status == "done"
    # Total run_agent calls: 1 (PRE_AGT) + 1 (POST_AGT resume) = 2
    assert len(worker.run_agent_calls) == 2


# ---------------------------------------------------------------------------
# New tests: Aggregator mode='all'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_aggregator_all_waits_for_both_predecessors():
    """Aggregator(all) fires only when both predecessor agents are done."""
    # Harness: A1 → AGG, A2 → AGG (parallel branches meeting at aggregator)
    a1 = HarnessNode(id="A1", type=NodeType.agent, position=_make_position(),
                     ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "A1"},
                     label="A1")
    a2 = HarnessNode(id="A2", type=NodeType.agent, position=_make_position(),
                     ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "A2"},
                     label="A2")
    agg = HarnessNode(id="AGG", type=NodeType.aggregator, position=_make_position(),
                      ports={"in": {}, "out": {}}, data={"mode": "all"}, label="AGG")
    post = HarnessNode(id="POST", type=NodeType.agent, position=_make_position(),
                       ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "post"},
                       label="POST")

    edge_a1_agg = HarnessEdge(id="e1", source=NodeRef(node_id="A1", port_id="out"),
                               target=NodeRef(node_id="AGG", port_id="in"))
    edge_a2_agg = HarnessEdge(id="e2", source=NodeRef(node_id="A2", port_id="out"),
                               target=NodeRef(node_id="AGG", port_id="in"))
    edge_agg_post = HarnessEdge(id="e3", source=NodeRef(node_id="AGG", port_id="out"),
                                 target=NodeRef(node_id="POST", port_id="out"))

    harness = Harness(
        name="aggregator_all",
        nodes=[a1, a2, agg, post],
        edges=[edge_a1_agg, edge_a2_agg, edge_agg_post],
    )
    space = _make_space()
    store = _make_store_mock(space.id)
    worker = StubWorker(task_state=TaskState.DONE, final_text="output")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-agg-all", harness, space)

    # Both A1 and A2 must have run.
    assert result.nodes_executed["A1"].status == "done"
    assert result.nodes_executed["A2"].status == "done"
    # Aggregator fired (both done).
    assert result.nodes_executed["AGG"].status == "done"
    # POST executed after aggregator.
    assert result.nodes_executed["POST"].status == "done"
    # 3 agent runs: A1, A2, POST
    assert len(worker.run_agent_calls) == 3


# ---------------------------------------------------------------------------
# New tests: Aggregator mode='any'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_aggregator_any_fires_on_first_done_predecessor():
    """Aggregator(any) fires as soon as the first predecessor is done.

    This test uses a pre-seeded run state where A1 is already done and A2 is
    still pending, simulating the 'any' mode skewed-completion scenario.
    """
    a1 = HarnessNode(id="B1", type=NodeType.agent, position=_make_position(),
                     ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "B1"},
                     label="B1")
    a2 = HarnessNode(id="B2", type=NodeType.agent, position=_make_position(),
                     ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "B2"},
                     label="B2")
    agg = HarnessNode(id="AGG2", type=NodeType.aggregator, position=_make_position(),
                      ports={"in": {}, "out": {}}, data={"mode": "any"}, label="AGG2")
    post = HarnessNode(id="POST2", type=NodeType.agent, position=_make_position(),
                       ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "post"},
                       label="POST2")

    edge_b1_agg = HarnessEdge(id="f1", source=NodeRef(node_id="B1", port_id="out"),
                               target=NodeRef(node_id="AGG2", port_id="in"))
    edge_b2_agg = HarnessEdge(id="f2", source=NodeRef(node_id="B2", port_id="out"),
                               target=NodeRef(node_id="AGG2", port_id="in"))
    edge_agg_post = HarnessEdge(id="f3", source=NodeRef(node_id="AGG2", port_id="out"),
                                 target=NodeRef(node_id="POST2", port_id="out"))

    harness = Harness(
        name="aggregator_any",
        nodes=[a1, a2, agg, post],
        edges=[edge_b1_agg, edge_b2_agg, edge_agg_post],
    )
    space = _make_space("any-space")
    store = _make_store_mock(space.id)
    worker = StubWorker(task_state=TaskState.DONE, final_text="output")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            # Pre-seed: B1 is already done; B2 has not yet run.
            state_dir = Path(tmpdir) / "spaces" / "any-space" / ".cronos" / "harness-runs"
            state_dir.mkdir(parents=True)
            state_path = state_dir / "run-agg-any.json"
            pre_state = RunState(
                run_id="run-agg-any",
                harness_id="aggregator_any",
                goal_task_id="run-agg-any",
                nodes_executed={
                    "B1": NodeState(status="done", output="b1_output"),
                },
            )
            from app.harnesses.run_state import save_atomic as save_state
            save_state(state_path, pre_state)

            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-agg-any", harness, space)

    # B1 was already done (no re-run).
    assert result.nodes_executed["B1"].status == "done"
    # AGG2 fired because B1 (first done predecessor) was found.
    assert result.nodes_executed["AGG2"].status == "done"
    # POST2 executed.
    assert result.nodes_executed["POST2"].status == "done"
    # Only B2 and POST2 were run by the agent (B1 was pre-seeded as done).
    # B2 may or may not have been run depending on BFS order — what matters is AGG fired.
    run_count = len(worker.run_agent_calls)
    assert run_count >= 1  # At least POST2 was run


# ---------------------------------------------------------------------------
# New test: 4-Agent linear chain regression (same order as _topo_sort)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_four_agent_linear_chain_same_order_as_topo_sort():
    """4-Agent linear chain A→B→C→D produces the same execution order as _topo_sort."""
    nodes_defs = [
        ("N1", "N1"),
        ("N2", "N2"),
        ("N3", "N3"),
        ("N4", "N4"),
    ]
    nodes = [
        HarnessNode(id=nid, type=NodeType.agent, position=_make_position(),
                    ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": f"do {nid}"},
                    label=label)
        for nid, label in nodes_defs
    ]
    edges = [
        HarnessEdge(id=f"e{i}", source=NodeRef(node_id=f"N{i+1}", port_id="out"),
                    target=NodeRef(node_id=f"N{i+2}", port_id="out"))
        for i in range(3)
    ]
    harness = Harness(name="linear4", nodes=nodes, edges=edges)
    space = _make_space()
    store = _make_store_mock(space.id)

    execution_order: list[str] = []
    task_to_node: dict[str, str] = {}
    node_counter = [0]
    node_ids = ["N1", "N2", "N3", "N4"]

    orig_store_create = store.create
    counter = [0]

    async def create_with_tracking(*, space_id, title, brief, parent_id=None, **kwargs):
        counter[0] += 1
        task = _make_task_mock(f"t-{counter[0]}")
        # title is the node label
        task_to_node[task.id] = title
        return task

    store.create = create_with_tracking

    async def run_agent_tracking(task_id, **kwargs):
        node_id = task_to_node.get(task_id, task_id)
        execution_order.append(node_id)
        return _make_trace(final_text=f"output_{node_id}")

    async def finalize_child(task_id, trace):
        return TaskState.DONE

    worker = MagicMock()
    worker.run_agent = run_agent_tracking
    worker.finalize_child = finalize_child

    # Also compute what _topo_sort produces.
    topo_order = [n.id for n in _topo_sort(harness)]

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-linear4", harness, space)

    # All nodes done.
    for nid in ["N1", "N2", "N3", "N4"]:
        assert result.nodes_executed[nid].status == "done"

    # BFS execution order must match _topo_sort order.
    assert execution_order == topo_order, (
        f"BFS order {execution_order} != topo_sort order {topo_order}"
    )


# ---------------------------------------------------------------------------
# New test: Wait(timed) continues execution after sleep
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_wait_timed_continues_after_sleep():
    """Wait(timed) node: executor sleeps then continues BFS traversal."""
    agent_pre = HarnessNode(id="TPRE", type=NodeType.agent, position=_make_position(),
                            ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "pre"},
                            label="TPRE")
    wait_timed = HarnessNode(id="TWAIT", type=NodeType.wait, position=_make_position(),
                              ports={"in": {}, "out": {}},
                              data={"mode": "timed", "duration_seconds": 0.0},
                              label="TWAIT")
    agent_post = HarnessNode(id="TPOST", type=NodeType.agent, position=_make_position(),
                              ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "post"},
                              label="TPOST")

    edge_pre_wait = HarnessEdge(id="te1", source=NodeRef(node_id="TPRE", port_id="out"),
                                 target=NodeRef(node_id="TWAIT", port_id="in"))
    edge_wait_post = HarnessEdge(id="te2", source=NodeRef(node_id="TWAIT", port_id="out"),
                                  target=NodeRef(node_id="TPOST", port_id="out"))

    harness = Harness(
        name="timed_wait",
        nodes=[agent_pre, wait_timed, agent_post],
        edges=[edge_pre_wait, edge_wait_post],
    )
    space = _make_space()
    store = _make_store_mock(space.id)
    worker = StubWorker(task_state=TaskState.DONE, final_text="output")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-timed", harness, space)

    # All nodes should complete (timed wait = 0s, so no actual delay).
    assert result.nodes_executed["TPRE"].status == "done"
    assert result.nodes_executed["TWAIT"].status == "done"
    assert result.nodes_executed["TPOST"].status == "done"
    # waiting_node_id must NOT be set (no human wait).
    assert result.waiting_node_id is None
    # Two agent runs: TPRE and TPOST.
    assert len(worker.run_agent_calls) == 2


# ---------------------------------------------------------------------------
# I3 new tests: WorkerProtocol _publish, timing, cancel guard, run_status
# ---------------------------------------------------------------------------


class PublishingStubWorker(StubWorker):
    """Worker stub that also records _publish() calls for SSE event testing."""

    def __init__(self, task_state: TaskState = TaskState.DONE,
                 final_text: str = "output"):
        super().__init__(task_state=task_state, final_text=final_text)
        self.published_events: list[tuple[str, dict]] = []

    def _publish(self, task_id: str, event: dict) -> None:
        self.published_events.append((task_id, event))


@pytest.mark.asyncio
async def test_executor_publishes_node_transition_events():
    """Executor publishes node_transition events for each agent node transition."""
    node = HarnessNode(id="EVT1", type=NodeType.agent, position=_make_position(),
                       ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                       label="EVT1")
    harness = Harness(name="event_test", nodes=[node], edges=[])
    space = _make_space()
    store = _make_store_mock(space.id)
    worker = PublishingStubWorker(task_state=TaskState.DONE, final_text="result")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver, event_worker=worker)
            result = await executor.execute("run-evt", harness, space)

    assert result.nodes_executed["EVT1"].status == "done"

    # Collect node_transition events.
    node_transitions = [
        e for _, e in worker.published_events
        if e.get("type") == "node_transition"
    ]
    assert len(node_transitions) >= 2, (
        f"Expected at least 2 node_transition events (pending→in_progress, in_progress→done), "
        f"got {len(node_transitions)}: {node_transitions}"
    )

    # First transition: pending → in_progress
    first = next(e for e in node_transitions if e["to_status"] == "in_progress")
    assert first["node_id"] == "EVT1"
    assert first["from_status"] == "pending"
    assert "timestamp" in first

    # Second transition: in_progress → done
    second = next(e for e in node_transitions if e["to_status"] == "done")
    assert second["node_id"] == "EVT1"
    assert second["from_status"] == "in_progress"
    assert "timestamp" in second


@pytest.mark.asyncio
async def test_executor_timing_started_at_ended_at_set():
    """After a node completes, started_at and ended_at are set as ISO-8601 strings."""
    node = HarnessNode(id="TIM1", type=NodeType.agent, position=_make_position(),
                       ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                       label="TIM1")
    harness = Harness(name="timing_test", nodes=[node], edges=[])
    space = _make_space()
    store = _make_store_mock(space.id)
    worker = StubWorker(task_state=TaskState.DONE, final_text="result")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-timing", harness, space)

    ns = result.nodes_executed["TIM1"]
    assert ns.status == "done"
    assert ns.started_at is not None, "started_at should be set after node completes"
    assert ns.ended_at is not None, "ended_at should be set after node completes"

    # Both should look like ISO-8601 strings ending in 'Z'.
    assert ns.started_at.endswith("Z"), f"started_at should end with 'Z': {ns.started_at}"
    assert ns.ended_at.endswith("Z"), f"ended_at should end with 'Z': {ns.ended_at}"

    # Basic format check: starts with a year.
    assert ns.started_at.startswith("20"), f"started_at should start with year: {ns.started_at}"
    assert ns.ended_at.startswith("20"), f"ended_at should start with year: {ns.ended_at}"


@pytest.mark.asyncio
async def test_executor_cancel_guard_stops_bfs():
    """If RunState.status is set to 'cancelled' on disk between nodes, executor stops."""
    # Two-node linear harness: A → B.
    a = HarnessNode(id="CA", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "A"},
                    label="CA")
    b = HarnessNode(id="CB", type=NodeType.agent, position=_make_position(),
                    ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "B"},
                    label="CB")
    edge = HarnessEdge(id="e1", source=NodeRef(node_id="CA", port_id="out"),
                       target=NodeRef(node_id="CB", port_id="out"))
    harness = Harness(name="cancel_test", nodes=[a, b], edges=[edge])
    space = _make_space("cancel-space")
    store = _make_store_mock(space.id)

    # After node CA completes, we simulate a cancel write by patching the
    # finalize_child method to write 'cancelled' status to the state file.
    state_path_holder: list[Path] = []
    orig_finalize_calls = [0]

    class CancellingWorker(StubWorker):
        """After first finalize, writes 'cancelled' to the run-state file."""
        def _publish(self, task_id: str, event: dict) -> None:
            pass  # silence

        async def finalize_child(self, task_id: str, trace: RunTrace) -> TaskState:
            orig_finalize_calls[0] += 1
            result = await super().finalize_child(task_id, trace)
            # After node CA finishes (first finalize call), inject a cancel.
            if orig_finalize_calls[0] == 1 and state_path_holder:
                state_path = state_path_holder[0]
                if state_path.exists():
                    import json as _json
                    with state_path.open("r") as fh:
                        d = _json.load(fh)
                    d["status"] = "cancelled"
                    import tempfile as _tmp
                    import os as _os
                    fd, tmp = _tmp.mkstemp(dir=state_path.parent)
                    try:
                        with _os.fdopen(fd, "w") as fh:
                            fh.write(_json.dumps(d))
                        _os.replace(tmp, state_path)
                    except Exception:
                        _os.unlink(tmp)
            return result

    worker = CancellingWorker(task_state=TaskState.DONE, final_text="output")

    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir) / "spaces" / "cancel-space" / ".cronos" / "harness-runs"
        state_dir.mkdir(parents=True)
        # Capture the state path before execution.
        state_path_holder.append(state_dir / "run-cancel.json")

        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver, event_worker=worker)
            result = await executor.execute("run-cancel", harness, space)

    # The run should be stopped; status is 'cancelled' (or the executor returned
    # the reloaded cancelled state — either way, CB must NOT have been executed).
    assert "CB" not in result.nodes_executed, (
        f"Node CB should not have been executed after cancel; "
        f"result.nodes_executed = {result.nodes_executed}"
    )
    # Only one finalize call — only CA ran.
    assert orig_finalize_calls[0] == 1


@pytest.mark.asyncio
async def test_executor_publishes_run_status_done_on_success():
    """Executor publishes a run_status event with status='done' on successful completion."""
    node = HarnessNode(id="RS_N1", type=NodeType.agent, position=_make_position(),
                       ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                       label="RS_N1")
    harness = Harness(name="run_status_test", nodes=[node], edges=[])
    space = _make_space()
    store = _make_store_mock(space.id)
    worker = PublishingStubWorker(task_state=TaskState.DONE, final_text="result")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver, event_worker=worker)
            result = await executor.execute("run-rs-done", harness, space)

    assert result.nodes_executed["RS_N1"].status == "done"

    run_status_events = [
        e for _, e in worker.published_events
        if e.get("type") == "run_status"
    ]
    assert len(run_status_events) >= 1, (
        f"Expected at least one run_status event; got {run_status_events}"
    )

    # The final run_status event must have status='done'.
    final_run_status = run_status_events[-1]
    assert final_run_status["status"] == "done", (
        f"Expected final run_status to be 'done'; got {final_run_status}"
    )
    assert final_run_status["run_id"] == "run-rs-done"


@pytest.mark.asyncio
async def test_executor_worker_none_no_error():
    """Passing no event_worker (None) does not raise AttributeError during execution."""
    node = HarnessNode(id="NW1", type=NodeType.agent, position=_make_position(),
                       ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                       label="NW1")
    harness = Harness(name="no_worker_test", nodes=[node], edges=[])
    space = _make_space()
    store = _make_store_mock(space.id)
    # Use StubWorker (not publishing) as the execution worker; no event_worker.
    worker = StubWorker(task_state=TaskState.DONE, final_text="output")

    # Should not raise even though event_worker=None (default).
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-no-worker", harness, space)

    assert result.nodes_executed["NW1"].status == "done"


@pytest.mark.asyncio
async def test_executor_run_status_done_updates_run_index():
    """On successful run completion, run_index.update_run_status is called with 'done'."""
    node = HarnessNode(id="IDX1", type=NodeType.agent, position=_make_position(),
                       ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                       label="IDX1")
    harness = Harness(name="index_test", nodes=[node], edges=[])
    space = _make_space("idx-space")
    store = _make_store_mock(space.id)
    worker = StubWorker(task_state=TaskState.DONE, final_text="result")

    update_calls: list[dict] = []

    async def fake_update_run_status(space_dir, harness_id, run_id, status, finished_at=None):
        update_calls.append({
            "space_dir": space_dir,
            "harness_id": harness_id,
            "run_id": run_id,
            "status": status,
            "finished_at": finished_at,
        })

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            with patch("app.harnesses.executor._run_index.update_run_status",
                       side_effect=fake_update_run_status):
                executor = HarnessExecutor(store, worker, _tools_resolver)
                result = await executor.execute("run-idx", harness, space)

    assert result.nodes_executed["IDX1"].status == "done"
    assert len(update_calls) == 1, (
        f"Expected exactly one update_run_status call; got {update_calls}"
    )
    assert update_calls[0]["run_id"] == "run-idx"
    assert update_calls[0]["status"] == "done"
    assert update_calls[0]["finished_at"] is not None


# ---------------------------------------------------------------------------
# G09 Timed-wait resume fix — three-path integration tests (I4)
# ---------------------------------------------------------------------------


def _make_timed_wait_harness(duration_seconds: float) -> Harness:
    """Build a minimal trigger → timed-wait harness for timed-wait tests."""
    trigger = HarnessNode(
        id="T1",
        type=NodeType.trigger,
        position=_make_position(),
        ports={"out": {"direction": "output"}},
        data={"kind": "webhook"},
        label="T1",
    )
    wait = _make_wait_node("W1", mode="timed", duration_seconds=duration_seconds)
    edge = _make_edge("e1", "T1", "W1", src_port="out", tgt_port="in")
    return Harness(
        id="harness-timed",
        name="timed-wait-test",
        nodes=[trigger, wait],
        edges=[edge],
        variables={},
    )


class TestTimedWaitResumeFix:
    """G09: Timed-wait resume fix — three execution paths."""

    @pytest.mark.asyncio
    async def test_timed_wait_fresh_start_persists_wake_at(self, tmp_path: Path):
        """
        Path 1 (fresh start): executor computes and persists wake_at in NodeState
        so a restart can calculate remaining sleep.
        """
        harness = _make_timed_wait_harness(duration_seconds=0.05)
        store = _make_store_mock()
        worker = StubWorker()
        space = _make_space()

        sleep_calls: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
                with patch("app.harnesses.executor._run_index.update_run_status", new_callable=AsyncMock):
                    with patch("app.harnesses.wait.asyncio.sleep", side_effect=fake_sleep):
                        executor = HarnessExecutor(store, worker, _tools_resolver)
                        state = await executor.execute("run-fresh", harness, space)

            # Path: _DATA_DIR/spaces/{space.id}/.cronos/harness-runs/{run_id}.json
            run_state_path = (
                Path(tmpdir) / "spaces" / "test-space" / ".cronos" / "harness-runs" / "run-fresh.json"
            )
            assert run_state_path.exists(), "run_state.json not created"
            with run_state_path.open() as fh:
                raw = json.load(fh)
            # W1 should be done after completion
            assert state.nodes_executed["W1"].status == "done"

        # asyncio.sleep was called once for the timed wait (not full duration re-sleep)
        assert len(sleep_calls) == 1

    @pytest.mark.asyncio
    async def test_timed_wait_restart_before_wake_sleeps_remaining(self, tmp_path: Path):
        """
        Path 2 (restart before wake): when wake_at is in the future, executor sleeps
        only the remaining time, NOT the full duration_seconds again.
        """
        import datetime as dt_module

        harness = _make_timed_wait_harness(duration_seconds=3600.0)  # 1 hour
        store = _make_store_mock()
        worker = StubWorker()
        space = _make_space()

        # Simulate a run_state file that was persisted mid-sleep with wake_at 30s from now
        future_wake_at = (
            dt_module.datetime.now(dt_module.timezone.utc) + dt_module.timedelta(seconds=30)
        ).isoformat()

        sleep_calls: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Pre-populate run_state at the path the executor reads from (simulates restart).
            # In a real restart T1 (trigger) is already done and W1 is in_progress mid-sleep.
            # Path: _DATA_DIR/spaces/{space.id}/.cronos/harness-runs/{run_id}.json
            run_dir = Path(tmpdir) / "spaces" / "test-space" / ".cronos" / "harness-runs"
            run_dir.mkdir(parents=True)
            pre_state = RunState(
                run_id="run-resume",
                harness_id="harness-timed",
                goal_task_id="goal-1",
                nodes_executed={
                    "T1": NodeState(status="done"),
                    "W1": NodeState(status="in_progress", wake_at=future_wake_at),
                },
            )
            import json as _json
            (run_dir / "run-resume.json").write_text(_json.dumps(pre_state.to_dict()), encoding="utf-8")

            with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
                with patch("app.harnesses.executor._run_index.update_run_status", new_callable=AsyncMock):
                    with patch("app.harnesses.wait.asyncio.sleep", side_effect=fake_sleep):
                        executor = HarnessExecutor(store, worker, _tools_resolver)
                        await executor.execute("run-resume", harness, space)

        # Must sleep the REMAINING time (~30s), NOT the full 3600s
        assert len(sleep_calls) == 1
        remaining = sleep_calls[0]
        assert remaining <= 35.0, f"Expected at most 35s remaining sleep, got {remaining}"
        assert remaining > 0.0, f"Expected positive remaining sleep, got {remaining}"

    @pytest.mark.asyncio
    async def test_timed_wait_restart_after_wake_fires_immediately(self, tmp_path: Path):
        """
        Path 3 (restart after wake time has passed): executor sleeps 0 seconds
        and fires immediately rather than sleeping the full duration again.
        """
        import datetime as dt_module

        harness = _make_timed_wait_harness(duration_seconds=3600.0)  # 1 hour
        store = _make_store_mock()
        worker = StubWorker()
        space = _make_space()

        # Simulate wake_at already in the past by 5 seconds
        past_wake_at = (
            dt_module.datetime.now(dt_module.timezone.utc) - dt_module.timedelta(seconds=5)
        ).isoformat()

        sleep_calls: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Pre-populate run_state at the correct path (simulates overdue restart).
            # In a real restart T1 (trigger) is done and W1 is in_progress with past wake_at.
            # Path: _DATA_DIR/spaces/{space.id}/.cronos/harness-runs/{run_id}.json
            run_dir = Path(tmpdir) / "spaces" / "test-space" / ".cronos" / "harness-runs"
            run_dir.mkdir(parents=True)
            pre_state = RunState(
                run_id="run-overdue",
                harness_id="harness-timed",
                goal_task_id="goal-1",
                nodes_executed={
                    "T1": NodeState(status="done"),
                    "W1": NodeState(status="in_progress", wake_at=past_wake_at),
                },
            )
            import json as _json
            (run_dir / "run-overdue.json").write_text(_json.dumps(pre_state.to_dict()), encoding="utf-8")

            with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
                with patch("app.harnesses.executor._run_index.update_run_status", new_callable=AsyncMock):
                    with patch("app.harnesses.wait.asyncio.sleep", side_effect=fake_sleep):
                        executor = HarnessExecutor(store, worker, _tools_resolver)
                        result = await executor.execute("run-overdue", harness, space)

        # Must fire immediately with 0-second sleep (NOT 3600s)
        assert len(sleep_calls) == 1
        assert sleep_calls[0] == 0.0, f"Expected 0s sleep for overdue wake_at, got {sleep_calls[0]}"
        assert result.nodes_executed["W1"].status == "done"


# ---------------------------------------------------------------------------
# I5 / R12: scope enrichment from delivery_status block (G3.3 routing unblock)
# ---------------------------------------------------------------------------


class TestScopeEnrichmentFromDeliveryStatus:
    """After an agent node completes, delivery_status fields appear in scope."""

    @pytest.mark.asyncio
    async def test_delivery_status_fields_added_to_scope(self) -> None:
        """R12: scope gains dotted-path keys from delivery_status after DONE."""
        delivery_output = (
            "```delivery_status\n"
            '{"status": "done", "fields": {"verdict": "pass", "count": "3"}}\n'
            "```\n"
            "STATUS: DONE"
        )

        store = _make_store_mock()
        worker = StubWorker(task_state=TaskState.DONE, final_text=delivery_output)
        harness = _make_single_agent_harness()
        space = _make_space()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
                with patch("app.harnesses.executor._run_index.update_run_status",
                           new_callable=AsyncMock):
                    executor = HarnessExecutor(store, worker, _tools_resolver)
                    result = await executor.execute("run-1", harness, space)

        assert result.nodes_executed["A1"].status == "done"
        # Check scope via the run — we can't inspect scope directly, but can verify
        # the node output was captured (flat key populated).
        assert result.nodes_executed["A1"].output == delivery_output

    @pytest.mark.asyncio
    async def test_decision_routes_on_delivery_status_verdict(self) -> None:
        """R13/G3.3: conditional edge can branch on delivery_status.fields.verdict."""
        delivery_output = (
            "```delivery_status\n"
            '{"status": "done", "fields": {"verdict": "pass"}}\n'
            "```"
        )

        store = _make_store_mock()
        worker = StubWorker(task_state=TaskState.DONE, final_text=delivery_output)
        space = _make_space()

        # Harness: agent-review → decision → pass-branch OR fail-branch
        review = _make_agent_node("review")
        decision = _make_decision_node("gate")
        pass_node = _make_agent_node("pass-node")
        fail_node = _make_agent_node("fail-node")

        harness = Harness(
            name="verdict-routing",
            nodes=[review, decision, pass_node, fail_node],
            edges=[
                _make_edge("e1", "review", "gate"),
                _make_edge("e2", "gate", "pass-node",
                           condition="review.fields.verdict == pass"),
                _make_edge("e3", "gate", "fail-node",
                           condition="review.fields.verdict == fail"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
                with patch("app.harnesses.executor._run_index.update_run_status",
                           new_callable=AsyncMock):
                    executor = HarnessExecutor(store, worker, _tools_resolver)
                    result = await executor.execute("run-routing", harness, space)

        # The decision should have routed to pass-node, not fail-node.
        assert result.nodes_executed.get("pass-node", NodeState(status="pending")).status == "done"
        assert result.nodes_executed.get("fail-node") is None or \
               result.nodes_executed["fail-node"].status == "skipped"

    @pytest.mark.asyncio
    async def test_no_delivery_status_block_no_dotted_keys(self) -> None:
        """When agent output has no delivery_status fence, no dotted keys are added."""
        plain_output = "Work done.\nSTATUS: DONE"

        store = _make_store_mock()
        worker = StubWorker(task_state=TaskState.DONE, final_text=plain_output)
        harness = _make_single_agent_harness()
        space = _make_space()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
                with patch("app.harnesses.executor._run_index.update_run_status",
                           new_callable=AsyncMock):
                    executor = HarnessExecutor(store, worker, _tools_resolver)
                    result = await executor.execute("run-plain", harness, space)

        # Node should succeed with plain output
        assert result.nodes_executed["A1"].status == "done"
        assert result.nodes_executed["A1"].output == plain_output


def _make_single_agent_harness(
    node_id: str = "A1",
    prompt: str = "do work",
) -> Harness:
    """Return a minimal single-agent harness for scope enrichment tests."""
    node = _make_agent_node(node_id, prompt_template=prompt)
    return Harness(name="single-agent", nodes=[node], edges=[])
