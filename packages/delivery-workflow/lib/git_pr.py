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
) -> str:
    """
    Emit a PR for a single Tier-1 finding.

    When gh + a GitHub remote are available, creates a branch, commits a
    proposal document, and runs ``gh pr create``, returning the PR URL.

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
    """
    repo_root = Path(repo_root)
    proposals_dir = Path(proposals_dir)
    proposals_dir.mkdir(parents=True, exist_ok=True)

    probe = gh_probe if gh_probe is not None else _gh_available
    has_gh = probe(repo_root)

    if has_gh:
        # Write proposal doc to proposals_dir (it will be committed to the branch)
        proposal_path = proposals_dir / f"proposed-pr-{finding_id}.md"
        proposal_path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")

        try:
            # Create the PR branch off the current HEAD
            _run(["git", "checkout", "-b", branch], cwd=repo_root)
            _run(["git", "add", str(proposal_path)], cwd=repo_root)
            _run(
                ["git", "commit", "-m", f"tier1-proposal({finding_id}): {title}"],
                cwd=repo_root,
            )
            _run(["git", "push", "-u", "origin", branch], cwd=repo_root)
            rc, out, _ = _run(
                ["gh", "pr", "create", "--title", title, "--body", body, "--head", branch],
                cwd=repo_root,
            )
            if rc == 0 and out.strip():
                return out.strip()
        except Exception:
            pass

    # Fallback: write PROPOSED_PR.md
    fallback_path = proposals_dir / f"proposed-pr-{finding_id}.md"
    fallback_path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    return str(fallback_path)
