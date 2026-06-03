"""
backend/app/harnesses/brief_composer — pure-function brief composition for harness nodes.

Provides:
  compose_brief(node, interpolated_prompt, agent_entry) -> str

The returned string is ready to pass directly to TaskStore.create(brief=...).

Brief format
------------
For a skill agent_ref:
    /<skill-name>

    <interpolated_prompt>

For an agent agent_ref (or when agent_entry is None / unresolved):
    Agent: <agent_ref>

    <interpolated_prompt>

The leading slash prefix is the signal to the Claude Code CLI that this task
should invoke a skill (e.g. /pipeline-gate). Only skill-category tools receive
this prefix; plain agents do not.

The agent_ref comes from HarnessNode.data["agent_ref"]. If absent or empty the
brief body consists of only the interpolated prompt.
"""

from __future__ import annotations

from ..harnesses.model import HarnessNode
from ..models import AiToolEntry


def _is_skill(agent_entry: AiToolEntry) -> bool:
    """Return True when the resolved tool entry is a skill (not a plain agent)."""
    # AiToolEntry carries a path like ".claude/skills/<name>/SKILL.md".
    # SpaceToolsResponse separates agents and skills into separate lists, but
    # compose_brief receives only the matched entry — we can identify skills by
    # the presence of "skills/" in the path string.
    return "skills/" in agent_entry.path or "/skills/" in agent_entry.path


def compose_brief(
    node: HarnessNode,
    interpolated_prompt: str,
    agent_entry: AiToolEntry | None,
) -> str:
    """Compose a child-task brief from a resolved harness node.

    Parameters
    ----------
    node:
        The HarnessNode being executed.  Its ``data`` dict may carry:
        - ``agent_ref`` (str): name of the agent/skill to invoke.
        Any other keys are ignored by this function.
    interpolated_prompt:
        The node's prompt_template after variable substitution (produced by
        ``interpolate()``).  Included verbatim in the brief body.
    agent_entry:
        The resolved ``AiToolEntry`` for ``agent_ref``, or ``None`` when the
        agent/skill could not be found in the tools index.

    Returns
    -------
    str
        A brief string ready to pass to ``TaskStore.create(brief=...)``.
    """
    agent_ref: str = node.data.get("agent_ref", "") or ""

    # --- determine prefix line -----------------------------------------------
    if agent_entry is not None and _is_skill(agent_entry):
        # Skill invocation: Claude Code CLI recognises "/<skill-name>" on the
        # first line as a skill trigger.
        skill_name = agent_entry.name
        header = f"/{skill_name}"
    elif agent_ref:
        if agent_entry is not None:
            # Resolved agent — embed by name for clarity.
            header = f"Agent: {agent_entry.name}"
        else:
            # agent_entry is None: agent_ref was provided but could not be
            # resolved.  Still embed the raw ref so downstream debugging is
            # possible; execution may mark the node as failed but compose_brief
            # itself always returns a string.
            header = f"Agent: {agent_ref}"
    else:
        # No agent_ref at all — brief is prompt-only.
        header = ""

    # --- assemble brief -------------------------------------------------------
    parts: list[str] = []
    if header:
        parts.append(header)
    if interpolated_prompt:
        parts.append(interpolated_prompt)

    return "\n\n".join(parts)
