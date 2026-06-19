---
agent_mode: auto
agent_model: default
claude_session_id: a6ffbf39-5a35-4114-8890-b3ffd520be0e
created_at: '2026-06-09T07:46:40Z'
depends_on:
- 2026-06-09-0746-create-featureform-modal-component
feature_key: null
feature_state: null
id: 2026-06-09-0746-replace-inline-featurecomposer-with-feat
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
title: Replace inline FeatureComposer with FeatureForm modal in FeaturesBoard
type: task
updated_at: '2026-06-16T09:30:16Z'
waiting_question: null
---

# Brief

Update frontend/src/components/FeaturesBoard.tsx to replace the inline FeatureComposer sub-component with the new FeatureForm modal.

Changes:
- Remove the FeatureComposer inline sub-component (currently defined within FeaturesBoard.tsx, handles inline title input + type radio + Add button)
- Add showAddModal boolean state to the FeaturesBoard component
- The Backlog lane header "+" button (Lane onAdd prop) should set showAddModal = true
- Render <FeatureForm spaceId={space.id} onClose={() => setShowAddModal(false)} /> when showAddModal is true
- Remove any composerExpanded / composerRef / focus-management state that supported the inline form
- The Lane component already has an onAdd callback prop — wire it to open the modal

Reference files:
- frontend/src/components/FeaturesBoard.tsx (file to modify)
- frontend/src/components/FeatureForm.tsx (new modal component, created in T1)
- frontend/src/components/Lane.tsx (Lane onAdd prop pattern)

# History

```
2026-06-09T08:34:33Z [agent]
I'll read the relevant files to understand the current structure before making changes.

Let me check the main codebase for FeatureForm.tsx.

FeatureForm.tsx doesn't exist yet. Let me check the workspace structure to understand what's available.

FeatureForm.tsx doesn't exist yet. I need to create it first, then update FeaturesBoard. Let me check TaskForm.tsx for the modal pattern, and also check the hooks and API.

Let me check TaskForm.tsx for the modal pattern, and the relevant parts of api.ts.

Now I have everything I need. Let me check the UI components and see if priority is in the API already.

Let me check git branches and existing work.

T1 branch exists. Let me check its changes.

The feature branch has FeatureForm already created. Let me check what's on it.

The feature branch already has `FeatureForm.tsx`. I need to check out that branch and get the files from there, then make the FeaturesBoard changes.

Now let me get the api.ts and useFeatures.ts changes from T1.

Now I have everything. I'll create FeatureForm.tsx, update api.ts and useFeatures.ts (T1 work), then update FeaturesBoard.tsx (T2 work).

Now update `api.ts` to add `priority` to `createFeature`:

Now update `useFeatures.ts` to add `priority` to `useCreateFeature`:

Now update `FeaturesBoard.tsx` to replace the inline FeatureComposer with the modal:

Now remove the FeatureComposer sub-component definition and the related interfaces:

Now update the FeaturesBoard component internals — remove `composerInputRef`, add `showAddModal` state:

Now update the Lane `onAdd` callback and remove the inline FeatureComposer rendering:

Now add the `FeatureForm` modal render after the DndContext closing tag:

Let me verify the final state of FeaturesBoard.tsx looks correct:

The file looks correct. Now let me run the frontend tests to verify everything compiles and the tests pass.

Need to install dependencies first.

3 tests failed in FeaturesBoard.test.tsx because they still look for inline composer elements. Let me see those tests.

Let me see the full test setup to understand the mocks.

Now I'll update the tests. I need to add a FeatureForm mock and replace the 3 broken inline-composer tests with modal open/close tests.

First, let me check where the vi.mock for FeatureDetail is to add the FeatureForm mock nearby:

Now replace the 3 failing FeatureComposer tests with modal open/close tests:

Now run the tests again to verify:

Waiting for the updated test run to complete.

All 1160 tests pass. Now let me finalize the task.

I need to switch to the feature branch. It already exists so I'll check it out directly.

The feature branch is in another worktree. I'll copy the changed files to the space's main directory and commit from there.

The T1 worktree already has the FeatureForm, api.ts, and useFeatures.ts changes. I only need to copy the FeaturesBoard files to the T1 worktree and commit.

Pushed. Now finalize the task.

## Step 1 — Verify completion

All requirements from the task brief were met:
- ✅ Removed `FeatureComposer` inline sub-component and its `ComposerProps` interface
- ✅ Added `showAddModal` boolean state
- ✅ Backlog lane `onAdd` wired to `setShowAddModal(true)`
- ✅ `<FeatureForm spaceId={spaceId} onClose={() => setShowAddModal(false)} />` rendered when `showAddModal` is true
- ✅ Removed `composerInputRef` and focus-management state
- ✅ Removed `useCreateFeature` import from FeaturesBoard (no longer needed there)
- ✅ Also created `FeatureForm.tsx` + updated `api.ts`/`useFeatures.ts` (T1 prereqs missing from branch)
- ✅ All 1160 tests pass

## Step 3 — Handle git

Already completed via goal-task-commit: committed `83caed1` and pushed to `feature/implement-adding-feature-dialogue`.

## Step 4 — Write memory

Memory written. All steps complete.

STATUS: DONE
```
