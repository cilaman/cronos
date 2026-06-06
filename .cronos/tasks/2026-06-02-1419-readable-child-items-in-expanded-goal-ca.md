---
agent_mode: auto
agent_model: default
claude_session_id: 88c2e657-5b09-44ae-a803-bbf93e328656
created_at: '2026-06-02T14:19:28Z'
depends_on: []
id: 2026-06-02-1419-readable-child-items-in-expanded-goal-ca
manual_order: 0
parent_id: 2026-06-02-1418-task-goal-tile-visualization-improvement
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: Readable child items in expanded goal cards
type: goal
updated_at: '2026-06-02T15:06:30Z'
waiting_question: null
---

# Brief

Improve the readability of task items shown inside an expanded goal card in the kanban view.

## Problem
In `Card.tsx`, when a goal is expanded (lines 468-505), each child item renders with:
- `text-xs text-ink-muted` title — very small
- `h-1.5 w-1.5` status dot — barely visible
- `text-[9px]` age and priority badge — extremely tiny
- Items are dense with only `py-1` padding

## Goal
Make each child row easily scannable. The items should feel like a compact but readable mini-list, not a dense log. Improvements:
- Title: `text-sm` (from `text-xs`), keep `text-ink` or `text-ink-muted`
- Spacing: increase to `py-1.5` or `py-2` between items
- Status: replaced by pill badge (see sibling goal: Prominent status indicators)
- Priority: keep at current size but ensure it's not crowded
- Add a subtle divider or spacing between rows for visual separation

# History

```
2026-06-02T15:06:30Z [agent]
I'll read the current Card.tsx to understand the child item rendering before making changes.

Now let me check what STATE_BADGE_STYLES looks like and how it's already used in the card.

Let me check if STATE_BADGE_STYLES already exists in the file (from the sibling goal's work):

STATE_BADGE_STYLES isn't in the current file yet. The sibling goal's work may be on a separate branch. Let me check:

The sibling branch already has the state badge implementation including child items. Let me see the full child rendering on that branch:

Now I can see what the sibling branch did (replaced state dots with badges) but still uses `text-xs text-ink-muted` for titles and `py-1` padding. My task needs to go further:
- Title: `text-sm` (from `text-xs`), use `text-ink` not `text-ink-muted`  
- Spacing: `py-1.5` or `py-2`
- State: pill badge (from the sibling goal)
- Add subtle dividers between rows

Let me check what goal feature branch I should be working on:

The feature branch has 2 sibling commits already. I need to build on top of that. Let me set up my worktree properly:

I need to switch to the feature branch to build on the sibling work:

The feature branch is checked out in another worktree. Let me read the procedure for this case:

The feature branch is in the main worktree. I'll read Card.tsx from there (which has sibling work already):

Let me check which worktree has the feature branch:

The feature branch is at the "distinguish-subtasks" worktree. I'll read its Card.tsx and make my improvements on it:

Now let me see the full child item rendering in this version:

Let me check if the "distinguish subtasks" sibling work is visible in the current feature branch child item rendering:

Let me check what the "distinguish subtasks" commit actually changed:

Now I have a clear picture. The "prominent status indicators" commit accidentally removed the goal-type badge that "distinguish subtasks" had added. My task also needs to improve title size/color and spacing. Let me make all changes at once to the feature branch worktree:

Now let me verify the change looks right by reading the updated section:

The changes look correct. Now let me check if there are any frontend tests that reference the child item rendering that may need updating:

No tests depend on those exact class strings. Now let me run the frontend tests to confirm nothing is broken:

All 678 tests pass in the main worktree. Now let me commit the change to the feature branch:

The diff is correct — building on top of both sibling commits. Let me commit:

Pushed successfully. Now let me finalize the task:

Changes are already committed and pushed to the feature branch. No further git action needed.

## Step 4 — Write memory

MEMORY[fact]: Improved expanded goal card child items in `frontend/src/components/Card.tsx`: title upgraded to `text-sm font-medium text-ink` (from `text-xs text-ink-muted`), row padding to `py-1.5` (from `py-1`), `divide-y divide-hairline` added for row separation, and goal-type badge restored (had been accidentally dropped by sibling "prominent status indicators" commit).

MEMORY[observation]: The "prominent status indicators" commit (`ff9bd52`) inadvertently dropped the goal-type badge added by the "distinguish subtasks" commit (`9b6e408`) because it replaced the STATE_DOT region without preserving the newly-added badge. When multiple agents commit to the same feature branch in sequence, later commits can silently drop earlier additions — always diff against HEAD before committing.

STATUS: DONE
```
