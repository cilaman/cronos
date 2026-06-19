---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-06T12:53:57Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-06-1253-features-board-redesign
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-06-1253-update-to-features-page
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: features board redesign
type: goal
updated_at: '2026-06-13T14:30:16Z'
waiting_question: null
---

# Brief

# Pipeline subgoal: Update to Features page

CC-v1 pipeline run scaffolded by the features-redesign setup script. Verbatim
request is at `.cronos/pipeline/{goal_slug}/request.md`; live state at
`.cronos/pipeline/{goal_slug}/pipeline-state.json`.

Child of root goal `2026-06-06-1253-update-to-features-page`. Branch + merge are root-goal driven
(/goal-branch-setup, /goal-finalize resolve the root).

## Request

# Redesign the Features board to behave like the Tasks board

The Features board (`frontend/src/components/FeaturesBoard.tsx`,
`frontend/src/pages/FeaturesPage.tsx`) currently diverges from the Tasks board
in ways that make it feel like a second-class surface. Bring it to parity with
the Tasks board (`BoardPage.tsx` / `Board.tsx` / `Lane.tsx` / `BoardToolbar.tsx`)
while keeping the FeatureState lane system (FEATURE_LANES) and the
feature/fix type distinction intact.

## Required changes

R1. **Add a feature/fix via a "+" on the Backlog lane (not the inline form).**
    Today a `FeatureComposer` inline form (radio Feature/Fix toggle + text input
    + Add button) is permanently mounted under the Backlog lane
    (`FeaturesBoard.tsx:212`), and every Lane is rendered with `showAdd={false}`.
    Replace this with the Tasks-board interaction: show the "+" add button on the
    Backlog lane header (Lane already supports `showAdd` and renders the button),
    and open the feature composer on demand (modal or popover) when "+" is
    clicked. The composer must still let the user choose Feature vs Fix and enter
    a title, and submit through `useCreateFeature`. The always-visible inline form
    under the lane should be removed.

R2. **Allow hiding lanes, exactly like the Tasks board.**
    The Tasks board lets the user hide individual lanes via the "×" button on the
    lane header (`Lane.tsx` `onHideLane`), persists the hidden set to localStorage
    keyed by space (see `readBoardLaneOverride`/`writeBoardLaneOverride` in
    `storage.ts`), and renders "Hidden:" restore chips above the grid
    (`Board.tsx`). Add the same capability to the Features board: wire
    `onHideLane` on each Features Lane, persist the hidden FeatureState set to
    localStorage (use a Features-scoped key, e.g. keyed by spaceId), filter hidden
    lanes out of the grid, and render restore chips so the user can bring a lane
    back. The responsive grid column count must adjust to the number of visible
    lanes (mirror the Tasks board's lgCols logic).

## Further optimizations (in scope)

R3. **Clickable feature cards.** Card `onOpen` is currently a no-op
    (`onOpen={() => {}}`). Wire it so clicking a feature/fix card opens its
    detail view/drawer, matching how Task cards open.

R4. **Toolbar parity + reset + correct empty-state copy.** Bring the Features
    toolbar closer to the Tasks toolbar: a clear add affordance, a "show all
    hidden lanes" reset control when one or more lanes are hidden, and lane
    empty-state copy that says "No features" rather than the inherited
    "No tasks" (Lane currently hardcodes "No tasks").

R5. **Per-space persisted layout.** Hidden-lane choices must persist per space
    (like the Tasks board's space-keyed override) so the layout survives reloads
    and space switches on both the scoped (`/spaces/:spaceId/features`) and global
    (`/features`) variants of the page.

## Constraints

- Keep FEATURE_LANES and the FeatureState state machine; do NOT collapse the
  Features board onto TaskState. Lane.tsx and Card.tsx are shared with the Tasks
  board — preserve their existing Tasks-board behaviour (the `showAdd` default of
  `state === "backlog"`, the `state: string` widening) and avoid regressions.
- All UI work MUST use the `/frontend-design` skill for a distinctive, cohesive,
  production-grade aesthetic (lane headers, type badges, the composer modal,
  restore chips) — no generic AI-slop styling.
- Maintain TypeScript strict typing; resolve the TaskState-vs-FeatureState typing
  at call sites with explicit wrappers rather than `any`.
- Add/extend frontend tests (vitest) for the new add flow, lane-hiding
  persistence, and restore chips; keep the existing suites green.

## Acceptance

- New feature/fix is created via the Backlog lane "+" (composer opens on click);
  the old always-on inline form is gone.
- Individual Features lanes can be hidden and restored; the choice persists per
  space across reloads.
- Feature cards open their detail on click.
- `npm run build` and `npm test` pass; backend pytest suite stays green.


## Child tasks (one per CC-v1 phase)

1. scout    — pipeline-scout    (research)
2. analysis — pipeline-analyst  (analysis)
3. design   — pipeline-architect(design)
4. impl     — pipeline-implementor (implementation; may fan out per iteration)
5. test     — tester            (test)
6. review   — pipeline-reviewer (review; may loop on verdict=needs_fix)
7. doc      — pipeline-doc-sync (doc; terminal — runs /goal-finalize)

Each phase task ends by invoking `/pipeline-gate` which closes the gate from the
artifact's YAML header — no prose parsing.

# History

```
2026-06-06T14:10:13Z [agent]
All tasks complete. Completed 7, skipped 0 already-done.
```
