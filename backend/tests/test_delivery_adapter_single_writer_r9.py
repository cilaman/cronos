"""R9 regression — the Cronos adapter returns results ONLY (host half of R9).

Moved from the package suite in R10c (02-package-boundary.md §2.3): the Cronos
adapter is host code, so its tests live here, next to its real dependencies.
The runner-side single-writer laws stay in the package suite
(``packages/delivery-workflow/tests/regression/test_single_writer_r9.py``).

Contract (01-state-model.md §5.8, 03-remediation-plan.md §R9):
``CronosAdapter.runGate``/``runExec`` return GateResult/ExecResult and perform
ZERO StateOps writes — the runner is the single writer of node
status/attempt/artifact_paths/gate/fields (the D11 double-writer kill).
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from app.delivery_adapter import CronosAdapter
from delivery_workflow.lib.state.store import StateStore
from delivery_workflow.results import GateResult
from delivery_workflow.state_types import BudgetState, WorkflowState


class SpyStateOps:
    """StateOps proxy recording every write() patch verbatim."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.writes: list[dict[str, Any]] = []

    def read(self) -> WorkflowState:
        return self._inner.read()

    def write(self, patch: dict[str, Any]) -> None:
        self.writes.append(copy.deepcopy(patch))
        self._inner.write(patch)


class TestAdapterReturnsOnly:
    def _adapter(self, tmp_path: Path) -> tuple[CronosAdapter, SpyStateOps]:
        space_dir = tmp_path / "space"
        run_dir = space_dir / ".cronos" / "delivery-runs" / "g1"
        run_dir.mkdir(parents=True)
        StateStore(run_dir).write(WorkflowState(
            spec="r9", run_id="run-r9", status="running",
            budget=BudgetState(usd_ceiling=0.0),
        ))
        adapter = CronosAdapter(
            store=object(),
            trace_store=object(),
            space_id="s1",
            run_dir=run_dir,
            space_dir=space_dir,
        )
        spy = SpyStateOps(adapter.state)
        adapter.state = spy
        return adapter, spy

    def test_run_gate_performs_zero_state_writes(self, tmp_path):
        adapter, spy = self._adapter(tmp_path)
        # Empty check list → real lib.gate.runGate → proceed.
        result = adapter.runGate({"id": "g-scout", "checks": []}, [])
        assert result.decision == "proceed"
        assert spy.writes == [], (
            f"runGate must return the GateResult ONLY; it wrote {spy.writes!r} "
            "(the runner is the single writer of node fields — R9/D11)"
        )

    def test_run_gate_failing_gate_performs_zero_state_writes(self, tmp_path):
        adapter, spy = self._adapter(tmp_path)
        # Unknown check type → decision 'fail' from the real gate engine.
        result = adapter.runGate(
            {"id": "g-x", "checks": [{"type": "no-such-check"}]}, []
        )
        assert result.decision == "fail"
        assert spy.writes == []

    def test_run_exec_performs_zero_state_writes(self, tmp_path):
        adapter, spy = self._adapter(tmp_path)
        result = adapter.runExec("testrun", "echo ok", {})
        assert result.status == "done"
        assert result.exit_code == 0
        # The artifact file is the exec node's OUTPUT, not node state.
        assert result.artifact_path is not None
        assert Path(result.artifact_path).exists()
        assert spy.writes == [], (
            f"runExec must return the ExecResult ONLY; it wrote {spy.writes!r}"
        )

    def test_run_gate_never_passes_state_path_to_lib_gate(self, tmp_path):
        """lib.gate._write_gate_result is CLI-standalone only: combined with a
        runner-managed state.json it would be a second writer (and its partial,
        statusless entry corrupts StateStore reads)."""
        from unittest.mock import patch

        adapter, spy = self._adapter(tmp_path)
        captured: dict[str, Any] = {}

        def _fake_run_gate(gate, paths, *, space, gate_id, state_path=None):
            captured["state_path"] = state_path
            return GateResult(decision="proceed", errors=[])

        with patch("delivery_workflow.lib.gate.runGate", side_effect=_fake_run_gate):
            adapter.runGate({"id": "g-scout", "checks": []}, [])
        assert captured["state_path"] is None
        assert spy.writes == []
