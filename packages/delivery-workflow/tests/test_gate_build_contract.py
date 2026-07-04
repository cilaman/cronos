"""Tests for the validation_command contract between the implementation-class
schema (lib/verify.py) and the build gate (lib/gate.py).

Regression coverage for the live g-build stall: the gate re-executes
header["validation_command"] (R6 — never trust the self-reported
validation_command_passed flag), but the schema neither required nor defined
that header field, so a perfectly compliant impl-report could not pass g-build.
These tests pin that (a) the schema now requires a concrete, non-placeholder
validation_command, (b) both the single-iteration and consolidated
multi-iteration report shapes are accepted, and (c) the build gate's
missing-key error is self-teaching (it reaches the re-run agent via scope).
"""
from __future__ import annotations

import textwrap

import yaml

from delivery_workflow.lib.gate import runGate
from delivery_workflow.lib.verify import verify


_BODY = textwrap.dedent("""\

    ## Summary

    Implemented X; validation_command passed.

    ## Files changed

    - backend/app/main.py (+10/-2)

    ## Out-of-scope findings

    None.

    ## Assumptions

    None.

    ## Open questions

    None.

    ## Next consumer brief

    Proceed to test.
""")


def _impl_artifact(
    tmp_path,
    *,
    slug="my-goal",
    validation_command="cd backend && python -m pytest tests/test_x.py -q",
    iteration_id="I1",
    iterations_completed=None,
    validation_command_passed=True,
    status="done",
    rel=".cronos/delivery/my-goal/impl-report.md",
):
    """Write a full implementation-class artifact and return its absolute path.

    Any header field can be overridden; pass ``None`` to omit an optional field
    entirely (used to exercise the missing-validation_command path).
    """
    header = {
        "cc_version": "1.0",
        "agent": "implementor",
        "slug": slug,
        "phase": "impl",
        "status": status,
        "confidence": 0.9,
        "inputs_used": ["backend/app/main.py"],
        "outputs_produced": [rel],
        "blockers": [],
        "next_consumer": "test",
        "files_changed": ["backend/app/main.py"],
        "validation_command_passed": validation_command_passed,
        "metrics": {
            "tool_calls": 5,
            "files_read": 1,
            "diff_lines_added": 10,
            "diff_lines_removed": 2,
        },
    }
    if validation_command is not None:
        header["validation_command"] = validation_command
    if iteration_id is not None:
        header["iteration_id"] = iteration_id
    if iterations_completed is not None:
        header["iterations_completed"] = iterations_completed

    text = "---\n" + yaml.safe_dump(header, sort_keys=False) + "---\n" + _BODY
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Schema: validation_command is now required and content-checked
# ---------------------------------------------------------------------------


class TestSchemaValidationCommand:
    def test_header_with_validation_command_proceeds(self, tmp_path):
        path = _impl_artifact(tmp_path)
        result = verify("implementation", "my-goal", tmp_path, artifact_path=str(path))
        assert result.outcome == "proceed", result.errors

    def test_header_missing_validation_command_fails(self, tmp_path):
        path = _impl_artifact(tmp_path, validation_command=None)
        result = verify("implementation", "my-goal", tmp_path, artifact_path=str(path))
        assert result.outcome == "fail"
        assert any("validation_command" in e for e in result.errors), result.errors

    def test_header_placeholder_validation_command_fails(self, tmp_path):
        path = _impl_artifact(tmp_path, validation_command="run tests")
        result = verify("implementation", "my-goal", tmp_path, artifact_path=str(path))
        assert result.outcome == "fail"
        assert any(
            "R-impl-7" in e and "placeholder" in e for e in result.errors
        ), result.errors

    def test_header_empty_validation_command_fails(self, tmp_path):
        path = _impl_artifact(tmp_path, validation_command="   ")
        result = verify("implementation", "my-goal", tmp_path, artifact_path=str(path))
        assert result.outcome == "fail"
        assert any("R-impl-7" in e for e in result.errors), result.errors


# ---------------------------------------------------------------------------
# Schema: iteration identity — single iteration_id OR consolidated shape
# ---------------------------------------------------------------------------


class TestIterationIdentity:
    def test_single_iteration_id_proceeds(self, tmp_path):
        path = _impl_artifact(tmp_path, iteration_id="I1", iterations_completed=None)
        result = verify("implementation", "my-goal", tmp_path, artifact_path=str(path))
        assert result.outcome == "proceed", result.errors

    def test_consolidated_report_without_iteration_id_proceeds(self, tmp_path):
        path = _impl_artifact(
            tmp_path, iteration_id=None, iterations_completed=["I1", "I2", "I3"]
        )
        result = verify("implementation", "my-goal", tmp_path, artifact_path=str(path))
        assert result.outcome == "proceed", result.errors

    def test_no_iteration_identity_fails(self, tmp_path):
        path = _impl_artifact(tmp_path, iteration_id=None, iterations_completed=None)
        result = verify("implementation", "my-goal", tmp_path, artifact_path=str(path))
        assert result.outcome == "fail"
        assert any("R-impl-8" in e for e in result.errors), result.errors

    def test_malformed_iterations_completed_entry_fails(self, tmp_path):
        path = _impl_artifact(
            tmp_path, iteration_id=None, iterations_completed=["I1", "i2"]
        )
        result = verify("implementation", "my-goal", tmp_path, artifact_path=str(path))
        assert result.outcome == "fail"
        assert any("R-impl-8" in e for e in result.errors), result.errors


# ---------------------------------------------------------------------------
# Gate: build check re-executes validation_command; missing-key is self-teaching
# ---------------------------------------------------------------------------


class TestBuildGate:
    def test_missing_validation_command_is_self_teaching(self, tmp_path):
        path = _impl_artifact(tmp_path, validation_command=None)
        gate = {"checks": [{"type": "build", "artifact_path": str(path)}]}
        result = runGate(gate, [str(path)], space=tmp_path)
        assert result.decision == "fail"
        # The error must name the fix and where to find it — it reaches the
        # re-run agent through runner scope (blind-retry defect).
        assert any(
            "validation_command" in e
            and "implement skill" in e
            and "cannot re-execute" in e
            for e in result.errors
        ), result.errors

    def test_placeholder_validation_command_fails(self, tmp_path):
        path = _impl_artifact(tmp_path, validation_command="pending")
        gate = {"checks": [{"type": "build", "artifact_path": str(path)}]}
        result = runGate(gate, [str(path)], space=tmp_path)
        assert result.decision == "fail"
        assert any("placeholder" in e for e in result.errors), result.errors

    def test_present_command_is_reexecuted_and_proceeds(self, tmp_path):
        # `true` exits 0 from the space root → gate re-executes and proceeds.
        path = _impl_artifact(tmp_path, validation_command="true")
        gate = {"checks": [{"type": "build", "artifact_path": str(path)}]}
        result = runGate(gate, [str(path)], space=tmp_path)
        assert result.decision == "proceed", result.errors
        assert result.evidence["build"]["exit_code"] == 0
