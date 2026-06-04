---
cc_version: "1.0"
agent: pipeline-implementor
slug: arc6-live-overlay--i5
phase: impl
status: done
confidence: 0.92
inputs_used:
  - memory:project_pipeline_implementor_agent
  - memory:project_arc6_visual_editor_impl
  - .cronos/pipeline/arc6-live-overlay/design-report-arc6-live-overlay.md
  - frontend/src/hooks/useHarnessRuns.ts
  - frontend/src/components/harness/AgentNode.tsx
  - frontend/src/components/harness/__tests__/nodes.test.tsx
  - frontend/src/components/harness/__tests__/VariableInspector.test.tsx
iteration_id: I5
files_changed:
  - frontend/src/components/harness/RunHistory.tsx
  - frontend/src/components/harness/__tests__/RunHistory.test.tsx
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/arc6-live-overlay/impl-report-arc6-live-overlay--i5.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 17
  files_read: 7
  memory_hits: 2
  diff_lines_added: 251
  diff_lines_removed: 0
---

## Summary

I5 creates `RunHistory.tsx` (left-panel component listing harness runs newest-first with status pill + timestamp) and its test suite `RunHistory.test.tsx`. The component calls `useHarnessRuns(spaceId, name)` from `useHarnessRuns.ts`, sorts results by `triggered_at` descending, emits `onSelectRun(runId, "live")` for running runs and `onSelectRun(runId, "replay")` for all other statuses, and renders "No runs yet." when the list is empty (R5). All 12 tests pass against the validation command.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/components/harness/RunHistory.tsx | created | +94 / 0 | Left-panel component listing harness runs with status pills, timestamps, and onSelectRun callback |
| frontend/src/components/harness/__tests__/RunHistory.test.tsx | created | +157 / 0 | 12 vitest tests covering empty state, loading, error, sorted order, live/replay mode dispatch, status pill labels, and hook args |

## Out-of-scope findings

- None.

## Assumptions

- `RunSummary.status === "running"` is the only live status; all other statuses ("done", "failed", "cancelled") map to `mode: "replay"`. This matches the `RunSummary` type in `api.ts`.
- No `runStatus.ts` import is needed in I5 since I5 has no `depends_on` (L0 layer). The `RunHistory` component does not consume the `NodeRunStatus` union — it uses `RunSummary["status"]` directly for its own pill styling.
- Tailwind classes (`bg-blue-100`, `bg-green-100`, `bg-red-100`, `bg-gray-100`, `bg-surface-3`) are consistent with `bg-surface-2` used in `AgentNode.tsx`.
- Scope files read before editing: all listed individually in `inputs_used[]`.

## Open questions

- None.

## Next consumer brief

Validation command to rerun: `cd frontend && npm test -- src/components/harness/__tests__/RunHistory.test.tsx`

All 12 tests pass. No edge cases uncovered beyond what the design specified. One implementation detail worth noting for I7 integration: `RunHistory` exports `RunHistoryProps` as a named interface, so I7 can import it directly. The component is stateless (no internal `selectedRunId` state) — I7 must hold `currentRunId` state and pass it down. No out-of-scope findings.
