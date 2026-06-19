---
agent_mode: auto
agent_model: default
claude_session_id: b0f3416f-5e46-4fcc-9eea-580097333d75
created_at: '2026-06-09T07:46:41Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-09-0746-update-featuredetail-to-align-with-task
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-09-0746-implement-adding-feature-dialogue
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Update FeatureDetail to align with task/goal editing UX
type: task
updated_at: '2026-06-16T08:30:16Z'
waiting_question: null
---

# Brief

Update frontend/src/components/FeatureDetail.tsx to align the editing and action UX with task/goal detail patterns.

Specific changes:

1. Process button → Start/play icon:
   - In the "Decompose" section, replace the "Process" button with a compact play/start icon button
   - Match the style used for run/start actions in task and goal details (look at how TaskDetail shows the start action)
   - The icon button should still call useProcessFeature on click
   - Add a tooltip or label for clarity (e.g. "Start decomposition")

2. Type editing in edit mode:
   - Currently the type badge (Feature / Fix) in the header is read-only
   - In edit mode, add a type toggle (two buttons: Feature | Fix) alongside the title/brief fields
   - Wire to usePatchFeature which already accepts a type field in the PATCH payload
   - Default to the current feature type when entering edit mode

3. Field styling in edit mode should match the modal form pattern (consistent padding, borders, labels)

Reference files:
- frontend/src/components/FeatureDetail.tsx (file to modify)
- frontend/src/components/TaskDetail.tsx (or similar — look for start/run icon pattern)
- frontend/src/hooks/useFeatures.ts (useProcessFeature, usePatchFeature)

# History

```
2026-06-09T08:19:43Z [agent]
I'll read the relevant files to understand the current implementation before making changes.

Let me search for TaskDetail or goal-related components that show start/run action icons.

Let me read the IconButton component and check the patchFeature API signature.

Now I have all I need. Let me make the three changes:
1. Add `type` to `api.ts` patchFeature body type
2. Add `type` to `usePatchFeature` mutation body type
3. Update `FeatureDetail.tsx` with the play icon button and type toggle in edit mode

Now update `FeatureDetail.tsx` with the play icon button and type toggle in edit mode:

Now update the edit section to include the type toggle:

Now replace the "Process" button with a compact play IconButton:

Now let me verify the final state of the file:

The code looks correct. Now let me run the frontend tests to verify nothing broke:

There are 4 test failures in FeatureDetail.test.tsx due to the aria-label change. Let me look at the test file:

Now I need to fix the 4 failing tests to match the new aria-labels:

Waiting for the test run to complete:

All 23 FeatureDetail tests pass. Let me also check the existing edit test to see if it needs updating for the `type` field in the patchFeature call:

The test uses `objectContaining` so it's flexible enough to pass with the added `type` field. The full test suite result from the background task shows `0 failed`. Let me confirm by checking the output:

All 1161 tests pass. Now let me finalize the task:

## Step 1 — Verify completion

All requirements met:
1. ✅ "Process" button replaced with `IconButton` (▶, variant="accent", aria-label="Start decomposition")
2. ✅ Type toggle (Feature | Fix) added in edit mode, wired to `usePatchFeature` via `type` field
3. ✅ Edit mode fields now have labels (Type, Title, Brief) matching modal form pattern
4. ✅ `api.ts` and `useFeatures.ts` updated to accept `type` in patchFeature body
5. ✅ All 1161 tests pass

Goal child task — delegating to goal-task-commit:

Not on the feature branch — need to run goal-branch-setup first:

The feature branch is in another worktree. I need to copy my changes there and commit from it:

Committed and pushed. Now writing memory:

MEMORY[fact]: Updated `FeatureDetail.tsx` — replaced "Process" button with `IconButton` (variant=accent, ▶, aria-label="Start decomposition"); added type toggle (Feature/Fix) in edit mode wired to `usePatchFeature`; also updated `api.ts` and `useFeatures.ts` to accept `type?: "feature" | "fix"` in patchFeature body. 4 test files updated.

MEMORY[observation]: Feature branch in another task's worktree → copy changed files to that worktree then `git -C <other-worktree> add/commit/push`; don't try to `git checkout` the branch in the current workspace.

STATUS: DONE
```
