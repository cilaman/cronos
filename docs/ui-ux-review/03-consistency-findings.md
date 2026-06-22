# 3 · Consistency Findings (the evidence)

Grounded in a full read of `frontend/src`. Severity: 🔴 high (breaks consistency or a11y
product-wide) · 🟠 medium (visible drift) · 🟡 low (polish). File:line references are
representative, not exhaustive.

---

## 3.1 Color & status — 🔴

**63 raw Tailwind-palette classes bypass the token system**, concentrated in badge logic:

| File | Examples |
|------|----------|
| `Card.tsx` | `text-red-600 dark:text-red-400`, `text-orange-600`, `text-teal-600`, `text-indigo-600`, `text-violet-600`, `text-emerald-700`, `text-rose-700`, `text-sky-700` (priority/state/type/mode — 10+ objects) |
| `Detail.tsx:280–352` | duplicate `PRIORITY_BADGE_STYLES`, `TYPE_BADGE_STYLES` |
| `TaskForm.tsx:9–15` | duplicate `PRIORITY_OPTIONS` with hardcoded classes |
| `FeatureForm.tsx`, `FeatureDetail.tsx` | more duplicates (`border-red-200 bg-red-50`, `border-emerald-300 bg-emerald-100`) |
| `ConversationEntry.tsx:35–49` | `MODEL_COLOR`, `AGENT_TYPE_COLOR` hardmaps |
| `HarnessRunsPage.tsx:14` | `border-amber-400/40 bg-amber-400/10 text-amber-600 dark:text-amber-400` for "running" |
| `AdoptedToolTelemetry.tsx` | `text-green-600/400`, `bg-green-500`, `bg-amber-500`, `text-amber-600` |
| `RunOverlay.tsx:119` | raw hex `#22c55e` for "done" |

**Consequences:** (1) the same meaning (P1 = red) is defined in 4+ places and drifts —
some badges use `-50/-600/-200`, others `-100/-800/-300`; (2) **none of these adapt to the
neon theme** (cyan accent, but badges stay emerald/red); (3) dark mode is hand-alpha-blended
per definition. → Fix with §2.1 tokens + `<Badge>`.

Raw hex in `.tsx`: 27 total, almost all legitimate (theme preview swatches in
`ThemePicker.tsx:6–8` / `useTheme.ts:8–10`; user-chosen space colors injected as inline
`style={{ backgroundColor: space.color }}` — correct for dynamic values). The only true
offender is `RunOverlay.tsx:119`.

---

## 3.2 Page headers & containers — 🔴

Titles have no shared scale:

| Page(s) | Title | Container |
|---------|-------|-----------|
| Dashboard, Stats, HarnessRuns, TestReports, Tools, Memory, SpaceCreate | `text-[22px]` | 1024 / 1280 |
| Harness list / global | `text-lg` (18) | `max-w-3xl` |
| HarnessEditor | `text-sm` (14) | full screen |
| Features, Archived | `text-[13px]` (inside StickyToolbar) | full width |
| SpaceSettings | `text-[22px]` | `max-w-5xl` |

Breadcrumbs are inconsistent (nested `<Link>` in SpaceSettings vs `<p>` eyebrow in
Dashboard vs none). Container max-width is one of **four** values with no rule. →
`<PageHeader>` + `<PageContainer>` (§2.8, wireframe §02 in [04](04-wireframes.md)).

---

## 3.3 Buttons — 🔴

`Button.tsx` (variants: primary/secondary/ghost/danger) and `IconButton.tsx` (5 variants)
exist and are well-built — but **~160 of 171 `<button>` elements are styled inline**, e.g.:

```
Lane.tsx:75            rounded p-1 text-ink-muted transition hover:bg-surface-2 …
SpaceFilterDropdown:49 flex h-8 items-center gap-2 rounded border border-hairline-strong …
MarkdownEditorModal:126 rounded border border-hairline px-3 py-1 text-xs …
TimeFrameSelector:70   rounded transition px-2 py-0.5 font-display text-[9px] uppercase …
ViewPicker:114         flex w-full items-center gap-2 px-3 py-2 text-left text-[12px] …
```

These cluster into recognizable archetypes the primitive doesn't yet cover: **toolbar
chip**, **dropdown trigger**, **segmented item**, **list-row button**. → expand `Button`
variants to cover them, add `focus-visible` ring, then migrate.

---

## 3.4 Modals — 🟠

`Modal.tsx` exists but is bypassed. **10 `fixed inset-0` sites; scrim opacity varies:**
`bg-black/50` (×5), `bg-black/80` (×2, MarkdownEditorModal & FileViewer), `bg-black/70`
(Modal.tsx itself), `bg-black/60` (ViewEditor delete), `bg-canvas/60` (ToolDetailPanel).
Close affordance: `✕` emoji in some, inline SVG in others. Escape handling present in
some dropdowns, absent in others. Z-index mixes 40 and 50 for the same role. → one Modal
contract (§2.8): `bg-black/60` + `backdrop-blur`, z-scrim/z-modal, Escape, focus-trap,
scale-fade entrance, one close button.

---

## 3.5 Iconography — 🔴

No icon library (`lucide-react` not a dependency). **77 emoji** used as structural icons:
file categories in `FileBrowser.tsx` (🤖 ⚡ ⌘ 📖 🖼 📄 💻 📑 🗜 ⬛), chrome glyphs
(＋ ✕ ▾ →) across Lane / SpaceFilter / ViewPicker / MarkdownEditorModal / TimeFrameSelector.
Plus hand-rolled inline SVGs (ThemeToggle, nav actions) with no shared sizing. Emoji
render differently per OS/font and can't be themed. → adopt lucide; emoji only for
user-chosen space avatars (§2.7).

---

## 3.6 Focus & keyboard a11y — 🔴

`focus-visible` used in only **33 of 138** focus-related sites. `FormInput` has a proper
ring (`focus:border-accent focus:ring-1 focus:ring-accent`); `Button.tsx` and
`IconButton.tsx` have **none**; primary nav links and space rows have none; cards use
`role="button"` divs with a ring but child rows don't. → bake one ring recipe into the
primitives (`focus-visible:ring-1 focus-visible:ring-accent focus:outline-none`) and add
to nav. Also: add a skip-to-content link; prefer real `<button>` over `role="button"`.

---

## 3.7 Touch targets — 🟠

Below the 44px minimum: lane header `＋`/`×` (`p-1` ≈ 24–28px), Detail modal close
(`p-1`), `IconButton` `sm` (28px) and `md` (32px) without extra hit area. Tight cards do
set `min-h-[44px]` ✅. → expand hit areas (padding / `hitSlop`-style negative margin),
keep glyph size.

---

## 3.8 Loading / empty / error — 🟠

- **Empty:** consistent and good — dashed hairline border, centered, `EmptyState` used
  widely. Keep.
- **Loading:** inconsistent — `FeaturesPage:91` spinner, `Dashboard:698` plain "Loading
  statistics…" text, `HarnessList:217` spinner+text. Only `Detail.tsx` uses a skeleton
  (`DetailSkeleton`). Plain-text/spinner loaders cause layout shift when data lands. →
  `Skeleton` primitive everywhere; reserve space.
- **Error:** present but generic and system-voiced — `Board.tsx:209` "Error: {message}",
  field errors are bare red text with no recovery path; some pages (Stats) show nothing on
  error. → consistent inline error + retry; rewrite copy (§ below).

---

## 3.9 Z-index & motion scales — 🟡

z: 10/20/30/40/50 used for inconsistent layers (modals at both 40 and 50). Motion: mostly
bare `transition` (~286 sites) with three ad-hoc explicit durations (100/200/500ms) and
custom keyframes at 180ms/1.8s/2s. Shadows, by contrast, are **95% semantic** (good
model to copy). → adopt the z and motion scales in §2.5–2.6.

---

## 3.10 Copy / voice — 🟡

System-voiced strings leak through: "Error: {message}", "Loading dashboard…", generic
"Invalid input". The conversation empty-state `// no exchanges yet — send the first
message below` is a nice example of the *right* terminal voice — extend that intentionality
everywhere. → errors state cause + fix; empty states invite an action; actions keep the
same verb through their flow (button "Publish" → toast "Published").

---

## 3.10b Goal tree readability — 🟠

`TreeNode.tsx` renders the goal→subgoal→task hierarchy by indenting the **full board
`Card`** by `depth × 1.25rem` (`--tree-indent`). Keyboard nav (`tree`/`treeitem`, arrow
keys) and drag-to-reparent are already implemented (good), but there are **no visual
connector guides** between parent and child, so at depth ≥ 2 the hierarchy is hard to
follow, and full cards make deep trees very tall. Separately, `GoalDependencyGraph`
(dagre DAG) is a distinct surface with no shared toggle. → compact goal/subgoal/leaf
rows with hairline connector guides + a Tree ⇄ Dependency-DAG view toggle
(wireframe §04b in [04](04-wireframes.md) / HTML gallery).

## 3.10c Task vs feature detail duplication — 🟠

`FeatureDetail.tsx` and the task `Detail.tsx` are structurally the same modal shell —
status+type badge header, key/id, title, markdown Brief, amber waiting bar, edit mode,
skeleton — but `FeatureDetail` re-implements all of it independently, including its own
`FeatureDetailSkeleton` and a `FEATURE_STATE_BADGE` map (violet/indigo/amber/sky) plus a
type map (rose/emerald). The only genuine difference is the footer: tasks run an agent
(tabs + conversation + chat); features decompose (Decompose action + Realizing-goals
list). → one `DetailShell` with a swappable footer + generic `RelationshipList`
(wireframe §05 in [04](04-wireframes.md) / HTML gallery, live toggle). Removes a
whole parallel header/skeleton/badge implementation.

## 3.10d Detail = one tall scroll column — 🟠 (UX)

In the task `Detail`, brief + metadata + relationships + conversation share a single
vertical scroll, so reading context and following the live transcript means scrolling up
and down repeatedly. Two gaps: (a) no independent scroll for context vs conversation; (b)
the current agent activity is only visible by scrolling to the bottom of the stream. →
two-pane workspace (Context | Conversation, independent scroll) + a pinned **NOW running**
card (current tool/target, model, subagent, elapsed, tokens, steps strip). Wireframe
§05b in [04](04-wireframes.md) / HTML gallery. Raised by the maintainer.

## 3.11 Per-surface polish ranking

Most polished → least, from the audits:

1. **Dashboard / Stats / TestReports** — comprehensive, consistent internal layout, clean tokens.
2. **Shell (Sidebar/App)** — clean, responsive; minor focus/mobile gaps.
3. **Board / Detail** — functionally rich; held back by badge color sprawl, radius drift, touch targets.
4. **HarnessEditor** — purpose-built and tidy; just the undersized title.
5. **Harness list / Memory / Settings forms** — fine but title/container drift makes them feel secondary.
6. **Features / Archived** — title buried in a 13px toolbar; reads as a sub-section, not a page.

Note: charts are **hand-coded CSS** (progress bars, colored divs) — no chart library. Fine
for the current simple viz, but they lack legends/tooltips/empty-loading consistency
(§2 charts rules in `ui-ux-pro-max`). Decide per-case whether to formalize as a `ProgressBar`
primitive vs adopt a small chart lib if richer viz is wanted.
