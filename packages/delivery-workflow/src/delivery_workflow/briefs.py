"""delivery_workflow.briefs — shared brief-composition helpers.

Both brief composers build from these helpers — the package reference
executor (``local_executor.compose_brief``) and any host brief composer — so
the sections a child agent depends on cannot drift between runtimes:

- ``load_agent_definition`` — the bundled role definition for an agent ref
  (``agents/<ref>.md``, frontmatter stripped).
- ``load_skill_definition`` / ``paired_skill_section`` — the bundled paired
  skill (``skills/<name>/SKILL.md``) inlined into the brief.  Role
  definitions say "Load the ``<name>`` skill" but children run in project
  workspaces where the packaged skills are not installed — inlining is the
  only delivery path, otherwise the method (artifact header spec included)
  silently never reaches the agent.
- ``return_contract`` — the ``node_status`` fence instruction with the closed
  status vocabulary.  This IS the pipeline's only recognized completion
  signal (``results.agent_result_from_envelope``); a child that never hears
  it can only ever be classified ``failed``.
- ``upstream_scope_section`` — the typed upstream scope as sorted JSON.

Zero host knowledge, zero app.* imports (enforced by .importlinter).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from delivery_workflow.results import AGENT_STATUS_VOCAB

#: Bundled role definitions, one ``<agent_ref>.md`` per agent (YAML
#: frontmatter + body).  Anchored the same way as ``verify.SCHEMAS_DIR`` so
#: the assets resolve from the installed wheel.
AGENTS_DIR: Path = Path(__file__).resolve().parent / "agents"

#: Bundled method skills, one ``<name>/SKILL.md`` per paired skill.  Anchored
#: the same way as ``AGENTS_DIR``.
SKILLS_DIR: Path = Path(__file__).resolve().parent / "skills"

#: Agent ref → paired-skill directory name (the ``agents/README.md`` roster).
#: Scout and tester deliberately carry no paired skill.
PAIRED_SKILLS: dict[str, str] = {
    "analyst": "analysis",
    "frontend-designer": "frontend",
    "architect": "design",
    "test-architect": "test-design",
    "implementor": "implement",
    "reviewer": "code-review",
    "security-reviewer": "security-review",
    "doc-sync": "doc",
    "retro": "retro",
    "improve": "improve",
}

#: Valid agent refs — doubles as the path-traversal guard for
#: ``load_agent_definition`` (rejects ``../analyst``, ``a/b``, uppercase, …).
_AGENT_REF_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def load_agent_definition(agent_ref: str) -> str | None:
    """Return the role-definition body for *agent_ref*, or ``None``.

    Reads ``AGENTS_DIR/<agent_ref>.md`` and strips the leading YAML
    frontmatter block (``--- … ---``) plus surrounding whitespace.  Returns
    ``None`` — never raises — when the ref fails the traversal guard, the
    file does not exist, or reading fails.
    """
    if not _AGENT_REF_RE.match(agent_ref):
        return None
    try:
        text = (AGENTS_DIR / f"{agent_ref}.md").read_text(encoding="utf-8")
    except OSError:
        return None
    return _strip_frontmatter(text).strip()


def load_skill_definition(agent_ref: str) -> str | None:
    """Return the paired-skill method body for *agent_ref*, or ``None``.

    Resolves via ``PAIRED_SKILLS`` and reads ``SKILLS_DIR/<name>/SKILL.md``,
    stripping the leading YAML frontmatter block like
    ``load_agent_definition``.  Returns ``None`` — never raises — when the
    ref fails the traversal guard, has no paired skill (scout, tester), or
    reading fails.
    """
    if not _AGENT_REF_RE.match(agent_ref):
        return None
    name = PAIRED_SKILLS.get(agent_ref)
    if name is None:
        return None
    try:
        text = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    except OSError:
        return None
    return _strip_frontmatter(text).strip()


def paired_skill_section(agent_ref: str) -> str:
    """Return the inlined paired-skill brief section, or ``""``.

    The heading tells the child NOT to go hunting for the skill on disk:
    children run in project workspaces where the packaged skills do not
    exist, so a "Load the X skill" role instruction alone dead-ends and the
    method (artifact header spec included) never reaches the agent.
    """
    body = load_skill_definition(agent_ref)
    if not body:
        return ""
    name = PAIRED_SKILLS[agent_ref]
    return (
        f"## Paired skill: {name} "
        f"(inlined — do not search the filesystem for it)\n\n{body}"
    )


def return_contract(produces: str | None) -> str:
    """Return the ``## Return contract`` brief section for *produces*.

    The example fence is deliberately NOT valid JSON (unquoted ``<status>``
    placeholder): agents echo the contract verbatim in planning turns, and
    turn-tolerant transports must never credit the echo as the run's real
    envelope.
    """
    lines = [
        "## Return contract",
        "When finished, print exactly one fenced node_status block in your",
        "REPLY TEXT (the chat message) — a fence only inside an artifact file",
        "you wrote does NOT count (ending the artifact with it too is fine).",
        "Emit it AFTER all other steps, memory writes and housekeeping",
        "included — the last thing you output before ending the turn:",
        "",
        "```node_status",
        '{"status": <status>, "artifact_paths": [], '
        f'"produces": "{produces or ""}", "fields": {{}}, "open_questions": []}}',
        "```",
        "",
        f"status MUST be one of: {', '.join(sorted(AGENT_STATUS_VOCAB))}.",
        "List every file you created or modified in artifact_paths.",
        'If you are blocked on a human decision, use status "blocked" and '
        "put the question in open_questions.",
    ]
    return "\n".join(lines)


def upstream_scope_section(scope: dict[str, Any] | None) -> str:
    """Return the upstream-scope brief section, or ``""`` for an empty scope."""
    if not scope:
        return ""
    lines = [
        "## Upstream scope (outputs of completed workflow nodes)",
        "```json",
        json.dumps(scope, indent=2, sort_keys=True, default=str),
        "```",
    ]
    return "\n".join(lines)


def _strip_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[i + 1 :])
    return text
