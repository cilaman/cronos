"""Tests for backend/app/harnesses/state_mapping.py (I3 — R5).

Coverage
--------
- Forward mapping: RunState → WorkflowState
  - All 5 harness node statuses map correctly
  - Run-level status mapping (running/done/failed/cancelled)
  - Loop bookkeeping preserved (attempt, prior_finding_ids)
  - All NodeState fields preserved in WfNodeState.fields
  - spec field = harness_id
  - run_id preserved

- Reverse mapping: WorkflowState → RunState
  - All 5 WorkflowState node statuses map correctly
  - Run-level status mapping (running/done/failed/blocked/escalated)
  - Loop bookkeeping preserved
  - Identity fields from base_run_state preserved (harness_id, goal_task_id, waiting_node_id)

- Round-trip property tests
  - RunState → WorkflowState → RunState equality (no loss) for all node status variants
  - Unknown / missing status values handled gracefully

- Edge cases
  - Empty nodes_executed
  - 'skipped' node round-trips faithfully via _harness_status sentinel
  - prior_finding_ids list is deep-copied (no aliasing)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Bring delivery-workflow onto sys.path (same pattern as other backend tests).
_BUNDLE = Path(__file__).parent.parent.parent / "packages" / "delivery-workflow"
if str(_BUNDLE) not in sys.path:
    sys.path.insert(0, str(_BUNDLE))

from state_types import NodeState as WfNodeState  # noqa: E402
from state_types import WorkflowState  # noqa: E402
from state_types import BudgetState  # noqa: E402

from app.harnesses.run_state import NodeState as HarnessNodeState, RunState  # noqa: E402
from app.harnesses.state_mapping import (  # noqa: E402
    runstate_to_workflowstate,
    workflowstate_to_runstate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_state(
    *,
    run_id: str = "run-1",
    harness_id: str = "my-harness",
    goal_task_id: str = "task-1",
    status: str = "running",
    waiting_node_id: str | None = None,
    nodes: dict | None = None,
) -> RunState:
    return RunState(
        run_id=run_id,
        harness_id=harness_id,
        goal_task_id=goal_task_id,
        status=status,
        waiting_node_id=waiting_node_id,
        nodes_executed=nodes or {},
    )


def _make_node(
    status: str = "pending",
    child_task_id: str | None = None,
    output: str | None = None,
    reason: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    wake_at: str | None = None,
    attempt: int = 0,
    prior_finding_ids: list | None = None,
) -> HarnessNodeState:
    return HarnessNodeState(
        status=status,
        child_task_id=child_task_id,
        output=output,
        reason=reason,
        started_at=started_at,
        ended_at=ended_at,
        wake_at=wake_at,
        attempt=attempt,
        prior_finding_ids=prior_finding_ids or [],
    )


# ---------------------------------------------------------------------------
# Forward mapping: node status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "harness_status, expected_wf_status",
    [
        ("pending", "blocked"),
        ("in_progress", "running"),
        ("done", "done"),
        ("failed", "failed"),
        ("skipped", "done"),
    ],
)
def test_forward_node_status(harness_status: str, expected_wf_status: str) -> None:
    rs = _make_run_state(nodes={"n1": _make_node(status=harness_status)})
    ws = runstate_to_workflowstate(rs, "my-harness")
    assert ws.nodes["n1"].status == expected_wf_status


# ---------------------------------------------------------------------------
# Forward mapping: run-level status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "harness_run_status, expected_wf_status",
    [
        ("running", "running"),
        ("done", "done"),
        ("failed", "failed"),
        ("cancelled", "failed"),
    ],
)
def test_forward_run_status(harness_run_status: str, expected_wf_status: str) -> None:
    rs = _make_run_state(status=harness_run_status)
    ws = runstate_to_workflowstate(rs, "my-harness")
    assert ws.status == expected_wf_status


# ---------------------------------------------------------------------------
# Forward mapping: metadata fields
# ---------------------------------------------------------------------------


def test_forward_spec_equals_harness_id() -> None:
    rs = _make_run_state(harness_id="pipeline-x")
    ws = runstate_to_workflowstate(rs, "pipeline-x")
    assert ws.spec == "pipeline-x"


def test_forward_run_id_preserved() -> None:
    rs = _make_run_state(run_id="run-abc")
    ws = runstate_to_workflowstate(rs, "h")
    assert ws.run_id == "run-abc"


def test_forward_empty_nodes() -> None:
    rs = _make_run_state()
    ws = runstate_to_workflowstate(rs, "h")
    assert ws.nodes == {}


# ---------------------------------------------------------------------------
# Forward mapping: loop bookkeeping preserved
# ---------------------------------------------------------------------------


def test_forward_attempt_preserved() -> None:
    rs = _make_run_state(nodes={"n1": _make_node(attempt=3)})
    ws = runstate_to_workflowstate(rs, "h")
    assert ws.nodes["n1"].attempt == 3


def test_forward_prior_finding_ids_preserved() -> None:
    rs = _make_run_state(nodes={"n1": _make_node(prior_finding_ids=["f1", "f2"])})
    ws = runstate_to_workflowstate(rs, "h")
    assert ws.nodes["n1"].fields["prior_finding_ids"] == ["f1", "f2"]


def test_forward_prior_finding_ids_deep_copy() -> None:
    original_ids = ["f1", "f2"]
    rs = _make_run_state(nodes={"n1": _make_node(prior_finding_ids=original_ids)})
    ws = runstate_to_workflowstate(rs, "h")
    ws.nodes["n1"].fields["prior_finding_ids"].append("f3")
    assert original_ids == ["f1", "f2"]  # original not mutated


# ---------------------------------------------------------------------------
# Forward mapping: all NodeState fields preserved in WfNodeState.fields
# ---------------------------------------------------------------------------


def test_forward_all_node_fields_preserved() -> None:
    node = _make_node(
        status="done",
        child_task_id="task-42",
        output="some output",
        reason="all good",
        started_at="2026-01-01T00:00:00Z",
        ended_at="2026-01-01T01:00:00Z",
        wake_at="2026-01-01T02:00:00Z",
        attempt=2,
        prior_finding_ids=["f-old"],
    )
    rs = _make_run_state(nodes={"n1": node})
    ws = runstate_to_workflowstate(rs, "h")
    wf_node = ws.nodes["n1"]
    fields = wf_node.fields

    assert fields["child_task_id"] == "task-42"
    assert fields["output"] == "some output"
    assert fields["reason"] == "all good"
    assert fields["started_at"] == "2026-01-01T00:00:00Z"
    assert fields["ended_at"] == "2026-01-01T01:00:00Z"
    assert fields["wake_at"] == "2026-01-01T02:00:00Z"
    assert fields["prior_finding_ids"] == ["f-old"]
    assert wf_node.attempt == 2
    assert wf_node.status == "done"


# ---------------------------------------------------------------------------
# Reverse mapping: node status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "wf_status, expected_harness_status",
    [
        ("running", "in_progress"),
        ("done", "done"),
        ("failed", "failed"),
        ("blocked", "pending"),
        ("escalated", "failed"),
    ],
)
def test_reverse_node_status(wf_status: str, expected_harness_status: str) -> None:
    wf_node = WfNodeState(status=wf_status)
    ws = WorkflowState(
        spec="h",
        run_id="run-1",
        status="running",
        budget=BudgetState(usd_ceiling=0.0),
        nodes={"n1": wf_node},
    )
    base = _make_run_state()
    rs = workflowstate_to_runstate(ws, base)
    assert rs.nodes_executed["n1"].status == expected_harness_status


# ---------------------------------------------------------------------------
# Reverse mapping: run-level status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "wf_run_status, expected_harness_status",
    [
        ("running", "running"),
        ("done", "done"),
        ("failed", "failed"),
        ("blocked", "running"),
        ("escalated", "failed"),
    ],
)
def test_reverse_run_status(wf_run_status: str, expected_harness_status: str) -> None:
    ws = WorkflowState(
        spec="h",
        run_id="run-1",
        status=wf_run_status,  # type: ignore[arg-type]
        budget=BudgetState(usd_ceiling=0.0),
    )
    base = _make_run_state()
    rs = workflowstate_to_runstate(ws, base)
    assert rs.status == expected_harness_status


# ---------------------------------------------------------------------------
# Reverse mapping: identity fields from base_run_state
# ---------------------------------------------------------------------------


def test_reverse_harness_id_from_base() -> None:
    ws = WorkflowState(spec="different-spec", run_id="run-1", status="done", budget=BudgetState(usd_ceiling=0.0))
    base = _make_run_state(harness_id="my-harness")
    rs = workflowstate_to_runstate(ws, base)
    assert rs.harness_id == "my-harness"


def test_reverse_goal_task_id_from_base() -> None:
    ws = WorkflowState(spec="h", run_id="run-1", status="done", budget=BudgetState(usd_ceiling=0.0))
    base = _make_run_state(goal_task_id="task-999")
    rs = workflowstate_to_runstate(ws, base)
    assert rs.goal_task_id == "task-999"


def test_reverse_waiting_node_id_from_base() -> None:
    ws = WorkflowState(spec="h", run_id="run-1", status="running", budget=BudgetState(usd_ceiling=0.0))
    base = _make_run_state(waiting_node_id="wait-node-1")
    rs = workflowstate_to_runstate(ws, base)
    assert rs.waiting_node_id == "wait-node-1"


def test_reverse_run_id_from_base() -> None:
    ws = WorkflowState(spec="h", run_id="different-id", status="done", budget=BudgetState(usd_ceiling=0.0))
    base = _make_run_state(run_id="run-abc")
    rs = workflowstate_to_runstate(ws, base)
    assert rs.run_id == "run-abc"


# ---------------------------------------------------------------------------
# Reverse mapping: loop bookkeeping
# ---------------------------------------------------------------------------


def test_reverse_attempt_preserved() -> None:
    wf_node = WfNodeState(status="done", attempt=5)
    ws = WorkflowState(spec="h", run_id="run-1", status="done", budget=BudgetState(usd_ceiling=0.0), nodes={"n1": wf_node})
    base = _make_run_state()
    rs = workflowstate_to_runstate(ws, base)
    assert rs.nodes_executed["n1"].attempt == 5


def test_reverse_prior_finding_ids_preserved() -> None:
    wf_node = WfNodeState(status="done", fields={"prior_finding_ids": ["f1", "f2"]})
    ws = WorkflowState(spec="h", run_id="run-1", status="done", budget=BudgetState(usd_ceiling=0.0), nodes={"n1": wf_node})
    base = _make_run_state()
    rs = workflowstate_to_runstate(ws, base)
    assert rs.nodes_executed["n1"].prior_finding_ids == ["f1", "f2"]


def test_reverse_prior_finding_ids_deep_copy() -> None:
    original_ids = ["f1", "f2"]
    wf_node = WfNodeState(status="done", fields={"prior_finding_ids": original_ids})
    ws = WorkflowState(spec="h", run_id="run-1", status="done", budget=BudgetState(usd_ceiling=0.0), nodes={"n1": wf_node})
    base = _make_run_state()
    rs = workflowstate_to_runstate(ws, base)
    rs.nodes_executed["n1"].prior_finding_ids.append("f3")
    assert original_ids == ["f1", "f2"]


def test_reverse_prior_finding_ids_missing_defaults_to_empty() -> None:
    wf_node = WfNodeState(status="done")  # no fields['prior_finding_ids']
    ws = WorkflowState(spec="h", run_id="run-1", status="done", budget=BudgetState(usd_ceiling=0.0), nodes={"n1": wf_node})
    base = _make_run_state()
    rs = workflowstate_to_runstate(ws, base)
    assert rs.nodes_executed["n1"].prior_finding_ids == []


# ---------------------------------------------------------------------------
# Round-trip property tests (RunState → WorkflowState → RunState)
# ---------------------------------------------------------------------------


def _assert_nodestate_equal(a: HarnessNodeState, b: HarnessNodeState, node_id: str) -> None:
    assert a.status == b.status, f"node {node_id}: status mismatch {a.status!r} != {b.status!r}"
    assert a.child_task_id == b.child_task_id, f"node {node_id}: child_task_id mismatch"
    assert a.output == b.output, f"node {node_id}: output mismatch"
    assert a.reason == b.reason, f"node {node_id}: reason mismatch"
    assert a.started_at == b.started_at, f"node {node_id}: started_at mismatch"
    assert a.ended_at == b.ended_at, f"node {node_id}: ended_at mismatch"
    assert a.wake_at == b.wake_at, f"node {node_id}: wake_at mismatch"
    assert a.attempt == b.attempt, f"node {node_id}: attempt mismatch"
    assert a.prior_finding_ids == b.prior_finding_ids, f"node {node_id}: prior_finding_ids mismatch"


@pytest.mark.parametrize(
    "status",
    ["pending", "in_progress", "done", "failed", "skipped"],
)
def test_roundtrip_node_status_no_loss(status: str) -> None:
    """Round-trip must preserve the original harness status exactly."""
    node = _make_node(
        status=status,
        child_task_id="task-1",
        output="out",
        reason="ok",
        started_at="2026-01-01T00:00:00Z",
        ended_at="2026-01-01T01:00:00Z",
        wake_at=None,
        attempt=2,
        prior_finding_ids=["fid-1", "fid-2"],
    )
    rs_orig = _make_run_state(nodes={"n1": node}, status="running", waiting_node_id="w1")
    ws = runstate_to_workflowstate(rs_orig, "my-harness")
    rs_back = workflowstate_to_runstate(ws, rs_orig)

    assert rs_back.run_id == rs_orig.run_id
    assert rs_back.harness_id == rs_orig.harness_id
    assert rs_back.goal_task_id == rs_orig.goal_task_id
    assert rs_back.status == rs_orig.status
    assert rs_back.waiting_node_id == rs_orig.waiting_node_id
    assert set(rs_back.nodes_executed.keys()) == set(rs_orig.nodes_executed.keys())
    _assert_nodestate_equal(rs_back.nodes_executed["n1"], rs_orig.nodes_executed["n1"], "n1")


def test_roundtrip_multiple_nodes() -> None:
    """Round-trip with multiple nodes of different statuses."""
    nodes = {
        "trigger": _make_node(status="done", output="fired"),
        "agent-1": _make_node(status="in_progress", child_task_id="task-a", attempt=1),
        "decision": _make_node(status="done"),
        "agent-2": _make_node(status="pending"),
        "wait": _make_node(status="skipped", reason="bypassed"),
    }
    rs_orig = _make_run_state(nodes=nodes, status="running")
    ws = runstate_to_workflowstate(rs_orig, "multi-harness")
    rs_back = workflowstate_to_runstate(ws, rs_orig)

    for node_id in nodes:
        _assert_nodestate_equal(
            rs_back.nodes_executed[node_id],
            rs_orig.nodes_executed[node_id],
            node_id,
        )


@pytest.mark.parametrize(
    "run_status",
    ["running", "done", "failed"],
)
def test_roundtrip_run_status_no_loss(run_status: str) -> None:
    """Run-level statuses that are valid in both systems round-trip exactly."""
    rs_orig = _make_run_state(status=run_status)
    ws = runstate_to_workflowstate(rs_orig, "h")
    rs_back = workflowstate_to_runstate(ws, rs_orig)
    assert rs_back.status == run_status


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_forward_unknown_node_status_defaults_to_blocked() -> None:
    """Unknown harness status maps to 'blocked' (safe default)."""
    rs = _make_run_state(nodes={"n1": _make_node(status="unknown-status")})
    ws = runstate_to_workflowstate(rs, "h")
    assert ws.nodes["n1"].status == "blocked"


def test_reverse_unknown_wf_node_status_defaults_to_pending() -> None:
    """Unknown WorkflowState node status maps to 'pending' (safe default)."""
    wf_node = WfNodeState(status="unknown-wf-status")
    ws = WorkflowState(spec="h", run_id="run-1", status="running", budget=BudgetState(usd_ceiling=0.0), nodes={"n1": wf_node})
    base = _make_run_state()
    rs = workflowstate_to_runstate(ws, base)
    assert rs.nodes_executed["n1"].status == "pending"


def test_forward_null_optional_fields_preserved() -> None:
    """None optional fields pass through as None in WfNodeState.fields."""
    node = _make_node(status="pending")  # all optionals are None
    rs = _make_run_state(nodes={"n1": node})
    ws = runstate_to_workflowstate(rs, "h")
    fields = ws.nodes["n1"].fields
    assert fields["child_task_id"] is None
    assert fields["output"] is None
    assert fields["reason"] is None
    assert fields["started_at"] is None
    assert fields["ended_at"] is None
    assert fields["wake_at"] is None


def test_reverse_empty_nodes() -> None:
    """WorkflowState with no nodes produces RunState with empty nodes_executed."""
    ws = WorkflowState(spec="h", run_id="run-1", status="running", budget=BudgetState(usd_ceiling=0.0))
    base = _make_run_state()
    rs = workflowstate_to_runstate(ws, base)
    assert rs.nodes_executed == {}


def test_forward_skipped_round_trip_via_sentinel() -> None:
    """'skipped' maps to 'done' in WF but round-trips back to 'skipped' via _harness_status sentinel."""
    node = _make_node(status="skipped", reason="branch not taken")
    rs_orig = _make_run_state(nodes={"n1": node})
    ws = runstate_to_workflowstate(rs_orig, "h")

    # The WF node should show 'done'
    assert ws.nodes["n1"].status == "done"
    # But the sentinel preserves the original
    assert ws.nodes["n1"].fields["_harness_status"] == "skipped"

    # Round-trip restores 'skipped'
    rs_back = workflowstate_to_runstate(ws, rs_orig)
    assert rs_back.nodes_executed["n1"].status == "skipped"


def test_reverse_node_without_harness_status_sentinel_uses_wf_mapping() -> None:
    """If _harness_status is absent, reverse mapping falls back to _WF_TO_HARNESS_NODE."""
    wf_node = WfNodeState(status="done", fields={})  # no _harness_status
    ws = WorkflowState(spec="h", run_id="run-1", status="done", budget=BudgetState(usd_ceiling=0.0), nodes={"n1": wf_node})
    base = _make_run_state()
    rs = workflowstate_to_runstate(ws, base)
    assert rs.nodes_executed["n1"].status == "done"
