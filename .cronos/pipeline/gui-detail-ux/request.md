GUI detail UX — DetailShell, two-pane workspace, goal tree (UX improvements)

Three structural UX improvements from the UI/UX review that address the biggest
usability gaps in the task/feature workflow and the goal hierarchy view.

**1. DetailShell (§3.10c):** Unifies task Detail.tsx and FeatureDetail.tsx into one
`DetailShell` component with a swappable footer slot. Currently both re-implement the
same header, skeleton, badge map, and waiting bar — a full parallel implementation.
- `DetailShell.tsx`: shared shell — status+type badge header, id/key, title, markdown
  Brief, amber waiting bar (WAITING state), edit mode toggle, loading skeleton.
  Footer slot: `task` variant renders the agent tabs + ConversationStream + chat input;
  `feature` variant renders the Decompose action + RelationshipList.
- Refactor Detail.tsx and FeatureDetail.tsx to use DetailShell with their respective
  footers.
- Delete FeatureDetailSkeleton, FEATURE_STATE_BADGE map, the parallel type map.

**2. Two-pane workspace (§3.10d):** Splits the task Detail view into two independently
scrolling panes — Context (brief + metadata + relationships) | Conversation (transcript).
- Left pane: Brief, metadata (state/type/priority/model badges), depends_on list,
  files, memory context — static, doesn't scroll away during a long agent run.
- Right pane: ConversationStream — scrolls independently.
- Pinned "NOW running" card: when a task is ACTIVE, a sticky card at the top of the
  right pane shows: current tool name, target file/path, model, subagent name, elapsed
  time, step count, token count. Uses the animated brand `active` mark from
  `docs/ui-ux-review/brand/states/cronos-state-active-animated.svg`.
- Mobile: collapses to `Context | Conversation` tab switch (the two-pane stays on ≥768px).

**3. Goal tree connector guides (§3.10b):** Adds visual connector guides and a DAG toggle
to TreePage.tsx / TreeNode.tsx.
- Hairline vertical connector lines between parent and child nodes in the tree.
- Compact goal/subgoal/leaf rows (instead of full board Cards) to reduce tree height.
- Tree ⇄ Dependency-DAG toggle button in the page header — switches between the tree
  view and the existing GoalDependencyGraph (dagre) view without leaving the page.

**Exit criteria:** DetailShell used by both Detail and FeatureDetail; FeatureDetail's
parallel header/skeleton removed; two-pane visible in task Detail ≥768px; tree has
connector guides and DAG toggle; `npm run build` + `npm test` green.

Scope: frontend/src/components/ui/DetailShell.tsx, frontend/src/pages/Detail.tsx, frontend/src/pages/FeatureDetail.tsx, frontend/src/pages/TreePage.tsx, frontend/src/components/TreeNode.tsx
