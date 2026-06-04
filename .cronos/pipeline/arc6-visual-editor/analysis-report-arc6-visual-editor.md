---
cc_version: '1.0'
agent: pipeline-analyst
slug: arc6-visual-editor
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:project_arc6_board_setup
- memory:project_arc6_61_review_loop
- .cronos/pipeline/arc6-visual-editor/scout-report-arc6-visual-editor.md
- backend/app/pipeline/CONTRACT.md
- backend/app/pipeline/schemas/analysis.schema.yaml
- backend/app/pipeline/verify.py
outputs_produced:
- .cronos/pipeline/arc6-visual-editor/analysis-report-arc6-visual-editor.md
blockers: []
next_consumer: design
request: "Build the editor. Add the `reactflow` npm dep (keep it isolated from the\
  \ existing\n`@dagrejs/dagre` SVG graph in GoalDependencyGraph.tsx). Use `frontend-design`\
  \ skill for a\nCronos paper/ink palette: quiet canvas, ink-line edges (no glow/gradients),\
  \ nodes = the\n**Card** style, smaller, with sockets.\n\n- New `frontend/src/pages/HarnessEditor.tsx`\
  \ + `frontend/src/components/harness/` (node\n  components for all 5 types, typed\
  \ sockets/edges, palette, variable-binding inspector).\n- Save/load round-trips\
  \ to YAML via the 6.1 CRUD API; TanStack keys\n  `[\"harnesses\", spaceId]` / `[\"\
  harness\", spaceId, name]`.\n- Extend types.ts with `Harness`/`HarnessNode`/`HarnessEdge`.\n\
  - **Add a route + Sidebar nav entry** (router.tsx / Sidebar.tsx -- currently absent)\
  \ so the\n  editor is reachable.\n\nAcceptance: author a 3-node harness on the canvas,\
  \ wire edges, set an Agent node's\n`agent_ref` + prompt, save, reload -> persists\
  \ and re-renders; an invalid graph surfaces\nthe backend 422."
has_ui: true
coverage_summary:
  searched:
  - backend/app/harnesses/ (model, validator, store, CRUD API via scout report)
  - backend/app/api/harnesses.py (endpoints, 422 paths via scout report)
  - frontend/src/router.tsx (route registration pattern via scout report)
  - frontend/src/types.ts (existing types, no harness types yet via scout report)
  - frontend/src/api.ts (harness run endpoints only via scout report)
  - frontend/src/hooks/useHarnessRuns.ts (TanStack Query pattern via scout report)
  - frontend/src/components/Card.tsx (Cronos styling tokens via scout report)
  - frontend/package.json (existing deps, @dagrejs/dagre isolation via scout report)
  - backend/app/pipeline/schemas/analysis.schema.yaml
  - backend/app/pipeline/CONTRACT.md
  - backend/app/pipeline/verify.py
  excluded:
  - 'backend/app/harnesses/executor.py: executor/run-lifecycle out of scope for editor'
  - 'frontend/src/**/__tests__/: test files not needed for requirement derivation'
  - 'backend/tests/: backend test coverage not needed for frontend requirements'
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: The npm package `reactflow` is added to frontend/package.json, isolated
    from `@dagrejs/dagre` which remains the sole graph-layout import in GoalDependencyGraph.tsx.
  acceptance_criteria:
  - Given package.json after the change, `reactflow` appears in dependencies.
  - Given GoalDependencyGraph.tsx, the only graph-layout import remains `@dagrejs/dagre`;
    no `reactflow` import is present in that file.
  - Given `npm run build`, the build succeeds with both libraries present.
  verifying_phase: test
  confidence: 0.98
- requirement_id: R2
  statement: 'frontend/src/types.ts is extended with TypeScript interfaces: `NodeType`
    (5-member union), `Position`, `NodePort`, `HarnessNode`, `NodeRef`, `HarnessEdge`,
    and `Harness`.'
  acceptance_criteria:
  - 'Given types.ts, `NodeType` covers exactly: agent | trigger | decision | wait
    | aggregator.'
  - Given types.ts, `HarnessNode` has fields id (string), type (NodeType), position
    (Position), ports (Record<string, NodePort>), data (Record<string, unknown>),
    label (string).
  - Given types.ts, `HarnessEdge` has fields id (string), source (NodeRef), target
    (NodeRef), condition (string | null).
  - Given types.ts, `Harness` has fields name, description, nodes (HarnessNode[]),
    edges (HarnessEdge[]), variables (Record<string, unknown>), version, created_at,
    updated_at.
  - Given TypeScript strict compilation, no type errors are introduced by the new
    types.
  verifying_phase: test
  confidence: 0.97
- requirement_id: R3
  statement: 'frontend/src/api.ts gains five CRUD methods for harnesses: listHarnesses,
    getHarness, createHarness, updateHarness, deleteHarness -- all typed against the
    Harness types from R2.'
  acceptance_criteria:
  - Given api.ts, `api.listHarnesses(spaceId)` returns `Promise<Harness[]>` via GET
    `/api/spaces/{spaceId}/harnesses`.
  - Given api.ts, `api.getHarness(spaceId, name)` returns `Promise<Harness>` via GET
    with name URL-encoded.
  - Given api.ts, `api.createHarness(spaceId, body)` returns `Promise<Harness>` via
    POST.
  - Given api.ts, `api.updateHarness(spaceId, name, body)` returns `Promise<Harness>`
    via PUT with name URL-encoded.
  - Given api.ts, `api.deleteHarness(spaceId, name)` returns `Promise<void>` via DELETE.
  verifying_phase: test
  confidence: 0.96
- requirement_id: R4
  statement: TanStack Query hooks `useHarnesses`, `useHarness`, and `useSaveHarness`
    are implemented with query keys `["harnesses", spaceId]` and `["harness", spaceId,
    name]` respectively.
  acceptance_criteria:
  - Given useHarnesses(spaceId), the hook uses queryKey ["harnesses", spaceId] and
    calls api.listHarnesses.
  - Given useHarness(spaceId, name), the hook uses queryKey ["harness", spaceId, name]
    and calls api.getHarness.
  - Given useSaveHarness(), the mutation calls api.updateHarness (PUT) and on success
    invalidates both ["harnesses", spaceId] and ["harness", spaceId, name].
  - Given TypeScript strict compilation, hook return types are consistent with the
    Harness interfaces.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R5
  statement: A route `spaces/:spaceId/harnesses/:name/edit` is registered in frontend/src/router.tsx,
    nested under the existing App layout outlet, pointing to the HarnessEditor page.
  acceptance_criteria:
  - Given router.tsx, a Route with path `spaces/:spaceId/harnesses/:name/edit` is
    present.
  - Given navigation to `/spaces/<id>/harnesses/<name>/edit`, the HarnessEditor page
    renders without a 404 or blank screen.
  - Given the existing `spaces/:spaceId/harnesses/:name/runs` route is unchanged.
  verifying_phase: test
  confidence: 0.97
- requirement_id: R6
  statement: A Harnesses nav entry is added to frontend/src/components/Sidebar.tsx,
    linking to the harness section for the current space.
  acceptance_criteria:
  - Given Sidebar.tsx, a nav link referencing `/spaces/${spaceId}/harnesses` or a
    harness edit path is present.
  - Given the rendered sidebar in a space context, the Harnesses link is visible and
    navigates to a harness-related route.
  - Given Sidebar.tsx, the existing nav entries (spaces, tools, memory, stats) remain
    present and unchanged.
  verifying_phase: test
  confidence: 0.93
- requirement_id: R7
  statement: The HarnessEditor page (`frontend/src/pages/HarnessEditor.tsx`) renders
    a React Flow canvas that loads an existing harness by `spaceId` and `name` from
    route params, displaying its nodes and edges, and supports interactive drag, connect,
    and delete operations.
  acceptance_criteria:
  - Given navigation to the editor route with a valid spaceId and harness name, the
    canvas renders existing nodes at their persisted positions.
  - Given the canvas, nodes can be dragged to new positions; position updates are
    reflected in local state.
  - Given the canvas, a connection can be drawn between two node sockets, creating
    a new HarnessEdge in local state.
  - Given the canvas, a node or edge can be selected and deleted from local state.
  - Given a harness with no nodes, the canvas renders an empty state prompting the
    user to add nodes from the palette.
  verifying_phase: manual
  confidence: 0.9
- requirement_id: R8
  statement: Five node-type components are implemented in `frontend/src/components/harness/`
    (AgentNode, TriggerNode, DecisionNode, WaitNode, AggregatorNode), each rendered
    as a Card-style panel with typed input/output React Flow socket Handles.
  acceptance_criteria:
  - Given the harness directory, component files exist for all 5 node types.
  - Given each node component, it renders with `rounded border border-hairline bg-surface-2`
    Card styling, a label, and visually distinct socket handles.
  - Given each node component, React Flow `Handle` elements are used for socket connection
    points.
  - Given each node type, a type-specific distinguishing header or icon differentiates
    nodes without using gradients or glow effects.
  verifying_phase: review
  confidence: 0.88
- requirement_id: R9
  statement: 'The editor visual style follows the Cronos paper/ink palette: quiet
    canvas (bg-surface-1), ink-line edges (no glow or gradients), and socket handles
    styled with Cronos border tokens.'
  acceptance_criteria:
  - Given the React Flow canvas, the background uses the `bg-surface-1` color token
    or its CSS variable equivalent.
  - Given rendered edges, they use a single solid stroke color from `text-ink` or
    `border-hairline` tokens with no drop-shadow, blur, or animated glow.
  - Given node socket handles, they render as small circles with `border border-hairline`
    styling.
  - Given the frontend-design skill is used for implementation, Cronos Tailwind tokens
    are referenced consistently throughout.
  verifying_phase: review
  confidence: 0.88
- requirement_id: R10
  statement: A node palette panel is present in the editor UI listing all 5 node types.
    Dragging a palette entry onto the canvas creates a new node of that type at the
    drop position with a generated unique ID.
  acceptance_criteria:
  - Given the editor layout, a palette panel is visible with entries for Agent, Trigger,
    Decision, Wait, and Aggregator.
  - Given a palette item is dragged onto the canvas, a new node of the corresponding
    type is added to local state with a unique ID and the drop position.
  - Given the new node is added, it appears on the canvas immediately without requiring
    a save/reload cycle.
  verifying_phase: manual
  confidence: 0.87
- requirement_id: R11
  statement: A variable-binding inspector panel is present in the editor, displaying
    and allowing edits to the selected node's `data` dict fields, with at minimum
    `agent_ref` and `prompt` editable for Agent nodes.
  acceptance_criteria:
  - Given an Agent node is selected on the canvas, the inspector shows editable fields
    for `agent_ref` and `prompt`.
  - Given a field is edited in the inspector, the corresponding key in the node's
    `data` dict is updated in local state.
  - Given no node is selected, the inspector shows an empty state or the harness-level
    `variables` dict.
  - Given a non-Agent node is selected, the inspector shows the node's generic `data`
    dict keys.
  verifying_phase: manual
  confidence: 0.85
- requirement_id: R12
  statement: The editor Save action pre-fetches the existing harness (GET), constructs
    an updated payload with current canvas state, calls PUT `/api/spaces/{spaceId}/harnesses/{name}`,
    and invalidates both TanStack cache keys on success.
  acceptance_criteria:
  - Given the Save button is clicked, the editor calls `api.getHarness(spaceId, name)`
    first, then `api.updateHarness(spaceId, name, payload)` to preserve `created_at`
    (arc6-6.1 fix).
  - Given PUT returns 200, the query keys `["harness", spaceId, name]` and `["harnesses",
    spaceId]` are both invalidated.
  - Given updated node positions on the canvas, the saved payload includes updated
    `position.x` and `position.y` for each node.
  - Given the current edge list, the saved payload includes all edges with source/target
    NodeRef objects.
  verifying_phase: test
  confidence: 0.93
- requirement_id: R13
  statement: After a successful save, reloading the editor route for the same harness
    re-fetches from the backend and re-renders the canvas with all nodes, edges, positions,
    and node data as persisted.
  acceptance_criteria:
  - Given a harness saved with 3 nodes and 2 edges, navigating away and back to the
    editor route renders those 3 nodes at their saved positions.
  - Given the reloaded canvas, edge connections between nodes match the persisted
    edge list.
  - Given an Agent node with `agent_ref` and `prompt` set, those values appear in
    the inspector after reload.
  verifying_phase: manual
  confidence: 0.92
- requirement_id: R14
  statement: When a Save attempt returns HTTP 422 from the backend, the editor surfaces
    the validation error message to the user inline; the canvas remains interactive.
  acceptance_criteria:
  - Given a save results in a 422 response, an error message derived from the response
    body is displayed (banner, toast, or inline alert).
  - Given the 422 error is displayed, the canvas remains interactive and the user
    can correct the graph and retry.
  - Given a cycle error (HarnessGraphError) or wait-node validation error (HarnessValidationError),
    the specific message text is shown, not a generic fallback.
  verifying_phase: manual
  confidence: 0.9
- requirement_id: R15
  statement: 'End-to-end acceptance scenario: a user adds three nodes (Agent, Trigger,
    Wait) via the palette, wires edges, sets the Agent node''s `agent_ref` and `prompt`,
    saves successfully, reloads the route and sees all data persisted, then introduces
    a cycle and confirms a 422 is surfaced.'
  acceptance_criteria:
  - Given an empty canvas, three nodes (Agent, Trigger, Wait) can be added via the
    palette.
  - Given the three nodes, edges can be drawn connecting them in a valid DAG.
  - Given the Agent node, `agent_ref` and `prompt` can be set via the inspector.
  - Given Save is clicked on a valid graph, the API returns 200 and the cache is invalidated.
  - Given the editor route is reloaded, all 3 nodes, their edges, and the agent_ref+prompt
    values are present.
  - Given an edge is added to create a cycle and Save is clicked, a 422 error message
    is displayed.
  verifying_phase: manual
  confidence: 0.88
metrics:
  tool_calls: 9
  files_read: 4
  memory_hits: 2
---

## Summary

This feature builds the Cronos harness visual editor: a React Flow canvas page enabling authoring, saving, and reloading execution harnesses via the existing arc6-6.1 CRUD API. The work is frontend-only (no backend changes required) across five implementation layers: TypeScript types, API client methods, TanStack Query hooks, routing/navigation wiring, and a React Flow canvas with 5 node-type components, a drag palette, and a variable-binding inspector. The Cronos paper/ink visual style (quiet canvas, ink-line edges, Card-style nodes) must be applied using the `frontend-design` skill, keeping `reactflow` isolated from the existing `@dagrejs/dagre` in GoalDependencyGraph.tsx. All 15 requirements have high confidence (>= 0.85) based on complete scout coverage of backend model, API endpoints, and frontend patterns.

## Scope

### In scope

- Add `reactflow` npm dependency to frontend/package.json
- Extend `frontend/src/types.ts` with `NodeType`, `Position`, `NodePort`, `HarnessNode`, `NodeRef`, `HarnessEdge`, `Harness`
- Add harness CRUD methods (`listHarnesses`, `getHarness`, `createHarness`, `updateHarness`, `deleteHarness`) to `frontend/src/api.ts`
- Add TanStack Query hooks: `useHarnesses`, `useHarness`, `useSaveHarness` in `frontend/src/hooks/useHarnesses.ts`
- Register route `spaces/:spaceId/harnesses/:name/edit` in `frontend/src/router.tsx`
- Add Harnesses nav entry to `frontend/src/components/Sidebar.tsx`
- Implement `frontend/src/pages/HarnessEditor.tsx` with React Flow canvas, save/load
- Implement 5 node-type components in `frontend/src/components/harness/` with typed socket Handles
- Implement palette panel (drag-to-canvas creation for all 5 node types)
- Implement variable-binding inspector (at minimum `agent_ref` + `prompt` for Agent nodes)
- Cronos paper/ink visual style (bg-surface-1 canvas, ink-line edges, border-hairline sockets, Card-style nodes)
- 422 error surfacing on save failure

### Out of scope

- Backend changes: the arc6-6.1 CRUD API is complete; no new endpoints or model changes required
- Harness list page or harness creation UI: editor loads a named harness from route params; upstream navigation is deferred
- Undo/redo history stack
- Multi-harness batch editing
- Optimistic locking / conflict detection: backend is last-writer-wins; no concurrency UI required
- Auto-save: explicit Save button only
- Port-level semantic validation on the frontend: structure is preserved opaquely; validation is backend-only

### Deferred

- Harness creation and delete flow from within the editor (follow-up story)
- Advanced inspector fields for Trigger, Decision, Wait, Aggregator node types beyond generic data dict
- Undo/redo history stack
- Real-time collaboration or concurrent-edit detection

## Requirements

| R#  | One-line summary |
|-----|-----------------|
| R1  | Add `reactflow` npm dep, isolated from `@dagrejs/dagre` |
| R2  | Extend types.ts with Harness/HarnessNode/HarnessEdge and supporting types |
| R3  | Add harness CRUD methods to api.ts typed against Harness types |
| R4  | Add TanStack Query hooks useHarnesses/useHarness/useSaveHarness with canonical query keys |
| R5  | Register harness editor route in router.tsx |
| R6  | Add Harnesses nav entry to Sidebar.tsx |
| R7  | HarnessEditor page renders React Flow canvas with load, drag, connect, delete |
| R8  | 5 node-type components in components/harness/ with Card style and typed socket Handles |
| R9  | Paper/ink visual style: quiet canvas, ink edges, no glow or gradients |
| R10 | Node palette panel -- drag-to-create for all 5 node types |
| R11 | Variable-binding inspector -- editable data fields, agent_ref+prompt for Agent nodes |
| R12 | Save action: pre-fetch GET, PUT, dual cache invalidation, preserving created_at |
| R13 | Reload round-trip: saved harness re-renders correctly from backend |
| R14 | 422 error surfacing: backend validation message shown inline on save failure |
| R15 | End-to-end acceptance scenario: 3-node harness, wire, set agent_ref+prompt, save, reload, cycle 422 |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form.

- R1 -- `reactflow` in package.json; `@dagrejs/dagre` import unchanged in GoalDependencyGraph.tsx; build passes
- R2 -- All 7 harness interfaces present in types.ts with correct field shapes; TypeScript strict compilation clean
- R3 -- Five api.ts methods map to the 5 CRUD endpoints with correct HTTP verbs and URL encoding
- R4 -- Three hooks with exact query keys `["harnesses", spaceId]` / `["harness", spaceId, name]`; mutation invalidates both
- R5 -- Route `spaces/:spaceId/harnesses/:name/edit` registered; existing runs route unchanged
- R6 -- Sidebar nav link for Harnesses visible and navigates correctly; existing entries unchanged
- R7 -- Canvas loads existing nodes at persisted positions; drag, connect, delete work in local state
- R8 -- One component file per node type; Card styling; React Flow Handle sockets; type-distinct headers without gradients
- R9 -- `bg-surface-1` canvas; solid ink-color edges; `border-hairline` socket circles; no blur/glow/gradient
- R10 -- Palette shows all 5 types; drag to canvas creates node with unique ID at drop position; visible immediately
- R11 -- Agent node inspector shows `agent_ref` and `prompt` fields; edits update local state; fallback for other types
- R12 -- Save pre-fetches existing harness (GET), then PUT; invalidates both cache keys on 200
- R13 -- After save + route reload, all nodes, edges, positions, and agent_ref+prompt are present
- R14 -- 422 response body message displayed in UI; canvas remains interactive after error
- R15 -- Full author, wire, set, save, reload, cycle-422 scenario passes manually

## Traceability

The full requirement to acceptance criteria to verifying_phase map is the YAML `traceability[]` array. This table is a human-readable orientation compass only.

| R#  | Verifying phase | Statement |
|-----|----------------|-----------|
| R1  | test | `reactflow` dep added, isolated from `@dagrejs/dagre` in GoalDependencyGraph.tsx |
| R2  | test | types.ts extended with 7 harness-related TypeScript interfaces |
| R3  | test | api.ts gains 5 typed CRUD methods for the harness endpoints |
| R4  | test | TanStack hooks useHarnesses/useHarness/useSaveHarness with canonical query keys |
| R5  | test | Route `spaces/:spaceId/harnesses/:name/edit` registered in router.tsx |
| R6  | test | Harnesses nav entry added to Sidebar.tsx |
| R7  | manual | HarnessEditor page renders canvas; supports drag, connect, delete in local state |
| R8  | review | 5 node-type components with Card style and typed React Flow socket Handles |
| R9  | review | Paper/ink visual style applied: quiet canvas, ink edges, no glow or gradients |
| R10 | manual | Palette panel with drag-to-canvas node creation for all 5 types |
| R11 | manual | Variable-binding inspector with agent_ref+prompt for Agent nodes |
| R12 | test | Save: pre-fetch GET + PUT + dual cache invalidation on 200 |
| R13 | manual | Reload round-trip: harness persists and re-renders with all data intact |
| R14 | manual | 422 error message surfaced inline in editor UI |
| R15 | manual | End-to-end acceptance scenario passes |

## Assumptions

- `has_ui: true` rationale: the entire feature is a frontend visual editor page; React Flow canvas, node components, palette, inspector, sidebar nav, and route are all UI artifacts.
- The arc6-6.1 CRUD API is complete and stable (backend/app/api/harnesses.py, 5 endpoints). No backend changes are required for this feature.
- `reactflow` v12+ will be used. The scout found zero existing reactflow imports; no legacy v11 constraints apply.
- `@dagrejs/dagre` is confined to GoalDependencyGraph.tsx; isolation is a naming/import discipline, not a bundling constraint.
- Node canvas positions round-trip through the backend: `HarnessNode.position` (x, y) is already part of the Pydantic model and YAML serialization. The editor reads and writes position directly.
- Port structure is preserved opaquely: the frontend stores the `ports` dict as-is; socket creation/deletion semantics are deferred to a follow-up.
- The pre-fetch pattern on PUT is required by the arc6-6.1 `created_at` preservation fix (commit c501a98). This is a known constraint, not a design choice.
- The `frontend-design` skill will be invoked by the implementor for Cronos color token application.

## Open questions

- None. The scout report provided complete data model, API endpoint, routing pattern, and styling token coverage. All 15 requirements have clear traceability to the request text and confirmed codebase state.

## Next consumer brief

Read from the YAML `traceability[]` array first: requirements R1-R6 are mechanical wiring (types/api/hooks/route/sidebar/dep) and verifiable by unit and integration tests. R7-R15 require React Flow canvas integration and manual verification.

Key design decision points for the architect:

1. **React Flow node type registration**: Each of the 5 node types must be registered in a `nodeTypes` map passed to `<ReactFlow>`. Specify how custom node components receive and mutate their `data` dict (likely via `useReactFlow` + `setNodes`).
2. **Canvas to inspector state management**: The inspector (R11) needs the selected node's `data`. Choose: lifted state in HarnessEditor, a context, or React Flow `onSelectionChange`.
3. **Palette drag-to-canvas**: React Flow v12 supports `onDrop` + `onDragOver` on the canvas wrapper for external drag-in. Specify drag-data format and unique-ID generation.
4. **Save payload construction**: The save action (R12) maps React Flow's internal node/edge state back to `HarnessNode[]` / `HarnessEdge[]`. React Flow carries `position` natively; specify how `NodeRef` (node_id, port_id) is constructed from React Flow edge `source` / `sourceHandle` fields.
5. **Pre-fetch on PUT constraint**: GET-before-PUT on every save preserves `created_at` per arc6-6.1. Not optional.
6. **422 display placement**: Choose one consistent pattern (banner below toolbar, toast, or inline alert) matching existing Cronos UI error patterns.
