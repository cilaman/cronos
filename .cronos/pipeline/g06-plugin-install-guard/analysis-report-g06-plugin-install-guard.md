---
cc_version: '1.0'
agent: pipeline-analyst
slug: g06-plugin-install-guard
phase: analysis
status: done
confidence: 0.9
inputs_used:
- memory:project-remediation-board-setup
- memory:project-plugin-management-board-setup
- memory:project-plugin-frontend-i1-impl
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- .claude/agents/pipeline-analyst.md
- backend/app/agent.py
- .claude/settings.json
- backend/app/tools/plugins.py
- frontend/src/pages/SpaceToolsPage.tsx
outputs_produced:
- .cronos/pipeline/g06-plugin-install-guard/analysis-report-g06-plugin-install-guard.md
blockers: []
next_consumer: design
request: 'G06: Enforce human-approved plugin install (Bash guard + provenance). Makes
  the human-UI-only plugin install intent a real security boundary. After: An agent
  attempting `claude plugin install/enable/…` via Bash is BLOCKED (tested). Plugin
  mutation succeeds only through the human UI/API path. Plugin source/provenance is
  shown in the UI. Trust boundary is documented (feeds G12). Currently agents have
  bare Bash + the claude CLI + root, so prompt-injection can install plugins bypassing
  the UI entirely. This goal closes that specific bypass.'
has_ui: true
coverage_summary:
  searched:
  - backend/app/agent.py (DEFAULT_TOOLS, acceptEdits, workspace settings merge)
  - backend/app/tools/plugins.py (mutation ops, input validation, PluginCliError)
  - .claude/settings.json (allow list, no deny list confirmed)
  - frontend/src/pages/SpaceToolsPage.tsx (PluginsPanel reference, ScopeBadge)
  - .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md (G06
    §)
  - .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
  excluded:
  - backend/app/api/plugins.py: delegator-only; governed by plugins.py
  - backend/app/models.py: schema already confirmed in memory
  - frontend/src/components/PluginsPanel.tsx: not in scope files; referenced by SpaceToolsPage
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: The `.claude/settings.json` `permissions.deny` list must contain entries
    that block all `claude plugin` mutation subcommands (install, enable, disable,
    uninstall, marketplace add, marketplace remove) from being invoked via an agent
    Bash tool call.
  acceptance_criteria:
  - A `deny` entry using the pattern `Bash(claude plugin*)` or equivalent per-subcommand
    patterns is present in `.claude/settings.json` under `permissions.deny`.
  - The deny entry syntax is verified against the installed claude CLI version (e.g.
    via `claude --help | grep -A2 denied-tools`).
  - Given an agent running with the configured settings, when the agent Bash tool
    attempts `claude plugin install <id>`, the CLI permission system rejects the call
    with a permission-denied error.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R2
  statement: When `_run_agent_body()` composes per-workspace settings and writes them
    to the workspace `.claude/settings.json`, the global `permissions.deny` entries
    from the project settings are preserved and not overridden.
  acceptance_criteria:
  - The settings merge function (`_merge_settings` or equivalent in `agent.py`) combines
    deny entries additively (union, not last-write-wins).
  - No code path in `_run_agent_body()` or `_write_workspace_settings()` clobbers
    the deny list.
  - A task running in `auto` or `plan` mode inherits the deny list from project settings.
  verifying_phase: review
  confidence: 0.85
- requirement_id: R3
  statement: Automated tests verify that the Bash deny guard fires on all plugin mutation
    command forms and that the human API path (backend/app/api/plugins.py) continues
    to succeed.
  acceptance_criteria:
  - 'Tests cover at least: `claude plugin install`, `claude plugin enable`, `claude
    plugin disable`, `claude plugin uninstall`, `claude plugin marketplace add`.'
  - Each blocked command test asserts a permission-denied outcome (non-zero exit or
    tool-rejection event) rather than silent success.
  - At least one test confirms that `POST /api/plugins/install` via the API still
    succeeds (guard only blocks the Bash path, not the FastAPI path).
  verifying_phase: test
  confidence: 0.88
- requirement_id: R4
  statement: The plugin management UI (`PluginsPanel` in `SpaceToolsPage.tsx`) displays
    plugin provenance — marketplace source URL, install path, and installed-at timestamp
    — for each installed plugin.
  acceptance_criteria:
  - Given a plugin with non-null `marketplace`, `installPath`, and `installedAt` fields,
    the `PluginsPanel` renders these values visibly alongside the plugin name.
  - A plugin with null provenance fields shows a 'source unknown' or 'unverified'
    indicator rather than a blank.
  - The display is consistent with the existing `ScopeBadge` and `ToolDetailPanel`
    styling conventions.
  verifying_phase: review
  confidence: 0.88
- requirement_id: R5
  statement: Plugin install and marketplace-add operations in `backend/app/tools/plugins.py`
    enforce a trusted-source allowlist, rejecting requests for sources not on the
    list.
  acceptance_criteria:
  - A `TRUSTED_MARKETPLACE_SOURCES` allowlist constant (or equivalent configurable
    mechanism) is introduced in `plugins.py` or its call site in `plugins.py`.
  - The `install()` function validates that the plugin's marketplace source is on
    the allowlist before proceeding; raises `ValueError` (→ 422) if not.
  - The `add_marketplace()` function validates that the new source URL is on the allowlist;
    raises `ValueError` (→ 422) if not.
  - The allowlist has a sensible default (e.g. the official Anthropic marketplace
    URL); it is configurable via an environment variable for self-hosted scenarios.
  verifying_phase: test
  confidence: 0.82
- requirement_id: R6
  statement: The Bash guard + UI-only mutation trust boundary is documented in a brief
    artifact that can feed the G12 security-posture note.
  acceptance_criteria:
  - 'A documentation artifact (inline comment block, ADR stub, or SECURITY note section)
    describes: (a) the deny-list entry that enforces the boundary, (b) which paths
    remain open (the FastAPI plugin API), and (c) the residual risk note that G03
    (non-root) contains the broader shell risk.'
  - 'The artifact references the relevant source locations: `.claude/settings.json`,
    `backend/app/tools/plugins.py`, and `backend/app/api/plugins.py`.'
  verifying_phase: review
  confidence: 0.92
metrics:
  tool_calls: 10
  files_read: 7
  memory_hits: 3
---

## Summary

G06 closes the gap between the stated policy (humans approve plugin installs via the UI) and actual enforcement (agents currently have bare `Bash` + the `claude` CLI + root, so prompt-injection or a rogue task can bypass the UI gate entirely). The fix has two halves: a **Bash guard** (deny-list entry in `.claude/settings.json` blocking `claude plugin` mutation subcommands from agent tool calls) and a **provenance upgrade** (surfacing source URL, install path, and a trusted-marketplace allowlist in the UI and API layer). Six requirements cover the guard, its non-bypassability via workspace settings, a test harness, UI provenance display, server-side allowlist enforcement, and a documentation artifact for G12.

## Scope

### In scope
- Adding a `permissions.deny` entry to `.claude/settings.json` blocking `Bash(claude plugin*)` mutation commands
- Verifying that the workspace settings merge in `agent.py` preserves deny entries (R2)
- Automated tests asserting the deny guard fires and the API path still succeeds (R3)
- Adding provenance display (marketplace source, install path, installed-at) to the PluginsPanel UI (R4)
- Server-side trusted-marketplace allowlist in `plugins.py` for `install()` and `add_marketplace()` (R5)
- A documentation artifact describing the trust boundary (R6, as source material for G12)

### Out of scope
- Removing `Bash` from `DEFAULT_TOOLS` entirely — agents legitimately need shell access; this goal narrows one specific class of commands
- G03 non-root / capability drop — broader containment, separate goal
- Restricting any other `claude` CLI subcommands beyond `plugin` mutations
- Multi-user or multi-tenant plugin scoping

### Deferred
- PreToolUse hook as an alternative guard mechanism — viable fallback if the deny-list pattern syntax proves unsupported on the deployed CLI version; the architect should decide based on the verified CLI capabilities
- Cryptographic verification of plugin integrity (signed packages) — beyond personal-project scope
- Audit log of plugin mutations (who installed what, when) — useful future hardening

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Bash deny-list in settings.json blocks all `claude plugin` mutation subcommands |
| R2 | Workspace settings merge preserves deny entries (not clobbered by `_run_agent_body`) |
| R3 | Tests assert deny guard fires on plugin mutations; API path still succeeds |
| R4 | PluginsPanel UI shows provenance: marketplace source, install path, installed-at |
| R5 | Server-side trusted-marketplace allowlist in `plugins.py` gates install and add-marketplace |
| R6 | Trust boundary documented as feed material for G12 security-posture note |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). Compact summary below.

- R1 — `permissions.deny` entry `Bash(claude plugin*)` (or per-subcommand equivalents) present and CLI-verified; `claude plugin install` blocked in a test.
- R2 — Merge logic in `_run_agent_body` is additive for deny entries; no task mode can clobber the global deny list.
- R3 — Test suite covers all five mutation command forms (install, enable, disable, uninstall, marketplace-add) as blocked; also confirms API path unblocked.
- R4 — `PluginsPanel` renders `marketplace`, `installPath`, `installedAt` per entry; missing fields show 'source unknown'.
- R5 — `TRUSTED_MARKETPLACE_SOURCES` allowlist (env-configurable) gates `install()` and `add_marketplace()`; unlisted source → 422.
- R6 — Doc artifact names the deny-list entry, the surviving API path, and the residual risk note; references are to the three source files.

## Traceability

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | `permissions.deny` in settings.json blocks all `claude plugin` mutation subcommands from Bash |
| R2 | review | Workspace settings merge preserves deny entries across all agent modes |
| R3 | test | Tests assert deny fires on all mutation forms; API path remains open |
| R4 | review | PluginsPanel displays provenance fields; missing fields show 'source unknown' |
| R5 | test | Trusted-marketplace allowlist in plugins.py rejects unlisted sources with 422 |
| R6 | review | Documentation artifact describes trust boundary and feeds G12 |

## Assumptions

- **Deny syntax**: The installed `claude` CLI (bundled at `backend/Dockerfile:15`) supports the `Bash(claude plugin*)` glob pattern in `permissions.deny`. The CLI `--help` output confirmed `--denied-tools` accepts patterns like `"Bash(git *)"`, so glob matching for subcommand prefixes is expected to work. The architect MUST verify the exact pattern by running `claude --denied-tools 'Bash(claude plugin*)' --print '' 2>&1` or equivalent in the container before committing the deny entry.
- **Merge is additive**: agent.py lines 240–243 show `if merged_deny: merged_perms["deny"] = merged_deny`, suggesting deny lists are assembled from multiple sources. The precise merge logic for the global project settings vs. workspace settings was not fully traced in this analysis — R2 requires the architect to confirm additive union behaviour.
- **PluginsPanel exists**: `SpaceToolsPage.tsx` imports `PluginsPanel` from a component not in the declared scope files. The component exists (confirmed by memory entry `project-plugin-frontend-i1-impl`). R4 targets that component without having read its implementation.
- **Allowlist configurable via env**: R5 assumes a simple env-var allowlist (`TRUSTED_MARKETPLACE_SOURCES`) is sufficient; the architect may choose a settings-file or hardcoded approach. Either is acceptable provided the default is safe.
- **has_ui = true** rationale: R4 requires changes to `SpaceToolsPage.tsx` / `PluginsPanel`; the request explicitly names the frontend plugin management UI as a scope file.
- **G03 dependency**: The remediation plan marks G06 "Enforcement contained by G03" — the Bash guard closes the plugin-specific bypass; G03 (non-root, cap-drop, egress) bounds the broader arbitrary-shell-as-root risk. G06 does not wait for G03 but is strengthened by it.

## Open questions

- None that block proceeding to design. The residual uncertainty (exact deny-list glob syntax) is an architect-level verification task called out in the R1 acceptance criteria.

## Next consumer brief

**Design agent — read first:** `traceability[]` (6 requirements), `has_ui: true`, `## Scope`.

**Key design decision points:**

1. **Deny syntax verification** (R1): Before designing the settings.json entry, run the installed CLI in the container to confirm `Bash(claude plugin*)` fires correctly. If glob matching is not supported, the fallback is a `PreToolUse` hook in `.claude/settings.json` with a shell script that pattern-matches the command string and exits 1 for plugin mutations.

2. **Settings merge trace** (R2): Trace `_merge_settings()` / `_write_workspace_settings()` in `backend/app/agent.py` to confirm deny entries from the project settings are carried through. The deny key may be absent from the merge currently; if so, a one-line fix in the merge function is the patch.

3. **allowlist bootstrapping** (R5): A single env var `TRUSTED_MARKETPLACE_SOURCES` (comma-separated URLs) with default `https://marketplace.claudeai.com` (verify actual Anthropic marketplace URL) is the minimal viable approach. Validate in `install()` by checking the installed plugin's `marketplace` source against the list; validate in `add_marketplace()` against the `source` arg.

4. **PluginsPanel changes** (R4): The component imports confirm the `PluginEntry` model already has `marketplace`, `installPath`, and `installedAt` fields (confirmed by `project-plugin-frontend-i1-impl`). The design task is rendering them — likely extending the existing card layout used in the `PluginsPanel`.

5. **No new API endpoints**: All six requirements are satisfied by settings changes, minimal logic additions to `plugins.py`, UI edits, and one doc artifact. No new routes or models are required.
