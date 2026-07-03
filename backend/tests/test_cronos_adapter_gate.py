"""I3 — CronosAdapter.runGate tests (R4, R9).

Tests:
- Delegates to lib.gate.runGate with gate_id + space (never state_path)
- Maps proceed/needs_fix/fail/retry decisions to results.GateResult
- R9 (kills D11): returns the GateResult ONLY — zero StateOps writes.  The
  runner is the single writer of node status/gate detail; it persists a
  non-proceed decision once as node status 'needs_fix'
- Returns GateResult(decision="fail") with errors on failure gate
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


from app.delivery_adapter import CronosAdapter
from delivery_workflow.lib.state.store import StateStore
from delivery_workflow.results import GateResult
from delivery_workflow.state_types import BudgetState, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cronos_gate_result(
    decision: str = "proceed",
    errors: list[str] | None = None,
    evidence: dict | None = None,
) -> MagicMock:
    """Build a mock lib.gate.GateResult."""
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
            "delivery_workflow.lib.gate.runGate",
            return_value=_make_cronos_gate_result("proceed"),
        ):
            result = adapter.runGate(gate, ["reports/scout.md"])

        assert isinstance(result, GateResult)
        assert result.decision == "proceed"

    def test_does_not_write_state_on_proceed(self, tmp_path: Path) -> None:
        """R9 (kills D11): runGate returns the GateResult ONLY.  The runner
        persists the gate node (status 'done' on proceed) — the adapter's
        historical out-of-band write here was the double-writer half of the
        phantom needs_fix→done event-log transition."""
        adapter = _adapter(tmp_path)
        gate = {"id": "g-scout", "checks": []}

        with patch(
            "delivery_workflow.lib.gate.runGate",
            return_value=_make_cronos_gate_result("proceed"),
        ):
            adapter.runGate(gate, [])

        ws = StateStore(tmp_path / "run").read()
        assert ws.nodes == {}, (
            f"runGate wrote node state out-of-band: {ws.nodes!r} — the runner "
            "is the single writer of node fields (R9)"
        )

    def test_passes_artifact_paths(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        gate = {"id": "g-scout", "checks": []}
        captured: dict = {}

        def _fake_run_gate(gate, paths, *, space, gate_id, state_path=None):
            captured["paths"] = paths
            captured["gate_id"] = gate_id
            captured["space"] = space
            return _make_cronos_gate_result("proceed")

        with patch("delivery_workflow.lib.gate.runGate", side_effect=_fake_run_gate):
            adapter.runGate(gate, ["a.md", "b.md"])

        # Paths are resolved to absolute under the space dir so the gate's direct
        # artifact reads (acceptance/traceability) find them, and space is passed.
        assert all(p.endswith("a.md") or p.endswith("b.md") for p in captured["paths"])
        assert all(str(adapter._space_dir) in p for p in captured["paths"])
        assert captured["space"] == adapter._space_dir
        assert captured["gate_id"] == "g-scout"

    def test_injects_class_and_slug_into_schema_check(self, tmp_path: Path) -> None:
        """A bare {type: schema} check gets agent(class)+slug injected from the
        upstream CC-v1 artifact filename, so the gate can locate/verify it."""
        adapter = _adapter(tmp_path)
        gate = {"id": "g-scout", "checks": [{"type": "schema"}]}
        captured: dict = {}

        def _fake_run_gate(gate, paths, *, space, gate_id, state_path=None):
            captured["checks"] = gate.get("checks")
            return _make_cronos_gate_result("proceed")

        with patch("delivery_workflow.lib.gate.runGate", side_effect=_fake_run_gate):
            adapter.runGate(gate, [".cronos/pipeline/my-goal/scout-report-my-goal.md"])

        schema_check = captured["checks"][0]
        assert schema_check["agent"] == "research"  # scout-report → research class
        assert schema_check["slug"] == "my-goal"


def test_class_and_slug_from_artifact():
    from app.delivery_adapter import _class_and_slug_from_artifact

    # .cronos/pipeline/ convention: slug in the filename suffix.
    assert _class_and_slug_from_artifact(
        [".cronos/pipeline/g/analysis-report-g.md"]
    ) == ("analysis", "g")
    assert _class_and_slug_from_artifact(
        ["review-report-my--i2.md"]
    ) == ("review", "my--i2")
    assert _class_and_slug_from_artifact([]) == (None, None)
    assert _class_and_slug_from_artifact(["random.md"]) == (None, None)

    # B3 — .cronos/delivery/ convention: bare {prefix}.md, slug from parent dir.
    assert _class_and_slug_from_artifact(
        [".cronos/delivery/sg1-fix-create-goal-skills/scout-report.md"]
    ) == ("research", "sg1-fix-create-goal-skills")
    assert _class_and_slug_from_artifact(
        ["/abs/space/.cronos/delivery/my-goal/analysis-report.md"]
    ) == ("analysis", "my-goal")
    # A bare prefix with no parent directory context yields no match (no slug
    # can be recovered — the parent-dir branch requires a real directory name).
    assert _class_and_slug_from_artifact(["scout-report.md"]) == (None, None)


class TestRunGateSingleWriter:
    """R9 (kills D11): the adapter never writes node state; lib.gate's
    standalone _write_gate_result never runs under the runner (state_path is
    not passed — its partial, statusless node entry would corrupt a
    StateStore state.json AND make it a second writer)."""

    def test_run_gate_leaves_state_json_untouched(self, tmp_path: Path) -> None:
        # Real lib.gate.runGate (NOT mocked) with an empty check list → proceed.
        # Exercises the full adapter→lib.gate path on a bootstrapped state.
        adapter = _adapter(tmp_path)
        before = (tmp_path / "run" / "state.json").read_text()

        result = adapter.runGate({"id": "g-scout", "checks": []}, [])

        assert result.decision == "proceed"
        after = (tmp_path / "run" / "state.json").read_text()
        assert after == before, "runGate modified state.json (R9 single writer)"
        # And a fresh read still succeeds (no statusless node corruption).
        ws = StateStore(tmp_path / "run").read()
        assert ws.status == "running"
        assert ws.nodes == {}

    def test_run_gate_does_not_write_statusless_node_via_state_path(
        self, tmp_path: Path
    ) -> None:
        """The adapter does not pass state_path to lib.gate, so lib.gate's
        _write_gate_result (CLI-standalone only) never runs."""
        captured: dict = {}

        def _fake_run_gate(gate, paths, *, space, gate_id, state_path=None):
            captured["state_path"] = state_path
            return _make_cronos_gate_result("proceed")

        adapter = _adapter(tmp_path)
        with patch("delivery_workflow.lib.gate.runGate", side_effect=_fake_run_gate):
            adapter.runGate({"id": "g-scout", "checks": []}, [])

        assert captured["state_path"] is None


class TestRunGateNeedsFix:
    def test_returns_needs_fix(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        gate = {"id": "g-review", "checks": []}

        with patch(
            "delivery_workflow.lib.gate.runGate",
            return_value=_make_cronos_gate_result(
                "needs_fix",
                errors=["schema check failed: missing required field 'traceability'"],
            ),
        ):
            result = adapter.runGate(gate, [])

        assert result.decision == "needs_fix"
        assert result.errors

    def test_does_not_write_needs_fix_node(self, tmp_path: Path) -> None:
        """R9: the non-proceed decision travels back on the GateResult only;
        the runner writes it once as the REAL node status 'needs_fix'."""
        adapter = _adapter(tmp_path)
        gate = {"id": "g-review", "checks": []}

        with patch(
            "delivery_workflow.lib.gate.runGate",
            return_value=_make_cronos_gate_result("needs_fix"),
        ):
            adapter.runGate(gate, [])

        ws = StateStore(tmp_path / "run").read()
        assert "g-review" not in ws.nodes, (
            "runGate wrote the needs_fix node out-of-band — that write was "
            "half of the D11 double-writer (runner then overwrote with done)"
        )


class TestRunGateFail:
    def test_returns_fail(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        gate = {"id": "g-tests", "checks": []}

        with patch(
            "delivery_workflow.lib.gate.runGate",
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
            "delivery_workflow.lib.gate.runGate",
            return_value=_make_cronos_gate_result("fail", evidence=evidence),
        ):
            result = adapter.runGate(gate, [])

        assert result.evidence == evidence


class TestRunGateNoId:
    def test_no_gate_id_still_returns_result_without_writes(self, tmp_path: Path) -> None:
        """Gate with no 'id' key returns a result; nothing is written (R9 —
        nothing is written for ANY gate)."""
        adapter = _adapter(tmp_path)
        gate = {"checks": []}

        with patch(
            "delivery_workflow.lib.gate.runGate",
            return_value=_make_cronos_gate_result("proceed"),
        ):
            result = adapter.runGate(gate, [])

        assert result.decision == "proceed"
        ws = StateStore(tmp_path / "run").read()
        assert not ws.nodes  # no nodes written
