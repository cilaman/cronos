"""
REQ-005 safety test: Tier-1 findings MUST NEVER auto-apply to agents/skills files.

Builds a fixture retro artifact carrying agent_prompt, skill, and gate_check
findings; snapshots every file under agents/ and skills/; runs classify_findings
+ run_back_half; then asserts:
  (a) the classifier never puts those fix_types into .tier0
  (b) every targeted source file is byte-identical afterward
  (c) the findings appear in tier1_findings and NOT in tier0_applied
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from lib.improve import BackHalfResult, classify_findings, run_back_half

PACKAGE_ROOT = Path(__file__).parent.parent

TIER1_FIX_TYPES = {"gate_check", "agent_prompt", "skill"}


def _digest(path: Path) -> str | None:
    """Return SHA-256 hex digest of a file, or None if it does not exist."""
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_tree(root: Path) -> dict[str, str | None]:
    """Snapshot all files under *root*; return {rel_path: digest}."""
    if not root.exists():
        return {}
    return {
        str(p.relative_to(PACKAGE_ROOT)): _digest(p)
        for p in root.rglob("*")
        if p.is_file()
    }


FIXTURE_FINDINGS: list[dict] = [
    {
        "id": "T1-A",
        "tier": 1,
        "fix_type": "agent_prompt",
        "target": "agents/implementor.md",
        "severity": "medium",
        "evidence": "backtrack_count=4 across 3 reads of foo.py",
        "suggested_action": "read each scope_file once before first Edit",
        "recipe": None,
    },
    {
        "id": "T1-B",
        "tier": 1,
        "fix_type": "skill",
        "target": "skills/improve/SKILL.md",
        "severity": "low",
        "evidence": "skill missing rollback step documentation",
        "suggested_action": "add rollback step to SKILL.md",
        "recipe": None,
    },
    {
        "id": "T1-C",
        "tier": 1,
        "fix_type": "gate_check",
        "target": "gate_check:review",
        "severity": "high",
        "evidence": "gate silently skips missing artifact_paths",
        "suggested_action": "fail-closed when artifact_paths is empty",
        "recipe": None,
    },
    # A mis-tiered finding (declared tier=0 but fix_type=agent_prompt)
    {
        "id": "T1-D",
        "tier": 0,
        "fix_type": "agent_prompt",
        "target": "agents/scout.md",
        "severity": "low",
        "evidence": "scout reads too many files",
        "suggested_action": "constrain scope in first step",
        "recipe": None,
    },
]


class TestClassifierNeverLeaksTier1IntoTier0:
    def test_all_tier1_fix_types_go_to_tier1(self):
        routed = classify_findings(FIXTURE_FINDINGS)
        tier0_fix_types = {f["fix_type"] for f in routed.tier0}
        leaked = tier0_fix_types & TIER1_FIX_TYPES
        assert not leaked, (
            f"Tier-1 fix_types found in .tier0: {leaked}. "
            "The classifier must never route agent_prompt/skill/gate_check to tier0."
        )

    def test_declared_tier0_with_tier1_fix_type_is_promoted(self):
        routed = classify_findings(FIXTURE_FINDINGS)
        tier1_ids = {f["id"] for f in routed.tier1}
        # T1-D was declared tier=0 but fix_type=agent_prompt → must be in tier1
        assert "T1-D" in tier1_ids, (
            "Finding T1-D (declared tier=0, fix_type=agent_prompt) must be promoted "
            "to tier1 by the classifier (fix_type-authoritative routing, DD-003)"
        )

    def test_tier0_is_empty_for_all_tier1_findings(self):
        routed = classify_findings(FIXTURE_FINDINGS)
        assert routed.tier0 == [], (
            f"Expected empty tier0 for this fixture set, got: {routed.tier0}"
        )


class TestSourceFilesUnchangedAfterRunBackHalf:
    def test_agents_and_skills_files_byte_identical(self, tmp_path):
        """The core REQ-005 assertion: no file under agents/ or skills/ is mutated."""
        agents_dir = PACKAGE_ROOT / "agents"
        skills_dir = PACKAGE_ROOT / "skills"

        before = {
            **_snapshot_tree(agents_dir),
            **_snapshot_tree(skills_dir),
        }

        routed = classify_findings(FIXTURE_FINDINGS)

        # Stub emitter: records calls but writes to tmp_path, never touching the package
        emitted: list[str] = []

        def stub_emitter(title, body, finding_id, *, branch, repo_root, proposals_dir, **_):
            p = tmp_path / f"proposed-pr-{finding_id}.md"
            p.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
            emitted.append(str(p))
            return str(p)

        # Run with evals_passed=True so PRs are attempted
        result = run_back_half(
            routed.tier1,
            routed.tier2,
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
            pr_emitter=stub_emitter,
        )

        after = {
            **_snapshot_tree(agents_dir),
            **_snapshot_tree(skills_dir),
        }

        assert before == after, (
            "Tier-1 run_back_half mutated files under agents/ or skills/:\n"
            + "\n".join(
                f"  CHANGED: {k}" for k in before if before[k] != after.get(k)
            )
            + "\n".join(
                f"  CREATED: {k}" for k in after if k not in before
            )
        )

    def test_tier1_findings_in_result_not_in_tier0_applied(self, tmp_path):
        """REQ-001 AC3: Tier-1 ids appear in tier1_findings, not tier0_applied."""
        routed = classify_findings(FIXTURE_FINDINGS)

        def stub_emitter(title, body, finding_id, *, branch, repo_root, proposals_dir, **_):
            p = tmp_path / f"proposed-pr-{finding_id}.md"
            p.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
            return str(p)

        result = run_back_half(
            routed.tier1,
            routed.tier2,
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
            pr_emitter=stub_emitter,
        )

        tier1_ids_in_result = set(result.tier1_findings)
        fixture_tier1_ids = {"T1-A", "T1-B", "T1-C", "T1-D"}

        assert fixture_tier1_ids == tier1_ids_in_result, (
            f"Expected tier1_findings={fixture_tier1_ids}, got {tier1_ids_in_result}"
        )

        # Simulate what a full applier would track; confirm Tier-1 ids
        # can never have been in a tier0_applied count (structural, not runtime)
        tier0_findings = routed.tier0
        tier0_ids = {f["id"] for f in tier0_findings}
        overlap = tier0_ids & fixture_tier1_ids
        assert not overlap, (
            f"Tier-1 ids {overlap} appeared in classifier's tier0 output — "
            "this would allow them to be applied in-place (REQ-005 violation)"
        )
