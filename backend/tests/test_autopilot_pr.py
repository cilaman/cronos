"""Tests for app.autopilot_pr — post-DONE commit/rebase/push/PR flow.

Covers:

- No-op when autopilot disabled, no git_repo_url, or no worktree.
- Nothing-to-commit short-circuit.
- Conflict path: rebase fails → store.autopilot_conflict → conflict=True, no push.
- Happy GitHub path: commit → rebase ok → push → gh_pr_create → pr_url set + persisted.
- Non-GitHub path: writes PROPOSED_PR.md and persists proposed_pr_path.
- gh CLI returns None → falls through to proposed_pr_path.
- store.set_pr_refs exception is swallowed (logged but does not propagate).
- _build_message preview truncation invariants.

All git boundary calls (`git_ops.commit_all`, `fetch_origin`, `rebase_onto`,
`push_branch`, `detect_default_branch`, `detect_github_remote`,
`gh_pr_create`, `_run`) are monkey-patched at the seam between
`autopilot_pr` and `git_ops`. The TaskStore is real (uses tmp_spaces_dir).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app import autopilot_pr as autopilot_pr_module
from app.autopilot_pr import PostDoneResult, _build_message, run_post_done_flow
from app.git_ops import RebaseResult
from app.models import Space, Task, TaskState

SPACE_ID = "test-space"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _space(
    *,
    autopilot: str = "enabled",
    git_repo_url: str | None = "https://github.com/foo/bar.git",
    git_branch: str | None = "main",
) -> Space:
    now = datetime.now(tz=UTC)
    return Space(
        id=SPACE_ID,
        name="Test Space",
        color="#15803D",
        icon=None,
        description="",
        created_at=now,
        updated_at=now,
        autopilot=autopilot,
        git_repo_url=git_repo_url,
        git_branch=git_branch,
    )


def _bare_task(task_id: str = "t1", title: str = "Demo task", brief: str = "Brief body") -> Task:
    now = datetime.now(tz=UTC)
    return Task(
        id=task_id,
        space_id=SPACE_ID,
        title=title,
        state=TaskState.DONE,
        created_at=now,
        updated_at=now,
        brief=brief,
    )


@pytest.fixture
def patched_git(monkeypatch, tmp_path):
    """Patch ALL git_ops functions used by autopilot_pr to no-op-by-default.

    Tests override individual seams as needed.
    """
    # Default: every git op succeeds with empty result; worktree exists.
    calls: dict[str, list] = {
        "commit_all": [],
        "fetch_origin": [],
        "rebase_onto": [],
        "push_branch": [],
        "detect_default_branch": [],
        "detect_github_remote": [],
        "gh_pr_create": [],
        "_run": [],
    }

    space_dir = tmp_path / "spaces" / SPACE_ID
    space_dir.mkdir(parents=True, exist_ok=True)
    worktrees_root = space_dir / ".cronos" / "workspaces"
    worktrees_root.mkdir(parents=True, exist_ok=True)

    def ensure_worktree(task_id: str) -> Path:
        wt = worktrees_root / task_id
        wt.mkdir(parents=True, exist_ok=True)
        return wt

    def fake_space_dir_for(space_id: str) -> Path:
        return tmp_path / "spaces" / space_id

    async def fake_commit_all(wt, msg):
        calls["commit_all"].append((wt, msg))
        return "abc123"

    async def fake_fetch_origin(sd):
        calls["fetch_origin"].append(sd)

    async def fake_rebase_onto(wt, onto):
        calls["rebase_onto"].append((wt, onto))
        return RebaseResult(ok=True)

    async def fake_push_branch(wt, branch, **kw):
        calls["push_branch"].append((wt, branch, kw))

    async def fake_detect_default_branch(sd, hint=None):
        calls["detect_default_branch"].append((sd, hint))
        return hint or "main"

    async def fake_detect_github_remote(sd):
        calls["detect_github_remote"].append(sd)
        return "foo/bar"

    async def fake_gh_pr_create(wt, *, title, body, base, head):
        calls["gh_pr_create"].append({"wt": wt, "title": title, "body": body, "base": base, "head": head})
        return "https://github.com/foo/bar/pull/42"

    async def fake_run(*args, cwd=None, **kw):
        calls["_run"].append({"args": args, "cwd": cwd})
        return 0, "stat-output", ""

    monkeypatch.setattr(autopilot_pr_module, "space_dir_for", fake_space_dir_for)
    monkeypatch.setattr(autopilot_pr_module.git_ops, "commit_all", fake_commit_all)
    monkeypatch.setattr(autopilot_pr_module.git_ops, "fetch_origin", fake_fetch_origin)
    monkeypatch.setattr(autopilot_pr_module.git_ops, "rebase_onto", fake_rebase_onto)
    monkeypatch.setattr(autopilot_pr_module.git_ops, "push_branch", fake_push_branch)
    monkeypatch.setattr(autopilot_pr_module.git_ops, "detect_default_branch", fake_detect_default_branch)
    monkeypatch.setattr(autopilot_pr_module.git_ops, "detect_github_remote", fake_detect_github_remote)
    monkeypatch.setattr(autopilot_pr_module.git_ops, "gh_pr_create", fake_gh_pr_create)
    monkeypatch.setattr(autopilot_pr_module.git_ops, "_run", fake_run)

    return {
        "calls": calls,
        "space_dir": space_dir,
        "worktrees_root": worktrees_root,
        "ensure_worktree": ensure_worktree,
        "tmp_path": tmp_path,
    }


# ---------------------------------------------------------------------------
# _build_message
# ---------------------------------------------------------------------------


def test_build_message_includes_task_id_and_status():
    space = _space()
    task = _bare_task(task_id="t-demo", title="My title", brief="Short brief")

    msg = _build_message(task, space)

    assert msg.startswith("cronos: My title\n")
    assert "Task: t-demo" in msg
    assert "Status: DONE" in msg
    assert f"Space: Test Space ({SPACE_ID})" in msg
    assert "Short brief" in msg


def test_build_message_truncates_long_brief_preview():
    space = _space()
    # Use 'Z' since it never appears in the task title or other header text.
    long_brief = "Z" * 600
    task = _bare_task(title="T", brief=long_brief)

    msg = _build_message(task, space)

    # _BRIEF_PREVIEW_LEN is 400; preview should be at most 400 chars long.
    # Only the brief contributes any 'Z' characters.
    assert msg.count("Z") == 400


def test_build_message_empty_brief_omits_preview_block():
    space = _space()
    task = _bare_task(brief="")

    msg = _build_message(task, space)

    # No trailing brief paragraph -> the last line is the Space line.
    assert msg.endswith(f"Space: Test Space ({SPACE_ID})")


# ---------------------------------------------------------------------------
# No-op gates
# ---------------------------------------------------------------------------


async def test_no_op_when_autopilot_disabled(task_store, patched_git):
    """autopilot != 'enabled' → no git calls, default result."""
    space = _space(autopilot="disabled")
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")

    result = await run_post_done_flow(task, space, task_store)

    assert result == PostDoneResult()
    assert patched_git["calls"]["commit_all"] == []
    assert patched_git["calls"]["detect_default_branch"] == []


async def test_no_op_when_autopilot_paused(task_store, patched_git):
    space = _space(autopilot="paused")
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")

    result = await run_post_done_flow(task, space, task_store)

    assert result.committed is False
    assert result.pushed is False
    assert result.pr_url is None
    assert patched_git["calls"]["commit_all"] == []


async def test_no_op_when_git_repo_url_missing(task_store, patched_git):
    space = _space(git_repo_url=None)
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")

    result = await run_post_done_flow(task, space, task_store)

    assert result == PostDoneResult()
    assert patched_git["calls"]["commit_all"] == []


async def test_no_op_when_worktree_missing(task_store, patched_git, monkeypatch, caplog):
    """Worktree dir doesn't exist → INFO log + default result, no git calls."""
    # Repoint worktree to a path that does NOT exist by recreating space_dir
    # without the worktree subdir.
    new_space_dir = patched_git["tmp_path"] / "other-spaces" / SPACE_ID
    new_space_dir.mkdir(parents=True)

    def fake_space_dir_for(space_id: str) -> Path:
        return new_space_dir

    monkeypatch.setattr(autopilot_pr_module, "space_dir_for", fake_space_dir_for)

    space = _space()
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")

    with caplog.at_level(logging.INFO, logger="cronos.autopilot_pr"):
        result = await run_post_done_flow(task, space, task_store)

    assert result == PostDoneResult()
    assert patched_git["calls"]["commit_all"] == []
    # Skipping log was emitted.
    autopilot_pr_records = [
        r for r in caplog.record_tuples if r[0] == "cronos.autopilot_pr"
    ]
    assert any("worktree missing" in r[2] for r in autopilot_pr_records)


# ---------------------------------------------------------------------------
# Commit short-circuit
# ---------------------------------------------------------------------------


async def test_returns_early_when_nothing_to_commit(
    task_store, patched_git, monkeypatch, caplog
):
    """commit_all returns None → return PostDoneResult(committed=False)."""

    async def fake_commit_all(wt, msg):
        patched_git["calls"]["commit_all"].append((wt, msg))
        return None

    monkeypatch.setattr(autopilot_pr_module.git_ops, "commit_all", fake_commit_all)

    space = _space()
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")
    patched_git["ensure_worktree"](task.id)

    with caplog.at_level(logging.INFO, logger="cronos.autopilot_pr"):
        result = await run_post_done_flow(task, space, task_store)

    assert result.committed is False
    assert result.pushed is False
    assert result.pr_url is None
    assert result.proposed_pr_path is None
    # Downstream git ops were never called.
    assert patched_git["calls"]["rebase_onto"] == []
    assert patched_git["calls"]["push_branch"] == []
    assert patched_git["calls"]["gh_pr_create"] == []
    # "nothing to commit" log was emitted.
    assert any(
        "nothing to commit" in r[2]
        for r in caplog.record_tuples
        if r[0] == "cronos.autopilot_pr"
    )


# ---------------------------------------------------------------------------
# Rebase conflict
# ---------------------------------------------------------------------------


async def test_rebase_conflict_moves_task_to_waiting_and_returns_conflict(
    task_store, patched_git, monkeypatch
):
    """Rebase fails → autopilot_conflict called, push/PR skipped, conflict=True."""
    conflict_files = ["src/foo.py", "docs/README.md"]

    async def fake_rebase_onto(wt, onto):
        patched_git["calls"]["rebase_onto"].append((wt, onto))
        return RebaseResult(ok=False, conflicting_files=conflict_files, error="conflict")

    monkeypatch.setattr(autopilot_pr_module.git_ops, "rebase_onto", fake_rebase_onto)

    # Create the task in DONE state so autopilot_conflict's WAITING transition is observable.
    task = await task_store.create(space_id=SPACE_ID, title="Conflicted", brief="b")
    patched_git["ensure_worktree"](task.id)
    await task_store.transition(
        task.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )
    await task_store.finalize_run(
        task.id,
        new_state=TaskState.DONE,
        session_id=None,
        waiting_question=None,
        history_entry="```\ndone\n```",
    )
    task = task_store.get(task.id)

    space = _space()

    result = await run_post_done_flow(task, space, task_store)

    assert result.committed is True
    assert result.conflict is True
    assert result.pushed is False
    assert result.pr_url is None
    assert result.proposed_pr_path is None
    # Conflict message includes both file names.
    assert "src/foo.py" in result.conflict_message
    assert "docs/README.md" in result.conflict_message
    # Downstream push + PR NOT attempted.
    assert patched_git["calls"]["push_branch"] == []
    assert patched_git["calls"]["gh_pr_create"] == []
    # Task moved DONE -> WAITING with the question.
    refreshed = task_store.get(task.id)
    assert refreshed.state == TaskState.WAITING
    assert refreshed.waiting_question is not None
    assert "src/foo.py" in refreshed.waiting_question


async def test_rebase_conflict_swallows_store_autopilot_conflict_exception(
    task_store, patched_git, monkeypatch, caplog
):
    """If store.autopilot_conflict raises, the function still returns conflict=True."""

    async def fake_rebase_onto(wt, onto):
        return RebaseResult(ok=False, conflicting_files=["x.py"], error="")

    monkeypatch.setattr(autopilot_pr_module.git_ops, "rebase_onto", fake_rebase_onto)

    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")
    patched_git["ensure_worktree"](task.id)
    space = _space()

    class _RaisingStore:
        def __init__(self, real):
            self.real = real

        async def autopilot_conflict(self, *a, **kw):
            raise RuntimeError("boom-conflict")

        async def set_pr_refs(self, *a, **kw):
            return await self.real.set_pr_refs(*a, **kw)

    wrapped = _RaisingStore(task_store)

    with caplog.at_level(logging.ERROR, logger="cronos.autopilot_pr"):
        result = await run_post_done_flow(task, space, wrapped)  # type: ignore[arg-type]

    assert result.conflict is True
    # Error was logged.
    assert any(
        r[1] == logging.ERROR and "conflict state" in r[2]
        for r in caplog.record_tuples
        if r[0] == "cronos.autopilot_pr"
    )


# ---------------------------------------------------------------------------
# Happy path — GitHub PR
# ---------------------------------------------------------------------------


async def test_happy_path_github_pr_sets_pr_url_and_persists(
    task_store, patched_git
):
    """commit → rebase ok → push → gh_pr_create returns URL → pr_url set + persisted."""
    task = await task_store.create(space_id=SPACE_ID, title="Demo", brief="brief")
    patched_git["ensure_worktree"](task.id)
    space = _space()

    result = await run_post_done_flow(task, space, task_store)

    assert result.committed is True
    assert result.pushed is True
    assert result.pr_url == "https://github.com/foo/bar/pull/42"
    assert result.proposed_pr_path is None
    assert result.conflict is False
    # gh_pr_create was called with the right kwargs.
    assert len(patched_git["calls"]["gh_pr_create"]) == 1
    gh_call = patched_git["calls"]["gh_pr_create"][0]
    assert gh_call["title"] == "cronos: Demo"
    assert gh_call["base"] == "main"
    assert gh_call["head"] == f"cronos/{task.id}"
    assert "Task: " + task.id in gh_call["body"]
    # Persistence: re-read task from store.
    refreshed = task_store.get(task.id)
    assert refreshed.pr_url == "https://github.com/foo/bar/pull/42"
    assert refreshed.proposed_pr_path is None


async def test_happy_path_passes_git_branch_hint_to_detect_default_branch(
    task_store, patched_git
):
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")
    patched_git["ensure_worktree"](task.id)
    space = _space(git_branch="develop")

    await run_post_done_flow(task, space, task_store)

    # Called with hint='develop'.
    calls = patched_git["calls"]["detect_default_branch"]
    assert len(calls) == 1
    assert calls[0][1] == "develop"


# ---------------------------------------------------------------------------
# Non-GitHub path → proposed_pr_path
# ---------------------------------------------------------------------------


async def test_non_github_remote_writes_proposed_pr_md_and_persists(
    task_store, patched_git, monkeypatch
):
    """No GitHub remote → write {space_dir}/.cronos/pull_requests/{task_id}.md."""

    async def fake_detect_github_remote(sd):
        patched_git["calls"]["detect_github_remote"].append(sd)
        return None  # not GitHub

    monkeypatch.setattr(autopilot_pr_module.git_ops, "detect_github_remote", fake_detect_github_remote)

    task = await task_store.create(space_id=SPACE_ID, title="GitLab task", brief="b")
    patched_git["ensure_worktree"](task.id)
    space = _space()

    result = await run_post_done_flow(task, space, task_store)

    assert result.committed is True
    assert result.pushed is True
    assert result.pr_url is None
    assert result.proposed_pr_path is not None
    # File was actually written.
    pr_file = Path(result.proposed_pr_path)
    assert pr_file.exists()
    content = pr_file.read_text(encoding="utf-8")
    assert "# cronos: GitLab task" in content
    assert "## Diff stat" in content
    # gh_pr_create was NOT called.
    assert patched_git["calls"]["gh_pr_create"] == []
    # Persisted on the task.
    refreshed = task_store.get(task.id)
    assert refreshed.proposed_pr_path == str(pr_file)
    assert refreshed.pr_url is None


async def test_gh_unavailable_returns_none_falls_back_to_proposed_pr_path(
    task_store, patched_git, monkeypatch
):
    """GitHub remote detected but gh_pr_create returns None → proposed_pr_path written."""

    async def fake_gh_pr_create(wt, *, title, body, base, head):
        return None  # gh not on PATH or auth failed

    monkeypatch.setattr(autopilot_pr_module.git_ops, "gh_pr_create", fake_gh_pr_create)

    task = await task_store.create(space_id=SPACE_ID, title="gh-down", brief="b")
    patched_git["ensure_worktree"](task.id)
    space = _space()

    result = await run_post_done_flow(task, space, task_store)

    assert result.pushed is True
    assert result.pr_url is None
    assert result.proposed_pr_path is not None
    assert Path(result.proposed_pr_path).exists()


async def test_proposed_pr_path_tolerates_diff_stat_exception(
    task_store, patched_git, monkeypatch
):
    """When `git diff --stat ...` raises, the .md file is still written with empty stat."""

    async def fake_detect_github_remote(sd):
        return None

    async def fake_run(*args, cwd=None, **kw):
        raise RuntimeError("git crashed")

    monkeypatch.setattr(autopilot_pr_module.git_ops, "detect_github_remote", fake_detect_github_remote)
    monkeypatch.setattr(autopilot_pr_module.git_ops, "_run", fake_run)

    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")
    patched_git["ensure_worktree"](task.id)
    space = _space()

    result = await run_post_done_flow(task, space, task_store)

    assert result.proposed_pr_path is not None
    content = Path(result.proposed_pr_path).read_text(encoding="utf-8")
    # Diff stat block exists but is empty.
    assert "## Diff stat" in content
    assert "```\n\n```" in content


# ---------------------------------------------------------------------------
# set_pr_refs exception is swallowed
# ---------------------------------------------------------------------------


async def test_set_pr_refs_exception_in_github_path_is_swallowed_and_logged(
    task_store, patched_git, caplog
):
    """If store.set_pr_refs raises (GitHub path), the function still returns result with pr_url."""
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")
    patched_git["ensure_worktree"](task.id)
    space = _space()

    class _RaisingStore:
        def __init__(self, real):
            self.real = real

        async def autopilot_conflict(self, *a, **kw):
            return await self.real.autopilot_conflict(*a, **kw)

        async def set_pr_refs(self, *a, **kw):
            raise RuntimeError("disk full")

    wrapped = _RaisingStore(task_store)

    with caplog.at_level(logging.ERROR, logger="cronos.autopilot_pr"):
        result = await run_post_done_flow(task, space, wrapped)  # type: ignore[arg-type]

    assert result.pr_url == "https://github.com/foo/bar/pull/42"
    # Logged at ERROR.
    error_records = [
        r for r in caplog.record_tuples
        if r[0] == "cronos.autopilot_pr" and r[1] == logging.ERROR
    ]
    assert any("pr_url" in r[2] for r in error_records)


async def test_set_pr_refs_exception_in_proposed_path_is_swallowed_and_logged(
    task_store, patched_git, monkeypatch, caplog
):
    """If store.set_pr_refs raises on the proposed-PR path, the function still returns proposed_pr_path."""

    async def fake_detect_github_remote(sd):
        return None

    monkeypatch.setattr(autopilot_pr_module.git_ops, "detect_github_remote", fake_detect_github_remote)

    task = await task_store.create(space_id=SPACE_ID, title="t", brief="b")
    patched_git["ensure_worktree"](task.id)
    space = _space()

    class _RaisingStore:
        def __init__(self, real):
            self.real = real

        async def autopilot_conflict(self, *a, **kw):
            return await self.real.autopilot_conflict(*a, **kw)

        async def set_pr_refs(self, *a, **kw):
            raise RuntimeError("disk full")

    wrapped = _RaisingStore(task_store)

    with caplog.at_level(logging.ERROR, logger="cronos.autopilot_pr"):
        result = await run_post_done_flow(task, space, wrapped)  # type: ignore[arg-type]

    assert result.proposed_pr_path is not None
    assert Path(result.proposed_pr_path).exists()
    error_records = [
        r for r in caplog.record_tuples
        if r[0] == "cronos.autopilot_pr" and r[1] == logging.ERROR
    ]
    assert any("proposed_pr_path" in r[2] for r in error_records)


# ---------------------------------------------------------------------------
# PostDoneResult defaults
# ---------------------------------------------------------------------------


def test_post_done_result_defaults_are_clean():
    """Lock the dataclass defaults: no false-positive `committed=True` etc."""
    r = PostDoneResult()
    assert r.committed is False
    assert r.pushed is False
    assert r.pr_url is None
    assert r.proposed_pr_path is None
    assert r.conflict is False
    assert r.conflict_message == ""
