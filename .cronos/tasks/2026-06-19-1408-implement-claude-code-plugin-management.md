---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-19T14:08:46Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-19-1408-implement-claude-code-plugin-management
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: Implement Claude Code Plugin Management
type: goal
updated_at: '2026-06-19T14:08:46Z'
waiting_question: null
---

# Brief

Implement a Plugin Management system in Cronos that allows users to view, install, uninstall, enable, and disable Claude Code plugins within the container runtime. Also expose enabled plugin skills/agents as selectable agent_ref options in the harness editor.

## Background

`claude plugin list --json` returns installed plugins with enabled state; `claude plugin list --available --json` adds the full marketplace catalog. Plugin state also lives under `~/.claude/plugins/`. Cronos's container volume `/root/.claude` is the target (not the host `~/.claude`).

## Sub-Goals

1. **plugin-backend-core** — CLI wrapper (`backend/app/tools/plugins.py`) + Pydantic schemas (`backend/app/models.py`)
2. **plugin-api-integration** — API router (`backend/app/api/plugins.py`) + main.py registration + tools index integration + brief_composer plugin-namespaced refs
3. **plugin-frontend** — Frontend types/api/hooks (`types.ts`, `api.ts`, `usePlugins.ts`), PluginsPanel component, SpaceToolsPage tab addition, VariableInspector agent_ref picker

## Feature Branch

`feature/implement-plugin-management` — all sub-goals share this branch.

# History
