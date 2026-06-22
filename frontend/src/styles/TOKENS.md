# Cronos Design Token Reference

This document describes every CSS custom property (token) and Tailwind utility shipped
in the `gui-tokens-brand` pipeline phase (I1 + I2). Values are drawn verbatim from
`frontend/src/index.css` (token definitions) and `frontend/tailwind.config.js`
(utility exposures). Three themes are documented: **light** (`:root`), **dark**
(`.dark`), and **neon** (`.neon`). Theme classes are applied to `<html>` at runtime.

---

## 1. How tokens work

CSS custom properties are stored as **space-separated RGB triplets** (no `rgb()` wrapper):

```css
--color-canvas: 250 250 247;
```

Tailwind utilities wrap them with the `<alpha-value>` placeholder so opacity modifiers
work transparently:

```js
canvas: "rgb(var(--color-canvas) / <alpha-value>)"
```

This means `bg-canvas` = full opacity, `bg-canvas/40` = 40% opacity — no extra CSS needed.

---

## 2. Surface tokens

Surfaces form the layered background stack: canvas → surface-1 → surface-2 → surface-3.

| CSS variable        | Tailwind utility    | Light `:root`   | Dark `.dark`    | Neon `.neon`    |
|---------------------|---------------------|-----------------|-----------------|-----------------|
| `--color-canvas`    | `bg-canvas`         | `250 250 247`   | `7 16 12`       | `3 7 30`        |
| `--color-surface-1` | `bg-surface-1`      | `255 255 255`   | `17 24 27`      | `8 14 52`       |
| `--color-surface-2` | `bg-surface-2`      | `241 241 236`   | `26 35 38`      | `12 22 68`      |
| `--color-surface-3` | `bg-surface-3`      | `230 230 223`   | `36 48 48`      | `18 30 88`      |

---

## 3. Ink (text) tokens

| CSS variable          | Tailwind utility    | Light `:root`   | Dark `.dark`    | Neon `.neon`    |
|-----------------------|---------------------|-----------------|-----------------|-----------------|
| `--color-ink`         | `text-ink`          | `13 19 15`      | `232 240 227`   | `214 236 255`   |
| `--color-ink-muted`   | `text-ink-muted`    | `70 80 74`      | `168 184 173`   | `126 166 218`   |
| `--color-ink-faint`   | `text-ink-faint`    | `107 117 109`   | `126 142 131`   | `66 102 168`    |

---

## 4. Accent tokens

The accent family drives interactive states: buttons, links, focus rings, selection highlights.

| CSS variable              | Tailwind utility      | Light `:root`   | Dark `.dark`    | Neon `.neon`    |
|---------------------------|-----------------------|-----------------|-----------------|-----------------|
| `--color-accent`          | `bg-accent`           | `21 128 61`     | `74 222 128`    | `0 210 255`     |
| `--color-accent-bright`   | `bg-accent-bright`    | `15 106 49`     | `134 239 172`   | `90 230 255`    |
| `--color-accent-dim`      | `bg-accent-dim`       | `10 77 34`      | `42 110 62`     | `0 132 200`     |
| `--color-accent-deep`     | `bg-accent-deep`      | `33 87 50`      | `33 87 50`      | `108 68 220`    |

---

## 5. Border (hairline) tokens

| CSS variable               | Tailwind utility       | Light `:root`   | Dark `.dark`    | Neon `.neon`    |
|----------------------------|------------------------|-----------------|-----------------|-----------------|
| `--color-hairline`         | `border-hairline`      | `220 220 213`   | `31 42 38`      | `22 28 78`      |
| `--color-hairline-strong`  | `border-hairline-strong` | `188 188 180` | `50 64 56`      | `38 46 118`     |

---

## 6. Status colour tokens (R1)

Status tokens convey operational state across badges, lane headers, and timeline entries.
They are defined in **all three** theme blocks so they always read legibly against that
theme's canvas.

> **Rule: lime is reserved for `running`.**  
> The neon-theme value `150 255 100` (bright lime-green) is intentionally the most
> visually distinct colour in the palette. Do not assign any other semantic role a
> lime-range hue; `running` must remain the lone "lime" anchor so agents and users can
> spot active tasks at a glance across all themes.

> **Note on neon `--color-info`:**  
> The neon theme assigns `120 210 255` (sky-leaning blue) rather than `90 230 255`.
> This avoids a collision with `--color-accent-bright` which holds `90 230 255` in the
> neon theme. The two values are intentionally distinct so info-state indicators do not
> appear identical to accent-bright glow elements.

| CSS variable       | Tailwind utility | Light `:root`   | Dark `.dark`    | Neon `.neon`    |
|--------------------|------------------|-----------------|-----------------|-----------------|
| `--color-running`  | `text-running`   | `30 160 30`     | `130 220 100`   | `150 255 100`   |
| `--color-success`  | `text-success`   | `20 140 100`    | `80 200 180`    | `80 255 200`    |
| `--color-info`     | `text-info`      | `0 120 200`     | `90 180 240`    | `120 210 255`   |
| `--color-warning`  | `text-warning`   | `180 120 0`     | `255 166 46`    | `255 200 50`    |
| `--color-danger`   | `text-danger`    | `190 50 50`     | `255 110 92`    | `255 100 80`    |
| `--color-neutral`  | `text-neutral`   | `100 110 120`   | `140 150 165`   | `160 170 185`   |

All six also work as background utilities: `bg-running`, `bg-success`, etc.  
The pre-existing `warning` and `danger` Tailwind aliases remain (they are identical to
`text-warning` / `text-danger` — backed by the same CSS variables).

---

## 7. Categorical tokens (R2)

Categorical tokens colour task-type distinctions: goal, feature, fix, issue, plan, ask.
They are adapted per-theme so they remain readable against that theme's surfaces.

| CSS variable    | Tailwind utility    | Light `:root`   | Dark `.dark`    | Neon `.neon`    |
|-----------------|---------------------|-----------------|-----------------|-----------------|
| `--cat-goal`    | `text-cat-goal`     | `122 79 176`    | `180 140 220`   | `200 160 255`   |
| `--cat-feature` | `text-cat-feature`  | `0 120 200`     | `90 180 240`    | `120 210 255`   |
| `--cat-fix`     | `text-cat-fix`      | `190 50 50`     | `255 110 92`    | `255 120 100`   |
| `--cat-issue`   | `text-cat-issue`    | `180 120 0`     | `255 166 46`    | `255 210 60`    |
| `--cat-plan`    | `text-cat-plan`     | `20 140 100`    | `80 200 180`    | `80 255 200`    |
| `--cat-ask`     | `text-cat-ask`      | `100 110 120`   | `140 150 165`   | `160 170 185`   |

All six also work as background utilities: `bg-cat-goal`, `bg-cat-feature`, etc.

---

## 8. Brand identity tokens (R3)

Brand tokens are **theme-invariant**: they are defined in `:root` only and are not
overridden by `.dark` or `.neon`. This means the violet anchor is identical across all
three themes — it is the one truly brand-locked colour in the system.

The violet triplet `122 79 176` is the same as hex `#7A4FB0` and is used directly in
`CronosMark.tsx` for the inner ring, nodes, and core of the sidebar logotype.

| CSS variable    | Tailwind utility | Value (all themes) | Hex equiv.  | Role                                 |
|-----------------|------------------|--------------------|-------------|--------------------------------------|
| `--brand`       | `bg-brand`       | `122 79 176`       | `#7A4FB0`   | Primary violet — logomark, accents   |
| `--brand-deep`  | `bg-brand-deep`  | `90 50 140`        | `#5A328C`   | Pressed / active violet state        |
| `--brand-light` | `bg-brand-light` | `180 140 220`      | `#B48CDC`   | Tinted violet — hover halos, badges  |

---

## 9. Typography scale (R5)

Defined in `tailwind.config.js` under `theme.extend.fontSize`. All steps use `px`
sizes. The `title` step is hardwired to JetBrains Mono; other steps inherit the
document font stack.

| Tailwind class    | Size  | Line height | Weight | Notes                              |
|-------------------|-------|-------------|--------|------------------------------------|
| `text-title`      | 22px  | 1.3         | 700    | JetBrains Mono; page/panel headers |
| `text-eyebrow`    | 11px  | 1.2         | 600    | Letter-spacing 0.08em; labels      |
| `text-cardtitle`  | 14px  | 1.4         | 600    | Card and section headings          |
| `text-body`       | 14px  | 1.5         | 400    | Default body copy                  |
| `text-meta`       | 12px  | 1.4         | 400    | Timestamps, secondary labels       |
| `text-micro`      | 10px  | 1.3         | 400    | Chip labels, count badges          |

---

## 10. Spacing scale (R8)

Defined in `tailwind.config.js` under `theme.extend.spacing`. These supplement
Tailwind's default rem-based scale with pixel-explicit steps.

| Tailwind class | Value  |
|----------------|--------|
| `p-4`          | 4px    |
| `p-8`          | 8px    |
| `p-12`         | 12px   |
| `p-16`         | 16px   |
| `p-24`         | 24px   |
| `p-32`         | 32px   |
| `p-48`         | 48px   |

(Also applies as `m-*`, `gap-*`, `w-*`, `h-*`, etc.)

---

## 11. Border radius scale

Defined in `tailwind.config.js` under `theme.extend.borderRadius`.

| Tailwind class   | Value   |
|------------------|---------|
| `rounded-sm`     | 4px     |
| `rounded-md`     | 6px     |
| `rounded-lg`     | 8px     |
| `rounded-full`   | 9999px  |

---

## 12. Z-index ladder (R6)

Seven named steps replace magic numbers in components.

| Tailwind class      | Value | Use                                  |
|---------------------|-------|--------------------------------------|
| `z-base`            | 0     | Default document flow                |
| `z-raised`          | 10    | Sticky headers, floated cards        |
| `z-dropdown`        | 100   | Dropdowns, auto-complete             |
| `z-scrim`           | 200   | Modal backdrops, overlays            |
| `z-modal`           | 300   | Modal dialogs, drawers               |
| `z-toast`           | 400   | Toast notifications                  |
| `z-tooltip`         | 500   | Tooltips (always topmost)            |

---

## 13. Motion duration tokens (R7)

Defined in `tailwind.config.js` under `theme.extend.transitionDuration`.

| Tailwind class              | Value  | Use                                       |
|-----------------------------|--------|-------------------------------------------|
| `duration-motion-fast`      | 120ms  | Micro-interactions (hover colour shifts)  |
| `duration-motion-base`      | 180ms  | Standard transitions (expand/collapse)    |
| `duration-motion-slow`      | 280ms  | Page-level enters, large panel slides     |

Pair with standard Tailwind easing: `ease-out` for enters, `ease-in` for exits.

---

## 14. Shadow and atmosphere tokens

These tokens are not exposed as named Tailwind utilities (they are consumed via
`boxShadow` and `backgroundImage` aliases). They exist in all three theme blocks.

| CSS variable                | Light `:root`                      | Dark `.dark`                       | Neon `.neon`                       |
|-----------------------------|------------------------------------|------------------------------------|-------------------------------------|
| `--shadow-inset-hairline`   | `rgb(0 0 0 / 0.04)`                | `rgb(255 255 255 / 0.04)`          | `rgb(0 210 255 / 0.16)`            |
| `--shadow-lift-outer`       | `rgb(0 0 0 / 0.12)`                | `rgb(0 0 0 / 0.6)`                 | `rgb(0 4 28 / 0.84)`               |
| `--shadow-lift-inner`       | `rgb(0 0 0 / 0.06)`                | `rgb(0 0 0 / 0.4)`                 | `rgb(0 6 42 / 0.68)`               |
| `--bg-grain`                | `none`                             | fractalNoise SVG (monochrome)      | fractalNoise SVG (blue-purple tint) |
| `--bg-hairline-grid`        | black/0.04 crosshatch              | white/0.03 crosshatch              | cyan/0.07 crosshatch                |

**Named Tailwind shadow aliases** (from `theme.extend.boxShadow`):

| Tailwind class       | Formula                                                                  |
|----------------------|--------------------------------------------------------------------------|
| `shadow-inset-hairline` | `inset 0 1px 0 0 var(--shadow-inset-hairline)`                      |
| `shadow-lift`        | outer 8px lift + inner 4px fill (reads `--shadow-lift-outer/inner`)     |
| `shadow-accent-glow` | 1px ring + 16px soft glow using `--color-accent` at 40%/25%             |
| `shadow-neon-glow`   | 1px ring + 20px + 48px cascading glow using `--color-accent` at 50%/45%/20% |

**Named Tailwind background-image aliases** (from `theme.extend.backgroundImage`):

| Tailwind class          | Maps to                   |
|-------------------------|---------------------------|
| `bg-grain`              | `var(--bg-grain)`         |
| `bg-hairline-grid`      | `var(--bg-hairline-grid)` |
| `bg-canvas-vignette`    | radial gradient (fixed)   |

Background-size helpers for grids: `bg-grid-sm` = 24×24px, `bg-grid-md` = 40×40px.

---

## 15. Font family aliases

| Tailwind class   | Stack                                                             |
|------------------|-------------------------------------------------------------------|
| `font-sans`      | Geist, system-ui, -apple-system, Segoe UI, Roboto, sans-serif    |
| `font-display`   | JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace |
| `font-mono`      | JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace |

`font-display` and `font-mono` resolve to the same stack. `font-mono` also activates
OpenType features `calt`, `ss01`, and `zero` via the `.font-mono` CSS rule in `index.css`.

---

## Appendix: Theme application

Themes are applied by setting classes on `<html>`:

| Theme | HTML class(es)        | Description                                          |
|-------|-----------------------|------------------------------------------------------|
| Light | (no class)            | Default `:root` variables active                     |
| Dark  | `dark`                | `.dark` overrides applied                            |
| Neon  | `dark neon`           | `.dark` then `.neon` — neon wins CSS cascade; Tailwind `dark:` variants fire |

The neon theme requires **both** `dark` and `neon` on `<html>` so that Tailwind's
`dark:` variant (used in badges and conditional classes) continues to apply, while the
`.neon` CSS block overrides the visual colours.
