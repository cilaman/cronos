---
agent_mode: auto
agent_model: default
claude_session_id: 959c15cf-73db-4e5a-95a6-1d1cda378aa2
created_at: '2026-06-02T14:19:04Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-02-1419-prominent-status-indicators
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-02-1418-task-goal-tile-visualization-improvement
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Prominent status indicators
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

Replace the tiny 1.5px status dot (h-1.5 w-1.5) with a larger, more visually distinct status indicator throughout the kanban card and its expanded children list.

## Problem
In `Card.tsx`, `STATE_DOT_STYLES` defines dot colors: backlog=ink-faint, active=emerald-500, waiting=amber-500, done=sky-500, archived=ink-faint/40. At 1.5×1.5px they are hard to read and emerald (active) vs sky (done) look similar.

## Scope
- `frontend/src/components/Card.tsx`
- Status dots appear in: tight-density mode (lines 196-203), the expanded children panel (lines 484-490)
- The main card body does NOT currently show a prominent status indicator (only the lane position implies it)

## Approach
Replace the tiny dot with a pill badge that shows a short label: "Active", "Waiting", "Done", "Backlog". Use color-coded background (keeping the existing palette). Badge should be readable at a glance. Apply consistently to:
1. Tight-density card (inline with title metadata)
2. Expanded children list rows
3. Optionally: add a small status badge to the default/compact card header

## Acceptance criteria
- Status is readable without squinting
- Active (emerald) and Done (sky/blue) are clearly distinct
- Works in both light and dark themes (dark: classes already defined in STATE_DOT_STYLES)

# History

```
2026-06-02T14:59:55Z [agent]
I'll read the current Card.tsx to understand the existing status dot implementation before making changes.

Now I have a clear picture of the three changes needed. Let me implement them:

1. Replace `STATE_DOT_STYLES` with `STATE_BADGE_STYLES` + `STATE_LABELS`
2. Swap the tiny dots in tight-density mode and expanded children list for pill badges
3. Add a status badge to the default card header row

Now replace the tiny dot in tight-density mode with a pill badge:

Now replace the tiny dot in the expanded children list:

Now add a status badge to the default/compact card header row (after the priority badge):

Now let me verify the final state of the relevant sections looks correct:

Good. Let me run the frontend build to check for TypeScript errors:

TypeScript compile is clean. Let me run the frontend tests:

Let me check the output directly while it runs:

Two existing tests relied on `aria-label="active"` on the old dot. Let me find and fix those tests:

Let me check what the second failing test is:

Only 1 test fails in Card.test.tsx. Let me also find the second failing test file:

Let me find which second test file is failing:

Now I know both failing tests. Let me read the second test in Card.test.tsx:

There are two test files to update. Let me fix both:

Now fix the second test in the other Card test file:

Wait — the parent goal might also be in "backlog" state, creating duplicate "Backlog" text. Let me check `makeGoalTask`:

The parent goal is state "backlog" and child-2 is also "backlog" — `getByText("Backlog")` will throw on duplicates. Let me use `getAllByText` instead:

Now let me run just the Card tests to verify both fixes work:

All 89 Card tests pass. Now let me run the full test suite to confirm nothing else broke:

All 678 tests pass. Now let me finalize the task:

## Step 1 — Verify completion

All requirements met:
- Replaced `STATE_DOT_STYLES` with `STATE_BADGE_STYLES` + `STATE_LABELS` 
- Tight-density card: dot → pill badge ("Active", "Waiting", etc.)
- Expanded children panel: dot → pill badge
- Default card header: added status badge after priority badge
- Updated 2 tests that relied on the old `aria-label` dot
- 678/678 tests pass

This is a goal child task. Delegating to goal-task-commit:

Not on the feature branch. Running goal-branch-setup first:

The feature branch is already checked out in another worktree. I need to copy changed files there and commit via that worktree. Let me find the changed files:

Committed and pushed. Now back to task-finalize Step 4 — write memory:

MEMORY[fact]: Replaced 1.5px status dots in `frontend/src/components/Card.tsx` with color-coded pill badges (`STATE_BADGE_STYLES` + `STATE_LABELS`). Badges show text labels ("Active", "Waiting", "Done", "Backlog", "Archived") in tight-density mode, expanded children panel, and default card header. Updated two test files (`src/__tests__/Card.test.tsx`, `src/components/__tests__/Card.test.tsx`) that relied on `aria-label` dot queries to use text-based queries instead.

STATUS: DONE
```
