"""Tests for the resolve_tool module-level helper in backend/app/worker.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.worker import resolve_tool
from app.harnesses.brief_composer import compose_brief
from app.harnesses.model import HarnessNode, NodeType, Position
from app.models import AiToolEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str = "# placeholder") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _make_node(agent_ref: str = "my-agent") -> HarnessNode:
    return HarnessNode(
        id="n1",
        type=NodeType.agent,
        position=Position(x=0.0, y=0.0),
        data={"agent_ref": agent_ref},
    )


def _empty_dir(tmp_path: Path, name: str) -> Path:
    d = tmp_path / name / ".claude"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# R1: scanner reuse — agent match
# ---------------------------------------------------------------------------

def test_agent_match(tmp_path: Path) -> None:
    space_claude = _empty_dir(tmp_path, "space")
    _write(space_claude / "agents" / "my-agent.md", "# My Agent\nDoes stuff.")
    global_claude = _empty_dir(tmp_path, "global")

    result = resolve_tool(space_claude, global_claude, "my-agent")

    assert result is not None
    assert result.name == "my-agent"
    assert result.scope == "space"
    assert "agents/" in result.path


# ---------------------------------------------------------------------------
# R4: skill detection — path contains "skills/", brief prefixed with /name
# ---------------------------------------------------------------------------

def test_skill_match_directory_based(tmp_path: Path) -> None:
    space_claude = _empty_dir(tmp_path, "space")
    _write(space_claude / "skills" / "bar" / "SKILL.md", "# Bar Skill\nDoes bar.")
    global_claude = _empty_dir(tmp_path, "global")

    result = resolve_tool(space_claude, global_claude, "bar")

    assert result is not None
    assert result.name == "bar"
    assert result.scope == "space"
    assert "skills/" in result.path

    node = _make_node("bar")
    brief = compose_brief(node, "the prompt", result)
    assert brief.startswith("/bar")
    assert "the prompt" in brief


def test_skill_match_flat_file(tmp_path: Path) -> None:
    space_claude = _empty_dir(tmp_path, "space")
    _write(space_claude / "skills" / "flat-skill.md", "# Flat skill")
    global_claude = _empty_dir(tmp_path, "global")

    result = resolve_tool(space_claude, global_claude, "flat-skill")

    assert result is not None
    assert result.name == "flat-skill"
    assert "skills/" in result.path

    node = _make_node("flat-skill")
    brief = compose_brief(node, "do work", result)
    assert brief.startswith("/flat-skill")


# ---------------------------------------------------------------------------
# R1: command match
# ---------------------------------------------------------------------------

def test_command_match(tmp_path: Path) -> None:
    space_claude = _empty_dir(tmp_path, "space")
    _write(space_claude / "commands" / "baz.md", "# Baz command")
    global_claude = _empty_dir(tmp_path, "global")

    result = resolve_tool(space_claude, global_claude, "baz")

    assert result is not None
    assert result.name == "baz"
    assert result.scope == "space"
    assert "commands/" in result.path


# ---------------------------------------------------------------------------
# R1: context match
# ---------------------------------------------------------------------------

def test_context_match_context_md(tmp_path: Path) -> None:
    space_claude = _empty_dir(tmp_path, "space")
    _write(space_claude / "CONTEXT.md", "# Context")
    global_claude = _empty_dir(tmp_path, "global")

    result = resolve_tool(space_claude, global_claude, "CONTEXT")

    assert result is not None
    assert result.name == "CONTEXT"
    assert result.scope == "space"


def test_context_match_context_dir_file(tmp_path: Path) -> None:
    space_claude = _empty_dir(tmp_path, "space")
    _write(space_claude / "context" / "project.md", "# Project context")
    global_claude = _empty_dir(tmp_path, "global")

    result = resolve_tool(space_claude, global_claude, "project")

    assert result is not None
    assert result.name == "project"
    assert result.scope == "space"


# ---------------------------------------------------------------------------
# Miss → None
# ---------------------------------------------------------------------------

def test_miss_returns_none(tmp_path: Path) -> None:
    space_claude = _empty_dir(tmp_path, "space")
    global_claude = _empty_dir(tmp_path, "global")

    result = resolve_tool(space_claude, global_claude, "nonexistent-tool")

    assert result is None


def test_empty_agent_ref_returns_none(tmp_path: Path) -> None:
    space_claude = _empty_dir(tmp_path, "space")
    _write(space_claude / "agents" / "something.md")
    global_claude = _empty_dir(tmp_path, "global")

    assert resolve_tool(space_claude, global_claude, "") is None
    assert resolve_tool(space_claude, global_claude, None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# R2: space shadows global (same name in both scopes → space wins)
# ---------------------------------------------------------------------------

def test_space_shadows_global(tmp_path: Path) -> None:
    space_claude = _empty_dir(tmp_path, "space")
    _write(space_claude / "agents" / "qux.md", "# Space qux")
    global_claude = _empty_dir(tmp_path, "global")
    _write(global_claude / "agents" / "qux.md", "# Global qux")

    result = resolve_tool(space_claude, global_claude, "qux")

    assert result is not None
    assert result.scope == "space"


def test_global_match_when_no_space(tmp_path: Path) -> None:
    space_claude = _empty_dir(tmp_path, "space")
    global_claude = _empty_dir(tmp_path, "global")
    _write(global_claude / "agents" / "qux.md", "# Global qux")

    result = resolve_tool(space_claude, global_claude, "qux")

    assert result is not None
    assert result.scope == "global"
    assert result.name == "qux"


# ---------------------------------------------------------------------------
# Intra-scope order: agents shadow skills of same name within one scope
# ---------------------------------------------------------------------------

def test_agent_shadows_skill_same_scope(tmp_path: Path) -> None:
    space_claude = _empty_dir(tmp_path, "space")
    _write(space_claude / "agents" / "foo.md", "# Agent foo")
    _write(space_claude / "skills" / "foo" / "SKILL.md", "# Skill foo")
    global_claude = _empty_dir(tmp_path, "global")

    result = resolve_tool(space_claude, global_claude, "foo")

    assert result is not None
    assert "agents/" in result.path


# ---------------------------------------------------------------------------
# Missing directories are handled gracefully (no FileNotFoundError)
# ---------------------------------------------------------------------------

def test_missing_space_dir_does_not_raise(tmp_path: Path) -> None:
    space_claude = tmp_path / "nonexistent" / ".claude"
    global_claude = _empty_dir(tmp_path, "global")
    _write(global_claude / "agents" / "zoo.md", "# Zoo")

    result = resolve_tool(space_claude, global_claude, "zoo")

    assert result is not None
    assert result.scope == "global"


def test_missing_global_dir_does_not_raise(tmp_path: Path) -> None:
    space_claude = _empty_dir(tmp_path, "space")
    _write(space_claude / "agents" / "zoo.md", "# Zoo")
    global_claude = tmp_path / "nonexistent-global" / ".claude"

    result = resolve_tool(space_claude, global_claude, "zoo")

    assert result is not None
    assert result.scope == "space"


def test_both_dirs_missing_returns_none(tmp_path: Path) -> None:
    space_claude = tmp_path / "no-space" / ".claude"
    global_claude = tmp_path / "no-global" / ".claude"

    result = resolve_tool(space_claude, global_claude, "anything")

    assert result is None
