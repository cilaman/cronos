"""
Portable git/gh PR helper for delivery/v1 Tier-1 improvements.

Provides emit_pr() which either creates a real GitHub PR via the gh CLI
or writes a PROPOSED_PR.md fallback when gh/GitHub is unavailable.

No app.* or backend.* imports — fully portable (spec §3.4, DD-002).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

_BRANCH_UNSAFE_RE = re.compile(r"[^a-zA-Z0-9._/-]")


def _slug_branch(text: str) -> str:
    """Sanitise *text* for use as a git branch name component."""
    lowered = text.lower().replace(" ", "-")
    return _BRANCH_UNSAFE_RE.sub("-", lowered)


def _run(
    cmd: list[str],
    *,
    cwd: Path | str | None = None,
) -> tuple[int, str, str]:
    """Run a subprocess command; return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(cwd) if cwd else None
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _gh_available(repo_root: Path) -> bool:
    """Return True if the gh CLI is present and a GitHub remote is configured."""
    rc, _, _ = _run(["gh", "--version"])
    if rc != 0:
        return False
    rc, out, _ = _run(["git", "remote", "-v"], cwd=repo_root)
    if rc != 0:
        return False
    return "github.com" in out


def emit_pr(
    title: str,
    body: str,
    finding_id: str,
    *,
    branch: str,
    repo_root: Path | str,
    proposals_dir: Path | str,
    gh_probe: object = None,
    runner: object = None,
) -> str:
    """
    Emit a PR for a single Tier-1 finding.

    When gh + a GitHub remote are available, creates a branch from a stable
    base ref, commits a proposal document, and runs ``gh pr create``,
    returning the PR URL. HEAD is always restored to the original branch
    after emission (whether the PR succeeded or not).

    When unavailable (or after a gh failure), writes a PROPOSED_PR.md
    fallback to ``{proposals_dir}/proposed-pr-{finding_id}.md`` and
    returns the file path.

    Parameters
    ----------
    title:         PR title
    body:          PR body (proposal content)
    finding_id:    finding id — used for the fallback filename
    branch:        git branch name (must be validate_branch-safe)
    repo_root:     repository root for git/gh calls
    proposals_dir: directory for fallback PROPOSED_PR.md files
    gh_probe:      injectable callable(repo_root) -> bool; defaults to _gh_available
    runner:        injectable subprocess runner (cmd, *, cwd) -> (rc, stdout, stderr);
                   defaults to _run; allows tests to exercise the gh path without real git/gh
    """
    repo_root = Path(repo_root)
    proposals_dir = Path(proposals_dir)
    proposals_dir.mkdir(parents=True, exist_ok=True)

    _runner = runner if runner is not None else _run
    probe = gh_probe if gh_probe is not None else _gh_available
    has_gh = probe(repo_root)

    if has_gh:
        # Capture a stable base ref BEFORE creating any branch.
        # Using --abbrev-ref gives the branch name (or "HEAD" in detached state).
        _, base_ref, _ = _runner(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
        base_ref = base_ref.strip() or "HEAD"

        # Write proposal doc (committed to the proposal branch, never to the base)
        proposal_path = proposals_dir / f"proposed-pr-{finding_id}.md"
        proposal_path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")

        try:
            # Create branch FROM the stable base ref (not from any previous proposal branch)
            _runner(["git", "checkout", "-b", branch, base_ref], cwd=repo_root)
            _runner(["git", "add", str(proposal_path)], cwd=repo_root)
            _runner(
                ["git", "commit", "-m", f"tier1-proposal({finding_id}): {title}"],
                cwd=repo_root,
            )
            _runner(["git", "push", "-u", "origin", branch], cwd=repo_root)
            rc, out, _ = _runner(
                ["gh", "pr", "create", "--title", title, "--body", body, "--head", branch],
                cwd=repo_root,
            )
            if rc == 0 and out.strip():
                return out.strip()
        finally:
            # Always restore HEAD to the original branch so subsequent calls
            # start from the same base (prevents branch-stacking across findings)
            _runner(["git", "checkout", base_ref], cwd=repo_root)

    # Fallback: write PROPOSED_PR.md
    fallback_path = proposals_dir / f"proposed-pr-{finding_id}.md"
    fallback_path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    return str(fallback_path)
