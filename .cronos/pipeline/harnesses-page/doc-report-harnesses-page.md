---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: harnesses-page
phase: doc
status: done
confidence: 0.92
inputs_used:
  - .cronos/pipeline/harnesses-page/scout-report-harnesses-page.md
  - frontend/src/pages/HarnessListPage.tsx
  - frontend/src/hooks/useHarnesses.ts
  - frontend/src/router.tsx
  - frontend/src/components/Sidebar.tsx
  - CLAUDE.md
outputs_produced:
  - .cronos/pipeline/harnesses-page/doc-report-harnesses-page.md
  - CLAUDE.md
blockers: []
next_consumer: user
intentionally_not_updated:
  - path: README.md
    reason: "Quick-start and architecture overview remain unchanged. Harnesses feature is transparent to deployment and dev workflow."
  - path: TESTING.md
    reason: "Testing guide is general-purpose. HarnessListPage follows existing React component test patterns; no testing methodology changes required."
  - path: deploy/VPS_SETUP.md
    reason: "Deployment unchanged. No new environment variables, ports, or service configuration introduced."
metrics:
  tool_calls: 5
  files_read: 6
  memory_hits: 0
  docs_updated: 1
  docs_considered: 4
---

## Summary

Harnesses-page implements a top-level landing page at `/spaces/:spaceId/harnesses` with harness card grid, create/edit/runs/delete actions, and modal dialogs. Frontend-only feature slice with no backend changes. Documentation updates are minimal and concentrated in CLAUDE.md Key modules table, which now includes a new HarnessListPage entry and expands the useHarnesses entry to document create/delete mutations. README.md, TESTING.md, and deploy/VPS_SETUP.md remain accurate and require no updates.

## Updated docs

| File | Change summary |
|------|----------------|
| CLAUDE.md | Added 1 new row to Key modules table: `frontend/src/pages/HarnessListPage.tsx` (harnesses landing page with space picker, card grid, create/edit/runs/delete actions, modals). Updated `frontend/src/hooks/useHarnesses.ts` entry to document `useCreateHarness` and `useDeleteHarness` mutations (previously only listed query hooks). |

## Intentionally not updated

- **README.md** — Quick-start and architecture overview remain unchanged. Harnesses feature is transparent to deployment and dev workflow.
- **TESTING.md** — Testing guide is general-purpose. HarnessListPage follows existing React component test patterns; no testing methodology changes required.
- **deploy/VPS_SETUP.md** — Deployment unchanged. No new environment variables, ports, or service configuration introduced.

## Assumptions

- Implementation scope per task brief: `frontend/src/pages/HarnessListPage.tsx` (new), `frontend/src/router.tsx` (route wired), `frontend/src/hooks/useHarnesses.ts` (mutations added), Sidebar harness link already present (conditional on spaceId). No backend changes; all APIs pre-existing from arc6.
- CLAUDE.md Key modules table is the sole user-facing architecture reference requiring updates.
- Changed file union: `frontend/src/pages/HarnessListPage.tsx` (new, 292 lines), `frontend/src/hooks/useHarnesses.ts` (enhanced with mutations), `frontend/src/router.tsx` (route import/registration). CLAUDE.md is the sole documentation artifact.

## Open questions

- None.

## Next consumer brief

All documentation updates have been applied to CLAUDE.md. User-facing summary:

**New harnesses landing page (harnesses-page):**
- **HarnessListPage** (`frontend/src/pages/HarnessListPage.tsx`) renders at `/spaces/:spaceId/harnesses` and provides:
  - Card grid with per-harness overview: name, description, node/edge/variable counts, last-modified date.
  - Actions per card: View Runs (links to `/spaces/:spaceId/harnesses/:name/runs`), Edit (links to `/spaces/:spaceId/harnesses/:name/edit`), Delete (with confirmation modal).
  - "New harness" button and modal dialog for harness creation (name + optional description).
  - Delete confirmation modal.
  - Loading state with spinner; error display on API failure; empty state with CTA.
- **useHarnesses** hook now includes `useCreateHarness` and `useDeleteHarness` mutations (alongside existing `useHarnesses` list query, `useHarness` single fetch, and `useSaveHarness` PUT mutation). All mutations use standard TanStack Query patterns with isPending/isError flags.

**Route wiring:**
- `frontend/src/router.tsx` imports HarnessListPage and registers route `<Route path="spaces/:spaceId/harnesses" element={<HarnessListPage />} />` before the existing `:name/runs` and `:name/edit` routes.

**Sidebar integration:**
- Sidebar (App.tsx root layout) already displays "Harnesses" nav link pointing to `/spaces/:spaceId/harnesses` when a spaceId is in context (conditional rendering).

**No user-visible backend changes; harness creation/deletion use pre-existing POST /api/harnesses and DELETE /api/harnesses/{name} endpoints.**
