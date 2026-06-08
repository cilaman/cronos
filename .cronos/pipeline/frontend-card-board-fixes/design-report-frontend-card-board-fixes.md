---
cc_version: '1.0'
agent: pipeline-architect
slug: frontend-card-board-fixes
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:project_sg1_tasksummary_impl
- memory:project_sg2_feature_detail_panel_design
- memory:project_features_redesign_board_setup
- .cronos/pipeline/frontend-card-board-fixes/analysis-report-frontend-card-board-fixes.md
- .cronos/pipeline/feature-card-ux-polish/scout-report-feature-card-ux-polish.md
- .cronos/pipeline/frontend-card-board-fixes/pipeline-state.json
- frontend/src/types.ts
- frontend/src/components/Card.tsx
outputs_produced:
- .cronos/pipeline/frontend-card-board-fixes/design-report-frontend-card-board-fixes.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/types.ts
  - frontend/src/components/Card.tsx
  - frontend/src/components/__tests__/
  excluded:
  - 'frontend/src/components/FeaturesBoard.tsx: analyst traceability does not cover
    board-level changes; SG2 brief items beyond R1-R4 (UX-1, UX-3, UX-11, NP-1) are
    flagged as a high-severity scope risk for review'
  - 'backend/: SG1 (commit 2ad24bf) already added realizes_feature_key and realized_by_count
    to backend TaskSummary'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: frontend
  scope_files:
  - frontend/src/types.ts
  - frontend/src/components/Card.tsx
  validation_command: cd frontend && npm run build
  max_diff_lines: 120
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/src/components/__tests__/Card.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Card.test.tsx
  max_diff_lines: 200
  depends_on:
  - I1
risks:
- description: Brief-vs-traceability scope mismatch. The SG2 brief and scout report
    enumerate 7 UX items (UX-1 issue icon, UX-3 realizing count badge, UX-6 single
    SortableContext, UX-9 404 guard, UX-11 drag-end toast, NP-1 inline composer error,
    NP-2 realizes feature key). Scout claimed 6 of 7 already shipped; analyst trusted
    scout and produced only R1-R4 covering NP-2. Direct branch-tip inspection shows
    UX-1 (Card.tsx still uses IconFileText not IconGitIssue), UX-3 (Card.tsx still
    renders raw realized_by[] UUIDs), UX-11 (FeaturesBoard onDragEnd has no onError
    toast), and NP-1 (FeaturesBoard createFeature has no error UI) are NOT shipped.
    Designing strictly to analyst traceability per contract leaves these gaps unaddressed
    by this pipeline cycle.
  severity: high
  mitigation: Review phase MUST verify scope completeness against the SG2 brief request
    (not just analyst traceability). If reviewer confirms additional brief items remain
    unshipped, escalate by setting review verdict to needs_fix with explicit instruction
    to re-run pipeline-analyst over the actual branch tip (HEAD aa089d0) so a follow-up
    SG2 cycle can plan iterations for UX-1, UX-3, UX-11, NP-1. Implementor for this
    cycle is bounded to scope_files in iterations[] and will not touch FeaturesBoard.tsx.
- description: 'Analyst R2 acceptance criterion is stale. R2 requires ''Existing realizing_count?:
    number field is retained (not renamed)'', but grep across frontend/src confirms
    realizing_count does NOT exist in types.ts. The retention criterion is therefore
    vacuously satisfied, but it signals the analyst worked from an outdated mental
    model. The functional requirement (add realized_by_count?: number for API parity)
    is still actionable.'
  severity: medium
  mitigation: 'Implementor adds realized_by_count?: number field per the literal requirement
    statement; no rename or retention work is needed because realizing_count is absent.
    Test agent validates only that types.ts compiles and realized_by_count is exported.
    Reviewer notes the criterion drift in attempt-1 review for analyst feedback loop.'
- description: 'R3 graceful fallback is under-specified. Analyst lists two valid fallbacks
    when realizes is set but realizes_feature_key is null: ''→ realizes (unknown)''
    OR ''hides the raw UUID entirely''. Different choices produce different test expectations
    for R4. If implementor and test agent pick differently, tests fail spuriously.'
  severity: medium
  mitigation: 'Implementor I1 MUST pick exactly one fallback strategy and inline-document
    the choice in a code comment at the render site (e.g. ''// Fallback when realizes
    is set but realizes_feature_key is null: render "→ realizes (unknown)"''). I2
    test agent reads the comment to mirror the choice in test assertions. Prefer the
    visible-fallback variant (''→ realizes (unknown)'') over hidden render so the
    click target remains discoverable to users.'
- description: Card.tsx is the most-touched frontend file in the codebase (~700 lines,
    multiple recent commits including SG1 tasksummary additions and SG2 feature-detail-panel).
    Concurrent merges or stale branch state could yield merge conflicts at the realizes
    block (currently line 542-558 on HEAD aa089d0, but the analyst report references
    lines 585-603 — already drifted).
  severity: low
  mitigation: Implementor MUST grep for 'realizes' in Card.tsx to locate the live
    render block before editing rather than trusting hard-coded line numbers from
    the analyst report. Iteration max_diff_lines budget (120) constrains accidental
    refactoring outside the realizes block.
metrics:
  tool_calls: 8
  files_read: 5
  memory_hits: 3
  iterations_planned: 2
---

## Summary

Design for SG2 R1-R4 (NP-2: `realizes_feature_key` plumbing). Two-iteration plan: I1 extends `frontend/src/types.ts` with two TaskSummary fields and updates the Card.tsx realizes link to render the feature key label (with graceful fallback); I2 adds Card.test.tsx coverage for both the key-present and key-absent paths. The iteration DAG is a simple two-node serial chain because the test in I2 must observe the rendering change from I1. A high-severity risk flags the brief-vs-traceability gap — four other SG2 brief items (UX-1, UX-3, UX-11, NP-1) remain unshipped per direct branch-tip inspection but are not covered by analyst traceability and must be escalated by the reviewer for a follow-up cycle.

## Components

### Data
- `frontend/src/types.ts` TaskSummary interface: add `realizes_feature_key?: string | null` (R1) and `realized_by_count?: number` (R2) fields. Source of truth for the backend payload shape returned by `/api/spaces/{id}/features/board` and `/api/spaces/{id}/tasks`. No runtime logic — type-only addition.

### Backend
- No backend changes. SG1 (commit 2ad24bf) already added both fields to `backend/app/models.py` TaskSummary and populated them in `storage.feature_board()` and `storage.realizing_items()`.

### Frontend
- `frontend/src/components/Card.tsx` realizes link block (currently lines 542-558 on HEAD aa089d0): replace the raw-UUID render `→ realizes {task.realizes}` with feature-key-aware render that displays `→ {task.realizes_feature_key}` when the key is available and a graceful textual fallback (`→ realizes (unknown)`) when the key is null. Click handler `onOpenTask?.(task.realizes!)`, role=button, tabIndex=0, and Enter/Space key handlers are preserved unchanged.
- `frontend/src/components/__tests__/Card.test.tsx` adds two test cases mirroring the existing issue-link test pattern: (1) realizes set, realizes_feature_key set → assert feature key text is visible; (2) realizes set, realizes_feature_key null/absent → assert raw UUID is NOT visible.

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                         | Validation                                                              |
|-----|----------|------------|----------------------------------------------------------------|-------------------------------------------------------------------------|
| I1  | frontend | -          | frontend/src/types.ts, frontend/src/components/Card.tsx        | cd frontend && npm run build                                            |
| I2  | frontend | I1         | frontend/src/components/__tests__/Card.test.tsx                | cd frontend && npm test -- src/components/__tests__/Card.test.tsx       |

## Risks

| Risk                                                                                                                       | Severity | Mitigation                                                                                                                              |
|----------------------------------------------------------------------------------------------------------------------------|----------|-----------------------------------------------------------------------------------------------------------------------------------------|
| Brief-vs-traceability scope mismatch: UX-1/UX-3/UX-11/NP-1 remain unshipped per branch-tip inspection, not in traceability | high     | Reviewer verifies scope completeness against SG2 brief; if gaps confirmed, set needs_fix and request re-run of pipeline-analyst at HEAD |
| Analyst R2 acceptance criterion references non-existent `realizing_count` field in types.ts                                | medium   | Implement literal requirement (add `realized_by_count?: number`); skip retention work since `realizing_count` is absent                  |
| R3 graceful fallback under-specified: two valid strategies → I1/I2 choice divergence risks spurious test failures           | medium   | I1 picks visible-fallback variant `→ realizes (unknown)` and inline-comments the choice; I2 mirrors via comment-driven test assertions   |
| Card.tsx churn risk (recent SG1/SG2 commits, analyst line refs already drifted)                                            | low      | Implementor greps for `realizes` in Card.tsx to locate live block instead of trusting analyst line numbers; max_diff_lines=120 caps drift |

## Assumptions

- has_ui=true per analyst; both iterations are `type: frontend`.
- SG1 backend (commit 2ad24bf) is merged and the API already returns `realizes_feature_key` populated on TaskSummary; no backend coordination needed for this cycle.
- The visible-fallback variant for R3 (`→ realizes (unknown)`) is preferred over hidden render to keep the click target discoverable for navigation back to the orphaned realizes target.
- `npm run build` (which runs `tsc -b && vite build`) is a sufficient I1 validation because type-only TaskSummary changes plus a Card.tsx reference to the new field will fail TypeScript strict mode if the field is misnamed or mistyped. A full vitest run is reserved for I2 to keep I1 fast.
- The existing Card.test.tsx already mocks TaskSummary objects in scope; R4 additions follow the existing factory pattern without introducing new test utilities.

## Open questions

- None. The brief-vs-traceability gap is captured as a high-severity risk rather than an open question because the design contract requires the architect to plan strictly to analyst traceability; the reviewer is the appropriate gate to surface and route the gap.

## Next consumer brief

Implementor: read `iterations[]` (two entries, simple serial DAG), `iterations[].scope_files` (hard boundary), and `iterations[].validation_command`. Critical cross-iteration invariant NOT derivable from YAML: I1 must inline-document the chosen R3 fallback strategy in a code comment at the Card.tsx realizes block — I2 test agent reads that comment to mirror the assertion choice. Use the visible-fallback variant `→ realizes (unknown)` unless I1 implementor has strong justification otherwise. Do NOT touch `frontend/src/components/FeaturesBoard.tsx` even though the SG2 brief mentions it — analyst traceability does not cover it and the scope risk is escalation-routed via the reviewer, not this cycle. Reviewer: read `risks[]` (especially R1 high-severity scope risk) and verify scope completeness against the SG2 brief request before passing the cycle.
