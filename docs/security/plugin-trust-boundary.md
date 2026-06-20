# Plugin Trust Boundary

## Intent

Plugin installation and marketplace mutations are **human-UI/API only**. An agent running in a Cronos task workspace cannot install, uninstall, enable, disable, or add/remove marketplaces via the Bash tool — even though the `claude` CLI is available inside the backend container.

## How the boundary is enforced

### 1. Agent Bash deny list (`.claude/settings.json`)

The project settings file contains a `permissions.deny` list that blocks the six plugin mutation subcommands from the agent Bash tool:

```json
{
  "permissions": {
    "deny": [
      "Bash(claude plugin install:*)",
      "Bash(claude plugin uninstall:*)",
      "Bash(claude plugin enable:*)",
      "Bash(claude plugin disable:*)",
      "Bash(claude plugin marketplace add:*)",
      "Bash(claude plugin marketplace remove:*)"
    ]
  }
}
```

This deny list is loaded by the Claude Code CLI from the project directory. Any agent task running within a Cronos workspace inherits these restrictions. The patterns use prefix matching: `Bash(claude plugin install:*)` denies any Bash command starting with `claude plugin install`. Enforcement is performed by the Claude Code CLI permission system; when a tool call matches a deny pattern, the engine rejects the call before subprocess invocation.

Read-only commands (`claude plugin list --available --json`, `claude plugin marketplace list --json`) are **not** denied — the backend uses them to surface plugin state.

### 2. Merge preservation regression lock (`backend/app/agent.py`)

`_merge_hook_settings()` (lines 200–256) merges adopted hook settings with the workspace settings. Deny entries from the workspace settings are preserved first (workspace-first union); hook entries are appended without duplication. The test suite pins this behaviour: any change to the merge logic that drops the project deny list will cause `test_agent_settings_merge_deny.py` to fail.

### 3. Server-side trusted marketplace allowlist (`backend/app/tools/plugins.py`)

`TRUSTED_MARKETPLACE_SOURCES` (env var, comma-separated URLs) gates the FastAPI plugin mutation path:

- **`add_marketplace(source)`**: rejects sources not in the allowlist with `ValueError` → HTTP 422.
- **`install(plugin_id)`**: looks up the plugin in the available list; if its source URL is known and not in the allowlist, raises `ValueError` → HTTP 422. Plugins absent from the available list (unknown source) are installed without re-validation, since the marketplace source was presumably validated when it was added via `add_marketplace()`.

Default: **unset = unrestricted** (any marketplace source allowed). All plugin sources are accepted unless explicitly restricted.  
Set `TRUSTED_MARKETPLACE_SOURCES=<comma-separated URLs>` to opt into allowlist enforcement (e.g., `TRUSTED_MARKETPLACE_SOURCES=https://claude.ai/marketplace`).

### 4. Frontend provenance display (`frontend/src/components/PluginsPanel.tsx`)

Each installed plugin card now surfaces:
- **Marketplace** (source name, shown in card header; "source unknown" if null)
- **Install path** (filesystem location, if provided by the CLI)
- **Installed at** (date, if provided by the CLI)

This gives the operator visibility into where each plugin came from before approving further changes.

## What this closes

**Threat:** prompt-injection causes an agent to run `claude plugin install <malicious-plugin>` via the Bash tool, bypassing the human approval UI entirely.

**After G06:** the deny list causes the CLI permission system to reject the tool call before any subprocess is spawned. The agent sees a tool-denied response, not a subprocess error. The FastAPI path (used by the UI) is unaffected — it invokes `plugins.py` coroutines in-process, not via Bash.

## Residual risks

| Risk | Mitigant | Tracked by |
|------|----------|-----------|
| Container root + unrestricted Bash still allows arbitrary OS operations | Broader container isolation (least-privilege user, seccomp, no-new-privs) | G03 |
| Deny list only applies inside the Claude Code permission system; a compromised agent subprocess that spawns its own shell bypasses it | Container-level controls | G03 |
| `TRUSTED_MARKETPLACE_SOURCES` default allows only `claude.ai/marketplace`; operators adding private marketplaces must update the env var | Documented above | — |

This document is the trust-boundary record referenced by G12 (lightweight documentation).
