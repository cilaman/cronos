Add the live-execution overlay — the differentiator — to the editor.

- **Reuse SSE, not polling/websockets.** Subscribe to the 6.4 run-level stream for
  node/edge transitions and to each Agent child's `/api/tasks/{id}/stream` (`_run_buffer`
  replay covers late joiners).
- Map run state to React Flow styling: **active node pulses, completed edges thicken,
  failed paths desaturate.** Click a node → open its child task in ConversationStream.tsx
  (child id per node from 6.4 status).
- **Run history:** list past runs (from 6.4); open a finished run to replay final states +
  traces. Empty: "No runs yet."
- New `frontend/src/components/harness/RunOverlay.tsx` + `RunHistory.tsx`; handle many
  simultaneous streams without jank.

Acceptance: trigger from the editor and watch the overlay animate per node; click a running
node → its live log; open a past run → final state; no-runs harness shows the empty state.

