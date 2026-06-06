---
cc_version: '1.0'
agent: pipeline-architect
slug: featurefix-board-ui
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:project_s1_data_model_impl
- memory:project_s2_api_impl
- memory:project_s4_worker_decompose_impl
- memory:project_arc_features_fixes_board_setup
- memory:project_pipeline_architect_agent
- .cronos/pipeline/featurefix-board-ui/analysis-report-featurefix-board-ui.md
- .cronos/pipeline/featurefix-board-ui/scout-report-featurefix-board-ui.md
- frontend/src/pages/BoardPage.tsx
- backend/app/pipeline/schemas/design.schema.yaml
outputs_produced:
- .cronos/pipeline/featurefix-board-ui/design-report-featurefix-board-ui.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/types.ts
  - frontend/src/api.ts
  - frontend/src/router.tsx
  - frontend/src/components/Sidebar.tsx
  - frontend/src/components/Lane.tsx
  - frontend/src/components/Card.tsx
  - frontend/src/components/Board.tsx
  - frontend/src/hooks/useTasks.ts
  - frontend/src/pages/BoardPage.tsx
  excluded:
  - 'backend/app/: backend foundation S1/S2/S4 already delivered; S5 is frontend-only'
  - 'frontend/src/pages/FeaturesPage.tsx: new file (I6 deliverable)'
  - 'frontend/src/components/FeaturesBoard.tsx: new file (I6 deliverable)'
  - 'frontend/src/hooks/useFeatures.ts: new file (I3 deliverable)'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: frontend
  scope_files:
  - frontend/src/types.ts
  validation_command: cd frontend && npx tsc --noEmit
  max_diff_lines: 250
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/src/api.ts
  validation_command: cd frontend && npx tsc --noEmit
  max_diff_lines: 200
  depends_on:
  - I1
- id: I3
  type: frontend
  scope_files:
  - frontend/src/hooks/useFeatures.ts
  - frontend/src/hooks/__tests__/useFeatures.test.tsx
  validation_command: cd frontend && npm test -- src/hooks/__tests__/useFeatures.test.tsx
  max_diff_lines: 350
  depends_on:
  - I2
- id: I4
  type: frontend
  scope_files:
  - frontend/src/components/Lane.tsx
  - frontend/src/components/__tests__/Lane.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Lane.test.tsx
  max_diff_lines: 200
  depends_on:
  - I1
- id: I5
  type: frontend
  scope_files:
  - frontend/src/components/Card.tsx
  - frontend/src/components/__tests__/Card.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Card.test.tsx
  max_diff_lines: 400
  depends_on:
  - I1
- id: I6
  type: frontend
  scope_files:
  - frontend/src/pages/FeaturesPage.tsx
  - frontend/src/components/FeaturesBoard.tsx
  - frontend/src/components/__tests__/FeaturesBoard.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/FeaturesBoard.test.tsx
  max_diff_lines: 600
  depends_on:
  - I3
  - I4
  - I5
- id: I7
  type: frontend
  scope_files:
  - frontend/src/router.tsx
  - frontend/src/components/Sidebar.tsx
  - frontend/src/components/__tests__/Sidebar.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Sidebar.test.tsx
  max_diff_lines: 250
  depends_on:
  - I6
- id: I8
  type: frontend
  scope_files:
  - frontend/src/components/Board.tsx
  - frontend/src/components/__tests__/Board.sharedBacklog.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Board.sharedBacklog.test.tsx
  max_diff_lines: 300
  depends_on:
  - I3
  - I4
- id: I9
  type: frontend
  scope_files:
  - frontend/src/types.ts
  validation_command: cd frontend && npx tsc --noEmit && npm test -- --run
  max_diff_lines: 50
  depends_on:
  - I6
  - I7
  - I8
risks:
- description: Lane.tsx state prop widening from TaskState to string risks accidental
    cross-system value passing (e.g. a feature-state lane id leaking into a Tasks
    board call-site) that tsc cannot catch. Lane-system disjointness is the analysis-level
    highest-risk invariant (R14).
  severity: high
  mitigation: Keep FEATURE_LANES and LANES as distinct const arrays in types.ts, never
    share a literal between them. In I4, document via JSDoc on Lane.Props.state that
    the value must come from exactly one lane-system constant for that board. Add
    a unit assertion in the Lane test that the existing Tasks BoardPage call-site
    still passes a TaskState value at runtime (compile-only check via a separate test
    fixture importing both lane constants and asserting empty set intersection).
- description: Shared Backlog column on the Tasks board (I8) could be accidentally
    wrapped in a SortableContext or treated as a droppable target, breaking the read-only
    contract (R13) and corrupting the Tasks DnD state machine.
  severity: high
  mitigation: In I8, render the Backlog column as a sibling of the SortableContext
    / DndContext subtree, not a child. The component used MUST NOT be Lane (to avoid
    inheriting droppable semantics); instead create an inline backlog-card list using
    Card directly with onOpenTask wired to navigate('/features'). Add a regression
    test (Board.sharedBacklog.test.tsx) asserting the column is outside any DndContext/SortableContext
    and clicks navigate (mock react-router useNavigate).
- description: Triple-key invalidation contract on every feature mutation (['features',
    spaceId], ['board', spaceId], ['spaces']) is easy to drop on later edits; missing
    one key would silently desync the shared Backlog on the Tasks board.
  severity: medium
  mitigation: Centralize the invalidation set in useFeatures.ts as a small helper
    (e.g. invalidateFeatureQueries(queryClient, spaceId)) called from both mutations.
    Add explicit tests in I3 asserting all three keys are invalidated on success of
    useTransitionFeatureState and useCreateFeature (use a spy on queryClient.invalidateQueries).
- description: FeaturesBoard drag-end handler must call canFeatureTransition guard
    BEFORE issuing useTransitionFeatureState; a missed guard sends illegal transitions
    to the backend, which would 400 but still cause flicker via optimistic refetch.
  severity: medium
  mitigation: 'In I6, structure onDragEnd as: (a) read fromState from active.data,
    (b) read toState from over.id, (c) if !canFeatureTransition(fromState, toState)
    return early, (d) call mutate. Cover both branches with two unit tests in FeaturesBoard.test.tsx:
    legal transition triggers mutation; illegal transition does NOT (assert mutate
    spy not called).'
- description: Both /features (root-level) and /spaces/:spaceId/features (scoped)
    routes point at FeaturesPage; if spaceId fallback to active-space-context is mis-wired,
    the unscoped route may render an empty board or crash on undefined spaceId.
  severity: low
  mitigation: 'In I6 FeaturesPage, resolve effective spaceId as: routeParams.spaceId
    ?? activeSpaceContextSpaceId ?? null. Render an explicit empty-state (''Pick a
    space from the sidebar'') when null. Add unit test in FeaturesBoard.test.tsx covering
    the null-spaceId branch.'
- description: Composer on Backlog lane (R10) reuses TaskForm with a Feature/Fix toggle;
    TaskForm currently emits TaskType values and may not natively support a 'fix'
    branch — wiring mistakes here are review-only (R10 verifying_phase=review).
  severity: medium
  mitigation: In I6, when the composer submits, map the toggle value to api.createFeature(spaceId,
    {title, type, ...}) — do NOT call the existing task-create endpoint. Pass an explicit
    `mode='feature-composer'` (or a new prop) to TaskForm so it surfaces a feature/fix
    radio rather than the existing goal/task radio; preserve the existing TaskForm
    goal/task UI when mode is absent. Reviewer (Phase 5) confirms styling per [[frontend-design]]
    skill.
metrics:
  tool_calls: 9
  files_read: 4
  memory_hits: 5
  iterations_planned: 9
---

## Summary

S5 delivers a parallel Features Kanban (5 lanes — backlog/processing/planned/waiting/done) alongside the existing Tasks board, sharing the same dnd-kit machinery but a disjoint state machine (`FeatureState` vs `TaskState`). The plan splits the 14 analysis requirements into 9 frontend-only iterations: types-first (I1) feeds the api/hooks track (I2, I3) and the component-widening track (I4, I5) in parallel; the new page+board (I6), nav/routing (I7), and Tasks-board shared Backlog column (I8) all consume the foundation; a final strict typecheck + vitest pass (I9) gates the merge. Critical invariants — lane-system disjointness (R14), shared-Backlog read-only isolation outside any `SortableContext` (R13), and triple-key invalidation on every feature mutation (R4) — are tracked as the top three risks with concrete mitigations.

## Components

### Data
- frontend/src/types.ts: `FeatureState` union (5 values), `FEATURE_LANES` constant array, `canFeatureTransition(from, to)` mirroring the 7 backend user-transition edges, optional feature fields (`feature_state`, `feature_key`, `issue_number`, `issue_url`, `realizes`, `realized_by`) on `TaskSummary` and `Task`, and a new `FeatureBoard` interface keyed by each `FeatureState`.

### Backend
- None. S5 is frontend-only; the backend foundation (S1 data model, S2 features API, S4 worker decompose) is already merged on `feature/features-and-fixes` and is read-only from this design's perspective.

### Frontend
- frontend/src/api.ts: three new HTTP client stubs — `features(spaceId)`, `transitionFeatureState(taskId, state)`, `createFeature(spaceId, body)` — matching the auth/error pattern of existing stubs.
- frontend/src/hooks/useFeatures.ts (NEW): `useFeatureBoard(spaceId)` query (`refetchInterval: 5000`, key `["features", spaceId]`); `useTransitionFeatureState` and `useCreateFeature` mutations, each invalidating `["features", spaceId]`, `["board", spaceId]`, and `["spaces"]` on success via a shared `invalidateFeatureQueries(qc, spaceId)` helper.
- frontend/src/components/Lane.tsx: widen `state` prop to `string`; add optional `showAdd?: boolean` (defaulting to legacy `state === "backlog"` behaviour at existing call-sites).
- frontend/src/components/Card.tsx: add `feature` (emerald) and `fix` (rose) entries to `TYPE_BADGE_STYLES`; render `feature_key` chip when present; clone `pr_url` anchor pattern for `issue_url`; clone parent-link chip pattern for each `realizes[]` entry (`→ realizes FEAT-NNN`); on feature/fix cards only, render a `realized_by[]` click-through list calling `onOpenTask(item.id)`.
- frontend/src/pages/FeaturesPage.tsx (NEW): mirrors `BoardPage` shape — reads `spaceId` from route params (falls back to active-space context), wires `useFeatureBoard`, renders loading/error states, delegates to `FeaturesBoard`.
- frontend/src/components/FeaturesBoard.tsx (NEW): 5 `Lane` components in a `lg:grid-cols-5` grid wrapped in `DndContext`+`SortableContext` (mirroring `Board.tsx`). `onDragEnd` guards via `canFeatureTransition`; on a legal drop calls `useTransitionFeatureState`. Backlog lane header hosts a composer reusing `TaskForm` (with a Feature/Fix toggle) wired to `useCreateFeature`. No lane hide/restore.
- frontend/src/components/Board.tsx: gain a read-only Backlog column rendered *outside* the existing `DndContext`/`SortableContext` subtree, populated by `useFeatureBoard(spaceId).data?.backlog`, with each card's click navigating to `/features` (no detail panel).
- frontend/src/router.tsx: add `/features` and `/spaces/:spaceId/features` routes, both pointing at `FeaturesPage`; preserve all existing routes.
- frontend/src/components/Sidebar.tsx: rename existing `Kanban` label → `Tasks` (href stays `/board`); add a `Features` link immediately after, pointing at `/features`, with the same active-route highlighting pattern.

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                                  | Validation                                                                 |
|-----|----------|------------|-------------------------------------------------------------------------|----------------------------------------------------------------------------|
| I1  | frontend | -          | frontend/src/types.ts                                                   | cd frontend && npx tsc --noEmit                                            |
| I2  | frontend | I1         | frontend/src/api.ts                                                     | cd frontend && npx tsc --noEmit                                            |
| I3  | frontend | I2         | frontend/src/hooks/useFeatures.ts (+test)                               | cd frontend && npm test -- src/hooks/__tests__/useFeatures.test.tsx        |
| I4  | frontend | I1         | frontend/src/components/Lane.tsx (+test)                                | cd frontend && npm test -- src/components/__tests__/Lane.test.tsx          |
| I5  | frontend | I1         | frontend/src/components/Card.tsx (+test)                                | cd frontend && npm test -- src/components/__tests__/Card.test.tsx          |
| I6  | frontend | I3,I4,I5   | frontend/src/pages/FeaturesPage.tsx, FeaturesBoard.tsx (+test)          | cd frontend && npm test -- src/components/__tests__/FeaturesBoard.test.tsx |
| I7  | frontend | I6         | frontend/src/router.tsx, Sidebar.tsx (+test)                            | cd frontend && npm test -- src/components/__tests__/Sidebar.test.tsx       |
| I8  | frontend | I3,I4      | frontend/src/components/Board.tsx (+test)                               | cd frontend && npm test -- src/components/__tests__/Board.sharedBacklog.test.tsx |
| I9  | frontend | I6,I7,I8   | frontend/src/types.ts (final disjointness pin)                          | cd frontend && npx tsc --noEmit && npm test -- --run                       |

Topological layers (orchestrator fan-out):
- Layer 0: I1
- Layer 1: I2, I4, I5 (parallel — all depend only on I1)
- Layer 2: I3 (depends on I2)
- Layer 3: I6 (depends on I3+I4+I5), I8 (depends on I3+I4)
- Layer 4: I7 (depends on I6)
- Layer 5: I9 (depends on I6+I7+I8)

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Lane-state widening loses TaskState/FeatureState disjointness at call-sites (R14 invariant) | high | Keep FEATURE_LANES and LANES disjoint const arrays; document Lane.Props.state via JSDoc; add a unit fixture asserting empty key-set intersection (see I4 test). |
| Shared Backlog column on Tasks board accidentally rendered inside SortableContext, breaking R13 read-only contract | high | Render Backlog as a sibling of the Tasks DndContext subtree (not a Lane); test asserts the column is outside any DndContext/SortableContext and clicks navigate to /features. |
| Triple-key invalidation contract silently dropped on later useFeatures.ts edits | medium | Centralize via invalidateFeatureQueries(qc, spaceId); spy-asserted in I3 mutation tests. |
| canFeatureTransition guard missed in FeaturesBoard drag-end → illegal API calls | medium | Structure onDragEnd to guard before mutate; cover legal/illegal branches in FeaturesBoard.test.tsx. |
| /features without spaceId param renders empty/crashes if active-space context fallback is wrong | low | Explicit null-spaceId empty-state in FeaturesPage; unit test covers the null branch. |
| TaskForm reuse for Feature/Fix composer mis-wires submit endpoint (R10 review-class) | medium | Composer submit calls api.createFeature exclusively; explicit mode flag to TaskForm; surfaced for human review at Phase 5. |

## Assumptions

- S1 / S2 / S4 backends are deployed on `feature/features-and-fixes` and provide: `GET /api/spaces/{spaceId}/features` (returns `FeatureBoard`), a feature-state transition endpoint (PATCH on the task), and a feature creation endpoint (POST on the features collection). The analysis report confirms these; this design does not revisit backend contracts.
- `TaskType` already includes `"feature"` and `"fix"` per S1; `types.ts` only adds the optional feature fields and `FeatureState`/`FEATURE_LANES`/`FeatureBoard`/`canFeatureTransition` — it does not redeclare `TaskType`.
- `TaskForm` is reusable as a composer if the call-site provides a `type` value and a submit handler; if the existing `TaskForm` signature does not support a Feature/Fix radio, I6 adds the prop in a backward-compatible way (defaults preserve the existing goal/task radio).
- The shared Backlog on the Tasks board triggers a second 5-second polling interval — accepted as MVP per analysis assumptions (no debouncing required).
- Frontend test infrastructure is vitest + Testing Library + a `vi.mock`-able `react-query` `QueryClient`; existing tests under `src/components/__tests__/` and `src/hooks/__tests__/` confirm this convention.
- No backend, schema, or migration file is touched by any iteration; if an implementor finds it must touch backend, that is a contract violation requiring escalation.

## Open questions

- None. The analysis report explicitly closed the question of `FeatureBoard` response shape (assumption A2 in the analysis) and no further unknowns surfaced during decomposition.

## Next consumer brief

For the implementation agent (and orchestrator fan-out):
- Read `iterations[]` directly; group by `depends_on` for parallel layers. `scope_files[]` is the hard diff boundary; `validation_command` runs verbatim.
- The cross-iteration invariant the YAML cannot encode: every feature mutation in `useFeatures.ts` (I3) MUST invalidate exactly the three query keys `["features", spaceId]`, `["board", spaceId]`, `["spaces"]`. The shared Backlog on the Tasks board (I8) depends on `["features"]` invalidation propagating back into Board.tsx without any direct call.
- The other cross-iteration invariant: `FEATURE_LANES` (I1) and `LANES` (existing) must remain disjoint constants — no shared literal. I9 re-runs `tsc --noEmit` + full vitest as a final consolidation gate; if a later iteration drifts on disjointness, I9 fails fast.
- R10 (composer) is review-class — Phase 5 reviewer signs off styling via the [[frontend-design]] skill; implementor at I6 wires the data flow and leaves styling as default-Tailwind that the reviewer can adjust.
- All iterations are frontend-only; an implementor touching `backend/app/` should stop and escalate.
