"""I3 — CronosAdapter.runGate tests (R4).

Tests:
- Delegates to app.pipeline.gate.runGate with gate_id + state_path
- Maps proceed/needs_fix/fail/retry decisions to results.GateResult
- Writes gate node into state.json on proceed
- Writes gate node with "needs_fix" on non-proceed
- Returns GateResult(decision="fail") with errors on failure gate
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_BUNDLE = Path(__file__).parent.parent.parent / "packages" / "delivery-workflow"
if str(_BUNDLE) not in sys.path:
    sys.path.insert(0, str(_BUNDLE))

from adapters.cronos.adapter import CronosAdapter
from lib.state.store import StateStore
from results import GateResult
from state_types import BudgetState, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cronos_gate_result(
    decision: str = "proceed",
    errors: list[str] | None = None,
    evidence: dict | None = None,
) -> MagicMock:
    """Build a mock app.pipeline.gate.GateResult."""
    r = MagicMock()
    r.decision = decision
    r.errors = errors or []
    r.evidence = evidence or {}
    r.to_dict = lambda: {
        "decision": decision,
        "errors": errors or [],
        "evidence": evidence or {},
    }
    return r


def _adapter(tmp_path: Path) -> CronosAdapter:
    run_dir = tmp_path / "run"
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
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunGateProceed:
    def test_returns_gate_result_proceed(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        gate = {"id": "g-scout", "checks": []}

        with patch(
            "app.pipeline.gate.runGate",
            return_value=_make_cronos_gate_result("proceed"),
        ):
            result = adapter.runGate(gate, ["reports/scout.md"])

        assert isinstance(result, GateResult)
        assert result.decision == "proceed"

    def test_writes_done_node_on_proceed(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        gate = {"id": "g-scout", "checks": []}

        with patch(
            "app.pipeline.gate.runGate",
            return_value=_make_cronos_gate_result("proceed"),
        ):
            adapter.runGate(gate, [])

        ws = StateStore(tmp_path / "run").read()
        assert "g-scout" in ws.nodes
        assert ws.nodes["g-scout"].status == "done"
        assert ws.nodes["g-scout"].gate is not None
        assert ws.nodes["g-scout"].gate["decision"] == "proceed"

    def test_passes_artifact_paths(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        gate = {"id": "g-scout", "checks": []}
        captured: dict = {}

        def _fake_run_gate(gate, paths, *, space, gate_id, state_path):
            captured["paths"] = paths
            captured["gate_id"] = gate_id
            return _make_cronos_gate_result("proceed")

        with patch("app.pipeline.gate.runGate", side_effect=_fake_run_gate):
            adapter.runGate(gate, ["a.md", "b.md"])

        assert captured["paths"] == ["a.md", "b.md"]
        assert captured["gate_id"] == "g-scout"


class TestRunGateNeedsFix:
    def test_returns_needs_fix(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        gate = {"id": "g-review", "checks": []}

        with patch(
            "app.pipeline.gate.runGate",
            return_value=_make_cronos_gate_result(
                "needs_fix",
                errors=["schema check failed: missing required field 'traceability'"],
            ),
        ):
            result = adapter.runGate(gate, [])

        assert result.decision == "needs_fix"
        assert result.errors

    def test_writes_needs_fix_node(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        gate = {"id": "g-review", "checks": []}

        with patch(
            "app.pipeline.gate.runGate",
            return_value=_make_cronos_gate_result("needs_fix"),
        ):
            adapter.runGate(gate, [])

        ws = StateStore(tmp_path / "run").read()
        assert ws.nodes["g-review"].status == "needs_fix"


class TestRunGateFail:
    def test_returns_fail(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        gate = {"id": "g-tests", "checks": []}

        with patch(
            "app.pipeline.gate.runGate",
            return_value=_make_cronos_gate_result(
                "fail", errors=["tests failed: 3 tests failing"]
            ),
        ):
            result = adapter.runGate(gate, [])

        assert result.decision == "fail"
        assert result.errors == ["tests failed: 3 tests failing"]

    def test_preserves_evidence(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        gate = {"id": "g-tests", "checks": []}
        evidence = {"coverage": 72.5, "failing_tests": 3}

        with patch(
            "app.pipeline.gate.runGate",
            return_value=_make_cronos_gate_result("fail", evidence=evidence),
        ):
            result = adapter.runGate(gate, [])

        assert result.evidence == evidence


class TestRunGateNoId:
    def test_no_gate_id_skips_state_write(self, tmp_path: Path) -> None:
        """Gate with no 'id' key should not write to state.json."""
        adapter = _adapter(tmp_path)
        gate = {"checks": []}

        with patch(
            "app.pipeline.gate.runGate",
            return_value=_make_cronos_gate_result("proceed"),
        ):
            result = adapter.runGate(gate, [])

        assert result.decision == "proceed"
        ws = StateStore(tmp_path / "run").read()
        assert not ws.nodes  # no nodes written
