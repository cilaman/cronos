---
agent_mode: auto
agent_model: haiku
claude_session_id: null
created_at: '2026-06-19T14:08:46Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-19-1408-scout-plugin-management
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
title: scout – plugin-management
type: task
updated_at: '2026-06-19T14:08:46Z'
waiting_question: null
---

# Brief

CC-v1 scout phase. Research all files relevant to the Claude Code plugin management feature.

## Setup — FIRST ACTION

Run `/goal-branch-setup` as the very first action. This is the first code-modifying task in the goal tree; it creates and checks out the feature branch `feature/implement-plugin-management`.

## Research scope

Explore these key areas and record exact line numbers for all integration points:

**Backend:**
- `backend/app/tools/scanner.py` — `_scan_category`, `_scan_skills` function signatures and logic to reuse for plugin component enumeration
- `backend/app/tools/` directory — module structure (discovery.py, adoption.py, index.py); understand the module layout
- `backend/app/agent.py` — subprocess spawning pattern: how it uses list args, `cwd`, `env`; timeout handling
- `backend/app/models.py` — existing model patterns (AiToolEntry, TaskSummary, etc.); where to add new models
- `backend/app/api/tools.py` — `get_space_tools` function (line numbers); how agents/skills are assembled and returned; where to inject plugin components
- `backend/app/harnesses/brief_composer.py` — `compose_brief`, `_is_skill` logic; how `agent_ref` resolves to AiToolEntry; verify executor's agent_ref→AiToolEntry lookup to see if it matches on namespaced `name`
- `backend/app/main.py` — router registration pattern; all existing router imports and `include_router` calls

**Frontend:**
- `frontend/src/types.ts` — existing type patterns (AiToolEntry equivalent, TaskSummary fields)
- `frontend/src/api.ts` — existing API helpers; `spaceTools` function; `taskFileUrl`, `spaceFileUrl` patterns
- `frontend/src/hooks/useHarnesses.ts` — React Query mutation pattern (useCreateHarness, useSaveHarness) to mirror in usePlugins.ts
- `frontend/src/pages/SpaceToolsPage.tsx` — Tab union definition (line ~364-366); TABS array; DiscoveryPanel rendering pattern (line ~512); space selector hide/show logic
- `frontend/src/components/DiscoveryPanel.tsx` — SectionHeader, SectionEmptyState styling conventions; card patterns; enable/disable UI patterns
- `frontend/src/components/harness/VariableInspector.tsx` — agent_ref field (line ~42); current input type; spaceTools fetch/usage

**CLI output format:**
- Run `claude plugin list --available --json 2>/dev/null || echo "not available"` and document the exact JSON schema
- Run `claude plugin marketplace list --json 2>/dev/null || echo "not available"` and document schema
- Note any differences between installed and available plugin entry shapes

## Output

Emit `.cronos/pipeline/plugin-management/scout-report-plugin-management.md` (class=research) covering:
- File-by-file integration points with exact line numbers
- CLI JSON schema (installed entry fields: id, version, scope, enabled, installPath, installedAt, lastUpdated; available entry fields: pluginId, name, description, marketplaceName, source, installCount)
- Scanner helper function signatures for reuse
- Existing model patterns that plugin models should mirror
- Frontend Tab/panel pattern details
- Brief list of risks (subprocess injection defense, asyncio.Lock for mutations, network requirement for install)

## Gate

```
GOAL_SLUG=plugin-management PHASE=scout AGENT=pipeline-scout UPSTREAM_TASK_ID=$TASK_ID /pipeline-gate
```

## Commit

After gate passes: `/goal-task-commit`

# History
