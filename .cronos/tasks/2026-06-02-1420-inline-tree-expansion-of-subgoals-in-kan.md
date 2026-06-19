---
agent_mode: auto
agent_model: default
claude_session_id: e3562efc-e676-449c-bd71-d621bd7b61ef
created_at: '2026-06-02T14:20:22Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-02-1420-inline-tree-expansion-of-subgoals-in-kan
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
title: Inline tree expansion of subgoals in kanban cards
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

When a goal card in the kanban board is expanded and it contains sub-goals as children, those sub-goals should themselves be expandable — revealing their own child tasks. This creates an inline tree view within the kanban card.

## Problem
Currently, expanding a goal card shows a flat list of direct children only. If a child is itself a goal (sub-goal), there is no way to drill down to see its tasks without navigating away.

## Desired UX
- Goal card expanded: shows direct children list
- Sub-goal children in the list have a small expand chevron (▶)
- Clicking the chevron expands that sub-goal inline, showing ITS children as a nested list
- Nesting can go arbitrarily deep (goals within goals within goals)
- This mirrors what the Tree view already does in TreeNode.tsx

## Technical approach
1. **Backend**: Each `ChildProgressItem` that is a goal needs to expose its own `children_progress` (or at minimum a `has_children` boolean and the count). This avoids N+1 by including it in the initial board response.
2. **Frontend - data**: The `ChildProgressItem` interface needs `children_progress?: { done, total, waiting, items? }` for goal children.
3. **Frontend - state**: Track which child goals are expanded (local state in Card.tsx — a Set of expanded child IDs).
4. **Frontend - rendering**: For goal children with children, render an expand button and a nested children panel (recursive or iterative).

# History

```
2026-06-02T15:18:59Z [agent]
I'll start by reading the relevant files to understand the current state before implementing the inline tree expansion.

Now let me read the full Card.tsx to understand the full component structure and see if `type` was already added.

Now let me check the current state of types.ts and models.py to see what `type` field support is already there.

Let me check the git branch and recent changes in the main codebase.

There's a feature branch for this goal. Let me check what changes are already on it.

The feature branch already has sibling tasks' work. Let me check out the feature branch and read the current file states.

The feature branch is checked out in a sibling worktree. I'll work directly with those files. Let me read the current state of the files on the feature branch.

Now let me read the full Card.tsx on the feature branch to understand the current state.

Now let me read the backend tasks.py `_enrich_progress()` in the feature branch.

Let me check the existing test files and the backend models more carefully.

Now let me check if there are relevant backend tests for `_enrich_progress`.

Now I have everything I need. Let me implement all the changes. I'll work directly in the feature branch worktree.

**Plan:**
1. `backend/app/models.py` — add `children_progress` field to `ChildItem`, add `model_rebuild()`
2. `backend/app/api/tasks.py` — add recursive `make_child_item()` in `_enrich_progress()`
3. `frontend/src/types.ts` — add `children_progress` to `ChildProgressItem`
4. `frontend/src/components/Card.tsx` — add `useState`, `ChildRow` component, wire up expansion state
5. Add tests for the new behavior

Now update the backend `_enrich_progress()` to recursively build child items:

Now update the frontend types:

Now update Card.tsx — add React import, `ChildProgressItem` import, `ChildRow` component, and expansion state:

Now add the `ChildRow` component before the `Card` component, and update the `Card` component to use it with state:

Now add `expandedChildIds` state to the Card component and replace the flat children panel with `ChildRow`:

Now replace the flat children panel rendering with `ChildRow`:

Now let me run the backend and frontend tests to check things work:

The model works. Now let me run the backend tests:

Tests pass. Now let me run the frontend tests to ensure existing tests still pass:

All 678 frontend tests pass. Now I'll add tests for the new inline tree expansion feature.

Now add the backend test for nested goal children_progress:

Now let me run the new backend tests:

Now run the new frontend tests:

One test has a faulty assertion — the test mixes a regular task child and a sub-goal child together, but then queries globally. Let me fix it:

All 54 Card tests pass. Let me run the full frontend test suite to confirm no regressions:

688 tests pass (10 new). Let me run the relevant backend tests too:

All backend tests pass too. Now let me commit this work to the feature branch:

Good — on the right feature branch. The tests already passed. Let me stage and commit from the feature branch worktree:

Pushed. Let me finalize the task:

## Step 1 — Verify completion

All requirements met:
- ✅ Backend: `ChildItem` now carries `children_progress: ChildrenProgress | None` (with `model_rebuild()`); `_enrich_progress()` recursively populates it for goal-type children via `make_child_item()`
- ✅ Frontend `types.ts`: `ChildProgressItem` interface has `children_progress` (self-referential)
- ✅ Frontend `Card.tsx`: `ChildRow` component with expand/collapse state (`Set<string>`) renders inline nested children for goal-type child items; arbitrary depth via recursion
- ✅ 9 new frontend tests + 2 new backend tests; full suite green (688 frontend, 7 backend `children_progress` tests)
- ✅ Committed and pushed to `feature/task-goal-tile-visualization-improvement`

## Step 3 — Handle git

Already committed and pushed via `goal-task-commit` earlier in the run.

## Step 4 — Write memory

Memory written. 

STATUS: DONE
```
