"""Tests for the CC-v1 pipeline normalizer (app.pipeline.normalize).

Cover every drift class in the auto-fix table:
  - blocker_string_wrap
  - strategy_synonym / strategy_unknown_drop
  - section_case_canonical
  - status_partial_to_blocked
  - path_backslash_to_slash

Also covers:
  - Dry-run mode (no write back)
  - JSON output flag via CLI
  - Hard-fail cases the normalizer must NOT fix
  - verify.py --normalize integration (round-trip)
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
import yaml

from app.pipeline.normalize import NormalizeResult, normalize
from app.pipeline.verify import (
    CLASS_CONFIG,
    EXIT_PROCEED,
    EXIT_RETRY,
    canonical_artifact_relpath,
    main as verify_main,
)
from app.pipeline.normalize import main as normalize_main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_artifact(
    space: Path,
    class_name: str,
    slug: str,
    header: dict,
    body: str | None = None,
) -> Path:
    rel = canonical_artifact_relpath(class_name, slug)
    path = space / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if body is None:
        body = _default_body(class_name)
    text = "---\n" + yaml.safe_dump(header, sort_keys=False) + "---\n\n" + body
    path.write_text(text, encoding="utf-8")
    return path


def read_header(space: Path, class_name: str, slug: str) -> dict:
    rel = canonical_artifact_relpath(class_name, slug)
    path = space / rel
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    block = text[3:end].strip()
    return yaml.safe_load(block)


def _default_body(class_name: str) -> str:
    sections = {
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
    }
    names = sections.get(class_name, sections["research"])
    return "".join(f"## {s}\n\nContent.\n\n" for s in names)


def _minimal_research_header(slug: str = "my-feature") -> dict:
    return {
        "cc_version": "1.0",
        "agent": "scout",
        "slug": slug,
        "phase": "scout",
        "status": "done",
        "confidence": 0.9,
        "inputs_used": ["backend/app/main.py"],
        "outputs_produced": [
            f".cronos/pipeline/{slug}/scout-report-{slug}.md"
        ],
        "blockers": [],
        "next_consumer": "analysis",
        "metrics": {
            "tool_calls": 5,
            "files_read": 1,
            "memory_hits": 0,
        },
        "coverage_summary": {
            "searched": ["backend/"],
            "excluded": [],
            "strategies": ["read_targeted"],
        },
    }


# ---------------------------------------------------------------------------
# blocker_string_wrap
# ---------------------------------------------------------------------------


class TestBlockerStringWrap:
    def test_bare_string_wrapped(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["status"] = "blocked"
        h["blockers"] = ["some problem"]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        assert r.modified is True
        assert any("blockers[0]" in f and "wrapped" in f for f in r.fixes_applied)
        saved = read_header(tmp_path, "research", "my-feature")
        assert saved["blockers"][0] == {
            "description": "some problem",
            "severity": "medium",
        }

    def test_multiple_strings_all_wrapped(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["status"] = "blocked"
        h["blockers"] = ["problem A", "problem B"]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        assert r.modified is True
        assert len([f for f in r.fixes_applied if "blockers[" in f]) == 2

    def test_already_dict_not_re_wrapped(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["status"] = "blocked"
        h["blockers"] = [{"description": "issue", "severity": "high"}]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        assert not any("blockers" in f and "wrapped" in f for f in r.fixes_applied)


# ---------------------------------------------------------------------------
# status_partial_to_blocked
# ---------------------------------------------------------------------------


class TestStatusCoerce:
    def test_partial_with_blockers_coerced(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["status"] = "partial"
        h["blockers"] = ["timeout issue"]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        assert r.modified is True
        assert any("'partial' -> 'blocked'" in f for f in r.fixes_applied)
        saved = read_header(tmp_path, "research", "my-feature")
        assert saved["status"] == "blocked"

    def test_partial_no_blockers_not_coerced(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["status"] = "partial"
        h["blockers"] = []
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        saved = read_header(tmp_path, "research", "my-feature")
        assert saved["status"] == "partial"

    def test_done_with_blockers_is_unfixable(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["status"] = "done"
        h["blockers"] = [{"description": "issue", "severity": "medium"}]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        assert any("done" in u and "ambiguous" in u for u in r.unfixable_issues)
        saved = read_header(tmp_path, "research", "my-feature")
        assert saved["status"] == "done"


# ---------------------------------------------------------------------------
# path_backslash_to_slash
# ---------------------------------------------------------------------------


class TestPathBackslash:
    def test_inputs_used_backslash_fixed(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["inputs_used"] = ["backend\\app\\main.py"]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        assert r.modified is True
        assert any("inputs_used[0]" in f and "backslash" in f for f in r.fixes_applied)
        saved = read_header(tmp_path, "research", "my-feature")
        assert saved["inputs_used"][0] == "backend/app/main.py"

    def test_outputs_produced_backslash_fixed(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["outputs_produced"] = [".cronos\\pipeline\\my-feature\\scout-report-my-feature.md"]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        saved = read_header(tmp_path, "research", "my-feature")
        assert "\\" not in saved["outputs_produced"][0]

    def test_url_not_mangled(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["inputs_used"] = ["https://example.com/path\\info"]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        saved = read_header(tmp_path, "research", "my-feature")
        assert saved["inputs_used"][0] == "https://example.com/path\\info"

    def test_files_changed_backslash_fixed(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["files_changed"] = ["backend\\app\\main.py"]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        saved = read_header(tmp_path, "research", "my-feature")
        assert saved["files_changed"][0] == "backend/app/main.py"


# ---------------------------------------------------------------------------
# strategy_synonym / strategy_unknown_drop
# ---------------------------------------------------------------------------


class TestStrategyNormalise:
    def test_kbsearch_synonym_mapped_to_memory_retrieval(
        self, tmp_path: Path
    ) -> None:
        h = _minimal_research_header()
        h["coverage_summary"]["strategies"] = ["kb_search", "read_targeted"]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        assert r.modified is True
        saved = read_header(tmp_path, "research", "my-feature")
        assert "memory_retrieval" in saved["coverage_summary"]["strategies"]
        assert "kb_search" not in saved["coverage_summary"]["strategies"]

    def test_webfetch_synonym_mapped(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["coverage_summary"]["strategies"] = ["webFetch", "read_targeted"]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        saved = read_header(tmp_path, "research", "my-feature")
        assert "fetch_url" in saved["coverage_summary"]["strategies"]

    def test_unknown_strategy_dropped(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["coverage_summary"]["strategies"] = [
            "read_targeted",
            "documented spec knowledge",
        ]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        assert any("dropped unknown" in f for f in r.fixes_applied)
        saved = read_header(tmp_path, "research", "my-feature")
        assert "documented spec knowledge" not in saved["coverage_summary"]["strategies"]

    def test_canonical_strategy_unchanged(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["coverage_summary"]["strategies"] = ["memory_retrieval", "grep_symbol"]
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        assert not any("strategies" in f for f in r.fixes_applied)


# ---------------------------------------------------------------------------
# section_case_canonical
# ---------------------------------------------------------------------------


class TestSectionCasing:
    def test_open_questions_title_case_fixed(self, tmp_path: Path) -> None:
        body = textwrap.dedent("""\
            ## Summary

            Content.

            ## Coverage

            Content.

            ## Findings

            Content.

            ## Assumptions

            Content.

            ## Open Questions

            Content.

            ## Next consumer brief

            Content.
        """)
        h = _minimal_research_header()
        write_artifact(tmp_path, "research", "my-feature", h, body=body)

        r = normalize("research", "my-feature", tmp_path)

        assert r.modified is True
        assert any("Open Questions" in f and "Open questions" in f for f in r.fixes_applied)
        rel = canonical_artifact_relpath("research", "my-feature")
        saved_text = (tmp_path / rel).read_text()
        assert "## Open questions" in saved_text
        assert "## Open Questions" not in saved_text

    def test_all_caps_summary_fixed(self, tmp_path: Path) -> None:
        body = _default_body("research").replace("## Summary", "## SUMMARY")
        h = _minimal_research_header()
        write_artifact(tmp_path, "research", "my-feature", h, body=body)

        r = normalize("research", "my-feature", tmp_path)

        assert r.modified is True
        rel = canonical_artifact_relpath("research", "my-feature")
        saved_text = (tmp_path / rel).read_text()
        assert "## Summary" in saved_text
        assert "## SUMMARY" not in saved_text

    def test_already_canonical_sections_unchanged(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        write_artifact(tmp_path, "research", "my-feature", h)

        r = normalize("research", "my-feature", tmp_path)

        assert not any("section header" in f for f in r.fixes_applied)

    def test_deeper_headings_not_touched(self, tmp_path: Path) -> None:
        body = _default_body("research")
        body = body.replace("## Summary\n", "## Summary\n\n### Open Questions\n\n")
        h = _minimal_research_header()
        write_artifact(tmp_path, "research", "my-feature", h, body=body)

        r = normalize("research", "my-feature", tmp_path)

        rel = canonical_artifact_relpath("research", "my-feature")
        saved_text = (tmp_path / rel).read_text()
        assert "### Open Questions" in saved_text


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_reports_but_does_not_write(self, tmp_path: Path) -> None:
        h = _minimal_research_header()
        h["status"] = "partial"
        h["blockers"] = ["problem"]
        write_artifact(tmp_path, "research", "my-feature", h)
        rel = canonical_artifact_relpath("research", "my-feature")
        original_text = (tmp_path / rel).read_text()

        r = normalize("research", "my-feature", tmp_path, dry_run=True)

        assert r.modified is True
        assert any("'partial' -> 'blocked'" in f for f in r.fixes_applied)
        assert (tmp_path / rel).read_text() == original_text


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    def test_artifact_not_found_returns_error(self, tmp_path: Path) -> None:
        r = normalize("research", "no-such-slug", tmp_path)
        assert r.error is not None
        assert "artifact not found" in r.error
        assert r.modified is False

    def test_unknown_agent_class_returns_error(self, tmp_path: Path) -> None:
        r = normalize("badclass", "my-feature", tmp_path)
        assert r.error is not None
        assert "unknown agent class" in r.error

    def test_no_frontmatter_returns_error(self, tmp_path: Path) -> None:
        rel = canonical_artifact_relpath("research", "my-feature")
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("No frontmatter here.\n", encoding="utf-8")

        r = normalize("research", "my-feature", tmp_path)

        assert r.error is not None
        assert "no YAML front-matter" in r.error


# ---------------------------------------------------------------------------
# to_dict coverage
# ---------------------------------------------------------------------------


class TestToDict:
    def test_to_dict_schema(self, tmp_path: Path) -> None:
        r = normalize("research", "no-slug", tmp_path)
        d = r.to_dict()
        for key in ("agent", "slug", "artifact_path", "modified",
                    "fixes_applied", "unfixable_issues", "error"):
            assert key in d


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


class TestCLI:
    def test_cli_dry_run_flag(self, tmp_path: Path, capsys) -> None:
        h = _minimal_research_header()
        h["status"] = "partial"
        h["blockers"] = ["issue"]
        write_artifact(tmp_path, "research", "my-feature", h)

        rc = normalize_main([
            "--agent", "research",
            "--slug", "my-feature",
            "--space", str(tmp_path),
            "--dry-run",
        ])

        assert rc == 0
        out = capsys.readouterr().out
        assert "DRY-RUN" in out

    def test_cli_json_flag(self, tmp_path: Path, capsys) -> None:
        h = _minimal_research_header()
        write_artifact(tmp_path, "research", "my-feature", h)

        rc = normalize_main([
            "--agent", "research",
            "--slug", "my-feature",
            "--space", str(tmp_path),
            "--json",
        ])

        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["modified"] is False
        assert payload["error"] is None

    def test_cli_bad_space_returns_2(self, tmp_path: Path, capsys) -> None:
        rc = normalize_main([
            "--agent", "research",
            "--slug", "my-feature",
            "--space", str(tmp_path / "no-such-dir"),
        ])
        assert rc == 2

    def test_cli_artifact_not_found_returns_1(self, tmp_path: Path, capsys) -> None:
        rc = normalize_main([
            "--agent", "research",
            "--slug", "my-feature",
            "--space", str(tmp_path),
        ])
        assert rc == 1

    def test_cli_no_drift_message(self, tmp_path: Path, capsys) -> None:
        h = _minimal_research_header()
        write_artifact(tmp_path, "research", "my-feature", h)

        normalize_main([
            "--agent", "research",
            "--slug", "my-feature",
            "--space", str(tmp_path),
        ])

        out = capsys.readouterr().out
        assert "no drift detected" in out

    def test_cli_modified_label(self, tmp_path: Path, capsys) -> None:
        h = _minimal_research_header()
        h["status"] = "partial"
        h["blockers"] = ["issue"]
        write_artifact(tmp_path, "research", "my-feature", h)

        normalize_main([
            "--agent", "research",
            "--slug", "my-feature",
            "--space", str(tmp_path),
        ])

        out = capsys.readouterr().out
        assert "MODIFIED" in out


# ---------------------------------------------------------------------------
# Round-trip: normalize then verify
# ---------------------------------------------------------------------------


class TestNormalizeThenVerify:
    def test_partial_with_blockers_coerced_then_verifies(
        self, tmp_path: Path
    ) -> None:
        """A 'partial + blockers' artifact normalizes to 'blocked' and verifies."""
        h = _minimal_research_header()
        h["status"] = "partial"
        h["blockers"] = ["upstream dep missing"]
        write_artifact(tmp_path, "research", "my-feature", h)

        # Normalize in place.
        r = normalize("research", "my-feature", tmp_path)
        assert r.modified is True

        # After normalization the artifact should verify as escalate (blocked).
        from app.pipeline.verify import EXIT_ESCALATE, verify
        vr = verify("research", "my-feature", tmp_path)
        assert vr.passed is True
        assert vr.outcome == "escalate"

    def test_blocker_string_then_verifies(self, tmp_path: Path) -> None:
        """Bare-string blocker is wrapped → verifier accepts the shape."""
        h = _minimal_research_header()
        h["status"] = "blocked"
        h["blockers"] = ["missing dep"]
        write_artifact(tmp_path, "research", "my-feature", h)

        normalize("research", "my-feature", tmp_path)

        from app.pipeline.verify import verify
        vr = verify("research", "my-feature", tmp_path)
        assert vr.passed is True

    def test_backslash_path_then_verifies(self, tmp_path: Path) -> None:
        """Backslash paths are fixed → R7 verifier check passes."""
        h = _minimal_research_header()
        h["inputs_used"] = ["backend\\app\\main.py"]
        h["metrics"]["files_read"] = 1
        write_artifact(tmp_path, "research", "my-feature", h)

        normalize("research", "my-feature", tmp_path)

        from app.pipeline.verify import verify
        vr = verify("research", "my-feature", tmp_path)
        assert vr.passed is True

    def test_via_verify_normalize_flag(self, tmp_path: Path) -> None:
        """verify --normalize round-trip: drifted artifact fixed and proceeds."""
        h = _minimal_research_header()
        h["status"] = "partial"
        h["blockers"] = ["upstream missing"]
        write_artifact(tmp_path, "research", "my-feature", h)

        code = verify_main([
            "--agent", "research",
            "--slug", "my-feature",
            "--space", str(tmp_path),
            "--normalize",
        ])
        # After normalisation: blocked + valid → escalate (2).
        from app.pipeline.verify import EXIT_ESCALATE
        assert code == EXIT_ESCALATE
