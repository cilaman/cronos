---
cc_version: "1.0"
agent: pipeline-implementor
slug: gui-button-focus--i3
phase: impl
status: done
confidence: 0.92
inputs_used:
  - memory:project_gui_refactor_board_setup.md
  - memory:gui-tokens-brand RESOLVED
  - memory:gui-badge-system review RESOLVED
  - .cronos/pipeline/gui-button-focus/design-report-gui-button-focus.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i1.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i2.md
  - frontend/src/components/ui/Button.tsx
  - frontend/src/components/ui/IconButton.tsx
  - frontend/src/components/Lane.tsx
  - frontend/src/components/SpaceFilterDropdown.tsx
  - frontend/src/components/ViewPicker.tsx
  - frontend/src/components/ui/StickyToolbar.tsx
  - frontend/src/components/__tests__/Lane.test.tsx
  - frontend/src/__tests__/ViewPicker.test.tsx
iteration_id: I3
files_changed:
  - frontend/src/components/Lane.tsx
  - frontend/src/components/SpaceFilterDropdown.tsx
  - frontend/src/components/ViewPicker.tsx
  - frontend/src/components/__tests__/Lane.buttons.test.tsx
  - frontend/src/components/__tests__/SpaceFilterDropdown.buttons.test.tsx
  - frontend/src/components/__tests__/ViewPicker.buttons.test.tsx
validation_command_passed: true
out_of_scope_findings:
  - description: "The design spec says aria-label='Add task' for the Lane add button but the existing out-of-scope Lane.test.tsx uses 'New task'. The aria-label was kept as 'New task' to preserve backward compatibility with the existing test suite. The design's intent (a descriptive aria-label on the IconButton) is fulfilled."
    location: "frontend/src/components/__tests__/Lane.test.tsx:102"
    severity: low
  - description: "StickyToolbar.tsx contains no inline <button> elements — it is a pure layout wrapper (renders a <div>). No migration needed."
    location: "frontend/src/components/ui/StickyToolbar.tsx"
    severity: low
outputs_produced:
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i3.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 32
  files_read: 14
  memory_hits: 3
  diff_lines_added: 594
  diff_lines_removed: 41
---

## Summary

I3 migrates all inline `<button>` elements in the shell-wave files to use the `Button` and `IconButton` primitives from I1 and I2. `Lane.tsx` replaces its add-task and hide-lane raw buttons with `IconButton` (`size="compact"`, preserving the existing `aria-label="New task"` and `"Hide <label> lane"` labels for backward compatibility with the existing out-of-scope `Lane.test.tsx`). `SpaceFilterDropdown.tsx` converts its trigger to `Button archetype="dropdown-trigger" variant="secondary"` and its three dropdown item buttons to `Button archetype="list-row" variant="ghost"`. `ViewPicker.tsx` converts its trigger likewise and converts all view-item buttons plus the "Manage views…" button to `Button archetype="list-row"`. `StickyToolbar.tsx` was audited and contains no inline `<button>` elements — left untouched. Three new button test files (32 tests total) were created and all pass. Validation command exited 0.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/components/Lane.tsx | modified | +9 / -11 | Replace 2 inline buttons with IconButton (compact size, existing aria-labels preserved) |
| frontend/src/components/SpaceFilterDropdown.tsx | modified | +19 / -16 | Replace trigger + "All spaces" + space items with Button primitives |
| frontend/src/components/ViewPicker.tsx | modified | +19 / -14 | Replace trigger + view items + Manage views button with Button primitives |
| frontend/src/components/__tests__/Lane.buttons.test.tsx | created | +143 / 0 | 14 tests: button tagName, aria-label, focus ring, click handlers, coexistence |
| frontend/src/components/__tests__/SpaceFilterDropdown.buttons.test.tsx | created | +184 / 0 | 9 tests: trigger button semantics, focus ring, dropdown items all have focus ring |
| frontend/src/components/__tests__/ViewPicker.buttons.test.tsx | created | +220 / 0 | 9 tests: trigger button semantics, focus ring, all dropdown items have focus ring |

## Out-of-scope findings

- `frontend/src/components/__tests__/Lane.test.tsx:102`: Existing test suite uses `aria-label="New task"` for the add button. The design spec called for `aria-label="Add task"` but changing it would silently break the out-of-scope Lane.test.tsx (which has 6 assertions using "New task"). Kept original label. Low severity — the semantic intent (a descriptive aria-label on a real `<button>`) is satisfied either way. I6's full test run will validate consistency.
- `frontend/src/components/ui/StickyToolbar.tsx`: No inline `<button>` elements found. File is a pure layout `<div>` wrapper; no migration was performed.

## Assumptions

- I1 and I2 are both `status: done` (confirmed by reading their impl-reports). The `Button` and `IconButton` primitives are available with the full API (archetype prop, compact size, focus ring).
- `IconButton` requires an `aria-label` string prop (enforced by TypeScript). The `compact` size (`h-8 w-8`) was used for lane header buttons because 44px would overflow the `h-10` StickyToolbar header.
- `Button archetype="list-row"` already provides `w-full justify-start` via the archetype class definition, so no additional `w-full` className is needed on dropdown item buttons.
- The `variant="ghost"` was chosen for dropdown items because it uses `border-transparent` — appropriate for items inside an already-bordered dropdown container. The trigger uses `variant="secondary"` to match the original bordered appearance.
- `variant="secondary"` with `archetype="dropdown-trigger"` was used for both SpaceFilterDropdown and ViewPicker triggers to preserve the bordered, surface-colored appearance of the original inline buttons.
- The design report's `aria-label="Add task"` direction was superseded by backward-compatibility with the existing Lane.test.tsx (`aria-label="New task"`). This is documented as an out-of-scope finding.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Validation command to rerun: `cd frontend && npm test -- src/components/__tests__/Lane.buttons.test.tsx src/components/__tests__/SpaceFilterDropdown.buttons.test.tsx src/components/__tests__/ViewPicker.buttons.test.tsx`

Edge cases uncovered during implementation:
1. **aria-label discrepancy**: The design says `aria-label="Add task"` for the Lane add button but the existing `Lane.test.tsx` (out-of-scope) asserts `aria-label="New task"`. I kept "New task" to avoid breaking the full test suite. The I6 gate (`npm test && npm run build`) will catch any regressions. If the orchestrator wants to align with "Add task", a scope-expanded iteration touching `Lane.test.tsx` is needed.
2. **IconButton compact size in StickyToolbar**: The Lane header uses `h-10` (40px); using the default `h-11` (44px) IconButton would overflow. `size="compact"` (`h-8 w-8`, 32px) was chosen. This is the intended escape hatch per the design risk register (R7 mitigation: "compact size for dense-toolbar callers that explicitly need to waive the WCAG minimum").
3. **Button variant selection**: SpaceFilterDropdown and ViewPicker triggers use `variant="secondary"` (bordered, surface-2 background) to visually match the original inline button appearance. Dropdown items use `variant="ghost"` (no border, no background) since they are inside an already-bordered container.
4. **StickyToolbar audit result**: No `<button>` elements found — it is purely a layout wrapper `<div>`. No test file was created for it.
5. **Focus ring on all Button instances**: The `Button` archetype classes are applied after `FOCUS_RING` in the `cn()` call, so all archetype variants inherit focus ring. The test suite asserts this for every rendered button.
