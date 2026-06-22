GUI tokens + brand integration (Phase 0)

Adds the missing token layer that every later phase depends on, plus wires the
brand assets (favicon, sidebar logo, runtime-state marks) that don't yet exist in the product.

**Concrete changes (minimal visual impact):**
- `index.css`: add `--color-running/success/info/warning/danger/neutral` status tokens
  (light: contrast-safe darker shades; dark/neon: brand palette values — lime=running,
  cyan=success, amber=warning, red=danger, from `docs/ui-ux-review/brand/tokens/tokens.css`).
- `index.css`: add `--cat-goal/feature/fix/issue/plan/ask` categorical tokens per theme.
- `index.css`: add `--brand/--brand-deep/--brand-light` violet identity tokens.
- `tailwind.config.js`: expose all new tokens plus scales — type
  (text-title 22px mono / text-eyebrow 11px / text-cardtitle 14px / text-body 14px /
  text-meta 12px / text-micro 10px), spacing steps (4/8/12/16/24/32/48),
  radius (sm=4px / md=6px / lg=8px / full), z-index (base/raised/dropdown/scrim/
  modal/toast/tooltip), motion (motion-fast 120ms / motion-base 180ms / motion-slow 280ms).
- `frontend/index.html`: wire favicon PNG/SVG, apple-touch-icon, PWA manifest from
  `docs/ui-ux-review/brand/png/` and `brand/logo/cronos-favicon.svg`.
- Sidebar logo (App.tsx or NavBar component): replace existing wordmark with the
  flat-mark SVG (`brand/logo/cronos-mark-flat.svg`) + live JetBrains Mono "CRONOS" text
  node (themes correctly on all three themes).
- `frontend/src/styles/TOKENS.md`: token reference document.

**Exit criteria:** tokens resolve in all three themes; favicon + sidebar logo updated;
`npm run build` + `npm test` green; no other component visually changed.

Scope: frontend/src/index.css, frontend/tailwind.config.js, frontend/index.html, frontend/src/App.tsx (sidebar logo only), frontend/src/styles/TOKENS.md
