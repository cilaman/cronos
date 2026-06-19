---
agent_mode: auto
agent_model: default
claude_session_id: d753eadf-d3aa-4615-9937-5a7a0dc4ef59
created_at: '2026-06-06T08:45:02Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-06-0845-tasks-site-error
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Tasks site error
type: task
updated_at: '2026-06-13T10:30:16Z'
waiting_question: null
---

# Brief

Tasks page cannot be used because it asis me to choose space on the left menu but there is no way how to choose space. Please add to the page space selector the same way as it is on other pages

# History

```
2026-06-06T09:01:35Z [agent] run=0 model=claude-sonnet-4-6 mode=auto
Let me look at the current Tasks page and how space selection works on other pages.

I don't see a TasksPage.tsx. Let me check the routing and see where the "Tasks" page is defined.

Now let me check the Sidebar and routes to understand what "Tasks" page the user is referring to.

The "Tasks" link in the sidebar goes to `/board`. Let me look at the BoardPage and the route configuration.

Now let me look at the BoardToolbar to understand the current space selector.

Now let me check the SpaceFilterDropdown component and ArchivedPage (another global page) to understand the full pattern.

Let me check the Board component to understand what happens when no space is selected.

Now let me look at the SpaceFilterDropdown component.

Let me check the FeaturesPage since that may be the problematic "Tasks" page (looking at the context).

Let me check the storage lib to understand `readBoardSpaceFilter`.

Now I understand the issue. The `FeaturesPage` shows "Pick a space from the sidebar" when no space is selected, but there's no space selector on that page. Let me check the FeaturesBoard to understand the complete component.

Let me check the StickyToolbar component.

Now I have enough context to fix the `FeaturesPage`. The issue is clear: the `/features` route shows "Pick a space from the sidebar" with no way to select one directly. I'll add a space selector toolbar following the same pattern as `HarnessesPage`.

Now let me verify the TypeScript compiles cleanly.

No TypeScript errors. Now let me run the frontend tests to ensure nothing is broken.

The tests are still running. Let me wait for the notification and check when complete.

2 tests failed. Let me check if they're pre-existing or caused by my change.

The tests are failing in `FeaturesBoard.test.tsx` because my loading state check blocks the scoped view. Let me look at those tests.

Let me read the full test file to understand all the tests that need updating.

Now I need to fix FeaturesPage (don't show loading for the scoped case) and update the tests. Let me do both.

Now update the tests to mock `useSpaces` and match the new behavior.

Now update the empty-state tests to match the new behavior:

Now let me verify TypeScript still compiles cleanly and run the tests again.

All 1110 tests pass. Now let me commit the fix and finalize the task.

The main worktree is still on the old feature branch. I need to get my changes onto main.

Need to abort the cherry-pick and copy files to the main-branch worktree instead.

Pushed to main. Now let me write memory and upgrade the app.

MEMORY[fact]: FeaturesPage at `frontend/src/pages/FeaturesPage.tsx` refactored into `ScopedFeaturesPage` + `GlobalFeaturesPage` components. GlobalFeaturesPage has `SpaceFilterDropdown` in a `StickyToolbar`, URL `?space=` param, localStorage key `cronos.features.lastSpaceId`, and auto-select first space. FeaturesBoard tests in `frontend/src/components/__tests__/FeaturesBoard.test.tsx` mock `useSpaces` and test the new dropdown behavior.

MEMORY[observation]: When the main worktree is on a stale feature branch (not main), committing standalone task changes there is wrong. Use `git worktree list | grep "\[main\]"` to find the main-branch worktree, copy files there, and commit+push from that worktree path.

Now update MEMORY.md:

Memory written. Now upgrade the app.

Now I need to trigger the upgrade so the fix is live.

STATUS: DONE

```
curl -s -X POST http://172.18.0.1:9137/upgrade
```

The fix is deployed. Here's what was done:

**Root cause**: The "Features" page (`/features`, labeled in the sidebar) showed "Pick a space from the sidebar" with no actual way to pick a space on that page.

**Fix**: Refactored `frontend/src/pages/FeaturesPage.tsx` into two components:
- **`ScopedFeaturesPage`** — for `/spaces/:spaceId/features` routes (space pre-determined, renders board directly)
- **`GlobalFeaturesPage`** — for the global `/features` route; adds a `SpaceFilterDropdown` in a sticky toolbar with URL `?space=` param persistence, `localStorage` memory, and auto-selects the first space on first visit

Tests in `FeaturesBoard.test.tsx` were updated to mock `useSpaces` and verify the new dropdown behavior. All 1110 tests pass.

STATUS: DONE
```

```
2026-06-06T09:35:51Z [user]
I was wrong, the problem of missing space selection is on features page
```

```
2026-06-06T09:36:02Z [agent] run=1 model=claude-sonnet-4-6 mode=auto
That's exactly what I fixed — the Features page at `/features` was showing "Pick a space from the sidebar" with no way to select one. The fix adds a `SpaceFilterDropdown` to that page's toolbar, auto-selects the first space on first visit, and persists the selection in the URL and localStorage. The upgrade was already deployed.
```
