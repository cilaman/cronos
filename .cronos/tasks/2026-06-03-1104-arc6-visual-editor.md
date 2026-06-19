---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T11:04:56Z'
depends_on:
- 2026-06-03-1104-arc6-event-triggers
feature_key: null
feature_state: null
id: 2026-06-03-1104-arc6-visual-editor
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-1104-arc-6-harnesses
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: arc6 visual editor
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Pipeline goal: 6.7 Visual harness editor React Flow

Pipeline run scaffolded by `/pipeline-scaffold`. Shared branch: `feature/arc-6-harnesses`.
Part of umbrella goal `arc-6-harnesses` (Arc 6 — Harnesses).

## Request

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


## Child tasks (one per CC-v1 phase)

1. scout    — pipeline-scout    (research)
2. analysis — pipeline-analyst  (analysis)
3. design   — pipeline-architect(design)
4. impl     — pipeline-implementor (implementation; may fan out per iteration)
5. test     — tester            (test)
6. review   — pipeline-reviewer (review; may loop on verdict=needs_fix)
7. doc      — pipeline-doc-sync (doc; commit-only — no merge to main)

Each phase task ends by invoking `/pipeline-gate` which closes the gate from
the artifact's YAML header — no prose parsing. The doc task commits via
`/goal-task-commit` (not /goal-finalize); the final merge happens in the Arc 6
integration task.

# History

```
2026-06-04T08:22:21Z [agent]
All tasks complete. Completed 7, skipped 0 already-done.
```
