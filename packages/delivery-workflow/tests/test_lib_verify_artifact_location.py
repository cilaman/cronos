"""Tests for lib/verify.py artifact-path resolution: canonical_artifact_relpath,
delivery_artifact_relpath, locate_artifact, and verify()'s artifact_path override.

Regression coverage for the bug where a gate's schema check always reconstructed
the CC-v1 .cronos/pipeline/ path from class+slug (canonical_artifact_relpath),
with no awareness of the delivery-workflow .cronos/delivery/ convention and no
way to use an already-known real artifact path — so a valid report written under
.cronos/delivery/<slug>/ failed with "artifact not found at expected path" naming
the wrong (pipeline-convention) location.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path


from delivery_workflow.lib.verify import (
    canonical_artifact_relpath,
    delivery_artifact_relpath,
    locate_artifact,
    verify,
)


def _valid_research_content(slug: str, outputs_produced: str) -> str:
    return textwrap.dedent(f"""\
        ---
        cc_version: '1.0'
        agent: scout
        slug: {slug}
        phase: scout
        status: done
        confidence: 0.9
        inputs_used:
        - backend/app/main.py
        outputs_produced:
        - {outputs_produced}
        blockers: []
        next_consumer: analysis
        coverage_summary:
          searched:
          - backend/app/main.py
          excluded:
          - frontend/
          strategies:
          - read_targeted
        metrics:
          tool_calls: 3
          files_read: 1
          memory_hits: 0
        ---

        ## Summary

        Scout report for verify() artifact-location testing.

        ## Coverage

        Searched backend/app/main.py; excluded frontend/.

        ## Findings

        - Nothing notable.

        ## Assumptions

        None.

        ## Open questions

        None.

        ## Next consumer brief

        Proceed to analysis.
    """)


class TestCanonicalAndDeliveryRelpath:
    def test_canonical_artifact_relpath_pipeline_convention(self):
        assert canonical_artifact_relpath("research", "my-goal") == (
            ".cronos/pipeline/my-goal/scout-report-my-goal.md"
        )

    def test_canonical_artifact_relpath_splits_fanout_slug(self):
        assert canonical_artifact_relpath("research", "parent--i2") == (
            ".cronos/pipeline/parent/scout-report-parent--i2.md"
        )

    def test_delivery_artifact_relpath_bare_filename(self):
        assert delivery_artifact_relpath("research", "my-goal") == (
            ".cronos/delivery/my-goal/scout-report.md"
        )

    def test_delivery_artifact_relpath_does_not_split_fanout_slug(self):
        """Delivery-workflow goals are not CC-v1 fan-out iterations — the full
        slug (including any '--') names the directory verbatim."""
        assert delivery_artifact_relpath("research", "parent--i2") == (
            ".cronos/delivery/parent--i2/scout-report.md"
        )


class TestLocateArtifact:
    def test_prefers_pipeline_when_only_pipeline_exists(self, tmp_path):
        pdir = tmp_path / ".cronos" / "pipeline" / "my-goal"
        pdir.mkdir(parents=True)
        (pdir / "scout-report-my-goal.md").write_text("x")
        assert locate_artifact("research", "my-goal", tmp_path) == (
            ".cronos/pipeline/my-goal/scout-report-my-goal.md"
        )

    def test_falls_back_to_delivery_when_only_delivery_exists(self, tmp_path):
        ddir = tmp_path / ".cronos" / "delivery" / "my-goal"
        ddir.mkdir(parents=True)
        (ddir / "scout-report.md").write_text("x")
        assert locate_artifact("research", "my-goal", tmp_path) == (
            ".cronos/delivery/my-goal/scout-report.md"
        )

    def test_prefers_pipeline_when_both_exist(self, tmp_path):
        pdir = tmp_path / ".cronos" / "pipeline" / "my-goal"
        pdir.mkdir(parents=True)
        (pdir / "scout-report-my-goal.md").write_text("x")
        ddir = tmp_path / ".cronos" / "delivery" / "my-goal"
        ddir.mkdir(parents=True)
        (ddir / "scout-report.md").write_text("x")
        assert locate_artifact("research", "my-goal", tmp_path) == (
            ".cronos/pipeline/my-goal/scout-report-my-goal.md"
        )

    def test_defaults_to_pipeline_path_when_neither_exists(self, tmp_path):
        """A 'not found' caller still gets a sensible (primary-convention) path
        to name in its error message, not None."""
        assert locate_artifact("research", "my-goal", tmp_path) == (
            ".cronos/pipeline/my-goal/scout-report-my-goal.md"
        )


class TestVerifyArtifactPathOverride:
    def test_explicit_delivery_path_is_used_directly(self, tmp_path):
        """The core regression: verify() must check the REAL given path, not
        reconstruct one from class+slug via the pipeline-only convention."""
        ddir = tmp_path / ".cronos" / "delivery" / "my-goal"
        ddir.mkdir(parents=True)
        artifact = ddir / "scout-report.md"
        artifact.write_text(
            _valid_research_content("my-goal", ".cronos/delivery/my-goal/scout-report.md")
        )
        result = verify("research", "my-goal", tmp_path, artifact_path=str(artifact))
        assert result.outcome == "proceed", result.errors
        assert result.artifact_path == ".cronos/delivery/my-goal/scout-report.md"

    def test_explicit_path_relative_to_space_is_resolved(self, tmp_path):
        ddir = tmp_path / ".cronos" / "delivery" / "my-goal"
        ddir.mkdir(parents=True)
        (ddir / "scout-report.md").write_text(
            _valid_research_content("my-goal", ".cronos/delivery/my-goal/scout-report.md")
        )
        result = verify(
            "research", "my-goal", tmp_path,
            artifact_path=".cronos/delivery/my-goal/scout-report.md",
        )
        assert result.outcome == "proceed", result.errors

    def test_explicit_path_missing_reports_that_exact_path_not_a_guess(self, tmp_path):
        """No silent re-guessing across conventions once a real path is known
        (would reopen the cross-goal artifact-leakage risk the adapter's B2
        scoping guard exists to prevent)."""
        missing = tmp_path / ".cronos" / "delivery" / "my-goal" / "scout-report.md"
        result = verify("research", "my-goal", tmp_path, artifact_path=str(missing))
        assert result.outcome == "retry"
        assert ".cronos/delivery/my-goal/scout-report.md" in result.errors[0]

    def test_no_artifact_path_falls_back_to_locate_artifact(self, tmp_path):
        """Backward compatibility: the CLI (and any caller with no path
        context) still resolves via the pipeline/delivery convention guess."""
        ddir = tmp_path / ".cronos" / "delivery" / "my-goal"
        ddir.mkdir(parents=True)
        (ddir / "scout-report.md").write_text(
            _valid_research_content("my-goal", ".cronos/delivery/my-goal/scout-report.md")
        )
        result = verify("research", "my-goal", tmp_path)  # no artifact_path
        assert result.outcome == "proceed", result.errors

    def test_no_artifact_path_and_nothing_on_disk_retries_pipeline_path(self, tmp_path):
        result = verify("research", "no-such-goal", tmp_path)
        assert result.outcome == "retry"
        assert (
            ".cronos/pipeline/no-such-goal/scout-report-no-such-goal.md"
            in result.errors[0]
        )
