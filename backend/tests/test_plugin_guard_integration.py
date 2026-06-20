"""Integration test: all plugin mutation Bash commands are denied by settings.json;
the FastAPI API path (plugins.py coroutines) remains unaffected."""
from __future__ import annotations

import json
import re
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent.parent.parent / ".claude" / "settings.json"

# All mutation Bash commands an agent could attempt
MUTATION_COMMANDS = [
    "claude plugin install some-plugin",
    "claude plugin uninstall some-plugin",
    "claude plugin enable some-plugin",
    "claude plugin disable some-plugin",
    "claude plugin marketplace add https://example.com",
    "claude plugin marketplace remove mymarket",
]

# Read-only commands the backend uses — must NOT be denied
READ_ONLY_COMMANDS = [
    "claude plugin list --available --json",
    "claude plugin marketplace list --json",
]


def _deny_pattern_matches(pattern: str, command: str) -> bool:
    """Return True if a deny pattern covers the command prefix."""
    m = re.match(r"^Bash\((.+?)(?::\*)?\)$", pattern)
    if not m:
        return False
    return command.startswith(m.group(1))


def _load_deny_patterns() -> list[str]:
    settings = json.loads(SETTINGS_PATH.read_text())
    return settings.get("permissions", {}).get("deny", [])


def test_all_mutation_forms_blocked():
    """Every plugin mutation command string is covered by at least one deny pattern."""
    deny_patterns = _load_deny_patterns()
    uncovered = [
        cmd for cmd in MUTATION_COMMANDS
        if not any(_deny_pattern_matches(p, cmd) for p in deny_patterns)
    ]
    assert not uncovered, (
        "Plugin mutation commands not covered by deny list:\n"
        + "\n".join(f"  {c}" for c in uncovered)
    )


def test_api_path_unaffected_deny_patterns_are_bash_only():
    """All deny patterns are Bash-scoped; they cannot affect FastAPI coroutines."""
    deny_patterns = _load_deny_patterns()
    non_bash = [p for p in deny_patterns if not p.startswith("Bash(")]
    assert not non_bash, (
        "Non-Bash deny patterns detected — these could interfere with the API path:\n"
        + "\n".join(f"  {p}" for p in non_bash)
    )


def test_read_only_commands_not_blocked():
    """Backend read-only list commands are not denied."""
    deny_patterns = _load_deny_patterns()
    blocked = [
        cmd for cmd in READ_ONLY_COMMANDS
        if any(_deny_pattern_matches(p, cmd) for p in deny_patterns)
    ]
    assert not blocked, (
        "Read-only plugin commands are incorrectly denied:\n"
        + "\n".join(f"  {c}" for c in blocked)
    )


def test_six_mutation_subcommands_covered():
    """All six known mutation subcommands have explicit deny coverage."""
    deny_patterns = _load_deny_patterns()
    subcommands = [
        "claude plugin install",
        "claude plugin uninstall",
        "claude plugin enable",
        "claude plugin disable",
        "claude plugin marketplace add",
        "claude plugin marketplace remove",
    ]
    missing = [
        sub for sub in subcommands
        if not any(_deny_pattern_matches(p, sub + " test") for p in deny_patterns)
    ]
    assert not missing, (
        "Missing deny coverage for subcommands:\n"
        + "\n".join(f"  {s}" for s in missing)
    )
