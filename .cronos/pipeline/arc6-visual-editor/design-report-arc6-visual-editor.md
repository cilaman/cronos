---
cc_version: '1.0'
agent: pipeline-architect
slug: arc6-visual-editor
phase: design
status: done
confidence: 0.88
inputs_used:
- memory:project_arc6_board_setup
- memory:project_arc6_61_review_loop
- .cronos/pipeline/arc6-visual-editor/analysis-report-arc6-visual-editor.md
- .cronos/pipeline/arc6-visual-editor/scout-report-arc6-visual-editor.md
outputs_produced:
- .cronos/pipeline/arc6-visual-editor/design-report-arc6-visual-editor.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - .cronos/pipeline/arc6-visual-editor/
  - frontend/src/ (via scout findings)
  - frontend/package.json (via scout findings)
  excluded:
  - 'backend/: feature is frontend-only; arc6-6.1 CRUD API already complete'
  - 'backend/app/harnesses/: no model/validator changes required'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: frontend
  scope_files:
  - frontend/package.json
  - frontend/package-lock.json
  validation_command: cd frontend && npm install && npm run build
  max_diff_lines: 200
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/src/types.ts
  - frontend/src/__tests__/types.harness.test.ts
  validation_command: cd frontend && npm test -- src/__tests__/types.harness.test.ts
    && npx tsc --noEmit
  max_diff_lines: 250
  depends_on: []
- id: I3
  type: frontend
  scope_files:
  - frontend/src/api.ts
  - frontend/src/__tests__/api.harness.test.ts
  validation_command: cd frontend && npm test -- src/__tests__/api.harness.test.ts
  max_diff_lines: 300
  depends_on:
  - I2
- id: I4
  type: frontend
  scope_files:
  - frontend/src/hooks/useHarnesses.ts
  - frontend/src/hooks/__tests__/useHarnesses.test.tsx
  validation_command: cd frontend && npm test -- src/hooks/__tests__/useHarnesses.test.tsx
  max_diff_lines: 300
  depends_on:
  - I3
- id: I5
  type: frontend
  scope_files:
  - frontend/src/router.tsx
  - frontend/src/components/Sidebar.tsx
  - frontend/src/__tests__/router.harness-editor.test.tsx
  - frontend/src/components/__tests__/Sidebar.harness.test.tsx
  validation_command: cd frontend && npm test -- src/__tests__/router.harness-editor.test.tsx
    src/components/__tests__/Sidebar.harness.test.tsx
  max_diff_lines: 250
  depends_on:
  - I2
- id: I6
  type: frontend
  scope_files:
  - frontend/src/components/harness/AgentNode.tsx
  - frontend/src/components/harness/TriggerNode.tsx
  - frontend/src/components/harness/DecisionNode.tsx
  - frontend/src/components/harness/WaitNode.tsx
  - frontend/src/components/harness/AggregatorNode.tsx
  - frontend/src/components/harness/nodeTypes.ts
  - frontend/src/components/harness/__tests__/nodes.test.tsx
  validation_command: cd frontend && npm test -- src/components/harness/__tests__/nodes.test.tsx
  max_diff_lines: 500
  depends_on:
  - I1
  - I2
- id: I7
  type: frontend
  scope_files:
  - frontend/src/components/harness/NodePalette.tsx
  - frontend/src/components/harness/VariableInspector.tsx
  - frontend/src/components/harness/__tests__/NodePalette.test.tsx
  - frontend/src/components/harness/__tests__/VariableInspector.test.tsx
  validation_command: cd frontend && npm test -- src/components/harness/__tests__/NodePalette.test.tsx
    src/components/harness/__tests__/VariableInspector.test.tsx
  max_diff_lines: 450
  depends_on:
  - I2
  - I6
- id: I8
  type: frontend
  scope_files:
  - frontend/src/pages/HarnessEditor.tsx
  - frontend/src/components/harness/harnessMapping.ts
  - frontend/src/components/harness/__tests__/harnessMapping.test.ts
  - frontend/src/pages/__tests__/HarnessEditor.test.tsx
  validation_command: cd frontend && npm test -- src/components/harness/__tests__/harnessMapping.test.ts
    src/pages/__tests__/HarnessEditor.test.tsx
  max_diff_lines: 600
  depends_on:
  - I1
  - I4
  - I5
  - I6
  - I7
- id: I9
  type: frontend
  scope_files:
  - frontend/src/pages/__tests__/HarnessEditor.acceptance.test.tsx
  validation_command: cd frontend && npm test -- src/pages/__tests__/HarnessEditor.acceptance.test.tsx
    && npm run build
  max_diff_lines: 400
  depends_on:
  - I8
risks:
- description: React Flow v12 ships its own CSS (`reactflow/dist/style.css`) and default
    theming; importing it naively will override Cronos paper/ink tokens with library
    defaults (gradients, blue selection halos, glow), violating R9.
  severity: high
  mitigation: I1 imports reactflow CSS in HarnessEditor.tsx only (not global app.css).
    I6/I7/I8 apply Cronos overrides via a co-located harness/reactflow-overrides.css
    scoped under a .harness-canvas wrapper class that zeroes out box-shadow, replaces
    edge stroke with text-ink, and recolors handles to border-hairline. I9 acceptance
    test asserts canvas wrapper has the override class and that computed edge stroke
    is the ink token.
- description: PUT save without GET pre-fetch silently overwrites `created_at` (regression
    of arc6-6.1 fix c501a98); silent because PUT still returns 200 and the response
    carries the corrupted timestamp.
  severity: high
  mitigation: 'I4 useSaveHarness mutation is implemented as a two-call sequence: api.getHarness(spaceId,name)
    -> merge canvas state into the returned object preserving created_at -> api.updateHarness(...).
    I4 test asserts api.getHarness is called before api.updateHarness with matching
    arguments and that created_at from the GET response appears verbatim in the PUT
    payload.'
- description: React Flow internal Node/Edge shapes (with sourceHandle/targetHandle
    as flat strings) do not match the backend HarnessNode/HarnessEdge shape (nested
    NodeRef with port_id). A naive save will send the wrong payload shape and trigger
    422 on every save.
  severity: high
  mitigation: I8 isolates the round-trip into a dedicated pure module frontend/src/components/harness/harnessMapping.ts
    exposing toReactFlow(harness)/fromReactFlow(rfNodes, rfEdges, harness) functions;
    harnessMapping.test.ts asserts symmetric round-trip on a 3-node fixture matching
    the R15 scenario.
- description: Drag-from-palette uses HTML5 dragstart/drop events; React Flow's own
    internal drag system can intercept drop events on the canvas if the wrapper is
    not configured with onDragOver preventDefault, causing palette drops to silently
    no-op (R10 acceptance regression).
  severity: medium
  mitigation: I7 NodePalette uses dataTransfer.setData('application/reactflow', nodeType)
    per React Flow v12 documented pattern. I8 HarnessEditor wraps <ReactFlow> in a
    div with onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move';
    }} and onDrop calling screenToFlowPosition. NodePalette test simulates drag with
    vi.spyOn on dataTransfer; HarnessEditor.test asserts onDrop creates a node with
    matching type at projected position.
- description: useHarness query key `["harness", spaceId, name]` is shaped differently
    from existing useHarnessRuns key `["harness-runs", spaceId, name]`; if a developer
    reuses the runs invalidation pattern verbatim the canvas will not refresh after
    save and R13 reload acceptance will pass in isolation but fail when the editor
    is opened twice in one session.
  severity: medium
  mitigation: 'I4 useSaveHarness onSuccess invalidates both keys explicitly: queryClient.invalidateQueries({queryKey:
    [''harnesses'', spaceId]}) and queryClient.invalidateQueries({queryKey: [''harness'',
    spaceId, name]}). useHarnesses.test.tsx asserts both invalidations fire with exact
    key arrays via a spy on QueryClient.'
- description: Sidebar nav entry for Harnesses needs a spaceId but the Sidebar renders
    globally; if implementor reads spaceId from a hook that returns undefined outside
    a space route, the link will render a broken URL like `/spaces/undefined/harnesses`.
  severity: low
  mitigation: 'I5 Sidebar harness link is rendered conditionally: only when useParams()
    yields a defined spaceId. Sidebar.harness.test.tsx asserts the link is absent
    on a non-space route and present on a space route. Out-of-space behavior matches
    existing space-scoped nav entries (tools, memory).'
- description: 'Bundler bloat: reactflow v12 + its react-flow-renderer transitive
    deps add ~250KB to the frontend bundle; CI build-size budgets (if any) may regress
    and prod first-load on the /spaces route could become noticeably slower.'
  severity: low
  mitigation: I8 lazy-loads HarnessEditor.tsx via React.lazy + Suspense in router.tsx
    so reactflow is only fetched when the user navigates to the editor route. I9 npm
    run build asserts the build succeeds; bundle-size deltas are tracked in the implementor
    report metrics, not gated.
metrics:
  tool_calls: 6
  files_read: 2
  memory_hits: 2
  iterations_planned: 9
---

## Summary

This design decomposes the React Flow harness visual editor into 9 frontend iterations on a wide DAG: three independent foundation iterations (npm dep, types, route+sidebar) feed two parallel component layers (5 node-type components in I6; palette+inspector in I7), which converge on the HarnessEditor page (I8) and a final end-to-end acceptance gate (I9). The crucial non-obvious work is isolated into a single mapping module (harnessMapping.ts) that translates between React Flow's flat node/edge shape and the backend's nested NodeRef shape, so the save/load round-trip can be unit-tested without mounting React Flow. The arc6-6.1 PUT-must-pre-fetch constraint is encoded in the useSaveHarness hook (I4) rather than scattered through the editor page, eliminating a known regression class. React Flow's default CSS is scoped to a `.harness-canvas` wrapper to keep Cronos paper/ink tokens authoritative.

## Components

### Data

- `frontend/src/types.ts` extensions — 7 new interfaces (`NodeType`, `Position`, `NodePort`, `HarnessNode`, `NodeRef`, `HarnessEdge`, `Harness`) mirroring the Pydantic v2 model from scout section 6 verbatim, for round-trip type safety.

### Backend

- No backend changes. The arc6-6.1 CRUD API (`/api/spaces/{space_id}/harnesses`) is complete; PUT preserves `created_at` server-side when the request payload includes a matching value (consumer responsibility).

### Frontend

- `frontend/src/api.ts` — five new methods `listHarnesses`, `getHarness`, `createHarness`, `updateHarness`, `deleteHarness` typed against the Harness interfaces; name URL-encoded for GET/PUT/DELETE.
- `frontend/src/hooks/useHarnesses.ts` — three TanStack Query hooks (`useHarnesses`, `useHarness`, `useSaveHarness`) with canonical query keys `["harnesses", spaceId]` and `["harness", spaceId, name]`; `useSaveHarness` enforces GET-before-PUT and dual cache invalidation.
- `frontend/src/router.tsx` — new lazy-loaded route `spaces/:spaceId/harnesses/:name/edit` pointing at `HarnessEditor`, nested under the existing `<App />` outlet alongside the unchanged `/runs` route.
- `frontend/src/components/Sidebar.tsx` — Harnesses nav entry rendered conditionally when `useParams().spaceId` is defined; existing entries (spaces, tools, memory, stats) untouched.
- `frontend/src/components/harness/AgentNode.tsx` + `TriggerNode.tsx` + `DecisionNode.tsx` + `WaitNode.tsx` + `AggregatorNode.tsx` — one React Flow custom node component per `NodeType`, each rendered as a small Card-style panel (`rounded border border-hairline bg-surface-2`) with type-distinct ink-only header and React Flow `<Handle>` socket points.
- `frontend/src/components/harness/nodeTypes.ts` — the `nodeTypes` map passed to `<ReactFlow>` registering all 5 custom node components by `NodeType` key.
- `frontend/src/components/harness/NodePalette.tsx` — left-side panel listing 5 draggable palette entries; uses `dataTransfer.setData('application/reactflow', nodeType)` per React Flow v12 convention.
- `frontend/src/components/harness/VariableInspector.tsx` — right-side panel; renders editable `agent_ref` + `prompt` fields for `agent` nodes, generic key/value list for other node types, and the harness-level `variables` dict when no node is selected.
- `frontend/src/components/harness/harnessMapping.ts` — pure round-trip module: `toReactFlow(harness)` produces React Flow nodes/edges with flattened handle ids; `fromReactFlow(rfNodes, rfEdges, original)` reconstructs the nested `Harness` payload preserving `created_at`, `version`, `variables`, and per-node `ports` from the original.
- `frontend/src/components/harness/reactflow-overrides.css` — Cronos paper/ink overrides scoped to `.harness-canvas` (no glow, no gradients, ink-token edge stroke, border-hairline handles).
- `frontend/src/pages/HarnessEditor.tsx` — top-level page; reads `spaceId`+`name` from `useParams`, calls `useHarness`, mounts `<ReactFlow>` with `nodeTypes`, `NodePalette`, `VariableInspector`, Save button, and 422 error banner; orchestrates `useSaveHarness` on click.

## Implementation plan

| ID  | Type     | Depends on              | Scope files (abridged)                                                       | Validation                                                                                          |
|-----|----------|-------------------------|------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| I1  | frontend | -                       | frontend/package.json, frontend/package-lock.json                            | cd frontend && npm install && npm run build                                                         |
| I2  | frontend | -                       | frontend/src/types.ts, tests                                                 | cd frontend && npm test -- src/__tests__/types.harness.test.ts && npx tsc --noEmit                  |
| I3  | frontend | I2                      | frontend/src/api.ts, tests                                                   | cd frontend && npm test -- src/__tests__/api.harness.test.ts                                        |
| I4  | frontend | I3                      | frontend/src/hooks/useHarnesses.ts, tests                                    | cd frontend && npm test -- src/hooks/__tests__/useHarnesses.test.tsx                                |
| I5  | frontend | I2                      | frontend/src/router.tsx, frontend/src/components/Sidebar.tsx, tests          | cd frontend && npm test -- src/__tests__/router.harness-editor.test.tsx src/components/__tests__/Sidebar.harness.test.tsx |
| I6  | frontend | I1, I2                  | frontend/src/components/harness/{Agent,Trigger,Decision,Wait,Aggregator}Node.tsx, nodeTypes.ts | cd frontend && npm test -- src/components/harness/__tests__/nodes.test.tsx                          |
| I7  | frontend | I2, I6                  | frontend/src/components/harness/NodePalette.tsx, VariableInspector.tsx       | cd frontend && npm test -- src/components/harness/__tests__/NodePalette.test.tsx src/components/harness/__tests__/VariableInspector.test.tsx |
| I8  | frontend | I1, I4, I5, I6, I7      | frontend/src/pages/HarnessEditor.tsx, harnessMapping.ts                      | cd frontend && npm test -- src/components/harness/__tests__/harnessMapping.test.ts src/pages/__tests__/HarnessEditor.test.tsx |
| I9  | frontend | I8                      | frontend/src/pages/__tests__/HarnessEditor.acceptance.test.tsx               | cd frontend && npm test -- src/pages/__tests__/HarnessEditor.acceptance.test.tsx && npm run build   |

## Risks

| Risk                                                                       | Severity | Mitigation                                                                                                                              |
|----------------------------------------------------------------------------|----------|-----------------------------------------------------------------------------------------------------------------------------------------|
| React Flow default CSS overrides Cronos paper/ink tokens                   | high     | I1 imports reactflow CSS in HarnessEditor only; I6/I7/I8 scope overrides under .harness-canvas; I9 asserts ink-token edge stroke         |
| PUT save without GET pre-fetch silently corrupts `created_at`              | high     | I4 useSaveHarness performs GET-then-PUT; test asserts call order and created_at presence in PUT payload                                  |
| React Flow flat handle ids do not match backend nested NodeRef shape       | high     | I8 isolates round-trip in harnessMapping.ts; symmetric round-trip test on 3-node fixture                                                 |
| Palette drop intercepted by React Flow if onDragOver not preventDefault'd  | medium   | I7 uses documented `application/reactflow` dataTransfer key; I8 wrapper sets preventDefault; tests assert node created at drop position  |
| Wrong invalidation key shape (runs vs editor) silently stales the cache    | medium   | I4 invalidates both `["harnesses", spaceId]` and `["harness", spaceId, name]`; test asserts exact key arrays                             |
| Sidebar Harness link renders `/spaces/undefined/harnesses` outside a space | low      | I5 conditional render gated on `useParams().spaceId`; test covers both space and non-space routes                                        |
| Bundle bloat from reactflow on first-load                                  | low      | I8 lazy-loads HarnessEditor via React.lazy + Suspense in router.tsx; I9 build asserts success                                            |

## Assumptions

- React Flow v12+ is used (latest at design time); v11 patterns (`react-flow-renderer` package, `useStoreState`) are NOT applicable.
- `frontend-design` skill is invoked by the I6/I7/I8 implementor for Cronos token application; no design tokens are introduced or modified.
- Vitest + React Testing Library is the established frontend test stack (consistent with `useHarnessRuns` test patterns observed by scout); no new test infrastructure is added.
- TanStack Query v5 client is available globally via the existing app provider; tests use `QueryClientProvider` wrappers as established in `frontend/src/hooks/__tests__/`.
- `npx tsc --noEmit` is available via the existing `typescript` devDependency; no separate `tsconfig` adjustments are needed.
- Lazy loading via `React.lazy(() => import('./pages/HarnessEditor'))` in `router.tsx` is compatible with the existing `<Suspense>` boundary at the `<App />` outlet (implementor adds a local `<Suspense fallback>` if none exists).
- No backend changes are in scope (analysis Section ## Scope — only frontend artifacts touched); the arc6-6.1 CRUD API is the source of truth.

## Open questions

- None. The analysis report's `## Open questions` section is empty and the scout coverage of data model, API, routing, types, and styling is complete.

## Next consumer brief

Read the YAML first: `iterations[]` is the work plan, `risks[]` carries the load-bearing cross-iteration constraints. Three invariants are NOT derivable from any single iteration's `scope_files` and must be respected across I3/I4/I8:

1. The exact API path is `/api/spaces/{spaceId}/harnesses/{name}` with `name` URL-encoded via `encodeURIComponent` (R3 acceptance). Use this literal in `api.ts` and assert it in `api.harness.test.ts`.
2. TanStack query keys are `["harnesses", spaceId]` (list) and `["harness", spaceId, name]` (single) verbatim — do NOT use `"harness-runs"` (that is the existing `useHarnessRuns` key for a different domain).
3. `useSaveHarness` MUST call `api.getHarness` then `api.updateHarness` (GET-then-PUT) in that order on every save; this enforces the arc6-6.1 `created_at` preservation contract. Tests should assert call order, not just that both calls happened.

Per-iteration `validation_command` strings are what the test agent runs; do not change them. The Cronos paper/ink palette is enforced via the `frontend-design` skill — implementors of I6/I7/I8 must invoke it rather than hand-rolling color values.
