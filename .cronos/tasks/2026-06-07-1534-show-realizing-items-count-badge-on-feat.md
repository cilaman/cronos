---
agent_mode: auto
agent_model: default
claude_session_id: 93091ad3-cf4c-493b-8b57-352d2a809b63
created_at: '2026-06-07T15:34:22Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1534-show-realizing-items-count-badge-on-feat
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1534-features-board-ux-ui-consistency-polish
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Show realizing_items count badge on feature cards (UX-2, UX-3)
type: task
updated_at: '2026-06-15T13:30:16Z'
waiting_question: null
---

# Brief

Feature cards should show how many tasks/goals realize them, similar to how task cards show goal progress.

The `FeatureBoard` lane data (from `GET /api/features?space_id=`) returns `TaskSummary[]` for each lane. `TaskSummary` includes the task metadata but not `realizing_items` count.

Options:
1. Add `realizing_count: int` to the lane `TaskSummary` in the backend `GET /api/features` response (preferred — avoids N+1 fetches)
2. Fetch counts lazily when the card is visible

Implement option 1: in `backend/app/api/features.py`, when building the board response, count `realizing` links per feature and include `realizing_count` in each lane item.

On the frontend, render a small badge "3 linked" (or similar) on feature cards when `realizing_count > 0`.

# History

```
2026-06-08T13:07:15Z [agent]
I'll start by exploring the relevant backend and frontend files to understand the current implementation.

Now let me look at the models and types files to understand `TaskSummary`.

Now let me read the `TaskSummary` model and the storage `feature_board` method.

Let me look at the `summarize` function in storage.py.

Now let me look at Card.tsx to understand where to add the badge.

Now I have a full picture. Let me check the existing test files for the features API.

Now I have all the information I need. Let me implement the changes:

1. Add `realizing_count: int = 0` to `TaskSummary` in `models.py`
2. Populate it in `feature_board()` in `storage.py`
3. Add `realizing_count?: number` to `TaskSummary` in `types.ts`
4. Add badge in `Card.tsx` and remove raw UUID `realized_by` display

Now update `feature_board()` in `storage.py` to populate `realizing_count`:

Now update the frontend `types.ts` to add `realizing_count` to `TaskSummary`:

Now update `Card.tsx` to replace the raw UUID `realized_by` display with a clean `realizing_count` badge. I'll add the badge in the top badges row (after `feature_key`) and remove the raw UUID section:

Now remove the raw UUID `realized_by` display section:

Also need to add the badge to the `tight` density layout (lines ~331-358):

Now let me write a backend test for the new `realizing_count` behavior in `feature_board`:

Now let me add the test for `realizing_count` in the storage-level test:

Now let me also add an API-level test for `realizing_count` in the board response:

Now let me run the backend tests to check everything passes:

All 18 tests pass. Let me run the full backend test suite to make sure nothing is broken:

2490 tests pass. Now let me run the frontend tests:

I'll wait for the frontend tests to complete:

There are 3 test failures in Card.test.tsx — let me check what they test:

I need to update the Card tests to replace the `realized_by` UUID tests with `realizing_count` badge tests:

Now let me check what the `makeTask` function returns to see if `realizing_count` is included:

Good — `makeTask` takes `Partial<TaskSummary>` overrides so `realizing_count` will be passed through since it's already added to `TaskSummary` in `types.ts`. Let me run the frontend tests now:

All 1183 frontend tests pass and all 2490 backend tests pass. Let me finalize with the task completion skill:

## Step 1 — Verify completion

All requirements met:
- `realizing_count: int = 0` added to `TaskSummary` in `models.py`
- `feature_board()` in `storage.py` counts realizing tasks per feature and populates the field
- `realizing_count?: number` added to frontend `TaskSummary` in `types.ts`
- Badge "N linked" rendered on feature/fix cards in both default and tight density layouts
- Raw UUID `realized_by` display removed
- Tests updated and all pass: 2490 backend + 1183 frontend

## Step 3 — Handle git

Not on the feature branch — need to run goal-branch-setup first.

The feature branch is checked out in another worktree. I'll commit from the space directory directly using `git -C`.

I need to copy my changed files to the feature branch worktree and commit from there.

Committed and pushed. Now back to task-finalize Step 4 — write memory.

## Step 4 — Write memory

MEMORY[fact]: Added `realizing_count: int = 0` to `TaskSummary` (backend `models.py`) and `realizing_count?: number` to frontend `TaskSummary` (types.ts). `feature_board()` in `storage.py` now builds a count map of tasks with `realizes == feature_id` and sets it on each summary. Card.tsx renders a sky-blue "N linked" badge for feature/fix types when count > 0; removed the raw UUID `realized_by` display.

## Step 5 — Emit STATUS

STATUS: DONE
```
