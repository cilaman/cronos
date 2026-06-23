---
cc_version: '1.0'
agent: pipeline-architect
slug: gui-detail-ux
phase: design
status: done
confidence: 0.84
inputs_used:
- memory:project_gui_refactor_board_setup
- memory:project_gui_tokens_brand_review_attempt1
- memory:project_pipeline_architect_agent
- .cronos/pipeline/gui-detail-ux/request.md
- .cronos/pipeline/gui-detail-ux/scout-report-gui-detail-ux.md
- .cronos/pipeline/gui-detail-ux/analysis-report-gui-detail-ux.md
- frontend/src/components/Detail.tsx
- frontend/src/components/FeatureDetail.tsx
- frontend/src/components/TreeNode.tsx
- frontend/src/components/TreeView.tsx
- frontend/src/pages/TreePage.tsx
- frontend/src/hooks/useLiveStream.ts
- frontend/vite.config.ts
outputs_produced:
- .cronos/pipeline/gui-detail-ux/design-report-gui-detail-ux.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/components/
  - frontend/src/components/ui/
  - frontend/src/components/__tests__/
  - frontend/src/pages/
  - frontend/src/hooks/
  - docs/ui-ux-review/brand/states/
  excluded:
  - 'backend/: frontend-only feature, no backend changes required (analysis confirmed)'
  - 'node_modules/: dependency snapshots'
  - 'frontend/src/generated/: auto-generated, no schema changes here'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: frontend
  scope_files:
  - frontend/src/components/ui/DetailShell.tsx
  - frontend/src/components/ui/__tests__/DetailShell.test.tsx
  validation_command: cd frontend && npm test -- src/components/ui/__tests__/DetailShell.test.tsx
    --run
  max_diff_lines: 450
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/src/components/Detail.tsx
  - frontend/src/components/__tests__/Detail.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Detail.test.tsx
    --run
  max_diff_lines: 600
  depends_on:
  - I1
- id: I3
  type: frontend
  scope_files:
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/components/__tests__/FeatureDetail.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/FeatureDetail.test.tsx
    --run
  max_diff_lines: 400
  depends_on:
  - I1
- id: I4
  type: frontend
  scope_files:
  - frontend/src/components/Detail.tsx
  - frontend/src/components/__tests__/Detail.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Detail.test.tsx
    --run
  max_diff_lines: 500
  depends_on:
  - I2
- id: I5
  type: frontend
  scope_files:
  - frontend/src/components/Detail.tsx
  - frontend/src/assets/cronos-state-active-animated.svg
  - frontend/src/components/__tests__/Detail.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Detail.test.tsx
    --run
  max_diff_lines: 400
  depends_on:
  - I4
- id: I6
  type: frontend
  scope_files:
  - frontend/src/components/TreeNode.tsx
  - frontend/src/components/__tests__/Tree.test.tsx
  - frontend/src/components/__tests__/TreeDnd.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Tree.test.tsx
    src/components/__tests__/TreeDnd.test.tsx --run
  max_diff_lines: 500
  depends_on: []
- id: I7
  type: frontend
  scope_files:
  - frontend/src/pages/TreePage.tsx
  - frontend/src/components/TreeView.tsx
  - frontend/src/components/__tests__/TreeToolbar.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/TreeToolbar.test.tsx
    --run
  max_diff_lines: 300
  depends_on:
  - I6
- id: I8
  type: frontend
  scope_files:
  - frontend/src/components/Detail.tsx
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/components/TreeNode.tsx
  - frontend/src/components/ui/DetailShell.tsx
  validation_command: cd frontend && npm run build && npm test -- --run
  max_diff_lines: 200
  depends_on:
  - I3
  - I5
  - I7
risks:
- description: DetailShell footer slot may not cleanly absorb task-side mutation hooks
    (start/stop/promote, useMutation handles) without TypeScript inference loss across
    the variant boundary, forcing a discriminated union that complicates both Detail
    and FeatureDetail call sites.
  severity: medium
  mitigation: 'I1 designs DetailShell with a single ReactNode `footer` prop and a
    discriminated `variant: ''task'' | ''feature''` that only affects badge rendering;
    mutation hooks stay inside the caller (Detail/FeatureDetail) and the rendered
    JSX is passed as footer, keeping inference local. I1 test asserts both variants
    render given a stub footer.'
- description: Two-pane layout inside the existing Modal wrapper may not produce bounded
    heights for `overflow-y-auto` to activate; without a fixed parent height, both
    panes will collapse to content height and scroll the modal instead of scrolling
    each pane independently.
  severity: high
  mitigation: I4 explicitly sets `h-full min-h-0` on the outer two-pane flex container
    and `min-h-0 overflow-y-auto` on each pane child (the `min-h-0` is critical inside
    flex columns). I4 test renders Detail with mocked long Brief and mocked long ConversationStream
    and asserts both panes have `overflow-y-auto` class and that scrolling one does
    not move the other (mock scrollHeight > clientHeight per pane).
- description: Test selectors in Detail.test.tsx and FeatureDetail.test.tsx that target
    the old inline header/skeleton markup (e.g. `getByText('Loading…')` inside an
    inline skeleton, role queries against the old header structure) will break when
    DetailShell takes over rendering, producing red tests that look like regressions
    but are selector drift.
  severity: medium
  mitigation: I2 and I3 each update the colocated test file as part of the same iteration
    (same scope_files). Test updates are scoped to selector changes only; assertion
    intent (skeleton visible on load, header shows badge X, etc.) is preserved. I8
    final pass runs the full vitest suite to catch any sibling test files that also
    queried the old structure.
- description: The `cronos-state-active-animated.svg` lives in `docs/ui-ux-review/brand/states/`
    which is outside the frontend Vite source tree; importing it via a relative path
    `../../../docs/...` works locally but will break in the Docker build context where
    `docs/` may not be copied into the frontend image.
  severity: medium
  mitigation: I5 copies the SVG into `frontend/src/assets/cronos-state-active-animated.svg`
    (creating the assets/ directory) and imports it from there via Vite's standard
    asset URL import. The `docs/` copy remains as documentation source-of-truth; I5
    test asserts the img/inline-SVG renders inside the NOW running card without depending
    on doc-tree paths.
- description: TreeNode currently delegates drag-drop and gap-zone rendering to Card;
    replacing Card with a compact row risks breaking dnd-kit drag handles and the
    GapZone insertion targets exercised by TreeDnd.test.tsx.
  severity: medium
  mitigation: I6 preserves the dnd-kit useSortable wiring and GapZone components;
    only the visual leaf (Card -> compact row markup) changes. The compact row reuses
    Card's drag-handle ref pattern. TreeDnd.test.tsx is in I6's scope_files so the
    implementor adjusts dnd-related selectors in the same diff. If drag handle DOM
    moves, the existing TreeDnd assertions catch it before I7 runs.
- description: The NOW running card requires fields (subagent_name, step_count, token_count)
    that are not first-class properties on useLiveStream's StreamEntry types; derivation
    logic (count entries, scan latest tool_call) is heuristic and may surface as wrong
    values in long-running tasks.
  severity: low
  mitigation: I5 derives step_count from the length of stream entries filtered to
    tool_call/assistant kinds, token_count from a documented placeholder ('—' or count
    of assistant text length / 4 as a rough proxy with a 'estimate' label), and tool_name
    from the most recent ToolCallEntry. I5 test mocks useLiveStream with a known entry
    list and asserts the card renders the derived values; an inline comment in Detail.tsx
    flags the proxy nature so review/doc phase can note the follow-up.
- description: I7 (DAG toggle) re-mounts GoalDependencyGraph each time the toggle
    flips, which discards any internal dagre layout state and forces a re-layout;
    on large goal trees this may produce a visible flash but does not break correctness.
  severity: low
  mitigation: I7 keeps the toggle state in local useState in TreePage; both TreeView
    and GoalDependencyGraph are mounted conditionally (no parallel rendering). Tree
    expand/collapse state lives in TreeView's existing local state and survives because
    TreeView remains mounted when toggle === 'tree'. I7 test asserts toggle flips
    render the correct component and that switching back to tree preserves an expanded
    node.
metrics:
  tool_calls: 12
  files_read: 10
  memory_hits: 3
  iterations_planned: 8
---

## Summary

This design splits the gui-detail-ux subgoal into eight frontend iterations across three parallel layers. Layer 0 builds the shared `DetailShell` primitive (I1) and refactors `TreeNode` to compact rows with connector lines (I6) in parallel. Layer 1 adopts DetailShell in `Detail.tsx` (I2) and `FeatureDetail.tsx` (I3), and adds the Tree/DAG toggle (I7). Layer 2 layers the two-pane workspace onto Detail (I4), then the sticky NOW running card (I5), and finally a full-suite regression sweep (I8). The DAG is intentionally wide at the root so DetailShell, TreeNode, and the toggle can land in parallel; the two-pane work serializes onto Detail because both layers mutate the same file. The highest-severity risk is bounded-height collapse inside Modal — mitigated by an explicit `h-full min-h-0` contract spelled out in I4.

## Components

### Data
- No data-model changes. All requirements are pure-frontend; backend contracts and `frontend/src/types.ts` are reused as-is.

### Backend
- No backend changes. Confirmed by analysis (`has_ui: true`, backend explicitly excluded from scope).

### Frontend
- `frontend/src/components/ui/DetailShell.tsx` (new): shared shell — Modal wrapper, status+type badge header, id/key, title, markdown Brief, amber waiting bar (WAITING), edit-mode toggle, loading skeleton; `variant: 'task' | 'feature'` discriminator and `footer: ReactNode` slot.
- `frontend/src/components/Detail.tsx` (refactor): replaces inline header/skeleton/waiting-bar with `<DetailShell variant="task" footer={...}>`; inner footer holds agent tabs, ConversationStream, ChatInput, HierarchySection, StatsPanel, TracePanel, FilesPanel. Receives the two-pane layout (I4) and NOW running card (I5).
- `frontend/src/components/FeatureDetail.tsx` (refactor): replaces inline header/skeleton with `<DetailShell variant="feature" footer={...}>`; deletes `FeatureDetailSkeleton` (lines 21–35) and `FEATURE_STATE_BADGE` (line 9) per R4. Inner footer holds edit mode, Decompose, RelationshipList, issue link.
- `frontend/src/components/TreeNode.tsx` (refactor): replaces `Card density="tight"` leaf with a compact row component (state badge + title + minimal indicators); adds depth-aligned hairline vertical connector lines via CSS pseudo-elements on parent nodes (visible-children only). Preserves dnd-kit `useSortable` wiring and GapZone.
- `frontend/src/pages/TreePage.tsx` + `frontend/src/components/TreeView.tsx` (minor update): adds a `Tree / DAG` toggle button in the page header; local `useState<'tree' | 'dag'>` swaps between TreeView and the existing GoalDependencyGraph; tree expand/collapse state preserved because TreeView remains mounted when mode === 'tree'.
- `frontend/src/assets/cronos-state-active-animated.svg` (new file, copied from `docs/ui-ux-review/brand/states/`): in-bundle asset for the NOW running card so the Docker build does not depend on the `docs/` tree.

## Implementation plan

| ID  | Type     | Depends on    | Scope files (abridged)                                                    | Validation                                                                              |
|-----|----------|---------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| I1  | frontend | -             | ui/DetailShell.tsx + DetailShell.test.tsx                                 | npm test -- src/components/ui/__tests__/DetailShell.test.tsx --run                      |
| I2  | frontend | I1            | Detail.tsx + Detail.test.tsx (header/skeleton adoption only)              | npm test -- src/components/__tests__/Detail.test.tsx --run                              |
| I3  | frontend | I1            | FeatureDetail.tsx + FeatureDetail.test.tsx (R3 + R4 deletions)            | npm test -- src/components/__tests__/FeatureDetail.test.tsx --run                       |
| I4  | frontend | I2            | Detail.tsx + Detail.test.tsx (two-pane R5 + mobile tabs R6)               | npm test -- src/components/__tests__/Detail.test.tsx --run                              |
| I5  | frontend | I4            | Detail.tsx + assets/cronos-state-active-animated.svg + Detail.test.tsx    | npm test -- src/components/__tests__/Detail.test.tsx --run                              |
| I6  | frontend | -             | TreeNode.tsx + Tree.test.tsx + TreeDnd.test.tsx (compact rows + connectors)| npm test -- src/components/__tests__/Tree.test.tsx src/components/__tests__/TreeDnd.test.tsx --run |
| I7  | frontend | I6            | pages/TreePage.tsx + TreeView.tsx + TreeToolbar.test.tsx (DAG toggle)     | npm test -- src/components/__tests__/TreeToolbar.test.tsx --run                         |
| I8  | frontend | I3, I5, I7    | full-suite regression sweep (no edits expected; touch-up only)            | npm run build && npm test -- --run                                                      |

Topological layers (orchestrator fan-out):
- **Layer 0** (parallel): I1, I6
- **Layer 1** (parallel): I2, I3, I7 — but I7 must wait for I6; I2 and I3 wait for I1
- **Layer 2** (serial on Detail.tsx): I4 → I5
- **Layer 3** (final): I8

## Risks

| Risk                                                                           | Severity | Mitigation                                                                                                              |
|--------------------------------------------------------------------------------|----------|-------------------------------------------------------------------------------------------------------------------------|
| Footer slot inference loss across variant boundary                             | medium   | I1 uses ReactNode footer + discriminated variant; mutation hooks stay in caller                                          |
| Two-pane bounded-height collapse inside Modal                                  | high     | I4 sets explicit `h-full min-h-0` contract and asserts independent scroll in test                                        |
| Test selector drift after header/skeleton migrates into DetailShell            | medium   | I2/I3 update colocated test files in same iteration; I8 full-suite sweep catches siblings                                |
| `cronos-state-active-animated.svg` outside Vite source tree breaks Docker build | medium   | I5 copies SVG into `frontend/src/assets/` and imports from there                                                         |
| TreeNode compact row breaks dnd-kit drag handles or GapZone                    | medium   | I6 preserves useSortable wiring + GapZone; TreeDnd.test.tsx in same iteration scope                                      |
| NOW running card fields (subagent, step, token) are derived not first-class    | low      | I5 documents proxy derivations inline; test mocks known stream and asserts derived values                                |
| DAG toggle re-mount discards dagre layout state                                | low      | I7 keeps local useState; TreeView stays mounted when mode==='tree' so expand state survives                              |

## Assumptions

- Mobile breakpoint **canonicalized to Tailwind `md:` (768px)** per the request text ("≥768px") — overrides the scout's earlier `lg:` guess. I4 will use `md:flex-row` for the two-pane split and `md:hidden` for the mobile tab bar.
- Actual scope file locations are `frontend/src/components/Detail.tsx` and `frontend/src/components/FeatureDetail.tsx` (both verified to exist). The task prompt's `frontend/src/pages/Detail.tsx` and `frontend/src/pages/FeatureDetail.tsx` are stale path references inherited from the request brief; analyst (`inputs_used` line 12–13) and scout (Findings §5) both confirm components/.
- DetailShell uses a single `footer: ReactNode` prop, not a render-prop or compound-component pattern, matching the existing Modal call style.
- Tree connector lines render via CSS pseudo-elements (`::before` with absolute positioning relative to a parent `relative` container at each tree level), not an SVG overlay — keeps the DOM tree simple and avoids a second coordinate system.
- Compact tree rows use a new inline row markup inside TreeNode (state badge + title + minimal indicators) rather than introducing a new shared `TreeNodeRow` component. If review feedback requests extraction, a follow-up iteration can lift it.
- `useLiveStream` derivations for the NOW running card: `tool_name` = most recent `ToolCallEntry.name`; `step_count` = length of entries filtered to `tool_call`/`assistant`; `token_count` and `subagent_name` may render as `'—'` placeholders or coarse estimates with an `(estimate)` label until first-class fields exist.
- The Vite/Docker `frontend/Dockerfile` copies `frontend/` into the build context; copying the SVG into `frontend/src/assets/` is the safe portable path.
- Existing `frontend/src/components/__tests__/Detail.test.tsx` and `FeatureDetail.test.tsx` are the canonical regression surfaces; no new tests for ConversationStream, HierarchySection, etc. are in scope unless an iteration touches their direct callsite.

## Open questions

- **NOW running card data fidelity:** Should `subagent_name`, `step_count`, `token_count` block this goal until first-class fields land on `useLiveStream`, or are derived/placeholder values acceptable for MVP? Design assumes the latter; the implementor and reviewer can escalate if the placeholders read as broken in practice.
- **Connector line styling token:** No existing CSS variable for tree connector hairline color/weight. I6 will use `border-cronos-line-muted` (or the closest neutral token from the gui-tokens-brand subgoal) and hard-code only if no token matches. Doc-sync phase can capture if a new token is needed.
- **Card density='compact' vs new compact-row markup:** Design picks new inline row markup. If the gui-button-focus / gui-badge-system iterations have since added a `density='compact'` to Card, I6 should prefer that — implementor checks at start.

## Next consumer brief

Implementor: read `iterations[]`, `iterations[].scope_files`, and `iterations[].validation_command` from the YAML header — that is the machine-readable plan. Cross-iteration invariants not derivable from the YAML:

1. **DetailShell API contract** is set by I1 and consumed verbatim by I2 and I3: `interface DetailShellProps { variant: 'task' | 'feature'; entity: Task | Feature; isLoading: boolean; onClose: () => void; footer: ReactNode; }`. I2 and I3 must NOT redesign this shape — if a field is missing, escalate to architect rather than diverge.
2. **Two-pane height contract** (I4): outer container is `flex h-full min-h-0`, each pane is `flex-1 min-h-0 overflow-y-auto`. The `min-h-0` on the pane is mandatory inside a flex column or the pane will not scroll.
3. **Mobile breakpoint is `md:` (768px)**, NOT `lg:`. Same token everywhere — the tab bar uses `md:hidden`, the two-pane wrapper uses `hidden md:flex` (or equivalent). Do not introduce a third breakpoint.
4. **SVG asset path** (I5): import from `frontend/src/assets/cronos-state-active-animated.svg`, not from the `docs/` tree. Copy the file as part of I5's diff.
5. **TreeNode dnd-kit wiring** (I6): preserve `useSortable` + GapZone; only the visual leaf changes. Run `TreeDnd.test.tsx` as part of the same iteration.
6. **I8 is a sweep, not a feature iteration.** It exists to catch full-suite regressions. If I8's `npm run build` or full vitest fails, fix the root-cause iteration (don't patch I8 itself).

Open questions in the section above are decisions the implementor must take when they hit the relevant iteration; flag any answer that diverges from the assumptions list in the impl-report.
