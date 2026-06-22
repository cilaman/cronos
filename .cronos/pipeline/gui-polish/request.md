GUI polish — touch targets, Toast, utility primitives (Phase 6)

A polish sweep covering three areas: touch targets, a Toast notification system,
and extraction of utility primitives from existing inline usage. This closes the gap
between the design system spec and the remaining ad-hoc patterns.

**Concrete changes:**
- **Touch targets:** sweep all interactive elements below 44px — lane header ＋/×
  (p-1≈24px → p-2.5), Detail modal close (p-1), IconButton sm(28px)/md(32px) hit areas
  (expand padding not glyph). Use `min-w-[44px] min-h-[44px]` with padding correction.
- **Toast system:** `Toast.tsx` + `ToastProvider.tsx` + `useToast()` hook —
  `tone: success|warning|danger|info`, `message: string`, `action?: {label, onClick}`,
  auto-dismiss 3–5s, `aria-live="polite"`, no focus steal. Wire into App.tsx.
- **Tabs.tsx:** extracted from Detail/SpaceTools inline tab switching pattern.
  Props: `items: {value, label}[]`, `value`, `onChange`.
- **Dropdown.tsx + Menu.tsx:** consolidate ViewPicker / SpaceFilter trigger patterns.
  Headless (or minimal) focus management; z-dropdown(20).
- **Tooltip.tsx:** keyboard-reachable, for icon-only affordances. z-tooltip(60).
- **StatTile.tsx:** `label`, `value`, `delta?`, `tone?` — extract from Dashboard/Stats.
- **ProgressBar.tsx:** `value`, `max`, `segments?`, `tone?`, `showLabel?`.
- **Copy rewrites:** replace "Error: {message}" with user-voiced cause + fix; loading
  states say what they're loading; empty states include a primary action.
- **Optional:** ESLint rule banning raw `(text|bg|border)-(red|emerald|amber|…)-\d`
  in `.tsx` files to prevent regression.

**Exit criteria:** all interactive elements ≥44px; Toast renders with aria-live; utility
primitives available; error/loading/empty copy user-voiced; `npm run build` + `npm test` green.

Scope: frontend/src/components/ui/Toast.tsx, frontend/src/components/ui/Tabs.tsx, frontend/src/components/ui/Dropdown.tsx, frontend/src/components/ui/Tooltip.tsx, frontend/src/components/ui/StatTile.tsx, frontend/src/components/ui/ProgressBar.tsx, frontend/src/components/Lane.tsx, frontend/src/pages/Dashboard.tsx, frontend/src/pages/Stats.tsx
