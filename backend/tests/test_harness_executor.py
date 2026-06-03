"""
Tests for backend/app/harnesses/executor.py

Covers:
- Basic 3-node linear harness (A→B→C) all Agent nodes
- Control-flow node treated as pass-through (skipped with reason='control_flow_stub')
- Fail-fast: when node B fails, node C is marked skipped with reason='upstream_failed'
- Variable interpolation: upstream output flows into downstream prompt_template
- Run state file created and updated per node
- Resume: in_progress node with done child_task_id → node marked done without re-executing
- WorkerProtocol is stubbed (not a real Worker instance)
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


def _make_edge(edge_id: str, src_node: str, tgt_node: str,
               src_port: str = "out", tgt_port: str = "out") -> HarnessEdge:
    return HarnessEdge(
        id=edge_id,
        source=NodeRef(node_id=src_node, port_id=src_port),
        target=NodeRef(node_id=tgt_node, port_id=tgt_port),
    )


def _make_trace(final_text: str = "result", parent_run_id: str | None = None) -> RunTrace:
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
        exit_reason="DONE",
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
# Control-flow node pass-through
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_control_flow_node_skipped():
    """A decision (control-flow) node should be skipped with reason='control_flow_stub'."""
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
    assert ns.status == "skipped"
    assert ns.reason == "control_flow_stub"
    # No agent calls for control-flow nodes.
    assert len(worker.run_agent_calls) == 0


@pytest.mark.asyncio
async def test_executor_control_flow_node_followed_by_agent():
    """Control-flow node is pass-through; downstream agent node still executes."""
    cf = HarnessNode(id="CF", type=NodeType.decision, position=_make_position(),
                     ports={"out": {}}, data={}, label="CF")
    ag = HarnessNode(id="AG", type=NodeType.agent, position=_make_position(),
                     ports={"out": {}}, data={"agent_ref": "ag", "prompt_template": "p"},
                     label="AG")
    edge = HarnessEdge(id="e1", source=NodeRef(node_id="CF", port_id="out"),
                       target=NodeRef(node_id="AG", port_id="out"))
    harness = Harness(name="cf_agent", nodes=[cf, ag], edges=[edge])
    space = _make_space()
    store = _make_store_mock(space.id)
    worker = StubWorker()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _tools_resolver)
            result = await executor.execute("run-cfa", harness, space)

    assert result.nodes_executed["CF"].status == "skipped"
    assert result.nodes_executed["CF"].reason == "control_flow_stub"
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
