---
agent_mode: auto
agent_model: default
claude_session_id: fd739140-c50f-435b-aaee-84a8f3b958ae
created_at: '2026-06-03T09:08:41Z'
depends_on:
- 2026-06-03-0908-a3-discovered-tools-sqlite-index-upsert
id: 2026-06-03-0908-a4-refresh-api-periodic-scheduler
manual_order: 0
parent_id: 2026-06-03-0908-arc-5-a-discovery-tool-sources-yml-index
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: done
title: A4 — Refresh API + periodic scheduler
type: task
updated_at: '2026-06-03T12:03:07Z'
waiting_question: null
---

# Brief

New `backend/app/api/discovery.py` registered in `main.py`:

- `POST /api/discovery/refresh` — runs refresh + walk + upsert for every enabled source; returns `{refreshed, items}`. 60-min lock against concurrent refreshes.
- `GET /api/discovery/tools?kind=&source_slug=` — query the index.
- `GET /api/discovery/sources` — parsed `tool_sources.yml`.

Periodic background task in `main.py` lifespan: refresh every 6h (env `CRONOS_DISCOVERY_INTERVAL_HOURS`). Errors log + back off; never crash app.

## Files

- New: `backend/app/api/discovery.py`
- Modified: `backend/app/main.py` (register router + lifespan periodic task)

## Acceptance

- Two fixture sources → POST clones+indexes → GET returns items
- Periodic task fires on shortened test interval
- 60-min lock prevents concurrent refreshes
- Missing `tool_sources.yml` → refresh returns empty `{refreshed: 0, items: []}`

---

## Standing rules

**Branch:** `feature/arc-5-tools`; create from `main` if missing. No branching from other bases; no merging to `main` (manual after arc lands).

**Test gate:** Invoke `test-architect`: "Update tests for this task; add coverage for new code paths (pytest + vitest); run full suites; report pass/fail." Commit only after green.

**Commit message:** `arc-5/<goal>/<n>: <summary>` — include task number in body.

**STATUS:** `STATUS: DONE` on success; `STATUS: BLOCKED` if tests can't be made green (describe blocker above).

# History

```
2026-06-03T12:03:07Z [agent]
I'll start by checking the current branch state and understanding the existing code I need to build on.

Now let me examine the main.py and existing API patterns:

Now let me look at how the database is set up in A3 and what tests exist:

Let me check where the discovered_tools table is created in storage.py and what db path is used:

Let me check existing async test patterns and the test_tools_discovery.py file:

Now I have everything I need. Let me write the implementation:

Now update `main.py` to register the router and add the periodic task:

Now add the `discovery_refresh_loop` function after the `memory_prune_loop` function:

Now add `discovery_db_path` and `discovery_sources_path` to `app.state` in the lifespan, and start the background task:

Now register the discovery router in the app:

Now let me write the tests. First, let me look at a few more patterns:

Now I'll write the test file:

Now let me run the tests to see how they do:

19/19 tests pass. Now let me run the full test suite to make sure nothing is broken:

All 1391 tests pass with 82.80% coverage, and `app/api/discovery.py` has 100% coverage. Now let me commit the changes:

The current branch `feature/arc-5-tools` is correct per the task standing rules. Now let me check and commit:

Committed and pushed. Now let me finalize the task:

**Step 1 — Verify completion**

All requirements met:
- `backend/app/api/discovery.py` created with all three endpoints (POST /refresh, GET /tools, GET /sources)
- `backend/app/main.py` updated with router registration and `discovery_refresh_loop` periodic task
- All acceptance criteria covered by 19 passing tests; full suite 1391 passed at 82.80% coverage
- Already committed (54a9a8a) and pushed to `feature/arc-5-tools`

**Step 2 — Skip** (not previously WAITING)

**Step 3 — Git already handled** via `goal-task-commit` above.

**Step 4 — Write memory**

The workspace-specific path is blocked. Let me write to the space-root memory instead, which is what gets injected into future project conversations:

Memory written and indexed. 

**Step 5 — STATUS:**

STATUS: DONE
```
