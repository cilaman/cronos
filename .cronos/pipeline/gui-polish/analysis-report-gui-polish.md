---
cc_version: '1.0'
agent: pipeline-analyst
slug: gui-polish
phase: analysis
status: done
confidence: 0.88
inputs_used:
- memory:project_gui_refactor_board_setup
- memory:project_gui_tokens_brand_review_attempt1
- .cronos/pipeline/gui-polish/scout-report-gui-polish.md
- frontend/src/components/ui/IconButton.tsx
- frontend/src/components/Lane.tsx
- frontend/src/components/ui/Modal.tsx
- frontend/src/App.tsx
outputs_produced:
- .cronos/pipeline/gui-polish/analysis-report-gui-polish.md
blockers: []
next_consumer: design
request: "GUI polish — touch targets, Toast, utility primitives (Phase 6)\n\nA polish\
  \ sweep covering three areas: touch targets, a Toast notification system,\nand extraction\
  \ of utility primitives from existing inline usage. This closes the gap\nbetween\
  \ the design system spec and the remaining ad-hoc patterns.\n\n**Concrete changes:**\n\
  - **Touch targets:** sweep all interactive elements below 44px — lane header +/x\n\
  \  (p-1≈24px → p-2.5), Detail modal close (p-1), IconButton sm(28px)/md(32px) hit\
  \ areas\n  (expand padding not glyph). Use `min-w-[44px] min-h-[44px]` with padding\
  \ correction.\n- **Toast system:** `Toast.tsx` + `ToastProvider.tsx` + `useToast()`\
  \ hook —\n  `tone: success|warning|danger|info`, `message: string`, `action?: {label,\
  \ onClick}`,\n  auto-dismiss 3–5s, `aria-live=\"polite\"`, no focus steal. Wire\
  \ into App.tsx.\n- **Tabs.tsx:** extracted from Detail/SpaceTools inline tab switching\
  \ pattern.\n  Props: `items: {value, label}[]`, `value`, `onChange`.\n- **Dropdown.tsx\
  \ + Menu.tsx:** consolidate ViewPicker / SpaceFilter trigger patterns.\n  Headless\
  \ (or minimal) focus management; z-dropdown(20).\n- **Tooltip.tsx:** keyboard-reachable,\
  \ for icon-only affordances. z-tooltip(60).\n- **StatTile.tsx:** `label`, `value`,\
  \ `delta?`, `tone?` — extract from Dashboard/Stats.\n- **ProgressBar.tsx:** `value`,\
  \ `max`, `segments?`, `tone?`, `showLabel?`.\n- **Copy rewrites:** replace \"Error:\
  \ {message}\" with user-voiced cause + fix; loading\n  states say what they're loading;\
  \ empty states include a primary action.\n- **Optional:** ESLint rule banning raw\
  \ `(text|bg|border)-(red|emerald|amber|…)-\\d`\n  in `.tsx` files to prevent regression.\n\
  \n**Exit criteria:** all interactive elements ≥44px; Toast renders with aria-live;\
  \ utility\nprimitives available; error/loading/empty copy user-voiced; `npm run\
  \ build` + `npm test` green.\n\nScope: frontend/src/components/ui/Toast.tsx, frontend/src/components/ui/Tabs.tsx,\
  \ frontend/src/components/ui/Dropdown.tsx, frontend/src/components/ui/Tooltip.tsx,\
  \ frontend/src/components/ui/StatTile.tsx, frontend/src/components/ui/ProgressBar.tsx,\
  \ frontend/src/components/Lane.tsx, frontend/src/pages/Dashboard.tsx, frontend/src/pages/Stats.tsx"
has_ui: true
coverage_summary:
  searched:
  - frontend/src/components/ui/
  - frontend/src/components/Lane.tsx
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/App.tsx
  - .cronos/pipeline/gui-polish/scout-report-gui-polish.md
  excluded:
  - 'backend/: frontend-only scope per request'
  - '.claude/agents/: not relevant to UI primitive extraction'
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: All interactive elements in Lane.tsx header (add and hide-lane buttons)
    must meet the 44px minimum touch target via min-w-[44px] min-h-[44px] with padding
    correction, without enlarging the visual glyph.
  acceptance_criteria:
  - Given the Lane header is rendered, when measured, each button's computed hit area
    is at least 44x44px.
  - The add-task button (p-1 to p-2.5) and hide-lane button (p-1 to p-2.5) preserve
    their existing glyph sizes.
  - Existing Lane snapshot tests pass with updated class names.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: The Modal close button must meet the 44px minimum touch target via min-w-[44px]
    min-h-[44px] with padding correction, without resizing the x icon.
  acceptance_criteria:
  - Given Modal is open, when measured, the close button's hit area is at least 44x44px.
  - The 16x16 SVG icon size is unchanged; only surrounding padding grows.
  - Existing Modal tests pass.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R3
  statement: IconButton sm and md size variants must guarantee a 44px minimum touch
    target by expanding surrounding padding while preserving the declared h-7/h-8
    visual size.
  acceptance_criteria:
  - Given IconButton size=sm, when rendered, the outer clickable area is at least
    44x44px.
  - Given IconButton size=md, when rendered, the outer clickable area is at least
    44x44px.
  - The visible button border box retains h-7 w-7 (sm) and h-8 w-8 (md) dimensions
    so dense toolbars are not disrupted.
  - IconButton unit tests pass for all variants and sizes.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: A Toast notification system must be implemented as Toast.tsx, ToastProvider.tsx,
    and useToast() hook, wired into App.tsx, supporting tone (success|warning|danger|info),
    message, optional action, auto-dismiss in 3-5 s, aria-live=polite, and no focus
    steal on appearance.
  acceptance_criteria:
  - Given ToastProvider wraps the app in App.tsx, when useToast().show() is called,
    a toast renders in the viewport with the correct tone styling.
  - Given a toast is visible, when 3-5 s elapses, the toast dismisses automatically
    without user interaction.
  - Given a toast with action={label, onClick}, when the action button is clicked,
    onClick fires and the toast dismisses.
  - The toast container has aria-live=polite and role=status; no interactive element
    receives focus automatically on toast appearance.
  - Toast and ToastProvider unit tests cover show, auto-dismiss, and manual dismiss.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R5
  statement: A Tabs.tsx primitive must be extracted from Detail.tsx and SpaceToolsPage
    inline tab patterns, accepting items ({value, label}[]), value, and onChange,
    with the same active-underline styling already in use.
  acceptance_criteria:
  - Given Tabs with items and a controlled value prop, the active tab item renders
    with the accent underline and inactive items do not.
  - Given a tab item is clicked, onChange fires with the clicked item value.
  - Detail.tsx tab bar is replaced by Tabs with no visual regression.
  - Unit tests cover active state, inactive state, and onChange callback.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R6
  statement: A Dropdown.tsx primitive must be extracted from ViewPicker.tsx keyboard-managed
    open/close pattern, supporting a trigger element, items [{label, onClick}], ESC
    close, outside-click close, and z-dropdown (z-20) positioning.
  acceptance_criteria:
  - Given Dropdown is rendered, when the trigger is activated, the item list opens.
  - Given the item list is open, when ESC is pressed, the list closes and focus returns
    to the trigger.
  - Given the item list is open, when a click occurs outside the component, the list
    closes.
  - The dropdown container uses z-[20] (z-dropdown layer).
  - Unit tests cover open, close via ESC, close via outside click, and item selection.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R7
  statement: A Tooltip.tsx primitive must be created that is keyboard-reachable (appears
    on focus and hover), used for icon-only affordances, and positioned at the z-tooltip
    layer (z-60).
  acceptance_criteria:
  - Given an icon-only button wrapped in Tooltip, when the button receives keyboard
    focus, the tooltip text is visible.
  - Given the tooltip is visible, when focus or hover leaves, the tooltip hides.
  - The tooltip container uses z-[60] (z-tooltip layer).
  - Tooltip unit tests cover focus-show, blur-hide, hover-show, hover-hide.
  verifying_phase: test
  confidence: 0.82
- requirement_id: R8
  statement: A StatTile.tsx primitive must be extracted from Dashboard/Stats inline
    stat patterns, accepting label, value, delta?, and tone?, rendering consistently
    across DashboardPage and Stats.
  acceptance_criteria:
  - Given StatTile with label and value props, the component renders the label and
    value.
  - Given StatTile with a positive delta, a green/success indicator is shown; negative
    delta shows red/danger.
  - Given StatTile with tone prop, the tile border or background reflects the tone
    color.
  - DashboardPage stat tiles are replaced by StatTile with no visual regression.
  - StatTile unit tests cover label+value, delta variants, and tone variants.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R9
  statement: A ProgressBar.tsx primitive must be created accepting value, max, segments?,
    tone?, and showLabel?, rendering a proportional bar with optional segmentation
    and accessible label.
  acceptance_criteria:
  - Given ProgressBar with value=3 max=10, the filled portion represents 30%.
  - Given ProgressBar with showLabel=true, an accessible text label showing the percentage
    or value/max is rendered.
  - Given ProgressBar with tone=danger, the filled bar uses the danger color token.
  - Given ProgressBar with segments, the bar is divided into visually distinct segments.
  - ProgressBar unit tests cover proportional fill, showLabel, tone, and segments.
  verifying_phase: test
  confidence: 0.82
- requirement_id: R10
  statement: Error, loading, and empty copy across the scoped pages (Dashboard, Stats,
    Detail, Lane) must be rewritten to user-voiced cause-and-fix framing, and empty
    states must expose a primary action where applicable.
  acceptance_criteria:
  - Given a loading state, the copy reads Loading <noun> (e.g., Loading task details...)
    rather than a generic spinner with no label.
  - Given an error state, the copy states the cause in plain language and offers a
    fix action or retry.
  - Given an empty lane, the EmptyState component renders with a primary action (e.g.,
    Add task) where the lane supports task creation.
  - No existing test fails due to copy changes; updated copy is covered by snapshot
    or text-match assertions.
  verifying_phase: review
  confidence: 0.8
- requirement_id: R11
  statement: npm run build and npm test must pass green after all changes with no
    new TypeScript errors or failing test assertions.
  acceptance_criteria:
  - npm run build exits 0 with no TypeScript errors.
  - npm test exits 0 with all existing and new tests passing.
  verifying_phase: test
  confidence: 0.95
metrics:
  tool_calls: 10
  files_read: 6
  memory_hits: 2
---

## Summary

GUI Polish (Phase 6) is the final-pass sweep of the design system rollout, covering three workstreams: (1) enforcing WCAG 44px minimum touch targets on Lane headers, Modal close, and IconButton variants by expanding padding without resizing glyphs; (2) introducing a Toast notification system (Toast.tsx, ToastProvider.tsx, useToast()) with aria-live accessibility wired into App.tsx; and (3) extracting six utility primitives (Tabs, Dropdown, Tooltip, StatTile, ProgressBar) from scattered inline implementations in Detail, ViewPicker, Dashboard, and Stats. Copy rewrites for error/loading/empty states complete the scope. All changes are isolated to frontend/src with no backend impact.

## Scope

### In scope
- Touch target fixes: Lane.tsx header add/hide buttons (p-1 to min-h-[44px] min-w-[44px] plus p-2.5)
- Touch target fixes: Modal.tsx close button (p-1 to min-h-[44px] min-w-[44px])
- Touch target fixes: IconButton.tsx sm (h-7, 28px) and md (h-8, 32px) to guaranteed 44px hit area
- Toast.tsx + ToastProvider.tsx + useToast() hook wired into App.tsx
- Tabs.tsx primitive extracted from Detail.tsx tab bar
- Dropdown.tsx primitive extracted from ViewPicker.tsx pattern
- Tooltip.tsx primitive (new, keyboard-reachable, z-tooltip layer)
- StatTile.tsx primitive extracted from DashboardPage/Stats inline patterns
- ProgressBar.tsx with segments, tone, showLabel
- Error/loading/empty copy rewrites across Dashboard, Stats, Detail, Lane (user-voiced)
- npm run build + npm test green gate

### Out of scope
- ESLint guardrail rule for raw palette class names (optional per request; deferred)
- Any backend changes
- SpaceFilter dropdown migration to Dropdown.tsx (deferred; primitive enables it)
- Menu.tsx as a separate primitive (Dropdown covers the pattern; Menu alias deferred)
- Button.tsx sm/md touch target (request explicitly lists Lane/Modal/IconButton only)

### Deferred
- ESLint raw-palette-class ban rule (optional in request, tooling overhead)
- SpaceFilter and other secondary trigger sites migrated to Dropdown.tsx
- Button.tsx sm/md touch target expansion
- SegmentedControl.tsx (roadmap Phase 6 mention but absent from concrete request list)

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Lane header add/hide buttons upgraded to 44px touch target |
| R2 | Modal close button upgraded to 44px touch target |
| R3 | IconButton sm/md size variants guaranteed 44px touch area via padding |
| R4 | Toast system (Toast.tsx + ToastProvider.tsx + useToast()) wired into App.tsx |
| R5 | Tabs.tsx primitive extracted from Detail.tsx inline tab pattern |
| R6 | Dropdown.tsx primitive extracted from ViewPicker.tsx open/close pattern |
| R7 | Tooltip.tsx primitive (keyboard-reachable, z-tooltip layer) |
| R8 | StatTile.tsx extracted from Dashboard/Stats inline stat display |
| R9 | ProgressBar.tsx with value/max/segments/tone/showLabel |
| R10 | Error/loading/empty copy rewritten to user-voiced cause-and-fix across scoped pages |
| R11 | npm run build and npm test exit 0 with no regressions |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (machine-readable source of truth). Compact mirrors:

- R1 — Lane header buttons render with at least 44x44px hit area; glyphs unchanged; tests pass
- R2 — Modal close button renders with at least 44x44px hit area; 16px icon unchanged; tests pass
- R3 — IconButton sm/md outer hit area is 44x44px; visual h-7/h-8 box unchanged; all variant tests pass
- R4 — Toast shows with correct tone on useToast().show(); auto-dismisses in 3-5 s; aria-live=polite; no focus steal; unit tests cover show/dismiss/action
- R5 — Tabs renders active underline on selected item; onChange fires on click; Detail.tsx migrated; unit tests pass
- R6 — Dropdown opens on trigger, closes on ESC/outside click, uses z-[20]; unit tests pass
- R7 — Tooltip shows on focus and hover, hides on blur/mouseleave, uses z-[60]; unit tests pass
- R8 — StatTile renders label+value; delta indicator reflects sign; tone reflects tone prop; Dashboard migrated; unit tests pass
- R9 — ProgressBar fill proportional to value/max; showLabel renders accessible text; tone colors correct; segments divide bar; unit tests pass
- R10 — Loading copy is "Loading <noun>..."; error copy states cause+fix; empty states have primary CTA where applicable; no test regressions
- R11 — npm run build exits 0; npm test exits 0; no TypeScript errors

## Traceability

The full requirement to acceptance criteria to verifying_phase map is in the YAML `traceability[]` array.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Lane header add/hide buttons meet 44px minimum touch target without glyph resize |
| R2 | test | Modal close button meets 44px minimum touch target without icon resize |
| R3 | test | IconButton sm and md variants guarantee 44px outer hit area while preserving visual size |
| R4 | test | Toast system wired into App.tsx with aria-live, auto-dismiss, and tone support |
| R5 | test | Tabs.tsx extracted from Detail.tsx tab bar, controlled via items/value/onChange |
| R6 | test | Dropdown.tsx extracted from ViewPicker pattern with ESC/outside-click close and z-[20] |
| R7 | test | Tooltip.tsx keyboard-reachable, appears on focus and hover, positioned at z-[60] |
| R8 | test | StatTile.tsx extracted from Dashboard/Stats with label, value, delta, tone props |
| R9 | test | ProgressBar.tsx with proportional fill, tone, showLabel, and optional segments |
| R10 | review | Error/loading/empty copy rewritten to user-voiced framing across scoped pages |
| R11 | test | npm run build and npm test exit 0 after all changes |

## Assumptions

- has_ui=true rationale: all requirements involve frontend React components, JSX rendering, and visual/interaction behavior — unambiguously UI.
- Phases 0-5 of the GUI refactor are already committed to feature/gui-refactor; Phase 6 builds on those tokens and primitives (confirmed by memory:project_gui_refactor_board_setup).
- The "padding wrapper" approach preserving visual size while expanding the hit area is the correct strategy per the request's explicit instruction "expand padding not glyph".
- Toast auto-dismiss window is 3-5 s as stated in the request; implementation may parameterize but default must fall in this range.
- Button.tsx sm/md touch target gap is noted but excluded from this scope; the request's concrete list covers Lane/Modal/IconButton only.
- StatTile and ProgressBar currently exist as inline JSX in DashboardPage and Detail; extraction creates new files in frontend/src/components/ui/ with no backend impact.
- App.tsx is the correct ToastProvider integration point (confirmed by reading App.tsx — it is the root layout wrapping all routes via Outlet).
- The ESLint guardrail is marked optional in the request and is deferred; it is not part of the exit gate.

## Open questions

- None.

## Next consumer brief

Read `traceability[]` first — it is the ground truth for requirement statements, acceptance criteria, and verifying phases. `has_ui=true` routes through the UI design sub-track.

Decision points for the design agent:

1. Touch target strategy (R1-R3): padding-wrapper approach is specified. Design must choose between replacing `p-1` with `min-h-[44px] min-w-[44px]` inline (simpler) vs. a negative-margin wrapper `span`. The request implies inline replacement.

2. IconButton hit-area (R3): visual h-7/h-8 must be preserved for dense toolbar contexts. Consider a wrapper span with min-h-[44px] that centers the button, or an after: pseudo-element expansion.

3. Toast z-layer (R4): design must confirm the exact Tailwind z-class from the design system ladder (02-design-system.md section 2.5 names z-toast). It must sit above scrim in non-modal contexts.

4. Tabs active-underline (R5): Detail.tsx uses an absolute-positioned bottom border accent bar. Tabs.tsx must canonicalize this exact pattern as the single source of truth.

5. Dropdown vs ViewPicker migration (R6): the request scopes only primitive extraction. Design should decide whether to also migrate ViewPicker to use the new Dropdown in this phase.

6. Copy rewrite enumeration (R10, verifying_phase=review): design should enumerate all specific string locations being changed so the reviewer can audit each one. Known locations: Detail.tsx "Loading stats...", Lane.tsx "No tasks", and scattered error messages in Dashboard/Stats.

Risk: Tabs and Dropdown extraction touches Detail.tsx and ViewPicker.tsx which have existing test coverage. Design iterations should separate primitive creation from migration of call sites into distinct iterations to avoid mid-iteration test breakage.
