---
cc_version: "1.0"
agent: pipeline-analyst
slug: frontend-card-board-fixes
phase: analysis
status: done
confidence: 0.92
inputs_used:
  - memory:impl-tasksummary-additions-sg1
  - memory:ux1-fix-card-tsx
  - memory:ux3-realizing-count-badge
  - .cronos/pipeline/feature-card-ux-polish/scout-report-feature-card-ux-polish.md
  - frontend/src/types.ts
  - frontend/src/components/Card.tsx
  - frontend/src/components/FeaturesBoard.tsx
  - backend/app/models.py
  - backend/app/storage.py
  - .cronos/pipeline/feature-card-ux-polish/pipeline-state.json
  - .cronos/pipeline/tasksummary-additions/pipeline-state.json
  - .cronos/pipeline/feature-card-ux-polish/analysis-report-tasksummary-additions.md
  - backend/app/pipeline/verify.py
  - .claude/skills/pipeline-gate/SKILL.md
  - .claude/agents/pipeline-analyst.md
outputs_produced:
  - .cronos/pipeline/frontend-card-board-fixes/analysis-report-frontend-card-board-fixes.md
blockers: []
next_consumer: design
request: "SG2: Frontend Card + Board UX Fixes.\n\nApply 6 frontend UX improvements to Card.tsx and FeaturesBoard.tsx.\nDepends on SG1 (new TaskSummary fields: realized_by_count, realizes_feature_key).\n\nFiles in scope:\n- frontend/src/components/Card.tsx — issue icon, realized_by_count rendering, realizes_feature_key\n- frontend/src/components/FeaturesBoard.tsx — remove double SortableContext, add 404 guard, add error toast, render createFeature.error inline\n- frontend/src/types.ts — add new TaskSummary fields to TypeScript type\n\nPipeline dir: .cronos/pipeline/feature-card-ux-polish/"
has_ui: true
coverage_summary:
  searched:
    - frontend/src/types.ts (TaskSummary type, lines 140-155)
    - frontend/src/components/Card.tsx (issue icon block lines 500-562, realizes block lines 585-603)
    - frontend/src/components/FeaturesBoard.tsx (FeatureComposer lines 40-145, onDragEnd lines 204-242, error guard lines 248-254, SortableContext lines 295-314)
    - backend/app/models.py (TaskSummary fields via grep)
    - backend/app/storage.py (feature_board populate logic via grep)
  excluded:
    - backend/app/api/features.py — API layer unchanged; scout already verified
    - frontend/src/hooks/useFeatures.ts — hooks unchanged; scout verified
    - frontend/src/api.ts — API client unchanged; scout verified
  strategies:
    - memory_retrieval
    - read_targeted
    - grep_symbol
traceability:
  - requirement_id: R1
    statement: "frontend/src/types.ts TaskSummary must include realizes_feature_key?: string | null so components can access the backend-provided feature key label."
    acceptance_criteria:
      - "types.ts TaskSummary has field realizes_feature_key?: string | null."
      - "TypeScript compiler emits no errors referencing task.realizes_feature_key in Card.tsx after the change."
    verifying_phase: review
    confidence: 0.97
  - requirement_id: R2
    statement: "frontend/src/types.ts TaskSummary must include realized_by_count?: number for API parity with the parallel backend field (backend exposes both realizing_count and realized_by_count set to the same value)."
    acceptance_criteria:
      - "types.ts TaskSummary has field realized_by_count?: number."
      - "Existing realizing_count?: number field is retained (not renamed)."
    verifying_phase: review
    confidence: 0.9
  - requirement_id: R3
    statement: "Card.tsx realizes link must render the feature key label (e.g., '→ FEAT-007') using task.realizes_feature_key instead of displaying the raw UUID stored in task.realizes."
    acceptance_criteria:
      - "Given task.realizes is set and task.realizes_feature_key is non-null, card renders '→ {realizes_feature_key}' (e.g., '→ FEAT-007')."
      - "Given task.realizes is set but task.realizes_feature_key is null (target feature deleted or not yet populated), card renders a graceful fallback — either '→ realizes (unknown)' or hides the raw UUID entirely."
      - "The onClick handler continues to call onOpenTask(task.realizes) regardless of whether realizes_feature_key is available."
      - "The aria/keyboard interaction (role=button, tabIndex=0, Enter/Space key) is preserved."
    verifying_phase: test
    confidence: 0.93
  - requirement_id: R4
    statement: "frontend/src/components/__tests__/Card.test.tsx must have test coverage for the realizes_feature_key rendering path."
    acceptance_criteria:
      - "A test case renders a Card with realizes set and realizes_feature_key set to a feature key string; asserts the feature key string is visible in the output."
      - "A test case renders a Card with realizes set but realizes_feature_key null or absent; asserts no raw UUID is rendered."
    verifying_phase: test
    confidence: 0.88
metrics:
  tool_calls: 18
  files_read: 12
  memory_hits: 3
---

## Summary

SG2 Frontend Card + Board UX Fixes targets 8 scope items across three files. Codebase inspection against the scout report confirms that 6 of 7 original UX findings are already implemented (UX-1: issue icon, UX-3: realizing count badge, UX-6: single SortableContext, UX-9: 404 guard, UX-11: drag-end toast, NP-1: FeatureComposer inline error). The one remaining gap is NP-2: `realizes_feature_key` is absent from `frontend/src/types.ts` and Card.tsx at line 601 renders `→ realizes {task.realizes}` using the raw UUID. SG1 (tasksummary-additions, commit 2ad24bf) already added `realizes_feature_key: str | None = None` and `realized_by_count: int = 0` to the backend `TaskSummary`; this analysis defines the frontend type additions (R1, R2) and the Card.tsx rendering fix (R3) with accompanying tests (R4).

## Scope

### In scope
- Add `realizes_feature_key?: string | null` to `TaskSummary` in `frontend/src/types.ts`
- Add `realized_by_count?: number` to `TaskSummary` in `frontend/src/types.ts` (API parity)
- Update `Card.tsx` realizes link (lines 585–603) to display feature key label from `realizes_feature_key`
- Graceful fallback when `realizes` is set but `realizes_feature_key` is null
- Test coverage in `Card.test.tsx` for the new rendering path

### Out of scope
- Re-implementing UX-1, UX-3, UX-6, UX-9, UX-11, NP-1 — all confirmed already shipped
- Backend model or storage changes — SG1 already added `realizes_feature_key` and `realized_by_count`
- Navigation to the feature from the realizes link — the existing `onOpenTask(task.realizes)` handler is correct and unchanged
- Removing the legacy `realized_by?: string[]` field from types.ts — a separate cleanup, not in this scope

### Deferred
- Tooltip/title attribute on realizes link showing full UUID for debugging (raised in scout open questions — post-analyst low priority)
- Removing `realized_by?: string[]` from types.ts once all consumers are migrated

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Add `realizes_feature_key?: string | null` to TaskSummary in types.ts |
| R2 | Add `realized_by_count?: number` to TaskSummary in types.ts for API parity |
| R3 | Card.tsx renders `→ FEAT-XXX` from realizes_feature_key instead of raw UUID |
| R4 | Card.test.tsx covers realizes_feature_key render path (feature key present and absent) |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). Summary:

- R1 — `types.ts` gains `realizes_feature_key?: string | null`; TypeScript compilation clean
- R2 — `types.ts` gains `realized_by_count?: number`; existing `realizing_count` field retained
- R3 — Card renders `→ FEAT-007` when key available; graceful fallback when key is null; click handler and keyboard nav preserved
- R4 — Two Card test cases: key present → visible label; key absent → no raw UUID visible

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | review | types.ts TaskSummary includes realizes_feature_key |
| R2 | review | types.ts TaskSummary includes realized_by_count |
| R3 | test | Card.tsx renders feature key label instead of raw UUID |
| R4 | test | Card.test.tsx covers realizes_feature_key both present and absent |

## Assumptions

- has_ui=true rationale: all four requirements modify or test a React card component rendered on the Kanban/Features board.
- The 6 already-implemented findings (UX-1, UX-3, UX-6, UX-9, UX-11, NP-1) require no design or implementation work; the design agent should skip them and focus exclusively on the NP-2 gap (R1–R4).
- `realized_by_count` and `realizing_count` in the backend are currently set to the same value; types.ts should carry both for API-model fidelity, but only `realizing_count` is consumed by the existing badge.
- SG1 backend data (commit 2ad24bf) is already merged and deployed; the API response from `/api/spaces/{id}/features/board` already includes `realizes_feature_key` for each TaskSummary.
- Graceful fallback for R3 (realizes set, realizes_feature_key null) should not render the raw UUID — the ID is an internal implementation detail not useful to end users.

## Open questions

- None.

## Next consumer brief

**Design agent:** Read `traceability[]`, `has_ui`, and `## Scope`.

Key context for design:
- Only R1–R4 need implementation; all other scope items are already shipped (do not design redundant iterations for them).
- R1 + R2 are single-line additions to `frontend/src/types.ts` (lines after `realizing_count?: number` at line 154); trivially combinable into one iteration.
- R3 is a targeted replacement in `Card.tsx:585–603`: replace `→ realizes {task.realizes}` with `→ {task.realizes_feature_key ?? "realizes"}` (or hide raw UUID entirely); the surrounding click handler and keyboard nav must be preserved unchanged.
- R4 test cases follow the pattern already in `Card.test.tsx` for the issue link tests (2–3 test cases covering key-present and key-absent states).
- Recommend a 2-iteration design: I1 = R1+R2+R3 (types.ts + Card.tsx update), I2 = R4 (tests). Alternatively, a single iteration covering all four requirements is acceptable given the small surface area.
- No new API hooks, routes, or backend changes needed.
