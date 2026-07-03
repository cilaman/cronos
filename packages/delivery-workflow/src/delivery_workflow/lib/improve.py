"""
Tier-1/Tier-2 back-half applier for delivery/v1 self-improvement.

Public API
----------
classify_findings(findings) -> Routed
    Partition a list of retro findings into tier0/tier1/tier2 using
    fix_type-authoritative routing (DD-003). Ignores the `tier` value in
    the finding — fix_type is the source of truth.

render_proposal(finding) -> (title, body)
    Render a human-readable PR title and body for a Tier-1 finding.

run_back_half(tier1, tier2, *, evals_passed, repo_root, proposals_dir,
              pr_emitter=git_pr.emit_pr) -> BackHalfResult
    Emit one PR per Tier-1 finding (when evals_passed) and record every
    Tier-2 finding as escalated (no file write). Returns BackHalfResult.

CLI usage
---------
    python -m delivery_workflow.lib.improve <retro_artifact_path> \\
        --evals-passed [true|false] \\
        --proposals-dir <path> \\
        [--repo-root <path>]   # default: walk up from artifact to nearest .git

Prints JSON: {tier1_pr_urls, tier1_findings, tier2_escalated, errors}.

No app.* or backend.* imports — fully portable (spec §3.4, DD-002).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from delivery_workflow.lib.delivery_status import parse_delivery_status
from delivery_workflow.lib import git_pr

# fix_type → canonical tier mapping (DD-003, spec §3.2 tier table)
_TIER1_FIX_TYPES: frozenset[str] = frozenset({"gate_check", "agent_prompt", "skill"})
_TIER2_FIX_TYPES: frozenset[str] = frozenset({"schema", "workflow"})
# Everything else (fixture, threshold, …) → tier0


@dataclass
class Routed:
    """Partitioned findings after fix_type-authoritative classification."""
    tier0: list[dict[str, Any]] = field(default_factory=list)
    tier1: list[dict[str, Any]] = field(default_factory=list)
    tier2: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class BackHalfResult:
    """Result of the Tier-1/Tier-2 back-half pass."""
    tier1_pr_urls: list[str] = field(default_factory=list)
    tier1_findings: list[str] = field(default_factory=list)
    tier2_escalated: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def classify_findings(findings: list[dict[str, Any]]) -> Routed:
    """
    Partition *findings* into tier0/tier1/tier2 by fix_type (DD-003).

    The declared ``tier`` value is ignored — fix_type is authoritative.
    A note is recorded for any finding whose declared tier disagrees with
    the fix_type mapping.
    """
    result = Routed()
    for f in findings:
        fix_type = f.get("fix_type", "")
        declared_tier = f.get("tier")
        fid = f.get("id", "?")

        if fix_type in _TIER1_FIX_TYPES:
            result.tier1.append(f)
            if declared_tier != 1:
                result.notes.append(
                    f"{fid}: declared tier={declared_tier} overridden to 1 "
                    f"(fix_type={fix_type!r} is Tier-1-authoritative)"
                )
        elif fix_type in _TIER2_FIX_TYPES:
            result.tier2.append(f)
            if declared_tier != 2:
                result.notes.append(
                    f"{fid}: declared tier={declared_tier} overridden to 2 "
                    f"(fix_type={fix_type!r} is Tier-2-authoritative)"
                )
        else:
            result.tier0.append(f)

    return result


def render_proposal(finding: dict[str, Any]) -> tuple[str, str]:
    """
    Render a PR *title* and *body* for a Tier-1 *finding*.

    The body embeds all fields a human reviewer needs: id, fix_type, target,
    severity, evidence, and suggested_action (DD-004, REQ-003).
    """
    fid = finding.get("id", "unknown")
    fix_type = finding.get("fix_type", "")
    target = finding.get("target", "")
    severity = finding.get("severity", "")
    evidence = finding.get("evidence", "")
    suggested_action = finding.get("suggested_action", "")

    title = f"tier1-improvement({fid}): {fix_type} — {target}"
    body = (
        f"## Tier-1 Improvement Proposal\n\n"
        f"**Finding id**: {fid}\n"
        f"**fix_type**: {fix_type}\n"
        f"**target**: {target}\n"
        f"**severity**: {severity}\n\n"
        f"### Evidence\n\n{evidence}\n\n"
        f"### Suggested action\n\n{suggested_action}\n\n"
        f"---\n\n"
        f"*This PR adds a proposal document. A human implements the actual edit.*\n"
        f"*No source file under `agents/` or `skills/` has been modified.*\n"
    )
    return title, body


def run_back_half(
    tier1: list[dict[str, Any]],
    tier2: list[dict[str, Any]],
    *,
    evals_passed: bool,
    repo_root: str | Path,
    proposals_dir: str | Path,
    pr_emitter: object = None,
) -> BackHalfResult:
    """
    Execute the Tier-1/Tier-2 back-half of the improve applier.

    Tier-1: emit one PR per finding **only** when ``evals_passed`` is True.
    Tier-2: record each finding as escalated — no file write, no branch, no PR.

    Parameters
    ----------
    tier1:          Tier-1 findings (from classify_findings().tier1)
    tier2:          Tier-2 findings (from classify_findings().tier2)
    evals_passed:   True if the eval corpus exited 0 (DD-006)
    repo_root:      repository root for git/gh operations
    proposals_dir:  directory for PROPOSED_PR.md fallback files
    pr_emitter:     injectable PR emitter; defaults to git_pr.emit_pr
    """
    if pr_emitter is None:
        pr_emitter = git_pr.emit_pr

    result = BackHalfResult()

    # Tier-1: PR per finding, gated on evals (DD-006, REQ-002)
    for f in tier1:
        fid = f.get("id", "unknown")
        result.tier1_findings.append(fid)

        if not evals_passed:
            # Red evals → no PR (REQ-002)
            continue

        title, body = render_proposal(f)
        branch = f"delivery-improve-tier1-{fid}"
        try:
            url_or_path = pr_emitter(
                title,
                body,
                fid,
                branch=branch,
                repo_root=repo_root,
                proposals_dir=proposals_dir,
            )
            result.tier1_pr_urls.append(url_or_path)
        except Exception as exc:
            result.errors.append(f"{fid}: PR emission failed — {exc}")

    # Tier-2: escalate-only, no file write, no branch, no PR (REQ-004)
    for f in tier2:
        fid = f.get("id", "unknown")
        result.tier2_escalated.append(fid)

    return result


def _find_repo_root(start: Path) -> Path:
    """Walk up from *start* until a .git directory is found; return that directory.

    Falls back to *start* itself if no .git ancestor is found (e.g. in tests).
    """
    current = start.resolve()
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return start.resolve()
        current = parent


def _parse_findings_from_artifact(artifact_path: str) -> list[dict[str, Any]]:
    """Parse findings[] from a retro artifact's delivery_status fence."""
    text = Path(artifact_path).read_text(encoding="utf-8")
    block = parse_delivery_status(text)
    if block is None:
        raise ValueError(f"No delivery_status fence found in {artifact_path!r}")
    findings = block.fields.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError(f"findings[] is not a list in {artifact_path!r}")
    return findings


def _main(argv: list[str] | None = None) -> int:
    """CLI entry point: python -m delivery_workflow.lib.improve <retro_artifact> --evals-passed <bool> --proposals-dir <path>"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the Tier-1/Tier-2 back-half of the delivery/v1 improve applier."
    )
    parser.add_argument("retro_artifact", help="Path to the retro artifact markdown file")
    parser.add_argument(
        "--evals-passed",
        required=True,
        choices=["true", "false"],
        help="Whether the eval corpus exited 0 (true|false)",
    )
    parser.add_argument("--proposals-dir", required=True, help="Directory for PROPOSED_PR.md fallbacks")
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root for git/gh calls (default: walk up from artifact to nearest .git)",
    )
    args = parser.parse_args(argv)

    evals_passed = args.evals_passed == "true"
    proposals_dir = args.proposals_dir
    if args.repo_root:
        repo_root = Path(args.repo_root)
    else:
        repo_root = _find_repo_root(Path(args.retro_artifact).resolve().parent)

    try:
        findings = _parse_findings_from_artifact(args.retro_artifact)
    except Exception as exc:
        out = {
            "tier1_pr_urls": [],
            "tier1_findings": [],
            "tier2_escalated": [],
            "errors": [str(exc)],
        }
        print(json.dumps(out))
        return 1

    routed = classify_findings(findings)
    result = run_back_half(
        routed.tier1,
        routed.tier2,
        evals_passed=evals_passed,
        repo_root=repo_root,
        proposals_dir=proposals_dir,
    )

    out = {
        "tier1_pr_urls": result.tier1_pr_urls,
        "tier1_findings": result.tier1_findings,
        "tier2_escalated": result.tier2_escalated,
        "errors": result.errors,
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
