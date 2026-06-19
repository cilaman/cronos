---
agent_mode: auto
agent_model: default
claude_session_id: 27747d69-78e9-4046-a621-46538bf68e9d
created_at: '2026-06-07T15:33:48Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1533-add-getfeature-patchfeature-processfeatu
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
title: Add getFeature, patchFeature, processFeature, setRealize to api.ts
type: task
updated_at: '2026-06-15T12:30:16Z'
waiting_question: null
---

# Brief

Add four missing API client functions to `frontend/src/api.ts`.

```typescript
// GET /api/features/{id}
export async function getFeature(taskId: string): Promise<FeatureRead> { ... }

// PATCH /api/features/{id}  body: {title?, brief?}
export async function patchFeature(taskId: string, patch: {title?: string; brief?: string}): Promise<FeatureRead> { ... }

// POST /api/features/{id}/process
export async function processFeature(taskId: string): Promise<Task> { ... }

// PATCH /api/features/{id}/realize  body: {feature_id: string | null}
export async function setRealize(taskId: string, featureId: string | null): Promise<Task> { ... }
```

Also ensure `FeatureRead` type in `api.ts` includes `waiting_question: string | null` and `realizing_items: TaskSummary[]` fields.

Write vitest unit tests for the new functions (mock fetch).

# History

```
2026-06-08T12:22:38Z [agent]
Let me read the current state of `api.ts` and the types to understand what's already there.

Now let me check the `FeatureRead` type in `types.ts`.

Let me check the backend feature API to understand the correct return types, and look for any existing api.ts tests.

Let me check the current `useFeatures.ts` and look for existing api tests.

Let me check if there's already an `api.features.test.ts`.

Let me read the full api.harness.test.ts to understand the test pattern.

Let me read the FeatureRead interface fully.

Now I have everything I need. I'll create the vitest test file for the feature API functions.

Now let me run the tests to verify they pass.

All 23 tests pass. Now let me run the full frontend test suite to make sure nothing is broken.

All 1175 tests pass (71 test files). Now let me finalize the task.

This is a goal child task — delegating to goal-task-commit.

Not on the feature branch yet — running goal-branch-setup first.

Feature branch is set up and checked out. Now back to goal-task-commit — checking for changes and committing.

These are exactly the changes this task requires — `api.ts` has the 4 new functions + `FeatureRead` import, `types.ts` has the `FeatureRead` interface, and `api.features.test.ts` is the new test file. All three need to be committed.

Committed and pushed. Now writing memory.

MEMORY[fact]: Task `2026-06-07-1533-add-getfeature-patchfeature-processfeatu` added `FeatureRead` interface to `frontend/src/types.ts` and four API client functions (`getFeature`, `patchFeature`, `processFeature`, `setRealize`) to `frontend/src/api.ts`, plus 23 vitest unit tests at `frontend/src/__tests__/api.features.test.ts` (mock-fetch pattern matching `api.harness.test.ts`); committed aa089d0 on `feature/build-feature-detail-panel-and-wire-miss`.

STATUS: DONE
```
