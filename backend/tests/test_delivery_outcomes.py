"""R10d acceptance — ONE Outcome → TaskState interpretation for BOTH hosts.

Kills D16 (00-assessment §2): the delivery driver and the harness runner path
used to interpret the same run terminal differently — the harness path
collapsed ``failed``/``escalated``/``stalled`` workflows to task DONE while
the driver parked WAITING.  Both hosts now finalize through the single shared
table in ``app.delivery_outcomes`` (01-state-model.md §5.6 + §4 matrix).

Layers:
1. ``action_for_outcome`` — the pure table, driven over every Outcome kind.
2. ``apply_outcome_to_task`` — park/finalize semantics (idempotence,
   metadata stamping on an already-WAITING task, only-if-active guard).
3. CROSS-HOST IDENTITY — for each terminal WorkflowState, drive the REAL
   ``run_delivery_goal`` and the REAL ``_execute_harness_run_runner`` with
   the package runner scripted, and assert both hosts finalize the tracking
   task to the IDENTICAL (TaskState, waiting_kind).
4. The D16 regression pin: a harness run whose workflow FAILS parks the
   tracking task WAITING kind='node_failed' (replacing the DONE collapse).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from delivery_workflow.ir import IREdge, IRGraph, IRNode
from delivery_workflow.outcome import Outcome
from delivery_workflow.state_types import BudgetState, NodeState, WorkflowState

from app.delivery_outcomes import (
    OutcomeAction,
    action_for_outcome,
    apply_outcome_to_task,
    park_task_waiting,
)
from app.models import TaskState


# ---------------------------------------------------------------------------
# Layer 1 — the pure table (§5.6 five rows + cancelled + defensive running)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome, expected_state, expected_kind",
    [
        (Outcome(kind="done"), TaskState.DONE, None),
        (
            Outcome(kind="stalled", stall={"kind": "starved_nodes", "nodes": ["x"]}),
            TaskState.WAITING, "stalled",
        ),
        (
            Outcome(kind="failed", node_id="build", reason="boom"),
            TaskState.WAITING, "node_failed",
        ),
        (
            Outcome(kind="blocked", node_id="signoff", question="ok?"),
            TaskState.WAITING, "signoff",
        ),
        # Blocked on a NON-sign-off node (agent self-reported blocked): no
        # Approve/Reject affordance — diagnostic park without a kind.
        (Outcome(kind="blocked", node_id=None), TaskState.WAITING, None),
        (
            Outcome(kind="escalated", escalation="budget", reason="ceiling"),
            TaskState.WAITING, "budget",
        ),
        (
            Outcome(kind="escalated", escalation="loop", node_id="review"),
            TaskState.WAITING, "loop",
        ),
        (
            Outcome(kind="escalated", escalation="iteration_cap"),
            TaskState.WAITING, "loop",
        ),
        (
            Outcome(kind="escalated", escalation="timed_wait", node_id="cooloff"),
            TaskState.WAITING, "escalated",
        ),
        (Outcome(kind="cancelled"), TaskState.WAITING, None),
        # 'running' is the pure-read non-terminal kind; reaching the apply
        # path with it is defensive — never DONE, never left ACTIVE.
        (Outcome(kind="running"), TaskState.WAITING, None),
    ],
)
def test_action_table(outcome: Outcome, expected_state, expected_kind) -> None:
    action = action_for_outcome(outcome)
    assert action.task_state == expected_state
    assert action.waiting_kind == expected_kind


def test_action_table_waiting_kinds_are_valid_model_literals() -> None:
    """Every waiting_kind the table can emit exists in models.WaitingKind."""
    import typing

    from app.models import WaitingKind

    allowed = set(typing.get_args(WaitingKind))
    kinds = {
        action_for_outcome(o).waiting_kind
        for o in (
            Outcome(kind="stalled"),
            Outcome(kind="failed", node_id="n"),
            Outcome(kind="blocked", node_id="s"),
            Outcome(kind="escalated", escalation="budget"),
            Outcome(kind="escalated", escalation="loop"),
            Outcome(kind="escalated", escalation="iteration_cap"),
            Outcome(kind="escalated", escalation="timed_wait"),
        )
    }
    assert kinds <= allowed, f"table emits kinds outside WaitingKind: {kinds - allowed}"


def test_action_blocked_carries_question_and_node() -> None:
    action = action_for_outcome(
        Outcome(kind="blocked", node_id="signoff", question="Right thing?")
    )
    assert action.waiting_node_id == "signoff"
    assert action.message == "Right thing?"
    assert action.only_if_active is True  # never clobber the adapter's park


def test_action_failed_message_names_node_and_offers_retry() -> None:
    action = action_for_outcome(
        Outcome(kind="failed", node_id="build", reason="exit -9")
    )
    assert "build" in action.message
    assert "exit -9" in action.message
    assert "retry" in action.message.lower()
    assert action.only_if_active is False


def test_action_subject_changes_message_never_the_state() -> None:
    for outcome in (
        Outcome(kind="done"),
        Outcome(kind="failed", node_id="n"),
        Outcome(kind="stalled"),
        Outcome(kind="cancelled"),
    ):
        a = action_for_outcome(outcome, subject="Delivery workflow")
        b = action_for_outcome(outcome, subject="Harness run")
        assert (a.task_state, a.waiting_kind, a.waiting_node_id) == (
            b.task_state, b.waiting_kind, b.waiting_node_id,
        )


# ---------------------------------------------------------------------------
# Layer 2 — apply semantics
# ---------------------------------------------------------------------------


def _store_with_task(state: TaskState):
    store = MagicMock()
    store.get.return_value = SimpleNamespace(
        id="t1", state=state, title="T", waiting_question=None,
    )
    store.finalize_run = AsyncMock()
    store.set_waiting_meta = AsyncMock()
    return store


@pytest.mark.asyncio
async def test_apply_done_finalizes_done() -> None:
    store = _store_with_task(TaskState.ACTIVE)
    result = await apply_outcome_to_task(store, "t1", Outcome(kind="done"))
    assert result == TaskState.DONE
    kwargs = store.finalize_run.call_args.kwargs
    assert kwargs["new_state"] == TaskState.DONE
    assert kwargs["waiting_question"] is None


@pytest.mark.asyncio
async def test_apply_done_is_noop_on_already_done_task() -> None:
    store = _store_with_task(TaskState.DONE)
    result = await apply_outcome_to_task(store, "t1", Outcome(kind="done"))
    assert result is None
    store.finalize_run.assert_not_called()


@pytest.mark.asyncio
async def test_apply_failed_parks_with_metadata() -> None:
    store = _store_with_task(TaskState.ACTIVE)
    outcome = Outcome(kind="failed", node_id="build", reason="boom")
    result = await apply_outcome_to_task(store, "t1", outcome)
    assert result == TaskState.WAITING
    kwargs = store.finalize_run.call_args.kwargs
    assert kwargs["new_state"] == TaskState.WAITING
    assert kwargs["waiting_kind"] == "node_failed"
    assert kwargs["waiting_node_id"] == "build"


@pytest.mark.asyncio
async def test_apply_stamps_meta_on_already_waiting_task() -> None:
    """A task the adapter already parked mid-run keeps its question but gets
    the structured §5.6 metadata stamped."""
    store = _store_with_task(TaskState.WAITING)
    outcome = Outcome(kind="blocked", node_id="signoff", question="ok?")
    result = await apply_outcome_to_task(store, "t1", outcome)
    assert result is None
    store.finalize_run.assert_not_called()
    store.set_waiting_meta.assert_awaited_once_with(
        "t1", waiting_kind="signoff", waiting_node_id="signoff",
    )


@pytest.mark.asyncio
async def test_park_only_if_active_skips_terminal_task() -> None:
    store = _store_with_task(TaskState.DONE)
    result = await park_task_waiting(
        store, "t1", "reason", only_if_active=True, waiting_kind="escalated",
    )
    assert result is None
    store.finalize_run.assert_not_called()
    store.set_waiting_meta.assert_not_called()


# ---------------------------------------------------------------------------
# Layer 3 + 4 — CROSS-HOST identity over real host finalization paths
# ---------------------------------------------------------------------------

# Spec for the delivery-goal host (has a human 'signoff' so blocked outcomes
# pin the sign-off exactly like production).
XHOST_SPEC_YAML = """\
apiVersion: delivery/v1
metadata:
  name: xhost
defaults:
  models:
    build: sonnet
  budget:
    usd_ceiling: 5.0
    on_exceed: escalate
nodes:
  - id: scout
    kind: agent
    agent: scout
    model: {use: build}
    produces: {class: research}
  - id: signoff
    kind: human
    prompt: "ok?"
edges:
  - {from: scout, to: signoff}
"""


def _wf(status: str, nodes: dict | None = None, stall: dict | None = None):
    return WorkflowState(
        spec="xhost", run_id="run-1", status=status,  # type: ignore[arg-type]
        budget=BudgetState(usd_ceiling=5.0),
        nodes=nodes or {},
        stall=stall,
    )


#: (scenario, scripted final WorkflowState, expected TaskState, expected kind)
_TERMINAL_SCENARIOS = [
    ("done", _wf("done"), TaskState.DONE, None),
    (
        "stalled",
        _wf("stalled", stall={"kind": "starved_nodes", "nodes": ["signoff"],
                              "reason": "scout dead-ended"}),
        TaskState.WAITING, "stalled",
    ),
    (
        "failed",
        _wf("failed", nodes={"scout": NodeState(status="failed",
                                                fields={"error": "boom"})}),
        TaskState.WAITING, "node_failed",
    ),
    (
        "blocked",
        _wf("blocked", nodes={"signoff": NodeState(status="blocked")}),
        TaskState.WAITING, "signoff",
    ),
    (
        "escalated",
        _wf("escalated", nodes={"scout": NodeState(status="escalated")}),
        TaskState.WAITING, "loop",
    ),
    ("cancelled", _wf("cancelled"), TaskState.WAITING, None),
]


def _scripted_runner(final_state):
    """A runner stub that mirrors production: it persists the final state
    through StateOps (the real runner is the sole state writer) and returns
    it — so a host reading state back sees exactly what it was returned."""

    def run(graph, executor, state_ops=None, host=None, **kw):
        if state_ops is not None and hasattr(state_ops, "write"):
            try:
                patch_dict = {
                    "status": final_state.status,
                    "nodes": {
                        nid: {"status": ns.status, "fields": dict(ns.fields or {})}
                        for nid, ns in final_state.nodes.items()
                    },
                }
                if final_state.stall is not None:
                    patch_dict["stall"] = final_state.stall
                state_ops.write(patch_dict)
            except Exception:
                pass
        return final_state

    return run


def _finalization_of(store) -> tuple:
    """(TaskState, waiting_kind) a host finalized the tracking task to."""
    assert store.finalize_run.call_count == 1, (
        f"expected exactly one finalize_run, got {store.finalize_run.call_count}"
    )
    kwargs = store.finalize_run.call_args.kwargs
    return kwargs["new_state"], kwargs.get("waiting_kind")


async def _drive_delivery_host(tmp_path, final_state) -> tuple:
    """Real run_delivery_goal with the package runner scripted."""
    from app.delivery_driver import run_delivery_goal

    tmp_path.mkdir(parents=True, exist_ok=True)
    spec_file = tmp_path / "workflow.yaml"
    spec_file.write_text(XHOST_SPEC_YAML)
    store = _store_with_task(TaskState.ACTIVE)

    import delivery_workflow.runner as _runner_mod
    original = _runner_mod.run
    _runner_mod.run = _scripted_runner(final_state)
    try:
        with patch("app.delivery_adapter.CronosAdapter") as MockAdapter:
            MockAdapter.return_value = MagicMock()
            await run_delivery_goal(
                goal_id="t1", spec_path="workflow.yaml", store=store,
                trace_store=MagicMock(), space_id="sp",
                space_dir=tmp_path, run_dir=tmp_path / "runs",
            )
    finally:
        _runner_mod.run = original
    return _finalization_of(store)


def _harness_ir_graph() -> IRGraph:
    return IRGraph(
        nodes=[
            IRNode(id="scout", kind="agent"),
            IRNode(id="signoff", kind="human", data={"prompt": "ok?"}),
        ],
        edges=[IREdge(source="scout", target="signoff")],
    )


async def _drive_harness_host(tmp_path, final_state) -> tuple:
    """Real _execute_harness_run_runner with the package runner scripted."""
    from app.run_executor import RunExecutor

    worker = MagicMock()
    worker._publish = AsyncMock(return_value=None)
    store = _store_with_task(TaskState.ACTIVE)
    space_store = MagicMock()
    space_store.spaces_dir = tmp_path / "spaces"

    executor = RunExecutor(
        worker=worker, store=store, event_bus=MagicMock(), finalizer=MagicMock(),
        space_store=space_store, harness_store=MagicMock(), memory_store=None,
        done_sentinel={}, lease_ttl=30.0, heartbeat_interval=10.0,
        memory_retrieval=None,
    )

    import delivery_workflow.runner as _runner_mod
    original = _runner_mod.run
    _runner_mod.run = _scripted_runner(final_state)
    try:
        with patch("app.harnesses.compiler.compile", return_value=_harness_ir_graph()):
            handled = await executor._execute_harness_run_runner(
                "t1", "h1", "sp", initial_run=True, space=MagicMock(),
                run_state_path=tmp_path / "run-state" / "t1.json",
                harness=MagicMock(),
            )
    finally:
        _runner_mod.run = original
    assert handled is True
    return _finalization_of(store)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario, final_state, expected_state, expected_kind",
    _TERMINAL_SCENARIOS,
    ids=[s[0] for s in _TERMINAL_SCENARIOS],
)
async def test_both_hosts_finalize_identically(
    tmp_path, scenario, final_state, expected_state, expected_kind
) -> None:
    """THE R10d acceptance: identical Outcome ⇒ identical TaskState +
    waiting_kind on the delivery-goal host AND the harness host."""
    delivery = await _drive_delivery_host(tmp_path / "delivery", final_state)
    harness = await _drive_harness_host(tmp_path / "harness", final_state)

    assert delivery == harness == (expected_state, expected_kind), (
        f"{scenario}: delivery={delivery} harness={harness} "
        f"expected={(expected_state, expected_kind)}"
    )


@pytest.mark.asyncio
async def test_d16_harness_failed_workflow_parks_waiting_node_failed(tmp_path) -> None:
    """THE D16 regression pin (replaces the old failed→DONE collapse): a
    harness run whose workflow terminates 'failed' parks the tracking task
    WAITING kind='node_failed' with the failing node pinned."""
    failed = _wf(
        "failed", nodes={"scout": NodeState(status="failed",
                                            fields={"error": "agent crashed"})},
    )
    state, kind = await _drive_harness_host(tmp_path, failed)
    assert state == TaskState.WAITING, (
        "a failed harness workflow must park WAITING — task DONE was the D16 "
        "divergence"
    )
    assert kind == "node_failed"


@pytest.mark.asyncio
async def test_d16_harness_stalled_workflow_parks_waiting_not_done(tmp_path) -> None:
    """Pre-R10d the harness path finalized a STALLED run DONE (with the reason
    only in history).  It now parks WAITING kind='stalled'."""
    stalled = _wf(
        "stalled",
        stall={"kind": "gate_exhausted", "nodes": ["g-x"], "reason": "max=3"},
    )
    state, kind = await _drive_harness_host(tmp_path, stalled)
    assert (state, kind) == (TaskState.WAITING, "stalled")


@pytest.mark.asyncio
async def test_harness_blocked_park_pins_waiting_node_in_run_state(tmp_path) -> None:
    """A blocked harness run persists waiting_node_id (the resume-routing key)
    from Outcome.node_id, and the parked wait node renders 'in_progress' in
    the persisted RunState — not 'pending' (the D16-note collision)."""
    from app.harnesses.run_state import load as load_run_state

    blocked = _wf("blocked", nodes={"signoff": NodeState(status="blocked")})
    run_state_path = tmp_path / "run-state" / "t1.json"

    state, kind = await _drive_harness_host(tmp_path, blocked)
    assert (state, kind) == (TaskState.WAITING, "signoff")

    persisted = load_run_state(run_state_path)
    assert persisted is not None
    assert persisted.waiting_node_id == "signoff"
    assert persisted.nodes_executed["signoff"].status == "in_progress"


@pytest.mark.asyncio
async def test_harness_human_wait_resume_progresses_run(tmp_path) -> None:
    """R10d follow-up: a reply (or Approve) on a runner-path human-wait park
    is translated into ``DeliveryRun.resume(HumanAnswer)`` and actually
    advances the run — previously the resume path always called ``start()``,
    the answer was discarded and the run re-parked identically forever.

    Uses the REAL runner (no scripting): the persisted RunState rebuilds the
    'blocked' park, the HumanAnswer completes the sign-off, and the run
    finishes 'done' → tracking task DONE, waiting_node_id cleared."""
    from app.harnesses.run_state import NodeState as HNodeState
    from app.harnesses.run_state import RunState as HRunState
    from app.harnesses.run_state import load as load_run_state, save_atomic
    from app.run_executor import RunExecutor

    worker = MagicMock()
    worker._publish = AsyncMock(return_value=None)
    store = _store_with_task(TaskState.ACTIVE)
    space_store = MagicMock()
    space_store.spaces_dir = tmp_path / "spaces"

    executor = RunExecutor(
        worker=worker, store=store, event_bus=MagicMock(), finalizer=MagicMock(),
        space_store=space_store, harness_store=MagicMock(), memory_store=None,
        done_sentinel={}, lease_ttl=30.0, heartbeat_interval=10.0,
        memory_retrieval=None,
    )

    # The parked persisted RunState exactly as a blocked first run writes it:
    # run 'running' (UI vocabulary has no 'blocked'), the parked human node
    # 'in_progress', waiting_node_id pinned (the resume-routing key).
    run_state_path = tmp_path / "run-state" / "t1.json"
    run_state_path.parent.mkdir(parents=True, exist_ok=True)
    parked = HRunState(
        run_id="t1", harness_id="h1", goal_task_id="t1",
        nodes_executed={
            "scout": HNodeState(status="done"),
            "signoff": HNodeState(status="in_progress"),
        },
        status="running",
        waiting_node_id="signoff",
    )
    save_atomic(run_state_path, parked)

    with patch("app.harnesses.compiler.compile", return_value=_harness_ir_graph()):
        handled = await executor._execute_harness_run_runner(
            "t1", "h1", "sp", initial_run=False, space=MagicMock(),
            run_state_path=run_state_path, harness=MagicMock(),
            user_message="looks good", verdict="approve",
        )

    assert handled is True
    state, kind = _finalization_of(store)
    assert (state, kind) == (TaskState.DONE, None), (
        "an approved sign-off must let the run progress to done — a re-park "
        "means the HumanAnswer was never applied"
    )
    persisted = load_run_state(run_state_path)
    assert persisted is not None
    assert persisted.status == "done"
    assert persisted.nodes_executed["signoff"].status == "done"
    assert persisted.waiting_node_id is None, (
        "a completed run must not keep a stale park pin (resume_harness_run "
        "would re-enter it forever)"
    )


@pytest.mark.asyncio
async def test_harness_human_wait_silent_reentry_reparks(tmp_path) -> None:
    """D10 on the harness path: re-entering a parked run with NO reply and NO
    verdict must NOT approve the sign-off — the rebuilt 'blocked' state seals
    start() and the task re-parks WAITING kind='signoff'."""
    from app.harnesses.run_state import NodeState as HNodeState
    from app.harnesses.run_state import RunState as HRunState
    from app.harnesses.run_state import load as load_run_state, save_atomic
    from app.run_executor import RunExecutor

    worker = MagicMock()
    worker._publish = AsyncMock(return_value=None)
    store = _store_with_task(TaskState.ACTIVE)
    space_store = MagicMock()
    space_store.spaces_dir = tmp_path / "spaces"

    executor = RunExecutor(
        worker=worker, store=store, event_bus=MagicMock(), finalizer=MagicMock(),
        space_store=space_store, harness_store=MagicMock(), memory_store=None,
        done_sentinel={}, lease_ttl=30.0, heartbeat_interval=10.0,
        memory_retrieval=None,
    )

    run_state_path = tmp_path / "run-state" / "t1.json"
    run_state_path.parent.mkdir(parents=True, exist_ok=True)
    parked = HRunState(
        run_id="t1", harness_id="h1", goal_task_id="t1",
        nodes_executed={
            "scout": HNodeState(status="done"),
            "signoff": HNodeState(status="in_progress"),
        },
        status="running",
        waiting_node_id="signoff",
    )
    save_atomic(run_state_path, parked)

    with patch("app.harnesses.compiler.compile", return_value=_harness_ir_graph()):
        handled = await executor._execute_harness_run_runner(
            "t1", "h1", "sp", initial_run=False, space=MagicMock(),
            run_state_path=run_state_path, harness=MagicMock(),
        )

    assert handled is True
    state, kind = _finalization_of(store)
    assert (state, kind) == (TaskState.WAITING, "signoff")
    persisted = load_run_state(run_state_path)
    assert persisted is not None
    assert persisted.waiting_node_id == "signoff"
    assert persisted.nodes_executed["signoff"].status == "in_progress"
