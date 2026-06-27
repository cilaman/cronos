"""Real-subprocess gate tests for _check_security (REQ-006).

No mocking of _run_command or subprocess.run.  Uses hermetic detector scripts
in tests/fixtures/gate/security/ — committed, deterministic, offline.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from app.pipeline.gate import _check_security

FIXTURES = Path(__file__).parent / "fixtures" / "gate" / "security"
FAKE_SECRETS = FIXTURES / "fake_secrets_scanner.py"
FAKE_DEPS = FIXTURES / "fake_deps_scanner.py"

PY = sys.executable  # the same Python that's running the test suite


# ---------------------------------------------------------------------------
# REQ-006 AC1/AC2 — real-subprocess scanner hits (secret + dependency)
# ---------------------------------------------------------------------------


def test_secrets_scanner_hit_is_not_proceed():
    """Fake secrets scanner finds planted sentinel → decision != proceed, class=code."""
    check = {
        "type": "security",
        "scanners": {"secrets": f"{PY} {FAKE_SECRETS}"},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "fail",
    }
    decision, errors, evidence = _check_security(check, [], FIXTURES)

    assert decision != "proceed", f"Expected non-proceed, got {decision!r}; errors={errors}"
    sec = evidence["security"]
    assert sec["has_fail_on_hit"] is True
    assert sec["effective_finding_class"] == "code"
    assert sec["scanner_results"]["secrets"]["status"] == "hit"


def test_deps_scanner_hit_is_not_proceed():
    """Fake deps scanner finds vulnerable pin → decision != proceed, class=dependency."""
    check = {
        "type": "security",
        "scanners": {"deps_python": f"{PY} {FAKE_DEPS}"},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "fail",
    }
    decision, errors, evidence = _check_security(check, [], FIXTURES)

    assert decision != "proceed", f"Expected non-proceed, got {decision!r}; errors={errors}"
    sec = evidence["security"]
    assert sec["has_fail_on_hit"] is True
    assert sec["effective_finding_class"] == "dependency"
    assert sec["scanner_results"]["deps_python"]["status"] == "hit"


# ---------------------------------------------------------------------------
# REQ-006 AC3 / REQ-004 AC2 — missing scanner policy
# ---------------------------------------------------------------------------


def test_missing_scanner_with_fail_policy_is_not_proceed():
    """Absent binary + on_missing_scanner=fail → decision != proceed."""
    check = {
        "type": "security",
        "scanners": {"sast": "cronos-no-such-scanner-xyz --json ."},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "fail",
    }
    decision, errors, evidence = _check_security(check, [], FIXTURES)

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
    decision, errors, evidence = _check_security(check, [], FIXTURES)

    # With skip, a missing scanner does NOT by itself make the decision needs_fix
    assert decision == "proceed", (
        f"Expected proceed when only a skipped-missing scanner, got {decision!r}"
    )
    assert evidence["security"]["has_missing_fail"] is False
    # But the missing scanner is still recorded in evidence
    assert evidence["security"]["scanner_results"]["sast"]["status"] == "missing"


# ---------------------------------------------------------------------------
# REQ-004 AC3 — infrastructure crash → retry
# ---------------------------------------------------------------------------


def test_scanner_infra_crash_returns_retry():
    """Scanner exits non-zero with non-JSON output → retry (infra crash)."""
    # Command that exits 2 with non-JSON stdout
    crash_cmd = f'{PY} -c "import sys; print(\'internal error\'); sys.exit(2)"'
    check = {
        "type": "security",
        "scanners": {"sast": crash_cmd},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "fail",
    }
    decision, errors, evidence = _check_security(check, [], FIXTURES)

    assert decision == "retry", f"Expected retry on infra crash, got {decision!r}"
    assert evidence["security"]["infra_crash"] is True


# ---------------------------------------------------------------------------
# Agent verdict path (design routing + reconcile)
# ---------------------------------------------------------------------------


def test_agent_needs_fix_with_clean_scanners_is_needs_fix(tmp_path: Path):
    """Agent verdict=needs_fix + clean scanners → needs_fix (reconcile keeps it)."""
    # Write a minimal security review artifact with YAML frontmatter
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
    # Use clean-fixture dir (no planted secret, no vuln deps) but with no scanners
    check = {
        "type": "security",
        "artifact_path": str(artifact),
        "scanners": {},
        "fail_on": ["critical", "high"],
        "on_missing_scanner": "fail",
        "reconcile": True,
    }
    decision, errors, evidence = _check_security(check, [str(artifact)], tmp_path)

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
    decision, errors, evidence = _check_security(check, [str(artifact)], tmp_path)

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
    decision, errors, evidence = _check_security(check, [str(artifact)], tmp_path)

    assert decision == "fail", f"Expected fail, got {decision!r}"


# ---------------------------------------------------------------------------
# Missing-scanner-only test (no artifact) with skip → scanner is recorded
# ---------------------------------------------------------------------------


def test_missing_scanner_skip_is_recorded_in_evidence():
    """on_missing_scanner=skip: missing scanner appears in evidence, not errors."""
    check = {
        "type": "security",
        "scanners": {"secrets": "cronos-no-such-scanner-xyz"},
        "fail_on": ["high"],
        "on_missing_scanner": "skip",
    }
    decision, errors, evidence = _check_security(check, [], FIXTURES)

    assert evidence["security"]["scanner_results"]["secrets"]["status"] == "missing"
    # The missing scanner should appear in scanner_errors, but not force needs_fix
    assert decision == "proceed"
