from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

import app.api.tools as api_tools
import app.tools.discovery as discovery
import app.tools.scanner as scanner
from app.tools.discovery import (
    DiscoveredItem,
    _make_slug,
    clone_source,
    refresh_source,
    walk_source,
)
from app.tools.sources import ToolSource


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _make_claude_repo(root: Path) -> Path:
    """Create a fixture clone with one agent, one dir-skill, one command,
    and a settings.json with a single hook. Returns the repo root."""
    claude = root / ".claude"

    agents = claude / "agents"
    agents.mkdir(parents=True)
    (agents / "reviewer.md").write_text(
        textwrap.dedent(
            """\
            ---
            description: Reviews code for bugs
            ---
            # Reviewer
            body text
            """
        ),
        encoding="utf-8",
    )

    skills = claude / "skills" / "frontend-design"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        textwrap.dedent(
            """\
            ---
            description: Styles the frontend
            ---
            # Frontend Design
            """
        ),
        encoding="utf-8",
    )

    commands = claude / "commands"
    commands.mkdir(parents=True)
    (commands / "deploy.md").write_text(
        "# Deploy\nShips the app\n", encoding="utf-8"
    )

    (claude / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"command": "echo guard"}],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    return root


# --------------------------------------------------------------------------
# _make_slug — URL → filesystem-safe slug
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        pytest.param(
            "https://github.com/foo/bar.git",
            "github.com-foo-bar",
            id="https-dot-git-stripped",
        ),
        pytest.param(
            "https://github.com/foo/bar",
            "github.com-foo-bar",
            id="https-no-git-suffix",
        ),
        pytest.param(
            "http://example.com/a/b",
            "example.com-a-b",
            id="http-scheme-stripped",
        ),
        pytest.param(
            "git@github.com:foo/bar.git",
            "github.com-foo-bar",
            id="ssh-scp-form",
        ),
    ],
)
def test_make_slug_converts_url(url, expected):
    assert _make_slug(url) == expected


def test_make_slug_collapses_runs_and_trims_dashes():
    # Multiple unsafe chars must collapse to a single dash and never leave
    # leading/trailing dashes that would create hidden/odd directory names.
    result = _make_slug("https://host.example/weird///path!!!.git")

    assert result == "host.example-weird-path"
    assert not result.startswith("-")
    assert not result.endswith("-")


def test_make_slug_is_filesystem_safe():
    # Every character produced must be safe for a directory name.
    result = _make_slug("https://gitlab.com/group/sub group/repo.git")

    assert all(c.isalnum() or c in "._-" for c in result)


# --------------------------------------------------------------------------
# clone_source — shallow clone, branch handling, idempotency
# --------------------------------------------------------------------------


@pytest.fixture
def _discovery_base(tmp_path, monkeypatch):
    base = tmp_path / "discovery_sources"
    monkeypatch.setattr(discovery, "DISCOVERY_BASE", base)
    return base


async def test_clone_source_invokes_shallow_clone(_discovery_base, monkeypatch):
    calls: list[tuple] = []

    async def fake_run_or_raise(*args, **kwargs):
        calls.append((args, kwargs))
        return ""

    monkeypatch.setattr(discovery, "_run_or_raise", fake_run_or_raise)
    monkeypatch.setattr(discovery, "_auth_env", lambda url: None)
    source = ToolSource(url="https://github.com/foo/bar.git")

    # Act
    dest = await clone_source(source)

    assert dest == _discovery_base / "github.com-foo-bar"
    assert len(calls) == 1
    args, _ = calls[0]
    assert args[0] == "clone"
    assert "--depth" in args and "1" in args
    assert str(dest) == args[-1]


async def test_clone_source_passes_branch_when_set(_discovery_base, monkeypatch):
    calls: list[tuple] = []

    async def fake_run_or_raise(*args, **kwargs):
        calls.append(args)
        return ""

    monkeypatch.setattr(discovery, "_run_or_raise", fake_run_or_raise)
    monkeypatch.setattr(discovery, "_auth_env", lambda url: None)
    source = ToolSource(url="https://github.com/foo/bar.git", branch="develop")

    # Act
    await clone_source(source)

    args = calls[0]
    assert "--branch" in args
    assert args[args.index("--branch") + 1] == "develop"


async def test_clone_source_skips_when_already_cloned(_discovery_base, monkeypatch):
    # Arrange an existing clone (presence of .git short-circuits the clone).
    dest = _discovery_base / "github.com-foo-bar"
    (dest / ".git").mkdir(parents=True)
    called = False

    async def fake_run_or_raise(*args, **kwargs):
        nonlocal called
        called = True
        return ""

    monkeypatch.setattr(discovery, "_run_or_raise", fake_run_or_raise)
    source = ToolSource(url="https://github.com/foo/bar.git")

    # Act
    result = await clone_source(source)

    assert result == dest
    assert called is False


# --------------------------------------------------------------------------
# refresh_source — fetch+reset on existing clone, clone when missing
# --------------------------------------------------------------------------


async def test_refresh_source_does_fetch_and_reset_not_reclone(
    _discovery_base, monkeypatch
):
    # Arrange an existing clone so refresh takes the update path.
    dest = _discovery_base / "github.com-foo-bar"
    (dest / ".git").mkdir(parents=True)
    invocations: list[tuple] = []

    async def fake_run_or_raise(*args, **kwargs):
        invocations.append(args)
        return ""

    monkeypatch.setattr(discovery, "_run_or_raise", fake_run_or_raise)
    monkeypatch.setattr(discovery, "_auth_env", lambda url: None)
    source = ToolSource(url="https://github.com/foo/bar.git", branch="main")

    # Act
    result = await refresh_source(source)

    assert result == dest
    verbs = [args[0] for args in invocations]
    assert verbs == ["fetch", "reset"]
    assert "clone" not in verbs
    # reset must be hard against FETCH_HEAD, fetch must reference the branch.
    assert "main" in invocations[0]
    assert invocations[1] == ("reset", "--hard", "FETCH_HEAD")


async def test_refresh_source_uses_head_when_no_branch(_discovery_base, monkeypatch):
    dest = _discovery_base / "github.com-foo-bar"
    (dest / ".git").mkdir(parents=True)
    invocations: list[tuple] = []

    async def fake_run_or_raise(*args, **kwargs):
        invocations.append(args)
        return ""

    monkeypatch.setattr(discovery, "_run_or_raise", fake_run_or_raise)
    monkeypatch.setattr(discovery, "_auth_env", lambda url: None)
    source = ToolSource(url="https://github.com/foo/bar.git")

    # Act
    await refresh_source(source)

    assert "HEAD" in invocations[0]


async def test_refresh_source_clones_when_missing(_discovery_base, monkeypatch):
    # No .git present → refresh delegates to clone_source.
    invocations: list[tuple] = []

    async def fake_run_or_raise(*args, **kwargs):
        invocations.append(args)
        return ""

    monkeypatch.setattr(discovery, "_run_or_raise", fake_run_or_raise)
    monkeypatch.setattr(discovery, "_auth_env", lambda url: None)
    source = ToolSource(url="https://github.com/foo/bar.git")

    # Act
    result = await refresh_source(source)

    assert result == _discovery_base / "github.com-foo-bar"
    assert [args[0] for args in invocations] == ["clone"]


# --------------------------------------------------------------------------
# walk_source — discovers agents/skills/commands/hooks with correct metadata
# --------------------------------------------------------------------------


@pytest.fixture
def _stub_git_metadata(monkeypatch):
    """Stub _run so walk_source resolves a deterministic origin URL + SHA."""

    async def fake_run(*args, **kwargs):
        if args[:1] == ("remote",):
            return 0, "https://github.com/foo/bar.git\n", ""
        if args[:1] == ("rev-parse",):
            return 0, "abc1234def\n", ""
        return 0, "", ""

    monkeypatch.setattr(discovery, "_run", fake_run)


async def test_walk_source_returns_all_kinds(tmp_path, _stub_git_metadata):
    repo = _make_claude_repo(tmp_path / "clone")

    # Act
    items = await walk_source(repo)

    kinds = {it.kind for it in items}
    assert kinds == {"agent", "skill", "command", "hook"}


async def test_walk_source_agent_metadata(tmp_path, _stub_git_metadata):
    repo = _make_claude_repo(tmp_path / "clone")

    items = await walk_source(repo)

    agent = next(it for it in items if it.kind == "agent")
    assert agent.name == "reviewer"
    assert agent.description == "Reviews code for bugs"
    assert agent.relative_path == ".claude/agents/reviewer.md"
    assert agent.source_url == "https://github.com/foo/bar.git"
    assert agent.source_slug == "github.com-foo-bar"
    assert agent.source_sha == "abc1234def"


async def test_walk_source_skill_uses_directory_name(tmp_path, _stub_git_metadata):
    repo = _make_claude_repo(tmp_path / "clone")

    items = await walk_source(repo)

    skill = next(it for it in items if it.kind == "skill")
    assert skill.name == "frontend-design"
    assert skill.relative_path == ".claude/skills/frontend-design/SKILL.md"
    assert skill.description == "Styles the frontend"


async def test_walk_source_hook_name_and_path(tmp_path, _stub_git_metadata):
    repo = _make_claude_repo(tmp_path / "clone")

    items = await walk_source(repo)

    hook = next(it for it in items if it.kind == "hook")
    assert hook.name == "PreToolUse:Bash"
    assert hook.relative_path == ".claude/settings.json"
    assert hook.description == "echo guard"


async def test_walk_source_no_claude_dir_returns_empty(tmp_path):
    # A repo with no .claude/ must short-circuit without touching git.
    repo = tmp_path / "bare"
    repo.mkdir()

    items = await walk_source(repo)

    assert items == []


async def test_walk_source_falls_back_when_git_unavailable(tmp_path, monkeypatch):
    # If git remote/rev-parse fail, slug falls back to the directory name and
    # sha is empty — items are still produced rather than crashing.
    repo = _make_claude_repo(tmp_path / "myclone")

    async def failing_run(*args, **kwargs):
        return 1, "", "fatal: not a git repo"

    monkeypatch.setattr(discovery, "_run", failing_run)

    # Act
    items = await walk_source(repo)

    assert items, "expected items even when git metadata is unavailable"
    agent = next(it for it in items if it.kind == "agent")
    assert agent.source_url == ""
    assert agent.source_slug == "myclone"
    assert agent.source_sha == ""


async def test_walk_source_hook_command_truncated_to_200(tmp_path, _stub_git_metadata):
    repo = _make_claude_repo(tmp_path / "clone")
    long_cmd = "x" * 500
    (repo / ".claude" / "settings.json").write_text(
        json.dumps(
            {"hooks": {"PreToolUse": [{"hooks": [{"command": long_cmd}]}]}}
        ),
        encoding="utf-8",
    )

    items = await walk_source(repo)

    hook = next(it for it in items if it.kind == "hook")
    # No matcher → name uses wildcard; description is capped at 200 chars.
    assert hook.name == "PreToolUse:*"
    assert hook.description == "x" * 200


# --------------------------------------------------------------------------
# Single source of truth — api/tools.py re-uses scanner.py, not local copies
# --------------------------------------------------------------------------


def test_api_tools_imports_scanner_helpers():
    # The scanner functions referenced by the tools API must be the *same*
    # objects defined in scanner.py — guards against the duplicate-impl
    # regression this refactor removed.
    assert api_tools._scan_category is scanner._scan_category
    assert api_tools._scan_skills is scanner._scan_skills
    assert api_tools._parse_settings is scanner._parse_settings
    assert api_tools._extract_description is scanner._extract_description
    assert api_tools._mtime_iso is scanner._mtime_iso


def test_discovered_item_is_dataclass_with_expected_fields():
    item = DiscoveredItem(
        source_url="u",
        source_slug="s",
        kind="agent",
        name="n",
        relative_path="p",
        description=None,
        source_sha="sha",
    )

    assert item.kind == "agent"
    assert item.description is None
