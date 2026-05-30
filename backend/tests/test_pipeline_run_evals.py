"""Tests for app.pipeline.run_evals — the CC-v1 eval harness.

Covers the public API (score_golden, score_negative, render_scorecard, main)
and verifies that the CLI gate correctly exits non-zero when a fixture regresses.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.pipeline.run_evals as run_evals
from app.pipeline.run_evals import (
    ALL_CLASSES,
    _discover_golden,
    _discover_negative,
    _slug_for,
    main,
    render_scorecard,
    score_golden,
    score_negative,
)


# ---------------------------------------------------------------------------
# Fixture discovery
# ---------------------------------------------------------------------------


def test_discover_golden_all_classes() -> None:
    """All 7 golden fixtures must be discoverable."""
    pairs = _discover_golden(ALL_CLASSES)
    found_classes = [cls for cls, _ in pairs]
    assert set(found_classes) == set(ALL_CLASSES)


def test_discover_golden_class_filter() -> None:
    """Filtering to one class returns only that class."""
    pairs = _discover_golden(["research"])
    assert len(pairs) == 1
    assert pairs[0][0] == "research"


def test_discover_negative_all_classes() -> None:
    """At least one negative fixture per class must exist."""
    triples = _discover_negative(ALL_CLASSES)
    found_classes = {cls for cls, _, _ in triples}
    assert found_classes == set(ALL_CLASSES), (
        f"Missing negative fixtures for: {set(ALL_CLASSES) - found_classes}"
    )


def test_discover_negative_class_filter() -> None:
    pairs = _discover_negative(["review"])
    assert all(cls == "review" for cls, _, _ in pairs)
    assert len(pairs) >= 1


def test_slug_for_implementation() -> None:
    assert _slug_for("implementation") == "fixture-test--i1"


def test_slug_for_default() -> None:
    for cls in ["research", "analysis", "design", "test", "review", "doc"]:
        assert _slug_for(cls) == "fixture-test"


# ---------------------------------------------------------------------------
# score_golden
# ---------------------------------------------------------------------------


def test_score_golden_all_pass() -> None:
    """Every golden fixture must report status='pass'."""
    for class_name, slug in _discover_golden(ALL_CLASSES):
        result = score_golden(class_name, slug)
        assert result["status"] == "pass", (
            f"Golden {class_name!r} failed:\n"
            + "\n".join(
                str(e)
                for c in result["checks"]
                for e in (c.get("errors") or [])
            )
        )


def test_score_golden_regress_detected(tmp_path: Path) -> None:
    """Breaking a golden fixture must flip status to 'fail'."""
    fixture_path = run_evals.FIXTURE_DIR / "golden" / "research.md"
    original = fixture_path.read_text(encoding="utf-8")
    broken = original.replace("cc_version: '1.0'", "cc_version: '9.9'")
    fixture_path.write_text(broken, encoding="utf-8")
    try:
        result = score_golden("research", "fixture-test")
        assert result["status"] == "fail"
        errors = result["checks"][0]["errors"]
        assert any("cc_version" in e for e in errors)
    finally:
        fixture_path.write_text(original, encoding="utf-8")


# ---------------------------------------------------------------------------
# score_negative
# ---------------------------------------------------------------------------


def test_score_negative_all_pass() -> None:
    """Every negative fixture must report status='pass' (i.e. verify rejects it)."""
    for class_name, slug, fixture_stem in _discover_negative(ALL_CLASSES):
        result = score_negative(class_name, slug, fixture_stem)
        assert result["status"] == "pass", (
            f"Negative {class_name!r}/{fixture_stem!r} unexpectedly "
            f"status={result['status']!r}: {result['checks']}"
        )


def test_score_negative_verify_rejects_check() -> None:
    """The verify_rejects check must be present and True for each negative."""
    for class_name, slug, fixture_stem in _discover_negative(ALL_CLASSES):
        result = score_negative(class_name, slug, fixture_stem)
        rejects = [c for c in result["checks"] if c["name"] == "verify_rejects"]
        assert rejects, f"No verify_rejects check for {class_name}/{fixture_stem}"
        assert rejects[0]["ok"] is True
        assert rejects[0]["verify_passed"] is False


# ---------------------------------------------------------------------------
# render_scorecard
# ---------------------------------------------------------------------------


def test_render_scorecard_pass_summary() -> None:
    golden = [{"type": "golden", "class": "research", "slug": "s", "checks": [], "status": "pass"}]
    negative = [
        {"type": "negative", "class": "research", "slug": "s", "fixture": "f", "checks": [], "status": "pass"}
    ]
    out = render_scorecard(golden, negative)
    assert "golden 1/1 pass" in out
    assert "negatives 1/1 pass" in out
    assert "OVERALL PASS" in out


def test_render_scorecard_fail_summary() -> None:
    golden = [{"type": "golden", "class": "research", "slug": "s", "checks": [], "status": "fail"}]
    negative: list = []
    out = render_scorecard(golden, negative)
    assert "OVERALL FAIL" in out


def test_render_scorecard_empty() -> None:
    out = render_scorecard([], [])
    assert "TOTALS" in out


# ---------------------------------------------------------------------------
# main() — CLI integration
# ---------------------------------------------------------------------------


def test_main_all_passes() -> None:
    """main(['--all']) must return 0 when all fixtures are intact."""
    rc = main(["--all"])
    assert rc == 0


def test_main_golden_only_passes() -> None:
    rc = main(["--golden-only"])
    assert rc == 0


def test_main_negatives_only_passes() -> None:
    rc = main(["--negatives-only"])
    assert rc == 0


def test_main_class_filter_passes() -> None:
    rc = main(["--class", "design"])
    assert rc == 0


def test_main_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    """--json mode must emit valid JSON with 'golden' and 'negatives' keys."""
    rc = main(["--all", "--json"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "golden" in data
    assert "negatives" in data
    assert all(r["status"] == "pass" for r in data["golden"])
    assert all(r["status"] == "pass" for r in data["negatives"])


def test_main_unknown_class_exits_3() -> None:
    rc = main(["--class", "nonexistent"])
    assert rc == 3


def test_main_regress_exits_1() -> None:
    """A broken golden fixture must cause main() to return 1."""
    fixture_path = run_evals.FIXTURE_DIR / "golden" / "analysis.md"
    original = fixture_path.read_text(encoding="utf-8")
    broken = original.replace("cc_version: '1.0'", "cc_version: '99.0'")
    fixture_path.write_text(broken, encoding="utf-8")
    try:
        rc = main(["--class", "analysis", "--golden-only"])
        assert rc == 1
    finally:
        fixture_path.write_text(original, encoding="utf-8")
