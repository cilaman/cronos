---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-29T17:29:46Z'
depends_on: []
id: 2026-05-29-1729-add-claude-opus-4-8-as-explicit-model-op
manual_order: 0
parent_id: 2026-05-29-1642-opus-4-8-support
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: Add claude-opus-4-8 as explicit model option
type: task
updated_at: '2026-05-29T17:29:46Z'
waiting_question: null
---

# Brief

Add `claude-opus-4-8` as an explicitly selectable model in Cronos so users can target it directly (rather than relying on the `opus` alias which follows the latest).

## Background

The current model system uses coarse aliases: `"default" | "sonnet" | "opus" | "haiku"`. When `"opus"` is used, `agent.py` passes `--model opus` to the CLI which maps to the latest opus model. This task adds a versioned option alongside the existing alias.

**Important:** `agent.py:243` currently passes `task.agent_model` directly as `--model <value>`. A new mapping dict is needed because the internal key `"opus-4-8"` must translate to the full CLI model ID `"claude-opus-4-8"`.

## Changes required

### `backend/app/models.py` line 19
Add `"opus-4-8"` to `AgentModel = Literal["default", "sonnet", "opus", "haiku", "opus-4-8"]`

### `backend/app/storage.py` line 21
Add `"opus-4-8"` to `VALID_AGENT_MODELS` tuple.

### `backend/app/api/tasks.py` lines 81 and 93
Update both `Literal["default", "sonnet", "opus", "haiku"]` annotations to include `"opus-4-8"`.

### `backend/app/agent.py` around line 243
Add a mapping dict so short keys translate to full CLI model IDs:


### `frontend/src/types.ts` lines 74-81
Add `"opus-4-8"` to the `AgentModel` union type and add `{ value: "opus-4-8", label: "Opus 4.8" }` to the `AGENT_MODELS` array.

## Acceptance

- A task can be created/updated with `agent_model: "opus-4-8"`.
- The backend sends `--model claude-opus-4-8` to the CLI when opus-4-8 is selected.
- The frontend model selector shows "Opus 4.8" as a choice.
- Backend tests pass (60% coverage floor).
- Frontend build succeeds with no TypeScript errors.

# History
