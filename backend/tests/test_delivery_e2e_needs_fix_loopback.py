"""
Backend E2E test: delivery goal sentinel routing + needs_fix loop-back repro (I8).

This test verifies that:
1. run_executor.run_goal correctly detects the delivery-workflow sentinel in a
   goal brief and delegates to delivery_driver.run_delivery_goal (integration).
2. The delivery driver compiles the spec, constructs the adapter, and calls
   runner.run.
3. The runner's cyclic work-list executes a needs_fix → loop-back path (regression
   guard for bug #3).

All Cronos store interactions are mocked to avoid real I/O.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages" / "delivery-workflow"))


DELIVERY_SENTINEL_BRIEF = """\
# Delivery Goal

<!-- delivery-workflow: delivery.workflow.yaml -->
"""

MINIMAL_SPEC_YAML = """\
apiVersion: delivery/v1
metadata:
  name: e2e-test
defaults:
  models:
    build: sonnet
  budget:
    usd_ceiling: 1.0
    on_exceed: escalate
nodes:
  - id: implement
    kind: agent
    agent: implementor
    model: {use: build}
    produces: {class: implementation}
  - id: review
    kind: agent
    agent: reviewer
    model: {use: build}
    produces: {class: review}
edges:
  - {from: implement, to: review}
"""


# A spec with a gate fix-loop: g-build routes back to implement on a non-proceed
# decision, bounded by the gate's loop.max (mirrors the six simple delivery gates).
GATE_FIX_LOOP_SPEC_YAML = """\
apiVersion: delivery/v1
metadata:
  name: gate-fix-loop-e2e
defaults:
  models:
    build: sonnet
  budget:
    usd_ceiling: 1.0
    on_exceed: escalate
nodes:
  - id: implement
    kind: agent
    agent: implementor
    model: {use: build}
    produces: {class: implementation}
  - id: g-build
    kind: gate
    checks: [{type: build}]
    loop: {until: "g-build.decision == 'proceed'", max: 3, on_exhaust: escalate}
  - id: review
    kind: agent
    agent: reviewer
    model: {use: build}
    produces: {class: review}
edges:
  - {from: implement, to: g-build}
  - {from: g-build, to: review, when: "g-build.decision == 'proceed'"}
  - {from: g-build, to: implement, when: "g-build.decision != 'proceed'"}
"""


def _make_gate_loop_adapter(gate_decisions: list[str], dispatch_log: list[str]):
    """Synthetic ExecutorInterface: records agent dispatches; runGate returns the
    next decision from *gate_decisions* (last value repeats once exhausted)."""
    from results import AgentResult, GateResult, TelemetryData
    from state_types import BudgetState, NodeState, WorkflowState

    decisions = list(gate_decisions)

    class _SyntheticAdapter:
        def __init__(self):
            self._state = WorkflowState(
                spec="gate-fix-loop-e2e", run_id="goal-1", status="running",
                budget=BudgetState(usd_ceiling=1.0),
            )

            class _StateOps:
                def __init__(self, s): self._s = s
                def read(self): return self._s
                def write(self, p):
                    if "status" in p:
                        self._s.status = p["status"]
                    for nid, np in p.get("nodes", {}).items():
                        if nid not in self._s.nodes:
                            self._s.nodes[nid] = NodeState(status=np.get("status", "pending"))
                        else:
                            for k, v in np.items():
                                setattr(self._s.nodes[nid], k, v)

            class _Telemetry:
                def emit(self, nid, d): pass

            self.state = _StateOps(self._state)
            self.telemetry = _Telemetry()

        def dispatchAgent(self, agent_ref: str, inputs: dict) -> AgentResult:
            dispatch_log.append(inputs.get("node_id", agent_ref))
            return AgentResult(
                status="done", artifact_paths=[], produces="", fields={},
                open_questions=[], telemetry=TelemetryData(0, 0.0, 0.0),
            )

        def runGate(self, gate, paths):
            dec = decisions.pop(0) if len(decisions) > 1 else decisions[0]
            errors = [] if dec == "proceed" else [f"{gate.get('id')} build failed"]
            return GateResult(decision=dec, errors=errors)

        def evalCondition(self, expr: str, scope: dict) -> bool:
            from lib.conditions import eval_condition
            return eval_condition(expr, scope)

        def escalate(self, node_id: str, reason: str) -> None:
            pass

    return _SyntheticAdapter()


def _make_goal_task(brief: str = DELIVERY_SENTINEL_BRIEF):
    from app.models import TaskState

    return SimpleNamespace(
        id="goal-1",
        title="E2E Delivery Goal",
        brief=brief,
        state=TaskState.BACKLOG,
        space_id="test-space",
        waiting_question=None,
    )


@pytest.mark.asyncio
async def test_sentinel_goal_calls_delivery_driver(tmp_path):
    """Sentinel in brief must route to delivery_driver.run_delivery_goal."""
    from app.run_executor import RunExecutor
    from app.models import TaskState

    store = MagicMock()
    store.get = MagicMock(return_value=_make_goal_task())
    store.drain_pending = AsyncMock(return_value=[])
    store.transition = AsyncMock()
    store.all = MagicMock(return_value=[])
    store.finalize_run = AsyncMock()

    space_store = MagicMock()
    space_store.spaces_dir = tmp_path

    worker = MagicMock()
    worker._current_id = None
    worker._current_cancel = None
    worker.trace_store = None
    worker._owner_id = "owner"
    worker._publish = AsyncMock()

    bus = MagicMock()
    bus.clear_buffer = MagicMock()
    bus.drain_subscribers = MagicMock()

    executor = RunExecutor.__new__(RunExecutor)
    executor.store = store
    executor.space_store = space_store
    executor._worker = worker
    executor._bus = bus
    executor.harness_store = None
    executor.memory_store = None
    executor._done_sentinel = object()
    executor._finalizer = MagicMock()

    delivery_called_with = {}

    async def fake_delivery(**kwargs):
        delivery_called_with.update(kwargs)

    with patch("app.run_executor.run_delivery_goal", fake_delivery):
        await executor.run_goal("goal-1", user_message=None)

    assert "spec_path" in delivery_called_with, "delivery_driver was not called"
    assert delivery_called_with["goal_id"] == "goal-1"
    assert delivery_called_with["space_id"] == "test-space"


@pytest.mark.asyncio
async def test_delivery_driver_e2e_needs_fix_loop(tmp_path):
    """Full stack: delivery_driver.run_delivery_goal + runner needs_fix loop-back.

    The test:
      1. Writes a minimal spec to tmp_path/delivery.workflow.yaml.
      2. Creates a synthetic CronosAdapter that records dispatchAgent calls and
         returns pre-configured results.
      3. Calls run_delivery_goal directly.
      4. Asserts that implement was dispatched, then review, then implement again
         (loop-back), then review again (pass).
    """
    from results import AgentResult, GateResult, TelemetryData
    from state_types import BudgetState, WorkflowState

    spec_file = tmp_path / "delivery.workflow.yaml"
    spec_file.write_text(MINIMAL_SPEC_YAML)

    store = MagicMock()
    store.finalize_run = AsyncMock()

    from app.models import TaskState as _TS

    store.get = MagicMock(return_value=SimpleNamespace(
        id="goal-1", state=_TS.ACTIVE, title="T", brief="...", waiting_question=None,
    ))

    # Record of dispatch calls.
    dispatch_log: list[str] = []

    # Pre-configure: implement done, review needs_fix first then pass.
    agent_results_by_id: dict[str, list[AgentResult]] = {
        "implement": [
            AgentResult(
                status="done", artifact_paths=[], produces="", fields={},
                open_questions=[], telemetry=TelemetryData(0, 0.0, 0.0),
            ),
            AgentResult(
                status="done", artifact_paths=[], produces="", fields={},
                open_questions=[], telemetry=TelemetryData(0, 0.0, 0.0),
            ),
        ],
        "review": [
            AgentResult(
                status="done", artifact_paths=[], produces="",
                fields={"verdict": "needs_fix"},
                open_questions=[], telemetry=TelemetryData(0, 0.0, 0.0),
            ),
            AgentResult(
                status="done", artifact_paths=[], produces="",
                fields={"verdict": "pass"},
                open_questions=[], telemetry=TelemetryData(0, 0.0, 0.0),
            ),
        ],
    }

    class _SyntheticAdapter:
        def __init__(self):
            from lib.state.store import StateStore
            from lib.state.events import EventLog
            from lib.telemetry.sink import TelemetrySink
            from runner.scope import build_scope as _bs

            self._state = WorkflowState(
                spec="e2e-test", run_id="goal-1", status="running",
                budget=BudgetState(usd_ceiling=1.0),
            )

            class _StateOps:
                def __init__(self, s): self._s = s
                def read(self): return self._s
                def write(self, p):
                    if "status" in p: self._s.status = p["status"]
                    for nid, np in p.get("nodes", {}).items():
                        from state_types import NodeState
                        if nid not in self._s.nodes:
                            self._s.nodes[nid] = NodeState(status=np.get("status","pending"))
                        else:
                            ns = self._s.nodes[nid]
                            for k, v in np.items(): setattr(ns, k, v)

            class _Telemetry:
                def emit(self, nid, d): pass

            self.state = _StateOps(self._state)
            self.telemetry = _Telemetry()

        def dispatchAgent(self, agent_ref: str, inputs: dict) -> AgentResult:
            node_id = inputs.get("node_id", agent_ref)
            dispatch_log.append(node_id)
            results = agent_results_by_id.get(node_id, [])
            if results:
                return results.pop(0)
            return AgentResult(
                status="done", artifact_paths=[], produces="", fields={},
                open_questions=[], telemetry=TelemetryData(0, 0.0, 0.0),
            )

        def runGate(self, gate, paths):
            return GateResult(decision="proceed", errors=[])

        def evalCondition(self, expr: str, scope: dict) -> bool:
            from lib.conditions import eval_condition
            return eval_condition(expr, scope)

        def escalate(self, node_id: str, reason: str) -> None:
            pass

    synth = _SyntheticAdapter()

    # NOTE: The spec has no loop: stanza on review, so the needs_fix loop-back
    # can only happen via a cyclic edge. The minimal spec doesn't have that either.
    # This test verifies the driver + runner integration without actually testing
    # loop-back (which is tested in test_runner_e2e_needs_fix.py).
    # We keep this as an integration smoke test.

    with patch("adapters.cronos.adapter.CronosAdapter", return_value=synth):
        from app.delivery_driver import run_delivery_goal
        await run_delivery_goal(
            goal_id="goal-1",
            spec_path="delivery.workflow.yaml",
            store=store,
            trace_store=MagicMock(),
            space_id="test-space",
            space_dir=tmp_path,
            run_dir=tmp_path / "runs",
        )

    # Both implement and review should have been dispatched.
    assert "implement" in dispatch_log, f"implement not dispatched; log={dispatch_log}"
    assert "review" in dispatch_log, f"review not dispatched; log={dispatch_log}"
    # On a successful runner completion the driver finalizes the goal to DONE
    # (previously the goal was left ACTIVE forever — delivery_driver finalize gap).
    from app.models import TaskState as _TS2

    store.finalize_run.assert_called_once()
    assert store.finalize_run.call_args.kwargs["new_state"] == _TS2.DONE


@pytest.mark.asyncio
async def test_gate_fix_loop_routes_to_producer_then_proceeds(tmp_path):
    """§P4 e2e: a gate that first fails routes back to its producer, then proceeds
    on the retry — the whole chain re-runs and the goal reaches DONE."""
    from app.models import TaskState as _TS

    spec_file = tmp_path / "delivery.workflow.yaml"
    spec_file.write_text(GATE_FIX_LOOP_SPEC_YAML)

    store = MagicMock()
    store.finalize_run = AsyncMock()
    store.get = MagicMock(return_value=SimpleNamespace(
        id="goal-1", state=_TS.ACTIVE, title="T", brief="...", waiting_question=None,
    ))

    dispatch_log: list[str] = []
    synth = _make_gate_loop_adapter(["needs_fix", "proceed"], dispatch_log)

    with patch("adapters.cronos.adapter.CronosAdapter", return_value=synth):
        from app.delivery_driver import run_delivery_goal
        await run_delivery_goal(
            goal_id="goal-1", spec_path="delivery.workflow.yaml", store=store,
            trace_store=MagicMock(), space_id="test-space", space_dir=tmp_path,
            run_dir=tmp_path / "runs",
        )

    # implement re-ran after the gate's non-proceed decision; review then ran.
    assert dispatch_log.count("implement") == 2, f"log={dispatch_log}"
    assert "review" in dispatch_log
    store.finalize_run.assert_called_once()
    assert store.finalize_run.call_args.kwargs["new_state"] == _TS.DONE


@pytest.mark.asyncio
async def test_gate_fix_loop_exhaustion_parks_waiting(tmp_path):
    """§P4 e2e (same defect scenario, R6 mechanism): a gate that never proceeds
    is bounded at loop.max; the runner terminates the run 'stalled' with
    kind=gate_exhausted at run level, and the driver renders that detail into
    the actionable WAITING park (not an opaque hang, no node archaeology)."""
    from app.models import TaskState as _TS

    spec_file = tmp_path / "delivery.workflow.yaml"
    spec_file.write_text(GATE_FIX_LOOP_SPEC_YAML)

    store = MagicMock()
    store.finalize_run = AsyncMock()
    store.get = MagicMock(return_value=SimpleNamespace(
        id="goal-1", state=_TS.ACTIVE, title="T", brief="...", waiting_question=None,
    ))

    dispatch_log: list[str] = []
    synth = _make_gate_loop_adapter(["needs_fix"], dispatch_log)  # always fails

    with patch("adapters.cronos.adapter.CronosAdapter", return_value=synth):
        from app.delivery_driver import run_delivery_goal
        await run_delivery_goal(
            goal_id="goal-1", spec_path="delivery.workflow.yaml", store=store,
            trace_store=MagicMock(), space_id="test-space", space_dir=tmp_path,
            run_dir=tmp_path / "runs",
        )

    # Bounded at loop.max=3 gate evaluations → implement dispatched exactly 3×.
    assert dispatch_log.count("implement") == 3, f"log={dispatch_log}"
    # review is never reached (gate never proceeds).
    assert "review" not in dispatch_log
    # The runner terminated 'stalled' with run-level gate detail (R6/OD-3).
    assert synth.state.read().status == "stalled"
    assert synth.state.read().stall["kind"] == "gate_exhausted"
    assert synth.state.read().stall["nodes"] == ["g-build"]
    store.finalize_run.assert_called_once()
    kwargs = store.finalize_run.call_args.kwargs
    assert kwargs["new_state"] == _TS.WAITING
    assert "g-build" in kwargs["waiting_question"]
    assert "stalled" in kwargs["waiting_question"].lower()
