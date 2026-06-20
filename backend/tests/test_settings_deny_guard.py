"""Test that .claude/settings.json deny list covers all claude plugin mutation commands."""
from __future__ import annotations

import json
import re
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent.parent.parent / ".claude" / "settings.json"

# All Bash mutation command strings an agent could attempt
MUTATION_COMMANDS = [
    "claude plugin install some-plugin",
    "claude plugin uninstall some-plugin",
    "claude plugin enable some-plugin",
    "claude plugin disable some-plugin",
    "claude plugin marketplace add https://example.com",
    "claude plugin marketplace remove mymarket",
]


def _deny_pattern_matches(pattern: str, command: str) -> bool:
    """Return True if a deny pattern covers a command string.

    Pattern form: Bash(prefix:*) or Bash(prefix)
    Matches if the command string starts with the prefix.
    """
    m = re.match(r"^Bash\((.+?)(?::\*)?\)$", pattern)
    if not m:
        return False
    prefix = m.group(1)
    return command.startswith(prefix)


def test_settings_file_exists():
    assert SETTINGS_PATH.exists(), f"Settings file not found at {SETTINGS_PATH}"


def test_deny_list_present():
    settings = json.loads(SETTINGS_PATH.read_text())
    perms = settings.get("permissions", {})
    deny = perms.get("deny", [])
    assert isinstance(deny, list) and deny, "permissions.deny must be a non-empty list"


def test_all_deny_patterns_are_bash_scoped():
    settings = json.loads(SETTINGS_PATH.read_text())
    deny_patterns = settings.get("permissions", {}).get("deny", [])
    for p in deny_patterns:
        assert p.startswith("Bash("), f"Deny pattern {p!r} is not Bash-scoped"


def test_all_mutation_commands_are_denied():
    settings = json.loads(SETTINGS_PATH.read_text())
    deny_patterns = settings.get("permissions", {}).get("deny", [])

    uncovered = [
        cmd
        for cmd in MUTATION_COMMANDS
        if not any(_deny_pattern_matches(p, cmd) for p in deny_patterns)
    ]

    assert not uncovered, (
        "These plugin mutation commands are not covered by any deny pattern:\n"
        + "\n".join(f"  {c}" for c in uncovered)
    )


def test_read_only_commands_not_in_deny():
    """list subcommands must not be blocked — they are used by the backend read path."""
    settings = json.loads(SETTINGS_PATH.read_text())
    deny_patterns = settings.get("permissions", {}).get("deny", [])

    read_only = [
        "claude plugin list --available --json",
        "claude plugin marketplace list --json",
    ]
    blocked = [
        cmd
        for cmd in read_only
        if any(_deny_pattern_matches(p, cmd) for p in deny_patterns)
    ]
    assert not blocked, (
        "Read-only plugin commands must not be denied (backend uses them):\n"
        + "\n".join(f"  {c}" for c in blocked)
    )
