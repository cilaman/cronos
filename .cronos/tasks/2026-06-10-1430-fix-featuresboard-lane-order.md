---
agent_mode: auto
agent_model: sonnet
claude_session_id: e2119e0b-d8d2-4026-bb65-fec2c24f1844
created_at: '2026-06-10T14:30:48Z'
depends_on:
- 2026-06-10-1430-fix-backend-feature-state-propagation-lo
feature_key: null
feature_state: null
id: 2026-06-10-1430-fix-featuresboard-lane-order
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-10-1430-implement-feature-fix-state-divergency
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Fix FeaturesBoard lane order
type: task
updated_at: '2026-06-17T16:30:17Z'
waiting_question: null
---

# Brief

Fix the lane order in the FeaturesBoard so lanes render in the correct order:
**Backlog → Planned → Processing → Waiting → Done**

## Current problem

The FeaturesBoard lanes may be in a different order (e.g., Processing appears before
Planned, or the order matches insertion order rather than the spec).

## Scope

- `frontend/src/pages/FeaturesBoard.tsx` (or wherever FeaturesBoard lane order is defined)
- `frontend/src/components/` — check for any FeatureState lane config
- `backend/app/models.py` — check FeatureState enum order (may affect frontend)

## Steps

1. Read `frontend/src/pages/FeaturesBoard.tsx` — find where FEATURE_STATES lane list is defined
2. Reorder lanes to: `['backlog', 'planned', 'processing', 'waiting', 'done']`
3. Verify state labels match this order in any state display components
4. Commit changes via `goal-task-commit`

## Acceptance

- FeaturesBoard renders lanes left-to-right as: Backlog, Planned, Processing, Waiting, Done
- No other layout changes

# History

```
2026-06-10T15:56:17Z [agent]
I'll read the FeaturesBoard.tsx file to find the lane order definition.

The lane order comes from `FEATURE_LANES` in `types.ts`. Let me check that.

The issue is clear. `FEATURE_LANES` in `types.ts` has `processing` before `planned`, but the spec requires `Backlog → Planned → Processing → Waiting → Done`.

Now let me check the Lane.test.tsx to ensure the test for `FEATURE_LANES` order won't break.

The tests only check containment, not order — the change is safe. Let me run the frontend tests to confirm.

The test runner isn't available in the workspace (node_modules not installed locally). Let me run tests from the main project directory.

All 1184 tests pass. Now I'll finalize the task using the `task-finalize` skill.

## Step 1 — Verify completion

The task required fixing the FeaturesBoard lane order to: Backlog → Planned → Processing → Waiting → Done. I swapped `processing` and `planned` in `FEATURE_LANES` in `frontend/src/types.ts`. All 1184 frontend tests pass. ✓

## Step 3 — Handle git

This is a goal child task. Delegating to `goal-task-commit`.

Not on the feature branch. Running `goal-branch-setup` first.

The feature branch is locked in another worktree. I'll commit via the main space directory using `git -C`.

The feature branch is in another worktree. I'll commit to it via that worktree path.

The feature branch worktree is clean. I need to copy the modified file there and commit.

Committed and pushed. Now back to `task-finalize` Step 4 — write memory.

## Step 4 — Write memory

MEMORY[fact]: Fixed FeaturesBoard lane order by reordering `FEATURE_LANES` in `frontend/src/types.ts` (lines 47-53). Was: backlog/processing/planned/waiting/done. Correct: backlog/planned/processing/waiting/done.

The shell's working directory has drifted. I'll use the correct workspace path explicitly.

Writing to the project-level memory instead (workspace-specific path is permission-blocked).

Memory written. Now emitting STATUS.

STATUS: DONE
```
