---
agent_mode: auto
agent_model: default
claude_session_id: d517726a-938a-4da4-ba22-76c6f9d6490b
created_at: '2026-05-26T14:25:52Z'
depends_on:
- 2026-05-26-0604-d2-aggregate-memory-hit-rate-into-runstat
- 2026-05-26-0604-d5-memory-browser-page-list-filter-confir
id: 2026-05-26-0604-d6-metrics-tests-hit-rate-computation-and
manual_order: 0
parent_id: 2026-05-26-0604-memory-metrics-hit-rate-in-traces-stats
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'D6: Metrics tests — hit rate computation and UI'
type: task
updated_at: '2026-06-03T05:33:36Z'
waiting_question: null
---

# Brief

Write backend tests in test_memory_metrics.py (hit rate math, stats aggregation) and frontend tests in MemoryPage.test.tsx (item list render, filter, confirm button).

# History

```
2026-05-27T04:52:00Z [agent]
Let me explore the codebase to understand the existing structure before writing tests.

Now let me read the actual source files to write accurate tests.

Let me look at the memory store and any existing memory API to understand what tests should cover.

Now let me look at the models and existing frontend test setup.

Let me check the existing memory API and conftest.

Now I have everything I need. Let me implement the `memory_hit_rate` feature and write the tests.

**Step 1:** Add `memory_hit_rate` to `RunTrace` and compute it.

Now add the computation of `memory_hit_rate` in `extract_run_trace()`:

Now add `memory_hit_rate` to the `RunTrace(...)` constructor call:

**Step 2:** Write `test_memory_metrics.py`:

**Step 3:** Add `MemoryItem` type to `types.ts` and memory API methods to `api.ts`:

Now add memory API methods to `api.ts`:

**Step 4:** Create `useMemory.ts` hook:

**Step 5:** Create `MemoryPage.tsx`:

**Step 6:** Write `MemoryPage.test.tsx`. Let me first check a similar test to follow the setup pattern:

Now write `MemoryPage.test.tsx`:

Now let's run both test suites to verify:

All 16 backend tests pass. Now run the frontend tests:

One test fails because "Fact" appears in both the dropdown and the badge. Fix it to use `getAllByText`:

All 15 frontend tests pass. Now let me commit using the goal-task-commit skill:

The goal's feature branch `feature/memory-metrics-hit-rate-in-traces-stats` already exists. Let me check it out and then run tests.

The feature branch is checked out in another worktree. I'll run the test suite, then commit on the current branch and push to the feature branch.

The 11 frontend failures are pre-existing issues in `DetailPRSection.test.tsx` and `useTasks.test.ts` — not in files I changed. Let me verify:

The feature branch already has a different `memory_hit_rate` implementation. Let me check it:

The feature branch has a different implementation — memory item tracking via `memory_injected`/`memory_used`, not cache tokens. Let me read the full feature branch version:

The feature branch uses a completely different implementation — memory item injection tracking, not cache tokens. I need to rebase onto the feature branch and fix my `trace_parser.py` changes and tests.

Let me look at what D2 changed in stats.py on the feature branch:

Now I understand. Let me pop the stash and apply the feature branch's correct implementations:

Now replace `trace_parser.py` and `stats.py` with the feature branch versions and rewrite the test:

Now let me see the full stats.py feature branch version to understand what I need to test:

Now I can rewrite `test_memory_metrics.py` with the correct semantics:

The path format needs to match the regex. Let me check exactly what it expects:

The regex matches `/memory/filename.md` directly (no `items/` subdirectory). Fix the test helper paths:

Also fix the `_read_event` helper and the other tests that use `/memory/fact-a.md`:

Also fix the `test_memory_hit_rate_one_when_all_used` and `test_memory_used_deduplicates` tests:

All 19 backend tests pass. Now verify frontend tests still pass:

All tests pass. Now commit and push to the feature branch:

My branch is behind the remote. I need to rebase onto the remote feature branch:

Remote has D4 too. I need to rebase my commit onto FETCH_HEAD:

The feature branch already has `MemoryPage.tsx` and `useMemory.ts` with different designs. Let me resolve by taking the feature branch versions for those files and adapting my tests:

Good, no more conflicts. Now let me check what the feature branch's `useMemory.ts` and `MemoryPage.tsx` look like so I can fix my test:

There are duplicates in `types.ts`. Let me check:

The feature branch added `MemoryItem` with extra fields (`created_at?`, `updated_at?`) after Test reports. I should remove the duplicate I added and keep only the feature branch's version:

Now run the frontend tests again:

Now add the remaining files and continue the rebase:

Now push to the feature branch:

Pushed successfully. Let me do a final verification of the test runs:

**STATUS: DONE**

All work is committed and pushed to `feature/memory-metrics-hit-rate-in-traces-stats`.

**Summary of what was delivered:**

- **`backend/tests/test_memory_metrics.py`** — 19 tests covering:
  - Hit rate math: zero when nothing injected, zero when injected but none used, 1.0 when all used, partial (2/3), cap at 1.0
  - Memory tracking: `memory_used` from Read tool calls, `memory_written` from Write tool calls, deduplication, `memory_injected` stored on trace
  - Stats aggregation: `TaskStats.avg_memory_hit_rate` (None when no data, ignores None runs, averages correctly), `GlobalStats.avg_memory_hit_rate` across tasks

- **`frontend/src/pages/__tests__/MemoryPage.test.tsx`** — 15 tests covering:
  - Item list render: shows all items, titles, kind badges, confirmed badge, loading state, empty state
  - Filter: dropdown present with all kind options, filters by kind, resets to all, empty state when no match
  - Confirm button: shows only for unconfirmed items, calls mutate with correct item id, absent for confirmed items
```
