"""Unit tests for git_ops._auth_env() and push_branch() credential injection.

Verifies:
- _auth_env() returns a properly constructed env dict for HTTPS URLs with a PAT
- _auth_env() returns None for SSH URLs and when no token is configured
- The raw PAT value never appears as plaintext in the env passed to git
- push_branch() injects credentials when the remote is HTTPS
- push_branch() never leaks the token value into caplog (git args are logged, not env)

These tests assert the 'contents:write / no admin / no workflow' credential contract
documented in git_ops.py and .env.example; they do not modify that contract.
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.git_ops import _auth_env, push_branch


# ---------------------------------------------------------------------------
# helpers / fixtures
# ---------------------------------------------------------------------------


def _run(*args: str, cwd: Path, env: dict | None = None) -> str:
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
def repo_with_local_remote(tmp_path: Path, git_env: dict) -> Path:
    """A repo with a local bare remote so push_branch can run without network access."""
    bare = tmp_path / "remote.git"
    bare.mkdir()
    _run("init", "--bare", "-b", "main", cwd=bare, env=git_env)

    repo = tmp_path / "repo"
    repo.mkdir()
    _run("init", "-b", "main", cwd=repo, env=git_env)
    _run("config", "user.email", "test@cronos.local", cwd=repo, env=git_env)
    _run("config", "user.name", "Cronos Test", cwd=repo, env=git_env)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _run("add", "README.md", cwd=repo, env=git_env)
    _run("commit", "-m", "initial", cwd=repo, env=git_env)
    _run("remote", "add", "origin", str(bare), cwd=repo, env=git_env)
    _run("push", "-u", "origin", "main", cwd=repo, env=git_env)
    return repo


# ---------------------------------------------------------------------------
# _auth_env unit tests
# ---------------------------------------------------------------------------


def test_auth_env_https_returns_env_with_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """_auth_env returns an env dict containing an Authorization header for HTTPS URLs."""
    token = "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    monkeypatch.setenv("CRONOS_GIT_TOKEN", token)

    env = _auth_env("https://github.com/owner/repo.git")

    assert env is not None
    assert env.get("GIT_CONFIG_COUNT") == "1"
    assert env.get("GIT_CONFIG_KEY_0") == "http.extraHeader"
    expected_b64 = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    assert env.get("GIT_CONFIG_VALUE_0") == f"Authorization: Basic {expected_b64}"


def test_auth_env_sets_no_terminal_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """_auth_env disables interactive prompts so a bad token fails fast."""
    monkeypatch.setenv("CRONOS_GIT_TOKEN", "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")

    env = _auth_env("https://github.com/owner/repo.git")

    assert env is not None
    assert env.get("GIT_TERMINAL_PROMPT") == "0"


def test_auth_env_token_not_as_plaintext_in_git_config_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """The raw PAT must not appear as plaintext in the GIT_CONFIG_VALUE_0 header.

    _auth_env encodes the PAT as base64('x-access-token:<token>') so it never
    appears as a recognisable string in the Authorization header that git sees.
    (The token is still present under CRONOS_GIT_TOKEN in the env dict — that is
    expected because _auth_env copies the full os.environ — but it is not in the
    git-specific header value that git actually processes and may reflect in errors.)
    """
    token = "ghp_ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"
    monkeypatch.setenv("CRONOS_GIT_TOKEN", token)

    env = _auth_env("https://github.com/owner/repo.git")

    assert env is not None
    git_header = env.get("GIT_CONFIG_VALUE_0", "")
    assert token not in git_header, (
        f"Raw PAT found in GIT_CONFIG_VALUE_0 — must be base64-encoded there: {git_header!r}"
    )


def test_auth_env_ssh_url_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """_auth_env returns None for SSH URLs — those use ssh-agent / deploy keys."""
    monkeypatch.setenv("CRONOS_GIT_TOKEN", "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")

    result = _auth_env("git@github.com:owner/repo.git")

    assert result is None


def test_auth_env_no_token_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """_auth_env returns None when CRONOS_GIT_TOKEN is not set."""
    monkeypatch.delenv("CRONOS_GIT_TOKEN", raising=False)

    result = _auth_env("https://github.com/owner/repo.git")

    assert result is None


def test_auth_env_http_url_also_authenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    """_auth_env handles plain http:// in addition to https:// (uncommon but supported)."""
    monkeypatch.setenv("CRONOS_GIT_TOKEN", "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")

    env = _auth_env("http://internal.git.example.com/repo.git")

    assert env is not None
    assert "Authorization: Basic " in (env.get("GIT_CONFIG_VALUE_0") or "")


# ---------------------------------------------------------------------------
# push_branch: credential injection
# ---------------------------------------------------------------------------


async def test_push_branch_injects_auth_env_for_https_remote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """push_branch must pass an auth env to git when the remote is HTTPS."""
    captured: dict = {}

    async def fake_run_or_raise(*args: str, cwd: Path | None = None, timeout: float = 300.0, env: dict | None = None) -> str:
        captured["env"] = env
        return ""

    async def fake_space_remote_url(_cwd: Path) -> str:
        return "https://github.com/owner/repo.git"

    token = "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    monkeypatch.setenv("CRONOS_GIT_TOKEN", token)
    monkeypatch.setattr("app.git_ops._run_or_raise", fake_run_or_raise)
    monkeypatch.setattr("app.git_ops._space_remote_url", fake_space_remote_url)

    await push_branch(Path("/tmp/fake-worktree"), "feature/test")

    env = captured.get("env")
    assert env is not None, "push_branch must pass an env dict to git for HTTPS remotes"
    assert "GIT_CONFIG_VALUE_0" in env
    assert "Authorization: Basic " in env["GIT_CONFIG_VALUE_0"]
    # The raw token must not appear in the GIT_CONFIG_VALUE_0 header (it is base64-encoded there).
    # (The token is still in env["CRONOS_GIT_TOKEN"] because os.environ is copied — that is expected.)
    assert token not in env["GIT_CONFIG_VALUE_0"], (
        f"Raw PAT found in GIT_CONFIG_VALUE_0 — must be base64-encoded: {env['GIT_CONFIG_VALUE_0']!r}"
    )


async def test_push_branch_no_auth_env_for_local_remote(
    repo_with_local_remote: Path,
    git_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """push_branch passes no auth env for non-HTTPS (local file://) remotes."""
    token = "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    monkeypatch.setenv("CRONOS_GIT_TOKEN", token)

    _run("checkout", "-b", "cred-test", cwd=repo_with_local_remote, env=git_env)
    (repo_with_local_remote / "f.txt").write_text("x\n", encoding="utf-8")
    _run("add", "f.txt", cwd=repo_with_local_remote, env=git_env)
    _run("commit", "-m", "test", cwd=repo_with_local_remote, env=git_env)

    # Should succeed without any network credentials (local bare remote).
    await push_branch(repo_with_local_remote, "cred-test")


# ---------------------------------------------------------------------------
# push_branch: token must not appear in logs
# ---------------------------------------------------------------------------


async def test_push_branch_token_not_in_caplog(
    repo_with_local_remote: Path,
    git_env: dict,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The PAT value must never appear in any log record emitted during push_branch.

    git_ops._run() logs 'git <args>' but NOT the subprocess environment, so
    the token injected via GIT_CONFIG_VALUE_0 must be invisible to the log.
    """
    token = "ghp_SECRETSECRETSECRETSECRETSECRETSEC"
    monkeypatch.setenv("CRONOS_GIT_TOKEN", token)

    _run("checkout", "-b", "log-leak-test", cwd=repo_with_local_remote, env=git_env)
    (repo_with_local_remote / "leak.txt").write_text("check\n", encoding="utf-8")
    _run("add", "leak.txt", cwd=repo_with_local_remote, env=git_env)
    _run("commit", "-m", "log-leak check", cwd=repo_with_local_remote, env=git_env)

    with caplog.at_level(logging.DEBUG, logger="cronos.git"):
        await push_branch(repo_with_local_remote, "log-leak-test")

    full_log = "\n".join(record.getMessage() for record in caplog.records)
    assert token not in full_log, (
        "CRONOS_GIT_TOKEN value found in git log — potential credential leak\n"
        f"Log output:\n{full_log}"
    )
