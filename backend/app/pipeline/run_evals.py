#!/usr/bin/env python3
"""Cronos CC-v1 pipeline eval harness.

Validates golden artifacts (must pass verify()) and negative artifacts (must
fail verify() even after normalize()).  This is the CI gate invoked by
``/goal-finalize`` before any merge — a regression in any golden or a
negative that starts passing blocks the merge.

Usage::

    python -m app.pipeline.run_evals --all
    python -m app.pipeline.run_evals --class research
    python -m app.pipeline.run_evals --negatives-only
    python -m app.pipeline.run_evals --golden-only
    python -m app.pipeline.run_evals --all --json

Exit codes::

    0  all checks passed
    1  at least one check failed
    3  usage error (bad --class value, missing dependencies)

Ported from Delivery Notes ``run_evals.py`` and adapted for the Cronos
contract (classes instead of agent names; artifacts under
``.cronos/pipeline/``; ``memory_hits`` / ``memory_retrieval``).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — works both as a module and as a direct script.
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

# When invoked as a script, add the package root so the relative imports work.
_pkg_root = Path(__file__).resolve().parent.parent.parent  # backend/
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

try:
    from app.pipeline.normalize import normalize
    from app.pipeline.verify import EXIT_PROCEED, canonical_artifact_relpath, verify
except ImportError as exc:
    print(
        f"ERROR: cannot import pipeline modules from {_pkg_root}: {exc}",
        file=sys.stderr,
    )
    sys.exit(3)

# ---------------------------------------------------------------------------
# Fixture manifest — slug overrides for classes that use a sub-slug.
# ---------------------------------------------------------------------------

_CLASS_SLUG: dict[str, str] = {
    "implementation": "fixture-test--i1",
}
_DEFAULT_SLUG = "fixture-test"

ALL_CLASSES = ["research", "analysis", "design", "implementation", "test", "review", "doc"]


def _slug_for(class_name: str) -> str:
    return _CLASS_SLUG.get(class_name, _DEFAULT_SLUG)


# ---------------------------------------------------------------------------
# Fixture discovery
# ---------------------------------------------------------------------------


def _discover_golden(classes: list[str]) -> list[tuple[str, str]]:
    """Return (class_name, slug) pairs for golden fixtures that exist on disk."""
    result: list[tuple[str, str]] = []
    for cls in classes:
        p = FIXTURE_DIR / "golden" / f"{cls}.md"
        if p.exists():
            result.append((cls, _slug_for(cls)))
    return result


def _discover_negative(classes: list[str]) -> list[tuple[str, str, str]]:
    """Return (class_name, slug, fixture_stem) triples for all negative fixtures."""
    result: list[tuple[str, str, str]] = []
    neg_root = FIXTURE_DIR / "negative"
    if not neg_root.exists():
        return result
    for cls in classes:
        cls_dir = neg_root / cls
        if not cls_dir.is_dir():
            continue
        slug = _slug_for(cls)
        for p in sorted(cls_dir.glob("*.md")):
            result.append((cls, slug, p.stem))
    return result


# ---------------------------------------------------------------------------
# Fixture staging helpers
# ---------------------------------------------------------------------------


def _place(tmp_path: Path, class_name: str, slug: str, content: str) -> Path:
    """Write *content* to the canonical artifact path inside *tmp_path*."""
    rel = canonical_artifact_relpath(class_name, slug)
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _read_fixture(path: Path) -> str:
    assert path.exists(), (
        f"Fixture missing: {path}\n"
        "Re-run the fixture generation task to recreate it."
    )
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Golden scoring
# ---------------------------------------------------------------------------


def score_golden(class_name: str, slug: str) -> dict[str, Any]:
    content = _read_fixture(FIXTURE_DIR / "golden" / f"{class_name}.md")
    result: dict[str, Any] = {
        "type": "golden",
        "class": class_name,
        "slug": slug,
        "checks": [],
        "status": "unknown",
    }
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _place(tmp_path, class_name, slug, content)
        v = verify(class_name, slug, tmp_path)

    result["checks"].append(
        {
            "name": "verify_outputs",
            "ok": v.passed,
            "errors": list(v.errors),
            "warnings": list(v.warnings),
            "outcome": v.outcome,
        }
    )
    result["status"] = "pass" if v.passed else "fail"
    return result


# ---------------------------------------------------------------------------
# Negative scoring
# ---------------------------------------------------------------------------


def score_negative(class_name: str, slug: str, fixture_stem: str) -> dict[str, Any]:
    fixture_path = FIXTURE_DIR / "negative" / class_name / f"{fixture_stem}.md"
    content = _read_fixture(fixture_path)
    result: dict[str, Any] = {
        "type": "negative",
        "class": class_name,
        "slug": slug,
        "fixture": fixture_stem,
        "checks": [],
        "status": "unknown",
    }
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _place(tmp_path, class_name, slug, content)

        # Normalize first — the negative must survive normalization and still fail.
        norm = normalize(class_name, slug, tmp_path, dry_run=False)
        result["checks"].append(
            {
                "name": "normalize",
                "ok": norm.error is None,
                "fixes_applied": list(norm.fixes_applied),
                "unfixable": list(norm.unfixable_issues),
                "error": norm.error,
            }
        )
        if norm.error is not None:
            result["status"] = "error"
            return result

        v = verify(class_name, slug, tmp_path)

    # A negative is OK iff verify REJECTED the artifact (not passed).
    ok = not v.passed
    result["checks"].append(
        {
            "name": "verify_rejects",
            "ok": ok,
            "verify_passed": v.passed,
            "detected_errors": list(v.errors),
            "msg": (
                f"rejected with {len(v.errors)} error(s)"
                if ok
                else "UNEXPECTED PASS — fixture no longer tests a hard-fail condition"
            ),
        }
    )
    result["status"] = "pass" if ok else "fail"
    return result


# ---------------------------------------------------------------------------
# Scorecard rendering
# ---------------------------------------------------------------------------


def render_scorecard(
    golden_results: list[dict[str, Any]],
    negative_results: list[dict[str, Any]],
) -> str:
    lines: list[str] = ["CC-v1 Pipeline Eval Scorecard", "=" * 60]

    if golden_results:
        lines += ["", "GOLDEN FIXTURES (must pass verify())"]
        for r in golden_results:
            status = r["status"].upper()
            lines.append(f"  [{status:<7}] {r['class']} (slug={r['slug']})")
            for c in r["checks"]:
                mark = "OK " if c.get("ok", True) else "FAIL"
                name = c.get("name", "?")
                extra = c.get("outcome", "") or c.get("msg", "")
                lines.append(f"             {mark}  {name:<30} {extra}")
                for e in c.get("errors") or []:
                    lines.append(f"                   ! {e}")
                for w in c.get("warnings") or []:
                    lines.append(f"                   ~ {w}")

    if negative_results:
        lines += ["", "NEGATIVE FIXTURES (must fail verify() after normalize())"]
        for r in negative_results:
            status = r["status"].upper()
            label = f"{r['class']}/{r['fixture']}"
            lines.append(f"  [{status:<7}] {label}")
            for c in r["checks"]:
                mark = "OK " if c.get("ok", True) else "FAIL"
                name = c.get("name", "?")
                msg = c.get("msg", "")
                lines.append(f"             {mark}  {name:<30} {msg}")
                for e in c.get("detected_errors") or []:
                    lines.append(f"                   ! {e}")

    lines.append("")
    g_pass = sum(1 for r in golden_results if r["status"] == "pass")
    g_total = len(golden_results)
    n_pass = sum(1 for r in negative_results if r["status"] == "pass")
    n_total = len(negative_results)
    lines.append(f"TOTALS  golden {g_pass}/{g_total} pass   negatives {n_pass}/{n_total} pass")
    overall = "PASS" if (g_pass == g_total and n_pass == n_total) else "FAIL"
    lines.append(f"OVERALL {overall}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cronos CC-v1 pipeline eval harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--class",
        dest="class_filter",
        metavar="CLASS",
        help=f"Filter to one class (one of: {', '.join(ALL_CLASSES)})",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--all",
        action="store_true",
        default=True,
        help="Run golden + negative fixtures (default)",
    )
    mode_group.add_argument(
        "--golden-only",
        action="store_true",
        help="Run only golden fixtures",
    )
    mode_group.add_argument(
        "--negatives-only",
        action="store_true",
        help="Run only negative fixtures",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    # Resolve which classes to eval.
    if args.class_filter:
        if args.class_filter not in ALL_CLASSES:
            print(
                f"ERROR: unknown class {args.class_filter!r}; "
                f"known: {', '.join(ALL_CLASSES)}",
                file=sys.stderr,
            )
            return 3
        classes = [args.class_filter]
    else:
        classes = list(ALL_CLASSES)

    run_golden = not args.negatives_only
    run_negatives = not args.golden_only

    golden_results: list[dict[str, Any]] = []
    negative_results: list[dict[str, Any]] = []

    if run_golden:
        for class_name, slug in _discover_golden(classes):
            golden_results.append(score_golden(class_name, slug))

    if run_negatives:
        for class_name, slug, fixture_stem in _discover_negative(classes):
            negative_results.append(score_negative(class_name, slug, fixture_stem))

    if args.json:
        print(
            json.dumps(
                {"golden": golden_results, "negatives": negative_results}, indent=2
            )
        )
    else:
        print(render_scorecard(golden_results, negative_results))

    any_fail = any(r["status"] != "pass" for r in golden_results + negative_results)
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
