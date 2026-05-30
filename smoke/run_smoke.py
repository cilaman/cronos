"""End-to-end smoke driver for the CC-v1 pipeline (task 3.5).

Exercises the same code path the pipeline-gate skill uses (
``app.pipeline.verify`` CLI + ``app.pipeline.state_writer.{update_phase,
record_phase_log}``) against two scratch spaces:

  * green/   -- every phase artifact is hand-crafted to pass verify.
               Expectation: each phase records gate_decision=proceed,
               status=done; pipeline-state.json ends with all 7 phases
               present; phases-log.jsonl has 7 lines, all proceed.
  * broken/  -- scout/analysis pass, then design has a deliberately
               broken artifact (cc_version='9.9' instead of '1.0').
               Expectation: verify exits 1, gate decision=fail,
               phase status=blocked, STATUS: BLOCKED is what the gate
               would emit, and we halt the DAG before impl/test/...

The driver does NOT spawn real sub-agents or POST to Cronos. Doing that
would require the Cronos worker, which can't run inside an agent task.
Instead, the driver simulates Phases 0..7 by writing artifacts and
running the gate logic synchronously. The acceptance criteria of task
3.5 ("artifacts pass verify; DAG advances on green; broken artifact
halts at the gate; evidence captured in pipeline-state.json +
phases-log.jsonl") are exactly the behaviours this driver checks.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
BACKEND = WORKSPACE / "backend"
sys.path.insert(0, str(BACKEND))

from app.pipeline.state_writer import (  # noqa: E402
    PhaseEntry,
    PhaseMetrics,
    PhaseVerifyResult,
    init_pipeline,
    load_state,
    record_phase_log,
    state_path,
    log_path,
    update_phase,
)

# ---------------------------------------------------------------------------
# Per-phase artifact templates: built from the in-repo goldens, with the
# slug + outputs_produced rewritten for the smoke run's slug.
# ---------------------------------------------------------------------------

GOLDEN_DIR = BACKEND / "app" / "pipeline" / "fixtures" / "golden"

# Maps the canonical CC-v1 class ("agent" CLI arg) to:
#   (golden_filename, slug-suffix-for-fan-out, agent_name, artifact_prefix)
PHASE_PLAN: list[tuple[str, str, str, str, str]] = [
    # (class,           golden,            slug_extra, agent_name,           filename_prefix)
    ("research",       "research.md",      "",         "pipeline-scout",     "scout-report"),
    ("analysis",       "analysis.md",      "",         "pipeline-analyst",   "analysis-report"),
    ("design",         "design.md",        "",         "pipeline-architect", "design-report"),
    ("implementation", "implementation.md","--i1",     "pipeline-implementor","impl-report"),
    ("test",           "test.md",          "",         "tester",             "test-report"),
    ("review",         "review.md",        "--attempt1","pipeline-reviewer", "review-report"),
    ("doc",            "doc.md",           "",         "pipeline-doc-sync",  "doc-report"),
]


def _rewrite_artifact(template_path: Path, *, target_slug: str) -> str:
    """Rewrite the golden so every reference to the fixture's slug (both the
    bare ``fixture-test`` and any fan-out form ``fixture-test--*``) points at
    ``target_slug``.

    The review/test/doc goldens use the bare ``fixture-test`` slug because
    the in-repo regression harness exercises them under that bare slug
    (see ``tests/test_pipeline_fixtures.py``). For the smoke run we need
    the header ``slug:`` to match the full fan-out slug the verifier is
    called with, so we rewrite the slug line directly.
    """
    text = template_path.read_text(encoding="utf-8")
    # 1) Rewrite the header `slug:` line to the target slug verbatim. This
    #    catches the case where the golden uses 'fixture-test' but we want
    #    'foo--attempt1' or 'foo--i1'.
    import re as _re
    text = _re.sub(
        r"(?m)^slug:\s*\S+\s*$",
        f"slug: {target_slug}",
        text,
        count=1,
    )
    # 2) Rewrite filename references in outputs_produced + body. The
    #    fixture's parent slug is 'fixture-test'; the target parent slug
    #    is target_slug.split('--', 1)[0]. We need both substitutions in
    #    the right order to avoid double-replacement.
    target_parent = target_slug.split("--", 1)[0]
    # The fixture's parent slug is always 'fixture-test'.
    text = text.replace("fixture-test", target_parent)
    return text


def _ensure_clean(scratch: Path) -> None:
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)


def _verify_cli(*, agent_class: str, slug: str, space: Path) -> tuple[int, dict]:
    """Invoke the verify CLI the same way the pipeline-gate skill does."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.pipeline.verify",
            "--agent",
            agent_class,
            "--slug",
            slug,
            "--space",
            str(space),
            "--normalize",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(BACKEND),
    )
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"_raw_stdout": proc.stdout, "_raw_stderr": proc.stderr}
    return proc.returncode, payload


@dataclass
class GateOutcome:
    phase: str
    slug: str
    exit_code: int
    passed: bool
    outcome: str
    errors: list[str]
    artifact_rel: str


def _run_gate(
    *,
    agent_class: str,
    slug: str,
    space: Path,
    goal_slug: str,
    agent_name: str,
    pseudo_task_id: str,
) -> GateOutcome:
    """Run one gate: verify + state_writer.{update_phase, record_phase_log}.

    This is the same sequence the pipeline-gate skill executes; the only
    difference is we synthesize PhaseMetrics manually because there is no
    upstream RunTrace (no real agent ran)."""
    exit_code, payload = _verify_cli(agent_class=agent_class, slug=slug, space=space)
    passed = bool(payload.get("passed", False))
    outcome = payload.get("outcome", "fail")
    errors = list(payload.get("errors", []))
    warnings = list(payload.get("warnings", []))
    artifact_rel = payload.get("artifact_path", "")
    norm_fixes: list[str] = []
    if isinstance(payload.get("normalize"), dict):
        norm_fixes = list(payload["normalize"].get("fixes_applied", []))

    gate_decision = outcome if outcome in {"proceed", "escalate", "retry", "fail"} else "fail"
    gate_reason = "all checks passed" if passed else "; ".join(errors)[:500]
    phase_status = "done" if gate_decision == "proceed" else "blocked"

    update_phase(
        space,
        goal_slug,
        PhaseEntry(
            phase=agent_class,
            status=phase_status,
            agent=agent_name,
            task_id=pseudo_task_id,
            run_index=0,
            artifact_path=artifact_rel,
            verify_result=PhaseVerifyResult(
                passed=passed,
                errors=errors,
                warnings=warnings,
                normalize_fixes=norm_fixes,
                gate_decision=gate_decision,
                gate_reason=gate_reason,
            ),
            metrics=PhaseMetrics(),  # no real trace for the smoke run
        ),
    )
    record_phase_log(
        space,
        goal_slug,
        phase=agent_class,
        status=phase_status,
        gate_decision=gate_decision,
        task_id=pseudo_task_id,
        run_index=0,
    )

    return GateOutcome(
        phase=agent_class,
        slug=slug,
        exit_code=exit_code,
        passed=passed,
        outcome=outcome,
        errors=errors,
        artifact_rel=artifact_rel,
    )


# ---------------------------------------------------------------------------
# Driver entry points
# ---------------------------------------------------------------------------


def _scaffold(space: Path, goal_slug: str, *, request_text: str) -> None:
    """Cronos Phase 0 — what pipeline-scaffold's init step does, minus the
    Cronos goal/task POSTs (we don't want to pollute the real board)."""
    pdir = space / ".cronos" / "pipeline" / goal_slug
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "request.md").write_text(request_text + "\n", encoding="utf-8")
    init_pipeline(space, goal_slug, status="running", request_text=request_text)


def _write_phase_artifact(
    *,
    space: Path,
    goal_slug: str,
    artifact_prefix: str,
    artifact_slug: str,
    body: str,
) -> Path:
    pdir = space / ".cronos" / "pipeline" / goal_slug
    pdir.mkdir(parents=True, exist_ok=True)
    out = pdir / f"{artifact_prefix}-{artifact_slug}.md"
    out.write_text(body, encoding="utf-8")
    return out


def run_green(scratch_root: Path) -> dict:
    """Drive every phase with a valid artifact; assert each gate passes."""
    space = scratch_root / "green-space"
    _ensure_clean(space)
    goal_slug = "smoke-csv-export-green"
    request = (
        "Add a 'Download CSV' button to the dashboard so users can export the "
        "currently visible task list to a CSV file."
    )
    _scaffold(space, goal_slug, request_text=request)

    outcomes: list[GateOutcome] = []
    for class_name, golden_name, slug_extra, agent_name, prefix in PHASE_PLAN:
        slug = f"{goal_slug}{slug_extra}"
        body = _rewrite_artifact(
            GOLDEN_DIR / golden_name,
            target_slug=slug,
        )
        _write_phase_artifact(
            space=space,
            goal_slug=goal_slug,
            artifact_prefix=prefix,
            artifact_slug=slug,
            body=body,
        )
        outcomes.append(
            _run_gate(
                agent_class=class_name,
                slug=slug,
                space=space,
                goal_slug=goal_slug,
                agent_name=agent_name,
                pseudo_task_id=f"smoke-{class_name}-{slug}",
            )
        )

    state = load_state(space, goal_slug) or {}
    log_lines = log_path(space, goal_slug).read_text().splitlines() if log_path(space, goal_slug).exists() else []
    return {
        "space": str(space),
        "goal_slug": goal_slug,
        "outcomes": [vars(o) for o in outcomes],
        "state_summary": _summarize_state(state),
        "log_count": len(log_lines),
        "log_entries": [json.loads(line) for line in log_lines],
    }


def run_broken(scratch_root: Path) -> dict:
    """Drive scout + analysis successfully, then break the design artifact
    and assert the gate halts the DAG before impl/test/review/doc."""
    space = scratch_root / "broken-space"
    _ensure_clean(space)
    goal_slug = "smoke-csv-export-broken"
    request = (
        "Same trivial request as the green run; the broken variant breaks "
        "the design artifact to prove the gate halts the DAG."
    )
    _scaffold(space, goal_slug, request_text=request)

    outcomes: list[GateOutcome] = []
    halted = False
    halted_at = ""

    for class_name, golden_name, slug_extra, agent_name, prefix in PHASE_PLAN:
        slug = f"{goal_slug}{slug_extra}"
        body = _rewrite_artifact(
            GOLDEN_DIR / golden_name,
            target_slug=slug,
        )

        if class_name == "design":
            # Break the artifact: tweak cc_version to something the verifier
            # explicitly rejects (CC_VERSION != '1.0'). This is the kind of
            # error a buggy agent would produce; the gate must catch it.
            body = body.replace("cc_version: '1.0'", "cc_version: '9.9'", 1)

        _write_phase_artifact(
            space=space,
            goal_slug=goal_slug,
            artifact_prefix=prefix,
            artifact_slug=slug,
            body=body,
        )
        outcome = _run_gate(
            agent_class=class_name,
            slug=slug,
            space=space,
            goal_slug=goal_slug,
            agent_name=agent_name,
            pseudo_task_id=f"smoke-{class_name}-{slug}",
        )
        outcomes.append(outcome)

        if outcome.outcome != "proceed":
            halted = True
            halted_at = class_name
            break  # gate halted the DAG; downstream phases must NOT run

    state = load_state(space, goal_slug) or {}
    log_lines = (
        log_path(space, goal_slug).read_text().splitlines()
        if log_path(space, goal_slug).exists()
        else []
    )
    return {
        "space": str(space),
        "goal_slug": goal_slug,
        "halted": halted,
        "halted_at": halted_at,
        "outcomes": [vars(o) for o in outcomes],
        "state_summary": _summarize_state(state),
        "log_count": len(log_lines),
        "log_entries": [json.loads(line) for line in log_lines],
    }


def _summarize_state(state: dict) -> dict:
    phases = state.get("phases", {})
    return {
        "cc_version": state.get("cc_version"),
        "status": state.get("status"),
        "phase_count": len(phases),
        "phases": {
            k: {
                "status": v.get("status"),
                "gate_decision": v.get("verify_result", {}).get("gate_decision"),
                "errors": v.get("verify_result", {}).get("errors", []),
            }
            for k, v in phases.items()
        },
        "telemetry": state.get("telemetry", {}),
    }


# ---------------------------------------------------------------------------
# Assertion helpers (the smoke acceptance criteria)
# ---------------------------------------------------------------------------


def assert_green(report: dict) -> list[str]:
    fails: list[str] = []
    if report["state_summary"]["phase_count"] != 7:
        fails.append(
            f"green: expected 7 phases recorded, got {report['state_summary']['phase_count']}"
        )
    if report["log_count"] != 7:
        fails.append(f"green: expected 7 log entries, got {report['log_count']}")
    for class_name in [c for c, *_ in PHASE_PLAN]:
        ph = report["state_summary"]["phases"].get(class_name)
        if ph is None:
            fails.append(f"green: phase {class_name!r} missing from state")
            continue
        if ph["gate_decision"] != "proceed":
            fails.append(
                f"green: phase {class_name!r} gate_decision={ph['gate_decision']!r} "
                f"(expected proceed); errors={ph['errors']}"
            )
        if ph["status"] != "done":
            fails.append(f"green: phase {class_name!r} status={ph['status']!r} (expected done)")
    for outcome in report["outcomes"]:
        if outcome["exit_code"] != 0:
            fails.append(
                f"green: verify CLI for {outcome['phase']!r} exited {outcome['exit_code']} "
                f"(expected 0); errors={outcome['errors']}"
            )
    tel = report["state_summary"]["telemetry"]
    if tel.get("phases_completed") != 7 or tel.get("phases_failed", 0) != 0:
        fails.append(f"green: telemetry mismatch: {tel}")
    return fails


def assert_broken(report: dict) -> list[str]:
    fails: list[str] = []
    if not report["halted"]:
        fails.append("broken: DAG was not halted — gate let a bad artifact through!")
    if report["halted_at"] != "design":
        fails.append(
            f"broken: halted at {report['halted_at']!r} (expected 'design')"
        )
    # Only scout + analysis + design should have been recorded.
    expected_phases = {"research", "analysis", "design"}
    actual_phases = set(report["state_summary"]["phases"].keys())
    if actual_phases != expected_phases:
        fails.append(
            f"broken: phases recorded={sorted(actual_phases)} (expected {sorted(expected_phases)})"
        )
    design_phase = report["state_summary"]["phases"].get("design", {})
    if design_phase.get("status") != "blocked":
        fails.append(
            f"broken: design phase status={design_phase.get('status')!r} (expected blocked)"
        )
    if design_phase.get("gate_decision") != "fail":
        fails.append(
            f"broken: design gate_decision={design_phase.get('gate_decision')!r} (expected fail)"
        )
    # Final outcome on design should be exit 1.
    design_outcome = next(o for o in report["outcomes"] if o["phase"] == "design")
    if design_outcome["exit_code"] != 1:
        fails.append(
            f"broken: design verify exit_code={design_outcome['exit_code']} (expected 1)"
        )
    return fails


def main() -> int:
    scratch_root = WORKSPACE / "smoke"
    green = run_green(scratch_root)
    broken = run_broken(scratch_root)

    green_fails = assert_green(green)
    broken_fails = assert_broken(broken)

    summary = {
        "green": green,
        "broken": broken,
        "green_assertions_failed": green_fails,
        "broken_assertions_failed": broken_fails,
    }
    out_json = scratch_root / "smoke-result.json"
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(
        {
            "green_state_summary": green["state_summary"],
            "green_log_count": green["log_count"],
            "broken_halted": broken["halted"],
            "broken_halted_at": broken["halted_at"],
            "broken_state_summary": broken["state_summary"],
            "broken_log_count": broken["log_count"],
            "green_assertions_failed": green_fails,
            "broken_assertions_failed": broken_fails,
        },
        indent=2,
    ))
    return 0 if (not green_fails and not broken_fails) else 1


if __name__ == "__main__":
    sys.exit(main())
