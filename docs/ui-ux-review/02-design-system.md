# 2 · The Unified Design System

This is the proposed single source of truth. It **extends** the existing token system
rather than replacing it — every value below is chosen to sit naturally with the
current `canvas / surface / ink / accent / hairline` vocabulary and the three themes.

> Convention: colors are stored as space-separated RGB triplets in CSS variables
> (`--token: 74 222 128;`) so Tailwind's `<alpha-value>` opacity modifiers keep working,
> exactly as the codebase does today.

---

## 2.1 Color

### What exists (keep)
`canvas`, `surface-1/2/3`, `ink / ink-muted / ink-faint`, `accent / -bright / -dim / -deep`,
`hairline / -strong`, `warning`, `danger`. Defined in `index.css` for `:root` (light),
`.dark`, `.neon`. These cover **chrome** (surfaces, text, borders, primary action) and
are used cleanly. Do not change them.

### The hole: status & categorical color
Badges encode meaning with raw Tailwind palette classes that (a) duplicate across files
and (b) do **not** participate in theming — in the neon theme the accent is cyan but a
"feature" badge is still emerald. Fix by adding two new token families.

**A. Status tokens** (semantic state — values now sourced from the **brand state palette**;
see [06-brand.md §6.4](06-brand.md)). The brand hues are dark-surface-tuned, so light uses
contrast-safe darker shades of the same hue (badge tone = text on a tinted fill → must
clear 4.5:1):

| Token | Meaning | Light | Dark / Neon (brand) | Brand source | Used by |
|-------|---------|------|------|------|---------|
| `--color-running` | active / in-progress / running | lime-700 `77 124 15` | **lime `184 255 92`** | `active` | active lane, running runs, agent live |
| `--color-success` | done / passed / gate ok | cyan-600 `8 145 178` | **cyan `46 196 255`** | `passed` | done state, passed tests, goal complete |
| `--color-info` | linked / informational | sky-700 | sky-400 | *(none — design system)* | "linked", neutral info |
| `--color-warning` | waiting / blocked / caution | amber-700 | **amber `255 166 46`** | `blocked` | waiting state, blocked, awaiting decision |
| `--color-danger` | failed / destructive / error | red-700 | **red `255 110 92`** | `failed` | failed tests, run error, delete |
| `--color-neutral` | backlog / idle / archived | ink-faint | ink-faint | *(design system)* | backlog, archived, "auto" mode |
| `--brand` | identity · idle-state mark | violet `122 79 176` | violet `122 79 176` | identity / `idle` | logo, wordmark, idle mark *(not a chrome accent)* |

> **Decision (brand integration):** `running` is **lime in every theme** — including neon —
> so that green *only ever* signals "agent running" ([06-brand.md §6.1](06-brand.md): lime is
> reserved). `done/passed` is **cyan** (`success`), deliberately distinct from running-lime
> for colourblind users. `info` (sky) is the one status token not from the brand. The chrome
> **accent stays per-theme** (green light/dark, cyan neon) — `--brand` violet is identity
> only. See the residual-tension note in [§6.5](06-brand.md).

**B. Categorical tokens** (task type & agent mode — no inherent semantics, just need to
be *distinguishable* and *theme-harmonious*). Define a small fixed palette tuned per
theme so hues stay in the theme's family instead of clashing primary colors:

| Token | Applied to | Light hue | Dark / Neon hue |
|-------|-----------|-----------|------------------|
| `--cat-goal` | type: goal | violet-600 | violet-400 |
| `--cat-feature` | type: feature | emerald-700 | emerald-400 |
| `--cat-fix` | type: fix | rose-700 | rose-400 |
| `--cat-issue` | type: issue | orange-600 | orange-400 |
| `--cat-plan` | mode: plan | indigo-600 | indigo-400 |
| `--cat-ask` | mode: ask | violet-500 | violet-400 |

(Mode `auto` → `--color-neutral`.) These are the *only* categorical hues allowed; six is
enough and keeps the board scannable. Priority P1–P5 maps onto status, not categorical:
**P1 `danger` → P2 `warning` → P3 `neutral` → P4 `info` → P5 `neutral/faint`** (a
hot→cool ramp), replacing the current bespoke red/orange/amber/teal/surface objects.

### The one badge recipe
Every badge — state, priority, type, mode, run status — renders through a single helper
and a single class recipe (tone-tinted fill + solid text + inset ring):

```
inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5
font-mono text-[10px] uppercase tracking-wide leading-none ring-1 ring-inset
bg-{tone}/12  text-{tone}  ring-{tone}/30
```

`<Badge tone="running">active</Badge>` — see the API in [05-roadmap.md](05-roadmap.md).
This deletes ~5 duplicated style maps and makes every status colour theme-aware for free.

### Contrast guardrails
- Body text ≥ 4.5:1, large/secondary ≥ 3:1, in **all three** themes (test each separately).
- Known issue to fix: `ink-faint` on `surface-2` is borderline — don't use it for
  meaningful labels (only decorative/tertiary). Bump to `ink-muted` for labels.
- Never encode meaning by color alone — every status badge carries a word or icon too
  (the mono label already does this; keep it when shrinking to dots in tight mode by
  adding a `title`/`aria-label`).

---

## 2.2 Typography

Keep the pairing — it *is* the brand: **JetBrains Mono** (`font-display`/`font-mono`) for
labels, data, eyebrows, page titles; **Geist** (`font-sans`) for prose and card titles.
Add one enforced scale (role → size/weight/spacing). Stop inventing per-page sizes.

| Role | Token | Font | Size / line-height | Weight | Tracking | Where |
|------|-------|------|--------------------|--------|----------|-------|
| Page title | `text-title` | mono | 22 / 28 | 600 | -0.01em | `<PageHeader>` h1 **only** |
| Section / eyebrow | `text-eyebrow` | mono | 11 / 14 | 600 | 0.18em, UPPER | section labels, breadcrumbs |
| Card / panel title | `text-cardtitle` | sans | 14 / 20 | 500 | normal | card & panel headings |
| Body | `text-body` | sans | 14 / 21 | 400 | normal | prose, descriptions |
| Meta / caption | `text-meta` | mono | 12 / 16 | 400 | normal, tabular-nums | timestamps, counts |
| Micro / badge | `text-micro` | mono | 10 / 12 | 500 | 0.04em, UPPER | badges, pills |

Rules: one `h1` per page (the page title); section labels are the eyebrow style, not
shrunken titles; numeric columns use `tabular-nums` (already done for timestamps —
extend to stats tables); body line-length 60–75ch on desktop, never edge-to-edge.

---

## 2.3 Spacing

Enforce the 4/8 rhythm. Allowed steps only: **4, 8, 12, 16, 24, 32, 48**.

| Context | Value |
|---------|-------|
| Page padding | 24 mobile · 32 desktop (`p-6 lg:p-8`) |
| Section vertical gap | 24 → 32 |
| Card padding | 12 (tight) · 16 (default) |
| Inline control gap | 8 (`gap-2`) |
| Badge row gap | 6 (`gap-1.5`) |
| Lane gap | 8 → 12 (`gap-2 lg:gap-3`) |

---

## 2.4 Radius

Pick four and assign them — kills the `rounded` vs `rounded-md` vs `rounded-lg` drift
(283/85/19 occurrences today).

| Token | px | Applies to |
|-------|----|-----------|
| `rounded-sm` | 4 | badges, chips, inline tags |
| `rounded-md` | 6 | **buttons, inputs, cards** (one value for both — stops the card/button mismatch) |
| `rounded-lg` | 8 | panels, lanes, modals, drawers |
| `rounded-full` | — | status dots, avatars, pills, pulse indicators |

Everything else (`rounded-xl`, `rounded-sm` misuse, bare `rounded`) is migrated to one of
these four.

---

## 2.5 Z-index

One ladder, named. Today 10/20/30/40/50 are used interchangeably for different layers.

| Layer | z | Examples |
|-------|---|----------|
| base | 0 | normal content |
| raised | 10 | sticky toolbars, lane headers |
| dropdown | 20 | menus, popovers, view picker, space filter |
| scrim | 30 | modal/drawer backdrop |
| modal | 40 | dialog/drawer panel |
| toast | 50 | notifications |
| tooltip | 60 | tooltips (always on top) |

---

## 2.6 Motion

Tasteful already; just needs a scale. Keep the existing `streamEnter`/`pulseDot` and the
`prefers-reduced-motion` guard.

| Token | Duration | Easing | Use |
|-------|----------|--------|-----|
| `motion-fast` | 120ms | ease-out | hover, press, color/opacity changes |
| `motion-base` | 180ms | ease-out (enter) / ease-in (exit) | expand/collapse, list entrance, tab switch |
| `motion-slow` | 280ms | ease-out | modal/drawer/page transitions |

Rules: exit ≈ 70% of enter; animate `transform`/`opacity` only (never width/height/top);
modals scale+fade from center (or slide from edge for drawers); one or two animated
elements per view; stagger list entrance 30–40ms; everything off under reduced-motion.

---

## 2.7 Iconography

**Adopt `lucide-react`** (tree-shakeable, stroke-based, themes via `currentColor`, matches
the existing 1.5px hand-drawn SVG weight). Retire the 77 emoji used as structural icons
and the scattered inline SVGs.

| Token | Size | Stroke | Use |
|-------|------|--------|-----|
| `icon-sm` | 14 | 1.5 | inline with 10–12px text, dense toolbars |
| `icon-md` | 16 | 1.5 | default — buttons, nav, list rows |
| `icon-lg` | 20 | 1.75 | page headers, empty-state glyphs |

Mapping examples: file categories 🤖→`Bot` ⚡→`Zap` ⌘→`Command` 📄→`FileText`
💻→`Terminal` 🖼→`Image`; chrome ✕→`X` ＋→`Plus` ▾→`ChevronDown` →→`ArrowRight`.
**Keep emoji** only where it is genuine user content — the per-space avatar glyph the
user picks. Use one icon set everywhere; never mix filled and outline at the same level.

**Brand glyphs are separate from the lucide set.** The Cronos **mark** (logo) and the
**runtime-state marks** (idle/active/passed/blocked/failed in `brand/states/`) are identity
assets, not UI icons — use them for the logo, the favicon, and the live-run indicator (the
animated `active` mark replaces the bespoke pulse-dot / RunOverlay glow), not as generic
button icons. See [06-brand.md §6.3](06-brand.md).

---

## 2.8 Primitive catalog

What `components/ui/` should contain. ✅ exists · ⬆ exists but expand · 🆕 new.
Full prop specs in [05-roadmap.md](05-roadmap.md).

| Primitive | Status | Note |
|-----------|:--:|------|
| `Button` | ⬆ | add `tertiary`/`link` variants, `focus-visible` ring, loading state, leading-icon slot |
| `IconButton` | ⬆ | add `focus-visible` ring, guarantee 44px hit area |
| `Modal` | ⬆ | enforce; standard scrim (`bg-black/60` + blur), Escape, focus-trap, scale-fade |
| `FormInput` / `FormField` | ✅ | already shared and good — extend with helper text + inline validation |
| `EmptyState` | ✅ | keep; add optional primary action |
| `SpaceTag` | ✅ | keep |
| `StickyToolbar` | ✅ | keep; becomes the action row inside `PageHeader` |
| `Badge` | 🆕 | tone-driven, the one recipe from §2.1 |
| `PageHeader` | 🆕 | breadcrumb + title + subtitle + actions slot |
| `PageContainer` | 🆕 | one of two max-widths: `content` (1280) / `reading` (768) |
| `Skeleton` | 🆕 | line/block/card variants; replaces spinner+text loaders |
| `Toast` / `ToastProvider` | 🆕 | `aria-live`, auto-dismiss 3–5s, undo slot |
| `Dropdown` / `Menu` | 🆕 | consolidates ViewPicker / SpaceFilter / etc. |
| `Tooltip` | 🆕 | keyboard-reachable; for icon-only affordances |
| `Tabs` | 🆕 | consolidates Detail tabs / SpaceTools tabs / Stats sections |
| `SegmentedControl` | 🆕 | density toggle, timeframe selector |
| `StatTile` | 🆕 | Dashboard/Stats metric tile (label + number + delta) |
| `ProgressBar` | 🆕 | goal children, test pass/fail, token usage |
| `Tree` / `TreeRow` | ⬆ | exists (`TreeNode`) but indents full cards with no guides — add hairline connector guides, compact goal/subgoal/leaf rows, Tree⇄DAG toggle (see §04b in [04](04-wireframes.md)) |
| `DetailShell` | 🆕 | shared header + brief + waiting bar + swappable footer + `RelationshipList`; unifies task `Detail` and `FeatureDetail` (see §05 in [04](04-wireframes.md)) — kills `FeatureDetail`'s duplicate header/skeleton/badge map |
| `Logo` | 🆕 | renders the brand mark at a given size — auto-picks glass `mark` (≥64) / `mark-flat` (24–64) / `favicon` (<24); `variant?: lockup` for navbars |
| `RunMark` | 🆕 | the runtime-state mark for a given state (idle/active/passed/blocked/failed); animated `active` variant; the one live-run indicator |

---

## 2.9 Brand & identity

The logo set, runtime-state marks, and brand colour tokens are specified in their own
document — **[06-brand.md](06-brand.md)** — because they cut across colour (§2.1), icons
(§2.7), and the primitive catalog (above). The one-line summary:

- **Identity = deep violet `#7A4FB0`.** Used for the mark, wordmark, and the `idle` state —
  surfaced as the `--brand` token. It is **not** the chrome accent (that stays per-theme).
- **Lime is reserved for `running`.** Never a decorative accent. `done/passed` is cyan.
  This is why §2.1's status values are sourced from the brand state palette.
- **Runtime-state marks** map 1:1 onto the task state machine and replace the bespoke
  pulse/RunOverlay green with one shared (optionally animated) asset.
- Assets live in [`brand/`](brand/); integration is Phase 0 of [05-roadmap.md](05-roadmap.md).
