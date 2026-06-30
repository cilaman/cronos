"""Tests for the CC-v1 auto-improvement applier (task 4.4).

Acceptance criterion (task brief):
    A normalize-rule finding is auto-applied and version-bumped only when
    evals stay green.

The applier reads ``retro-{slug}.md`` findings, filters to machine-applicable
recipes (``normalize:strategy_synonym`` and ``fixture:<rel_path>``), applies
each change, bumps CC_VERSION across contract/schemas/fixtures, then runs
the goal-1 evals. If the evals pass the change stays; if they fail every
touched file is restored from snapshot.

The tests use a synthetic repo root (copied into ``tmp_path``) so the
applier can write, bump versions, and run a fake eval command without
touching the real codebase.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from app.pipeline.auto_improver import (
    AppliedChange,
    ApplierResult,
    SkippedFinding,
    apply_retro_improvements,
    bump_minor,
    read_cc_version,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


REAL_REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # workspace root
REAL_PIPELINE_DIR = REAL_REPO_ROOT / "backend" / "app" / "pipeline"
REAL_LIB_DIR = REAL_REPO_ROOT / "packages" / "delivery-workflow" / "lib"


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Build a minimal synthetic repo root under ``tmp_path``.

    Copies the real lib/{contract.py,schemas/} and backend/app/pipeline/
    {fixtures,normalize_rules.json} so the applier can patch them in isolation.
    contract.py and schemas/ now live in lib/ (SG7 canonical lift).
    """
    # lib/ — contract.py, verify.py and schemas/ (canonical sources after SG7)
    dst_lib = tmp_path / "packages" / "delivery-workflow" / "lib"
    dst_lib.mkdir(parents=True)
    shutil.copy(REAL_LIB_DIR / "__init__.py", dst_lib / "__init__.py")
    shutil.copy(REAL_LIB_DIR / "contract.py", dst_lib / "contract.py")
    shutil.copy(REAL_LIB_DIR / "verify.py", dst_lib / "verify.py")
    shutil.copytree(REAL_LIB_DIR / "schemas", dst_lib / "schemas")

    src_pipeline = REAL_PIPELINE_DIR
    dst_pipeline = tmp_path / "backend" / "app" / "pipeline"
    dst_pipeline.mkdir(parents=True)

    # normalize_rules registry stays in backend/app/pipeline/
    shutil.copy(
        src_pipeline / "normalize_rules.json",
        dst_pipeline / "normalize_rules.json",
    )

    # Fixtures (the applier propagates the version bump here)
    shutil.copytree(src_pipeline / "fixtures", dst_pipeline / "fixtures")

    return tmp_path


@pytest.fixture
def space(tmp_path: Path) -> Path:
    """Synthetic space root for retro artifacts."""
    sp = tmp_path / "space"
    sp.mkdir()
    return sp


def write_retro_artifact(
    space: Path,
    slug: str,
    findings: list[dict],
    *,
    status: str = "done",
    confidence: float = 0.85,
) -> Path:
    """Write a retro artifact at the canonical location and return its path."""
    artifact_dir = space / ".cronos" / "pipeline" / slug
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"retro-{slug}.md"

    header = {
        "cc_version": "1.0",
        "agent": "pipeline-retro",
        "slug": slug,
        "phase": "retro",
        "status": status,
        "confidence": confidence,
        "inputs_used": [".cronos/pipeline/" + slug + "/pipeline-state.json"],
        "outputs_produced": [f".cronos/pipeline/{slug}/retro-{slug}.md"],
        "blockers": [],
        "next_consumer": "user",
        "metrics": {"tool_calls": 1, "files_read": 1, "memory_hits": 0},
        "scores": {
            "planning": 4,
            "error_handling": 4,
            "efficiency": 4,
            "completion": 5,
            "communication": 4,
        },
        "findings": findings,
    }
    text = (
        "---\n"
        + yaml.safe_dump(header, sort_keys=False)
        + "---\n\n## Summary\n\nSynthetic retro for tests.\n"
    )
    artifact_path.write_text(text, encoding="utf-8")
    return artifact_path


def make_normalize_synonym_finding(
    fid: str, synonym: str, canonical: str
) -> dict:
    return {
        "id": fid,
        "severity": "low",
        "fix_type": "normalize_rule",
        "target": "normalize:strategy_synonym",
        "evidence": f"scout-report listed {synonym!r} as a strategy",
        "suggested_action": (
            f"Add a synonym mapping {synonym!r} -> {canonical!r} to "
            "app.pipeline.normalize_rules.json."
        ),
        "auto_apply": {"synonym": synonym, "canonical": canonical},
    }


def make_fixture_finding(
    fid: str, rel_path: str, content: str
) -> dict:
    return {
        "id": fid,
        "severity": "medium",
        "fix_type": "normalize_rule",
        "target": f"fixture:{rel_path}",
        "evidence": "negative fixture missing for the new normalize rule",
        "suggested_action": f"Add fixture at {rel_path}.",
        "auto_apply": {"content": content},
    }


# A trivial passing-evals command — exit 0, no output.
PASSING_EVALS = (sys.executable, "-c", "import sys; sys.exit(0)")

# A trivial failing-evals command — exit 1.
FAILING_EVALS = (sys.executable, "-c", "import sys; sys.exit(1)")


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_bump_minor_increments_minor() -> None:
    assert bump_minor("1.0") == "1.1"
    assert bump_minor("1.1") == "1.2"
    assert bump_minor("2.9") == "2.10"


def test_bump_minor_rejects_bad_shapes() -> None:
    for bad in ("1", "1.0.0", "x.y", "1.x", ""):
        with pytest.raises(ValueError):
            bump_minor(bad)


def test_read_cc_version_returns_one_dot_oh(repo_root: Path) -> None:
    contract = repo_root / "packages" / "delivery-workflow" / "lib" / "contract.py"
    assert read_cc_version(contract) == "1.0"


# ---------------------------------------------------------------------------
# Classification — findings that must be skipped
# ---------------------------------------------------------------------------


def test_prompt_refinement_findings_are_skipped(
    repo_root: Path, space: Path
) -> None:
    finding = {
        "id": "F1",
        "severity": "high",
        "fix_type": "agent_prompt_refinement",
        "target": "agent:pipeline-implementor",
        "evidence": "implementor re-read same file 3x",
        "suggested_action": "Add 'read once' guidance to the agent prompt.",
        "auto_apply": {"hint": "ignored"},
    }
    write_retro_artifact(space, "my-feature", [finding])

    result = apply_retro_improvements(
        slug="my-feature",
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
    )

    assert result.applied == []
    assert len(result.skipped) == 1
    assert result.skipped[0].fix_type == "agent_prompt_refinement"
    assert "human review" in result.skipped[0].reason
    assert result.cc_version_after is None
    assert read_cc_version(repo_root / "packages/delivery-workflow/lib/contract.py") == "1.0"


def test_contract_change_findings_are_skipped(
    repo_root: Path, space: Path
) -> None:
    finding = {
        "id": "F1",
        "severity": "high",
        "fix_type": "contract_change",
        "target": "contract:CONTRACT.md#7.2",
        "evidence": "duration_s appeared in agent-written header",
        "suggested_action": "Document TRACE_OWNED_METRICS more aggressively.",
        "auto_apply": {"hint": "ignored"},
    }
    write_retro_artifact(space, "my-feature", [finding])

    result = apply_retro_improvements(
        slug="my-feature",
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
    )

    assert result.applied == []
    assert len(result.skipped) == 1
    assert result.skipped[0].fix_type == "contract_change"
    assert result.evals_ran is False  # no apply means no eval run


def test_finding_without_auto_apply_is_skipped(
    repo_root: Path, space: Path
) -> None:
    finding = {
        "id": "F1",
        "severity": "low",
        "fix_type": "normalize_rule",
        "target": "normalize:strategy_synonym",
        "evidence": "scout used 'kb_query' as a strategy",
        "suggested_action": "Add a synonym mapping.",
        # no auto_apply payload
    }
    write_retro_artifact(space, "my-feature", [finding])
    result = apply_retro_improvements(
        slug="my-feature",
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
    )
    assert result.applied == []
    assert "no auto_apply payload" in result.skipped[0].reason


def test_unknown_target_is_skipped(repo_root: Path, space: Path) -> None:
    finding = {
        "id": "F1",
        "severity": "medium",
        "fix_type": "normalize_rule",
        "target": "normalize:unknown_rule",
        "evidence": "n/a",
        "suggested_action": "n/a",
        "auto_apply": {"hint": "x"},
    }
    write_retro_artifact(space, "s", [finding])
    result = apply_retro_improvements(
        slug="s",
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
    )
    assert result.applied == []
    assert "unrecognised auto-apply recipe" in result.skipped[0].reason


def test_fixture_target_outside_fixtures_dir_is_skipped(
    repo_root: Path, space: Path
) -> None:
    finding = {
        "id": "F1",
        "severity": "medium",
        "fix_type": "normalize_rule",
        "target": "fixture:backend/app/main.py",
        "evidence": "n/a",
        "suggested_action": "n/a",
        "auto_apply": {"content": "x"},
    }
    write_retro_artifact(space, "s", [finding])
    result = apply_retro_improvements(
        slug="s",
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
    )
    assert result.applied == []
    assert "fixtures/" in result.skipped[0].reason


# ---------------------------------------------------------------------------
# Acceptance — normalize-rule finding applied + version bumped on green evals
# ---------------------------------------------------------------------------


def test_normalize_rule_applied_and_version_bumped_when_evals_pass(
    repo_root: Path, space: Path
) -> None:
    finding = make_normalize_synonym_finding("F1", "kbquery", "memory_retrieval")
    write_retro_artifact(space, "my-feature", [finding])

    result = apply_retro_improvements(
        slug="my-feature",
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
    )

    # Acceptance: applied + version bumped + not rolled back.
    assert result.error is None
    assert result.rolled_back is False
    assert len(result.applied) == 1
    assert result.applied[0].recipe == "normalize_strategy_synonym"
    assert result.applied[0].finding_id == "F1"
    assert result.evals_ran is True
    assert result.evals_passed is True
    assert result.cc_version_before == "1.0"
    assert result.cc_version_after == "1.1"

    # contract.py rewritten
    contract_path = repo_root / "packages/delivery-workflow/lib/contract.py"
    assert read_cc_version(contract_path) == "1.1"

    # normalize_rules.json now has the synonym
    rules_path = repo_root / "backend/app/pipeline/normalize_rules.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    assert rules["strategy_synonyms"]["kbquery"] == "memory_retrieval"

    # Schemas + fixtures pinned at the new version
    research_schema = (
        repo_root / "packages/delivery-workflow/lib/schemas/research.schema.yaml"
    ).read_text(encoding="utf-8")
    assert 'const: "1.1"' in research_schema
    research_golden = (
        repo_root / "backend/app/pipeline/fixtures/golden/research.md"
    ).read_text(encoding="utf-8")
    assert re.search(r"^cc_version: '1\.1'", research_golden, re.MULTILINE)

    # The intentionally-wrong-version negative fixture stays at '2.0'.
    wrong = (
        repo_root
        / "backend/app/pipeline/fixtures/negative/research/wrong_cc_version.md"
    ).read_text(encoding="utf-8")
    assert re.search(r"^cc_version: '2\.0'", wrong, re.MULTILINE)


# ---------------------------------------------------------------------------
# Acceptance — rollback when evals go red
# ---------------------------------------------------------------------------


def test_rollback_when_evals_fail(repo_root: Path, space: Path) -> None:
    finding = make_normalize_synonym_finding(
        "F1", "kbquery", "memory_retrieval"
    )
    write_retro_artifact(space, "my-feature", [finding])

    contract_path = repo_root / "packages/delivery-workflow/lib/contract.py"
    rules_path = repo_root / "backend/app/pipeline/normalize_rules.json"
    before_contract = contract_path.read_text(encoding="utf-8")
    before_rules = rules_path.read_text(encoding="utf-8")
    before_research_schema = (
        repo_root / "packages/delivery-workflow/lib/schemas/research.schema.yaml"
    ).read_text(encoding="utf-8")
    before_golden = (
        repo_root / "backend/app/pipeline/fixtures/golden/research.md"
    ).read_text(encoding="utf-8")

    result = apply_retro_improvements(
        slug="my-feature",
        space=space,
        repo_root=repo_root,
        evals_command=FAILING_EVALS,
    )

    # Rollback: nothing applied stays, no version bump survives, everything
    # restored byte-for-byte.
    assert result.rolled_back is True
    assert result.evals_passed is False
    assert result.cc_version_after is None
    assert result.applied == []
    # The skipped list documents the rollback.
    assert any(
        s.reason == "rolled back after evals went red" for s in result.skipped
    )
    assert read_cc_version(contract_path) == "1.0"
    assert contract_path.read_text(encoding="utf-8") == before_contract
    assert rules_path.read_text(encoding="utf-8") == before_rules
    assert (
        repo_root / "packages/delivery-workflow/lib/schemas/research.schema.yaml"
    ).read_text(encoding="utf-8") == before_research_schema
    assert (
        repo_root / "backend/app/pipeline/fixtures/golden/research.md"
    ).read_text(encoding="utf-8") == before_golden


# ---------------------------------------------------------------------------
# Acceptance — fixture finding applied
# ---------------------------------------------------------------------------


def test_fixture_finding_creates_new_file(repo_root: Path, space: Path) -> None:
    rel = (
        "backend/app/pipeline/fixtures/negative/research/new_drift.md"
    )
    fixture_content = textwrap.dedent(
        """\
        ---
        cc_version: '1.0'
        agent: scout
        slug: fixture-test
        ---

        ## Summary

        Synthetic negative fixture inserted by the auto-improver.
        """
    )
    finding = make_fixture_finding("F1", rel, fixture_content)
    write_retro_artifact(space, "my-feature", [finding])

    result = apply_retro_improvements(
        slug="my-feature",
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
    )

    assert result.error is None
    assert result.rolled_back is False
    assert len(result.applied) == 1
    assert result.applied[0].recipe == "fixture"
    new_file = repo_root / rel
    assert new_file.exists()
    assert "Synthetic negative fixture inserted" in new_file.read_text(
        encoding="utf-8"
    )
    # The freshly written fixture is pinned to '1.0' which is now the OLD
    # version; the propagation step rewrote it to '1.1'.
    assert "cc_version: '1.1'" in new_file.read_text(encoding="utf-8")


def test_fixture_rollback_removes_new_file(
    repo_root: Path, space: Path
) -> None:
    rel = (
        "backend/app/pipeline/fixtures/negative/research/short_lived.md"
    )
    fixture_content = textwrap.dedent(
        """\
        ---
        cc_version: '1.0'
        agent: scout
        slug: fixture-test
        ---

        ## Summary

        This fixture should not survive a failed eval run.
        """
    )
    finding = make_fixture_finding("F1", rel, fixture_content)
    write_retro_artifact(space, "my-feature", [finding])

    new_file = repo_root / rel
    assert not new_file.exists()

    result = apply_retro_improvements(
        slug="my-feature",
        space=space,
        repo_root=repo_root,
        evals_command=FAILING_EVALS,
    )

    assert result.rolled_back is True
    # Snapshot recorded the file as non-existent; rollback removes it.
    assert not new_file.exists()


def test_fixture_path_traversal_is_rejected(
    repo_root: Path, space: Path
) -> None:
    finding = {
        "id": "F1",
        "severity": "medium",
        "fix_type": "normalize_rule",
        "target": "fixture:backend/app/pipeline/fixtures/../../../etc/evil.md",
        "evidence": "n/a",
        "suggested_action": "n/a",
        "auto_apply": {"content": "evil"},
    }
    write_retro_artifact(space, "s", [finding])
    result = apply_retro_improvements(
        slug="s",
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
    )
    assert result.applied == []
    assert "'..'" in result.skipped[0].reason or "fixtures/" in result.skipped[0].reason


# ---------------------------------------------------------------------------
# Mixed batches — auto + skipped findings together
# ---------------------------------------------------------------------------


def test_mixed_batch_applies_only_machine_findings(
    repo_root: Path, space: Path
) -> None:
    """When some findings are auto-applicable and others not, only the
    auto-applicable ones land; the others are recorded in ``skipped``."""
    findings = [
        make_normalize_synonym_finding("F1", "kbq", "memory_retrieval"),
        {
            "id": "F2",
            "severity": "high",
            "fix_type": "agent_prompt_refinement",
            "target": "agent:pipeline-implementor",
            "evidence": "...",
            "suggested_action": "...",
        },
        {
            "id": "F3",
            "severity": "medium",
            "fix_type": "contract_change",
            "target": "contract:CONTRACT.md#7.2",
            "evidence": "...",
            "suggested_action": "...",
        },
    ]
    write_retro_artifact(space, "my-feature", findings)

    result = apply_retro_improvements(
        slug="my-feature",
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
    )

    assert len(result.applied) == 1
    assert result.applied[0].finding_id == "F1"
    skipped_ids = {s.finding_id for s in result.skipped}
    assert skipped_ids == {"F2", "F3"}
    assert result.cc_version_after == "1.1"


def test_empty_findings_does_nothing(repo_root: Path, space: Path) -> None:
    write_retro_artifact(space, "my-feature", [])
    result = apply_retro_improvements(
        slug="my-feature",
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
    )
    assert result.applied == []
    assert result.skipped == []
    assert result.evals_ran is False
    # No bump happened — version still 1.0.
    assert (
        read_cc_version(repo_root / "packages/delivery-workflow/lib/contract.py")
        == "1.0"
    )


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------


def test_dry_run_classifies_without_writing(
    repo_root: Path, space: Path
) -> None:
    finding = make_normalize_synonym_finding("F1", "kbq", "memory_retrieval")
    write_retro_artifact(space, "my-feature", [finding])

    contract_path = repo_root / "packages/delivery-workflow/lib/contract.py"
    rules_path = repo_root / "backend/app/pipeline/normalize_rules.json"
    before_contract = contract_path.read_text(encoding="utf-8")
    before_rules = rules_path.read_text(encoding="utf-8")

    result = apply_retro_improvements(
        slug="my-feature",
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
        dry_run=True,
    )

    assert result.dry_run is True
    assert len(result.applied) == 1
    assert result.applied[0].files_modified == []
    assert result.cc_version_before == "1.0"
    assert result.cc_version_after == "1.1"
    assert result.evals_ran is False
    # Nothing on disk changed.
    assert contract_path.read_text(encoding="utf-8") == before_contract
    assert rules_path.read_text(encoding="utf-8") == before_rules


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_missing_retro_artifact_returns_error(
    repo_root: Path, space: Path
) -> None:
    result = apply_retro_improvements(
        slug="no-such-slug",
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
    )
    assert result.error is not None
    assert "Retro artifact not found" in result.error
    assert result.applied == []


def test_retro_with_malformed_yaml_returns_error(
    repo_root: Path, space: Path
) -> None:
    slug = "bad-yaml"
    artifact_dir = space / ".cronos" / "pipeline" / slug
    artifact_dir.mkdir(parents=True)
    artifact_path = artifact_dir / f"retro-{slug}.md"
    artifact_path.write_text("not a yaml artifact\n", encoding="utf-8")

    result = apply_retro_improvements(
        slug=slug,
        space=space,
        repo_root=repo_root,
        evals_command=PASSING_EVALS,
    )
    assert result.error is not None
    assert result.applied == []


# ---------------------------------------------------------------------------
# Real-evals smoke — applier vs. the actual fixture harness
# ---------------------------------------------------------------------------


def test_strategy_synonym_recipe_keeps_fixture_harness_green(
    repo_root: Path, space: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: applier touches the synthetic repo + runs the actual
    ``test_pipeline_fixtures.py`` harness against it via a subprocess.
    Verifies adding a strategy synonym + bumping the version keeps goldens
    green and negatives red."""
    import os

    # Stand up a minimal backend package tree in the synthetic repo so pytest
    # can import ``app.pipeline`` against the patched contract/schemas/fixtures.
    backend = repo_root / "backend"
    (backend / "app").mkdir(parents=True, exist_ok=True)
    for sub in ("app", "app/pipeline"):
        init = backend / sub / "__init__.py"
        # Force an empty package init — the real __init__.py imports modules
        # (state_writer, auto_improver) we don't copy across, so we'd fail
        # to import the package as a whole.
        init.write_text("", encoding="utf-8")
    # Copy only the runtime modules the harness imports directly.
    for fname in ("verify.py", "normalize.py", "contract.py"):
        src = REAL_PIPELINE_DIR / fname
        if src.exists():
            shutil.copy(src, backend / "app" / "pipeline" / fname)
    # Tests dir + a copy of the fixture harness pointing at the synthetic repo.
    tests_dir = backend / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(
        REAL_REPO_ROOT / "backend" / "tests" / "test_pipeline_fixtures.py",
        tests_dir / "test_pipeline_fixtures.py",
    )

    finding = make_normalize_synonym_finding("F1", "kbq", "memory_retrieval")
    write_retro_artifact(space, "my-feature", [finding])

    eval_cmd = (
        sys.executable,
        "-m",
        "pytest",
        "backend/tests/test_pipeline_fixtures.py",
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
    )
    # Make the synthetic backend AND lib importable for the subprocess — prepend
    # so they win over the workspace backend the parent test imported from.
    # lib_pkg must be on PYTHONPATH so the stub verify.py (which does
    # `from lib.verify import verify`) resolves to the synthetic lib where
    # _bump_and_propagate() has already updated CC_VERSION.
    lib_pkg = repo_root / "packages" / "delivery-workflow"
    existing = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv(
        "PYTHONPATH",
        str(backend) + ":" + str(lib_pkg) + (":" + existing if existing else ""),
    )

    result = apply_retro_improvements(
        slug="my-feature",
        space=space,
        repo_root=repo_root,
        evals_command=eval_cmd,
        evals_timeout=120,
    )

    assert result.error is None, result.error
    assert result.evals_ran is True
    assert result.evals_passed is True, result.evals_output
    assert result.rolled_back is False
    assert result.cc_version_after == "1.1"
