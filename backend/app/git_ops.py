from __future__ import annotations

import asyncio
import asyncio.subprocess
import base64
import dataclasses
import logging
import os
import re
import shutil
from pathlib import Path

log = logging.getLogger("cronos.git")

# Branch namespace for per-task worktrees. `cronos/{task_id}` keeps them
# easy to list (`git branch --list 'cronos/*'`) and unlikely to collide
# with user branches.
TASK_BRANCH_PREFIX = "cronos/"

# Conservative validation. We pass these to `git`, so anything that could
# look like a flag must be rejected. URLs and branch names are unbounded
# in git but we cap them to keep error messages sane.
_URL_RE = re.compile(r"^[A-Za-z0-9_./:@+~\-]+$")
_BRANCH_RE = re.compile(r"^(?!-)[A-Za-z0-9._/\-]{1,200}$")


class GitError(Exception):
    """Raised when a git command fails or input is invalid."""


def validate_repo_url(url: str) -> None:
    if not url or len(url) > 2048 or not _URL_RE.match(url):
        raise GitError(f"Invalid repo URL: {url!r}")


def validate_branch(name: str) -> None:
    if not _BRANCH_RE.match(name) or ".." in name or name.endswith("/") or name.endswith(".lock"):
        raise GitError(f"Invalid branch name: {name!r}")


async def _run(
    *args: str,
    cwd: Path | None = None,
    timeout: float = 300.0,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run a git command and capture stdout/stderr.

    Returns (exit_code, stdout, stderr). Does not raise on non-zero exits;
    callers decide. Times out at 300s by default (clones can take a while).
    """
    log.info("git %s%s", " ".join(args), f" (cwd={cwd})" if cwd else "")
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise GitError(f"git {' '.join(args)} timed out after {timeout}s") from None
    return proc.returncode or 0, stdout_b.decode(errors="replace"), stderr_b.decode(errors="replace")


async def _run_or_raise(
    *args: str,
    cwd: Path | None = None,
    timeout: float = 300.0,
    env: dict[str, str] | None = None,
) -> str:
    code, out, err = await _run(*args, cwd=cwd, timeout=timeout, env=env)
    if code != 0:
        raise GitError(f"git {' '.join(args)} failed (exit {code}): {err.strip() or out.strip()}")
    return out


# ---------- credentials ----------

# Single-user pragmatic auth: a Personal Access Token in the environment is
# injected into git's `http.extraHeader` via `GIT_CONFIG_*` env vars (not
# subprocess args — keeps the token out of `ps`). The token applies only to
# the specific git invocation; it is NOT persisted into the cloned repo's
# config and is never visible to the agent subprocess that later runs in
# the worktree.
#
# When Cronos grows multi-user this should be replaced by a per-space (or
# per-user) credential lookup — `_clone_env(token=...)` is the only seam.
_GIT_TOKEN_ENV = "CRONOS_GIT_TOKEN"


def _auth_env(repo_url: str) -> dict[str, str] | None:
    """Build a subprocess env that injects a PAT for HTTPS git operations.

    Returns None when no token is configured or the URL isn't HTTPS (SSH
    URLs are authenticated via ssh-agent / mounted keys, not PATs).
    """
    token = os.environ.get(_GIT_TOKEN_ENV)
    if not token or not repo_url.startswith(("https://", "http://")):
        return None
    # `Authorization: Basic <base64(x-access-token:TOKEN)>` is the form
    # GitHub Actions and GitHub Apps use; it also works for fine-grained
    # PATs on github.com and most GitLab/Bitbucket setups.
    auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    env = os.environ.copy()
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
    env["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {auth}"
    # Stop git from prompting if the token is wrong — fail fast instead.
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    return env


def _clone_env(repo_url: str) -> dict[str, str] | None:
    """Alias kept for backward-compat callers; delegates to _auth_env."""
    return _auth_env(repo_url)


# ---------- repo linking ----------


def _is_empty_or_cronos_only(space_dir: Path) -> bool:
    """A space dir is "clone-able" if it's empty or contains only `.cronos/`."""
    if not space_dir.is_dir():
        return False
    for entry in space_dir.iterdir():
        if entry.name != ".cronos":
            return False
    return True


async def clone_into_space(space_dir: Path, repo_url: str, branch: str) -> None:
    """Clone `repo_url` at `branch` into `space_dir`.

    `space_dir` must be empty (or contain only `.cronos/`, which is moved
    aside and merged back after clone so we don't lose task data when
    linking an existing space).
    """
    validate_repo_url(repo_url)
    validate_branch(branch)
    if not _is_empty_or_cronos_only(space_dir):
        raise GitError(
            f"Cannot clone into {space_dir}: directory is not empty "
            "(must contain only .cronos/ or be empty)"
        )

    # Move `.cronos/` aside if present — git refuses to clone into a non-empty dir.
    cronos_dir = space_dir / ".cronos"
    parking = space_dir.parent / f".__cronos_parked_{space_dir.name}"
    parked = False
    if cronos_dir.exists():
        if parking.exists():
            shutil.rmtree(parking)
        cronos_dir.rename(parking)
        parked = True

    try:
        # Need to clone into the dir itself, but git wants either an empty
        # dir or a non-existent one. Workaround: clone to a sibling temp
        # then move contents over.
        scratch = space_dir.parent / f".__cronos_clone_{space_dir.name}"
        if scratch.exists():
            shutil.rmtree(scratch)
        try:
            await _run_or_raise(
                "clone", "--branch", branch, "--single-branch", repo_url, str(scratch),
                env=_auth_env(repo_url),
            )
            # Move every entry (including dotfiles) out of scratch into space_dir.
            for entry in scratch.iterdir():
                dest = space_dir / entry.name
                if dest.exists():
                    raise GitError(f"Collision while moving cloned files: {dest}")
                entry.rename(dest)
        finally:
            if scratch.exists():
                shutil.rmtree(scratch, ignore_errors=True)
    except Exception:
        # On any failure, restore the parked .cronos/ so we don't lose data.
        if parked and parking.exists() and not cronos_dir.exists():
            parking.rename(cronos_dir)
        raise

    if parked:
        # Restore .cronos/ into the freshly cloned working tree.
        parking.rename(cronos_dir)


async def unlink_repo(space_dir: Path) -> None:
    """Remove the git checkout from `space_dir`, preserving `.cronos/`.

    Deletes every entry in space_dir except `.cronos/`. Worktrees on
    `cronos/*` branches are pruned implicitly because `.git/` is gone.
    """
    if not space_dir.is_dir():
        return
    for entry in space_dir.iterdir():
        if entry.name == ".cronos":
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            try:
                entry.unlink()
            except OSError:
                pass


# ---------- worktrees ----------


def _task_branch(task_id: str) -> str:
    return f"{TASK_BRANCH_PREFIX}{task_id}"


def _worktree_path(space_dir: Path, task_id: str) -> Path:
    return space_dir / ".cronos" / "workspaces" / task_id


async def ensure_task_worktree(
    space_dir: Path,
    task_id: str,
    base_branch: str,
) -> Path:
    """Idempotently create a git worktree for `task_id` on a new branch.

    Returns the worktree path. If the worktree already exists at the expected
    path we just return it. If the branch already exists, we reuse it.
    """
    validate_branch(base_branch)
    wt_path = _worktree_path(space_dir, task_id)
    if wt_path.exists() and (wt_path / ".git").exists():
        return wt_path

    wt_path.parent.mkdir(parents=True, exist_ok=True)

    branch = _task_branch(task_id)
    # Does the branch already exist?
    code, _out, _err = await _run("rev-parse", "--verify", branch, cwd=space_dir)
    if code == 0:
        await _run_or_raise("worktree", "add", str(wt_path), branch, cwd=space_dir)
    else:
        await _run_or_raise(
            "worktree", "add", "-b", branch, str(wt_path), base_branch, cwd=space_dir
        )
    return wt_path


async def remove_task_worktree(space_dir: Path, task_id: str) -> None:
    """Remove the task's worktree, keeping its branch around for recovery."""
    wt_path = _worktree_path(space_dir, task_id)
    if not wt_path.exists():
        return
    # `worktree remove --force` deletes the working tree even if it has
    # uncommitted changes — appropriate for a soft-delete since the branch
    # still has the committed history.
    code, _out, err = await _run(
        "worktree", "remove", "--force", str(wt_path), cwd=space_dir
    )
    if code != 0:
        log.warning(
            "git worktree remove failed for %s: %s — falling back to rmtree",
            task_id, err.strip(),
        )
        shutil.rmtree(wt_path, ignore_errors=True)
        # Tell git to forget the stale worktree entry.
        await _run("worktree", "prune", cwd=space_dir)


# ---------- gitignore ----------


def apply_gitignore(space_dir: Path, share_cronos: bool) -> None:
    """Ensure `.cronos/` is in `.gitignore` when `share_cronos` is False.

    Idempotent: appends only when the entry is missing. When sharing, this
    function is a no-op (we don't strip existing rules — that's the user's
    repo).
    """
    if share_cronos:
        return
    gitignore = space_dir / ".gitignore"
    needle = ".cronos/"
    existing = ""
    if gitignore.exists():
        existing = gitignore.read_text(encoding="utf-8")
        for line in existing.splitlines():
            if line.strip().rstrip("/") == ".cronos":
                return  # already ignored
    sep = "" if existing.endswith("\n") or not existing else "\n"
    addition = f"{sep}# Cronos task data — see https://github.com/anthropics/cronos\n{needle}\n"
    gitignore.write_text(existing + addition, encoding="utf-8")


# ---------- commit / fetch / rebase / push / PR ----------


async def has_changes(worktree: Path) -> bool:
    """Return True when the worktree has uncommitted changes."""
    code, out, _ = await _run("status", "--porcelain", cwd=worktree)
    return code == 0 and bool(out.strip())


async def commit_all(worktree: Path, message: str) -> str | None:
    """Stage everything and commit. Returns the new SHA, or None when clean."""
    if not await has_changes(worktree):
        return None
    await _run_or_raise("add", "-A", cwd=worktree)
    await _run_or_raise("commit", "-m", message, cwd=worktree)
    sha = await _run_or_raise("rev-parse", "HEAD", cwd=worktree)
    return sha.strip()


async def _space_remote_url(space_dir: Path) -> str:
    """Return the origin remote URL, or empty string on error."""
    code, out, _ = await _run("remote", "get-url", "origin", cwd=space_dir)
    return out.strip() if code == 0 else ""


async def fetch_origin(space_dir: Path) -> None:
    """Fetch and prune from origin, injecting credentials when available."""
    url = await _space_remote_url(space_dir)
    env = _auth_env(url) if url else None
    await _run_or_raise("fetch", "origin", "--prune", cwd=space_dir, env=env)


async def detect_default_branch(space_dir: Path, hint: str | None = None) -> str:
    """Return the default remote branch name.

    Resolution order: explicit hint → symbolic-ref HEAD → 'main' → 'master'.
    """
    if hint:
        return hint
    code, out, _ = await _run(
        "symbolic-ref", "refs/remotes/origin/HEAD", cwd=space_dir
    )
    if code == 0 and out.strip():
        # refs/remotes/origin/HEAD → refs/remotes/origin/<branch>
        return out.strip().split("/")[-1]
    # Check whether common defaults exist on the remote.
    for candidate in ("main", "master"):
        code, _, _ = await _run(
            "rev-parse", "--verify", f"origin/{candidate}", cwd=space_dir
        )
        if code == 0:
            return candidate
    return "main"


@dataclasses.dataclass
class RebaseResult:
    ok: bool
    conflicting_files: list[str] = dataclasses.field(default_factory=list)
    error: str = ""


async def rebase_onto(worktree: Path, onto: str) -> RebaseResult:
    """Rebase the worktree branch onto origin/<onto>.

    On conflict, parses conflicting files, aborts the rebase so the worktree
    is left clean, and returns ok=False with the file list.
    """
    validate_branch(onto)
    code, out, err = await _run("rebase", f"origin/{onto}", cwd=worktree)
    if code == 0:
        return RebaseResult(ok=True)

    # Collect conflicting files from porcelain status.
    _code, status_out, _ = await _run("status", "--porcelain", cwd=worktree)
    conflicting: list[str] = []
    for line in status_out.splitlines():
        xy = line[:2]
        if any(c in xy for c in ("U", "A", "D")):
            conflicting.append(line[3:].strip())

    # Always abort to leave the worktree clean.
    await _run("rebase", "--abort", cwd=worktree)

    combined = err.strip() or out.strip()
    return RebaseResult(ok=False, conflicting_files=conflicting, error=combined)


async def push_branch(
    worktree: Path,
    branch: str,
    *,
    force_with_lease: bool = False,
) -> None:
    """Push `branch` to origin from `worktree`."""
    validate_branch(branch)
    url = await _space_remote_url(worktree)
    env = _auth_env(url) if url else None
    extra = ["--force-with-lease"] if force_with_lease else []
    await _run_or_raise("push", "origin", branch, *extra, cwd=worktree, env=env)


_GITHUB_RE = re.compile(
    r"github\.com[/:](?P<owner>[^/]+)/(?P<repo>[^/\s]+?)(?:\.git)?$"
)


async def detect_github_remote(space_dir: Path) -> str | None:
    """Return 'owner/repo' if origin points to GitHub, else None."""
    url = await _space_remote_url(space_dir)
    if not url:
        return None
    m = _GITHUB_RE.search(url)
    if m:
        return f"{m.group('owner')}/{m.group('repo')}"
    return None


async def gh_pr_create(
    worktree: Path,
    *,
    title: str,
    body: str,
    base: str,
    head: str,
) -> str | None:
    """Create a GitHub PR via the `gh` CLI. Returns the PR URL or None.

    Returns None (with a log message) when `gh` is absent or not authenticated.
    """
    if not shutil.which("gh"):
        log.info("gh_pr_create: 'gh' not found on PATH — skipping PR creation")
        return None

    try:
        proc = await asyncio.create_subprocess_exec(
            "gh", "pr", "create",
            "--base", base,
            "--head", head,
            "--title", title,
            "--body-file", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(worktree),
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(input=body.encode()), timeout=60.0
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            log.warning("gh_pr_create: timed out after 60s")
            return None

        if proc.returncode != 0:
            err = stderr_b.decode(errors="replace").strip()
            log.warning("gh_pr_create: gh exited %d — %s", proc.returncode, err)
            return None

        url = stdout_b.decode(errors="replace").strip()
        return url or None
    except FileNotFoundError:
        log.info("gh_pr_create: 'gh' not found — skipping PR creation")
        return None
