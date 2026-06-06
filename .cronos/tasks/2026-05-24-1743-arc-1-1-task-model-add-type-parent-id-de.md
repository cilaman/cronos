---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-24-1743-arc-1-1-task-model-add-type-parent-id-de
manual_order: 1
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-1/1: Task model — add type, parent_id, depends_on'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Extend the `Task` model and storage layer with three optional hierarchy fields.

## Changes
1. `backend/app/models.py` — add to `Task`: `type: Literal["task","goal","issue"] = "task"`, `parent_id: str | None = None`, `depends_on: list[str] = Field(default_factory=list)`
2. `backend/app/storage.py` — round-trip these fields through the markdown frontmatter parser/serializer. Default to the values above when the frontmatter field is missing (back-compat).
3. SQLite index: add columns `type TEXT NOT NULL DEFAULT 'task'`, `parent_id TEXT NULL`, `depends_on_json TEXT NOT NULL DEFAULT '[]'` plus indices on `(space_id, parent_id)` and `(space_id, type)`. Apply the migration idempotently.
4. Update Pydantic response models in `backend/app/api/` so the new fields appear in API responses.

## Acceptance
- Existing task MD files load without modification (defaults applied).
- A task declaring `type: goal`, `parent_id: <id>`, `depends_on: [<id>]` round-trips byte-equal.
- SQLite `tasks` table has the three new columns and indices after startup.

## Standing rules
Branch: `feature/arc-1-hierarchy` from `main`. Do NOT merge to `main` — that's manual after the arc lands.
Test gate before commit: invoke the `test-architect` subagent. Only commit after green.
Commit message: `arc-1: <summary>`. STATUS: DONE on success, STATUS: BLOCKED if tests fail.

# History
