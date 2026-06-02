"""Tests for app.pipeline.known_issues.

Covers:
- append_issue: assigns sequential F-NN numbers
- append_issue: validates severity and status
- append_issue: produces well-formed markdown entry
- append_issue: round-trips (multiple appends stay sequential)
- append_issue: raises FileNotFoundError for missing catalog
- _next_fnum: handles empty catalog and existing entries
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.pipeline.known_issues import (
    VALID_SEVERITIES,
    VALID_STATUSES,
    _next_fnum,
    append_issue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_HEADER = """\
# CC-v1 Pipeline Known Issues

Findings catalog.

"""

SEED_WITH_F01 = MINIMAL_HEADER + """\
---

## F-01 — First issue

**Status**: Open (2026-01-01) | **Affects**: all phases
**Severity**: Low

Some description.

**Workaround**: Do something.
"""


# ---------------------------------------------------------------------------
# _next_fnum
# ---------------------------------------------------------------------------

class TestNextFnum:
    def test_empty_catalog_returns_f01(self):
        assert _next_fnum(MINIMAL_HEADER) == "F-01"

    def test_existing_f01_returns_f02(self):
        assert _next_fnum(SEED_WITH_F01) == "F-02"

    def test_padded_two_digits(self):
        text = MINIMAL_HEADER
        for i in range(1, 10):
            text += f"\n## F-{i:02d} — Issue {i}\n"
        assert _next_fnum(text) == "F-10"

    def test_sparse_numbering_picks_max_plus_one(self):
        # F-03 and F-07 present → next should be F-08
        text = MINIMAL_HEADER + "\n## F-03 — A\n\n## F-07 — B\n"
        assert _next_fnum(text) == "F-08"

    def test_accepts_en_dash_separator(self):
        # en-dash (–) variant
        text = MINIMAL_HEADER + "\n## F-05 – Title\n"
        assert _next_fnum(text) == "F-06"


# ---------------------------------------------------------------------------
# append_issue — validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_invalid_severity_raises(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        with pytest.raises(ValueError, match="severity"):
            append_issue(
                "Title",
                "Desc",
                affects="all",
                severity="critical",  # not a valid value
                workaround="none",
                path=catalog,
            )

    def test_invalid_status_raises(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        with pytest.raises(ValueError, match="status"):
            append_issue(
                "Title",
                "Desc",
                affects="all",
                severity="medium",
                workaround="none",
                status="unknown",
                path=catalog,
            )

    def test_missing_catalog_raises(self, tmp_path):
        missing = tmp_path / "nonexistent.md"
        with pytest.raises(FileNotFoundError):
            append_issue(
                "Title",
                "Desc",
                affects="all",
                severity="low",
                workaround="none",
                path=missing,
            )

    @pytest.mark.parametrize("severity", sorted(VALID_SEVERITIES))
    def test_all_valid_severities_accepted(self, tmp_path, severity):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        fnum = append_issue(
            "Title",
            "Desc",
            affects="all",
            severity=severity,
            workaround="none",
            path=catalog,
        )
        assert fnum == "F-01"

    @pytest.mark.parametrize("status", sorted(VALID_STATUSES))
    def test_all_valid_statuses_accepted(self, tmp_path, status):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        fnum = append_issue(
            "Title",
            "Desc",
            affects="all",
            severity="low",
            workaround="none",
            status=status,
            path=catalog,
        )
        assert fnum == "F-01"


# ---------------------------------------------------------------------------
# append_issue — content
# ---------------------------------------------------------------------------

class TestAppendContent:
    def test_returns_correct_fnum_on_empty_catalog(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        fnum = append_issue(
            "My Issue",
            "Body text.",
            affects="pipeline-gate skill",
            severity="medium",
            workaround="Do X.",
            path=catalog,
        )
        assert fnum == "F-01"

    def test_heading_contains_fnum_and_title(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        append_issue(
            "My Issue",
            "Body text.",
            affects="pipeline-gate skill",
            severity="medium",
            workaround="Do X.",
            path=catalog,
        )
        text = catalog.read_text(encoding="utf-8")
        assert "## F-01 — My Issue" in text

    def test_status_line_format(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        append_issue(
            "Issue",
            "Desc.",
            affects="all phases",
            severity="high",
            workaround="Workaround text.",
            status="investigating",
            today="2026-05-30",
            path=catalog,
        )
        text = catalog.read_text(encoding="utf-8")
        assert "**Status**: Investigating (2026-05-30) | **Affects**: all phases" in text

    def test_severity_line_format(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        append_issue(
            "Issue",
            "Desc.",
            affects="all",
            severity="blocking",
            workaround="Reboot.",
            path=catalog,
        )
        text = catalog.read_text(encoding="utf-8")
        assert "**Severity**: Blocking" in text

    def test_workaround_in_output(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        append_issue(
            "Issue",
            "Desc.",
            affects="all",
            severity="low",
            workaround="Use the --verbose flag.",
            path=catalog,
        )
        text = catalog.read_text(encoding="utf-8")
        assert "**Workaround**: Use the --verbose flag." in text

    def test_description_body_in_output(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        append_issue(
            "Issue",
            "Detailed explanation of the root cause.",
            affects="all",
            severity="medium",
            workaround="None yet.",
            path=catalog,
        )
        text = catalog.read_text(encoding="utf-8")
        assert "Detailed explanation of the root cause." in text

    def test_separator_dashes_added(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER.rstrip(), encoding="utf-8")
        append_issue(
            "Issue",
            "Desc.",
            affects="all",
            severity="low",
            workaround="None.",
            path=catalog,
        )
        text = catalog.read_text(encoding="utf-8")
        assert "\n---\n" in text


# ---------------------------------------------------------------------------
# append_issue — sequential numbering
# ---------------------------------------------------------------------------

class TestSequentialNumbering:
    def test_second_append_gets_f02(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        append_issue("First", "D1.", affects="a", severity="low", workaround="w", path=catalog)
        fnum = append_issue("Second", "D2.", affects="b", severity="medium", workaround="w2", path=catalog)
        assert fnum == "F-02"

    def test_five_appends_are_sequential(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        fnums = []
        for i in range(5):
            fn = append_issue(
                f"Issue {i}",
                f"Desc {i}.",
                affects="all",
                severity="low",
                workaround="none",
                path=catalog,
            )
            fnums.append(fn)
        assert fnums == ["F-01", "F-02", "F-03", "F-04", "F-05"]

    def test_existing_catalog_seed_continues_sequence(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(SEED_WITH_F01, encoding="utf-8")
        fnum = append_issue(
            "New Issue",
            "Desc.",
            affects="pipeline-gate",
            severity="medium",
            workaround="workaround text",
            path=catalog,
        )
        assert fnum == "F-02"

    def test_all_entries_present_after_multiple_appends(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        for i in range(3):
            append_issue(
                f"Issue {i}",
                f"Desc {i}.",
                affects="all",
                severity="low",
                workaround="none",
                path=catalog,
            )
        text = catalog.read_text(encoding="utf-8")
        assert "## F-01 — Issue 0" in text
        assert "## F-02 — Issue 1" in text
        assert "## F-03 — Issue 2" in text


# ---------------------------------------------------------------------------
# Case-insensitivity of severity / status inputs
# ---------------------------------------------------------------------------

class TestCaseInsensitivity:
    def test_uppercase_severity_accepted(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        fnum = append_issue(
            "Issue",
            "Desc.",
            affects="all",
            severity="MEDIUM",
            workaround="none",
            path=catalog,
        )
        assert fnum == "F-01"
        text = catalog.read_text(encoding="utf-8")
        assert "**Severity**: Medium" in text

    def test_uppercase_status_accepted(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        append_issue(
            "Issue",
            "Desc.",
            affects="all",
            severity="low",
            workaround="none",
            status="OPEN",
            today="2026-01-01",
            path=catalog,
        )
        text = catalog.read_text(encoding="utf-8")
        assert "**Status**: Open (2026-01-01)" in text


# ---------------------------------------------------------------------------
# Default today stamp
# ---------------------------------------------------------------------------

class TestTodayStamp:
    def test_default_today_is_iso_date(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        append_issue(
            "Issue",
            "Desc.",
            affects="all",
            severity="low",
            workaround="none",
            path=catalog,
        )
        text = catalog.read_text(encoding="utf-8")
        # Matches YYYY-MM-DD inside parentheses
        assert re.search(r"\(\d{4}-\d{2}-\d{2}\)", text)

    def test_today_override(self, tmp_path):
        catalog = tmp_path / "known-issues.md"
        catalog.write_text(MINIMAL_HEADER, encoding="utf-8")
        append_issue(
            "Issue",
            "Desc.",
            affects="all",
            severity="low",
            workaround="none",
            today="2099-12-31",
            path=catalog,
        )
        text = catalog.read_text(encoding="utf-8")
        assert "(2099-12-31)" in text
