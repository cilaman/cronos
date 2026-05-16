---
name: frontend-design
description: Create distinctive, production-grade UI for Cronos — the Kanban task manager that orchestrates Claude Code agents. Use this skill when the user asks to build, restyle, or beautify any React component, page, modal, or interface in the frontend/ workspace (e.g. board lanes, cards, detail views, chat input, live logs, login, settings). Generates polished React + TypeScript + Tailwind code with a coherent aesthetic point-of-view, avoiding generic AI slop.
license: Internal use — Cronos project.
---

# Cronos Frontend Design

This skill guides creation of distinctive, production-grade frontend interfaces inside the Cronos workspace. Cronos is a personal Kanban-style task manager that orchestrates Claude Code agents — four lanes (Backlog → Active → Waiting → Done), drag-and-drop cards, a chat input for talking to agents, and a live execution log. Implement real working code with exceptional attention to aesthetic details and creative choices, while respecting the actual stack and conventions of this repo.

## The workspace you're designing in

**Stack — do not import alternatives without explicit request:**
- React 18.3 + TypeScript 5.6, built with Vite 5.4
- Tailwind CSS 3.4 (utility-first) + `@tailwindcss/typography`
- `@tanstack/react-query` for server state, `@dnd-kit/core` for drag-and-drop
- `react-markdown` + `remark-gfm` for rendered task content
- **No external UI library** (no shadcn/ui, Radix, Material, Chakra). All primitives are hand-rolled.
- **No animation library** (no Framer Motion, no Motion). CSS transforms/transitions only.
- **No icon library currently in use** — inline glyphs (`＋`, `✕`) or inline SVG. If a project needs many icons, prefer adding inline SVG components over pulling a package; ask before adding `lucide-react`.

**File layout:**
```
frontend/src/
  components/       new UI components go here, flat (no subfolders unless a feature needs ≥3 files)
  hooks/            data + behavior hooks (useTasks lives here)
  api.ts            fetch helpers — call these, don't fetch directly
  types.ts          TaskState, Task, Board — extend here, don't redeclare
  state-badges.ts   semantic color tokens by TaskState
  App.tsx           root layout
  main.tsx          entry
  index.css         only @tailwind directives — add @layer/@font-face here if needed
```

**Reusable building blocks already in the repo — prefer extending these:**
- [Board.tsx](frontend/src/components/Board.tsx) — drag-drop container, lane layout
- [Lane.tsx](frontend/src/components/Lane.tsx) — column shell with count badge
- [Card.tsx](frontend/src/components/Card.tsx) — draggable task tile
- [Detail.tsx](frontend/src/components/Detail.tsx) — modal task inspector (modal pattern: `bg-slate-900/50` backdrop, full-screen on mobile, `max-w-3xl` centered on desktop, Escape-to-close)
- [TaskForm.tsx](frontend/src/components/TaskForm.tsx) — create/edit modal
- [ChatInput.tsx](frontend/src/components/ChatInput.tsx) — agent chat affordance
- [LiveLog.tsx](frontend/src/components/LiveLog.tsx) — streaming execution log
- [state-badges.ts](frontend/src/state-badges.ts) — `STATE_BADGE[state]` returns Tailwind classes; reuse for any UI that surfaces task state

**Current baseline palette (the floor, not the ceiling):**
- Neutrals: `slate-{50,100,200,400,500,600,800,900}`
- State accents: `emerald` (active), `amber` (waiting), `blue` (done), `slate` (backlog)
- Theme color (PWA meta): `#215732` deep green — the *true* aesthetic anchor of the project; the current `bg-slate-50` UI undersells it.
- Light mode only today; dark mode is not implemented.

**Recommended direction: go darker.** The default `slate-50` paper is provisional. New work should bias toward a **deep, low-key palette** — either:
1. **Dark mode by default** — near-black neutrals (`slate-900`, `slate-950`, `#0b0f0d`, `#10130f`) with off-white type and a single luminous accent. Wire it via `darkMode: 'class'` in `tailwind.config.js` and set the root class in [main.tsx](frontend/src/main.tsx) or `index.html`; don't half-implement with `dark:` variants only.
2. **Deep daylight** — replace `bg-slate-50` with a darker, warmer surface (`#1c1f1a` ink-on-moss, `#2a2522` warm pitch, `#0f1411` forest-shadow) paired with bone/cream type (`#e8e2d3`, `#f1ede4`). Not dim — *deep.*

Either way, lean into the `#215732` bottle-green anchor: oxidized copper, brass, malachite, kelp, ink, oxblood, and bone are all on the table as the single sharp accent. The four `TaskState` colors stay semantically distinct but should be re-toned for a dark surface (deeper emerald, burnt amber, indigo-blue, charcoal) — update [state-badges.ts](frontend/src/state-badges.ts) accordingly when you migrate. Avoid washed-out mid-greys; commit to the dark.

## Design thinking before you code

Cronos is a tool the user lives inside — it must feel like a *real* product, not a generic kanban template. Commit to a clear aesthetic direction and execute it with precision.

1. **Purpose** — What does this view/component actually do? Who is the operator (a single power user running agents on their VPS), and what do they need to feel at a glance? Speed, control, calm, or momentum?
2. **Tone** — Pick one and commit. For Cronos, directions that fit the domain especially well: *terminal/CLI-inflected*, *editorial/notebook*, *industrial-utilitarian*, *Swiss/grid-systemic*, *cartographic/topographic* (lanes as territory), *muted brutalism*. Avoid the SaaS-default "rounded purple gradient on white." If the user names a different tone, follow theirs.
3. **The memorable detail** — One thing a returning user will recognize from a thumbnail: a typographic tic, a state-transition motion, a card silhouette, a lane separator treatment, an empty state. Design it first; let the rest fall in line.
4. **Stack-honest restraint** — Maximalism here means *typographic richness, deliberate color, sharp motion*, not heavy assets or animation libraries. Match implementation complexity to vision; CSS-only animation can still feel choreographed.

## Aesthetic guidelines (Cronos-specific)

**Typography.** System fonts are the *current* default, not a mandate. When elevating a view, introduce one display face and one body face via Google Fonts or self-hosted `@font-face` in [index.css](frontend/src/index.css). Avoid the AI-default trio (Inter, Roboto, Space Grotesk). Lean into character: *JetBrains Mono / IBM Plex Mono* for an operator-console feel; *Instrument Serif / Fraunces / Newsreader* for editorial weight; *Geist / Söhne-like alternatives, Söhne is paid*; *Pixelify Sans / VT323* for retro-terminal accents on logs. Pair a distinctive display face with a refined neutral body. Set tracking, leading, and optical sizes explicitly — don't accept Tailwind defaults blindly.

**Color.** Don't paint with the whole `slate` rainbow. Pick a dominant *dark* neutral lane (near-black ink, forest shadow, warm pitch, oxidized graphite) and a single sharp accent that earns its appearance. The PWA theme `#215732` is the anchor — push toward bottle green, malachite, oxidized copper, brass, kelp, or oxblood. Use the existing emerald/amber/blue *only* for the four `TaskState` badges via [state-badges.ts](frontend/src/state-badges.ts), re-toning their shades for legibility against the dark surface; reserve the chrome accent for links, focus rings, selection, headings. Define new tokens in `tailwind.config.js` `theme.extend.colors` rather than scattering hex codes. Aim for contrast that feels confident, not hazy — bone-on-pitch beats grey-on-grey.

**Motion.** No animation library — use CSS `@keyframes`, `transition`, and `transform`. Prioritize a few high-impact moments over scattered micro-interactions:
- One orchestrated load: stagger lane reveals with `animation-delay`.
- State changes (card moves between lanes) deserve a real transition, not an opacity flip.
- Hover affordances on cards: lift, border-darken, or expose secondary metadata.
- The live log already streams — let new lines fade-in from the bottom with a 120–180ms ease-out.
Respect `prefers-reduced-motion` — wrap non-essential animations in `@media (prefers-reduced-motion: no-preference)`.

**Spatial composition.** The board is a horizontal grid by necessity; everything else can break the grid. Asymmetric headers, decorative rules, oversized numerals for lane counts, marginalia. Generous breathing room around the board, controlled density inside cards. Modal pattern is established in [Detail.tsx](frontend/src/components/Detail.tsx) — extend it, don't reinvent.

**Backgrounds & texture.** Flat `bg-slate-50` is the default to *replace*, not preserve. On a dark surface, atmosphere matters more — empty pitch reads as cheap, layered pitch reads as designed. Acceptable atmosphere on this stack: a subtle CSS grain/noise via SVG `feTurbulence` data-URL, a hairline grid in `linear-gradient` (faint, ~4% opacity on dark), a slow radial gradient behind the header, a vignette at the board edges, phosphor-glow on accent text. Keep it cheap — no large raster assets in `public/`.

**Iconography.** When a glyph beats text, prefer inline SVG (single-path, `currentColor`) inside a tiny component. If a feature truly needs a kit, ask before adding `lucide-react` — it is small and fits the aesthetic if introduced cleanly.

## What to avoid (the AI-slop list, calibrated to this repo)

- Purple→pink gradients on white. The Cronos theme color is deep green and the direction is dark; don't fight it.
- "Dark mode" that is just `bg-slate-900` with otherwise unchanged tokens. Re-tone the accents and surfaces; don't invert lazily.
- `font-family: Inter, system-ui, sans-serif` as the elevated answer. System UI is the *baseline*; if you're "designing," you must commit to a face.
- Bootstrap-style rounded-2xl-shadow-xl cards stacked uniformly down the page.
- A primary button that is just `bg-blue-600 text-white rounded`.
- Emoji as iconography (this codebase already avoids it — keep it that way).
- Adding `framer-motion`, `lucide-react`, `shadcn/ui`, `@radix-ui/*`, `clsx`, or any styling-adjacent package without surfacing the dependency change to the user first.
- Inventing a new color token in JSX. Put it in `tailwind.config.js` so it composes.
- Breaking the `STATE_BADGE` contract — those four colors are semantic across the app.

## Output expectations

Code you write should be:
- **Production-grade**: typed, drop-in, no `any`, no TODOs left behind.
- **Stack-honest**: only the deps already in `frontend/package.json`, unless the user OK'd more.
- **Cohesive**: a single aesthetic direction per request — don't blend three.
- **Refined down to the details**: focus rings, hover states, empty states, loading skeletons, mobile layout. The 90% case isn't done; the edges are where Cronos lives.
- **Accessible enough to be real**: keyboard reachable, `aria-*` on interactive non-buttons, contrast ratios that survive AA, `prefers-reduced-motion` honored.

When the user asks for one component, deliver one component built well, in the right file, using the existing hooks/api/types, with any new tokens added to `tailwind.config.js` and any new fonts wired into `index.css`. Show the work — don't hold back on the distinctive choice that makes the surface memorable.
