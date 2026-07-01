"""Tests for backend/app/pipeline/gate.py — runGate engine and all check types."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from lib.gate import (
    GateResult,
    CHECK_REGISTRY,
    runGate,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "gate"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _make_review_content(verdict: str, blocking: bool = False) -> str:
    """Create a minimal inline review report with the given verdict."""
    if blocking:
        findings_yaml = (
            "findings:\n"
            "- id: F1\n"
            "  severity: medium\n"
            "  file: backend/app/gate.py:1\n"
            "  evidence: test evidence\n"
            "  blocking: true\n"
            "  suggested_action: fix it\n"
        )
    else:
        findings_yaml = "findings: []\n"

    return (
        "---\n"
        "cc_version: '1.0'\n"
        "agent: pipeline-reviewer\n"
        "slug: test-slug\n"
        "phase: review\n"
        "status: done\n"
        "confidence: 0.9\n"
        "inputs_used:\n"
        "- backend/app/main.py\n"
        "outputs_produced:\n"
        "- .cronos/pipeline/test-slug/review-report-test-slug.md\n"
        "blockers: []\n"
        "next_consumer: doc\n"
        f"verdict: {verdict}\n"
        + findings_yaml
        + "metrics:\n"
        "  tool_calls: 5\n"
        "  files_read: 1\n"
        "---\n"
        "## Summary\n"
        "Test review.\n"
        "## Findings\n"
        "No findings.\n"
        "## Verdict\n"
        f"{verdict.upper()}\n"
        "## Assumptions\n"
        "None.\n"
        "## Open questions\n"
        "None.\n"
        "## Next consumer brief\n"
        "Proceed.\n"
    )


# ---------------------------------------------------------------------------
# I1: Fixtures availability
# ---------------------------------------------------------------------------

class TestFixtures:
    def test_analysis_report_good_exists(self):
        assert (FIXTURES_DIR / "analysis-report-good.md").exists()

    def test_analysis_report_bad_missing_ac_exists(self):
        assert (FIXTURES_DIR / "analysis-report-bad-missing-ac.md").exists()

    def test_analysis_report_bad_placeholder_ac_exists(self):
        assert (FIXTURES_DIR / "analysis-report-bad-placeholder-ac.md").exists()

    def test_impl_report_good_exists(self):
        assert (FIXTURES_DIR / "impl-report-good.md").exists()

    def test_impl_report_lying_exists(self):
        assert (FIXTURES_DIR / "impl-report-lying.md").exists()

    def test_review_report_pass_exists(self):
        assert (FIXTURES_DIR / "review-report-pass.md").exists()

    def test_review_report_needs_fix_exists(self):
        assert (FIXTURES_DIR / "review-report-needs-fix.md").exists()

    def test_review_report_fail_exists(self):
        assert (FIXTURES_DIR / "review-report-fail.md").exists()

    def test_readme_exists(self):
        assert (FIXTURES_DIR / "README.md").exists()

    def test_check_registry_has_all_types(self):
        expected = {
            "schema", "acceptance", "traceability",
            "build", "lint", "types", "test",
            "diff_vs_acceptance", "g-review",
        }
        assert expected.issubset(set(CHECK_REGISTRY.keys()))


# ---------------------------------------------------------------------------
# I2: GateResult, runGate spine, StateWrite
# ---------------------------------------------------------------------------

class TestGateResult:
    def test_valid_decisions(self):
        for d in ("proceed", "needs_fix", "fail", "retry"):
            r = GateResult(decision=d)
            assert r.decision == d

    def test_invalid_decision_raises(self):
        with pytest.raises(ValueError, match="not in"):
            GateResult(decision="escalate")

    def test_to_dict_shape(self):
        r = GateResult(decision="proceed", errors=["e1"], evidence={"k": "v"})
        d = r.to_dict()
        assert d["decision"] == "proceed"
        assert d["errors"] == ["e1"]
        assert d["evidence"] == {"k": "v"}

    def test_needs_fix_is_valid_escalate_is_not(self):
        GateResult(decision="needs_fix")
        with pytest.raises(ValueError):
            GateResult(decision="escalate")

    def test_defaults_empty_lists_and_dict(self):
        r = GateResult(decision="proceed")
        assert r.errors == []
        assert r.evidence == {}


class TestRunGate:
    def test_empty_checks_returns_proceed(self):
        result = runGate({"checks": []}, [])
        assert result.decision == "proceed"

    def test_no_checks_key_returns_proceed(self):
        result = runGate({}, [])
        assert result.decision == "proceed"

    def test_unknown_check_type_returns_fail(self):
        result = runGate({"checks": [{"type": "unknown-check-xyz"}]}, [])
        assert result.decision == "fail"
        assert any("unknown check type" in e for e in result.errors)

    def test_fail_dominates_needs_fix(self, tmp_path):
        review_needs_fix = tmp_path / "review_nf.md"
        review_fail = tmp_path / "review_fail.md"
        review_needs_fix.write_text(_make_review_content("needs_fix"))
        review_fail.write_text(_make_review_content("fail"))
        gate = {
            "checks": [
                {"type": "g-review", "artifact_path": str(review_needs_fix)},
                {"type": "g-review", "artifact_path": str(review_fail)},
            ]
        }
        result = runGate(gate, [])
        assert result.decision == "fail"

    def test_needs_fix_wins_over_proceed(self, tmp_path):
        review_pass = tmp_path / "review_pass.md"
        review_nf = tmp_path / "review_nf.md"
        review_pass.write_text(_make_review_content("pass"))
        review_nf.write_text(_make_review_content("needs_fix"))
        gate = {
            "checks": [
                {"type": "g-review", "artifact_path": str(review_pass)},
                {"type": "g-review", "artifact_path": str(review_nf)},
            ]
        }
        result = runGate(gate, [])
        assert result.decision == "needs_fix"

    def test_retry_short_circuits_remaining_checks(self, tmp_path):
        review_pass = tmp_path / "review_pass.md"
        review_pass.write_text(_make_review_content("pass"))
        gate = {
            "checks": [
                {"type": "g-review", "artifact_path": str(tmp_path / "nonexistent.md")},
                {"type": "g-review", "artifact_path": str(review_pass)},  # should not run
            ]
        }
        result = runGate(gate, [])
        assert result.decision == "retry"

    def test_accumulates_evidence_across_checks(self, tmp_path):
        r1 = tmp_path / "r1.md"
        r2 = tmp_path / "r2.md"
        r1.write_text(_make_review_content("pass"))
        r2.write_text(_make_review_content("pass"))
        gate = {
            "checks": [
                {"type": "g-review", "artifact_path": str(r1)},
                {"type": "lint", "command": "echo ok"},
            ]
        }
        result = runGate(gate, [], space=tmp_path)
        assert "g_review" in result.evidence
        assert "lint" in result.evidence


class TestStateWrite:
    def test_writes_gate_result_to_state_json(self, tmp_path):
        state_file = tmp_path / "state.json"
        result = runGate({"checks": []}, [], gate_id="gate-1", state_path=state_file)
        assert result.decision == "proceed"
        state = json.loads(state_file.read_text())
        assert state["nodes"]["gate-1"]["gate"]["decision"] == "proceed"

    def test_creates_state_json_if_absent(self, tmp_path):
        state_file = tmp_path / "new-state.json"
        assert not state_file.exists()
        runGate({"checks": []}, [], gate_id="g", state_path=state_file)
        assert state_file.exists()

    def test_preserves_existing_nodes(self, tmp_path):
        state_file = tmp_path / "state.json"
        existing = {"nodes": {"other-gate": {"gate": {"decision": "proceed"}}}}
        state_file.write_text(json.dumps(existing))
        runGate({"checks": []}, [], gate_id="gate-2", state_path=state_file)
        state = json.loads(state_file.read_text())
        assert "other-gate" in state["nodes"]
        assert "gate-2" in state["nodes"]

    def test_writes_on_needs_fix(self, tmp_path):
        state_file = tmp_path / "state.json"
        review_path = tmp_path / "review.md"
        review_path.write_text(_make_review_content("needs_fix"))
        gate = {"checks": [{"type": "g-review", "artifact_path": str(review_path)}]}
        runGate(gate, [], gate_id="g", state_path=state_file)
        state = json.loads(state_file.read_text())
        assert state["nodes"]["g"]["gate"]["decision"] == "needs_fix"

    def test_writes_on_fail(self, tmp_path):
        state_file = tmp_path / "state.json"
        review_path = tmp_path / "review.md"
        review_path.write_text(_make_review_content("fail"))
        gate = {"checks": [{"type": "g-review", "artifact_path": str(review_path)}]}
        runGate(gate, [], gate_id="g", state_path=state_file)
        state = json.loads(state_file.read_text())
        assert state["nodes"]["g"]["gate"]["decision"] == "fail"

    def test_no_write_without_gate_id(self, tmp_path):
        state_file = tmp_path / "state.json"
        runGate({"checks": []}, [], state_path=state_file)
        assert not state_file.exists()

    def test_state_json_shape(self, tmp_path):
        state_file = tmp_path / "state.json"
        runGate({"checks": []}, [], gate_id="g1", state_path=state_file)
        state = json.loads(state_file.read_text())
        gate_entry = state["nodes"]["g1"]["gate"]
        assert "decision" in gate_entry
        assert "errors" in gate_entry
        assert "evidence" in gate_entry


# ---------------------------------------------------------------------------
# I3: Schema and Acceptance checks
# ---------------------------------------------------------------------------

class TestSchema:
    def test_good_analysis_report_proceeds(self, tmp_path):
        pipeline_dir = tmp_path / ".cronos" / "pipeline" / "test-feature"
        pipeline_dir.mkdir(parents=True)
        (pipeline_dir / "analysis-report-test-feature.md").write_text(
            _read_fixture("analysis-report-good.md")
        )
        gate = {"checks": [{"type": "schema", "agent": "analysis", "slug": "test-feature"}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "proceed"

    def test_evidence_contains_schema_fields(self, tmp_path):
        pipeline_dir = tmp_path / ".cronos" / "pipeline" / "test-feature"
        pipeline_dir.mkdir(parents=True)
        (pipeline_dir / "analysis-report-test-feature.md").write_text(
            _read_fixture("analysis-report-good.md")
        )
        gate = {"checks": [{"type": "schema", "agent": "analysis", "slug": "test-feature"}]}
        result = runGate(gate, [], space=tmp_path)
        ev = result.evidence["schema"]
        assert "passed" in ev
        assert "errors" in ev
        assert "warnings" in ev

    def test_missing_artifact_returns_retry(self, tmp_path):
        gate = {"checks": [{"type": "schema", "agent": "analysis", "slug": "no-such-slug"}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "retry"

    def test_malformed_artifact_fails_or_retries(self, tmp_path):
        pipeline_dir = tmp_path / ".cronos" / "pipeline" / "bad"
        pipeline_dir.mkdir(parents=True)
        (pipeline_dir / "analysis-report-bad.md").write_text("no frontmatter")
        gate = {"checks": [{"type": "schema", "agent": "analysis", "slug": "bad"}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision in ("fail", "retry")

    def test_schema_check_without_space_fails(self):
        gate = {"checks": [{"type": "schema", "agent": "analysis", "slug": "s"}]}
        result = runGate(gate, [], space=None)
        assert result.decision == "fail"

    def test_schema_does_not_reimpl_verify_logic(self, tmp_path):
        """schema check calls verify() and wraps — does not duplicate logic."""
        pipeline_dir = tmp_path / ".cronos" / "pipeline" / "test-feature"
        pipeline_dir.mkdir(parents=True)
        # Artifact with wrong cc_version → should produce errors from verify
        bad_content = _read_fixture("analysis-report-good.md").replace(
            "cc_version: '1.0'", "cc_version: '99.0'"
        )
        (pipeline_dir / "analysis-report-test-feature.md").write_text(bad_content)
        gate = {"checks": [{"type": "schema", "agent": "analysis", "slug": "test-feature"}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "fail"
        assert len(result.evidence["schema"]["errors"]) > 0


class TestAcceptance:
    def test_good_report_proceeds(self, tmp_path):
        path = tmp_path / "analysis.md"
        path.write_text(_read_fixture("analysis-report-good.md"))
        gate = {"checks": [{"type": "acceptance", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert result.decision == "proceed"

    def test_missing_ac_fails(self, tmp_path):
        path = tmp_path / "analysis.md"
        path.write_text(_read_fixture("analysis-report-bad-missing-ac.md"))
        gate = {"checks": [{"type": "acceptance", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert result.decision == "fail"
        assert "acceptance" in result.evidence

    def test_placeholder_ac_fails(self, tmp_path):
        path = tmp_path / "analysis.md"
        path.write_text(_read_fixture("analysis-report-bad-placeholder-ac.md"))
        gate = {"checks": [{"type": "acceptance", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert result.decision == "fail"

    def test_evidence_includes_ac_count(self, tmp_path):
        path = tmp_path / "analysis.md"
        path.write_text(_read_fixture("analysis-report-good.md"))
        gate = {"checks": [{"type": "acceptance", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert result.evidence["acceptance"]["ac_count"] > 0

    def test_evidence_includes_failing_req_ids(self, tmp_path):
        path = tmp_path / "analysis.md"
        path.write_text(_read_fixture("analysis-report-bad-missing-ac.md"))
        gate = {"checks": [{"type": "acceptance", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert "R2" in result.evidence["acceptance"]["failing_req_ids"]

    def test_missing_file_returns_retry(self, tmp_path):
        gate = {"checks": [{"type": "acceptance", "artifact_path": str(tmp_path / "x.md")}]}
        result = runGate(gate, [])
        assert result.decision == "retry"

    def test_artifact_without_traceability_proceeds(self, tmp_path):
        path = tmp_path / "impl.md"
        path.write_text(_read_fixture("impl-report-good.md"))
        gate = {"checks": [{"type": "acceptance", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert result.decision == "proceed"


# ---------------------------------------------------------------------------
# I4: Traceability check
# ---------------------------------------------------------------------------

class TestTraceability:
    def test_good_report_proceeds_with_required_ids(self, tmp_path):
        path = tmp_path / "analysis.md"
        path.write_text(_read_fixture("analysis-report-good.md"))
        gate = {"checks": [
            {"type": "traceability", "artifact_path": str(path), "required_ids": ["R1", "R2"]}
        ]}
        result = runGate(gate, [])
        assert result.decision == "proceed"
        ev = result.evidence["traceability"]
        assert "R1" in ev["resolved_ids"]
        assert "R2" in ev["resolved_ids"]
        assert ev["missing_ids"] == []

    def test_missing_required_id_fails(self, tmp_path):
        path = tmp_path / "analysis.md"
        path.write_text(_read_fixture("analysis-report-good.md"))
        gate = {"checks": [
            {"type": "traceability", "artifact_path": str(path), "required_ids": ["R99"]}
        ]}
        result = runGate(gate, [])
        assert result.decision == "fail"
        assert "R99" in result.evidence["traceability"]["missing_ids"]

    def test_no_required_ids_proceeds(self, tmp_path):
        path = tmp_path / "analysis.md"
        path.write_text(_read_fixture("analysis-report-good.md"))
        gate = {"checks": [{"type": "traceability", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert result.decision == "proceed"

    def test_evidence_shows_resolved_and_missing(self, tmp_path):
        path = tmp_path / "analysis.md"
        path.write_text(_read_fixture("analysis-report-good.md"))
        gate = {"checks": [
            {"type": "traceability", "artifact_path": str(path), "required_ids": ["R1", "R99"]}
        ]}
        result = runGate(gate, [])
        ev = result.evidence["traceability"]
        assert "R1" in ev["resolved_ids"]
        assert "R99" in ev["missing_ids"]

    def test_missing_file_returns_retry(self, tmp_path):
        gate = {"checks": [
            {"type": "traceability", "artifact_path": str(tmp_path / "x.md")}
        ]}
        result = runGate(gate, [])
        assert result.decision == "retry"

    def test_artifact_without_traceability_with_required_ids_fails(self, tmp_path):
        path = tmp_path / "review.md"
        path.write_text(_read_fixture("review-report-pass.md"))
        gate = {"checks": [
            {"type": "traceability", "artifact_path": str(path), "required_ids": ["R1"]}
        ]}
        result = runGate(gate, [])
        assert result.decision == "fail"


# ---------------------------------------------------------------------------
# I5: Build, Lint, Types checks
# ---------------------------------------------------------------------------

class TestBuild:
    def test_good_impl_proceeds(self, tmp_path):
        path = tmp_path / "impl.md"
        path.write_text(_read_fixture("impl-report-good.md"))
        gate = {"checks": [{"type": "build", "artifact_path": str(path)}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "proceed"
        assert result.evidence["build"]["exit_code"] == 0

    def test_lying_impl_returns_needs_fix(self, tmp_path):
        """validation_command_passed: true but actual command exits non-zero → needs_fix."""
        path = tmp_path / "impl.md"
        path.write_text(_read_fixture("impl-report-lying.md"))
        gate = {"checks": [{"type": "build", "artifact_path": str(path)}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "needs_fix"
        assert result.evidence["build"]["exit_code"] != 0

    def test_missing_validation_command_returns_fail(self, tmp_path):
        path = tmp_path / "impl.md"
        path.write_text("---\ncc_version: '1.0'\n---\n## body\n")
        gate = {"checks": [{"type": "build", "artifact_path": str(path)}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "fail"

    def test_placeholder_validation_command_returns_fail(self, tmp_path):
        path = tmp_path / "impl.md"
        path.write_text("---\ncc_version: '1.0'\nvalidation_command: tbd\n---\n## body\n")
        gate = {"checks": [{"type": "build", "artifact_path": str(path)}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "fail"

    def test_evidence_has_required_keys(self, tmp_path):
        path = tmp_path / "impl.md"
        path.write_text(_read_fixture("impl-report-good.md"))
        gate = {"checks": [{"type": "build", "artifact_path": str(path)}]}
        result = runGate(gate, [], space=tmp_path)
        ev = result.evidence["build"]
        assert "exit_code" in ev
        assert "stdout_tail" in ev
        assert "stderr_tail" in ev
        assert "command" in ev

    def test_missing_artifact_returns_retry(self, tmp_path):
        gate = {"checks": [{"type": "build", "artifact_path": str(tmp_path / "x.md")}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "retry"

    def test_ignores_self_reported_passed_flag(self, tmp_path):
        """The critical R6 assertion: real exit code matters, not validation_command_passed."""
        path = tmp_path / "impl.md"
        path.write_text(_read_fixture("impl-report-lying.md"))
        gate = {"checks": [{"type": "build", "artifact_path": str(path)}]}
        result = runGate(gate, [], space=tmp_path)
        # Must NOT be proceed even though validation_command_passed: true
        assert result.decision != "proceed"
        assert result.decision == "needs_fix"


class TestLint:
    def test_exit_zero_proceeds(self, tmp_path):
        gate = {"checks": [{"type": "lint", "command": "echo no violations"}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "proceed"

    def test_nonzero_exit_returns_needs_fix(self, tmp_path):
        gate = {"checks": [{"type": "lint", "command": "exit 1"}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "needs_fix"

    def test_evidence_has_exit_code_and_command(self, tmp_path):
        gate = {"checks": [{"type": "lint", "command": "echo ok"}]}
        result = runGate(gate, [], space=tmp_path)
        ev = result.evidence["lint"]
        assert "exit_code" in ev
        assert "command" in ev
        assert ev["exit_code"] == 0

    def test_uses_command_from_check_spec(self, tmp_path):
        gate = {"checks": [{"type": "lint", "command": "echo custom-lint"}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.evidence["lint"]["command"] == "echo custom-lint"


class TestTypes:
    def test_exit_zero_proceeds(self, tmp_path):
        gate = {"checks": [{"type": "types", "command": "echo no type errors"}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "proceed"

    def test_nonzero_exit_returns_needs_fix(self, tmp_path):
        gate = {"checks": [{"type": "types", "command": "exit 2"}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "needs_fix"

    def test_evidence_has_exit_code_and_command(self, tmp_path):
        gate = {"checks": [{"type": "types", "command": "echo ok"}]}
        result = runGate(gate, [], space=tmp_path)
        ev = result.evidence["types"]
        assert "exit_code" in ev
        assert "command" in ev
        assert ev["exit_code"] == 0

    def test_evidence_has_error_count_field(self, tmp_path):
        gate = {"checks": [{"type": "types", "command": "echo ok"}]}
        result = runGate(gate, [], space=tmp_path)
        assert "error_count" in result.evidence["types"]


# ---------------------------------------------------------------------------
# I6: Test outcome check
# ---------------------------------------------------------------------------

class TestTestOutcome:
    def test_passing_suite_proceeds(self, tmp_path):
        gate = {"checks": [{"type": "test", "command": "echo '1 passed'", "coverage_floor": 0}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "proceed"

    def test_nonzero_exit_returns_needs_fix(self, tmp_path):
        gate = {"checks": [{"type": "test", "command": "exit 1", "coverage_floor": 0}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "needs_fix"

    def test_coverage_below_floor_returns_needs_fix(self, tmp_path):
        cmd = "printf 'TOTAL                100     50    50%%\\n'"
        gate = {"checks": [{"type": "test", "command": cmd, "coverage_floor": 80}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "needs_fix"
        assert result.evidence["test"]["coverage_pct"] == 50.0

    def test_coverage_above_floor_proceeds(self, tmp_path):
        cmd = "printf 'TOTAL                100     10    90%%\\n'"
        gate = {"checks": [{"type": "test", "command": cmd, "coverage_floor": 80}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "proceed"
        assert result.evidence["test"]["coverage_pct"] == 90.0

    def test_no_coverage_line_gates_on_exit_code_only(self, tmp_path):
        """When no coverage line is found, coverage_pct=null and gate uses exit code only."""
        gate = {"checks": [{"type": "test", "command": "echo '5 passed'", "coverage_floor": 99}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "proceed"
        assert result.evidence["test"]["coverage_pct"] is None

    def test_evidence_has_all_required_fields(self, tmp_path):
        gate = {"checks": [{"type": "test", "command": "echo ok", "coverage_floor": 0}]}
        result = runGate(gate, [], space=tmp_path)
        ev = result.evidence["test"]
        for key in ("exit_code", "coverage_pct", "coverage_floor", "command"):
            assert key in ev, f"missing key: {key}"

    def test_self_reported_pass_ignored_on_failing_build(self, tmp_path):
        """Gate reads real exit code, not what impl says."""
        gate = {"checks": [{"type": "test", "command": "exit 1", "coverage_floor": 0}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "needs_fix"


# ---------------------------------------------------------------------------
# I7: DiffVsAcceptance check
# ---------------------------------------------------------------------------

class TestDiffVsAcceptance:
    def test_proceeds_when_no_analysis_path(self, tmp_path):
        gate = {"checks": [{"type": "diff_vs_acceptance"}]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "proceed"

    def test_evidence_includes_limits(self, tmp_path):
        gate = {"checks": [{"type": "diff_vs_acceptance"}]}
        result = runGate(gate, [], space=tmp_path)
        limits = result.evidence["diff_vs_acceptance"]["LIMITS"]
        assert isinstance(limits, list)
        assert any("keyword" in l.lower() for l in limits)

    def test_threshold_zero_always_proceeds(self, tmp_path):
        analysis_path = tmp_path / "analysis.md"
        analysis_path.write_text(_read_fixture("analysis-report-good.md"))
        gate = {"checks": [
            {"type": "diff_vs_acceptance", "analysis_path": str(analysis_path), "threshold": 0.0}
        ]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "proceed"

    def test_coverage_ratio_in_evidence(self, tmp_path):
        analysis_path = tmp_path / "analysis.md"
        analysis_path.write_text(_read_fixture("analysis-report-good.md"))
        gate = {"checks": [
            {"type": "diff_vs_acceptance", "analysis_path": str(analysis_path), "threshold": 0.0}
        ]}
        result = runGate(gate, [], space=tmp_path)
        ev = result.evidence["diff_vs_acceptance"]
        assert "coverage_ratio" in ev

    def test_covered_and_uncovered_ids_in_evidence(self, tmp_path):
        analysis_path = tmp_path / "analysis.md"
        analysis_path.write_text(_read_fixture("analysis-report-good.md"))
        gate = {"checks": [
            {"type": "diff_vs_acceptance", "analysis_path": str(analysis_path), "threshold": 0.0}
        ]}
        result = runGate(gate, [], space=tmp_path)
        ev = result.evidence["diff_vs_acceptance"]
        assert "covered_ac_ids" in ev
        assert "uncovered_ac_ids" in ev

    def test_needs_fix_when_below_threshold(self, tmp_path):
        """With threshold=1.0 and no diff coverage, should return needs_fix."""
        analysis_path = tmp_path / "analysis.md"
        analysis_path.write_text(_read_fixture("analysis-report-good.md"))
        gate = {"checks": [
            {"type": "diff_vs_acceptance", "analysis_path": str(analysis_path), "threshold": 1.0}
        ]}
        result = runGate(gate, [], space=tmp_path)
        # Without any real diff, coverage_ratio=0.0 < 1.0
        assert result.decision == "needs_fix"

    def test_advisory_when_no_traceability_source(self, tmp_path):
        """When analysis report has no traceability, advisory proceed."""
        analysis_path = tmp_path / "analysis.md"
        analysis_path.write_text(_read_fixture("review-report-pass.md"))  # no traceability
        gate = {"checks": [
            {"type": "diff_vs_acceptance", "analysis_path": str(analysis_path), "threshold": 1.0}
        ]}
        result = runGate(gate, [], space=tmp_path)
        assert result.decision == "proceed"


# ---------------------------------------------------------------------------
# I8: GReview check
# ---------------------------------------------------------------------------

class TestGReview:
    def test_pass_verdict_proceeds(self, tmp_path):
        path = tmp_path / "review.md"
        path.write_text(_read_fixture("review-report-pass.md"))
        gate = {"checks": [{"type": "g-review", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert result.decision == "proceed"

    def test_needs_fix_verdict_returns_needs_fix(self, tmp_path):
        path = tmp_path / "review.md"
        path.write_text(_read_fixture("review-report-needs-fix.md"))
        gate = {"checks": [{"type": "g-review", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert result.decision == "needs_fix"

    def test_fail_verdict_returns_fail(self, tmp_path):
        path = tmp_path / "review.md"
        path.write_text(_read_fixture("review-report-fail.md"))
        gate = {"checks": [{"type": "g-review", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert result.decision == "fail"

    def test_needs_fix_not_mapped_to_fail(self, tmp_path):
        """Critical: needs_fix must NOT become fail."""
        path = tmp_path / "review.md"
        path.write_text(_read_fixture("review-report-needs-fix.md"))
        gate = {"checks": [{"type": "g-review", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert result.decision == "needs_fix"
        assert result.decision != "fail"

    def test_evidence_has_verdict_and_blocking_count(self, tmp_path):
        path = tmp_path / "review.md"
        path.write_text(_read_fixture("review-report-needs-fix.md"))
        gate = {"checks": [{"type": "g-review", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        ev = result.evidence["g_review"]
        assert ev["verdict"] == "needs_fix"
        assert isinstance(ev["blocking_finding_count"], int)
        assert ev["blocking_finding_count"] == 1

    def test_missing_artifact_returns_retry(self, tmp_path):
        gate = {"checks": [{"type": "g-review", "artifact_path": str(tmp_path / "x.md")}]}
        result = runGate(gate, [])
        assert result.decision == "retry"

    def test_invalid_verdict_returns_fail(self, tmp_path):
        path = tmp_path / "review.md"
        path.write_text(
            "---\ncc_version: '1.0'\nverdict: invalid-verdict\nfindings: []\n---\n## body\n"
        )
        gate = {"checks": [{"type": "g-review", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert result.decision == "fail"

    def test_pass_with_no_findings_proceeds(self, tmp_path):
        path = tmp_path / "review.md"
        path.write_text(_make_review_content("pass", blocking=False))
        gate = {"checks": [{"type": "g-review", "artifact_path": str(path)}]}
        result = runGate(gate, [])
        assert result.decision == "proceed"
        assert result.evidence["g_review"]["blocking_finding_count"] == 0
