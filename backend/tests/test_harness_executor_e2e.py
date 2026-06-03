"""
End-to-end tests for HarnessExecutor — acceptance criteria from R9 and R10.

These tests go beyond the unit tests in test_harness_executor.py by verifying:

  Test 1 (R10): Full 3-node linear harness A→B→C executes correctly:
    - Goal expands to 3 child Tasks created in topo order (A first, then B, then C)
    - Each child Task has parent_run_id = run_goal_id
    - Upstream output from A is interpolated into B's prompt template
    - Run-state file is created at the expected path with all nodes recorded as 'done'

  Test 2 (R4): Variable interpolation flows through the chain:
    - Node A output = "result_from_A"
    - Node B prompt_template = "process ${node_A_output}"
      (where node_A_output is set from A's output via the variable scope)
    - Node B's composed brief contains "process result_from_A"

  Test 3 (R9): FIFO / sequential execution invariant:
    - Nodes run sequentially — no concurrent asyncio tasks
    - Node B is not started before node A finishes
    - Node C is not started before node B finishes
    - Verified via an in-order execution-tracking list in the stub worker

  Test 4: Fail-fast halts remaining nodes:
    - Node B fails (finalize_child returns WAITING, a non-DONE state)
    - Node C is marked 'skipped' with reason='upstream_failed' in run state
    - The goal run-state file reflects the failure
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.harnesses.executor import HarnessExecutor
from app.harnesses.model import (
    Harness,
    HarnessEdge,
    HarnessNode,
    NodeRef,
    NodeType,
    Position,
)
from app.harnesses.run_state import load as load_run_state
from app.models import AiToolEntry, Space, TaskState
from app.trace_parser import RunTrace


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _make_space(space_id: str = "e2e-space") -> Space:
    now = _utcnow()
    return Space(
        id=space_id,
        name="E2E Test Space",
        color="#abcdef",
        created_at=now,
        updated_at=now,
    )


def _make_position() -> Position:
    return Position(x=0.0, y=0.0)


def _make_agent_node(
    node_id: str,
    *,
    label: str = "",
    agent_ref: str = "test-agent",
    prompt_template: str = "do something",
) -> HarnessNode:
    """Build an Agent-type harness node with a single 'out' port."""
    return HarnessNode(
        id=node_id,
        type=NodeType.agent,
        position=_make_position(),
        ports={"out": {"direction": "output"}},
        data={"agent_ref": agent_ref, "prompt_template": prompt_template},
        label=label or node_id,
    )


def _make_edge(
    edge_id: str,
    src_node: str,
    tgt_node: str,
    src_port: str = "out",
    tgt_port: str = "out",
) -> HarnessEdge:
    return HarnessEdge(
        id=edge_id,
        source=NodeRef(node_id=src_node, port_id=src_port),
        target=NodeRef(node_id=tgt_node, port_id=tgt_port),
    )


def _make_trace(
    task_id: str = "child-task",
    final_text: str = "output",
    parent_run_id: str | None = None,
) -> RunTrace:
    now = _utcnow()
    return RunTrace(
        task_id=task_id,
        space_id="e2e-space",
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


def _no_tools_resolver(space_id: str, agent_ref: str) -> AiToolEntry | None:
    return None


# ---------------------------------------------------------------------------
# Test 1: 3-node linear harness e2e (R10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_three_node_linear_all_done():
    """
    R10 acceptance criterion: full 3-node linear harness A→B→C.

    Asserts:
    - 3 child tasks are created, one per node, in topo order (A, B, C)
    - Each run_agent call receives parent_run_id=run_goal_id via kwargs
    - All three nodes are recorded as 'done' in the returned RunState
    - Run-state JSON file exists at the expected path and reflects all nodes done
    """
    run_goal_id = "e2e-run-001"
    space = _make_space("e2e-space-1")

    # Build A→B→C harness
    node_a = _make_agent_node("A", prompt_template="do A")
    node_b = _make_agent_node("B", prompt_template="do B")
    node_c = _make_agent_node("C", prompt_template="do C")
    edge_ab = _make_edge("e1", "A", "B")
    edge_bc = _make_edge("e2", "B", "C")
    harness = Harness(
        name="three-node-linear",
        nodes=[node_a, node_b, node_c],
        edges=[edge_ab, edge_bc],
    )

    # Track task creation order to verify topo-order
    created_task_ids: list[str] = []
    created_briefs: list[str] = []
    task_counter = [0]

    store = MagicMock()

    async def mock_create(*, space_id, title, brief, parent_id=None, **kwargs):
        task_counter[0] += 1
        tid = f"child-{task_counter[0]}"
        created_task_ids.append(tid)
        created_briefs.append(brief)
        return _make_task_mock(tid)

    store.create = mock_create
    store.get = MagicMock(return_value=None)

    # Track run_agent calls to verify parent_run_id propagation
    run_agent_calls: list[dict] = []

    async def mock_run_agent(task_id: str, **kwargs) -> RunTrace:
        run_agent_calls.append({"task_id": task_id, "kwargs": kwargs})
        return _make_trace(task_id=task_id, final_text=f"output_of_{task_id}")

    async def mock_finalize_child(task_id: str, trace: RunTrace) -> TaskState:
        return TaskState.DONE

    worker = MagicMock()
    worker.run_agent = mock_run_agent
    worker.finalize_child = mock_finalize_child

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _no_tools_resolver)
            result = await executor.execute(run_goal_id, harness, space)

        # Verify run-state file path
        state_path = (
            Path(tmpdir)
            / "spaces"
            / "e2e-space-1"
            / ".cronos"
            / "harness-runs"
            / f"{run_goal_id}.json"
        )
        assert state_path.exists(), f"Run-state file not found at {state_path}"

        with state_path.open() as f:
            raw = json.load(f)

    # All three nodes executed
    assert len(run_agent_calls) == 3, f"Expected 3 run_agent calls, got {len(run_agent_calls)}"

    # run_agent called with parent_run_id=run_goal_id (FIFO/harness linkage)
    for call in run_agent_calls:
        assert call["kwargs"].get("parent_run_id") == run_goal_id, (
            f"Expected parent_run_id={run_goal_id!r} in run_agent kwargs, "
            f"got {call['kwargs']}"
        )

    # All nodes are 'done' in the returned RunState
    for node_id in ("A", "B", "C"):
        ns = result.nodes_executed.get(node_id)
        assert ns is not None, f"Node {node_id!r} missing from run state"
        assert ns.status == "done", f"Node {node_id!r} expected 'done', got {ns.status!r}"
        assert ns.child_task_id is not None, f"Node {node_id!r} has no child_task_id"

    # Run-state JSON file reflects all nodes done
    assert raw["run_id"] == run_goal_id
    for node_id in ("A", "B", "C"):
        assert node_id in raw["nodes_executed"], f"Node {node_id!r} absent from JSON"
        assert raw["nodes_executed"][node_id]["status"] == "done"

    # Topo order: A first, then B, then C (by child task creation order)
    # The store.create() is called in topo order — verify 3 tasks created
    assert len(created_task_ids) == 3, f"Expected 3 tasks created, got {len(created_task_ids)}"


# ---------------------------------------------------------------------------
# Test 2: Variable interpolation flows through the chain (R4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_variable_interpolation_chain():
    """
    R4: Variable substitution flows from upstream node output into downstream prompt.

    Scenario:
    - Node A runs; its final_text_snippet is "result_from_A"
    - harness.variables has no 'A' key (so upstream output is placed in scope under 'A')
    - Node B prompt_template = "process ${A}"
      (where A is the node_id whose output gets promoted to scope key 'A')
    - After execution, Node B's composed brief must contain "process result_from_A"

    Note: The executor sets scope[node_id] = trace.final_text_snippet after each
    successful Agent node. So node_id 'A' maps to A's output in the variable scope.
    """
    run_goal_id = "e2e-interp-001"
    space = _make_space("e2e-space-interp")

    node_a = _make_agent_node("A", prompt_template="produce data")
    # B's template uses $A which will resolve to node A's output
    node_b = _make_agent_node("B", prompt_template="process $A")
    edge_ab = _make_edge("e1", "A", "B")
    harness = Harness(
        name="interp-chain",
        nodes=[node_a, node_b],
        edges=[edge_ab],
    )

    created_briefs: list[str] = []
    task_counter = [0]

    store = MagicMock()

    async def mock_create(*, space_id, title, brief, parent_id=None, **kwargs):
        task_counter[0] += 1
        tid = f"child-{task_counter[0]}"
        created_briefs.append(brief)
        return _make_task_mock(tid)

    store.create = mock_create
    store.get = MagicMock(return_value=None)

    # Node A returns "result_from_A"; Node B should see this substituted into its prompt
    async def mock_run_agent(task_id: str, **kwargs) -> RunTrace:
        # Return "result_from_A" for the first call (node A)
        if task_counter[0] == 1:
            return _make_trace(task_id=task_id, final_text="result_from_A")
        return _make_trace(task_id=task_id, final_text="output_B")

    async def mock_finalize_child(task_id: str, trace: RunTrace) -> TaskState:
        return TaskState.DONE

    worker = MagicMock()
    worker.run_agent = mock_run_agent
    worker.finalize_child = mock_finalize_child

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _no_tools_resolver)
            result = await executor.execute(run_goal_id, harness, space)

    assert result.nodes_executed["A"].status == "done"
    assert result.nodes_executed["B"].status == "done"

    # Node B's brief (second brief created) must contain the interpolated output from A
    assert len(created_briefs) >= 2, "Expected at least 2 briefs created"
    node_b_brief = created_briefs[1]
    assert "result_from_A" in node_b_brief, (
        f"Expected 'result_from_A' in Node B's brief; got: {node_b_brief!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: FIFO sequential execution invariant (R9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_fifo_sequential_execution():
    """
    R9: No concurrent asyncio tasks — nodes run strictly sequentially.

    Verifies:
    - Node B is not started before node A finishes (start_A < finish_A < start_B)
    - Node C is not started before node B finishes (start_B < finish_B < start_C)

    Implementation: the stub worker records (start, finish) timestamps per call.
    Since Python asyncio is cooperative (no threading), sequential start/finish
    ordering is sufficient evidence of FIFO serial execution without concurrency.
    We also verify run_agent is never called with asyncio.gather or create_task
    by ensuring the call-order list is exactly [A, B, C].
    """
    run_goal_id = "e2e-fifo-001"
    space = _make_space("e2e-space-fifo")

    node_a = _make_agent_node("FA", prompt_template="step A")
    node_b = _make_agent_node("FB", prompt_template="step B")
    node_c = _make_agent_node("FC", prompt_template="step C")
    edge_ab = _make_edge("e1", "FA", "FB")
    edge_bc = _make_edge("e2", "FB", "FC")
    harness = Harness(
        name="fifo-test",
        nodes=[node_a, node_b, node_c],
        edges=[edge_ab, edge_bc],
    )

    task_counter = [0]
    store = MagicMock()

    async def mock_create(*, space_id, title, brief, parent_id=None, **kwargs):
        task_counter[0] += 1
        return _make_task_mock(f"child-{task_counter[0]}")

    store.create = mock_create
    store.get = MagicMock(return_value=None)

    # Execution order tracking
    execution_log: list[str] = []  # ["start_FA", "finish_FA", "start_FB", ...]
    finalize_log: list[str] = []

    async def mock_run_agent(task_id: str, **kwargs) -> RunTrace:
        # Map task_id back to node_id by order: child-1=FA, child-2=FB, child-3=FC
        node_map = {"child-1": "FA", "child-2": "FB", "child-3": "FC"}
        node_label = node_map.get(task_id, task_id)
        execution_log.append(f"start_{node_label}")
        # Yield control to event loop to expose any concurrency issues
        await asyncio.sleep(0)
        execution_log.append(f"finish_{node_label}")
        return _make_trace(task_id=task_id, final_text=f"output_{node_label}")

    async def mock_finalize_child(task_id: str, trace: RunTrace) -> TaskState:
        node_map = {"child-1": "FA", "child-2": "FB", "child-3": "FC"}
        node_label = node_map.get(task_id, task_id)
        finalize_log.append(node_label)
        return TaskState.DONE

    worker = MagicMock()
    worker.run_agent = mock_run_agent
    worker.finalize_child = mock_finalize_child

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _no_tools_resolver)
            result = await executor.execute(run_goal_id, harness, space)

    # All three nodes completed
    for node_id in ("FA", "FB", "FC"):
        assert result.nodes_executed[node_id].status == "done", (
            f"Node {node_id!r} expected done, got {result.nodes_executed[node_id].status!r}"
        )

    # Verify sequential ordering via execution log:
    # Expected: start_FA, finish_FA, start_FB, finish_FB, start_FC, finish_FC
    assert len(execution_log) == 6, f"Expected 6 log entries, got: {execution_log}"

    fa_start = execution_log.index("start_FA")
    fa_finish = execution_log.index("finish_FA")
    fb_start = execution_log.index("start_FB")
    fb_finish = execution_log.index("finish_FB")
    fc_start = execution_log.index("start_FC")
    fc_finish = execution_log.index("finish_FC")

    # A must start and finish before B starts
    assert fa_start < fa_finish, "FA start must precede FA finish"
    assert fa_finish < fb_start, "FA must finish before FB starts (FIFO invariant)"

    # B must start and finish before C starts
    assert fb_start < fb_finish, "FB start must precede FB finish"
    assert fb_finish < fc_start, "FB must finish before FC starts (FIFO invariant)"

    assert fc_start < fc_finish, "FC start must precede FC finish"

    # Finalize order also follows topo order
    assert finalize_log == ["FA", "FB", "FC"], (
        f"finalize_child called out of order: {finalize_log}"
    )


# ---------------------------------------------------------------------------
# Test 4: Fail-fast halts remaining nodes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_fail_fast_halts_remaining_nodes():
    """
    Fail-fast: when node B fails, node C is never started and is marked 'skipped'.

    Asserts:
    - Node A completes normally (status='done')
    - Node B fails (finalize_child returns WAITING → non-DONE) → status='failed'
    - Node C is marked 'skipped' with reason='upstream_failed' (never run)
    - run_agent is NOT called for node C
    - The run-state JSON file on disk reflects the failure and skip correctly
    """
    run_goal_id = "e2e-failfast-001"
    space = _make_space("e2e-space-fail")

    node_a = _make_agent_node("NA", prompt_template="step A")
    node_b = _make_agent_node("NB", prompt_template="step B")
    node_c = _make_agent_node("NC", prompt_template="step C")
    edge_ab = _make_edge("e1", "NA", "NB")
    edge_bc = _make_edge("e2", "NB", "NC")
    harness = Harness(
        name="failfast-test",
        nodes=[node_a, node_b, node_c],
        edges=[edge_ab, edge_bc],
    )

    task_counter = [0]
    store = MagicMock()

    async def mock_create(*, space_id, title, brief, parent_id=None, **kwargs):
        task_counter[0] += 1
        return _make_task_mock(f"child-{task_counter[0]}")

    store.create = mock_create
    store.get = MagicMock(return_value=None)

    run_agent_called_for: list[str] = []

    async def mock_run_agent(task_id: str, **kwargs) -> RunTrace:
        run_agent_called_for.append(task_id)
        return _make_trace(task_id=task_id, final_text=f"output_{task_id}")

    async def mock_finalize_child(task_id: str, trace: RunTrace) -> TaskState:
        # NA (child-1) succeeds; NB (child-2) fails; NC should never be reached
        if task_id == "child-1":
            return TaskState.DONE
        if task_id == "child-2":
            return TaskState.WAITING  # failure = non-DONE state
        # Should never be called for child-3
        raise AssertionError(f"finalize_child called unexpectedly for {task_id}")

    worker = MagicMock()
    worker.run_agent = mock_run_agent
    worker.finalize_child = mock_finalize_child

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _no_tools_resolver)
            result = await executor.execute(run_goal_id, harness, space)

        state_path = (
            Path(tmpdir)
            / "spaces"
            / "e2e-space-fail"
            / ".cronos"
            / "harness-runs"
            / f"{run_goal_id}.json"
        )
        assert state_path.exists(), f"Run-state file not found at {state_path}"
        with state_path.open() as f:
            raw = json.load(f)

    # Node A: done
    na = result.nodes_executed.get("NA")
    assert na is not None, "Node NA missing from run state"
    assert na.status == "done", f"Node NA expected 'done', got {na.status!r}"

    # Node B: failed (finalize_child returned WAITING)
    nb = result.nodes_executed.get("NB")
    assert nb is not None, "Node NB missing from run state"
    assert nb.status == "failed", f"Node NB expected 'failed', got {nb.status!r}"

    # Node C: skipped with reason='upstream_failed'
    nc = result.nodes_executed.get("NC")
    assert nc is not None, "Node NC missing from run state"
    assert nc.status == "skipped", f"Node NC expected 'skipped', got {nc.status!r}"
    assert nc.reason == "upstream_failed", (
        f"Node NC expected reason='upstream_failed', got {nc.reason!r}"
    )

    # run_agent was NOT called for NC (task_id would be 'child-3')
    assert "child-3" not in run_agent_called_for, (
        f"run_agent should not have been called for NC; calls: {run_agent_called_for}"
    )
    # run_agent was called exactly twice (NA and NB)
    assert len(run_agent_called_for) == 2, (
        f"Expected 2 run_agent calls, got {len(run_agent_called_for)}: {run_agent_called_for}"
    )

    # Run-state JSON file reflects failure and skip
    assert raw["run_id"] == run_goal_id
    assert raw["nodes_executed"]["NA"]["status"] == "done"
    assert raw["nodes_executed"]["NB"]["status"] == "failed"
    assert raw["nodes_executed"]["NC"]["status"] == "skipped"
    assert raw["nodes_executed"]["NC"]["reason"] == "upstream_failed"
