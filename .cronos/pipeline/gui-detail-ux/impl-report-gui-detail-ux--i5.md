---
cc_version: '1.0'
agent: pipeline-implementor
slug: gui-detail-ux--i5
phase: impl
status: done
confidence: 0.95
inputs_used:
- .cronos/pipeline/gui-detail-ux/design-report-gui-detail-ux.md
- .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i4.md
- frontend/src/components/Detail.tsx
- frontend/src/components/__tests__/Detail.test.tsx
- frontend/src/hooks/useLiveStream.ts
- docs/ui-ux-review/brand/states/cronos-state-active-animated.svg
iteration_id: I5
files_changed:
- frontend/src/components/Detail.tsx
- frontend/src/components/__tests__/Detail.test.tsx
- frontend/src/assets/cronos-state-active-animated.svg
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
- .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i5.md
blockers: []
next_consumer: review
metrics:
  tool_calls: 18
  files_read: 6
  memory_hits: 2
  diff_lines_added: 110
  diff_lines_removed: 5
---

## Summary

Added "NOW running" live indicator card to the conversation pane in `Detail.tsx`.
Wired `useLiveStream` for last tool name and step count. Copied animated SVG
asset to `frontend/src/assets/` for Vite Docker compatibility. 5 new tests.
Total: 30/30 Detail tests pass.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/components/Detail.tsx | modified | +60 / -5 | Add useLiveStream hook, derive liveToolName + liveStepCount, render NOW running card (data-testid="now-running-card") inside right pane when task.state === "active" |
| frontend/src/components/__tests__/Detail.test.tsx | modified | +45 / -0 | Add useLiveStream + SVG mocks, beforeEach mock reset, 5 I5 NOW-running-card tests |
| frontend/src/assets/cronos-state-active-animated.svg | created | +5 / -0 | Animated SVG copied from docs/ui-ux-review/brand/states/ for Vite import |

## Out-of-scope findings

None.

## Assumptions

- SVG is imported as a URL string via Vite's default asset import (`import url from "../assets/file.svg"`); the `vite/client` types declaration provides the `string` type for this pattern.
- `liveToolName` finds the last entry with `kind === "tool_call"` in reverse order, using its `name` field.
- `liveStepCount` counts entries with `kind === "tool_call"` or `kind === "assistant"`.
- `vi.restoreAllMocks()` in two delete/confirm tests resets the `vi.fn().mockReturnValue()` on `useLiveStream`; fixed by adding `vi.mocked(useLiveStream).mockReturnValue({ entries: [], status: "ended" })` to `beforeEach`.
- Token count renders as `'—'` placeholder per design spec (not derived from stream).

## Open questions

None.

## Next consumer brief

Validation command:
```
cd /data/spaces/cronos-development/frontend
npm test -- src/components/__tests__/Detail.test.tsx --run
```

All 30 tests pass (25 pre-existing + 5 new I5 tests). I8 adds the full-suite
build+test gate including `DetailPRSection.test.tsx` mock fix for active-state tasks.
