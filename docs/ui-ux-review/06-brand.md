# 6 · Brand & Identity

The brand asset set lives in [`brand/`](brand/) (logos, runtime-state marks, design
tokens, rasterized PNGs, and an open-in-browser [`preview.html`](brand/preview.html)).
This document records **how that brand layers onto the design system in [02](02-design-system.md)**
— what to use where, and the one rule that touches every other doc.

> **Integration decision (this review): _brand identity layer_.** The chrome **accent
> stays per-theme** (green in light/dark, cyan in neon) exactly as [02](02-design-system.md)
> proposes. The brand contributes three things on top: the **logos**, the **runtime-state
> marks**, and the **state colour palette** (the values the status tokens resolve to). Deep
> violet is an **identity** colour (mark, wordmark, idle state) — it is *not* promoted to the
> chrome accent. See [§6.5](#65-the-residual-tension) for the consequence and the escape hatch.

---

## 6.1 The one rule: lime is reserved

**Lime-green means `running`. Nothing else may be lime.**

A stray lime accent anywhere in the product reads as "an agent is working." Decorative
lime creates false system-activity signals — the single worst thing an operator console
can do. This is why the brand is violet, not lime: lime was deliberately demoted out of
the identity slot and into the reserved `running` state. (Brand decision #1.)

Practical consequences for the codebase:
- The `running` status token resolves to lime (`#B8FF5C` on dark surfaces).
- Live indicators — pulse dot, RunOverlay glow, NOW-card, board "active" strip, harness
  running node — all draw from `running`/the `active` mark, never a one-off green.
- Do **not** introduce a lime hover, lime link, or lime "success" decoration. Done/passed
  is **cyan** (see below), specifically so it can't be confused with running.

---

## 6.2 Logo set

| Asset | File | Use | Min size |
|---|---|---|---|
| Horizontal lockup | `logo/cronos-lockup-h.svg` | navbar / page header (dark surfaces) | — |
| Vertical lockup | `logo/cronos-lockup-v.svg` | login / splash / square aspect | — |
| Glass mark | `logo/cronos-mark.svg` | hero, marketing, **app-icon source** | 64px |
| Flat mark | `logo/cronos-mark-flat.svg` | **sidebar, tiles, toolbars** | 24px |
| Mono mark | `logo/cronos-mark-mono.svg` | icon-in-button — inherits `currentColor` | any |
| App icon | `logo/cronos-app-icon.svg` | OS / PWA tile, social share | — |
| Favicon | `logo/cronos-favicon.svg` | browser tab (1 ring + dot) | 16px |

PNG rasters at standard sizes are in `brand/png/` (favicons, apple-touch-icon,
app-icon-512, OG fallbacks) — wire these into `index.html` and the PWA manifest.

**Hard rules** (from `brand/README.md`):
- Never render the full **glass mark below 48px** — switch to `mark-flat`, then `favicon`.
- Never recolour the glass mark to other brand variants (its gradients are tuned for
  violet) — use `mark-flat` or `mono` if you need a recolour.
- The wordmark typeface is a **placeholder** (`Inter`/system fallback). Pick and lock one
  before production — candidates: Inter, Geist, IBM Plex Sans, JetBrains Mono — then either
  bundle the font with the lockup or outline the wordmark to paths. (For the app shell, the
  cheapest robust path is **flat mark SVG + a live `JetBrains Mono` "CRONOS" text node**,
  which is what the wireframe sidebar does — it themes correctly on light/dark/neon, whereas
  the lockup's near-white wordmark is dark-surface-only.)

**Three anchors, never more.** The mark's three nodes define a plane / harness. Don't add
a fourth (reads as ornament) or drop to two (reads as binary).

---

## 6.3 Runtime-state marks → the task state machine

The brand ships six recolours of the flat mark, one visual language across the whole
lifecycle. They map directly onto Cronos' state machine and run outcomes:

| Mark (`brand/states/`) | Colour | State-machine / run meaning | Status token |
|---|---|---|---|
| `cronos-state-idle.svg` | violet `#7A4FB0` | `backlog` · default / idle | `--brand` (identity) |
| `cronos-state-active.svg` / `-active-animated.svg` | lime `#B8FF5C` | `active` · run in flight | `--running` |
| `cronos-state-passed.svg` | cyan `#2EC4FF` | `done` · gate passed / goal complete | `--success` |
| `cronos-state-blocked.svg` | amber `#FFA62E` | `waiting` · gate failed / awaiting decision | `--warning` |
| `cronos-state-failed.svg` | red `#FF6E5C` | run error · executor crash | `--danger` |

- The **animated** active mark (self-contained SMIL: rotating orbit + pulsing core, no JS,
  respects nothing extra — pair it with the existing `prefers-reduced-motion` guard at the
  call site) is the canonical "agent live" glyph. It can replace the bespoke pulse-dot and
  the hardcoded `#22c55e` RunOverlay glow with a single shared asset.
- **PASSED is cyan, not emerald** (brand decision #2): emerald is too close to active-lime
  for deuteranopia/protanopia. Cyan is distinct from both violet identity and lime active.
- Wireframe usage in context: §07 harness running node and §05b NOW card use the animated
  active mark; §00 shows the full set.

> **Note on `info`.** The brand palette has no "informational/linked" colour; the design
> system keeps `--info` (sky) for the `linked` relationship and neutral info. It is the one
> status token *not* sourced from the brand.

---

## 6.4 Colour tokens — how brand values reach the themes

The brand state palette is tuned for **dark surfaces** (`#0E1822`). The design system's
status tokens therefore resolve to the brand hues on **dark and neon**, and to
**contrast-safe darker shades of the same hue** on **light** (where a badge uses the tone
colour as *text* on a tinted fill, so it must clear 4.5:1). This is the standard way to
bridge a dark-tuned brand palette into a light theme.

| Status token | Light (contrast-safe) | Dark / Neon (brand value) | Source |
|---|---|---|---|
| `--running` | lime-700 `77 124 15` | lime `184 255 92` | brand `active` |
| `--success` | cyan-600 `8 145 178` | cyan `46 196 255` | brand `passed` |
| `--warning` | amber-700 `180 83 9` | amber `255 166 46` | brand `blocked` |
| `--danger` | red-700 `185 28 28` | red `255 110 92` | brand `failed` |
| `--info` | sky-700 `3 105 161` | sky `56 189 248` / `90 230 255` | (design system) |
| `--neutral` | ink-faint | ink-faint | (design system) |
| `--brand` | violet `122 79 176` | violet `122 79 176` | brand identity / idle |

`--brand` is theme-independent (identity is constant). All values are space-separated RGB
triplets so Tailwind `<alpha-value>` opacity modifiers keep working, per the existing
codebase convention. The full `brand/tokens/tokens.css` + `tokens.json` are the canonical
hex source; map them into `index.css`'s `:root` / `.dark` / `.neon` during Phase 0.

---

## 6.5 The residual tension

Because the chrome **accent stays green** on light/dark while **lime now means `running`**,
those two greens sit adjacent on the green themes. It's acceptable here — they never label
the same thing (accent = chrome / primary action; lime = live agent) and the brand reserves
lime tightly — but if it ever reads ambiguous in practice, the escape hatch is the
**brand-canonical** option: promote violet `#7A4FB0` to the chrome accent and free green
entirely for `running`. That is a one-file change (the accent token per theme) given the
token discipline this review already enforces. Neon has no tension (accent = cyan).

---

## 6.6 Roadmap hook

Brand integration slots into **Phase 0 — Tokens & docs** of [05-roadmap.md](05-roadmap.md):

1. Map `brand/tokens/tokens.css` values into `index.css` status tokens per [§6.4](#64-colour-tokens--how-brand-values-reach-the-themes); add `--brand` / `--brand-deep` / `--brand-light`.
2. Wire favicons + apple-touch-icon + PWA manifest from `brand/png/` and `brand/logo/cronos-favicon.svg`.
3. Replace the app-shell wordmark with `mark-flat` SVG + live `JetBrains Mono` text node.
4. In Phase 1/3, route every live indicator (pulse, RunOverlay `#22c55e`, NOW card, run
   node) through `--running` / the `active` mark — deleting the one-off green.
5. Lock the wordmark typeface (decision owner: maintainer) before any marketing surface.

See [`brand/README.md`](brand/README.md) for the full asset map, regeneration commands,
and the complete design-decision record.
</content>
</invoke>
