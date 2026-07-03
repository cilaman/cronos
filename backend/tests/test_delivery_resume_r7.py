"""R7 host-side acceptance tests — resume via the package API (kills D7 + D10).

End-to-end through ``delivery_driver.run_delivery_goal`` with REAL package
machinery (compiler_a, runner.run/resume, CronosStateOps persistence over
state.json) and a synthetic executor that records every dispatch's inputs:

* D10 dies: a delivery goal parked on a human sign-off, resumed with
  verdict='reject' + "no — change X", routes the spec's ``on_reject`` edge —
  "change X" reaches the re-run node's inputs (scope) and the sign-off is NOT
  approved (the run re-parks on the sign-off; downstream never runs).
* The approve path preserves the text: it lands in ``fields.answer`` and flows
  into the downstream node's scope; the goal finalizes DONE.
* D7 dies host-side: a persisted 'escalated' run re-enters on user action and
  makes progress (no WAITING livelock).
* The sign-off park carries structured wait metadata
  (waiting_kind='signoff' + waiting_node_id) for the UI affordance.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages" / "delivery-workflow"))

from app.delivery_driver import run_delivery_goal
from app.models import TaskState


SIGNOFF_SPEC_YAML = """\
apiVersion: delivery/v1
metadata:
  name: signoff-e2e
defaults:
  models:
    build: sonnet
  budget:
    usd_ceiling: 5.0
    on_exceed: escalate
nodes:
  - id: analyze
    kind: agent
    agent: analyst
    model: {use: build}
    produces: {class: analysis}
  - id: signoff
    kind: human
    prompt: "Right thing to build?"
    on_reject: analyze
  - id: build
    kind: agent
    agent: implementor
    model: {use: build}
    produces: {class: implementation}
edges:
  - {from: analyze, to: signoff}
  - {from: signoff, to: build}
"""

TWO_AGENT_SPEC_YAML = """\
apiVersion: delivery/v1
metadata:
  name: escalated-e2e
defaults:
  models:
    build: sonnet
  budget:
    usd_ceiling: 5.0
    on_exceed: escalate
nodes:
  - id: analyze
    kind: agent
    agent: analyst
    model: {use: build}
    produces: {class: analysis}
  - id: build
    kind: agent
    agent: implementor
    model: {use: build}
    produces: {class: implementation}
edges:
  - {from: analyze, to: build}
"""


class _RecordingAdapter:
    """Synthetic ExecutorInterface with REAL CronosStateOps persistence.

    State survives across run_delivery_goal invocations through run_dir's
    state.json — exactly like production — so park/resume flows are honest.
    """

    def __init__(self, run_dir: Path, dispatch_log: list, inputs_log: dict):
        from adapters.cronos.adapter import CronosStateOps
        from lib.state.events import EventLog
        from lib.state.store import StateStore

        run_dir.mkdir(parents=True, exist_ok=True)
        self.state = CronosStateOps(StateStore(run_dir), EventLog(run_dir))
        self._dispatch_log = dispatch_log
        self._inputs_log = inputs_log
        self.escalations: list[tuple[str, str]] = []

        class _Telemetry:
            def emit(self, nid, d):
                pass

        self.telemetry = _Telemetry()

    def dispatchAgent(self, agent_ref: str, inputs: dict):
        from results import AgentResult, TelemetryData

        node_id = inputs.get("node_id", agent_ref)
        self._dispatch_log.append(node_id)
        self._inputs_log.setdefault(node_id, []).append(inputs)
        return AgentResult(
            status="done", artifact_paths=[], produces="", fields={},
            open_questions=[], telemetry=TelemetryData(0, 0.0, 0.0),
        )

    def runGate(self, gate, paths):
        from results import GateResult

        return GateResult(decision="proceed", errors=[])

    def evalCondition(self, expr: str, scope: dict) -> bool:
        from lib.conditions import eval_condition

        return eval_condition(expr, scope)

    def escalate(self, node_id: str, reason: str) -> None:
        self.escalations.append((node_id, reason))


def _make_store():
    store = MagicMock()
    store.get.return_value = SimpleNamespace(
        id="goal-1", state=TaskState.ACTIVE, title="Signoff Goal",
        brief="...", waiting_question=None,
    )
    store.finalize_run = AsyncMock()
    store.set_waiting_meta = AsyncMock()
    return store


async def _drive(tmp_path, adapter, store, spec_yaml=SIGNOFF_SPEC_YAML, **kwargs):
    spec_file = tmp_path / "delivery.workflow.yaml"
    spec_file.write_text(spec_yaml)
    with patch("adapters.cronos.adapter.CronosAdapter", return_value=adapter):
        await run_delivery_goal(
            goal_id="goal-1", spec_path="delivery.workflow.yaml", store=store,
            trace_store=MagicMock(), space_id="space", space_dir=tmp_path,
            run_dir=tmp_path / "runs", **kwargs,
        )


@pytest.mark.asyncio
async def test_signoff_park_carries_structured_wait_meta(tmp_path):
    """First run parks on the sign-off: WAITING with waiting_kind='signoff' and
    the node id — the UI affordance key."""
    dispatch_log: list[str] = []
    adapter = _RecordingAdapter(tmp_path / "runs", dispatch_log, {})
    store = _make_store()

    await _drive(tmp_path, adapter, store)

    assert dispatch_log == ["analyze"]
    assert adapter.state.read().status == "blocked"
    store.finalize_run.assert_called_once()
    kwargs = store.finalize_run.call_args.kwargs
    assert kwargs["new_state"] == TaskState.WAITING
    assert kwargs["waiting_kind"] == "signoff"
    assert kwargs["waiting_node_id"] == "signoff"


@pytest.mark.asyncio
async def test_signoff_approve_preserves_text_and_continues(tmp_path):
    """D10 approve path: the reply text lands in fields.answer, flows into the
    downstream node's scope, and the goal finalizes DONE."""
    dispatch_log: list[str] = []
    inputs_log: dict[str, list] = {}
    adapter = _RecordingAdapter(tmp_path / "runs", dispatch_log, inputs_log)
    store = _make_store()

    await _drive(tmp_path, adapter, store)  # park on the sign-off
    store.finalize_run.reset_mock()

    await _drive(
        tmp_path, adapter, store,
        user_message="ship it — looks right", verdict=None,  # None = approve
    )

    # The sign-off was approved with the answer preserved (OD-2).
    final = adapter.state.read()
    assert final.status == "done"
    assert final.nodes["signoff"].status == "done"
    assert final.nodes["signoff"].fields["answer"] == "ship it — looks right"
    assert final.nodes["signoff"].fields["verdict"] == "approve"
    # Downstream ran and saw the answer in its scope.
    assert dispatch_log == ["analyze", "build"]
    build_scope = inputs_log["build"][-1]["scope"]
    assert build_scope["signoff.fields.answer"] == "ship it — looks right"
    # Goal finalized DONE.
    store.finalize_run.assert_called_once()
    assert store.finalize_run.call_args.kwargs["new_state"] == TaskState.DONE


@pytest.mark.asyncio
async def test_signoff_reject_routes_feedback_and_does_not_approve(tmp_path):
    """D10 dies: verdict='reject' + 'no — change X' routes the on_reject edge;
    'change X' reaches the re-run node's inputs; the sign-off is NOT approved
    (downstream never runs, the run re-parks on the sign-off)."""
    dispatch_log: list[str] = []
    inputs_log: dict[str, list] = {}
    adapter = _RecordingAdapter(tmp_path / "runs", dispatch_log, inputs_log)
    store = _make_store()

    await _drive(tmp_path, adapter, store)  # park on the sign-off
    store.finalize_run.reset_mock()

    await _drive(
        tmp_path, adapter, store,
        user_message="no — change X", verdict="reject",
    )

    # The on_reject route re-ran analyze with the feedback in scope.
    assert dispatch_log.count("analyze") == 2
    reject_run_scope = inputs_log["analyze"][-1]["scope"]
    assert reject_run_scope["signoff.fields.answer"] == "no — change X"
    assert reject_run_scope["signoff.fields.verdict"] == "reject"
    # The sign-off was NOT approved: build never ran and the run re-parked
    # on the sign-off (blocked), not done.
    assert "build" not in dispatch_log
    final = adapter.state.read()
    assert final.status == "blocked"
    assert final.nodes["signoff"].status == "blocked"
    # Goal parked WAITING again as a sign-off (never DONE).
    for call in store.finalize_run.call_args_list:
        assert call.kwargs["new_state"] != TaskState.DONE
    kwargs = store.finalize_run.call_args.kwargs
    assert kwargs["new_state"] == TaskState.WAITING
    assert kwargs["waiting_kind"] == "signoff"


@pytest.mark.asyncio
async def test_reject_feedback_reaches_child_brief():
    """The brief composer renders `<node>.fields.answer` (OD-2) so the text
    reaches the re-run child's agent prompt."""
    from app.run_executor import _human_answers_section

    section = _human_answers_section({
        "signoff.fields.answer": "no — change X",
        "signoff.fields.verdict": "reject",
        "analyze.fields.has_ui": True,
    })
    assert "no — change X" in section
    assert "signoff" in section
    assert "reject" in section
    # No answers → no section (brief unchanged).
    assert _human_answers_section({"analyze.fields.has_ui": True}) == ""


@pytest.mark.asyncio
async def test_escalated_run_resumes_and_progresses(tmp_path):
    """D7 host-side: a persisted 'escalated' run re-enters on user action
    (package Nothing() event) and makes progress — no WAITING livelock."""
    from state_types import BudgetState, NodeState, WorkflowState
    from lib.state.store import StateStore

    dispatch_log: list[str] = []
    inputs_log: dict[str, list] = {}
    run_dir = tmp_path / "runs"
    run_dir.mkdir(parents=True)
    # Pre-seed a persisted escalated run: analyze done, build never ran
    # (e.g. the global iteration cap fired).
    StateStore(run_dir).write(WorkflowState(
        spec="escalated-e2e", run_id="goal-1", status="escalated",
        budget=BudgetState(usd_ceiling=5.0),
        nodes={"analyze": NodeState(status="done")},
    ))

    adapter = _RecordingAdapter(run_dir, dispatch_log, inputs_log)
    store = _make_store()

    await _drive(tmp_path, adapter, store, spec_yaml=TWO_AGENT_SPEC_YAML,
                 user_message="continue")

    assert dispatch_log == ["build"], "the escalated run must progress on resume"
    assert adapter.state.read().status == "done"
    store.finalize_run.assert_called_once()
    assert store.finalize_run.call_args.kwargs["new_state"] == TaskState.DONE
