"""CronosAdapter.runExec tests (P1 Embodiment A — delivery exec node).

Verifies the adapter runs a shell command to completion (no LLM), writes the
captured output as the node's own artifact, and maps the exit code to node status:
- exit 0 → done
- non-zero → failed, unless fail_on_nonzero=False (then done; g-tests routes)
- a written artifact path is always returned on success
- R9 (kills D11): runExec returns the ExecResult ONLY — the runner is the
  single writer of the exec node's state row (status + artifact + exit_code)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock


from app.delivery_adapter import CronosAdapter
from delivery_workflow.lib.state.store import StateStore
from delivery_workflow.state_types import BudgetState, WorkflowState


def _adapter(tmp_path: Path) -> CronosAdapter:
    # run_dir = <space>/.cronos/delivery-runs/<goal_id>; space_dir derives from it.
    space_dir = tmp_path / "space"
    run_dir = space_dir / ".cronos" / "delivery-runs" / "g1"
    run_dir.mkdir(parents=True)
    ws = WorkflowState(
        spec="delivery-ping",
        run_id="r1",
        status="running",
        budget=BudgetState(usd_ceiling=25.0),
    )
    StateStore(run_dir).write(ws)
    return CronosAdapter(
        store=MagicMock(),
        trace_store=MagicMock(),
        space_id="s1",
        run_dir=run_dir,
        space_dir=space_dir,
    )


def test_exec_zero_exit_is_done_and_writes_artifact(tmp_path):
    adapter = _adapter(tmp_path)
    result = adapter.runExec("testrun", "echo hello", {"produces": {"class": "test"}})

    assert result.status == "done"
    assert result.exit_code == 0
    assert "hello" in result.stdout_tail
    assert result.produces == "test"
    # Artifact was written under run_dir and is named for the node.
    assert result.artifact_path is not None
    art = Path(result.artifact_path)
    assert art.exists()
    assert art.name == "testrun-output.md"
    assert "hello" in art.read_text()


def test_exec_nonzero_exit_is_failed_by_default(tmp_path):
    adapter = _adapter(tmp_path)
    result = adapter.runExec("build", "exit 3", {})
    assert result.status == "failed"
    assert result.exit_code == 3


def test_exec_nonzero_exit_is_done_when_fail_on_nonzero_false(tmp_path):
    """testrun uses fail_on_nonzero=false so a test failure doesn't halt the DAG."""
    adapter = _adapter(tmp_path)
    result = adapter.runExec("testrun", "exit 1", {"fail_on_nonzero": False})
    assert result.status == "done"
    assert result.exit_code == 1


def test_exec_does_not_write_node_state(tmp_path):
    """R9 (kills D11): runExec returns the ExecResult ONLY.  The runner
    persists the exec node's status/artifact_paths/exit_code exactly once
    from that result (runner/dispatch.py) — the adapter's historical
    out-of-band write here was a second writer of the same node fields."""
    adapter = _adapter(tmp_path)
    result = adapter.runExec("testrun", "echo ok", {})
    # Everything the runner needs is carried on the ExecResult.
    assert result.exit_code == 0
    assert result.status == "done"
    assert result.artifact_path and result.artifact_path.endswith("testrun-output.md")
    state = StateStore(adapter._run_dir).read()
    assert "testrun" not in state.nodes, (
        f"runExec wrote node state out-of-band: {state.nodes!r} — the runner "
        "is the single writer of node fields (R9)"
    )


def test_exec_runs_in_space_dir(tmp_path):
    """The command's cwd is the space dir (so pytest resolves the repo)."""
    adapter = _adapter(tmp_path)
    result = adapter.runExec("pwd-node", "pwd", {})
    assert result.status == "done"
    assert str(adapter._space_dir) in result.stdout_tail
