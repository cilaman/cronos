---
agent_mode: auto
agent_model: default
claude_session_id: bfcc23c9-b362-47b3-9845-801f30b7d039
created_at: '2026-06-03T09:08:41Z'
depends_on:
- 2026-06-03-0908-a2-discovery-module-clone-walk-parse
feature_key: null
feature_state: null
id: 2026-06-03-0908-a3-discovered-tools-sqlite-index-upsert
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
title: A3 — discovered_tools SQLite index + upsert
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

Add a `discovered_tools` table to the existing storage SQLite (NOT tied to MD parsing). Columns: `source_url, source_slug, kind, name, relative_path, description, source_sha, last_seen`. PK `(source_slug, kind, name)`. Index on `kind`.

New `backend/app/tools/index.py`:
- `upsert_discovered(items: list[DiscoveredItem])` — upsert with updated `last_seen`
- `prune_stale(source_slug, cutoff: datetime)` — removes rows older than the current run's `last_seen`
- `list_discovered(kind=None, source_slug=None) -> list[DiscoveredItem]` — order-stable

## Files

- New: `backend/app/tools/index.py`
- Modified: `backend/app/storage.py` (add `discovered_tools` table migration)

## Acceptance

- Upsert + re-run with item deleted upstream → pruned by `prune_stale`
- Same item with new SHA → row updated, not duplicated
- `list_discovered` is order-stable across calls

---

## Standing rules

**Branch:** `feature/arc-5-tools`; create from `main` if missing. No branching from other bases; no merging to `main` (manual after arc lands).

**Test gate:** Invoke `test-architect`: "Update tests for this task; add coverage for new code paths (pytest + vitest); run full suites; report pass/fail." Commit only after green.

**Commit message:** `arc-5/<goal>/<n>: <summary>` — include task number in body.

**STATUS:** `STATUS: DONE` on success; `STATUS: BLOCKED` if tests can't be made green (describe blocker above).

# History

```
2026-06-03T11:54:15Z [agent]
I'll start by exploring the relevant existing code to understand patterns before implementing.

Now let me read the exact relevant sections of storage.py and discovery.py before implementing.

Now let me check how the db_path is configured and where I should add the new table migration.

Now let me check the existing tests for tools to understand test patterns:

I have enough context. Let me implement the changes now. I'll start with the storage migration and the new index module:

Now create `backend/app/tools/index.py`:

Now invoke `test-architect` to add coverage:

All 1372 tests pass, 82.62% coverage (floor is 60%). Now commit and finalize:

The task brief explicitly specifies `feature/arc-5-tools`, and the current branch matches. Previous task A2 also committed to this branch. I'll use it as instructed.

Committed and pushed. Now finalize:

## Step 1 — Verify completion

All requirements met:
- `discovered_tools` table + `kind` index added to `_ensure_db_schema` in `storage.py`
- `backend/app/tools/index.py` created with `upsert_discovered`, `prune_stale`, `list_discovered`
- 12 new tests; 1372 total pass; 82.62% coverage (floor: 60%)
- Committed (`0f5652c`) and pushed to `feature/arc-5-tools`

## Step 2 — Trace history

First run, not re-activated. Skip.

## Step 3 — Handle git

Already handled by `goal-task-commit` above. Commit `0f5652c` pushed to `feature/arc-5-tools`.

Memory written. Now also update the space-root memory with the arc-5/A3 fact:

Memory written. Now mark the task done via the API:

The `ACTIVE → DONE` transition is a worker-only transition. The harness reads `STATUS: DONE` from the agent output and handles state transition automatically. I don't need to call the API manually.

Task A3 is complete:
- `backend/app/tools/index.py` created with `upsert_discovered`, `prune_stale`, `list_discovered`
- `discovered_tools` table + `kind` index added to `storage._ensure_db_schema`
- 12 new tests, 1372 total pass, 82.62% coverage
- Committed (`0f5652c`) and pushed to `feature/arc-5-tools`

STATUS: DONE
```
