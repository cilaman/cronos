---
cc_version: "1.0"
agent: pipeline-implementor
slug: gui-polish--i2
phase: impl
status: done
confidence: 0.93
inputs_used:
  - memory:project_gui_refactor_board_setup
  - memory:gui-tokens-brand RESOLVED
  - .cronos/pipeline/gui-polish/design-report-gui-polish.md
  - frontend/src/components/ui/Button.tsx
  - frontend/src/components/ui/EmptyState.tsx
  - frontend/src/components/ui/IconButton.tsx
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/components/ui/__tests__/ui.test.tsx
  - frontend/vitest.config.ts
  - frontend/src/utils/cn.ts
iteration_id: I2
files_changed:
  - frontend/src/components/ui/Tabs.tsx
  - frontend/src/components/ui/Dropdown.tsx
  - frontend/src/components/ui/Tooltip.tsx
  - frontend/src/components/ui/StatTile.tsx
  - frontend/src/components/ui/ProgressBar.tsx
  - frontend/src/components/ui/__tests__/Tabs.test.tsx
  - frontend/src/components/ui/__tests__/Dropdown.test.tsx
  - frontend/src/components/ui/__tests__/Tooltip.test.tsx
  - frontend/src/components/ui/__tests__/StatTile.test.tsx
  - frontend/src/components/ui/__tests__/ProgressBar.test.tsx
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/gui-polish/impl-report-gui-polish--i2.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 32
  files_read: 10
  memory_hits: 2
  diff_lines_added: 896
  diff_lines_removed: 0
---

## Summary

Iteration I2 of gui-polish is complete. Five new UI primitive components were created in isolation (`Tabs.tsx`, `Dropdown.tsx`, `Tooltip.tsx`, `StatTile.tsx`, `ProgressBar.tsx`) along with five corresponding test files. The Tooltip component was initially implemented with a 50 ms debounce on hide, which caused two test failures; the debounce was removed in favour of immediate state update (simpler and correct for this primitive). All 60 tests across the 5 test files pass with exit code 0. No call-site modifications were made per the design's strict layer-split strategy (callers are migrated in I5/I6). The diff line count (896) exceeds the `max_diff_lines: 600` hint in the design; all 10 files are fully in scope and required to satisfy the iteration — the budget was underestimated relative to 5 components + 5 test files.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/components/ui/Tabs.tsx | created | +47 / 0 | Controlled tab bar; tablist + tab roles; active-underline accent style |
| frontend/src/components/ui/Dropdown.tsx | created | +111 / 0 | Keyboard-managed trigger+items dropdown; ESC/outside-click close; z-[20] |
| frontend/src/components/ui/Tooltip.tsx | created | +72 / 0 | Focus+hover tooltip primitive; aria-describedby wiring; z-[60] |
| frontend/src/components/ui/StatTile.tsx | created | +54 / 0 | Label/value/delta/tone stat tile extracted from DashboardPage pattern |
| frontend/src/components/ui/ProgressBar.tsx | created | +88 / 0 | Proportional fill with optional segments, tone, showLabel; progressbar role |
| frontend/src/components/ui/__tests__/Tabs.test.tsx | created | +79 / 0 | 9 tests: rendering, aria-selected, onChange, className, active styling |
| frontend/src/components/ui/__tests__/Dropdown.test.tsx | created | +99 / 0 | 11 tests: open/close, item selection, ESC, outside-click, disabled, z-[20], alignment |
| frontend/src/components/ui/__tests__/Tooltip.test.tsx | created | +135 / 0 | 11 tests: hover show/hide, focus show/hide, aria-describedby, z-[60], event forwarding |
| frontend/src/components/ui/__tests__/StatTile.test.tsx | created | +96 / 0 | 13 tests: label/value/delta rendering, all tone variants, empty delta, className |
| frontend/src/components/ui/__tests__/ProgressBar.test.tsx | created | +115 / 0 | 16 tests: progressbar role, aria attrs, fill widths, tones, segments, showLabel, edge cases |

## Out-of-scope findings

- None.

## Assumptions

- All 10 scope files were new; none existed before this iteration.
- The `cn` utility at `../../utils/cn` follows the same relative-path pattern used by existing UI components (confirmed by reading Button.tsx, IconButton.tsx, Modal.tsx).
- `Tooltip` hide is immediate (no debounce): the initial 50 ms debounce introduced complexity without benefit — callers that need animation can add CSS transitions. Tests confirm synchronous hide on blur/unhover.
- `Dropdown` uses the `style={{ display: "contents" }}` wrapper div trick to pass click events through to an arbitrary trigger node without imposing layout on the trigger element.
- `ProgressBar` multi-segment mode renders segments via a flex row; segment widths are proportional to `seg.value / max`. Segments are not required to sum to `max` — callers control the values.
- `StatTile` accepts `React.ReactNode` as `value` to allow rendered elements (sparklines, icons, etc.) in addition to plain numbers/strings.
- `diff_lines_added: 896` exceeds `max_diff_lines: 600` from the design. All files are fully within `scope_files[]`; the budget was underestimated for the amount of test coverage required. No scope escape occurred.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Verbatim validation command to rerun:
```
cd frontend && npm test -- src/components/ui/__tests__/Tabs.test.tsx src/components/ui/__tests__/Dropdown.test.tsx src/components/ui/__tests__/Tooltip.test.tsx src/components/ui/__tests__/StatTile.test.tsx src/components/ui/__tests__/ProgressBar.test.tsx --run
```

Result: 60/60 tests pass (exit code 0).

Edge cases uncovered during implementation:
1. **Tooltip debounce vs test environment**: a 50 ms hide delay interacts badly with `userEvent.setup()` real-timer mode. The debounce was removed. If a fade-out animation is desired, use CSS `opacity` transitions rather than a JS timer in the component.
2. **Dropdown trigger wrapper**: the `style={{ display: "contents" }}` div allows arbitrary trigger elements without altering the trigger's layout box. The outer container is `relative inline-block` — callers rendering Dropdown inside a `flex` or `grid` container should be aware this changes the layout context.
3. **ProgressBar segment mode**: when `segments` is provided, the `value` and `tone` props are ignored for fill rendering (segments define their own tones). The `aria-valuenow` still reflects the `value` prop for accessibility.
4. **StatTile delta suppression**: `delta=""` (empty string) produces no delta element (treated same as omitted). Callers that render `delta={0}` (the number zero) will see "0" rendered since `0 !== ""`.

Out-of-scope findings for next review cycle: none.
