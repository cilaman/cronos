# Features & Fixes Refactoring Goals

Created: 2026-06-07
Source audits:
- `/data/spaces/cronos-development/.cronos/qa/features-backend-audit.md`
- `/data/spaces/cronos-development/.cronos/qa/features-frontend-audit.md`
- `/data/spaces/cronos-development/.cronos/qa/features-test-audit.md`

---

## Summary Table

| Goal ID | Title | Type | Priority | Child Tasks |
|---------|-------|------|----------|-------------|
| `2026-06-07-1127-fix-features-backend-critical-bugs` | Fix Features Backend Critical Bugs | Simple goal (3 tasks) | 1 | Task 1a, 1b, 1c |
| `2026-06-07-1127-feature-detail-view` | Feature Detail View | CC-v1 pipeline (scout + 2 sub-goals × 6 phases) | 2 | Scout + SG1 (6) + SG2 (6) = 13 |
| `2026-06-07-1128-feature-card-ux-polish` | Feature Card UX Polish | CC-v1 pipeline (scout + 2 sub-goals × 6 phases) | 2 | Scout + SG1 (6) + SG2 (6) = 13 |
| `2026-06-07-1129-feature-module-test-coverage-gaps` | Feature Module Test Coverage Gaps | Simple goal (2 tasks) | 3 | Task 4a, 4b |

---

## Group 1 — Fix Features Backend Critical Bugs

**Goal:** `2026-06-07-1127-fix-features-backend-critical-bugs`
**Type:** Simple goal — flat backend-only bug fixes
**Priority:** 1 (P1 bugs silently break production features)

**Findings addressed:** F1, F2, F3, F4, F7, F8, F9, F10 from backend audit

### Child tasks

| Task ID | Title | Findings |
|---------|-------|---------|
| `2026-06-07-1127-add-set-feature-waiting-question-expose` | Add set_feature_waiting_question + expose waiting_question in FeatureRead | F1, F2 |
| `2026-06-07-1127-guard-process-feature-against-double-pro` | Guard process_feature against double-processing (409) | F3 |
| `2026-06-07-1127-backend-quality-fixes-bundle-f4-f7-f8-f9` | Backend quality fixes bundle (F4, F7, F8, F9, F10) | F4, F7, F8, F9, F10 |

**Execution order:** Task 1a → Task 1b → Task 1c (sequential deps)

---

## Group 2 — Feature Detail View

**Goal:** `2026-06-07-1127-feature-detail-view`
**Pipeline slug:** `feature-detail-view`
**Pipeline dir:** `.cronos/pipeline/feature-detail-view/`
**Type:** CC-v1 pipeline (scout + 2 sequential sub-goals)
**Priority:** 2

**Findings addressed:** CG-1, CG-2, CG-3, CG-4, CG-5, CG-6, UX-7 from frontend audit

The Features board has no detail view — every card click is a no-op. All backend endpoints
already exist; this goal builds the missing frontend wiring.

### Structure

```
feature-detail-view (goal)
├── scout – feature-detail-view            [haiku]  2026-06-07-1127-scout-feature-detail-view
├── SG1: API Client + Hooks               [goal]   2026-06-07-1127-sg1-api-client-hooks-for-feature-detail
│   ├── analyst   – api-client-hooks      [sonnet] 2026-06-07-1127-analyst-api-client-hooks
│   ├── architect – api-client-hooks      [opus]   2026-06-07-1127-architect-api-client-hooks
│   ├── impl      – api-client-hooks      [sonnet] 2026-06-07-1127-impl-api-client-hooks
│   ├── test      – api-client-hooks      [sonnet] 2026-06-07-1127-test-api-client-hooks
│   ├── review    – api-client-hooks      [opus]   2026-06-07-1127-review-api-client-hooks
│   └── doc       – api-client-hooks      [haiku]  2026-06-07-1127-doc-api-client-hooks
└── SG2: FeatureDetail Panel + Wiring     [goal]   2026-06-07-1127-sg2-featuredetail-panel-board-wiring
    ├── analyst   – feature-detail-panel  [sonnet] 2026-06-07-1127-analyst-feature-detail-panel
    ├── architect – feature-detail-panel  [opus]   2026-06-07-1127-architect-feature-detail-panel
    ├── impl      – feature-detail-panel  [sonnet] 2026-06-07-1127-impl-feature-detail-panel
    ├── test      – feature-detail-panel  [sonnet] 2026-06-07-1127-test-feature-detail-panel
    ├── review    – feature-detail-panel  [opus]   2026-06-07-1127-review-feature-detail-panel
    └── doc       – feature-detail-panel  [haiku]  2026-06-07-1127-doc-feature-detail-panel
```

SG2 depends on SG1 (sibling dep ensures SG1 ships before SG2 starts building the panel).

---

## Group 3 — Feature Card UX Polish

**Goal:** `2026-06-07-1128-feature-card-ux-polish`
**Pipeline slug:** `feature-card-ux-polish`
**Pipeline dir:** `.cronos/pipeline/feature-card-ux-polish/`
**Type:** CC-v1 pipeline (scout + 2 sequential sub-goals)
**Priority:** 2

**Findings addressed:** UX-1, UX-2, UX-3, UX-6, UX-9, UX-11, NP-1, NP-2 from frontend audit

Card-level display gaps and board reliability issues: issue links indistinguishable from PR links,
realized_by shows raw UUIDs, missing realizing count, swallowed errors.

### Structure

```
feature-card-ux-polish (goal)
├── scout – feature-card-ux-polish              [haiku]  2026-06-07-1128-scout-feature-card-ux-polish
├── SG1: Backend TaskSummary Additions          [goal]   2026-06-07-1128-sg1-backend-tasksummary-additions
│   ├── analyst   – tasksummary-additions       [sonnet] 2026-06-07-1128-analyst-tasksummary-additions
│   ├── architect – tasksummary-additions       [opus]   2026-06-07-1128-architect-tasksummary-additions
│   ├── impl      – tasksummary-additions       [sonnet] 2026-06-07-1128-impl-tasksummary-additions
│   ├── test      – tasksummary-additions       [sonnet] 2026-06-07-1128-test-tasksummary-additions
│   ├── review    – tasksummary-additions       [opus]   2026-06-07-1128-review-tasksummary-additions
│   └── doc       – tasksummary-additions       [haiku]  2026-06-07-1128-doc-tasksummary-additions
└── SG2: Frontend Card + Board UX Fixes         [goal]   2026-06-07-1128-sg2-frontend-card-board-ux-fixes
    ├── analyst   – frontend-card-board-fixes   [sonnet] 2026-06-07-1128-analyst-frontend-card-board-fixes
    ├── architect – frontend-card-board-fixes   [opus]   2026-06-07-1128-architect-frontend-card-board-fixes
    ├── impl      – frontend-card-board-fixes   [sonnet] 2026-06-07-1128-impl-frontend-card-board-fixes
    ├── test      – frontend-card-board-fixes   [sonnet] 2026-06-07-1128-test-frontend-card-board-fixes
    ├── review    – frontend-card-board-fixes   [opus]   2026-06-07-1128-review-frontend-card-board-fixes
    └── doc       – frontend-card-board-fixes   [haiku]  2026-06-07-1128-doc-frontend-card-board-fixes
```

SG2 depends on SG1 (needs new TaskSummary fields realized_by_count, realizes_feature_key).

---

## Group 4 — Feature Module Test Coverage Gaps

**Goal:** `2026-06-07-1129-feature-module-test-coverage-gaps`
**Type:** Simple goal — test-writing tasks only
**Priority:** 3

**Findings addressed:** P1-A, P1-B, P1-C, P1-D, P1-E, P2-A through P2-H from test audit

### Child tasks

| Task ID | Title | Findings |
|---------|-------|---------|
| `2026-06-07-1129-write-tests-feature-sync-untested-paths` | Write tests: feature_sync untested paths | P1-A, P1-D, P1-E, P2-F, P2-G |
| `2026-06-07-1129-write-tests-api-error-paths-hooks-config` | Write tests: API error paths + hooks config | P1-B, P1-C, P2-A–P2-E, P2-H |

**Execution order:** Task 4a → Task 4b (sequential)

---

## Synthesis rationale

### Why 4 groups (not 5)

The audit brief suggested a possible 5th group for "Process & Realize Workflow UX". After reading
the frontend audit, all process/realize workflow work falls into Group 2 (Feature Detail View):
- CG-4 (Process button) → FeatureDetail panel
- CG-5 (realize link/unlink UI) → FeatureDetail "Realizing goals" section
No separate workflow-UX goal is needed.

### Why Group 2 and Group 3 are separate

Group 2 (detail view) creates the panel infrastructure needed by Group 3 in one spot (UX-7 fix
depends on the `?feature=<id>` URL convention established in Group 2). They are sequentially
independent enough to run in parallel, and have different scope boundaries (Group 2 = new
FeatureDetail component; Group 3 = existing Card.tsx + FeaturesBoard.tsx).

### Why Group 3 uses CC-v1 pipeline

UX-2, UX-3, and NP-2 require backend changes to `TaskSummary` (new fields `realized_by_count`,
`realizes_feature_key`). Adding backend schema fields + frontend consumers warrants the full
scout → analyst → architect → impl → test → review → doc pipeline.

### Execution order recommendation

1. **Group 1** first (unblocks UX-4 which is currently masked by backend bugs)
2. **Groups 2, 3, 4** can run in parallel after Group 1 completes
