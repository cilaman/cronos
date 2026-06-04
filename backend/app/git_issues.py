"""One-way GitHub issue mirror helpers."""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path

from app.git_ops import detect_github_remote

log = logging.getLogger(__name__)

_ISSUE_URL_RE = re.compile(r'https?://[^\s]+/issues/(\d+)')


async def gh_issue_upsert(
    space_dir: Path,
    *,
    title: str,
    body: str,
    labels: list[str],
    issue_number: int | None,
) -> tuple[int | None, str | None]:
    """Create or edit a GitHub issue.

    Returns (issue_number, issue_url) on success, or (None, None) on failure
    (gh absent, non-GitHub remote, subprocess error, timeout).

    When issue_number is None: creates a new issue, parses URL from stdout.
    When issue_number is set: edits the existing issue (title + body only).
    On edit rc!=0 (stale issue_number): returns (None, None) so the caller
    can clear the stored issue_number and fall back to the MD snapshot.
    """
    if not shutil.which("gh"):
        log.info("gh_issue_upsert: 'gh' not found on PATH — skipping")
        return None, None

    # Only proceed for GitHub remotes.
    repo = await detect_github_remote(space_dir)
    if repo is None:
        log.info("gh_issue_upsert: no GitHub remote detected — skipping")
        return None, None

    if issue_number is None:
        # Create a new issue.
        label_args: list[str] = []
        for lbl in labels:
            label_args += ["--label", lbl]
        cmd = ["gh", "issue", "create", *label_args, "--title", title, "--body-file", "-"]
    else:
        # Edit an existing issue (body and title only).
        cmd = ["gh", "issue", "edit", str(issue_number), "--title", title, "--body-file", "-"]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(space_dir),
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(input=body.encode()), timeout=60.0
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            log.warning("gh_issue_upsert: timed out after 60s")
            return None, None

        if proc.returncode != 0:
            err = stderr_b.decode(errors="replace").strip()
            log.warning("gh_issue_upsert: gh exited %d — %s", proc.returncode, err)
            return None, None

        stdout_text = stdout_b.decode(errors="replace")

        if issue_number is not None:
            # Edit succeeded; return the known issue_number, URL not provided by gh.
            return issue_number, None

        # Parse issue number and URL from create stdout (permissive: scan all lines).
        for line in stdout_text.splitlines():
            m = _ISSUE_URL_RE.search(line)
            if m:
                url = m.group(0)
                num = int(m.group(1))
                return num, url

        # URL not found in stdout — gh create succeeded but output was unexpected.
        log.warning(
            "gh_issue_upsert: gh issue create succeeded but no URL in stdout: %r",
            stdout_text[:200],
        )
        return None, None

    except FileNotFoundError:
        log.info("gh_issue_upsert: 'gh' not found — skipping")
        return None, None


async def gh_issue_close(space_dir: Path, issue_number: int) -> bool:
    """Close a GitHub issue.

    Returns True on success, False on any failure (never raises).
    """
    if not shutil.which("gh"):
        log.info("gh_issue_close: 'gh' not found on PATH — skipping")
        return False

    try:
        repo = await detect_github_remote(space_dir)
        if repo is None:
            log.info("gh_issue_close: no GitHub remote detected — skipping")
            return False

        proc = await asyncio.create_subprocess_exec(
            "gh", "issue", "close", str(issue_number),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(space_dir),
        )
        try:
            _stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=60.0
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            log.warning("gh_issue_close: timed out after 60s")
            return False

        if proc.returncode != 0:
            err = stderr_b.decode(errors="replace").strip()
            log.warning("gh_issue_close: gh exited %d — %s", proc.returncode, err)
            return False

        return True

    except Exception as exc:  # noqa: BLE001
        log.warning("gh_issue_close: unexpected error: %s", exc)
        return False
