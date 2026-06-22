---
cc_version: '1.0'
agent: pipeline-architect
slug: gui-tokens-brand
phase: design
status: done
confidence: 0.88
inputs_used:
- memory:project_gui_refactor_board_setup
- memory:project_branding
- .cronos/pipeline/gui-tokens-brand/analysis-report-gui-tokens-brand.md
- .cronos/pipeline/gui-tokens-brand/scout-report-gui-tokens-brand.md
- frontend/src/index.css
- frontend/tailwind.config.js
- frontend/src/components/Sidebar.tsx
- docs/ui-ux-review/brand/logo/cronos-mark-flat.svg
outputs_produced:
- .cronos/pipeline/gui-tokens-brand/design-report-gui-tokens-brand.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/index.css
  - frontend/tailwind.config.js
  - frontend/src/components/Sidebar.tsx
  - frontend/public/ (verified absent — must be created)
  - frontend/src/styles/ (verified absent — must be created)
  - docs/ui-ux-review/brand/logo/
  - docs/ui-ux-review/brand/png/
  excluded:
  - 'backend/: not relevant to frontend token integration'
  - 'frontend/src/ (other components): out of scope per analysis ## Scope'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: frontend
  scope_files:
  - frontend/src/index.css
  - frontend/tests/index.css.test.ts
  validation_command: cd frontend && npm test -- src/../tests/index.css.test.ts --run
  max_diff_lines: 300
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/tailwind.config.js
  - frontend/tests/tailwind.config.test.ts
  validation_command: cd frontend && npm test -- tests/tailwind.config.test.ts --run
  max_diff_lines: 250
  depends_on:
  - I1
- id: I3
  type: frontend
  scope_files:
  - frontend/public/cronos-favicon.svg
  - frontend/public/favicon-16.png
  - frontend/public/favicon-32.png
  - frontend/public/apple-touch-icon-180.png
  - frontend/public/site.webmanifest
  - frontend/index.html
  - frontend/tests/index-html.test.ts
  validation_command: cd frontend && npm test -- tests/index-html.test.ts --run
  max_diff_lines: 250
  depends_on: []
- id: I4
  type: frontend
  scope_files:
  - frontend/src/components/Sidebar.tsx
  - frontend/src/components/CronosMark.tsx
  - frontend/src/components/__tests__/Sidebar.wordmark.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Sidebar.wordmark.test.tsx
    --run
  max_diff_lines: 250
  depends_on:
  - I1
  - I2
- id: I5
  type: frontend
  scope_files:
  - frontend/src/styles/TOKENS.md
  validation_command: cd frontend && npm run build && npm test -- --run
  max_diff_lines: 400
  depends_on:
  - I1
  - I2
  - I3
  - I4
risks:
- description: Existing tailwind.config.js already exposes `warning` and `danger`
    Tailwind utilities backed by `--color-warning` / `--color-danger`. R1 adds new
    per-theme RGB triplets for the same variables (dark/neon must change from current
    amber/red values to brand-aligned values). Existing components reading `bg-warning`/`text-danger`
    will visually shift in dark and neon themes.
  severity: medium
  mitigation: 'Q2 resolution: merge approach (option a) — update the three existing
    --color-warning and --color-danger triplets per theme in I1 to brand values, keep
    existing Tailwind `warning`/`danger` aliases in tailwind.config.js (no rename),
    and do not add color-warning/color-danger aliases. I2 only adds the new utilities
    (running, success, info, neutral, brand*, cat-*). The two visual shifts (dark
    warning amber 212→255 166 46; dark danger red 168→255 110 92) are acceptable as
    part of the brand-alignment goal; R12 only forbids removal/rename, not value updates.'
- description: cronos-mark-flat.svg contains hardcoded fill colours `#3B4757` (outer
    ring), `#56657A` (middle ring), and `#7A4FB0` (inner ring + nodes + core). The
    analyst assumption that the SVG uses `currentColor` is incorrect. R10 requires
    the mark to theme correctly in all three themes without hardcoded colours breaking
    theme switching.
  severity: high
  mitigation: 'I4 creates a new local React component `frontend/src/components/CronosMark.tsx`
    that inlines the SVG geometry but replaces the three hardcoded fills with theme-aware
    refs: outer ring → `stroke="rgb(var(--color-hairline-strong))"`, middle ring →
    `stroke="rgb(var(--color-ink-faint))"`, brand violet ring + nodes + core → `stroke/fill="rgb(var(--brand))"`.
    The brand violet (`--brand` from R3) is theme-invariant, so the violet anchor
    nodes look identical across themes; only the chrome rings adapt. Do NOT copy the
    raw SVG file into frontend/public/ for sidebar use (favicon use in I3 is still
    raw and acceptable — it renders against browser chrome, not the app surface).'
- description: R9 lists five files to copy into `frontend/public/`. `frontend/public/`
    does not currently exist in the repo. If Vite is configured to expect the public
    dir and it does not exist before `npm run build`, build may emit a non-fatal warning
    that masks asset-resolution errors at runtime.
  severity: medium
  mitigation: I3 creates the directory by virtue of writing files into it (git tracks
    files, not directories). The implementor must copy the four binary assets from
    `docs/ui-ux-review/brand/` (cronos-favicon.svg, favicon-16.png, favicon-32.png,
    apple-touch-icon-180.png) using `cp` via the Bash tool, NOT via the Write tool
    (which corrupts binary files). The `site.webmanifest` is text JSON and must be
    created via Write. The I3 validation reads frontend/index.html plus the manifest
    JSON; a separate manual check `cd frontend && npm run build` runs in I5 to confirm
    Vite resolves the asset references.
- description: 'Q1 collision: in the neon theme, the scout proposed `--color-info:
    90 230 255` which is the same triplet as `--color-accent-bright: 90 230 255` (verified
    in index.css line 99). Reusing the accent-bright value for info would conflate
    two semantic roles and break later phases that paint info badges next to accent-bright
    glow elements.'
  severity: low
  mitigation: 'I1 assigns neon `--color-info` a distinct sky value: `120 210 255`
    (slightly lighter, more sky-leaning than the cyan accent-bright). Document the
    choice in TOKENS.md (I5) under Status tokens > Per-theme RGB > note row for `--color-info`.'
- description: R12 requires `npm test` to pass green after all changes, but iterations
    I1–I4 add their own narrow vitest specs. A narrow `-k` run may pass while the
    full suite fails due to a stale snapshot or a token-coupled component test elsewhere.
  severity: medium
  mitigation: I5's validation_command runs `npm run build && npm test -- --run` (the
    full vitest suite, no -k filter). This is the gate that catches any regression
    caused by I1–I4. If any cross-iteration test fails, the I5 implementor must trace
    the failure to the offending iteration and either patch the test within I5 (if
    the test was assertion-stale) or escalate via blockers (if a component visually
    relies on the legacy --color-warning/--color-danger triplet).
metrics:
  tool_calls: 7
  files_read: 6
  memory_hits: 2
  iterations_planned: 5
---

## Summary

Phase 0 of the GUI refactor lays down the token foundation: status / categorical / brand CSS variables in all three theme blocks, Tailwind utility exposures (colours + typography + z-index + motion), favicon and PWA wiring, a brand-aware sidebar logo swap, and a TOKENS.md reference. The DAG is 5 iterations across 2 layers: layer 0 runs I1 (CSS tokens) and I3 (HTML head + public assets) in parallel; layer 1 runs I2 (Tailwind exposure, depends on I1), then I4 (sidebar component, depends on I1+I2), then I5 (TOKENS.md + full-suite build gate). The two key non-obvious decisions are recorded in the risk register: Q2 is resolved by merging (update existing --color-warning/danger triplets, keep Tailwind aliases) and Q1 by assigning a distinct neon --color-info value (120 210 255). The cronos-mark-flat.svg's hardcoded fills force I4 to inline a theme-aware React component rather than reuse the raw SVG.

## Components

### Data
- No data layer changes — Phase 0 is presentation-token only.

### Backend
- No backend layer changes — Phase 0 is frontend-only.

### Frontend
- `frontend/src/index.css`: extend each of the three existing theme blocks (`:root`, `.dark`, `.neon`) with six status colour tokens (R1), six categorical tokens (R2), and three theme-invariant brand identity tokens (R3, `:root` only).
- `frontend/tailwind.config.js`: extend `theme.extend.colors` with the new semantic tokens (R4), `theme.extend.fontSize` with the six-step typography scale (R5), `theme.extend.zIndex` with the seven-step ladder (R6), and `theme.extend.transitionDuration` with three motion durations (R7).
- `frontend/index.html`: append five `<link>` elements to `<head>` for favicon SVG + PNG sizes + apple-touch-icon + manifest (R8).
- `frontend/public/`: new directory containing four brand binary assets plus `site.webmanifest` JSON (R9).
- `frontend/src/components/CronosMark.tsx`: new inline-SVG React component using theme-aware `rgb(var(--…))` strokes/fills so the sidebar mark adapts to all three themes (R10, supports R3 brand violet).
- `frontend/src/components/Sidebar.tsx`: remove pulse-dot span, replace text-only wordmark with `<CronosMark />` at 24px alongside JetBrains Mono "CRONOS" text (R10).
- `frontend/src/styles/TOKENS.md`: new directory + structured token reference document with eight sections (R11) and the "lime reserved for running" rule.

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                          | Validation                                                                                  |
|-----|----------|------------|-----------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| I1  | frontend | -          | frontend/src/index.css, frontend/tests/index.css.test.ts        | cd frontend && npm test -- src/../tests/index.css.test.ts --run                             |
| I2  | frontend | I1         | frontend/tailwind.config.js, frontend/tests/tailwind.config.test.ts | cd frontend && npm test -- tests/tailwind.config.test.ts --run                          |
| I3  | frontend | -          | frontend/public/* (4 assets + site.webmanifest), frontend/index.html, frontend/tests/index-html.test.ts | cd frontend && npm test -- tests/index-html.test.ts --run            |
| I4  | frontend | I1, I2     | frontend/src/components/Sidebar.tsx, frontend/src/components/CronosMark.tsx, frontend/src/components/__tests__/Sidebar.wordmark.test.tsx | cd frontend && npm test -- src/components/__tests__/Sidebar.wordmark.test.tsx --run |
| I5  | frontend | I1, I2, I3, I4 | frontend/src/styles/TOKENS.md                              | cd frontend && npm run build && npm test -- --run                                           |

## Risks

| Risk                                                                                          | Severity | Mitigation                                                                                                                          |
|-----------------------------------------------------------------------------------------------|----------|-------------------------------------------------------------------------------------------------------------------------------------|
| Existing warning/danger Tailwind utilities will visually shift in dark/neon themes when --color-warning/--color-danger triplets are updated to brand values (Q2). | medium   | Merge approach: update CSS variable triplets in I1; keep existing Tailwind warning/danger aliases unchanged in I2. Brand-shift accepted. |
| cronos-mark-flat.svg has hardcoded grey + violet fills; analyst's currentColor assumption is wrong; raw SVG cannot theme. | high     | I4 creates CronosMark.tsx React component inlining geometry with rgb(var(--color-hairline-strong))/rgb(var(--color-ink-faint))/rgb(var(--brand)) strokes/fills. |
| frontend/public/ does not exist; binary assets must be copied (not Written) to avoid corruption. | medium   | I3 uses Bash `cp` for the four binary assets and Write only for the JSON manifest; full Vite build is gated in I5.                  |
| Q1 neon-theme --color-info collision with --color-accent-bright (both 90 230 255).            | low      | I1 assigns neon --color-info = 120 210 255 (distinct sky-leaning value); documented in TOKENS.md.                                   |
| Narrow per-iteration vitest runs may mask cross-component regressions from token shifts.       | medium   | I5 validation runs the full `npm run build && npm test -- --run` suite; I5 implementor must patch stale assertions or escalate.    |

## Assumptions

- `frontend/tests/` (the dedicated config-test directory) is acceptable for `index.css.test.ts`, `tailwind.config.test.ts`, and `index-html.test.ts`. These tests read the source files as text and assert on string presence (regex / substring). If vitest is configured with a `src/`-only root, the implementor of I1 must instead place the spec under `frontend/src/__tests__/tokens.test.ts` and update the validation_command accordingly; this is a path-only change.
- The brand violet `#7A4FB0` = decimal 122 79 176 matches R3 `--brand` exactly; the CronosMark component's inner ring + nodes + core all map to `rgb(var(--brand))` and require no per-theme override.
- The flat-mark's two grey rings (`#3B4757`, `#56657A`) are intentionally treated as theme-aware chrome — mapping to `--color-hairline-strong` and `--color-ink-faint` respectively keeps the structural grey shape readable on all three theme canvases without bespoke per-theme overrides.
- The favicon SVG (`cronos-favicon.svg`) is copied verbatim into `frontend/public/` and consumed by the browser tab UI; theme drift inside the browser chrome is not a concern (browsers ignore CSS variables in linked SVG favicons).
- `site.webmanifest` references `cronos-app-icon-512.png` as the 512×512 entry per R9; the implementor must also copy this asset from `docs/ui-ux-review/brand/png/cronos-app-icon-512.png` into `frontend/public/` (scope-listed implicitly via the manifest reference; the implementor should treat this as a sixth public asset rather than risk a manifest-resolution warning at build).
- `npm test -- --run` invokes vitest in non-watch mode (verified pattern in earlier pipeline memory entries); the I5 validation command relies on this so it can exit cleanly inside the pipeline runner.

## Open questions

- None. Q1 and Q2 from the analysis report are resolved in the risk register above.

## Next consumer brief

Implementor: read `iterations[]` for the 5-entry DAG; each entry's `scope_files[]` is a hard diff boundary and `validation_command` is the only test the tester will run for that iteration. Layer 0 = I1 + I3 (parallelizable). Layer 1 = I2 (after I1). Layer 2 = I4 (after I1+I2). Layer 3 = I5 (after all). Key cross-iteration invariants not derivable from YAML: (1) the exact CSS variable names `--color-running`, `--color-success`, `--color-info`, `--color-warning`, `--color-danger`, `--color-neutral`, `--cat-goal`, `--cat-feature`, `--cat-fix`, `--cat-issue`, `--cat-plan`, `--cat-ask`, `--brand`, `--brand-deep`, `--brand-light` are referenced literally by both I1 (definitions) and I2 (Tailwind exposures) — any rename in I1 breaks I2; (2) the violet brand triplet `122 79 176` must be identical in both index.css (R3) and CronosMark.tsx (I4) — the implementor of I4 must read I1's output verbatim, not retype; (3) `site.webmanifest` must reference `cronos-app-icon-512.png` and that asset must be present in `frontend/public/` (see Assumptions). Read the risk register before starting I4 — the SVG hardcoded-fill issue rewrites that iteration's approach.
