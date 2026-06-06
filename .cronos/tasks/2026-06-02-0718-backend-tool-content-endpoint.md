---
agent_mode: auto
agent_model: sonnet
claude_session_id: 558e7bc2-d64a-44fd-80b3-c68ea83115f7
created_at: '2026-06-02T07:18:50Z'
depends_on: []
id: 2026-06-02-0718-backend-tool-content-endpoint
manual_order: 0
parent_id: 2026-06-02-0718-ai-tools-detail-screens
pending_messages:
- why didn't you realise tasks from this goal?
- why didn't you realise tasks from this goal?
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: Backend – Tool content endpoint
type: goal
updated_at: '2026-06-02T08:26:41Z'
waiting_question: null
---

# Brief

Add a new API endpoint that fetches the full raw content and metadata of a single AI tool file.

## What to build

File: `backend/app/api/tools.py`

Add endpoint:
```
GET /api/spaces/{space_id}/tool-content
Query params:
  path: str   (e.g. ".claude/agents/my-agent.md" or "~/.claude/agents/global-agent.md")
  scope: "space" | "global"
```

Response schema (add to `backend/app/models.py`):
```python
class AiToolDetail(BaseModel):
    name: str
    path: str
    description: str | None
    scope: Literal["space", "global"]
    modified_at: str
    category: Literal["agent", "command", "skill", "context"]
    content: str   # raw file content
```

### Security

- Resolve the absolute path.
- For `scope="space"`: path MUST be under `{space_directory}/.claude/` — reject anything that resolves outside with HTTP 400.
- For `scope="global"`: path MUST be under `~/.claude/` — same rule.
- Use `Path.resolve()` and check `str(resolved).startswith(str(allowed_root))`.
- Return HTTP 404 if the file does not exist.

### Infer category from path

- Contains `/.claude/agents/` → `"agent"`
- Contains `/.claude/commands/` → `"command"`
- Contains `/.claude/skills/` → `"skill"`
- Otherwise → `"context"`

### Wire it up

Register the new route in `backend/app/main.py` (already imports the tools router) — confirm the router is already included; no new wiring needed if tools router is already registered.

## Acceptance

- `GET /api/spaces/cronos-development/tool-content?path=.claude/agents/tester.md&scope=space` returns 200 with `content` field containing the file's text.
- Path traversal attempt (e.g. `path=../../etc/passwd`) returns HTTP 400.
- Non-existent path returns HTTP 404.
- `category` is correctly inferred from the path.

# History

```
2026-06-02T08:10:04Z [agent]
I'll examine the existing tools router and models to understand what's already in place before adding the new endpoint.

Now let me check the AiToolEntry model and the rest of models.py:

Let me see the rest of models.py after the `SpaceToolsResponse` definition:

I have everything I need. The tools router is already registered in `main.py` (line 218). Now I'll:
1. Add `AiToolDetail` to `models.py`
2. Add the `GET /api/spaces/{space_id}/tool-content` endpoint to `tools.py`

Now add the endpoint to `tools.py`:

Now append the new endpoint at the end of `tools.py`:

Now run the tests to verify nothing is broken and the new endpoint works:

All 1252 tests pass, coverage at 82.18%. Let me do a quick sanity check on the final state of the new endpoint:

Good. Now finalize the task.

## Step 1 — Verify completion

All requirements met:
- `AiToolDetail` model added to `models.py`
- `GET /api/spaces/{space_id}/tool-content` endpoint added to `tools.py`
- Path traversal → HTTP 400 (via `is_relative_to`)
- Missing file → HTTP 404
- Category inferred from resolved path
- Router already registered in `main.py` — no wiring needed
- 1252 tests pass, 82.18% coverage

Goal child task — delegating to goal-task-commit.

On a `cronos/*` branch — need to set up the feature branch first.

On `feature/ai-tools-detail-screens`. Tests already confirmed passing. Now check for changes:

The changes are in the main worktree (`/data/spaces/cronos-development` on `main`). I need to check the task worktree structure:

The task worktree is missing the changes — they landed in the main worktree. I'll copy the modified files here and commit:

Committed and pushed to `feature/ai-tools-detail-screens`. Back to task-finalize Step 4.

## Step 4 — Write memory

MEMORY[fact]: Added `AiToolDetail` model to `backend/app/models.py` and `GET /api/spaces/{space_id}/tool-content` endpoint to `backend/app/api/tools.py`. Endpoint accepts `path` + `scope` query params, validates path is under `{space_dir}/.claude/` (space) or `~/.claude/` (global) using `Path.is_relative_to()`, returns HTTP 400 on traversal / 404 on missing, infers category from resolved path segments, returns full file content.

MEMORY[observation]: Edit tools write to absolute paths in the main worktree (`/data/spaces/cronos-development/`), not the task worktree. After `goal-branch-setup`, must `cp` modified files from main worktree to task worktree before committing.

STATUS: DONE
```
