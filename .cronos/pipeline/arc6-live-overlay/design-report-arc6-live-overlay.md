---
cc_version: '1.0'
agent: pipeline-architect
slug: arc6-live-overlay
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:project_arc6_visual_editor_impl
- memory:project_arc6_64_run_lifecycle_review
- memory:project_arc6_board_setup
- .cronos/pipeline/arc6-live-overlay/analysis-report-arc6-live-overlay.md
- .cronos/pipeline/arc6-live-overlay/scout-report-arc6-live-overlay.md
- frontend/src/hooks/useHarnessRuns.ts
- frontend/src/pages/HarnessEditor.tsx
- frontend/src/components/harness/AgentNode.tsx
- frontend/src/components/ConversationStream.tsx
outputs_produced:
- .cronos/pipeline/arc6-live-overlay/design-report-arc6-live-overlay.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/components/harness/
  - frontend/src/pages/HarnessEditor.tsx
  - frontend/src/hooks/useHarnessRuns.ts
  - frontend/src/components/ConversationStream.tsx
  - frontend/src/api.ts
  excluded:
  - 'backend/app/api/harness_runs.py: no backend changes required (analysis OUT scope)'
  - 'backend/app/harnesses/: no backend changes required (analysis OUT scope)'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: frontend
  scope_files:
  - frontend/src/components/harness/runStatus.ts
  - frontend/src/components/harness/__tests__/runStatus.test.ts
  validation_command: cd frontend && npm test -- src/components/harness/__tests__/runStatus.test.ts
  max_diff_lines: 200
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/src/components/harness/AgentNode.tsx
  - frontend/src/components/harness/TriggerNode.tsx
  - frontend/src/components/harness/DecisionNode.tsx
  - frontend/src/components/harness/AggregatorNode.tsx
  - frontend/src/components/harness/WaitNode.tsx
  - frontend/src/components/harness/reactflow-overrides.css
  - frontend/src/components/harness/__tests__/nodeRunStatusStyling.test.tsx
  validation_command: cd frontend && npm test -- src/components/harness/__tests__/nodeRunStatusStyling.test.tsx
  max_diff_lines: 400
  depends_on:
  - I1
- id: I3
  type: frontend
  scope_files:
  - frontend/src/hooks/useRunStateOverlay.ts
  - frontend/src/hooks/__tests__/useRunStateOverlay.test.tsx
  validation_command: cd frontend && npm test -- src/hooks/__tests__/useRunStateOverlay.test.tsx
  max_diff_lines: 350
  depends_on:
  - I1
- id: I4
  type: frontend
  scope_files:
  - frontend/src/components/harness/RunOverlay.tsx
  - frontend/src/components/harness/__tests__/RunOverlay.test.tsx
  validation_command: cd frontend && npm test -- src/components/harness/__tests__/RunOverlay.test.tsx
  max_diff_lines: 450
  depends_on:
  - I2
  - I3
- id: I5
  type: frontend
  scope_files:
  - frontend/src/components/harness/RunHistory.tsx
  - frontend/src/components/harness/__tests__/RunHistory.test.tsx
  validation_command: cd frontend && npm test -- src/components/harness/__tests__/RunHistory.test.tsx
  max_diff_lines: 300
  depends_on: []
- id: I6
  type: frontend
  scope_files:
  - frontend/src/components/harness/ChildTaskDrawer.tsx
  - frontend/src/components/harness/__tests__/ChildTaskDrawer.test.tsx
  validation_command: cd frontend && npm test -- src/components/harness/__tests__/ChildTaskDrawer.test.tsx
  max_diff_lines: 250
  depends_on: []
- id: I7
  type: frontend
  scope_files:
  - frontend/src/pages/HarnessEditor.tsx
  - frontend/src/pages/__tests__/HarnessEditor.runOverlay.test.tsx
  validation_command: cd frontend && npm test -- src/pages/__tests__/HarnessEditor.runOverlay.test.tsx
  max_diff_lines: 400
  depends_on:
  - I4
  - I5
  - I6
risks:
- description: React Flow setNodes() called on every SSE event for harnesses with
    10+ concurrent in-progress nodes may exceed the browser's per-frame budget, producing
    visible stutter (R7).
  severity: medium
  mitigation: In I3 (useRunStateOverlay), coalesce incoming events into a pending
    map and flush via a single requestAnimationFrame callback per tick; assert non-stutter
    behavior in I4 RunOverlay.test.tsx by dispatching 20 synthetic node_transition
    events in a single act() and verifying setNodes is invoked at most twice.
- description: Replaying a finished run via RunHistory while another live run is in
    progress could leak the prior EventSource subscription, double-counting events
    or pinning a stale runId in node.data.
  severity: medium
  mitigation: 'In I3, the hook keys the EventSource by a `mode: ''live'' | ''replay''`
    discriminator; switching modes calls es.close() and resets pendingNodeStatus.
    I7 test asserts that selecting a past run after a live run does not keep the live
    EventSource open (spy on EventSource constructor count vs close count).'
- description: ConversationStream requires a full Task object (not just an ID), so
    naively passing child_task_id from NodeState will not satisfy its prop contract;
    an extra useTask(child_task_id) fetch is required and may briefly render an empty
    drawer (R3).
  severity: low
  mitigation: I6 (ChildTaskDrawer) wraps useTask(child_task_id) with a loading skeleton
    and renders ConversationStream only after the task resolves; test asserts skeleton
    -> ConversationStream transition and that a null child_task_id renders nothing.
- description: Adding a runStatus data attribute to existing node components could
    regress saved-harness rendering if persisted node.data already carries an unrelated
    runStatus key from a prior schema.
  severity: low
  mitigation: I1 defines runStatus as an optional, namespaced field on a typed RunStatusOverlayData
    interface; I2 nodes read it via a default-undefined accessor so legacy harnesses
    with no runStatus render exactly as before. The I2 test loads a stock harness
    fixture and asserts no className diff vs. main.
- description: buffer_truncated event arriving early in a long-running session is
    silently absorbed by event handlers (R1 AC-2), losing the integrity signal to
    the operator.
  severity: medium
  mitigation: I4 RunOverlay renders an explicit `data-testid='buffer-truncated-banner'`
    element when any buffer_truncated event appears in the stream's events array;
    test asserts the banner is visible and a-11y label reads 'Some events were dropped
    before this view connected.'
metrics:
  tool_calls: 11
  files_read: 6
  memory_hits: 3
  iterations_planned: 7
---

## Summary

This design splits the live-execution overlay into seven topologically-ordered frontend iterations centered on a single styling contract (`runStatus.ts`) consumed by both the existing harness node components and a new `RunOverlay`/`RunHistory` pair. The architectural decision is to use **React Flow `node.data.runStatus`** (not a context provider) as the styling channel — it keeps node components stateless, matches the existing `setNodes()` mutation pattern, and isolates re-renders to affected nodes. SSE event handling is centralized in a new `useRunStateOverlay` hook that coalesces bursts via `requestAnimationFrame` to satisfy R7 (10+ concurrent nodes without jank). Child-task logs (R3) open in a right-side `ChildTaskDrawer` that fetches the full Task via `useTask(child_task_id)` then renders the existing `ConversationStream` — keeping the Task-prop contract intact. `RunHistory` lives as a left-side panel inside `HarnessEditor`; the canvas stays visible (R6). Backend stays untouched.

## Components

### Data
- `frontend/src/components/harness/runStatus.ts` — pure module exporting the `NodeRunStatus` union (`'pending' | 'in_progress' | 'done' | 'failed' | 'skipped'`), the `RunStatusOverlayData` interface (the `runStatus`, `startedAt`, `endedAt`, `childTaskId` keys merged onto `node.data`), and the `runStatusClassName(status)` mapper returning the Tailwind class string per status. Single source of truth for node-and-edge styling.

### Backend
- (none — analysis report `## Scope` excludes all backend changes; existing `/api/harness-runs/{run_id}/stream` and `/api/tasks/{id}/stream` are reused as-is.)

### Frontend
- `useRunStateOverlay(runId, mode)` (`frontend/src/hooks/useRunStateOverlay.ts`) — wraps `useHarnessRunStream` for live mode and `useHarnessRun` for replay mode; reduces events into a `Map<nodeId, RunStatusOverlayData>` flushed via rAF; returns `{ nodeStatuses, edgeStatuses, bufferTruncated, status }`.
- `RunOverlay` (`frontend/src/components/harness/RunOverlay.tsx`) — top-level overlay component mounted inside `HarnessEditor`; receives `runId`, drives `setNodes`/`setEdges` from `useRunStateOverlay`, renders the buffer-truncated banner, and lifts node-click events upward via `onNodeOpen(child_task_id)`.
- `RunHistory` (`frontend/src/components/harness/RunHistory.tsx`) — left panel listing `useHarnessRuns(spaceId, name)` newest-first with status pill + timestamp; emits `onSelectRun(runId, mode: 'live' | 'replay')`; renders "No runs yet." when the list is empty (R5).
- `ChildTaskDrawer` (`frontend/src/components/harness/ChildTaskDrawer.tsx`) — right-side drawer that takes a `child_task_id`, calls `useTask`, and renders `ConversationStream` with the resolved Task. Renders nothing when id is null (R3 AC-2).
- Updated node components (`AgentNode.tsx`, `TriggerNode.tsx`, `DecisionNode.tsx`, `AggregatorNode.tsx`, `WaitNode.tsx`) — read `data.runStatus` via the typed accessor from `runStatus.ts` and append the corresponding Tailwind class; behavior unchanged when `runStatus` is undefined (R8 invariant).
- Modified `HarnessEditor.tsx` — adds layout slots for `RunHistory` (left) and `ChildTaskDrawer` (right), holds `currentRunId`+`mode` state, mounts `RunOverlay` when `currentRunId` is set, and threads `triggerHarnessRun` into the existing Save header (R6).
- Reused: `useHarnessRunStream` / `useHarnessRuns` / `useHarnessRun` / `useTriggerHarnessRun` from `useHarnessRuns.ts` (no extension required — scout's "minor extend" hint turned out to be unnecessary once SSE handling moved into `useRunStateOverlay`).

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                               | Validation                                                                                       |
|-----|----------|------------|----------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| I1  | frontend | -          | runStatus.ts, runStatus.test.ts                                      | cd frontend && npm test -- src/components/harness/__tests__/runStatus.test.ts                    |
| I2  | frontend | I1         | AgentNode/TriggerNode/DecisionNode/Aggregator/WaitNode + overrides.css | cd frontend && npm test -- src/components/harness/__tests__/nodeRunStatusStyling.test.tsx        |
| I3  | frontend | I1         | useRunStateOverlay.ts + test                                         | cd frontend && npm test -- src/hooks/__tests__/useRunStateOverlay.test.tsx                       |
| I4  | frontend | I2, I3     | RunOverlay.tsx + test                                                | cd frontend && npm test -- src/components/harness/__tests__/RunOverlay.test.tsx                  |
| I5  | frontend | -          | RunHistory.tsx + test                                                | cd frontend && npm test -- src/components/harness/__tests__/RunHistory.test.tsx                  |
| I6  | frontend | -          | ChildTaskDrawer.tsx + test                                           | cd frontend && npm test -- src/components/harness/__tests__/ChildTaskDrawer.test.tsx             |
| I7  | frontend | I4, I5, I6 | HarnessEditor.tsx + runOverlay.test.tsx                              | cd frontend && npm test -- src/pages/__tests__/HarnessEditor.runOverlay.test.tsx                 |

<!-- DAG layers (Kahn): L0 = {I1, I5, I6}; L1 = {I2, I3}; L2 = {I4}; L3 = {I7}. Wide first layer keeps implementor fan-out parallel. -->

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| setNodes() called per-event for 10+ concurrent nodes may stutter (R7) | medium | I3 hook coalesces events via rAF; I4 test verifies setNodes called <=2 times for 20-event burst |
| Past-run replay leaks live EventSource subscription | medium | I3 hook keys by mode discriminator + es.close() on mode change; I7 asserts EventSource constructor vs close balance |
| ConversationStream needs full Task, not just an ID (R3) | low | I6 ChildTaskDrawer fetches via useTask(child_task_id), renders skeleton then ConversationStream |
| Adding runStatus to node.data could collide with saved harness data | low | I1 namespaces runStatus on RunStatusOverlayData; I2 nodes default-undefined; fixture-load test asserts no diff |
| buffer_truncated absorbed silently (R1 AC-2) | medium | I4 RunOverlay renders an explicit banner with a-11y label when any buffer_truncated event appears |

## Assumptions

- `node.data.runStatus` as the styling channel (per scout finding 5 and the analysis next-consumer brief decision 2) — chosen over a React context provider because it integrates with the existing `setNodes()` mutation flow and minimizes re-render scope to affected nodes only.
- Overlay placement uses split-pane / side-drawer layout (RunHistory left, ChildTaskDrawer right, canvas center) per analysis next-consumer brief decision 1 — no modal, since R6 requires the canvas stays visible.
- `useRunStateOverlay` consolidates SSE + replay so individual node components remain stateless; this is a load-bearing architectural choice for R7 (the rAF batching point lives in one place).
- ConversationStream's existing Task-prop contract is preserved (no signature change) per analysis assumption that ConversationStream accepts any valid task ID — I6 satisfies this by fetching the Task via `useTask` before rendering.
- React Flow 12 (@xyflow/react) `setNodes` does not remount unaffected node components when only `data` changes for one node — confirmed by scout finding 5 and prior memory `project_arc6_visual_editor_impl`.
- `npm test` runs vitest; per memory `project_arc6_visual_editor_impl` no `--coverage` flag is needed and tests are file-scoped via vitest's positional pattern.

## Open questions

- None.

## Next consumer brief

Implementors should read `iterations[]` strictly in DAG order: L0 = {I1, I5, I6} can run fully in parallel, L1 = {I2, I3} after I1, L2 = {I4} after both, L3 = {I7} last. The cross-iteration invariant that does NOT live in any single `scope_files` block is the **`RunStatusOverlayData` shape from I1's `runStatus.ts`** — every later iteration imports it (I2 to read `data.runStatus`, I3 to populate the map, I4 to thread it into `setNodes`, I7 to type the layout state). Implementor I1 must export it from `runStatus.ts` with the exact field names `runStatus`, `startedAt`, `endedAt`, `childTaskId`; downstream implementors must not rename these. The R7 batching contract is also load-bearing: I3 must use `requestAnimationFrame` (not `startTransition`, not `setTimeout`); I4's test will assert this. No unresolved open questions blocking implementation.
