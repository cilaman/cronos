"""CC-v1 artifact verifier.

Validates a pipeline artifact against:

* the relevant per-class YAML schema in :mod:`lib.schemas`,
* the base cross-field rules R1-R7 from
  :mod:`lib.contract`, and
* the per-class extensions (R-impl/R-val/R-rev/R-doc).

The semantics mirror Delivery Notes' ``verify_outputs.py`` adapted for the
Cronos contract (``memory_hits`` replaces ``kb_hits``, ``duration_s`` and
``token_spend`` are trace-owned and must not appear in agent-written headers,
artifacts live under ``{space}/.cronos/pipeline/{parent_slug}/``).

CLI::

    python -m app.pipeline.verify --agent research --slug my-feature --space /path/to/space

``--agent`` is the agent **class** identifier (the schema family the artifact
belongs to). The accepted values are the keys of :data:`CLASS_CONFIG`. The
agent's literal name (e.g. ``scout``, ``architect``) is checked against the
schema rules separately as the ``agent`` YAML field.

Exit codes (Cronos gate vocabulary)::

    0  proceed   — artifact is valid; pipeline may continue
    1  fail      — artifact has hard validation errors
    2  escalate  — artifact is valid but agent itself escalated
                   (status in {blocked, failed}, or gate_decision/verdict
                   explicitly says ``escalate``)
    3  retry     — artifact missing, unreadable, or malformed in a way a
                   re-run could fix (no YAML frontmatter, bad YAML, etc.)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from lib.contract import (
    CC_VERSION,
    FINDINGS_SECTION_ALIASES,
    OPEN_QUESTIONS_SECTION_ALIASES,
    REQUIRED_SECTIONS,
    STATUS_VALUES,
    TRACE_OWNED_METRICS,
)


# ---------------------------------------------------------------------------
# Exit codes — Cronos gate vocabulary
# ---------------------------------------------------------------------------

EXIT_PROCEED = 0
EXIT_FAIL = 1
EXIT_ESCALATE = 2
EXIT_RETRY = 3


# ---------------------------------------------------------------------------
# Class registry: maps the CLI ``--agent`` value to the schema + path template.
# ---------------------------------------------------------------------------

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


CLASS_CONFIG: dict[str, dict[str, str]] = {
    "research": {
        "schema_file": "research.schema.yaml",
        "phase_const": "scout",
        "filename_prefix": "scout-report",
    },
    "analysis": {
        "schema_file": "analysis.schema.yaml",
        "phase_const": "analysis",
        "filename_prefix": "analysis-report",
    },
    "design": {
        "schema_file": "design.schema.yaml",
        "phase_const": "design",
        "filename_prefix": "design-report",
    },
    "implementation": {
        "schema_file": "implementation.schema.yaml",
        "phase_const": "impl",
        "filename_prefix": "impl-report",
    },
    "test": {
        "schema_file": "test.schema.yaml",
        "phase_const": "test",
        "filename_prefix": "test-report",
    },
    "review": {
        "schema_file": "review.schema.yaml",
        "phase_const": "review",
        "filename_prefix": "review-report",
    },
    "doc": {
        "schema_file": "doc.schema.yaml",
        "phase_const": "doc",
        "filename_prefix": "doc-report",
    },
    "retro": {
        "schema_file": "retro.schema.yaml",
        "phase_const": "retro",
        "filename_prefix": "retro",
    },
}


# ---------------------------------------------------------------------------
# Patterns + enums repeated from the schemas for fast in-Python checks.
# ---------------------------------------------------------------------------

BLOCKER_SEVERITY_ENUM = {"low", "medium", "high", "critical"}
FINDING_SEVERITY_ENUM = {"critical", "high", "medium", "low"}
RETRO_FIX_TYPE_ENUM = {
    "normalize_rule",
    "verifier_rule_or_schema_field",
    "agent_prompt_refinement",
    "contract_change",
}
RETRO_SCORE_DIMENSIONS = (
    "planning",
    "error_handling",
    "efficiency",
    "completion",
    "communication",
)

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*(--[a-z0-9]+(-[a-z0-9]+)*)?$")
ITER_PATTERN = re.compile(r"^I[0-9]+$")
REQ_PATTERN = re.compile(r"^R[0-9]+$")
FINDING_PATTERN = re.compile(r"^F[0-9]+$")

VALIDATION_COMMAND_PLACEHOLDERS = {"todo", "tbd", "pending", "run tests", "tests"}

PER_CLASS_REQUIRED_SECTIONS: dict[str, tuple[str, ...]] = {
    # The base REQUIRED_SECTIONS is enforced for every class; per-class
    # schemas may rename slots (Findings -> Decisions, Open questions ->
    # Blockers) but the slot must still be present.
    "implementation": (
        "Summary",
        "Files changed",
        "Out-of-scope findings",
        "Assumptions",
        "Open questions",
        "Next consumer brief",
    ),
    "analysis": (
        "Summary",
        "Scope",
        "Requirements",
        "Acceptance criteria",
        "Traceability",
        "Assumptions",
        "Open questions",
        "Next consumer brief",
    ),
    "design": (
        "Summary",
        "Components",
        "Implementation plan",
        "Risks",
        "Assumptions",
        "Open questions",
        "Next consumer brief",
    ),
    "test": (
        "Summary",
        "Gate result",
        "Failures",
        "Assumptions",
        "Open questions",
        "Next consumer brief",
    ),
    "review": (
        "Summary",
        "Findings",
        "Verdict",
        "Assumptions",
        "Open questions",
        "Next consumer brief",
    ),
    "doc": (
        "Summary",
        "Updated docs",
        "Intentionally not updated",
        "Assumptions",
        "Open questions",
        "Next consumer brief",
    ),
    "retro": (
        "Summary",
        "Scores",
        "Findings",
        "Assumptions",
        "Open questions",
        "Next consumer brief",
    ),
}
"""Per-class section list overrides. Sections that match an entry in
:data:`FINDINGS_SECTION_ALIASES` or :data:`OPEN_QUESTIONS_SECTION_ALIASES`
are matched by any of their aliases, so e.g. ``Findings`` in this list also
accepts ``Decisions`` or ``Top relevance``."""


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class VerifyResult:
    """The verifier's outcome for a single artifact.

    ``passed`` is True iff there are no hard validation errors. ``outcome``
    is the gate decision used to compute the exit code, which can be
    ``"escalate"`` even when ``passed`` is True (agent itself escalated).
    """

    agent: str
    slug: str
    artifact_path: str
    passed: bool = True
    outcome: str = "proceed"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    header: dict[str, Any] | None = None

    def fail(self, msg: str) -> None:
        """Record a hard validation error; outcome -> fail (unless retry)."""
        self.passed = False
        self.errors.append(msg)
        if self.outcome != "retry":
            self.outcome = "fail"

    def retry(self, msg: str) -> None:
        """Record a retryable failure (missing/malformed artifact)."""
        self.passed = False
        self.errors.append(msg)
        self.outcome = "retry"

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def exit_code(self) -> int:
        return {
            "proceed": EXIT_PROCEED,
            "fail": EXIT_FAIL,
            "escalate": EXIT_ESCALATE,
            "retry": EXIT_RETRY,
        }[self.outcome]

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "slug": self.slug,
            "artifact_path": self.artifact_path,
            "passed": self.passed,
            "outcome": self.outcome,
            "exit_code": self.exit_code(),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_schema(class_name: str) -> dict[str, Any]:
    """Load the YAML schema for ``class_name`` from the bundled schemas dir."""
    cfg = CLASS_CONFIG[class_name]
    schema_path = SCHEMAS_DIR / cfg["schema_file"]
    with schema_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def canonical_artifact_relpath(class_name: str, slug: str) -> str:
    """Workspace-relative path to the artifact for ``class_name`` + ``slug``.

    Fan-out / iteration slugs use ``--`` to split a parent goal slug from a
    sub-component (e.g. ``pipeline-foundation--i2``). The directory uses the
    parent part; the filename keeps the full slug verbatim.
    """
    cfg = CLASS_CONFIG[class_name]
    parent_slug = slug.split("--", 1)[0] if "--" in slug else slug
    filename = f"{cfg['filename_prefix']}-{slug}.md"
    return f".cronos/pipeline/{parent_slug}/{filename}"


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Return (header_dict, body). header is None if no `---` frontmatter."""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    yaml_block = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    try:
        header = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML front-matter: {exc}") from exc
    if not isinstance(header, dict):
        raise ValueError("YAML front-matter must be a mapping")
    return header, body


def validate_path_format(value: Any) -> str | None:
    """R7: workspace-relative forward-slash. Return error message or None."""
    if not isinstance(value, str):
        return f"not a string: {value!r}"
    if not value:
        return "empty string"
    if value.startswith("/"):
        return f"absolute Unix path: {value!r} (paths must be workspace-relative)"
    if len(value) >= 2 and value[1] == ":":
        return f"absolute Windows path: {value!r} (paths must be workspace-relative)"
    if "\\" in value:
        return f"backslash separators in {value!r} (use forward slashes)"
    return None


def _is_non_negative_int(value: Any) -> bool:
    """True iff value is an int (not a bool) and >= 0."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_real_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _section_present(body: str, slot: str) -> bool:
    """Check if an H2 section ``## <slot>`` (or an alias) is present in body.

    Sections must appear as line-anchored H2 headings — not merely as text in
    a paragraph or HTML comment (mirrors Delivery Notes F-18 fix).
    """
    aliases: tuple[str, ...]
    if slot == "Findings":
        aliases = FINDINGS_SECTION_ALIASES
    elif slot == "Open questions":
        aliases = OPEN_QUESTIONS_SECTION_ALIASES
    else:
        aliases = (slot,)
    for name in aliases:
        pattern = re.compile(rf"(?m)^##\s+{re.escape(name)}\s*$")
        if pattern.search(body):
            return True
    return False


# ---------------------------------------------------------------------------
# Schema-driven base header checks
# ---------------------------------------------------------------------------


def _check_required_header_fields(
    result: VerifyResult, schema: dict[str, Any], header: dict[str, Any]
) -> None:
    """Required fields from the per-class schema must all be present."""
    required = schema.get("required", []) or []
    missing = [f for f in required if f not in header]
    if missing:
        result.fail(f"missing required header fields: {', '.join(missing)}")


def _check_cc_version(result: VerifyResult, header: dict[str, Any]) -> None:
    """cc_version must equal the supported CC_VERSION."""
    if "cc_version" not in header:
        return  # already reported by required-fields check
    cc = header["cc_version"]
    if cc != CC_VERSION:
        result.fail(
            f"cc_version={cc!r} not supported by this verifier "
            f"(expected {CC_VERSION!r})"
        )


def _check_phase(
    result: VerifyResult, class_name: str, header: dict[str, Any]
) -> None:
    """phase header field must equal the class's phase const."""
    if "phase" not in header:
        return
    expected = CLASS_CONFIG[class_name]["phase_const"]
    actual = header["phase"]
    if actual != expected:
        result.fail(
            f"phase={actual!r} does not match {class_name!r} class phase const "
            f"({expected!r})"
        )


def _check_agent_field(result: VerifyResult, header: dict[str, Any]) -> None:
    """The agent header field must be a non-empty string."""
    if "agent" not in header:
        return
    agent_name = header["agent"]
    if not isinstance(agent_name, str) or not agent_name.strip():
        result.fail(f"agent must be a non-empty string, got {agent_name!r}")


def _check_slug_format(result: VerifyResult, header: dict[str, Any]) -> None:
    """slug must match the kebab-case pattern."""
    if "slug" not in header:
        return
    slug_val = header["slug"]
    if not isinstance(slug_val, str):
        result.fail(f"slug must be a string, got {type(slug_val).__name__}")
        return
    if not SLUG_PATTERN.match(slug_val):
        result.fail(
            f"slug {slug_val!r} does not match kebab-case pattern "
            r"^[a-z0-9]+(-[a-z0-9]+)*(--[a-z0-9]+(-[a-z0-9]+)*)?$"
        )


def _check_status_value(result: VerifyResult, header: dict[str, Any]) -> None:
    if "status" not in header:
        return
    status = header["status"]
    if status not in STATUS_VALUES:
        result.fail(f"status {status!r} not in {sorted(STATUS_VALUES)}")


def _check_blockers(result: VerifyResult, header: dict[str, Any]) -> None:
    """blockers[] must be a list of {description, severity} objects."""
    blockers = header.get("blockers")
    if blockers is None:
        return
    if not isinstance(blockers, list):
        result.fail("blockers must be a list")
        return
    for idx, b in enumerate(blockers):
        if not isinstance(b, dict):
            result.fail(f"blockers[{idx}] must be a mapping")
            continue
        if "description" not in b or "severity" not in b:
            result.fail(f"blockers[{idx}] missing description or severity")
        sev = b.get("severity")
        if sev is not None and sev not in BLOCKER_SEVERITY_ENUM:
            result.fail(
                f"blockers[{idx}].severity {sev!r} not in "
                f"{sorted(BLOCKER_SEVERITY_ENUM)}"
            )
        desc = b.get("description")
        if desc is not None and (
            not isinstance(desc, str) or not desc.strip()
        ):
            result.fail(f"blockers[{idx}].description must be a non-empty string")


def _check_metrics(
    result: VerifyResult, schema: dict[str, Any], header: dict[str, Any]
) -> None:
    """Per-schema required metrics + non-negative-integer counts."""
    metrics = header.get("metrics")
    if not isinstance(metrics, dict):
        result.fail("metrics must be a mapping")
        return
    metrics_schema = schema.get("properties", {}).get("metrics", {})
    required_metrics = metrics_schema.get("required", []) or []
    missing = [m for m in required_metrics if m not in metrics]
    if missing:
        result.fail(f"missing required metrics: {', '.join(missing)}")
    if "tool_calls" in metrics:
        tc = metrics["tool_calls"]
        if not _is_non_negative_int(tc) or tc < 1:
            result.fail(
                f"metrics.tool_calls must be a positive integer (>=1), got {tc!r}"
            )
    for key in ("files_read", "memory_hits"):
        if key in metrics and not _is_non_negative_int(metrics[key]):
            result.fail(
                f"metrics.{key} must be a non-negative integer, got {metrics[key]!r}"
            )
    # Trace-owned metrics MUST NOT appear in agent-written artifacts.
    for trace_key in TRACE_OWNED_METRICS:
        if trace_key in metrics:
            result.fail(
                f"metrics.{trace_key} is trace-owned — agents MUST NOT write it"
            )


def _check_required_sections(
    result: VerifyResult, class_name: str, body: str
) -> None:
    """Verify the markdown body contains the required H2 sections."""
    sections = PER_CLASS_REQUIRED_SECTIONS.get(class_name, REQUIRED_SECTIONS)
    for slot in sections:
        if not _section_present(body, slot):
            # Surface the slot name + any aliases in the error message so an
            # agent or human reading the verifier output can pick the right
            # variant.
            if slot == "Findings":
                names = " | ".join(f"## {n}" for n in FINDINGS_SECTION_ALIASES)
            elif slot == "Open questions":
                names = " | ".join(
                    f"## {n}" for n in OPEN_QUESTIONS_SECTION_ALIASES
                )
            else:
                names = f"## {slot}"
            result.fail(f"missing required section ({names})")


def _check_path_lists(result: VerifyResult, header: dict[str, Any]) -> None:
    """R7: inputs_used / outputs_produced are workspace-relative forward-slash."""
    inputs = header.get("inputs_used")
    if isinstance(inputs, list):
        for idx, p in enumerate(inputs):
            err = validate_path_format(p)
            if err:
                result.fail(f"R7: inputs_used[{idx}] {err}")
    elif inputs is not None:
        result.fail("inputs_used must be a list")

    outputs = header.get("outputs_produced")
    if isinstance(outputs, list):
        if not outputs:
            result.fail("outputs_produced must contain at least one entry")
        for idx, p in enumerate(outputs):
            err = validate_path_format(p)
            if err:
                result.fail(f"R7: outputs_produced[{idx}] {err}")
    elif outputs is not None:
        result.fail("outputs_produced must be a list")


def _check_R1_R6(
    result: VerifyResult,
    header: dict[str, Any],
    slug: str,
    artifact_rel: str,
) -> None:
    """Cross-field rules R1 through R6.

    R7 is enforced in :func:`_check_path_lists`; R3 is enforced as part of
    the confidence value check below.
    """
    status = header.get("status")
    confidence = header.get("confidence")
    blockers = header.get("blockers")
    inputs = header.get("inputs_used")
    outputs = header.get("outputs_produced")
    metrics = header.get("metrics") if isinstance(header.get("metrics"), dict) else {}

    # R1 — non-empty blockers requires status in {blocked, failed}
    has_blockers = isinstance(blockers, list) and len(blockers) > 0
    if has_blockers and status not in {"blocked", "failed"}:
        result.fail(
            "R1: non-empty blockers[] requires status in {blocked, failed}; "
            f"got status={status!r}"
        )

    # R3 — confidence in [0.0, 1.0] AND must be a number
    if confidence is not None:
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            result.fail(f"R3: confidence must be a number, got {confidence!r}")
        elif not 0.0 <= float(confidence) <= 1.0:
            result.fail(f"R3: confidence {confidence} not in [0.0, 1.0]")

    # R2 — status=done requires confidence >= 0.7
    if (
        status == "done"
        and isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        and 0.0 <= float(confidence) <= 1.0
        and float(confidence) < 0.7
    ):
        result.fail(
            f"R2: status=done requires confidence>=0.7; got {float(confidence)}"
        )

    # R4 — files_read + memory_hits >= len(inputs_used)
    files_read = metrics.get("files_read", 0)
    memory_hits = metrics.get("memory_hits", 0)
    if not isinstance(files_read, int) or isinstance(files_read, bool):
        files_read = 0
    if not isinstance(memory_hits, int) or isinstance(memory_hits, bool):
        memory_hits = 0
    if isinstance(inputs, list):
        accessible = files_read + memory_hits
        if accessible < len(inputs):
            result.fail(
                f"R4: metrics.files_read ({files_read}) + memory_hits "
                f"({memory_hits}) = {accessible} < len(inputs_used) "
                f"({len(inputs)})"
            )

    # R5 — outputs_produced[0] matches canonical artifact path (warning)
    if isinstance(outputs, list) and outputs:
        first = outputs[0]
        if first != artifact_rel:
            result.warn(
                f"R5: outputs_produced[0] ({first!r}) does not match canonical "
                f"artifact path ({artifact_rel!r})"
            )

    # R6 — slug in header equals slug passed by orchestrator
    header_slug = header.get("slug")
    if header_slug != slug:
        result.fail(
            f"R6: header.slug={header_slug!r} does not equal orchestrator "
            f"slug={slug!r}; agents MUST NOT re-derive the slug"
        )


# ---------------------------------------------------------------------------
# Per-class extensions
# ---------------------------------------------------------------------------


def _check_research(result: VerifyResult, header: dict[str, Any]) -> None:
    cov = header.get("coverage_summary")
    if not isinstance(cov, dict):
        result.fail("coverage_summary must be a mapping")
        return
    for sub in ("searched", "excluded", "strategies"):
        if sub not in cov:
            result.fail(f"coverage_summary.{sub} missing")
    strategies = cov.get("strategies")
    allowed = {
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
    if isinstance(strategies, list):
        if not strategies:
            result.fail("coverage_summary.strategies must contain at least one entry")
        for idx, s in enumerate(strategies):
            if not isinstance(s, str):
                result.fail(
                    f"coverage_summary.strategies[{idx}] must be a string, got {s!r}"
                )
            elif s not in allowed:
                result.fail(
                    f"coverage_summary.strategies[{idx}] {s!r} not in "
                    f"{sorted(allowed)}"
                )


def _check_analysis(result: VerifyResult, header: dict[str, Any]) -> None:
    # has_ui must be a real boolean
    if "has_ui" in header and not _is_real_bool(header["has_ui"]):
        result.fail(
            f"has_ui must be a boolean, got "
            f"{type(header['has_ui']).__name__}: {header['has_ui']!r}"
        )
    # request must be non-empty string
    req = header.get("request")
    if req is not None and (not isinstance(req, str) or not req.strip()):
        result.fail("request must be a non-empty string (verbatim user request)")
    # traceability rows
    traceability = header.get("traceability")
    if traceability is not None:
        if not isinstance(traceability, list):
            result.fail("traceability must be a list")
        elif not traceability:
            result.fail("traceability must contain at least one requirement")
        else:
            allowed_verifiers = {"test", "review", "design", "manual"}
            seen: set[str] = set()
            for idx, row in enumerate(traceability):
                if not isinstance(row, dict):
                    result.fail(f"traceability[{idx}] must be a mapping")
                    continue
                for f in (
                    "requirement_id",
                    "statement",
                    "acceptance_criteria",
                    "verifying_phase",
                ):
                    if f not in row:
                        result.fail(
                            f"traceability[{idx}] missing required field {f!r}"
                        )
                req_id = row.get("requirement_id")
                if isinstance(req_id, str):
                    if not REQ_PATTERN.match(req_id):
                        result.fail(
                            f"traceability[{idx}].requirement_id {req_id!r} "
                            "does not match pattern '^R[0-9]+$'"
                        )
                    if req_id in seen:
                        result.fail(
                            f"traceability[{idx}].requirement_id {req_id!r} duplicated"
                        )
                    seen.add(req_id)
                ac = row.get("acceptance_criteria")
                if ac is not None:
                    if not isinstance(ac, list):
                        result.fail(
                            f"traceability[{idx}].acceptance_criteria must be a list"
                        )
                    elif not ac:
                        result.fail(
                            f"traceability[{idx}].acceptance_criteria must be non-empty"
                        )
                verifier = row.get("verifying_phase")
                if verifier is not None and verifier not in allowed_verifiers:
                    result.fail(
                        f"traceability[{idx}].verifying_phase {verifier!r} not in "
                        f"{sorted(allowed_verifiers)}"
                    )
                per_conf = row.get("confidence")
                if per_conf is not None:
                    if (
                        not isinstance(per_conf, (int, float))
                        or isinstance(per_conf, bool)
                    ):
                        result.fail(
                            f"traceability[{idx}].confidence must be a number"
                        )
                    elif not 0.0 <= float(per_conf) <= 1.0:
                        result.fail(
                            f"traceability[{idx}].confidence {per_conf} not in [0.0, 1.0]"
                        )


def _check_design(result: VerifyResult, header: dict[str, Any]) -> None:
    # risks[]
    risks = header.get("risks")
    if risks is not None:
        if not isinstance(risks, list):
            result.fail("risks must be a list")
        elif not risks:
            result.fail("risks must contain at least one entry")
        else:
            for idx, r in enumerate(risks):
                if not isinstance(r, dict):
                    result.fail(f"risks[{idx}] must be a mapping")
                    continue
                for f in ("description", "severity", "mitigation"):
                    if f not in r:
                        result.fail(f"risks[{idx}] missing required field {f!r}")
                sev = r.get("severity")
                if sev is not None and sev not in BLOCKER_SEVERITY_ENUM:
                    result.fail(
                        f"risks[{idx}].severity {sev!r} not in "
                        f"{sorted(BLOCKER_SEVERITY_ENUM)}"
                    )
                mit = r.get("mitigation")
                if mit is not None and (not isinstance(mit, str) or not mit.strip()):
                    result.fail(f"risks[{idx}].mitigation must be a non-empty string")

    # iterations[]
    iterations = header.get("iterations")
    if iterations is not None:
        if not isinstance(iterations, list):
            result.fail("iterations must be a list")
        elif not iterations:
            result.fail("iterations must contain at least one entry")
        else:
            allowed_types = {"data", "backend", "frontend", "infra"}
            seen_ids: set[str] = set()
            for idx, it in enumerate(iterations):
                if not isinstance(it, dict):
                    result.fail(f"iterations[{idx}] must be a mapping")
                    continue
                for f in (
                    "id",
                    "type",
                    "scope_files",
                    "validation_command",
                    "depends_on",
                ):
                    if f not in it:
                        result.fail(
                            f"iterations[{idx}] missing required field {f!r}"
                        )
                iid = it.get("id")
                if isinstance(iid, str):
                    if not ITER_PATTERN.match(iid):
                        result.fail(
                            f"iterations[{idx}].id {iid!r} does not match "
                            "pattern '^I[0-9]+$'"
                        )
                    if iid in seen_ids:
                        result.fail(f"iterations[{idx}].id {iid!r} duplicated")
                    seen_ids.add(iid)
                itype = it.get("type")
                if itype is not None and itype not in allowed_types:
                    result.fail(
                        f"iterations[{idx}].type {itype!r} not in {sorted(allowed_types)}"
                    )
                scope = it.get("scope_files")
                if scope is not None:
                    if not isinstance(scope, list):
                        result.fail(f"iterations[{idx}].scope_files must be a list")
                    else:
                        for sidx, sp in enumerate(scope):
                            err = validate_path_format(sp)
                            if err:
                                result.fail(
                                    f"iterations[{idx}].scope_files[{sidx}] {err}"
                                )
                vc = it.get("validation_command")
                if vc is None or not isinstance(vc, str) or not vc.strip():
                    result.fail(
                        f"iterations[{idx}].validation_command must be a non-empty string"
                    )
                elif vc.strip().lower() in VALIDATION_COMMAND_PLACEHOLDERS:
                    result.fail(
                        f"iterations[{idx}].validation_command is a placeholder "
                        f"({vc!r}) — must be a concrete executable command"
                    )
                deps = it.get("depends_on")
                if deps is not None and not isinstance(deps, list):
                    result.fail(f"iterations[{idx}].depends_on must be a list")

            # depends_on dangling references — all refs must exist in iterations[]
            for idx, it in enumerate(iterations):
                if not isinstance(it, dict):
                    continue
                for dep in it.get("depends_on") or []:
                    if dep not in seen_ids:
                        result.fail(
                            f"iterations[{idx}].depends_on references unknown "
                            f"iteration id {dep!r} (known: {sorted(seen_ids)})"
                        )

            # iterations_planned (if present) must equal len(iterations)
            metrics = header.get("metrics") or {}
            ip = metrics.get("iterations_planned") if isinstance(metrics, dict) else None
            if isinstance(ip, int) and not isinstance(ip, bool):
                if ip != len(iterations):
                    result.fail(
                        f"metrics.iterations_planned={ip} does not match "
                        f"len(iterations)={len(iterations)}"
                    )


def _check_implementation(
    result: VerifyResult, header: dict[str, Any], slug: str
) -> None:
    """R-impl-1..6."""
    iter_id = header.get("iteration_id")
    # R-impl-1: iteration_id matches ^I[0-9]+$
    if iter_id is None:
        # already reported by required-fields check
        pass
    elif not isinstance(iter_id, str) or not ITER_PATTERN.match(iter_id):
        result.fail(
            f"R-impl-1: iteration_id {iter_id!r} does not match pattern '^I[0-9]+$'"
        )
    else:
        # R-impl-2: slug ends with "--<iter_id_lower>" when slug contains "--"
        if "--" in slug:
            expected_suffix = "--" + iter_id.lower()
            if not slug.endswith(expected_suffix):
                result.fail(
                    f"R-impl-2: slug {slug!r} does not end with expected suffix "
                    f"{expected_suffix!r} (convention: "
                    "slug=<goal_slug>--<iteration_id.lower()>)"
                )

    # R-impl-3: files_changed non-empty when status=done
    files_changed = header.get("files_changed")
    status = header.get("status")
    if files_changed is None:
        pass
    elif not isinstance(files_changed, list):
        result.fail("files_changed must be a list")
    else:
        for idx, p in enumerate(files_changed):
            err = validate_path_format(p)
            if err:
                result.fail(f"files_changed[{idx}] {err}")
        if not files_changed and status == "done":
            result.fail(
                "R-impl-3: files_changed must be non-empty when status=done"
            )

    # R-impl-4: validation_command_passed is a real boolean
    vcp = header.get("validation_command_passed")
    if vcp is not None and not _is_real_bool(vcp):
        result.fail(
            f"R-impl-4: validation_command_passed must be a boolean, got "
            f"{type(vcp).__name__}: {vcp!r}"
        )

    # R-impl-5: validation_command_passed=false + status=done is rejected
    if vcp is False and status == "done":
        result.fail(
            "R-impl-5: validation_command_passed=false with status=done is "
            "incoherent — set status to partial/blocked/failed when validation fails"
        )

    # R-impl-6: metrics.diff_lines_added / diff_lines_removed non-negative ints
    metrics = header.get("metrics")
    if isinstance(metrics, dict):
        for key in ("diff_lines_added", "diff_lines_removed"):
            if key in metrics and not _is_non_negative_int(metrics[key]):
                result.fail(
                    f"R-impl-6: metrics.{key} must be a non-negative integer, "
                    f"got {metrics[key]!r}"
                )

    # out_of_scope_findings structural check (optional field)
    oof = header.get("out_of_scope_findings")
    if oof is not None:
        if not isinstance(oof, list):
            result.fail("out_of_scope_findings must be a list")
        else:
            for idx, f in enumerate(oof):
                if not isinstance(f, dict):
                    result.fail(f"out_of_scope_findings[{idx}] must be a mapping")
                    continue
                for fn in ("description", "location", "severity"):
                    if fn not in f:
                        result.fail(
                            f"out_of_scope_findings[{idx}] missing required field {fn!r}"
                        )
                sev = f.get("severity")
                if sev is not None and sev not in BLOCKER_SEVERITY_ENUM:
                    result.fail(
                        f"out_of_scope_findings[{idx}].severity {sev!r} not in "
                        f"{sorted(BLOCKER_SEVERITY_ENUM)}"
                    )


def _check_test(result: VerifyResult, header: dict[str, Any]) -> None:
    """R-val-1..5."""
    allowed = {"pass", "fail", "escalate"}
    # R-val-1: gate_decision in {pass, fail, escalate}
    gate = header.get("gate_decision")
    if gate is not None and gate not in allowed:
        result.fail(f"R-val-1: gate_decision {gate!r} not in {sorted(allowed)}")

    # R-val-2: passed/failed/errors non-negative integers
    for key in ("passed", "failed", "errors"):
        v = header.get(key)
        if v is None:
            continue
        if not _is_non_negative_int(v):
            result.fail(
                f"R-val-2: {key} must be a non-negative integer, got {v!r}"
            )

    # R-val-3: gate_decision=pass implies failed=0
    if gate == "pass":
        failed_count = header.get("failed", 0)
        if isinstance(failed_count, int) and not isinstance(failed_count, bool):
            if failed_count > 0:
                result.fail(
                    f"R-val-3: gate_decision='pass' with failed={failed_count} "
                    "is incoherent"
                )


def _check_review(result: VerifyResult, header: dict[str, Any]) -> None:
    """R-rev-1..6."""
    allowed_verdicts = {"pass", "fail", "needs_fix"}
    verdict = header.get("verdict")
    # R-rev-1: verdict in {pass, fail, needs_fix}
    if verdict is not None and verdict not in allowed_verdicts:
        result.fail(
            f"R-rev-1: verdict {verdict!r} not in {sorted(allowed_verdicts)}"
        )

    findings = header.get("findings")
    if findings is None:
        return
    if not isinstance(findings, list):
        result.fail("findings must be a list")
        return
    seen_ids: set[str] = set()
    has_blocking = False
    for idx, f in enumerate(findings):
        if not isinstance(f, dict):
            result.fail(f"findings[{idx}] must be a mapping")
            continue
        for fn in ("id", "severity", "file", "evidence", "blocking", "suggested_action"):
            if fn not in f:
                result.fail(f"findings[{idx}] missing required field {fn!r}")
        fid = f.get("id")
        if isinstance(fid, str):
            # R-rev-2: ^F[0-9]+$
            if not FINDING_PATTERN.match(fid):
                result.fail(
                    f"R-rev-2: findings[{idx}].id {fid!r} does not match '^F[0-9]+$'"
                )
            # R-rev-3: unique
            elif fid in seen_ids:
                result.fail(f"R-rev-3: findings[{idx}].id {fid!r} is duplicated")
            else:
                seen_ids.add(fid)
        sev = f.get("severity")
        # R-rev-6: finding.severity in {critical, high, medium, low}
        if sev is not None and sev not in FINDING_SEVERITY_ENUM:
            result.fail(
                f"R-rev-6: findings[{idx}].severity {sev!r} not in "
                f"{sorted(FINDING_SEVERITY_ENUM)}"
            )
        blocking = f.get("blocking")
        if blocking is True:
            has_blocking = True
        elif blocking is not None and not _is_real_bool(blocking):
            result.fail(
                f"findings[{idx}].blocking must be a boolean, got {blocking!r}"
            )
        # finding.file: path:line allowed; path portion is workspace-relative
        fpath = f.get("file")
        if isinstance(fpath, str):
            path_only = fpath.split(":", 1)[0]
            perr = validate_path_format(path_only)
            if perr:
                result.fail(f"findings[{idx}].file {perr}")

    # R-rev-4: verdict=pass implies no blocking findings
    # R-rev-5 (contrapositive): blocking finding implies verdict != pass
    if verdict == "pass" and has_blocking:
        result.fail(
            "R-rev-4: verdict='pass' is incoherent with a finding marked "
            "blocking=true"
        )


def _check_doc(result: VerifyResult, header: dict[str, Any], artifact_rel: str) -> None:
    """R-doc-1..5."""
    outputs = header.get("outputs_produced")
    inu = header.get("intentionally_not_updated")
    status = header.get("status")
    metrics = header.get("metrics")

    # R-doc-1: outputs_produced[0] is always the doc report itself
    if isinstance(outputs, list) and outputs:
        if outputs[0] != artifact_rel:
            result.fail(
                f"R-doc-1: outputs_produced[0]={outputs[0]!r} must equal the "
                f"doc report path itself ({artifact_rel!r})"
            )

    # R-doc-2: each path in outputs_produced[1:] must be a valid workspace-relative path
    # Path format is already enforced by R7 in _check_path_lists; here we
    # additionally require it to be syntactically a doc path (any path is
    # acceptable structurally — the agent claims it touched it).

    # R-doc-3: intentionally_not_updated must be present (empty list acceptable)
    if inu is None:
        result.fail(
            "R-doc-3: intentionally_not_updated must be present (empty list acceptable)"
        )
    elif not isinstance(inu, list):
        result.fail("intentionally_not_updated must be a list")
    else:
        for idx, entry in enumerate(inu):
            if not isinstance(entry, dict):
                result.fail(f"intentionally_not_updated[{idx}] must be a mapping")
                continue
            for fn in ("path", "reason"):
                if fn not in entry:
                    result.fail(
                        f"intentionally_not_updated[{idx}] missing required field {fn!r}"
                    )
            p = entry.get("path")
            if isinstance(p, str):
                err = validate_path_format(p)
                if err:
                    result.fail(f"intentionally_not_updated[{idx}].path {err}")
            reason = entry.get("reason")
            if reason is not None and (not isinstance(reason, str) or not reason.strip()):
                result.fail(
                    f"intentionally_not_updated[{idx}].reason must be a non-empty string"
                )

    # R-doc-4: status=done with only the report in outputs_produced requires
    # non-empty intentionally_not_updated.
    if status == "done" and isinstance(outputs, list):
        updated_doc_count = max(0, len(outputs) - 1)
        if updated_doc_count == 0:
            if not isinstance(inu, list) or not inu:
                result.fail(
                    "R-doc-4: status=done with only the report in outputs_produced "
                    "requires non-empty intentionally_not_updated (a silent no-op "
                    "is not a valid doc-sync outcome)"
                )

    # R-doc-5: metrics.docs_updated (if present) == len(outputs_produced) - 1
    if isinstance(metrics, dict) and "docs_updated" in metrics:
        declared = metrics.get("docs_updated")
        if isinstance(declared, int) and not isinstance(declared, bool):
            actual = max(0, len(outputs) - 1) if isinstance(outputs, list) else 0
            if declared != actual:
                result.fail(
                    f"R-doc-5: metrics.docs_updated={declared} does not match "
                    f"len(outputs_produced)-1 ({actual})"
                )


def _check_retro(result: VerifyResult, header: dict[str, Any]) -> None:
    """R-retro-1..4."""
    outputs = header.get("outputs_produced")
    scores = header.get("scores")
    findings = header.get("findings")

    # R-retro-1: outputs_produced has exactly one entry (the retro itself).
    if isinstance(outputs, list) and len(outputs) != 1:
        result.fail(
            f"R-retro-1: retro outputs_produced must have exactly one entry "
            f"(the retro artifact); got {len(outputs)}"
        )

    # R-retro-3: scores object has all five dimensions, each int in [1, 5].
    if scores is None:
        # already reported by required-fields check
        pass
    elif not isinstance(scores, dict):
        result.fail("R-retro-3: scores must be a mapping")
    else:
        for dim in RETRO_SCORE_DIMENSIONS:
            if dim not in scores:
                result.fail(f"R-retro-3: scores.{dim} missing")
                continue
            val = scores[dim]
            if not _is_non_negative_int(val):
                result.fail(
                    f"R-retro-3: scores.{dim} must be an integer, got {val!r}"
                )
            elif not 1 <= val <= 5:
                result.fail(
                    f"R-retro-3: scores.{dim} {val} out of range [1, 5]"
                )

    # R-retro-2 + R-retro-4: findings structure + fix_type + unique F-ids.
    if findings is None:
        return
    if not isinstance(findings, list):
        result.fail("findings must be a list")
        return
    seen_ids: set[str] = set()
    for idx, f in enumerate(findings):
        if not isinstance(f, dict):
            result.fail(f"findings[{idx}] must be a mapping")
            continue
        for fn in ("id", "severity", "fix_type", "target", "evidence", "suggested_action"):
            if fn not in f:
                result.fail(f"findings[{idx}] missing required field {fn!r}")
        fid = f.get("id")
        if isinstance(fid, str):
            # R-retro-4: id matches ^F[0-9]+$ and is unique within findings[].
            if not FINDING_PATTERN.match(fid):
                result.fail(
                    f"R-retro-4: findings[{idx}].id {fid!r} does not match '^F[0-9]+$'"
                )
            elif fid in seen_ids:
                result.fail(f"R-retro-4: findings[{idx}].id {fid!r} is duplicated")
            else:
                seen_ids.add(fid)
        sev = f.get("severity")
        if sev is not None and sev not in FINDING_SEVERITY_ENUM:
            result.fail(
                f"findings[{idx}].severity {sev!r} not in "
                f"{sorted(FINDING_SEVERITY_ENUM)}"
            )
        # R-retro-2: every finding has a fix_type from the enum.
        fix_type = f.get("fix_type")
        if fix_type is None:
            # already reported by required-fields check
            pass
        elif fix_type not in RETRO_FIX_TYPE_ENUM:
            result.fail(
                f"R-retro-2: findings[{idx}].fix_type {fix_type!r} not in "
                f"{sorted(RETRO_FIX_TYPE_ENUM)}"
            )
        target = f.get("target")
        if target is not None and (not isinstance(target, str) or not target.strip()):
            result.fail(f"findings[{idx}].target must be a non-empty string")
        action = f.get("suggested_action")
        if action is not None and (not isinstance(action, str) or not action.strip()):
            result.fail(f"findings[{idx}].suggested_action must be a non-empty string")


# ---------------------------------------------------------------------------
# Top-level verify
# ---------------------------------------------------------------------------


def verify(agent: str, slug: str, space: Path) -> VerifyResult:
    """Verify the artifact for ``agent`` (class) + ``slug`` under ``space``."""
    if agent not in CLASS_CONFIG:
        result = VerifyResult(agent=agent, slug=slug, artifact_path="<unknown>")
        result.fail(
            f"unknown agent class {agent!r}; expected one of "
            f"{sorted(CLASS_CONFIG.keys())}"
        )
        return result

    artifact_rel = canonical_artifact_relpath(agent, slug)
    artifact_path = space / artifact_rel
    result = VerifyResult(agent=agent, slug=slug, artifact_path=artifact_rel)

    # 1. Artifact existence
    if not artifact_path.exists():
        result.retry(f"artifact not found at expected path: {artifact_rel}")
        return result
    if not artifact_path.is_file():
        result.retry(f"artifact path is not a file: {artifact_rel}")
        return result

    # 2. Read + parse YAML frontmatter
    try:
        text = artifact_path.read_text(encoding="utf-8")
    except OSError as exc:
        result.retry(f"cannot read artifact: {exc}")
        return result

    try:
        header, body = split_frontmatter(text)
    except ValueError as exc:
        result.retry(str(exc))
        return result

    if header is None:
        result.retry(
            "artifact has no YAML front-matter block (must start with '---')"
        )
        return result

    result.header = header

    # 3. Schema-driven base checks
    schema = load_schema(agent)
    _check_required_header_fields(result, schema, header)
    _check_cc_version(result, header)
    _check_agent_field(result, header)
    _check_phase(result, agent, header)
    _check_slug_format(result, header)
    _check_status_value(result, header)
    _check_blockers(result, header)
    _check_metrics(result, schema, header)
    _check_path_lists(result, header)

    # 4. Cross-field rules R1-R6 (R7 is enforced in _check_path_lists)
    _check_R1_R6(result, header, slug, artifact_rel)

    # 5. Required markdown body sections
    _check_required_sections(result, agent, body)

    # 6. Per-class extensions
    if agent == "research":
        _check_research(result, header)
    elif agent == "analysis":
        _check_analysis(result, header)
    elif agent == "design":
        _check_design(result, header)
    elif agent == "implementation":
        _check_implementation(result, header, slug)
    elif agent == "test":
        _check_test(result, header)
    elif agent == "review":
        _check_review(result, header)
    elif agent == "doc":
        _check_doc(result, header, artifact_rel)
    elif agent == "retro":
        _check_retro(result, header)

    # 7. Outcome resolution: if no hard errors, decide proceed vs escalate
    if result.passed:
        status = header.get("status")
        gate = header.get("gate_decision")
        if status in {"blocked", "failed"}:
            result.outcome = "escalate"
        elif gate == "escalate":
            result.outcome = "escalate"
        else:
            result.outcome = "proceed"

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="app.pipeline.verify",
        description=(
            "Verify a CC-v1 pipeline artifact against its class schema "
            "and the R1-R7 cross-field rules."
        ),
    )
    parser.add_argument(
        "--agent",
        required=True,
        choices=sorted(CLASS_CONFIG.keys()),
        help="Agent class identifier (selects the schema family).",
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
        "--normalize",
        action="store_true",
        help=(
            "Run the normalizer (app.pipeline.normalize) before verifying. "
            "Available once task 1.4 lands; until then this flag exits 3 "
            "with a usage error."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON report on stdout instead of human-readable lines.",
    )
    args = parser.parse_args(argv)

    space = Path(args.space).resolve()
    if not space.is_dir():
        msg = f"ERROR: --space is not a directory: {space}"
        if args.json:
            print(
                json.dumps(
                    {"error": msg, "outcome": "retry", "exit_code": EXIT_RETRY}
                )
            )
        else:
            print(msg, file=sys.stderr)
        return EXIT_RETRY

    normalize_report: dict[str, Any] | None = None
    if args.normalize:
        try:
            from app.pipeline.normalize import normalize  # type: ignore
        except ImportError as exc:
            msg = (
                f"ERROR: --normalize requested but normalizer is not available: "
                f"{exc}"
            )
            if args.json:
                print(
                    json.dumps(
                        {"error": msg, "outcome": "retry", "exit_code": EXIT_RETRY}
                    )
                )
            else:
                print(msg, file=sys.stderr)
            return EXIT_RETRY
        n = normalize(args.agent, args.slug, space, dry_run=False)
        # The normalizer returns its own result object; we just surface its
        # to_dict() output here so the verifier remains the source of truth
        # for the exit code.
        normalize_report = (
            n.to_dict() if hasattr(n, "to_dict") else {"applied": True}
        )

    result = verify(args.agent, args.slug, space)

    if args.json:
        payload = result.to_dict()
        if normalize_report is not None:
            payload["normalize"] = normalize_report
        print(json.dumps(payload, indent=2))
    else:
        outcome_label = result.outcome.upper()
        print(f"[{outcome_label}] agent={result.agent} slug={result.slug}")
        print(f"       artifact={result.artifact_path}")
        if normalize_report is not None:
            print(f"  NORMALIZE: {normalize_report}")
        for err in result.errors:
            print(f"  ERROR: {err}")
        for warn in result.warnings:
            print(f"  WARN:  {warn}")

    return result.exit_code()


if __name__ == "__main__":
    sys.exit(main())
