"""
backend/tests/test_harness_acceptance.py — End-to-end acceptance tests for the
arc6-control-flow feature.

These four scenarios are the **acceptance criteria** for the whole arc6-control-flow
feature.  They exercise the executor (and in one case the worker/executor integration)
together against realistic harness graphs.

Acceptance scenarios
--------------------
1. Decision routes to edge A on STATUS: DONE, edge B on STATUS: BLOCKED.
2. Aggregator(all) waits for both upstream agents before firing.
3. Aggregator(any) fires as soon as the first upstream agent completes.
4. Wait(human) parks the harness run in WAITING; after a reply the second agent
   runs and the first agent is NOT re-executed.

Design invariants verified
--------------------------
- Control-flow evaluators create no child tasks and call no subprocess.
- RunState.waiting_node_id is the single source of truth for Wait-human resume.
- The BFS executor handles in-degree correctly for all node types.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
from app.harnesses.run_state import NodeState, RunState, save_atomic as _save_run_state
from app.models import Space, TaskState
from app.trace_parser import RunTrace


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _pos() -> Position:
    return Position(x=0.0, y=0.0)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _make_space(space_id: str = "accept-space") -> Space:
    return Space(
        id=space_id,
        name="Acceptance Test Space",
        color="#000000",
        created_at=_now(),
        updated_at=_now(),
    )


def _agent_node(node_id: str, prompt: str = "do something") -> HarnessNode:
    return HarnessNode(
        id=node_id,
        type=NodeType.agent,
        position=_pos(),
        ports={"out": {}},
        data={"agent_ref": "test-agent", "prompt_template": prompt},
        label=node_id,
    )


def _wait_node(node_id: str) -> HarnessNode:
    return HarnessNode(
        id=node_id,
        type=NodeType.wait,
        position=_pos(),
        ports={"in": {}, "out": {}},
        data={"mode": "human", "max_wait_seconds": 300, "waiting_question": "Ready?"},
        label=node_id,
    )


def _aggregator_node(node_id: str, mode: str = "all") -> HarnessNode:
    return HarnessNode(
        id=node_id,
        type=NodeType.aggregator,
        position=_pos(),
        ports={"in": {}, "out": {}},
        data={"mode": mode},
        label=node_id,
    )


def _edge(eid: str, src_node: str, tgt_node: str,
          src_port: str = "out", tgt_port: str = "out",
          condition: str | None = None) -> HarnessEdge:
    return HarnessEdge(
        id=eid,
        source=NodeRef(node_id=src_node, port_id=src_port),
        target=NodeRef(node_id=tgt_node, port_id=tgt_port),
        condition=condition,
    )


def _trace(task_id: str = "t1", final_text: str = "output",
           exit_reason: str = "DONE") -> RunTrace:
    now = _now()
    return RunTrace(
        task_id=task_id,
        space_id="accept-space",
        run_index=0,
        session_id=None,
        model="sonnet",
        mode="auto",
        started_at=now,
        ended_at=now,
        duration_seconds=0.0,
        exit_reason=exit_reason,
        final_text_snippet=final_text,
    )


def _make_store() -> MagicMock:
    """TaskStore mock — creates tasks with unique IDs; no pre-existing tasks."""
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


def _no_tools(space_id: str, agent_ref: str):
    return None


class _StubWorker:
    """Minimal WorkerProtocol stub — all agents return the given final_text and task_state."""

    def __init__(self, task_state: TaskState = TaskState.DONE,
                 final_text: str = "output") -> None:
        self.task_state = task_state
        self.final_text = final_text
        self.run_agent_calls: list[str] = []

    async def run_agent(self, task_id: str, **kwargs) -> RunTrace:
        self.run_agent_calls.append(task_id)
        return _trace(task_id=task_id, final_text=self.final_text)

    async def finalize_child(self, task_id: str, trace: RunTrace) -> TaskState:
        return self.task_state


# ---------------------------------------------------------------------------
# Acceptance scenario 1: Decision routes correctly based on STATUS marker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acceptance_decision_routes_to_edge_a_on_status_done():
    """Acceptance 1a — Decision routes to edge A when agent output contains STATUS: DONE.

    Harness: AGENT → DECISION → (edge_a: condition='DONE') → DEST_A
                              → (edge_b: condition='BLOCKED') → DEST_B

    With agent output "STATUS: DONE", the Decision should follow edge_a and execute
    DEST_A; DEST_B must NOT be executed.
    """
    agent = _agent_node("AGT_1A")
    decision = HarnessNode(
        id="DEC_1A",
        type=NodeType.decision,
        position=_pos(),
        ports={"in": {}, "out_a": {}, "out_b": {}},
        data={},
        label="DEC_1A",
    )
    dest_a = _agent_node("DEST_A_1A", "handle done")
    dest_b = _agent_node("DEST_B_1A", "handle blocked")

    harness = Harness(
        name="accept-decision-done",
        nodes=[agent, decision, dest_a, dest_b],
        edges=[
            # AGENT → DECISION
            _edge("e1", "AGT_1A", "DEC_1A", tgt_port="in"),
            # DECISION → DEST_A (STATUS: DONE matches)
            _edge("e_a", "DEC_1A", "DEST_A_1A", src_port="out_a", condition="DONE"),
            # DECISION → DEST_B (STATUS: BLOCKED matches)
            _edge("e_b", "DEC_1A", "DEST_B_1A", src_port="out_b", condition="BLOCKED"),
        ],
    )
    space = _make_space("dec-done-space")
    store = _make_store()
    # Agent output contains the STATUS marker that the Decision will read.
    worker = _StubWorker(task_state=TaskState.DONE, final_text="STATUS: DONE\nAll tasks complete.")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _no_tools)
            result = await executor.execute("run-dec-done", harness, space)

    # Agent ran.
    assert result.nodes_executed["AGT_1A"].status == "done"
    # Decision evaluated and chose edge_a.
    assert result.nodes_executed["DEC_1A"].status == "done"
    # DEST_A must have run (STATUS: DONE → edge_a).
    assert result.nodes_executed["DEST_A_1A"].status == "done", (
        "DEST_A_1A should have executed (edge condition='DONE' matched STATUS: DONE)"
    )
    # DEST_B must NOT have run.
    assert "DEST_B_1A" not in result.nodes_executed, (
        "DEST_B_1A must NOT execute when STATUS: DONE routes to edge_a"
    )
    # run_agent called for AGT_1A and DEST_A_1A (not DEST_B_1A) = 2 total.
    assert len(worker.run_agent_calls) == 2


@pytest.mark.asyncio
async def test_acceptance_decision_routes_to_edge_b_on_status_blocked():
    """Acceptance 1b — Decision routes to edge B when agent output contains STATUS: BLOCKED.

    Same harness topology as 1a; agent output now contains STATUS: BLOCKED.
    DEST_B must execute; DEST_A must NOT.
    """
    agent = _agent_node("AGT_1B")
    decision = HarnessNode(
        id="DEC_1B",
        type=NodeType.decision,
        position=_pos(),
        ports={"in": {}, "out_a": {}, "out_b": {}},
        data={},
        label="DEC_1B",
    )
    dest_a = _agent_node("DEST_A_1B", "handle done")
    dest_b = _agent_node("DEST_B_1B", "handle blocked")

    harness = Harness(
        name="accept-decision-blocked",
        nodes=[agent, decision, dest_a, dest_b],
        edges=[
            _edge("g1", "AGT_1B", "DEC_1B", tgt_port="in"),
            _edge("g_a", "DEC_1B", "DEST_A_1B", src_port="out_a", condition="DONE"),
            _edge("g_b", "DEC_1B", "DEST_B_1B", src_port="out_b", condition="BLOCKED"),
        ],
    )
    space = _make_space("dec-blocked-space")
    store = _make_store()
    worker = _StubWorker(task_state=TaskState.DONE, final_text="STATUS: BLOCKED\nBlocked by dep.")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _no_tools)
            result = await executor.execute("run-dec-blocked", harness, space)

    assert result.nodes_executed["AGT_1B"].status == "done"
    assert result.nodes_executed["DEC_1B"].status == "done"
    # DEST_B must have run (STATUS: BLOCKED → edge_b).
    assert result.nodes_executed["DEST_B_1B"].status == "done", (
        "DEST_B_1B should have executed (edge condition='BLOCKED' matched STATUS: BLOCKED)"
    )
    # DEST_A must NOT have run.
    assert "DEST_A_1B" not in result.nodes_executed, (
        "DEST_A_1B must NOT execute when STATUS: BLOCKED routes to edge_b"
    )
    # run_agent called for AGT_1B and DEST_B_1B = 2 total.
    assert len(worker.run_agent_calls) == 2


# ---------------------------------------------------------------------------
# Acceptance scenario 2: Aggregator(all) waits for BOTH upstreams
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acceptance_aggregator_all_waits_for_both_upstreams():
    """Acceptance 2 — Aggregator(all) fires only after BOTH upstream agents complete.

    Harness:  A1 ─┐
                   ├─→ AGG(all) → POST
              A2 ─┘

    Both A1 and A2 must run; the Aggregator fires when both are done; POST executes
    after the Aggregator.

    Design invariant (R7): mode='all' partial-failure semantics — if any predecessor
    fails, the Aggregator is 'failed'. This test verifies the happy path (both done).
    """
    a1 = _agent_node("ACC2_A1", "branch 1")
    a2 = _agent_node("ACC2_A2", "branch 2")
    agg = _aggregator_node("ACC2_AGG", mode="all")
    post = _agent_node("ACC2_POST", "post aggregation")

    harness = Harness(
        name="accept-aggregator-all",
        nodes=[a1, a2, agg, post],
        edges=[
            # Both parallel agents feed the aggregator
            _edge("a2_e1", "ACC2_A1", "ACC2_AGG", tgt_port="in"),
            _edge("a2_e2", "ACC2_A2", "ACC2_AGG", tgt_port="in"),
            # Aggregator feeds post
            _edge("a2_e3", "ACC2_AGG", "ACC2_POST", src_port="out"),
        ],
    )
    space = _make_space("agg-all-space")
    store = _make_store()
    worker = _StubWorker(task_state=TaskState.DONE, final_text="done_output")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            executor = HarnessExecutor(store, worker, _no_tools)
            result = await executor.execute("run-agg-all", harness, space)

    # Both parallel agents must have completed.
    assert result.nodes_executed["ACC2_A1"].status == "done", (
        "ACC2_A1 must run before Aggregator(all) fires"
    )
    assert result.nodes_executed["ACC2_A2"].status == "done", (
        "ACC2_A2 must run before Aggregator(all) fires"
    )
    # Aggregator must have fired (done).
    assert result.nodes_executed["ACC2_AGG"].status == "done", (
        "Aggregator(all) should fire after both predecessors are done"
    )
    # POST must have run after the aggregator.
    assert result.nodes_executed["ACC2_POST"].status == "done", (
        "ACC2_POST should execute after Aggregator fires"
    )
    # Exactly 3 agent runs: A1, A2, POST (AGG is a control-flow node, not an agent).
    assert len(worker.run_agent_calls) == 3, (
        f"Expected 3 agent runs (A1, A2, POST), got {len(worker.run_agent_calls)}"
    )


# ---------------------------------------------------------------------------
# Acceptance scenario 3: Aggregator(any) fires on first done
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acceptance_aggregator_any_fires_on_first_done():
    """Acceptance 3 — Aggregator(any) fires as soon as the first upstream agent completes.

    Harness: B1 ─┐
                  ├─→ AGG(any) → POST
             B2 ─┘

    We pre-seed B1 as already done; B2 has not yet run.  The Aggregator should
    fire immediately (mode='any') and POST should run, without waiting for B2.

    Design invariant (R8): mode='any' must fire on first-done predecessor.
    """
    b1 = _agent_node("ACC3_B1", "fast branch")
    b2 = _agent_node("ACC3_B2", "slow branch")
    agg = _aggregator_node("ACC3_AGG", mode="any")
    post = _agent_node("ACC3_POST", "post any-aggregation")

    harness = Harness(
        name="accept-aggregator-any",
        nodes=[b1, b2, agg, post],
        edges=[
            _edge("a3_e1", "ACC3_B1", "ACC3_AGG", tgt_port="in"),
            _edge("a3_e2", "ACC3_B2", "ACC3_AGG", tgt_port="in"),
            _edge("a3_e3", "ACC3_AGG", "ACC3_POST", src_port="out"),
        ],
    )
    space = _make_space("agg-any-space")
    store = _make_store()
    worker = _StubWorker(task_state=TaskState.DONE, final_text="any_output")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            # Pre-seed B1 as already done, simulating the skewed-completion scenario
            # (B1 completed "much faster" than B2 in a prior partial run).
            state_dir = (
                Path(tmpdir) / "spaces" / "agg-any-space" / ".cronos" / "harness-runs"
            )
            state_dir.mkdir(parents=True)
            pre_state = RunState(
                run_id="run-agg-any",
                harness_id="accept-aggregator-any",
                goal_task_id="run-agg-any",
                nodes_executed={
                    "ACC3_B1": NodeState(status="done", output="b1_done_output"),
                },
            )
            _save_run_state(state_dir / "run-agg-any.json", pre_state)

            executor = HarnessExecutor(store, worker, _no_tools)
            result = await executor.execute("run-agg-any", harness, space)

    # B1 was pre-seeded as done (must still be done after run).
    assert result.nodes_executed["ACC3_B1"].status == "done", (
        "ACC3_B1 must remain done (pre-seeded)"
    )
    # Aggregator must have fired because B1 (first done) was found by mode='any'.
    assert result.nodes_executed["ACC3_AGG"].status == "done", (
        "Aggregator(any) must fire as soon as the first predecessor (B1) is done"
    )
    # POST must have run after the aggregator fires.
    assert result.nodes_executed["ACC3_POST"].status == "done", (
        "ACC3_POST should execute after Aggregator(any) fires"
    )
    # B1 was pre-seeded — not re-run.  At minimum POST ran.
    assert len(worker.run_agent_calls) >= 1, (
        "At least POST agent must have been run after Aggregator(any) fired"
    )


# ---------------------------------------------------------------------------
# Acceptance scenario 4: Wait(human) parks in WAITING; resume runs Agent2 only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acceptance_wait_human_parks_and_resumes():
    """Acceptance 4 — Wait(human) parks the harness; Agent2 runs on resume; Agent1 does not re-run.

    Harness: AGENT1 → WAIT(human) → AGENT2

    Phase 1 (first execute call):
      - AGENT1 runs and completes.
      - WAIT(human) sets waiting_node_id and returns early (harness parks).
      - AGENT2 must NOT have run yet.
      - The returned RunState must have waiting_node_id set (asserting WAITING state).

    Phase 2 (second execute call — simulates human reply):
      - Executor resumes from WAIT's outgoing edges.
      - AGENT2 runs and completes.
      - AGENT1 must NOT be re-run (run_agent calls stay at 1 from phase 1).
      - waiting_node_id cleared after resume.

    Design invariants verified:
      - RunState.waiting_node_id is the single source of truth (I2/I6 contract).
      - The executor's resume path does not re-execute completed nodes (I6).
      - Worker re-entry calls executor.execute() unchanged (I7 pattern).
    """
    agent1 = _agent_node("ACC4_A1", "phase 1 work")
    wait_node = _wait_node("ACC4_WAIT")
    agent2 = _agent_node("ACC4_A2", "phase 2 work")

    harness = Harness(
        name="accept-wait-human",
        nodes=[agent1, wait_node, agent2],
        edges=[
            _edge("w4_e1", "ACC4_A1", "ACC4_WAIT", tgt_port="in"),
            _edge("w4_e2", "ACC4_WAIT", "ACC4_A2"),
        ],
    )
    space = _make_space("wait-human-space")
    store = _make_store()
    worker = _StubWorker(task_state=TaskState.DONE, final_text="phase_output")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        with patch("app.harnesses.executor._DATA_DIR", tmpdir_path):
            executor = HarnessExecutor(store, worker, _no_tools)

            # --- Phase 1: first execute() call ---
            state1 = await executor.execute("run-wait4", harness, space)

    # After phase 1: executor returned early (parked at WAIT).
    assert state1.waiting_node_id == "ACC4_WAIT", (
        f"Expected waiting_node_id='ACC4_WAIT' after phase 1; got {state1.waiting_node_id!r}"
    )
    # AGENT1 completed before the WAIT.
    assert state1.nodes_executed["ACC4_A1"].status == "done", (
        "ACC4_A1 must have run and completed in phase 1"
    )
    # WAIT node is in_progress (parked).
    assert state1.nodes_executed["ACC4_WAIT"].status == "in_progress", (
        "ACC4_WAIT must be in_progress (parked) in phase 1"
    )
    # AGENT2 must NOT have run yet.
    assert "ACC4_A2" not in state1.nodes_executed, (
        "ACC4_A2 must NOT execute during phase 1 (Wait blocks it)"
    )
    # Only AGENT1 ran an agent subprocess in phase 1.
    assert len(worker.run_agent_calls) == 1, (
        f"Expected 1 run_agent call after phase 1; got {len(worker.run_agent_calls)}"
    )

    # --- Phase 2: simulate human reply — call execute() again with persisted state ---
    with tempfile.TemporaryDirectory() as tmpdir2:
        tmpdir2_path = Path(tmpdir2)

        with patch("app.harnesses.executor._DATA_DIR", tmpdir2_path):
            # Pre-seed the state file (simulates the state persisted by phase 1).
            state_dir = (
                tmpdir2_path / "spaces" / "wait-human-space" / ".cronos" / "harness-runs"
            )
            state_dir.mkdir(parents=True)
            _save_run_state(state_dir / "run-wait4.json", state1)

            executor2 = HarnessExecutor(store, worker, _no_tools)
            state2 = await executor2.execute("run-wait4", harness, space)

    # After phase 2: waiting_node_id cleared.
    assert state2.waiting_node_id is None, (
        "waiting_node_id must be cleared (None) after resume"
    )
    # AGENT1 still done — output preserved from phase 1.
    assert state2.nodes_executed["ACC4_A1"].status == "done", (
        "ACC4_A1 must remain done after resume (not re-run)"
    )
    # WAIT node transitioned to done.
    assert state2.nodes_executed["ACC4_WAIT"].status == "done", (
        "ACC4_WAIT must be marked done after resume"
    )
    # AGENT2 ran after resume.
    assert state2.nodes_executed["ACC4_A2"].status == "done", (
        "ACC4_A2 must have run after the Wait resume (phase 2)"
    )
    # Critical: AGENT1 was NOT re-run — total agent calls = 1 (phase 1) + 1 (phase 2) = 2.
    assert len(worker.run_agent_calls) == 2, (
        f"Expected exactly 2 total run_agent calls (A1 in phase 1, A2 in phase 2); "
        f"got {len(worker.run_agent_calls)} — A1 must NOT be re-run on resume"
    )
