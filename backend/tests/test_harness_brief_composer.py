"""
Tests for backend/app/harnesses/brief_composer.py

Covers:
  - Skill agent_ref gets /<skill-name> prefix in the output.
  - Non-skill (agent) agent_ref does NOT get a slash prefix.
  - agent_entry=None handled gracefully (agent not found case).
  - Interpolated prompt is included in the brief.
  - Brief is always a str.
  - Empty / missing agent_ref handled.
  - Brief format: header separated from body by double-newline.
"""

from __future__ import annotations

import pytest

from app.harnesses.brief_composer import compose_brief, _is_skill
from app.harnesses.model import HarnessNode, NodeType, Position
from app.models import AiToolEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(agent_ref: str = "pipeline-scout", **extra_data) -> HarnessNode:
    data = {"agent_ref": agent_ref, **extra_data}
    return HarnessNode(
        id="n1",
        type=NodeType.agent,
        position=Position(x=0.0, y=0.0),
        data=data,
    )


def _make_agent_entry(
    name: str = "pipeline-scout",
    path: str = ".claude/agents/pipeline-scout.md",
    scope: str = "global",
) -> AiToolEntry:
    return AiToolEntry(
        name=name,
        path=path,
        description="A scout agent.",
        scope=scope,
        modified_at="2026-01-01T00:00:00Z",
    )


def _make_skill_entry(
    name: str = "goal-task-commit",
    path: str = ".claude/skills/goal-task-commit/SKILL.md",
    scope: str = "space",
) -> AiToolEntry:
    return AiToolEntry(
        name=name,
        path=path,
        description="A skill.",
        scope=scope,
        modified_at="2026-01-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# _is_skill unit tests
# ---------------------------------------------------------------------------

class TestIsSkill:
    def test_skill_path_with_skills_slash(self):
        entry = _make_skill_entry(path=".claude/skills/goal-task-commit/SKILL.md")
        assert _is_skill(entry) is True

    def test_skill_path_with_leading_slash(self):
        entry = _make_skill_entry(path="/home/user/.claude/skills/my-skill/SKILL.md")
        assert _is_skill(entry) is True

    def test_agent_path_not_skill(self):
        entry = _make_agent_entry(path=".claude/agents/pipeline-scout.md")
        assert _is_skill(entry) is False

    def test_agent_path_with_agents_dir(self):
        entry = _make_agent_entry(path="~/.claude/agents/tester.md")
        assert _is_skill(entry) is False


# ---------------------------------------------------------------------------
# compose_brief — skill prefix rule
# ---------------------------------------------------------------------------

class TestComposeBriefSkillPrefix:
    def test_skill_gets_slash_prefix(self):
        node = _make_node(agent_ref="goal-task-commit")
        skill = _make_skill_entry(name="goal-task-commit")
        result = compose_brief(node, "Commit the changes.", skill)
        assert result.startswith("/goal-task-commit")

    def test_skill_prefix_exact_format(self):
        node = _make_node(agent_ref="pipeline-gate")
        skill = _make_skill_entry(name="pipeline-gate")
        result = compose_brief(node, "Run the gate.", skill)
        lines = result.split("\n")
        assert lines[0] == "/pipeline-gate"

    def test_skill_prefix_uses_entry_name_not_agent_ref(self):
        """If the resolved name differs from the raw agent_ref, entry.name wins."""
        node = _make_node(agent_ref="pipeline-gate-alias")
        skill = _make_skill_entry(name="pipeline-gate")
        result = compose_brief(node, "Run.", skill)
        assert result.startswith("/pipeline-gate")
        assert "pipeline-gate-alias" not in result.split("\n")[0]

    def test_skill_prefix_separated_from_prompt_by_blank_line(self):
        node = _make_node(agent_ref="goal-task-commit")
        skill = _make_skill_entry(name="goal-task-commit")
        result = compose_brief(node, "Commit work.", skill)
        parts = result.split("\n\n")
        assert len(parts) == 2
        assert parts[0] == "/goal-task-commit"
        assert parts[1] == "Commit work."


# ---------------------------------------------------------------------------
# compose_brief — non-skill (agent) agent_ref
# ---------------------------------------------------------------------------

class TestComposeBriefAgentRef:
    def test_agent_does_not_get_slash_prefix(self):
        node = _make_node(agent_ref="pipeline-scout")
        agent = _make_agent_entry(name="pipeline-scout")
        result = compose_brief(node, "Analyse {target}.", agent)
        assert not result.startswith("/")

    def test_agent_ref_embedded_in_brief(self):
        node = _make_node(agent_ref="pipeline-scout")
        agent = _make_agent_entry(name="pipeline-scout")
        result = compose_brief(node, "Analyse {target}.", agent)
        assert "pipeline-scout" in result

    def test_agent_header_format(self):
        node = _make_node(agent_ref="tester")
        agent = _make_agent_entry(name="tester")
        result = compose_brief(node, "Run tests.", agent)
        lines = result.split("\n")
        assert lines[0] == "Agent: tester"

    def test_agent_header_separated_from_prompt(self):
        node = _make_node(agent_ref="tester")
        agent = _make_agent_entry(name="tester")
        result = compose_brief(node, "Run tests.", agent)
        parts = result.split("\n\n")
        assert len(parts) == 2
        assert parts[0] == "Agent: tester"
        assert parts[1] == "Run tests."


# ---------------------------------------------------------------------------
# compose_brief — agent_entry=None (unresolved agent_ref)
# ---------------------------------------------------------------------------

class TestComposeBriefNoneEntry:
    def test_none_entry_does_not_raise(self):
        node = _make_node(agent_ref="unknown-agent")
        result = compose_brief(node, "Do something.", None)
        assert isinstance(result, str)

    def test_none_entry_still_includes_agent_ref(self):
        node = _make_node(agent_ref="unknown-agent")
        result = compose_brief(node, "Do something.", None)
        assert "unknown-agent" in result

    def test_none_entry_no_slash_prefix(self):
        node = _make_node(agent_ref="unknown-agent")
        result = compose_brief(node, "Do something.", None)
        assert not result.startswith("/")

    def test_none_entry_header_format(self):
        node = _make_node(agent_ref="unknown-agent")
        result = compose_brief(node, "Do something.", None)
        lines = result.split("\n")
        assert lines[0] == "Agent: unknown-agent"

    def test_none_entry_prompt_included(self):
        node = _make_node(agent_ref="unknown-agent")
        prompt = "This is the interpolated prompt text."
        result = compose_brief(node, prompt, None)
        assert prompt in result

    def test_none_entry_empty_agent_ref_returns_prompt_only(self):
        """When agent_ref is empty AND entry is None, return prompt-only brief."""
        node = _make_node(agent_ref="")
        result = compose_brief(node, "Only the prompt.", None)
        assert result == "Only the prompt."


# ---------------------------------------------------------------------------
# compose_brief — interpolated_prompt always present
# ---------------------------------------------------------------------------

class TestComposeBriefPromptIncluded:
    def test_prompt_in_skill_brief(self):
        node = _make_node(agent_ref="goal-task-commit")
        skill = _make_skill_entry(name="goal-task-commit")
        prompt = "Commit changes for task ABC."
        result = compose_brief(node, prompt, skill)
        assert prompt in result

    def test_prompt_in_agent_brief(self):
        node = _make_node(agent_ref="tester")
        agent = _make_agent_entry(name="tester")
        prompt = "Run all pytest tests and report."
        result = compose_brief(node, prompt, agent)
        assert prompt in result

    def test_empty_prompt_skill_brief_is_just_prefix(self):
        node = _make_node(agent_ref="goal-task-commit")
        skill = _make_skill_entry(name="goal-task-commit")
        result = compose_brief(node, "", skill)
        assert result == "/goal-task-commit"

    def test_empty_prompt_agent_brief_is_just_header(self):
        node = _make_node(agent_ref="tester")
        agent = _make_agent_entry(name="tester")
        result = compose_brief(node, "", agent)
        assert result == "Agent: tester"


# ---------------------------------------------------------------------------
# compose_brief — return type
# ---------------------------------------------------------------------------

class TestComposeBriefReturnType:
    def test_returns_str_for_skill(self):
        node = _make_node(agent_ref="goal-task-commit")
        skill = _make_skill_entry(name="goal-task-commit")
        assert isinstance(compose_brief(node, "prompt", skill), str)

    def test_returns_str_for_agent(self):
        node = _make_node(agent_ref="pipeline-scout")
        agent = _make_agent_entry(name="pipeline-scout")
        assert isinstance(compose_brief(node, "prompt", agent), str)

    def test_returns_str_for_none_entry(self):
        node = _make_node(agent_ref="missing")
        assert isinstance(compose_brief(node, "prompt", None), str)

    def test_returns_str_for_no_agent_ref(self):
        node = _make_node(agent_ref="")
        assert isinstance(compose_brief(node, "prompt", None), str)


# ---------------------------------------------------------------------------
# compose_brief — node with no agent_ref key in data
# ---------------------------------------------------------------------------

class TestComposeBriefMissingAgentRef:
    def test_missing_agent_ref_key_handled(self):
        """HarnessNode.data without 'agent_ref' key should not raise."""
        node = HarnessNode(
            id="n_bare",
            type=NodeType.agent,
            position=Position(x=0.0, y=0.0),
            data={"prompt_template": "Do something."},
        )
        result = compose_brief(node, "Do something.", None)
        assert isinstance(result, str)
        assert result == "Do something."

    def test_missing_agent_ref_key_with_entry_is_agent_type(self):
        """If data has no agent_ref but entry is provided, we still compose cleanly."""
        node = HarnessNode(
            id="n_bare2",
            type=NodeType.agent,
            position=Position(x=0.0, y=0.0),
            data={},
        )
        agent = _make_agent_entry(name="pipeline-scout")
        result = compose_brief(node, "Run scout.", agent)
        # Without agent_ref key, header falls back to empty → prompt-only
        assert result == "Run scout."
