---
cc_version: '1.0'
agent: pipeline-analyst
slug: gui-tokens-brand
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:project_gui_refactor_board_setup
- memory:project_branding
- .cronos/pipeline/gui-tokens-brand/scout-report-gui-tokens-brand.md
- frontend/src/index.css
- frontend/tailwind.config.js
- frontend/index.html
- frontend/src/components/Sidebar.tsx
outputs_produced:
- .cronos/pipeline/gui-tokens-brand/analysis-report-gui-tokens-brand.md
blockers: []
next_consumer: design
request: "GUI tokens + brand integration (Phase 0)\n\nAdds the missing token layer\
  \ that every later phase depends on, plus wires the\nbrand assets (favicon, sidebar\
  \ logo, runtime-state marks) that don't yet exist in the product.\n\n**Concrete\
  \ changes (minimal visual impact):**\n- `index.css`: add `--color-running/success/info/warning/danger/neutral`\
  \ status tokens\n  (light: contrast-safe darker shades; dark/neon: brand palette\
  \ values — lime=running,\n  cyan=success, amber=warning, red=danger, from `docs/ui-ux-review/brand/tokens/tokens.css`).\n\
  - `index.css`: add `--cat-goal/feature/fix/issue/plan/ask` categorical tokens per\
  \ theme.\n- `index.css`: add `--brand/--brand-deep/--brand-light` violet identity\
  \ tokens.\n- `tailwind.config.js`: expose all new tokens plus scales — type\n  (text-title\
  \ 22px mono / text-eyebrow 11px / text-cardtitle 14px / text-body 14px /\n  text-meta\
  \ 12px / text-micro 10px), spacing steps (4/8/12/16/24/32/48),\n  radius (sm=4px\
  \ / md=6px / lg=8px / full), z-index (base/raised/dropdown/scrim/\n  modal/toast/tooltip),\
  \ motion (motion-fast 120ms / motion-base 180ms / motion-slow 280ms).\n- `frontend/index.html`:\
  \ wire favicon PNG/SVG, apple-touch-icon, PWA manifest from\n  `docs/ui-ux-review/brand/png/`\
  \ and `brand/logo/cronos-favicon.svg`.\n- Sidebar logo (App.tsx or NavBar component):\
  \ replace existing wordmark with the\n  flat-mark SVG (`brand/logo/cronos-mark-flat.svg`)\
  \ + live JetBrains Mono \"CRONOS\" text\n  node (themes correctly on all three themes).\n\
  - `frontend/src/styles/TOKENS.md`: token reference document.\n\n**Exit criteria:**\
  \ tokens resolve in all three themes; favicon + sidebar logo updated;\n`npm run\
  \ build` + `npm test` green; no other component visually changed.\n\nScope: frontend/src/index.css,\
  \ frontend/tailwind.config.js, frontend/index.html, frontend/src/App.tsx (sidebar\
  \ logo only), frontend/src/styles/TOKENS.md"
has_ui: true
coverage_summary:
  searched:
  - frontend/src/index.css
  - frontend/tailwind.config.js
  - frontend/index.html
  - frontend/src/components/Sidebar.tsx
  - docs/ui-ux-review/brand/logo/
  - docs/ui-ux-review/brand/png/
  - .cronos/pipeline/gui-tokens-brand/scout-report-gui-tokens-brand.md
  excluded:
  - backend/: not relevant to frontend token integration
  - frontend/src/ (components other than Sidebar.tsx): no structural changes needed
      beyond sidebar logo
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: index.css defines status colour tokens (--color-running, --color-success,
    --color-info, --color-warning, --color-danger, --color-neutral) in all three theme
    blocks (:root, .dark, .neon), using contrast-safe darker shades in light theme
    and brand palette values in dark/neon.
  acceptance_criteria:
  - Given the :root block, --color-running resolves to lime-700 (77 124 15), --color-success
    to cyan-600 (8 145 178), --color-info to sky-700 (3 105 161), --color-warning
    to amber-700 (180 83 9), --color-danger to red-700 (185 28 28), --color-neutral
    to the existing ink-faint triplet (107 117 109).
  - Given the .dark block, --color-running resolves to lime brand (184 255 92), --color-success
    to cyan brand (46 196 255), --color-info to sky (56 189 248), --color-warning
    to amber brand (255 166 46), --color-danger to red brand (255 110 92).
  - Given the .neon block, --color-info resolves to a distinct neon sky value (90
    230 255) diverging from the .dark value; all other status tokens match .dark brand
    values.
  - 'All triplets are space-separated RGB (no commas, no # prefix) so Tailwind opacity
    modifiers remain functional.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: index.css defines categorical colour tokens (--cat-goal, --cat-feature,
    --cat-fix, --cat-issue, --cat-plan, --cat-ask) in all three theme blocks with
    per-theme resolved values.
  acceptance_criteria:
  - All six --cat-* variables are present in :root, .dark, and .neon blocks.
  - Each value is a space-separated RGB triplet compatible with Tailwind opacity modifier
    interpolation.
  - Light-theme values provide sufficient contrast on --color-surface-1 (white) backgrounds.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R3
  statement: index.css defines brand identity tokens (--brand, --brand-deep, --brand-light)
    as theme-invariant violet triplets present in the :root block and not overridden
    in .dark or .neon.
  acceptance_criteria:
  - --brand resolves to 122 79 176 (violet) in :root.
  - --brand-deep resolves to 106 63 160 (darker violet) in :root.
  - --brand-light resolves to 184 149 224 (light violet) in :root.
  - The .dark and .neon blocks do not contain --brand, --brand-deep, or --brand-light
    overrides.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R4
  statement: tailwind.config.js exposes all new CSS token variables as Tailwind color
    utilities (color-running, color-success, color-info, color-neutral, brand, brand-deep,
    brand-light, and six cat-* entries) following the existing rgb(var(--color-X)
    / <alpha-value>) pattern.
  acceptance_criteria:
  - theme.extend.colors contains entries for running, success, info, neutral, brand,
    brand-deep, brand-light, and all six cat-* tokens.
  - existing warning and danger entries are preserved unchanged; if the new status
    tokens introduce naming overlap, co-existing aliases are used (e.g. color-warning)
    rather than replacing the existing names.
  - npm run build completes without Tailwind configuration errors.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R5
  statement: 'tailwind.config.js exposes the design-system typography scale as named
    fontSize utilities: text-title (22px/28px lh/600 weight mono), text-eyebrow (11px/14px/600
    mono 0.18em tracking), text-cardtitle (14px/20px/500 sans), text-body (14px/21px/400
    sans), text-meta (12px/16px/400 mono), text-micro (10px/12px/500 mono 0.04em tracking).'
  acceptance_criteria:
  - theme.extend.fontSize contains all six named entries.
  - Each entry uses the [size, { lineHeight, fontWeight, letterSpacing? }] tuple form.
  - text-eyebrow and text-micro include letterSpacing in their tuple configuration.
  - npm run build resolves all six class names without errors.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R6
  statement: 'tailwind.config.js exposes the design-system z-index ladder as named
    zIndex utilities: z-base (0), z-raised (10), z-dropdown (20), z-scrim (30), z-modal
    (40), z-toast (50), z-tooltip (60).'
  acceptance_criteria:
  - theme.extend.zIndex contains all seven named entries with the correct integer
    values.
  - npm run build resolves z-base through z-tooltip without errors.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R7
  statement: 'tailwind.config.js exposes motion duration tokens as named transitionDuration
    utilities: motion-fast (120ms), motion-base (180ms), motion-slow (280ms).'
  acceptance_criteria:
  - theme.extend.transitionDuration defines motion-fast, motion-base, and motion-slow
    with the required millisecond string values.
  - npm run build resolves the three duration class names without errors.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R8
  statement: 'frontend/index.html head section is extended with all required favicon
    and PWA link elements: SVG icon, PNG 32x32, PNG 16x16, apple-touch-icon 180x180,
    and PWA manifest reference.'
  acceptance_criteria:
  - 'The head contains: <link rel="icon" type="image/svg+xml" href="/cronos-favicon.svg"
    />'
  - 'The head contains: <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png"
    />'
  - 'The head contains: <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png"
    />'
  - 'The head contains: <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon-180.png"
    />'
  - 'The head contains: <link rel="manifest" href="/site.webmanifest" />'
  verifying_phase: review
  confidence: 0.95
- requirement_id: R9
  statement: Brand asset files (cronos-favicon.svg, favicon-16.png, favicon-32.png,
    apple-touch-icon-180.png) are copied to frontend/public/ and site.webmanifest
    is created there, so Vite serves them at the root paths referenced in index.html.
  acceptance_criteria:
  - frontend/public/cronos-favicon.svg exists (sourced from docs/ui-ux-review/brand/logo/).
  - frontend/public/favicon-16.png and frontend/public/favicon-32.png exist (sourced
    from docs/ui-ux-review/brand/png/).
  - frontend/public/apple-touch-icon-180.png exists (sourced from docs/ui-ux-review/brand/png/).
  - frontend/public/site.webmanifest exists as a valid JSON file referencing cronos-app-icon-512.png
    as the 512x512 icon.
  verifying_phase: review
  confidence: 0.92
- requirement_id: R10
  statement: 'The Sidebar wordmark in frontend/src/components/Sidebar.tsx is replaced:
    the pulse-dot glyph is removed, an SVG mark (cronos-mark-flat.svg) is rendered
    at 24px, and a JetBrains Mono ''CRONOS'' text node is rendered alongside it, theming
    correctly in all three themes.'
  acceptance_criteria:
  - The <span aria-hidden className='h-2 w-2 rounded-full bg-accent-bright shadow-accent-glow'
    /> element is removed.
  - An img or inline SVG for cronos-mark-flat.svg renders at h-6 w-6 (24px) in the
    wordmark container.
  - The adjacent text node renders 'CRONOS' using font-display (JetBrains Mono) with
    uppercase tracking equivalent to the original.
  - No hardcoded colour values are introduced in the SVG or the surrounding JSX that
    would break theme switching.
  verifying_phase: review
  confidence: 0.88
- requirement_id: R11
  statement: frontend/src/styles/TOKENS.md is created as a structured token reference
    with sections for all token categories and an explicit 'lime reserved for running'
    constraint note.
  acceptance_criteria:
  - File exists at frontend/src/styles/TOKENS.md.
  - 'Document contains named sections for: Status tokens, Categorical tokens, Brand
    tokens, Typography scale, Spacing rhythm, Radius scale, Z-index ladder, Motion
    scale.'
  - Each token entry includes the CSS variable name, semantic role, and per-theme
    RGB values where applicable.
  - The constraint 'lime (#B8FF5C) is reserved for running state only; never use decoratively'
    is explicitly stated.
  verifying_phase: review
  confidence: 0.95
- requirement_id: R12
  statement: 'All changes are strictly additive: no existing Tailwind class names,
    CSS variable names, or component structures are removed or renamed, and both npm
    run build and npm test pass green after all changes.'
  acceptance_criteria:
  - npm run build exits 0 after all changes are applied.
  - npm test exits 0 after all changes are applied.
  - The existing canvas, surface-1/2/3, ink, accent, hairline, warning, danger, boxShadow
    Tailwind utilities remain available and unchanged.
  - The existing --color-warning and --color-danger CSS variable definitions in :root,
    .dark, and .neon are preserved verbatim.
  verifying_phase: test
  confidence: 0.95
metrics:
  tool_calls: 8
  files_read: 5
  memory_hits: 2
---

## Summary

Phase 0 establishes the complete token foundation for the Cronos GUI refactor: six status colour tokens sourced from the brand palette, six categorical type tokens, three violet brand identity tokens, a full design-system scale (typography, z-index, motion durations) in Tailwind config, favicon and PWA wiring in index.html with asset files placed in frontend/public/, a sidebar logo swap from pulse-dot wordmark to flat-mark SVG, and a TOKENS.md reference document. The scope is strictly additive — no existing component classes change. Every later GUI-refactor phase depends on these tokens being present; this is the unblocking prerequisite for all eight subgoals in the gui-refactor tree.

## Scope

### In scope
- `frontend/src/index.css`: add --color-running/success/info/warning/danger/neutral, --cat-goal/feature/fix/issue/plan/ask, and --brand/--brand-deep/--brand-light across all three theme blocks (:root, .dark, .neon)
- `frontend/tailwind.config.js`: expose all new colour tokens, the typography scale (text-title/eyebrow/cardtitle/body/meta/micro), z-index ladder (z-base through z-tooltip), and motion durations (motion-fast/base/slow)
- `frontend/index.html`: add favicon PNG/SVG link elements, apple-touch-icon, and PWA manifest link
- `frontend/public/`: copy cronos-favicon.svg, favicon-16.png, favicon-32.png, apple-touch-icon-180.png; create site.webmanifest
- `frontend/src/components/Sidebar.tsx`: remove pulse-dot glyph; add flat-mark SVG at 24px + JetBrains Mono CRONOS text
- `frontend/src/styles/TOKENS.md`: new token reference document (documentation only, no runtime effect)

### Out of scope
- Any component other than Sidebar.tsx — badges, buttons, cards, modals, and board lanes are untouched in this phase
- Backend changes of any kind
- favicon-48.png link element (Windows tile size; deferred)
- Animated or reactive runtime-state marks in the sidebar (deferred to a later GUI phase)
- Removing or replacing existing --color-warning and --color-danger definitions (new tokens co-exist)
- Applying new typography tokens to existing components (Phase 1+)

### Deferred
- Runtime-state marks and live agent activity indicators in the sidebar (later GUI phase)
- Dark-mode OG image and PWA screenshots entries in site.webmanifest
- Adoption of text-title/eyebrow/cardtitle in existing page headers
- cronos-app-icon-512.png wiring in OG meta tags

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Status colour tokens (running/success/info/warning/danger/neutral) added to all three theme blocks in index.css |
| R2 | Categorical colour tokens (--cat-goal through --cat-ask) added to all three theme blocks in index.css |
| R3 | Brand identity tokens (--brand/--brand-deep/--brand-light) defined in :root as theme-invariant violet triplets |
| R4 | All new colour tokens exposed as Tailwind utilities in tailwind.config.js |
| R5 | Typography scale (text-title through text-micro) added to tailwind.config.js fontSize |
| R6 | Z-index ladder (z-base through z-tooltip) added to tailwind.config.js zIndex |
| R7 | Motion duration tokens (motion-fast/base/slow) added to tailwind.config.js transitionDuration |
| R8 | Favicon, apple-touch-icon, and PWA manifest link elements wired in frontend/index.html head |
| R9 | Brand asset files and site.webmanifest placed in frontend/public/ |
| R10 | Sidebar wordmark replaced: pulse-dot removed, flat-mark SVG + JetBrains Mono CRONOS text added |
| R11 | frontend/src/styles/TOKENS.md token reference document created |
| R12 | All changes are additive and non-breaking; npm run build and npm test pass green |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — Six status tokens present with correct RGB triplets in :root (contrast-safe shades), .dark (brand palette), and .neon (brand + sky shift for info)
- R2 — Six categorical tokens present in all three theme blocks as space-separated RGB triplets
- R3 — Three brand violet tokens in :root only (122 79 176 / 106 63 160 / 184 149 224); absent from .dark/.neon overrides
- R4 — New colour tokens in tailwind.config.js theme.extend.colors using rgb(var(--X) / <alpha-value>); build passes; existing warning/danger preserved
- R5 — Six fontSize entries with [size, {lineHeight, fontWeight, letterSpacing?}] tuples; eyebrow and micro include tracking; build passes
- R6 — Seven zIndex entries (base=0 through tooltip=60); build passes
- R7 — Three transitionDuration entries (120ms/180ms/280ms); build passes
- R8 — Five link elements present in index.html head: SVG icon, PNG 32x32, PNG 16x16, apple-touch-icon 180x180, manifest
- R9 — Four asset files + site.webmanifest present in frontend/public/; webmanifest references 512px app icon
- R10 — Pulse-dot removed; flat-mark SVG at h-6 w-6; CRONOS text in font-display; no hardcoded colours; themes correctly
- R11 — TOKENS.md at frontend/src/styles/TOKENS.md with eight sections; lime-reserved rule documented
- R12 — No existing utilities removed; npm run build exits 0; npm test exits 0

## Traceability

The full requirement -> acceptance criteria -> verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | index.css status colour tokens in all three theme blocks with correct per-theme RGB triplets |
| R2 | test | index.css categorical colour tokens in all three theme blocks |
| R3 | test | index.css brand identity tokens as theme-invariant violet triplets in :root only |
| R4 | test | tailwind.config.js exposes all new colour tokens as Tailwind utilities |
| R5 | test | tailwind.config.js typography scale as named fontSize utilities |
| R6 | test | tailwind.config.js z-index ladder as named zIndex utilities |
| R7 | test | tailwind.config.js motion duration tokens as named transitionDuration utilities |
| R8 | review | frontend/index.html head wires favicon, apple-touch-icon, and PWA manifest link elements |
| R9 | review | Brand asset files and site.webmanifest present in frontend/public/ |
| R10 | review | Sidebar wordmark replaced with flat-mark SVG + JetBrains Mono CRONOS text; pulse-dot removed |
| R11 | review | frontend/src/styles/TOKENS.md created with all eight required sections |
| R12 | test | All changes additive and non-breaking; build and test both exit 0 |

## Assumptions

- has_ui=true rationale: the request explicitly names frontend/src/index.css, frontend/tailwind.config.js, frontend/index.html, Sidebar.tsx, and TOKENS.md — all frontend deliverables with direct visual impact.
- The existing `--color-warning` and `--color-danger` CSS variables in index.css are preserved. The new status tokens R1 introduces use the same names; the design agent must decide whether to merge (update existing triplets to match brand values) or use aliased names. Merging is preferred for simplicity but requires verifying no existing component depends on the legacy amber/red shades being different from the brand values.
- `--color-neutral` maps to the existing `--color-ink-faint` triplet values per theme (107 117 109 in light / 126 142 131 in dark / 66 102 168 in neon) — aliasing not introducing new hue.
- The flat-mark SVG (cronos-mark-flat.svg) is assumed to use `currentColor` or no fill attribute, allowing theme adaptation via CSS `color`. If the file uses hardcoded fills, the implementor must patch the SVG in the same sidebar iteration.
- JetBrains Mono is confirmed loaded in index.html line 59; no additional font wiring needed.
- Tailwind v3.4 confirmed; `<alpha-value>` and fontSize tuple syntax are supported.
- site.webmanifest is a new file (not currently present in the repo); its creation is in-scope per the request.
- Neon --color-info (90 230 255) matches the --color-accent-bright neon value — this collision is noted in Open questions for the design agent to resolve.

## Open questions

- Q1: In the neon theme, the scout assigns --color-info the value 90 230 255, which is the same triplet as --color-accent-bright in neon. The design agent should assign a differentiated neon info value or explicitly document that the overlap is intentional and visually acceptable.
- Q2: The existing tailwind.config.js warning and danger entries (lines 60-61) and the new R1 --color-warning/--color-danger status tokens may cause naming ambiguity. Design agent should decide: (a) update existing CSS variable triplets to match brand values and keep existing Tailwind names, or (b) add prefixed aliases (color-warning, color-danger) alongside the existing warning/danger entries.

## Next consumer brief

Design agent: read traceability[] for the complete requirement set (12 items). has_ui=true, pure frontend, no backend iterations required. Suggested 5-iteration DAG: I1 (index.css: R1-R3), I2 (tailwind.config.js: R4-R7), I3 (index.html + public/ assets: R8-R9), I4 (Sidebar.tsx logo swap: R10), I5 (TOKENS.md + R12 verification pass). Resolve Open questions Q1 and Q2 in the design report before handing to implementor. Key risk: flat-mark SVG currentColor assumption (R10) — verify before I4 scope is locked. The warning/danger naming decision (Q2) affects I1 and I2 scope boundaries.
