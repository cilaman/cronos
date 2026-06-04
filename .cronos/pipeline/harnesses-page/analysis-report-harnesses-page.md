---
cc_version: '1.0'
agent: pipeline-analyst
slug: harnesses-page
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:project_harness_list_page
- memory:project_arc6_merge_to_main
- .cronos/pipeline/harnesses-page/scout-report-harnesses-page.md
- frontend/src/components/Sidebar.tsx
- frontend/src/router.tsx
- frontend/src/pages/HarnessListPage.tsx
outputs_produced:
- .cronos/pipeline/harnesses-page/analysis-report-harnesses-page.md
blockers: []
next_consumer: design
request: 'Harnesses landing page + sidebar nav.

  Decompose the feature into testable requirements:

  1. Sidebar always shows "Harnesses" link (remove spaceId gate)

  2. New /harnesses route accessible to all users

  3. HarnessesPage component with space selector (dropdown or list)

  4. When a space is selected, shows its harnesses using existing HarnessCard-like
  pattern

  5. New harness creation navigates to the editor

  6. Each harness card has Edit and Runs buttons

  7. Empty state when no spaces or no harnesses

  8. Mobile-responsive design consistent with existing pages

  Scope: frontend/src/components/Sidebar.tsx, frontend/src/router.tsx, new frontend/src/pages/HarnessesPage.tsx

  '
has_ui: true
coverage_summary:
  searched:
  - frontend/src/components/Sidebar.tsx
  - frontend/src/router.tsx
  - frontend/src/pages/HarnessListPage.tsx
  - .cronos/pipeline/harnesses-page/scout-report-harnesses-page.md
  excluded:
  - backend/: pure frontend feature, no API changes required
  - frontend/src/hooks/useHarnesses.ts: covered by scout; no additional reads needed
  - frontend/src/hooks/useSpaces.ts: covered by scout; hook signatures confirmed
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: The Sidebar renders a 'Harnesses' NavLink unconditionally, not gated
    on spaceId, routing to /harnesses.
  acceptance_criteria:
  - Given the user is on any page (with or without spaceId in the URL), when the sidebar
    is visible, then the 'Harnesses' nav link is present in the DOM.
  - Given the user is on the /harnesses page, the 'Harnesses' nav link shows the active
    indicator (ActiveStrip component).
  - The spaceId && guard at Sidebar.tsx:176 is removed; NavLink target changes from
    /spaces/${spaceId}/harnesses to /harnesses.
  verifying_phase: review
  confidence: 0.97
- requirement_id: R2
  statement: A /harnesses route is registered in AppRoutes and renders HarnessesPage.
  acceptance_criteria:
  - Given no spaceId in the URL, when the user navigates to /harnesses, HarnessesPage
    renders without a 404 or crash.
  - The route entry appears alongside other global routes (board, archived, tools,
    memory, stats) in router.tsx.
  - HarnessesPage is imported and wired in router.tsx; lazy loading is optional but
    consistent with HarnessEditor pattern.
  verifying_phase: test
  confidence: 0.97
- requirement_id: R3
  statement: HarnessesPage renders a space selector (dropdown or pill list) populated
    from useSpaces().
  acceptance_criteria:
  - Given the user navigates to /harnesses and spaces data loads, a space selector
    displays all available spaces by name.
  - Given spaces are loading, the selector area shows a loading indicator.
  - Given useSpaces() returns an error, the selector area shows an error message rather
    than crashing.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: Selecting a space in the selector fetches and displays that space's harnesses
    via useHarnesses(spaceId).
  acceptance_criteria:
  - Given the user selects a space, when the selection changes, harnesses for that
    space are fetched and rendered as cards.
  - Given only one space exists, that space is auto-selected on page load so the user
    sees harnesses immediately.
  - Given harnesses are loading after a space selection, a loading spinner is shown
    in the harness list area.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R5
  statement: Creating a new harness from HarnessesPage navigates to the harness editor
    upon success.
  acceptance_criteria:
  - Given a space is selected, when the user clicks '+ New harness', submits a valid
    name, and the POST succeeds, then the app navigates to /spaces/:spaceId/harnesses/:name/edit.
  - Given no space is selected, the '+ New harness' button is disabled or absent.
  - The create flow reuses the existing CreateHarnessModal pattern (name required,
    description optional).
  verifying_phase: test
  confidence: 0.92
- requirement_id: R6
  statement: Each harness card on HarnessesPage includes 'Edit' and 'Runs' buttons
    that navigate to the correct space-scoped routes.
  acceptance_criteria:
  - Clicking 'Edit' on a card navigates to /spaces/:spaceId/harnesses/:name/edit (encodeURIComponent
    applied to name).
  - Clicking 'Runs' on a card navigates to /spaces/:spaceId/harnesses/:name/runs (encodeURIComponent
    applied to name).
  - HarnessCard (or an equivalent inline implementation) is reused from HarnessListPage
    with spaceId passed as a prop.
  verifying_phase: review
  confidence: 0.95
- requirement_id: R7
  statement: HarnessesPage shows distinct empty states for (a) no spaces and (b) a
    selected space with no harnesses.
  acceptance_criteria:
  - Given useSpaces() returns an empty array, HarnessesPage shows a 'No spaces yet'
    message with guidance to create a space.
  - Given a space is selected and useHarnesses(spaceId) returns an empty array (not
    loading), HarnessesPage shows a 'No harnesses in this space' message and a '+
    New harness' affordance.
  - Neither empty state shows a broken grid or undefined-related UI artifacts.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R8
  statement: HarnessesPage layout is mobile-responsive, matching the visual conventions
    of HarnessListPage.
  acceptance_criteria:
  - The harness card grid uses responsive column classes (e.g., grid-cols-1 lg:grid-cols-2)
    consistent with HarnessListPage.
  - The space selector is touch-friendly and usable on small viewports (appropriate
    min-height, tap targets ≥ 44px).
  - Page header typography and button styling match HarnessListPage (font-display,
    tracking, accent colors).
  verifying_phase: review
  confidence: 0.85
metrics:
  tool_calls: 7
  files_read: 4
  memory_hits: 2
---

## Summary

This feature adds a global harnesses landing page (`/harnesses`) accessible from the sidebar without requiring a space context. It replaces the current `spaceId`-gated sidebar link with an unconditional link, adds a new route, and introduces a new `HarnessesPage` component that lets users pick a space and browse its harnesses — reusing the existing `HarnessCard`, `CreateHarnessModal`, and data hooks (`useHarnesses`, `useSpaces`) from Arc 6 with minimal duplication.

## Scope

### In scope
- Remove `spaceId` gate from Sidebar's Harnesses NavLink; change target to `/harnesses`
- Register `/harnesses` route in `AppRoutes` pointing to `HarnessesPage`
- `HarnessesPage` component: space selector, harness card list (reusing HarnessCard pattern), create modal, empty states
- Auto-select single space on load
- Mobile-responsive layout consistent with `HarnessListPage`

### Out of scope
- Cross-space harness aggregation (all harnesses from all spaces in one flat list) — requires backend aggregation endpoint
- Search/filter across spaces
- Harness delete from the landing page (keep that at the space-scoped `/spaces/:spaceId/harnesses` page to avoid accidental mass deletes)
- Backend API changes

### Deferred
- Cross-space search/filter view (Scout Option 2) — future enhancement once user feedback on single-space view is collected
- Breadcrumb or back-navigation from landing page to space board

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Sidebar Harnesses link is unconditional (no spaceId gate), routes to /harnesses |
| R2 | /harnesses route registered in AppRoutes and renders HarnessesPage |
| R3 | HarnessesPage shows a space selector from useSpaces() |
| R4 | Selecting a space loads and displays its harnesses via useHarnesses(spaceId) |
| R5 | New harness creation from HarnessesPage navigates to the editor on success |
| R6 | Each harness card has Edit and Runs buttons with correct space-scoped URLs |
| R7 | Distinct empty states for no-spaces and no-harnesses conditions |
| R8 | Mobile-responsive layout matching HarnessListPage conventions |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — Harnesses NavLink present in sidebar on all pages; active indicator correct on /harnesses
- R2 — /harnesses route resolves without 404; HarnessesPage renders
- R3 — Space selector populated from useSpaces(); loading and error states handled
- R4 — Selecting space triggers useHarnesses(); single-space auto-selects on load
- R5 — Successful create → navigate to /spaces/:spaceId/harnesses/:name/edit; button absent when no space selected
- R6 — Edit/Runs buttons navigate to correct encodeURIComponent-safe URLs
- R7 — "No spaces" message when spaces empty; "No harnesses" message when selected space is empty
- R8 — Responsive grid cols; touch-friendly space selector; header/button styling consistent

## Traceability

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | review | Sidebar renders Harnesses link unconditionally, routing to /harnesses |
| R2 | test | /harnesses route in AppRoutes renders HarnessesPage |
| R3 | test | HarnessesPage renders space selector from useSpaces() with loading/error states |
| R4 | test | Selecting a space fetches and displays harnesses; single space auto-selects |
| R5 | test | New harness creation navigates to editor; button gated on space selection |
| R6 | review | Edit and Runs buttons navigate to correct space-scoped, URL-encoded routes |
| R7 | review | Distinct empty states for no-spaces and no-harnesses conditions |
| R8 | review | Mobile-responsive layout matching HarnessListPage visual conventions |

## Assumptions

- Arc 6 (harnesses) is stable and merged to main (confirmed by memory and scout: commit d878799, 2026-06-04).
- `HarnessCard` remains in `HarnessListPage.tsx` and can be imported from that module; no extraction to a shared component file is required unless the design agent deems it cleaner.
- The existing `/spaces/:spaceId/harnesses` route and `HarnessListPage` stay untouched — the new landing page is additive, not a replacement.
- `has_ui: true` — every requirement involves visible React components, a nav link change, and user interaction through a browser.
- Auto-selecting the single space (R4 acceptance criterion 2) is a UX convenience, not a hard requirement if the design agent finds it awkward to implement; the design agent may defer this to a follow-up.
- Harness delete is intentionally excluded from the landing page (scoped to the space-specific page) to reduce surface area and avoid UX ambiguity about which space the delete targets.

## Open questions

- Should the `/harnesses` route also remain usable when navigated to directly with no spaces (the "no spaces" empty state is specified, but it may be better UX to redirect to `/spaces/new`)?
- Should the `HarnessCard` component be extracted from `HarnessListPage.tsx` into a shared `components/harness/HarnessCard.tsx`, or should `HarnessesPage` import it from the existing page file? Design agent can decide.

## Next consumer brief

**To: pipeline-architect**

Read `traceability[]` for the full requirement list (R1–R8) and `## Scope` for hard boundaries. Key points:

- **Two file changes** (Sidebar.tsx, router.tsx) and **one new file** (`HarnessesPage.tsx`) — design should map each R to one of these files.
- **R1** is a one-line change in Sidebar.tsx (remove `{spaceId && ...}` wrapper, change route target). Design can handle this as a micro-iteration.
- **R3/R4 dependency**: space selector state (`selectedSpaceId`) drives the `useHarnesses` call — design must wire a controlled component pattern (useState or URL search params for deep-linkability).
- **HarnessCard reuse question** (see Open questions): design agent should decide whether to import from `HarnessListPage` or extract to shared component; both are valid.
- **R5 create flow** requires the selected `spaceId` to be available in scope when the modal submits — design must ensure `useCreateHarness(selectedSpaceId)` receives a non-null value.
- **Auto-select single space (R4)**: implement as a `useEffect` that fires when `spaces.length === 1 && selectedSpaceId === null`.
- Risk: if `HarnessCard` is not exported from `HarnessListPage.tsx`, the implementor will need to either export it or inline an equivalent — scout confirmed it is a named function in that file (not exported). Design should call this out as a scope decision.
