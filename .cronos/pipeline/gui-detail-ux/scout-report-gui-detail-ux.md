---
cc_version: "1.0"
agent: pipeline-scout
slug: gui-detail-ux
phase: scout
status: done
confidence: 0.88
inputs_used:
  - memory:project_gui_refactor_board_setup
  - memory:project_gui_tokens_brand_review_attempt1
  - frontend/src/components/Detail.tsx
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/pages/TreePage.tsx
  - frontend/src/components/TreeView.tsx
  - frontend/src/components/TreeNode.tsx
  - frontend/src/components/GoalDependencyGraph.tsx
  - frontend/src/components/ConversationStream.tsx
  - frontend/src/components/ui/Modal.tsx
  - .cronos/pipeline/gui-detail-ux/request.md
outputs_produced:
  - .cronos/pipeline/gui-detail-ux/scout-report-gui-detail-ux.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - frontend/src/components/
    - frontend/src/pages/
    - frontend/src/components/ui/
    - docs/ui-ux-review/
  excluded:
    - backend/: not relevant to this frontend-only refactor
    - tests/: implementation detail
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "GUI detail UX — DetailShell, two-pane workspace, goal tree (UX improvements)"
metrics:
  tool_calls: 22
  files_read: 10
  memory_hits: 2
---

## Summary

The gui-detail-ux subgoal requires three major frontend UX refactors: (1) unifying Detail.tsx and FeatureDetail.tsx into a reusable DetailShell component with swappable footer slots, eliminating 140+ lines of duplicated header/skeleton/badge logic; (2) splitting task Detail into independently scrolling left (Context) and right (Conversation) panes with a sticky "NOW running" card for ACTIVE state, collapsing to tabs on mobile <768px; (3) adding vertical connector lines and a DAG toggle to the goal tree to improve hierarchy visualization. Current state: Detail (~1189 lines), FeatureDetail (~372 lines), TreeNode renders Card children in a tree with no connectors, GoalDependencyGraph (dagre) exists as a separate visualization. Existing ui/ component library (Modal, Button, IconButton) provides foundation; Modal is the wrapper for both detail panels.

## Coverage

### Searched
- frontend/src/components/ — Detail.tsx (1189 lines), FeatureDetail.tsx (372 lines), TreeNode.tsx (199 lines), ConversationStream.tsx, GoalDependencyGraph.tsx
- frontend/src/components/ui/ — Modal, Button, IconButton, formfield patterns
- frontend/src/pages/ — TreePage (6 lines wrapper), TreeView (116 lines, tree orchestration)
- docs/ui-ux-review/ — brand assets (cronos-state-active-animated.svg)

### Excluded
- backend/: no backend changes needed
- test files: implementation detail
- node_modules: dependency snapshots

### Strategies
- memory_retrieval: 2 hits (gui-refactor board context, tokens/brand system)
- glob_structural: identified all scope files (Detail, FeatureDetail, TreePage, TreeNode, ui/)
- grep_symbol: confirmed no pre-existing DetailShell or two-pane layout
- read_targeted: full reads of Detail.tsx, FeatureDetail.tsx, TreeNode.tsx to assess duplication and structure

## Findings

### 1. DetailShell Unification Scope (§3.10c)

**Parallel header implementation** (Detail.tsx:926–1016 vs FeatureDetail.tsx:132–180):
- Both render status badge using state_to_badge maps (STATE_BADGE in Detail, FEATURE_STATE_BADGE in FeatureDetail)
- Both render ID/key badges, title, and close button
- Detail wraps in Modal; FeatureDetail wraps in Modal
- Detail includes priority/mode/model selectors in header; FeatureDetail has simpler header
- Both have matching EditButton/EditMode toggle patterns (Detail:1029, FeatureDetail:163)

**Duplicate skeletons:**
- DetailSkeleton (Detail.tsx:797–811): 6 skeleton lines, generic gray box pattern
- FeatureDetailSkeleton (FeatureDetail.tsx:21–35): identical structure (6 lines, same pattern)
- Both respond to isLoading state

**Footer content divergence:**
- Detail footer (lines 1069–1157): tabs (details/stats/trace/files), ConversationStream, ChatInput, HierarchySection, StatsPanel, TracePanel, FilesPanel (right sidebar on lg+)
- FeatureDetail footer (lines 182–366): edit mode, Brief section, waiting bar, Decompose action, RelationshipList, issue link

**Badge maps to consolidate:**
- STATE_BADGE (task states): used across Detail header
- FEATURE_STATE_BADGE (feature states): FeatureDetail only
- TYPE_BADGE_STYLES (task.type): Detail.tsx line 349–364
- Feature type badge (inline in FeatureDetail line 146–151)

**Key structure for DetailShell:**
```
<DetailShell 
  entity={task|feature}
  isLoading={bool}
  error={Error|null}
  onClose={fn}
  variant="task"|"feature"
  footer={ReactNode}
/>
```

### 2. Two-Pane Layout (§3.10d)

**Current Detail layout** (Detail.tsx:1069–1141):
- Single flex container: left column (flex-1) + FilesPanel (right sidebar hidden on mobile)
- Conversation and Brief in the same scrollable left pane
- No visual separation or independent scroll bounds

**Two-pane architecture:**
- **Left pane (Context):** Brief (section), metadata (state/priority/model badges), depends_on list, files, memory context—all in a flex-col with overflow-y-auto, max-height constrained on md+
- **Right pane (Conversation):** ConversationStream (already component), ChatInput, with independent overflow-y-auto
- **Breakpoint:** lg:flex-row (≥1024px desktop) vs flex-col with tab switch (<1024px, mobile shows Context | Conversation tabs)
- **Sticky "NOW running" card:** rendered at top of right pane when task.state === "active"; uses animated SVG from docs/ui-ux-review/brand/states/cronos-state-active-animated.svg; shows tool name, file/path, model, subagent, elapsed time, step count, token count

**Candidate hook/state integration:**
- useLiveStream (from hooks/useLiveStream.tsx) provides LiveStatus, StreamEntry, and subagent/tool info
- task.state === "active" triggers card visibility
- ConversationStream already consumes task prop with live streaming data

### 3. Goal Tree Connector Guides (§3.10b)

**Current TreeNode structure** (TreeNode.tsx:47–198):
- Uses dnd-kit for drag-drop reordering (active/over context)
- Renders Card child component (full board-style card in tree context)
- GapZone for sibling-insertion targets
- Chevron toggle button for expand/collapse (lines 124–153)
- No visual connectors between parent and children

**Connector line requirements:**
- **Vertical hairlines:** SVG or CSS lines between parent and first-child, continuing through all siblings, then down to parent-of-next-sibling
- **Depth-relative positioning:** lines must align with tree indentation (--tree-indent CSS var, default 1.25rem)
- **Rendering placement:** SVG backdrop (z-0) behind the tree, or CSS pseudo-elements on parent nodes

**DAG toggle:**
- TreeToolbar component (lines 83–96 in TreeView.tsx) already has sortMode toggle button pattern
- Add button to toggle between tree view (current) and GoalDependencyGraph (dagre) view
- GoalDependencyGraph.tsx lines 1–50 show it requires goal, children[], onOpenTask, runningIds props
- State: useState(viewMode: "tree" | "dag"), conditional render TreeView vs GoalDependencyGraph

**Card density optimization:**
- Current: TreeNode renders Card with density="tight" (line 174)
- Brief req: "compact goal/subgoal/leaf rows (instead of full board Cards)"
- Action: introduce density="compact" variant or new TreeNodeRow component with minimal styling (just state badge + title + indicators)

### 4. TypeScript / UI Library Context

**Existing type patterns:**
- Task, TaskSummary, FeatureState, Feature types from frontend/src/types.ts (re-export from generated api-types.ts)
- Modal component (ui/Modal.tsx): wraps with backdrop, onClose callback, className support
- Button/IconButton components for standard action buttons
- STATE_BADGE, PRIORITY_BADGE_STYLES patterns already established (Detail.tsx lines 70–77, 280–286)

**Testing patterns:**
- Detail.test.tsx exists (27 test files total in __tests__/)
- Should cover: DetailShell load states, footer slot rendering, task vs feature variants
- Two-pane: tab switching on mobile, independent scroll behavior
- Tree: connector render (visual regression), DAG toggle state, card density

### 5. Scope Clarification

**Clarified paths (from request.md line 39):**
- ✓ frontend/src/components/ui/DetailShell.tsx — **new file** (currently missing)
- ✓ frontend/src/pages/Detail.tsx — **refactor** (move to components, use DetailShell)
- ✓ frontend/src/pages/FeatureDetail.tsx — **refactor** (move to components, use DetailShell)
- Note: request.md line 39 says "frontend/src/pages/" but Detail.tsx is at components/; likely copy-paste from page structure. Implementation should refactor existing component files.
- ✓ frontend/src/pages/TreePage.tsx — **minor update** (add DAG toggle in header)
- ✓ frontend/src/components/TreeNode.tsx — **refactor** (add connectors, update Card density)

### 6. Animated Brand Asset

**cronos-state-active-animated.svg** (docs/ui-ux-review/brand/states/):
- Used for sticky "NOW running" card header pulse
- File exists at path; no component wrapper found yet
- Need to import and render as inline SVG or img with animation CSS

## Assumptions

- DetailShell will be a controlled component accepting variant="task"|"feature" and footer slot children, not a render-prop pattern—matches existing UI component style (Modal pattern).
- Two-pane layout uses CSS Grid (lg:grid-cols-2) or Flex (lg:flex-row) with independent overflow-y-auto children, not complex viewport-height calculations—simplifies mobile collapse.
- Tree connectors render via SVG overlay (new TreeConnectors component) or CSS borders, not inline pseudo-elements on every node—single z-0 layer reduces DOM churn.
- Existing GoalDependencyGraph component is reusable as-is for DAG toggle view; no modifications needed there.
- Mobile breakpoint "≥768px" maps to Tailwind `md:` prefix (768px), not `lg:` (1024px); confirm with design intent.
- Tests use vitest (frontend/src/.vitest.config or npm test runs vitest), not jest; follow existing test patterns (Detail.test.tsx).

## Open questions

- **Mobile breakpoint precision:** Request says "≥768px" but Tailwind standard is md:768px, lg:1024px. Should two-pane visible at md: or only lg:?
- **TreeNode Card density:** Should "compact" variant remove entire Card component and use minimal inline row (just badge + title + icon)? Or keep Card with tighter padding/font?
- **Tree connector SVG scope:** Should lines render only between visible (expanded) parent/children, or all nodes (including collapsed subtrees)? Performance-wise, visible-only is simpler.

## Next consumer brief

**Analysis agent:** Evaluate these requirements for feasibility and dependencies:

1. **DetailShell component design:** Confirm the footer slot pattern unifies both Detail and FeatureDetail without breaking task-specific actions (start/stop/promote, decompose/realize).
2. **Two-pane tab switching on mobile:** Verify the breakpoint (md: vs lg:) and test that context pane doesn't scroll away during long conversation streams.
3. **Tree connectors visual:** Confirm whether connector lines should be static SVG or CSS, and clarify the "compact rows" goal (full Card vs minimal row).
4. **DAG toggle integration:** Ensure GoalDependencyGraph re-mounts cleanly when toggled and doesn't break the existing tree expand/collapse state.
5. **Breaking changes:** Check if refactoring Detail.tsx or FeatureDetail.tsx location (from pages/ to components/) impacts any route definitions or imports elsewhere.
6. **Test coverage:** Identify which existing tests (Detail.test.tsx, FeatureDetail.test.tsx) need updating for new component structure and tab/pane switching.

Recommend analysis agent focus on: (1) Header badge unification rules (STATE_BADGE vs FEATURE_STATE_BADGE), (2) Footer slot design constraints (task-specific mutations vs feature-specific actions), (3) Mobile responsive collapse order (tabs first, then below-768px logic).
