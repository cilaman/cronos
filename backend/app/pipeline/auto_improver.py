"""Auto-improvement applier for CC-v1 pipeline retro findings (task 4.4).

After ``pipeline-retro`` produces a verified ``retro-{slug}.md``, this module
reads the artifact's ``findings[]``, filters the subset that is **machine
applicable** (today: ``fix_type=normalize_rule`` with a strategy-synonym
recipe, and ``target: fixture:<rel_path>`` recipes that drop a new
golden/negative fixture into place), applies each change, bumps the
``CC_VERSION`` constant by one minor (``1.x -> 1.x+1``) across
``contract.py`` + per-class schemas + every fixture pinned to the prior
version, then re-runs the goal-1 evals (the CC-v1 fixture harness).

If the evals stay **green** the change is kept and the new version stands.
If the evals go **red** every file the applier touched is restored from the
in-memory snapshot — the version bump is rolled back too. Findings of
``fix_type ∈ {agent_prompt_refinement, contract_change}`` are deliberately
**skipped**: they need human eyes.

Recipe schema
-------------

A retro finding becomes machine-applicable when it carries an extra
``auto_apply`` mapping in addition to the six required CC-v1 finding
fields. The applier ignores findings without ``auto_apply``.

``normalize:strategy_synonym``::

    fix_type: normalize_rule
    target: normalize:strategy_synonym
    auto_apply:
      synonym:  "<lower-alnum drift form>"
      canonical: "<canonical enum value>"

The pair is appended to ``backend/app/pipeline/normalize_rules.json`` and
picked up by ``normalize.py`` at the next import.

``fixture:<rel_path>``::

    target: fixture:backend/app/pipeline/fixtures/golden/research.md
    auto_apply:
      content: |
        ---
        cc_version: '1.0'
        ...
        ---
        ## Summary
        ...

The applier writes ``content`` to ``<repo_root>/<rel_path>`` (creating
parent directories as needed). The path must live under
``backend/app/pipeline/fixtures/`` to bound the blast radius.

CLI
---

::

    python -m app.pipeline.auto_improver \\
        --space /path/to/space \\
        --slug  my-feature
    # add --dry-run to plan without writing or bumping
    # add --json to emit a machine-readable report

Exit codes::

    0  applier ran and either applied changes (evals green) or had nothing
       to apply
    1  applier ran, applied changes, evals went red → all changes rolled
       back. The caller (pipeline-gate Step 3c) keeps the gate at PASS
       because the retro itself verified; the rollback is logged.
    2  artifact not found / unparseable / usage error
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("cronos.auto_improver")


# ---------------------------------------------------------------------------
# Constants & paths
# ---------------------------------------------------------------------------

# Repository root = backend/app/pipeline → 3 parents up.
_PIPELINE_PKG_DIR: Path = Path(__file__).resolve().parent
_BACKEND_DIR: Path = _PIPELINE_PKG_DIR.parent.parent
_REPO_ROOT: Path = _BACKEND_DIR.parent
_NORMALIZE_RULES_PATH: Path = _PIPELINE_PKG_DIR / "normalize_rules.json"
_CONTRACT_PY_PATH: Path = _PIPELINE_PKG_DIR / "contract.py"
_SCHEMAS_DIR: Path = _PIPELINE_PKG_DIR / "schemas"
_FIXTURES_DIR: Path = _PIPELINE_PKG_DIR / "fixtures"
_FIXTURES_ROOT_REL: str = "backend/app/pipeline/fixtures/"

# Recipe target identifiers.
NORMALIZE_STRATEGY_SYNONYM_TARGET: str = "normalize:strategy_synonym"
FIXTURE_TARGET_PREFIX: str = "fixture:"

# Default eval command — the CC-v1 fixture harness (goal-1 baseline).
DEFAULT_EVALS_COMMAND: tuple[str, ...] = (
    sys.executable,
    "-m",
    "pytest",
    "backend/tests/test_pipeline_fixtures.py",
    "-q",
    "--no-header",
)

# Fix types that are NEVER auto-applied — human review required.
_HUMAN_REVIEW_FIX_TYPES: frozenset[str] = frozenset({
    "agent_prompt_refinement",
    "contract_change",
})


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class AppliedChange:
    """A single successfully applied recipe."""
    finding_id: str
    fix_type: str
    target: str
    recipe: str
    files_modified: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "fix_type": self.fix_type,
            "target": self.target,
            "recipe": self.recipe,
            "files_modified": list(self.files_modified),
        }


@dataclass
class SkippedFinding:
    """A finding the applier deliberately did not act on."""
    finding_id: str
    fix_type: str
    target: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "fix_type": self.fix_type,
            "target": self.target,
            "reason": self.reason,
        }


@dataclass
class ApplierResult:
    """Outcome of one ``apply_retro_improvements()`` invocation."""
    slug: str
    retro_path: str
    applied: list[AppliedChange] = field(default_factory=list)
    skipped: list[SkippedFinding] = field(default_factory=list)
    evals_ran: bool = False
    evals_passed: bool | None = None
    evals_output: str = ""
    cc_version_before: str | None = None
    cc_version_after: str | None = None
    rolled_back: bool = False
    rollback_reason: str | None = None
    error: str | None = None
    dry_run: bool = False

    @property
    def had_change(self) -> bool:
        """True iff at least one recipe ran (regardless of rollback)."""
        return len(self.applied) > 0 or self.rolled_back

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "retro_path": self.retro_path,
            "applied": [a.to_dict() for a in self.applied],
            "skipped": [s.to_dict() for s in self.skipped],
            "evals_ran": self.evals_ran,
            "evals_passed": self.evals_passed,
            "evals_output": self.evals_output,
            "cc_version_before": self.cc_version_before,
            "cc_version_after": self.cc_version_after,
            "rolled_back": self.rolled_back,
            "rollback_reason": self.rollback_reason,
            "error": self.error,
            "dry_run": self.dry_run,
        }


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------


_CC_VERSION_RE = re.compile(
    r'^(?P<prefix>CC_VERSION:\s*Final\[str\]\s*=\s*)"(?P<ver>[^"]+)"(?P<suffix>.*)$',
    re.MULTILINE,
)


def read_cc_version(contract_path: Path = _CONTRACT_PY_PATH) -> str:
    """Return the current ``CC_VERSION`` literal from ``contract.py``.

    Raises ``ValueError`` when the constant cannot be located.
    """
    text = contract_path.read_text(encoding="utf-8")
    match = _CC_VERSION_RE.search(text)
    if match is None:
        raise ValueError(
            f"Could not find CC_VERSION literal in {contract_path}"
        )
    return match.group("ver")


def bump_minor(version: str) -> str:
    """Bump the minor component of a ``"<major>.<minor>"`` version string.

    ``"1.0" -> "1.1"``, ``"1.1" -> "1.2"``, ``"2.3" -> "2.4"``.
    Raises ``ValueError`` for shapes the parser does not understand
    (e.g. non-numeric components, missing minor part).
    """
    parts = version.split(".")
    if len(parts) != 2:
        raise ValueError(
            f"Expected '<major>.<minor>' version, got {version!r}"
        )
    try:
        major = int(parts[0])
        minor = int(parts[1])
    except ValueError as exc:
        raise ValueError(
            f"Non-numeric version components in {version!r}"
        ) from exc
    return f"{major}.{minor + 1}"


def _patch_contract_version(new_version: str, contract_path: Path = _CONTRACT_PY_PATH) -> None:
    """Rewrite the ``CC_VERSION`` literal in ``contract.py``."""
    text = contract_path.read_text(encoding="utf-8")
    new_text, count = _CC_VERSION_RE.subn(
        lambda m: f'{m.group("prefix")}"{new_version}"{m.group("suffix")}',
        text,
        count=1,
    )
    if count != 1:
        raise ValueError(
            f"Did not patch CC_VERSION in {contract_path} (count={count})"
        )
    contract_path.write_text(new_text, encoding="utf-8")


def _patch_schema_version(
    schema_path: Path, old_version: str, new_version: str
) -> bool:
    """Rewrite ``const: "<old>"`` under the ``cc_version`` key in one schema.

    Returns True when the file changed. We anchor on the literal block
    ``cc_version:\\n    type: string\\n    const: "<old>"`` so we only touch
    the field that pins the contract version, not any other ``const:`` value.
    """
    text = schema_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(cc_version:\s*\n\s*type:\s*string\s*\n\s*const:\s*)"'
        + re.escape(old_version)
        + r'"',
        re.MULTILINE,
    )
    new_text, count = pattern.subn(rf'\g<1>"{new_version}"', text, count=1)
    if count == 0:
        return False
    schema_path.write_text(new_text, encoding="utf-8")
    return True


_FIXTURE_VERSION_RE_TEMPLATE = (
    r"^(cc_version:\s*)(['\"]?){ver}(['\"]?)\s*$"
)


def _patch_fixture_version(
    fixture_path: Path, old_version: str, new_version: str
) -> bool:
    """Rewrite ``cc_version: '<old>'`` in a fixture front-matter line.

    Only touches fixtures whose current value matches ``old_version`` —
    fixtures that hard-code a bogus version (e.g. the wrong_cc_version
    negative) are intentionally left alone.
    Returns True iff the file was modified.
    """
    text = fixture_path.read_text(encoding="utf-8")
    pattern = re.compile(
        _FIXTURE_VERSION_RE_TEMPLATE.format(ver=re.escape(old_version)),
        re.MULTILINE,
    )
    new_text, count = pattern.subn(
        lambda m: f"{m.group(1)}{m.group(2)}{new_version}{m.group(3)}",
        text,
        count=1,
    )
    if count == 0:
        return False
    fixture_path.write_text(new_text, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Snapshot + rollback
# ---------------------------------------------------------------------------


@dataclass
class _Snapshot:
    """In-memory snapshot of file contents the applier may rewrite.

    A value of ``None`` means the file did not exist before the applier ran
    (so rollback should delete it instead of restoring contents).
    """
    entries: dict[Path, bytes | None] = field(default_factory=dict)

    def capture(self, path: Path) -> None:
        if path in self.entries:
            return  # first-write wins; later mutations stay covered
        if path.exists():
            self.entries[path] = path.read_bytes()
        else:
            self.entries[path] = None

    def restore(self) -> None:
        for path, content in self.entries.items():
            if content is None:
                if path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)


# ---------------------------------------------------------------------------
# Finding parsing
# ---------------------------------------------------------------------------


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (yaml_header_dict, body_str) from a retro artifact."""
    if not text.startswith("---"):
        raise ValueError("Artifact has no YAML front-matter (must start with '---')")
    parts = text.split("\n---", 2)
    if len(parts) < 2:
        raise ValueError("Artifact front-matter is not closed by a '---' line")
    yaml_text = parts[0].lstrip("-").lstrip("\n")
    header = yaml.safe_load(yaml_text)
    if not isinstance(header, dict):
        raise ValueError("Artifact front-matter is not a YAML mapping")
    body = parts[1] if len(parts) == 2 else "\n---".join(parts[1:])
    return header, body


def _load_findings(retro_path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Parse the retro artifact and return (slug, findings)."""
    if not retro_path.exists():
        raise FileNotFoundError(f"Retro artifact not found: {retro_path}")
    text = retro_path.read_text(encoding="utf-8")
    header, _body = _split_frontmatter(text)
    slug = header.get("slug")
    if not isinstance(slug, str) or not slug:
        raise ValueError(
            f"Retro artifact has no usable 'slug' field: {retro_path}"
        )
    findings = header.get("findings")
    if findings is None:
        return slug, []
    if not isinstance(findings, list):
        raise ValueError(
            f"Retro artifact 'findings' must be a list, got "
            f"{type(findings).__name__}: {retro_path}"
        )
    return slug, [f for f in findings if isinstance(f, dict)]


# ---------------------------------------------------------------------------
# Recipe classification
# ---------------------------------------------------------------------------


def _classify_finding(finding: dict[str, Any]) -> tuple[str | None, str]:
    """Return (recipe_name, reason).

    ``recipe_name`` is ``None`` when the finding is to be skipped; in that
    case ``reason`` explains why. When ``recipe_name`` is non-None the
    second value is empty.
    """
    fix_type = finding.get("fix_type", "")
    target = finding.get("target", "")
    auto_apply = finding.get("auto_apply")

    if fix_type in _HUMAN_REVIEW_FIX_TYPES:
        return None, f"fix_type={fix_type!r} requires human review"

    if not isinstance(auto_apply, dict):
        return None, "no auto_apply payload"

    if target == NORMALIZE_STRATEGY_SYNONYM_TARGET:
        if fix_type != "normalize_rule":
            return None, (
                f"target=normalize:strategy_synonym requires "
                f"fix_type=normalize_rule, got {fix_type!r}"
            )
        synonym = auto_apply.get("synonym")
        canonical = auto_apply.get("canonical")
        if not isinstance(synonym, str) or not synonym:
            return None, "auto_apply.synonym missing or not a string"
        if not isinstance(canonical, str) or not canonical:
            return None, "auto_apply.canonical missing or not a string"
        return "normalize_strategy_synonym", ""

    if target.startswith(FIXTURE_TARGET_PREFIX):
        rel_path = target[len(FIXTURE_TARGET_PREFIX):].strip()
        if not rel_path.startswith(_FIXTURES_ROOT_REL):
            return None, (
                f"fixture target must live under {_FIXTURES_ROOT_REL!r}, "
                f"got {rel_path!r}"
            )
        if ".." in Path(rel_path).parts:
            return None, "fixture target uses '..' segment"
        content = auto_apply.get("content")
        if not isinstance(content, str) or not content.strip():
            return None, "auto_apply.content missing or empty"
        return "fixture", ""

    return None, (
        f"unrecognised auto-apply recipe (target={target!r}, "
        f"fix_type={fix_type!r})"
    )


# ---------------------------------------------------------------------------
# Recipe execution
# ---------------------------------------------------------------------------


def _apply_strategy_synonym(
    finding: dict[str, Any],
    repo_root: Path,
    snapshot: _Snapshot,
) -> AppliedChange:
    """Append ``synonym -> canonical`` to ``normalize_rules.json``."""
    rules_path = repo_root / "backend" / "app" / "pipeline" / "normalize_rules.json"
    snapshot.capture(rules_path)
    if rules_path.exists():
        data = json.loads(rules_path.read_text(encoding="utf-8"))
    else:
        data = {}
    syn_map = data.setdefault("strategy_synonyms", {})
    if not isinstance(syn_map, dict):
        syn_map = {}
        data["strategy_synonyms"] = syn_map
    auto_apply = finding["auto_apply"]
    syn_map[str(auto_apply["synonym"])] = str(auto_apply["canonical"])
    rules_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return AppliedChange(
        finding_id=str(finding.get("id", "?")),
        fix_type=str(finding.get("fix_type", "")),
        target=str(finding.get("target", "")),
        recipe="normalize_strategy_synonym",
        files_modified=[str(rules_path.relative_to(repo_root))],
    )


def _apply_fixture(
    finding: dict[str, Any],
    repo_root: Path,
    snapshot: _Snapshot,
) -> AppliedChange:
    """Write the fixture file at the path encoded in ``target``."""
    target = str(finding.get("target", ""))
    rel_path = target[len(FIXTURE_TARGET_PREFIX):].strip()
    dest = (repo_root / rel_path).resolve()
    fixtures_root = (repo_root / _FIXTURES_ROOT_REL).resolve()
    # Defence in depth — refuse to write outside the fixtures dir.
    if not str(dest).startswith(str(fixtures_root)):
        raise ValueError(
            f"Resolved fixture path escapes fixtures root: {dest}"
        )
    snapshot.capture(dest)
    content = finding["auto_apply"]["content"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not content.endswith("\n"):
        content = content + "\n"
    dest.write_text(content, encoding="utf-8")
    return AppliedChange(
        finding_id=str(finding.get("id", "?")),
        fix_type=str(finding.get("fix_type", "")),
        target=target,
        recipe="fixture",
        files_modified=[str(dest.relative_to(repo_root))],
    )


# ---------------------------------------------------------------------------
# Version propagation
# ---------------------------------------------------------------------------


def _bump_and_propagate(
    repo_root: Path,
    snapshot: _Snapshot,
) -> tuple[str, str, list[str]]:
    """Bump ``CC_VERSION`` and propagate to schemas + fixtures.

    Returns (old_version, new_version, files_modified_rel).
    Files whose ``cc_version`` differs from the *current* value are left
    alone — e.g. the ``wrong_cc_version`` negative fixture stays at its
    intentionally-bogus value.
    """
    contract_path = repo_root / "backend" / "app" / "pipeline" / "contract.py"
    schemas_dir = repo_root / "backend" / "app" / "pipeline" / "schemas"
    fixtures_dir = repo_root / "backend" / "app" / "pipeline" / "fixtures"

    old_version = read_cc_version(contract_path)
    new_version = bump_minor(old_version)
    files_modified: list[str] = []

    # contract.py
    snapshot.capture(contract_path)
    _patch_contract_version(new_version, contract_path)
    files_modified.append(str(contract_path.relative_to(repo_root)))

    # schemas/*.schema.yaml
    if schemas_dir.is_dir():
        for schema_path in sorted(schemas_dir.glob("*.schema.yaml")):
            snapshot.capture(schema_path)
            if _patch_schema_version(schema_path, old_version, new_version):
                files_modified.append(str(schema_path.relative_to(repo_root)))

    # fixtures/**/*.md
    if fixtures_dir.is_dir():
        for fixture_path in sorted(fixtures_dir.rglob("*.md")):
            snapshot.capture(fixture_path)
            if _patch_fixture_version(fixture_path, old_version, new_version):
                files_modified.append(str(fixture_path.relative_to(repo_root)))

    return old_version, new_version, files_modified


# ---------------------------------------------------------------------------
# Evals
# ---------------------------------------------------------------------------


def run_evals(
    repo_root: Path,
    command: tuple[str, ...] | list[str] = DEFAULT_EVALS_COMMAND,
    timeout: int = 300,
) -> tuple[bool, str]:
    """Run the goal-1 eval command from ``repo_root``.

    Returns (passed, combined_stdout_stderr). ``passed`` is True iff the
    subprocess exit code is 0.
    """
    try:
        proc = subprocess.run(
            list(command),
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, f"eval command failed to run: {exc!r}"
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_retro_improvements(
    slug: str,
    space: Path | str,
    *,
    retro_path: Path | None = None,
    repo_root: Path | None = None,
    evals_command: tuple[str, ...] | list[str] | None = None,
    evals_timeout: int = 300,
    dry_run: bool = False,
) -> ApplierResult:
    """Apply auto-applicable retro findings, bump CC_VERSION, gate on evals.

    Parameters
    ----------
    slug:
        Goal slug (e.g. ``"my-feature"``).
    space:
        Absolute path to the Cronos space root (the directory holding
        ``.cronos/``). Used to resolve the retro artifact when
        ``retro_path`` is not supplied.
    retro_path:
        Override the canonical retro artifact path
        (``{space}/.cronos/pipeline/{slug}/retro-{slug}.md``).
    repo_root:
        Override the Cronos repository root the applier writes into.
        Defaults to the parent of ``backend/``.
    evals_command:
        Override the eval command. The default is the CC-v1 fixture
        harness (``pytest backend/tests/test_pipeline_fixtures.py``).
    evals_timeout:
        Subprocess timeout in seconds.
    dry_run:
        Plan and classify findings but do not write, bump, or run evals.

    Notes
    -----
    On eval failure, every file touched (including the version bump) is
    restored from the in-memory snapshot. The retro artifact itself is
    NEVER modified.
    """
    space_path = Path(space)
    repo = Path(repo_root) if repo_root is not None else _REPO_ROOT

    if retro_path is None:
        retro_path = (
            space_path / ".cronos" / "pipeline" / slug / f"retro-{slug}.md"
        )
    retro_path = Path(retro_path)

    result = ApplierResult(
        slug=slug,
        retro_path=str(retro_path),
        dry_run=dry_run,
    )

    try:
        artifact_slug, findings = _load_findings(retro_path)
    except (FileNotFoundError, ValueError) as exc:
        result.error = str(exc)
        return result

    if artifact_slug != slug:
        # Honor the artifact's declared slug for routing, but flag the drift.
        log.warning(
            "Retro artifact slug %r does not match caller slug %r — using artifact value",
            artifact_slug,
            slug,
        )
        result.slug = artifact_slug

    # Classify every finding.
    candidates: list[tuple[dict[str, Any], str]] = []  # (finding, recipe)
    for finding in findings:
        finding_id = str(finding.get("id", "?"))
        fix_type = str(finding.get("fix_type", ""))
        target = str(finding.get("target", ""))
        recipe, reason = _classify_finding(finding)
        if recipe is None:
            result.skipped.append(
                SkippedFinding(
                    finding_id=finding_id,
                    fix_type=fix_type,
                    target=target,
                    reason=reason,
                )
            )
            continue
        candidates.append((finding, recipe))

    if not candidates:
        log.info(
            "Retro %s: no auto-applicable findings (%d skipped)",
            slug,
            len(result.skipped),
        )
        result.cc_version_before = read_cc_version(repo / "backend" / "app" / "pipeline" / "contract.py")
        return result

    if dry_run:
        # Populate "would apply" entries but stop short of mutation.
        for finding, recipe in candidates:
            result.applied.append(
                AppliedChange(
                    finding_id=str(finding.get("id", "?")),
                    fix_type=str(finding.get("fix_type", "")),
                    target=str(finding.get("target", "")),
                    recipe=recipe,
                    files_modified=[],
                )
            )
        result.cc_version_before = read_cc_version(repo / "backend" / "app" / "pipeline" / "contract.py")
        result.cc_version_after = bump_minor(result.cc_version_before)
        return result

    snapshot = _Snapshot()
    try:
        for finding, recipe in candidates:
            if recipe == "normalize_strategy_synonym":
                applied = _apply_strategy_synonym(finding, repo, snapshot)
            elif recipe == "fixture":
                applied = _apply_fixture(finding, repo, snapshot)
            else:
                # Unreachable — _classify_finding only returns known names.
                result.skipped.append(
                    SkippedFinding(
                        finding_id=str(finding.get("id", "?")),
                        fix_type=str(finding.get("fix_type", "")),
                        target=str(finding.get("target", "")),
                        reason=f"unknown recipe {recipe!r}",
                    )
                )
                continue
            result.applied.append(applied)

        # Bump CC_VERSION and propagate to schemas + fixtures.
        old_version, new_version, version_files = _bump_and_propagate(
            repo, snapshot
        )
        result.cc_version_before = old_version
        result.cc_version_after = new_version
        # Annotate the synthetic "version bump" change set on each applied entry.
        if result.applied:
            result.applied[0].files_modified.extend(version_files)

        # Run evals.
        cmd = tuple(evals_command) if evals_command is not None else DEFAULT_EVALS_COMMAND
        passed, output = run_evals(repo, cmd, timeout=evals_timeout)
        result.evals_ran = True
        result.evals_passed = passed
        result.evals_output = output

        if not passed:
            snapshot.restore()
            result.rolled_back = True
            result.rollback_reason = (
                f"goal-1 evals failed (exit != 0); applier reverted "
                f"{len(snapshot.entries)} file(s) and the {old_version}->{new_version} bump"
            )
            # Clear the cc_version_after — we rolled it back.
            result.cc_version_after = None
            # Move applied entries into skipped so the caller sees nothing landed.
            for applied in result.applied:
                result.skipped.append(
                    SkippedFinding(
                        finding_id=applied.finding_id,
                        fix_type=applied.fix_type,
                        target=applied.target,
                        reason="rolled back after evals went red",
                    )
                )
            result.applied = []
            log.warning(
                "Retro %s: evals failed; rolled back %d change(s)",
                slug,
                len(snapshot.entries),
            )
            return result

        log.info(
            "Retro %s: applied %d change(s); CC_VERSION %s -> %s",
            slug,
            len(result.applied),
            old_version,
            new_version,
        )
        return result

    except Exception as exc:  # noqa: BLE001 — best-effort rollback
        snapshot.restore()
        result.rolled_back = True
        result.rollback_reason = f"applier raised: {exc!r}; rolled back"
        result.error = f"{type(exc).__name__}: {exc}"
        result.applied = []
        log.exception("Auto-improver crashed; rolled back snapshot")
        return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_human(result: ApplierResult) -> str:
    lines: list[str] = []
    label = "DRY-RUN" if result.dry_run else (
        "ROLLBACK" if result.rolled_back else
        ("APPLIED" if result.applied else "NO-CHANGE")
    )
    lines.append(f"[{label}] slug={result.slug}")
    lines.append(f"         retro={result.retro_path}")
    if result.error:
        lines.append(f"  ERROR: {result.error}")
    if result.cc_version_before is not None:
        lines.append(
            f"  CC_VERSION: {result.cc_version_before}"
            + (f" -> {result.cc_version_after}" if result.cc_version_after else " (unchanged)")
        )
    for applied in result.applied:
        lines.append(
            f"  APPLY: {applied.finding_id} [{applied.recipe}] target={applied.target}"
        )
        for f in applied.files_modified:
            lines.append(f"         + {f}")
    for skipped in result.skipped:
        lines.append(
            f"  SKIP:  {skipped.finding_id} fix_type={skipped.fix_type} — {skipped.reason}"
        )
    if result.evals_ran:
        lines.append(
            f"  EVALS: {'PASS' if result.evals_passed else 'FAIL'}"
        )
    if result.rolled_back and result.rollback_reason:
        lines.append(f"  ROLL:  {result.rollback_reason}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="app.pipeline.auto_improver",
        description=(
            "Apply auto-applicable retro findings (normalize rule + fixture "
            "recipes), bump CC_VERSION, gate on goal-1 evals."
        ),
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="Goal slug identifying the pipeline run.",
    )
    parser.add_argument(
        "--space",
        required=True,
        help="Absolute path to the Cronos space root (the dir holding .cronos/).",
    )
    parser.add_argument(
        "--retro",
        default=None,
        help="Override retro artifact path (default: {space}/.cronos/pipeline/{slug}/retro-{slug}.md).",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Override repo root the applier writes into (default: inferred from this module).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan and classify findings without writing or bumping CC_VERSION.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable lines.",
    )
    parser.add_argument(
        "--evals-timeout",
        type=int,
        default=300,
        help="Subprocess timeout for the eval command (seconds; default 300).",
    )
    args = parser.parse_args(argv)

    space = Path(args.space).resolve()
    if not space.is_dir():
        print(f"ERROR: --space is not a directory: {space}", file=sys.stderr)
        return 2

    retro_override = Path(args.retro).resolve() if args.retro else None
    repo_override = Path(args.repo_root).resolve() if args.repo_root else None

    result = apply_retro_improvements(
        slug=args.slug,
        space=space,
        retro_path=retro_override,
        repo_root=repo_override,
        dry_run=args.dry_run,
        evals_timeout=args.evals_timeout,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(_format_human(result))

    if result.error:
        return 2
    if result.rolled_back:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
