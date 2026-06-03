from __future__ import annotations

import dataclasses
import logging
from pathlib import Path

from . import git_ops
from .agent import space_dir_for
from .models import Space, Task
from .storage import TaskStore

log = logging.getLogger("cronos.autopilot_pr")

_BRIEF_PREVIEW_LEN = 400


@dataclasses.dataclass
class PostDoneResult:
    committed: bool = False
    pushed: bool = False
    pr_url: str | None = None
    proposed_pr_path: str | None = None
    conflict: bool = False
    conflict_message: str = ""


async def commit_and_open_pr(
    worktree: Path,
    branch: str,
    title: str,
    body: str,
    *,
    space_dir: Path,
) -> PostDoneResult:
    """Commit all changes in *worktree*, push to *branch*, open a PR.

    No rebase step — suitable for fresh branches (e.g. evolve proposals).
    Returns a ``PostDoneResult`` populated with ``committed``/``pushed``/
    ``pr_url``/``proposed_pr_path``.
    """
    sha = await git_ops.commit_all(worktree, title)
    if sha is None:
        log.info("commit_and_open_pr: nothing to commit in %s", worktree)
        return PostDoneResult()

    result = PostDoneResult(committed=True)

    git_ops.validate_branch(branch)
    try:
        await git_ops.push_branch(worktree, branch)
        result.pushed = True
    except Exception:
        log.exception("commit_and_open_pr: push failed for branch %s", branch)
        return result

    base = await git_ops.detect_default_branch(space_dir)
    github_repo = await git_ops.detect_github_remote(space_dir)
    if github_repo:
        pr_url = await git_ops.gh_pr_create(
            worktree, title=title, body=body, base=base, head=branch,
        )
        if pr_url:
            result.pr_url = pr_url
            return result

    # Fallback: write a PROPOSED_PR.md.
    pr_dir = space_dir / ".cronos" / "pull_requests"
    pr_dir.mkdir(parents=True, exist_ok=True)
    pr_file = pr_dir / f"{branch.replace('/', '-')}.md"
    pr_file.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    result.proposed_pr_path = str(pr_file)
    return result


def _build_message(task: Task, space: Space) -> str:
    brief_preview = (task.brief or "").strip()
    if len(brief_preview) > _BRIEF_PREVIEW_LEN:
        brief_preview = brief_preview[:_BRIEF_PREVIEW_LEN].rstrip()
    lines = [
        f"cronos: {task.title}",
        "",
        f"Task: {task.id}",
        "Status: DONE",
        f"Space: {space.name} ({space.id})",
    ]
    if brief_preview:
        lines += ["", brief_preview]
    return "\n".join(lines)


async def run_post_done_flow(
    task: Task,
    space: Space,
    store: TaskStore,
) -> PostDoneResult:
    """Commit, rebase, push, and open a PR for a task that just reached DONE.

    No-ops when autopilot is disabled or the space has no git repo configured.
    Swallow all exceptions at the call site — this function may raise.
    """
    if space.autopilot != "enabled" or space.git_repo_url is None:
        return PostDoneResult()

    space_dir = space_dir_for(space.id)
    worktree = git_ops._worktree_path(space_dir, task.id)
    if not worktree.exists():
        log.info("autopilot_pr: worktree missing for %s — skipping", task.id)
        return PostDoneResult()

    base = await git_ops.detect_default_branch(space_dir, hint=space.git_branch)
    message = _build_message(task, space)

    # Commit
    sha = await git_ops.commit_all(worktree, message)
    if sha is None:
        log.info("autopilot_pr: nothing to commit for %s", task.id)
        return PostDoneResult(committed=False)

    result = PostDoneResult(committed=True)

    # Rebase
    await git_ops.fetch_origin(space_dir)
    rebase = await git_ops.rebase_onto(worktree, base)
    if not rebase.ok:
        files_list = "\n".join(f"  - {f}" for f in rebase.conflicting_files)
        waiting_question = (
            f"Rebase conflict on origin/{base}.\n"
            f"Conflicting files:\n{files_list}\n"
            f"Resolve in {worktree}, push when ready, move task to backlog."
        )
        try:
            await store.autopilot_conflict(task.id, waiting_question)
        except Exception:
            log.exception("autopilot_pr: failed to set conflict state for %s", task.id)
        result.conflict = True
        result.conflict_message = waiting_question
        return result

    # Push
    branch = git_ops._task_branch(task.id)
    await git_ops.push_branch(worktree, branch)
    result.pushed = True

    # PR
    title = f"cronos: {task.title}"
    body = message
    github_repo = await git_ops.detect_github_remote(space_dir)
    if github_repo:
        pr_url = await git_ops.gh_pr_create(
            worktree,
            title=title,
            body=body,
            base=base,
            head=branch,
        )
        if pr_url:
            result.pr_url = pr_url
            try:
                await store.set_pr_refs(task.id, pr_url=pr_url, proposed_pr_path=None)
            except Exception:
                log.exception("autopilot_pr: failed to persist pr_url for %s", task.id)
            return result

    # No GitHub or gh unavailable — write PROPOSED_PR.md
    pr_dir = space_dir / ".cronos" / "pull_requests"
    pr_dir.mkdir(parents=True, exist_ok=True)
    pr_file = pr_dir / f"{task.id}.md"

    try:
        _code, diff_stat, _ = await git_ops._run(
            "diff", "--stat", f"origin/{base}...HEAD", cwd=worktree
        )
    except Exception:
        diff_stat = ""

    pr_content = f"# {title}\n\n{body}\n\n## Diff stat\n\n```\n{diff_stat.strip()}\n```\n"
    pr_file.write_text(pr_content, encoding="utf-8")
    proposed_path = str(pr_file)
    result.proposed_pr_path = proposed_path
    try:
        await store.set_pr_refs(task.id, pr_url=None, proposed_pr_path=proposed_path)
    except Exception:
        log.exception("autopilot_pr: failed to persist proposed_pr_path for %s", task.id)

    return result
