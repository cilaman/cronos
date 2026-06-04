---
cc_version: "1.0"
agent: pipeline-scout
slug: arc6-live-overlay
phase: scout
status: done
confidence: 0.9
inputs_used:
  - memory:project_arc6_board_setup
  - memory:project_arc6_64_run_lifecycle_review
  - memory:project_arc6_visual_editor_impl
  - backend/app/api/harness_runs.py
  - backend/app/worker.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/run_index.py
  - frontend/src/pages/HarnessEditor.tsx
  - frontend/src/pages/HarnessRunsPage.tsx
  - frontend/src/components/HarnessRunPanel.tsx
  - frontend/src/hooks/useHarnessRuns.ts
  - frontend/src/api.ts
  - frontend/src/components/ConversationStream.tsx
  - frontend/src/components/harness/AgentNode.tsx
outputs_produced:
  - .cronos/pipeline/arc6-live-overlay/scout-report-arc6-live-overlay.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/api/harness_runs.py (SSE stream infrastructure)
    - backend/app/worker.py (event publishing and replay buffer)
    - frontend/src/pages/HarnessRunsPage.tsx (run history list)
    - frontend/src/components/HarnessRunPanel.tsx (run state visualization)
    - frontend/src/hooks/useHarnessRuns.ts (stream event handling)
    - frontend/src/components/harness/ (node styling)
  excluded:
    - test files: not required for feature implementation context
    - node_modules: dependency packages only
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Add the live-execution overlay — the differentiator — to the editor. Reuse SSE, not polling/websockets. Subscribe to the 6.4 run-level stream for node/edge transitions and to each Agent child's `/api/tasks/{id}/stream`. Map run state to React Flow styling: active node pulses, completed edges thicken, failed paths desaturate. Click a node → open its child task in ConversationStream.tsx. Run history: list past runs; open a finished run to replay final states + traces. New `frontend/src/components/harness/RunOverlay.tsx` + `RunHistory.tsx`; handle many simultaneous streams without jank."
metrics:
  tool_calls: 15
  files_read: 14
  memory_hits: 3
---

## Summary

The arc6-live-overlay feature reuses mature SSE infrastructure from Arc 6.4 (run-lifecycle branch) to overlay live node/edge transitions atop the React Flow canvas in HarnessEditor.tsx. The 6.4 run-level SSE stream (`GET /api/harness-runs/{run_id}/stream`) emits discriminated `node_transition`, `edge_chosen`, and `run_status` events with 2000-event buffer replay for late joiners. HarnessRunPanel.tsx already demonstrates consuming this stream; the overlay integrates that pattern into the editor via two new components (RunOverlay.tsx + RunHistory.tsx). Node state maps to React Flow styling via data attributes; child task logs open via ConversationStream.tsx. Run history queries the per-harness run index (`.cronos/harness-runs/{harness_id}-index.json`) to list and replay past runs.

## Coverage

### Searched
- **backend/app/api/harness_runs.py** — SSE stream endpoint (`GET /{run_id}/stream`), late-joiner replay via `_sse_harness_run_events()`, buffer_truncated synthetic event on overflow
- **backend/app/worker.py** — Worker `_run_buffer` (2000-event cap), `subscribe()` / `unsubscribe()` queues, `_publish()` event sink
- **backend/app/harnesses/run_state.py** — RunState + NodeState dataclasses; node status values (pending/in_progress/done/failed/skipped); child_task_id link
- **backend/app/harnesses/run_index.py** — RunSummary schema; index path `.cronos/harness-runs/{harness_id}-index.json`; append + update_run_status APIs
- **frontend/src/pages/HarnessRunsPage.tsx** — Run list with status badges; click-to-select via query param; HarnessRunPanel integration
- **frontend/src/components/HarnessRunPanel.tsx** — Live run consumption via `useHarnessRunStream()` hook; node row rendering with status/timing
- **frontend/src/hooks/useHarnessRuns.ts** — `useHarnessRunStream()` EventSource listener; discriminated event types; buffer_truncated handling
- **frontend/src/pages/HarnessEditor.tsx** — React Flow canvas wrapped in `.harness-canvas` div; node selection callback; NodePalette + VariableInspector sidebars
- **frontend/src/components/harness/AgentNode.tsx** — Sample node styling: Tailwind border/bg classes; Handle top/bottom ports

### Excluded
- **test files** (`*.test.tsx`, `*.test.ts`): not required for feature architecture
- **node_modules**: dependency introspection not needed
- **frontend build artifacts**: `.dist/` output only

### Strategies
- **memory_retrieval**: 3 relevant entries found (Arc 6 board setup, 6.4 run lifecycle fixes, 6.7 editor implementation patterns)
- **glob_structural**: located API routes (harness_runs.py), component tree (HarnessRunPanel, useHarnessRuns hooks), React Flow config
- **grep_symbol**: identified SSE endpoints, replay buffer mechanics, discriminated event types, Worker._publish internals
- **read_targeted**: deep-read architecture for SSE pattern, run state schema, node styling patterns, ConversationStream integration path

## Findings

### 1. SSE Stream Infrastructure (6.4 run-level stream)

**Endpoint**: `GET /api/harness-runs/{run_id}/stream` (harness_runs.py:238–292)

**Implementation**:
- Async generator `_sse_harness_run_events()` yields SSE-formatted lines.
- **Late-joiner replay**: `Worker.subscribe(run_id)` returns `(replay, q)` tuple where `replay` is a list of buffered events (up to 2000 per `_RUN_BUFFER_CAP`).
- **Buffer overflow signal**: if replay buffer was at capacity when subscribed, a synthetic `buffer_truncated` event is emitted first (line 215–219).
- **Event type discrimination**: each event's `type` field (e.g. `node_transition`, `edge_chosen`, `run_status`) is copied to the SSE `event:` field so EventSource listeners can use named event listeners.
- **Stream end**: when `_DONE_SENTINEL` is received from the queue, an `event: end` frame is sent and the generator returns (lines 227–231).

**Headers**:
```
Cache-Control: no-cache
X-Accel-Buffering: no
Connection: keep-alive
```

### 2. Task Stream Endpoint (`/api/tasks/{id}/stream`)

**Context**: Brief mentions "subscribe to each Agent child's `/api/tasks/{id}/stream`" for child task logs. This endpoint is managed by the Worker's SSE infrastructure (imported in tasks.py:30 as `sse_events`) but architecture is identical to harness-runs:
- Same `Worker.subscribe(task_id)` pattern for replay + live events.
- ConversationStream.tsx already consumes task streams via `useLiveStream()` hook for agent output rendering.

### 3. Run State Data Model (run_state.py)

**RunState** (run_state.py:68–139):
- `run_id`: unique run identifier (goal task ID per design)
- `harness_id`: the harness this run executes
- `goal_task_id`: the goal task that owns the run
- `nodes_executed`: dict[node_id → NodeState]
- `status`: 'running' | 'done' | 'failed' | 'cancelled'
- `waiting_node_id`: (optional) id of Wait(human) node currently blocking the run

**NodeState** (run_state.py:56–64):
- `status`: 'pending' | 'in_progress' | 'done' | 'failed' | 'skipped'
- `child_task_id`: task ID created by this node (for clicking to open ConversationStream)
- `output`: node result (optional)
- `reason`: failure reason (optional)
- `started_at`, `ended_at`: ISO-8601 UTC timestamps

**Persistence**: atomic save via `save_atomic(path, state)` to `.cronos/harness-runs/{run_id}.json` per space_dir.

### 4. Run History: Run Index

**Path**: `.cronos/harness-runs/{harness_id}-index.json` (per space_dir)

**Schema** (run_index.py:23–52):
- RunSummary array (JSON):
  ```json
  {
    "run_id": "...",
    "harness_id": "...",
    "status": "running|done|failed|cancelled",
    "triggered_at": "2026-06-03T12:34:56Z",
    "finished_at": "2026-06-03T12:45:00Z" (or null if running)
  }
  ```
- API: `read_index()` returns entries oldest-first; `append_run()` adds new summary; `update_run_status()` mutates a run's status/finished_at in-place (run_index.py:100–150).

**Frontend consumption** (HarnessRunsPage.tsx:101):
- `useHarnessRuns(spaceId, name)` calls `api.listHarnessRuns(spaceId, name)` which POSTs to `/api/spaces/{spaceId}/harnesses/{name}/runs`.
- Returns array of RunSummary; sorted newest-first for display (line 132–134).

### 5. React Flow Integration & Styling

**Canvas setup** (HarnessEditor.tsx:104–114):
- ReactFlow component with node/edge state managed by `useNodesState` / `useEdgesState`.
- Custom `nodeTypes` map (from nodeTypes.ts) for AgentNode, TriggerNode, DecisionNode, etc.
- Node selection callback (line 38–42): finds matching HarnessNode by id and sets `selectedNode` state.

**Node styling pattern** (AgentNode.tsx:10–24):
- Each node is a React component wrapping Tailwind classes (`border-hairline`, `bg-surface-2`, etc.) and @xyflow/react Handles for input/output ports.
- Styling is purely CSS-based; no dynamic class binding per run state yet.

**How to integrate live state**:
- Map RunState.nodes_executed[node_id].status → CSS class (e.g. `in_progress` → `animate-pulse border-amber-400`, `done` → `border-accent`, `failed` → `border-danger`).
- Update node.data with run state on each SSE event; React Flow will re-render via `setNodes()`.
- For edges: add stroke class based on destination node status (e.g. `done` → thicker stroke, `failed` → desaturated).

### 6. Run Overlay Consumer: HarnessRunPanel.tsx

**Architecture** (HarnessRunPanel.tsx:147–277):
- Query `useHarnessRun(runId)` for overall RunState.
- Conditionally subscribe to stream if run.status === 'running': `useHarnessRunStream(runId)` (line 150–152).
- Iterate nodes_executed and render NodeRow for each (lines 260–262).
- On SSE event, invalidate React Query caches to refresh (line 159–161).
- Display `buffer_truncated` badge if applicable (line 233–240).

**Key pattern for RunOverlay**:
- Use same hook pattern: `useHarnessRunStream(runId)` if overlay is visible.
- On each event, map node_id → React Flow node and update `node.data.status` + `node.data.started_at` etc.
- Trigger `setNodes()` to re-render; React Flow handles animation via CSS classes.

### 7. ConversationStream Integration

**Pattern** (ConversationStream.tsx:1–10, line 20–22):
- Accepts a Task prop and renders live agent output via `useLiveStream()` hook.
- Shows agent turns, tool calls, thinking blocks.

**For child task logs**:
- When user clicks a node in the overlay, retrieve `NodeState.child_task_id`.
- Pass that task to a ConversationStream panel (e.g. in a modal or side drawer).
- The hook `useLiveStream()` subscribes to `/api/tasks/{task_id}/stream` automatically.

### 8. Discriminated Event Types

From useHarnessRunStream (useHarnessRuns.ts:109–122):
```typescript
const HARNESS_EVENT_TYPES = [
  "node_transition",
  "edge_chosen",
  "run_status",
  "buffer_truncated",
] as const;
```

Each event type is a named EventSource listener target. Backend harness_runs.py line 254–259 documents the mapping:
- `event: node_transition` — harness node state change
- `event: edge_chosen` — BFS edge selection
- `event: run_status` — overall run status update
- `event: buffer_truncated` — synthetic overflow signal

**Payload structure**: `{ type: "...", [key]: value, ... }` — JSON after parsing.

### 9. Empty Run State Handling

**HarnessRunsPage.tsx:200–212** already demonstrates:
- "No runs yet" empty state when runs array is empty.
- "Run now" button to trigger the first run.

For the editor overlay:
- Show "No runs yet. Click a node to run, or use Run Now to start." until first run.
- Once a run exists, load run history via query param and display overlay on demand.

### 10. Practical Data Flow

**Live run on editor**:
1. User clicks "Run" button (or node triggers harness via control flow).
2. HarnessRunsPage POST `/api/spaces/{spaceId}/harnesses/{name}/run` → returns TriggerRunResponse with run_id.
3. Frontend opens RunOverlay, subscribes to `GET /api/harness-runs/{run_id}/stream`.
4. Backend publishes `node_transition` events as executor advances.
5. RunOverlay updates React Flow node.data; nodes re-render with new CSS classes (pulse, thicken, desaturate).
6. User clicks a node → ConversationStream opens in modal/drawer, showing child task log.
7. When run finishes, `run_status` event marks status=done; SSE stream sends `event: end`.

**Past run replay**:
1. User selects a finished run from RunHistory list.
2. Frontend loads RunState via GET `/api/harness-runs/{run_id}`.
3. RunOverlay reads final nodes_executed and displays static node states (no SSE subscription).
4. Clicking a node still opens its child task ConversationStream if child_task_id is set.

## Assumptions
- HarnessRunPanel.tsx's `useHarnessRunStream()` pattern is the reference implementation; overlay will reuse it directly.
- React Flow node data can be mutated via `setNodes()` with new `data.status`/`data.started_at` without breaking diffing.
- ConversationStream.tsx does not require task ID to be a direct child of the current task; it only needs a valid task ID to stream from.
- SSE buffer cap (2000 events) is sufficient for multi-node harnesses in typical runtimes; no additional cap needed in overlay.
- `/api/tasks/{id}/stream` endpoint exists and works identically to `/api/harness-runs/{run_id}/stream` (both use Worker._run_buffer).

## Open questions
- None.

## Next consumer brief

**Analysis agent should focus on**:

1. **UI/UX placement**: Where does RunOverlay sit relative to HarnessEditor canvas? Overlay panel, modal, split-pane?
2. **Event filtering**: Should edge_chosen events be filtered client-side or consumed raw? Depends on how many harnesses have frequent edge transitions.
3. **Performance**: With many simultaneous nodes executing and SSE events arriving in bursts, does React's reconciliation keep up? Estimated node count per harness and event frequency needed.
4. **Child task navigation**: When user clicks a node with child_task_id, does it open ConversationStream in a modal, side panel, or new tab? Link to existing Detail.tsx pattern.
5. **Replay interaction**: Past runs show static final states. Should clicking "replay" show animated playback of state transitions? Or just show final snapshot?
6. **Run history UI**: Should run history be a drawer on the left (like run list in HarnessRunsPage), or a modal overlay? Context: HarnessRunsPage has 2-pane layout; HarnessEditor is full-canvas.
7. **Error recovery**: If SSE stream drops (e.g. network), should overlay show "reconnecting…" and attempt resume? Or close and show "stream ended"?
8. **Styling API**: AgentNode uses Tailwind; how to pass live status CSS classes? Via node.data attribute or a separate run-state context provider?

Downstream analysis/design should establish visual hierarchy, component boundaries (RunOverlay vs RunHistory split), and state management pattern (local vs shared context).
