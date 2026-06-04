---
cc_version: '1.0'
agent: pipeline-architect
slug: harnesses-page
phase: design
status: done
confidence: 0.9
inputs_used:
- memory:project_harness_list_page
- memory:project_arc6_merge_to_main
- .cronos/pipeline/harnesses-page/analysis-report-harnesses-page.md
- .cronos/pipeline/harnesses-page/scout-report-harnesses-page.md
- frontend/src/components/Sidebar.tsx
- frontend/src/router.tsx
- frontend/src/pages/HarnessListPage.tsx
- frontend/src/hooks/useHarnesses.ts
- frontend/src/hooks/useSpaces.ts
- frontend/src/types.ts
- frontend/package.json
outputs_produced:
- .cronos/pipeline/harnesses-page/design-report-harnesses-page.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/components/Sidebar.tsx
  - frontend/src/router.tsx
  - frontend/src/pages/HarnessListPage.tsx
  - frontend/src/hooks/useHarnesses.ts
  - frontend/src/hooks/useSpaces.ts
  - frontend/src/types.ts
  - frontend/src/pages/__tests__/
  excluded:
  - 'backend/: no backend changes needed (analyst confirmed)'
  - 'frontend/src/api.ts: existing harness/space endpoints reused verbatim'
  - 'frontend/src/pages/HarnessListPage.tsx (edit): out of analyst scope; inline an
    equivalent card instead of refactoring/exporting'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: frontend
  scope_files:
  - frontend/src/pages/HarnessesPage.tsx
  validation_command: cd frontend && npx tsc -b
  max_diff_lines: 350
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/src/components/Sidebar.tsx
  validation_command: cd frontend && npx tsc -b
  max_diff_lines: 50
  depends_on: []
- id: I3
  type: frontend
  scope_files:
  - frontend/src/router.tsx
  validation_command: cd frontend && npx tsc -b
  max_diff_lines: 30
  depends_on:
  - I1
- id: I4
  type: frontend
  scope_files:
  - frontend/src/pages/__tests__/HarnessesPage.test.tsx
  validation_command: cd frontend && npx vitest run src/pages/__tests__/HarnessesPage.test.tsx
  max_diff_lines: 400
  depends_on:
  - I1
  - I2
  - I3
risks:
- description: HarnessCard is a non-exported inner function of HarnessListPage.tsx,
    which the analyst placed out of scope for editing. Inlining a duplicate card in
    HarnessesPage.tsx risks visual drift between the two pages if HarnessListPage's
    card is later restyled.
  severity: medium
  mitigation: I1 must inline the card with the exact same Tailwind class strings as
    HarnessListPage.tsx lines 34-83 (verbatim copy of markup). Add a brief code comment
    naming the source-of-truth file so future restyles update both. A follow-up extraction
    iteration (out of this design's scope) can later move both call sites to frontend/src/components/harness/HarnessCard.tsx.
- description: URL-driven space selection (?space=:spaceId) and localStorage-driven
    default can fight each other on first navigation, producing a flash or wrong selection
    if both signals exist.
  severity: low
  mitigation: 'I1 must implement a single deterministic precedence: (1) ?space query
    param wins if present and resolves to a known space, (2) else last-used spaceId
    from localStorage if it resolves to a known space, (3) else first space from useSpaces()
    data, (4) else null (empty-state). Changing the selector writes localStorage and
    replaces (not pushes) the URL query param so back-button behavior is intuitive.'
- description: useSpaces() polls every 10s; an unstable identity of the spaces array
    could cause the auto-select effect to overwrite a user's manual change on the
    next refetch.
  severity: medium
  mitigation: I1 must gate the auto-select effect on selectedSpaceId === null (only
    set when nothing is selected), not on spaces.length or array identity. Manual
    selection by the user transitions selectedSpaceId to a non-null value, which permanently
    disarms the auto-select branch for that mount.
- description: Tests rely on mocking useSpaces / useHarnesses / useCreateHarness;
    if mocked hook return shapes drift from real hook return shapes (TanStack Query
    useQueryResult fields), the tests pass but the production page crashes.
  severity: low
  mitigation: I4 mocks must return objects with the same field set the page actually
    destructures (data, isLoading, isError, error). I1 must destructure only these
    documented fields (no internal TanStack fields) and tolerate undefined data via
    ?? fallbacks.
metrics:
  tool_calls: 9
  files_read: 9
  memory_hits: 2
  iterations_planned: 4
---

## Summary

This design adds a global `/harnesses` landing page that picks a space (controlled state, hydrated from URL search param then localStorage then first-space fallback) and renders that space's harnesses as inline cards, with a create modal that navigates to the editor on success. The sidebar Harnesses NavLink loses its `spaceId` gate so the link is always visible. The DAG is wide: I1 (HarnessesPage) and I2 (Sidebar) run in parallel layer 0; I3 (router wiring) depends only on I1; I4 (test suite) joins all three. No backend changes; no existing components edited beyond the two explicit Sidebar/router lines. The main tradeoff captured in the risk register is inlining a HarnessCard duplicate (rather than extracting a shared component) to keep `HarnessListPage.tsx` out of scope as the analyst directed.

## Components

### Data
- No data-layer changes. Existing `Harness`, `SpaceSummary`, `HarnessNode`, `HarnessEdge` types in `frontend/src/types.ts` are sufficient.

### Backend
- No backend changes. Existing endpoints reused: `GET /api/spaces` (via `useSpaces`), `GET /api/spaces/{spaceId}/harnesses` (via `useHarnesses`), `POST /api/spaces/{spaceId}/harnesses` (via `useCreateHarness`).

### Frontend
- `frontend/src/pages/HarnessesPage.tsx` (NEW): global `/harnesses` landing page. State: `selectedSpaceId` (`useState<string | null>`), `showCreate` (`useState<boolean>`). Reads `?space=` via `useSearchParams`. Persists last selection to `localStorage` key `cronos.harnesses.lastSpaceId`. Pre-select precedence: URL query → localStorage → single-space auto-select → first-space fallback → null. Renders header, space selector (`<select>` styled to match Tailwind tokens, touch-friendly min-h-9), harness card grid (inline card markup duplicated verbatim from `HarnessListPage.tsx:34-83` with a "source of truth" code comment), `+ New harness` button (disabled until `selectedSpaceId` is non-null), `CreateHarnessModal` (inline duplicate of the modal in `HarnessListPage.tsx:103-159`, or a freshly written equivalent — implementor's choice as long as it reuses the same Tailwind class strings), and three distinct empty states (loading spaces, no spaces, no harnesses in selected space).
- `frontend/src/components/Sidebar.tsx` (EDIT): remove `{spaceId && (...)}` wrapper at lines 176-189; change NavLink `to` from `` `/spaces/${spaceId}/harnesses` `` to the literal `"/harnesses"`. Drop the `useParams<{ spaceId: string }>()` call and the unused `spaceId` local (line 101) — the only consumer was the gate. The NavLink keeps `primaryNavLinkClasses` styling and the `ActiveStrip` active-state indicator.
- `frontend/src/router.tsx` (EDIT): add `import { HarnessesPage } from "./pages/HarnessesPage";` and register `<Route path="harnesses" element={<HarnessesPage />} />` as a sibling of `<Route path="board" .../>` (alphabetically sensible position; not lazy — page is small and on the primary nav). Do NOT remove the existing `<Route path="spaces/:spaceId/harnesses" element={<HarnessListPage />} />` — both routes coexist.
- `frontend/src/pages/__tests__/HarnessesPage.test.tsx` (NEW): vitest suite mocking `useSpaces`, `useHarnesses`, `useCreateHarness`, and `useNavigate`. Cases: (a) renders space selector with all spaces from useSpaces, (b) auto-selects when exactly one space exists, (c) URL `?space=foo` pre-selects when foo exists, (d) localStorage value pre-selects when no URL param, (e) selecting a space triggers useHarnesses with that id, (f) renders harness cards with Edit/Runs buttons routing to correct `/spaces/:spaceId/harnesses/:name/{edit|runs}` URLs (use `encodeURIComponent` check), (g) `+ New harness` is disabled when `selectedSpaceId === null`, (h) successful create navigates to `/spaces/:spaceId/harnesses/:name/edit`, (i) "No spaces yet" empty state when `useSpaces()` data is empty, (j) "No harnesses in this space" empty state when selected space's list is empty, (k) loading state shown while spaces or harnesses are loading, (l) error state shown when `useHarnesses` errors.

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                         | Validation                                                                          |
|-----|----------|------------|----------------------------------------------------------------|-------------------------------------------------------------------------------------|
| I1  | frontend | -          | frontend/src/pages/HarnessesPage.tsx                           | cd frontend && npx tsc -b                                                           |
| I2  | frontend | -          | frontend/src/components/Sidebar.tsx                            | cd frontend && npx tsc -b                                                           |
| I3  | frontend | I1         | frontend/src/router.tsx                                        | cd frontend && npx tsc -b                                                           |
| I4  | frontend | I1, I2, I3 | frontend/src/pages/__tests__/HarnessesPage.test.tsx            | cd frontend && npx vitest run src/pages/__tests__/HarnessesPage.test.tsx            |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| HarnessCard is a non-exported inner function of HarnessListPage.tsx; inlining a duplicate risks visual drift. | medium | Copy markup verbatim from HarnessListPage.tsx:34-83; add a source-of-truth comment; schedule extraction follow-up. |
| URL search param + localStorage may fight on first navigation. | low | Deterministic precedence: URL → localStorage → first-space → null. Manual select writes localStorage and replaces (not pushes) URL. |
| useSpaces polls every 10s; auto-select effect could overwrite a manual change on refetch. | medium | Gate auto-select effect on `selectedSpaceId === null` only; never re-run once a user has chosen. |
| Mock hook shapes in I4 may drift from real TanStack Query return objects. | low | I4 mocks return only the documented destructured fields; I1 destructures only `{ data, isLoading, isError, error }` and tolerates undefined data via `?? []`/`?? null`. |

## Assumptions

- HarnessCard styling and CreateHarnessModal markup in `HarnessListPage.tsx` (lines 20-83 and 86-160) is the canonical visual reference; copying its Tailwind class strings verbatim is acceptable for this design slice.
- `useNavigate()` from `react-router-dom` is the correct programmatic navigation hook (matches HarnessListPage's pattern); no `<Link>`-only convention applies.
- `localStorage` is acceptable for "last used space" persistence (no SSR; cronos is a SPA per scout findings); no need for a backend `last_used_space_id` user-preference field in this design.
- The existing `/spaces/:spaceId/harnesses` route + `HarnessListPage` are retained unchanged; they remain reachable via the per-space row in the Sidebar (Tree-view button at line 69 is sibling navigation, no edit needed).
- `cd frontend && npx tsc -b` will exit non-zero on any type error in the touched file (the project's `npm run build` is `tsc -b && vite build`, confirming `tsc -b` is the canonical type gate).
- Vitest is the project's test runner (`npm test === vitest run` per `frontend/package.json`); filtering by file path is supported via `vitest run <path>`.

## Open questions

- Should `selectedSpaceId === null` on a fresh visit (no URL param, no localStorage, multiple spaces) auto-select the first space, or show an explicit "pick a space" prompt? Design choice in I1: auto-select first space (analyst R4 acceptance criterion #2 covers the single-space case; extending to multi-space is the cleaner UX given the empty-state alternative shows nothing actionable). Implementor may flip this if they discover a strong reason during build.

## Next consumer brief

Read `iterations[]` (4 entries) and `iterations[].validation_command` first — those are the hard contracts. Cross-iteration invariants the YAML cannot capture: (1) the inline harness card markup in I1 MUST be a verbatim copy of `HarnessListPage.tsx:34-83` Tailwind classes (risk #1 mitigation); (2) the route literal `/harnesses` is shared between I2 (Sidebar NavLink `to` prop) and I3 (router `path`) — these strings must match exactly, including the leading slash on the NavLink and the omission of it on the route child; (3) the localStorage key string is `cronos.harnesses.lastSpaceId` and must be used identically in I1's read effect and write handler (risk #2 mitigation). I3 cannot start until I1 lands the HarnessesPage symbol it imports. I4 cannot start until all three of I1/I2/I3 land, since it integration-tests routing through the Sidebar link as well as the page itself. No open question blocks implementation; the auto-select multi-space default is a soft preference (see Open questions) the implementor may flip if a clear UX argument emerges.
