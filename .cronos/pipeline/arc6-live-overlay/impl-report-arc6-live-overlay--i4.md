---
cc_version: "1.0"
agent: pipeline-implementor
slug: arc6-live-overlay--i4
phase: impl
status: done
confidence: 0.95
inputs_used:
  - memory:project_arc6_visual_editor_impl
  - memory:project_pipeline_implementor_agent
  - .cronos/pipeline/arc6-live-overlay/design-report-arc6-live-overlay.md
  - .cronos/pipeline/arc6-live-overlay/impl-report-arc6-live-overlay--i4.md
  - .cronos/pipeline/arc6-live-overlay/review-report-arc6-live-overlay--attempt1.md
  - .cronos/pipeline/arc6-live-overlay/review-report-arc6-live-overlay--attempt2.md
  - frontend/src/components/harness/RunOverlay.tsx
  - frontend/src/components/harness/__tests__/RunOverlay.test.tsx
iteration_id: I4
files_changed:
  - frontend/src/components/harness/RunOverlay.tsx
  - frontend/src/components/harness/__tests__/RunOverlay.test.tsx
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/arc6-live-overlay/impl-report-arc6-live-overlay--i4.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 18
  files_read: 8
  memory_hits: 2
  diff_lines_added: 199
  diff_lines_removed: 1
---

## Summary

This revision fixes F2 (non-blocking, low severity) from review attempts 1 and 2: stale `runStatus`/`childTaskId`/`startedAt`/`endedAt` on `node.data` after switching runs via RunHistory. The approach adds a separate cleanup `useEffect` keyed on `runId` in `RunOverlay.tsx` that strips the four overlay fields from all nodes and resets animated-edge styling whenever `runId` changes — but skips initial mount (using a `prevRunIdRef` sentinel) to avoid spurious calls. The existing empty-map early-return guards in the `nodeStatuses` and `edgeStatuses` effects are preserved unchanged, so all 18 original tests pass without modification. Three new regression tests cover the stale-node cleanup, stale-edge cleanup, and the no-cleanup-on-first-mount invariant. All 21 RunOverlay tests pass. The HarnessEditor.runOverlay tests (I7 scope) also pass unchanged (13/13).

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/components/harness/RunOverlay.tsx | modified | +40 / -1 | Add `useRef` import; add cleanup `useEffect` keyed on `runId` that strips stale overlay fields from nodes and resets edge styling on run switch |
| frontend/src/components/harness/__tests__/RunOverlay.test.tsx | modified | +159 / 0 | Add 3 F2 regression tests: stale-node cleanup, stale-edge cleanup, no-cleanup-on-first-mount |

## Out-of-scope findings

- None.

## Assumptions

- The cleanup effect approach (separate `useEffect` keyed on `runId`) was chosen over removing the empty-map early-returns because: (a) three existing tests assert `setNodes`/`setEdges` are NOT called when maps are empty — removing the guards would break those tests without a deeper rewrite; (b) the cleanup effect more precisely targets the actual problem (run switch, not every empty-map tick); and (c) the review report's suggested alternative ("add a separate cleanup useEffect keyed on runId") matches this choice exactly.
- The `prevRunIdRef` is initialized to `undefined` (not `null`) to distinguish "never rendered" from "rendered with runId=null". This ensures the cleanup does not fire on the very first mount cycle, which is necessary to preserve the "no setNodes call on first mount" invariant tested by the new third test.
- Nodes that carry none of the four overlay fields are returned as the same object reference by the cleanup updater — this preserves the React Flow identity check and avoids unnecessary node remounts for non-overlay nodes.
- Scope files read before editing: all listed individually in inputs_used[].
- The eslint-disable comment on the cleanup effect's dependency array is intentional: the `prevRunIdRef` ref write inside the effect is not a dependency (refs do not trigger re-renders) and should not be in the array.

## Open questions

- None.

## Next consumer brief

Validation command to rerun: `cd frontend && npm test -- src/components/harness/__tests__/RunOverlay.test.tsx`

Companion check that should also be confirmed green: `cd frontend && npm test -- src/pages/__tests__/HarnessEditor.runOverlay.test.tsx` (13 tests, all pass — confirmed during this revision).

Key notes for the test agent:
1. **3 new F2 regression tests added** (tests 19–21 in the suite): "clears stale runStatus and childTaskId from nodes when switching runs", "clears stale edge styling when switching runs", and "does NOT call setNodes on first mount". These cover the run-switch stale-data path that was absent in the original 18 tests.
2. **All 18 original tests preserved unchanged** — R7 rAF batching contract, R8 legacy-invariant, R1 buffer_truncated banner, and all other behaviors are unmodified.
3. **No edge cases beyond the design** — the `prevRunIdRef` sentinel pattern is standard React and does not introduce any async or timing subtlety; the cleanup fires synchronously within the same render cycle as the `runId` prop change.
4. **I7 HarnessEditor.runOverlay tests unaffected** — confirmed 13/13 green; the cleanup effect in RunOverlay is invisible to the I7 test because the mocked RunOverlay in HarnessEditor tests never exercises the real cleanup path.
