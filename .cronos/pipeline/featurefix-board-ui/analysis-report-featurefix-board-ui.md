---
cc_version: '1.0'
agent: pipeline-analyst
slug: featurefix-board-ui
phase: analysis
status: done
confidence: 0.9
inputs_used:
- memory:project_s1_data_model_impl
- memory:project_s2_api_impl
- memory:project_s4_worker_decompose_impl
- memory:project_arc_features_fixes_board_setup
- .cronos/pipeline/featurefix-board-ui/scout-report-featurefix-board-ui.md
- .cronos/pipeline/featurefix-board-ui/request.md
- backend/app/pipeline/CONTRACT.md
- backend/app/pipeline/schemas/analysis.schema.yaml
outputs_produced:
- .cronos/pipeline/featurefix-board-ui/analysis-report-featurefix-board-ui.md
blockers: []
next_consumer: design
request: "# S5 — Features board + Tasks rename + cards + composer + realization links\n\
  \n**Title:** `Features&Fixes/S5 — Features board, Tasks rename, cards` · **has_ui:**\
  \ yes · **dep:** S2, S4\n\n- **types.ts:** `FeatureState` union; `FEATURE_LANES`\
  \ (5) + `canFeatureTransition()`; extend `TaskType`;\n  optional `feature_state/feature_key/issue_number/issue_url/realizes`\
  \ on `TaskSummary` (39-64) + `Task`\n  (86-112); `realized_by?: Array<{id;title;type?;state}>`\
  \ (server-computed); a `FeatureBoard` interface.\n  Keep the two lane systems disjoint\
  \ (note 6).\n- **`pages/FeaturesPage.tsx` + `components/FeaturesBoard.tsx`** (new):\
  \ parallel lightweight board (note 5)\n  reusing `Lane`/`Card`/`DndContext`/sensors\
  \ over `FEATURE_LANES`. Drag -> `useTransitionFeatureState`\n  (note 7); illegal\
  \ transition = no-op. Add `lg:grid-cols-5`. **Skip lane hide/restore**.\n- **`Lane.tsx`:**\
  \ widen `state` to `string`; add `showAdd?: boolean`; Tasks board passes\n  `showAdd={state===\"\
  backlog\"}` (backward-compatible).\n- **`Card.tsx`:** `feature`/`fix` `TYPE_BADGE_STYLES`\
  \ (91-94); `feature_key` chip; issue-link anchor\n  cloning the `pr_url` anchor\
  \ (476-487); a `-> realizes FEAT-NNN` chip cloning the parent-link chip\n  (503-521,\
  \ click-through via `onOpenTask`); on a feature card, a `realized_by` click-through\
  \ list.\n- **Hooks/API:** `hooks/useFeatures.ts` (new) - `useFeatureBoard(spaceId)`\
  \ keyed `[\"features\",spaceId]`\n  `refetchInterval:5000`; `useTransitionFeatureState`,\
  \ `useCreateFeature`. **Every feature mutation\n  invalidates `[\"features\",...]\
  \ AND `[\"board\",...]`** (shared Backlog) + `[\"spaces\"]`. `api.ts`:\n  `features`,\
  \ `transitionFeatureState`, `createFeature`.\n- **Routing/nav:** router.tsx add\
  \ `/features` + `/spaces/:spaceId/features`; Sidebar.tsx rename `/board`\n  `\"\
  Kanban\"->\"Tasks\"`, add `\"Features\"`.\n- **Shared Backlog on the Tasks board**\
  \ (read-only, single source of truth): an extra click-through\n  Backlog column\
  \ fed by `useFeatureBoard(spaceId).data.backlog`, outside the dnd `SortableContext`;\n\
  \  click -> `/features`. `Board.tsx`'s `TaskState` drag stays untouched.\n- **Composer:**\
  \ reuse `TaskForm` with a Feature/Fix `type` toggle (wired to `useCreateFeature`)\
  \ on the\n  Features Backlog lane header. Use [[frontend-design]] for styling.\n\
  \n**Scope files:** types.ts, `pages/FeaturesPage.tsx` + `components/FeaturesBoard.tsx`\
  \ + `hooks/useFeatures.ts` (new), Lane.tsx, Card.tsx, api.ts, router.tsx, Sidebar.tsx.\n\
  **Acceptance:** `/features` renders 5 lanes; drag hits the feature-state endpoint\
  \ only; sidebar shows\n\"Tasks\"+\"Features\" and `/board` still works; feature\
  \ card shows key + badge + issue link + realizing\nitems; a `realizes` goal/task\
  \ shows a `-> realizes FEAT-NNN` chip; a feature/fix can be created from the\nFeatures\
  \ Backlog; the Tasks board shows the shared read-only Backlog with existing task\
  \ flows unchanged;\n`tsc --strict` clean (no lane-system key mixing)."
has_ui: true
coverage_summary:
  searched:
  - frontend/src/types.ts
  - frontend/src/api.ts
  - frontend/src/router.tsx
  - frontend/src/components/Sidebar.tsx
  - frontend/src/components/Lane.tsx
  - frontend/src/components/Card.tsx
  - backend/app/feature_state.py
  - backend/app/feature_hooks.py
  - backend/app/pipeline/schemas/analysis.schema.yaml
  excluded:
  - 'backend/app/storage.py: S1 feature storage on feature/features-and-fixes branch'
  - 'backend/app/api/features.py: S2 features router on feature/features-and-fixes
    branch'
  - 'frontend/src/pages/FeaturesPage.tsx: target deliverable (does not yet exist)'
  - 'frontend/src/components/FeaturesBoard.tsx: target deliverable (does not yet exist)'
  - 'frontend/src/hooks/useFeatures.ts: target deliverable (does not yet exist)'
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: types.ts exports FeatureState union type, FEATURE_LANES constant (5 entries),
    and canFeatureTransition(from, to) function matching the 7 user-transition edges
    from backend feature_state.py.
  acceptance_criteria:
  - 'FeatureState is a string union: ''backlog'' | ''processing'' | ''planned'' |
    ''waiting'' | ''done''.'
  - FEATURE_LANES has exactly 5 entries, one per FeatureState value, with display
    labels.
  - canFeatureTransition(from, to) returns true for each of the 7 user-allowed edges
    and false for all others.
  - tsc --strict compiles types.ts without error; FeatureState and TaskState keys
    are disjoint constants (no mixing).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: 'types.ts extends TaskSummary (lines 39-64) and Task (lines 86-112) with
    optional feature fields: feature_state, feature_key, issue_number, issue_url,
    realizes, and realized_by; plus a FeatureBoard interface.'
  acceptance_criteria:
  - 'TaskSummary gains optional fields: feature_state?: FeatureState; feature_key?:
    string; issue_number?: number; issue_url?: string | null; realizes?: Array<{id:
    string; title: string; type?: TaskType}>.'
  - 'Task gains the same optional fields plus realized_by?: Array<{id: string; title:
    string; type?: string; state?: string}>.'
  - FeatureBoard interface is defined with keys matching each FeatureState value,
    each holding an array of the feature item type.
  - No existing required fields on TaskSummary or Task are removed or made optional.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R3
  statement: 'api.ts adds three feature API functions: features(spaceId), transitionFeatureState(taskId,
    state), and createFeature(spaceId, body).'
  acceptance_criteria:
  - 'api.features(spaceId: string): Promise<FeatureBoard> calls GET /api/spaces/{spaceId}/features
    and returns a FeatureBoard.'
  - 'api.transitionFeatureState(taskId: string, state: FeatureState): Promise<Task>
    calls the backend feature transition endpoint.'
  - 'api.createFeature(spaceId: string, body: {title: string; type: ''feature'' |
    ''fix''; [key: string]: unknown}): Promise<Task> calls the backend create feature
    endpoint.'
  - All three functions use the same auth and error-handling pattern as existing api.ts
    functions.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: hooks/useFeatures.ts (new file) exports useFeatureBoard, useTransitionFeatureState,
    and useCreateFeature hooks with the correct TanStack Query keys and mutation invalidation
    contract.
  acceptance_criteria:
  - 'useFeatureBoard(spaceId) returns a TanStack Query result keyed [''features'',
    spaceId] with refetchInterval: 5000.'
  - useTransitionFeatureState mutation calls api.transitionFeatureState and on success
    invalidates ['features', spaceId], ['board', spaceId], and ['spaces'].
  - useCreateFeature mutation calls api.createFeature and on success invalidates ['features',
    spaceId], ['board', spaceId], and ['spaces'].
  - All three hooks match the structural patterns of existing hooks in terms of error
    handling and query client usage.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R5
  statement: 'Lane.tsx is widened so state accepts string (not only TaskState) and
    a showAdd?: boolean prop controls the add button display, keeping existing Tasks
    board behavior unchanged.'
  acceptance_criteria:
  - Lane Props interface changes state type from TaskState to string.
  - 'Lane Props interface adds showAdd?: boolean.'
  - The add button renders when showAdd === true, regardless of the state value.
  - Existing Tasks board call-sites pass showAdd={state === 'backlog'} and behavior
    is unchanged.
  - tsc --strict compiles Lane.tsx without error after widening.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R6
  statement: 'Card.tsx adds feature/fix TYPE_BADGE_STYLES entries and renders three
    new chips: feature_key chip, issue_url anchor, and a realizes chip per realizes
    array entry.'
  acceptance_criteria:
  - TYPE_BADGE_STYLES gains 'feature' (emerald color) and 'fix' (rose color) entries
    alongside existing 'goal' and 'issue'.
  - When task.feature_key is set, a chip displaying the key value is rendered on the
    card.
  - When task.issue_url is set, an anchor element linking to that URL is rendered,
    cloning the pr_url anchor pattern at lines 476-487.
  - When task.realizes is set and non-empty, each entry renders a '-> realizes FEAT-NNN'
    chip that calls onOpenTask on click, cloning the parent-link chip pattern at lines
    503-521.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R7
  statement: Card.tsx renders a realized_by click-through list on feature/fix cards
    when realized_by is present and non-empty.
  acceptance_criteria:
  - When task.realized_by is set and the card type is 'feature' or 'fix', each item
    in realized_by renders as a clickable element showing the item title.
  - Clicking a realized_by item calls onOpenTask with that item's id.
  - The realized_by list does not render on non-feature/fix cards even if the field
    is present.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R8
  statement: FeaturesPage.tsx (new) is a page-level component that reads spaceId from
    route params, calls useFeatureBoard, and renders FeaturesBoard with loading and
    error states.
  acceptance_criteria:
  - FeaturesPage reads spaceId from route params (optional, falls back to active space
    context).
  - FeaturesPage calls useFeatureBoard(spaceId) and passes the result to FeaturesBoard.
  - FeaturesPage renders a loading state while data is fetching and an error state
    on failure.
  - tsc --strict compiles FeaturesPage.tsx without error.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R9
  statement: FeaturesBoard.tsx (new) renders exactly 5 feature-state Lane components
    with lg:grid-cols-5, dnd-kit drag-and-drop, and a canFeatureTransition no-op guard
    on drag end.
  acceptance_criteria:
  - FeaturesBoard renders exactly 5 Lane components, one per FEATURE_LANES entry.
  - The grid container uses the Tailwind class lg:grid-cols-5.
  - Drag-and-drop uses dnd-kit DndContext and SortableContext (same structural pattern
    as Board.tsx).
  - On drag end, if canFeatureTransition(from, to) returns false, no API call is made
    and the drag is a no-op.
  - On a valid drag, useTransitionFeatureState is called with the card's taskId and
    the target lane's FeatureState.
  - Lane hide/restore is not implemented.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R10
  statement: FeaturesBoard.tsx Backlog lane header includes a composer using TaskForm
    with a Feature/Fix type toggle wired to useCreateFeature.
  acceptance_criteria:
  - The Backlog lane (feature state 'backlog') renders a composer trigger in its header
    area.
  - The composer uses TaskForm (existing component) with a type toggle offering 'feature'
    and 'fix' options.
  - Submitting the form calls useCreateFeature with the selected type and other form
    values.
  - Styling follows the [[frontend-design]] skill conventions consistent with the
    rest of the board UI.
  verifying_phase: review
  confidence: 0.82
- requirement_id: R11
  statement: router.tsx adds /features (root-level) and /spaces/:spaceId/features
    (scoped) routes both pointing to FeaturesPage.
  acceptance_criteria:
  - Route /features renders FeaturesPage without a spaceId param.
  - Route /spaces/:spaceId/features renders FeaturesPage with spaceId param.
  - The existing /board and /spaces/:spaceId routes are unchanged and still functional.
  - tsc --strict compiles router.tsx without error.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R12
  statement: Sidebar.tsx renames the 'Kanban' nav link label to 'Tasks' and adds a
    'Features' nav link pointing to /features after it.
  acceptance_criteria:
  - The nav link previously labeled 'Kanban' now displays 'Tasks'; its href remains
    /board.
  - A new 'Features' nav link is present immediately after 'Tasks', pointing to /features.
  - Both links apply active-route highlighting correctly using the existing pattern.
  - tsc --strict compiles Sidebar.tsx without error.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R13
  statement: Board.tsx gains a read-only shared Backlog column fed by useFeatureBoard(spaceId).data?.backlog,
    placed outside the dnd SortableContext, with click navigating to /features.
  acceptance_criteria:
  - Board.tsx calls useFeatureBoard(spaceId) in addition to its existing data hooks.
  - A read-only Backlog column is rendered showing feature backlog items; it is NOT
    wrapped in any SortableContext.
  - Dragging items from the shared Backlog column into task lanes is not enabled.
  - Clicking a card in the shared Backlog navigates to /features (not opening a task
    detail panel).
  - All existing TaskState drag-and-drop lanes and task flows are unaffected.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R14
  statement: The entire S5 frontend change set compiles under tsc --strict with zero
    errors and no lane-system key collisions between TaskState and FeatureState; vitest
    test suite passes.
  acceptance_criteria:
  - Running tsc --strict on the frontend project produces zero type errors after all
    S5 changes.
  - No component passes a FeatureState value to a prop typed as TaskState or vice
    versa.
  - FEATURE_LANES and LANES constants use different key spaces with no intersection.
  - The vitest test suite passes with no new test failures introduced by the S5 changes.
  verifying_phase: test
  confidence: 0.92
metrics:
  tool_calls: 9
  files_read: 4
  memory_hits: 4
---

## Summary

S5 delivers a parallel Features board (5 lanes: backlog/processing/planned/waiting/done) alongside the existing Tasks Kanban, with full drag-and-drop wired to the S2 feature-state API. The frontend types, hooks, API stubs, and navigation all require additions; four files are new (FeaturesPage.tsx, FeaturesBoard.tsx, useFeatures.ts, and the FeatureBoard interface in types.ts). The Tasks board gains a read-only shared Backlog column fed by feature data, while its own drag state machine remains untouched. The key invariant across all 14 requirements is lane-system disjointness: FeatureState and TaskState must not mix as key types anywhere in the component tree.

## Scope

### In scope
- types.ts: FeatureState union, FEATURE_LANES (5), canFeatureTransition, optional feature fields on TaskSummary/Task, FeatureBoard interface
- api.ts: features(), transitionFeatureState(), createFeature() stubs
- hooks/useFeatures.ts (new): useFeatureBoard, useTransitionFeatureState, useCreateFeature with full invalidation contract
- FeaturesPage.tsx (new): page-level component with route-param space scoping and loading/error states
- FeaturesBoard.tsx (new): 5-lane dnd-kit board with lg:grid-cols-5, canFeatureTransition no-op guard, and Backlog composer
- Lane.tsx: widen state to string; add showAdd?: boolean prop
- Card.tsx: feature/fix TYPE_BADGE_STYLES; feature_key chip; issue_url anchor; realizes chip; realized_by list
- router.tsx: /features and /spaces/:spaceId/features routes
- Sidebar.tsx: rename "Kanban" to "Tasks"; add "Features" link
- Board.tsx: read-only shared Backlog column outside SortableContext with /features click-through

### Out of scope
- Backend changes: no new SQLite tables, no new API endpoints, no new backend modules (S1/S2 already delivered)
- Lane hide/restore: explicitly excluded by the request
- GitHub issue creation UI or HTTP issue API calls
- Feature detail/edit modal beyond what the existing Card/task-detail already shows
- Harnesses, archived, or other unrelated page navigation changes

### Deferred
- Real-time collaborative drag (optimistic updates beyond refetchInterval=5000)
- Feature board filtering/sorting by type, priority, or assignee
- Pagination on large feature backlogs
- Feature card inline editing from the board view

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | types.ts: FeatureState union, FEATURE_LANES (5 entries), canFeatureTransition (7 user-transition edges) |
| R2 | types.ts: optional feature fields on TaskSummary/Task and FeatureBoard interface |
| R3 | api.ts: features(), transitionFeatureState(), createFeature() functions |
| R4 | hooks/useFeatures.ts (new): useFeatureBoard, useTransitionFeatureState, useCreateFeature with invalidation contract |
| R5 | Lane.tsx: widen state to string, add showAdd?: boolean prop |
| R6 | Card.tsx: feature/fix badge styles, feature_key chip, issue_url anchor, realizes chip |
| R7 | Card.tsx: realized_by click-through list on feature/fix cards |
| R8 | FeaturesPage.tsx (new): page component with space scoping, loading/error states |
| R9 | FeaturesBoard.tsx (new): 5-lane dnd-kit board with canFeatureTransition no-op guard |
| R10 | FeaturesBoard.tsx: Backlog lane composer (TaskForm reuse with Feature/Fix toggle) |
| R11 | router.tsx: /features and /spaces/:spaceId/features routes |
| R12 | Sidebar.tsx: rename "Kanban" -> "Tasks", add "Features" link |
| R13 | Board.tsx: read-only shared Backlog column outside SortableContext |
| R14 | Full tsc --strict clean, no TaskState/FeatureState key mixing, vitest passing |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — FeatureState union with 5 values; FEATURE_LANES with 5 labelled entries; canFeatureTransition returns true only for 7 user-allowed edges; tsc clean
- R2 — TaskSummary and Task gain 6 optional feature fields; FeatureBoard interface defined; no existing required fields removed
- R3 — Three api.ts functions with correct endpoint targets and return types, consistent auth/error handling
- R4 — Three hooks with correct TanStack Query keys, refetchInterval:5000, and triple-key invalidation on mutation success
- R5 — Lane state widens to string; showAdd prop added; existing Tasks board behavior unchanged; tsc clean
- R6 — feature/fix emerald/rose badge styles; feature_key chip when present; issue_url anchor when present; realizes chip per entry
- R7 — realized_by list renders clickable items on feature/fix cards only; click calls onOpenTask
- R8 — FeaturesPage reads spaceId from route, calls useFeatureBoard, renders loading/error, passes data to FeaturesBoard; tsc clean
- R9 — 5 Lane components with lg:grid-cols-5; dnd-kit DndContext; canFeatureTransition no-op guard; useTransitionFeatureState on valid drag; no hide/restore
- R10 — Backlog lane header composer using TaskForm with Feature/Fix toggle; useCreateFeature on submit; frontend-design styling
- R11 — Two new routes in router.tsx pointing to FeaturesPage; existing routes unchanged; tsc clean
- R12 — "Kanban" label changed to "Tasks" at same /board href; "Features" link added to /features; active-route highlighting correct
- R13 — Board.tsx calls useFeatureBoard; read-only column outside SortableContext; click navigates to /features; existing task DnD unaffected
- R14 — tsc --strict zero errors; no FeatureState/TaskState key mixing across all files; vitest passes

## Traceability

The full requirement -> acceptance criteria -> verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | types.ts: FeatureState union, FEATURE_LANES (5 entries), canFeatureTransition (7 user-transition edges) |
| R2 | test | types.ts: optional feature fields on TaskSummary/Task and FeatureBoard interface |
| R3 | test | api.ts: features(), transitionFeatureState(), createFeature() functions |
| R4 | test | hooks/useFeatures.ts: useFeatureBoard, useTransitionFeatureState, useCreateFeature with invalidation contract |
| R5 | test | Lane.tsx: widen state to string, add showAdd?: boolean prop |
| R6 | test | Card.tsx: feature/fix badge styles, feature_key chip, issue_url anchor, realizes chip |
| R7 | test | Card.tsx: realized_by click-through list on feature/fix cards |
| R8 | test | FeaturesPage.tsx (new): page component with space scoping, loading/error states |
| R9 | test | FeaturesBoard.tsx (new): 5-lane dnd-kit board with canFeatureTransition no-op guard |
| R10 | review | FeaturesBoard.tsx: Backlog lane composer (TaskForm reuse with Feature/Fix toggle) |
| R11 | test | router.tsx: /features and /spaces/:spaceId/features routes |
| R12 | test | Sidebar.tsx: rename "Kanban" -> "Tasks", add "Features" link |
| R13 | test | Board.tsx: read-only shared Backlog column outside SortableContext |
| R14 | test | Full tsc --strict clean, no TaskState/FeatureState key mixing, vitest passing |

## Assumptions

- S1 (data model) and S2 (features API) are already merged to feature/features-and-fixes and backend endpoints (GET /api/spaces/{spaceId}/features, POST /features, PATCH feature-state transition) are callable; this spec does not revisit backend contracts.
- S4 (worker feature decompose) is done per memory entry project_s4_worker_decompose_impl; no feature_sync coupling is required in the S5 frontend.
- The FeatureBoard type groups feature items (type=feature|fix, identified by feature_state field) by their feature_state value, mirroring the backend response shape from S2.
- TaskType (currently "task"|"goal"|"issue") was extended in S1 to include "feature" and "fix"; S5 types.ts imports or redeclares these values without conflict.
- The shared Backlog on the Tasks board uses the same useFeatureBoard hook as FeaturesPage; this results in two concurrent 5-second polling intervals in the tasks view — acceptable for MVP.
- has_ui=true: the request explicitly states has_ui: yes and all 14 requirements are purely frontend UI changes.
- Board.tsx is in scope for the shared Backlog addition even though it is not listed in the "Scope files" bullet of the request; the acceptance criteria require it and the scout report (section 9) confirms the pattern.
- [[frontend-design]] skill styling for the Backlog composer (R10) is a design-phase concern; this spec records the requirement without prescribing specific style tokens.

## Open questions

- None. The scout report confirms no unresolved ambiguities; S1/S2/S4 foundation provides all needed backend contracts.

## Next consumer brief

Design agent entry points in priority order:

1. Read `traceability[]` for the full 14-requirement list; `has_ui: true` confirms UI track routing.
2. Scope boundary: frontend-only. All 10 scope files listed in the request are the hard implementation boundary; `backend/app/` is read-only reference.
3. Critical structural constraint (R1, R14): FeatureState and TaskState must remain disjoint type constants. Any component accepting both must use `string` (as in R5 Lane widening), never a union of the two enums. This is the highest type-system risk.
4. Invalidation contract (R4): every feature mutation invalidates exactly `["features", spaceId]`, `["board", spaceId]`, and `["spaces"]`; the shared Backlog on Board.tsx auto-refetches via the `["features"]` cache key.
5. Shared Backlog isolation (R13): the read-only column in Board.tsx must be outside SortableContext; dnd-kit isolation must be explicit to prevent accidental cross-drag. This is the highest structural DnD risk.
6. R10 (composer) is verifying_phase: review because TaskForm reuse pattern and frontend-design styling require human review; allocate a dedicated design iteration for it.
7. New files to create: FeaturesPage.tsx, FeaturesBoard.tsx, useFeatures.ts — all mirror existing Board.tsx/BoardPage.tsx/useTasks.ts patterns documented in scout section 7.
8. Confirm the exact response shape of GET /spaces/{spaceId}/features from S2 to validate the FeatureBoard interface definition in R2.
