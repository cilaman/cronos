---
cc_version: "1.0"
agent: pipeline-implementor
slug: feature-detail-view--api-client-hooks
phase: impl
status: done
iteration: api-client-hooks
scope_files:
  - frontend/src/api.ts
  - frontend/src/hooks/useFeatures.ts
  - frontend/src/types.ts
files_changed:
  - frontend/src/types.ts
  - frontend/src/api.ts
  - frontend/src/hooks/useFeatures.ts
validation_command_passed: true
---

## Summary

Implemented SG1: API Client + Hooks for Feature Detail. Added `FeatureRead` TypeScript interface, 4 API client methods, and 4 React Query hooks.

## Changes

### frontend/src/types.ts

Added `FeatureRead` interface after `FeatureBoard`. Mirrors the backend `FeatureRead` Pydantic model (models.py:199-225) with all fields:
- Base fields: id, space_id, title, state, created_at, updated_at, brief, priority, manual_order, type, parent_id, depends_on, pr_url, proposed_pr_path
- Feature-specific: feature_state, feature_key, realizes, issue_number, issue_url, proposed_issue_path, waiting_question, realizing_items

### frontend/src/api.ts

Added `FeatureRead` to the type import list.

Added 4 methods to the `// --- features ---` section:
- `getFeature(featureId)` → GET /api/features/{id} → FeatureRead
- `patchFeature(featureId, body)` → PATCH /api/features/{id} → FeatureRead
- `processFeature(featureId)` → POST /api/features/{id}/process → FeatureRead
- `setRealize(featureId, body)` → PATCH /api/features/{id}/realize → FeatureRead

### frontend/src/hooks/useFeatures.ts

Added `FeatureRead` to the type import.

Added 4 hooks:
- `useFeature(featureId: string | null)` — query, queryKey=["feature", featureId], enabled when non-null
- `usePatchFeature()` — mutation, mutationFn takes `{ featureId, body }`; onSuccess invalidates ["feature", id] + triple-key using result.space_id
- `useProcessFeature()` — mutation, mutationFn takes featureId string; onSuccess invalidates ["feature", id] + triple-key
- `useSetRealize()` — mutation, mutationFn takes `{ featureId, body: { item_id, feature_id } }`; onSuccess invalidates ["feature", id] + triple-key

All mutations extract `space_id` from the returned `FeatureRead` to call `invalidateFeatureQueries(qc, space_id)`, avoiding the need to pass spaceId as a hook argument while still satisfying the R4 triple-key contract.

## Validation

```
cd frontend && npm test -- --run
```

Result: 1110 tests passed (68 test files), exit code 0. TypeScript type-check (`npx tsc --noEmit`) passed with no errors.
