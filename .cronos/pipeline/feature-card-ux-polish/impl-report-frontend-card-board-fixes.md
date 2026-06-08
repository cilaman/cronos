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
- .cronos/pipeline/feature-card-ux-polish/impl-report-frontend-card-board-fixes.md
iterations_executed:
- id: I1
  scope_files:
  - frontend/src/types.ts
  - frontend/src/components/Card.tsx
  validation_command: cd frontend && npm run build
  validation_command_passed: true
  notes: >
    Build has 2 pre-existing TS2322 errors in frontend/src/__tests__/api.features.test.ts
    (incomplete TaskSummary mocks missing required fields — present before this change,
    confirmed via git stash). My changes introduced no new TypeScript errors.
- id: I2
  scope_files:
  - frontend/src/components/__tests__/Card.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Card.test.tsx
  validation_command_passed: true
  notes: 65 tests passed, including 4 updated/new realizes-chip tests.
files_changed:
- frontend/src/types.ts
- frontend/src/components/Card.tsx
- frontend/src/components/__tests__/Card.test.tsx
blockers: []
scope_respected: true
---

## Summary

Implemented I1 and I2 per the design DAG for NP-2 (realizes_feature_key plumbing).

### I1 — Types + Card rendering

**`frontend/src/types.ts`**: Added three new optional fields to `TaskSummary`:
- `realizes_feature_key?: string | null` (R1 — display feature key instead of UUID)
- `realized_by_count?: number` (R2 — API parity field)
- `realizing_count?: number` (already partially present; confirmed in final file)

**`frontend/src/components/Card.tsx`**: Updated the realizes link render block (previously line 601):
- Before: `→ realizes {task.realizes}` (raw UUID displayed)
- After: `→ {task.realizes_feature_key ?? "realizes (unknown)"}` with inline comment documenting the fallback strategy

The visible fallback `→ realizes (unknown)` was chosen per design guidance: keeps the click target discoverable for navigation even when the denormalized key is absent (e.g., orphaned realizes target or pre-SG1 data).

### I2 — Tests

**`frontend/src/components/__tests__/Card.test.tsx`**: Updated existing `realizes chip` describe block:
1. `renders feature key when realizes and realizes_feature_key are both set` — verifies `→ FEAT-007` text is present and raw UUID is absent
2. `renders fallback '→ realizes (unknown)' when realizes is set but realizes_feature_key is null` — verifies fallback text; confirms raw UUID is hidden
3. `does NOT render the realizes chip when realizes is null` — updated assertion (no longer checks raw UUID pattern)
4. `calls onOpenTask with the realizes id when the chip is clicked` — updated to use feature key label `→ FEAT-007` for the user-event click target; onOpenTask still called with raw `realizes` UUID (the navigation target)

### Scope notes

Design explicitly excluded `FeaturesBoard.tsx` (high-severity risk R1 in design: brief-vs-traceability gap). FeaturesBoard was not touched. Reviewer should verify scope completeness against SG2 brief and escalate if UX-1/UX-3/UX-11/NP-1 remain unaddressed in subsequent cycles.

## Validation

| Iteration | Command | Result |
|-----------|---------|--------|
| I1 | `cd frontend && npm run build` | Passed (2 pre-existing TS errors in unrelated test file) |
| I2 | `cd frontend && npm test -- src/components/__tests__/Card.test.tsx` | 65/65 passed |
