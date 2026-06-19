---
cc_version: '1.0'
agent: pipeline-analyst
slug: api-client-hooks
phase: analysis
status: done
confidence: 0.95
inputs_used:
- memory:project_features_backend_audit
- memory:project_s2_api_impl
- memory:project_s5_board_ui_impl
- memory:project_merge_2026_06_08
- .cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md
- frontend/src/api.ts
- frontend/src/hooks/useFeatures.ts
- backend/app/api/features.py
- .claude/agents/pipeline-analyst.md
outputs_produced:
- .cronos/pipeline/api-client-hooks/analysis-report-api-client-hooks.md
blockers: []
next_consumer: design
request: "CC-v1 analyst phase for: SG1 API Client + Hooks for Feature Detail.\n\n\
  Scope:\n- frontend/src/api.ts — add getFeature(id), patchFeature(id, body), processFeature(id),\
  \ setRealize(featureId, body)\n- frontend/src/hooks/useFeatures.ts — add useFeature(id),\
  \ usePatchFeature(), useProcessFeature(), useSetRealize()\n  All new hooks must\
  \ use the existing invalidateFeatureQueries(qc, spaceId) triple-key invalidation."
has_ui: false
coverage_summary:
  searched:
  - frontend/src/api.ts (existing feature API methods, lines 402-423)
  - frontend/src/hooks/useFeatures.ts (existing hooks and invalidateFeatureQueries
    helper)
  - backend/app/api/features.py (all 4 endpoints: GET, PATCH edit, POST process, PATCH
      realize)
  excluded:
  - frontend/src/components/: UI components are SG2 scope
  - backend/app/models.py: FeatureRead schema confirmed via scout report
  - frontend/src/types.ts: FeatureState/FeatureBoard types confirmed via scout report
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: api.getFeature(featureId) must be added to api.ts, calling GET /api/features/{featureId}
    and returning Promise<FeatureRead>.
  acceptance_criteria:
  - Given a valid feature ID, when api.getFeature(id) is called, then the HTTP request
    is GET /api/features/{id} and the resolved value has type FeatureRead including
    waiting_question, feature_state, feature_key, realizing_items, and all inherited
    Task fields.
  - api.getFeature is exported as a property of the api object alongside the three
    existing feature methods (features, transitionFeatureState, createFeature).
  verifying_phase: test
  confidence: 0.97
- requirement_id: R2
  statement: 'api.patchFeature(featureId, body) must be added to api.ts, calling PATCH
    /api/features/{featureId} with body { title?: string; brief?: string } and returning
    Promise<FeatureRead>.'
  acceptance_criteria:
  - 'Given a feature ID and a partial update body, when api.patchFeature(id, body)
    is called, then the HTTP request is PATCH /api/features/{id} with Content-Type:
    application/json and the serialised body.'
  - The return type is Promise<FeatureRead> (same shape as getFeature return).
  verifying_phase: test
  confidence: 0.97
- requirement_id: R3
  statement: api.processFeature(featureId) must be added to api.ts, calling POST /api/features/{featureId}/process
    with no body and returning Promise<FeatureRead>.
  acceptance_criteria:
  - Given a feature ID, when api.processFeature(id) is called, then the HTTP request
    is POST /api/features/{id}/process.
  - The backend returns FeatureRead with feature_state=PROCESSING on success, or 409
    if already processing. The client method propagates rejections transparently (no
    error swallowing).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R4
  statement: 'api.setRealize(featureId, body) must be added to api.ts, calling PATCH
    /api/features/{featureId}/realize with body { item_id: string; feature_id?: string
    | null } and returning Promise<FeatureRead>.'
  acceptance_criteria:
  - Given a feature ID and a realize body, when api.setRealize(featureId, body) is
    called, then the HTTP request is PATCH /api/features/{featureId}/realize with
    the serialised body.
  - The return type is Promise<FeatureRead> with updated realizing_items reflecting
    the link/unlink operation.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R5
  statement: useFeature(featureId) query hook must be added to useFeatures.ts, fetching
    a single feature via api.getFeature with queryKey ['feature', featureId] and enabled
    guard.
  acceptance_criteria:
  - Given featureId !== null, the hook fires a query with queryKey ['feature', featureId]
    and queryFn calling api.getFeature(featureId).
  - Given featureId === null, enabled is false and no network request is made.
  - The hook mirrors the useTasks.ts useTask pattern (enabled guard, same key shape).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R6
  statement: usePatchFeature(spaceId) mutation hook must be added to useFeatures.ts,
    calling api.patchFeature and on success invoking invalidateFeatureQueries(qc,
    spaceId) plus invalidating ['feature', featureId].
  acceptance_criteria:
  - Given a mutation call with { featureId, title?, brief? }, the mutationFn calls
    api.patchFeature(featureId, { title, brief }).
  - 'onSuccess calls invalidateFeatureQueries(qc, spaceId) (triple-key: [''features'',
    spaceId], [''board'', spaceId], [''spaces'']).'
  - 'onSuccess also calls qc.invalidateQueries({ queryKey: [''feature'', featureId]
    }) to refresh the single-feature detail query.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R7
  statement: useProcessFeature(spaceId) mutation hook must be added to useFeatures.ts,
    calling api.processFeature and on success invoking invalidateFeatureQueries(qc,
    spaceId).
  acceptance_criteria:
  - Given a mutation call with featureId, the mutationFn calls api.processFeature(featureId).
  - onSuccess calls invalidateFeatureQueries(qc, spaceId) (triple-key invalidation).
  - 'The hook signature is useProcessFeature(spaceId: string) consistent with useTransitionFeatureState
    and useCreateFeature.'
  verifying_phase: test
  confidence: 0.93
- requirement_id: R8
  statement: useSetRealize(spaceId) mutation hook must be added to useFeatures.ts,
    calling api.setRealize and on success invoking invalidateFeatureQueries(qc, spaceId)
    plus invalidating ['feature', featureId] to reflect updated realizing_items.
  acceptance_criteria:
  - Given a mutation call with { featureId, item_id, feature_id? }, the mutationFn
    calls api.setRealize(featureId, { item_id, feature_id }).
  - 'onSuccess calls invalidateFeatureQueries(qc, spaceId) (triple-key) and qc.invalidateQueries({
    queryKey: [''feature'', featureId] }).'
  verifying_phase: test
  confidence: 0.93
metrics:
  tool_calls: 7
  files_read: 5
  memory_hits: 4
---

## Summary

SG1 adds four API client methods (`getFeature`, `patchFeature`, `processFeature`, `setRealize`) to `frontend/src/api.ts` and four React Query hooks (`useFeature`, `usePatchFeature`, `useProcessFeature`, `useSetRealize`) to `frontend/src/hooks/useFeatures.ts`. All four backend endpoints are confirmed production-ready; no backend changes are required. Every new hook must call the existing `invalidateFeatureQueries(qc, spaceId)` triple-key helper on success; `usePatchFeature` and `useSetRealize` must additionally invalidate the single-feature query key `["feature", featureId]` so live-open detail panels update without a full board reload.

## Scope

### In scope

- `api.getFeature(featureId: string): Promise<FeatureRead>` — wraps `GET /api/features/{id}`
- `api.patchFeature(featureId: string, body: { title?: string; brief?: string }): Promise<FeatureRead>` — wraps `PATCH /api/features/{id}`
- `api.processFeature(featureId: string): Promise<FeatureRead>` — wraps `POST /api/features/{id}/process`
- `api.setRealize(featureId: string, body: { item_id: string; feature_id?: string | null }): Promise<FeatureRead>` — wraps `PATCH /api/features/{id}/realize`
- `useFeature(featureId: string | null)` — single-feature query hook
- `usePatchFeature(spaceId: string)` — edit mutation hook
- `useProcessFeature(spaceId: string)` — process/decompose mutation hook
- `useSetRealize(spaceId: string)` — realize link/unlink mutation hook

### Out of scope

- `FeatureDetail` modal component — wired by SG2, not this sub-goal
- `FeaturesBoard.tsx` dead handler wiring — SG2 scope
- Any modification to backend endpoints
- New TypeScript types or interfaces (all required types exist: `FeatureRead` from `api.ts` imports, `FeatureState` from `types.ts`)

### Deferred

- Optimistic updates on `usePatchFeature` — not required for MVP; pessimistic invalidation is sufficient
- `useFeature` cache warming via board data pre-seeding — advanced optimization, out of SG1 scope

## Requirements

| R#  | One-line summary |
|-----|------------------|
| R1  | `api.getFeature(featureId)` — GET single feature returning FeatureRead |
| R2  | `api.patchFeature(featureId, body)` — PATCH edit title/brief returning FeatureRead |
| R3  | `api.processFeature(featureId)` — POST /process trigger returning FeatureRead |
| R4  | `api.setRealize(featureId, body)` — PATCH realize link/unlink returning FeatureRead |
| R5  | `useFeature(featureId)` — single-feature query hook with enabled guard |
| R6  | `usePatchFeature(spaceId)` — mutation hook with triple-key + single-key invalidation |
| R7  | `useProcessFeature(spaceId)` — mutation hook with triple-key invalidation |
| R8  | `useSetRealize(spaceId)` — mutation hook with triple-key + single-key invalidation |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]`
array (the machine-readable source of truth). The body summary below mirrors them
in compact form for the human reader.

- R1 — `api.getFeature` calls `GET /api/features/{id}`, returns `Promise<FeatureRead>` with all fields including `waiting_question`
- R2 — `api.patchFeature` calls `PATCH /api/features/{id}` with serialised body, returns `Promise<FeatureRead>`
- R3 — `api.processFeature` calls `POST /api/features/{id}/process`, propagates 409 transparently
- R4 — `api.setRealize` calls `PATCH /api/features/{id}/realize`, returns updated `FeatureRead` with fresh `realizing_items`
- R5 — `useFeature` has `queryKey: ["feature", featureId]`, `enabled: featureId !== null`, fetches via `api.getFeature`
- R6 — `usePatchFeature` mutation fires `api.patchFeature`, calls `invalidateFeatureQueries` + invalidates `["feature", featureId]` on success
- R7 — `useProcessFeature` mutation fires `api.processFeature`, calls `invalidateFeatureQueries` on success
- R8 — `useSetRealize` mutation fires `api.setRealize`, calls `invalidateFeatureQueries` + invalidates `["feature", featureId]` on success

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML
`traceability[]` array. Downstream agents read the YAML directly; this section
exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | `api.getFeature(featureId)` must call `GET /api/features/{featureId}` and return `Promise<FeatureRead>` |
| R2 | test | `api.patchFeature(featureId, body)` must call `PATCH /api/features/{featureId}` and return `Promise<FeatureRead>` |
| R3 | test | `api.processFeature(featureId)` must call `POST /api/features/{featureId}/process` and return `Promise<FeatureRead>` |
| R4 | test | `api.setRealize(featureId, body)` must call `PATCH /api/features/{featureId}/realize` and return `Promise<FeatureRead>` |
| R5 | test | `useFeature(featureId)` query hook with `queryKey: ["feature", featureId]` and `enabled: featureId !== null` |
| R6 | test | `usePatchFeature(spaceId)` mutation with `invalidateFeatureQueries` + `["feature", featureId]` invalidation on success |
| R7 | test | `useProcessFeature(spaceId)` mutation with `invalidateFeatureQueries` on success |
| R8 | test | `useSetRealize(spaceId)` mutation with `invalidateFeatureQueries` + `["feature", featureId]` invalidation on success |

## Assumptions

- **All four backend endpoints are production-ready**: Confirmed by scout report (confidence 0.92), memory:project_s2_api_impl, and direct read of `backend/app/api/features.py:283-375`. No backend changes required.
- **`FeatureRead` type is already importable from `api.ts`**: The type is used in `transitionFeatureState` return signature; adding new methods using the same return type requires no new import.
- **`waiting_question` is present in `FeatureRead`**: Confirmed by memory:project_merge_2026_06_08 (commit f02301b) and scout report; safe to rely on for `useFeature` consumers.
- **has_ui: false rationale**: SG1 adds only API client methods and React Query hooks — purely a data-access layer. No JSX, no visual state, no user interaction is introduced. The hooks will be consumed by `FeatureDetail` (SG2) but SG1 itself has no rendering output.
- **Triple-key invalidation contract (R4)**: `invalidateFeatureQueries` helper is already documented as mandatory in `useFeatures.ts` header comment. All four mutation hooks must call it to avoid desyncing the shared Backlog column on the Tasks board.
- **Single-feature query key `["feature", featureId]`**: This key does not yet exist in `useFeatures.ts`. It will be introduced by `useFeature` (R5) and must be invalidated by `usePatchFeature` (R6) and `useSetRealize` (R8) to ensure an open detail panel reflects its own edits.

## Open questions

- None. All backend endpoints confirmed, all existing hook patterns identified. Implementation can proceed with existing evidence.

## Next consumer brief

**For design agent**: Read `traceability[]` for the 8 requirements and `## Scope` for file boundaries. `has_ui: false` — no component design work.

Key implementation decisions already resolved by existing patterns:
1. **API method shape**: Follow the three existing feature methods in `api.ts:402-423` exactly (one-liner arrow functions using the `request<T>()` helper).
2. **Hook shape**: All mutation hooks follow `useTransitionFeatureState` pattern (lines 41-49 of `useFeatures.ts`): `useQueryClient()` → `useMutation({ mutationFn, onSuccess })` → call `invalidateFeatureQueries`.
3. **Query hook shape**: `useFeature` follows `useTask` pattern from `useTasks.ts:15-20` (enabled guard via `featureId !== null`, queryKey as two-element array).
4. **R6 + R8 extra invalidation**: `usePatchFeature` and `useSetRealize` must invalidate `["feature", featureId]` in addition to the triple-key, because they mutate the feature the detail panel is currently showing. Extract `featureId` from mutationFn argument to pass to `invalidateQueries`.
5. **No new TypeScript types needed**: `FeatureRead` already exists in `api.ts` imports; `PatchRealizeBody`-equivalent can be expressed as an inline type `{ item_id: string; feature_id?: string | null }`.
