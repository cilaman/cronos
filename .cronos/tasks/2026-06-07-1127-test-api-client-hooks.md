---
agent_mode: auto
agent_model: sonnet
claude_session_id: ca4658b5-083e-452c-aedc-16af94aaaa7c
created_at: '2026-06-07T11:27:59Z'
depends_on:
- 2026-06-07-1127-impl-api-client-hooks
feature_key: null
feature_state: null
id: 2026-06-07-1127-test-api-client-hooks
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
title: test – api-client-hooks
type: task
updated_at: '2026-06-15T10:30:16Z'
waiting_question: null
---

# Brief

CC-v1 test phase for: SG1 API Client + Hooks for Feature Detail.

Scout report: `.cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md`

Scope:
- `frontend/src/api.ts` — add getFeature(id), patchFeature(id, body), processFeature(id), setRealize(featureId, body)
- `frontend/src/hooks/useFeatures.ts` — add useFeature(id), usePatchFeature(), useProcessFeature(), useSetRealize()
  All new hooks must use the existing `invalidateFeatureQueries(qc, spaceId)` triple-key invalidation.

Agent contract: `.claude/agents/pipeline-tester.md`
Artifact: `.cronos/pipeline/feature-detail-view/test-report-api-client-hooks.md`

Then run: /pipeline-gate

# History

```
2026-06-08T09:57:13Z [agent]
I'll start by reading the relevant files to understand the current state and what needs to be tested.

The API methods are already implemented. Let me check the hooks file and existing tests.

The implementations are already done. Let me check what tests already exist and find the test file structure.

Let me read the existing test file and check what's already covered.

The test file is missing tests for `useFeature`, `usePatchFeature`, `useProcessFeature`, and `useSetRealize`. I need to add them. Let me check the FeatureRead type first.

Now I have everything I need. I'll update the test file to add tests for the 4 new hooks (`useFeature`, `usePatchFeature`, `useProcessFeature`, `useSetRealize`).

Now add the `mockFeatureRead` fixture and the new test suites at the end of the file:

Now add the new test suites before the final import line:

Now let me run the tests to see if they pass:

All 19 tests pass (8 existing + 11 new). Now let me run the full test suite to make sure nothing is broken:

All 1121 tests pass (1109 before + 12 new). Now I need to write the CC-v1 test report artifact and run `/pipeline-gate`.

Let me check the agent contract and existing test reports for the correct format:

Now I have enough context. Let me write the test report:

Now run the pipeline gate:

Let me read the verify.py to understand the path construction before running the gate:

Let me check the test schema and the correct canonical path:

The test schema requires specific fields (`gate_decision`, `tests_added`, `passed`, `failed`) and sections (`Gate result`, `Failures`). The canonical path from the verifier formula should be `test-report-feature-detail-view.md` in the `feature-detail-view` directory. Let me create the correct conformant artifact:

Now run the gate with the correct goal_slug:

Verifier passes with exit 0. Now run the state writer:

Both steps pass. Now finalize the task:

The impl is already on main. The feature branch doesn't exist — I should commit my test changes directly. Let me check what needs to be committed:

Good — `useFeatures.ts` (implementor's new hooks) and my test updates are both uncommitted. Let me stage and commit the relevant files:

Committed and pushed. Now write memory and emit STATUS:

MEMORY[fact]: SG1 test phase (api-client-hooks): added 11 test cases to `frontend/src/hooks/__tests__/useFeatures.test.tsx` covering `useFeature`, `usePatchFeature`, `useProcessFeature`, `useSetRealize`; CC-v1 test artifact at `.cronos/pipeline/feature-detail-view/test-report-feature-detail-view.md`; gate passed; committed to main (781d634).

MEMORY[observation]: For CC-v1 test phase artifacts, the canonical slug must match the pipeline goal slug (e.g. `feature-detail-view`), not the SG/sub-task slug (`api-client-hooks`). The verifier path formula is `.cronos/pipeline/{slug}/test-report-{slug}.md`; using a sub-task name creates an unreachable path.

STATUS: DONE
```
