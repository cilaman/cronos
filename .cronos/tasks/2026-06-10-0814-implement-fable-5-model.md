---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-10T08:14:36Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-10-0814-implement-fable-5-model
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: 2026-06-10-0805-fable-5-model
space_id: cronos-development
state: archived
title: 'Implement: Fable 5 model'
type: goal
updated_at: '2026-06-17T09:30:17Z'
waiting_question: null
---

# Brief

Add support for the newly released Anthropic model "Fable 5" (model ID: claude-fable-5) across the Cronos platform.

## Context

Cronos allows tasks and harness nodes to run with different Claude models. Model support requires changes in four layers:
1. Backend type definitions (AgentModel Literal + VALID_AGENT_MODELS)
2. Backend API validation (Literal types in request bodies)
3. Backend agent execution (CLI model name mapping)
4. Frontend type definitions and UI dropdown

## Scope

Files to modify:
-  — add "fable-5" to AgentModel Literal
-  — add to VALID_AGENT_MODELS tuple
-  — add to Literal in CreateTaskBody and UpdateTaskBody
-  — add fable-5 → claude-fable-5 to _MODEL_CLI_NAMES
-  — add to AgentModel type and AGENT_MODELS array

## Acceptance criteria
- Users can select "Fable 5" in task creation and editing UI dropdowns
- Backend accepts and stores "fable-5" as a valid agent_model value
- Agent execution passes --model claude-fable-5 to the Claude Code CLI when fable-5 is selected
- Existing backend and frontend tests pass; new tests cover fable-5 validation

# History

```
2026-06-10T08:57:30Z [agent]
All tasks complete. Completed 5, skipped 0 already-done.
```
