---
agent_mode: auto
agent_model: sonnet
claude_session_id: 6bcba2c1-330a-41a1-8b56-57698ff8821b
created_at: '2026-06-07T11:27:59Z'
depends_on:
- 2026-06-07-1127-architect-api-client-hooks
feature_key: null
feature_state: null
id: 2026-06-07-1127-impl-api-client-hooks
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1127-sg1-api-client-hooks-for-feature-detail
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: impl – api-client-hooks
type: task
updated_at: '2026-06-15T10:30:16Z'
waiting_question: null
---

# Brief

CC-v1 impl phase for: SG1 API Client + Hooks for Feature Detail.

Scout report: `.cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md`

Scope:
- `frontend/src/api.ts` — add getFeature(id), patchFeature(id, body), processFeature(id), setRealize(featureId, body)
- `frontend/src/hooks/useFeatures.ts` — add useFeature(id), usePatchFeature(), useProcessFeature(), useSetRealize()
  All new hooks must use the existing `invalidateFeatureQueries(qc, spaceId)` triple-key invalidation.

Agent contract: `.claude/agents/pipeline-implementor.md`
Artifact: `.cronos/pipeline/feature-detail-view/impl-report-api-client-hooks.md`

Then run: /pipeline-gate

# History

```
2026-06-08T09:45:26Z [agent]
I'll read the key files before making changes.

Now let me read the current state of the files I need to modify.

Let me check the TypeScript types and backend models to understand the FeatureRead shape.

Let me check the backend models for FeatureRead and the API endpoints for processFeature and setRealize.

Let me check the useTasks.ts hook patterns for reference.

I have all the information needed. Now I'll implement the changes across all three files.

**Step 1:** Add `FeatureRead` interface to `types.ts`

`FeatureRead` needs `TaskType` which is defined later in the file. Let me verify the ordering is fine.

TypeScript interfaces are hoisted, so forward references are fine. Now **Step 2:** add `FeatureRead` to the import in `api.ts` and add the 4 methods.

Now add the 4 API methods to the features section:

**Step 3:** Add 4 hooks to `useFeatures.ts`:

Now add the 4 new hooks at the end of the file:

Now let's run the frontend tests to verify nothing is broken:

TypeScript check passed (no output = no errors). Let me read the test results:

All 1110 tests pass. Now let me verify the final state of the changed files:

Now let me write the impl report artifact and run the pipeline gate.

Now run the pipeline gate:

Now I'll execute the pipeline gate. Let me first establish the required inputs from the task brief.

The verifier expects `impl-report-feature-detail-view--api-client-hooks.md`. I need to rename the artifact with the correct full slug.

I need to rename the artifact with the correct full slug. Let me fix this:

Now run the pipeline gate steps:

The artifact is missing required CC-v1 fields for the `implementation` phase. Let me check the schema:

The schema requires `iteration_id` to match `^I[0-9]+$`. I need to check existing impl reports to understand the correct pattern:

The convention is `impl-report-{goal_slug}--i{N}.md`. This is the first (and only) iteration, so it's `I1`. I need to rename the artifact and fix the fields:

Now run the verifier against the correctly named artifact:

Verifier passes. Now run the state writer:

Both steps passed. Now run the `task-finalize` skill to commit and push the changes.

gate PASS — implementation / feature-detail-view
  artifact: .cronos/pipeline/feature-detail-view/impl-report-feature-detail-view--i1.md

STATUS: DONE
```
