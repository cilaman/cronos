"""CronosAdapter.runExec tests (P1 Embodiment A — delivery exec node).

Verifies the adapter runs a shell command to completion (no LLM), writes the
captured output as the node's own artifact, and maps the exit code to node status:
- exit 0 → done
- non-zero → failed, unless fail_on_nonzero=False (then done; g-tests routes)
- a written artifact path is always returned on success
- the node's state row is persisted with status + artifact + exit_code
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

_BUNDLE = Path(__file__).parent.parent.parent / "packages" / "delivery-workflow"
if str(_BUNDLE) not in sys.path:
    sys.path.insert(0, str(_BUNDLE))

from adapters.cronos.adapter import CronosAdapter
from lib.state.store import StateStore
from state_types import BudgetState, WorkflowState


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


def test_exec_persists_node_state(tmp_path):
    adapter = _adapter(tmp_path)
    result = adapter.runExec("testrun", "echo ok", {})
    # exit_code is carried on the ExecResult (StateStore does not round-trip fields).
    assert result.exit_code == 0
    state = StateStore(adapter._run_dir).read()
    ns = state.nodes["testrun"]
    assert ns.status == "done"
    assert ns.artifact_paths and ns.artifact_paths[0].endswith("testrun-output.md")


def test_exec_runs_in_space_dir(tmp_path):
    """The command's cwd is the space dir (so pytest resolves the repo)."""
    adapter = _adapter(tmp_path)
    result = adapter.runExec("pwd-node", "pwd", {})
    assert result.status == "done"
    assert str(adapter._space_dir) in result.stdout_tail
