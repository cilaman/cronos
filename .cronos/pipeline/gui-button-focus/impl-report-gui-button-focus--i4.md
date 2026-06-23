---
cc_version: "1.0"
agent: pipeline-implementor
slug: gui-button-focus--i4
phase: impl
status: done
confidence: 0.88
inputs_used:
  - memory:project_gui_refactor_board_setup.md
  - memory:gui-tokens-brand RESOLVED
  - memory:gui-badge-system review RESOLVED
  - .cronos/pipeline/gui-button-focus/design-report-gui-button-focus.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i1.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i2.md
  - frontend/src/components/Card.tsx
  - frontend/src/components/__tests__/Card.test.tsx
  - frontend/src/pages/BoardPage.tsx
  - frontend/src/components/ui/Button.tsx
  - frontend/src/components/Lane.tsx
  - frontend/src/components/Board.tsx
  - frontend/src/components/BoardToolbar.tsx
iteration_id: I4
files_changed:
  - frontend/src/components/Card.tsx
  - frontend/src/components/__tests__/Card.test.tsx
  - frontend/src/components/__tests__/Card.buttons.test.tsx
  - frontend/src/pages/__tests__/BoardPage.addtask.test.tsx
validation_command_passed: true
out_of_scope_findings:
  - description: "BoardPage.tsx has no inline <button> or role='button' elements — all
      button-level UI (add-task chip, sort/compact toggles, new-task button) is delegated
      to BoardToolbar and Board child components which are out of I4 scope. The design
      brief targets BoardPage for the board wave but there is nothing to migrate in the
      file itself."
    location: "frontend/src/pages/BoardPage.tsx"
    severity: low
  - description: "The parent-breadcrumb and realizes-chip span[role='button'] elements
      are nested INSIDE the card body <button>. Converting them to native <button>
      elements would produce invalid HTML (nested interactive elements). They remain
      as span[role='button'] with keyboard handlers per ARIA authoring practices.
      A future refactor could restructure the card body to avoid this nesting."
    location: "frontend/src/components/Card.tsx:489,509"
    severity: low
  - description: "The proposed-PR and proposed-issue-path action elements were already
      native <button> elements (pre-I4) nested inside the card body role='button' div.
      After converting the card body to a native <button>, these became nested buttons
      (invalid HTML). They have been converted to span[role='button'] in this iteration
      to resolve the nesting violation — this is an incidental fix discovered during
      implementation."
    location: "frontend/src/components/Card.tsx:430,457"
    severity: low
outputs_produced:
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i4.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 40
  files_read: 13
  memory_hits: 3
  diff_lines_added: 623
  diff_lines_removed: 162
---

## Summary

Iteration I4 converts the main card body `role="button"` div in `Card.tsx` to a native `<button type="button">` while preserving all dnd-kit `useSortable` refs and attributes (the drag `listeners` were already on a separate drag-handle span, not the card body itself — making this conversion straightforward). The existing `Card.test.tsx` was updated to replace the stale `div[role='button']` query selector with `button:last-child` for the card body. Two new test files were created: `Card.buttons.test.tsx` (17 tests asserting semantic tag correctness and dnd-kit attribute preservation) and `BoardPage.addtask.test.tsx` (5 tests for the add-task flow). The validation command exits 0 with 22/22 tests passing. One key design finding: `BoardPage.tsx` itself has no inline buttons to migrate (all button-level UI is in child components), and two nested-button HTML violations were discovered and corrected incidentally.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/components/Card.tsx | modified | +88 / -156 | Convert card body div[role='button'] to native button; convert nested proposed-PR and proposed-issue buttons to span[role='button'] to avoid nested-button HTML violation |
| frontend/src/components/__tests__/Card.test.tsx | modified | +6 / -6 | Update `div[role='button']` query selectors to `button:last-child` to match the converted card body |
| frontend/src/components/__tests__/Card.buttons.test.tsx | created | +315 / 0 | 17 tests asserting card body is native button, drag attributes preserved, focus ring present, interaction callbacks work |
| frontend/src/pages/__tests__/BoardPage.addtask.test.tsx | created | +214 / 0 | 5 tests verifying BoardPage wires add-task correctly and toolbar new-task button is a native button |

## Out-of-scope findings

- `frontend/src/pages/BoardPage.tsx`: No inline `<button>` or `role="button"` elements exist in this file. All button-level UI is delegated to `BoardToolbar` and `Board` child components. Nothing to migrate in I4 scope.
- `frontend/src/components/Card.tsx:489,509`: The parent-breadcrumb and realizes-chip elements are `span[role='button']` nested inside the card body `<button>`. Converting them to native buttons would create invalid nested-button HTML. They remain as ARIA role="button" spans with keyboard handlers. This is a known limitation of the current card DOM structure.
- `frontend/src/components/Card.tsx:430,457`: The proposed-PR and proposed-issue-path action elements were pre-existing `<button>` elements nested inside the card body (which was `role="button"` div before I4). Converting the card body to a native `<button>` created a nested-button violation. These were converted to `span[role='button']` as part of this iteration.

## Assumptions

- dnd-kit's `useSortable` injects `role="button"` and `aria-roledescription="sortable"` onto the outer wrapper div via the `attributes` spread. This is expected dnd-kit behaviour and is NOT a scope violation — the outer wrapper remains a div.
- The drag `listeners` in `Card.tsx` (default density path) were already applied to a separate `<span aria-label="Drag">` element, not the `role="button"` div body. This means converting the card body to `<button>` does not move or duplicate any drag listener attachment.
- `BoardPage.tsx` has no inline buttons to migrate. The design's description of "add-task dashed-border chip" refers to elements that, in the current codebase, live in `Lane.tsx` (migrated to `IconButton` in I3) and `Board.tsx` (the hidden-lanes restore chip). Neither file is in I4 scope. The `BoardPage.addtask.test.tsx` tests the orchestration of the add-task flow at the page level instead.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Re-run the verbatim validation command:
`cd frontend && npm test -- src/components/__tests__/Card.buttons.test.tsx src/pages/__tests__/BoardPage.addtask.test.tsx`

Edge cases uncovered during implementation:
1. **dnd-kit outer wrapper**: `useSortable` with `attributes` spread adds `role="button"` and `aria-roledescription="sortable"` to the outer wrapper div — this is expected and is NOT a test failure. The Card.buttons.test.tsx explicitly asserts that the sortable wrapper has `aria-roledescription="sortable"` to lock in this understanding.
2. **Nested button HTML violation (pre-existing)**: The proposed-PR and proposed-issue-path `<button>` elements inside the card body were pre-existing violations that only became HTML-invalid after the card body was converted from `div[role='button']` to `<button>`. They were converted to `span[role='button']` to fix this. The test agent should verify that `getByTitle("Draft issue (no GitHub remote)")` and `getByTitle("PROPOSED PR (no GitHub remote)")` still work in Card.test.tsx.
3. **BoardPage.tsx is unchanged**: No diff on this file; the `BoardPage.addtask.test.tsx` tests the page via mocked child components. The test agent should confirm 0 files_changed on BoardPage.tsx is acceptable given the out-of-scope finding.
4. **Card.test.tsx selector update**: The 6 changed lines replace `div[role='button']` with `button:last-child` in 4 test locations. The selector finds the card body button (last direct child of the inner flex wrapper). If the card structure changes in a future iteration, this selector may need updating.

Out-of-scope findings of priority concern for the next review cycle:
- The card DOM has several interactive elements (breadcrumb, realizes chip) nested inside the main card body button. A future design iteration should consider restructuring the card body to avoid interactive descendants that need stopPropagation. This is a WCAG concern (interactive controls should not contain other interactive controls).
