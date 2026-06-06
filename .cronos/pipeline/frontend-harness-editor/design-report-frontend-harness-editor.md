---
cc_version: '1.0'
agent: pipeline-architect
slug: frontend-harness-editor
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:arc6-visual-editor-impl
- memory:arc6-harnesses
- memory:feedback_pipeline_narrow_k_coverage
- .cronos/pipeline/frontend-harness-editor/analysis-report-frontend-harness-editor.md
- .cronos/pipeline/frontend-harness-editor/scout-report-frontend-harness-editor.md
outputs_produced:
- .cronos/pipeline/frontend-harness-editor/design-report-frontend-harness-editor.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/types.ts
  - frontend/src/components/harness/harnessMapping.ts
  - frontend/src/components/harness/VariableInspector.tsx
  - frontend/src/pages/HarnessEditor.tsx
  - frontend/src/components/harness/AgentNode.tsx
  - frontend/src/components/harness/TriggerNode.tsx
  - frontend/src/components/harness/DecisionNode.tsx
  - frontend/src/components/harness/WaitNode.tsx
  - frontend/src/components/harness/AggregatorNode.tsx
  - frontend/src/components/harness/NodePalette.tsx
  excluded:
  - backend/: model.py is immutable per feature request; backend already verified
      by scout
  - frontend/src/pages/HarnessRunsPage.tsx: out of scope per analyst Scope/Out section
  - frontend/src/pages/HarnessListPage.tsx: out of scope per analyst Scope/Out section
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: frontend
  scope_files:
  - frontend/src/types.ts
  - frontend/src/components/harness/harnessMapping.ts
  - frontend/src/components/harness/harnessMapping.test.ts
  validation_command: cd frontend && npm test -- src/components/harness/harnessMapping.test.ts
  max_diff_lines: 600
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/src/components/harness/VariableInspector.tsx
  - frontend/src/components/harness/VariableInspector.test.tsx
  validation_command: cd frontend && npm test -- src/components/harness/VariableInspector.test.tsx
  max_diff_lines: 500
  depends_on:
  - I1
- id: I3
  type: frontend
  scope_files:
  - frontend/src/pages/HarnessEditor.tsx
  - frontend/src/pages/HarnessEditor.test.tsx
  validation_command: cd frontend && npm test -- src/pages/HarnessEditor.test.tsx
  max_diff_lines: 450
  depends_on:
  - I1
  - I2
- id: I4
  type: frontend
  scope_files:
  - frontend/src/pages/HarnessEditor.tsx
  - frontend/src/pages/HarnessEditor.test.tsx
  validation_command: cd frontend && npm run build
  max_diff_lines: 300
  depends_on:
  - I1
  - I2
  - I3
risks:
- description: Renaming HarnessNode.config to HarnessNode.data in types.ts produces
    a TypeScript strict-mode cascade across harnessMapping.ts, VariableInspector.tsx,
    HarnessEditor.tsx, and any other consumer. A partial fix leaves the workspace
    in a non-compiling state between iterations.
  severity: high
  mitigation: 'Iteration I1 is intentionally atomic: types.ts + harnessMapping.ts
    + harnessMapping.test.ts ship as one diff (max_diff_lines=600) so the type rename
    and the only two pure-data consumers land together. I2 and I3 depend on I1, ensuring
    downstream UI iterations only run against a typechecking baseline. The final I4
    gate runs `npm run build` (which executes `tsc -b && vite build`) to catch any
    residual type drift.'
- description: React Flow v12 (@xyflow/react) does not pass selected edges to a side
    panel by default; condition editing for decision-out edges (R4) requires either
    an onEdgeClick + selected-edge prop wired into VariableInspector or an inline
    edge editor on the canvas. A naive implementation either misses edge selection
    entirely (R4 acceptance fails) or duplicates selection state between node-selected
    and edge-selected branches.
  severity: medium
  mitigation: 'Adopt analyst-preferred Option (a): HarnessEditor.tsx maintains a single
    selectedItem state machine — { kind: ''node'' | ''edge'' | ''none'', id: string
    | null }. The canvas wires onNodeClick and onEdgeClick to set this state; VariableInspector
    accepts an optional `selectedEdge: HarnessEdge | null` prop alongside `selectedNode`.
    When kind=''edge'' and the edge''s source node is a DecisionNode, VariableInspector
    renders the editable condition field (yes/no/empty=default). I3 owns the wiring;
    I2 owns the inspector field rendering.'
- description: AggregatorNode renders a static N=2 input handles (in-0, in-1) but
    the analyst Open question 2 leaves dynamic port count out of scope. If fromReactFlow()
    defaults Aggregator to fewer than 2 ports, the existing canvas-rendered handles
    will reference unknown ports and the backend will return 422; if it emits more
    than 2, the canvas will not render the extra handles.
  severity: medium
  mitigation: 'I1 fixes fromReactFlow() default ports for AggregatorNode at exactly
    { ''in-0'': {}, ''in-1'': {}, ''out'': {} } — matching the current static render.
    Dynamic port count remains explicitly deferred (documented in design ## Assumptions).
    I1 vitest spec asserts the exact port keys for each of the five node types per
    analyst R3 acceptance criteria.'
- description: Backend 422 responses are not a plain string — FastAPI/Pydantic v2
    returns a list of `{loc, msg, type}` dicts under `detail`. If R7 surface logic
    stringifies the response naively, the user sees `[object Object]` or `undefined`.
    The error shape varies between fetch failures (network), HTTPException strings,
    and Pydantic validation arrays.
  severity: medium
  mitigation: 'I3 (HarnessEditor.tsx error surface) implements a `formatSaveError(error)`
    helper with three branches: (a) network/transport error → use error.message; (b)
    HTTPException with string detail → render detail; (c) Pydantic validation array
    → join each entry as `${loc.join(''.'')}: ${msg}` separated by newlines. The vitest
    spec for I3 covers all three shapes. The visible DOM element uses data-testid=''save-error''
    per analyst R7 AC.'
metrics:
  tool_calls: 5
  files_read: 2
  memory_hits: 3
  iterations_planned: 4
---

## Summary

Align the harness visual editor to the immutable backend data model in four ordered iterations: a single atomic data-layer change (I1: types.ts + harnessMapping.ts + tests) that flips `HarnessNode.config` → `HarnessNode.data`, normalizes ports to a dict, generates correct per-node-type default ports, round-trips edge `condition`, and persists `data.prompt_template`; a UI-layer change (I2) that adds per-node-type editable fields in VariableInspector plus variable add/remove plus selected-edge condition editing; a canvas wiring change (I3) that wires `onVariableChange` to real state, adds an edge-selection state machine, and surfaces 422 errors via a `formatSaveError` helper at `data-testid="save-error"`; and a final build gate (I4) that runs `npm run build` to catch any residual TypeScript drift. The DAG is intentionally serialized — every UI iteration depends on the type rename landing first — to avoid leaving the workspace in a non-compiling state.

## Components

### Data
- `frontend/src/types.ts` (HarnessNode interface): replace `config: Record<string,unknown>` with `data: Record<string,unknown>`; change `ports` from `NodePort[]` to `Record<string, Record<string, unknown>>`; HarnessEdge gains optional `condition: string | null`.
- `frontend/src/components/harness/harnessMapping.ts` (`toReactFlow`/`fromReactFlow`): spread `node.data` directly into RF `data` (no `config` wrapper); separate `_ports` handling removed; emit `ports` as dict; generate default ports per node type for new nodes; round-trip edge `condition` via RF edge `data.condition`.

### Backend
- (No backend changes — model.py is immutable per feature request and analyst Scope.)

### Frontend
- `frontend/src/components/harness/VariableInspector.tsx`: read/write `data.prompt_template` (not `config.prompt`); add per-node-type editable sections — Wait (mode dropdown human/timed + conditional `max_wait_seconds`/`duration_seconds`), Aggregator (mode dropdown all/any), Trigger (kind dropdown cron/webhook/file-change/task-state-change + per-kind fields per model.py); add edge-condition field when a decision-out edge is selected; add Add/Remove variable row controls.
- `frontend/src/pages/HarnessEditor.tsx`: replace the no-op `onVariableChange={() => {}}` with a real handler mutating local `variables` state; add `selectedItem` state machine (kind: node | edge | none) and wire `onNodeClick` + `onEdgeClick`; pass `selectedEdge` into VariableInspector; implement `formatSaveError` and render at `data-testid="save-error"` while `saveMutation.isError`; clear error on next successful save.
- `frontend/src/components/harness/AgentNode.tsx` / `TriggerNode.tsx` / `DecisionNode.tsx` / `WaitNode.tsx` / `AggregatorNode.tsx`: no behavioral changes required; existing Handle ids already match the default port keys. If a node component imports `HarnessNode.config` or `NodePort[]` for display, update the field reference. Touched only if I1 produces a downstream type error.
- `frontend/src/components/harness/NodePalette.tsx`: no changes (covered for completeness; absent from final iteration scope_files).

## Implementation plan

| ID  | Type     | Depends on   | Scope files (abridged)                                                                                                | Validation                                                                       |
|-----|----------|--------------|-----------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| I1  | frontend | -            | types.ts, components/harness/harnessMapping.ts, components/harness/harnessMapping.test.ts                             | cd frontend && npm test -- src/components/harness/harnessMapping.test.ts          |
| I2  | frontend | I1           | components/harness/VariableInspector.tsx, components/harness/VariableInspector.test.tsx                               | cd frontend && npm test -- src/components/harness/VariableInspector.test.tsx      |
| I3  | frontend | I1, I2       | pages/HarnessEditor.tsx, pages/HarnessEditor.test.tsx                                                                 | cd frontend && npm test -- src/pages/HarnessEditor.test.tsx                       |
| I4  | frontend | I1, I2, I3   | pages/HarnessEditor.tsx, pages/HarnessEditor.test.tsx                                                                 | cd frontend && npm run build                                                      |

<!-- Requirement coverage cross-check:
  R1 (data round-trip, types.ts data field): I1
  R2 (prompt_template persistence): I1 (harnessMapping passes data.prompt_template through) + I2 (VariableInspector binds to data.prompt_template)
  R3 (ports as dict + defaults): I1
  R4 (edge condition round-trip + edit UI): I1 (round-trip) + I2 (inspector field) + I3 (edge selection wiring)
  R5 (per-node-type editors): I2
  R6 (variables add/edit/remove): I2 (UI controls) + I3 (onVariableChange wiring)
  R7 (422 error display): I3
  R8 (vitest coverage + npm test + npm build): I1 (mapping spec) + I2 (inspector spec) + I3 (editor spec) + I4 (npm run build gate)
-->

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| TypeScript strict-mode cascade when `HarnessNode.config` → `HarnessNode.data` flips | high | I1 ships types.ts + harnessMapping.ts + tests atomically (budget 600 LOC); I4 final `npm run build` catches residual drift |
| React Flow v12 has no built-in selected-edge → side-panel wiring for decision condition editing | medium | I3 owns a `selectedItem` state machine (kind: node/edge/none); VariableInspector accepts `selectedEdge` prop wired in I2 |
| AggregatorNode default port count is ambiguous (analyst Open question 2) | medium | I1 hard-codes default `{in-0:{}, in-1:{}, out:{}}` matching the static N=2 canvas render; dynamic port count explicitly deferred |
| Backend 422 response shape is a list of `{loc,msg,type}` dicts, not a string (R7 risk) | medium | I3 implements `formatSaveError` with three branches (network / string detail / Pydantic array); vitest covers all three |

## Assumptions

- `has_ui: true` from analysis is binding; all four iterations are frontend-class. No backend, infra, or data iterations are needed because `model.py` is the immutable contract.
- The implementor will use `@xyflow/react` (per memory:arc6-visual-editor-impl), not the legacy `reactflow` package.
- Vitest specs run via `cd frontend && npm test -- <path>` per memory:feedback_pipeline_narrow_k_coverage; no `--cov-fail-under` flag applies on the frontend side.
- `npm run build` in `frontend/` runs `tsc -b && vite build` and is the canonical TypeScript gate.
- AggregatorNode default port count is fixed at 2 (`in-0`, `in-1`) per analyst Open question 2; dynamic port expansion remains out of scope.
- Edge selection uses analyst-preferred Option (a): React Flow `onEdgeClick` → HarnessEditor `selectedItem` state → VariableInspector renders edge-condition field.
- Test files live colocated with source per the existing frontend convention (e.g., `frontend/src/components/harness/harnessMapping.test.ts`, `frontend/src/pages/HarnessEditor.test.tsx`).
- Coupling-aware iteration count is 4 (well under the 12 cap); the DAG is intentionally a serial chain because every UI iteration must compile against the new types from I1.

## Open questions

- None blocking. The three Open questions in the analysis report are all resolved here: (1) edge selection via Option (a) state machine in I3; (2) Aggregator defaults at N=2 in I1; (3) `HarnessNode.ports` typed as `Record<string, Record<string, unknown>>` in I1.

## Next consumer brief

Implementor: read YAML `iterations[]` and pick your assigned `I<N>`. Treat `scope_files` as a hard diff boundary; the verifier and reviewer reject any path outside it. Treat `validation_command` as the literal command the test agent will execute — do not rename test files. Cross-iteration invariants the YAML does not encode: (a) the default port dicts for new nodes in `fromReactFlow()` MUST be exactly `{in:{}, out:{}}` for Agent/Wait, `{out:{}}` for Trigger, `{in:{}, yes:{}, no:{}}` for Decision, and `{'in-0':{}, 'in-1':{}, out:{}}` for Aggregator — these match canvas-rendered Handle ids and a mismatch produces backend 422; (b) the error DOM element MUST be `data-testid="save-error"` per analyst R7 AC; (c) the agent prompt textarea binds to `data.prompt_template` (NOT `data.prompt`, NOT `config.prompt`); (d) edges use a single selected-item state machine — do not duplicate node-selected and edge-selected state. Risks: see the risk register for the 422-shape formatting helper contract (`formatSaveError` three branches). No open questions remain.
