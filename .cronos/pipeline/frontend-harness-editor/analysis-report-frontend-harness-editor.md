---
cc_version: '1.0'
agent: pipeline-analyst
slug: frontend-harness-editor
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:arc6-visual-editor-impl
- memory:arc6-harnesses
- .cronos/pipeline/frontend-harness-editor/scout-report-frontend-harness-editor.md
- backend/app/harnesses/model.py
- frontend/src/types.ts
- frontend/src/components/harness/harnessMapping.ts
- frontend/src/pages/HarnessEditor.tsx
outputs_produced:
- .cronos/pipeline/frontend-harness-editor/analysis-report-frontend-harness-editor.md
blockers: []
next_consumer: design
request: "Align the harness visual editor to the backend data model so saved harnesses\n\
  are valid and runnable. The backend model in `backend/app/harnesses/model.py` is\
  \ the source of\ntruth and MUST NOT be changed.\n\nAcceptance criteria:\n1. **Node\
  \ data round-trip.** `frontend/src/components/harness/harnessMapping.ts` `toReactFlow()`\n\
  \   maps backend `node.data` into the editor and `fromReactFlow()` maps editor state\
  \ back into\n   `node.data` (NOT a separate `config` key). No keys are dropped in\
  \ either direction. Update\n   `frontend/src/types.ts` so the node type exposes\
  \ `data` consistently.\n2. **prompt_template.** The agent prompt field persists\
  \ to `node.data.prompt_template` (what the\n   runtime reads at `backend/app/harnesses/executor.py:736`).\
  \ `VariableInspector.tsx` currently\n   reads/writes `config.prompt` — fix it.\n\
  3. **ports as dict + defaults + Handle ids.** `fromReactFlow()` emits `ports` as\
  \ `dict[str,dict]`\n   (never a list, never `[]`). New nodes get default ports matching\
  \ the Handle `id`s their node\n   component renders: DecisionNode (`yes`,`no`),\
  \ AgentNode/TriggerNode/WaitNode (single in/out),\n   AggregatorNode (N inputs +\
  \ single out). A freshly dragged node must save without a 422.\n4. **Edge condition\
  \ round-trip + editing.** `HarnessEdge.condition: str|None` (backend) maps to/from\n\
  \   the editor edge. Decision-out edges expose an editable condition (`yes`/`no`/default\
  \ = null).\n5. **Editable config for ALL node types**, not just Agent: decision\
  \ condition, wait\n   `max_wait_seconds` + mode, aggregator `mode` (all/any), trigger\
  \ kind + per-kind fields.\n6. **Variables add/edit/remove.** Wire `onVariableChange`\
  \ through `HarnessEditor.tsx` so it mutates\n   `harness.variables`; add UI to add\
  \ and remove variable rows. Saved harness has the variables.\n7. **Save feedback.**\
  \ Surface backend 422 validation errors in the editor (inline or toast) instead\n\
  \   of failing silently."
has_ui: true
coverage_summary:
  searched:
  - backend/app/harnesses/model.py
  - frontend/src/types.ts
  - frontend/src/components/harness/harnessMapping.ts
  - frontend/src/pages/HarnessEditor.tsx
  - .cronos/pipeline/frontend-harness-editor/scout-report-frontend-harness-editor.md
  excluded:
  - backend/app/harnesses/executor.py: only the specific line 736 referenced for prompt_template
      key; not re-explored
  - frontend/src/components/harness/*Node.tsx: Handle ids confirmed correct per scout;
      no additional reads needed
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: 'harnessMapping.ts toReactFlow() maps backend node.data into the React
    Flow node''s data prop (not a config key), and fromReactFlow() maps editor state
    back into node.data; no keys are dropped in either direction; HarnessNode in types.ts
    exposes data: Record<string,unknown> instead of config.'
  acceptance_criteria:
  - 'Given a backend Harness with nodes where node.data = {prompt_template: ''x'',
    mode: ''human''}, when toReactFlow() is called, then each RF node''s data contains
    prompt_template and mode without wrapping them in a config sub-object.'
  - Given an RF node whose data contains arbitrary keys, when fromReactFlow() is called,
    then the resulting HarnessNode.data contains exactly those keys (minus internal
    RF keys label/type/id).
  - 'types.ts HarnessNode interface has field data: Record<string,unknown> and ports:
    Record<string, Record<string,unknown>>; the config and ports: NodePort[] fields
    are removed.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: The agent prompt field in VariableInspector.tsx reads and writes node.data.prompt_template
    so that what the user types is persisted to the correct key consumed by the backend
    executor at executor.py:736.
  acceptance_criteria:
  - 'Given an AgentNode is selected in the editor, when the user edits the prompt
    field, then onNodeChange is called with { prompt_template: <value> } (not prompt).'
  - Given a saved harness loaded from the backend with node.data.prompt_template =
    'foo', when toReactFlow() maps it, then the VariableInspector prompt textarea
    shows 'foo'.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R3
  statement: fromReactFlow() emits ports as Record<string,Record<string,unknown>>
    (never an array, never []); newly dragged nodes receive correct default ports
    matching each component's Handle ids.
  acceptance_criteria:
  - 'Given a new AgentNode dropped onto the canvas (no original in harness), when
    fromReactFlow() processes it, then node.ports = { in: {}, out: {} }.'
  - 'Given a new DecisionNode, when fromReactFlow() processes it, then node.ports
    = { in: {}, yes: {}, no: {} }.'
  - 'Given a new TriggerNode, when fromReactFlow() processes it, then node.ports =
    { out: {} }.'
  - 'Given a new WaitNode, when fromReactFlow() processes it, then node.ports = {
    in: {}, out: {} }.'
  - 'Given a new AggregatorNode with two inputs, when fromReactFlow() processes it,
    then node.ports = { ''in-0'': {}, ''in-1'': {}, out: {} }.'
  - A freshly dragged node of any type, when saved via PUT /api/spaces/{id}/harnesses/{name},
    receives HTTP 200 (not 422).
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: 'HarnessEdge.condition (backend) round-trips through the editor: toReactFlow()
    maps condition to the RF edge''s data.condition, fromReactFlow() maps it back;
    decision-out edges in VariableInspector expose an editable condition field defaulting
    to yes/no.'
  acceptance_criteria:
  - 'Given a backend edge with condition: ''yes'', when toReactFlow() maps it, then
    the RF edge has data.condition = ''yes'' (or is accessible for display).'
  - Given an RF edge with data.condition = 'no', when fromReactFlow() maps it, then
    HarnessEdge.condition = 'no'.
  - Given a selected edge from a DecisionNode source, the VariableInspector shows
    an editable condition input populated with the current condition value.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R5
  statement: 'VariableInspector.tsx renders node-type-specific editable fields for
    Decision (no data fields, condition is on edge), Wait (mode selector + max_wait_seconds/duration_seconds),
    Aggregator (mode selector), and Trigger (kind selector + per-kind fields: expression/timezone
    for cron; webhook_path/auth_token for webhook; watch_pattern/debounce_seconds
    for file-change; watched_state for task-state-change); changes call onNodeChange
    with the correct data keys.'
  acceptance_criteria:
  - Given a WaitNode is selected, VariableInspector renders a mode dropdown (human/timed);
    selecting 'human' shows a max_wait_seconds input; selecting 'timed' shows a duration_seconds
    input.
  - Given an AggregatorNode is selected, VariableInspector renders a mode dropdown
    (all/any).
  - Given a TriggerNode is selected, VariableInspector renders a kind dropdown (cron/webhook/file-change/task-state-change)
    plus per-kind fields matching model.py documentation.
  - 'For each node-type field changed in the inspector, onNodeChange is called with
    { <field>: <value> } mapping to the correct node.data key.'
  verifying_phase: review
  confidence: 0.88
- requirement_id: R6
  statement: HarnessEditor.tsx wires onVariableChange to mutate harness.variables
    in React state; VariableInspector shows Add variable and Remove variable controls;
    a saved harness contains all variables the user added/edited/removed.
  acceptance_criteria:
  - The onVariableChange prop passed to VariableInspector is connected to a handler
    in HarnessEditor that updates a local variables state (not a no-op).
  - VariableInspector shows an 'Add variable' button that appends a new key/value
    row.
  - Each variable row has a 'Remove' control that deletes the row.
  - After adding a variable and saving, the saved Harness.variables contains the new
    key.
  - After removing a variable and saving, the saved Harness.variables does not contain
    the removed key.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R7
  statement: When useSaveHarness returns an error (HTTP 422 or other), HarnessEditor
    displays the validation errors to the user — either as a toast notification or
    an inline error message — instead of silently failing.
  acceptance_criteria:
  - Given saveMutation.isError is true with a 422 response body, the editor renders
    a visible error message containing the backend error detail (not just 'Save failed').
  - The error message is data-testid='save-error' and is accessible in the DOM while
    isError is true.
  - When the user fixes the invalid fields and saves again, the error message is cleared
    on the next successful save.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R8
  statement: Vitest coverage is added or extended for harnessMapping round-trip (toReactFlow
    + fromReactFlow with real node.data), VariableInspector field wiring (prompt_template,
    node-type-specific fields, variable add/remove), and new-node default port generation.
  acceptance_criteria:
  - A vitest spec for harnessMapping.ts covers toReactFlow → fromReactFlow round-trip
    for Agent, Decision, Wait, Aggregator, and Trigger node types with real data objects.
  - A vitest spec for VariableInspector.tsx covers prompt_template persistence (R2),
    node-type-specific field rendering (R5), and variable add/remove (R6).
  - cd frontend && npm test passes with all new specs.
  - cd frontend && npm run build exits 0.
  verifying_phase: test
  confidence: 0.92
metrics:
  tool_calls: 7
  files_read: 5
  memory_hits: 2
---

## Summary

The harness visual editor frontend diverges from the backend data model in seven structural areas — data/config naming mismatch, wrong prompt field key, ports stored as arrays instead of dicts, edges missing the condition field, no per-node-type editors, no variable add/remove UI, and no error feedback. All gaps are frontend-only and solvable within the declared scope files. This analysis decomposes the seven acceptance criteria into eight testable requirements (AC-5 stays as one requirement; AC-7 is validated separately from AC-1; a test coverage requirement is added as R8 to ensure correctness is verifiable).

## Scope

### In scope
- Fix HarnessNode TypeScript interface to replace `config: Record<string,unknown>` with `data: Record<string,unknown>` and ports with `Record<string,Record<string,unknown>>`
- Fix `toReactFlow()` to pass `node.data` correctly into RF node data and `fromReactFlow()` to map back to `node.data` (not a config key)
- Rename the prompt field from `config.prompt` to `data.prompt_template` in VariableInspector
- Generate correct default ports dict for each node type when a new node is dropped
- Map `HarnessEdge.condition` to/from RF edge; add condition editing UI for decision-out edges
- Add VariableInspector sections for Wait, Aggregator, and Trigger node types
- Wire `onVariableChange` in HarnessEditor from a no-op to a real state mutation
- Add Add/Remove variable row controls in VariableInspector
- Surface 422 backend errors in the editor (inline text showing the detail message)
- Add vitest specs covering the above round-trips and UI wiring

### Out of scope
- Backend model changes (model.py is immutable per the feature request)
- Backend executor changes
- HarnessRunsPage, HarnessListPage, or other pages not in scope
- Creating a discriminated union per node type in TypeScript (nice-to-have; deferred)
- Modal-based variable editing
- Aggregator N-input dynamic Handle rendering (backend-side port count tracking; deferred)

### Deferred
- TypeScript discriminated union types per node type (e.g., AgentNodeData vs WaitNodeData) — would improve type safety but is not required for correctness
- Modal-based 422 error display with detailed field-level annotations
- Aggregator dynamic N-input expansion from the editor UI

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Node data round-trip: replace config with data in types.ts and fix harnessMapping.ts |
| R2 | prompt_template: VariableInspector reads/writes data.prompt_template not config.prompt |
| R3 | ports as dict + defaults for each node type in fromReactFlow() |
| R4 | Edge condition round-trip + editable condition UI for decision-out edges |
| R5 | Editable config in VariableInspector for Wait, Aggregator, and Trigger node types |
| R6 | Variables add/edit/remove: wire onVariableChange + Add/Remove controls |
| R7 | Save feedback: surface backend 422 errors in the editor UI |
| R8 | Vitest coverage for harnessMapping round-trip, VariableInspector wiring, and new-node defaults |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — toReactFlow spreads node.data directly; fromReactFlow writes back to node.data; HarnessNode.config removed from types.ts
- R2 — VariableInspector prompt textarea maps to data.prompt_template in both read and write paths
- R3 — fromReactFlow generates ports: { in:{}, out:{} } for Agent/Wait, { out:{} } for Trigger, { in:{}, yes:{}, no:{} } for Decision, { in-0:{}, in-1:{}, out:{} } for Aggregator; existing nodes preserve their ports
- R4 — toReactFlow maps edge.condition to RF edge data.condition; fromReactFlow maps it back; VariableInspector shows editable condition for selected decision-out edges
- R5 — Wait inspector: mode dropdown + conditional duration/max_wait fields; Aggregator: mode dropdown; Trigger: kind dropdown + per-kind fields per model.py conventions
- R6 — onVariableChange wired to real state mutation; Add/Remove controls present; save persists changes
- R7 — 422 error detail rendered in data-testid="save-error" span; cleared on next successful save
- R8 — vitest specs for round-trip (5 node types) + VariableInspector wiring + npm test + npm build pass

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | harnessMapping round-trip preserves all data keys; types.ts uses data not config |
| R2 | test | VariableInspector prompt field persists to data.prompt_template |
| R3 | test | fromReactFlow emits ports as dict with correct default keys per node type |
| R4 | test | HarnessEdge.condition round-trips; decision-out edges have editable condition |
| R5 | review | VariableInspector renders correct fields for Wait/Aggregator/Trigger node types |
| R6 | test | onVariableChange wired; Add/Remove controls work; save persists variables |
| R7 | test | 422 errors surface in the editor UI at data-testid="save-error" |
| R8 | test | vitest specs cover round-trip and UI wiring; npm test + npm build pass |

## Assumptions

- `has_ui: true` rationale: all 7 acceptance criteria involve user interaction in the harness visual editor canvas; multiple React components require new/changed form fields, dropdowns, and buttons.
- The backend model is frozen at `backend/app/harnesses/model.py` and must not be changed. All divergence is a frontend bug, not a backend design decision.
- React Flow v12 (@xyflow/react) is the canvas framework; Handle id semantics (source/target with explicit id strings) are correct as implemented.
- The scout report confirmed that node component Handle ids are already correct (AgentNode: top target/bottom source; DecisionNode: top target/bottom-yes source/bottom-no source; TriggerNode: bottom source; WaitNode: top target/bottom source; AggregatorNode: in-N targets/bottom source); port default generation must match these ids.
- AggregatorNode default port count is 2 (in-0, in-1) — matching the current static render. Dynamic expansion is deferred.
- The onVariableChange no-op at line 197 of HarnessEditor.tsx (`onVariableChange={() => {}}`) is the root cause of R6 failure; wiring it to a real handler plus React state is the minimal fix.
- saveMutation.isError already gates the existing inline "Save failed — check the graph for errors." message (HarnessEditor.tsx line 133-137); R7 requires surfacing the actual 422 detail, not just adding the existing generic message.
- Test files should be created in the same directory as the source (e.g., `harnessMapping.test.ts`, `VariableInspector.test.tsx`) consistent with existing vitest patterns in the frontend workspace.

## Open questions

1. **Edge selection UI**: React Flow edges are selectable, but the current canvas does not pass a selected-edge callback to VariableInspector. The design agent must decide whether to add an `onEdgeClick` handler and pass the selected edge to VariableInspector, or handle condition editing via a separate panel/popover.
2. **Aggregator default port count**: Defaulting to 2 input ports (in-0, in-1) is assumed for freshly dropped Aggregator nodes. If the design agent wants dynamic port addition, that is out of scope here but the default must be at least 1 to avoid a 422.
3. **Types.ts HarnessNode ports type**: Should `ports` become `Record<string, Record<string, unknown>>` or a specific typed dict? The backend model has `dict[str, dict]` which is effectively `Record<string, unknown>`. Using `Record<string, Record<string, unknown>>` is preferred for type-level clarity.

## Next consumer brief

The **design agent** should:
1. Read `traceability[]` in this report for all 8 requirements; each has been scoped to named files in the declared scope.
2. `has_ui: true` — plan iterations that span both harnessMapping.ts (data layer) and VariableInspector.tsx + HarnessEditor.tsx (UI layer). The data layer must land first (R1/R2/R3) before the UI work (R4/R5/R6/R7) to avoid TypeScript type errors cascading across files.
3. R1 and R3 are coupled: renaming `config` to `data` in types.ts will break every file that imports `HarnessNode.config`; the design should plan a single atomic types.ts + harnessMapping.ts change that updates all consuming sites together.
4. R4 requires an edge-selection mechanism in HarnessEditor (currently absent). The design agent must decide between: (a) `onEdgeClick` → VariableInspector for the selected edge, or (b) inline edge label editing directly on the canvas. Option (a) is preferred as it reuses the existing inspector pattern.
5. R5 (per-node-type editors) is the largest single change — five node types with distinct field sets. The design agent should plan this as its own iteration, clearly specifying which fields map to which `node.data` keys per model.py.
6. R8 (tests) should be planned as the final iteration after all production code changes, ensuring the test specs cover the corrected implementations.
7. Risk area: TypeScript strict mode is enabled (`tsconfig.json`). Changing `HarnessNode.config` to `HarnessNode.data` will surface every access site as a type error until corrected. The implementation agent must update all consumers in the same iteration.
