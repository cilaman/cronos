---
agent_mode: auto
agent_model: default
claude_session_id: 2e1b9b88-5957-4d36-9fcb-07d9c00cec34
created_at: '2026-05-27T07:19:21Z'
depends_on:
- 2026-05-27-0718-rename-board-kanban-and-memory-memory-br
id: 2026-05-27-0719-extract-treeview-component-remove-tree-f
manual_order: 0
parent_id: 2026-05-27-0715-menu-changes-goal
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Extract TreeView component; remove /tree from main nav
type: task
updated_at: '2026-06-03T09:05:03Z'
waiting_question: null
---

# Brief

TreePage.tsx is a full page, but the tree view is more useful as an embeddable component. This task extracts it and removes the /tree route from the global nav.

## What to do

### 1. Create frontend/src/components/TreeView.tsx

Extract the logic from TreePage.tsx into a self-contained TreeView component with this interface:

```tsx
interface TreeViewProps {
  spaceId?: string | null;   // pre-filter to a specific space
  archivedOnly?: boolean;    // if true, load archived tasks instead of board tasks
}
export function TreeView({ spaceId, archivedOnly }: TreeViewProps) { ... }
```

The component should:
- Include the toolbar (space filter, sort mode, search/expand buttons)
- Render the Tree component
- Handle the task detail panel (Detail) internally via URL search params

TreePage.tsx itself can become a thin wrapper:
```tsx
export function TreePage() {
  const { spaceId } = useParams();
  return <TreeView spaceId={spaceId ?? null} />;
}
```

Keep TreePage.tsx and its routes (router.tsx) intact -- the page still works for space-scoped tree views via /spaces/:spaceId/tree.

### 2. Remove /tree from the global sidebar nav (frontend/src/components/Sidebar.tsx)
- Delete the NavLink for route "/tree"

### 3. Remove the global /tree route from router.tsx
- Remove the route entry for path="tree" pointing to TreePage (the global one, not the space-specific /spaces/:spaceId/tree)

### 4. Clean up imports in router.tsx if TreePage is no longer directly imported at top-level (it may still be needed for space routes)

## Checks
- Run frontend tests: cd frontend && npm test
- Fix any failures.

Finish with /goal-task-commit.

# History

```
2026-05-27T08:47:08Z [agent]
I'll start by reading the relevant files to understand the current structure.

Now I'll check the `useBoard` hook to understand how to handle the `archivedOnly` prop.

Now let me check the `useBoard` and `useArchivedTasks` hooks to understand how to handle `archivedOnly`.

Now I have everything I need. Let me create the `TreeView.tsx` component and make all the required changes.

Now update `TreePage.tsx` to be a thin wrapper:

Remove the `/tree` NavLink from `Sidebar.tsx`:

Remove the global `/tree` route from `router.tsx`:

Now let me check if `useArchivedTasks` is properly exported from the hooks file:

Good. Now run the frontend tests:

Let me check whether the test failures are pre-existing (not related to my changes):

The 9 failing tests are in `DetailPRSection.test.tsx` and involve `useRoutePreview` — unrelated to my changes. Let me verify they're pre-existing:

The 9 failures existed before my changes (same count pre-stash). Let me restore my changes:

All my changes are restored. The test suite shows 9 pre-existing failures in `DetailPRSection.test.tsx` (unrelated to tree view work), while all other 652 tests pass. Now let me commit and finish with the skill:

The feature branch `feature/menu-changes-goal` exists. I need to set up the branch in my worktree and run tests before committing.

The feature branch is checked out in the main workspace. I'll commit on this branch and push directly to `feature/menu-changes-goal`.

The tester incorrectly identified the root cause — I verified before that these 9 failures are pre-existing (same failures on main/before my changes). Let me confirm:

My changes only touch `Sidebar.tsx`, `TreePage.tsx`, `router.tsx`, and the new `TreeView.tsx` — the `DetailPRSection` failures are pre-existing on the feature branch. Proceeding to commit and push to the feature branch:

Need to rebase on top of the remote feature branch first:

Done. The task is complete:

- Created `frontend/src/components/TreeView.tsx` — self-contained component with toolbar, tree, and detail panel; accepts `spaceId` and `archivedOnly` props
- Simplified `frontend/src/pages/TreePage.tsx` to a thin wrapper around `TreeView`
- Removed the `/tree` NavLink from `Sidebar.tsx`
- Removed the global `path="tree"` route from `router.tsx` (space-scoped `/spaces/:spaceId/tree` route remains intact)
- All 652 tests pass (9 pre-existing failures in `DetailPRSection.test.tsx` unrelated to this change)
- Committed and pushed to `feature/menu-changes-goal`
```
