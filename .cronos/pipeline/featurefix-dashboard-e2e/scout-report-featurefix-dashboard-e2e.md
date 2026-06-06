---
cc_version: "1.0"
agent: pipeline-scout
slug: featurefix-dashboard-e2e
phase: scout
status: done
confidence: 0.92
inputs_used:
  - memory:project_dashboard_design
  - memory:project_s2_api_impl
  - memory:project_s5_board_ui_impl
  - memory:Arc_features_fixes_board_setup
  - memory:S1_data_model_impl
  - frontend/src/pages/DashboardPage.tsx
  - backend/app/api/spaces.py
  - backend/app/models.py
  - frontend/src/types.ts
  - frontend/src/hooks/useSpaces.ts
  - backend/tests/test_feature_decompose_e2e.py
outputs_produced:
  - .cronos/pipeline/featurefix-dashboard-e2e/scout-report-featurefix-dashboard-e2e.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - frontend/src/pages/DashboardPage.tsx (main dashboard component)
    - backend/app/api/spaces.py (SpacesResponse definition)
    - backend/app/models.py (SpaceSummary, SpacesResponse, FeatureState schemas)
    - frontend/src/types.ts (SpacesResponse TypeScript types)
    - frontend/src/hooks/useSpaces.ts (useSpaces React Query hook)
    - backend/tests/test_feature_decompose_e2e.py (e2e test pattern reference)
  excluded:
    - Harness components: not relevant to dashboard tile logic
    - Memory store: only needed if dashboard reads memory (it doesn't)
    - Git ops: only if feature branch logic is tested (covered by feature_decompose tests)
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted

brief: |
  S6 — Dashboard & stats impact + end-to-end verification
  · Dashboard add "Features"/"In Backlog" tile linking to /features, fed by feature_totals
  · Backend: extend SpacesResponse with feature-count fields (separate from task_counts)
  · E2E pytest: capture → FEAT-001, process → decompose → realize → done + delete branch → feature
    done + issue closed; assert Tasks excludes it, Features buckets it, feature_totals reflects it
  · Acceptance: dashboard shows feature presence (≥ tile + total) without altering 5 task tiles or
    task_counts-driven UI; AI Performance + Test Health render identically; e2e passes; tsc
    --strict + pytest ≥60%

metrics:
  tool_calls: 7
  files_read: 7
  memory_hits: 5
---

## Summary

S6 adds feature-count visibility to the dashboard (via a new `feature_totals` field on `SpacesResponse`)
and implements an end-to-end pytest that validates the full feature lifecycle: capture (FEAT-001),
process/decompose (creates realizing goal), planned, done, and branch deletion (feature marked done,
issue closed). The dashboard will show feature presence as a 6th stat tile, separate from the existing
5 task-state tiles. No changes to task_counts-driven UI components (Sidebar open-count, Spaces grid)
are required. E2E mocks agent subprocess, gh CLI, and git branch checks to achieve deterministic
coverage without network or filesystem side effects.

## Coverage

### Searched
- DashboardPage.tsx: stat tile layout (StatTile component, Zone A mission control, 5 tiles for task states)
- SpacesResponse/SpaceSummary in backend/app/models.py: current schema (lines 155–168)
- SpacesResponse in frontend/src/types.ts and usage in DashboardPage.tsx (lines 562–673)
- useSpaces hook at frontend/src/hooks/useSpaces.ts (query invalidation patterns)
- E2E test pattern from test_feature_decompose_e2e.py (mocks, assertions, lifecycle)
- Feature lifecycle from S1-S5 memory entries

### Excluded
- Harness editor canvas and run overlay: not relevant to dashboard tile rendering
- Memory system: dashboard does not expose memory totals
- Adoption/discovery tools: separate from feature feature lifecycle
- Git operations internals: only needed for understanding when feature done-detection works

### Strategies
- memory_retrieval: Found 5 highly relevant memory entries documenting dashboard architecture, S2
  API design, S5 frontend completion, S1 data model (FeatureState), feature decompose e2e test pattern
- glob_structural: Identified all key files (DashboardPage, spaces.py, models.py, types.ts, hooks)
- grep_symbol: Confirmed SpacesResponse, FeatureState, SpaceCard, StatTile components present and
  accessible
- read_targeted: Read 7 files to depth sufficient to understand: (1) current stat tile layout and
  totals usage, (2) SpacesResponse contract (already has spaces and totals keys), (3) FeatureState
  enum (5 states: backlog/processing/planned/waiting/done), (4) e2e test patterns (mocks,
  assertions), (5) useSpaces query invalidation strategy

## Findings

### Backend API Contract (SpacesResponse)

**Current state (models.py:165–168):**
```python
class SpacesResponse(BaseModel):
    spaces: list[SpaceSummary] = []
    totals: dict[TaskState, int] = Field(default_factory=dict)
```

**Current usage in spaces.py (lines 106–119):** The `/api/spaces` GET endpoint returns a
SpacesResponse with `totals` computed from all tasks across all spaces:
```python
totals: dict[TaskState, int] = {s: 0 for s in TaskState}
for task in task_store.all():
    totals[task.state] = totals.get(task.state, 0) + 1
```

**Requirement:** Add a new field `feature_totals: Record<FeatureState, number>` to SpacesResponse
(separate from `totals`). This requires:
- Pydantic model addition in backend/app/models.py (1 line)
- Computation in backend/app/api/spaces.py list_spaces (iterate features by state, 3-4 lines)
- TypeScript model update in frontend/src/types.ts (1 line)

### Frontend Dashboard Layout

**Current stat tile layout (DashboardPage.tsx:657–674):** 5 stat tiles in a grid
(`grid-cols-2 sm:grid-cols-3 md:grid-cols-5`) for task states: To Do, Active agents, Waiting,
Done, Total tasks. Each tile uses `StatTile` component (lines 54–101) with optional `to=` prop for
linking (e.g., `to="/board"`).

**New tile requirement:** Add a 6th tile "Features / In Backlog" (or similar label) linking to
`/features`. Grid will adjust to `md:grid-cols-6` to accommodate or wrap to 2 rows. The tile value
should be the sum of feature_totals[backlog] + feature_totals[processing] (in-flight features) or
just feature_totals[backlog] depending on UX preference.

**No impact to existing components:**
- AI Performance and Test Health cards render identically (no totals change)
- Sidebar open-count logic derives from task state counts, not feature state
- SpaceCard grid (line 869) renders task_counts per space (unchanged)
- Activity feed (lines 882–911) shows task events (unchanged)

### E2E Test Structure (test_features_e2e.py)

Based on memory + test_feature_decompose_e2e.py pattern, the e2e test must:

1. **Setup:** Create a space with a feature task (type=feature), advance to PROCESSING
2. **Capture:** Create the feature with feature_key=FEAT-001, issue_number=42, issue_url (mocked)
3. **Process:** Mock agent subprocess (runAgentResult) returning decomposition output with goal
   having realizes=<feature_id>
4. **Decompose:** Verify goal created with realizes field set, feature state → PLANNED
5. **Drive goal to DONE:** Mock goal child tasks reaching done state, feature waiting→planned→done
6. **Branch deletion:** Mock branch_exists_on_origin returning False to trigger done-detection
7. **Verify feature done:** Assert feature_state=DONE, gh_issue_close called with issue_number
8. **Verify dashboard buckets:** Assert Tasks board excludes feature task, Features board includes
   it with correct state styling, feature_totals in next HTTP /api/spaces response reflects it

**Key mocks:** (following test_feature_decompose_e2e.py pattern at lines 133–200)
- `Worker._run_feature_decompose()` → mock to return AgentResult(status=DONE)
- `git_ops.fetch_origin()` → no-op async stub
- `git_ops.branch_exists_on_origin()` → return False to signal branch deleted
- `gh_issue_close()` → AsyncMock to verify call with issue_number

**Scope files (per brief):** DashboardPage.tsx, api/spaces.py, types.ts, test_features_e2e.py
(new). All frontend + backend changes under 150 lines of production code, ~200 lines test.

### TypeScript Type Alignment

**Current types.ts (lines 1–150):** Contains TaskState, FeatureState, FEATURE_LANES, SpaceCard,
etc. Frontend SpacesResponse must match backend; uses Record typing for totals (task_counts).

**Required addition:** Export feature_totals type:
```typescript
export interface SpacesResponse {
  spaces: SpaceSummary[];
  totals: Record<TaskState, number>;
  feature_totals: Record<FeatureState, number>;
}
```

Note: FeatureState already imported in types.ts (line 34).

### Acceptance Criteria Verification Vectors

1. **Dashboard tile presence:** StatTile with label "Features / In Backlog" renders at md:grid-cols-6
   or equivalent breakpoint, links to `/features`
2. **No task tile alteration:** 5 existing tiles (To Do, Active, Waiting, Done, Total) render
   identically, values from totals[TaskState], not feature_totals
3. **AI Performance + Test Health:** No changes to card structure, styling, or data source
4. **E2E lifecycle:** All steps above (capture through issue close) execute deterministically with
   mocks; feature_totals in response reflects done count after completion
5. **TypeScript strict:** tsc --strict passes with new feature_totals field in SpacesResponse
6. **Test coverage:** New test_features_e2e.py contributes ≥60% to overall coverage (pytest
   --cov-fail-under=60); feature path fully covered

## Assumptions
- The `/features` route already exists and renders a Features board (from S5 completion)
- FeatureState and feature task infrastructure (feature_state field on Task, decomposition skill,
  realizes field) are already in place (S1–S4 complete)
- Dashboard should show feature presence but NOT replace the task-state tiles; 6th tile is additive
- E2E test may use TestClient (synchronous) or async test harness; feature_decompose_e2e uses
  async pytest, following that pattern
- GitHub issue closing (gh_issue_close) is mocked; no real GitHub API calls needed

## Open questions
None. All brief requirements are actionable:
- SpacesResponse extension is a straightforward Pydantic model addition + query logic
- Dashboard tile addition is a copy-paste of StatTile pattern + grid breakpoint adjustment
- E2E test closely mirrors existing test_feature_decompose_e2e.py structure

## Next consumer brief

**Analysis phase should verify:**
- Dashboard tile can be hidden/shown per user preference (or is it always visible if any feature
  exists?)
- Feature totals aggregation logic: sum all spaces or per-space breakdown needed? (Brief says
  feature_totals on SpacesResponse, implying global totals like task_counts)
- E2E test parallelization: can it run alongside other feature tests or does it contend for a
  single SPACE_ID? (Recommend unique SPACE_ID per test)
- Tile label and link destination: does "Features / In Backlog" link to `/features` or a
  filtered view of in-flight features?

**Key decisions for implementor:**
- Grid breakpoint for 6 tiles: md:grid-cols-6 (60px tiles) or reflow to 2×3 layout
- Feature total value: backlog only, or backlog + processing (in-progress)?
- E2E test: deterministic run order or parallel-safe isolation per SPACE_ID?

**Files with highest impact (implementor priority):**
- backend/app/api/spaces.py (list_spaces function, ~5 lines feature_totals logic)
- frontend/src/pages/DashboardPage.tsx (stat tile grid + 1 new StatTile, ~10 lines)
- backend/app/models.py (SpacesResponse field, 1 line)
- frontend/src/types.ts (TypeScript SpacesResponse update, 1 line)
- backend/tests/test_features_e2e.py (new file, ~250 lines)
