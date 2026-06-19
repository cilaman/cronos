---
agent_mode: auto
agent_model: default
claude_session_id: 4f61fc34-9942-412f-ad6f-fa7071b0b3bf
created_at: '2026-06-07T15:34:22Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1534-fix-issue-link-icon-and-render-issue-num
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
title: Fix issue link icon and render issue number (UX-1)
type: task
updated_at: '2026-06-15T13:30:16Z'
waiting_question: null
---

# Brief

In `frontend/src/components/FeaturesBoard.tsx` (or wherever feature cards render the issue link):

- When `issue_url` is set and `issue_number` is non-null: render as an `<a href={issue_url}>` with a GitHub-branded icon (or `IconGitPullRequest` / `IconBrandGithub` from tabler-icons) and the text `#${issue_number}`
- When only `proposed_issue_path` is set (no GitHub issue yet): render as a file icon with "Draft issue" label
- When neither is set: render nothing

Also fix the icon style: issue links should be visually distinct from PR links.

# History

```
2026-06-08T12:53:19Z [agent]
Let me look at the current FeaturesBoard.tsx to understand the existing issue link rendering.

The issue link rendering is likely in Card.tsx. Let me check that.

Now I can see the issue. Lines 503-514 in Card.tsx use `IconFileText` for issue links instead of a distinct icon, and don't render the issue number. Let me check the TaskSummary type for `issue_number` and `proposed_issue_path` fields.

I notice `TaskSummary` in types.ts has `issue_url` and `issue_number` but not `proposed_issue_path`. Let me also check the backend to see if it's in the task summary response.

The backend `TaskSummary` already has `proposed_issue_path`. Now I'll make the changes:

1. Add `proposed_issue_path` to frontend `TaskSummary` in `types.ts`
2. Add a GitHub issue icon to Card.tsx
3. Fix the issue link rendering logic

Now update Card.tsx to add a GitHub issue icon and fix the rendering logic:

Now update the issue link rendering logic in Card.tsx:

Now let me run the frontend tests to make sure nothing is broken:

The test is still running. Let me wait for the notification and check the tests directly from the Card test files to confirm nothing broke.

Let me check the existing tests around `issue_url`:

The test uses `title="Open issue"` but my change updated it to `"Open GitHub issue"`. I need to update the test. Let me also check the `makeTask` helper:

Now I'll update the test to use the new title and also add coverage for `issue_number` and `proposed_issue_path`:

Now let me check if the background test finished and also run a quick targeted test:

All 64 tests pass. Now let me finalize this task:

## Step 1 — Verify completion

All requirements met:
- `issue_url` + `issue_number`: renders green GitHub circle icon + `#42` link ✅
- `proposed_issue_path` only: renders file icon + "Draft issue" button ✅  
- Neither: renders nothing ✅
- Issue links visually distinct from PR links (green vs ink-faint) ✅
- All 64 Card tests pass ✅

## Step 3 — Handle git

This is a goal child task. Delegating to goal-task-commit.

Not on the feature branch. Running goal-branch-setup first.

The feature branch is used by another worktree. I need to copy the changes there and commit via git -C.

The files are modified in the main worktree. I need to copy them to the feature branch worktree and commit there.

Committed and pushed. Now completing Step 4 (memory) and Step 5 (STATUS).

## Step 4 — Write memory

MEMORY[fact]: UX-1 fix in `frontend/src/components/Card.tsx`: issue links now use `IconGitIssue` (green GitHub circle-dot SVG) + `#${issue_number}` for confirmed GitHub issues (`issue_url` set), `IconFileText` + "Draft issue" text for draft-only (`proposed_issue_path` set), and nothing when neither is present. Added `proposed_issue_path` to `TaskSummary` in `frontend/src/types.ts`. Tests updated in `frontend/src/components/__tests__/Card.test.tsx` (title changed from "Open issue" to "Open GitHub issue", 4 test cases covering all three render states).

STATUS: DONE
```
