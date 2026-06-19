---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-19T14:08:46Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-19-1408-plugin-backend-core
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-19-1408-implement-claude-code-plugin-management
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: Plugin Backend Core
type: goal
updated_at: '2026-06-19T14:08:46Z'
waiting_question: null
---

# Brief

Implement the Claude Code plugin CLI wrapper and Pydantic schemas.

## Scope (hard boundary)

- `backend/app/tools/plugins.py` (NEW)
- `backend/app/models.py` (additions only)

## Key requirements

From the plan:
- `list_plugins()` → run `claude plugin list --available --json`, parse `{installed: [...], available: [...]}` response
- `list_marketplaces()` → `claude plugin marketplace list --json`
- `plugin_components(install_path)` → reuse `_scan_category`/`_scan_skills` from scanner.py; return AiToolEntry with namespaced name `plugin-name:component-name` and scope="plugin"
- Mutation functions: `install(plugin_id, scope="user")`, `uninstall(plugin_id)`, `enable(plugin_id)`, `disable(plugin_id)`, `add_marketplace(source)`, `remove_marketplace(name)`
- All mutations: serialized via asyncio.Lock; validate plugin_id/name/source against strict regex (defense-in-depth); capture stdout/stderr; surface failures as structured errors
- All subprocess calls: list args, no shell=True, explicit cwd/env

Pydantic models to add to models.py:
- `PluginComponent` (name, kind: "agent"|"skill"|"command")
- `PluginEntry` (id, name, marketplace, version, scope, enabled, components: list[PluginComponent])
- `MarketplacePluginEntry` (pluginId, name, description, marketplaceName, source, installCount)
- `MarketplaceEntry` (name, source)
- `PluginsResponse` (installed: list[PluginEntry], available: list[MarketplacePluginEntry], marketplaces: list[MarketplaceEntry])

## Feature branch

All tasks in this goal tree share `feature/implement-plugin-management`.

# History
