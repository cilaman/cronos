---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-25-1342-arc-9-5-dependency-dag-visualization-in
manual_order: 5
parent_id: 2026-05-25-1341-arc-9-goal-processing-ux-sync
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-9/5: Dependency DAG visualization in goal detail'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Add a dependency graph visualization to the goal detail panel.

## Changes
1. Install `@dagrejs/dagre@^1.1.5`.
2. New `GoalDependencyGraph.tsx` — SVG DAG of children + `depends_on` edges. Node size 180×56. Edge colors: ink-faint (default/backlog), amber (WAITING), ink (DONE).
3. Render in the Detail panel for goals. Mobile fallback: flat indented list.
4. Node click → open that task's Detail.


Branch: `feature/arc-9-goal-ux`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-9:`.

# History
