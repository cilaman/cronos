---
agent_mode: auto
agent_model: sonnet
claude_session_id: 87896825-08f9-4ff1-924d-76b15358cfdf
created_at: '2026-06-07T11:27:59Z'
depends_on:
- 2026-06-07-1127-scout-feature-detail-view
feature_key: null
feature_state: null
id: 2026-06-07-1127-analyst-api-client-hooks
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
title: analyst – api-client-hooks
type: task
updated_at: '2026-06-15T10:30:16Z'
waiting_question: null
---

# Brief

CC-v1 analyst phase for: SG1 API Client + Hooks for Feature Detail.

Scout report: `.cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md`

Scope:
- `frontend/src/api.ts` — add getFeature(id), patchFeature(id, body), processFeature(id), setRealize(featureId, body)
- `frontend/src/hooks/useFeatures.ts` — add useFeature(id), usePatchFeature(), useProcessFeature(), useSetRealize()
  All new hooks must use the existing `invalidateFeatureQueries(qc, spaceId)` triple-key invalidation.

Agent contract: `.claude/agents/pipeline-analyst.md`
Artifact: `.cronos/pipeline/feature-detail-view/analyst-report-api-client-hooks.md`

Then run: /pipeline-gate

# History

```
2026-06-08T09:31:14Z [agent]
I'll read the scout report and analyst agent contract to understand what needs to be produced.

Now let me read the current source files to validate requirements before writing the artifact.

Let me verify the backend endpoints exist for processFeature and setRealize.

Let me check the PatchRealizeBody model and the FeatureRead type.

I have all the information needed. Now I'll write the analysis report artifact.

Now I'll run the self-verification step.

The verifier looks up the path using the slug — it needs the fan-out slug form. Let me try with the full slug.

Let me check what options the verify script accepts.

Let me look at the actual pipeline structure to understand the correct slug/path convention.

Let me check the actual task to understand how pipeline-gate will be invoked.

The verifier path rule requires the file to be at `.cronos/pipeline/{parent_slug}/analysis-report-{slug}.md`. With `slug=api-client-hooks`, the parent_slug is also `api-client-hooks`. I'll move the artifact to the correct location and update the YAML accordingly.

Now verify the artifact passes the CC-v1 verifier.

Verification passes (exit 0) with one warning about `outputs_produced` path. Let me fix that in the artifact.

Verifier exits 0 with no warnings. Now running `/pipeline-gate`.

Both steps passed. VERIFY_EXIT=0, PY_EXIT=0.

gate PASS — analysis / api-client-hooks
  artifact: .cronos/pipeline/api-client-hooks/analysis-report-api-client-hooks.md
  normalize: 2 fixes applied (dropped non-standard strategy entries)

STATUS: DONE
```
