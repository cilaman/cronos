---
cc_version: "1.0"
agent: pipeline-scout
slug: arc6-visual-editor
phase: scout
status: done
confidence: 0.95
inputs_used:
  - memory:project_arc6_board_setup
  - memory:project_arc6_61_review_loop
  - backend/app/harnesses/model.py
  - backend/app/api/harnesses.py
  - backend/app/harnesses/validator.py
  - backend/app/harnesses/store.py
  - frontend/src/router.tsx
  - frontend/src/types.ts
  - frontend/src/api.ts
  - frontend/src/components/GoalDependencyGraph.tsx
  - frontend/src/components/Card.tsx
  - frontend/src/pages/HarnessRunsPage.tsx
  - frontend/src/hooks/useHarnessRuns.ts
  - frontend/package.json
outputs_produced:
  - .cronos/pipeline/arc6-visual-editor/scout-report-arc6-visual-editor.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - "backend/app/harnesses/ (model, validator, store, CRUD API)"
    - "backend/app/api/harnesses.py (CRUD endpoints, validation responses)"
    - "frontend/src/ (router, types, api hooks, pages, components)"
    - "frontend/package.json (existing dependencies)"
  excluded:
    - "Test files (**/tests/, **/__tests__/)"
    - "Executor/trigger/run-lifecycle modules"
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Research the codebase to support building a visual harness editor with React Flow. Focus on (1) harness data model & YAML serialization, (2) frontend routing & navigation, (3) component patterns & TanStack Query usage, (4) npm dependencies & isolation from @dagrejs/dagre, (5) backend validation (422 responses), (6) types system structure."
metrics:
  tool_calls: 18
  files_read: 14
  memory_hits: 2
---

## Summary

The Cronos harness system has a complete backend CRUD API (5 endpoints on `/api/spaces/{space_id}/harnesses`) with a Pydantic v2 data model supporting 5 node types (agent, trigger, decision, wait, aggregator), YAML persistence, and round-trip validation (R1–R7). The frontend has no existing harness editor but extensive patterns exist: TanStack Query hooks in `useHarnessRuns.ts`, a fully-routed `HarnessRunsPage`, and a Tailwind/Cronos-styled card component system. The `@dagrejs/dagre` dependency is isolated in `GoalDependencyGraph.tsx`; React Flow can be added without conflicts. Invalid graphs (422 responses) are caught by Pydantic model validation and cycle detection in the validator module. The types system is sparse for harness data on the frontend—types will need to be added to `frontend/src/types.ts`.

## Coverage

### Searched

- **Backend data model**: `backend/app/harnesses/model.py` (Harness, HarnessNode, HarnessEdge, NodeType, Position; R1–R4 field validation)
- **Harness validator**: `backend/app/harnesses/validator.py` (cycle detection R5, human wait guardrail R6, trigger-node validation R7)
- **Harness store**: `backend/app/harnesses/store.py` (YAML serialization, atomic writes, in-memory index, last-writer-wins concurrency)
- **CRUD API**: `backend/app/api/harnesses.py` (list, create, get, update, delete; 422 response paths)
- **Frontend router**: `frontend/src/router.tsx` (route registration pattern, outlet structure)
- **Frontend types**: `frontend/src/types.ts` (task/space/memory types; no harness types yet)
- **Frontend API client**: `frontend/src/api.ts` (harness run endpoints only; no harness CRUD calls)
- **Frontend hooks**: `frontend/src/hooks/useHarnessRuns.ts` (TanStack Query pattern, SSE stream usage)
- **Component patterns**: `GoalDependencyGraph.tsx` (dagre layout, SVG rendering), `Card.tsx` (Tailwind/Cronos styling)
- **Page structure**: `HarnessRunsPage.tsx` (page layout, list+detail pattern, responsive grid)
- **Dependencies**: `frontend/package.json` (@dagrejs/dagre@^1.1.8, TanStack Query@^5.59.20, react-router-dom@^6.30.3)

### Excluded

- Test files (`**/tests/`, `**/__tests__/`): not needed to understand data model and routing
- Executor modules (`executor.py`, `run_trigger.py`, `triggers.py`, `run_state.py`): orthogonal to editor scope
- Harness run-management endpoints (SSE, cancellation): already routed, not editor concern
- Worker background loop (`worker.py`): not relevant to frontend editor

### Strategies

- **memory_retrieval**: 2 relevant entries (Arc 6 board setup IDs, 6.1 harness model review notes)
- **glob_structural**: file enumeration to identify backend/frontend layout
- **grep_symbol**: searched for "reactflow" (0 hits), "canvas" (styling color class only), "editor" (existing markdown editor only)
- **read_targeted**: deep reads of 14 key files (model, validator, store, API, router, types, hooks, components)

## Findings

### 1. Harness Data Model — 5 Node Types, YAML Serialization

**Model structure** (backend/app/harnesses/model.py:93–203):

```
NodeType (Enum):
  - agent
  - trigger
  - decision
  - wait
  - aggregator
```

**HarnessNode fields**:
- `id: str` (unique within harness)
- `type: NodeType`
- `position: Position` (x: float, y: float) — **already supports canvas position**
- `ports: dict[str, dict]` (keyed by port-id; free-form metadata per port)
- `data: dict` (node-specific config; semantics documented in model.py docstring L16–82)
- `label: str`

**HarnessEdge fields**:
- `id: str` (unique within harness)
- `source: NodeRef` (node_id, port_id)
- `target: NodeRef` (node_id, port_id)
- `condition: str | None` (guard expression for decision routing)

**Top-level Harness**:
- `name, description, nodes[], edges[], variables: dict`
- `version: str = "1.0"`
- `created_at, updated_at: datetime` (UTC ISO-8601)

**YAML serialization** (store.py:86–97):
- Uses `model_dump(mode='json')` to emit datetimes as ISO-8601 strings
- Enums converted to string values
- Persisted to `.cronos/harnesses/<slugified_name>.yml`
- Deserialization via `Pydantic.model_validate(dict)` from yaml.safe_load

**Round-trip validation on create/update** (harnesses.py:147–182, 200–243):
- POST/PUT catch `ValidationError` → 422 Unprocessable Entity with error message
- Store layer calls `validate_graph(harness)` before persistence:
  - R1: node IDs unique (enforced by Pydantic model_validator)
  - R2: edge IDs unique (enforced by Pydantic model_validator)
  - R3: edge source/target node_id exist (enforced by Pydantic model_validator)
  - R4: edge source/target port_id exist on referenced node (enforced by Pydantic model_validator)
  - R5: DAG property (no cycles/self-loops) — **cycle detection in validator.py:37–116**
  - R6: human Wait nodes must have `max_wait_seconds` in data (validator.py:219–242)
  - R7: event trigger nodes must satisfy per-kind field requirements (validator.py:165–216)

**Cycle detection algorithm** (validator.py:37–116):
- Uses BFS per start node; builds adjacency list from edge source→target node_ids
- Returns cycle path as list of node_ids (first == last) or None
- Self-loops detected first

**Invalid graph responses** (422 Unprocessable Entity):
- Pydantic ValidationError from model_validator rules (R1–R4)
- HarnessGraphError from cycle detection (R5)
- HarnessValidationError from trigger/wait validation (R6, R7)

### 2. Frontend Routing & Navigation

**Router structure** (router.tsx:15–35):
- Root `<App />` outlet (main layout, sidebar)
- Current harness route: `<Route path="spaces/:spaceId/harnesses/:name/runs" element={<HarnessRunsPage />} />`
- **No editor route yet**

**Pattern for new route**:
```tsx
<Route path="spaces/:spaceId/harnesses/:name/edit" element={<HarnessEditorPage />} />
```

**Sidebar navigation** (Sidebar.tsx): 
- Link pattern: `to={`/spaces/${spaceId}/...`}` using `useParams()` hook
- Current nav includes spaces, tools, memory, stats; harnesses linked via board or tools page

**How to integrate editor**:
1. Add new route `spaces/:spaceId/harnesses/:name/edit` → `HarnessEditorPage.tsx`
2. Link from existing harness-list pages (e.g., HarnessRunsPage header or nav breadcrumb)
3. Use `useParams<{ spaceId: string; name: string }>()` to extract params
4. Call `api.getHarness(spaceId, name)` via TanStack Query (to be added)

### 3. Frontend Component Patterns — TanStack Query & Styling

**TanStack Query hook pattern** (useHarnessRuns.ts:22–65):

```typescript
// Query hook
export function useHarnessRuns(spaceId: string, name: string) {
  return useQuery({
    queryKey: ["harness-runs", spaceId, name],
    queryFn: () => api.listHarnessRuns(spaceId, name),
    refetchInterval: 5_000,
  });
}

// Mutation hook
export function useTriggerHarnessRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ spaceId, name }) => api.triggerHarnessRun(spaceId, name),
    onSuccess: (_data, { spaceId, name }) => {
      qc.invalidateQueries({ queryKey: ["harness-runs", spaceId, name] });
    },
  });
}
```

**Cronos styling (Tailwind v3.4)**:
- **Color tokens**: `bg-surface-1`, `bg-surface-2`, `border-hairline`, `border-accent`, `text-ink`, `text-ink-faint`, `text-accent-bright`
- **Card borders**: `rounded border border-hairline`
- **Button styles**: Example from HarnessRunsPage (L154): `rounded border border-accent/30 bg-accent/10 px-4 py-2 ... transition hover:bg-accent/20 disabled:opacity-60`
- **Grid layout**: Two-column responsive: `grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]`
- **Mobile-first**: Tailwind sm/lg breakpoints (sm:hidden, hidden sm:block)

**Card component** (Card.tsx):
- Complex task card with drag-drop (dnd-kit), state badges, priority dots, mode labels
- Tailwind classes for borders, surfaces, text colors
- Pattern: `className={cn(...classes)}` using `cn` utility from `utils/cn.ts`

**Graph visualization pattern** (GoalDependencyGraph.tsx:87–253):
- Uses dagre layout engine (not interactive, SVG-only)
- `useGraphLayout()` hook computes node positions via dagre.graphlib.Graph
- Renders SVG with `<foreignObject>` to embed React buttons inside SVG
- Mobile: flat list; desktop: toggle between graph/list views

### 4. Dependencies & Isolation

**Current dependencies** (package.json):
- `@dagrejs/dagre@^1.1.8` — **used only in GoalDependencyGraph.tsx (L2)**
- `@tanstack/react-query@^5.59.20` — core data-fetching library
- `@dnd-kit/*` — drag-drop (not needed for basic editor)
- `react-router-dom@^6.30.3` — routing
- `@uiw/react-md-editor@^4.1.0` — markdown editor (could be template for node data editor)

**Isolation of @dagrejs/dagre**:
- **Only import in**: GoalDependencyGraph.tsx (L2: `import * as dagre`)
- No other components depend on it; safe to add React Flow alongside without naming conflicts
- React Flow would be isolated similarly to a single HarnessEditor or canvas component

**React Flow addition**:
- `npm install reactflow` (latest: v12+)
- Zero conflicts with dagre; both are node graph libraries but separate namespaces
- Can co-exist: GoalDependencyGraph for task DAG, HarnessEditor for harness graph

### 5. Backend CRUD API & Validation

**Endpoints** (api/harnesses.py:138–489):

| Method | Path | Response | Notes |
|--------|------|----------|-------|
| GET | `/api/spaces/{space_id}/harnesses` | `list[Harness]` | List all harnesses in space |
| POST | `/api/spaces/{space_id}/harnesses` | `Harness` (201) | Create; validates via Pydantic + validate_graph() |
| GET | `/api/spaces/{space_id}/harnesses/{name}` | `Harness` | Fetch single harness |
| PUT | `/api/spaces/{space_id}/harnesses/{name}` | `Harness` | Update; preserves created_at via pre-fetch (fixed in arc6-harness-model review) |
| DELETE | `/api/spaces/{space_id}/harnesses/{name}` | 204 No Content | Blocks if active runs exist (409 Conflict) |

**Request/response schemas** (api/harnesses.py:81–100):

```python
class HarnessCreate(BaseModel):
    name: str
    description: str = ""
    nodes: list[HarnessNode] = []
    edges: list[HarnessEdge] = []
    variables: dict = {}
    version: str = "1.0"

class HarnessUpdate(BaseModel):
    # Identical structure; frontend should reuse same request type
    name: str
    description: str = ""
    nodes: list[HarnessNode] = []
    edges: list[HarnessEdge] = []
    variables: dict = {}
    version: str = "1.0"
```

**Error handling**:
- **400**: Malformed request body (JSON parse error)
- **404**: Harness not found (GET, PUT, DELETE on missing name)
- **409 Conflict**: DELETE blocked by active runs; name conflict on CREATE
- **422 Unprocessable Entity**: Validation failure (Pydantic ValidationError or HarnessGraphError)

**Concurrency note** (store.py:16–22, harnesses.py:11–18):
- Last-writer-wins semantics; no optimistic locking
- Callers must re-fetch after await boundaries
- Future: executor phase will add optimistic locking

### 6. Types System — Where to Add Harness Types

**Current frontend types** (types.ts:1–501):
- Task, TaskState, Board (task-management domain)
- View, Space, SpaceToolsResponse (workspace domain)
- Memory, Activity, Stats (cross-cutting)
- **No harness types yet**

**What to add to frontend/src/types.ts**:

```typescript
export type NodeType = "agent" | "trigger" | "decision" | "wait" | "aggregator";

export interface Position {
  x: number;
  y: number;
}

export interface NodePort {
  [key: string]: unknown; // free-form per port
}

export interface HarnessNode {
  id: string;
  type: NodeType;
  position: Position;
  ports: Record<string, NodePort>;
  data: Record<string, unknown>; // node-specific config
  label: string;
}

export interface NodeRef {
  node_id: string;
  port_id: string;
}

export interface HarnessEdge {
  id: string;
  source: NodeRef;
  target: NodeRef;
  condition: string | null;
}

export interface Harness {
  name: string;
  description: string;
  nodes: HarnessNode[];
  edges: HarnessEdge[];
  variables: Record<string, unknown>;
  version: string;
  created_at: string; // ISO-8601
  updated_at: string;
}
```

**Backend imports in api.ts**:
- Already imports from `./types` (line 1–27)
- Add Harness types to the import list, then export from api functions:

```typescript
// api.ts additions
export interface HarnessCreateRequest {
  name: string;
  description?: string;
  nodes: HarnessNode[];
  edges: HarnessEdge[];
  variables?: Record<string, unknown>;
  version?: string;
}

export const api = {
  // ... existing endpoints ...
  harnesses: {
    list: (spaceId: string) =>
      request<Harness[]>(`/api/spaces/${spaceId}/harnesses`),
    get: (spaceId: string, name: string) =>
      request<Harness>(`/api/spaces/${spaceId}/harnesses/${encodeURIComponent(name)}`),
    create: (spaceId: string, body: HarnessCreateRequest) =>
      request<Harness>(`/api/spaces/${spaceId}/harnesses`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    update: (spaceId: string, name: string, body: HarnessCreateRequest) =>
      request<Harness>(`/api/spaces/${spaceId}/harnesses/${encodeURIComponent(name)}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    delete: (spaceId: string, name: string) =>
      request<void>(`/api/spaces/${spaceId}/harnesses/${encodeURIComponent(name)}`, {
        method: "DELETE",
      }),
  },
};
```

## Assumptions

- **Position persistence**: The `Position` field in HarnessNode is already part of the model and will round-trip through YAML; the editor will read/write `node.position.x` and `node.position.y` directly.
- **Ports semantics**: Ports are arbitrary metadata dicts; their structure is determined by node type (agent nodes may have different ports than trigger nodes). The editor need only preserve the structure; validation of port semantics is deferred to backend.
- **Node data validation**: Complex node-type-specific validation (e.g., "wait node must have max_wait_seconds") happens at the backend; frontend form can guide users but backend is source of truth.
- **React Flow version**: Latest v12+ will be used; no legacy v11 constraints apply.
- **Drag-drop on canvas**: React Flow provides native drag-drop; no need for @dnd-kit overlay (which is used for task board reordering).
- **Single harness editor scope**: The task 6.7 delivers a single-harness editor view (no multi-harness batch editor); harness selection happens upstream (via router params or sidebar nav).

## Open questions

- None. All six focus areas have sufficient codebase context to guide analysis and design phases.

## Next consumer brief

**Read first from this report**:
1. Section 1 (data model): All R1–R7 validation rules, node types, edge/port/position fields
2. Section 5 (CRUD API): Request/response schemas, 422/404/409 error codes, concurrency last-writer-wins note
3. Section 6 (types): Proposed TypeScript types to add to frontend/src/types.ts

**Key decision points for analyst/architect**:
1. **Iteration structure**: Will the editor be a single large component or split into canvas/sidebar/inspector? Arc 6 design will determine.
2. **Node/edge creation UX**: Will users drag from a palette, or right-click canvas? Will ports be visual or implicit?
3. **Validation feedback**: Should the editor show 422 errors inline (per field) or as a modal banner?
4. **Undo/redo**: Needed? Can be deferred to a follow-up story.
5. **Auto-save vs explicit save**: HarnessRunsPage uses explicit "Run now" button; editor needs explicit save (PUT) or auto-save on idle?

**Unresolved blocker from 6.1 review**: Arc 6/6.1 fixed `created_at` mutation bug in update_harness (commit c501a98); ensure architect notes that PUT must re-fetch existing harness before constructing the updated one (pattern is in harnesses.py:208–223).
