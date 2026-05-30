"""Regression fixture harness for the CC-v1 pipeline (task 1.5).

Golden artifacts (fixtures/golden/<class>.md) must pass verify() cleanly.
Negative artifacts (fixtures/negative/<class>/<name>.md) must fail verify()
even AFTER normalize() has been applied — they encode hard-fail conditions
that the drift-absorption layer cannot fix.

This module is the eval baseline: if a golden regresses or a negative starts
passing, something in the contract/schema/verifier/normalizer changed and must
be reviewed before merging.

Directory layout expected under backend/app/pipeline/fixtures/:

  golden/
    research.md, analysis.md, design.md, implementation.md,
    test.md, review.md, doc.md
  negative/
    research/missing_coverage_summary.md, research/wrong_cc_version.md
    analysis/confidence_too_high.md, analysis/r4_violation.md
    design/missing_section.md, design/dangling_depends_on.md
    implementation/r_impl_5.md, implementation/trace_owned_metric.md
    test/r_val_3.md, test/invalid_gate_decision.md
    review/r_rev_4.md, review/r_rev_2.md
    doc/r_doc_not_a_list.md, doc/r_doc_4.md
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.pipeline.normalize import normalize
from app.pipeline.verify import (
    EXIT_PROCEED,
    canonical_artifact_relpath,
    verify,
)


FIXTURE_DIR = (
    Path(__file__).resolve().parent.parent / "app" / "pipeline" / "fixtures"
)


# ---------------------------------------------------------------------------
# Fixture manifest
# ---------------------------------------------------------------------------

#: (agent_class, slug) for each golden fixture.
GOLDEN_FIXTURES: list[tuple[str, str]] = [
    ("research", "fixture-test"),
    ("analysis", "fixture-test"),
    ("design", "fixture-test"),
    ("implementation", "fixture-test--i1"),
    ("test", "fixture-test"),
    ("review", "fixture-test"),
    ("doc", "fixture-test"),
]

#: (agent_class, slug, fixture_name) for each negative fixture.
#  fixture_name is the stem of the .md file under fixtures/negative/<class>/.
NEGATIVE_FIXTURES: list[tuple[str, str, str]] = [
    # research — missing required field; wrong contract version
    ("research", "fixture-test", "missing_coverage_summary"),
    ("research", "fixture-test", "wrong_cc_version"),
    # analysis — R3 confidence out-of-range; R4 accessibility count mismatch
    ("analysis", "fixture-test", "confidence_too_high"),
    ("analysis", "fixture-test", "r4_violation"),
    # design — missing required section; dangling depends_on reference
    ("design", "fixture-test", "missing_section"),
    ("design", "fixture-test", "dangling_depends_on"),
    # implementation — R-impl-5 incoherent status; trace-owned metric written by agent
    ("implementation", "fixture-test--i1", "r_impl_5"),
    ("implementation", "fixture-test--i1", "trace_owned_metric"),
    # test — R-val-3 pass+failures contradiction; R-val-1 invalid gate_decision
    ("test", "fixture-test", "r_val_3"),
    ("test", "fixture-test", "invalid_gate_decision"),
    # review — R-rev-4 pass+blocking contradiction; R-rev-2 bad finding ID format
    ("review", "fixture-test", "r_rev_4"),
    ("review", "fixture-test", "r_rev_2"),
    # doc — intentionally_not_updated wrong type; R-doc-4 silent no-op
    ("doc", "fixture-test", "r_doc_not_a_list"),
    ("doc", "fixture-test", "r_doc_4"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_fixture(fixture_path: Path) -> str:
    """Return the raw text of a fixture file, asserting it exists."""
    assert fixture_path.exists(), (
        f"Fixture file missing: {fixture_path}\n"
        "Run the fixture-harness task to regenerate it."
    )
    return fixture_path.read_text(encoding="utf-8")


def _place_artifact(space: Path, class_name: str, slug: str, content: str) -> Path:
    """Write *content* to the canonical artifact path for (class_name, slug)."""
    rel = canonical_artifact_relpath(class_name, slug)
    artifact_path = space / rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(content, encoding="utf-8")
    return artifact_path


def _golden_path(class_name: str) -> Path:
    return FIXTURE_DIR / "golden" / f"{class_name}.md"


def _negative_path(class_name: str, fixture_name: str) -> Path:
    return FIXTURE_DIR / "negative" / class_name / f"{fixture_name}.md"


# ---------------------------------------------------------------------------
# Golden tests — every golden must pass verify() cleanly (EXIT_PROCEED)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "class_name,slug",
    GOLDEN_FIXTURES,
    ids=[f"{c}:{s}" for c, s in GOLDEN_FIXTURES],
)
def test_golden_passes(tmp_path: Path, class_name: str, slug: str) -> None:
    """A golden fixture must pass verify() without any errors."""
    content = _read_fixture(_golden_path(class_name))
    _place_artifact(tmp_path, class_name, slug, content)

    result = verify(class_name, slug, tmp_path)

    assert result.passed, (
        f"Golden {class_name!r} ({slug!r}) failed verify().\n"
        f"Errors: {result.errors}\n"
        f"Warnings: {result.warnings}\n"
        "A golden fixture regressing means the contract or verifier changed.\n"
        "Review the change before updating the fixture."
    )
    assert result.outcome == "proceed", (
        f"Golden {class_name!r} ({slug!r}) has unexpected outcome "
        f"{result.outcome!r} (expected 'proceed').\n"
        f"Errors: {result.errors}"
    )


# ---------------------------------------------------------------------------
# Negative tests — every negative must still fail verify() after normalize()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "class_name,slug,fixture_name",
    NEGATIVE_FIXTURES,
    ids=[f"{c}:{n}" for c, _, n in NEGATIVE_FIXTURES],
)
def test_negative_fails_after_normalize(
    tmp_path: Path, class_name: str, slug: str, fixture_name: str
) -> None:
    """A negative fixture must remain invalid even after normalize() runs.

    Normalization is allowed to fix surface drift (case, synonyms, bare strings)
    but MUST NOT silently heal hard-fail contract violations.
    """
    content = _read_fixture(_negative_path(class_name, fixture_name))
    _place_artifact(tmp_path, class_name, slug, content)

    # Run the normalizer first (mirrors what verify --normalize does).
    norm_result = normalize(class_name, slug, tmp_path, dry_run=False)
    assert norm_result.error is None, (
        f"normalize() itself errored on {class_name!r}/{fixture_name!r}: "
        f"{norm_result.error}"
    )

    # Now verify the (possibly rewritten) artifact.
    result = verify(class_name, slug, tmp_path)

    assert not result.passed, (
        f"Negative {class_name!r}/{fixture_name!r} unexpectedly PASSED verify() "
        f"after normalize().\n"
        f"Fixes applied by normalize: {norm_result.fixes_applied}\n"
        f"This means the fixture no longer tests a hard-fail condition — either "
        f"normalize now heals what it shouldn't, or the fixture content changed."
    )


# ---------------------------------------------------------------------------
# Fixture coverage guard — all NEGATIVE_FIXTURES have files on disk
# ---------------------------------------------------------------------------


def test_all_negative_fixture_files_exist() -> None:
    """All entries in NEGATIVE_FIXTURES must have a corresponding .md file."""
    missing: list[str] = []
    for class_name, _slug, fixture_name in NEGATIVE_FIXTURES:
        p = _negative_path(class_name, fixture_name)
        if not p.exists():
            missing.append(str(p))
    assert not missing, (
        f"Missing negative fixture files:\n" + "\n".join(f"  {m}" for m in missing)
    )


def test_all_golden_fixture_files_exist() -> None:
    """All entries in GOLDEN_FIXTURES must have a corresponding .md file."""
    missing: list[str] = []
    for class_name, _slug in GOLDEN_FIXTURES:
        p = _golden_path(class_name)
        if not p.exists():
            missing.append(str(p))
    assert not missing, (
        f"Missing golden fixture files:\n" + "\n".join(f"  {m}" for m in missing)
    )
