"""Tests for backend/app/delivery_driver.py (I6)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure package is importable.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages" / "delivery-workflow"))

from app.delivery_driver import (
    DELIVERY_NODE_SENTINEL,
    DELIVERY_WORKFLOW_SENTINEL_PATTERN,
    _resume_persisted_run,
    _stall_reason,
    detect_delivery_workflow_spec,
    run_delivery_goal,
)


# ---------------------------------------------------------------------------
# detect_delivery_workflow_spec
# ---------------------------------------------------------------------------

class TestDetectDeliveryWorkflowSpec:
    def test_returns_spec_path(self):
        brief = "# Goal\n\n<!-- delivery-workflow: packages/delivery-workflow/delivery.workflow.yaml -->"
        path = detect_delivery_workflow_spec(brief)
        assert path == "packages/delivery-workflow/delivery.workflow.yaml"

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
    from state_types import BudgetState, WorkflowState
    mock_state = WorkflowState(
        spec="test-workflow", run_id="goal-1", status="done",
        budget=BudgetState(usd_ceiling=5.0),
    )

    # Patch runner.run at the module level it's imported.
    called_with = {}

    def fake_run(graph, executor, state_ops=None):
        called_with["graph"] = graph
        called_with["executor"] = executor
        called_with["state_ops"] = state_ops
        return mock_state

    # Patch runner.run where it's imported inside the driver function.
    # The driver does `import runner as workflow_runner` inside the async fn,
    # so we patch the module-level runner.run.
    import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = fake_run

    try:
        with patch("adapters.cronos.adapter.CronosAdapter") as MockAdapter:
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
    from state_types import BudgetState, WorkflowState
    store = _make_store()
    store.get.return_value = SimpleNamespace(
        id="goal-1", state=_TS.ACTIVE, title="T", brief="...", waiting_question=None,
    )
    ts = _make_trace_store()

    blocked_state = WorkflowState(
        spec="test-workflow", run_id="goal-1", status="blocked",
        budget=BudgetState(usd_ceiling=5.0),
    )
    import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = lambda graph, executor, state_ops=None: blocked_state
    try:
        with patch("adapters.cronos.adapter.CronosAdapter"):
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
    from state_types import BudgetState, WorkflowState
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
    import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = lambda graph, executor, state_ops=None: blocked_state
    try:
        with patch("adapters.cronos.adapter.CronosAdapter"):
            await run_delivery_goal(
                goal_id="goal-1", spec_path="workflow.yaml", store=store,
                trace_store=ts, space_id="space", space_dir=tmp_path, run_dir=run_dir,
            )
    finally:
        _runner_mod.run = original_run

    store.finalize_run.assert_not_called()


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
    from ir import IREdge, IRGraph, IRNode
    return IRGraph(
        nodes=[
            IRNode(id="scout", kind="agent"),
            IRNode(id="signoff-scope", kind="human", data={"prompt": "ok?"}),
            IRNode(id="frontend", kind="agent"),
        ],
        edges=[IREdge(source="signoff-scope", target="frontend")],
    )


def _wf_state(status, nodes=None, stall=None):
    from state_types import BudgetState, NodeState, WorkflowState

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
        import runner as _runner_mod
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
    from runner import HumanAnswer

    persisted = _wf_state("blocked", {"scout": "done", "signoff-scope": "blocked"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    done_state = _wf_state("done")

    with _ResumeSpy([done_state]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _graph_with_human(), adapter, persisted, "looks good", None, "goal-1",
        )

    assert final is done_state and reason is None
    assert spy.events == [
        HumanAnswer(node_id="signoff-scope", text="looks good", verdict="approve")
    ]


def test_resume_blocked_signoff_reject_verdict_passes_through():
    from runner import HumanAnswer

    persisted = _wf_state("blocked", {"signoff-scope": "blocked"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))

    with _ResumeSpy([_wf_state("stalled")]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _graph_with_human(), adapter, persisted, "no — change X", "reject", "goal-1",
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
            _graph_with_human(), adapter, persisted, message, None, "goal-1",
        )

    assert final is None
    assert spy.events == [], "no resume event may be synthesized without an answer"
    assert "signoff-scope" in reason
    assert park_kind == "signoff"
    assert park_node == "signoff-scope"


def test_resume_blocked_signoff_explicit_verdict_without_text_applies():
    """An explicit UI verdict with no accompanying text is still a real
    answer (the user pressed Approve): HumanAnswer(text='') is legal."""
    from runner import HumanAnswer

    persisted = _wf_state("blocked", {"signoff-scope": "blocked"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    done_state = _wf_state("done")

    with _ResumeSpy([done_state]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _graph_with_human(), adapter, persisted, None, "approve", "goal-1",
        )

    assert final is done_state and reason is None
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
            _graph_with_human(), adapter, persisted, "what now?", None, "goal-1",
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
            _graph_with_human(), adapter, persisted, "hello", None, "goal-1",
        )

    assert final is None
    assert "non-sign-off" in reason
    assert spy.events == []


def test_resume_failed_builds_retry_failed_all():
    from runner import RetryFailed

    persisted = _wf_state("failed", {"scout": "failed"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    done_state = _wf_state("done")

    with _ResumeSpy([done_state]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _graph_with_human(), adapter, persisted, None, None, "goal-1",
        )

    assert final is done_state and reason is None
    assert spy.events == [RetryFailed("all")]


def test_resume_failed_resume_error_parks_with_message():
    from runner import ResumeError

    persisted = _wf_state("failed", {"scout": "failed"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))

    with _ResumeSpy([ResumeError("nothing to retry")]):
        final, reason, park_kind, park_node = _resume_persisted_run(
            _graph_with_human(), adapter, persisted, None, None, "goal-1",
        )

    assert final is None
    assert "nothing to retry" in reason


def test_resume_escalated_tries_nothing_then_retry_failed_on_no_progress():
    """escalated → Nothing() first; a re-derived 'escalated' terminal (no
    progress) is re-armed once via RetryFailed('all') (package-bounded)."""
    from runner import Nothing, RetryFailed

    persisted = _wf_state("escalated", {"scout": "escalated"})
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    still_escalated = _wf_state("escalated", {"scout": "escalated"})
    done_state = _wf_state("done")

    with _ResumeSpy([still_escalated, done_state]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _graph_with_human(), adapter, persisted, None, None, "goal-1",
        )

    assert final is done_state and reason is None
    assert spy.events == [Nothing(), RetryFailed("all")]


def test_resume_escalated_nothing_suffices_when_run_progresses():
    from runner import Nothing

    persisted = _wf_state("escalated")
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    done_state = _wf_state("done")

    with _ResumeSpy([done_state]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _graph_with_human(), adapter, persisted, None, None, "goal-1",
        )

    assert final is done_state and reason is None
    assert spy.events == [Nothing()]


def test_resume_escalated_keeps_terminal_when_nothing_retryable():
    """Nothing() re-derives 'escalated' and RetryFailed matches nothing — the
    escalated terminal is returned and the caller parks the goal."""
    from runner import Nothing, ResumeError, RetryFailed

    persisted = _wf_state("escalated")
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    still_escalated = _wf_state("escalated")

    with _ResumeSpy([still_escalated, ResumeError("no retryable node")]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _graph_with_human(), adapter, persisted, None, None, "goal-1",
        )

    assert final is still_escalated and reason is None
    assert spy.events == [Nothing(), RetryFailed("all")]


def test_resume_stalled_rejected_with_message_reopens_signoff():
    from runner import RetryFailed

    stall = {"kind": "rejected", "nodes": ["signoff-scope"], "reason": "rejected"}
    persisted = _wf_state(
        "stalled", {"signoff-scope": "needs_fix"}, stall=stall,
    )
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))
    blocked_again = _wf_state("blocked", {"signoff-scope": "blocked"})

    with _ResumeSpy([blocked_again]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _graph_with_human(), adapter, persisted, "please re-ask", None, "goal-1",
        )

    assert final is blocked_again and reason is None
    assert spy.events == [RetryFailed(["signoff-scope"])]


def test_resume_stalled_non_rejected_stays_parked_with_stall_reason():
    """R6 semantics: a stalled run (starved/gate_exhausted/retry_exhausted)
    stays parked — no blind resume."""
    stall = {"kind": "gate_exhausted", "nodes": ["g-build"], "reason": "max=3"}
    persisted = _wf_state("stalled", stall=stall)
    adapter = SimpleNamespace(state=_FakeStateOps(persisted))

    with _ResumeSpy([]) as spy:
        final, reason, park_kind, park_node = _resume_persisted_run(
            _graph_with_human(), adapter, persisted, "try again", None, "goal-1",
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
            _graph_with_human(), adapter, persisted, None, None, "goal-1",
        )

    assert final is None
    assert "rejected" in reason.lower()
    assert spy.events == []


# ---------------------------------------------------------------------------
# _stall_reason — render the runner's RUN-LEVEL stall detail (R6).
# The pre-R6 node-archaeology heuristics (_stalled_gate_ids,
# _stalled_gate_reason, _resume_from_stalled_gate + the stalled_gate_resumes.json
# sidecar) are DELETED: the runner now proves completeness itself and reports
# 'stalled' with machine-readable detail at run level.
# ---------------------------------------------------------------------------


def _stalled_wf_state(stall: dict | None):
    from state_types import BudgetState, WorkflowState

    return WorkflowState(
        spec="w", run_id="goal-1", status="stalled",
        budget=BudgetState(usd_ceiling=5.0),
        stall=stall,
    )


def test_stall_reason_renders_starved_nodes_detail():
    reason = _stall_reason(_stalled_wf_state({
        "kind": "starved_nodes",
        "nodes": ["frontend"],
        "reason": "dead-end node(s) signoff-scope completed but no outgoing "
                  "edge condition matched",
        "dead_ends": ["signoff-scope"],
    }))
    assert "frontend" in reason
    assert "signoff-scope" in reason
    assert "never reached" in reason


def test_stall_reason_renders_gate_exhausted_detail():
    reason = _stall_reason(_stalled_wf_state({
        "kind": "gate_exhausted",
        "nodes": ["g-build"],
        "reason": "gate 'g-build' fix-loop exhausted after 3 evaluation(s) "
                  "(max=3, decision=needs_fix: impl-report failed schema check)",
    }))
    assert "g-build" in reason
    assert "fix-loop" in reason
    assert "impl-report failed schema check" in reason


def test_stall_reason_without_detail_is_generic_but_honest():
    reason = _stall_reason(_stalled_wf_state(None))
    assert "stalled" in reason.lower()


def test_stall_reason_never_reads_workflow_nodes():
    """The driver must render the park message from the run-level record only —
    a state whose ``nodes`` access explodes must still render fine."""

    class _NoNodes:
        stall = {"kind": "starved_nodes", "nodes": ["b"], "reason": "a dead-ended"}

        @property
        def nodes(self):  # pragma: no cover - the assertion is that it's unused
            raise AssertionError("_stall_reason must not read WorkflowState.nodes")

    reason = _stall_reason(_NoNodes())
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
    import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = lambda graph, executor, state_ops=None: stalled_state
    try:
        with patch("adapters.cronos.adapter.CronosAdapter"):
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
    from state_types import BudgetState, NodeState, WorkflowState
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
    import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = lambda graph, executor, state_ops=None: verdict_routed_done
    try:
        with patch("adapters.cronos.adapter.CronosAdapter"):
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

    import runner as _runner_mod
    original_run = _runner_mod.run

    def exploding_run(graph, executor, state_ops=None):
        raise RuntimeError("runner exploded")

    _runner_mod.run = exploding_run
    try:
        with patch("adapters.cronos.adapter.CronosAdapter"):
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
