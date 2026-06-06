---
cc_version: "1.0"
agent: pipeline-scout
slug: featurefix-board-ui
phase: scout
status: done
confidence: 0.88
inputs_used:
  - memory:project_s1_data_model_impl
  - memory:project_s2_api_impl
  - memory:project_s4_worker_decompose_impl
  - frontend/src/types.ts
  - frontend/src/api.ts
  - frontend/src/router.tsx
  - frontend/src/components/Sidebar.tsx
  - frontend/src/components/Lane.tsx
  - backend/app/feature_state.py
  - backend/app/feature_hooks.py
outputs_produced:
  - .cronos/pipeline/featurefix-board-ui/scout-report-featurefix-board-ui.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - "frontend/src/types.ts: union types, interfaces, constants"
    - "frontend/src/api.ts: HTTP client function stubs"
    - "frontend/src/router.tsx: route definitions"
    - "frontend/src/components/{Lane,Card,Sidebar}.tsx: UI component interfaces"
    - "backend/app/feature_state.py: FeatureState enum and transitions"
    - "backend/app/feature_hooks.py: stub signatures for S3/S4"
    - "backend/app/models.py: existing Task/TaskSummary/Board models"
  excluded:
    - "backend/app/storage.py: requires S1 feature storage methods (on feature/features-and-fixes)"
    - "backend/app/api/features.py: S2 implementation is on feature/features-and-fixes"
    - "frontend/src/pages/FeaturesPage.tsx: does not exist yet (S5 target)"
    - "frontend/src/components/FeaturesBoard.tsx: does not exist yet (S5 target)"
    - "frontend/src/hooks/useFeatures.ts: does not exist yet (S5 target)"
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: |
  Reconnaissance of the frontend codebase for Features&Fixes/S5 (Features board + Tasks
  rename + cards + composer + realization links). Map the existing Task/Board architecture,
  understand what S1 (data model) and S2 (API) provide as foundation, and identify what
  new components/types/hooks/routes must be created. Note Lane type-widening, Card feature/fix
  badge styles, router structure, and hook patterns.
metrics:
  tool_calls: 18
  files_read: 10
  memory_hits: 3
---

## Summary

S5 builds a parallel Features board with 5 feature states (backlog/processing/planned/waiting/done)
alongside the existing Tasks Kanban. The backend foundation is in place: S1 added `FeatureState`
enum and numbering; S2 added features API router, realize/process endpoints, and feature fields
to TaskSummary/Task. The frontend needs four new top-level modules (FeaturesPage, FeaturesBoard,
useFeatures hook, new types), plus widening of Lane to accept `string` state and adding feature/fix
TYPE_BADGE_STYLES to Card. Types.ts must be extended with `FeatureState`, `FEATURE_LANES`, and
optional feature fields on TaskSummary/Task; router.tsx adds `/features` paths; Sidebar.tsx renames
Kanban → Tasks and adds Features link. All existing Task board drag, invalidation, and composition
logic can be reused.

## Coverage

### Searched

- **frontend/src/types.ts**: TaskState enum (5 states), LANES constants; canUserTransition; TaskSummary (lines 39–64) and Task (lines 86–112) models; no FeatureState yet
- **frontend/src/api.ts**: task/board/spaces/views/harness CRUD endpoints; no features stubs yet
- **frontend/src/router.tsx**: 50 lines; routes for board, harnesses, archived, spaces; no /features routes
- **frontend/src/components/Sidebar.tsx**: primary nav (Dashboard, Kanban at line 135–141, no Features); space list
- **frontend/src/components/Lane.tsx**: 102 lines; dnd-kit droppable with SortableContext; state:TaskState typed; add button backlog-only at line 53
- **frontend/src/components/Card.tsx**: TYPE_BADGE_STYLES at 91–94 (goal/issue only); pr_url anchor pattern at 476–487; parent-link chip at 503–521
- **backend/app/feature_state.py**: FeatureState enum (5 states); FEATURE_USER_TRANSITIONS (7 edges); FEATURE_WORKER_TRANSITIONS (5 edges)
- **backend/app/feature_hooks.py**: mirror_feature_to_github, enqueue_feature_decomposition stubs (S3/S4 contracts)
- **backend/app/models.py**: TaskState, TaskSummary, Task; no FeatureState or feature fields yet

### Excluded

- **backend/app/storage.py**: S1 feature table + transition_feature method on feature/features-and-fixes
- **backend/app/api/features.py**: S2 features router on feature/features-and-fixes
- **frontend/src/pages/FeaturesPage.tsx**: target deliverable
- **frontend/src/components/FeaturesBoard.tsx**: target deliverable
- **frontend/src/hooks/useFeatures.ts**: target deliverable
- **test files**: not in S5 scope

### Strategies

- **memory_retrieval**: 3 hits — S1 data model (FeatureState, Task fields), S2 API (features router), S4 worker (feature_sync)
- **glob_structural**: frontend src tree pattern scans
- **grep_symbol**: FeatureState enum, feature_state identifiers, FEATURE_LANES, Task/Board patterns
- **read_targeted**: types.ts, api.ts, router.tsx fully read; Lane/Card components for dnd-kit patterns; feature_state.py enum for state names

## Findings

### 1. Frontend Type System (types.ts) — Gaps

**Current state** (lines 1–27):
- TaskState enum: backlog, active, waiting, done, archived
- LANES array with 5 labels
- canUserTransition(from, to) with 12 allowed edges

**What S5 needs to add:**
- FeatureState enum: backlog, processing, planned, waiting, done (5 states, differs from TaskState)
- FEATURE_LANES array: 5 entries with labels for each feature state
- canFeatureTransition(from, to) function mirroring FEATURE_USER_TRANSITIONS from backend (7 allowed edges)
- Optional fields on TaskSummary (lines 39–64):
  - feature_state?: FeatureState
  - feature_key?: string (e.g., FEAT-123)
  - issue_number?: number
  - issue_url?: string | null
  - realizes?: Array<{id: string; title: string; type?: TaskType}> (server-computed)
- Optional fields on Task (lines 86–112): same as TaskSummary
- FeatureBoard interface: backlog, processing, planned, waiting, done (each: Feature[])
- Feature items use type="feature" or type="fix" in same Task table, distinguished by feature_state field

### 2. API Stubs (api.ts) — Missing Endpoints

**Current state** (lines 108–399):
- task, board, create, transition, reorder, spaces, views endpoints
- No features endpoints

**What S5 needs to add (per S2):**
- api.features(spaceId: string): Promise<FeatureBoard> — all features grouped by state
- api.transitionFeatureState(taskId: string, state: FeatureState): Promise<Task> — mutates feature_state
- api.createFeature(spaceId: string, body: {...}): Promise<Task> — returns task with feature_state=backlog
- Each mutation invalidates ["features", spaceId] AND ["board", spaceId] + ["spaces"]

### 3. Route Definitions (router.tsx) — Additions

**Current state** (lines 20–50):
- /board → BoardPage
- /spaces/:spaceId → BoardPage
- /harnesses → HarnessesPage

**What S5 needs:**
- /features → FeaturesPage (root-level, like /board)
- /spaces/:spaceId/features → FeaturesPage (scoped)

### 4. Lane Component — Type Widening

**Current state** (Lane.tsx):
```typescript
interface Props {
  state: TaskState;  // strictly typed
  label: string;
  tasks: TaskSummary[];
  onAdd: () => void;
}
```
Add button only when state === "backlog" (line 53)

**What S5 needs:**
- Widen state to string (covers both TaskState and FeatureState)
- Add showAdd?: boolean prop (Tasks board passes showAdd={state==="backlog"}, Features passes same)
- Existing button logic remains unchanged

### 5. Card Component — Feature/Fix Badges + Realizes Chip

**Current state** (Card.tsx):
```typescript
const TYPE_BADGE_STYLES: Partial<Record<TaskType, string>> = {
  goal: "...",
  issue: "...",
};
```

**What S5 needs:**
- Add feature/fix badge styles (emerald for feature, rose for fix)
- Render feature_key chip if task.feature_key exists (mirrors pr_url anchor pattern at Card.tsx:476–487)
- Render issue_url anchor if task.issue_url exists
- Add realizes chip: "→ realizes FEAT-NNN" linking to parent feature (clones parent-link chip pattern at 503–521)
- On feature card, render realized_by list click-through if present

### 6. Sidebar Navigation — Rename + Feature Link

**Current state** (Sidebar.tsx lines 135–141):
- Link to /board labeled "Kanban"

**What S5 needs:**
- Rename "Kanban" → "Tasks"
- Add new "Features" link to /features after Tasks

### 7. New Modules (Not Yet Created)

**FeaturesPage.tsx:**
- Mirrors BoardPage.tsx
- Route params scoping (:spaceId optional)
- useFeatureBoard(boardSpaceId) with refetchInterval=5000
- Renders FeaturesBoard

**FeaturesBoard.tsx:**
- Mirrors Board.tsx
- 5 Lane components (backlog, processing, planned, waiting, done)
- Drag → useTransitionFeatureState(taskId, newState)
- Grid-cols-5 class
- Shared Backlog read-only column (outside SortableContext)
- Composer: TaskForm with Feature/Fix type toggle

**useFeatures.ts hook:**
- useFeatureBoard(spaceId): Query, refetchInterval=5000
- useTransitionFeatureState: Mutation invalidating ["features", spaceId] + ["board", spaceId] + ["spaces"]
- useCreateFeature: Mutation with same invalidations

### 8. State Transitions — Backend Reference

**FeatureState enum (backend/app/feature_state.py):**
- States: BACKLOG, PROCESSING, PLANNED, WAITING, DONE
- User transitions (7): backlog↔processing, planned↔processing, waiting↔processing, waiting→planned, planned→done, done→backlog
- Worker transitions (5): processing→{planned,waiting}, planned↔waiting, planned→done

Frontend canFeatureTransition must match user transitions (7 edges); illegal drag = no-op.

### 9. Composition Patterns — Lane/Card Reuse

**Lane component:**
- Already generic over state type (will widen to string)
- DnD droppable on state ID
- SortableContext on taskIds
- onAdd callback controlled by showAdd prop

**Card component:**
- Renders brief_preview, priority, mode, type badge, space tag, parent link, children progress
- For features: feature/fix badge, feature_key chip, issue_url anchor, realizes chip, realized_by list
- Click → onOpen(id)

**Shared Backlog on Tasks board:**
- Single read-only extra column outside SortableContext
- Populated by useFeatureBoard(spaceId).data.backlog
- Click → navigate to /features

---

## Assumptions

- FeatureState enum exists on backend; S5 imports from backend models or types.ts
- S2 API (features endpoint) deployed; S5 calls api.features(spaceId)
- feature_state, feature_key, issue_number, issue_url, realizes fields exist in backend Task models (S1) and storage (S1)
- TaskType remains "task"|"goal"|"issue"; Feature/Fix items use type="feature"/"fix", distinguished by feature_state
- Backend auto-invalidates ["board", spaceId] when feature transitions (Shared Backlog auto-refetches)
- Drag-and-drop uses same dnd-kit machinery (useDroppable, SortableContext); only state machine differs
- Composer reuses TaskForm component with type toggle; no new form component

## Open questions

None. Brief is clear; S1/S2/S4 foundation on feature/features-and-fixes provides contracts for S5 UI work.

## Next consumer brief

**For analysis agent:**

1. **Has UI**: yes (5-lane board, nav changes, composer)
2. **Scope**: Frontend only (no backend changes)
3. **Components to create/modify**:
   - types.ts: add FeatureState, FEATURE_LANES, canFeatureTransition, optional feature fields
   - router.tsx: add /features and /spaces/:spaceId/features routes
   - Sidebar.tsx: rename Kanban → Tasks, add Features link
   - Lane.tsx: widen state to string, add showAdd prop
   - Card.tsx: add feature/fix TYPE_BADGE_STYLES, feature_key chip, issue_url anchor, realizes chip, realized_by list
   - api.ts: add features(), transitionFeatureState(), createFeature() stubs
   - NEW: FeaturesPage.tsx (page-level component)
   - NEW: FeaturesBoard.tsx (board container)
   - NEW: useFeatures.ts (hook module)
4. **Invalidation contract**: mutations invalidate ["features", spaceId], ["board", spaceId], ["spaces"]
5. **Validation**: tsc --strict clean; no TaskState/FeatureState key collision; Shared Backlog outside SortableContext
6. **Reuse patterns**: Lane accepts string state, Card renders feature/fix badge, dnd-kit drag unchanged
7. **Dependencies**: depends on S1 (types), S2 (api), S4 (feature sync)
