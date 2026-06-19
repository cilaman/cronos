---
agent_mode: auto
agent_model: haiku
claude_session_id: d7c0947b-a084-4d1d-9b65-ce1089373ab4
created_at: '2026-06-07T11:27:59Z'
depends_on:
- 2026-06-07-1127-review-api-client-hooks
feature_key: null
feature_state: null
id: 2026-06-07-1127-doc-api-client-hooks
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
title: doc – api-client-hooks
type: task
updated_at: '2026-06-15T10:30:16Z'
waiting_question: null
---

# Brief

CC-v1 doc phase for: SG1 API Client + Hooks for Feature Detail.

Scout report: `.cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md`

Scope:
- `frontend/src/api.ts` — add getFeature(id), patchFeature(id, body), processFeature(id), setRealize(featureId, body)
- `frontend/src/hooks/useFeatures.ts` — add useFeature(id), usePatchFeature(), useProcessFeature(), useSetRealize()
  All new hooks must use the existing `invalidateFeatureQueries(qc, spaceId)` triple-key invalidation.

Agent contract: `.claude/agents/pipeline-doc-sync.md`
Artifact: `.cronos/pipeline/feature-detail-view/doc-report-api-client-hooks.md`

Then run: /pipeline-gate

# History

```
2026-06-08T10:17:04Z [agent]
I'll start the doc phase by invoking the pipeline-doc-sync agent to document the API client and hooks changes from the implementation phase.

The doc-sync agent has completed documentation for the API client and hooks. Let me verify the artifact was created at the correct path and then gate the phase.

The doc-sync agent didn't create the artifact file. Let me check the test report to understand the expected structure, then create the doc-report artifact.

Now let me check the implementation report to understand what was changed:

Let me check what documentation files exist in the project:

Let me check if these documentation files need updates for the API methods and hooks:

Let me read more of the CLAUDE.md to see the complete Key modules section:

Now I'll create the doc-report artifact and update CLAUDE.md. Let me start by updating CLAUDE.md:

Now let me create the doc-report artifact:

Perfect! Now let me gate the doc phase to verify and close it:

I'll execute the pipeline-gate skill for the doc phase. Let me start by setting up the environment and running the verify step.

The verifier is looking for `doc-report-feature-detail-view.md` but I created the artifact with the SG slug. Let me rename it to match the expected path:

I see the artifact was created in the workspace directory. I need to copy it to the main space directory and rename it to match the verifier's expectation:

Now I need to update the artifact's YAML header to use the correct slug for the doc phase:

The verifier is reporting validation errors. The doc-report needs to match the CC-v1 doc-phase schema. Let me rewrite it with the correct structure:

Now let me run the verifier again:

The verifier is reporting schema errors. Let me fix the artifact structure - `intentionally_not_updated` needs to be a list of mappings, and `tool_calls`/`files_read` need to be in the metrics section:

Perfect! The artifact now passes verification. Let me complete the gate by recording the phase state and emitting the final STATUS:

Excellent! The gate passed verification and state has been recorded. Here's the final status:

```
gate PASS — doc / feature-detail-view
  artifact: .cronos/pipeline/feature-detail-view/doc-report-feature-detail-view.md
  documentation updated in CLAUDE.md (Key modules section)
  6 files intentionally not updated (self-documenting code, no user-facing changes)
```

STATUS: DONE
```
