---
agent_mode: auto
agent_model: default
claude_session_id: bf068193-b4bb-4bcf-bd79-7b325244e531
created_at: '2026-05-29T19:12:51Z'
depends_on: []
id: 2026-05-29-1912-add-claude-opus-4-8-as-explicit-model-op
manual_order: 0
parent_id: 2026-05-29-1912-opus-4-8-support
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Add claude-opus-4-8 as explicit model option
type: task
updated_at: '2026-06-04T10:26:29Z'
waiting_question: null
---

# Brief

Add `claude-opus-4-8` as an explicitly selectable model in Cronos alongside the existing `opus` alias.

## Background

`agent.py:243` passes `task.agent_model` directly as `--model <value>`. A mapping dict is needed because the internal key `"opus-4-8"` must become `"claude-opus-4-8"` for the CLI.

## Changes required

**`backend/app/models.py` line 19**
```python
AgentModel = Literal["default", "sonnet", "opus", "haiku", "opus-4-8"]
```

**`backend/app/storage.py` line 21**
```python
VALID_AGENT_MODELS: tuple[AgentModel, ...] = ("default", "sonnet", "opus", "haiku", "opus-4-8")
```

**`backend/app/api/tasks.py` lines 81 and 93**
Add `"opus-4-8"` to both `Literal["default", "sonnet", "opus", "haiku"]` annotations.

**`backend/app/agent.py` around line 243**
```python
_MODEL_CLI_NAMES: dict[str, str] = {
    "opus-4-8": "claude-opus-4-8",
}

if task.agent_model != "default":
    cli_model = _MODEL_CLI_NAMES.get(task.agent_model, task.agent_model)
    cmd += ["--model", cli_model]
```

**`frontend/src/types.ts` lines 74–81**
```typescript
export type AgentModel = "default" | "sonnet" | "opus" | "haiku" | "opus-4-8";
export const AGENT_MODELS = [
  { value: "default",  label: "Default"  },
  { value: "sonnet",   label: "Sonnet"   },
  { value: "opus",     label: "Opus"     },
  { value: "haiku",    label: "Haiku"    },
  { value: "opus-4-8", label: "Opus 4.8" },
];
```

## Acceptance

- `POST /api/tasks` with `agent_model: "opus-4-8"` succeeds.
- Backend passes `--model claude-opus-4-8` to the CLI when `opus-4-8` is selected.
- Frontend model selector shows "Opus 4.8".
- Backend tests pass (60% coverage floor).
- Frontend build has no TypeScript errors.

# History

```
2026-05-30T06:00:14Z [agent]
I'll read the relevant files before making changes.

Now let me read the frontend types file.

Now I'll make all the changes in parallel.

Now let me move `_MODEL_CLI_NAMES` outside the function (it's a module-level constant, not a local):

I'll move `_MODEL_CLI_NAMES` to module level alongside the other constants:

Now let me run the backend tests to verify coverage stays above 60%:

All 986 tests pass with 81% coverage (well above the 60% floor), and the frontend TypeScript build is clean. Let me now finalize the task.

## Step 1 — Verify completion

All requirements were implemented:
- `models.py` — `AgentModel` includes `"opus-4-8"`
- `storage.py` — `VALID_AGENT_MODELS` includes `"opus-4-8"`
- `api/tasks.py` — both `Literal` annotations updated
- `agent.py` — `_MODEL_CLI_NAMES` dict maps `"opus-4-8"` → `"claude-opus-4-8"`
- `frontend/src/types.ts` — `AgentModel` type and `AGENT_MODELS` array updated

986 tests pass, 81% coverage, frontend TypeScript build clean.

## Step 3 — Handle git

This is a goal child task. Delegating to goal-task-commit.

### Step 1: Verify branch

I'm on a `cronos/*` branch. Let me check if the feature branch already exists.

No feature branch for this goal yet. I need to run `/goal-branch-setup` first.

### Step 1: Resolve goal ID and feature branch name

### Step 2: Fetch and create the feature branch

### Step 3: Check out the feature branch

### Step 4: Verify

Now on `feature/opus-4-8-support`. Back to goal-task-commit — check for changes, stage, and commit.

### Step 3: Check for changes

The task worktree shows nothing because the edits are in the main repo checkout. Let me check the space directory:

The changes are in the main repo checkout. Let me check what branch it's on:

The changes are in the main checkout (`main`), but I need to commit them to the feature branch. I'll switch the task worktree back to free up the feature branch, then switch the main checkout to it:

The changes carried over. Now stage and commit the relevant files:

### Step 5: Push to origin

Committed and pushed to `feature/opus-4-8-support`. Now back to task-finalize Step 4.

## Step 4 — Write memory

MEMORY[fact]: Added `"opus-4-8"` as an explicit model option across backend and frontend. Key files: `backend/app/models.py` (AgentModel Literal), `backend/app/storage.py` (VALID_AGENT_MODELS tuple), `backend/app/api/tasks.py` (both CreateTaskBody and UpdateTaskBody), `backend/app/agent.py` (module-level `_MODEL_CLI_NAMES` dict maps internal key to CLI `"claude-opus-4-8"`), `frontend/src/types.ts` (AgentModel type + AGENT_MODELS array).

MEMORY[procedure]: When adding a new model alias that needs a different CLI name, add to `_MODEL_CLI_NAMES` in `agent.py` — that dict is the single mapping point between internal model keys and what's passed to `--model` CLI flag.

STATUS: DONE
```
