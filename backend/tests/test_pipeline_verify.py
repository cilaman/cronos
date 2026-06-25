"""Tests for the CC-v1 pipeline verifier.

Cover the cross-field rules R1-R7, the per-class extensions
(R-impl/R-val/R-rev/R-doc), the exit-code vocabulary
(proceed/fail/escalate/retry), and the CLI surface.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from app.pipeline.verify import (
    CLASS_CONFIG,
    EXIT_ESCALATE,
    EXIT_FAIL,
    EXIT_PROCEED,
    EXIT_RETRY,
    canonical_artifact_relpath,
    main,
    verify,
)


# ---------------------------------------------------------------------------
# Helpers — build canonical valid artifacts for every class, then mutate.
# ---------------------------------------------------------------------------


def write_artifact(
    space: Path,
    class_name: str,
    slug: str,
    header: dict,
    body: str | None = None,
) -> Path:
    """Write a frontmatter+body artifact to the canonical path for the class."""
    rel = canonical_artifact_relpath(class_name, slug)
    path = space / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if body is None:
        body = default_body(class_name)
    text = "---\n" + yaml.safe_dump(header, sort_keys=False) + "---\n\n" + body
    path.write_text(text, encoding="utf-8")
    return path


def default_body(class_name: str) -> str:
    """Return a minimal markdown body that satisfies the section checks."""
    sections_by_class: dict[str, list[str]] = {
        "research": [
            "Summary", "Coverage", "Findings", "Assumptions",
            "Open questions", "Next consumer brief",
        ],
        "analysis": [
            "Summary", "Scope", "Requirements", "Acceptance criteria",
            "Traceability", "Assumptions", "Open questions",
            "Next consumer brief",
        ],
        "design": [
            "Summary", "Components", "Implementation plan", "Risks",
            "Assumptions", "Open questions", "Next consumer brief",
        ],
        "implementation": [
            "Summary", "Files changed", "Out-of-scope findings",
            "Assumptions", "Open questions", "Next consumer brief",
        ],
        "test": [
            "Summary", "Gate result", "Failures", "Assumptions",
            "Open questions", "Next consumer brief",
        ],
        "review": [
            "Summary", "Findings", "Verdict", "Assumptions",
            "Open questions", "Next consumer brief",
        ],
        "doc": [
            "Summary", "Updated docs", "Intentionally not updated",
            "Assumptions", "Open questions", "Next consumer brief",
        ],
        "retro": [
            "Summary", "Scores", "Findings", "Assumptions",
            "Open questions", "Next consumer brief",
        ],
    }
    parts = []
    for s in sections_by_class[class_name]:
        parts.append(f"## {s}\n\nstub.\n")
    return "\n".join(parts)


# --- canonical "good" headers (must pass verifier as-is) ---------------------


def research_header(slug: str = "test-feature") -> dict:
    return {
        "cc_version": "1.0",
        "agent": "scout",
        "slug": slug,
        "phase": "scout",
        "status": "done",
        "confidence": 0.8,
        "inputs_used": ["docs/spec.md"],
        "outputs_produced": [canonical_artifact_relpath("research", slug)],
        "blockers": [],
        "next_consumer": "analysis",
        "metrics": {"tool_calls": 5, "files_read": 1, "memory_hits": 0},
        "coverage_summary": {
            "searched": ["docs/"],
            "excluded": ["node_modules/"],
            "strategies": ["memory_retrieval", "read_targeted"],
        },
    }


def analysis_header(slug: str = "test-feature") -> dict:
    return {
        "cc_version": "1.0",
        "agent": "analyst",
        "slug": slug,
        "phase": "analysis",
        "status": "done",
        "confidence": 0.85,
        "inputs_used": ["docs/req.md"],
        "outputs_produced": [canonical_artifact_relpath("analysis", slug)],
        "blockers": [],
        "next_consumer": "design",
        "metrics": {"tool_calls": 3, "files_read": 1, "memory_hits": 0},
        "request": "Add a new feature.",
        "has_ui": True,
        "coverage_summary": {
            "searched": ["docs/"],
            "excluded": [],
            "strategies": ["requirements_decomposition"],
        },
        "traceability": [
            {
                "requirement_id": "R1",
                "statement": "Must do X.",
                "acceptance_criteria": ["X works."],
                "verifying_phase": "test",
            }
        ],
    }


def design_header(slug: str = "test-feature") -> dict:
    return {
        "cc_version": "1.0",
        "agent": "architect",
        "slug": slug,
        "phase": "design",
        "status": "done",
        "confidence": 0.9,
        "inputs_used": ["docs/req.md"],
        "outputs_produced": [canonical_artifact_relpath("design", slug)],
        "blockers": [],
        "next_consumer": "backend-impl",
        "metrics": {
            "tool_calls": 4,
            "files_read": 1,
            "memory_hits": 0,
            "iterations_planned": 1,
        },
        "iterations": [
            {
                "id": "I1",
                "type": "backend",
                "scope_files": ["app/foo.py"],
                "validation_command": "pytest tests/",
                "depends_on": [],
            }
        ],
        "risks": [
            {
                "description": "Risk of X.",
                "severity": "medium",
                "mitigation": "Test thoroughly.",
            }
        ],
        "coverage_summary": {
            "searched": ["app/"],
            "excluded": [],
            "strategies": ["component_decomposition"],
        },
    }


def impl_header(slug: str = "test-feature--i1") -> dict:
    return {
        "cc_version": "1.0",
        "agent": "backend-impl",
        "slug": slug,
        "phase": "impl",
        "status": "done",
        "confidence": 0.9,
        "inputs_used": ["docs/design.md"],
        "outputs_produced": [canonical_artifact_relpath("implementation", slug)],
        "blockers": [],
        "next_consumer": "test",
        "metrics": {
            "tool_calls": 8,
            "files_read": 1,
            "memory_hits": 0,
            "diff_lines_added": 30,
            "diff_lines_removed": 5,
        },
        "iteration_id": "I1",
        "files_changed": ["app/foo.py"],
        "validation_command_passed": True,
    }


def _make_test_header(slug: str = "test-feature") -> dict:
    return {
        "cc_version": "1.0",
        "agent": "tester",
        "slug": slug,
        "phase": "test",
        "status": "done",
        "confidence": 0.95,
        "inputs_used": [],
        "outputs_produced": [canonical_artifact_relpath("test", slug)],
        "blockers": [],
        "next_consumer": "review",
        "metrics": {"tool_calls": 3, "files_read": 0},
        "gate_decision": "pass",
        "tests_added": 0,
        "passed": 42,
        "failed": 0,
    }


def review_header(slug: str = "test-feature") -> dict:
    return {
        "cc_version": "1.0",
        "agent": "reviewer",
        "slug": slug,
        "phase": "review",
        "status": "done",
        "confidence": 0.9,
        "inputs_used": ["app/foo.py"],
        "outputs_produced": [canonical_artifact_relpath("review", slug)],
        "blockers": [],
        "next_consumer": "doc",
        "metrics": {"tool_calls": 4, "files_read": 1},
        "verdict": "pass",
        "findings": [],
    }


def doc_header(slug: str = "test-feature") -> dict:
    rel = canonical_artifact_relpath("doc", slug)
    return {
        "cc_version": "1.0",
        "agent": "doc-writer",
        "slug": slug,
        "phase": "doc",
        "status": "done",
        "confidence": 0.9,
        "inputs_used": ["app/foo.py"],
        "outputs_produced": [rel, "docs/feature.md"],
        "blockers": [],
        "next_consumer": "user",
        "metrics": {
            "tool_calls": 3,
            "files_read": 1,
            "docs_updated": 1,
        },
        "intentionally_not_updated": [
            {"path": "docs/old.md", "reason": "Out of scope for this feature."}
        ],
    }


def retro_header(slug: str = "test-feature") -> dict:
    return {
        "cc_version": "1.0",
        "agent": "pipeline-retro",
        "slug": slug,
        "phase": "retro",
        "status": "done",
        "confidence": 0.9,
        "inputs_used": [".cronos/pipeline/test-feature/pipeline-state.json"],
        "outputs_produced": [canonical_artifact_relpath("retro", slug)],
        "blockers": [],
        "next_consumer": "user",
        "metrics": {
            "tool_calls": 6,
            "files_read": 1,
            "memory_hits": 0,
            "phases_reviewed": 7,
            "traces_reviewed": 7,
        },
        "scores": {
            "planning": 4,
            "error_handling": 4,
            "efficiency": 3,
            "completion": 5,
            "communication": 4,
        },
        "findings": [
            {
                "id": "F1",
                "severity": "medium",
                "fix_type": "agent_prompt_refinement",
                "target": "agent:pipeline-implementor",
                "evidence": "Implementor backtracked twice on backend/app/foo.py.",
                "suggested_action": (
                    "Add 'read scope_files before first Edit' to the implementor "
                    "preflight checklist."
                ),
            }
        ],
    }


GOOD_HEADERS = {
    "research": research_header,
    "analysis": analysis_header,
    "design": design_header,
    "implementation": impl_header,
    "test": _make_test_header,
    "review": review_header,
    "doc": doc_header,
    "retro": retro_header,
}


def slug_for(class_name: str) -> str:
    return "test-feature--i1" if class_name == "implementation" else "test-feature"


# ---------------------------------------------------------------------------
# Golden-path: each class verifies cleanly with its canonical header.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("class_name", sorted(CLASS_CONFIG.keys()))
def test_golden_path_all_classes(tmp_path: Path, class_name: str) -> None:
    slug = slug_for(class_name)
    write_artifact(tmp_path, class_name, slug, GOOD_HEADERS[class_name](slug))
    result = verify(class_name, slug, tmp_path)
    assert result.passed, (
        f"{class_name} golden header failed: {result.errors}"
    )
    assert result.outcome == "proceed"
    assert result.exit_code() == EXIT_PROCEED


# ---------------------------------------------------------------------------
# Retry path — missing or malformed artifacts.
# ---------------------------------------------------------------------------


def test_retry_when_artifact_missing(tmp_path: Path) -> None:
    result = verify("research", "missing-feature", tmp_path)
    assert not result.passed
    assert result.outcome == "retry"
    assert result.exit_code() == EXIT_RETRY
    assert "not found" in result.errors[0]


def test_retry_when_no_frontmatter(tmp_path: Path) -> None:
    rel = canonical_artifact_relpath("research", "no-fm")
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# just markdown, no frontmatter\n", encoding="utf-8")
    result = verify("research", "no-fm", tmp_path)
    assert result.outcome == "retry"
    assert result.exit_code() == EXIT_RETRY


def test_retry_when_yaml_invalid(tmp_path: Path) -> None:
    rel = canonical_artifact_relpath("research", "bad-yaml")
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n: : invalid : yaml :::\n---\nbody\n", encoding="utf-8")
    result = verify("research", "bad-yaml", tmp_path)
    assert result.outcome == "retry"


# ---------------------------------------------------------------------------
# Cross-field rules R1-R7.
# ---------------------------------------------------------------------------


def test_R1_blockers_with_done_status_fails(tmp_path: Path) -> None:
    h = research_header()
    h["blockers"] = [{"description": "x", "severity": "high"}]
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("R1" in e for e in result.errors)


def test_R1_blockers_with_blocked_status_passes(tmp_path: Path) -> None:
    h = research_header()
    h["status"] = "blocked"
    h["blockers"] = [{"description": "missing input", "severity": "high"}]
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert result.passed
    # status=blocked -> escalate
    assert result.outcome == "escalate"
    assert result.exit_code() == EXIT_ESCALATE


def test_R2_done_low_confidence_fails(tmp_path: Path) -> None:
    h = research_header()
    h["confidence"] = 0.5
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("R2" in e for e in result.errors)


def test_R3_confidence_out_of_range_fails(tmp_path: Path) -> None:
    h = research_header()
    h["confidence"] = 1.2
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("R3" in e for e in result.errors)


def test_R3_confidence_non_number_fails(tmp_path: Path) -> None:
    h = research_header()
    h["confidence"] = "high"
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("R3" in e for e in result.errors)


def test_R4_underfunded_inputs_fails(tmp_path: Path) -> None:
    h = research_header()
    h["inputs_used"] = ["a.md", "b.md", "c.md"]
    h["metrics"]["files_read"] = 1
    h["metrics"]["memory_hits"] = 0
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("R4" in e for e in result.errors)


def test_R4_memory_hits_count_toward_coverage(tmp_path: Path) -> None:
    h = research_header()
    h["inputs_used"] = ["a.md", "b.md", "c.md"]
    h["metrics"]["files_read"] = 1
    h["metrics"]["memory_hits"] = 2  # covers the gap via memory
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert result.passed, result.errors


def test_R5_outputs_first_path_mismatch_warns(tmp_path: Path) -> None:
    h = research_header()
    h["outputs_produced"] = ["docs/other-artifact.md"]
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    # R5 is a warning, not a hard fail
    assert result.passed
    assert any("R5" in w for w in result.warnings)


def test_R6_slug_mismatch_fails(tmp_path: Path) -> None:
    h = research_header(slug="other-slug")
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("R6" in e for e in result.errors)


def test_R7_absolute_path_fails(tmp_path: Path) -> None:
    h = research_header()
    h["inputs_used"] = ["/etc/passwd"]
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("R7" in e for e in result.errors)


def test_R7_backslash_path_fails(tmp_path: Path) -> None:
    h = research_header()
    h["inputs_used"] = ["docs\\spec.md"]
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("R7" in e for e in result.errors)


def test_R7_windows_drive_fails(tmp_path: Path) -> None:
    h = research_header()
    h["inputs_used"] = ["c:/spec.md"]
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("R7" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Schema-driven checks.
# ---------------------------------------------------------------------------


def test_unknown_agent_class_fails(tmp_path: Path) -> None:
    result = verify("bogus-class", "x", tmp_path)
    assert not result.passed
    assert result.outcome == "fail"
    assert any("unknown agent class" in e for e in result.errors)


def test_cc_version_mismatch_fails(tmp_path: Path) -> None:
    h = research_header()
    h["cc_version"] = "0.9"
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("cc_version" in e for e in result.errors)


def test_phase_const_mismatch_fails(tmp_path: Path) -> None:
    h = research_header()
    h["phase"] = "analysis"
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("phase" in e for e in result.errors)


def test_empty_agent_field_fails(tmp_path: Path) -> None:
    h = research_header()
    h["agent"] = ""
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed


def test_missing_required_field_fails(tmp_path: Path) -> None:
    h = research_header()
    del h["next_consumer"]
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("next_consumer" in e for e in result.errors)


def test_bad_status_value_fails(tmp_path: Path) -> None:
    h = research_header()
    h["status"] = "in-progress"
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("status" in e for e in result.errors)


def test_trace_owned_metric_in_artifact_fails(tmp_path: Path) -> None:
    h = research_header()
    h["metrics"]["duration_s"] = 12.4
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("duration_s" in e for e in result.errors)


def test_bad_blocker_severity_fails(tmp_path: Path) -> None:
    h = research_header()
    h["status"] = "blocked"
    h["blockers"] = [{"description": "x", "severity": "huge"}]
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed


def test_slug_pattern_violation_fails(tmp_path: Path) -> None:
    h = research_header(slug="Test_Feature")
    write_artifact(tmp_path, "research", "Test_Feature", h)
    result = verify("research", "Test_Feature", tmp_path)
    assert not result.passed
    assert any("kebab-case" in e or "pattern" in e for e in result.errors)


def test_outputs_must_be_non_empty(tmp_path: Path) -> None:
    h = research_header()
    h["outputs_produced"] = []
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed


# ---------------------------------------------------------------------------
# Section presence + aliases.
# ---------------------------------------------------------------------------


def test_missing_required_section_fails(tmp_path: Path) -> None:
    h = research_header()
    body = textwrap.dedent(
        """\
        ## Summary

        x

        ## Coverage

        x
        """
    )
    write_artifact(tmp_path, "research", "test-feature", h, body=body)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed
    assert any("section" in e for e in result.errors)


def test_findings_section_alias_decisions(tmp_path: Path) -> None:
    h = design_header()
    # Custom body: design class allows "Decisions" or "Top relevance" in
    # place of "Findings". But design's per-class sections list doesn't
    # include "Findings" — it requires "Components" and "Implementation plan"
    # instead. So validate that the alias works in classes that DO use it:
    # research-class accepts "Top relevance" instead of "Findings".
    body = textwrap.dedent(
        """\
        ## Summary

        x

        ## Coverage

        x

        ## Top relevance

        x

        ## Assumptions

        x

        ## Open questions

        x

        ## Next consumer brief

        x
        """
    )
    write_artifact(tmp_path, "research", "test-feature", research_header(), body=body)
    result = verify("research", "test-feature", tmp_path)
    assert result.passed, result.errors


def test_open_questions_alias_blockers(tmp_path: Path) -> None:
    h = research_header()
    h["status"] = "blocked"
    h["blockers"] = [{"description": "stuck", "severity": "high"}]
    body = textwrap.dedent(
        """\
        ## Summary

        x

        ## Coverage

        x

        ## Findings

        x

        ## Assumptions

        x

        ## Blockers

        x

        ## Next consumer brief

        x
        """
    )
    write_artifact(tmp_path, "research", "test-feature", h, body=body)
    result = verify("research", "test-feature", tmp_path)
    assert result.passed, result.errors


# ---------------------------------------------------------------------------
# Outcome resolution: escalate vs proceed.
# ---------------------------------------------------------------------------


def test_status_failed_escalates(tmp_path: Path) -> None:
    h = research_header()
    h["status"] = "failed"
    h["confidence"] = 0.3
    h["blockers"] = [{"description": "tool errored", "severity": "critical"}]
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert result.passed
    assert result.outcome == "escalate"
    assert result.exit_code() == EXIT_ESCALATE


def test_gate_decision_escalate_escalates(tmp_path: Path) -> None:
    h = _make_test_header()
    h["gate_decision"] = "escalate"
    write_artifact(tmp_path, "test", "test-feature", h)
    result = verify("test", "test-feature", tmp_path)
    assert result.passed
    assert result.outcome == "escalate"


# ---------------------------------------------------------------------------
# Research-class checks.
# ---------------------------------------------------------------------------


def test_research_invalid_strategy_fails(tmp_path: Path) -> None:
    h = research_header()
    h["coverage_summary"]["strategies"] = ["mystery_method"]
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed


def test_research_empty_strategies_fails(tmp_path: Path) -> None:
    h = research_header()
    h["coverage_summary"]["strategies"] = []
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert not result.passed


def test_research_traceability_mapping_strategy_passes(tmp_path: Path) -> None:
    h = research_header()
    h["coverage_summary"]["strategies"] = ["memory_retrieval", "traceability_mapping"]
    write_artifact(tmp_path, "research", "test-feature", h)
    result = verify("research", "test-feature", tmp_path)
    assert result.passed
    assert result.outcome == "proceed"


# ---------------------------------------------------------------------------
# Analysis-class checks.
# ---------------------------------------------------------------------------


def test_analysis_has_ui_must_be_bool(tmp_path: Path) -> None:
    h = analysis_header()
    h["has_ui"] = "yes"
    write_artifact(tmp_path, "analysis", "test-feature", h)
    result = verify("analysis", "test-feature", tmp_path)
    assert not result.passed
    assert any("has_ui" in e for e in result.errors)


def test_analysis_duplicate_requirement_ids_fail(tmp_path: Path) -> None:
    h = analysis_header()
    h["traceability"] = [
        {
            "requirement_id": "R1",
            "statement": "x",
            "acceptance_criteria": ["a"],
            "verifying_phase": "test",
        },
        {
            "requirement_id": "R1",  # duplicate
            "statement": "y",
            "acceptance_criteria": ["b"],
            "verifying_phase": "test",
        },
    ]
    write_artifact(tmp_path, "analysis", "test-feature", h)
    result = verify("analysis", "test-feature", tmp_path)
    assert not result.passed
    assert any("duplicated" in e for e in result.errors)


def test_analysis_bad_requirement_id_pattern(tmp_path: Path) -> None:
    h = analysis_header()
    h["traceability"][0]["requirement_id"] = "REQ-1"
    write_artifact(tmp_path, "analysis", "test-feature", h)
    result = verify("analysis", "test-feature", tmp_path)
    assert not result.passed


def test_analysis_bad_verifying_phase(tmp_path: Path) -> None:
    h = analysis_header()
    h["traceability"][0]["verifying_phase"] = "scout"
    write_artifact(tmp_path, "analysis", "test-feature", h)
    result = verify("analysis", "test-feature", tmp_path)
    assert not result.passed


# ---------------------------------------------------------------------------
# Design-class checks.
# ---------------------------------------------------------------------------


def test_design_empty_risks_fails(tmp_path: Path) -> None:
    h = design_header()
    h["risks"] = []
    write_artifact(tmp_path, "design", "test-feature", h)
    result = verify("design", "test-feature", tmp_path)
    assert not result.passed


def test_design_placeholder_validation_command_fails(tmp_path: Path) -> None:
    h = design_header()
    h["iterations"][0]["validation_command"] = "TODO"
    write_artifact(tmp_path, "design", "test-feature", h)
    result = verify("design", "test-feature", tmp_path)
    assert not result.passed
    assert any("placeholder" in e for e in result.errors)


def test_design_dangling_depends_on_fails(tmp_path: Path) -> None:
    h = design_header()
    h["iterations"][0]["depends_on"] = ["I99"]
    write_artifact(tmp_path, "design", "test-feature", h)
    result = verify("design", "test-feature", tmp_path)
    assert not result.passed
    assert any("depends_on" in e or "unknown" in e for e in result.errors)


def test_design_duplicate_iteration_id_fails(tmp_path: Path) -> None:
    h = design_header()
    h["iterations"] = [
        {
            "id": "I1",
            "type": "backend",
            "scope_files": ["a.py"],
            "validation_command": "pytest",
            "depends_on": [],
        },
        {
            "id": "I1",  # duplicate
            "type": "frontend",
            "scope_files": ["b.tsx"],
            "validation_command": "npm test",
            "depends_on": [],
        },
    ]
    write_artifact(tmp_path, "design", "test-feature", h)
    result = verify("design", "test-feature", tmp_path)
    assert not result.passed


def test_design_iterations_planned_mismatch_fails(tmp_path: Path) -> None:
    h = design_header()
    h["metrics"]["iterations_planned"] = 99
    write_artifact(tmp_path, "design", "test-feature", h)
    result = verify("design", "test-feature", tmp_path)
    assert not result.passed


# ---------------------------------------------------------------------------
# Implementation-class checks (R-impl-1..6).
# ---------------------------------------------------------------------------


def test_R_impl_1_bad_iteration_id_pattern(tmp_path: Path) -> None:
    h = impl_header()
    h["iteration_id"] = "iter1"
    write_artifact(tmp_path, "implementation", "test-feature--i1", h)
    result = verify("implementation", "test-feature--i1", tmp_path)
    assert not result.passed
    assert any("R-impl-1" in e for e in result.errors)


def test_R_impl_2_slug_suffix_mismatch(tmp_path: Path) -> None:
    h = impl_header(slug="test-feature--i2")
    h["iteration_id"] = "I3"  # mismatch with slug suffix
    write_artifact(tmp_path, "implementation", "test-feature--i2", h)
    result = verify("implementation", "test-feature--i2", tmp_path)
    assert not result.passed
    assert any("R-impl-2" in e for e in result.errors)


def test_R_impl_3_empty_files_changed_with_done_fails(tmp_path: Path) -> None:
    h = impl_header()
    h["files_changed"] = []
    write_artifact(tmp_path, "implementation", "test-feature--i1", h)
    result = verify("implementation", "test-feature--i1", tmp_path)
    assert not result.passed
    assert any("R-impl-3" in e for e in result.errors)


def test_R_impl_4_validation_command_passed_must_be_bool(tmp_path: Path) -> None:
    h = impl_header()
    h["validation_command_passed"] = "true"  # string, not bool
    write_artifact(tmp_path, "implementation", "test-feature--i1", h)
    result = verify("implementation", "test-feature--i1", tmp_path)
    assert not result.passed
    assert any("R-impl-4" in e for e in result.errors)


def test_R_impl_5_failed_validation_with_done_fails(tmp_path: Path) -> None:
    h = impl_header()
    h["validation_command_passed"] = False
    write_artifact(tmp_path, "implementation", "test-feature--i1", h)
    result = verify("implementation", "test-feature--i1", tmp_path)
    assert not result.passed
    assert any("R-impl-5" in e for e in result.errors)


def test_R_impl_6_negative_diff_lines_fails(tmp_path: Path) -> None:
    h = impl_header()
    h["metrics"]["diff_lines_added"] = -1
    write_artifact(tmp_path, "implementation", "test-feature--i1", h)
    result = verify("implementation", "test-feature--i1", tmp_path)
    assert not result.passed
    assert any("R-impl-6" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Test-class checks (R-val-1..4).
# ---------------------------------------------------------------------------


def test_R_val_1_bad_gate_decision_fails(tmp_path: Path) -> None:
    h = _make_test_header()
    h["gate_decision"] = "maybe"
    write_artifact(tmp_path, "test", "test-feature", h)
    result = verify("test", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-val-1" in e for e in result.errors)


def test_R_val_2_negative_passed_count_fails(tmp_path: Path) -> None:
    h = _make_test_header()
    h["passed"] = -1
    write_artifact(tmp_path, "test", "test-feature", h)
    result = verify("test", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-val-2" in e for e in result.errors)


def test_R_val_3_pass_with_failed_gt_zero_fails(tmp_path: Path) -> None:
    h = _make_test_header()
    h["gate_decision"] = "pass"
    h["failed"] = 3
    write_artifact(tmp_path, "test", "test-feature", h)
    result = verify("test", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-val-3" in e for e in result.errors)


def test_R_val_4_gate_fail_with_status_done_is_valid(tmp_path: Path) -> None:
    """A test gate that ran cleanly but the suite failed is a coherent state."""
    h = _make_test_header()
    h["gate_decision"] = "fail"
    h["failed"] = 5
    h["passed"] = 37
    write_artifact(tmp_path, "test", "test-feature", h)
    result = verify("test", "test-feature", tmp_path)
    assert result.passed, result.errors


# ---------------------------------------------------------------------------
# Review-class checks (R-rev-1..6).
# ---------------------------------------------------------------------------


def test_R_rev_1_bad_verdict_fails(tmp_path: Path) -> None:
    h = review_header()
    h["verdict"] = "approved"
    write_artifact(tmp_path, "review", "test-feature", h)
    result = verify("review", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-rev-1" in e for e in result.errors)


def test_R_rev_2_bad_finding_id_pattern(tmp_path: Path) -> None:
    h = review_header()
    h["verdict"] = "needs_fix"
    h["findings"] = [
        {
            "id": "finding-1",  # bad
            "severity": "high",
            "file": "app/foo.py:42",
            "evidence": "x",
            "blocking": False,
            "suggested_action": "fix it",
        }
    ]
    write_artifact(tmp_path, "review", "test-feature", h)
    result = verify("review", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-rev-2" in e for e in result.errors)


def test_R_rev_3_duplicate_finding_id_fails(tmp_path: Path) -> None:
    h = review_header()
    h["verdict"] = "needs_fix"
    h["findings"] = [
        {
            "id": "F1",
            "severity": "high",
            "file": "app/foo.py",
            "evidence": "x",
            "blocking": False,
            "suggested_action": "fix",
        },
        {
            "id": "F1",  # duplicate
            "severity": "low",
            "file": "app/bar.py",
            "evidence": "y",
            "blocking": False,
            "suggested_action": "fix",
        },
    ]
    write_artifact(tmp_path, "review", "test-feature", h)
    result = verify("review", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-rev-3" in e for e in result.errors)


def test_R_rev_4_pass_with_blocking_finding_fails(tmp_path: Path) -> None:
    h = review_header()
    h["verdict"] = "pass"
    h["findings"] = [
        {
            "id": "F1",
            "severity": "high",
            "file": "app/foo.py",
            "evidence": "x",
            "blocking": True,  # incoherent with verdict=pass
            "suggested_action": "fix",
        }
    ]
    write_artifact(tmp_path, "review", "test-feature", h)
    result = verify("review", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-rev-4" in e for e in result.errors)


def test_R_rev_6_bad_finding_severity(tmp_path: Path) -> None:
    h = review_header()
    h["verdict"] = "needs_fix"
    h["findings"] = [
        {
            "id": "F1",
            "severity": "blocker",  # not in enum
            "file": "app/foo.py",
            "evidence": "x",
            "blocking": False,
            "suggested_action": "fix",
        }
    ]
    write_artifact(tmp_path, "review", "test-feature", h)
    result = verify("review", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-rev-6" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Doc-class checks (R-doc-1..5).
# ---------------------------------------------------------------------------


def test_R_doc_1_first_output_must_be_report(tmp_path: Path) -> None:
    h = doc_header()
    h["outputs_produced"] = ["docs/feature.md", canonical_artifact_relpath("doc", "test-feature")]
    write_artifact(tmp_path, "doc", "test-feature", h)
    result = verify("doc", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-doc-1" in e for e in result.errors)


def test_R_doc_3_intentionally_not_updated_required(tmp_path: Path) -> None:
    h = doc_header()
    del h["intentionally_not_updated"]
    write_artifact(tmp_path, "doc", "test-feature", h)
    result = verify("doc", "test-feature", tmp_path)
    assert not result.passed


def test_R_doc_4_no_op_doc_run_requires_skipped_docs(tmp_path: Path) -> None:
    h = doc_header()
    h["outputs_produced"] = [canonical_artifact_relpath("doc", "test-feature")]
    h["metrics"]["docs_updated"] = 0
    h["intentionally_not_updated"] = []
    write_artifact(tmp_path, "doc", "test-feature", h)
    result = verify("doc", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-doc-4" in e for e in result.errors)


def test_R_doc_5_docs_updated_metric_mismatch(tmp_path: Path) -> None:
    h = doc_header()
    h["metrics"]["docs_updated"] = 5  # actual is 1
    write_artifact(tmp_path, "doc", "test-feature", h)
    result = verify("doc", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-doc-5" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Retro-class checks (R-retro-1..4).
# ---------------------------------------------------------------------------


def test_R_retro_1_extra_output_entry_fails(tmp_path: Path) -> None:
    h = retro_header()
    h["outputs_produced"] = [
        canonical_artifact_relpath("retro", "test-feature"),
        "docs/should-not-be-here.md",
    ]
    write_artifact(tmp_path, "retro", "test-feature", h)
    result = verify("retro", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-retro-1" in e for e in result.errors)


def test_R_retro_2_fix_type_must_be_in_enum(tmp_path: Path) -> None:
    h = retro_header()
    h["findings"][0]["fix_type"] = "rewrite_orchestrator"
    write_artifact(tmp_path, "retro", "test-feature", h)
    result = verify("retro", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-retro-2" in e for e in result.errors)


def test_R_retro_3_scores_missing_dimension_fails(tmp_path: Path) -> None:
    h = retro_header()
    del h["scores"]["communication"]
    write_artifact(tmp_path, "retro", "test-feature", h)
    result = verify("retro", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-retro-3" in e for e in result.errors)


def test_R_retro_3_score_out_of_range_fails(tmp_path: Path) -> None:
    h = retro_header()
    h["scores"]["planning"] = 7
    write_artifact(tmp_path, "retro", "test-feature", h)
    result = verify("retro", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-retro-3" in e for e in result.errors)


def test_R_retro_4_duplicate_finding_id_fails(tmp_path: Path) -> None:
    h = retro_header()
    h["findings"].append(
        {
            "id": "F1",  # duplicate
            "severity": "low",
            "fix_type": "normalize_rule",
            "target": "normalize:trailing_whitespace",
            "evidence": "Trailing whitespace in slugs across scout reports.",
            "suggested_action": "Strip trailing whitespace in normalize.py.",
        }
    )
    write_artifact(tmp_path, "retro", "test-feature", h)
    result = verify("retro", "test-feature", tmp_path)
    assert not result.passed
    assert any("R-retro-4" in e for e in result.errors)


def test_retro_finding_missing_target_fails(tmp_path: Path) -> None:
    h = retro_header()
    del h["findings"][0]["target"]
    write_artifact(tmp_path, "retro", "test-feature", h)
    result = verify("retro", "test-feature", tmp_path)
    assert not result.passed


# ---------------------------------------------------------------------------
# CLI exit codes + JSON output mode.
# ---------------------------------------------------------------------------


def test_cli_exit_code_proceed(tmp_path: Path, capsys) -> None:
    write_artifact(tmp_path, "research", "test-feature", research_header())
    code = main(
        [
            "--agent", "research",
            "--slug", "test-feature",
            "--space", str(tmp_path),
        ]
    )
    assert code == EXIT_PROCEED
    out = capsys.readouterr().out
    assert "PROCEED" in out


def test_cli_exit_code_fail(tmp_path: Path) -> None:
    h = research_header()
    h["confidence"] = 0.3  # R2 fail
    write_artifact(tmp_path, "research", "test-feature", h)
    code = main(
        [
            "--agent", "research",
            "--slug", "test-feature",
            "--space", str(tmp_path),
        ]
    )
    assert code == EXIT_FAIL


def test_cli_exit_code_escalate(tmp_path: Path) -> None:
    h = research_header()
    h["status"] = "blocked"
    h["blockers"] = [{"description": "x", "severity": "high"}]
    write_artifact(tmp_path, "research", "test-feature", h)
    code = main(
        [
            "--agent", "research",
            "--slug", "test-feature",
            "--space", str(tmp_path),
        ]
    )
    assert code == EXIT_ESCALATE


def test_cli_exit_code_retry(tmp_path: Path) -> None:
    code = main(
        [
            "--agent", "research",
            "--slug", "no-such-feature",
            "--space", str(tmp_path),
        ]
    )
    assert code == EXIT_RETRY


def test_cli_json_output(tmp_path: Path, capsys) -> None:
    write_artifact(tmp_path, "research", "test-feature", research_header())
    code = main(
        [
            "--agent", "research",
            "--slug", "test-feature",
            "--space", str(tmp_path),
            "--json",
        ]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["passed"] is True
    assert payload["outcome"] == "proceed"
    assert payload["exit_code"] == EXIT_PROCEED
    assert code == EXIT_PROCEED


def test_cli_invalid_space_dir_returns_retry(tmp_path: Path, capsys) -> None:
    bogus = tmp_path / "does-not-exist"
    code = main(
        [
            "--agent", "research",
            "--slug", "test-feature",
            "--space", str(bogus),
        ]
    )
    assert code == EXIT_RETRY


def test_cli_normalize_flag_runs_normalizer_and_proceeds(
    tmp_path: Path, capsys
) -> None:
    """--normalize runs the normalizer then verifies; a clean artifact proceeds."""
    write_artifact(tmp_path, "research", "test-feature", research_header())
    code = main(
        [
            "--agent", "research",
            "--slug", "test-feature",
            "--space", str(tmp_path),
            "--normalize",
        ]
    )
    assert code == EXIT_PROCEED


def test_cli_normalize_json_includes_normalize_key(
    tmp_path: Path, capsys
) -> None:
    """--normalize --json output includes a 'normalize' key from the normalizer."""
    write_artifact(tmp_path, "research", "test-feature", research_header())
    code = main(
        [
            "--agent", "research",
            "--slug", "test-feature",
            "--space", str(tmp_path),
            "--normalize",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == EXIT_PROCEED
    assert "normalize" in payload
    assert payload["normalize"]["modified"] is False
    assert payload["normalize"]["error"] is None


def test_cli_via_subprocess_matches_module_main(tmp_path: Path) -> None:
    """Sanity-check `python -m app.pipeline.verify` mirrors the in-process CLI."""
    write_artifact(tmp_path, "research", "test-feature", research_header())
    proc = subprocess.run(
        [
            sys.executable, "-m", "app.pipeline.verify",
            "--agent", "research",
            "--slug", "test-feature",
            "--space", str(tmp_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == EXIT_PROCEED, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["passed"] is True
