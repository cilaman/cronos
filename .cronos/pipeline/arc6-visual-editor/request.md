Build the editor. Add the `reactflow` npm dep (keep it isolated from the existing
`@dagrejs/dagre` SVG graph in GoalDependencyGraph.tsx). Use `frontend-design` skill for a
Cronos paper/ink palette: quiet canvas, ink-line edges (no glow/gradients), nodes = the
**Card** style, smaller, with sockets.

- New `frontend/src/pages/HarnessEditor.tsx` + `frontend/src/components/harness/` (node
  components for all 5 types, typed sockets/edges, palette, variable-binding inspector).
- Save/load round-trips to YAML via the 6.1 CRUD API; TanStack keys
  `["harnesses", spaceId]` / `["harness", spaceId, name]`.
- Extend types.ts with `Harness`/`HarnessNode`/`HarnessEdge`.
- **Add a route + Sidebar nav entry** (router.tsx / Sidebar.tsx — currently absent) so the
  editor is reachable.

Acceptance: author a 3-node harness on the canvas, wire edges, set an Agent node's
`agent_ref` + prompt, save, reload → persists and re-renders; an invalid graph surfaces
the backend 422.

