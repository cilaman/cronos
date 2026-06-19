---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-19T14:08:46Z'
depends_on:
- 2026-06-19-1408-plugin-backend-core
feature_key: null
feature_state: null
id: 2026-06-19-1408-plugin-api-integration
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
title: Plugin API & Integration
type: goal
updated_at: '2026-06-19T14:08:46Z'
waiting_question: null
---

# Brief

Implement the plugin API router and integrate plugin components into the tools index and harness brief composer.

## Scope (hard boundary)

- `backend/app/api/plugins.py` (NEW)
- `backend/app/main.py` (router registration)
- `backend/app/api/tools.py` (plugin component injection)
- `backend/app/harnesses/brief_composer.py` (plugin-namespaced ref handling)

## Key requirements

From the plan:
- 7 endpoints in plugins router:
  - `GET  /api/plugins` → PluginsResponse (installed w/ components + available + marketplaces)
  - `POST /api/plugins/install` body `{plugin_id, scope?}` → refreshed PluginsResponse
  - `POST /api/plugins/uninstall` body `{plugin_id}` → refreshed PluginsResponse
  - `POST /api/plugins/enable` body `{plugin_id}` → refreshed PluginsResponse
  - `POST /api/plugins/disable` body `{plugin_id}` → refreshed PluginsResponse
  - `POST /api/plugins/marketplaces` body `{source}` → refreshed PluginsResponse
  - `DELETE /api/plugins/marketplaces/{name}` → refreshed PluginsResponse
- Register plugin router in main.py alongside other routers
- tools.py `get_space_tools`: after global scan, append components of enabled plugins to agents/skills list (scope="plugin", namespaced names)
- brief_composer.py: plugin skill AiToolEntry (scope="plugin") → brief header `/plugin-name:skill-name`; plugin agent → `Agent: plugin-name:agent-name`; verify executor's agent_ref→AiToolEntry lookup matches on namespaced name

## Feature branch

All tasks share `feature/implement-plugin-management`.

# History
