---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-07T11:28:43Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1128-feature-card-ux-polish
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Feature Card UX Polish
type: goal
updated_at: '2026-06-15T16:30:16Z'
waiting_question: null
---

# Brief

Multiple UX inconsistencies make the Features board feel half-finished. This goal
addresses card-level display gaps and board reliability through targeted backend additions
and frontend fixes.

## Findings addressed

**Backend (TaskSummary additions):**
- UX-2: `realized_by` renders raw UUIDs — backend must return title summaries or count
- UX-3: `realizing_items` count invisible on card — add `realized_by_count` to TaskSummary
- NP-2: `realizes` link shows raw UUID — add `realizes_feature_key` to TaskSummary

**Frontend (card + board):**
- UX-1: Issue link icon indistinguishable from PR doc icon — add `IconGitIssue`, render `#number`
- UX-6: Double-wrapped `SortableContext` in `FeaturesBoard.tsx` — remove outer wrapper
- UX-9: No 404 silencing on board error — mirror `Board.tsx:208-210` guard
- UX-11: State-change drag swallows errors — surface transition errors via toast
- NP-1: `FeatureComposer` swallows backend 400 — render `createFeature.error` inline

## Sub-goals

1. **Backend TaskSummary additions** — Add `realized_by_count`, `realizes_feature_key` to `TaskSummary`
2. **Frontend card + board fixes** — All 6 frontend-side UX improvements

Pipeline artifacts: `.cronos/pipeline/feature-card-ux-polish/`

# History

```
2026-06-08T15:33:17Z [agent]
All tasks complete. Completed 3, skipped 0 already-done.
```
