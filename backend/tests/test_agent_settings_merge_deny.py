"""Regression test: _merge_hook_settings must preserve the deny list across all merge paths."""
from __future__ import annotations

from app.agent import _merge_hook_settings

PLUGIN_DENY_PATTERNS = [
    "Bash(claude plugin install:*)",
    "Bash(claude plugin uninstall:*)",
    "Bash(claude plugin enable:*)",
    "Bash(claude plugin disable:*)",
    "Bash(claude plugin marketplace add:*)",
    "Bash(claude plugin marketplace remove:*)",
]


def test_deny_list_preserved_with_no_hooks():
    ws = {"permissions": {"deny": PLUGIN_DENY_PATTERNS}}
    result = _merge_hook_settings([], ws)
    assert result["permissions"]["deny"] == PLUGIN_DENY_PATTERNS


def test_deny_list_preserved_when_hooks_add_allow():
    ws = {"permissions": {"deny": PLUGIN_DENY_PATTERNS}}
    hook_settings = [{"permissions": {"allow": ["Bash(npm run:*)"]}}]
    result = _merge_hook_settings(hook_settings, ws)
    assert result["permissions"]["deny"] == PLUGIN_DENY_PATTERNS
    assert "Bash(npm run:*)" in result["permissions"]["allow"]


def test_deny_list_workspace_first_union():
    """Workspace deny entries come first; hook deny entries are appended without duplication."""
    hook_deny = ["Bash(rm:*)"]
    ws = {"permissions": {"deny": PLUGIN_DENY_PATTERNS.copy()}}
    hook_settings = [{"permissions": {"deny": hook_deny}}]
    result = _merge_hook_settings(hook_settings, ws)
    result_deny = result["permissions"]["deny"]

    for p in PLUGIN_DENY_PATTERNS:
        assert p in result_deny, f"Missing deny pattern: {p!r}"
    assert "Bash(rm:*)" in result_deny
    # Workspace entries appear before hook entries
    plugin_indices = [result_deny.index(p) for p in PLUGIN_DENY_PATTERNS]
    hook_index = result_deny.index("Bash(rm:*)")
    assert all(i < hook_index for i in plugin_indices)


def test_deny_list_no_duplication():
    """Identical deny entries from hooks are not duplicated."""
    overlapping_hook_deny = PLUGIN_DENY_PATTERNS[:2]
    ws = {"permissions": {"deny": PLUGIN_DENY_PATTERNS.copy()}}
    hook_settings = [{"permissions": {"deny": overlapping_hook_deny}}]
    result = _merge_hook_settings(hook_settings, ws)
    result_deny = result["permissions"]["deny"]
    for p in overlapping_hook_deny:
        assert result_deny.count(p) == 1, f"Deny pattern {p!r} duplicated in merged result"


def test_deny_list_preserved_with_hooks_and_allow_overlap():
    """Deny list is intact even when hooks provide both allow and deny entries."""
    hook_settings = [
        {
            "permissions": {
                "allow": ["Bash(git status:*)", "Bash(git log:*)"],
                "deny": ["Bash(git push --force:*)"],
            }
        }
    ]
    ws = {"permissions": {"allow": ["Bash(pytest:*)"], "deny": PLUGIN_DENY_PATTERNS.copy()}}
    result = _merge_hook_settings(hook_settings, ws)
    result_deny = result["permissions"]["deny"]
    for p in PLUGIN_DENY_PATTERNS:
        assert p in result_deny
    assert "Bash(git push --force:*)" in result_deny
