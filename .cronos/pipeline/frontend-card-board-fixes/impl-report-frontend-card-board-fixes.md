---
cc_version: '1.0'
agent: pipeline-implementor
slug: frontend-card-board-fixes
phase: impl
status: done
confidence: 0.95
inputs_used:
- .cronos/pipeline/frontend-card-board-fixes/design-report-frontend-card-board-fixes.md
- frontend/src/types.ts
- frontend/src/components/Card.tsx
- frontend/src/components/__tests__/Card.test.tsx
outputs_produced:
- .cronos/pipeline/frontend-card-board-fixes/impl-report-frontend-card-board-fixes.md
iteration_id: I2
next_consumer: test
blockers: []
validation_command_passed: true
files_changed:
- frontend/src/types.ts
- frontend/src/components/Card.tsx
- frontend/src/components/__tests__/Card.test.tsx
metrics:
  tool_calls: 14
  files_read: 4
  memory_hits: 0
  diff_lines_added: 25
  diff_lines_removed: 6
  tests_added: 4
---

## Summary

Implemented design iterations I1 and I2 (NP-2: realizes_feature_key plumbing) in a single run. Both iterations were trivially serial with no blocking dependency — I1's types + rendering change validated by `npm run build`, I2's test additions validated by vitest targeting the Card test file. All 65 Card tests pass.

## Files changed

### `frontend/src/types.ts`
Added three optional fields to the `TaskSummary` interface (R1 + R2):
- `realizes_feature_key?: string | null` — denormalized feature key for display (e.g. "FEAT-007")
- `realized_by_count?: number` — count of tasks realizing this feature/fix (API parity)
- `realizing_count?: number` — confirmed present in working tree

### `frontend/src/components/Card.tsx`
Updated the realizes link render block:
- Before: `→ realizes {task.realizes}` (raw UUID displayed)
- After: `→ {task.realizes_feature_key ?? "realizes (unknown)"}` with inline comment documenting the R3 fallback strategy

The visible fallback `→ realizes (unknown)` was chosen per design R3 guidance: keeps the click target discoverable for navigation even when the denormalized key is absent.

### `frontend/src/components/__tests__/Card.test.tsx`
Updated the `Card — realizes chip` describe block with 4 test cases mirroring the new rendering behavior:
1. `renders feature key when realizes and realizes_feature_key are both set` — asserts `→ FEAT-007` visible, raw UUID absent
2. `renders fallback '→ realizes (unknown)' when realizes is set but realizes_feature_key is null` — asserts fallback text, raw UUID absent
3. `does NOT render the realizes chip when realizes is null` — no arrow rendered
4. `calls onOpenTask with the realizes id when the chip is clicked` — navigation still uses raw `realizes` UUID as the target; label uses feature key

## Out-of-scope findings

- Design risk R1 (brief-vs-traceability scope mismatch): UX-1/UX-3/UX-11/NP-1 from the SG2 brief remain flagged. FeaturesBoard.tsx was NOT touched per scope contract — this is routed to the reviewer for escalation.

## Assumptions

- SG1 backend (commit 2ad24bf) is merged; `realizes_feature_key` is populated by `storage.feature_board()` at runtime.
- `npm run build` pre-existing failures (2 TS2322 errors in `frontend/src/__tests__/api.features.test.ts`) are unrelated to scope files and do not affect I1 validation.
- The visible-fallback strategy for R3 (`→ realizes (unknown)`) is preferred over hidden render.

## Open questions

None.

## Next consumer brief

**Test phase (or reviewer):** Validate that the Card renders feature key when `realizes_feature_key` is set and the fallback when it is null. The 4 test cases in `Card.test.tsx` already cover this. The reviewer should also check design risk R1 (brief scope completeness) and escalate if UX-1/UX-3/UX-11/NP-1 items are still unshipped.
