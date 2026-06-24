# Cronos UI/UX Review — June 2026

A full audit of the Cronos web frontend with a plan to **unify and modernize** the
interface so it is consistent, crisp, and easy to use — without throwing away the
strong "operator console" identity it already has.

**Scope:** analysis and design only. No implementation, no code changes. Every
document here is a spec or a wireframe meant to be executed later as its own goal.

## The one-sentence finding

> Cronos has a genuinely good design *foundation* (semantic theme tokens, three
> coherent themes, custom shadow/atmosphere system, a real `components/ui/`
> primitives folder) — but the foundation is applied **inconsistently**, so the
> product reads as several apps wearing the same paint.

The work is therefore **consolidation, not reinvention**: promote the good patterns
into enforced primitives and tokens, then retire the ad-hoc copies.

## Documents

| # | File | What's inside |
|---|------|---------------|
| 1 | [01-executive-summary.md](01-executive-summary.md) | Scorecard, top 10 findings, prioritized roadmap (P0–P2), effort/impact |
| 2 | [02-design-system.md](02-design-system.md) | The proposed unified system: status & categorical color tokens, type scale, spacing, radius, z-index, motion, icon strategy, primitive catalog |
| 3 | [03-consistency-findings.md](03-consistency-findings.md) | The evidence — every inconsistency with counts, file:line refs, and severity |
| 4 | [04-wireframes.md](04-wireframes.md) | Wireframes **index** — section map + responsive notes + generated previews, pointing to the HTML (the single source of truth). No hand-maintained ASCII copy. |
| 5 | [05-roadmap.md](05-roadmap.md) | Phased execution plan + component API specs (props only, no code) |
| 6 | [06-brand.md](06-brand.md) | How the brand asset set ([`brand/`](brand/)) layers onto the system — logos, runtime-state marks, the lime-reserved rule, and how brand colours reach the status tokens |
| — | **[wireframes/index.html](wireframes/index.html)** | **Interactive HTML wireframes** — open in a browser; brand logos + runtime-state marks (§00) plus 9 unified patterns rendered with the proposed token system and a live **light / dark / neon** toggle (watch every badge re-resolve from tokens — the headline fix, demonstrated) |
| — | [brand/preview.html](brand/preview.html) | The brand asset preview — every logo/state/token in context with a dark/light toggle (source of the assets folded in here) |

> **Open the HTML wireframes:** `open docs/ui-ux-review/wireframes/index.html`. Self-contained
> (fonts via CDN); toggle the theme in the top-left rail to see status/categorical colour
> adapt across all three themes.
>
> **Responsive** — built for MacBook / iPad / iPhone. Desktop & iPad (≥768px) keep the
> rail and show the detail two panes side by side; below 768px the chrome switches to a
> sticky mobile bar (theme switch lives there), the board lanes become swipeable, and the
> two-pane workspace collapses to a `Context | Conversation` tab switch. Resize the window
> or use device emulation to check 393px (iPhone 17), 834px (iPad), 1440px (MacBook).

Static previews (rendered from the HTML) — same components, three themes:

| Dark (operator console) | Light (editorial paper) | Neon (midnight navy) |
|---|---|---|
| ![dark](wireframes/preview-dark.png) | ![light](wireframes/preview-light.png) | ![neon](wireframes/preview-neon.png) |

## Method

Four parallel read-only audits over the entire `frontend/src` tree (≈18 pages, ≈55
components), cross-referenced against the two design skills (`frontend-design` for
aesthetic direction, `ui-ux-pro-max` for the accessibility/interaction rule set).
Findings are grounded in the actual code — file:line references throughout.

## Design north star

Cronos is an **operator console for orchestrating AI agents** — a mission-control
surface, not a generic SaaS dashboard. The existing vocabulary already says this:
JetBrains Mono labels, hairline grids, phosphor-green-on-deep-forest, status-as-light
(pulse dots, accent glow), film grain. The plan **leans into** that identity and makes
it the consistent, deliberate signature rather than an effect applied in some places
and forgotten in others.

The **brand asset set** ([`brand/`](brand/), folded into [06-brand.md](06-brand.md))
sharpens that identity: **deep violet `#7A4FB0`** is the logo/wordmark/idle colour, and
**lime-green is reserved for `running`** — so green only ever means "an agent is working,"
which is exactly the status-as-light language above. The chrome accent stays per-theme;
the brand contributes the logos, the runtime-state marks, and the status colour palette.

## Implementation status

This design document is now being implemented incrementally as autonomous CC-v1 pipeline goals. Progress:

- **gui-detail-ux** (goal 2026-06-22-1335) — DELIVERED. Implements the detail view UX improvements:
  - `DetailShell` component (I1): Shared shell for task and feature details with discriminated union variant (`task | feature`); owns Modal, skeleton, error+retry, header/footer slots.
  - `Detail.tsx` adoption (I2): Adopts DetailShell, replaces inline Modal/skeleton; test coverage maintained.
  - Two-pane workspace (I4): Task Detail split into independently scrolling panes (Context left, sticky | Conversation right); mobile breakpoint md (768px) tabs to Context | Conversation switch.
  - NOW running card (I5): Sticky live indicator in conversation pane for ACTIVE tasks; animated SVG asset.
  - `FeatureDetail.tsx` adoption (I3): Adopts DetailShell, replaces local skeleton/header markup.
  - Tree improvements (I6–I7): TreeNode compact rows + connector lines; TreeToolbar Tree/DAG toggle button (F6 disclosure: placed in TreeToolbar by design, not TreePage).
  - Semantic token migration (I9): Raw Tailwind palette classes (24 instances in Detail/FeatureDetail) replaced with semantic tokens (`danger`, `warning`, `accent`, `surface-*`, `bg-warning/10`, CSS-var syntax for goal badge colors).
  - Exit gate: clean build (tsc + vite), all tests green (5 pre-existing failures only, zero new regressions), scope delivered.
  - Non-blocking deviations disclosed: F6 (toggle placement), F7 (test-only mock fix), F8 (DetailShell unification scope deferred).

Other gui-refactor goals (gui-tokens-brand, gui-layout-primitives, gui-badge-system, gui-button-focus, gui-icons, gui-modal-loading, gui-polish) completed or in flight; see goal tree for full status.
