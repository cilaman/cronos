---
agent_mode: auto
agent_model: default
claude_session_id: c9aafc6b-68b3-423a-b507-2c76e9dca24a
created_at: '2026-06-03T09:08:41Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-03-0908-a1-tool-sources-yml-loader-schema
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-0908-arc-5-a-discovery-tool-sources-yml-index
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: A1 — tool_sources.yml loader + schema
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

New `backend/app/tools/sources.py`: Pydantic `ToolSource(url, branch=None, enabled=True, label=None)`, `load_sources(path) -> list[ToolSource]`. Validate URL via existing `git_ops.validate_repo_url`. Missing file → `[]`. YAML shape: top-level `sources:` list of objects. Env override `CRONOS_TOOL_SOURCES_PATH` for tests.

## Acceptance

- Parsed list returned from a valid YAML file
- Invalid URL raises `ToolSourceError`
- Missing file → empty list
- Env override `CRONOS_TOOL_SOURCES_PATH` works in tests

---

## Standing rules

**Branch:** `feature/arc-5-tools`; create from `main` if missing. No branching from other bases; no merging to `main` (manual after arc lands).

**Test gate:** Invoke `test-architect`: "Update tests for this task; add coverage for new code paths (pytest + vitest); run full suites; report pass/fail." Commit only after green.

**Commit message:** `arc-5/<goal>/<n>: <summary>` — include task number in body.

**STATUS:** `STATUS: DONE` on success; `STATUS: BLOCKED` if tests can't be made green (describe blocker above).

# History

```
2026-06-03T11:34:10Z [agent]
I'll start by exploring the codebase structure and finding the relevant `git_ops.validate_repo_url` function.

Now I have all the context. Let me create the `backend/app/tools/` directory with the required files.

Now I'll create the `backend/app/tools/` package with `sources.py`:

Now I'll invoke the test-architect to add coverage for the new module:

All 1340 tests pass with 82.31% coverage. Now I'll finalize the task — commit to the feature branch and emit STATUS.

## Step 1 — Verify completion

All requirements met:
- `ToolSource` Pydantic model with `url`, `branch`, `enabled`, `label` ✓
- `load_sources(path) -> list[ToolSource]` ✓
- URL validated via `git_ops.validate_repo_url`, raises `ToolSourceError` on invalid ✓
- Missing file → `[]` ✓
- `CRONOS_TOOL_SOURCES_PATH` env override ✓
- 20 tests, 1340 total passing, 82.31% coverage ✓

## Step 3 — Handle git

Goal child task — delegating to goal-task-commit:

## Step 1: Resolve root goal and check branch

Not on the feature branch — need to set it up first.

## Step 1: Resolve root goal and feature branch name

## Step 2: Fetch and create/retrieve the feature branch

## Step 3: Check out the feature branch in this worktree

## Step 4: Verify

On the feature branch. Now back to goal-task-commit — Stage, commit, and push:

## Step 3: Check for changes

## Step 4: Stage and commit

## Step 5: Push to origin

## Step 6: Confirm

Committed and pushed. Back to task-finalize:

## Step 4 — Write memory

MEMORY[fact]: `backend/app/tools/sources.py` created (arc-5/A1, commit b02ed16 on `feature/arc-5-a-discovery-tool-sources-yml-index`). Provides `ToolSource(BaseModel)` with url/branch/enabled/label fields, `ToolSourceError`, and `load_sources(path)` that reads YAML `sources:` list, validates URLs via `git_ops.validate_repo_url`, returns `[]` on missing file, and respects `CRONOS_TOOL_SOURCES_PATH` env override. 20 tests at 100% coverage in `backend/tests/test_tools_sources.py`.

MEMORY[fact]: Arc-5 root goal slug is `arc-5-a-discovery-tool-sources-yml-index`; feature branch is `feature/arc-5-a-discovery-tool-sources-yml-index` (created from main, pushed to origin).

STATUS: DONE
```
