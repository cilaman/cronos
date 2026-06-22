# 1 · Executive Summary

## Verdict

Cronos is **80% of the way to a distinctive, professional UI** and stalls on the last
20% — the part that makes a product feel like one coherent thing. The foundation is
above average for an internal tool: a CSS-variable theme system with three
hand-tuned themes (light "editorial paper", dark "operator console", neon "midnight
navy"), semantic color tokens wired into Tailwind, bespoke shadow/grain/grid
atmosphere, and an actual `components/ui/` primitives folder.

What's missing is **enforcement and a few absent scales**. Primitives exist but are
routinely bypassed; the one place the token system has a hole — categorical/status
colors — is filled with raw Tailwind palette classes copy-pasted across many files,
which also silently break in the neon theme.

A **brand asset set** now exists ([`brand/`](brand/) → folded into [06-brand.md](06-brand.md)):
logos, runtime-state marks, and design tokens. It is integrated as an **identity layer** —
deep violet `#7A4FB0` for the logo/idle, **lime reserved for `running`**, cyan for `passed`
— which fills exactly that status-colour hole (the status tokens below now resolve to the
brand state palette) while leaving the per-theme chrome accent unchanged.

## Scorecard

| Dimension | Grade | One-line |
|-----------|:----:|----------|
| Theme & color tokens (chrome) | **A−** | Semantic tokens used cleanly for surfaces/text/borders across the shell and most pages |
| Status & categorical color (badges) | **D** | Raw `red/amber/emerald/violet/sky/…` palette duplicated in 5+ files; not theme-aware |
| Typography system | **C** | Good font pairing (Geist + JetBrains Mono) but no enforced type scale; page titles range 13→22px |
| Spacing & layout | **C+** | 4/8 rhythm mostly followed; container max-widths scattered (768 / 1024 / 1280 / 5xl) |
| Component primitives | **C** | Real primitives exist; ~160/171 buttons and 4/5 modals bypass them |
| Iconography | **D** | No icon library; 77 emoji used as structural icons; hand-rolled SVGs inconsistent |
| Focus / keyboard a11y | **C−** | Inputs have focus rings; buttons & nav mostly don't (33/138 use `focus-visible`) |
| Touch targets | **C−** | Several icon buttons, lane controls, modal close < 44px |
| Loading / empty / error states | **C+** | Empty states consistent; loading mixes spinner + bare text, no skeletons; error copy generic |
| Motion | **B−** | Tasteful, reduced-motion respected — but no duration/easing scale |
| Navigation shell | **B+** | Clean responsive sidebar+drawer; minor focus/mobile-context gaps |

## Top 10 findings (by impact)

1. **Badge/status color is not in the token system.** Priority, task-state, type, and
   mode badges hardcode Tailwind palette colors (`text-red-600 dark:text-red-400`,
   `text-emerald-700`, …) in `Card.tsx`, `Detail.tsx`, `TaskForm.tsx`, `FeatureForm.tsx`,
   `ConversationEntry.tsx`, `HarnessRunsPage.tsx`. 63 such classes. They don't adapt to
   the neon theme and the same meaning (P1 = red) is defined 4+ times. → **single source
   of truth: theme-aware status & categorical tokens + one `<Badge>` recipe.**

2. **Page headers drift.** Titles span `text-[13px]` (Features/Archived) → `text-sm`
   (HarnessEditor) → `text-lg` (Harness lists) → `text-[22px]` (Dashboard/Stats/…).
   Breadcrumbs are ad-hoc; container max-width is one of four values. → **one
   `<PageHeader>` + `<PageContainer>`.**

3. **Primitives are bypassed.** `Button`/`IconButton` exist but ~160 of 171 `<button>`s
   are styled inline; `Modal.tsx` exists but `MarkdownEditorModal`, the file viewer, and
   the view-delete dialog each re-implement a backdrop. → **expand + enforce.**

4. **No icon system.** Zero icon-library imports; 77 emoji (🤖 ⚡ ⌘ 📄 ✕ ＋ ▾) as
   structural icons, plus scattered inline SVG. → **adopt one stroke-based set
   (lucide-react); keep emoji only as user-chosen space avatars.**

5. **Modal scrim & behavior drift.** Backdrops range `bg-black/50 → /60 → /70 → /80 →
   bg-canvas/60`; close is sometimes `✕` emoji, sometimes SVG; Escape/focus-trap
   handled inconsistently. → **one modal contract.**

6. **Focus rings are not universal.** Form inputs have them; buttons, nav links, and
   card-as-button elements largely don't. Keyboard users lose their place. → **bake
   `focus-visible` ring into the primitives.**

7. **Touch targets below 44px.** Lane `＋`/`×`, modal close, several icon buttons are
   ~32px or smaller. → **44px minimum hit area (expand, don't enlarge the glyph).**

8. **Loading states are inconsistent and jumpy.** Some pages show a spinner, some show
   "Loading…" text, none (except Detail) use skeletons → layout shift on data arrival.
   → **a `Skeleton` primitive + reserved space.**

9. **No z-index / motion scale.** z-values 10/20/30/40/50 used interchangeably for the
   same layer; durations 100/180/200/500ms ad-hoc. → **define both scales as tokens.**

10. **Error & empty copy is system-voiced, not user-voiced.** "Error: {message}",
    generic field errors with no recovery path. → **rewrite to say what happened and
    what to do next.**

## What is already good (keep, don't touch)

- The three-theme CSS-variable architecture and the semantic surface/ink/hairline tokens.
- Custom shadow system (`shadow-inset-hairline`, `shadow-lift`, `accent-glow`) — 95% adoption.
- The operator-console aesthetic: mono eyebrows, hairline grid, grain, pulse-dot live state.
- `reduced-motion` handling already in `index.css`.
- Empty-state visual pattern (dashed hairline border, centered) — already consistent.

## Prioritized roadmap

Effort: **S** ≈ <1 day · **M** ≈ 1–3 days · **L** ≈ 3–5 days. Impact is product-wide unless noted.

### P0 — Foundation (do first; everything else depends on these)
| Item | Effort | Why first |
|------|:--:|-----------|
| Status + categorical color tokens (per theme) + `<Badge tone=…>` | M | Unblocks badge migration; fixes neon-theme breakage; kills 5-file duplication |
| `<PageHeader>` + `<PageContainer>` (title scale, breadcrumb, actions, max-width) | S | Instantly unifies every page's first impression |
| Define & document scales: type, spacing, radius, z-index, motion | S | The reference every later PR cites |
| Add `focus-visible` ring to `Button`/`IconButton`; expand variants | S | A11y + removes the reason people write inline buttons |

### P1 — Consolidation
| Item | Effort | |
|------|:--:|--|
| Adopt lucide-react; replace emoji/inline-SVG icons; icon-size tokens | M | Single crisp icon language |
| Migrate badges → `<Badge>`; delete duplicated style objects | M | Depends on P0 tokens |
| Migrate ad-hoc buttons → `Button`/`IconButton` | M | Depends on expanded variants |
| Enforce `Modal` contract; migrate the 4 ad-hoc modals | S | Scrim/escape/focus consistency |
| `Skeleton` primitive; replace spinner/text loaders | S | Kills layout shift |

### P2 — Polish
| Item | Effort | |
|------|:--:|--|
| Touch-target sweep (44px) | S | Mobile usability |
| `Toast`/alert provider with `aria-live`; rewrite error/empty copy | M | Voice + a11y |
| Stats/Dashboard data-viz pass (legends, tooltips, empty/loading) | M | Charts clarity |
| Mobile refinements (space context in header, drawer Escape, target sizes) | S | |
| Optional: ESLint guardrail banning raw palette classes + raw hex in `.tsx` | S | Prevents regression |

See [05-roadmap.md](05-roadmap.md) for the detailed plan and component specs, and
[04-wireframes.md](04-wireframes.md) for what each unified pattern looks like.
