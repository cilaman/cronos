---
agent_mode: auto
agent_model: opus
claude_session_id: 603864ce-759f-4169-9711-9c6dc3ed9b23
created_at: '2026-06-07T11:27:59Z'
depends_on:
- 2026-06-07-1127-test-api-client-hooks
feature_key: null
feature_state: null
id: 2026-06-07-1127-review-api-client-hooks
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
title: review – api-client-hooks
type: task
updated_at: '2026-06-15T10:30:16Z'
waiting_question: null
---

# Brief

CC-v1 review phase for: SG1 API Client + Hooks for Feature Detail.

Scout report: `.cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md`

Scope:
- `frontend/src/api.ts` — add getFeature(id), patchFeature(id, body), processFeature(id), setRealize(featureId, body)
- `frontend/src/hooks/useFeatures.ts` — add useFeature(id), usePatchFeature(), useProcessFeature(), useSetRealize()
  All new hooks must use the existing `invalidateFeatureQueries(qc, spaceId)` triple-key invalidation.

Agent contract: `.claude/agents/pipeline-reviewer.md`
Artifact: `.cronos/pipeline/feature-detail-view/review-report-api-client-hooks.md`

Then run: /pipeline-gate

# History

```
2026-06-08T10:09:55Z [agent]
I'll start by reading the pipeline reviewer contract and the scout/design artifacts to understand the review scope.

Now let me look at the actual implementation in the workspace.

I have enough context. The committed branch state has a critical gap: `useFeatures.ts` references `api.getFeature`/`patchFeature`/`processFeature`/`setRealize` and imports `FeatureRead` from `../types`, but neither the api.ts changes nor the FeatureRead interface were committed — they live only as uncommitted edits in the main worktree. Let me write the review.

Now let me run the verifier on the artifact.

Verifier passes. Now let me run /pipeline-gate per the brief.

Verify passes with `outcome=proceed` exit 0. Now let me record state via the state_writer.

The review phase entry is persisted in `pipeline-state.json` with `gate_decision: proceed` and `status: done`.

## Summary

Wrote `.cronos/pipeline/feature-detail-view/review-report-feature-detail-view--attempt1.md` with verdict `needs_fix` and 6 findings (3 blocking, 3 non-blocking). The verifier exited 0 (proceed) on the artifact, and the gate skill recorded the review phase into `pipeline-state.json` + `phases-log.jsonl`.

Critical findings:
- **F1, F2, F3 (high, blocking)**: The branch's committed state is broken. `useFeatures.ts` imports `FeatureRead` from `../types` and calls `api.getFeature/patchFeature/processFeature/setRealize`, but those changes were never committed — they exist only as uncommitted edits in the main worktree (the known `observation_worktree_main_vs_workspace` failure mode). `npm test` passes only because `vi.mock` stubs the api module and esbuild silently strips the missing type import; `npm run build` (tsc -b) would fail.
- **F4 (medium)**: Two stale impl-report duplicates clutter the pipeline dir; only the `--i1` canonical artifact should remain.
- **F5, F6 (low)**: Late `useQueryClient` import at test file bottom; spaceId-from-result divergence vs. spaceId-as-arg pattern.

Routing: `verdict=needs_fix` → orchestrator should re-spawn implementor for attempt 2. Recovery is mechanical (copy two files from main worktree, commit, push, re-validate with `npm run build`).

STATUS: DONE
```
