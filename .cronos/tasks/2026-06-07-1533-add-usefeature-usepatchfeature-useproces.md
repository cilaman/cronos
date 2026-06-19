---
agent_mode: auto
agent_model: default
claude_session_id: 1d0ee9e2-ef99-4815-b2a2-0ccafd2f5a2b
created_at: '2026-06-07T15:33:48Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1533-add-usefeature-usepatchfeature-useproces
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1533-build-feature-detail-panel-and-wire-miss
pending_messages: []
pr_url: null
priority: 1
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Add useFeature, usePatchFeature, useProcessFeature, useSetRealize hooks
type: task
updated_at: '2026-06-15T12:30:16Z'
waiting_question: null
---

# Brief

Add four React Query hooks to `frontend/src/hooks/useFeatures.ts`:

```typescript
// Single feature fetch
export function useFeature(taskId: string | null) { ... }

// Edit mutation  
export function usePatchFeature() { ... }

// Process (decompose) mutation
export function useProcessFeature() { ... }

// Realize/unrealize mutation
export function useSetRealize() { ... }
```

All mutations should call `invalidateFeatureQueries(qc, spaceId)` on success (triple-key invalidation R4 contract).

`useProcessFeature` should handle 409 responses gracefully (feature already processing) and show a toast/error.

# History

```
2026-06-08T12:24:08Z [agent]
I'll start by reading the current state of the relevant files to understand what's already in place.

The hooks are already implemented. Let me verify the API functions exist and run the tests to confirm everything passes.

Good. Now let me run the tests to verify everything passes.

The workspace doesn't have node_modules. Tests need to run from the main project.

All 19 tests pass. Now let me finalize the task.

This is a goal child task. Delegating to goal-task-commit.

Not on the feature branch — need to run goal-branch-setup first.

The feature branch is checked out in another worktree. I need to compare workspace files to the main project to see if there are changes to commit.

The workspace files are identical to the main project — the hooks were already implemented and committed in a prior task. No new changes to commit.

MEMORY[fact]: Task `2026-06-07-1533-add-usefeature-usepatchfeature-useproces` verified that all four React Query hooks (`useFeature`, `usePatchFeature`, `useProcessFeature`, `useSetRealize`) are implemented in `frontend/src/hooks/useFeatures.ts` (lines 71–136). All 19 tests in `useFeatures.test.tsx` pass. No new code changes needed — the implementation was already present from a prior task on the same feature branch.

STATUS: DONE
```
