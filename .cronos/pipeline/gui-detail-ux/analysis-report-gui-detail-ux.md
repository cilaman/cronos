---
cc_version: '1.0'
agent: pipeline-analyst
slug: gui-detail-ux
phase: analysis
status: done
confidence: 0.88
inputs_used:
- memory:project_gui_refactor_board_setup
- memory:project_gui_tokens_brand_review_attempt1
- .cronos/pipeline/gui-detail-ux/scout-report-gui-detail-ux.md
- frontend/src/components/Detail.tsx
- frontend/src/components/FeatureDetail.tsx
- frontend/src/pages/TreePage.tsx
- frontend/src/components/TreeView.tsx
- frontend/src/components/TreeNode.tsx
- frontend/src/components/GoalDependencyGraph.tsx
- frontend/src/components/ConversationStream.tsx
- frontend/src/components/ui/Modal.tsx
outputs_produced:
- .cronos/pipeline/gui-detail-ux/analysis-report-gui-detail-ux.md
blockers: []
next_consumer: design
request: "GUI detail UX — DetailShell, two-pane workspace, goal tree (UX improvements)\n\
  \nThree structural UX improvements from the UI/UX review that address the biggest\n\
  usability gaps in the task/feature workflow and the goal hierarchy view.\n\n**1.\
  \ DetailShell (§3.10c):** Unifies task Detail.tsx and FeatureDetail.tsx into one\n\
  `DetailShell` component with a swappable footer slot. Currently both re-implement\
  \ the\nsame header, skeleton, badge map, and waiting bar — a full parallel implementation.\n\
  - `DetailShell.tsx`: shared shell — status+type badge header, id/key, title, markdown\n\
  \  Brief, amber waiting bar (WAITING state), edit mode toggle, loading skeleton.\n\
  \  Footer slot: `task` variant renders the agent tabs + ConversationStream + chat\
  \ input;\n  `feature` variant renders the Decompose action + RelationshipList.\n\
  - Refactor Detail.tsx and FeatureDetail.tsx to use DetailShell with their respective\n\
  \  footers.\n- Delete FeatureDetailSkeleton, FEATURE_STATE_BADGE map, the parallel\
  \ type map.\n\n**2. Two-pane workspace (§3.10d):** Splits the task Detail view into\
  \ two independently\nscrolling panes — Context (brief + metadata + relationships)\
  \ | Conversation (transcript).\n- Left pane: Brief, metadata (state/type/priority/model\
  \ badges), depends_on list,\n  files, memory context — static, doesn't scroll away\
  \ during a long agent run.\n- Right pane: ConversationStream — scrolls independently.\n\
  - Pinned \"NOW running\" card: when a task is ACTIVE, a sticky card at the top of\
  \ the\n  right pane shows: current tool name, target file/path, model, subagent\
  \ name, elapsed\n  time, step count, token count. Uses the animated brand `active`\
  \ mark from\n  `docs/ui-ux-review/brand/states/cronos-state-active-animated.svg`.\n\
  - Mobile: collapses to `Context | Conversation` tab switch (the two-pane stays on\
  \ ≥768px).\n\n**3. Goal tree connector guides (§3.10b):** Adds visual connector\
  \ guides and a DAG toggle\nto TreePage.tsx / TreeNode.tsx.\n- Hairline vertical\
  \ connector lines between parent and child nodes in the tree.\n- Compact goal/subgoal/leaf\
  \ rows (instead of full board Cards) to reduce tree height.\n- Tree ⇄ Dependency-DAG\
  \ toggle button in the page header — switches between the tree\n  view and the existing\
  \ GoalDependencyGraph (dagre) view without leaving the page.\n\n**Exit criteria:**\
  \ DetailShell used by both Detail and FeatureDetail; FeatureDetail's\nparallel header/skeleton\
  \ removed; two-pane visible in task Detail ≥768px; tree has\nconnector guides and\
  \ DAG toggle; `npm run build` + `npm test` green.\n\nScope: frontend/src/components/ui/DetailShell.tsx,\
  \ frontend/src/pages/Detail.tsx, frontend/src/pages/FeatureDetail.tsx, frontend/src/pages/TreePage.tsx,\
  \ frontend/src/components/TreeNode.tsx"
has_ui: true
coverage_summary:
  searched:
  - frontend/src/components/
  - frontend/src/components/ui/
  - frontend/src/pages/
  - .cronos/pipeline/gui-detail-ux/
  excluded:
  - 'backend/: frontend-only feature, no backend changes required'
  - 'node_modules/: dependency snapshots'
  - 'frontend/src/__tests__/: implementation detail, read by scout'
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: A new DetailShell component exists at frontend/src/components/ui/DetailShell.tsx
    and renders a shared shell comprising a status+type badge header, entity id/key,
    title, markdown Brief, amber waiting bar (WAITING state), edit mode toggle, loading
    skeleton, and an injectable footer slot.
  acceptance_criteria:
  - Given DetailShell is rendered with isLoading=true, a skeleton placeholder is shown
    and no entity content is visible.
  - Given a task entity in WAITING state, the amber waiting bar is visible inside
    the shell.
  - Given a footer ReactNode is passed, it is rendered below the shared header/brief
    section.
  - DetailShell accepts a variant prop ('task' | 'feature') that alters the badge
    rendering but not the shell layout.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R2
  statement: Detail.tsx is refactored to use DetailShell for its header, skeleton,
    and waiting bar, passing a task-variant footer that contains the existing agent
    tabs, ConversationStream, chat input, HierarchySection, StatsPanel, TracePanel,
    and FilesPanel.
  acceptance_criteria:
  - Detail.tsx no longer contains an inline loading skeleton implementation; isLoading
    is delegated to DetailShell.
  - All task-specific action elements (start/stop/promote, chat input, conversation
    tabs) are present in the rendered output of Detail when mounted with a valid task.
  - Existing Detail vitest tests pass without modifications to test assertions about
    header/skeleton rendering.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R3
  statement: FeatureDetail.tsx is refactored to use DetailShell for its header, skeleton,
    and waiting bar, passing a feature-variant footer that contains the Decompose
    action, RelationshipList, edit mode form, and issue link.
  acceptance_criteria:
  - FeatureDetail.tsx no longer contains an inline FeatureDetailSkeleton component
    definition.
  - The FEATURE_STATE_BADGE constant is removed from FeatureDetail.tsx.
  - The feature-specific parallel type map (inline badge map) is removed from FeatureDetail.tsx.
  - All feature-specific actions (Decompose, realize, issue link) remain accessible
    after refactor.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R4
  statement: The FeatureDetailSkeleton component and the FEATURE_STATE_BADGE constant
    are deleted from the codebase; DetailShell's shared skeleton and badge map serve
    both variants.
  acceptance_criteria:
  - A grep for 'FeatureDetailSkeleton' across frontend/src/ returns zero matches.
  - A grep for 'FEATURE_STATE_BADGE' across frontend/src/ returns zero matches.
  - npm run build completes without import errors related to these deleted symbols.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R5
  statement: 'The task Detail view renders a two-pane layout at viewport widths >=768px:
    a left Context pane (Brief, metadata badges, depends_on list, files, memory context)
    and a right Conversation pane (ConversationStream, ChatInput), each with independent
    overflow-y-auto scroll.'
  acceptance_criteria:
  - Given a viewport >=768px, the Detail component renders two sibling pane containers
    with md:flex-row or equivalent responsive class.
  - The left pane contains Brief content and metadata badges; the right pane contains
    ConversationStream.
  - Both panes have overflow-y-auto applied so each scrolls independently without
    affecting the other.
  verifying_phase: test
  confidence: 0.87
- requirement_id: R6
  statement: Below 768px (mobile), the task Detail two-pane layout collapses to a
    Context | Conversation tab switch that shows one pane at a time.
  acceptance_criteria:
  - Given a viewport <768px, a tab bar with 'Context' and 'Conversation' labels is
    visible.
  - Clicking the 'Context' tab shows the left pane content and hides the right pane.
  - Clicking the 'Conversation' tab shows the right pane content and hides the left
    pane.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R7
  statement: When a task is in ACTIVE state, a sticky 'NOW running' card is pinned
    at the top of the right Conversation pane, displaying current tool name, target
    file/path, model, subagent name, elapsed time, step count, and token count, using
    the animated cronos-state-active-animated.svg brand asset as its visual marker.
  acceptance_criteria:
  - Given task.state === 'active', the NOW running card is rendered inside the right
    pane with position sticky or equivalent CSS.
  - 'The card displays at minimum: tool name, file/path, model, subagent name, elapsed
    time, step count, token count sourced from the existing useLiveStream hook or
    equivalent.'
  - The animated SVG asset (cronos-state-active-animated.svg) is rendered within the
    NOW running card as an img or inline SVG.
  - Given task.state !== 'active', the NOW running card is not rendered.
  verifying_phase: test
  confidence: 0.82
- requirement_id: R8
  statement: TreeNode.tsx renders hairline vertical connector lines between a parent
    node and its visible child nodes, aligned to the tree indentation depth.
  acceptance_criteria:
  - Given a goal node with visible (expanded) children, a vertical connector line
    is rendered between the parent and the first child, continuing through all siblings.
  - Connector lines are depth-relative and align with the tree indentation CSS variable
    or Tailwind equivalent.
  - Collapsed subtrees do not show connector lines for their hidden children.
  verifying_phase: test
  confidence: 0.83
- requirement_id: R9
  statement: TreeNode.tsx renders compact row items (not full board Cards) for goal/subgoal/leaf
    entries in the tree, reducing visual height per node.
  acceptance_criteria:
  - Tree nodes no longer use the Card component with density='tight'; they use a compact
    row component showing state badge, title, and minimal status indicators.
  - npm run build succeeds with no references to the old Card density='tight' pattern
    in TreeNode.tsx.
  - Vitest tests for the tree that previously asserted on Card markup are updated
    to match the new compact row structure.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R10
  statement: TreePage.tsx or TreeView.tsx includes a toggle button in the page header
    that switches the view between the hierarchical TreeView and the existing GoalDependencyGraph
    (dagre) visualization without navigating away from the page.
  acceptance_criteria:
  - A toggle button labeled 'Tree' / 'DAG' or equivalent is visible in the tree page
    header.
  - Clicking the toggle switches the rendered view between TreeView and GoalDependencyGraph
    components.
  - Toggle state is local (useState); switching away from tree and back preserves
    tree expand/collapse state.
  - GoalDependencyGraph receives the required props (goal, children, onOpenTask, runningIds)
    when rendered.
  verifying_phase: test
  confidence: 0.87
metrics:
  tool_calls: 5
  files_read: 11
  memory_hits: 2
---

## Summary

This feature delivers three structural frontend UX improvements to Cronos: (1) a new shared `DetailShell` component at `frontend/src/components/ui/DetailShell.tsx` that unifies the parallel header, skeleton, and waiting-bar logic currently duplicated across `Detail.tsx` and `FeatureDetail.tsx`, with a swappable footer slot for variant-specific content; (2) a two-pane workspace layout for task Detail that separates Context (brief, metadata, relationships) from Conversation (transcript, chat) into independently scrolling columns at >=768px, with a pinned "NOW running" card for ACTIVE tasks and a tab collapse for mobile; (3) hairline vertical connector lines and a Tree/DAG toggle button added to the goal tree view. All changes are frontend-only across five existing files and one new component.

## Scope

### In scope
- `frontend/src/components/ui/DetailShell.tsx` — new shared shell component (header, skeleton, waiting bar, badge maps, edit mode toggle, footer slot)
- `frontend/src/components/Detail.tsx` — refactored to use DetailShell with a task-variant footer
- `frontend/src/components/FeatureDetail.tsx` — refactored to use DetailShell with a feature-variant footer; FeatureDetailSkeleton and FEATURE_STATE_BADGE deleted
- `frontend/src/components/TreeNode.tsx` — compact row rendering (replaces Card) and hairline connector lines
- `frontend/src/pages/TreePage.tsx` and/or `frontend/src/components/TreeView.tsx` — Tree/DAG toggle button
- Existing vitest tests for affected components updated to match new structure

### Out of scope
- `backend/`: no backend changes required; all data contracts are in place
- `frontend/src/components/GoalDependencyGraph.tsx`: reused without modification for the DAG toggle
- Route definitions and file locations: Detail.tsx and FeatureDetail.tsx stay at current import paths
- New API endpoints or data model changes

### Deferred
- Reusable animated SVG component wrapper for `cronos-state-active-animated.svg` beyond the NOW running card
- Virtualized connector-line rendering for very deep/wide goal trees (performance optimization)
- Full visual regression test suite for two-pane layout beyond unit-level vitest assertions
- URL-persisted Tree/DAG toggle state (ephemeral useState is the MVP)

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | DetailShell renders shared header, skeleton, waiting bar, and injectable footer slot |
| R2 | Detail.tsx uses DetailShell for header/skeleton, passing task-variant footer |
| R3 | FeatureDetail.tsx uses DetailShell for header/skeleton, passing feature-variant footer |
| R4 | FeatureDetailSkeleton and FEATURE_STATE_BADGE are deleted from the codebase |
| R5 | Task Detail renders two-pane layout (Context left, Conversation right) at >=768px with independent scroll |
| R6 | Below 768px, task Detail two-pane collapses to a Context / Conversation tab switch |
| R7 | ACTIVE tasks show a sticky NOW running card in the Conversation pane |
| R8 | TreeNode renders hairline vertical connector lines between parent and visible children |
| R9 | TreeNode renders compact row items instead of full board Cards |
| R10 | TreePage/TreeView has a Tree / DAG toggle button switching between hierarchical tree and GoalDependencyGraph |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]`
array (the machine-readable source of truth). The body summary below mirrors them
in compact form for the human reader.

- R1 — skeleton on isLoading; amber bar on WAITING state; footer slot rendered; variant prop accepted
- R2 — Detail delegates skeleton to DetailShell; all task actions remain; existing tests pass
- R3 — FeatureDetail delegates skeleton to DetailShell; FeatureDetailSkeleton removed; feature actions remain
- R4 — Zero grep matches for FeatureDetailSkeleton and FEATURE_STATE_BADGE; build clean
- R5 — Two sibling pane containers at >=768px; both overflow-y-auto; left=Context, right=Conversation
- R6 — Tab bar with Context/Conversation labels at <768px; each tab shows one pane, hides the other
- R7 — NOW running card sticky in right pane when active; shows tool/file/model/subagent/elapsed/steps/tokens; SVG rendered; absent when not active
- R8 — Vertical connector line between parent and visible expanded children; depth-aligned; absent for collapsed subtrees
- R9 — TreeNode uses compact row not Card density=tight; build clean; affected tests updated
- R10 — Toggle button in tree header; switches TreeView/GoalDependencyGraph; local state; tree expand/collapse preserved; DAG receives required props

## Traceability

The full requirement to acceptance criteria to verifying_phase map is the YAML
`traceability[]` array. Downstream agents read the YAML directly; this section
exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | DetailShell renders shared header, skeleton, waiting bar, and injectable footer slot |
| R2 | test | Detail.tsx is refactored to use DetailShell for its header, skeleton, and waiting bar |
| R3 | test | FeatureDetail.tsx is refactored to use DetailShell for its header, skeleton, and waiting bar |
| R4 | test | FeatureDetailSkeleton and FEATURE_STATE_BADGE are deleted from the codebase |
| R5 | test | Task Detail renders a two-pane layout at >=768px with independent scroll |
| R6 | test | Below 768px, task Detail collapses to a Context / Conversation tab switch |
| R7 | test | ACTIVE tasks show a sticky NOW running card in the Conversation pane |
| R8 | test | TreeNode renders hairline vertical connector lines between parent and visible children |
| R9 | test | TreeNode renders compact row items instead of full board Cards |
| R10 | test | TreePage/TreeView has a Tree / DAG toggle button |

## Assumptions

- `has_ui: true` rationale: all requirements are frontend component changes; no backend work is in scope.
- The two-pane responsive breakpoint maps to Tailwind `md:` (768px) as stated explicitly in the request (">=768px"); the scout noted an ambiguity with `lg:` (1024px) but the request text is authoritative. The design agent should confirm this against existing Detail.tsx lg: usage.
- DetailShell uses a `footer` prop (ReactNode) for the swappable slot, consistent with the Modal component's child-rendering pattern already used by both Detail and FeatureDetail.
- GoalDependencyGraph.tsx is reused without modification for the DAG toggle; the scout confirmed it exists and its required props (goal, children, onOpenTask, runningIds) are known.
- Tree connector lines render via CSS borders or SVG on parent container elements; the design agent selects the exact implementation approach.
- "Compact rows" in the tree replaces the full Card component with a lightweight TreeNodeRow or equivalent showing state badge + title + minimal indicators.
- The NOW running card data is sourced from the existing `useLiveStream` hook confirmed by the scout; no new data-fetching infrastructure is required.
- The `cronos-state-active-animated.svg` file exists at `docs/ui-ux-review/brand/states/` per scout finding section 6; it is imported as img src or inline SVG without a new component wrapper.
- All requirements are verified by the `test` phase (vitest); no manual-only acceptance criteria exist.

## Open questions

- **Mobile breakpoint (md: vs lg:):** Request says ">=768px" (Tailwind `md:`); scout found Detail uses `lg:` in some places. Design agent should canonicalize the breakpoint for the two-pane split before implementation.
- **TreeNodeRow vs Card density='compact':** Design agent should decide whether to introduce a new TreeNodeRow component or extend Card with a new density prop — the choice determines how many existing test fixtures need updating.
- **Connector line animation on collapse:** Should connector lines animate in/out when a node is expanded/collapsed, or render only for currently visible (expanded) tree nodes? Performance vs visual polish tradeoff for the design agent.

## Next consumer brief

**Design agent** — read `traceability[]` (10 requirements, all `verifying_phase: test`) and `has_ui: true` first, then `## Scope` for boundaries.

Key decision points not derivable from this header:

1. **DetailShell footer slot API:** Confirm the ReactNode footer prop does not create TypeScript inference issues with variant-specific mutation hooks (task start/stop vs feature decompose). A typed discriminated union variant prop may be needed.
2. **Two-pane height constraint:** Both panes need a bounded height for overflow-y-auto to activate. Detail.tsx wraps in Modal — identify the CSS height constraint (h-full, max-h-screen, or explicit vh) inside the Modal that enables independent scroll without viewport overflow.
3. **NOW running card data wiring:** Confirm exact fields available from `useLiveStream` (tool_name, file_path, model, subagent_name, elapsed_seconds, step_count, token_count) and flag any that are missing from the current payload.
4. **TreeNode compact row definition:** Define the exact markup for the compact row — state badge color mapping, title truncation limit, drag handle position, GapZone interaction — to make the implementation iteration unambiguous.
5. **Test update scope:** Enumerate which existing test files (Detail.test.tsx, FeatureDetail.test.tsx, TreeNode.test.tsx) need selector updates vs which can test new components in isolation — this bounds the implementation iteration count (suggest 4-5 iterations).
