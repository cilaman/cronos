---
agent_mode: auto
agent_model: default
claude_session_id: 8f6a8d48-5c6e-4556-9101-0d405e856165
created_at: '2026-05-27T07:18:43Z'
depends_on: []
id: 2026-05-27-0718-rename-board-kanban-and-memory-memory-br
manual_order: 0
parent_id: 2026-05-27-0715-menu-changes-goal
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Rename Board → Kanban and Memory → Memory Browser
type: task
updated_at: '2026-06-03T09:05:03Z'
waiting_question: null
---

# Brief

This is the FIRST developing task for the menu-changes goal.

Start by running /goal-branch-setup to create the feature branch.

Then make these label-only changes (keep routes as-is to avoid breaking deep links):

1. frontend/src/components/Sidebar.tsx
   - Change nav label "Board" → "Kanban"
   - Change nav label "Memory" → "Memory Browser"

2. frontend/src/pages/BoardPage.tsx — if the page has an <h1> or header title, update it to say "Kanban"

3. frontend/src/pages/MemoryPage.tsx — if the page has an <h1> or header title, update it to say "Memory Browser"

4. Any other places that display these names as visible labels (not route strings).

Routes /board and /memory stay unchanged.

Run frontend tests (cd frontend && npm test) and verify no regressions, then run /goal-task-commit.

# History

```
2026-05-27T08:06:19Z [agent]
I'll start by running the goal-branch-setup skill to create the feature branch.

Feature branch created and checked out. Now let me look at the files to change.

Let me check if BoardPage and MemoryPage have visible headers.

Let me read the rest of MemoryPage.tsx to find any page title.

MemoryPage's h1 already says "Memory Browser" but the subtitle says "Cronos · Memory". BoardPage has no visible h1. Now I'll make the changes.

Now run the frontend tests.

The test failure is about `useRoutePreview` not being in the `useTasks` mock — that's pre-existing and unrelated to my label changes. Let me confirm by checking which tests failed.

Let me verify this failure is pre-existing (not caused by my changes) by checking if `useRoutePreview` was recently added.

The 9 failing tests are pre-existing (same 1 failed file, 9 failed tests without my changes). My changes introduced no regressions. Now I'll run `/goal-task-commit`.

On `feature/menu-changes-goal`. Tests already confirmed passing (9 pre-existing failures, no regressions). Now staging and committing.

Done. The commit `c416f23` is on `feature/menu-changes-goal` and pushed to origin.

**Summary of changes:**
- `frontend/src/components/Sidebar.tsx`: nav label "Board" → "Kanban", "Memory" → "Memory Browser"
- `frontend/src/pages/MemoryPage.tsx`: subtitle `Cronos · Memory` → `Cronos · Memory Browser` (the `<h1>` already said "Memory Browser")
- `BoardPage.tsx` has no visible page title — no change needed

Frontend tests: 652 passing, 9 pre-existing failures in `Detail.test.tsx` (missing `useRoutePreview` mock, unrelated to this task).
```
