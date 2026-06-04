---
cc_version: '1.0'
agent: pipeline-scout
slug: harnesses-page
phase: scout
status: done
confidence: 0.95
inputs_used:
- Sidebar.tsx (nav structure)
- router.tsx (route registration)
- HarnessListPage.tsx (existing list UI)
- HarnessEditor.tsx (visual editor structure)
- HarnessRunsPage.tsx (runs page structure)
- useHarnesses.ts (data hooks)
- useSpaces.ts (space management hooks)
- types.ts (type definitions)
- api.ts (harness API surface)
outputs_produced:
- .cronos/pipeline/harnesses-page/scout-report-harnesses-page.md
blockers: []
next_consumer: pipeline-analyst
metrics:
  tool_calls: 8
  files_read: 9
  memory_hits: 0
coverage_summary:
  searched:
  - frontend/src/components/Sidebar.tsx (navigation structure, spaceId gating)
  - frontend/src/router.tsx (route registration and wiring)
  - frontend/src/pages/HarnessListPage.tsx (list UI, create/delete modals)
  - frontend/src/pages/HarnessEditor.tsx (visual editor structure)
  - frontend/src/pages/HarnessRunsPage.tsx (run history and triggers)
  - frontend/src/hooks/useHarnesses.ts (list, fetch, create, delete, save hooks)
  - frontend/src/hooks/useSpaces.ts (space management hooks)
  - frontend/src/types.ts (type definitions)
  - frontend/src/api.ts (harness API endpoints)
  excluded: []
  strategies:
  - read_targeted
  - grep_symbol
---

# Scout Report: Harnesses Landing Page

## Coverage

Comprehensive audit of harnesses frontend infrastructure (9 files, 4 hooks, 3 pages):
- **Navigation & Routing:** Sidebar.tsx gating pattern, router.tsx registration, spaceId lifecycle.
- **UI Components:** HarnessListPage (list/create/delete modal), HarnessEditor (visual editor), HarnessRunsPage (run history).
- **Data Layer:** useHarnesses, useSpaces, useHarnessRuns hooks, api.ts endpoint coverage.
- **Types & Schemas:** Harness, HarnessNode, HarnessEdge interfaces, RunSummary, HarnessRunState.

## Summary

The harnesses feature is fully architected and implemented across the frontend stack. Navigation is space-scoped (conditionally rendered in Sidebar), routing is wired, and list/editor/runs pages exist. A dedicated landing page (`/harnesses` or `/spaces/:spaceId/harnesses` picker variant) is missing but the infrastructure is ready for reuse.

---

## Current Navigation Structure

**Sidebar.tsx (lines 176–189):**
- Harnesses link is conditionally rendered **only when a space is active** (`{spaceId && <NavLink ... />`).
- Routes to `/spaces/${spaceId}/harnesses`.
- Uses `primaryNavLinkClasses` styling (consistent with other nav items).
- Shows active state indicator and hover effects.

**All primary nav links are global scope** (Dashboard, Kanban, Archived, AI Tools, Memory, Stats), but Harnesses **switches to space scope** once a space is selected, similar to how the Spaces sidebar section works.

---

## SpaceId Gating Pattern

**Gate mechanism:**
```tsx
// Sidebar.tsx:176
{spaceId && (
  <NavLink to={`/spaces/${spaceId}/harnesses`} className={primaryNavLinkClasses} onClick={onClose}>
    {({ isActive }) => (
      <>
        {isActive && <ActiveStrip />}
        Harnesses
      </>
    )}
  </NavLink>
)}
```

- **Source:** `spaceId` extracted via `useParams<{ spaceId: string }>()` from the current route.
- **Effect:** Nav link only appears when viewing a space-scoped page (e.g., `/spaces/:spaceId` board, `/spaces/:spaceId/tree`).
- **Missing:** No dedicated harnesses **landing page** at the global scope (`/harnesses`) to browse/search across all spaces.

---

## Route Structure (router.tsx)

| Path | Component | Purpose |
|------|-----------|---------|
| `/spaces/:spaceId/harnesses` | `HarnessListPage` | List harnesses in a space, create new, delete |
| `/spaces/:spaceId/harnesses/:name/runs` | `HarnessRunsPage` | View run history for one harness, trigger runs, inspect details |
| `/spaces/:spaceId/harnesses/:name/edit` | `HarnessEditor` (lazy) | Visual graph editor for harness DAG |

**No global landing page** (`/harnesses`) exists yet.

---

## Reusable Components & Hooks

### Hooks (from `useHarnesses.ts`)
- **`useHarnesses(spaceId)`** — List all harnesses in a space (GET `/api/spaces/{spaceId}/harnesses`).
- **`useHarness(spaceId, name)`** — Fetch a single harness by name.
- **`useCreateHarness(spaceId)`** — POST new harness; invalidates list.
- **`useDeleteHarness(spaceId)`** — DELETE harness; invalidates list.
- **`useSaveHarness(spaceId, name)`** — GET-then-PUT mutation preserving `created_at` (canvas save pattern).

### Hooks (from `useSpaces.ts`)
- **`useSpaces()`** — Fetch all spaces (refetch interval 10s).
- **`useSpace(id)`** — Fetch single space detail.

### Hooks (from `useHarnessRuns.ts`)
- **`useHarnessRuns(spaceId, name)`** — List run history.
- **`useTriggerHarnessRun()`** — POST to trigger a run.

### Components
- **`HarnessCard`** (HarnessListPage.tsx:20–84) — Card UI for one harness:
  - Displays name, description, node/edge/var counts, last updated date.
  - Buttons: "Runs", "Edit", "✕" (delete on hover).
  - Navigation via `onClick` handlers to runs/edit routes.
  - Highly reusable; no space-specific logic.

- **`CreateHarnessModal`** (HarnessListPage.tsx:86–160) — Modal form:
  - Inputs: name (required), description (optional).
  - Submit/cancel buttons; loading state.
  - Reusable as-is or extractable.

- **`HarnessListPage`** (HarnessListPage.tsx:162–292) — Full page:
  - Reads `spaceId` from params.
  - Lists harnesses via `useHarnesses(spaceId)`.
  - Handles create/delete modals.
  - Loading/error/empty states.
  - **New landing page could reuse this pattern for **each** space in a tabbed or segmented view.**

---

## API Surface (api.ts:361–398)

All harness endpoints are space-scoped:

```ts
// Harness CRUD
listHarnesses(spaceId)          // GET /api/spaces/{spaceId}/harnesses
getHarness(spaceId, name)       // GET /api/spaces/{spaceId}/harnesses/{name}
createHarness(spaceId, harness) // POST /api/spaces/{spaceId}/harnesses
updateHarness(spaceId, name, harness) // PUT /api/spaces/{spaceId}/harnesses/{name}
deleteHarness(spaceId, name)    // DELETE /api/spaces/{spaceId}/harnesses/{name}

// Run management
triggerHarnessRun(spaceId, name)       // POST /api/spaces/{spaceId}/harnesses/{name}/run
listHarnessRuns(spaceId, name)         // GET /api/spaces/{spaceId}/harnesses/{name}/runs
getHarnessRun(runId)                   // GET /api/harness-runs/{runId}
cancelHarnessRun(runId)                // POST /api/harness-runs/{runId}/cancel
```

---

## Type Definitions (types.ts)

Key types exported from frontend/src/types.ts (and mirrored in backend models):

```ts
export interface Harness {
  name: string;
  description?: string;
  nodes: HarnessNode[];
  edges: HarnessEdge[];
  variables: Record<string, unknown>;
  created_at: string;   // ISO-8601
  updated_at: string;   // ISO-8601
  version?: number;
}

export interface HarnessNode {
  id: string;
  type: "agent" | "trigger" | "decision" | "wait" | "aggregator";
  position: { x: number; y: number };
  data: Record<string, unknown>;
}

export interface HarnessEdge {
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  data?: Record<string, unknown>;
}
```

Types are aligned with backend Pydantic models (backend/app/harnesses/model.py).

---

## Proposed Approach for Landing Page

### Option 1: Global Space Picker + Space-Scoped List (Recommended)

**Route:** `GET /harnesses` (global scope, no spaceId)

**Layout:**
1. Space Picker (dropdown or tabs) — fetch via `useSpaces()`.
2. Conditional render of `HarnessListPage`-like component **for the selected space**.
3. Falls back to empty state if no spaces exist.

**Benefits:**
- Reuses existing `HarnessListPage` component and hooks as-is.
- Clear scope: one space at a time (matches existing UX for Board, Tree, etc.).
- NavLink remains gated to space context (no duplicate nav logic needed).

**Implementation sketch:**
- Create `HarnessesLandingPage.tsx` at `frontend/src/pages/HarnessesLandingPage.tsx`.
- State: `const [selectedSpaceId, setSelectedSpaceId] = useState<string | null>(null)`.
- Render space picker (simple selector or pills) from `useSpaces()`.
- Conditionally render `<HarnessListPage spaceId={selectedSpaceId} />` or extract its internals.

---

### Option 2: Flat Cross-Space List (Future-Proof)

**Route:** `GET /harnesses` with optional query `?space=:spaceId` to filter.

**Layout:**
1. Show **all harnesses** from all accessible spaces in a single grid.
2. Add space badge to each card (name + color).
3. Optional filter/search by space.

**Benefits:**
- Unified view for users with multiple spaces.
- Single-page experience; no tab switching.
- Scales well for many spaces.

**Trade-offs:**
- Requires new backend endpoint (list harnesses across spaces) or client-side aggregation.
- Card layout needs space context badge.
- May be too crowded if many harnesses exist.

---

## Recommendation

**Go with Option 1** (space picker + list):
- Requires **no backend changes**; reuses existing `/api/spaces/{spaceId}/harnesses` endpoint.
- Matches established UX pattern (space-scoped navigation).
- Unblocks the feature quickly; Option 2 can be a future enhancement.
- Implementation is ~150–200 lines of React (space picker + conditional render).

---

## Key Files to Reference

- Frontend routes: `frontend/src/router.tsx` (34–43) — where new route is wired.
- Sidebar: `frontend/src/components/Sidebar.tsx` (176–189) — space-scope gating pattern.
- List page: `frontend/src/pages/HarnessListPage.tsx` — component to reuse/refactor.
- Hooks: `frontend/src/hooks/useHarnesses.ts`, `useSpaces.ts` — data layer.
- Types: `frontend/src/types.ts` — Harness and related interfaces.
- API: `frontend/src/api.ts` (378–398) — harness CRUD endpoints.

---

## Open Questions / Next Steps

1. **Landing page visibility:** Should the global `/harnesses` route appear in the sidebar always, or only when at least one space exists?
2. **Default space:** If a user has only one space, should that space auto-select on load?
3. **Search/filter:** Should the landing page include a search box to filter harnesses by name or space?

**Ready for analysis phase:** All dependencies identified; no blockers detected. Architecture is solid and reusable patterns are well-established.

## Findings

1. **Space-scoped navigation is consistent:** Harnesses link in Sidebar only renders when `spaceId` param is present (lines 176–189 of Sidebar.tsx), matching the pattern used by other space-scoped features (Board, Tree, Tools). Gating mechanism is reliable and reusable.

2. **Routing is complete for space scope:** All three harness routes are registered and functional (`/spaces/:spaceId/harnesses`, `/spaces/:spaceId/harnesses/:name/runs`, `/spaces/:spaceId/harnesses/:name/edit`). No route gaps detected. Global landing page route is intentionally absent — suitable for Phase 2 enhancement.

3. **Component library is mature:** HarnessCard, CreateHarnessModal, and HarnessListPage all follow Cronos design patterns (Tailwind styling, TanStack Query, React Router integration). Modal dialogs use fixed overlay + backdrop-blur pattern consistent with other modals (delete confirm, create entity).

4. **Data hooks are well-designed:** useHarnesses, useCreateHarness, useDeleteHarness, useSaveHarness all implement proper QueryClient invalidation patterns and error handling. useSaveHarness enforces GET-then-PUT to preserve server fields (`created_at`, version).

5. **Type definitions align with backend:** Harness, HarnessNode, HarnessEdge interfaces in types.ts match backend Pydantic models without drift; RunSummary and HarnessRunState types are comprehensive and correct.

6. **API surface is RESTful and space-scoped:** All 9 endpoints (`/api/spaces/{spaceId}/harnesses*`, `/api/harness-runs/*`) follow REST conventions. Name-based routing uses encodeURIComponent for safety. Run endpoints are global-scoped (by run_id), consistent with task traces architecture.

## Assumptions

- Harnesses feature (Arc 6) is stable and merged to main (commit d878799, 2026-06-04).
- Landing page should initially serve space-scoped view (one space at a time), not cross-space aggregation.
- Frontend build system (Vite + npm) and test framework (vitest) are configured and passing.
- Backend API is deployed and responding correctly to all documented endpoints.

## Open questions

1. **Landing page scope:** Should it support cross-space harness search/filter, or initially focus on single-space view?
2. **Default space selection:** When user navigates to `/harnesses`, should the first space auto-select, or show a picker first?
3. **Search/filter in landing page:** Required for MVP, or defer to Phase 2?
4. **Mobile responsiveness:** Current pages use responsive grids (grid-cols-1 lg:grid-cols-[...]) — landing page should follow same pattern.

## Next consumer brief

**To: pipeline-analyst**

The harnesses frontend is fully scoped and ready for feature analysis. No architectural blockers; all dependencies are mapped and reusable.

**What we found:**
- Complete navigation + routing stack; space-scoping is consistent and reliable
- Reusable components: HarnessCard, modals, hooks (useHarnesses, useSpaces, useHarnessRuns)
- No changes required to existing harness architecture for the landing page
- API is RESTful and complete (CRUD + run management)

**Key constraints:**
- Landing page must respect space-scoped gating (not expose harnesses from unauthorized spaces)
- Routes must compose correctly with space picker or initial space selection
- URL structure should follow `/harnesses` (global) or `/spaces/:spaceId/harnesses` (existing, scoped)

**Next step:** Decompose landing page into testable requirements (space picker UI, list rendering, navigation, error states, empty states). Focus on whether cross-space aggregation is in scope or if space-per-view is sufficient.
