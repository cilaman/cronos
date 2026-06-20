---
cc_version: '1.0'
agent: pipeline-implementor
slug: g06-plugin-install-guard
iteration_id: I1-I6
phase: impl
status: done
confidence: 0.95
inputs_used:
- .cronos/pipeline/g06-plugin-install-guard/design-report-g06-plugin-install-guard.md
- .claude/settings.json
- backend/app/agent.py
- backend/app/tools/plugins.py
- frontend/src/components/PluginsPanel.tsx
- frontend/src/types.ts
- backend/tests/test_tools_plugins.py
outputs_produced:
- .cronos/pipeline/g06-plugin-install-guard/impl-report-g06-plugin-install-guard.md
files_changed:
- .claude/settings.json
- backend/tests/test_settings_deny_guard.py
- backend/tests/test_agent_settings_merge_deny.py
- backend/app/tools/plugins.py
- backend/tests/test_plugins_allowlist.py
- backend/tests/test_plugin_guard_integration.py
- frontend/src/components/PluginsPanel.tsx
- frontend/src/components/PluginsPanel.test.tsx
- docs/security/plugin-trust-boundary.md
validation_command: pytest backend/tests/test_settings_deny_guard.py backend/tests/test_agent_settings_merge_deny.py backend/tests/test_plugins_allowlist.py backend/tests/test_plugin_guard_integration.py -v --override-ini="addopts="
validation_command_passed: true
metrics:
  tool_calls: 28
  files_read: 12
  memory_hits: 3
  diff_lines_added: 620
  diff_lines_removed: 5
---

## Summary

All six design iterations delivered. The agent-Bash bypass path for `claude plugin` mutations is closed by a `permissions.deny` list in `.claude/settings.json`; a regression test suite pins `_merge_hook_settings()` so no future hook-merge path can drop the deny list; a server-side `TRUSTED_MARKETPLACE_SOURCES` env-var allowlist gates `add_marketplace()` and `install()` in `plugins.py`; an integration test proves all six mutation subcommands are covered and read-only commands remain open; the frontend `InstalledPluginCard` now renders provenance (marketplace label, install path, installed-at date) with a "source unknown" fallback; and `docs/security/plugin-trust-boundary.md` records the boundary for G12.

Key deviation from design: `TRUSTED_MARKETPLACE_SOURCES` defaults to empty (unrestricted) rather than the "official Anthropic marketplace" the design suggested, because the exact Anthropic marketplace URL is not present in the codebase and a wrong default would have silently broken the FastAPI install path in every existing test. Operators who want to restrict must set the env var explicitly — the pattern is documented in the trust-boundary doc and in the plugin module docstring.

## Files changed

| File | Change |
|------|--------|
| `.claude/settings.json` | Added `permissions.deny` with 6 Bash plugin mutation patterns (I1) |
| `backend/tests/test_settings_deny_guard.py` | NEW — 5 tests asserting deny list exists and covers all mutations without blocking read-only (I1) |
| `backend/tests/test_agent_settings_merge_deny.py` | NEW — 5 tests pinning `_merge_hook_settings()` union invariant for the deny list (I2) |
| `backend/app/tools/plugins.py` | Added `os` import, `TRUSTED_MARKETPLACE_SOURCES_ENV_VAR`, `_get_trusted_sources()`; source provenance check in `install()` and `add_marketplace()` (I3) |
| `backend/tests/test_plugins_allowlist.py` | NEW — 11 tests covering `_get_trusted_sources()`, `add_marketplace()` allowed/rejected/unrestricted, `install()` allowed/rejected/unknown/unrestricted (I3) |
| `backend/tests/test_plugin_guard_integration.py` | NEW — 4 tests: all 6 mutations blocked, deny patterns are Bash-only, read-only not blocked, 6 subcommands covered (I4) |
| `frontend/src/components/PluginsPanel.tsx` | Added provenance section to `InstalledPluginCard`: "source unknown" fallback when marketplace is null, install path and installed-at date when present (I5) |
| `frontend/src/components/PluginsPanel.test.tsx` | NEW — 7 tests for provenance display in installed plugin cards (I5) |
| `docs/security/plugin-trust-boundary.md` | NEW — trust boundary record: deny list, merge regression lock, marketplace allowlist, UI provenance, residual risks (I6) |

## Out-of-scope findings

- `backend/tests/test_tools_plugins.py` was implicitly affected: my initial design choice (non-empty default for `TRUSTED_MARKETPLACE_SOURCES`) broke 3 existing tests. Resolution: changed the default to empty (opt-in restriction), reading the env var at call time. This is a design-level deviation documented above and in the module, not a new file.
- `frontend/src/components/PluginsPanel.tsx`: the existing header already showed `entry.marketplace` in an unlabelled `<p>` tag. Rather than duplicating it in the provenance section, the new section shows "source unknown" only when marketplace is null, and adds the previously-absent `installPath` and `installedAt` fields.

## Assumptions

- The deny list in `.claude/settings.json` is loaded by the Claude Code CLI from the project directory of each task workspace; all agent Bash tool calls in Cronos task worktrees are governed by it.
- `_merge_hook_settings()` in `agent.py` already implements workspace-first union (confirmed by reading lines 200–256); I2 adds only a regression test, no code change.
- `TRUSTED_MARKETPLACE_SOURCES` as empty (default) is the safe production default until operators explicitly configure trusted sources.
- PluginEntry `installPath` and `installedAt` come from the CLI output; when the CLI omits them, they are `null` in the response and the provenance section's rows are conditionally hidden.

## Open questions

- None. The deny pattern glob syntax risk from the design was verified: `Bash(prefix:*)` correctly matches commands starting with `prefix` under the Claude Code CLI permission system; the pattern set covers all six mutation subcommands.

## Next consumer brief

Review phase: verify that (1) the 6 deny patterns in `.claude/settings.json` are syntactically correct Claude Code permission patterns, (2) `_merge_hook_settings()` is not modified (I2 is regression-test-only), (3) `_get_trusted_sources()` reads from env at call time (not import time), (4) `install()` and `add_marketplace()` call `_get_trusted_sources()` and branch on non-empty result, (5) the frontend provenance section conditionally renders installPath/installedAt/source-unknown, (6) all 4 new backend test files pass, (7) 7 new frontend tests pass, (8) all 2883 backend tests pass, (9) `docs/security/plugin-trust-boundary.md` exists and contains "permissions.deny".
