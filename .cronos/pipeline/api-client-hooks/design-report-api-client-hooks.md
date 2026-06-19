---
cc_version: '1.0'
agent: pipeline-architect
slug: api-client-hooks
phase: design
status: done
confidence: 0.9
inputs_used:
- memory:project_features_backend_audit
- memory:project_s2_api_impl
- memory:project_s5_board_ui_impl
- memory:project_merge_2026_06_08
- memory:project_pipeline_architect_agent
- .cronos/pipeline/api-client-hooks/analysis-report-api-client-hooks.md
- .cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md
- frontend/src/api.ts
- frontend/src/hooks/useFeatures.ts
- frontend/src/hooks/useTasks.ts
- frontend/src/types.ts
- frontend/src/hooks/__tests__/useFeatures.test.tsx
outputs_produced:
- .cronos/pipeline/api-client-hooks/design-report-api-client-hooks.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/api.ts
  - frontend/src/hooks/useFeatures.ts
  - frontend/src/hooks/useTasks.ts
  - frontend/src/types.ts
  - frontend/src/hooks/__tests__/useFeatures.test.tsx
  excluded:
  - 'backend/: backend endpoints already production-ready (analyst confidence 0.95)'
  - 'frontend/src/components/: SG2 scope (FeatureDetail modal)'
  - 'frontend/src/pages/: routing untouched in SG1'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: frontend
  scope_files:
  - frontend/src/types.ts
  validation_command: cd frontend && npx tsc --noEmit
  max_diff_lines: 60
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/src/api.ts
  - frontend/src/hooks/__tests__/useFeatures.test.tsx
  validation_command: cd frontend && npm test -- src/hooks/__tests__/useFeatures.test.tsx
  max_diff_lines: 250
  depends_on:
  - I1
- id: I3
  type: frontend
  scope_files:
  - frontend/src/hooks/useFeatures.ts
  - frontend/src/hooks/__tests__/useFeatures.test.tsx
  validation_command: cd frontend && npm test -- src/hooks/__tests__/useFeatures.test.tsx
  max_diff_lines: 400
  depends_on:
  - I2
- id: I4
  type: frontend
  scope_files:
  - frontend/src/hooks/__tests__/useFeatures.test.tsx
  validation_command: cd frontend && npm test -- src/hooks/__tests__/useFeatures.test.tsx
  max_diff_lines: 200
  depends_on:
  - I3
risks:
- description: 'FeatureRead frontend type does not yet exist in types.ts (analyst
    Assumption 2 is incorrect: only FeatureBoard and FeatureState are exported; existing
    methods return Task). Without a new FeatureRead interface that includes realizing_items
    (TaskSummary[]) and waiting_question, R1''s acceptance criterion (resolved value
    has type FeatureRead including waiting_question and realizing_items) cannot be
    satisfied.'
  severity: high
  mitigation: 'I1 is dedicated to adding a FeatureRead interface to frontend/src/types.ts
    that extends the existing Task interface with realizing_items?: TaskSummary[]
    (TaskSummary is already exported). All four new api.ts methods (R1-R4) and the
    useFeature hook (R5) import FeatureRead from ./types and use it as their resolved
    type. I1 is the first iteration and a hard blocker for I2-I4.'
- description: 'Triple-key invalidation contract drift: if usePatchFeature (R6) or
    useSetRealize (R8) invalidates [''feature'', featureId] without also calling invalidateFeatureQueries(qc,
    spaceId), the shared Backlog column on the Tasks board silently desyncs (memory:project_s5_board_ui_impl).
    The verifying hook test must assert both invalidation paths fire.'
  severity: medium
  mitigation: 'I3 mandates onSuccess body for R6 and R8 must call invalidateFeatureQueries(qc,
    spaceId) FIRST then qc.invalidateQueries({ queryKey: [''feature'', featureId]
    }). I4 adds two dedicated vitest cases per hook: ''invalidates triple-key'' and
    ''also invalidates single-feature key'' using a spy on QueryClient.invalidateQueries
    (pattern already established in lines 130-158 of useFeatures.test.tsx).'
- description: 'useFeature enabled-guard regression: copy-pasting the useTask pattern
    but forgetting the `featureId !== null` guard would cause api.getFeature(null!)
    to be called at mount, generating a 404 storm on every detail panel close.'
  severity: medium
  mitigation: 'I3 explicitly mirrors useTasks.ts:15-20 (re-read during scout): `enabled:
    featureId !== null`. I4 adds a vitest case ''is disabled when featureId is null''
    modeled on the existing useFeatureBoard disabled test (line 96 of useFeatures.test.tsx).'
- description: 'PATCH /api/features/{id}/realize body shape (R4/R8) — backend uses
    { item_id: string; feature_id?: string | null } where item_id is the task to link
    and feature_id=null unlinks. A swapped argument order or missing nullable feature_id
    would silently break the link/unlink semantics with no compile-time signal.'
  severity: low
  mitigation: 'I2 declares the body parameter type inline as `{ item_id: string; feature_id?:
    string | null }` so TypeScript catches structural mismatches at the call site.
    I4 adds an api-level vitest case that asserts the request body is JSON.stringify
    of the literal { item_id, feature_id } passed in.'
metrics:
  tool_calls: 11
  files_read: 7
  memory_hits: 5
  iterations_planned: 4
---

## Summary

SG1 introduces four `api.*` client methods and four React Query hooks that together complete the data-access layer the Feature Detail panel (SG2) consumes. The work splits into a 4-iteration DAG: I1 lands a new `FeatureRead` frontend interface (analyst Assumption 2 is incorrect — only `FeatureBoard`/`FeatureState` exist today; the new type is a hard prereq for R1's acceptance criterion); I2 adds the four `api.*` methods (R1-R4) and their api-level test cases; I3 adds the four hooks (R5-R8) following the established `useTransitionFeatureState`/`useTask` patterns; I4 backfills the hook unit tests asserting the triple-key + single-feature-key invalidation contracts. `has_ui: false` is honored — no JSX, no components. All iterations target a single vitest file (`useFeatures.test.tsx`) which already establishes the QueryClient.invalidateQueries-spy pattern in lines 130-158.

## Components

### Data

- `FeatureRead` interface (new, in `frontend/src/types.ts`): extends `Task` shape with `realizing_items?: TaskSummary[]`. Mirrors backend `FeatureRead` Pydantic schema (`backend/app/models.py:199-225`). Imported by `api.ts` and `useFeatures.ts`.

### Backend

- No backend changes. All four endpoints already production-ready: `GET /api/features/{id}`, `PATCH /api/features/{id}`, `POST /api/features/{id}/process`, `PATCH /api/features/{id}/realize` (scout finding 1, analyst Assumption 1).

### Frontend

- `api.getFeature(featureId)`: one-liner arrow fn wrapping `request<FeatureRead>` against `GET /api/features/{id}`. (R1)
- `api.patchFeature(featureId, body)`: PATCH `/api/features/{id}` with JSON body `{ title?, brief? }`. (R2)
- `api.processFeature(featureId)`: POST `/api/features/{id}/process` with no body. (R3)
- `api.setRealize(featureId, body)`: PATCH `/api/features/{id}/realize` with JSON body `{ item_id, feature_id? }`. (R4)
- `useFeature(featureId)`: query hook with `queryKey: ["feature", featureId]`, `enabled: featureId !== null`, calls `api.getFeature`. Mirrors `useTask` at `useTasks.ts:15-20`. (R5)
- `usePatchFeature(spaceId)`: mutation hook; `mutationFn({ featureId, title?, brief? })` → `api.patchFeature(featureId, { title, brief })`; `onSuccess` calls `invalidateFeatureQueries(qc, spaceId)` THEN `qc.invalidateQueries({ queryKey: ["feature", featureId] })`. (R6)
- `useProcessFeature(spaceId)`: mutation hook; `mutationFn(featureId)` → `api.processFeature(featureId)`; `onSuccess` calls `invalidateFeatureQueries(qc, spaceId)`. (R7)
- `useSetRealize(spaceId)`: mutation hook; `mutationFn({ featureId, item_id, feature_id? })` → `api.setRealize(featureId, { item_id, feature_id })`; `onSuccess` calls `invalidateFeatureQueries(qc, spaceId)` THEN `qc.invalidateQueries({ queryKey: ["feature", featureId] })`. (R8)

## Implementation plan

| ID | Type     | Depends on | Scope files (abridged)                                         | Validation                                                                       |
|----|----------|------------|----------------------------------------------------------------|----------------------------------------------------------------------------------|
| I1 | frontend | -          | frontend/src/types.ts                                          | cd frontend && npx tsc --noEmit                                                  |
| I2 | frontend | I1         | frontend/src/api.ts, frontend/src/hooks/__tests__/useFeatures.test.tsx | cd frontend && npm test -- src/hooks/__tests__/useFeatures.test.tsx              |
| I3 | frontend | I2         | frontend/src/hooks/useFeatures.ts, frontend/src/hooks/__tests__/useFeatures.test.tsx | cd frontend && npm test -- src/hooks/__tests__/useFeatures.test.tsx              |
| I4 | frontend | I3         | frontend/src/hooks/__tests__/useFeatures.test.tsx              | cd frontend && npm test -- src/hooks/__tests__/useFeatures.test.tsx              |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| `FeatureRead` frontend type missing (analyst Assumption 2 wrong) — R1 cannot satisfy "type FeatureRead including waiting_question/realizing_items" without it | high   | I1 adds `FeatureRead` to `types.ts` extending `Task` with `realizing_items?: TaskSummary[]`; I2-I4 import it from `./types`. Hard dependency in DAG. |
| Triple-key invalidation drift on R6/R8 hooks desyncs shared Backlog column on Tasks board | medium | I3 mandates `invalidateFeatureQueries` call before single-feature-key invalidate; I4 adds dedicated `QueryClient.invalidateQueries` spy assertions per hook (pattern from `useFeatures.test.tsx:130-158`). |
| `useFeature` enabled-guard regression triggers 404 storm on null featureId | medium | I3 explicitly mirrors `useTasks.ts:15-20` enabled guard; I4 adds vitest case modeled on `useFeatureBoard` disabled test (`useFeatures.test.tsx:96`). |
| `setRealize` body shape `{ item_id, feature_id? }` argument-order/null mishandling silently breaks link vs unlink | low    | I2 declares inline body type so TS catches structural mismatches; I4 asserts request body equals `JSON.stringify({ item_id, feature_id })` per call. |

## Assumptions

- `FeatureRead` must be introduced as a new TypeScript interface (deviates from analyst Assumption 2). Justification: direct grep of `frontend/src/types.ts` shows only `FeatureState` (line 34) and `FeatureBoard` (line 77) — no `FeatureRead`. Existing `transitionFeatureState`/`createFeature` return `Task`, which lacks `realizing_items`. Without a new type, R1's acceptance criterion ("resolved value has type FeatureRead including ... realizing_items") fails type-checking.
- All new methods follow the one-liner arrow-fn shape at `api.ts:402-423` (compact, no try/catch, propagates `request<T>` rejections — satisfies R3's "no error swallowing" criterion automatically because `request` already throws on non-2xx).
- The single hook test file `useFeatures.test.tsx` is the verification surface for all 8 requirements. No separate `api.features.test.ts` file is needed — hook tests mock `global.fetch` and assert URL+method+body, covering the api-level requirements (R1-R4) end-to-end.
- `invalidateFeatureQueries(qc, spaceId)` precedes `qc.invalidateQueries({ queryKey: ["feature", featureId] })` in R6/R8 onSuccess bodies. Order is not functionally required (React Query invalidations are async) but keeping triple-key first matches the existing `useTransitionFeatureState` mental model and simplifies test assertion order.

## Open questions

- None.

## Next consumer brief

Read `iterations[]` in YAML order; the DAG has one root (I1) and is fully serial. Critical cross-iteration invariants not derivable from `scope_files` alone:

1. **`FeatureRead` is the contract type for R1-R5** — I1 defines it as `interface FeatureRead extends Task { realizing_items?: TaskSummary[] }` exported from `frontend/src/types.ts`. I2 imports it in `api.ts` (add to the existing `import type {...} from "./types"` block at lines 1-30). I3 imports it in `useFeatures.ts`. Do not redefine inline.
2. **Triple-key invalidation order (R6/R8)** — `invalidateFeatureQueries(qc, spaceId)` MUST be called before `qc.invalidateQueries({ queryKey: ["feature", featureId] })` in onSuccess bodies. I4's verifying tests assert this ordering by spy-call-index.
3. **Hook signatures** — `usePatchFeature(spaceId: string)` and `useSetRealize(spaceId: string)` (spaceId-curried, featureId via mutationFn argument). Do not flip to `usePatchFeature(featureId)` — that breaks the existing `useTransitionFeatureState(spaceId)` mental model and the triple-key invalidation closes over `spaceId`.
4. **No new test files** — All assertions go into the existing `frontend/src/hooks/__tests__/useFeatures.test.tsx`. The describe blocks already exist for the three current hooks; extend with four new describe blocks matching their style (`describe("useFeature", () => {...})` etc.).
5. **`npm test` runs `vitest run`** (per `frontend/package.json`); the validation command form `cd frontend && npm test -- src/hooks/__tests__/useFeatures.test.tsx` runs vitest against that one file. All four iterations validate the same way after I1.
