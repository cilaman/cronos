---
agent_mode: auto
agent_model: sonnet
claude_session_id: bdd9b76f-f6d9-4247-a2cb-07877ca73fef
created_at: '2026-06-07T11:27:59Z'
depends_on:
- 2026-06-07-1127-architect-feature-detail-panel
feature_key: null
feature_state: null
id: 2026-06-07-1127-impl-feature-detail-panel
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1127-sg2-featuredetail-panel-board-wiring
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: impl – feature-detail-panel
type: task
updated_at: '2026-06-15T11:30:16Z'
waiting_question: null
---

# Brief

CC-v1 impl phase for: SG2 FeatureDetail Panel + Board Wiring.

Scout report: `.cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md`

Scope:
- `frontend/src/components/FeatureDetail.tsx` (new file)
- `frontend/src/components/FeaturesBoard.tsx` — wire onOpen to write ?feature=<id> to URL
- `frontend/src/pages/FeaturesPage.tsx` — mount FeatureDetail when ?feature param present
- `frontend/src/components/Board.tsx` — fix shared-backlog card click to deep-link to ?feature=<id>

The FeatureDetail panel must use the hooks from SG1 (useFeature, usePatchFeature,
useProcessFeature, useSetRealize). Mirror the `Detail.tsx` + `Board.tsx:55-322` pattern
for panel lifecycle, URL param management, and onClose behavior.

Agent contract: `.claude/agents/pipeline-implementor.md`
Artifact: `.cronos/pipeline/feature-detail-view/impl-report-feature-detail-panel.md`

Then run: /pipeline-gate

# History

```
2026-06-08T10:53:33Z [agent]
I'll start by reading the design report and key existing files to understand what needs to be implemented.

Let me read the design report and the existing relevant files.

Good - api.ts already has the feature methods. Let me check types.ts and the hooks, then read the existing files I need to modify.

Now let me read the Board.tsx and Detail.tsx files to understand the patterns I need to mirror.

Now let me look at the Modal component and check the existing FeaturesBoard tests.

Let me check what was already done in I1.

Let me check the Lane component and existing Board tests for context.

Let me check the STATE_BADGE for feature states and the Card component structure.

Let me read the full Board.tsx context and the Detail.tsx editing/brief sections.

Let me check how Lane passes the onOpen to Card.

Now I have all the context I need. Let me implement all the changes in parallel.

Now let me create the test file for FeatureDetail:

Now let me update FeaturesBoard.tsx to wire the detail panel:

Now add the URL param management and state inside FeaturesBoard component:

Now wire the Lane `onOpen` and update the return to mount FeatureDetail:

Now update the return to wrap with a fragment and mount FeatureDetail:

Now fix Board.tsx deep-link (lines 308-309):

Now update the existing Board.sharedBacklog.test.tsx to expect the new deep-link URL:

Now create the new Board.features-backlog.test.tsx test file:

Now update the FeaturesBoard test to add the mock for FeatureDetail and add card-click tests. First let me add the mock and new test cases:

Now add a render helper that accepts an initial URL and add test cases for card-click behavior. First let me add a renderBoard helper with URL params and new tests at the end of the file:

Now add the new test cases at the end of the FeaturesBoard test file:

Now I also need to add `userEvent` import to FeaturesBoard.test.tsx since we're using it in the new tests:

Now let's run the tests to see if they pass. Let me start with the FeatureDetail tests:

Two test failures due to mock state not being cleared. Let me fix the test setup:

All 23 FeatureDetail tests pass. Now run the FeaturesBoard tests:

All 20 FeaturesBoard tests pass. Now run the Board tests:

All tests pass. Now let's run the full frontend build to verify no TypeScript errors:

Minor TypeScript issue - remove unused React import from the test file:

Build passes. Now let's run the full test suite to verify everything is green:

All 1152 frontend tests pass. Now let me write the impl report artifact:

Now let's run the pipeline gate:

Looking at the task brief, the artifact needs to follow CC-v1 naming convention. The slug `feature-detail-view--feature-detail-panel` means the file should be `impl-report-feature-detail-view--feature-detail-panel.md`. Let me rename it:

Now run the pipeline gate. The parameters are:
- GOAL_SLUG = `feature-detail-view`
- PHASE = `implementation`
- ITERATION_ID = `feature-detail-panel`
- AGENT_NAME = `pipeline-implementor`
- UPSTREAM_TASK_ID = `2026-06-07-1127-impl-feature-detail-panel`

The artifact is in place. Now run the full gate:

The `iteration_id` format is wrong. Let me check what the verifier actually validates:

Let me read more of the verifier to understand the slug handling:

The CC-v1 contract requires `iteration_id` to match `^I[0-9]+$` and the slug to end with `--{iter_id_lower}`. I implemented iterations I2-I5 in this task - I'll report as `I5` (the final integration iteration):

Now run the verifier again with `ITERATION_ID=I5`:

Verifier passes. Now run the state writer:

Gate passes. Now finalize the task with git commit and push.

**Step 1 — Completed:** All iterations I2-I5 implemented, 1152 tests pass, build passes, pipeline gate passed (PROCEED).

**Step 3 — Handle git**

This is a goal child task. Delegating to goal-task-commit:

Not on the feature branch. Running goal-branch-setup first:

On the feature branch. Now back to goal-task-commit — check status and commit:

I'll stage only the relevant files for this task:

Committed and pushed. Now **Step 4 — Write memory**:

Now update MEMORY.md. Let me check if it exists:

Memory written. All steps complete.

**Summary:** Implemented SG2 FeatureDetail Panel + Board Wiring (iterations I2-I5): created `FeatureDetail.tsx` with full feature panel (state badges, inline edit, waiting_question box, Process button, realizing_items), wired `FeaturesBoard.tsx` with URL param management, fixed `Board.tsx:308-309` deep-link to `/features?feature=${id}`, and added 31 new tests (all 1152 pass). Pipeline gate passed as `feature-detail-view--i5`. Committed and pushed to `feature/feature-detail-view`.

STATUS: DONE
```
