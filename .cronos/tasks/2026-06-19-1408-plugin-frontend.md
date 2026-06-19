---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-19T14:08:46Z'
depends_on:
- 2026-06-19-1408-plugin-api-integration
feature_key: null
feature_state: null
id: 2026-06-19-1408-plugin-frontend
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
title: Plugin Frontend
type: goal
updated_at: '2026-06-19T14:08:46Z'
waiting_question: null
---

# Brief

Implement the frontend plugin management UI: types, API helpers, React Query hooks, PluginsPanel component, SpaceToolsPage tab, and VariableInspector agent_ref picker.

## Scope (hard boundary)

- `frontend/src/types.ts` (additions)
- `frontend/src/api.ts` (additions)
- `frontend/src/hooks/usePlugins.ts` (NEW)
- `frontend/src/components/PluginsPanel.tsx` (NEW)
- `frontend/src/pages/SpaceToolsPage.tsx` (tab addition)
- `frontend/src/components/harness/VariableInspector.tsx` (agent_ref picker)

## Key requirements

From the plan:
- types.ts: add PluginEntry, MarketplacePluginEntry, MarketplaceEntry, PluginsResponse, PluginComponent interfaces
- api.ts: add `plugins()`, `installPlugin`, `uninstallPlugin`, `enablePlugin`, `disablePlugin`, `addMarketplace`, `removeMarketplace` functions
- usePlugins.ts: React Query `usePlugins()` query + all mutations, invalidate the plugins query on every mutation; model on useHarnesses.ts
- PluginsPanel.tsx: three sections (Installed / Available / Marketplaces), card per plugin with enable/disable toggle, uninstall with confirmation, expandable component list, marketplace add (source URL) + remove; reuse existing SectionHeader/SectionEmptyState styling; icon vocabulary 🤖 agent, ⚡ skill, ⌘ command
- SpaceToolsPage.tsx: add `"plugins"` to Tab union and TABS array; render `<PluginsPanel />` when `activeTab === "plugins"`; plugins are runtime-global so panel ignores space selector (keep existing behavior of hiding space selector outside `installed` tab)
- VariableInspector.tsx: back agent_ref text input with `<datalist>` sourced from `api.spaceTools()` agents+skills (now including plugin components with namespaced names); keep free-text fallback

No new routes or sidebar entries needed — reached via existing /tools AI Tools nav entry.

## Feature branch

All tasks share `feature/implement-plugin-management`. The doc task of this (last) sub-goal runs `/goal-finalize` to merge to main.

# History
