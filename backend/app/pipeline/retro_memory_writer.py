"""Retro memory write-back for CC-v1 pipelines.

After a retro-class artifact is verified (exit 0 from pipeline-gate), this
module reads the artifact's ``findings[]`` from the YAML header and writes
each finding as a Cronos memory item in the ``global`` scope so that future
pipeline runs in ANY space can surface the lesson via
``app.memory_retrieval.retrieve``.

fix_type → MemoryKind mapping
------------------------------
``agent_prompt_refinement``       → ``procedure``
  (tells future agents *how* to behave correctly)
``contract_change``               → ``observation``
``normalize_rule``                → ``observation``
``verifier_rule_or_schema_field`` → ``observation``

Memory item layout
------------------
``title`` : ``"[retro:{slug}:{finding_id}] {target}"``
    Target keywords (e.g. "pipeline-implementor") appear here so
    ``memory_retrieval._extract_terms`` can match them against future task
    titles and briefs that share the same terminology.

``body``  : ``"Evidence: …\\n\\nSuggested action: …\\n\\nSeverity: {severity}"``
    Verbatim from the finding so deeper term matches find additional signal.

``scope``     : ``"global"`` — lessons propagate across all spaces.
``confidence``: ``0.8``     — retrospective evidence, not machine-verified.
``confirmed`` : ``False``   — unconfirmed until a human or eval validates.
``sources``   : ``["retro:{slug}:{finding_id}"]`` — traceability link.

CLI usage
---------
::

    python -m app.pipeline.retro_memory_writer \\
        --space /data/spaces/cronos-development \\
        --slug  my-feature

Programmatic usage
------------------
::

    import asyncio
    from pathlib import Path
    from app.memory_store import MemoryStore
    from app.pipeline.retro_memory_writer import write_retro_lessons

    store = MemoryStore(Path("/data"), Path("/data/spaces"))
    items = asyncio.run(write_retro_lessons("my-feature", "/data/spaces/my-space", store))
    print(f"Wrote {len(items)} memory items")
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import frontmatter

from app.memory_store import MemoryStore
from app.models import MemoryItem, MemoryKind

log = logging.getLogger("cronos.retro_memory_writer")

# Findings whose fix_type maps to procedure (agent-how-to).
_PROCEDURE_FIX_TYPES: frozenset[str] = frozenset({"agent_prompt_refinement"})


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def _kind_for_fix_type(fix_type: str) -> MemoryKind:
    """Map a retro finding fix_type to a MemoryKind."""
    if fix_type in _PROCEDURE_FIX_TYPES:
        return MemoryKind.PROCEDURE
    return MemoryKind.OBSERVATION


def _build_title(slug: str, finding: dict[str, Any]) -> str:
    """Build a keyword-rich title for the memory item.

    Format: ``[retro:{slug}:{id}] {target}``

    The ``target`` field already contains agent/rule/schema names
    (e.g. "agent:pipeline-implementor", "rule:R-impl-3") that serve as the
    primary retrieval keywords.  The ``[retro:…]`` prefix enables direct
    lookup by slug or finding id.
    """
    finding_id = finding.get("id", "?")
    target = finding.get("target", "")
    return f"[retro:{slug}:{finding_id}] {target}"


def _build_body(finding: dict[str, Any]) -> str:
    """Build the memory item body from finding fields."""
    evidence = (finding.get("evidence") or "").strip()
    suggested_action = (finding.get("suggested_action") or "").strip()
    severity = finding.get("severity", "")
    fix_type = finding.get("fix_type", "")
    parts: list[str] = []
    if evidence:
        parts.append(f"Evidence: {evidence}")
    if suggested_action:
        parts.append(f"Suggested action: {suggested_action}")
    if severity:
        parts.append(f"Severity: {severity}")
    if fix_type:
        parts.append(f"Fix type: {fix_type}")
    return "\n\n".join(parts)


def _parse_retro_artifact(artifact_path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Parse a retro artifact and return (slug, findings[]).

    Raises
    ------
    FileNotFoundError
        If the artifact does not exist.
    ValueError
        If the YAML header is missing or ``findings`` is not a list.
    """
    if not artifact_path.exists():
        raise FileNotFoundError(f"Retro artifact not found: {artifact_path}")

    post = frontmatter.load(artifact_path)
    header: dict[str, Any] = dict(post.metadata)

    slug = header.get("slug", "")
    if not slug:
        raise ValueError(f"Retro artifact has no 'slug' field: {artifact_path}")

    findings = header.get("findings")
    if findings is None:
        raise ValueError(f"Retro artifact has no 'findings' field: {artifact_path}")
    if not isinstance(findings, list):
        raise ValueError(
            f"Retro artifact 'findings' must be a list, got {type(findings).__name__}: {artifact_path}"
        )

    return slug, findings


async def write_retro_lessons(
    slug: str,
    space_dir: str | Path,
    store: MemoryStore,
    *,
    data_dir: Path | None = None,
    spaces_dir: Path | None = None,
    artifact_path: Path | None = None,
) -> list[MemoryItem]:
    """Read a verified retro artifact and write findings as global memory items.

    Parameters
    ----------
    slug:
        Goal slug identifying the pipeline run (e.g. ``"my-feature"``).
    space_dir:
        Absolute path to the Cronos space root — the directory that holds
        ``.cronos/``.  Used to resolve the artifact path and the memory store
        when ``store`` is constructed from defaults.
    store:
        Initialised :class:`~app.memory_store.MemoryStore` to write into.
    artifact_path:
        Override the canonical artifact path.  Defaults to
        ``{space_dir}/.cronos/pipeline/{slug}/retro-{slug}.md``.

    Returns
    -------
    list[MemoryItem]
        The created memory items (one per finding, in order).  Empty list
        when the artifact has no findings.
    """
    space_path = Path(space_dir)

    # Resolve artifact path
    if artifact_path is None:
        artifact_path = space_path / ".cronos" / "pipeline" / slug / f"retro-{slug}.md"

    slug_from_artifact, findings = _parse_retro_artifact(artifact_path)

    if not findings:
        log.info("Retro artifact %s has no findings — no memory items written", artifact_path)
        return []

    created: list[MemoryItem] = []
    for finding in findings:
        if not isinstance(finding, dict):
            log.warning("Skipping non-dict finding entry: %r", finding)
            continue

        finding_id = finding.get("id", "")
        fix_type = finding.get("fix_type", "")
        if not finding_id or not fix_type:
            log.warning("Skipping finding with missing id or fix_type: %r", finding)
            continue

        kind = _kind_for_fix_type(fix_type)
        title = _build_title(slug_from_artifact, finding)
        body = _build_body(finding)
        source_ref = f"retro:{slug_from_artifact}:{finding_id}"

        item = await store.create(
            scope="global",
            kind=kind,
            title=title,
            body=body,
            confirmed=False,
            confidence=0.8,
            sources=[source_ref],
        )
        log.info(
            "Wrote memory item %s for retro finding %s (fix_type=%s)",
            item.id,
            finding_id,
            fix_type,
        )
        created.append(item)

    return created


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli() -> None:  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m app.pipeline.retro_memory_writer",
        description="Write retro findings as global Cronos memory items.",
    )
    parser.add_argument("--space", required=True, help="Absolute path to the Cronos space root.")
    parser.add_argument(
        "--slug",
        required=True,
        help="Goal slug (matches the retro artifact filename retro-{slug}.md).",
    )
    parser.add_argument(
        "--artifact",
        default=None,
        help="Override artifact path (default: {space}/.cronos/pipeline/{slug}/retro-{slug}.md).",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Override data directory for the MemoryStore (default: {space}/../data).",
    )
    parser.add_argument(
        "--spaces-dir",
        default=None,
        help="Override spaces directory for the MemoryStore (default: {space}/..).",
    )
    args = parser.parse_args()

    space_path = Path(args.space).resolve()
    data_dir = Path(args.data_dir).resolve() if args.data_dir else space_path.parent.parent / "data"
    spaces_dir = Path(args.spaces_dir).resolve() if args.spaces_dir else space_path.parent
    artifact_override = Path(args.artifact).resolve() if args.artifact else None

    store = MemoryStore(data_dir, spaces_dir)

    items = asyncio.run(
        write_retro_lessons(
            args.slug,
            space_path,
            store,
            artifact_path=artifact_override,
        )
    )

    if items:
        print(f"Wrote {len(items)} memory item(s):")
        for item in items:
            print(f"  {item.id}  [{item.kind.value}]  {item.title[:80]}")
    else:
        print("No findings found — no memory items written.")


if __name__ == "__main__":  # pragma: no cover
    _cli()
