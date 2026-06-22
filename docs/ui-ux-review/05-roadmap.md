# 5 · Execution Roadmap & Component Specs

A phased plan to execute the unification as its own goal later. Specs below are
**contracts (props + behavior)**, not implementation. Each phase is independently
shippable and leaves the app green.

---

## Phases

### Phase 0 — Tokens, brand & docs (P0, ~1 day, minimal visual change)
- Add status (`--color-running/success/info/neutral`) and categorical (`--cat-*`) CSS
  variables to `:root`, `.dark`, `.neon` in `index.css`; expose via `tailwind.config`.
  Source the status values from the **brand state palette** ([06-brand.md §6.4](06-brand.md)):
  lime=`running`, cyan=`success/passed`, amber=`warning/blocked`, red=`danger/failed`;
  light theme uses the contrast-safe darker shades.
- Add `--brand` / `--brand-deep` / `--brand-light` (violet identity) from
  `brand/tokens/tokens.css`.
- Wire favicons + apple-touch-icon + PWA manifest from `brand/png/` and
  `brand/logo/cronos-favicon.svg`; swap the app-shell wordmark to `mark-flat` SVG + a live
  `JetBrains Mono` text node (themes correctly on all three).
- Add the type/spacing/radius/z-index/motion scales to `tailwind.config` (or a documented
  `theme.extend`), mirroring §2.2–2.6.
- Write `frontend/src/styles/TOKENS.md` (or extend CLAUDE.md) as the cited reference.
- **Exit:** tokens resolve in all three themes; favicon + sidebar logo live; nothing else
  visually changed yet.

### Phase 1 — Layout primitives (P0, ~1 day)
- Ship `PageHeader` + `PageContainer`; adopt on **all** pages. Delete per-page title
  markup. This alone unifies the product's first impression.
- **Exit:** every page top is identical in structure; one title size; two container widths.

### Phase 2 — Badge unification (P0→P1, ~2 days)
- Ship `Badge` (tone-driven, the §2.1 recipe). Add `badgeTone()` mapping helpers for
  priority/state/type/mode/run-status.
- Replace the duplicated style objects in `Card`, `Detail`, `TaskForm`, `FeatureForm`,
  `FeatureDetail`, `ConversationEntry`, `HarnessRunsPage`; fix `RunOverlay` hex.
- **Exit:** zero raw palette classes in badge logic; badges correct in neon theme.

### Phase 3 — Button/IconButton enforcement (P1, ~2 days)
- Expand `Button` (add `tertiary`, `link`; `focus-visible` ring; `loading`; leading-icon).
- Add the toolbar-chip / dropdown-trigger / segmented / list-row archetypes.
- Migrate the ~160 ad-hoc buttons in waves (shell → board → pages).
- **Exit:** inline button className strings essentially gone; focus rings everywhere.

### Phase 4 — Icons (P1, ~1.5 days)
- Add `lucide-react`; create an `Icon` wrapper with `icon-sm/md/lg` tokens.
- Replace emoji + inline SVG (file categories, chrome glyphs, nav). Keep space-avatar emoji.
- **Exit:** one icon language; no structural emoji.

### Phase 5 — Modal + Skeleton + states (P1, ~1.5 days)
- Enforce `Modal` contract; migrate the 4 ad-hoc modals.
- Ship `Skeleton`; replace spinner/text loaders; reserve space.
- **Exit:** one scrim/escape/focus behavior; no layout shift on load.

### Phase 6 — Polish (P2, ~2 days)
- Touch-target sweep (44px). `Toast`/`aria-live`; rewrite error/empty copy (user voice).
- `Tabs`, `Dropdown`, `SegmentedControl`, `Tooltip`, `StatTile`, `ProgressBar` extraction.
- Stats/Dashboard viz pass (legends, tooltips, empty/loading); mobile refinements.
- Optional ESLint guardrail: ban `(text|bg|border)-(gray|slate|red|emerald|…)-\d` and raw
  hex in `.tsx` to prevent regression.

---

## Component specs (contracts only)

> Props are the contract; styling derives from the tokens in [02](02-design-system.md).
> No implementation here by design.

**`<Badge tone size?>`**
- `tone`: `running | success | info | warning | danger | neutral | goal | feature | fix | issue | plan | ask`
- `size?`: `sm`(default) — renders the §2.1 recipe; children = label; optional leading dot/icon.

**`<PageHeader>`**
- `title: string` · `breadcrumb?: {label, to?}[]` · `subtitle?: ReactNode` ·
  `actions?: ReactNode` (0–3 buttons; overflow → menu) · `sticky?: boolean`.

**`<PageContainer width?>`**
- `width?`: `content`(1280, default) | `reading`(768) · applies `p-6 lg:p-8`.

**`<Button variant size? loading? leadingIcon? fullWidth?>`**
- `variant`: `primary | secondary | tertiary | ghost | danger | link`
- `size`: `sm | md(default)` · always includes `focus-visible` ring + 44px hit area on `md`.

**`<IconButton icon variant size? label tooltip?>`**
- `label` required (a11y) · `tooltip?` → `Tooltip` · guaranteed ≥44px hit area · `focus-visible` ring.

**`<Modal open onClose title? size? dismissable?>`**
- scrim `bg-black/60`+blur (z-scrim), panel z-modal, scale-fade `motion-slow`, Escape,
  focus-trap, focus-return; `dismissable=false` for unsaved-changes guard; single `X` close.

**`<Skeleton variant lines? />`** — `variant`: `text | block | card`; shimmer at `motion-base`; reserves space.

**`<Toast />` / `useToast()`** — `tone`, `message`, `action?` (e.g. Undo), auto-dismiss 3–5s, `aria-live="polite"`, no focus steal.

**`<Tabs items value onChange />`** · **`<SegmentedControl />`** · **`<Dropdown trigger items />`** ·
**`<Tooltip content>`** · **`<StatTile label value delta? tone? sparkline? />`** ·
**`<ProgressBar value max segments? tone? showLabel? />`** — extract from existing inline usage.

---

## Acceptance criteria for the whole effort

1. **Zero** raw Tailwind-palette color classes and raw hex in `.tsx` (except dynamic
   `style={{ backgroundColor: space.color }}` and theme-preview swatches).
2. Every page uses `PageHeader`/`PageContainer`; exactly one page-title size; ≤2 container widths.
3. Every badge renders through `<Badge>`; verified correct in light **and** dark **and** neon.
4. `lucide-react` is the only icon source (plus user space-avatars); no structural emoji.
5. All interactive elements have a visible `focus-visible` state and ≥44px hit area.
6. No layout shift on data load (skeletons + reserved space); one modal behavior.
7. The three themes still pass contrast (AA body, AA-large secondary) — tested independently.
8. `npm run build` + `npm test` green; visual parity confirmed on 375 / 768 / 1280 widths.

---

## Notes & non-goals

- **Not** changing the themes or the operator-console aesthetic — this is consolidation.
  The mono-label / hairline-grid / status-as-light identity is the asset. The **brand layer**
  ([06-brand.md](06-brand.md)) is additive: it formalises the logo/identity (violet) and the
  status palette (lime=running reserved, cyan=passed, …) without touching the per-theme chrome
  accent. Promoting violet to the chrome accent is an explicit *future* option, not this scope.
- **Not** adopting a component framework (shadcn/Radix) wholesale — the existing
  primitives are good; we expand them. (A headless lib for `Dropdown`/`Tooltip`/`Tabs`
  focus-management is a reasonable Phase-6 implementation detail to evaluate then.)
- Charts stay hand-coded unless richer interactive viz is requested; if so, evaluate a
  small lib in Phase 6 against the `ProgressBar`/`StatTile` primitives first.
- This document set is the analysis deliverable. Implementation should be run as a
  separate goal, phase by phase, each behind the acceptance criteria above.
