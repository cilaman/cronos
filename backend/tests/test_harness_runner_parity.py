"""
backend/tests/test_harness_runner_parity -- BFS vs runner parity tests.

PARITY SCOPE (control-flow only)
---------------------------------
These tests verify that the BFS HarnessExecutor and the delivery-workflow
runner (via HarnessExecutorAdapter + runner.core.run) produce identical
*control-flow* outcomes when driven with the same fake WorkerAdapter stubs:

  - Final run outcome: done / blocked (human-wait) / failed
  - Per-node status: done / failed / skipped / in_progress / blocked
  - Event stream shape: event types and node_id coverage

Agent fidelity (real CLI process timing, streaming output,
partial output buffering) is explicitly OUT OF SCOPE and deferred to
shadow-mode production testing (see design-report ## Deferred section 3).

Event schema note
-----------------
BFS HarnessExecutor emits node_transition events with 'to_status' key
(not 'status').  The runner path (HarnessExecutorAdapter._TelemetryOps.emit)
emits node_transition events with 'status' key to match the frontend
SSE consumer schema.  Both paths emit 'from_status', 'node_id', 'type',
and 'timestamp'.  Parity tests that compare events accept both conventions.

Runner human-wait resume
------------------------
Runner-path human-wait resume is implemented via the package resume grammar:
run_executor._execute_harness_run_runner translates the user's reply/verdict
into DeliveryRun.resume(HumanAnswer(node_id=waiting_node_id, ...)) — the
persisted RunState park (waiting_node_id + node 'in_progress') is rebuilt as
a 'blocked' WorkflowState by state_mapping.runstate_to_workflowstate, so
bare start() is sealed on the park (silence never approves, D10).  End-to-end
progression is covered by
tests/test_delivery_outcomes.py::test_harness_human_wait_resume_progresses_run;
this suite still exercises the park itself (scenario 4) plus BFS resume.

Scenarios
---------
1. LINEAR -- trigger + agent: simple two-node path, outcome=done.
2. AGGREGATOR_ALL -- two agents + aggregator(all): both branches must complete.
3. AGGREGATOR_ANY -- one agent + aggregator(any): fires on single completion.
4. HUMAN_WAIT -- trigger + wait(human) + agent: first run parks; BFS resume tested.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap -- make packages/delivery-workflow importable.
# ---------------------------------------------------------------------------

from delivery_workflow.state_types import WorkflowState  # noqa: E402

from app.harnesses.compiler import compile as compile_harness  # noqa: E402
from app.harnesses.executor import HarnessExecutor  # noqa: E402
from app.harnesses.executor_adapter import HarnessExecutorAdapter  # noqa: E402
from app.harnesses.model import Harness, NodeType  # noqa: E402
from app.harnesses.run_state import NodeState as HarnessNodeState, RunState  # noqa: E402
from app.harnesses.state_mapping import workflowstate_to_runstate  # noqa: E402
from app.models import AiToolEntry, Space, TaskState  # noqa: E402
from app.trace_parser import RunTrace  # noqa: E402

# Import fixtures from the conftest module.
pytest_plugins = ["tests.conftest_harness_parity"]


# ---------------------------------------------------------------------------
# Shared stubs
# ---------------------------------------------------------------------------


def _make_run_trace(
    task_id: str = "child-task",
    final_text: str = "agent output",
    exit_reason: str = "DONE",
) -> RunTrace:
    now = datetime.now(tz=UTC)
    return RunTrace(
        task_id=task_id,
        space_id="space-parity",
        run_index=0,
        session_id=None,
        model="claude-test",
        mode="auto",
        started_at=now,
        ended_at=now,
        duration_seconds=0.1,
        exit_reason=exit_reason,
        final_text_snippet=final_text,
    )


def _make_space(space_id: str = "space-parity") -> Space:
    now = datetime.now(tz=UTC)
    return Space(
        id=space_id,
        name="Parity Test Space",
        color="#000000",
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# BFS Stubs
# ---------------------------------------------------------------------------


class _BFSWorkerStub:
    """WorkerProtocol stub for BFS HarnessExecutor."""

    def __init__(
        self,
        finalize_result: TaskState = TaskState.DONE,
        final_text: str = "bfs agent output",
    ) -> None:
        self._finalize_result = finalize_result
        self._final_text = final_text
        self.run_agent_calls: list[str] = []
        self.finalize_calls: list[str] = []
        self._events: list[dict] = []

    async def run_agent(self, task_id: str, **kwargs: Any) -> RunTrace:
        self.run_agent_calls.append(task_id)
        return _make_run_trace(task_id=task_id, final_text=self._final_text)

    async def finalize_child(self, task_id: str, trace: RunTrace) -> TaskState:
        self.finalize_calls.append(task_id)
        return self._finalize_result

    def _publish(self, task_id: str, event: dict) -> None:
        self._events.append(event)


def _make_bfs_store() -> MagicMock:
    """Build a minimal TaskStore mock for BFS executor."""
    store = MagicMock()
    _counter = [0]

    async def create(
        *, space_id: str, title: str, brief: str, parent_id: str | None = None, **kwargs: Any
    ) -> MagicMock:
        _counter[0] += 1
        task = MagicMock()
        task.id = f"bfs-child-{_counter[0]}"
        task.state = TaskState.DONE
        return task

    store.create = create
    store.get = MagicMock(return_value=None)
    return store


def _tools_resolver_stub(space_id: str, agent_ref: str) -> AiToolEntry | None:
    return None


# ---------------------------------------------------------------------------
# Runner Stubs
# ---------------------------------------------------------------------------


class _RunnerWorkerAdapterStub:
    """WorkerAdapter stub for HarnessExecutorAdapter (runner path)."""

    def __init__(
        self,
        finalize_result: TaskState = TaskState.DONE,
        final_text: str = "runner agent output",
    ) -> None:
        self._finalize_result = finalize_result
        self._final_text = final_text
        self.run_agent_calls: list[str] = []
        self.finalize_calls: list[str] = []

    async def run_agent(self, task_id: str) -> RunTrace:
        self.run_agent_calls.append(task_id)
        return _make_run_trace(task_id=task_id, final_text=self._final_text)

    async def finalize_child(self, task_id: str) -> TaskState:
        self.finalize_calls.append(task_id)
        return self._finalize_result


def _make_runner_adapter(
    harness: Harness,
    run_state: RunState | None = None,
    finalize_result: TaskState = TaskState.DONE,
    captured_events: list[dict] | None = None,
) -> tuple[HarnessExecutorAdapter, _RunnerWorkerAdapterStub]:
    """Build a HarnessExecutorAdapter + worker stub pair for runner path."""
    worker = _RunnerWorkerAdapterStub(finalize_result=finalize_result)
    if run_state is None:
        run_state = RunState(
            run_id="parity-run",
            harness_id=harness.name,
            goal_task_id="parity-goal",
        )

    events: list[dict] = [] if captured_events is None else captured_events

    def _publish_cb(tid: str, event: dict) -> None:
        events.append(event)

    _task_counter = [0]

    def _task_id_factory(agent_ref: str, inputs: dict) -> str:
        _task_counter[0] += 1
        return f"runner-child-{_task_counter[0]}"

    adapter = HarnessExecutorAdapter(
        worker_adapter=worker,
        run_state=run_state,
        harness_id=harness.name,
        goal_task_id="parity-goal",
        publish_cb=_publish_cb,
        task_id_factory=_task_id_factory,
    )
    return adapter, worker


# ---------------------------------------------------------------------------
# Execution helpers
# ---------------------------------------------------------------------------


def _run_bfs(
    harness: Harness,
    tmp_path: Path,
    worker_stub: _BFSWorkerStub | None = None,
) -> tuple[RunState, list[dict]]:
    """Run BFS executor on *harness* in a temp directory.

    Returns (final_run_state, events).
    """
    if worker_stub is None:
        worker_stub = _BFSWorkerStub()
    store = _make_bfs_store()
    executor = HarnessExecutor(
        store=store,
        worker_protocol=worker_stub,
        tools_resolver=_tools_resolver_stub,
        event_worker=worker_stub,
    )
    space = _make_space()

    # Patch the BFS DATA_DIR to use tmp_path so it writes run-state files there.
    import app.harnesses.executor as _exec_mod  # noqa: PLC0415

    original_data_dir = _exec_mod._DATA_DIR
    _exec_mod._DATA_DIR = tmp_path

    try:
        run_state = asyncio.run(executor.execute("parity-run", harness, space))
    finally:
        _exec_mod._DATA_DIR = original_data_dir

    return run_state, worker_stub._events


def _run_runner(
    harness: Harness,
    run_state: RunState | None = None,
    finalize_result: TaskState = TaskState.DONE,
) -> tuple[WorkflowState, RunState, list[dict]]:
    """Run the delivery-workflow runner on *harness*.

    Returns (workflow_state, mapped_run_state, events).
    """
    from delivery_workflow.runner.core import run as runner_run  # noqa: PLC0415

    events: list[dict] = []
    adapter, _worker = _make_runner_adapter(
        harness,
        run_state=run_state,
        finalize_result=finalize_result,
        captured_events=events,
    )
    ir_graph = compile_harness(harness)
    wf_state = runner_run(ir_graph, adapter, state_ops=adapter.state)

    # Map back to RunState for comparison with BFS output.
    base_rs = run_state or RunState(
        run_id="parity-run",
        harness_id=harness.name,
        goal_task_id="parity-goal",
    )
    rs = workflowstate_to_runstate(wf_state, base_rs)
    return wf_state, rs, events


# ---------------------------------------------------------------------------
# Status normalisation helpers
# ---------------------------------------------------------------------------


def _node_status_from_bfs(run_state: RunState, node_id: str) -> str:
    """Return node status from BFS RunState, 'pending' if absent."""
    ns = run_state.nodes_executed.get(node_id)
    return ns.status if ns is not None else "pending"


def _node_status_from_runner(wf_state: WorkflowState, node_id: str) -> str:
    """Return node status from WorkflowState normalised to Harness convention.

    Maps runner statuses to harness node statuses for comparison:
      done       -> done
      blocked    -> pending  (not dispatched yet)
      running    -> in_progress
      failed     -> failed
      escalated  -> failed
    """
    from app.harnesses.state_mapping import _WF_TO_HARNESS_NODE  # noqa: PLC0415

    ns = wf_state.nodes.get(node_id)
    if ns is None:
        return "pending"
    return _WF_TO_HARNESS_NODE.get(ns.status, "pending")


def _node_transition_statuses(events: list[dict], node_id: str) -> set[str]:
    """Extract the set of status values from node_transition events for *node_id*.

    Accepts both 'status' (runner/adapter schema) and 'to_status' (BFS schema).
    """
    result: set[str] = set()
    for e in events:
        if e.get("type") != "node_transition":
            continue
        if e.get("node_id") != node_id:
            continue
        # Accept both BFS 'to_status' and runner 'status' key.
        val = e.get("status") or e.get("to_status")
        if val:
            result.add(val)
    return result


# ---------------------------------------------------------------------------
# Scenario 1: LINEAR -- trigger + agent
# ---------------------------------------------------------------------------


class TestLinearParity:
    """BFS vs runner parity for a simple trigger -> agent harness."""

    def test_bfs_outcome_done(
        self, harness_linear: Harness, tmp_path: Path
    ) -> None:
        """BFS: trigger+agent harness completes with status='done'."""
        run_state, _events = _run_bfs(harness_linear, tmp_path)
        assert run_state.status == "done", (
            f"BFS expected status='done', got {run_state.status!r}"
        )

    def test_runner_outcome_done(self, harness_linear: Harness) -> None:
        """Runner: trigger+agent harness completes with status='done'."""
        wf_state, rs, _events = _run_runner(harness_linear)
        assert wf_state.status == "done", (
            f"Runner expected status='done', got {wf_state.status!r}"
        )

    def test_bfs_trigger_done(
        self, harness_linear: Harness, tmp_path: Path
    ) -> None:
        """BFS: trigger node reaches status='done'."""
        run_state, _ = _run_bfs(harness_linear, tmp_path)
        assert _node_status_from_bfs(run_state, "trigger-1") == "done"

    def test_runner_trigger_done(self, harness_linear: Harness) -> None:
        """Runner: trigger node reaches status='done'."""
        wf_state, rs, _ = _run_runner(harness_linear)
        assert _node_status_from_runner(wf_state, "trigger-1") == "done"

    def test_bfs_agent_done(
        self, harness_linear: Harness, tmp_path: Path
    ) -> None:
        """BFS: agent node reaches status='done'."""
        run_state, _ = _run_bfs(harness_linear, tmp_path)
        assert _node_status_from_bfs(run_state, "agent-1") == "done"

    def test_runner_agent_done(self, harness_linear: Harness) -> None:
        """Runner: agent node reaches status='done'."""
        wf_state, rs, _ = _run_runner(harness_linear)
        assert _node_status_from_runner(wf_state, "agent-1") == "done"

    def test_parity_outcome(
        self, harness_linear: Harness, tmp_path: Path
    ) -> None:
        """BFS and runner produce identical final outcome for linear harness."""
        bfs_state, _ = _run_bfs(harness_linear, tmp_path)
        wf_state, rs, _ = _run_runner(harness_linear)

        assert bfs_state.status == rs.status, (
            f"Parity failure: BFS={bfs_state.status!r}, runner={rs.status!r}"
        )

    def test_parity_node_statuses(
        self, harness_linear: Harness, tmp_path: Path
    ) -> None:
        """BFS and runner produce identical node statuses for trigger and agent."""
        bfs_state, _ = _run_bfs(harness_linear, tmp_path)
        wf_state, rs, _ = _run_runner(harness_linear)

        for node_id in ("trigger-1", "agent-1"):
            bfs_status = _node_status_from_bfs(bfs_state, node_id)
            runner_status = _node_status_from_runner(wf_state, node_id)
            assert bfs_status == runner_status, (
                f"Node {node_id!r}: BFS={bfs_status!r}, runner={runner_status!r}"
            )

    def test_bfs_events_contain_agent_transitions(
        self, harness_linear: Harness, tmp_path: Path
    ) -> None:
        """BFS emits node_transition events with in_progress and done for agent."""
        _, bfs_events = _run_bfs(harness_linear, tmp_path)
        statuses = _node_transition_statuses(bfs_events, "agent-1")
        assert "in_progress" in statuses, f"BFS missing in_progress: events={bfs_events}"
        assert "done" in statuses, f"BFS missing done: events={bfs_events}"

    def test_runner_events_contain_agent_transitions(
        self, harness_linear: Harness
    ) -> None:
        """Runner emits node_transition events with in_progress and done for agent."""
        _, _, runner_events = _run_runner(harness_linear)
        statuses = _node_transition_statuses(runner_events, "agent-1")
        assert "in_progress" in statuses, f"Runner missing in_progress: events={runner_events}"
        assert "done" in statuses, f"Runner missing done: events={runner_events}"

    def test_parity_events_agent_transition_coverage(
        self, harness_linear: Harness, tmp_path: Path
    ) -> None:
        """Both BFS and runner emit in_progress and done transitions for agent-1."""
        _, bfs_events = _run_bfs(harness_linear, tmp_path)
        _, _, runner_events = _run_runner(harness_linear)

        bfs_statuses = _node_transition_statuses(bfs_events, "agent-1")
        runner_statuses = _node_transition_statuses(runner_events, "agent-1")

        for expected in ("in_progress", "done"):
            assert expected in bfs_statuses, (
                f"BFS missing {expected!r} transition for agent-1"
            )
            assert expected in runner_statuses, (
                f"Runner missing {expected!r} transition for agent-1"
            )


# ---------------------------------------------------------------------------
# Scenario 2: AGGREGATOR_ALL -- two agents + aggregator(all)
# ---------------------------------------------------------------------------


class TestDecisionAggAllParity:
    """BFS vs runner parity for aggregator(all) harness with direct fan-out.

    The fixture uses a direct fan-out from agent-main to both branches
    (no decision node) so that both BFS and runner visit all nodes.
    The BFS executor follows ALL outgoing edges from a non-decision agent node.
    """

    def test_bfs_outcome_done(
        self, harness_decision_agg_all: Harness, tmp_path: Path
    ) -> None:
        """BFS: agg(all) harness completes with status='done'."""
        run_state, _ = _run_bfs(harness_decision_agg_all, tmp_path)
        assert run_state.status == "done", f"BFS status: {run_state.status!r}"

    def test_runner_outcome_done(self, harness_decision_agg_all: Harness) -> None:
        """Runner: agg(all) harness completes with status='done'."""
        wf_state, rs, _ = _run_runner(harness_decision_agg_all)
        assert wf_state.status == "done", f"Runner status: {wf_state.status!r}"

    def test_parity_outcome(
        self, harness_decision_agg_all: Harness, tmp_path: Path
    ) -> None:
        """BFS and runner produce identical final outcome for agg(all) harness."""
        bfs_state, _ = _run_bfs(harness_decision_agg_all, tmp_path)
        wf_state, rs, _ = _run_runner(harness_decision_agg_all)
        assert bfs_state.status == rs.status, (
            f"Parity failure: BFS={bfs_state.status!r}, runner={rs.status!r}"
        )

    def test_bfs_all_nodes_done(
        self, harness_decision_agg_all: Harness, tmp_path: Path
    ) -> None:
        """BFS: all nodes in agg(all) harness are done."""
        run_state, _ = _run_bfs(harness_decision_agg_all, tmp_path)
        for node_id in ("trigger-1", "agent-main", "branch-a", "branch-b", "agg-all", "agent-final"):
            status = _node_status_from_bfs(run_state, node_id)
            assert status == "done", f"BFS node {node_id!r}: expected done, got {status!r}"

    def test_runner_all_nodes_done(self, harness_decision_agg_all: Harness) -> None:
        """Runner: all agent nodes are done in agg(all) harness."""
        wf_state, rs, _ = _run_runner(harness_decision_agg_all)
        for node_id in ("trigger-1", "agent-main", "branch-a", "branch-b", "agent-final"):
            status = _node_status_from_runner(wf_state, node_id)
            assert status == "done", f"Runner node {node_id!r}: expected done, got {status!r}"

    def test_parity_agent_node_statuses(
        self, harness_decision_agg_all: Harness, tmp_path: Path
    ) -> None:
        """BFS and runner agree on node statuses for all agent nodes."""
        bfs_state, _ = _run_bfs(harness_decision_agg_all, tmp_path)
        wf_state, rs, _ = _run_runner(harness_decision_agg_all)

        for node_id in ("agent-main", "branch-a", "branch-b", "agent-final"):
            bfs_status = _node_status_from_bfs(bfs_state, node_id)
            runner_status = _node_status_from_runner(wf_state, node_id)
            assert bfs_status == runner_status, (
                f"Node {node_id!r}: BFS={bfs_status!r}, runner={runner_status!r}"
            )


# ---------------------------------------------------------------------------
# Scenario 3: AGGREGATOR_ANY -- one agent + aggregator(any)
# ---------------------------------------------------------------------------


class TestDecisionAggAnyParity:
    """BFS vs runner parity for decision -> aggregator(any) harness."""

    def test_bfs_outcome_done(
        self, harness_decision_agg_any: Harness, tmp_path: Path
    ) -> None:
        """BFS: decision+agg(any) harness completes with status='done'."""
        run_state, _ = _run_bfs(harness_decision_agg_any, tmp_path)
        assert run_state.status == "done", f"BFS status: {run_state.status!r}"

    def test_runner_outcome_done(self, harness_decision_agg_any: Harness) -> None:
        """Runner: decision+agg(any) harness completes with status='done'."""
        wf_state, rs, _ = _run_runner(harness_decision_agg_any)
        assert wf_state.status == "done", f"Runner status: {wf_state.status!r}"

    def test_parity_outcome(
        self, harness_decision_agg_any: Harness, tmp_path: Path
    ) -> None:
        """BFS and runner produce identical final outcome for agg(any) harness."""
        bfs_state, _ = _run_bfs(harness_decision_agg_any, tmp_path)
        wf_state, rs, _ = _run_runner(harness_decision_agg_any)
        assert bfs_state.status == rs.status, (
            f"Parity failure: BFS={bfs_state.status!r}, runner={rs.status!r}"
        )

    def test_parity_agent_node_statuses(
        self, harness_decision_agg_any: Harness, tmp_path: Path
    ) -> None:
        """BFS and runner produce identical agent-node statuses for agg(any) harness."""
        bfs_state, _ = _run_bfs(harness_decision_agg_any, tmp_path)
        wf_state, rs, _ = _run_runner(harness_decision_agg_any)

        for node_id in ("agent-main", "branch-a", "agent-final"):
            bfs_status = _node_status_from_bfs(bfs_state, node_id)
            runner_status = _node_status_from_runner(wf_state, node_id)
            assert bfs_status == runner_status, (
                f"Node {node_id!r}: BFS={bfs_status!r}, runner={runner_status!r}"
            )

    def test_bfs_all_nodes_done(
        self, harness_decision_agg_any: Harness, tmp_path: Path
    ) -> None:
        """BFS: all nodes in agg(any) harness reach done status."""
        run_state, _ = _run_bfs(harness_decision_agg_any, tmp_path)
        for node_id in ("trigger-1", "agent-main", "decision-1", "branch-a", "agg-any", "agent-final"):
            status = _node_status_from_bfs(run_state, node_id)
            assert status == "done", f"BFS node {node_id!r}: expected done, got {status!r}"


# ---------------------------------------------------------------------------
# Scenario 4: HUMAN_WAIT -- park + resume
# ---------------------------------------------------------------------------


class TestHumanWaitParity:
    """BFS vs runner parity for human-wait park + resume scenario.

    Parity assertion (first run):
      BFS: RunState.waiting_node_id == 'wait-1'
      Runner: WorkflowState.status == 'blocked' AND nodes['wait-1'].status == 'blocked'

    Resume parity:
      BFS: re-run on the same tmp_path (loads parked RunState from disk); completes.
      Runner: resume is translated into DeliveryRun.resume(HumanAnswer) by
        run_executor._execute_harness_run_runner; end-to-end progression is
        covered in tests/test_delivery_outcomes.py::
        test_harness_human_wait_resume_progresses_run (this class covers the
        park itself).
    """

    def test_bfs_parks_at_wait_node(
        self, harness_human_wait: Harness, tmp_path: Path
    ) -> None:
        """BFS: first run parks at wait node (waiting_node_id='wait-1')."""
        run_state, _ = _run_bfs(harness_human_wait, tmp_path)
        assert run_state.waiting_node_id == "wait-1", (
            f"BFS: expected waiting_node_id='wait-1', got {run_state.waiting_node_id!r}"
        )

    def test_runner_parks_blocked_at_wait_node(self, harness_human_wait: Harness) -> None:
        """Runner: first run produces status='blocked' (human-wait park)."""
        wf_state, rs, _ = _run_runner(harness_human_wait)
        assert wf_state.status == "blocked", (
            f"Runner: expected status='blocked', got {wf_state.status!r}"
        )

    def test_runner_wait_node_blocked_in_wf_state(self, harness_human_wait: Harness) -> None:
        """Runner: wait-1 node is marked 'blocked' in WorkflowState after park."""
        wf_state, rs, _ = _run_runner(harness_human_wait)
        wait_ns = wf_state.nodes.get("wait-1")
        assert wait_ns is not None, "Runner: wait-1 not in WorkflowState.nodes"
        assert wait_ns.status == "blocked", (
            f"Runner: wait-1 status expected 'blocked', got {wait_ns.status!r}"
        )

    def test_bfs_trigger_done_before_park(
        self, harness_human_wait: Harness, tmp_path: Path
    ) -> None:
        """BFS: trigger is done before the run parks at the wait node."""
        run_state, _ = _run_bfs(harness_human_wait, tmp_path)
        trigger_status = _node_status_from_bfs(run_state, "trigger-1")
        assert trigger_status == "done", f"BFS trigger-1: {trigger_status!r}"

    def test_bfs_wait_node_in_progress_when_parked(
        self, harness_human_wait: Harness, tmp_path: Path
    ) -> None:
        """BFS: wait node is in_progress when parked (not done/failed)."""
        run_state, _ = _run_bfs(harness_human_wait, tmp_path)
        wait_status = _node_status_from_bfs(run_state, "wait-1")
        assert wait_status == "in_progress", (
            f"BFS wait-1: expected in_progress, got {wait_status!r}"
        )

    def test_bfs_agent_not_run_on_first_park(
        self, harness_human_wait: Harness, tmp_path: Path
    ) -> None:
        """BFS: agent-final has NOT been run when the run is first parked."""
        run_state, _ = _run_bfs(harness_human_wait, tmp_path)
        agent_status = _node_status_from_bfs(run_state, "agent-final")
        assert agent_status == "pending", (
            f"BFS agent-final: expected pending (not run), got {agent_status!r}"
        )

    def test_parity_park_signal(
        self, harness_human_wait: Harness, tmp_path: Path
    ) -> None:
        """Both BFS and runner signal a human-wait park on first run.

        BFS signals via waiting_node_id; runner signals via WorkflowState.status.
        """
        bfs_state, _ = _run_bfs(harness_human_wait, tmp_path)
        wf_state, rs, _ = _run_runner(harness_human_wait)

        bfs_parked = bfs_state.waiting_node_id == "wait-1"
        runner_parked = wf_state.status == "blocked"

        assert bfs_parked, f"BFS did not park: waiting_node_id={bfs_state.waiting_node_id!r}"
        assert runner_parked, f"Runner did not park: wf_state.status={wf_state.status!r}"

    def test_parity_trigger_done_on_park(
        self, harness_human_wait: Harness, tmp_path: Path
    ) -> None:
        """Both BFS and runner show trigger-1 as done when parked at wait."""
        bfs_state, _ = _run_bfs(harness_human_wait, tmp_path)
        wf_state, rs, _ = _run_runner(harness_human_wait)

        bfs_trigger = _node_status_from_bfs(bfs_state, "trigger-1")
        runner_trigger = _node_status_from_runner(wf_state, "trigger-1")
        assert bfs_trigger == "done", f"BFS trigger-1: {bfs_trigger!r}"
        assert runner_trigger == "done", f"Runner trigger-1: {runner_trigger!r}"

    def test_bfs_resume_completes(
        self, harness_human_wait: Harness, tmp_path: Path
    ) -> None:
        """BFS: after parking, BFS resumes from the parked state and completes.

        The BFS executor persists the RunState to disk on park.  The second
        call to execute() loads the persisted state, detects waiting_node_id,
        and resumes from the wait node's successors.
        """
        # First run -- parks at wait-1.
        parked_state, _ = _run_bfs(harness_human_wait, tmp_path)
        assert parked_state.waiting_node_id == "wait-1", "First run did not park"

        # Second run on same tmp_path -- loads parked state and resumes.
        resumed_state, _ = _run_bfs(harness_human_wait, tmp_path)
        assert resumed_state.status == "done", (
            f"BFS resume: expected status='done', got {resumed_state.status!r}"
        )

    def test_bfs_resume_agent_done(
        self, harness_human_wait: Harness, tmp_path: Path
    ) -> None:
        """BFS resume: agent-final is done after resuming past the wait node."""
        _run_bfs(harness_human_wait, tmp_path)  # first run -- parks
        resumed_state, _ = _run_bfs(harness_human_wait, tmp_path)  # resume
        agent_status = _node_status_from_bfs(resumed_state, "agent-final")
        assert agent_status == "done", f"BFS resume agent-final: {agent_status!r}"

    def test_parity_wait_node_signal(
        self, harness_human_wait: Harness, tmp_path: Path
    ) -> None:
        """Both paths indicate the wait node is involved in the park signal.

        BFS: waiting_node_id='wait-1'.
        Runner: WorkflowState.nodes['wait-1'].status='blocked'.
        Both refer to the same logical node.
        """
        bfs_state, _ = _run_bfs(harness_human_wait, tmp_path)
        wf_state, rs, _ = _run_runner(harness_human_wait)

        assert bfs_state.waiting_node_id == "wait-1", (
            f"BFS waiting_node_id={bfs_state.waiting_node_id!r}"
        )
        runner_wait_ns = wf_state.nodes.get("wait-1")
        assert runner_wait_ns is not None, "Runner wait-1 not in nodes"
        assert runner_wait_ns.status == "blocked", (
            f"Runner wait-1 status={runner_wait_ns.status!r}"
        )


# ---------------------------------------------------------------------------
# Cross-scenario: event schema parity
# ---------------------------------------------------------------------------


class TestEventSchemaParity:
    """Verify that runner and BFS emit events with compatible schemas.

    The BFS HarnessExecutor emits node_transition events with 'to_status';
    the runner path (HarnessExecutorAdapter._TelemetryOps.emit) emits events
    with 'status'.  Both emit 'type', 'node_id', 'from_status', 'timestamp'.
    Tests here verify the shared-key subset and both per-convention keys.
    """

    def test_bfs_node_transition_shared_keys(
        self, harness_linear: Harness, tmp_path: Path
    ) -> None:
        """BFS node_transition events include shared required keys."""
        shared_keys = {"type", "node_id", "from_status", "timestamp"}
        _, bfs_events = _run_bfs(harness_linear, tmp_path)
        bfs_nt = [e for e in bfs_events if e.get("type") == "node_transition"]

        assert bfs_nt, "BFS produced no node_transition events"
        for ev in bfs_nt:
            missing = shared_keys - set(ev.keys())
            assert not missing, f"BFS node_transition missing keys {missing}: {ev}"

    def test_runner_node_transition_shared_keys(
        self, harness_linear: Harness
    ) -> None:
        """Runner node_transition events include shared required keys."""
        shared_keys = {"type", "node_id", "from_status", "timestamp"}
        _, _, runner_events = _run_runner(harness_linear)
        runner_nt = [e for e in runner_events if e.get("type") == "node_transition"]

        assert runner_nt, "Runner produced no node_transition events"
        for ev in runner_nt:
            missing = shared_keys - set(ev.keys())
            assert not missing, f"Runner node_transition missing keys {missing}: {ev}"

    def test_bfs_uses_to_status_key(
        self, harness_linear: Harness, tmp_path: Path
    ) -> None:
        """BFS node_transition events use 'to_status' (not 'status')."""
        _, bfs_events = _run_bfs(harness_linear, tmp_path)
        bfs_nt = [e for e in bfs_events if e.get("type") == "node_transition"]
        assert bfs_nt, "No node_transition events from BFS"
        # BFS uses 'to_status'
        for ev in bfs_nt:
            assert "to_status" in ev, f"BFS event missing 'to_status': {ev}"

    def test_runner_uses_status_key(self, harness_linear: Harness) -> None:
        """Runner node_transition events use 'status' (SSE frontend schema)."""
        _, _, runner_events = _run_runner(harness_linear)
        runner_nt = [e for e in runner_events if e.get("type") == "node_transition"]
        assert runner_nt, "No node_transition events from runner"
        for ev in runner_nt:
            assert "status" in ev, f"Runner event missing 'status': {ev}"

    def test_parity_both_emit_agent_transitions(
        self, harness_linear: Harness, tmp_path: Path
    ) -> None:
        """Both BFS and runner emit node_transition events for the agent node."""
        _, bfs_events = _run_bfs(harness_linear, tmp_path)
        _, _, runner_events = _run_runner(harness_linear)

        bfs_nt = [e for e in bfs_events if e.get("type") == "node_transition" and e.get("node_id") == "agent-1"]
        runner_nt = [e for e in runner_events if e.get("type") == "node_transition" and e.get("node_id") == "agent-1"]

        assert len(bfs_nt) >= 2, f"BFS: expected >=2 events for agent-1, got {bfs_nt}"
        assert len(runner_nt) >= 2, f"Runner: expected >=2 events for agent-1, got {runner_nt}"
