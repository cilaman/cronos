"""Tests for app.pipeline.retro_memory_writer.

Covers:
- write_retro_lessons: writes one memory item per finding
- write_retro_lessons: maps fix_type to the correct MemoryKind
- write_retro_lessons: sets global scope on all items
- write_retro_lessons: title contains slug + finding_id + target keywords
- write_retro_lessons: body contains evidence + suggested_action
- write_retro_lessons: returns empty list when findings is []
- write_retro_lessons: skips findings with missing id or fix_type
- write_retro_lessons: raises FileNotFoundError for missing artifact
- write_retro_lessons: raises ValueError for missing slug field
- Integration: written memory items are retrieved for a matching task via
  memory_retrieval.retrieve (the acceptance criterion for task 4.3)
"""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.memory_retrieval import retrieve
from app.memory_store import MemoryStore
from app.models import MemoryKind, Task, TaskState
from app.pipeline.retro_memory_writer import (
    _build_body,
    _build_title,
    _kind_for_fix_type,
    _parse_retro_artifact,
    write_retro_lessons,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_retro_artifact(
    tmp_path: Path,
    slug: str,
    findings: list[dict],
    *,
    status: str = "done",
    confidence: float = 0.85,
) -> Path:
    """Write a minimal valid retro artifact to tmp_path and return its path."""
    pipeline_dir = tmp_path / ".cronos" / "pipeline" / slug
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    artifact = pipeline_dir / f"retro-{slug}.md"

    # Build findings YAML block with correct indentation:
    # Each list item is indented 2 spaces from the `findings:` key.
    # Keys within each item are indented 4 spaces from `findings:`.
    if not findings:
        findings_block = "findings: []\n"
    else:
        lines = ["findings:"]
        for f in findings:
            # Only emit keys that are present so intentionally malformed fixtures
            # can omit 'id' or 'fix_type' to test the skip-guard in the writer.
            first = True
            for key in ("id", "severity", "fix_type", "target"):
                if key in f:
                    prefix = "  - " if first else "    "
                    lines.append(f"{prefix}{key}: {f[key]}")
                    first = False
            if first:
                # Completely empty entry — write a placeholder list item
                lines.append("  - {}")
            evidence = f.get("evidence", "test evidence").strip()
            lines.append("    evidence: |")
            for ev_line in evidence.splitlines():
                lines.append(f"      {ev_line}")
            action = f.get("suggested_action", "test action").strip()
            lines.append("    suggested_action: |")
            for ac_line in action.splitlines():
                lines.append(f"      {ac_line}")
        findings_block = "\n".join(lines) + "\n"

    content = (
        "---\n"
        f'cc_version: "1.0"\n'
        f"agent: pipeline-retro\n"
        f"slug: {slug}\n"
        f"phase: retro\n"
        f"status: {status}\n"
        f"confidence: {confidence}\n"
        f"inputs_used:\n"
        f"  - .cronos/pipeline/{slug}/pipeline-state.json\n"
        f"outputs_produced:\n"
        f"  - .cronos/pipeline/{slug}/retro-{slug}.md\n"
        f"blockers: []\n"
        f"next_consumer: user\n"
        f"metrics:\n"
        f"  tool_calls: 5\n"
        f"  files_read: 2\n"
        f"  memory_hits: 0\n"
        f"  phases_reviewed: 1\n"
        f"  traces_reviewed: 1\n"
        f"scores:\n"
        f"  planning: 4\n"
        f"  error_handling: 4\n"
        f"  efficiency: 3\n"
        f"  completion: 5\n"
        f"  communication: 4\n"
        f"{findings_block}"
        f"---\n"
        f"\n"
        f"## Summary\n"
        f"\n"
        f"Test retro.\n"
        f"\n"
        f"## Scores\n"
        f"\n"
        f"| Dimension | Score |\n"
        f"|-----------|-------|\n"
        f"| Planning  | 4/5   |\n"
        f"\n"
        f"## Findings\n"
        f"\n"
        f"- None.\n"
        f"\n"
        f"## Assumptions\n"
        f"\n"
        f"- Test assumption.\n"
        f"\n"
        f"## Open questions\n"
        f"\n"
        f"- None.\n"
        f"\n"
        f"## Next consumer brief\n"
        f"\n"
        f"Test brief.\n"
    )
    artifact.write_text(content, encoding="utf-8")
    return artifact





def _make_task(title: str, brief: str = "", space_id: str = "test-space") -> Task:
    now = datetime.now(tz=UTC)
    return Task(
        id="task-001",
        space_id=space_id,
        title=title,
        brief=brief,
        state=TaskState.ACTIVE,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "data", tmp_path / "spaces")


@pytest.fixture
def space_dir(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests: helper functions
# ---------------------------------------------------------------------------


def test_kind_for_fix_type_agent_prompt_refinement() -> None:
    assert _kind_for_fix_type("agent_prompt_refinement") == MemoryKind.PROCEDURE


def test_kind_for_fix_type_contract_change() -> None:
    assert _kind_for_fix_type("contract_change") == MemoryKind.OBSERVATION


def test_kind_for_fix_type_normalize_rule() -> None:
    assert _kind_for_fix_type("normalize_rule") == MemoryKind.OBSERVATION


def test_kind_for_fix_type_verifier_rule() -> None:
    assert _kind_for_fix_type("verifier_rule_or_schema_field") == MemoryKind.OBSERVATION


def test_build_title_contains_slug_id_and_target() -> None:
    finding = {"id": "F1", "target": "agent:pipeline-implementor", "fix_type": "agent_prompt_refinement"}
    title = _build_title("my-feature", finding)
    assert "retro:my-feature:F1" in title
    assert "agent:pipeline-implementor" in title


def test_build_body_contains_evidence_and_action() -> None:
    finding = {
        "evidence": "impl-report had backtrack_count=4",
        "suggested_action": "Add read-once rule to implementor",
        "severity": "medium",
        "fix_type": "agent_prompt_refinement",
    }
    body = _build_body(finding)
    assert "impl-report had backtrack_count=4" in body
    assert "Add read-once rule to implementor" in body
    assert "medium" in body


def test_build_body_handles_missing_fields() -> None:
    body = _build_body({})
    assert body == ""


# ---------------------------------------------------------------------------
# _parse_retro_artifact
# ---------------------------------------------------------------------------


def test_parse_retro_artifact_basic(tmp_path: Path) -> None:
    artifact = _make_retro_artifact(
        tmp_path,
        "test-slug",
        [{"id": "F1", "fix_type": "normalize_rule", "target": "normalize:test"}],
    )
    slug, findings = _parse_retro_artifact(artifact)
    assert slug == "test-slug"
    assert len(findings) == 1
    assert findings[0]["id"] == "F1"


def test_parse_retro_artifact_empty_findings(tmp_path: Path) -> None:
    artifact = _make_retro_artifact(tmp_path, "empty-slug", [])
    slug, findings = _parse_retro_artifact(artifact)
    assert slug == "empty-slug"
    assert findings == []


def test_parse_retro_artifact_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _parse_retro_artifact(tmp_path / "nonexistent.md")


def test_parse_retro_artifact_missing_slug(tmp_path: Path) -> None:
    bad_artifact = tmp_path / "retro-test.md"
    bad_artifact.write_text(
        "---\nfindings: []\n---\n\n## Summary\n\ntest\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no 'slug' field"):
        _parse_retro_artifact(bad_artifact)


# ---------------------------------------------------------------------------
# write_retro_lessons
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_retro_lessons_creates_items(space_dir: Path, store: MemoryStore) -> None:
    findings = [
        {
            "id": "F1",
            "fix_type": "agent_prompt_refinement",
            "target": "agent:pipeline-implementor",
            "evidence": "backtrack_count=4 in trace",
            "suggested_action": "Read scope files once before editing",
            "severity": "medium",
        },
        {
            "id": "F2",
            "fix_type": "normalize_rule",
            "target": "normalize:trailing_whitespace_in_slug",
            "evidence": "slug field had trailing newline",
            "suggested_action": "Strip trailing whitespace in normalize.py",
            "severity": "low",
        },
    ]
    artifact = _make_retro_artifact(space_dir, "my-feature", findings)
    items = await write_retro_lessons("my-feature", space_dir, store, artifact_path=artifact)

    assert len(items) == 2


@pytest.mark.asyncio
async def test_write_retro_lessons_correct_kinds(space_dir: Path, store: MemoryStore) -> None:
    findings = [
        {
            "id": "F1",
            "fix_type": "agent_prompt_refinement",
            "target": "agent:pipeline-implementor",
            "evidence": "test",
            "suggested_action": "test",
            "severity": "medium",
        },
        {
            "id": "F2",
            "fix_type": "verifier_rule_or_schema_field",
            "target": "rule:R-impl-7",
            "evidence": "test",
            "suggested_action": "test",
            "severity": "medium",
        },
    ]
    artifact = _make_retro_artifact(space_dir, "kind-test", findings)
    items = await write_retro_lessons("kind-test", space_dir, store, artifact_path=artifact)

    kinds = {item.id: item.kind for item in items}
    assert items[0].kind == MemoryKind.PROCEDURE
    assert items[1].kind == MemoryKind.OBSERVATION


@pytest.mark.asyncio
async def test_write_retro_lessons_global_scope(space_dir: Path, store: MemoryStore) -> None:
    findings = [
        {
            "id": "F1",
            "fix_type": "contract_change",
            "target": "contract:CONTRACT.md#7.2",
            "evidence": "test evidence",
            "suggested_action": "test action",
            "severity": "high",
        }
    ]
    artifact = _make_retro_artifact(space_dir, "scope-test", findings)
    items = await write_retro_lessons("scope-test", space_dir, store, artifact_path=artifact)

    assert len(items) == 1
    assert items[0].scope == "global"


@pytest.mark.asyncio
async def test_write_retro_lessons_title_keywords(space_dir: Path, store: MemoryStore) -> None:
    findings = [
        {
            "id": "F3",
            "fix_type": "agent_prompt_refinement",
            "target": "agent:pipeline-architect",
            "evidence": "architect did not list scope_files for all iterations",
            "suggested_action": "Update architect prompt §4",
            "severity": "medium",
        }
    ]
    artifact = _make_retro_artifact(space_dir, "title-test", findings)
    items = await write_retro_lessons("title-test", space_dir, store, artifact_path=artifact)

    assert len(items) == 1
    title = items[0].title
    assert "retro:title-test:F3" in title
    assert "pipeline-architect" in title


@pytest.mark.asyncio
async def test_write_retro_lessons_sources_traceability(space_dir: Path, store: MemoryStore) -> None:
    findings = [
        {
            "id": "F1",
            "fix_type": "normalize_rule",
            "target": "normalize:backslash_paths",
            "evidence": "backslash in inputs_used",
            "suggested_action": "normalize backslash to forward slash",
            "severity": "low",
        }
    ]
    artifact = _make_retro_artifact(space_dir, "src-test", findings)
    items = await write_retro_lessons("src-test", space_dir, store, artifact_path=artifact)

    assert "retro:src-test:F1" in items[0].sources


@pytest.mark.asyncio
async def test_write_retro_lessons_empty_findings(space_dir: Path, store: MemoryStore) -> None:
    artifact = _make_retro_artifact(space_dir, "no-findings", [])
    items = await write_retro_lessons("no-findings", space_dir, store, artifact_path=artifact)
    assert items == []


@pytest.mark.asyncio
async def test_write_retro_lessons_missing_artifact(space_dir: Path, store: MemoryStore) -> None:
    missing = space_dir / ".cronos" / "pipeline" / "x" / "retro-x.md"
    with pytest.raises(FileNotFoundError):
        await write_retro_lessons("x", space_dir, store, artifact_path=missing)


@pytest.mark.asyncio
async def test_write_retro_lessons_skips_malformed_findings(
    space_dir: Path, store: MemoryStore
) -> None:
    """Findings missing id or fix_type are skipped gracefully."""
    findings = [
        {"id": "F1", "fix_type": "normalize_rule", "target": "normalize:x", "evidence": "e", "suggested_action": "a", "severity": "low"},
        {"fix_type": "normalize_rule", "target": "normalize:y"},  # missing id
        {"id": "F3", "target": "agent:x"},  # missing fix_type
    ]
    artifact = _make_retro_artifact(space_dir, "skip-test", findings)
    items = await write_retro_lessons("skip-test", space_dir, store, artifact_path=artifact)
    # Only F1 passes the guard
    assert len(items) == 1
    assert "F1" in items[0].title


# ---------------------------------------------------------------------------
# Integration: memory retrieval
#
# Acceptance criterion for task 4.3:
# "A retro lesson is persisted as memory and demonstrably injected into
#  a later matching run."
#
# We demonstrate this by writing a finding about "pipeline-implementor scope
# files efficiency" and then asking retrieve() for a task whose title and
# brief share those keywords. The lesson must appear in the top-5 results.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retro_lesson_retrieved_for_matching_task(
    space_dir: Path, store: MemoryStore
) -> None:
    """End-to-end: write retro lesson → retrieved for matching task."""
    findings = [
        {
            "id": "F1",
            "fix_type": "agent_prompt_refinement",
            "target": "agent:pipeline-implementor",
            "evidence": (
                "impl-report-my-feature--i1.md: backtrack_count=4 across 3 reads of "
                "backend/app/foo.py; implementor re-read scope_files after each Write."
            ),
            "suggested_action": (
                "Add to .claude/agents/pipeline-implementor.md Step 2: "
                "'Read every scope_file once before the first Edit; "
                "only re-read after a verify failure.'"
            ),
            "severity": "medium",
        }
    ]
    artifact = _make_retro_artifact(space_dir, "integration-slug", findings)

    # Write the lesson to the global memory store
    items = await write_retro_lessons(
        "integration-slug", space_dir, store, artifact_path=artifact
    )
    assert len(items) == 1, "Expected exactly one memory item written"

    # Now simulate a future pipeline task whose title+brief overlap with the lesson
    future_task = _make_task(
        title="pipeline-implementor reads scope_files multiple times",
        brief="The implementor agent re-reads the same file after every Edit, "
              "causing high backtrack_count in traces.",
        space_id="some-other-space",
    )

    retrieved = await retrieve(future_task, "some-other-space", store)

    assert len(retrieved) >= 1, (
        "Expected the retro lesson to be retrieved for the matching task, "
        f"but got {len(retrieved)} results"
    )
    # The written lesson should be the first result (or at least present)
    lesson_ids = {item.id for item in retrieved}
    written_id = items[0].id
    assert written_id in lesson_ids, (
        f"Written lesson {written_id} not found in retrieved items: {lesson_ids}"
    )


@pytest.mark.asyncio
async def test_retro_lesson_not_retrieved_for_unrelated_task(
    space_dir: Path, store: MemoryStore
) -> None:
    """Retro lesson should NOT pollute results for unrelated tasks."""
    findings = [
        {
            "id": "F1",
            "fix_type": "normalize_rule",
            "target": "normalize:trailing_whitespace_in_slug",
            "evidence": "slug field had trailing newline in review artifact",
            "suggested_action": "Strip trailing whitespace in normalize.py _normalize_slug",
            "severity": "low",
        }
    ]
    artifact = _make_retro_artifact(space_dir, "noise-test", findings)
    items = await write_retro_lessons("noise-test", space_dir, store, artifact_path=artifact)
    assert len(items) == 1

    # A task about something entirely unrelated
    unrelated_task = _make_task(
        title="Add dark mode to frontend dashboard",
        brief="Implement dark mode toggle in the React UI using Tailwind CSS classes.",
        space_id="some-space",
    )
    retrieved = await retrieve(unrelated_task, "some-space", store)

    # The normalizer finding should not match frontend/dark mode terminology
    written_id = items[0].id
    retrieved_ids = {item.id for item in retrieved}
    assert written_id not in retrieved_ids, (
        "Retro lesson for slug trailing whitespace should not match a frontend dark mode task"
    )


@pytest.mark.asyncio
async def test_retro_lessons_available_across_spaces(
    space_dir: Path, store: MemoryStore
) -> None:
    """Global-scoped lessons must surface in a DIFFERENT space than where they were written."""
    findings = [
        {
            "id": "F1",
            "fix_type": "contract_change",
            "target": "contract:CONTRACT.md#7.2",
            "evidence": "duration_s stamped by agent instead of trace-owned writer",
            "suggested_action": "Add R-contract-1 rule forbidding agent-stamped duration_s",
            "severity": "high",
        }
    ]
    # Write lesson in space-A context
    artifact = _make_retro_artifact(space_dir, "cross-space", findings)
    items = await write_retro_lessons("cross-space", space_dir, store, artifact_path=artifact)
    assert len(items) == 1

    # Retrieve in space-B — completely different space_id
    task_in_space_b = _make_task(
        title="contract duration_s trace-owned field enforcement",
        brief="Ensure the contract rule about duration_s being trace-owned is enforced.",
        space_id="space-b",
    )
    retrieved = await retrieve(task_in_space_b, "space-b", store)

    assert len(retrieved) >= 1, "Global lesson should be visible from space-b"
    assert items[0].id in {r.id for r in retrieved}
