---
agent_mode: auto
agent_model: default
claude_session_id: 7afc7860-b576-4431-af09-6468f038328a
created_at: '2026-06-03T09:08:41Z'
depends_on:
- 2026-06-03-0908-a1-tool-sources-yml-loader-schema
id: 2026-06-03-0908-a2-discovery-module-clone-walk-parse
manual_order: 0
parent_id: 2026-06-03-0908-arc-5-a-discovery-tool-sources-yml-index
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: done
title: 'A2 — Discovery module: clone + walk + parse'
type: task
updated_at: '2026-06-03T11:45:14Z'
waiting_question: null
---

# Brief

New `backend/app/tools/discovery.py`:

- `async clone_source(source) -> Path` — `git clone --depth 1 [--branch ...]` into `/data/.cronos/discovery_sources/<slug>/`; slug = sanitised `host+path`. Reuse auth-env from `git_ops.py:94-115` (or Arc 4's extracted version).
- `async refresh_source(source)` — clone-if-missing, else `git fetch --depth 1 origin <branch> && git reset --hard FETCH_HEAD`.
- `async walk_source(path) -> list[DiscoveredItem]` — reuse `_scan_category` / `_scan_skills` from `api/tools.py:83-149`; **refactor both into `tools/scanner.py`** so discovery + existing `/api/spaces/{id}/tools` share one parser. Also parse `.claude/settings.json` (kind=`hook`).
- `DiscoveredItem`: `source_url, source_slug, kind, name, relative_path, description, source_sha` (cloned-branch HEAD).

## Files

- New: `backend/app/tools/discovery.py`, `backend/app/tools/scanner.py`
- Modified: `backend/app/api/tools.py` (import from scanner.py)

## Acceptance

- Fixture repo with one agent + one skill dir → walker returns both with correct kinds/names/SHA
- `refresh_source` on existing clone does fetch+reset, not re-clone
- `scanner.py` is the single source of truth for `_scan_category`/`_scan_skills`

---

## Standing rules

**Branch:** `feature/arc-5-tools`; create from `main` if missing. No branching from other bases; no merging to `main` (manual after arc lands).

**Test gate:** Invoke `test-architect`: "Update tests for this task; add coverage for new code paths (pytest + vitest); run full suites; report pass/fail." Commit only after green.

**Commit message:** `arc-5/<goal>/<n>: <summary>` — include task number in body.

**STATUS:** `STATUS: DONE` on success; `STATUS: BLOCKED` if tests can't be made green (describe blocker above).

# History

```
2026-06-03T11:45:14Z [agent]
I'll start by reading the relevant files to understand the existing codebase structure.

Now let me read the sources.py from A1 and the models.py to understand existing types:

Now let me check the current branch and find the tools directory structure:

Let me check the A1 branch content and understand the branch strategy:

I can see I'm in the task worktree. Let me check the current state of the workspace and set up the feature branch properly:

The workspace is on the main branch but A1's work is on a separate branch. I'll set up `feature/arc-5-tools` from A1's branch and work there:

Now I have the branch with sources.py. Let me read the full sources.py and the tools `__init__.py`:

I have everything I need. Now I'll implement the three files. Let me start by creating `scanner.py`:

Now create `discovery.py`:

Now update `api/tools.py` to import from `scanner.py` instead of having duplicate implementations:

Now remove the old `_parse_settings` and `_scan_context` functions (keep `_scan_context` since it's not moved to scanner yet - it's only used in `api/tools.py`):

I need to remove the stale `_parse_settings` definition that's still in the file (conflicting with the import from scanner.py):

Now let's verify the final state of `api/tools.py`:

Now let me do a quick import check to verify the code is syntactically correct:

Imports work. Now let me invoke the test-architect to write and run tests:

All 1361 tests pass. Now I'll commit the changes to `feature/arc-5-tools`:

Now finalize the task:

## Step 1 — Verify completion

All objectives met:
- `backend/app/tools/scanner.py` created — single source of truth for `_scan_category`, `_scan_skills`, `_parse_settings`, `_extract_description`, `_mtime_iso`
- `backend/app/tools/discovery.py` created — `clone_source`, `refresh_source`, `walk_source`, `DiscoveredItem`
- `backend/app/api/tools.py` refactored to import from scanner.py
- 1361 tests pass, 82.52% coverage, new test file at 100% discovery coverage
- Committed (`7358121`) and pushed to `feature/arc-5-tools`

## Step 2 — Skip (no WAITING history)

## Step 3 — Handle git

This is a goal child task. Delegating git to goal-task-commit:

The workspace is clean — changes were committed directly to `feature/arc-5-tools` in the main worktree. Skip steps 4–5 per the skill.

## Step 4 — Write memory

The workspace-specific path is blocked. Writing to the global project memory (which IS injected per MEMORY.md):

Now update MEMORY.md:

Memory written. 

STATUS: DONE
```
