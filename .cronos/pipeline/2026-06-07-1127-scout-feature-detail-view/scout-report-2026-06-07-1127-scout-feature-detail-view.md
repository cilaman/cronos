---
cc_version: "1.0"
agent: pipeline-scout
slug: 2026-06-07-1127-scout-feature-detail-view
phase: scout
status: done
confidence: 0.92
inputs_used:
  - memory:project_features_backend_audit
  - memory:project_s2_api_impl
  - memory:project_s5_board_ui_impl
  - memory:project_merge_2026_06_08
  - memory:project_architecture_key_modules
  - memory:project_pipeline_scout_agent
  - frontend/src/api.ts:402-423
  - frontend/src/hooks/useFeatures.ts
  - frontend/src/components/FeaturesBoard.tsx:240-271
  - frontend/src/components/Board.tsx:55-322
  - frontend/src/components/Detail.tsx:1-1189
  - frontend/src/hooks/useTasks.ts:1-100
  - backend/app/api/features.py:180-327
  - backend/app/models.py:199-225
  - frontend/src/types.ts:1-150
outputs_produced:
  - .cronos/pipeline/2026-06-07-1127-scout-feature-detail-view/scout-report-2026-06-07-1127-scout-feature-detail-view.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - frontend/src/api.ts (feature API methods)
    - frontend/src/hooks/useFeatures.ts (feature query hooks)
    - frontend/src/components/FeaturesBoard.tsx (board layout + dead onOpen)
    - frontend/src/components/Board.tsx (task detail panel lifecycle)
    - frontend/src/components/Detail.tsx (task detail component pattern)
    - frontend/src/hooks/useTasks.ts (task query hook patterns)
    - backend/app/api/features.py (GET, PATCH, POST endpoints)
    - backend/app/models.py (FeatureRead schema with waiting_question)
    - frontend/src/types.ts (FeatureState, FeatureBoard, Task definitions)
  excluded:
    - frontend/src/pages/: not focus; routing layer exists
    - backend/app/storage.py: feature state machine checked via memory
    - Test files: not in scope for discovery phase
  strategies:
    - memory_retrieval
    - glob_structural
    - read_targeted

brief: "Detail view for feature/fix cards. Identify missing frontend API methods (getFeature, patchFeature) + hooks + modal component. Compare Task detail lifecycle to needed Feature detail lifecycle. Traceability to backend endpoints."

metrics:
  tool_calls: 12
  files_read: 9
  memory_hits: 6
---

## Summary

Feature detail view infrastructure exists on the backend (4 endpoints: GET, PATCH edit, PATCH state, POST process) and partially on the frontend (FeaturesBoard canvas, no detail modal). The FeaturesBoard at line 252 has a dead `onOpen={() => {}}` handler — a signal that detail-view wiring was planned but not completed. The Task detail pattern (Detail.tsx: 1189 lines) provides the complete lifecycle: modal state management, tab switching, inline editing, hierarchy panel, conversation stream, and action bar. Feature detail must mirror this structure but serve feature-specific fields (feature_state, feature_key, realizing_items, waiting_question) and omit task-only sections (agent_mode/model selectors, hierarchy graph). Four missing frontend pieces block implementation: (1) `api.getFeature(id)` and `api.patchFeature(id, body)` methods; (2) `useFeature(id)` and `useUpdateFeature(id)` hooks; (3) `FeatureDetail` modal component; (4) `useFeature` hook integration in FeaturesBoard.

## Coverage

### Searched

- **frontend/src/api.ts:402-423** — Feature API methods (features, transitionFeatureState, createFeature) present; **missing getFeature, patchFeature**
- **frontend/src/hooks/useFeatures.ts** — Three hooks: useFeatureBoard (5s polling), useTransitionFeatureState, useCreateFeature; invalidateFeatureQueries helper handles triple-key sync ([features, spaceId], [board, spaceId], [spaces])
- **frontend/src/components/FeaturesBoard.tsx:240-271** — Lane renderer calls `Lane` with `onOpen={() => {}}` (dead no-op at line 252); Card clickHandler also no-op (line 266)
- **frontend/src/components/Board.tsx:55-322** — Task board lifecycle: openId/setOpenId state via URL searchparams (lines 74-89); Detail modal injected at 318 with taskId + onClose; modal lifecycle uses `?task={id}` query param and Escape key handler
- **frontend/src/components/Detail.tsx:1-1189** — Full 1189-line Task detail pattern: Modal wrapper with close handler, header (badges, title, controls), action bar, tabs (details/stats/trace/files), content panels, editing form overlay. Key integration: useTask hook (line 815), mutations for update/delete/start/stop/archive/reply (lines 816-821), Hierarchy section with promote/parent/dependencies, ConversationStream, ChatInput with waiting_question awareness (line 1126)
- **frontend/src/hooks/useTasks.ts:1-100** — Query pattern: useTask (no-op enabled guard), invalidateBoards predicate-match, useUpdateTask calls api.update + invalidates boards + refetches task
- **backend/app/api/features.py:180-327** — Four endpoints: GET /api/features/{id} (FeatureRead + realizing_items), PATCH /api/features/{id}/feature-state (state transition), PATCH /api/features/{id} (edit title/brief), POST /api/features/{id}/process (decomposition). All 404 on missing/wrong-type, PATCH state fires mirror call (R13), GET does not (call_count==0)
- **backend/app/models.py:199-225** — FeatureRead schema: inherits from Task fields (id, space_id, title, state, created_at, updated_at, brief, priority, manual_order, type, parent_id, depends_on, pr_url, proposed_pr_path); adds feature-specific fields (feature_state, feature_key, realizes, issue_number, issue_url, proposed_issue_path, waiting_question added 2026-05-30 fix, realizing_items: TaskSummary[])
- **frontend/src/types.ts:1-150** — FeatureState type (5 states: backlog, processing, planned, waiting, done), FEATURE_LANES, canFeatureTransition guard, FeatureBoard interface (5 lanes of TaskSummary), TaskSummary with optional feature_state/feature_key/issue_number/issue_url/realizes/realized_by fields, Task interface (full shape with optional feature fields)

### Excluded

- **frontend/src/pages/**: not in brief scope; routing layer is separate from detail-view mechanics
- **backend/app/storage.py**: feature state machine already documented in memory; not needed for frontend requirements
- **Test files**: discovery phase focuses on implementation surface, not test coverage
- **frontend/src/components/Modal.tsx**: wrapper exists (used by Detail.tsx); not scope

### Strategies

- **memory_retrieval**: 6 hits — features backend audit (waiting_question fix), S2 API impl notes (PATCH endpoints), S5 board UI (card structure), merge 2026-06-08 (fix confirmation), architecture modules, pipeline-scout role
- **glob_structural**: skipped; all focus areas provided by brief (no additional pattern discovery needed)
- **read_targeted**: all 9 files read to working depth (Detail.tsx full for pattern reference)

## Findings

### 1. Backend API Surface is Complete

Four endpoints exist and are production-ready per S2 memory:

- **GET /api/features/{feature_id}** (line 180-196, features.py): Returns FeatureRead with realizing_items populated. No mirror call (R13: call_count==0). Guards: 404 if feature_id missing or task.type not in ("feature", "fix").
- **PATCH /api/features/{feature_id}/feature-state** (line 199-239): Enforces FEATURE_USER_TRANSITIONS. Fires mirror call with reason='state_change' (R13). Returns 409 on illegal transition.
- **PATCH /api/features/{feature_id}** (line 242-280): Edits title and/or brief. Fires mirror call with reason='edit'. Returns 404 on missing/wrong-type, 400 on validation error.
- **POST /api/features/{feature_id}/process** (line 330+): Transitions to PROCESSING and enqueues S4 decomposition. Fires mirror call. Returns 409 on illegal transition, 404 on missing IDs.

**FeatureRead schema** (models.py:199-225) now includes waiting_question field (merged 2026-06-08, commit f02301b). Inherits Task-like fields (state, created_at, updated_at, brief, priority, manual_order, parent_id, depends_on, pr_url, proposed_pr_path) plus feature-specific fields (feature_state: FeatureState | None, feature_key: str | None, realizes: str | None, issue_number: int | None, issue_url: str | None, proposed_issue_path: str | None, realizing_items: TaskSummary[]).

### 2. Frontend API Methods — Two Missing

Current frontend features API (api.ts:402-423):
- `features(spaceId)` — GET /api/features (FeatureBoard board data)
- `transitionFeatureState(taskId, state)` — PATCH /api/features/{taskId}/feature-state
- `createFeature(spaceId, body)` — POST /api/features

**Missing methods:**
- **`getFeature(featureId: string): Promise<FeatureRead>`** — corresponds to GET /api/features/{id}. Must return full FeatureRead with realizing_items, waiting_question, feature_key, etc.
- **`patchFeature(featureId: string, body: { title?: string; brief?: string }): Promise<FeatureRead>`** — corresponds to PATCH /api/features/{id}. Used by detail view inline edit.

Both are straightforward wraps of their backend counterparts (lines 180-280, features.py).

### 3. Frontend Hooks — Two Missing

Current useFeatures.ts:
- `useFeatureBoard(spaceId)` — fetches FeatureBoard with 5s polling (line 28-34)
- `useTransitionFeatureState(spaceId)` — mutates state + invalidates triple-key (line 41-49)
- `useCreateFeature(spaceId)` — mutates + invalidates triple-key (line 56-64)
- `invalidateFeatureQueries(qc, spaceId)` — helper that invalidates [features, spaceId], [board, spaceId], [spaces] (required for Backlog sync on Tasks board per R4)

**Missing hooks:**
- **`useFeature(featureId: string | null): UseQueryResult<FeatureRead>`** — Pattern mirrors useTasks.ts:15-20 (useTask). Must enable=featureId!==null, queryKey=["feature", featureId], fetch via api.getFeature.
- **`useUpdateFeature(featureId: string): UseMutationResult`** — Pattern mirrors useTasks.ts:42-56 (useUpdateTask). Accepts body: { title?: string; brief?: string }, calls api.patchFeature, invalidates [feature, featureId] and triple-key for board sync.

### 4. FeaturesBoard — Dead Detail Handler

FeaturesBoard.tsx line 252: `onOpen={() => {}}` — no-op handler passed to Lane component. This is the signal that detail-view wiring was planned but incomplete. Similarly, Card clickHandler (line 266) is `onClick={() => {}}`.

Contrast to Board.tsx (lines 268, 271): `onOpen={setOpenId}` and `onOpenTask={setOpenId}` — Board has live handlers that set URL searchParam `?task={id}` and trigger Detail modal injection (line 318).

**Required change:** FeaturesBoard must adopt same pattern: useState for detailId, setSearchParams to ?feature={id}, inject FeatureDetail modal at bottom (mirrors Board.tsx:318).

### 5. Task Detail Pattern (Complete Reference)

Detail.tsx (1189 lines) establishes the canonical pattern for detail modals in Cronos:

**State Management (lines 814-828):**
- useTask hook with taskId prop
- useState for activeTab ("details" | "stats" | "trace" | "files")
- useState for editing (form overlay)
- Mutation hooks: updateTask, deleteTask, archiveTask, replyTask, startTask, stopTask, transitionTask

**Modal Layout (lines 902-1161):**
- Modal wrapper with onClose callback (line 904)
- Header section (lines 926-1017): badges (state, priority, space), title, controls (priority/mode/model dropdowns), close button
- TaskActionBar (lines 1019-1034): Start/Stop/Edit/Delete/Archive/MarkDone/SendToBacklog buttons, state-gated visibility
- Tab bar (lines 1036-1066): details/stats/trace/files tabs, mobile-friendly files tab
- Conditional content panels (lines 1068-1157): Brief section (Markdown), Pull Request link, HierarchySection, ConversationStream for details tab; StatsPanel for stats tab; TracePanel for trace tab; FilesPanel for files/mobile
- ChatInput at bottom (line 1124-1137): state-aware, accepts waiting_question

**Hierarchy Section (lines 629-788):**
- ParentPicker: search, select, remove parent
- DependencyPicker: add/remove dependencies
- Type badge + Promote button
- Goal-specific children progress + graph

**Key integration points:**
- waiting_question handled in ChatInput (line 1126)
- Editing form overlay (TaskForm component, lines 1163-1185)
- Esc key closes modal (lines 830-845)
- Search params integration (lines 630, 676-684)

### 6. Feature Detail — What Should Be Different

Feature detail must mirror Task detail but with scope adjustments:

**Reuse:**
- Modal wrapper, header badges, tab bar structure
- ConversationStream (features also have history)
- ChatInput with waiting_question (FeatureRead includes waiting_question per 2026-06-08 fix)
- Brief/description display

**Omit/Modify:**
- **Agent controls** (priority/mode/model dropdowns): features don't have agent_mode/agent_model (lines 957-1006 in Detail.tsx)
- **Hierarchy section** (parent/depends_on/promote): features are independent units; may not apply the same way
- **PR/Issue linking**: features have issue_url/proposed_issue_path instead of pr_url; need different section
- **Stats/Trace tabs**: may not apply; features may focus on state/decomposition instead

**Feature-specific sections needed:**
- Feature-state transition UI (mirroring TaskState drag-drop but for FeatureState: backlog → processing → planned → done)
- realizing_items list (tasks that implement this feature)
- feature_key display (e.g., "ENG-123")
- Process button (POST /api/features/{id}/process) for decomposition trigger

### 7. Implementation Dependencies — Dependency Graph

**Frontend changes required (sequential):**
1. Add `api.getFeature` + `api.patchFeature` to frontend/src/api.ts (2 lines)
2. Add `useFeature` + `useUpdateFeature` hooks to frontend/src/hooks/useFeatures.ts (~25 lines)
3. Create `FeatureDetail.tsx` modal component mirroring Detail.tsx pattern (~400-600 lines, feature-specific)
4. Wire FeaturesBoard.tsx to call setDetailId on card click + inject FeatureDetail modal (lines 252, 266, + new state + modal JSX)
5. Optionally: add feature-specific sub-components (e.g., FeatureStateCard, RealizingItemsList)

**Backend:**
- All 4 endpoints exist and are production-ready
- FeatureRead schema includes waiting_question (merged 2026-06-08)
- No backend changes required

**Testing:**
- Frontend tests: Detail.tsx has inline patterns (DragOverlay, Card interaction, etc.); vitest coverage for FeatureDetail modal interactions
- Backend: S2 tests already cover GET/PATCH endpoints (per memory:project_s2_api_impl)

## Assumptions

- **FeatureDetail mirrors Task Detail structure** — Both are modal overlays with tab-based content layout and mutation-driven state management. Feature scope differs (no agent controls, feature-state-specific transitions) but mechanical pattern is identical.
- **waiting_question now in FeatureRead** — Memory and git log (f02301b) confirm recent fix; safe to rely on for feature detail ChatInput wiring.
- **Triple-key invalidation must include [feature, spaceId]** — Following useFeatures pattern (R4 contract), any feature mutation (edit, state change) must invalidate [features, spaceId] (board), [board, spaceId] (tasks Backlog mirror), and [spaces] (sidebar stats). A fourth key [feature, featureId] will be needed for single-feature refetch after edit.
- **Feature detail is modal-first, not page-first** — Following Board.tsx pattern, detail opens in a side modal via URL searchparam (?feature={id}), not a dedicated /spaces/:spaceId/features/:featureId page.
- **realizing_items is read-only in detail view** — Backend populates realizing_items list from GET /api/features/{id}; detail view displays it but does not edit it via detail modal. The PATCH /api/features/{id}/realize endpoint exists but is separate (not in detail panel scope).

## Open questions

- None. All focus areas have been read and mapped to specific file:line citations.

## Next consumer brief

**For analysis agent:**

The feature-detail-view feature must implement a modal detail panel for feature/fix cards, mirroring the Task detail pattern established in Detail.tsx but adapted for feature-specific fields (feature_state, feature_key, realizing_items, waiting_question).

**Key decision points:**

1. **Modal vs page?** Current Board pattern uses modal + URL searchparam (?task={id}). Recommend same for features: FeaturesBoard stores detailId in searchParams, injects FeatureDetail modal.
2. **Agent controls needed?** FeatureRead schema does not include agent_mode/agent_model fields (per models.py:199-225). Detail view should omit Priority/Mode/Model dropdowns. Feature state (backlog/processing/planned/waiting/done) is the primary control.
3. **Hierarchy section?** Features are not hierarchical (no parent_id field in FeatureRead). Omit parent picker and promote button.
4. **Tabs to include?** Recommend: details (brief, feature-state, realizing-items, waiting_question section), maybe conversation (if features log history like tasks). Omit stats/trace (agent-specific). Include files if feature descriptions reference assets.
5. **Realizing items interaction?** Backend provides realizing_items list. Detail view displays as read-only section; link/unlink is POST /api/features/{id}/realize (separate workflow, not in detail panel).

**Traceability:**

- Missing API methods: frontend/src/api.ts:402-423 — need getFeature, patchFeature
- Missing hooks: frontend/src/hooks/useFeatures.ts — need useFeature, useUpdateFeature
- Dead handler: frontend/src/components/FeaturesBoard.tsx:252 — onOpen={() => {}} to be wired
- Reference pattern: frontend/src/components/Detail.tsx (full 1189 lines) + frontend/src/components/Board.tsx:74-89, 318
- Backend ready: backend/app/api/features.py:180-327, backend/app/models.py:199-225

**Blocked by:** None. All backend API exists. Frontend can proceed immediately with API method + hook + component additions.
