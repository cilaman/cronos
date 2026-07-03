"""Tests for lib.security.evaluate_security — portable security evaluator.

All tests use hermetic fixture scanners (no network, no real CVE database).
The DD-002 regression test verifies that scanners emitting >2 KB of JSON are
parsed correctly (not fail-opened by a 2 KB stdout tail truncation).
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

from delivery_workflow.lib.security import evaluate_security

# Reuse the backend gate security fixtures — same scanners, same planted sentinel
FIXTURES = (
    Path(__file__).parent.parent.parent.parent
    / "backend"
    / "tests"
    / "fixtures"
    / "gate"
    / "security"
)
FAKE_SECRETS = FIXTURES / "fake_secrets_scanner.py"
FAKE_DEPS = FIXTURES / "fake_deps_scanner.py"
PY = sys.executable


# ---------------------------------------------------------------------------
# Scanner hit paths
# ---------------------------------------------------------------------------


def test_secrets_scanner_hit_is_not_proceed():
    """Planted sentinel → decision != proceed, class=code."""
    check = {
        "type": "security",
        "scanners": {"secrets": f"{PY} {FAKE_SECRETS}"},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "fail",
    }
    decision, errors, evidence = evaluate_security(check, [], FIXTURES)

    assert decision != "proceed", f"Expected non-proceed, got {decision!r}; errors={errors}"
    sec = evidence["security"]
    assert sec["has_fail_on_hit"] is True
    assert sec["effective_finding_class"] == "code"
    assert sec["scanner_results"]["secrets"]["status"] == "hit"


def test_deps_scanner_hit_is_not_proceed():
    """Vulnerable pin in requirements.txt → decision != proceed, class=dependency."""
    check = {
        "type": "security",
        "scanners": {"deps_python": f"{PY} {FAKE_DEPS}"},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "fail",
    }
    decision, errors, evidence = evaluate_security(check, [], FIXTURES)

    assert decision != "proceed", f"Expected non-proceed, got {decision!r}; errors={errors}"
    sec = evidence["security"]
    assert sec["has_fail_on_hit"] is True
    assert sec["effective_finding_class"] == "dependency"
    assert sec["scanner_results"]["deps_python"]["status"] == "hit"


# ---------------------------------------------------------------------------
# Missing scanner policy
# ---------------------------------------------------------------------------


def test_missing_scanner_with_fail_policy_is_not_proceed():
    """Absent binary + on_missing_scanner=fail → decision != proceed."""
    check = {
        "type": "security",
        "scanners": {"sast": "cronos-no-such-scanner-xyz --json ."},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "fail",
    }
    decision, errors, evidence = evaluate_security(check, [], FIXTURES)

    assert decision != "proceed", f"Expected non-proceed, got {decision!r}"
    assert evidence["security"]["has_missing_fail"] is True


def test_missing_scanner_with_skip_policy_does_not_force_needs_fix():
    """Absent binary + on_missing_scanner=skip alone does not force needs_fix."""
    check = {
        "type": "security",
        "scanners": {"sast": "cronos-no-such-scanner-xyz --json ."},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "skip",
    }
    decision, errors, evidence = evaluate_security(check, [], FIXTURES)

    assert decision == "proceed", (
        f"Expected proceed when only a skipped-missing scanner, got {decision!r}"
    )
    assert evidence["security"]["has_missing_fail"] is False
    assert evidence["security"]["scanner_results"]["sast"]["status"] == "missing"


def test_missing_scanner_defaults_to_skip_when_policy_omitted():
    """P3: with no on_missing_scanner set, an un-shipped scanner is skipped, not
    failed — a not-installed scanner must not hard-fail an otherwise-green pipeline."""
    check = {
        "type": "security",
        "scanners": {"sast": "cronos-no-such-scanner-xyz --json ."},
        "fail_on": ["critical", "high"],
        # on_missing_scanner intentionally omitted → default 'skip'.
    }
    decision, errors, evidence = evaluate_security(check, [], FIXTURES)

    assert decision == "proceed", f"Expected proceed by default, got {decision!r}"
    assert evidence["security"]["has_missing_fail"] is False


def test_build_subprocess_env_puts_interpreter_bin_on_path():
    """P3: gate/security subprocesses get the running interpreter's bin on PATH so
    pytest/scanners resolve the same way they do for the interactive agent shell."""
    import os
    import sys

    from delivery_workflow.lib.security import build_subprocess_env

    env = build_subprocess_env()
    bindir = os.path.dirname(sys.executable)
    assert env["PATH"].split(os.pathsep)[0] == bindir


# ---------------------------------------------------------------------------
# Infrastructure crash → retry
# ---------------------------------------------------------------------------


def test_scanner_infra_crash_returns_retry():
    """Scanner exits non-zero with non-JSON output → retry (infra crash)."""
    crash_cmd = f'{PY} -c "import sys; print(\'internal error\'); sys.exit(2)"'
    check = {
        "type": "security",
        "scanners": {"sast": crash_cmd},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "fail",
    }
    decision, errors, evidence = evaluate_security(check, [], FIXTURES)

    assert decision == "retry", f"Expected retry on infra crash, got {decision!r}"
    assert evidence["security"]["infra_crash"] is True


# ---------------------------------------------------------------------------
# Agent verdict paths
# ---------------------------------------------------------------------------


def test_agent_needs_fix_with_clean_scanners_is_needs_fix(tmp_path: Path):
    """Agent verdict=needs_fix + clean scanners → needs_fix."""
    artifact = tmp_path / "security-review.md"
    artifact.write_text(
        textwrap.dedent(
            """\
            ---
            verdict: needs_fix
            finding_class: design
            findings:
              - id: S1
                severity: high
                class: design
                blocking: true
                owasp: A04
                cwe: CWE-657
                evidence: auth boundary is misplaced
            ---

            # Security Review
            Auth boundary flaw found.
            """
        )
    )
    check = {
        "type": "security",
        "artifact_path": str(artifact),
        "scanners": {},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "fail",
    }
    decision, errors, evidence = evaluate_security(check, [str(artifact)], tmp_path)

    assert decision == "needs_fix", f"Expected needs_fix from agent verdict, got {decision!r}"
    sec = evidence["security"]
    assert sec["agent_verdict"] == "needs_fix"
    assert sec["effective_finding_class"] == "design"


def test_agent_pass_with_clean_scanners_is_proceed(tmp_path: Path):
    """Agent verdict=pass + clean scanners → proceed."""
    artifact = tmp_path / "security-review.md"
    artifact.write_text(
        textwrap.dedent(
            """\
            ---
            verdict: pass
            finding_class: code
            findings: []
            ---

            # Security Review
            No findings.
            """
        )
    )
    check = {
        "type": "security",
        "artifact_path": str(artifact),
        "scanners": {},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "fail",
    }
    decision, errors, evidence = evaluate_security(check, [str(artifact)], tmp_path)

    assert decision == "proceed", f"Expected proceed, got {decision!r}; errors={errors}"


def test_agent_fail_verdict_returns_fail(tmp_path: Path):
    """Agent verdict=fail → gate decision=fail."""
    artifact = tmp_path / "security-review.md"
    artifact.write_text(
        textwrap.dedent(
            """\
            ---
            verdict: fail
            finding_class: design
            findings:
              - id: S1
                severity: critical
                class: design
                blocking: true
                evidence: critical auth bypass
            ---

            # Security Review
            Critical finding.
            """
        )
    )
    check = {
        "type": "security",
        "artifact_path": str(artifact),
        "scanners": {},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "fail",
    }
    decision, errors, evidence = evaluate_security(check, [str(artifact)], tmp_path)

    assert decision == "fail", f"Expected fail, got {decision!r}"


# ---------------------------------------------------------------------------
# DD-002 regression: >2 KB JSON with fail_on severity must NOT be scored clean
# ---------------------------------------------------------------------------


def test_large_json_scanner_output_is_parsed_not_truncated(tmp_path: Path):
    """Scanner emitting >2 KB of JSON with a HIGH finding must yield needs_fix.

    This guards against the fail-open where gate._run_command's 2 KB tail
    truncated a real scanner's JSON → json.loads failed → parsed=None → clean.
    lib/security.py captures full stdout so this cannot happen.
    """
    # Build a JSON array where the HIGH finding is past the 2 KB mark
    padding = [
        {"severity": "info", "description": f"padding finding {i}"}
        for i in range(50)
    ]
    high_finding = {"severity": "high", "description": "real vuln at the end"}
    payload = json.dumps(padding + [high_finding])
    # Verify payload is actually >2 KB
    assert len(payload) > 2000, "Payload must exceed 2 KB to exercise the fix"

    # Write the scanner to a temp script to avoid shell-quoting issues with JSON
    scanner_script = tmp_path / "big_scanner.py"
    scanner_script.write_text(
        f"import sys\nprint({payload!r})\nsys.exit(1)\n"
    )
    check = {
        "type": "security",
        "scanners": {"sast": f"{PY} {scanner_script}"},
        "fail_on": ["high", "critical"],
        "on_missing_scanner": "fail",
    }
    decision, errors, evidence = evaluate_security(check, [], tmp_path)

    assert decision != "proceed", (
        f"Large-JSON scanner with HIGH finding must not be scored clean; got {decision!r}"
    )
    sec = evidence["security"]
    assert sec["has_fail_on_hit"] is True, "HIGH hit must be recorded in evidence"
    assert sec["scanner_results"]["sast"]["status"] == "hit"
