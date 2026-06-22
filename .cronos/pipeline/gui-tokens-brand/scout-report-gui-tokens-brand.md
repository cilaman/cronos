---
cc_version: "1.0"
agent: pipeline-scout
slug: gui-tokens-brand
phase: scout
status: done
confidence: 0.95
inputs_used:
  - memory:project_gui_refactor_board_setup
  - memory:project_branding
  - memory:project_dashboard_design
  - docs/ui-ux-review/02-design-system.md
  - docs/ui-ux-review/05-roadmap.md
  - docs/ui-ux-review/06-brand.md
  - docs/ui-ux-review/brand/tokens/tokens.css
  - docs/ui-ux-review/brand/tokens/tokens.json
  - frontend/src/index.css
  - frontend/tailwind.config.js
  - frontend/index.html
  - frontend/src/components/Sidebar.tsx
outputs_produced:
  - .cronos/pipeline/gui-tokens-brand/scout-report-gui-tokens-brand.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - docs/ui-ux-review/ (brand assets + design tokens)
    - frontend/src/ (current token structure, components)
    - frontend/ (HTML, Tailwind config)
  excluded:
    - backend/: not relevant to frontend token work
    - tests/: asset testing deferred to implementation
  strategies:
    - memory_retrieval
    - glob_structural
    - read_targeted
brief: "GUI tokens + brand integration (Phase 0)"
metrics:
  tool_calls: 12
  files_read: 9
  memory_hits: 3
---

## Summary

Phase 0 integrates three missing token layers into the frontend: **status colour tokens** (running/success/info/warning/danger/neutral sourced from brand palette), **categorical type tokens** (goal/feature/fix/issue/plan/ask), and **identity brand tokens** (violet). The scope also wires favicons/apple-touch-icon from brand/png/, replaces the sidebar wordmark with flat-mark SVG + live JetBrains Mono text, and documents all new tokens. All three themes (light/dark/neon) must resolve correctly; no other components change visually yet. Exit criteria: tokens work in all three themes, favicon + sidebar logo live, `npm run build` + `npm test` green.

## Coverage

### Searched
- `docs/ui-ux-review/`: brand assets, design-system.md (§2.1–2.6), brand.md (§6.4 colour mapping), roadmap.md (Phase 0 spec)
- `docs/ui-ux-review/brand/tokens/`: tokens.css (canonical source) + tokens.json (structured reference)
- `docs/ui-ux-review/brand/logo/`: cronos-mark-flat.svg + cronos-favicon.svg verified present
- `docs/ui-ux-review/brand/png/`: favicon sizes (16/32/48px) + apple-touch-icon-180.png present
- `frontend/src/index.css`: existing `:root` / `.dark` / `.neon` token structure + current chrome palette
- `frontend/tailwind.config.js`: theme.extend.colors section (tokenizes CSS vars via rgb())
- `frontend/index.html`: current head; no favicon/apple-touch-icon wired yet
- `frontend/src/components/Sidebar.tsx`: wordmark at lines 122–128 (text-only "Cronos")

### Excluded
- Backend modules: not relevant to frontend token integration
- Test files: test wiring deferred to implementation phase
- Noscript section in index.html: immutable fallback content

### Strategies
- memory_retrieval: 3 relevant entries found (gui-refactor board setup, branding decision, dashboard structure)
- glob_structural: located brand assets (logo SVGs, PNG set), CSS/config files
- read_targeted: deep-read design tokens (tokens.css brand values + RGB mapping), current theme structure, sidebar component

## Findings

### Status colour tokens (brand-sourced)

**Brand state palette** (dark-surface-tuned, from `brand/tokens/tokens.css` lines 13–18):
- Idle: `#7A4FB0` (violet, brand identity)
- Active: `#B8FF5C` (lime; **reserved for running only**)
- Passed: `#2EC4FF` (cyan; done/success, distinct from lime for colourblind)
- Blocked: `#FFA62E` (amber; waiting/caution)
- Failed: `#FF6E5C` (red; error/destructive)

**Light theme mapping** (per `06-brand.md §6.4`): use darker shades of the same hue for contrast-safe badge rendering (tone colour as text on tinted fill):
- `--color-running`: lime-700 `77 124 15` (light) / lime `184 255 92` (dark/neon)
- `--color-success`: cyan-600 `8 145 178` (light) / cyan `46 196 255` (dark/neon)
- `--color-warning`: amber-700 `180 83 9` (light) / amber `255 166 46` (dark/neon)
- `--color-danger`: red-700 `185 28 28` (light) / red `255 110 92` (dark/neon)
- `--color-info`: sky-700 `3 105 161` (light) / sky `56 189 248` + neon `90 230 255` (design-system, not brand)
- `--color-neutral`: ink-faint (all themes; backlog/idle/archived)

**Brand identity tokens**:
- `--brand`: `122 79 176` (violet, theme-independent)
- `--brand-deep`: `106 63 160` (darker variant for headers)
- `--brand-light`: `184 149 224` (lighter variant for accents on dark)

**Decision rule** (`06-brand.md §6.1`): lime means running only. Never decorative lime. This prevents false "agent active" signals.

### Typography + spacing + radius + z-index + motion scales

Per `02-design-system.md §2.2–2.6`, add to `tailwind.config`:

**Type scales** (font-size / line-height / font-weight):
- `text-title`: 22px / 28 / 600 (JetBrains Mono, page h1 only)
- `text-eyebrow`: 11px / 14 / 600 (mono, uppercase, 0.18em tracking, section labels)
- `text-cardtitle`: 14px / 20 / 500 (Geist sans, card/panel headings)
- `text-body`: 14px / 21 / 400 (sans, prose)
- `text-meta`: 12px / 16 / 400 (mono, tabular-nums, timestamps/counts)
- `text-micro`: 10px / 12 / 500 (mono, uppercase, 0.04em tracking, badges)

**Spacing steps** (enforce 4/8 rhythm; only: 4, 8, 12, 16, 24, 32, 48):
- Page padding: 24 (mobile) / 32 (desktop) → `p-6 lg:p-8`
- Section gap: 24 → 32
- Card padding: 12 (tight) / 16 (default)
- Inline control gap: 8 → `gap-2`
- Badge row gap: 6 → `gap-1.5`

**Radius** (four values only):
- `rounded-sm`: 4px (badges, chips, inline tags)
- `rounded-md`: 6px (buttons, inputs, cards)
- `rounded-lg`: 8px (panels, lanes, modals, drawers)
- `rounded-full`: status dots, avatars, pills

**Z-index ladder**:
- base: 0
- raised: 10 (sticky toolbars, lane headers)
- dropdown: 20 (menus, popovers)
- scrim: 30 (modal/drawer backdrop)
- modal: 40 (dialog/drawer panel)
- toast: 50 (notifications)
- tooltip: 60 (always on top)

**Motion scale**:
- `motion-fast`: 120ms ease-out (hover, press, colour/opacity)
- `motion-base`: 180ms ease-out enter / ease-in exit (expand/collapse, list entrance, tab switch)
- `motion-slow`: 280ms ease-out (modal/drawer/page transitions)

### Favicon + apple-touch-icon wiring

**Required in `frontend/index.html` head** (before `</head>`):
- `<link rel="icon" href="/favicon.ico" />` (fallback)
- `<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />`
- `<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png" />`
- `<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon-180.png" />`
- `<link rel="manifest" href="/site.webmanifest" />`
- SVG favicon fallback: `<link rel="icon" type="image/svg+xml" href="/cronos-favicon.svg" />`

**Files to copy to `frontend/public/`**:
- `docs/ui-ux-review/brand/png/favicon-16.png`, `favicon-32.png`, `favicon-48.png`
- `docs/ui-ux-review/brand/png/apple-touch-icon-180.png`
- `docs/ui-ux-review/brand/logo/cronos-favicon.svg`
- Create `frontend/public/site.webmanifest` (PWA manifest; reference `cronos-app-icon-512.png` if available)

### Sidebar logo replacement

**Current state** (`frontend/src/components/Sidebar.tsx:122–128`): text-only wordmark
```tsx
<span
  aria-hidden
  className="h-2 w-2 rounded-full bg-accent-bright shadow-accent-glow"
/>
<span className="font-display text-sm font-semibold uppercase tracking-[0.22em] text-ink">
  Cronos
</span>
```

**Replace with flat-mark SVG + live text** (per `06-brand.md §6.2`):
- Load `cronos-mark-flat.svg` from `docs/ui-ux-review/brand/logo/` into `frontend/src/components/` (or import as React component)
- Render at 24px (min size per brand guidelines)
- Add live "CRONOS" text in JetBrains Mono alongside mark
- Text themes correctly on all three themes (no hardcoded colours in SVG)
- Remove pulse-dot glyph (will be replaced by state marks in later phases)

### Token reference document

Create `frontend/src/styles/TOKENS.md`:
- Organize by category: status (running/success/info/warning/danger/neutral), categorical (goal/feature/fix/issue/plan/ask), brand (brand/brand-deep/brand-light)
- For each token, list the CSS variable name, the semantic meaning, and RGB values per theme
- Include type scale table (text-title, text-eyebrow, …) with font-family / size / weight / tracking
- Include spacing/radius/z-index/motion scales as reference tables
- Note the "lime is reserved for running" rule

### Tailwind config extension

**Current structure** (`frontend/tailwind.config.js:35–62`): colors section already uses `rgb(var(--color-X) / <alpha-value>)` pattern.

**To add** in `theme.extend`:
1. All new CSS variables (running/success/info/warning/danger/neutral/brand/brand-deep/brand-light) as `colors` entries
2. Type scale utilities (text-title, text-eyebrow, …) via `fontSize` + `fontWeight` + `lineHeight` and/or custom utility classes
3. Named spacing steps (4, 8, 12, 16, 24, 32, 48) — Tailwind already supports these; verify they're exposed
4. Radius scale (sm=4px, md=6px, lg=8px, full) — already standard; document enforcement rule
5. Z-index ladder (base/raised/dropdown/scrim/modal/toast/tooltip) via `zIndex` entries
6. Motion scale (fast/base/slow) via custom `@layer utilities` keyframe references or CSS custom properties

### Current index.css theme structure

**Existing pattern** (lines 14–120):
- `:root` = light theme
- `.dark` = dark theme (overrides)
- `.neon` = neon theme (must come after .dark so both classes on `<html>` let neon win)

**To extend**: add status/categorical/brand tokens in the same three blocks, maintaining the `--color-X: R G B;` space-separated format for opacity modifier compatibility.

### No other components visually impacted

The scope is **token definition only**. No component code changes (except sidebar logo replacement). Existing badge styling, button sizes, layout remain untouched until later phases. This ensures minimal risk and a single verifiable deliverable (tokens resolve, favicon appears, sidebar logo updated).

## Assumptions
- Tailwind v3.4+ is in use; `<alpha-value>` placeholder works as documented.
- Favicon copying is done via implementation-phase asset copy (not scout scope).
- The sidebar logo replacement is the sole component-code change; all else is token + HTML meta.
- Light theme colour shades are sufficiently distinct from dark/neon brand values (verified by design doc §6.4 contrast justification).
- JetBrains Mono font already loaded in `index.html` via Google Fonts (verified line 59).

## Open questions
- None.

## Next consumer brief

**Analysis agent should read:**
1. `coverage_summary.searched` — documents token locations and design sources
2. `## Findings` sections on status/categorical/brand colour mapping per theme (RGB triplets)
3. Type/spacing/radius/z-index/motion scale tables for implementation reference
4. "Sidebar logo replacement" section describing the flat-mark SVG + text node approach
5. "Tailwind config extension" for scope of config changes needed

**Key decision points for analyst:**
- Confirm neon-theme status token values (cyan-shifted `--color-info`? cyan for accent too?)
- Verify apple-touch-icon size (180px stated; confirm it's the only size needed)
- Clarify whether `site.webmanifest` PWA generation is Phase 0 scope or Phase 1

**Unresolved blockers:**
- None; all design sources are committed and canonical.
