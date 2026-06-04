---
cc_version: "1.0"
agent: pipeline-implementor
slug: arc6-visual-editor--i4
phase: impl
status: done
confidence: 0.95
inputs_used:
  - .cronos/pipeline/arc6-visual-editor/design-report-arc6-visual-editor.md
  - .cronos/pipeline/arc6-visual-editor/impl-report-arc6-visual-editor--i3.md
  - frontend/src/api.ts
  - frontend/src/types.ts
  - frontend/src/hooks/__tests__/useHarnessRuns.test.tsx
  - frontend/src/hooks/__tests__/useSpaces.test.ts
iteration_id: I4
files_changed:
  - frontend/src/hooks/useHarnesses.ts
  - frontend/src/hooks/__tests__/useHarnesses.test.tsx
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/arc6-visual-editor/impl-report-arc6-visual-editor--i4.md
blockers: []
next_consumer: pipeline-reviewer
metrics:
  tool_calls: 18
  files_read: 6
  memory_hits: 0
  diff_lines_added: 299
  diff_lines_removed: 0
---

## Summary

I4 creates `frontend/src/hooks/useHarnesses.ts` with three TanStack Query hooks (`useHarnesses`, `useHarness`, `useSaveHarness`) and an accompanying test file with 9 tests. The `useSaveHarness` hook enforces the arc6-6.1 GET-then-PUT pattern — it fetches the current server-side harness via `api.getHarness` first, merges the canvas state in while preserving `created_at` verbatim, then calls `api.updateHarness`. On success, both `["harnesses", spaceId]` and `["harness", spaceId, name]` query keys are invalidated. All 9 tests pass with exit code 0.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/hooks/useHarnesses.ts | created | +40 / 0 | Three TanStack Query hooks: useHarnesses (list), useHarness (single), useSaveHarness (GET-then-PUT mutation) |
| frontend/src/hooks/__tests__/useHarnesses.test.tsx | created | +259 / 0 | 9 tests: list/single fetch correctness, disabled-when-empty guards, GET-before-PUT call order, created_at preservation, dual cache invalidation, canvas state merge |

## Out-of-scope findings

- None.

## Assumptions

- `Harness` is exported from `frontend/src/types.ts` (confirmed by grepping — present from I2).
- `api.listHarnesses`, `api.getHarness`, `api.updateHarness` are all present in `frontend/src/api.ts` (confirmed from I3 impl-report and reading the file).
- Test pattern follows established conventions from `useHarnessRuns.test.tsx` and `useSpaces.test.ts`: `vi.mock("../../api", async (importOriginal) => ...)` with a flat `api` object mock, `makeClient()` + `makeWrapper()` helpers, `renderHook` with `waitFor`.
- Scope files read before editing: all listed individually in `inputs_used[]`.

## Open questions

- None.

## Next consumer brief

**Verbatim validation command:** `cd frontend && npm test -- src/hooks/__tests__/useHarnesses.test.tsx`

**Test result:** 9/9 GREEN, exit code 0.

**Key invariants for downstream I8 (HarnessEditor page):**
- `useSaveHarness(spaceId, name)` performs GET-then-PUT internally — the caller does NOT need to fetch first; just pass a `Partial<Harness>` with the canvas diff.
- Query keys are `["harnesses", spaceId]` (list) and `["harness", spaceId, name]` (single) — use these exact keys in any manual `prefetchQuery` or `setQueryData` calls.
- Both invalidations fire automatically after a successful save — no manual `refetch()` calls needed in the editor.
- `useSaveHarness` mutationFn is async and throws on API error — the editor page should handle `mutation.error` for 422 banner display (design risk 3 / harnessMapping.ts).

No edge cases uncovered during implementation beyond the design risk list.
