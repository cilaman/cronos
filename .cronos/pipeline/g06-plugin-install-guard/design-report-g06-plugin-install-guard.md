---
cc_version: '1.0'
agent: pipeline-architect
slug: g06-plugin-install-guard
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:project-remediation-board-setup
- memory:project-plugin-frontend-i1-impl
- .cronos/pipeline/g06-plugin-install-guard/analysis-report-g06-plugin-install-guard.md
- backend/app/agent.py
- .claude/settings.json
- backend/app/tools/plugins.py
outputs_produced:
- .cronos/pipeline/g06-plugin-install-guard/design-report-g06-plugin-install-guard.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - .claude/settings.json
  - backend/app/agent.py
  - backend/app/tools/plugins.py
  - frontend/src/components/PluginsPanel.tsx
  excluded:
  - backend/app/api/plugins.py: delegator-only; governed by plugins.py and the FastAPI
      path that intentionally stays open
  - backend/app/models.py: PluginEntry provenance fields already shipped (memory:project-plugin-frontend-i1-impl)
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: infra
  scope_files:
  - .claude/settings.json
  - backend/tests/test_settings_deny_guard.py
  validation_command: pytest backend/tests/test_settings_deny_guard.py -v
  max_diff_lines: 200
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/agent.py
  - backend/tests/test_agent_settings_merge_deny.py
  validation_command: pytest backend/tests/test_agent_settings_merge_deny.py -v
  max_diff_lines: 200
  depends_on: []
- id: I3
  type: backend
  scope_files:
  - backend/app/tools/plugins.py
  - backend/tests/test_plugins_allowlist.py
  validation_command: pytest backend/tests/test_plugins_allowlist.py -v
  max_diff_lines: 300
  depends_on: []
- id: I4
  type: backend
  scope_files:
  - backend/tests/test_plugin_guard_integration.py
  validation_command: pytest backend/tests/test_plugin_guard_integration.py -v
  max_diff_lines: 250
  depends_on:
  - I1
  - I3
- id: I5
  type: frontend
  scope_files:
  - frontend/src/components/PluginsPanel.tsx
  - frontend/src/components/PluginsPanel.test.tsx
  validation_command: cd frontend && npm test -- src/components/PluginsPanel.test.tsx
  max_diff_lines: 300
  depends_on: []
- id: I6
  type: infra
  scope_files:
  - docs/security/plugin-trust-boundary.md
  validation_command: grep -q 'permissions.deny' docs/security/plugin-trust-boundary.md
  max_diff_lines: 150
  depends_on:
  - I1
  - I3
metrics:
  tool_calls: 12
  files_read: 4
  memory_hits: 2
  iterations_planned: 6
risks:
  - description: "Deny-pattern glob form (Bash(claude plugin:*) vs Bash(claude plugin *)) may not match how the bundled CLI (2.1.181) tokenizes the command, letting a mutation subcommand slip past the guard."
    severity: high
    mitigation: "I1 ships a broad prefix entry plus explicit per-subcommand deny entries (install/enable/disable/uninstall/marketplace add/remove); I1's test asserts each of the five mutation command strings is matched by at least one deny pattern, and the implementor smoke-checks the pattern with claude --disallowedTools against a sample command before committing."
  - description: "_write_workspace_settings (agent.py:356) overwrites the workspace .claude/settings.json when adopted hooks exist; a future change to _merge_hook_settings could drop the project deny list, silently disabling the guard for hook-enabled spaces."
    severity: medium
    mitigation: "I2 adds a regression test pinning _merge_hook_settings to a union of deny entries (workspace-first) so the deny list survives every merge path, including the hooks-present path."
  - description: "A too-strict TRUSTED_MARKETPLACE_SOURCES default rejects the user's own legitimate marketplace, breaking the human UI install path."
    severity: medium
    mitigation: "I3 makes the allowlist env-configurable with the official Anthropic marketplace as the default and a 422 message that names the offending source; tests cover both an allowed and a rejected source so the default is provably permissive for the intended case."
  - description: "The analysis assumes PluginsPanel exists with marketplace/installPath/installedAt field names, but the component was not in the declared scope files."
    severity: low
    mitigation: "I5 scope includes the component and its test; the implementor first greps frontend/src/types.ts to confirm PluginEntry field names before rendering, and uses the 'source unknown' fallback path for any null field."
---

## Summary

G06 turns the "humans approve plugin installs via the UI" policy into an enforced trust boundary by closing the agent-Bash bypass and adding server-side provenance controls. The design splits into three independent layer-0 tracks — a settings-level Bash deny guard (I1), a regression lock on the workspace settings merge so the deny list is never clobbered (I2), and a server-side trusted-marketplace allowlist in `plugins.py` (I3) — plus a frontend provenance display (I5) that is wholly parallel. Two convergence iterations follow: an integration test that proves all five mutation forms are blocked while the FastAPI path stays open (I4), and a doc artifact that records the boundary for G12 (I6). The DAG is deliberately wide (four group-0 iterations) since the guard, allowlist, and UI touch disjoint files. The load-bearing risk is deny-pattern glob syntax on the bundled CLI (2.1.181), mitigated by belt-and-suspenders per-subcommand entries plus a matcher-semantics test.

## Components

### Data
- `PluginEntry` provenance fields (`marketplace`, `installPath`, `installedAt`): already present (memory:project-plugin-frontend-i1-impl) — consumed read-only, not modified.

### Backend
- `.claude/settings.json` `permissions.deny`: new deny list blocking `claude plugin` mutation subcommands from the agent Bash tool (R1).
- `backend/app/agent.py` `_merge_hook_settings`: confirmed to union deny entries (workspace-first, lines 196–206); pinned by regression test so no merge path drops the project deny list (R2).
- `backend/app/tools/plugins.py` `install()` + `add_marketplace()`: env-configurable `TRUSTED_MARKETPLACE_SOURCES` allowlist; unlisted source raises `ValueError` (→ 422) (R5).
- Integration test harness asserting all mutation forms are denied and the API path remains open (R3).

### Frontend
- `frontend/src/components/PluginsPanel.tsx`: renders provenance (marketplace source, install path, installed-at) per installed plugin, with a 'source unknown' fallback for null fields (R4).

### Docs
- `docs/security/plugin-trust-boundary.md`: brief trust-boundary note naming the deny entry, the surviving FastAPI path, and the residual-risk hand-off to G03/G12 (R6).

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                          | Validation                                                      |
|-----|----------|------------|-----------------------------------------------------------------|----------------------------------------------------------------|
| I1  | infra    | -          | .claude/settings.json, backend/tests/test_settings_deny_guard.py| pytest backend/tests/test_settings_deny_guard.py -v            |
| I2  | backend  | -          | backend/app/agent.py, backend/tests/test_agent_settings_merge_deny.py | pytest backend/tests/test_agent_settings_merge_deny.py -v |
| I3  | backend  | -          | backend/app/tools/plugins.py, backend/tests/test_plugins_allowlist.py | pytest backend/tests/test_plugins_allowlist.py -v        |
| I4  | backend  | I1, I3     | backend/tests/test_plugin_guard_integration.py                  | pytest backend/tests/test_plugin_guard_integration.py -v      |
| I5  | frontend | -          | frontend/src/components/PluginsPanel.tsx, …PluginsPanel.test.tsx | cd frontend && npm test -- src/components/PluginsPanel.test.tsx |
| I6  | infra    | I1, I3     | docs/security/plugin-trust-boundary.md                          | grep -q 'permissions.deny' docs/security/plugin-trust-boundary.md |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Deny-pattern glob form (`Bash(claude plugin:*)` vs `Bash(claude plugin *)`) may not match how the bundled CLI (2.1.181) tokenizes the command, letting a mutation subcommand slip past the guard. | high | I1 ships a broad prefix entry **plus** explicit per-subcommand deny entries (install/enable/disable/uninstall/marketplace add/remove); I1's test asserts each of the five mutation command strings is matched by at least one deny pattern, and the implementor smoke-checks the pattern with `claude --disallowedTools` against a sample command before committing. |
| `_write_workspace_settings` (agent.py:356) overwrites the workspace `.claude/settings.json` when adopted hooks exist; a future change to `_merge_hook_settings` could drop the project deny list, silently disabling the guard for hook-enabled spaces. | medium | I2 adds a regression test pinning `_merge_hook_settings` to a union of deny entries (workspace-first) so the deny list survives every merge path, including the hooks-present path. |
| A too-strict `TRUSTED_MARKETPLACE_SOURCES` default rejects the user's own legitimate marketplace, breaking the human UI install path. | medium | I3 makes the allowlist env-configurable with the official Anthropic marketplace as the default and a 422 message that names the offending source; tests cover both an allowed and a rejected source so the default is provably permissive for the intended case. |
| The analysis assumes `PluginsPanel` exists with `marketplace`/`installPath`/`installedAt` field names, but the component was not in the declared scope files. | low | I5 scope includes the component and its test; the implementor first greps `frontend/src/types.ts` to confirm `PluginEntry` field names before rendering, and uses the 'source unknown' fallback path for any null field. |

## Assumptions

- **Worktree inherits the deny list**: each task workspace is a git worktree of the repo, so the committed `.claude/settings.json` (with the new deny entries) is present at the agent's `cwd`; the CLI loads it natively, so no `agent.py` change is needed for the guard to take effect in normal (no-hook) runs — only the merge-preservation regression (I2).
- **Merge is already additive (R2)**: `agent.py:196–206` shows `_merge_hook_settings` builds `merged_deny = ws_deny + [p for p in agg_deny if p not in ws_deny]`, a workspace-first union. I2 therefore is primarily a regression-lock; an actual code change in `agent.py` is included in scope only if the test surfaces a gap.
- **FastAPI path stays open by design**: `backend/app/api/plugins.py` invokes `plugins.py` coroutines in-process (not via the agent Bash tool), so the Bash deny guard does not affect it; R3's "API still succeeds" assertion targets this path.
- **Allowlist applies to provenance, not plugin_id**: R5 validation keys off the marketplace/source URL (the `source` arg of `add_marketplace` and the resolved marketplace of an installed plugin), consistent with the existing `MARKETPLACE_SOURCE_PATTERN` validation already in `plugins.py:243`.
- **`has_ui = true`**: R4 requires a frontend iteration (I5); confirmed by the analysis report and the named scope file.

## Open questions

- None. The one residual uncertainty (exact deny glob syntax) is an implementor-level verification baked into I1's acceptance, not a design blocker.

## Next consumer brief

Read `iterations[]`, each `scope_files`, and each `validation_command` from the YAML; the DAG is wide — I1/I2/I3/I5 are layer 0, I4 and I6 wait on `[I1, I3]`. Cross-iteration invariant **not** derivable from the YAML: the **exact deny pattern strings** chosen in I1 must be reused verbatim by I4's integration test and quoted verbatim in I6's doc — pick the pattern set once in I1, then reference it. I3's env var name is fixed as `TRUSTED_MARKETPLACE_SOURCES` (comma-separated URLs); I6's doc must name it. Before starting I1, verify the glob form against the bundled CLI (`claude --version` → 2.1.181; `--disallowedTools` accepts `Bash(... )` patterns) — see risk #1. I5's implementor must confirm `PluginEntry` field names in `frontend/src/types.ts` before rendering.
