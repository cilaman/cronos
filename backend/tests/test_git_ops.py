"""Tests for app.git_ops new commit/rebase/push/PR helpers (arc-4 task 2).

Real `git init` fixtures only — no network access, git itself is never mocked.
Covers:
- has_changes / commit_all
- fetch_origin (via a local bare-repo "remote")
- detect_default_branch (hint, symbolic-ref, fallback)
- RebaseResult + rebase_onto (happy path AND deliberate conflict)
- push_branch (to a local bare-repo remote, both plain and --force-with-lease)
- detect_github_remote (HTTPS + SSH GitHub URLs, plus negative GitLab)
- gh_pr_create (gh-missing path via mocked shutil.which)
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

import pytest

from app.git_ops import (
    RebaseResult,
    commit_all,
    detect_default_branch,
    detect_github_remote,
    fetch_origin,
    gh_pr_create,
    has_changes,
    push_branch,
    rebase_onto,
)


# ---------------------------------------------------------------------------
# helpers / fixtures
# ---------------------------------------------------------------------------


def _run(*args: str, cwd: Path, env: dict | None = None) -> str:
    """Synchronous git helper for test setup (NOT testing the SUT)."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout


def _git_identity_env() -> dict:
    """Env with deterministic git author/committer so commits work in CI sandboxes."""
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Cronos Test"
    env["GIT_AUTHOR_EMAIL"] = "test@cronos.local"
    env["GIT_COMMITTER_NAME"] = "Cronos Test"
    env["GIT_COMMITTER_EMAIL"] = "test@cronos.local"
    return env


@pytest.fixture
def git_env() -> dict:
    return _git_identity_env()


@pytest.fixture
def empty_repo(tmp_path: Path, git_env: dict) -> Path:
    """A fresh repo with one initial commit on `main`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run("init", "-b", "main", cwd=repo, env=git_env)
    _run("config", "user.email", "test@cronos.local", cwd=repo, env=git_env)
    _run("config", "user.name", "Cronos Test", cwd=repo, env=git_env)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _run("add", "README.md", cwd=repo, env=git_env)
    _run("commit", "-m", "initial", cwd=repo, env=git_env)
    return repo


@pytest.fixture
def bare_remote(tmp_path: Path, git_env: dict) -> Path:
    """A bare repo that acts as 'origin' for tests that need a push target."""
    bare = tmp_path / "remote.git"
    bare.mkdir()
    _run("init", "--bare", "-b", "main", cwd=bare, env=git_env)
    return bare


@pytest.fixture
def repo_with_remote(empty_repo: Path, bare_remote: Path, git_env: dict) -> Path:
    """`empty_repo` with `origin` pointing at the bare remote and `main` pushed."""
    _run("remote", "add", "origin", str(bare_remote), cwd=empty_repo, env=git_env)
    _run("push", "-u", "origin", "main", cwd=empty_repo, env=git_env)
    return empty_repo


# ---------------------------------------------------------------------------
# has_changes
# ---------------------------------------------------------------------------


async def test_has_changes_false_on_clean_worktree(empty_repo: Path):
    # Arrange: fresh repo with no edits.

    # Act
    result = await has_changes(empty_repo)

    # Assert
    assert result is False


async def test_has_changes_true_on_modified_file(empty_repo: Path):
    # Arrange
    (empty_repo / "README.md").write_text("changed\n", encoding="utf-8")

    # Act
    result = await has_changes(empty_repo)

    # Assert
    assert result is True


async def test_has_changes_true_on_untracked_file(empty_repo: Path):
    # Arrange
    (empty_repo / "NEW.txt").write_text("untracked\n", encoding="utf-8")

    # Act
    result = await has_changes(empty_repo)

    # Assert
    assert result is True


# ---------------------------------------------------------------------------
# commit_all
# ---------------------------------------------------------------------------


async def test_commit_all_returns_none_on_clean_worktree(empty_repo: Path):
    # Arrange: nothing to commit.
    head_before = _run("rev-parse", "HEAD", cwd=empty_repo).strip()

    # Act
    sha = await commit_all(empty_repo, "no-op")

    # Assert: returned None AND HEAD did not advance.
    assert sha is None
    head_after = _run("rev-parse", "HEAD", cwd=empty_repo).strip()
    assert head_before == head_after


async def test_commit_all_returns_sha_after_changes(empty_repo: Path, git_env: dict):
    # Arrange — configure committer on the per-repo level so commit_all picks it up.
    (empty_repo / "feature.txt").write_text("body\n", encoding="utf-8")

    # Act
    sha = await commit_all(empty_repo, "add feature")

    # Assert: returned sha matches HEAD and the commit message is recorded.
    assert sha is not None
    assert len(sha) == 40  # full SHA-1 hex
    head = _run("rev-parse", "HEAD", cwd=empty_repo).strip()
    assert sha == head
    msg = _run("log", "-1", "--pretty=%s", cwd=empty_repo).strip()
    assert msg == "add feature"


async def test_commit_all_stages_untracked_and_modified(empty_repo: Path):
    # Arrange — both an untracked file and a modified existing file.
    (empty_repo / "README.md").write_text("changed\n", encoding="utf-8")
    (empty_repo / "added.txt").write_text("new\n", encoding="utf-8")

    # Act
    sha = await commit_all(empty_repo, "mixed")

    # Assert — after commit the worktree is clean and both files are in the tree.
    assert sha is not None
    assert await has_changes(empty_repo) is False
    files = _run("ls-tree", "-r", "--name-only", "HEAD", cwd=empty_repo).split()
    assert "added.txt" in files
    assert "README.md" in files


# ---------------------------------------------------------------------------
# fetch_origin
# ---------------------------------------------------------------------------


async def test_fetch_origin_updates_remote_tracking_ref(
    repo_with_remote: Path, bare_remote: Path, tmp_path: Path, git_env: dict
):
    """Push a new branch from a second clone, then fetch from the first must see it."""
    # Arrange: clone the bare remote into a sibling worktree and push a new branch.
    other = tmp_path / "other"
    _run("clone", str(bare_remote), str(other), cwd=tmp_path, env=git_env)
    _run("config", "user.email", "other@cronos.local", cwd=other, env=git_env)
    _run("config", "user.name", "Other Dev", cwd=other, env=git_env)
    _run("checkout", "-b", "side", cwd=other, env=git_env)
    (other / "side.txt").write_text("from other\n", encoding="utf-8")
    _run("add", "side.txt", cwd=other, env=git_env)
    _run("commit", "-m", "side commit", cwd=other, env=git_env)
    _run("push", "origin", "side", cwd=other, env=git_env)

    # Sanity: before fetch, repo_with_remote knows nothing about origin/side.
    pre = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/side"],
        cwd=str(repo_with_remote), capture_output=True, text=True,
    )
    assert pre.returncode != 0

    # Act
    await fetch_origin(repo_with_remote)

    # Assert: origin/side now resolves.
    post = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/side"],
        cwd=str(repo_with_remote), capture_output=True, text=True,
    )
    assert post.returncode == 0


async def test_fetch_origin_prunes_deleted_branch(
    repo_with_remote: Path, bare_remote: Path, tmp_path: Path, git_env: dict
):
    """A remote branch deleted upstream must vanish after fetch (--prune)."""
    # Arrange: push a branch, fetch it, then delete it on the remote.
    other = tmp_path / "other2"
    _run("clone", str(bare_remote), str(other), cwd=tmp_path, env=git_env)
    _run("checkout", "-b", "ephemeral", cwd=other, env=git_env)
    (other / "x.txt").write_text("x\n", encoding="utf-8")
    _run("add", "x.txt", cwd=other, env=git_env)
    _run(
        "-c", "user.email=o@c.l", "-c", "user.name=O",
        "commit", "-m", "x", cwd=other, env=git_env,
    )
    _run("push", "origin", "ephemeral", cwd=other, env=git_env)
    await fetch_origin(repo_with_remote)
    assert subprocess.run(
        ["git", "rev-parse", "--verify", "origin/ephemeral"],
        cwd=str(repo_with_remote), capture_output=True,
    ).returncode == 0

    # Delete on remote and re-fetch.
    _run("push", "origin", "--delete", "ephemeral", cwd=other, env=git_env)
    await fetch_origin(repo_with_remote)

    # Assert: --prune removed the stale tracking ref.
    assert subprocess.run(
        ["git", "rev-parse", "--verify", "origin/ephemeral"],
        cwd=str(repo_with_remote), capture_output=True,
    ).returncode != 0


# ---------------------------------------------------------------------------
# detect_default_branch
# ---------------------------------------------------------------------------


async def test_detect_default_branch_uses_hint_short_circuit(empty_repo: Path):
    # Arrange: no remote at all — hint must short-circuit before we even try.

    # Act
    branch = await detect_default_branch(empty_repo, hint="develop")

    # Assert
    assert branch == "develop"


async def test_detect_default_branch_reads_symbolic_ref(
    repo_with_remote: Path, git_env: dict
):
    # Arrange: explicitly set origin/HEAD -> main (clone wouldn't have done it
    # for our local bare remote in all git versions).
    _run("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main",
         cwd=repo_with_remote, env=git_env)

    # Act
    branch = await detect_default_branch(repo_with_remote)

    # Assert
    assert branch == "main"


async def test_detect_default_branch_fallback_to_main_when_no_remote(
    empty_repo: Path,
):
    # Arrange: no origin configured at all.

    # Act
    branch = await detect_default_branch(empty_repo)

    # Assert: the documented last-resort default.
    assert branch == "main"


async def test_detect_default_branch_prefers_master_when_only_master_on_origin(
    tmp_path: Path, git_env: dict
):
    """When symbolic-ref is absent, the helper probes origin/main then origin/master."""
    # Arrange: build a bare remote with only `master` as a real ref.
    bare = tmp_path / "master_remote.git"
    bare.mkdir()
    _run("init", "--bare", "-b", "master", cwd=bare, env=git_env)
    seed = tmp_path / "seed"
    seed.mkdir()
    _run("init", "-b", "master", cwd=seed, env=git_env)
    _run("config", "user.email", "t@c.l", cwd=seed, env=git_env)
    _run("config", "user.name", "T", cwd=seed, env=git_env)
    (seed / "f").write_text("x", encoding="utf-8")
    _run("add", "f", cwd=seed, env=git_env)
    _run("commit", "-m", "init", cwd=seed, env=git_env)
    _run("remote", "add", "origin", str(bare), cwd=seed, env=git_env)
    _run("push", "-u", "origin", "master", cwd=seed, env=git_env)
    # Wipe any symbolic-ref so the function falls through to the probe loop.
    sym = seed / ".git" / "refs" / "remotes" / "origin" / "HEAD"
    if sym.exists():
        sym.unlink()

    # Act
    branch = await detect_default_branch(seed)

    # Assert
    assert branch == "master"


# ---------------------------------------------------------------------------
# RebaseResult dataclass
# ---------------------------------------------------------------------------


def test_rebase_result_defaults():
    # Arrange / Act
    result = RebaseResult(ok=True)

    # Assert: factory defaults must be a fresh, empty list (not shared) and "".
    assert result.ok is True
    assert result.conflicting_files == []
    assert result.error == ""
    # Each instance gets its own list.
    other = RebaseResult(ok=False)
    other.conflicting_files.append("x")
    assert result.conflicting_files == []


def test_rebase_result_carries_fields():
    # Arrange / Act
    result = RebaseResult(ok=False, conflicting_files=["a.txt"], error="boom")

    # Assert
    assert result.ok is False
    assert result.conflicting_files == ["a.txt"]
    assert result.error == "boom"


# ---------------------------------------------------------------------------
# rebase_onto
# ---------------------------------------------------------------------------


async def test_rebase_onto_happy_path_returns_ok_true(
    repo_with_remote: Path, bare_remote: Path, tmp_path: Path, git_env: dict
):
    """When there's no conflict, rebase succeeds and HEAD advances cleanly."""
    # Arrange: advance origin/main via a second clone, then create a side
    # branch on top of the old main and rebase it.
    other = tmp_path / "advancer"
    _run("clone", str(bare_remote), str(other), cwd=tmp_path, env=git_env)
    (other / "new_on_main.txt").write_text("upstream\n", encoding="utf-8")
    _run("add", "new_on_main.txt", cwd=other, env=git_env)
    _run("-c", "user.email=a@c.l", "-c", "user.name=A",
         "commit", "-m", "upstream change", cwd=other, env=git_env)
    _run("push", "origin", "main", cwd=other, env=git_env)

    _run("checkout", "-b", "feature", cwd=repo_with_remote, env=git_env)
    (repo_with_remote / "feature.txt").write_text("local\n", encoding="utf-8")
    _run("add", "feature.txt", cwd=repo_with_remote, env=git_env)
    _run("commit", "-m", "feature work", cwd=repo_with_remote, env=git_env)
    await fetch_origin(repo_with_remote)

    # Act
    result = await rebase_onto(repo_with_remote, "main")

    # Assert
    assert result.ok is True
    assert result.conflicting_files == []
    assert result.error == ""
    # Both upstream's file and the feature file are present.
    files = _run("ls-tree", "-r", "--name-only", "HEAD", cwd=repo_with_remote).split()
    assert "new_on_main.txt" in files
    assert "feature.txt" in files


async def test_rebase_onto_conflict_returns_files_and_cleans_worktree(
    repo_with_remote: Path, bare_remote: Path, tmp_path: Path, git_env: dict
):
    """Deliberate conflict on the same file → ok=False + files populated + clean tree."""
    # Arrange: push a conflicting change to origin/main from a sibling clone.
    other = tmp_path / "conflict_other"
    _run("clone", str(bare_remote), str(other), cwd=tmp_path, env=git_env)
    (other / "shared.txt").write_text("upstream version\n", encoding="utf-8")
    _run("add", "shared.txt", cwd=other, env=git_env)
    _run("-c", "user.email=a@c.l", "-c", "user.name=A",
         "commit", "-m", "upstream shared", cwd=other, env=git_env)
    _run("push", "origin", "main", cwd=other, env=git_env)

    # In our repo, branch from old main and make a conflicting edit to shared.txt.
    _run("checkout", "-b", "feature-conflict", cwd=repo_with_remote, env=git_env)
    (repo_with_remote / "shared.txt").write_text("local version\n", encoding="utf-8")
    _run("add", "shared.txt", cwd=repo_with_remote, env=git_env)
    _run("commit", "-m", "local shared", cwd=repo_with_remote, env=git_env)
    await fetch_origin(repo_with_remote)

    # Act
    result = await rebase_onto(repo_with_remote, "main")

    # Assert
    assert result.ok is False
    assert "shared.txt" in result.conflicting_files
    assert result.error  # some non-empty diagnostic message
    # Most critical: the rebase was aborted so no .git/rebase-merge/ remains.
    assert not (repo_with_remote / ".git" / "rebase-merge").exists()
    assert not (repo_with_remote / ".git" / "rebase-apply").exists()
    # And the worktree must be clean (status --porcelain empty).
    assert await has_changes(repo_with_remote) is False


async def test_rebase_onto_rejects_invalid_branch_name(empty_repo: Path):
    """validate_branch must short-circuit before any git call."""
    from app.git_ops import GitError

    # Act / Assert
    with pytest.raises(GitError, match="Invalid branch name"):
        await rebase_onto(empty_repo, "-rm-rf")


# ---------------------------------------------------------------------------
# push_branch
# ---------------------------------------------------------------------------


async def test_push_branch_pushes_local_branch_to_remote(
    repo_with_remote: Path, bare_remote: Path, git_env: dict
):
    # Arrange: create a local branch with a unique commit.
    _run("checkout", "-b", "deploy", cwd=repo_with_remote, env=git_env)
    (repo_with_remote / "deploy.txt").write_text("ship\n", encoding="utf-8")
    _run("add", "deploy.txt", cwd=repo_with_remote, env=git_env)
    _run("commit", "-m", "deploy", cwd=repo_with_remote, env=git_env)
    local_sha = _run("rev-parse", "HEAD", cwd=repo_with_remote).strip()

    # Act
    await push_branch(repo_with_remote, "deploy")

    # Assert: the bare remote now has a `deploy` ref pointing at the same sha.
    remote_sha = _run("rev-parse", "deploy", cwd=bare_remote).strip()
    assert remote_sha == local_sha


async def test_push_branch_force_with_lease_overwrites_remote(
    repo_with_remote: Path, bare_remote: Path, tmp_path: Path, git_env: dict
):
    """force_with_lease must allow a non-fast-forward push when local has fetched."""
    # Arrange: push a branch, then rewrite it locally.
    _run("checkout", "-b", "rewrite", cwd=repo_with_remote, env=git_env)
    (repo_with_remote / "a.txt").write_text("v1\n", encoding="utf-8")
    _run("add", "a.txt", cwd=repo_with_remote, env=git_env)
    _run("commit", "-m", "v1", cwd=repo_with_remote, env=git_env)
    _run("push", "origin", "rewrite", cwd=repo_with_remote, env=git_env)
    # Amend to rewrite history.
    (repo_with_remote / "a.txt").write_text("v2\n", encoding="utf-8")
    _run("add", "a.txt", cwd=repo_with_remote, env=git_env)
    _run("commit", "--amend", "-m", "v2", cwd=repo_with_remote, env=git_env)
    new_sha = _run("rev-parse", "HEAD", cwd=repo_with_remote).strip()

    # Plain push must fail (non-fast-forward).
    from app.git_ops import GitError
    with pytest.raises(GitError):
        await push_branch(repo_with_remote, "rewrite")

    # Act
    await push_branch(repo_with_remote, "rewrite", force_with_lease=True)

    # Assert
    remote_sha = _run("rev-parse", "rewrite", cwd=bare_remote).strip()
    assert remote_sha == new_sha


async def test_push_branch_rejects_invalid_branch_name(empty_repo: Path):
    from app.git_ops import GitError

    with pytest.raises(GitError, match="Invalid branch name"):
        await push_branch(empty_repo, "..bad..")


# ---------------------------------------------------------------------------
# detect_github_remote
# ---------------------------------------------------------------------------


async def test_detect_github_remote_https_url(empty_repo: Path, git_env: dict):
    # Arrange
    _run("remote", "add", "origin",
         "https://github.com/foo/bar.git", cwd=empty_repo, env=git_env)

    # Act
    result = await detect_github_remote(empty_repo)

    # Assert
    assert result == "foo/bar"


async def test_detect_github_remote_ssh_url(empty_repo: Path, git_env: dict):
    # Arrange
    _run("remote", "add", "origin",
         "git@github.com:foo/bar.git", cwd=empty_repo, env=git_env)

    # Act
    result = await detect_github_remote(empty_repo)

    # Assert
    assert result == "foo/bar"


async def test_detect_github_remote_https_url_no_dot_git_suffix(
    empty_repo: Path, git_env: dict
):
    # Arrange — many people configure remotes without the trailing .git
    _run("remote", "add", "origin",
         "https://github.com/octo/Hello-World", cwd=empty_repo, env=git_env)

    # Act
    result = await detect_github_remote(empty_repo)

    # Assert
    assert result == "octo/Hello-World"


async def test_detect_github_remote_gitlab_returns_none(
    empty_repo: Path, git_env: dict
):
    # Arrange
    _run("remote", "add", "origin",
         "https://gitlab.com/foo/bar.git", cwd=empty_repo, env=git_env)

    # Act
    result = await detect_github_remote(empty_repo)

    # Assert
    assert result is None


async def test_detect_github_remote_no_origin_returns_none(empty_repo: Path):
    # Arrange: no remote configured.

    # Act
    result = await detect_github_remote(empty_repo)

    # Assert
    assert result is None


async def test_detect_github_remote_ssh_with_subgroup_does_not_match(
    empty_repo: Path, git_env: dict
):
    """The regex anchors at end-of-string; URLs with extra path segments don't match."""
    # Arrange: bitbucket SSH-style URL — should not be misclassified as GitHub.
    _run("remote", "add", "origin",
         "git@bitbucket.org:team/repo.git", cwd=empty_repo, env=git_env)

    # Act
    result = await detect_github_remote(empty_repo)

    # Assert
    assert result is None


# ---------------------------------------------------------------------------
# gh_pr_create
# ---------------------------------------------------------------------------


async def test_gh_pr_create_returns_none_when_gh_not_on_path(
    empty_repo: Path, monkeypatch: pytest.MonkeyPatch, caplog
):
    # Arrange: simulate gh missing.
    monkeypatch.setattr("app.git_ops.shutil.which", lambda _: None)

    # Act
    with caplog.at_level("INFO", logger="cronos.git"):
        result = await gh_pr_create(
            empty_repo,
            title="t",
            body="b",
            base="main",
            head="feature",
        )

    # Assert
    assert result is None
    # The early-return path logs an info message; assert on the logger, not exact text.
    assert any(
        r.name == "cronos.git" and r.levelname == "INFO"
        for r in caplog.records
    )


async def test_gh_pr_create_returns_none_on_subprocess_filenotfound(
    empty_repo: Path, monkeypatch: pytest.MonkeyPatch
):
    """If shutil.which lies (race) and the subprocess raises FileNotFoundError, return None."""
    # Arrange: pretend gh exists for the which-guard, but the subprocess raises.
    monkeypatch.setattr("app.git_ops.shutil.which", lambda _: "/fake/gh")

    async def _raise_fnf(*args, **kwargs):
        raise FileNotFoundError("gh")

    monkeypatch.setattr("app.git_ops.asyncio.create_subprocess_exec", _raise_fnf)

    # Act
    result = await gh_pr_create(
        empty_repo, title="t", body="b", base="main", head="feature"
    )

    # Assert
    assert result is None


async def test_gh_pr_create_returns_url_on_success(
    empty_repo: Path, monkeypatch: pytest.MonkeyPatch
):
    """Happy path: gh exits 0, stdout is the PR URL → returned verbatim, trimmed."""
    # Arrange: fake gh subprocess.
    monkeypatch.setattr("app.git_ops.shutil.which", lambda _: "/fake/gh")

    class _FakeProc:
        returncode = 0

        async def communicate(self, input=None):
            return (b"https://github.com/foo/bar/pull/42\n", b"")

    async def _exec(*args, **kwargs):
        return _FakeProc()

    monkeypatch.setattr("app.git_ops.asyncio.create_subprocess_exec", _exec)

    # Act
    url = await gh_pr_create(
        empty_repo, title="t", body="b", base="main", head="feature"
    )

    # Assert
    assert url == "https://github.com/foo/bar/pull/42"


async def test_gh_pr_create_returns_none_on_nonzero_exit(
    empty_repo: Path, monkeypatch: pytest.MonkeyPatch, caplog
):
    # Arrange
    monkeypatch.setattr("app.git_ops.shutil.which", lambda _: "/fake/gh")

    class _FakeProc:
        returncode = 1

        async def communicate(self, input=None):
            return (b"", b"not authenticated\n")

    async def _exec(*args, **kwargs):
        return _FakeProc()

    monkeypatch.setattr("app.git_ops.asyncio.create_subprocess_exec", _exec)

    # Act
    with caplog.at_level("WARNING", logger="cronos.git"):
        result = await gh_pr_create(
            empty_repo, title="t", body="b", base="main", head="feature"
        )

    # Assert
    assert result is None
    assert any(
        r.name == "cronos.git" and r.levelname == "WARNING"
        for r in caplog.records
    )


async def test_gh_pr_create_returns_none_on_empty_stdout(
    empty_repo: Path, monkeypatch: pytest.MonkeyPatch
):
    """Exit 0 but empty stdout (whitespace only) → None, not empty string."""
    # Arrange
    monkeypatch.setattr("app.git_ops.shutil.which", lambda _: "/fake/gh")

    class _FakeProc:
        returncode = 0

        async def communicate(self, input=None):
            return (b"   \n", b"")

    async def _exec(*args, **kwargs):
        return _FakeProc()

    monkeypatch.setattr("app.git_ops.asyncio.create_subprocess_exec", _exec)

    # Act
    result = await gh_pr_create(
        empty_repo, title="t", body="b", base="main", head="feature"
    )

    # Assert
    assert result is None


async def test_gh_pr_create_timeout_returns_none(
    empty_repo: Path, monkeypatch: pytest.MonkeyPatch, caplog
):
    """If gh hangs past the 60s budget, returns None and logs a warning — no exception."""
    # Arrange
    monkeypatch.setattr("app.git_ops.shutil.which", lambda _: "/fake/gh")

    killed = {"count": 0}

    class _SlowProc:
        returncode = None

        async def communicate(self, input=None):
            # Trigger the wait_for timeout path immediately.
            await asyncio.sleep(0.01)
            return (b"", b"")

        def kill(self):
            killed["count"] += 1

        async def wait(self):
            return 0

    async def _exec(*args, **kwargs):
        return _SlowProc()

    async def _fake_wait_for(coro, timeout):
        # Drain the coroutine to avoid "never awaited" warnings, then raise.
        try:
            coro.close()
        except Exception:
            pass
        raise asyncio.TimeoutError()

    monkeypatch.setattr("app.git_ops.asyncio.create_subprocess_exec", _exec)
    monkeypatch.setattr("app.git_ops.asyncio.wait_for", _fake_wait_for)

    # Act
    with caplog.at_level("WARNING", logger="cronos.git"):
        result = await gh_pr_create(
            empty_repo, title="t", body="b", base="main", head="feature"
        )

    # Assert
    assert result is None
    assert killed["count"] == 1
    assert any(
        r.name == "cronos.git" and r.levelname == "WARNING"
        for r in caplog.records
    )
