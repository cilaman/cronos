"""Normalize CC-v1 pipeline artifacts before verification.

Implements the drift-absorption table from the CC-v1 contract (§5.1 / F-14)
for the Cronos pipeline. Mirrors Delivery Notes' ``normalize_outputs.py``
adapted for the Cronos contract (``memory_hits`` replaces ``kb_hits``;
artifacts under ``.cronos/pipeline/``; ``memory_retrieval`` replaces
``kb_search`` in the strategy enum).

What is auto-fixed
------------------
blocker_string_wrap
    ``blockers[i]`` as a bare string is wrapped as
    ``{description: <str>, severity: "medium"}``.
strategy_synonym
    ``coverage_summary.strategies`` entries that are synonyms of a canonical
    enum value (e.g. ``kbsearch``, ``webfetch``) are mapped to the canonical
    form.
strategy_unknown_drop
    Free-text strategy entries that do not match any canonical label or known
    synonym are removed with a warning.
section_case_canonical
    Title-Case / ALL-CAPS H2 section headers whose lowercase form matches a
    canonical required-section name are rewritten to canonical case (e.g.
    ``## Open Questions`` → ``## Open questions``).
status_partial_to_blocked
    ``status: partial`` with non-empty ``blockers`` is coerced to
    ``status: blocked`` to satisfy R1.  ``status: done`` is intentionally
    NOT coerced — that is a semantic contradiction the agent must resolve.
path_backslash_to_slash
    Backslash separators in ``inputs_used``, ``outputs_produced``,
    ``files_changed``, ``files_modified``, and ``findings[].file`` are
    replaced with forward slashes (R7).

What is NOT fixed (hard-fails remain)
--------------------------------------
- Missing required header fields.
- Missing required sections (only renames existing; never inserts).
- ``confidence`` out of ``[0.0, 1.0]`` or non-numeric.
- Wrong agent name or slug.
- URL in ``inputs_used``.
- ``status: done`` with non-empty blockers.

CLI::

    python -m app.pipeline.normalize --agent research --slug my-feature \\
        --space /path/to/space
    python -m app.pipeline.normalize --agent research --slug X \\
        --space /path/to/space --dry-run
    python -m app.pipeline.normalize --agent research --slug X \\
        --space /path/to/space --json

Exit codes::

    0  normalization succeeded (fixes may or may not have been applied)
    1  artifact not found, unreadable, or unparseable
    2  usage error (unknown agent class, bad --space, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.pipeline.contract import (
    FINDINGS_SECTION_ALIASES,
    OPEN_QUESTIONS_SECTION_ALIASES,
    REQUIRED_SECTIONS,
)
from app.pipeline.verify import (
    CLASS_CONFIG,
    PER_CLASS_REQUIRED_SECTIONS,
    canonical_artifact_relpath,
    split_frontmatter,
)


# ---------------------------------------------------------------------------
# Strategy synonym map
#
# Keys are normalised (lower, alphanumeric only) forms of common LLM drifts.
# Values are canonical enum labels as defined in verify.py _check_research().
# ---------------------------------------------------------------------------

_STRATEGY_SYNONYMS: dict[str, str] = {
    # Cronos memory substrate (canonical); also catches Delivery Notes drifts.
    "memoryretrieval": "memory_retrieval",
    "memoryhits": "memory_retrieval",
    "memorysearch": "memory_retrieval",
    "kbsearch": "memory_retrieval",
    "knowledgebasesearch": "memory_retrieval",
    # codebase search
    "globstructural": "glob_structural",
    "glob": "glob_structural",
    "grepsymbol": "grep_symbol",
    "grepkeyword": "grep_keyword",
    "grep": "grep_keyword",
    "readtargeted": "read_targeted",
    "read": "read_targeted",
    "repomap": "repo_map",
    # web
    "websearch": "web_search",
    "fetchurl": "fetch_url",
    "webfetch": "fetch_url",
    "urlfetch": "fetch_url",
    "sourcequalityreview": "source_quality_review",
}


# Sidecar registry — extra synonyms appended at module-load time by the
# auto-improvement applier (task 4.4). The file ships with an empty
# strategy_synonyms map and is the durable home for synonyms learned from
# retro findings (fix_type=normalize_rule, target=normalize:strategy_synonym).
_NORMALIZE_RULES_PATH: Path = Path(__file__).parent / "normalize_rules.json"


def _load_synonym_registry() -> dict[str, str]:
    """Read the sidecar synonym registry; return empty dict if missing/invalid."""
    if not _NORMALIZE_RULES_PATH.exists():
        return {}
    try:
        data = json.loads(_NORMALIZE_RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw = data.get("strategy_synonyms")
    if not isinstance(raw, dict):
        return {}
    return {
        str(k): str(v)
        for k, v in raw.items()
        if isinstance(k, str) and isinstance(v, str)
    }


_STRATEGY_SYNONYMS.update(_load_synonym_registry())

_RESEARCH_STRATEGIES: frozenset[str] = frozenset(
    {
        "memory_retrieval",
        "glob_structural",
        "grep_symbol",
        "grep_keyword",
        "read_targeted",
        "repo_map",
        "web_search",
        "fetch_url",
        "traceability_mapping",
    }
)


def _canonicalize_strategy(raw: str, allowed: frozenset[str]) -> str | None:
    """Return canonical form if ``raw`` can be mapped; ``None`` means drop it."""
    if not isinstance(raw, str):
        return None
    if raw in allowed:
        return raw
    normalised = "".join(ch for ch in raw.lower() if ch.isalnum())
    canonical = _STRATEGY_SYNONYMS.get(normalised)
    if canonical and canonical in allowed:
        return canonical
    return None


# ---------------------------------------------------------------------------
# Section lookup helper
# ---------------------------------------------------------------------------


def _build_section_lookup(
    sections: tuple[str, ...] | list[str],
) -> dict[str, str]:
    """Build ``{lowercase_heading: canonical_heading}`` for the section fixer.

    ``## `` prefix is included in both key and value so the fixer can compare
    directly against stripped body lines.  Slots that have canonical aliases
    (Findings, Open questions) are expanded to all accepted names so any of
    them can be normalised to itself.
    """
    lookup: dict[str, str] = {}
    for sec in sections:
        if sec == "Findings":
            for alias in FINDINGS_SECTION_ALIASES:
                heading = f"## {alias}"
                lookup[heading.lower()] = heading
        elif sec == "Open questions":
            for alias in OPEN_QUESTIONS_SECTION_ALIASES:
                heading = f"## {alias}"
                lookup[heading.lower()] = heading
        else:
            heading = f"## {sec}"
            lookup[heading.lower()] = heading
    return lookup


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class NormalizeResult:
    """Outcome of a single ``normalize()`` call."""

    agent: str
    slug: str
    artifact_path: str
    modified: bool = False
    fixes_applied: list[str] = field(default_factory=list)
    unfixable_issues: list[str] = field(default_factory=list)
    error: str | None = None

    def log_fix(self, msg: str) -> None:
        self.modified = True
        self.fixes_applied.append(msg)

    def log_unfixable(self, msg: str) -> None:
        self.unfixable_issues.append(msg)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "slug": self.slug,
            "artifact_path": self.artifact_path,
            "modified": self.modified,
            "fixes_applied": self.fixes_applied,
            "unfixable_issues": self.unfixable_issues,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Individual fixers — each mutates ``header`` and/or ``body`` in place and
# records changes in ``result``.
# ---------------------------------------------------------------------------


def _fix_blockers(header: dict[str, Any], result: NormalizeResult) -> None:
    """Wrap bare-string blockers as ``{description, severity=medium}`` dicts."""
    blockers = header.get("blockers")
    if not isinstance(blockers, list):
        return
    changed = False
    for idx, entry in enumerate(blockers):
        if isinstance(entry, str):
            blockers[idx] = {"description": entry, "severity": "medium"}
            result.log_fix(
                f"blockers[{idx}]: wrapped bare string as "
                "{description, severity=medium} dict"
            )
            changed = True
    if changed:
        header["blockers"] = blockers


def _fix_strategies(
    header: dict[str, Any],
    allowed: frozenset[str],
    result: NormalizeResult,
) -> None:
    """Map strategy synonyms and drop unknown free-text entries."""
    coverage = header.get("coverage_summary")
    if not isinstance(coverage, dict):
        return
    raw = coverage.get("strategies")
    if not isinstance(raw, list):
        return

    new_list: list[Any] = []
    for idx, item in enumerate(raw):
        if isinstance(item, dict):
            # Rich-annotation form — leave for the verifier to reject.
            new_list.append(item)
            continue
        if not isinstance(item, str):
            result.log_unfixable(
                f"coverage_summary.strategies[{idx}] has non-string shape: {item!r}"
            )
            new_list.append(item)
            continue
        canonical = _canonicalize_strategy(item, allowed)
        if canonical is None:
            result.log_fix(
                f"coverage_summary.strategies[{idx}]: dropped unknown "
                f"free-text strategy {item!r}"
            )
            continue
        if canonical != item:
            result.log_fix(
                f"coverage_summary.strategies[{idx}]: {item!r} -> "
                f"{canonical!r} (synonym)"
            )
        new_list.append(canonical)

    if new_list != raw:
        coverage["strategies"] = new_list
        header["coverage_summary"] = coverage
        result.modified = True


def _fix_status_coerce(header: dict[str, Any], result: NormalizeResult) -> None:
    """Coerce ``status=partial`` to ``blocked`` when blockers are non-empty.

    R1 requires ``status ∈ {blocked, failed}`` when ``blockers`` is non-empty.
    ``status=done`` is intentionally NOT coerced — the ambiguity (drop blockers
    or downgrade status) cannot be resolved without semantic context.
    """
    status = header.get("status")
    blockers = header.get("blockers")
    has_blockers = isinstance(blockers, list) and len(blockers) > 0
    if not has_blockers:
        return
    if status == "partial":
        header["status"] = "blocked"
        result.log_fix(
            "status: 'partial' -> 'blocked' (non-empty blockers require "
            "status in {blocked, failed} per R1)"
        )
    elif status == "done":
        result.log_unfixable(
            "status='done' with non-empty blockers — contradiction is too "
            "ambiguous to auto-fix; agent must choose to drop blockers or "
            "change status manually"
        )


def _fix_path_separators(header: dict[str, Any], result: NormalizeResult) -> None:
    """Replace backslash separators with forward slashes in path fields (R7)."""
    # Flat list fields that contain workspace-relative paths.
    for field_name in (
        "inputs_used",
        "outputs_produced",
        "files_changed",
        "files_modified",
    ):
        values = header.get(field_name)
        if not isinstance(values, list):
            continue
        changed = False
        for idx, p in enumerate(values):
            if isinstance(p, str) and "\\" in p and "://" not in p:
                fixed = p.replace("\\", "/")
                values[idx] = fixed
                result.log_fix(
                    f"{field_name}[{idx}]: {p!r} -> {fixed!r} "
                    "(backslash -> forward slash)"
                )
                changed = True
        if changed:
            header[field_name] = values

    # Nested: findings[].file — "path:line" format; replace in full string.
    findings = header.get("findings")
    if isinstance(findings, list):
        for idx, f in enumerate(findings):
            if not isinstance(f, dict):
                continue
            fpath = f.get("file")
            if isinstance(fpath, str) and "\\" in fpath and "://" not in fpath:
                fixed = fpath.replace("\\", "/")
                f["file"] = fixed
                result.log_fix(
                    f"findings[{idx}].file: {fpath!r} -> {fixed!r} "
                    "(backslash -> forward slash)"
                )


def _fix_section_casing(
    body: str,
    class_name: str,
    result: NormalizeResult,
) -> str:
    """Rewrite H2 section headers to canonical required-section case.

    Only touches ``## `` (exactly two hashes then space) headers whose
    lowercased form matches a canonical required section or accepted alias.
    Deeper headings (``###+``) are left alone.
    """
    sections = PER_CLASS_REQUIRED_SECTIONS.get(class_name, REQUIRED_SECTIONS)
    lookup = _build_section_lookup(sections)
    if not lookup:
        return body

    lines = body.splitlines()
    changed = False
    for idx, line in enumerate(lines):
        stripped = line.rstrip()
        if not stripped.startswith("## ") or stripped.startswith("### "):
            continue
        lower = stripped.lower()
        if lower in lookup and lookup[lower] != stripped:
            canonical = lookup[lower]
            leading = line[: len(line) - len(line.lstrip())]
            lines[idx] = leading + canonical
            result.log_fix(
                f"section header: {stripped!r} -> {canonical!r} (canonical case)"
            )
            changed = True

    if not changed:
        return body

    joined = "\n".join(lines)
    if body.endswith("\n") and not joined.endswith("\n"):
        joined += "\n"
    return joined


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize(
    agent: str,
    slug: str,
    space: Path,
    dry_run: bool = False,
) -> NormalizeResult:
    """Normalize the artifact for ``agent`` (class) + ``slug`` under ``space``.

    When ``dry_run=True`` the file is not written back but the returned
    :class:`NormalizeResult` still reflects what would have changed.
    """
    if agent not in CLASS_CONFIG:
        r = NormalizeResult(agent=agent, slug=slug, artifact_path="<unknown>")
        r.error = (
            f"unknown agent class {agent!r}; expected one of "
            f"{sorted(CLASS_CONFIG.keys())}"
        )
        return r

    artifact_rel = canonical_artifact_relpath(agent, slug)
    artifact_path = space / artifact_rel
    result = NormalizeResult(agent=agent, slug=slug, artifact_path=artifact_rel)

    if not artifact_path.exists():
        result.error = f"artifact not found at: {artifact_rel}"
        return result
    if not artifact_path.is_file():
        result.error = f"artifact path is not a file: {artifact_rel}"
        return result

    try:
        original_text = artifact_path.read_text(encoding="utf-8")
    except OSError as exc:
        result.error = f"cannot read artifact: {exc}"
        return result

    try:
        header, body = split_frontmatter(original_text)
    except ValueError as exc:
        result.error = f"cannot parse YAML front-matter: {exc}"
        return result

    if header is None:
        result.error = (
            "artifact has no YAML front-matter block (must start with '---')"
        )
        return result

    # Fixers run in dependency order: blockers shape first, then status coerce.
    _fix_blockers(header, result)
    _fix_strategies(header, _RESEARCH_STRATEGIES, result)
    _fix_status_coerce(header, result)
    _fix_path_separators(header, result)
    new_body = _fix_section_casing(body, agent, result)

    if not result.modified and new_body == body:
        return result

    if dry_run:
        return result

    new_yaml = yaml.safe_dump(
        header,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip("\n")
    new_text = f"---\n{new_yaml}\n---\n\n{new_body.lstrip()}"
    if original_text.endswith("\n") and not new_text.endswith("\n"):
        new_text += "\n"

    try:
        artifact_path.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        result.error = f"cannot write normalized artifact: {exc}"
        return result

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="app.pipeline.normalize",
        description=(
            "Normalize a CC-v1 pipeline artifact before verification "
            "(drift-absorption layer, F-14)."
        ),
    )
    parser.add_argument(
        "--agent",
        required=True,
        choices=sorted(CLASS_CONFIG.keys()),
        help="Agent class identifier (e.g. 'research', 'implementation').",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="Goal slug (kebab-case, optionally compound with '--' for fan-out).",
    )
    parser.add_argument(
        "--space",
        required=True,
        help="Absolute path to the space root (the directory holding .cronos/).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report fixes without writing the artifact back to disk.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON report on stdout instead of human-readable lines.",
    )
    args = parser.parse_args(argv)

    space = Path(args.space).resolve()
    if not space.is_dir():
        print(f"ERROR: --space is not a directory: {space}", file=sys.stderr)
        return 2

    result = normalize(args.agent, args.slug, space, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        label = (
            "DRY-RUN"
            if args.dry_run
            else ("MODIFIED" if result.modified else "UNCHANGED")
        )
        print(f"[{label}] agent={result.agent} slug={result.slug}")
        print(f"         artifact={result.artifact_path}")
        if result.error:
            print(f"  ERROR: {result.error}")
        for fix in result.fixes_applied:
            print(f"  FIX:   {fix}")
        for issue in result.unfixable_issues:
            print(f"  SKIP:  {issue}")
        if not result.fixes_applied and not result.unfixable_issues and not result.error:
            print("  (no drift detected)")

    return 1 if result.error else 0


if __name__ == "__main__":
    sys.exit(main())
