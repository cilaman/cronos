---
agent_mode: auto
agent_model: default
claude_session_id: ec9f3779-e5fe-4bf5-8474-86f4af068198
created_at: '2026-06-09T07:46:40Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-09-0746-create-featureform-modal-component
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
title: Create FeatureForm modal component
type: task
updated_at: '2026-06-16T08:30:16Z'
waiting_question: null
---

# Brief

Create frontend/src/components/FeatureForm.tsx — a proper modal for creating features, following the pattern established by TaskForm.tsx.

Requirements:
- Use the Modal base component from components/ui/Modal.tsx
- Header: "New Feature" or "New Fix" (updates with type selection)
- Body fields:
  - Type toggle: Feature (emerald) | Fix (rose) — default Feature
  - Title: required text input, autofocus, max 200 chars
  - Priority: P1-P5 buttons (styled like TaskForm)
  - Brief: optional textarea (8 rows, monospace, markdown hint)
- Footer: Cancel + "Add Feature" / "Add Fix" submit button
- Escape key and backdrop click close the modal
- Uses useCreateFeature(spaceId) hook from hooks/useFeatures.ts
- On success: close modal, query invalidation handles refresh
- Validation: submit disabled if title empty; show API error if mutation fails
- Styling: match existing dark-mode theme (bg-surface-1, neutral borders)

Props: { spaceId: string; onClose: () => void }

Reference files:
- frontend/src/components/TaskForm.tsx (pattern to follow)
- frontend/src/components/ui/Modal.tsx (base modal component)
- frontend/src/hooks/useFeatures.ts (useCreateFeature hook)
- frontend/src/types.ts (FeatureRead type)

# History

```
2026-06-09T08:08:06Z [agent]
I'll read the reference files to understand the patterns before implementing the component.

Now let me check the `createFeature` API function to understand the expected body:

Let me check the FeaturesBoard and the api.ts for the createFeature signature:

Let me check the backend feature creation endpoint and api.ts:

Let me check the FormField and Button components to understand their props:

Now I have all the information I need. Let me implement the changes:

1. Update `api.ts` to pass `priority` through
2. Update `useFeatures.ts` hook to accept `priority`
3. Create `FeatureForm.tsx`

Now create the `FeatureForm.tsx` component:

Now let me verify the TypeScript compiles correctly by running the build:

TypeScript compiles cleanly. Now let me run the frontend tests to make sure nothing is broken:

All 1161 tests pass. Now let me finalize the task:

## Step 1 — Verify completion

All requirements met:
- `FeatureForm.tsx` created with Modal, type toggle (Feature/Fix), Title, Priority (P1-P5), Brief textarea
- Header updates dynamically with type selection
- Escape key + backdrop click close modal
- `useCreateFeature` hook used; submit disabled when title empty; API error shown on failure
- Updated `api.ts` and `useFeatures.ts` to thread `priority` through
- 1161 frontend tests pass

## Step 3 — Handle git

Goal child task — delegating to goal-task-commit.

Not on the feature branch — running goal-branch-setup first.

Now on the feature branch. Back to goal-task-commit — running tests then committing.

The changes are in the main worktree. I need to copy them to the workspace worktree (now on the feature branch) and commit there:

Pushed. Back to task-finalize Step 4 — writing memory.

## Step 4 — Write memory

MEMORY[fact]: Created `frontend/src/components/FeatureForm.tsx` — modal for creating features/fixes. Props: `{ spaceId, onClose }`. Fields: type toggle (Feature/emerald | Fix/rose), title (autofocus, max 200), priority P1-P5, brief textarea. Uses `useCreateFeature` hook; header title updates with type; Escape key handled via `useEffect`. Also updated `api.ts` `createFeature` body type and `useFeatures.ts` `useCreateFeature` mutation body type to add optional `priority?: number` field (backend `CreateFeatureBody` already supported it).

STATUS: DONE
```
