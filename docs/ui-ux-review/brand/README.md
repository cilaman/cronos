# Cronos Brand Assets

Logo set and design tokens for **Cronos** — the harnessed agentic task management system.

> Version 1.0.0 · V2 Deep Violet · Generated June 2026

---

## Quick start

Open `preview.html` in any browser to see every asset in context with dark/light toggling. No build tools required.

To use in your app:

```html
<!-- favicon -->
<link rel="icon" type="image/svg+xml" href="brand/logo/cronos-favicon.svg">
<link rel="apple-touch-icon" href="brand/png/apple-touch-icon-180.png">

<!-- design tokens -->
<link rel="stylesheet" href="brand/tokens/tokens.css">

<!-- navbar logo -->
<img src="brand/logo/cronos-lockup-h.svg" alt="Cronos" height="48">

<!-- status indicator -->
<img src="brand/states/cronos-state-active-animated.svg" alt="running" width="16">
```

---

## What's in here

```
brand/
├── README.md              this file
├── preview.html           open-in-browser preview of every asset
├── logo/                  primary logo assets (SVG)
├── states/                runtime state icons (SVG)
├── tokens/                design tokens (CSS + JSON)
└── png/                   rasterized exports at standard sizes
```

---

## Asset map

### `logo/`

| File | Use for | Size guidance |
|---|---|---|
| `cronos-mark.svg` | Primary glass mark | 64px and up — hero, marketing, app icon source |
| `cronos-mark-flat.svg` | Simplified mark | 24–64px — UI tiles, toolbars |
| `cronos-mark-mono.svg` | Monochrome — inherits `currentColor` | Any size — buttons, icons inside text |
| `cronos-lockup-h.svg` | Horizontal lockup (mark + wordmark) | Navbars, page headers |
| `cronos-lockup-v.svg` | Vertical lockup with tagline | Splash screens, login, square aspect |
| `cronos-app-icon.svg` | Rounded square tile | OS app icons, social share images |
| `cronos-favicon.svg` | Ultra-simplified | 16–24px favicons |

### `states/`

| File | Color | Semantic |
|---|---|---|
| `cronos-state-idle.svg` | violet `#7A4FB0` | Default · brand identity |
| `cronos-state-active.svg` | lime `#A6FF2E` | Agent in flight · run in progress |
| `cronos-state-active-animated.svg` | lime + SMIL | Same as active, with rotating orbit and pulsing core |
| `cronos-state-passed.svg` | cyan `#2EC4FF` | Gate passed · goal complete |
| `cronos-state-blocked.svg` | amber `#FFA62E` | Gate failed · awaiting decision |
| `cronos-state-failed.svg` | red `#FF6E5C` | Run error · executor crash |

### `png/`

| File | Size | Use for |
|---|---|---|
| `cronos-mark-{512,256,128}.png` | various | OG images, social, fallback rasters |
| `cronos-mark-flat-{64,32}.png` | small | toolbars |
| `cronos-app-icon-512.png` | 512px | PWA manifest, app store |
| `apple-touch-icon-180.png` | 180px | iOS home screen |
| `favicon-{48,32,16}.png` | favicons | Browser tab icon raster fallback |

---

## Design tokens

CSS custom properties live in `tokens/tokens.css`. JSON for design tools in `tokens/tokens.json`.

| Token | Hex | Notes |
|---|---|---|
| `--cronos-brand` | `#7A4FB0` | Primary mid-tone. WCAG 5.9:1 on white. |
| `--cronos-brand-deep` | `#6A3FA0` | For wordmarks on light surfaces. |
| `--cronos-brand-light` | `#B895E0` | Accents and hover states on dark surfaces. |
| `--cronos-brand-ink` | `#2A0848` | Deepest violet for shadows. |
| `--cronos-state-active` | `#B8FF5C` | Reserved for "agent running" — do not use as decorative accent. |
| `--cronos-state-passed` | `#2EC4FF` | Gate ok / goal complete. |
| `--cronos-state-blocked` | `#FFA62E` | Gate failed / awaiting decision. |
| `--cronos-state-failed` | `#FF6E5C` | Run error / executor crash. |

---

## Wordmark typeface

The wordmark in the lockups uses a generic fallback chain (`Inter, Helvetica Neue, Arial, sans-serif`). **This is a placeholder.**

Before production use, pick one of:

- **Inter** — neutral, ubiquitous, free
- **Geist** — Vercel, more modern, free
- **IBM Plex Sans** — open-source, technical feel
- **JetBrains Mono** — for terminal-themed contexts

Then either ensure the font is loaded with the lockup, or convert the wordmark text to outlined paths so it renders consistently without a font dependency.

---

## Design decisions

A short record of why things are the way they are, so the next maintainer doesn't relitigate.

1. **Brand is deep violet, not lime.** Lime was strongly considered but rejected because it collides with the runtime semantic for "running / OK" that any agentic system needs. Lime was promoted to the reserved `--cronos-state-active` slot.

2. **PASSED is cyan, not emerald.** Emerald (proposed first) was too close to active lime for colorblind users (deuteranopia / protanopia). Cyan is clearly distinguishable from both violet brand and lime active.

3. **Below 64px, switch to the flat mark.** The translucent gradients, sheen highlights, and three concentric rings in the full glass mark turn to mush at small sizes. The flat version preserves identity (3 rings + 3 anchors + core) without depending on rendering fidelity. The favicon goes further — 1 ring + 1 dot — because three rings at 16px is unreadable.

4. **Monochrome uses `currentColor`.** Theme-agnostic; the mark inherits whatever color the parent element has. Useful for icon-in-button contexts.

5. **State icons share geometry with the flat mark.** A single visual language across idle / active / passed / blocked / failed, recoloured rather than redrawn. The animated active uses SMIL (currently supported in all major browsers) for self-contained portability — no JS, no CSS keyframes external file.

---

## Constraints / what not to do

- **Don't use lime as a decorative accent.** It's the running indicator. Decorative lime elsewhere will create false "system is working" signals.
- **Don't render the full glass mark below 48px.** It loses identity and looks like noise. Use `cronos-mark-flat.svg` or `cronos-favicon.svg`.
- **Don't recolour the glass mark to brand variants without rebuilding the gradients.** The ring gradients are tuned for the violet palette; swapping them naively produces muddy mid-tones. Use the flat or mono variants if you need a recolour.
- **Don't add additional anchor nodes.** The three nodes are intentional — three anchors define a plane / harness. Two reads as binary, four reads as ornament.

---

## Regenerating PNGs

If you change an SVG and need to update its PNG export:

```bash
pip install cairosvg --break-system-packages
python3 -c "import cairosvg; cairosvg.svg2png(url='logo/cronos-mark.svg', write_to='png/cronos-mark-256.png', output_width=256, output_height=256)"
```

A batch script is straightforward — see the `png/` listing above for the full set of size targets.

---

## License

These assets are project assets for Cronos. Use freely within the project. If extracting for use elsewhere, please credit.
