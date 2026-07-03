"""Tests for backend/app/delivery_driver.py (I6)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure package is importable.

from app.delivery_driver import (
    DELIVERY_NODE_SENTINEL,
    DELIVERY_WORKFLOW_SENTINEL_PATTERN,
    _resume_persisted_run,
    detect_delivery_workflow_spec,
    run_delivery_goal,
)
from app.delivery_outcomes import render_stall_message


# ---------------------------------------------------------------------------
# detect_delivery_workflow_spec
# ---------------------------------------------------------------------------

class TestDetectDeliveryWorkflowSpec:
    def test_returns_spec_path(self):
        brief = "# Goal\n\n<!-- delivery-workflow: packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml -->"
        path = detect_delivery_workflow_spec(brief)
        assert path == "packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml"

    def test_no_sentinel_returns_none(self):
        brief = "# Regular goal\n\nSome description."
        assert detect_delivery_workflow_spec(brief) is None

    def test_empty_brief_returns_none(self):
        assert detect_delivery_workflow_spec("") is None
        assert detect_delivery_workflow_spec(None) is None  # type: ignore[arg-type]

    def test_strict_line_anchor_no_substring_match(self):
        """Inline HTML comments inside prose must not match."""
        brief = "Use <!-- delivery-workflow: sneaky --> to configure."
        # The regex requires the entire line to be the sentinel.
        # The above line has content before/after the comment, so it should match
        # only if the regex is NOT strictly anchored. Let's verify.
        path = detect_delivery_workflow_spec(brief)
        # The sentinel is on its own line segment, but if the full line has
        # "Use" before it, it should not match (^...$).
        # Actually with MULTILINE, ^ matches start of each line.
        # "Use <!-- ... -->" is a single line that starts with "Use", not "<!--".
        assert path is None

    def test_sentinel_on_own_line(self):
        brief = "# Goal title\n<!-- delivery-workflow: specs/my.yaml -->\nSome text."
        path = detect_delivery_workflow_spec(brief)
        assert path == "specs/my.yaml"

    def test_path_with_slashes(self):
        brief = "<!-- delivery-workflow: a/b/c/workflow.yaml -->"
        path = detect_delivery_workflow_spec(brief)
        assert path == "a/b/c/workflow.yaml"

    def test_extra_whitespace_in_sentinel(self):
        brief = "<!--  delivery-workflow:   my.yaml   -->"
        path = detect_delivery_workflow_spec(brief)
        assert path is not None  # whitespace-tolerant


class TestSentinelConstants:
    def test_delivery_node_sentinel_has_placeholder(self):
        """DELIVERY_NODE_SENTINEL must contain {node_id} for formatting."""
        assert "{node_id}" in DELIVERY_NODE_SENTINEL

    def test_delivery_node_sentinel_format(self):
        tag = DELIVERY_NODE_SENTINEL.format(node_id="review")
        assert tag == "<!-- delivery-node: review -->"


# ---------------------------------------------------------------------------
# run_delivery_goal
# ---------------------------------------------------------------------------

MINIMAL_SPEC_YAML = """\
apiVersion: delivery/v1
metadata:
  name: test-workflow
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
edges: []
"""


def _make_store(goal_state="active"):
    store = MagicMock()
    task = SimpleNamespace(
        id="goal-1",
        state=MagicMock(value=goal_state),
        title="Test Goal",
        brief="<!-- delivery-workflow: workflow.yaml -->",
    )
    store.get.return_value = task
    store.finalize_run = AsyncMock()
    return store


def _make_trace_store():
    ts = MagicMock()
    ts.load_latest = AsyncMock(return_value=None)
    return ts


@pytest.mark.asyncio
async def test_run_delivery_goal_loads_spec_and_runs(tmp_path):
    """Happy path: spec loads, runner runs, returns done."""
    spec_file = tmp_path / "workflow.yaml"
    spec_file.write_text(MINIMAL_SPEC_YAML)

    run_dir = tmp_path / "runs" / "goal-1"

    # Mock the runner to return done immediately.
    from delivery_workflow.state_types import BudgetState, WorkflowState
    mock_state = WorkflowState(
        spec="test-workflow", run_id="goal-1", status="done",
        budget=BudgetState(usd_ceiling=5.0),
    )

    # Patch runner.run at the module level it's imported.
    called_with = {}

    def fake_run(graph, executor, state_ops=None, host=None, **kwargs):
        called_with["graph"] = graph
        called_with["executor"] = executor
        called_with["state_ops"] = state_ops
        called_with["host"] = host
        return mock_state

    # Patch runner.run where it's imported inside the driver function.
    # The driver does `import runner as workflow_runner` inside the async fn,
    # so we patch the module-level runner.run.
    from delivery_workflow import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = fake_run

    try:
        with patch("app.delivery_adapter.CronosAdapter") as MockAdapter:
            MockAdapter.return_value = MagicMock()
            store = _make_store()
            ts = _make_trace_store()
            await run_delivery_goal(
                goal_id="goal-1",
                spec_path="workflow.yaml",
                store=store,
                trace_store=ts,
                space_id="test-space",
                space_dir=tmp_path,
                run_dir=run_dir,
            )
    finally:
        _runner_mod.run = original_run

    # Graph should have been compiled with the spec.
    assert "graph" in called_with
    assert called_with["graph"].metadata.get("name") == "test-workflow"

    # B1 — state_ops is passed to the runner (enables persistence + resume) and
    # state.json is bootstrapped before the run.
    assert called_with["state_ops"] is MockAdapter.return_value.state
    MockAdapter.return_value.state.bootstrap_if_absent.assert_called_once()
    _bs_kwargs = MockAdapter.return_value.state.bootstrap_if_absent.call_args.kwargs
    assert _bs_kwargs["run_id"] == "goal-1"
    # B2/B4 — the goal slug (slugify("Test Goal")) is handed to the adapter.
    assert MockAdapter.call_args.kwargs["goal_slug"] == "test-goal"


@pytest.mark.asyncio
async def test_run_delivery_goal_parks_on_missing_spec(tmp_path):
    """When the spec file does not exist, goal is parked to WAITING."""
    run_dir = tmp_path / "runs" / "goal-1"
    store = _make_store()
    ts = _make_trace_store()

    from app.models import TaskState as _TS
    store.get.return_value = SimpleNamespace(
        id="goal-1",
        state=_TS.ACTIVE,
        title="T",
        brief="...",
        waiting_question=None,
    )

    await run_delivery_goal(
        goal_id="goal-1",
        spec_path="nonexistent.yaml",
        store=store,
        trace_store=ts,
        space_id="space",
        space_dir=tmp_path,
        run_dir=run_dir,
    )

    # finalize_run should have been called to park to WAITING.
    store.finalize_run.assert_called_once()
    _, kwargs = store.finalize_run.call_args
    assert kwargs.get("new_state") is not None


@pytest.mark.asyncio
async def test_run_delivery_goal_parks_on_compiler_error(tmp_path):
    """When Compiler A raises ValueError, goal is parked to WAITING."""
    spec_file = tmp_path / "bad.yaml"
    # Spec with undefined alias to trigger compiler error.
    spec_file.write_text("""\
apiVersion: delivery/v1
metadata:
  name: bad
defaults:
  models:
    build: sonnet
  budget:
    usd_ceiling: 1.0
nodes:
  - id: n
    kind: agent
    model: {use: undefined_alias}
edges: []
""")
    run_dir = tmp_path / "runs" / "goal-1"
    store = _make_store()
    ts = _make_trace_store()

    from app.models import TaskState as _TS
    store.get.return_value = SimpleNamespace(
        id="goal-1", state=_TS.ACTIVE, title="T", brief="...", waiting_question=None,
    )

    await run_delivery_goal(
        goal_id="goal-1",
        spec_path="bad.yaml",
        store=store,
        trace_store=ts,
        space_id="space",
        space_dir=tmp_path,
        run_dir=run_dir,
    )

    store.finalize_run.assert_called_once()
    _, kwargs = store.finalize_run.call_args
    assert "compiler" in kwargs.get("waiting_question", "").lower() or \
           "alias" in kwargs.get("waiting_question", "").lower() or \
           "error" in kwargs.get("waiting_question", "").lower()


@pytest.mark.asyncio
async def test_run_delivery_goal_blocked_parks_active_goal(tmp_path):
    """Runner status=blocked but goal still ACTIVE (adapter didn't park) → park WAITING."""
    spec_file = tmp_path / "workflow.yaml"
    spec_file.write_text(MINIMAL_SPEC_YAML)
    run_dir = tmp_path / "runs" / "goal-1"

    from app.models import TaskState as _TS
    from delivery_workflow.state_types import BudgetState, WorkflowState
    store = _make_store()
    store.get.return_value = SimpleNamespace(
        id="goal-1", state=_TS.ACTIVE, title="T", brief="...", waiting_question=None,
    )
    ts = _make_trace_store()

    blocked_state = WorkflowState(
        spec="test-workflow", run_id="goal-1", status="blocked",
        budget=BudgetState(usd_ceiling=5.0),
    )
    from delivery_workflow import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = lambda graph, executor, state_ops=None: blocked_state
    try:
        with patch("app.delivery_adapter.CronosAdapter"):
            await run_delivery_goal(
                goal_id="goal-1", spec_path="workflow.yaml", store=store,
                trace_store=ts, space_id="space", space_dir=tmp_path, run_dir=run_dir,
            )
    finally:
        _runner_mod.run = original_run

    store.finalize_run.assert_called_once()
    assert store.finalize_run.call_args.kwargs["new_state"] == _TS.WAITING


@pytest.mark.asyncio
async def test_run_delivery_goal_blocked_does_not_clobber_waiting(tmp_path):
    """Runner status=blocked and goal already WAITING (human signoff) → left as-is."""
    spec_file = tmp_path / "workflow.yaml"
    spec_file.write_text(MINIMAL_SPEC_YAML)
    run_dir = tmp_path / "runs" / "goal-1"

    from app.models import TaskState as _TS
    from delivery_workflow.state_types import BudgetState, WorkflowState
    store = _make_store()
    store.get.return_value = SimpleNamespace(
        id="goal-1", state=_TS.WAITING, title="T", brief="...",
        waiting_question="signoff: proceed?",
    )
    ts = _make_trace_store()

    blocked_state = WorkflowState(
        spec="test-workflow", run_id="goal-1", status="blocked",
        budget=BudgetState(usd_ceiling=5.0),
    )
    from delivery_workflow import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = lambda graph, executor, state_ops=None: blocked_state
    try:
        with patch("app.delivery_adapter.CronosAdapter"):
            await run_delivery_goal(
                goal_id="goal-1", spec_path="workflow.yaml", store=store,
                trace_store=ts, space_id="space", space_dir=tmp_path, run_dir=run_dir,
            )
    finally:
        _runner_mod.run = original_run

    store.finalize_run.assert_not_called()


@pytest.mark.asyncio
async def test_run_delivery_goal_cancel_event_persists_cancelled(tmp_path):
    """R11 real cancellation: a user stop (cancel_event set mid-run) persists
    run status 'cancelled' via DeliveryRun.cancel and parks the goal with the
    cancelled row (no 'node_failed' kind, no retry prompt) — not as a
    silently-retryable failure."""
    spec_file = tmp_path / "workflow.yaml"
    spec_file.write_text(MINIMAL_SPEC_YAML)
    run_dir = tmp_path / "runs" / "goal-1"

    from app.models import TaskState as _TS
    from delivery_workflow.state_types import BudgetState, WorkflowState
    store = _make_store()
    store.get.return_value = SimpleNamespace(
        id="goal-1", state=_TS.ACTIVE, title="T", brief="...", waiting_question=None,
    )
    ts = _make_trace_store()

    # A cancelled child dispatch surfaces to the runner as a failed node.
    failed_state = WorkflowState(
        spec="test-workflow", run_id="goal-1", status="failed",
        budget=BudgetState(usd_ceiling=5.0),
    )
    cancel_event = asyncio.Event()
    cancel_event.set()

    from delivery_workflow import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = lambda graph, executor, state_ops=None, host=None, **kw: failed_state
    try:
        with patch("app.delivery_adapter.CronosAdapter") as MockAdapter:
            adapter = MagicMock()
            # First read: _read_persisted_state at entry — fresh run (no
            # persisted state yet).  Second read: DeliveryRun.cancel reads
            # the failed state before sealing it 'cancelled'.
            adapter.state.read.side_effect = [
                FileNotFoundError("no state yet"), failed_state,
            ]
            MockAdapter.return_value = adapter
            await run_delivery_goal(
                goal_id="goal-1", spec_path="workflow.yaml", store=store,
                trace_store=ts, space_id="space", space_dir=tmp_path,
                run_dir=run_dir, cancel_event=cancel_event,
            )
    finally:
        _runner_mod.run = original_run

    # The 'cancelled' status was persisted through StateOps (the R10b seal:
    # start() halts and resume() raises on it).
    adapter.state.write.assert_any_call({"status": "cancelled"})
    kwargs = store.finalize_run.call_args.kwargs
    assert kwargs["new_state"] == _TS.WAITING
    assert "cancelled" in kwargs["waiting_question"].lower()
    assert kwargs.get("waiting_kind") is None


@pytest.mark.asyncio
async def test_run_delivery_goal_remaps_legacy_spec_path(tmp_path):
    """R10a legacy remap: a goal created before the src-layout restructure
    points at the deleted old canonical spec path; the driver resolves it to
    the relocated spec instead of parking on FileNotFoundError forever."""
    legacy_rel = "packages/delivery-workflow/delivery.workflow.yaml"
    new_rel = "packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml"
    spec_file = tmp_path / new_rel
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(MINIMAL_SPEC_YAML)
    run_dir = tmp_path / "runs" / "goal-1"

    from delivery_workflow.state_types import BudgetState, WorkflowState
    done_state = WorkflowState(
        spec="test-workflow", run_id="goal-1", status="done",
        budget=BudgetState(usd_ceiling=5.0),
    )
    called_with = {}

    def fake_run(graph, executor, state_ops=None, host=None, **kwargs):
        called_with["graph"] = graph
        return done_state

    from delivery_workflow import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = fake_run
    try:
        with patch("app.delivery_adapter.CronosAdapter") as MockAdapter:
            MockAdapter.return_value = MagicMock()
            store = _make_store()
            ts = _make_trace_store()
            await run_delivery_goal(
                goal_id="goal-1", spec_path=legacy_rel, store=store,
                trace_store=ts, space_id="space", space_dir=tmp_path,
                run_dir=run_dir,
            )
    finally:
        _runner_mod.run = original_run

    # The remapped spec compiled and ran — no "spec load/compiler error" park.
    assert called_with["graph"].metadata.get("name") == "test-workflow"
    kwargs = store.finalize_run.call_args.kwargs
    assert kwargs["waiting_question"] is None  # finalized DONE, not parked


# ---------------------------------------------------------------------------
# _resume_persisted_run — translate persisted halt + user action into ONE
# package resume() event (R7).  The pre-R7 heuristics (_resume_from_blocked,
# _resume_from_failed + the failed_resumes.json sidecar) are DELETED: the
# package owns resume semantics and the retry ceiling lives in state.
# ---------------------------------------------------------------------------

class _FakeStateOps:
    """Records write() patches; read() returns a pre-seeded WorkflowState."""

    def __init__(self, state):
        self._state = state
        self.writes: list[dict] = []

    def read(self):
        return self._state

    def write(self, patch: dict) -> None:
        self.writes.append(patch)
        if "status" in patch:
            self._state.status = patch["status"]
        for nid, np in patch.get("nodes", {}).items():
            if nid in self._state.nodes and "status" in np:
                self._state.nodes[nid].status = np["status"]


def _graph_with_human():
    from delivery_workflow.ir import IREdge, IRGraph, IRNode
    return IRGraph(
        nodes=[
            IRNode(id="scout", kind="agent"),
            IRNode(id="signoff-scope", kind="human", data={"prompt": "ok?"}),
            IRNode(id="frontend", kind="agent"),
        ],
        edges=[IREdge(source="signoff-scope", target="frontend")],
    )


def _make_run(adapter):
    """Build the DeliveryRun facade _resume_persisted_run drives (R10d)."""
    from delivery_workflow import DeliveryRun

    return DeliveryRun(
        _graph_with_human(), executor=adapter, state_ops=adapter.state,
    )


def _wf_state(status, nodes=None, stall=None):
    from delivery_workflow.state_types import BudgetState, NodeState, WorkflowState

    return WorkflowState(
        spec="w", run_id="goal-1", status=status,
        budget=BudgetState(usd_ceiling=5.0),
        nodes={nid: NodeState(status=s) for nid, s in (nodes or {}).items()},
        stall=stall,
    )


class _ResumeSpy:
    """Patches runner.resume to record events and return scripted states."""

    def __init__(self, results):
        self._results = list(results)
        self.events: list = []

    def __enter__(self):
        from delivery_workflow import runner as _runner_mod
        self._mod = _runner_mod
        self._orig = _runner_mod.resume

        def fake_resume(graph, executor, state_ops, event, **kwargs):
            self.events.append(event)
            result = self._results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        _runner_mod.resume = fake_resume
        return self

    def __exit__(self, *exc):
        self._mod.resume = self._orig
        return False


def test_resume_blocked_signoff_builds_human_answer_approve_default():
    """blocked + message, no explicit verdict → HumanAnswer(approve) with the
    text preserved (backward-compatible default, D10: text never dropped)."""
    from delivery_workflow.runner import HumanAnswer

    persisted = _wf_state("blocked", {"scout": "done", "signoff-scope": "blocked"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    done_state = _wf_state("done")

    with _ResumeSpy([done_state]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, "looks good", None, "goal-1",
        )

    assert final.kind == "done" and reason is None
    assert spy.events == [
        HumanAnswer(node_id="signoff-scope", text="looks good", verdict="approve")
    ]


def test_resume_blocked_signoff_reject_verdict_passes_through():
    from delivery_workflow.runner import HumanAnswer

    persisted = _wf_state("blocked", {"signoff-scope": "blocked"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))

    with _ResumeSpy([_wf_state("stalled")]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, "no — change X", "reject", "goal-1",
        )

    assert reason is None
    assert spy.events == [
        HumanAnswer(node_id="signoff-scope", text="no — change X", verdict="reject")
    ]


@pytest.mark.parametrize("message", [None, "", "   "])
def test_resume_blocked_signoff_without_message_reparks_never_approves(message):
    """A message-less re-entry of a blocked sign-off (backend restart recovery,
    goal-sync propagation, board drag) is NOT an answer: no HumanAnswer event
    is synthesized — the goal re-parks WAITING with the signoff metadata so
    the Approve/Reject affordance survives (D10: silence never becomes a yes)."""
    persisted = _wf_state("blocked", {"scout": "done", "signoff-scope": "blocked"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))

    with _ResumeSpy([]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, message, None, "goal-1",
        )

    assert final is None
    assert spy.events == [], "no resume event may be synthesized without an answer"
    assert "signoff-scope" in reason
    assert park_kind == "signoff"
    assert park_node == "signoff-scope"


def test_resume_blocked_signoff_explicit_verdict_without_text_applies():
    """An explicit UI verdict with no accompanying text is still a real
    answer (the user pressed Approve): HumanAnswer(text='') is legal."""
    from delivery_workflow.runner import HumanAnswer

    persisted = _wf_state("blocked", {"signoff-scope": "blocked"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    done_state = _wf_state("done")

    with _ResumeSpy([done_state]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, None, "approve", "goal-1",
        )

    assert final.kind == "done" and reason is None
    assert spy.events == [
        HumanAnswer(node_id="signoff-scope", text="", verdict="approve")
    ]


def test_resume_stalled_rederive_parks_with_stalled_kind():
    """Stall re-derives keep the §5.6 structured metadata across re-parks:
    waiting_kind='stalled' is returned for the caller to stamp."""
    stall = {"kind": "gate_exhausted", "nodes": ["g-build"], "reason": "max=3"}
    persisted = _wf_state("stalled", stall=stall)
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))

    with _ResumeSpy([]):
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, "what now?", None, "goal-1",
        )

    assert final is None
    assert park_kind == "stalled"


def test_resume_blocked_without_human_node_parks_with_reason():
    """A run blocked on a non-sign-off node (agent self-reported blocked) has
    no legal resume event — the driver returns a park reason, never guesses."""
    persisted = _wf_state("blocked", {"scout": "blocked"})  # agent node
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))

    with _ResumeSpy([]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, "hello", None, "goal-1",
        )

    assert final is None
    assert "non-sign-off" in reason
    assert spy.events == []


def test_resume_failed_builds_retry_failed_all():
    from delivery_workflow.runner import RetryFailed

    persisted = _wf_state("failed", {"scout": "failed"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    done_state = _wf_state("done")

    with _ResumeSpy([done_state]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, None, None, "goal-1",
        )

    assert final.kind == "done" and reason is None
    assert spy.events == [RetryFailed("all")]


def test_resume_failed_resume_error_parks_with_message():
    from delivery_workflow.runner import ResumeError

    persisted = _wf_state("failed", {"scout": "failed"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))

    with _ResumeSpy([ResumeError("nothing to retry")]):
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, None, None, "goal-1",
        )

    assert final is None
    assert "nothing to retry" in reason


def test_resume_escalated_tries_nothing_then_retry_failed_on_no_progress():
    """escalated → Nothing() first; a re-derived 'escalated' terminal (no
    progress) is re-armed once via RetryFailed('all') (package-bounded)."""
    from delivery_workflow.runner import Nothing, RetryFailed

    persisted = _wf_state("escalated", {"scout": "escalated"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    still_escalated = _wf_state("escalated", {"scout": "escalated"})
    done_state = _wf_state("done")

    with _ResumeSpy([still_escalated, done_state]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, None, None, "goal-1",
        )

    assert final.kind == "done" and reason is None
    assert spy.events == [Nothing(), RetryFailed("all")]


def test_resume_escalated_nothing_suffices_when_run_progresses():
    from delivery_workflow.runner import Nothing

    persisted = _wf_state("escalated")
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    done_state = _wf_state("done")

    with _ResumeSpy([done_state]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, None, None, "goal-1",
        )

    assert final.kind == "done" and reason is None
    assert spy.events == [Nothing()]


def test_resume_escalated_keeps_terminal_when_nothing_retryable():
    """Nothing() re-derives 'escalated' and RetryFailed matches nothing — the
    escalated terminal is returned and the caller parks the goal."""
    from delivery_workflow.runner import Nothing, ResumeError, RetryFailed

    persisted = _wf_state("escalated")
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    still_escalated = _wf_state("escalated")

    with _ResumeSpy([still_escalated, ResumeError("no retryable node")]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, None, None, "goal-1",
        )

    assert final.kind == "escalated" and reason is None
    assert spy.events == [Nothing(), RetryFailed("all")]


def test_resume_stalled_rejected_with_message_reopens_signoff():
    from delivery_workflow.runner import RetryFailed

    stall = {"kind": "rejected", "nodes": ["signoff-scope"], "reason": "rejected"}
    persisted = _wf_state(
        "stalled", {"signoff-scope": "needs_fix"}, stall=stall,
    )
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    blocked_again = _wf_state("blocked", {"signoff-scope": "blocked"})

    with _ResumeSpy([blocked_again]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, "please re-ask", None, "goal-1",
        )

    assert final.kind == "blocked" and reason is None
    assert spy.events == [RetryFailed(["signoff-scope"])]


def test_resume_stalled_non_rejected_stays_parked_with_stall_reason():
    """R6 semantics: a stalled run (starved/gate_exhausted/retry_exhausted)
    stays parked — no blind resume."""
    stall = {"kind": "gate_exhausted", "nodes": ["g-build"], "reason": "max=3"}
    persisted = _wf_state("stalled", stall=stall)
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))

    with _ResumeSpy([]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, "try again", None, "goal-1",
        )

    assert final is None
    assert "g-build" in reason
    assert spy.events == []


def test_resume_stalled_rejected_without_message_stays_parked():
    """Re-activation without a NEW message does not re-open a rejected
    sign-off — the park message explains how to."""
    stall = {"kind": "rejected", "nodes": ["signoff-scope"], "reason": "no"}
    persisted = _wf_state("stalled", stall=stall)
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))

    with _ResumeSpy([]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _make_run(adapter), persisted, None, None, "goal-1",
        )

    assert final is None
    assert "rejected" in reason.lower()
    assert spy.events == []


# ---------------------------------------------------------------------------
# render_stall_message (app.delivery_outcomes, shared by BOTH hosts since
# R10d) — renders the runner's RUN-LEVEL stall record (R6).  The pre-R6
# node-archaeology heuristics (_stalled_gate_ids, _stalled_gate_reason,
# _resume_from_stalled_gate + the stalled_gate_resumes.json sidecar) are
# DELETED: the runner proves completeness itself and reports 'stalled' with
# machine-readable detail at run level.  The renderer takes ONLY that record
# (Outcome.stall, a plain dict) — it structurally cannot read
# WorkflowState.nodes, which is the R6 no-archaeology guarantee.
# ---------------------------------------------------------------------------


def _stalled_wf_state(stall: dict | None):
    from delivery_workflow.state_types import BudgetState, WorkflowState

    return WorkflowState(
        spec="w", run_id="goal-1", status="stalled",
        budget=BudgetState(usd_ceiling=5.0),
        stall=stall,
    )


def test_stall_reason_renders_starved_nodes_detail():
    reason = render_stall_message({
        "kind": "starved_nodes",
        "nodes": ["frontend"],
        "reason": "dead-end node(s) signoff-scope completed but no outgoing "
                  "edge condition matched",
        "dead_ends": ["signoff-scope"],
    })
    assert "frontend" in reason
    assert "signoff-scope" in reason
    assert "never reached" in reason


def test_stall_reason_renders_gate_exhausted_detail():
    reason = render_stall_message({
        "kind": "gate_exhausted",
        "nodes": ["g-build"],
        "reason": "gate 'g-build' fix-loop exhausted after 3 evaluation(s) "
                  "(max=3, decision=needs_fix: impl-report failed schema check)",
    })
    assert "g-build" in reason
    assert "fix-loop" in reason
    assert "impl-report failed schema check" in reason


def test_stall_reason_without_detail_is_generic_but_honest():
    reason = render_stall_message(None)
    assert "stalled" in reason.lower()


def test_stall_reason_takes_only_the_run_level_record():
    """The park message is rendered from the run-level stall record ONLY —
    the renderer's input is the plain ``Outcome.stall`` dict, so no host can
    smuggle node archaeology back in through it."""
    reason = render_stall_message(
        {"kind": "starved_nodes", "nodes": ["b"], "reason": "a dead-ended"}
    )
    assert "b" in reason


@pytest.mark.asyncio
async def test_run_delivery_goal_stalled_parks_waiting_with_detail(tmp_path):
    """Runner returns 'stalled' (R6) → goal parks WAITING with the actionable
    message rendered from the run-level stall detail."""
    spec_file = tmp_path / "workflow.yaml"
    spec_file.write_text(MINIMAL_SPEC_YAML)
    run_dir = tmp_path / "runs" / "goal-1"

    from app.models import TaskState as _TS
    store = _make_store()
    store.get.return_value = SimpleNamespace(
        id="goal-1", state=_TS.ACTIVE, title="T", brief="...", waiting_question=None,
    )
    ts = _make_trace_store()

    stalled_state = _stalled_wf_state({
        "kind": "gate_exhausted",
        "nodes": ["g-build"],
        "reason": "gate 'g-build' fix-loop exhausted after 3 evaluation(s) "
                  "(max=3, decision=needs_fix)",
    })
    from delivery_workflow import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = lambda graph, executor, state_ops=None, **kw: stalled_state
    try:
        with patch("app.delivery_adapter.CronosAdapter"):
            await run_delivery_goal(
                goal_id="goal-1", spec_path="workflow.yaml", store=store,
                trace_store=ts, space_id="space", space_dir=tmp_path, run_dir=run_dir,
            )
    finally:
        _runner_mod.run = original_run

    store.finalize_run.assert_called_once()
    kwargs = store.finalize_run.call_args.kwargs
    assert kwargs["new_state"] == _TS.WAITING
    assert "stalled" in kwargs["waiting_question"].lower()
    assert "g-build" in kwargs["waiting_question"]


@pytest.mark.asyncio
async def test_run_delivery_goal_done_with_non_proceed_gate_finalizes_done(tmp_path):
    """The D12 false positive is gone: a run the runner reports 'done' (its
    completeness invariant held — e.g. a verdict-routed run past a needs_fix
    g-review decision) finalizes the goal DONE.  No node archaeology, no
    spurious WAITING at completion."""
    spec_file = tmp_path / "workflow.yaml"
    spec_file.write_text(MINIMAL_SPEC_YAML)
    run_dir = tmp_path / "runs" / "goal-1"

    from app.models import TaskState as _TS
    from delivery_workflow.state_types import BudgetState, NodeState, WorkflowState
    store = _make_store()
    store.get.return_value = SimpleNamespace(
        id="goal-1", state=_TS.ACTIVE, title="T", brief="...", waiting_question=None,
    )
    ts = _make_trace_store()

    verdict_routed_done = WorkflowState(
        spec="test-workflow", run_id="goal-1", status="done",
        budget=BudgetState(usd_ceiling=5.0),
        nodes={
            "review": NodeState(status="done", fields={"verdict": "pass"}),
            # The gate's own decision is needs_fix, but the run routed past it
            # on the review verdict — the runner proved completeness → done.
            "g-review": NodeState(status="done", gate={"decision": "needs_fix"}),
            "security": NodeState(status="done"),
        },
    )
    from delivery_workflow import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = lambda graph, executor, state_ops=None, **kw: verdict_routed_done
    try:
        with patch("app.delivery_adapter.CronosAdapter"):
            await run_delivery_goal(
                goal_id="goal-1", spec_path="workflow.yaml", store=store,
                trace_store=ts, space_id="space", space_dir=tmp_path, run_dir=run_dir,
            )
    finally:
        _runner_mod.run = original_run

    store.finalize_run.assert_called_once()
    kwargs = store.finalize_run.call_args.kwargs
    assert kwargs["new_state"] == _TS.DONE, (
        "a runner-proven 'done' with a non-proceed gate decision must finalize "
        "DONE — the WAITING park here was the D12 false positive"
    )


@pytest.mark.asyncio
async def test_run_delivery_goal_parks_on_runner_exception(tmp_path):
    """When runner.run raises, goal is parked to WAITING."""
    spec_file = tmp_path / "workflow.yaml"
    spec_file.write_text(MINIMAL_SPEC_YAML)
    run_dir = tmp_path / "runs" / "goal-1"

    store = _make_store()
    ts = _make_trace_store()

    from app.models import TaskState as _TS
    store.get.return_value = SimpleNamespace(
        id="goal-1", state=_TS.ACTIVE, title="T", brief="...", waiting_question=None,
    )

    from delivery_workflow import runner as _runner_mod
    original_run = _runner_mod.run

    def exploding_run(graph, executor, state_ops=None):
        raise RuntimeError("runner exploded")

    _runner_mod.run = exploding_run
    try:
        with patch("app.delivery_adapter.CronosAdapter"):
            await run_delivery_goal(
                goal_id="goal-1",
                spec_path="workflow.yaml",
                store=store,
                trace_store=ts,
                space_id="space",
                space_dir=tmp_path,
                run_dir=run_dir,
            )
    finally:
        _runner_mod.run = original_run

    store.finalize_run.assert_called_once()
