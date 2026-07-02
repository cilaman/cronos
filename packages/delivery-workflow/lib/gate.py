"""delivery/v1 gate engine — runGate dispatcher and all check implementations.

runGate(gate, artifact_paths, *, space, gate_id, state_path) -> GateResult

Check families:
  contract: schema, traceability, acceptance   — read the artifact
  outcome:  build, lint, types, test,          — re-execute the claim
            diff_vs_acceptance, g-review

Decision precedence: fail > needs_fix > proceed.
retry short-circuits on unreadable artifact.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

import yaml

from lib.verify import split_frontmatter
from lib.verify import verify as _cc_verify
from lib.security import evaluate_security as _evaluate_security
from lib.security import build_subprocess_env


GATE_DECISIONS = frozenset({"proceed", "needs_fix", "fail", "retry"})

_ACCEPTANCE_PLACEHOLDERS = frozenset(
    {"todo", "tbd", "pending", "n/a", "", "placeholder", "tbd."}
)

_VALIDATION_CMD_PLACEHOLDERS = frozenset(
    {"todo", "tbd", "pending", "run tests", "tests"}
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GateResult:
    """Outcome of a runGate call.

    decision ∈ {proceed, needs_fix, fail, retry}.
    Distinct from CC-v1 VerifyResult: ``needs_fix`` replaces ``escalate``
    (re-run the upstream agent) and ``fail`` means escalate to human.
    """

    decision: Literal["proceed", "needs_fix", "fail", "retry"]
    errors: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.decision not in GATE_DECISIONS:
            raise ValueError(
                f"decision {self.decision!r} not in {sorted(GATE_DECISIONS)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "errors": list(self.errors),
            "evidence": dict(self.evidence),
        }


@dataclass
class CommandResult:
    """Result of a subprocess invocation."""

    exit_code: int
    stdout_tail: str
    stderr_tail: str
    timed_out: bool = False


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------


def _run_command(cmd: str, cwd: str | Path, timeout: int = 300) -> CommandResult:
    """Run a shell command and return exit code + tail output.

    All outcome checks share this single subprocess boundary. TimeoutExpired
    is caught and returned as a timed_out=True result — never a hang.
    """
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=build_subprocess_env(),
        )
        return CommandResult(
            exit_code=proc.returncode,
            stdout_tail=proc.stdout[-2000:] if proc.stdout else "",
            stderr_tail=proc.stderr[-2000:] if proc.stderr else "",
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            exit_code=-1,
            stdout_tail="",
            stderr_tail=f"Command timed out after {timeout}s",
            timed_out=True,
        )


def _tail(text: str, chars: int = 500) -> str:
    return text[-chars:] if len(text) > chars else text


def _resolve_artifact_path(
    check: dict[str, Any], artifact_paths: list[str]
) -> str | None:
    """Resolve artifact path from check spec or fall back to artifact_paths[0]."""
    if check.get("artifact_path"):
        return check["artifact_path"]
    if artifact_paths:
        return artifact_paths[0]
    return None


def _read_header(artifact_path: str) -> tuple[dict[str, Any] | None, str | None]:
    """Read and parse YAML frontmatter from an artifact file.

    Returns (header, error_string). error_string is None on success.
    """
    try:
        text = Path(artifact_path).read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"cannot read artifact: {exc}"

    try:
        header, _ = split_frontmatter(text)
    except ValueError as exc:
        return None, f"malformed YAML frontmatter: {exc}"

    if header is None:
        return None, "artifact has no YAML frontmatter"

    return header, None


# ---------------------------------------------------------------------------
# Contract checks (I3, I4)
# ---------------------------------------------------------------------------


def _check_schema(
    check: dict[str, Any],
    artifact_paths: list[str],
    space: Path | None,
) -> tuple[str, list[str], dict[str, Any]]:
    """R3: Delegate to verify.verify(), wrap VerifyResult into evidence['schema']."""
    agent_class = check.get("agent")
    slug = check.get("slug")
    if not agent_class or not slug:
        return "fail", ["schema check requires 'agent' and 'slug' fields"], {}
    if space is None:
        return "fail", ["schema check requires a space path"], {}

    result = _cc_verify(agent_class, slug, space)
    evidence: dict[str, Any] = {
        "schema": {
            "passed": result.passed,
            "outcome": result.outcome,
            "errors": list(result.errors),
            "warnings": list(result.warnings),
        }
    }
    if result.outcome == "retry":
        return "retry", list(result.errors), evidence
    if not result.passed:
        return "fail", list(result.errors), evidence
    if result.outcome == "escalate":
        return "needs_fix", [], evidence
    return "proceed", [], evidence


def _check_acceptance(
    check: dict[str, Any],
    artifact_paths: list[str],
    space: Path | None,
) -> tuple[str, list[str], dict[str, Any]]:
    """R5: Verify ACs present, non-empty, non-placeholder in artifact."""
    artifact_path = _resolve_artifact_path(check, artifact_paths)
    if not artifact_path:
        return "retry", ["acceptance check requires 'artifact_path'"], {}

    header, err = _read_header(artifact_path)
    if err:
        return "retry", [err], {}

    traceability = header.get("traceability")  # type: ignore[union-attr]
    if not isinstance(traceability, list) or not traceability:
        return "proceed", [], {"acceptance": {"ac_count": 0, "failing_req_ids": []}}

    errors: list[str] = []
    total_acs = 0
    failing: list[str] = []

    for row in traceability:
        if not isinstance(row, dict):
            continue
        req_id = row.get("requirement_id", "?")
        acs = row.get("acceptance_criteria")
        if not isinstance(acs, list) or not acs:
            errors.append(f"{req_id}: acceptance_criteria is empty or missing")
            if req_id not in failing:
                failing.append(str(req_id))
            continue
        for ac in acs:
            total_acs += 1
            if not isinstance(ac, str):
                errors.append(f"{req_id}: acceptance criterion is not a string: {ac!r}")
                if req_id not in failing:
                    failing.append(str(req_id))
            elif ac.strip().lower() in _ACCEPTANCE_PLACEHOLDERS:
                errors.append(
                    f"{req_id}: acceptance criterion is a placeholder: {ac!r}"
                )
                if req_id not in failing:
                    failing.append(str(req_id))

    evidence: dict[str, Any] = {
        "acceptance": {
            "ac_count": total_acs,
            "failing_req_ids": failing,
        }
    }
    if errors:
        return "fail", errors, evidence
    return "proceed", [], evidence


def _check_traceability(
    check: dict[str, Any],
    artifact_paths: list[str],
    space: Path | None,
) -> tuple[str, list[str], dict[str, Any]]:
    """R4: Verify required id-links present (MVP: REQ variant from analysis-report)."""
    artifact_path = _resolve_artifact_path(check, artifact_paths)
    if not artifact_path:
        return "retry", ["traceability check requires 'artifact_path'"], {}

    header, err = _read_header(artifact_path)
    if err:
        return "retry", [err], {}

    required_ids: list[str] = check.get("required_ids") or []
    traceability = header.get("traceability")  # type: ignore[union-attr]

    if not isinstance(traceability, list):
        evidence: dict[str, Any] = {
            "traceability": {"resolved_ids": [], "missing_ids": required_ids}
        }
        if required_ids:
            return (
                "fail",
                [f"artifact has no traceability[] but {len(required_ids)} ids required"],
                evidence,
            )
        return "proceed", [], {"traceability": {"resolved_ids": [], "missing_ids": []}}

    present_ids = sorted(
        rid
        for row in traceability
        if isinstance(row, dict) and (rid := row.get("requirement_id")) is not None
    )
    missing_ids = [rid for rid in required_ids if rid not in present_ids]

    evidence = {
        "traceability": {
            "resolved_ids": present_ids,
            "missing_ids": missing_ids,
        }
    }
    if missing_ids:
        return "fail", [f"missing required traceability ids: {missing_ids}"], evidence
    return "proceed", [], evidence


# ---------------------------------------------------------------------------
# Outcome checks (I5, I6, I7, I8)
# ---------------------------------------------------------------------------


def _check_build(
    check: dict[str, Any],
    artifact_paths: list[str],
    space: Path | None,
) -> tuple[str, list[str], dict[str, Any]]:
    """R6: Re-execute validation_command from impl-report header.

    Never trusts the self-reported validation_command_passed flag.
    """
    artifact_path = _resolve_artifact_path(check, artifact_paths)
    if not artifact_path:
        return "retry", ["build check requires 'artifact_path'"], {}

    header, err = _read_header(artifact_path)
    if err:
        return "retry", [err], {}

    cmd = header.get("validation_command")  # type: ignore[union-attr]
    if not cmd or not isinstance(cmd, str) or not cmd.strip():
        return "fail", ["impl-report has no validation_command — cannot re-execute"], {}
    if cmd.strip().lower() in _VALIDATION_CMD_PLACEHOLDERS:
        return "fail", [f"validation_command is a placeholder ({cmd!r})"], {}

    cwd = space if space is not None else Path(".")
    result = _run_command(cmd, cwd)

    evidence: dict[str, Any] = {
        "build": {
            "command": cmd,
            "exit_code": result.exit_code,
            "stdout_tail": _tail(result.stdout_tail),
            "stderr_tail": _tail(result.stderr_tail),
            "timed_out": result.timed_out,
        }
    }
    if result.timed_out:
        return "needs_fix", ["validation_command timed out after 300s"], evidence
    if result.exit_code != 0:
        return "needs_fix", [f"validation_command exited {result.exit_code}"], evidence
    return "proceed", [], evidence


def _check_lint(
    check: dict[str, Any],
    artifact_paths: list[str],
    space: Path | None,
) -> tuple[str, list[str], dict[str, Any]]:
    """R7: Re-run linter, gate on exit code, capture violation count."""
    cmd = check.get("command", "ruff check backend/")
    cwd = space if space is not None else Path(".")
    result = _run_command(cmd, cwd)

    violation_count: int | None = None
    combined = result.stdout_tail + result.stderr_tail
    m = re.search(r"Found (\d+) error", combined)
    if m:
        violation_count = int(m.group(1))

    evidence: dict[str, Any] = {
        "lint": {
            "command": cmd,
            "exit_code": result.exit_code,
            "violation_count": violation_count,
            "stdout_tail": _tail(result.stdout_tail),
            "stderr_tail": _tail(result.stderr_tail),
            "timed_out": result.timed_out,
        }
    }
    if result.timed_out:
        return "needs_fix", ["lint command timed out after 300s"], evidence
    if result.exit_code != 0:
        return "needs_fix", [f"lint command exited {result.exit_code}"], evidence
    return "proceed", [], evidence


def _check_types(
    check: dict[str, Any],
    artifact_paths: list[str],
    space: Path | None,
) -> tuple[str, list[str], dict[str, Any]]:
    """R8: Re-run type-checker, gate on exit code, capture error count."""
    cmd = check.get("command", "mypy backend/app")
    cwd = space if space is not None else Path(".")
    result = _run_command(cmd, cwd)

    error_count: int | None = None
    combined = result.stdout_tail + result.stderr_tail
    m = re.search(r"Found (\d+) error", combined)
    if m:
        error_count = int(m.group(1))

    evidence: dict[str, Any] = {
        "types": {
            "command": cmd,
            "exit_code": result.exit_code,
            "error_count": error_count,
            "stdout_tail": _tail(result.stdout_tail),
            "stderr_tail": _tail(result.stderr_tail),
            "timed_out": result.timed_out,
        }
    }
    if result.timed_out:
        return "needs_fix", ["types command timed out after 300s"], evidence
    if result.exit_code != 0:
        return "needs_fix", [f"types command exited {result.exit_code}"], evidence
    return "proceed", [], evidence


def _parse_coverage_pct(output: str) -> float | None:
    """Parse coverage % from pytest --cov-report=term-missing TOTAL line."""
    m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
    if m:
        return float(m.group(1))
    return None


def _check_test(
    check: dict[str, Any],
    artifact_paths: list[str],
    space: Path | None,
) -> tuple[str, list[str], dict[str, Any]]:
    """R9: Re-run test suite, gate on exit code AND coverage floor.

    Coverage percentage is parsed from the pytest TOTAL line using a defensive
    regex. When no coverage line is found, coverage_pct=None and gating is on
    exit code only — the floor is never fabricated.
    """
    cmd = check.get("command", "pytest tests/ --cov=app --cov-report=term-missing")
    coverage_floor: int = check.get("coverage_floor", 80)
    cwd = space if space is not None else Path(".")
    result = _run_command(cmd, cwd)

    combined = result.stdout_tail + result.stderr_tail
    coverage_pct = _parse_coverage_pct(combined)

    tests_passed: int | None = None
    tests_failed: int | None = None
    m = re.search(r"(\d+) passed", combined)
    if m:
        tests_passed = int(m.group(1))
    m = re.search(r"(\d+) failed", combined)
    if m:
        tests_failed = int(m.group(1))

    errors: list[str] = []
    if result.timed_out:
        errors.append("test command timed out after 300s")
    elif result.exit_code != 0:
        errors.append(f"test command exited {result.exit_code}")

    # Only gate on coverage floor when: exit=0 and a coverage line was parsed
    if (
        not result.timed_out
        and result.exit_code == 0
        and coverage_pct is not None
        and coverage_pct < coverage_floor
    ):
        errors.append(
            f"coverage {coverage_pct:.0f}% < floor {coverage_floor}%"
        )

    evidence: dict[str, Any] = {
        "test": {
            "command": cmd,
            "exit_code": result.exit_code,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "coverage_pct": coverage_pct,
            "coverage_floor": coverage_floor,
            "timed_out": result.timed_out,
        }
    }
    if errors:
        return "needs_fix", errors, evidence
    return "proceed", [], evidence


def _check_diff_vs_acceptance(
    check: dict[str, Any],
    artifact_paths: list[str],
    space: Path | None,
) -> tuple[str, list[str], dict[str, Any]]:
    """R10: Keyword overlap heuristic between git diff and acceptance criteria.

    advisory-proceed when traceability source is unavailable (never hard-fails
    on missing upstream data). threshold is a gate-spec field (default 0.5,
    set 0.0 for advisory-only).
    """
    threshold: float = check.get("threshold", 0.5)
    analysis_path: str | None = check.get("analysis_path")
    impl_path = _resolve_artifact_path(check, artifact_paths)

    LIMITS = [
        "keyword match is not semantic",
        "large diffs trivially cover short ACs",
        "cannot detect wrong-thing coverage",
        f"threshold={threshold} (configurable; set 0.0 for advisory-only)",
    ]

    # Read acceptance criteria from analysis report
    acceptance_criteria: dict[str, list[str]] = {}
    if analysis_path:
        header, _ = _read_header(analysis_path)
        if header and isinstance(header.get("traceability"), list):
            for row in header["traceability"]:
                if isinstance(row, dict):
                    rid = row.get("requirement_id", "?")
                    acs = row.get("acceptance_criteria")
                    if isinstance(acs, list):
                        acceptance_criteria[str(rid)] = [
                            ac for ac in acs if isinstance(ac, str)
                        ]

    total_acs = sum(len(acs) for acs in acceptance_criteria.values())
    if not acceptance_criteria or total_acs == 0:
        return "proceed", [], {
            "diff_vs_acceptance": {
                "coverage_ratio": None,
                "covered_ac_ids": [],
                "uncovered_ac_ids": [],
                "LIMITS": ["No analysis-report traceability data available — advisory pass"]
                + LIMITS,
            }
        }

    # Compute git diff for changed files
    diff_text = ""
    files_changed: list[str] = []
    if impl_path:
        header, _ = _read_header(impl_path)
        if header and isinstance(header.get("files_changed"), list):
            files_changed = header["files_changed"]

    if files_changed and space is not None:
        files_arg = " ".join(files_changed)
        cmd_result = _run_command(
            f"git diff HEAD~1 -- {files_arg}", space, timeout=30
        )
        diff_text = cmd_result.stdout_tail

    diff_tokens = set(re.findall(r"\b[a-zA-Z][a-zA-Z0-9_]{2,}\b", diff_text.lower()))

    covered_ids: list[str] = []
    uncovered_ids: list[str] = []

    for req_id, acs in acceptance_criteria.items():
        covered = False
        for ac in acs:
            ac_keywords = set(
                re.findall(r"\b[a-zA-Z][a-zA-Z0-9_]{2,}\b", ac.lower())
            )
            if ac_keywords and ac_keywords & diff_tokens:
                covered = True
                break
        (covered_ids if covered else uncovered_ids).append(req_id)

    total_req = len(acceptance_criteria)
    coverage_ratio = len(covered_ids) / total_req if total_req > 0 else 0.0

    evidence: dict[str, Any] = {
        "diff_vs_acceptance": {
            "coverage_ratio": round(coverage_ratio, 3),
            "covered_ac_ids": covered_ids,
            "uncovered_ac_ids": uncovered_ids,
            "threshold": threshold,
            "LIMITS": LIMITS,
        }
    }
    if coverage_ratio < threshold:
        return (
            "needs_fix",
            [f"diff coverage {coverage_ratio:.0%} < threshold {threshold:.0%}"],
            evidence,
        )
    return "proceed", [], evidence


def _check_security(
    check: dict[str, Any],
    artifact_paths: list[str],
    space: Path | None,
) -> tuple[str, list[str], dict[str, Any]]:
    """Security gate: delegate to lib.security.evaluate_security.

    Decision semantics are documented in lib/security.py. This wrapper keeps
    the named _check_* convention used by CHECK_REGISTRY while sharing one
    portable implementation with the standalone runner.
    """
    return _evaluate_security(check, artifact_paths, space)


def _check_g_review(
    check: dict[str, Any],
    artifact_paths: list[str],
    space: Path | None,
) -> tuple[str, list[str], dict[str, Any]]:
    """R11: Route GateResult.decision on the verdict field inside review artifact.

    verdict=pass   → proceed
    verdict=needs_fix → needs_fix  (NOT fail — loop continues)
    verdict=fail   → fail
    missing/invalid verdict → fail
    """
    artifact_path = _resolve_artifact_path(check, artifact_paths)
    if not artifact_path:
        return "retry", ["g-review check requires 'artifact_path'"], {}

    header, err = _read_header(artifact_path)
    if err:
        return "retry", [err], {}

    verdict = header.get("verdict")  # type: ignore[union-attr]
    findings = header.get("findings") or []  # type: ignore[union-attr]
    blocking_count = sum(
        1 for f in findings if isinstance(f, dict) and f.get("blocking") is True
    )

    evidence: dict[str, Any] = {
        "g_review": {
            "verdict": verdict,
            "blocking_finding_count": blocking_count,
            "finding_class": header.get("finding_class"),  # type: ignore[union-attr]
        }
    }

    if verdict == "pass":
        return "proceed", [], evidence
    if verdict == "needs_fix":
        return (
            "needs_fix",
            [f"review verdict=needs_fix ({blocking_count} blocking findings)"],
            evidence,
        )
    if verdict == "fail":
        return (
            "fail",
            [f"review verdict=fail ({blocking_count} blocking findings)"],
            evidence,
        )
    return (
        "fail",
        [f"review artifact has no valid verdict field (got {verdict!r})"],
        evidence,
    )


# ---------------------------------------------------------------------------
# Dispatch table — all check types registered here
# ---------------------------------------------------------------------------

CHECK_REGISTRY: dict[str, Callable] = {
    "schema": _check_schema,
    "acceptance": _check_acceptance,
    "traceability": _check_traceability,
    "build": _check_build,
    "lint": _check_lint,
    "types": _check_types,
    "test": _check_test,
    "diff_vs_acceptance": _check_diff_vs_acceptance,
    "g-review": _check_g_review,
    "security": _check_security,
}


# ---------------------------------------------------------------------------
# State persistence (R12)
# ---------------------------------------------------------------------------


def _write_gate_result(
    result: GateResult,
    gate_id: str,
    state_path: Path,
) -> None:
    """Atomically write GateResult into state.json under nodes.<gate_id>.gate."""
    state: dict[str, Any] = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state = {}

    nodes = state.setdefault("nodes", {})
    node = nodes.setdefault(gate_id, {})
    node["gate"] = result.to_dict()

    tmp = state_path.with_suffix(".tmp")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp.write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(str(tmp), str(state_path))
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# runGate — main entry point
# ---------------------------------------------------------------------------


def runGate(
    gate: dict[str, Any],
    artifact_paths: list[str],
    *,
    space: str | Path | None = None,
    gate_id: str | None = None,
    state_path: str | Path | None = None,
) -> GateResult:
    """Execute all gate checks and return a single GateResult.

    Iterates gate['checks'], dispatches by type, accumulates errors/evidence.
    Decision precedence: fail > needs_fix > proceed.
    retry short-circuits — no further checks run.

    Writes result atomically to state.json when both state_path and gate_id
    are provided (R12). The write happens for every decision value.
    """
    space_path = Path(space) if space is not None else None
    checks: list[dict[str, Any]] = gate.get("checks") or []

    overall_decision: str = "proceed"
    all_errors: list[str] = []
    all_evidence: dict[str, Any] = {}

    for check in checks:
        check_type = check.get("type")
        handler = CHECK_REGISTRY.get(check_type)  # type: ignore[arg-type]
        if handler is None:
            all_errors.append(f"unknown check type: {check_type!r}")
            overall_decision = "fail"
            continue

        decision, errors, evidence = handler(check, artifact_paths, space_path)
        all_errors.extend(errors)
        all_evidence.update(evidence)

        if decision == "retry":
            result = GateResult(
                decision="retry", errors=all_errors, evidence=all_evidence
            )
            if state_path is not None and gate_id is not None:
                _write_gate_result(result, gate_id, Path(state_path))
            return result

        if decision == "fail":
            overall_decision = "fail"
        elif decision == "needs_fix" and overall_decision != "fail":
            overall_decision = "needs_fix"

    result = GateResult(
        decision=overall_decision,  # type: ignore[arg-type]
        errors=all_errors,
        evidence=all_evidence,
    )

    if state_path is not None and gate_id is not None:
        _write_gate_result(result, gate_id, Path(state_path))

    return result
