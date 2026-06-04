---
cc_version: '1.0'
agent: pipeline-analyst
slug: arc6-live-overlay
phase: analysis
status: done
confidence: 0.88
inputs_used:
- memory:project_arc6_visual_editor_impl
- memory:project_arc6_64_run_lifecycle_review
- memory:project_arc6_board_setup
- .cronos/pipeline/arc6-live-overlay/scout-report-arc6-live-overlay.md
- backend/app/pipeline/CONTRACT.md
- backend/app/pipeline/verify.py
- backend/app/pipeline/schemas/analysis.schema.yaml
outputs_produced:
- .cronos/pipeline/arc6-live-overlay/analysis-report-arc6-live-overlay.md
blockers: []
next_consumer: design
request: "Add the live-execution overlay — the differentiator — to the editor.\n\n\
  - **Reuse SSE, not polling/websockets.** Subscribe to the 6.4 run-level stream for\n\
  \  node/edge transitions and to each Agent child's `/api/tasks/{id}/stream` (`_run_buffer`\n\
  \  replay covers late joiners).\n- Map run state to React Flow styling: **active\
  \ node pulses, completed edges thicken,\n  failed paths desaturate.** Click a node\
  \ → open its child task in ConversationStream.tsx\n  (child id per node from 6.4\
  \ status).\n- **Run history:** list past runs (from 6.4); open a finished run to\
  \ replay final states +\n  traces. Empty: \"No runs yet.\"\n- New `frontend/src/components/harness/RunOverlay.tsx`\
  \ + `RunHistory.tsx`; handle many\n  simultaneous streams without jank.\n\nAcceptance:\
  \ trigger from the editor and watch the overlay animate per node; click a running\n\
  node → its live log; open a past run → final state; no-runs harness shows the empty\
  \ state."
has_ui: true
coverage_summary:
  searched:
  - backend/app/api/harness_runs.py
  - backend/app/worker.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/run_index.py
  - frontend/src/pages/HarnessEditor.tsx
  - frontend/src/pages/HarnessRunsPage.tsx
  - frontend/src/components/HarnessRunPanel.tsx
  - frontend/src/hooks/useHarnessRuns.ts
  - frontend/src/components/harness/AgentNode.tsx
  - frontend/src/components/ConversationStream.tsx
  excluded:
  - 'test files (*.test.tsx, *.test.ts): not required for requirements derivation'
  - 'node_modules: dependency packages only'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
  - glob_structural
traceability:
- requirement_id: R1
  statement: RunOverlay.tsx subscribes to the 6.4 run-level SSE stream (GET /api/harness-runs/{run_id}/stream)
    using EventSource and handles late-joiner replay via the existing _run_buffer
    mechanism.
  acceptance_criteria:
  - Given a run is in progress, when RunOverlay mounts, then it connects via EventSource
    and replays all buffered events before receiving live ones.
  - Given a buffer_truncated event is received, then RunOverlay shows a visible truncation
    indicator rather than silently dropping state.
  - 'Given the SSE stream ends (event: end), then RunOverlay stops event processing
    and marks the run as finished.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: RunOverlay maps received SSE event types (node_transition, edge_chosen,
    run_status) to React Flow node and edge state updates via setNodes() / setEdges().
  acceptance_criteria:
  - Given a node_transition event with status in_progress, when processed, then the
    corresponding React Flow node gains an animate-pulse border-amber class.
  - Given a node_transition event with status done, when processed, then the node
    gains a thickened accent-border class and the outgoing edges gain a thicker stroke.
  - Given a node_transition event with status failed, when processed, then the node
    and its outgoing edges are rendered desaturated.
  - Given a node_transition event with status skipped, when processed, then the node
    is rendered with a neutral skipped style distinct from failed.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R3
  statement: Clicking a node in RunOverlay that has a child_task_id opens a ConversationStream
    panel showing the live or replayed task log for that child task.
  acceptance_criteria:
  - Given a node has child_task_id set in its NodeState, when the user clicks that
    node, then ConversationStream renders the task output for child_task_id.
  - Given a node has no child_task_id, when the user clicks it, then no ConversationStream
    panel opens.
  - Given the child task is still running, then ConversationStream subscribes to /api/tasks/{child_task_id}/stream
    and shows live output.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: RunHistory.tsx lists past runs for the current harness sorted newest-first,
    and selecting a finished run loads its final RunState snapshot into the editor
    overlay without an SSE subscription.
  acceptance_criteria:
  - Given a harness has completed runs, when RunHistory renders, then runs are listed
    newest-first with status badge and triggered_at timestamp.
  - Given the user selects a finished run, when the selection is applied, then RunOverlay
    displays the final node states from RunState.nodes_executed without subscribing
    to SSE.
  - Given a finished run node is clicked, then ConversationStream opens using its
    child_task_id from the stored NodeState.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R5
  statement: When a harness has no runs yet, the overlay UI shows an empty state reading
    'No runs yet.' rather than a blank or broken panel.
  acceptance_criteria:
  - Given listHarnessRuns returns an empty array, then RunHistory renders 'No runs
    yet.' text.
  - Given the overlay is opened on a harness with no run history, then no SSE connection
    is established and no spinner is stuck.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R6
  statement: The live-execution overlay is launched from within HarnessEditor.tsx
    and displays atop or alongside the React Flow canvas without replacing the editor
    view.
  acceptance_criteria:
  - Given HarnessEditor is open, when the user triggers a run, then RunOverlay appears
    within the editor layout (not on a separate page).
  - Given RunOverlay is visible, then the user can still see the React Flow canvas
    nodes and edges.
  verifying_phase: review
  confidence: 0.85
- requirement_id: R7
  statement: RunOverlay handles multiple simultaneous SSE event streams without UI
    jank; event dispatch is batched or debounced when needed.
  acceptance_criteria:
  - Given a harness run with 10 or more concurrent nodes emitting SSE events, when
    events arrive, then the React Flow canvas re-renders without visible stutter.
  - Given multiple ConversationStream panels are open, then each maintains its own
    independent EventSource subscription.
  verifying_phase: review
  confidence: 0.78
- requirement_id: R8
  statement: 'Two new frontend component files are created: frontend/src/components/harness/RunOverlay.tsx
    and frontend/src/components/harness/RunHistory.tsx.'
  acceptance_criteria:
  - Given the implementation is complete, then RunOverlay.tsx and RunHistory.tsx exist
    at the specified paths.
  - Given existing files were imported into the new components, then those files are
    modified only to add imports or pass new props.
  verifying_phase: review
  confidence: 0.95
metrics:
  tool_calls: 7
  files_read: 4
  memory_hits: 3
---

## Summary

The arc6-live-overlay feature adds a live-execution overlay to HarnessEditor that animates React Flow nodes and edges in real time as a harness run progresses. It reuses the mature SSE infrastructure from Arc 6.4 (`GET /api/harness-runs/{run_id}/stream` with 2000-event replay buffer) to drive per-node CSS class transitions: active nodes pulse amber, completed edges thicken, failed paths desaturate. Clicking a running node opens its child task log in an existing ConversationStream panel. A companion RunHistory component lists past runs from the harness run index and can replay final states statically. Two new frontend components are required (`RunOverlay.tsx`, `RunHistory.tsx`); the backend SSE infrastructure requires no changes.

## Scope

### In scope
- `frontend/src/components/harness/RunOverlay.tsx` — new component; subscribes to run-level SSE, maps node/edge events to React Flow styling
- `frontend/src/components/harness/RunHistory.tsx` — new component; lists past runs from run index, selects a finished run for static replay
- `frontend/src/pages/HarnessEditor.tsx` — modified to mount RunOverlay and RunHistory, wire Run trigger, pass run_id to overlay
- `frontend/src/hooks/useHarnessRuns.ts` — minor extension to expose useHarnessRunStream for RunOverlay reuse
- Node CSS class bindings in existing node components (AgentNode.tsx and peers) to accept a runStatus data prop
- Empty-state handling in RunHistory ("No runs yet.")
- ConversationStream integration: pass child_task_id from clicked node's NodeState

### Out of scope
- Backend SSE endpoints (harness_runs.py, worker.py): no changes required
- Run-state persistence (run_state.py, run_index.py): no changes required
- Animated step-by-step replay of past run event sequences: deferred
- New API endpoints or backend data models
- Mobile-specific layout adjustments for the overlay

### Deferred
- Animated (step-through) replay of past run event sequences — only final-state snapshot is in scope now
- SSE reconnect/retry logic with "reconnecting..." indicator if stream drops mid-run
- Run cancellation control from within the overlay
- Per-node timing bars or duration annotations

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | RunOverlay subscribes to the run-level SSE stream with late-joiner replay |
| R2 | SSE events drive React Flow node and edge styling (pulse / thicken / desaturate) |
| R3 | Clicking a node with a child_task_id opens ConversationStream for that task |
| R4 | RunHistory lists past runs; selecting a finished run loads its final static state |
| R5 | Empty-state: "No runs yet." when the harness has no run history |
| R6 | The overlay is launched from HarnessEditor and coexists with the canvas view |
| R7 | Multiple simultaneous streams handled without UI jank |
| R8 | Two new component files created (RunOverlay.tsx, RunHistory.tsx) |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — EventSource connects on mount, replays buffer, signals buffer_truncated, closes cleanly on stream end
- R2 — in_progress = pulse-amber; done = accent-border + thick edge; failed = desaturated; skipped = neutral style
- R3 — Click node with child_task_id opens ConversationStream; click node without = no-op
- R4 — Runs listed newest-first with status + timestamp; finished run click = static final states; node click still opens ConversationStream
- R5 — Empty array from listHarnessRuns = "No runs yet." text; no SSE connection, no stuck spinner
- R6 — Overlay appears inside HarnessEditor layout on run trigger; canvas remains visible
- R7 — 10+ concurrent nodes emit without stutter; multiple ConversationStream panels maintain independent subscriptions
- R8 — RunOverlay.tsx and RunHistory.tsx exist at canonical paths after implementation

## Traceability

The full requirement to acceptance criteria to verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | RunOverlay.tsx subscribes to the 6.4 run-level SSE stream with late-joiner replay |
| R2 | test | SSE events map to React Flow styling (pulse / thicken / desaturate / skipped) |
| R3 | test | Click node opens ConversationStream for child_task_id |
| R4 | test | RunHistory lists past runs; finished run = final static state |
| R5 | test | Empty state "No runs yet." when no run history |
| R6 | review | Overlay launched from HarnessEditor, coexists with canvas |
| R7 | review | Multiple simultaneous streams without jank |
| R8 | review | RunOverlay.tsx and RunHistory.tsx created at canonical paths |

## Assumptions

- has_ui: true rationale: the entire feature is frontend-only UI; new React Flow overlay components with live CSS animations.
- The useHarnessRunStream() hook already exported from frontend/src/hooks/useHarnessRuns.ts (scout finding 6) is the correct reuse point for RunOverlay's SSE subscription — no new hook skeleton needed.
- React Flow's setNodes() call with updated node.data fields does not cause full-tree remounts; only the affected node components re-render (standard React Flow contract per scout finding 5).
- The SSE 2000-event buffer cap is sufficient for all harnesses in scope — no additional client-side event windowing is required.
- child_task_id in NodeState may be absent for non-Agent nodes (TriggerNode, DecisionNode); the overlay must guard this case (R3 acceptance criterion 2).
- ConversationStream.tsx accepts any valid task ID regardless of task hierarchy — it only needs child_task_id to be a real task UUID (scout finding 7).
- The design agent will decide the visual placement of the overlay (drawer vs. split-pane vs. modal); R6 only constrains that the canvas remains visible.
- The scout report has status: done and confidence: 0.9; no upstream blockers.

## Open questions

- None.

## Next consumer brief

Read `traceability[]` (R1-R8) for the requirement set; `has_ui: true` routes through the UI design sub-track. Scout findings 1-3 document the complete SSE contract (endpoint, event types, buffer mechanics) — the design agent does not need to re-investigate these.

Key design decisions not yet resolved that the design agent must settle:

1. **Overlay placement**: Where RunOverlay sits relative to the React Flow canvas — right-side drawer, floating panel, or split-pane. Scout finding 5 shows current HarnessEditor layout structure.

2. **Styling API**: How live runStatus values reach individual node components — via node.data attribute on each React Flow node object, or a React context provider. The design agent should pick one pattern for all node types (AgentNode, TriggerNode, DecisionNode, etc.).

3. **ConversationStream mounting**: Whether the child-task log panel is a modal, a side drawer anchored to the overlay, or reuse of the existing task detail side-panel. Determines which existing component gets a new "open task" prop.

4. **Batching strategy for R7**: If event bursts cause jank, specify whether to batch setNodes calls via requestAnimationFrame, React 18 startTransition, or a 50ms debounce timer.

Scope files for implementation: `frontend/src/components/harness/RunOverlay.tsx` (new), `frontend/src/components/harness/RunHistory.tsx` (new), `frontend/src/pages/HarnessEditor.tsx` (modify), `frontend/src/hooks/useHarnessRuns.ts` (minor extend), node components under `frontend/src/components/harness/` (CSS class additions only).
