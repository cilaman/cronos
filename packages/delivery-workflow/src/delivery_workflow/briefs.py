"""delivery_workflow.briefs — shared brief-composition helpers.

Both brief composers build from these helpers — the package reference
executor (``local_executor.compose_brief``) and any host brief composer — so
the sections a child agent depends on cannot drift between runtimes:

- ``load_agent_definition`` — the bundled role definition for an agent ref
  (``agents/<ref>.md``, frontmatter stripped).
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
