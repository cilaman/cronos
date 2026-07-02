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
    _MAX_FAILED_RESUMES,
    _resume_from_blocked,
    _resume_from_failed,
    _stalled_gate_ids,
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
# _resume_from_blocked — clear a blocked run so it continues past a sign-off
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


def test_resume_from_blocked_approves_human_node_and_clears_status():
    from state_types import BudgetState, NodeState, WorkflowState

    state = WorkflowState(
        spec="w", run_id="goal-1", status="blocked",
        budget=BudgetState(usd_ceiling=5.0),
        nodes={
            "scout": NodeState(status="done"),
            "signoff-scope": NodeState(status="blocked"),
        },
    )
    ops = _FakeStateOps(state)
    adapter = SimpleNamespace(state=ops)

    _resume_from_blocked(adapter, _graph_with_human(), "goal-1")

    # Status reset to running so the runner's cancel-race guard won't halt.
    assert state.status == "running"
    # The blocked human node is marked done → runner routes to its successors.
    assert state.nodes["signoff-scope"].status == "done"
    assert ops.writes and ops.writes[0]["status"] == "running"
    assert ops.writes[0]["nodes"]["signoff-scope"]["status"] == "done"


def test_resume_from_blocked_noop_when_running():
    from state_types import BudgetState, NodeState, WorkflowState

    state = WorkflowState(
        spec="w", run_id="g", status="running",
        budget=BudgetState(usd_ceiling=5.0),
        nodes={"scout": NodeState(status="done")},
    )
    ops = _FakeStateOps(state)
    _resume_from_blocked(SimpleNamespace(state=ops), _graph_with_human(), "g")
    # Fresh (non-blocked) run must not be patched.
    assert ops.writes == []


def test_resume_from_blocked_does_not_touch_non_human_blocked_node():
    """A blocked node that is NOT a human/wait node is left blocked (only status cleared)."""
    from state_types import BudgetState, NodeState, WorkflowState

    state = WorkflowState(
        spec="w", run_id="g", status="blocked",
        budget=BudgetState(usd_ceiling=5.0),
        nodes={"scout": NodeState(status="blocked")},  # scout is an agent, not human
    )
    ops = _FakeStateOps(state)
    _resume_from_blocked(SimpleNamespace(state=ops), _graph_with_human(), "g")
    assert state.status == "running"
    assert state.nodes["scout"].status == "blocked"  # not auto-approved
    assert "nodes" not in ops.writes[0]


# ---------------------------------------------------------------------------
# _resume_from_failed — bound re-dispatch of a persistently-failing node
# ---------------------------------------------------------------------------


def _failed_state(node_ids, status="failed"):
    from state_types import BudgetState, NodeState, WorkflowState

    return WorkflowState(
        spec="w", run_id="goal-1", status=status,
        budget=BudgetState(usd_ceiling=5.0),
        nodes={nid: NodeState(status="failed") for nid in node_ids},
    )


def test_resume_from_failed_bounds_retries(tmp_path):
    adapter = SimpleNamespace(state=_FakeStateOps(_failed_state(["testrun"])))
    # The first _MAX_FAILED_RESUMES re-entries allow a retry (return None).
    for _ in range(_MAX_FAILED_RESUMES):
        assert _resume_from_failed(adapter, "goal-1", tmp_path) is None
    # The next re-entry exceeds the cap → park reason returned, runner skipped.
    reason = _resume_from_failed(adapter, "goal-1", tmp_path)
    assert reason is not None
    assert "testrun" in reason
    # Counter is persisted in a sidecar so the cap survives process restarts.
    assert (tmp_path / "failed_resumes.json").exists()


def test_resume_from_failed_noop_when_not_failed(tmp_path):
    adapter = SimpleNamespace(state=_FakeStateOps(_failed_state([], status="running")))
    assert _resume_from_failed(adapter, "g", tmp_path) is None


def test_resume_from_failed_noop_when_no_failed_nodes(tmp_path):
    from state_types import BudgetState, NodeState, WorkflowState

    state = WorkflowState(
        spec="w", run_id="g", status="failed",
        budget=BudgetState(usd_ceiling=5.0),
        nodes={"a": NodeState(status="done")},
    )
    adapter = SimpleNamespace(state=_FakeStateOps(state))
    assert _resume_from_failed(adapter, "g", tmp_path) is None


# ---------------------------------------------------------------------------
# _stalled_gate_ids — detect a dead-end gate reported as "done"
# ---------------------------------------------------------------------------

def test_stalled_gate_ids_flags_non_proceed_gate():
    from state_types import BudgetState, NodeState, WorkflowState

    state = WorkflowState(
        spec="w", run_id="g", status="done",
        budget=BudgetState(usd_ceiling=5.0),
        nodes={
            "scout": NodeState(status="done"),
            "g-scout": NodeState(status="done", gate={"decision": "needs_fix"}),
        },
    )
    assert _stalled_gate_ids(state) == ["g-scout"]


def test_stalled_gate_ids_empty_when_all_proceed():
    from state_types import BudgetState, NodeState, WorkflowState

    state = WorkflowState(
        spec="w", run_id="g", status="done",
        budget=BudgetState(usd_ceiling=5.0),
        nodes={
            "g-scout": NodeState(status="done", gate={"decision": "proceed"}),
            "analyze": NodeState(status="done"),
        },
    )
    assert _stalled_gate_ids(state) == []


@pytest.mark.asyncio
async def test_run_delivery_goal_done_with_stalled_gate_parks_waiting(tmp_path):
    """Runner returns done but a gate ended needs_fix → park WAITING, not DONE."""
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

    done_but_stalled = WorkflowState(
        spec="test-workflow", run_id="goal-1", status="done",
        budget=BudgetState(usd_ceiling=5.0),
        nodes={"g-scout": NodeState(status="done", gate={"decision": "needs_fix"})},
    )
    import runner as _runner_mod
    original_run = _runner_mod.run
    _runner_mod.run = lambda graph, executor, state_ops=None: done_but_stalled
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
