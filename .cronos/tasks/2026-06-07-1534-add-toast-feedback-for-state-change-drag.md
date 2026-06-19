---
agent_mode: auto
agent_model: default
claude_session_id: db145c05-7f57-4a2d-a3b0-aaeb5da7472e
created_at: '2026-06-07T15:34:22Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1534-add-toast-feedback-for-state-change-drag
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
title: Add toast feedback for state-change drag (UX-11) and FeatureComposer error
  (NP-1)
type: task
updated_at: '2026-06-15T13:30:16Z'
waiting_question: null
---

# Brief

Two pieces of missing user feedback:

**UX-11 — State-change drag feedback**
In `frontend/src/components/FeaturesBoard.tsx`, the `handleDragEnd` callback calls `transitionFeatureState` (from `useTransitionFeatureState`). Add:
- On success: brief success toast "Feature moved to {lane}"
- On 409 error: error toast "Cannot move to {lane} from current state"
- On other error: generic error toast "Failed to update feature state"

Use whatever toast library is already used in the Tasks board (check `BoardPage.tsx` or the notification system).

**NP-1 — FeatureComposer 400 error**
In the FeatureComposer form submission handler, when `createFeature` returns a 400, display an inline error message below the form: "This space must be linked to a git repository to create features." Do not swallow the error silently.

# History

```
2026-06-08T12:48:05Z [agent]
I'll start by exploring the relevant files to understand the toast system and the components I need to modify.

Now let me read the full FeaturesBoard.tsx to understand the complete structure before editing.

Now let me check the existing tests and the `useFeatures` hook to understand the mutation API:

Now I have everything I need. Let me implement the changes to `FeaturesBoard.tsx`:

Now update `onDragEnd` to pass success/error callbacks to `mutate`:

Now render the toast in the JSX, just before the closing `</>`:

Now update `FeatureComposer` to show inline error on 400:

Now add the inline error rendering inside the form, after the submit button row:

Now let me run the frontend tests to verify everything passes:

Need to run tests from the main space frontend directory. Let me check where the actual node_modules live:

The tests need updating — `mutate` is now called with a second argument (the callback object). Let me update the three affected test assertions:

Now let me add new tests for the toast behaviors, then copy and run:

The section 7 test has an overcomplicated pattern. Let me simplify it by adding a shared `createMutate` variable to the existing mock setup:

Now replace the complicated section 7 test with a clean version:

Now copy and run the tests:

Let me see the full failure output:

The callbacks update React state, so they need `act()`. Let me fix the new tests:

Now fix the FeatureComposer tests similarly:

All 26 tests pass. Now let me run the full frontend test suite to verify no regressions:

1181/1181 tests pass. Now let me finalize the task using the skill:

Goal child task — delegating to goal-task-commit:

Need to set up the feature branch first:

On the feature branch. Now back to goal-task-commit — stage, commit, and push:

Committed and pushed. Now write memory and emit STATUS:

MEMORY[fact]: UX-11 + NP-1 implemented in `frontend/src/components/FeaturesBoard.tsx`: `onDragEnd` now passes `onSuccess`/`onError` callbacks to `transition.mutate()` with a fixed-position toast (success = accent, error = danger); `FeatureComposer` shows an inline `role="alert"` paragraph on 400 ("This space must be linked to a git repository to create features."). Both behaviors tested in `frontend/src/components/__tests__/FeaturesBoard.test.tsx` with `act()` wrapping for state-update callbacks.

MEMORY[observation]: When adding `onError`/`onSuccess` callbacks to an existing `mutate()` call that tests mock as a bare `vi.fn()`, existing `toHaveBeenCalledWith(singleArg)` assertions fail because `mutate` now receives a second argument. Update them to `toHaveBeenCalledWith(singleArg, expect.objectContaining({onSuccess: ..., onError: ...}))`.

STATUS: DONE
```
