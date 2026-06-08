---
cc_version: "1.0"
agent: pipeline-implementor
slug: feature-detail-view--i5
phase: impl
status: done
confidence: 0.97
iteration_id: I5
inputs_used:
  - .cronos/pipeline/feature-detail-view/design-report-feature-detail-view--feature-detail-panel.md
  - .cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md
  - .cronos/pipeline/feature-detail-view/impl-report-feature-detail-view--i1.md
  - frontend/src/types.ts
  - frontend/src/api.ts
  - frontend/src/hooks/useFeatures.ts
  - frontend/src/components/FeaturesBoard.tsx
  - frontend/src/components/Board.tsx
  - frontend/src/components/Detail.tsx
  - frontend/src/components/Lane.tsx
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/pages/FeaturesPage.tsx
  - frontend/src/components/__tests__/FeaturesBoard.test.tsx
  - frontend/src/components/__tests__/Board.sharedBacklog.test.tsx
outputs_produced:
  - .cronos/pipeline/feature-detail-view/impl-report-feature-detail-view--i5.md
blockers: []
next_consumer: test
files_changed:
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/components/__tests__/FeatureDetail.test.tsx
  - frontend/src/components/FeaturesBoard.tsx
  - frontend/src/components/__tests__/FeaturesBoard.test.tsx
  - frontend/src/components/Board.tsx
  - frontend/src/components/__tests__/Board.sharedBacklog.test.tsx
  - frontend/src/components/__tests__/Board.features-backlog.test.tsx
validation_command_passed: true
metrics:
  tool_calls: 28
  files_read: 16
  memory_hits: 4
  diff_lines_added: 622
  diff_lines_removed: 8
---

## Summary

Implemented SG2: FeatureDetail Panel + Board Wiring across iterations I2–I5 (I1 was
previously completed). The implementation delivers:

1. **I2** — `FeatureDetail.tsx` (new, ~250 LOC): single-pane modal mirroring Detail.tsx
   lifecycle (Esc key handler, Modal wrapper, inline title+brief editing via
   `usePatchFeature`, waiting_question amber box, Process button with confirm-dialog
   guarded call to `useProcessFeature`, realizing_items list with per-row Unlink button
   calling `useSetRealize({ feature_id: null })`). All mutations go through hooks —
   never via direct api.* calls (R4 triple-key contract preserved).

2. **I3** — `FeaturesBoard.tsx` wiring: replaced dead `onOpen={() => {}}` with
   `onOpen={setOpenFeatureId}` (live URL searchParam handler), added `useSearchParams`
   import, wired `<FeatureDetail featureId={openFeatureId} onClose={...} />` outside
   the DndContext fragment (mirrors Board.tsx:318 pattern). FeaturesPage.tsx requires no
   changes (single-mount invariant: FeatureDetail lives in FeaturesBoard only).

3. **I4** — `Board.tsx:308-309` deep-link fix: changed both `onClick` and `onOpenTask`
   callsites from `navigate("/features")` to `navigate(\`/features?feature=${task.id}\`)`
   so Tasks-board Features-Backlog cards open the panel directly.

4. **I5** — Integration verification: full `npm run build` passes with no TypeScript
   errors; `npm test` (all 1152 tests) passes.

## Files changed

- `frontend/src/components/FeatureDetail.tsx` — NEW. 250-line single-pane modal:
  feature_state + type + feature_key + id badges in header; inline edit form (title +
  brief textarea) via usePatchFeature; waiting_question amber box (`data-testid="waiting-question-box"`
  for tests); Process button (disabled when feature_state==='processing', confirm-dialog
  guarded); realizing_items section with per-row Unlink button; issue_url link section.

- `frontend/src/components/__tests__/FeatureDetail.test.tsx` — NEW. 23 tests covering:
  loading/error states, data rendering (title/brief/badges/feature_key), waiting_question
  box show/hide, Process button disabled state + mutateAsync call + confirm cancel,
  realizing_items render + Unlink mutation, inline edit form (Save + Cancel paths),
  Close button + Esc key close behavior.

- `frontend/src/components/FeaturesBoard.tsx` — Added `useSearchParams` import,
  `FeatureDetail` import; added `openFeatureId` URL param state + `setOpenFeatureId`
  handler; replaced dead `onOpen={() => {}}` with `onOpen={setOpenFeatureId}`; wrapped
  return in fragment to mount `<FeatureDetail>` outside DndContext.

- `frontend/src/components/__tests__/FeaturesBoard.test.tsx` — Added `userEvent`
  import; updated `renderBoard` helper to accept `initialUrl` param; added
  `vi.mock("../FeatureDetail", ...)` stub; added 4 new tests (section 5): URL-param
  renders FeatureDetail, no param hides it, card click sets param, close removes it.

- `frontend/src/components/Board.tsx` — Lines 308-309: changed both `onClick` and
  `onOpenTask` to `navigate(\`/features?feature=${task.id}\`)`.

- `frontend/src/components/__tests__/Board.sharedBacklog.test.tsx` — Updated the
  navigate assertion from `"/features"` to `"/features?feature=feat-1"`.

- `frontend/src/components/__tests__/Board.features-backlog.test.tsx` — NEW. 4 tests
  verifying deep-link behavior: onClick uses `/features?feature=<id>`, unique IDs per
  card, does NOT navigate to plain `/features`, onClick path verified.

## Out-of-scope findings

- `frontend/src/pages/FeaturesPage.tsx`: intentionally unchanged — single-mount
  invariant confirmed (FeaturesBoard owns the panel mount).
- The DragOverlay Card `onClick={() => {}}` in FeaturesBoard is intentionally kept as
  no-op: the drag overlay is a visual ghost, not a click target.

## Assumptions

- **I1 already shipped** — `types.ts:FeatureRead`, `api.ts` methods, and `useFeatures.ts`
  hooks were all present on main (verified by reading the files before implementing).
- **Single-mount invariant** — `<FeatureDetail>` is rendered exactly once, inside
  `FeaturesBoard.tsx`. `FeaturesPage.tsx` does not import or render it.
- **URL key `"feature"` (lowercase)** — used consistently across FeaturesBoard (write),
  Board.tsx:308-309 (write), and any consumer reading `searchParams.get("feature")`.
- **`window.confirm` in Process button** — matches the Detail.tsx pattern for
  destructive/expensive actions (see Detail.tsx:849 for delete). Recommend keeping for
  S4 decomposition cost reasons.

## Open questions

None blocking. All design iterations delivered and validated.

## Next consumer brief

**For test agent (CC-v1 tester phase):**

New exports available:
- `components/FeatureDetail.tsx`: `FeatureDetail({ featureId, onClose })` — modal
  panel; renders when featureId is non-null; calls `usePatchFeature`, `useProcessFeature`,
  `useSetRealize` from `hooks/useFeatures`.
- `components/FeaturesBoard.tsx`: now reads `?feature=<id>` from URL searchParams and
  renders `<FeatureDetail>` conditionally; `onOpen` in Lane is live (no longer a no-op).
- `components/Board.tsx:308-309`: both props now call
  `navigate(\`/features?feature=${task.id}\`)`.

Test targets already covered:
1. FeatureDetail.test.tsx — 23 tests (all passing): loading, error, data rendering,
   waiting_question box, Process button states, realizing_items + Unlink, inline edit,
   close behavior.
2. FeaturesBoard.test.tsx — 20 tests (all passing, 4 new): card click → URL param →
   FeatureDetail renders; close button removes it.
3. Board.features-backlog.test.tsx — 4 tests (all passing): deep-link URL shape.
4. Board.sharedBacklog.test.tsx — 11 tests (all passing, 1 updated): navigate assertion
   updated to `/features?feature=feat-1`.

Validation: `cd frontend && npm run build` passes (1152 tests, 0 type errors).
