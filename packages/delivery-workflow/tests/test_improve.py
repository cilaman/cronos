"""
Behavioural tests for lib/improve.py — REQ-001 through REQ-006.

All git/gh and eval operations are injected — no network, no real branches.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from delivery_workflow.lib.improve import (
    BackHalfResult,
    Routed,
    classify_findings,
    render_proposal,
    run_back_half,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

AGENT_PROMPT_FINDING = {
    "id": "AP-1",
    "tier": 1,
    "fix_type": "agent_prompt",
    "target": "agents/implementor.md",
    "severity": "medium",
    "evidence": "backtrack_count=3",
    "suggested_action": "read scope_files once before first Edit",
    "recipe": None,
}

SKILL_FINDING = {
    "id": "SK-1",
    "tier": 1,
    "fix_type": "skill",
    "target": "skills/improve/SKILL.md",
    "severity": "low",
    "evidence": "missing section",
    "suggested_action": "add section X",
    "recipe": None,
}

GATE_CHECK_FINDING = {
    "id": "GC-1",
    "tier": 1,
    "fix_type": "gate_check",
    "target": "gate_check:review",
    "severity": "high",
    "evidence": "gate fail-opens on empty artifact_paths",
    "suggested_action": "fail-closed",
    "recipe": None,
}

SCHEMA_FINDING = {
    "id": "SCH-1",
    "tier": 2,
    "fix_type": "schema",
    "target": "schemas/retro.schema.yaml",
    "severity": "low",
    "evidence": "missing field X",
    "suggested_action": "add field X",
    "recipe": None,
}

WORKFLOW_FINDING = {
    "id": "WF-1",
    "tier": 2,
    "fix_type": "workflow",
    "target": "delivery.workflow.yaml",
    "severity": "medium",
    "evidence": "node missing edge",
    "suggested_action": "add edge",
    "recipe": None,
}

FIXTURE_FINDING = {
    "id": "FX-1",
    "tier": 0,
    "fix_type": "fixture",
    "target": "fixture:packages/delivery-workflow/tests/fixtures/sample.json",
    "severity": "low",
    "evidence": "fixture outdated",
    "suggested_action": "update content",
    "recipe": {"content": '{"version": 2}\n'},
}

THRESHOLD_FINDING = {
    "id": "TH-1",
    "tier": 0,
    "fix_type": "threshold",
    "target": "threshold:g-tests.max",
    "severity": "low",
    "evidence": "loop max too low",
    "suggested_action": "raise to 5",
    "recipe": {"old": 3, "new": 5},
}


# ---------------------------------------------------------------------------
# REQ-001: Tier routing
# ---------------------------------------------------------------------------

class TestClassifyFindings:
    def test_agent_prompt_goes_to_tier1(self):
        r = classify_findings([AGENT_PROMPT_FINDING])
        assert len(r.tier1) == 1 and r.tier0 == [] and r.tier2 == []

    def test_skill_goes_to_tier1(self):
        r = classify_findings([SKILL_FINDING])
        assert len(r.tier1) == 1 and r.tier0 == [] and r.tier2 == []

    def test_gate_check_goes_to_tier1(self):
        r = classify_findings([GATE_CHECK_FINDING])
        assert len(r.tier1) == 1 and r.tier0 == [] and r.tier2 == []

    def test_schema_goes_to_tier2(self):
        r = classify_findings([SCHEMA_FINDING])
        assert len(r.tier2) == 1 and r.tier0 == [] and r.tier1 == []

    def test_workflow_goes_to_tier2(self):
        r = classify_findings([WORKFLOW_FINDING])
        assert len(r.tier2) == 1 and r.tier0 == [] and r.tier1 == []

    def test_fixture_goes_to_tier0(self):
        r = classify_findings([FIXTURE_FINDING])
        assert len(r.tier0) == 1 and r.tier1 == [] and r.tier2 == []

    def test_threshold_goes_to_tier0(self):
        r = classify_findings([THRESHOLD_FINDING])
        assert len(r.tier0) == 1 and r.tier1 == [] and r.tier2 == []

    def test_mixed_set(self):
        all_findings = [
            AGENT_PROMPT_FINDING, SKILL_FINDING, GATE_CHECK_FINDING,
            SCHEMA_FINDING, WORKFLOW_FINDING, FIXTURE_FINDING, THRESHOLD_FINDING,
        ]
        r = classify_findings(all_findings)
        assert len(r.tier0) == 2
        assert len(r.tier1) == 3
        assert len(r.tier2) == 2

    def test_fix_type_overrides_declared_tier(self):
        """A finding with tier=0 but fix_type=agent_prompt must go to tier1 (DD-003)."""
        mis_tiered = dict(AGENT_PROMPT_FINDING, tier=0, id="MT-1")
        r = classify_findings([mis_tiered])
        assert r.tier0 == []
        assert len(r.tier1) == 1
        assert r.tier1[0]["id"] == "MT-1"
        assert len(r.notes) >= 1, "Classifier should record a note for overridden tier"

    def test_empty_findings(self):
        r = classify_findings([])
        assert r.tier0 == [] and r.tier1 == [] and r.tier2 == []


# ---------------------------------------------------------------------------
# REQ-003: render_proposal
# ---------------------------------------------------------------------------

class TestRenderProposal:
    def test_title_contains_fix_type_and_target(self):
        title, body = render_proposal(AGENT_PROMPT_FINDING)
        assert "agent_prompt" in title
        assert "agents/implementor.md" in title

    def test_body_contains_required_fields(self):
        title, body = render_proposal(AGENT_PROMPT_FINDING)
        assert "AP-1" in body
        assert "agent_prompt" in body
        assert "agents/implementor.md" in body
        assert "medium" in body
        assert "backtrack_count=3" in body
        assert "read scope_files once" in body

    def test_body_states_human_implements(self):
        _, body = render_proposal(AGENT_PROMPT_FINDING)
        assert "human" in body.lower()

    def test_all_tier1_fix_types_render(self):
        for finding in [AGENT_PROMPT_FINDING, SKILL_FINDING, GATE_CHECK_FINDING]:
            title, body = render_proposal(finding)
            assert finding["id"] in body
            assert finding["fix_type"] in body


# ---------------------------------------------------------------------------
# REQ-002: No PR emitted on red evals
# ---------------------------------------------------------------------------

class TestNoPROnRedEvals:
    def test_tier1_pr_urls_empty_on_red_evals(self, tmp_path):
        r = classify_findings([AGENT_PROMPT_FINDING, SKILL_FINDING])

        exploding_emitter_calls: list = []

        def exploding_emitter(*a, **k):
            exploding_emitter_calls.append((a, k))
            raise AssertionError("pr_emitter must not be called when evals are red")

        result = run_back_half(
            r.tier1, r.tier2,
            evals_passed=False,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
            pr_emitter=exploding_emitter,
        )

        assert exploding_emitter_calls == [], "pr_emitter was called despite red evals"
        assert result.tier1_pr_urls == []
        assert set(result.tier1_findings) == {"AP-1", "SK-1"}

    def test_tier2_escalated_even_on_red_evals(self, tmp_path):
        """Tier-2 escalation is ungated — always records even when evals red (DD-006)."""
        r = classify_findings([SCHEMA_FINDING, WORKFLOW_FINDING])
        result = run_back_half(
            r.tier1, r.tier2,
            evals_passed=False,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
        )
        assert set(result.tier2_escalated) == {"SCH-1", "WF-1"}


# ---------------------------------------------------------------------------
# REQ-003: PR emitted once per Tier-1 finding, body carries required fields
# ---------------------------------------------------------------------------

class TestOnePRPerFinding:
    def test_stub_emitter_called_once_per_tier1_finding(self, tmp_path):
        r = classify_findings([AGENT_PROMPT_FINDING, SKILL_FINDING, GATE_CHECK_FINDING])

        calls: list[dict] = []

        def stub_emitter(title, body, finding_id, *, branch, repo_root, proposals_dir, **_):
            calls.append({"title": title, "body": body, "finding_id": finding_id, "branch": branch})
            p = tmp_path / f"proposed-pr-{finding_id}.md"
            p.write_text(f"# {title}\n\n{body}\n")
            return str(p)

        result = run_back_half(
            r.tier1, r.tier2,
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
            pr_emitter=stub_emitter,
        )

        assert len(calls) == 3, f"Expected 3 emitter calls, got {len(calls)}"
        call_ids = {c["finding_id"] for c in calls}
        assert call_ids == {"AP-1", "SK-1", "GC-1"}

    def test_pr_body_carries_all_required_fields(self, tmp_path):
        r = classify_findings([AGENT_PROMPT_FINDING])

        captured_bodies: list[str] = []

        def stub_emitter(title, body, finding_id, *, branch, repo_root, proposals_dir, **_):
            captured_bodies.append(body)
            p = tmp_path / f"proposed-pr-{finding_id}.md"
            p.write_text(f"# {title}\n\n{body}\n")
            return str(p)

        run_back_half(
            r.tier1, r.tier2,
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
            pr_emitter=stub_emitter,
        )

        assert len(captured_bodies) == 1
        body = captured_bodies[0]
        assert "AP-1" in body
        assert "agent_prompt" in body
        assert "agents/implementor.md" in body
        assert "medium" in body
        assert "backtrack_count=3" in body
        assert "read scope_files once" in body

    def test_proposed_pr_md_fallback_written(self, tmp_path):
        """When gh probe returns False, PROPOSED_PR.md fallback is written (REQ-003)."""
        from delivery_workflow.lib.git_pr import emit_pr

        proposals_dir = tmp_path / "proposals"
        fallback_path = emit_pr(
            "Test PR",
            "body text",
            "AP-1",
            branch="delivery-improve-tier1-AP-1",
            repo_root=tmp_path,
            proposals_dir=proposals_dir,
            gh_probe=lambda *_: False,
        )
        path = Path(fallback_path)
        assert path.exists()
        assert "body text" in path.read_text()
        assert "proposed-pr-AP-1" in path.name

    def test_tier1_pr_urls_populated_on_green_evals(self, tmp_path):
        r = classify_findings([AGENT_PROMPT_FINDING, SKILL_FINDING])

        def stub_emitter(title, body, finding_id, *, branch, repo_root, proposals_dir, **_):
            p = tmp_path / f"proposed-pr-{finding_id}.md"
            p.write_text(f"# {title}\n\n{body}\n")
            return str(p)

        result = run_back_half(
            r.tier1, r.tier2,
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
            pr_emitter=stub_emitter,
        )

        assert len(result.tier1_pr_urls) == 2
        assert set(result.tier1_findings) == {"AP-1", "SK-1"}


# ---------------------------------------------------------------------------
# REQ-004: Tier-2 escalate-only (no file write, no branch, no PR)
# ---------------------------------------------------------------------------

class TestTier2EscalateOnly:
    def test_no_file_written_for_tier2(self, tmp_path):
        """Tier-2 findings must never write any file."""
        r = classify_findings([SCHEMA_FINDING, WORKFLOW_FINDING])

        files_before = set(tmp_path.rglob("*"))

        def stub_emitter(*a, **k):
            raise AssertionError("pr_emitter must not be called for Tier-2")

        result = run_back_half(
            r.tier1, r.tier2,
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
            pr_emitter=stub_emitter,
        )

        # Verify no files written (proposals_dir not created for tier2)
        files_after = set(tmp_path.rglob("*"))
        new_files = files_after - files_before
        assert not new_files, f"Unexpected files created for Tier-2: {new_files}"

    def test_tier2_ids_in_escalated_list(self, tmp_path):
        r = classify_findings([SCHEMA_FINDING, WORKFLOW_FINDING])
        result = run_back_half(
            r.tier1, r.tier2,
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
        )
        assert set(result.tier2_escalated) == {"SCH-1", "WF-1"}
        assert result.tier1_pr_urls == []
        assert result.tier1_findings == []

    def test_status_done_with_only_tier2(self, tmp_path):
        """REQ-004: status=done even when only Tier-2 present (no crash/blocked)."""
        r = classify_findings([SCHEMA_FINDING])
        result = run_back_half(
            r.tier1, r.tier2,
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
        )
        # No exception raised; errors list is empty = success
        assert result.errors == []
        assert result.tier2_escalated == ["SCH-1"]


# ---------------------------------------------------------------------------
# REQ-006: Extended delivery_status fence fields
# ---------------------------------------------------------------------------

class TestBackHalfResultFields:
    def test_all_three_new_fields_present(self, tmp_path):
        r = classify_findings([AGENT_PROMPT_FINDING, SCHEMA_FINDING])

        def stub_emitter(title, body, finding_id, *, branch, repo_root, proposals_dir, **_):
            p = tmp_path / f"proposed-pr-{finding_id}.md"
            p.write_text(f"# {title}\n\n{body}\n")
            return str(p)

        result = run_back_half(
            r.tier1, r.tier2,
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
            pr_emitter=stub_emitter,
        )

        assert hasattr(result, "tier1_pr_urls")
        assert hasattr(result, "tier1_findings")
        assert hasattr(result, "tier2_escalated")
        assert hasattr(result, "errors")

    def test_tier0_fields_preserved(self, tmp_path):
        """tier0_applied and tier0_rolled_back semantics must not be broken (DD-007)."""
        # run_back_half doesn't touch Tier-0 fields — they're owned by the Tier-0 step.
        # This test verifies that BackHalfResult does NOT have tier0_applied, since
        # those are tracked by the Tier-0 applier and must be merged by the skill driver.
        r = classify_findings([AGENT_PROMPT_FINDING])

        def stub_emitter(title, body, finding_id, *, branch, repo_root, proposals_dir, **_):
            p = tmp_path / f"proposed-pr-{finding_id}.md"
            p.write_text(f"# {title}\n\n{body}\n")
            return str(p)

        result = run_back_half(
            r.tier1, r.tier2,
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
            pr_emitter=stub_emitter,
        )

        # The back-half result has no tier0 fields — those belong to the Tier-0 applier
        assert not hasattr(result, "tier0_applied")
        assert not hasattr(result, "tier0_rolled_back")

    def test_empty_lists_when_no_findings(self, tmp_path):
        result = run_back_half(
            [], [],
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
        )
        assert result.tier1_pr_urls == []
        assert result.tier1_findings == []
        assert result.tier2_escalated == []
        assert result.errors == []

    def test_errors_list_populated_on_emitter_failure(self, tmp_path):
        """Individual emitter failures go to errors[], not a crash."""
        r = classify_findings([AGENT_PROMPT_FINDING, SKILL_FINDING])

        call_count = [0]

        def failing_emitter(title, body, finding_id, *, branch, repo_root, proposals_dir, **_):
            call_count[0] += 1
            raise RuntimeError(f"gh failed for {finding_id}")

        result = run_back_half(
            r.tier1, r.tier2,
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
            pr_emitter=failing_emitter,
        )

        assert call_count[0] == 2, "Emitter must be attempted for all findings"
        assert len(result.errors) == 2
        assert result.tier1_pr_urls == []
        # findings are still tracked even if emission failed
        assert set(result.tier1_findings) == {"AP-1", "SK-1"}


# ---------------------------------------------------------------------------
# Real-gh path: stable base ref + HEAD restore (F1 fix coverage)
# ---------------------------------------------------------------------------

class TestGhPath:
    """Tests for the real-gh emit_pr path using an injectable runner."""

    def _make_fake_runner(self, pr_url: str = "https://github.com/owner/repo/pull/1"):
        """Return (calls_list, fake_runner) where calls_list accumulates every argv."""
        calls: list[list[str]] = []

        def fake_runner(cmd: list[str], *, cwd=None) -> tuple[int, str, str]:
            calls.append(list(cmd))
            if cmd[:2] == ["git", "rev-parse"]:
                return (0, "main", "")
            if cmd[:2] == ["gh", "pr"]:
                return (0, pr_url, "")
            # git checkout, add, commit, push — all succeed silently
            return (0, "", "")

        return calls, fake_runner

    def test_emit_pr_gh_path_uses_stable_base_ref(self, tmp_path):
        """Branch is created with the stable base ref as explicit parent."""
        from delivery_workflow.lib.git_pr import emit_pr

        calls, fake_runner = self._make_fake_runner()
        proposals = tmp_path / "proposals"

        url = emit_pr(
            "Test PR", "body content", "F1",
            branch="delivery-improve-tier1-F1",
            repo_root=tmp_path,
            proposals_dir=proposals,
            gh_probe=lambda *_: True,
            runner=fake_runner,
        )

        assert url == "https://github.com/owner/repo/pull/1"

        # checkout -b must include the base ref as the 4th arg
        checkout_b = [c for c in calls if c[:3] == ["git", "checkout", "-b"]]
        assert len(checkout_b) == 1
        assert checkout_b[0] == ["git", "checkout", "-b", "delivery-improve-tier1-F1", "main"], (
            f"Expected checkout with stable base 'main', got: {checkout_b[0]}"
        )

    def test_emit_pr_gh_path_restores_head_after_success(self, tmp_path):
        """HEAD is restored to the original branch after a successful PR emission."""
        from delivery_workflow.lib.git_pr import emit_pr

        calls, fake_runner = self._make_fake_runner()
        proposals = tmp_path / "proposals"

        emit_pr(
            "Test PR", "body", "F1",
            branch="delivery-improve-tier1-F1",
            repo_root=tmp_path,
            proposals_dir=proposals,
            gh_probe=lambda *_: True,
            runner=fake_runner,
        )

        # git checkout <base> (without -b) must appear after the branch work
        restore_calls = [
            c for c in calls
            if c[:2] == ["git", "checkout"] and len(c) == 3 and "-b" not in c
        ]
        assert any(c[2] == "main" for c in restore_calls), (
            f"Expected HEAD restore to 'main', got restore calls: {restore_calls}"
        )

    def test_emit_pr_gh_path_restores_head_on_failure(self, tmp_path):
        """HEAD is restored even when gh pr create fails (finally block)."""
        from delivery_workflow.lib.git_pr import emit_pr

        calls: list[list[str]] = []

        def failing_runner(cmd: list[str], *, cwd=None) -> tuple[int, str, str]:
            calls.append(list(cmd))
            if cmd[:2] == ["git", "rev-parse"]:
                return (0, "main", "")
            if cmd[:2] == ["gh", "pr"]:
                return (1, "", "error: not a GitHub repo")  # gh fails
            return (0, "", "")

        proposals = tmp_path / "proposals"
        # Falls back to PROPOSED_PR.md since gh returned rc=1
        result = emit_pr(
            "Test PR", "body", "F1",
            branch="delivery-improve-tier1-F1",
            repo_root=tmp_path,
            proposals_dir=proposals,
            gh_probe=lambda *_: True,
            runner=failing_runner,
        )

        # Result is the fallback file path
        assert Path(result).exists()

        # HEAD must still be restored
        restore_calls = [
            c for c in calls
            if c[:2] == ["git", "checkout"] and len(c) == 3 and "-b" not in c
        ]
        assert any(c[2] == "main" for c in restore_calls), (
            f"HEAD must be restored even on gh failure; restore calls: {restore_calls}"
        )

    def test_two_findings_branch_from_same_stable_base(self, tmp_path):
        """REQ-003 + F1 fix: 2 sequential emit_pr calls both branch from the same base."""
        from delivery_workflow.lib.git_pr import emit_pr

        calls, fake_runner = self._make_fake_runner()
        proposals = tmp_path / "proposals"

        for fid, branch in [("F1", "delivery-improve-tier1-F1"), ("F2", "delivery-improve-tier1-F2")]:
            emit_pr(
                f"PR for {fid}", f"body {fid}", fid,
                branch=branch,
                repo_root=tmp_path,
                proposals_dir=proposals,
                gh_probe=lambda *_: True,
                runner=fake_runner,
            )

        checkout_b_calls = [c for c in calls if c[:3] == ["git", "checkout", "-b"]]
        assert len(checkout_b_calls) == 2, f"Expected 2 branch creations, got: {checkout_b_calls}"

        # Both branches must be created from the SAME base ref
        bases = [c[4] for c in checkout_b_calls]
        assert bases[0] == bases[1], (
            f"Branches stacked on different bases: {bases[0]!r} vs {bases[1]!r}. "
            "Each call must capture a fresh base ref (they'll both be 'main' here)."
        )

    def test_run_back_half_two_findings_all_get_prs(self, tmp_path):
        """end-to-end: run_back_half with gh path produces one PR per finding."""
        from delivery_workflow.lib.git_pr import emit_pr

        pr_counter = [0]

        def counting_runner(cmd: list[str], *, cwd=None) -> tuple[int, str, str]:
            if cmd[:2] == ["git", "rev-parse"]:
                return (0, "main", "")
            if cmd[:2] == ["gh", "pr"]:
                pr_counter[0] += 1
                return (0, f"https://github.com/owner/repo/pull/{pr_counter[0]}", "")
            return (0, "", "")

        def gh_emitter(title, body, finding_id, *, branch, repo_root, proposals_dir, **_):
            return emit_pr(
                title, body, finding_id,
                branch=branch,
                repo_root=Path(repo_root),
                proposals_dir=Path(proposals_dir),
                gh_probe=lambda *_: True,
                runner=counting_runner,
            )

        findings = [
            {"id": "A1", "tier": 1, "fix_type": "agent_prompt", "target": "agents/implementor.md",
             "severity": "med", "evidence": "e", "suggested_action": "s"},
            {"id": "B2", "tier": 1, "fix_type": "skill", "target": "skills/improve/SKILL.md",
             "severity": "low", "evidence": "e", "suggested_action": "s"},
        ]
        routed = classify_findings(findings)
        result = run_back_half(
            routed.tier1, routed.tier2,
            evals_passed=True,
            repo_root=str(tmp_path),
            proposals_dir=str(tmp_path / "proposals"),
            pr_emitter=gh_emitter,
        )

        assert len(result.tier1_pr_urls) == 2
        assert all(url.startswith("https://") for url in result.tier1_pr_urls)
        assert set(result.tier1_findings) == {"A1", "B2"}
        assert result.errors == []
