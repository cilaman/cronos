---
agent_mode: auto
agent_model: opus
claude_session_id: 54b75285-67ea-4d2c-8626-9d766c89dc47
created_at: '2026-06-07T11:27:59Z'
depends_on:
- 2026-06-07-1127-analyst-api-client-hooks
feature_key: null
feature_state: null
id: 2026-06-07-1127-architect-api-client-hooks
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
title: architect – api-client-hooks
type: task
updated_at: '2026-06-15T10:30:16Z'
waiting_question: null
---

# Brief

CC-v1 architect phase for: SG1 API Client + Hooks for Feature Detail.

Scout report: `.cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md`

Scope:
- `frontend/src/api.ts` — add getFeature(id), patchFeature(id, body), processFeature(id), setRealize(featureId, body)
- `frontend/src/hooks/useFeatures.ts` — add useFeature(id), usePatchFeature(), useProcessFeature(), useSetRealize()
  All new hooks must use the existing `invalidateFeatureQueries(qc, spaceId)` triple-key invalidation.

Agent contract: `.claude/agents/pipeline-architect.md`
Artifact: `.cronos/pipeline/feature-detail-view/architect-report-api-client-hooks.md`

Then run: /pipeline-gate

# History

```
2026-06-08T09:36:16Z [agent]
Both reports confirmed. Analysis is at `.cronos/pipeline/api-client-hooks/analysis-report-api-client-hooks.md`. I'll delegate to the pipeline-architect agent.

Architect phase passed (exit 0). Now running the pipeline-gate as the brief instructs.

Setting up gate inputs. The upstream task ID is the current architect task (this same task ran the architect subagent and now runs the gate).

Verify passed (exit 0, outcome=proceed). Now recording state via state_writer.

Both VERIFY_EXIT and PY_EXIT are 0. PHASE is `design` not `retro`, so Steps 3b/3c are skipped.

gate PASS — design / api-client-hooks
  artifact: .cronos/pipeline/api-client-hooks/design-report-api-client-hooks.md
  4-iteration DAG (I1→I2→I3→I4) covering R1–R8; 3 normalize fixes applied (unknown free-text strategies dropped).

STATUS: DONE
```
