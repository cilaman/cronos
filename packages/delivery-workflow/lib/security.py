"""Portable security evaluator — shared by the Cronos gate and the standalone runner.

evaluate_security(check, artifact_paths, space) -> (decision, errors, evidence)

Decision semantics mirror gate.py:_check_security exactly:
  proceed   — agent verdict==pass (or absent) AND no scanner fail_on hit AND no required
              scanner missing under on_missing_scanner=fail.
  needs_fix — agent verdict==needs_fix OR any scanner reports fail_on severity
              OR a required scanner is missing under on_missing_scanner=fail.
  fail      — agent verdict==fail.
  retry     — unreadable agent artifact OR scanner infrastructure crash.

This module captures full scanner stdout (no 2 KB tail truncation) so a real scanner
emitting large JSON is always parsed correctly — preventing the fail-open described in
the delivery/v2 security review.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Private subprocess helper — full stdout, tailed stderr
# ---------------------------------------------------------------------------


def _run_security_cmd(cmd: str, cwd: Path, timeout: int = 300) -> tuple[int, str, str, bool]:
    """Run cmd, return (exit_code, full_stdout, stderr_tail, timed_out).

    Full stdout is returned (not tailed) so large JSON payloads parse correctly.
    """
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stderr_tail = proc.stderr[-2000:] if proc.stderr else ""
        return proc.returncode, proc.stdout or "", stderr_tail, False
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s", True


def _tail(text: str, chars: int = 500) -> str:
    return text[-chars:] if len(text) > chars else text


# ---------------------------------------------------------------------------
# Private frontmatter splitter — mirrors verify.split_frontmatter semantics
# without importing from app.*
# ---------------------------------------------------------------------------


def _split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Return (header_dict, body). header is None if no --- frontmatter."""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    yaml_block = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    try:
        header = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML front-matter: {exc}") from exc
    if not isinstance(header, dict):
        raise ValueError("YAML front-matter must be a mapping")
    return header, body


def _read_security_header(
    artifact_path: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Read and parse YAML frontmatter from a security agent artifact.

    Returns (header, error_string). error_string is None on success.
    """
    try:
        text = Path(artifact_path).read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"cannot read artifact: {exc}"
    try:
        header, _ = _split_frontmatter(text)
    except ValueError as exc:
        return None, f"malformed YAML frontmatter: {exc}"
    if header is None:
        return None, "artifact has no YAML frontmatter"
    return header, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_security(
    check: dict[str, Any],
    artifact_paths: list[str],
    space: Path | None,
) -> tuple[str, list[str], dict[str, Any]]:
    """Portable security evaluator.

    Identical signature and return-tuple contract to gate.py:_check_security so
    the Cronos gate can delegate with a one-line call.

    Returns (decision, errors, evidence) where decision ∈ {proceed, needs_fix, fail, retry}.
    """
    fail_on: list[str] = [s.lower() for s in (check.get("fail_on") or [])]
    on_missing: str = check.get("on_missing_scanner", "fail")
    scanners: dict[str, str] = check.get("scanners") or {}
    cwd = space if space is not None else Path(".")

    # Resolve artifact path
    artifact_path: str | None = check.get("artifact_path") or (
        artifact_paths[0] if artifact_paths else None
    )

    # Read security agent artifact (optional — scanners can run standalone)
    agent_verdict: str | None = None
    agent_finding_class: str | None = None
    agent_findings: list[dict] = []

    if artifact_path:
        header, err = _read_security_header(artifact_path)
        if err:
            return "retry", [f"cannot read security agent artifact: {err}"], {}
        if header is not None:
            agent_verdict = header.get("verdict")
            agent_finding_class = header.get("finding_class")
            agent_findings = header.get("findings") or []

    # Run scanners
    scanner_results: dict[str, Any] = {}
    scanner_errors: list[str] = []
    has_fail_on_hit = False
    has_missing_fail = False
    dep_hit = False
    code_hit = False

    for name, cmd in scanners.items():
        exit_code, full_stdout, stderr_tail, timed_out = _run_security_cmd(cmd, cwd)

        is_missing = exit_code == 127 or (
            "not found" in stderr_tail.lower()
            or "command not found" in stderr_tail.lower()
        )
        if is_missing:
            scanner_results[name] = {"status": "missing", "exit_code": exit_code}
            if on_missing == "fail":
                has_missing_fail = True
                scanner_errors.append(
                    f"scanner '{name}' is missing (exit {exit_code});"
                    " on_missing_scanner=fail"
                )
            else:
                scanner_errors.append(
                    f"scanner '{name}' is missing — skipped (on_missing_scanner=skip)"
                )
            continue

        # Parse full stdout (not tailed) so large JSON is always parseable (DD-002)
        parsed: Any = None
        stdout = full_stdout.strip()
        if stdout:
            try:
                parsed = json.loads(stdout)
            except (json.JSONDecodeError, ValueError):
                parsed = None

        if parsed is None and exit_code not in (0, 1):
            # Non-zero exit + unparseable output = infrastructure crash → retry
            scanner_results[name] = {
                "status": "crash",
                "exit_code": exit_code,
                "stderr_tail": _tail(stderr_tail),
            }
            return (
                "retry",
                scanner_errors + [
                    f"scanner '{name}' crashed (exit {exit_code},"
                    " unparseable output)"
                ],
                {"security": {"scanner_results": scanner_results, "infra_crash": True}},
            )

        # Extract severity hits from parsed output
        severity_hits: list[str] = []
        items: list[Any] = []
        if isinstance(parsed, list):
            items = parsed
        elif isinstance(parsed, dict):
            items = (
                parsed.get("findings")
                or parsed.get("results")
                or parsed.get("vulnerabilities")
                or []
            )

        for item in items:
            if isinstance(item, dict):
                sev = (item.get("severity") or item.get("Severity") or "").lower()
                if sev and fail_on and sev in fail_on:
                    severity_hits.append(sev)

        scanner_results[name] = {
            "status": "hit" if severity_hits else "clean",
            "exit_code": exit_code,
            "severity_hits": severity_hits,
            "findings_count": len(severity_hits),
        }

        if severity_hits:
            has_fail_on_hit = True
            if name.startswith("deps"):
                dep_hit = True
            else:
                code_hit = True
            scanner_errors.append(
                f"scanner '{name}' found {len(severity_hits)}"
                f" {'/'.join(sorted(set(severity_hits)))} finding(s)"
            )

    # Derive effective routing finding_class (design > dependency > code)
    if agent_finding_class == "design":
        effective_class: str = "design"
    elif dep_hit or agent_finding_class == "dependency":
        effective_class = "dependency"
    else:
        effective_class = "code"

    blocking_count = sum(
        1 for f in agent_findings if isinstance(f, dict) and f.get("blocking") is True
    )

    evidence: dict[str, Any] = {
        "security": {
            "agent_verdict": agent_verdict,
            "agent_finding_class": agent_finding_class,
            "agent_blocking_finding_count": blocking_count,
            "scanner_results": scanner_results,
            "effective_finding_class": effective_class,
            "has_fail_on_hit": has_fail_on_hit,
            "has_missing_fail": has_missing_fail,
        }
    }

    errors: list[str] = list(scanner_errors)

    if agent_verdict == "fail":
        errors.insert(0, f"security agent verdict=fail ({blocking_count} blocking findings)")
        return "fail", errors, evidence

    not_proceed = agent_verdict == "needs_fix" or has_fail_on_hit or has_missing_fail
    if not_proceed:
        if agent_verdict == "needs_fix":
            errors.insert(
                0,
                f"security agent verdict=needs_fix ({blocking_count} blocking findings)",
            )
        return "needs_fix", errors, evidence

    return "proceed", [], evidence
