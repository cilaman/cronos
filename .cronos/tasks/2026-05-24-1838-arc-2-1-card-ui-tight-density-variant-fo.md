---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-24-1838-arc-2-1-card-ui-tight-density-variant-fo
manual_order: 1
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-2/1: Card UI — tight density variant for Tree view'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Add a `density="tight"` variant to the Card component for use in the Tree view, targeting ≥6 cards visible on a phone screen without scrolling.

## Changes
1. `frontend/src/components/Card.tsx` — accept `density` prop (`"default" | "compact" | "tight"`). In `"tight"`: single-line title with ellipsis; inline row beneath with state dot, priority dot, age stamp, and Arc 1 badges; padding ~½ of default; height target ~36–44px. Tap target remains ≥44px.
2. Add `data-density` attribute on the Card root.
3. Do NOT change the existing default or compact rendering.

## Acceptance
- Existing Board tests pass unchanged. Card with `density="tight"` shows one-line title and badge row only; brief preview is absent. ≥6 cards fit in 640px viewport height. `data-density="tight"` attribute is on the root.


Branch: `feature/arc-2-tree-view`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-2:`.

# History
