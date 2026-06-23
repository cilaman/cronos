---
cc_version: '1.0'
agent: pipeline-analyst
slug: gui-modal-loading
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:GUI Refactor Board Setup
- memory:gui-tokens-brand RESOLVED
- memory:gui-layout-primitives review RESOLVED
- memory:gui-badge-system review RESOLVED
- memory:gui-button-focus review RESOLVED
- memory:gui-icons review RESOLVED
- .cronos/pipeline/gui-modal-loading/scout-report-gui-modal-loading.md
- frontend/src/components/ui/Modal.tsx
- frontend/src/components/MarkdownEditorModal.tsx
- frontend/src/pages/HarnessListPage.tsx
- frontend/tailwind.config.js
outputs_produced:
- .cronos/pipeline/gui-modal-loading/analysis-report-gui-modal-loading.md
blockers: []
next_consumer: design
request: "GUI modal contract + Skeleton loading states (Phase 5)\n\nEnforces a single\
  \ Modal contract and ships a Skeleton component to eliminate layout\nshift on data\
  \ load. Currently 10 `fixed inset-0` implementations use different scrim\nopacities\
  \ (bg-black/50 to bg-black/80) and inconsistent Escape/close behavior.\nPlain text/spinner\
  \ loaders cause visible layout shift when data arrives.\n\n**Concrete changes:**\n\
  - `Modal.tsx`: enforce the single contract — `bg-black/60` + `backdrop-blur-sm`\
  \ scrim\n  (z-scrim=30), panel z-modal=40, scale-fade entrance at motion-slow(280ms),\n\
  \  Escape key handler, focus-trap (first focusable element on open, return on close),\n\
  \  `dismissable=false` for unsaved-changes guard, single SVG X close button.\n-\
  \ Migrate 4 ad-hoc modal implementations to use Modal.tsx:\n  - MarkdownEditorModal\
  \ (currently bg-black/80, ✕ emoji)\n  - FileViewer (currently bg-black/80, no Escape)\n\
  \  - View-delete dialog (currently bg-black/60)\n  - ToolDetailPanel (currently\
  \ bg-canvas/60)\n- `Skeleton.tsx`: three variants — `text` (single line shimmer),\
  \ `block` (fixed height),\n  `card` (card-shaped with header + rows). Shimmer at\
  \ motion-base(180ms).\n- Replace spinner/text loaders: FeaturesPage spinner, Dashboard\
  \ \"Loading statistics…\"\n  text, HarnessList spinner+text — each replaced with\
  \ reserved-space Skeleton.\n\n**Exit criteria:** one scrim/escape/focus behavior\
  \ across all modals; no layout shift\non data load; `npm run build` + `npm test`\
  \ green.\n\nScope: frontend/src/components/ui/Modal.tsx, frontend/src/components/ui/Skeleton.tsx,\
  \ frontend/src/components/MarkdownEditorModal.tsx, frontend/src/components/FileViewer.tsx,\
  \ frontend/src/pages/FeaturesPage.tsx, frontend/src/pages/Dashboard.tsx, frontend/src/pages/HarnessListPage.tsx,\
  \ frontend/src/components/ToolDetailPanel.tsx"
has_ui: true
coverage_summary:
  searched:
  - frontend/src/components/ui/
  - frontend/src/components/
  - frontend/src/pages/
  - frontend/tailwind.config.js
  excluded:
  - backend/: frontend-only feature
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: Modal.tsx exports a single unified contract with bg-black/60 scrim at
    z-[30], panel at z-[40], backdrop-blur-sm, scale-fade entrance animation at 280ms,
    built-in Escape key handler, built-in focus-trap (focus first focusable element
    on open; return focus to trigger on close), dismissable prop (default true; false
    prevents scrim-click and Escape dismissal), and a single SVG X close button.
  acceptance_criteria:
  - Given a modal is rendered, the scrim element has class bg-black/60, z-[30], and
    backdrop-blur-sm.
  - Given a modal is rendered, the panel wrapper has z-[40].
  - Given a modal mounts, it plays a scale-fade entrance completing in 280ms.
  - When the user presses Escape and dismissable=true (default), the modal calls onClose.
  - When the user presses Escape and dismissable=false, the modal does not call onClose.
  - When the modal opens, focus moves to the first focusable element inside the panel.
  - When the modal closes, focus returns to the element that triggered it.
  - Given the modal is open and the user presses Tab, focus cycles only within the
    modal panel (focus trap).
  - The modal renders a single SVG X icon close button that calls onClose when clicked.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: Motion tokens motion-slow (280ms) and motion-base (180ms) are added to
    tailwind.config.js under theme.extend.transitionDuration, and a @keyframes shimmer
    animation is defined in frontend/src/index.css.
  acceptance_criteria:
  - tailwind.config.js theme.extend.transitionDuration contains 'slow' mapped to '280ms'.
  - tailwind.config.js theme.extend.transitionDuration contains 'base' mapped to '180ms'.
  - frontend/src/index.css defines @keyframes shimmer with a gradient-position shift
    suitable for a shimmer effect.
  - npm run build exits 0 after the changes.
  verifying_phase: test
  confidence: 0.93
- requirement_id: R3
  statement: 'Skeleton.tsx is created at frontend/src/components/ui/Skeleton.tsx and
    exports three variants: text (single-line shimmer placeholder), block (fixed-height
    shimmer rectangle), and card (card-shaped skeleton with a header row and content
    rows).'
  acceptance_criteria:
  - Given variant='text', Skeleton renders a single shimmer bar appropriate for a
    line of text.
  - Given variant='block', Skeleton renders a fixed-height shimmer rectangle; height
    is configurable via className.
  - Given variant='card', Skeleton renders a card-shaped container with a distinct
    header shimmer row and multiple content shimmer rows.
  - All variants animate using the shimmer @keyframes at 180ms (motion-base).
  - Skeleton is accessible via aria-hidden or aria-label='Loading' with no meaningful
    text content.
  verifying_phase: test
  confidence: 0.93
- requirement_id: R4
  statement: 'MarkdownEditorModal is migrated to use Modal.tsx: its ad-hoc scrim div
    (bg-black/80, z-50) and window.keydown Escape listener are removed; Modal.tsx
    handles scrim, Escape, and focus-trap; Modal.tsx receives dismissable=false when
    the editor has unsaved changes (dirty=true).'
  acceptance_criteria:
  - MarkdownEditorModal no longer contains a fixed inset-0 div with bg-black/80.
  - MarkdownEditorModal no longer registers its own window.keydown Escape listener.
  - MarkdownEditorModal wraps its content in Modal.tsx.
  - When dirty=true, MarkdownEditorModal passes dismissable=false to Modal.tsx so
    Escape and scrim-click do not close it.
  - The editor is still accessible and functional after migration.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R5
  statement: 'FileBrowser''s FileViewerModal is migrated to use Modal.tsx: its ad-hoc
    scrim div (bg-black/80, z-50) and window.keydown Escape listener are replaced
    by Modal.tsx; the plaintext ''Loading...'' loader inside FileViewerModal is replaced
    with Skeleton variant=''block''.'
  acceptance_criteria:
  - FileViewerModal no longer contains a fixed inset-0 div with bg-black/80.
  - FileViewerModal no longer registers its own window.keydown Escape listener.
  - FileViewerModal wraps its content in Modal.tsx.
  - While file content is loading, Skeleton variant='block' is rendered in place of
    the text 'Loading...'.
  - After content loads, Skeleton is replaced by file content without layout shift.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R6
  statement: 'ViewEditor''s inline delete-confirm dialog is migrated to use Modal.tsx:
    its ad-hoc scrim div (bg-black/60, z-50) and window.keydown Escape listener are
    replaced by Modal.tsx.'
  acceptance_criteria:
  - The delete-confirm dialog in ViewEditor no longer contains a fixed inset-0 div
    with its own scrim styling.
  - The delete-confirm dialog wraps its content in Modal.tsx.
  - Pressing Escape on the delete-confirm dialog calls the cancel handler (dismissable=true).
  - Scrim click on the delete-confirm dialog calls the cancel handler.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R7
  statement: 'ToolDetailPanel''s backdrop and slide-over panel are migrated to the
    Modal.tsx contract: the ad-hoc backdrop div (bg-canvas/60, z-40) and panel (z-50)
    are replaced with Modal.tsx scrim and panel; the existing window.keydown Escape
    handler is removed in favor of Modal.tsx''s built-in; the SVG animate-spin loading
    spinner is replaced with Skeleton.'
  acceptance_criteria:
  - ToolDetailPanel no longer has a standalone backdrop div with bg-canvas/60.
  - ToolDetailPanel wraps its slide-over panel inside Modal.tsx.
  - Pressing Escape closes ToolDetailPanel via the Modal.tsx handler.
  - Scrim click closes ToolDetailPanel (dismissable=true).
  - The ToolDetailPanel SVG loading spinner is replaced with Skeleton variant='block'
    or variant='card' while data loads.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R8
  statement: HarnessListPage's two inline modals — CreateHarnessModal (bg-black/50,
    z-50) and the delete-confirm dialog (bg-black/50, z-50) — are migrated to use
    Modal.tsx.
  acceptance_criteria:
  - CreateHarnessModal no longer renders a fixed inset-0 div with bg-black/50; it
    wraps its content in Modal.tsx.
  - The delete-confirm dialog in HarnessListPage no longer renders a fixed inset-0
    div with bg-black/50; it wraps its content in Modal.tsx.
  - Both modals respond to Escape key dismissal via Modal.tsx's built-in handler.
  - Both modals move focus to the first focusable element on open via Modal.tsx's
    focus-trap.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R9
  statement: FeaturesPage's animate-spin spinner and 'Loading spaces...' text loader
    are replaced with a Skeleton component that reserves space matching the eventual
    content layout.
  acceptance_criteria:
  - When FeaturesPage is in the loading state, no animate-spin spinner element is
    rendered.
  - When FeaturesPage is in the loading state, a Skeleton component is rendered with
    dimensions approximating the feature board layout.
  - When data arrives, the Skeleton is replaced by content without visible layout
    shift.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R10
  statement: DashboardPage's plaintext 'Loading dashboard...' (line 601), 'Loading
    statistics...' (line 699), and loading text (line 816) are replaced with Skeleton
    components that reserve space matching the dashboard tile layout.
  acceptance_criteria:
  - When DashboardPage is in loading states, no plaintext 'Loading...' strings are
    rendered as primary UI content.
  - Skeleton components are rendered in place of loading text, with dimensions approximating
    dashboard tiles.
  - When data arrives, Skeleton components are replaced by content without visible
    layout shift.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R11
  statement: HarnessListPage's spinner+text loading state is replaced with Skeleton
    card components that reserve space for the harness card list.
  acceptance_criteria:
  - When HarnessListPage is in the loading state, no animate-spin spinner or 'Loading...'
    text is rendered.
  - One or more Skeleton variant='card' components are rendered to approximate the
    harness card list.
  - When harness data arrives, Skeleton cards are replaced by HarnessCard components
    without visible layout shift.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R12
  statement: npm run build and npm test both exit 0 after all changes, with no new
    TypeScript strict-mode errors introduced.
  acceptance_criteria:
  - Running npm run build from frontend/ exits with code 0.
  - Running npm test from frontend/ exits with code 0.
  - No new TypeScript errors are present in the changed files.
  verifying_phase: test
  confidence: 0.98
metrics:
  tool_calls: 8
  files_read: 5
  memory_hits: 6
---

## Summary

Phase 5 of the GUI refactor enforces a single, contract-compliant Modal component and introduces a shared Skeleton loader to eliminate layout shift. The existing Modal.tsx is minimal (22 lines, no Escape handling, no focus-trap, mismatched scrim opacity bg-black/70); six locations across four components and two pages use ad-hoc inline modals with three distinct scrim opacities (bg-black/50, bg-black/60, bg-black/80, bg-canvas/60) and inconsistent dismiss behavior. Three pages (FeaturesPage, DashboardPage, HarnessListPage) show plain text or CSS spinner loaders that cause visible layout shift. This phase ships Modal.tsx with the full contract, migrates all six ad-hoc modal sites, ships Skeleton.tsx with three variants, and replaces the three spinner/text loading states — all verifiable through unit tests and a green build.

## Scope

### In scope
- Rewrite frontend/src/components/ui/Modal.tsx with unified contract: bg-black/60 scrim, z-[30], z-[40] panel, backdrop-blur-sm, 280ms scale-fade entrance, built-in Escape handler, built-in focus-trap, dismissable prop, SVG X close button
- Add motion-slow (280ms) and motion-base (180ms) to tailwind.config.js under theme.extend.transitionDuration
- Add @keyframes shimmer to frontend/src/index.css
- Create frontend/src/components/ui/Skeleton.tsx with text, block, and card variants (shimmer at 180ms)
- Migrate MarkdownEditorModal to Modal.tsx (remove ad-hoc scrim + Escape listener; wire dismissable=false when dirty)
- Migrate FileBrowser's FileViewerModal to Modal.tsx (remove ad-hoc scrim + Escape listener; replace text loader with Skeleton)
- Migrate ViewEditor's delete-confirm dialog to Modal.tsx
- Migrate ToolDetailPanel slide-over to Modal.tsx (replace bg-canvas/60 backdrop; replace SVG spinner with Skeleton)
- Migrate HarnessListPage's CreateHarnessModal to Modal.tsx
- Migrate HarnessListPage's delete-confirm dialog to Modal.tsx
- Replace FeaturesPage spinner+text with Skeleton component
- Replace DashboardPage plaintext loading states with Skeleton components
- Replace HarnessListPage spinner+text loading state with Skeleton card

### Out of scope
- Backend changes: this is a frontend-only phase
- Detail.tsx and FeatureDetail.tsx ad-hoc skeleton functions: not listed in brief scope
- Non-modal fixed-position overlays not in the scope list (e.g., toast notifications, sidebar)
- Additional Skeleton variants beyond text, block, and card
- Third-party focus-trap library introduction

### Deferred
- Refactoring Detail.tsx and FeatureDetail.tsx inline skeletons to use shared Skeleton.tsx (polish phase)
- Distinct slide-from-right entrance animation for ToolDetailPanel (deferred; scale-fade used for now per brief)
- Visual regression testing for entrance animations

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Modal.tsx unified contract: bg-black/60 scrim z-[30], panel z-[40], 280ms scale-fade, Escape, focus-trap, dismissable prop, SVG X |
| R2 | Add motion-slow/motion-base to tailwind.config.js; add @keyframes shimmer to index.css |
| R3 | Create Skeleton.tsx with text, block, and card variants using shimmer at 180ms |
| R4 | Migrate MarkdownEditorModal to Modal.tsx; remove ad-hoc scrim and Escape listener; wire dismissable=false when dirty |
| R5 | Migrate FileBrowser FileViewerModal to Modal.tsx; replace text loader with Skeleton block |
| R6 | Migrate ViewEditor delete-confirm dialog to Modal.tsx |
| R7 | Migrate ToolDetailPanel to Modal.tsx; replace SVG spinner with Skeleton |
| R8 | Migrate HarnessListPage's two inline modals to Modal.tsx |
| R9 | Replace FeaturesPage spinner/text loader with Skeleton |
| R10 | Replace DashboardPage plaintext loading states with Skeleton |
| R11 | Replace HarnessListPage spinner+text loading state with Skeleton card |
| R12 | npm run build and npm test both exit 0 after all changes |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — bg-black/60 scrim at z-[30]; panel at z-[40]; 280ms scale-fade entrance; Escape closes unless dismissable=false; focus traps inside panel; SVG X button present
- R2 — tailwind.config.js has transitionDuration 'slow'=280ms and 'base'=180ms; index.css has @keyframes shimmer; build green
- R3 — text/block/card variants each shimmer at 180ms; aria-accessible; no meaningful text content
- R4 — MarkdownEditorModal uses Modal.tsx; no own bg-black/80 scrim div; no own Escape listener; dirty=true passes dismissable=false
- R5 — FileViewerModal uses Modal.tsx; no own bg-black/80 scrim; no own Escape listener; Skeleton block replaces text loader; no layout shift
- R6 — ViewEditor delete dialog uses Modal.tsx; no inline scrim; Escape and scrim-click call cancel
- R7 — ToolDetailPanel uses Modal.tsx; no bg-canvas/60 backdrop; SVG spinner replaced with Skeleton; Escape closes via Modal
- R8 — Both HarnessListPage modals use Modal.tsx; no bg-black/50 scrim divs; both respond to Escape and focus-trap
- R9 — FeaturesPage loading shows Skeleton (no spinner); no layout shift on data arrival
- R10 — DashboardPage loading shows Skeleton tiles (no plaintext Loading strings); no layout shift
- R11 — HarnessListPage loading shows Skeleton cards (no spinner); no layout shift
- R12 — npm run build exits 0; npm test exits 0; no new TypeScript errors

## Traceability

The full requirement to acceptance criteria to verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Modal.tsx exports unified contract: bg-black/60 scrim z-[30], panel z-[40], 280ms scale-fade entrance, Escape, focus-trap, dismissable prop, SVG X close button. |
| R2 | test | Motion tokens motion-slow/motion-base added to tailwind.config.js; @keyframes shimmer added to index.css. |
| R3 | test | Skeleton.tsx created with text, block, and card variants shimming at 180ms. |
| R4 | test | MarkdownEditorModal migrated to Modal.tsx; ad-hoc scrim and Escape listener removed; dismissable=false when dirty. |
| R5 | test | FileBrowser FileViewerModal migrated to Modal.tsx; text loader replaced with Skeleton block variant. |
| R6 | test | ViewEditor delete-confirm dialog migrated to Modal.tsx. |
| R7 | test | ToolDetailPanel migrated to Modal.tsx; SVG spinner replaced with Skeleton. |
| R8 | test | Both HarnessListPage inline modals migrated to Modal.tsx. |
| R9 | test | FeaturesPage spinner/text loader replaced with Skeleton component. |
| R10 | test | DashboardPage plaintext loading states replaced with Skeleton components. |
| R11 | test | HarnessListPage spinner+text loading state replaced with Skeleton card. |
| R12 | test | npm run build and npm test both exit 0; no new TypeScript errors. |

## Assumptions

- has_ui=true rationale: all requirements involve frontend component changes visible to the user through screens and forms; no backend changes are needed.
- dismissable=false is a prop on Modal.tsx itself (not a caller-side workaround). MarkdownEditorModal passes dismissable=false when dirty=true; other callers omit the prop (default true).
- Focus-trap is implemented inline in Modal.tsx via a useEffect that queries focusable elements and wires Tab/Shift-Tab key handlers. No third-party library is introduced (no @headlessui is present in current frontend deps).
- ToolDetailPanel slide-over is in scope per the task brief's explicit mention of its bg-canvas/60 scrim and the orchestrator resolution. Entrance animation follows scale-fade contract per brief; a slide-from-right variant is deferred.
- Both HarnessListPage inline modals (CreateHarnessModal and delete-confirm dialog) are in scope per orchestrator resolution, extending the brief's listed 4 migration sites to 6 effective sites.
- Motion tokens are added to tailwind.config.js under theme.extend.transitionDuration; shimmer @keyframes is added to index.css (consistent with project pattern: streamEnter, pulseDot, neonPulseDot already live there).
- Only three Skeleton variants (text, block, card) are in scope. No avatar or line-group variants.
- Unit tests for Escape key, focus behavior, and Skeleton variant rendering are the expected test surface; visual regression tests are out of scope.
- DashboardPage has three loading text locations (lines 601, 699, 816); R10 covers all three; the design agent should confirm Skeleton variant per site.

## Open questions

- None. All scout open questions have been resolved by the orchestrator prior to this analysis pass.

## Next consumer brief

Read traceability[] (R1-R12) as the full ground-truth requirement list; has_ui=true routes this to the frontend design track. Key decisions for the design iteration DAG:

1. Layer 0 (infrastructure): R2 (motion tokens + shimmer keyframes) must land first. Both Modal.tsx entrance animation (R1) and Skeleton shimmer (R3) depend on these definitions. Two file changes only: tailwind.config.js + index.css.

2. Layer 1 (primitives): R1 (Modal.tsx rewrite) and R3 (Skeleton.tsx creation) are independent and can be developed in parallel once R2 is done. Modal.tsx is the higher-risk item: focus-trap implementation requires careful Tab/Shift-Tab key handling and must not break ViewEditor's existing usage of Modal.tsx (ViewEditor already wraps a child in Modal.tsx at line 300 -- confirm this is not broken after the rewrite).

3. Layer 2 (modal migrations): R4-R8 depend on R1. They can be batched by file: MarkdownEditorModal (R4), FileBrowser (R5), ViewEditor delete dialog (R6), ToolDetailPanel (R7), HarnessListPage two modals (R8). Each migration removes an ad-hoc scrim div and Escape listener and wraps content in Modal.tsx.

4. Layer 3 (loading state replacements): R9-R11 depend on R3 only. FeaturesPage (R9), DashboardPage (R10 -- three loading sites), HarnessListPage (R11).

5. Risk: MarkdownEditorModal dirty guard (R4) -- must thread dirty state to Modal.tsx dismissable prop without removing existing save-prompt UX.

6. Risk: ViewEditor uses both Modal.tsx (existing) and has an inline delete dialog (R6 migration target) -- the Modal.tsx rewrite must not regress the existing wrapper usage.

7. R12 (build + test green) is a gate for every iteration, not just the final one.
