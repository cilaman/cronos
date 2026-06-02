from __future__ import annotations

"""Tests for app/api/tools.py — scanning .claude directories for agents, commands, skills, etc."""

import json
from pathlib import Path

import pytest

from app.api.tools import (
    _extract_description,
    _mtime_iso,
    _parse_settings,
    _scan_category,
    _scan_context,
    _scan_skills,
)

from .conftest import SPACE_ID


# ---------------------------------------------------------------------------
# _mtime_iso
# ---------------------------------------------------------------------------


def test_mtime_iso_returns_iso_string_for_existing_file(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("hello")
    result = _mtime_iso(f)
    # Should be a valid ISO datetime string ending with +00:00 (UTC)
    assert "T" in result
    assert "+00:00" in result or "Z" in result or result.endswith("+00:00")


def test_mtime_iso_returns_current_time_for_missing_file(tmp_path):
    missing = tmp_path / "nonexistent.md"
    result = _mtime_iso(missing)
    assert "T" in result


# ---------------------------------------------------------------------------
# _extract_description
# ---------------------------------------------------------------------------


def test_extract_description_yaml_frontmatter(tmp_path):
    f = tmp_path / "agent.md"
    f.write_text('---\nname: test\ndescription: "My agent description"\n---\nSome body text.\n')
    assert _extract_description(f) == "My agent description"


def test_extract_description_yaml_frontmatter_single_quotes(tmp_path):
    f = tmp_path / "agent.md"
    f.write_text("---\ndescription: 'Single quoted desc'\n---\nBody.\n")
    assert _extract_description(f) == "Single quoted desc"


def test_extract_description_yaml_frontmatter_unquoted(tmp_path):
    f = tmp_path / "agent.md"
    f.write_text("---\ndescription: Unquoted description\n---\nBody.\n")
    assert _extract_description(f) == "Unquoted description"


def test_extract_description_falls_back_to_first_paragraph(tmp_path):
    f = tmp_path / "agent.md"
    f.write_text("# Heading\n\nThis is the first paragraph.\n")
    assert _extract_description(f) == "This is the first paragraph."


def test_extract_description_skips_empty_lines_and_headings(tmp_path):
    f = tmp_path / "agent.md"
    f.write_text("\n# Title\n\n## Subtitle\n\nReal description here.\n")
    assert _extract_description(f) == "Real description here."


def test_extract_description_empty_file(tmp_path):
    f = tmp_path / "agent.md"
    f.write_text("")
    assert _extract_description(f) is None


def test_extract_description_missing_file(tmp_path):
    assert _extract_description(tmp_path / "missing.md") is None


def test_extract_description_truncates_to_200_chars(tmp_path):
    f = tmp_path / "agent.md"
    long_line = "x" * 300
    f.write_text(f"# Heading\n\n{long_line}\n")
    result = _extract_description(f)
    assert result is not None
    assert len(result) <= 200


def test_extract_description_skips_separator_lines(tmp_path):
    f = tmp_path / "agent.md"
    f.write_text("---\nname: foo\n---\n\nActual content.\n")
    assert _extract_description(f) == "Actual content."


# ---------------------------------------------------------------------------
# _scan_category
# ---------------------------------------------------------------------------


def test_scan_category_missing_dir(tmp_path):
    result = _scan_category(tmp_path / "nonexistent", "agents", "space")
    assert result == []


def test_scan_category_empty_dir(tmp_path):
    (tmp_path / "agents").mkdir()
    result = _scan_category(tmp_path, "agents", "space")
    assert result == []


def test_scan_category_finds_markdown_files(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "my-agent.md").write_text("---\ndescription: Does things\n---\n")
    (agents_dir / "other.md").write_text("Other agent.\n")

    result = _scan_category(tmp_path, "agents", "space")
    assert len(result) == 2
    names = {e.name for e in result}
    assert "my-agent" in names
    assert "other" in names


def test_scan_category_extracts_description(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "coder.md").write_text("---\ndescription: Writes code\n---\n")

    result = _scan_category(tmp_path, "agents", "space")
    assert result[0].description == "Writes code"


def test_scan_category_scope_set_correctly(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "a.md").write_text("# A\n")

    result = _scan_category(tmp_path, "agents", "global")
    assert result[0].scope == "global"


def test_scan_category_ignores_non_markdown(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "script.sh").write_text("#!/bin/bash\n")
    (agents_dir / "readme.md").write_text("Hello.\n")

    result = _scan_category(tmp_path, "agents", "space")
    assert len(result) == 1
    assert result[0].name == "readme"


def test_scan_category_recursive_finds_nested(tmp_path):
    commands_dir = tmp_path / "commands"
    subdir = commands_dir / "git"
    subdir.mkdir(parents=True)
    (subdir / "commit.md").write_text("Commit helper.\n")

    result = _scan_category(tmp_path, "commands", "space", recursive=True)
    assert len(result) == 1
    assert result[0].name == "commit"


def test_scan_category_non_recursive_skips_nested(tmp_path):
    agents_dir = tmp_path / "agents"
    subdir = agents_dir / "sub"
    subdir.mkdir(parents=True)
    (subdir / "nested.md").write_text("Nested.\n")

    result = _scan_category(tmp_path, "agents", "space", recursive=False)
    assert result == []


# ---------------------------------------------------------------------------
# _scan_skills
# ---------------------------------------------------------------------------


def test_scan_skills_missing_dir(tmp_path):
    result = _scan_skills(tmp_path / "nonexistent", "space")
    assert result == []


def test_scan_skills_flat_files(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "deploy.md").write_text("---\ndescription: Deploy skill\n---\n")

    result = _scan_skills(tmp_path, "space")
    assert len(result) == 1
    assert result[0].name == "deploy"
    assert result[0].description == "Deploy skill"


def test_scan_skills_directory_based(tmp_path):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "frontend-design"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\ndescription: Frontend design skill\n---\n")

    result = _scan_skills(tmp_path, "global")
    assert len(result) == 1
    assert result[0].name == "frontend-design"
    assert result[0].scope == "global"


def test_scan_skills_deduplicates_flat_and_dir(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "myskill.md").write_text("Flat skill.\n")
    skill_dir = skills_dir / "myskill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Dir skill.\n")

    result = _scan_skills(tmp_path, "space")
    # flat file should be picked up, directory version skipped (seen set)
    assert len(result) == 1
    assert result[0].name == "myskill"


def test_scan_skills_dir_without_skill_md_ignored(tmp_path):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "orphan"
    skill_dir.mkdir(parents=True)
    (skill_dir / "README.md").write_text("Not a SKILL.md.\n")

    result = _scan_skills(tmp_path, "space")
    assert result == []


# ---------------------------------------------------------------------------
# _scan_context
# ---------------------------------------------------------------------------


def test_scan_context_empty(tmp_path):
    result = _scan_context(tmp_path, "space")
    assert result == []


def test_scan_context_finds_context_md(tmp_path):
    (tmp_path / "CONTEXT.md").write_text("---\ndescription: Main context\n---\n")
    result = _scan_context(tmp_path, "space")
    assert len(result) == 1
    assert result[0].name == "CONTEXT"
    assert result[0].description == "Main context"


def test_scan_context_finds_context_dir_files(tmp_path):
    ctx_dir = tmp_path / "context"
    ctx_dir.mkdir()
    (ctx_dir / "rules.md").write_text("Context rules.\n")
    (ctx_dir / "guide.txt").write_text("Guide.\n")

    result = _scan_context(tmp_path, "global")
    assert len(result) == 2
    names = {e.name for e in result}
    assert "rules" in names
    assert "guide" in names
    for e in result:
        assert e.scope == "global"


def test_scan_context_both_context_md_and_dir(tmp_path):
    (tmp_path / "CONTEXT.md").write_text("Top-level context.\n")
    ctx_dir = tmp_path / "context"
    ctx_dir.mkdir()
    (ctx_dir / "extra.md").write_text("Extra context.\n")

    result = _scan_context(tmp_path, "space")
    assert len(result) == 2


# ---------------------------------------------------------------------------
# _parse_settings
# ---------------------------------------------------------------------------


def test_parse_settings_missing_file(tmp_path):
    hooks, perms = _parse_settings(tmp_path / "settings.json", "space")
    assert hooks == []
    assert perms == []


def test_parse_settings_invalid_json(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text("not valid json {{{")
    hooks, perms = _parse_settings(f, "space")
    assert hooks == []
    assert perms == []


def test_parse_settings_permissions(tmp_path):
    f = tmp_path / "settings.json"
    data = {
        "permissions": {
            "allow": ["Bash(git *)", "Read"],
            "deny": ["Bash(rm *)"],
        }
    }
    f.write_text(json.dumps(data))
    hooks, perms = _parse_settings(f, "space")
    assert len(perms) == 3
    allowed = [p for p in perms if p.allowed]
    denied = [p for p in perms if not p.allowed]
    assert len(allowed) == 2
    assert len(denied) == 1
    assert denied[0].pattern == "Bash(rm *)"


def test_parse_settings_hooks(tmp_path):
    f = tmp_path / "settings.json"
    data = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "echo done"}],
                }
            ]
        }
    }
    f.write_text(json.dumps(data))
    hooks, perms = _parse_settings(f, "global")
    assert len(hooks) == 1
    assert hooks[0].event == "PostToolUse"
    assert hooks[0].matcher == "Bash"
    assert hooks[0].command == "echo done"
    assert hooks[0].scope == "global"


def test_parse_settings_hook_without_matcher(tmp_path):
    f = tmp_path / "settings.json"
    data = {
        "hooks": {
            "Stop": [
                {
                    "hooks": [{"type": "command", "command": "notify.sh"}],
                }
            ]
        }
    }
    f.write_text(json.dumps(data))
    hooks, _ = _parse_settings(f, "space")
    assert len(hooks) == 1
    assert hooks[0].matcher is None
    assert hooks[0].command == "notify.sh"


def test_parse_settings_hook_group_missing_command_skipped(tmp_path):
    f = tmp_path / "settings.json"
    data = {
        "hooks": {
            "PostToolUse": [
                {"hooks": [{"type": "command", "command": ""}]},
            ]
        }
    }
    f.write_text(json.dumps(data))
    hooks, _ = _parse_settings(f, "space")
    assert hooks == []


def test_parse_settings_empty_json(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text("{}")
    hooks, perms = _parse_settings(f, "space")
    assert hooks == []
    assert perms == []


def test_parse_settings_ignores_non_string_patterns(tmp_path):
    f = tmp_path / "settings.json"
    data = {"permissions": {"allow": [123, None, "ValidPattern"], "deny": []}}
    f.write_text(json.dumps(data))
    _, perms = _parse_settings(f, "space")
    assert len(perms) == 1
    assert perms[0].pattern == "ValidPattern"


# ---------------------------------------------------------------------------
# GET /api/spaces/{space_id}/tools — integration
# ---------------------------------------------------------------------------


async def test_get_space_tools_not_found(async_client):
    resp = await async_client.get("/api/spaces/nonexistent-space/tools")
    assert resp.status_code == 404


async def test_get_space_tools_empty_space(async_client, space_store):
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert body["space_id"] == SPACE_ID
    assert isinstance(body["agents"], list)
    assert isinstance(body["commands"], list)
    assert isinstance(body["skills"], list)
    assert isinstance(body["hooks"], list)
    assert isinstance(body["permissions"], list)
    assert "has_claude_md" in body


async def test_get_space_tools_with_agents(async_client, space_store, tmp_spaces_dir):
    space_dir = tmp_spaces_dir / SPACE_ID
    agents_dir = space_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "test-agent.md").write_text("---\ndescription: Test agent\n---\n")

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools")
    assert resp.status_code == 200
    body = resp.json()
    space_agents = [a for a in body["agents"] if a.get("scope") == "space"]
    assert any(a["name"] == "test-agent" for a in space_agents)


async def test_get_space_tools_with_settings(async_client, space_store, tmp_spaces_dir):
    space_dir = tmp_spaces_dir / SPACE_ID
    claude_dir = space_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "permissions": {"allow": ["Bash(git *)"], "deny": []},
        "hooks": {
            "Stop": [{"hooks": [{"type": "command", "command": "echo done"}]}]
        },
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings))

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools")
    assert resp.status_code == 200
    body = resp.json()
    space_perms = [p for p in body["permissions"] if p.get("scope") == "space"]
    assert len(space_perms) >= 1
    space_hooks = [h for h in body["hooks"] if h.get("scope") == "space"]
    assert len(space_hooks) >= 1


async def test_get_space_tools_detects_claude_md(async_client, space_store, tmp_spaces_dir):
    space_dir = tmp_spaces_dir / SPACE_ID
    space_dir.mkdir(parents=True, exist_ok=True)
    (space_dir / "CLAUDE.md").write_text("# Instructions\n")

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools")
    assert resp.status_code == 200
    assert resp.json()["has_claude_md"] is True


async def test_tool_content_roundtrip_for_listed_path(async_client, space_store, tmp_spaces_dir):
    """A path returned by the listing endpoint must resolve via the content endpoint.

    Regression: listing emitted paths relative to .claude (e.g. ``agents/x.md``)
    while the content endpoint joined them to the space dir, yielding 404.
    """
    space_dir = tmp_spaces_dir / SPACE_ID
    agents_dir = space_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "test-agent.md").write_text("---\ndescription: Test agent\n---\nbody\n")

    listing = (await async_client.get(f"/api/spaces/{SPACE_ID}/tools")).json()
    entry = next(a for a in listing["agents"] if a["name"] == "test-agent")
    assert entry["path"] == ".claude/agents/test-agent.md"

    resp = await async_client.get(
        f"/api/spaces/{SPACE_ID}/tool-content",
        params={"path": entry["path"], "scope": entry["scope"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "agent"
    assert "body" in body["content"]


async def test_tool_content_rejects_path_traversal(async_client, space_store, tmp_spaces_dir):
    (tmp_spaces_dir / SPACE_ID).mkdir(parents=True, exist_ok=True)
    resp = await async_client.get(
        f"/api/spaces/{SPACE_ID}/tool-content",
        params={"path": "../../etc/passwd", "scope": "space"},
    )
    assert resp.status_code == 400
