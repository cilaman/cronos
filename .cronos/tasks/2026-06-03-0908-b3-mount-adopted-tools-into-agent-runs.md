---
agent_mode: auto
agent_model: default
claude_session_id: 4e77a0c4-9936-4dd8-9c7a-9f24544d3ad8
created_at: '2026-06-03T09:08:41Z'
depends_on:
- 2026-06-03-0908-b1-adoption-module-manifest-watcher
feature_key: null
feature_state: null
id: 2026-06-03-0908-b3-mount-adopted-tools-into-agent-runs
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-0908-arc-5-b-adoption-vendor-mount-merge-upst
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: B3 — Mount adopted tools into agent runs
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

In `backend/app/agent.py` at line 216:

- Resolve task's space → list adopted dirs under `{space}/.cronos/tools/`. Append `--add-dir <abs>` per dir AFTER the workspace `--add-dir` (workspace stays highest precedence).
- For any adopted item kind=`hook`, deep-merge its `permissions` / `hooks` blocks into a generated `<workspace>/.claude/settings.json` written before subprocess spawn. User workspace settings override on key conflict.

## Files

- Modified: `backend/app/agent.py` (add `--add-dir` per adopted tool + settings merge)

## Unit test

`run_agent` on fixture space with one adopted skill → captured subprocess args include the adopted `--add-dir`.

## Acceptance

- Subprocess args include adopted tool paths after workspace path
- `settings.json` generated in workspace when a hook is adopted
- User workspace `settings.json` takes precedence over hook's settings on key conflict
- No adopted tools → no extra `--add-dir` args appended

---

## Standing rules

**Branch:** `feature/arc-5-tools`; create from `main` if missing. No branching from other bases; no merging to `main` (manual after arc lands).

**Test gate:** Invoke `test-architect`: "Update tests for this task; add coverage for new code paths (pytest + vitest); run full suites; report pass/fail." Commit only after green.

**Commit message:** `arc-5/<goal>/<n>: <summary>` — include task number in body.

**STATUS:** `STATUS: DONE` on success; `STATUS: BLOCKED` if tests can't be made green (describe blocker above).

# History

```
2026-06-03T13:03:04Z [agent]
I'll start by reading the relevant files to understand the current state of the codebase.

Now let me look at the adoption API and models to understand the `kind` field values and the tools directory structure:

Let me look at the discovery module to understand what kind="hook" means:

Let me look at the adoption tests to understand the hook structure:

Now let me look at the existing agent tests:

Let me read the remaining part of agent.py and understand the full `_extract_assistant_text` function:

Now I have a complete picture. Let me implement the changes to `agent.py` and then write the tests.

Now I'll make the changes. First, add the helper functions after `workspace_for` and before `PERMISSION_MODE`:

Now modify `run_agent` to use these helpers. I need to change the workspace setup and cmd building:

Now let me add the tests to `test_agent.py`:

Now add the new test section at the end of the file:

Now let's run the tests to see if everything passes:

All 69 agent tests pass. Now let me run the full test suite to confirm nothing is broken:

1440 tests passed, 83% coverage (well above the 60% floor). Now let me commit and finalize:

Good — we're on the right branch `feature/arc-5-tools`. Now let me run the tests via test-architect, then commit:

All tests green. Now commit and push:

Pushed. Now finalize the task:

**Step 1 — Verify completion**

All B3 requirements are met:
- `_load_adopted_dirs()` enumerates `{space}/.cronos/tools/` adopted items
- `run_agent()` appends `--add-dir` per adopted dir after workspace dir
- Hook items merge `permissions`/`hooks` into `workspace/.claude/settings.json` before spawn
- Workspace settings override hook settings on conflict
- 23 new tests; 1440 total green, 83% coverage
- Already committed and pushed to `feature/arc-5-tools` via `goal-task-commit`

**Step 4 — Write memory**

The workspace-scoped path is blocked. Writing to the project-level memory that is injected into future runs:

MEMORY[fact]: Arc 5/B3 complete — `_load_adopted_dirs()`, `_read_hook_settings()`, `_merge_hook_settings()`, `_read/_write_workspace_settings()` added to `backend/app/agent.py`; `run_agent()` appends `--add-dir` per adopted tool and writes merged `workspace/.claude/settings.json` when hook items are adopted. 23 new tests, 1440 total green, 83% coverage. Committed b6ec572 on `feature/arc-5-tools`.

STATUS: DONE
```
