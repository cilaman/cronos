---
cc_version: "1.0"
agent: pipeline-implementor
slug: feature-detail-view--i1
phase: impl
status: done
confidence: 0.97
iteration_id: I1
inputs_used:
  - frontend/src/api.ts
  - frontend/src/hooks/useFeatures.ts
  - frontend/src/hooks/useTasks.ts
  - frontend/src/types.ts
  - backend/app/models.py
  - backend/app/api/features.py
  - .cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md
outputs_produced:
  - .cronos/pipeline/feature-detail-view/impl-report-feature-detail-view--i1.md
blockers: []
next_consumer: test
files_changed:
  - frontend/src/types.ts
  - frontend/src/api.ts
  - frontend/src/hooks/useFeatures.ts
validation_command_passed: true
metrics:
  tool_calls: 14
  files_read: 8
  memory_hits: 3
  diff_lines_added: 116
  diff_lines_removed: 1
---

## Summary

Implemented SG1: API Client + Hooks for Feature Detail. Added `FeatureRead` TypeScript interface to `types.ts`, 4 API client methods to `api.ts`, and 4 React Query hooks to `useFeatures.ts`. All 1110 frontend tests pass; TypeScript type-check is clean.

## Files changed

- `frontend/src/types.ts` — Added `FeatureRead` interface (28 lines) after `FeatureBoard`, mirroring the backend `FeatureRead` Pydantic model (models.py:199-225).
- `frontend/src/api.ts` — Added `FeatureRead` to the type import; added `getFeature`, `patchFeature`, `processFeature`, `setRealize` methods to the `// --- features ---` section.
- `frontend/src/hooks/useFeatures.ts` — Added `FeatureRead` to the type import; added `useFeature`, `usePatchFeature`, `useProcessFeature`, `useSetRealize` hooks at end of file.

## Out-of-scope findings

- `frontend/src/components/FeaturesBoard.tsx:252` still has dead `onOpen={() => {}}` — this is SG2 scope (FeatureDetail panel wiring), not this iteration.
- The old `impl-report-api-client-hooks.md` (malformed) and `impl-report-feature-detail-view--api-client-hooks.md` (wrong iteration naming) exist in the pipeline dir; they can be cleaned up after the gate passes.

## Assumptions

- `iteration_id: I1` — This is the first and only implementation iteration for the `feature-detail-view` goal SG1. The task brief used the non-standard name `api-client-hooks` for the iteration, but CC-v1 requires `^I[0-9]+$`; I1 is the correct canonical form.
- New mutations (`usePatchFeature`, `useProcessFeature`, `useSetRealize`) extract `space_id` from the returned `FeatureRead` rather than accepting it as a hook argument. This satisfies the R4 triple-key invalidation contract without coupling call sites to a spaceId they may not have in context.
- TypeScript forward references are fine: `FeatureRead` in `types.ts` uses `TaskType` which is defined later in the same file; TypeScript hoists all interface/type declarations.

## Open questions

None. Scope was fully delivered and verified.

## Next consumer brief

**For test agent (SG1 gate / tester phase):**

The following new exports are now available:
- `types.ts`: `FeatureRead` interface
- `api.ts`: `api.getFeature(id)`, `api.patchFeature(id, body)`, `api.processFeature(id)`, `api.setRealize(featureId, body)`
- `hooks/useFeatures.ts`: `useFeature(id|null)`, `usePatchFeature()`, `useProcessFeature()`, `useSetRealize()`

Test targets:
1. `useFeature(null)` should not fire a query (enabled guard)
2. `useFeature("some-id")` should call `api.getFeature("some-id")`
3. `usePatchFeature().mutate({featureId, body})` should call `api.patchFeature` and invalidate `["feature", id]` + triple-key
4. `useProcessFeature().mutate(featureId)` should call `api.processFeature` and invalidate + triple-key
5. `useSetRealize().mutate({featureId, body})` should call `api.setRealize` and invalidate + triple-key
6. All 4 api methods should call the correct backend URLs with the correct HTTP method and body serialization
