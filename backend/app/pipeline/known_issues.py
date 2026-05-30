"""pipeline-issue helper — append a well-formed F-NN entry to the CC-v1
known-issues catalog at ``backend/app/pipeline/known-issues.md``.

CLI usage::

    python -m app.pipeline.known_issues append \\
        --title "Verifier drops stack trace on parse error" \\
        --affects "pipeline-gate skill, all phases" \\
        --severity medium \\
        --workaround "Inspect the raw artifact with verify --json for full detail." \\
        --description "When the YAML header cannot be parsed ..."

Programmatic usage::

    from app.pipeline.known_issues import append_issue
    fnum = append_issue(
        "Verifier drops stack trace on parse error",
        "When the YAML header ...",
        affects="pipeline-gate skill, all phases",
        severity="medium",
        workaround="Inspect the raw artifact with verify --json for full detail.",
    )
    print(fnum)   # "F-03"
"""

from __future__ import annotations

import re
import sys
from datetime import date, timezone, datetime
from pathlib import Path

KNOWN_ISSUES_PATH = Path(__file__).parent / "known-issues.md"

VALID_STATUSES: frozenset[str] = frozenset({
    "open",
    "resolved",
    "mitigated",
    "investigating",
})

VALID_SEVERITIES: frozenset[str] = frozenset({
    "blocking",
    "high",
    "medium",
    "low",
    "process",
})


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def _next_fnum(text: str) -> str:
    """Return the next F-NN label by scanning existing headings."""
    nums = [int(m) for m in re.findall(r"##\s+F-(\d+)\s+[—–-]", text)]
    return f"F-{max(nums, default=0) + 1:02d}"


def _build_entry(
    fnum: str,
    title: str,
    description: str,
    *,
    affects: str,
    severity: str,
    workaround: str,
    status: str,
    today: str,
) -> str:
    return (
        f"\n---\n\n"
        f"## {fnum} — {title}\n\n"
        f"**Status**: {status.capitalize()} ({today})"
        f" | **Affects**: {affects}\n"
        f"**Severity**: {severity.capitalize()}\n\n"
        f"{description.strip()}\n\n"
        f"**Workaround**: {workaround.strip()}\n"
    )


def append_issue(
    title: str,
    description: str,
    *,
    affects: str,
    severity: str,
    workaround: str,
    status: str = "open",
    path: Path | None = None,
    today: str | None = None,
) -> str:
    """Append a well-formed F-NN entry to the known-issues catalog.

    Parameters
    ----------
    title:
        Short one-line title (no F-number prefix — that is assigned here).
    description:
        Multi-sentence body describing the issue, root cause, and evidence.
    affects:
        Which agents / skills / pipeline phases are affected.
    severity:
        One of ``blocking``, ``high``, ``medium``, ``low``, ``process``.
    workaround:
        What callers can do right now to work around the issue.
    status:
        One of ``open`` (default), ``resolved``, ``mitigated``,
        ``investigating``.
    path:
        Override catalog path (defaults to the canonical known-issues.md next
        to this module).  Useful in tests.
    today:
        Override the date stamp (ISO-8601, e.g. ``"2026-05-30"``).  Defaults
        to today's UTC date.

    Returns
    -------
    str
        The assigned F-number, e.g. ``"F-03"``.

    Raises
    ------
    ValueError
        If *severity* or *status* is not one of the legal values.
    FileNotFoundError
        If *path* (or the default catalog path) does not exist.
    """
    severity_lower = severity.lower()
    status_lower = status.lower()
    if severity_lower not in VALID_SEVERITIES:
        raise ValueError(
            f"severity must be one of {sorted(VALID_SEVERITIES)!r}, got {severity!r}"
        )
    if status_lower not in VALID_STATUSES:
        raise ValueError(
            f"status must be one of {sorted(VALID_STATUSES)!r}, got {status!r}"
        )

    target = path or KNOWN_ISSUES_PATH
    if not target.exists():
        raise FileNotFoundError(f"Known-issues catalog not found: {target}")

    text = target.read_text(encoding="utf-8")
    fnum = _next_fnum(text)
    date_str = today or datetime.now(timezone.utc).date().isoformat()

    entry = _build_entry(
        fnum, title, description,
        affects=affects,
        severity=severity_lower,
        workaround=workaround,
        status=status_lower,
        today=date_str,
    )

    target.write_text(text.rstrip() + entry, encoding="utf-8")
    return fnum


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m app.pipeline.known_issues",
        description="Append an F-NN entry to the CC-v1 known-issues catalog.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    ap = sub.add_parser("append", help="Append a new known-issue entry.")
    ap.add_argument("--title", required=True, help="One-line issue title.")
    ap.add_argument(
        "--description",
        default="",
        help="Multi-sentence body (can be empty; fill in later).",
    )
    ap.add_argument("--affects", required=True, help="Affected agents / phases / skills.")
    ap.add_argument(
        "--severity",
        required=True,
        choices=sorted(VALID_SEVERITIES),
        help="Issue severity.",
    )
    ap.add_argument("--workaround", required=True, help="Current workaround text.")
    ap.add_argument(
        "--status",
        default="open",
        choices=sorted(VALID_STATUSES),
        help="Issue status (default: open).",
    )
    ap.add_argument(
        "--catalog",
        default=None,
        help="Path to the known-issues.md file (default: canonical path).",
    )

    args = parser.parse_args()

    catalog_path = Path(args.catalog) if args.catalog else None
    fnum = append_issue(
        args.title,
        args.description,
        affects=args.affects,
        severity=args.severity,
        workaround=args.workaround,
        status=args.status,
        path=catalog_path,
    )
    print(f"Appended {fnum}: {args.title}")


if __name__ == "__main__":  # pragma: no cover
    _cli()
