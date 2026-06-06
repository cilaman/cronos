---
cc_version: "1.0"
agent: pipeline-implementor
slug: featurefix-board-ui--i3
phase: impl
status: done
confidence: 0.95
inputs_used:
  - memory:project_s1_data_model_impl
  - memory:project_s2_api_impl
  - memory:feedback_pipeline_narrow_k_coverage
  - .cronos/pipeline/featurefix-board-ui/design-report-featurefix-board-ui.md
  - .cronos/pipeline/featurefix-board-ui/impl-report-featurefix-board-ui--i1.md
  - .cronos/pipeline/featurefix-board-ui/impl-report-featurefix-board-ui--i2.md
  - frontend/src/hooks/useTasks.ts
  - frontend/src/api.ts
  - frontend/src/hooks/__tests__/useTasks.test.ts
  - frontend/src/hooks/__tests__/useHarnesses.test.tsx
  - frontend/src/types.ts
iteration_id: I3
files_changed:
  - frontend/src/hooks/useFeatures.ts
  - frontend/src/hooks/__tests__/useFeatures.test.tsx
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/featurefix-board-ui/impl-report-featurefix-board-ui--i3.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 22
  files_read: 11
  memory_hits: 3
  diff_lines_added: 333
  diff_lines_removed: 0
---

## Summary

Implemented iteration I3 of featurefix-board-ui: created `frontend/src/hooks/useFeatures.ts` with the `invalidateFeatureQueries` helper, `useFeatureBoard` query hook, `useTransitionFeatureState` mutation, and `useCreateFeature` mutation. The R4 triple-key invalidation contract (`["features", spaceId]`, `["board", spaceId]`, `["spaces"]`) is centralized in the `invalidateFeatureQueries` helper and called by both mutations. Created `frontend/src/hooks/__tests__/useFeatures.test.tsx` with 8 tests covering all three hooks plus a direct unit test for the helper; all 8 tests pass (`vitest run` exit 0).

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/hooks/useFeatures.ts | created | +65 / 0 | useFeatureBoard query, useTransitionFeatureState + useCreateFeature mutations, invalidateFeatureQueries helper |
| frontend/src/hooks/__tests__/useFeatures.test.tsx | created | +268 / 0 | 8 tests: query key, disabled-when-null, mutation API call, triple-key invalidation (both mutations), space-scoped invalidation, direct helper unit test |

## Out-of-scope findings

- None.

## Assumptions

- `useTransitionFeatureState` and `useCreateFeature` both accept `spaceId` as a hook argument (not a mutation variable) because the spaceId is invariant for the lifecycle of the component mounting the hook, consistent with the pattern used in `useUpdateTask`, `useArchiveTask`, etc.
- `useFeatureBoard` passes `spaceId` directly to `api.features(spaceId!)` and is disabled when `spaceId` is null, matching the `useTask`/`enabled` pattern from `useTasks.ts`.
- The `invalidateFeatureQueries` helper uses exact key matches (`["features", spaceId]` and `["board", spaceId]`) rather than a predicate, because the Features board always operates in a space-scoped context. The Tasks board uses a predicate to invalidate all board variants; the feature queries are always space-scoped so exact keys are sufficient and safer.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Rerun validation: `cd /data/spaces/cronos-development/frontend && npm test -- src/hooks/__tests__/useFeatures.test.tsx`

All 8 tests pass (2.52s). Key facts for I6 (FeaturesBoard) which depends on this iteration:
- `useTransitionFeatureState(spaceId)` takes `{ taskId, state }` as mutation variable — call `mutate({ taskId: active.id, state: overLaneId as FeatureState })` from `onDragEnd`.
- `useCreateFeature(spaceId)` takes `{ title, type, description? }` — call from the Backlog lane composer on submit.
- `invalidateFeatureQueries` is exported and can be called directly in any future mutation that touches feature data, maintaining the R4 contract without duplicating the three-key list.
- No edge cases were uncovered beyond those in the design. The `["board", spaceId]` key uses the exact board query key format from `useTasks.ts` (`["board", spaceId ?? "all", viewId]`) — verify in I8 (Board.tsx) that the `useFeatureBoard` 5-second poll plus `["board", spaceId]` invalidation does not trigger double-fetch with the existing `useBoard` hook when both are mounted simultaneously.
