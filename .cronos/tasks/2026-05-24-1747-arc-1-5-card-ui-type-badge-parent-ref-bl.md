---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-24-1746-arc-1-4-api-tree-promote-parent-depends
id: 2026-05-24-1747-arc-1-5-card-ui-type-badge-parent-ref-bl
manual_order: 5
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-1/5: Card UI — type badge, parent ref, blocked-by pill'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Make the new hierarchy visible on the Kanban Card.

## Changes
1. `frontend/src/components/Card.tsx` — render:
   - **Type badge**: small pill labelled `GOAL`/`ISSUE`. Tasks get no badge.
   - **Parent ref** (when `parent_id` is set): one-line breadcrumb showing the parent goal's title. Clicking opens the parent in Detail modal.
   - **"Blocked by N" pill** when `unmet_dependencies.length > 0`: warm-amber accent, tooltip lists blocker titles.
   - **"Blocks N" pill** showing the count of tasks depending on this one.
2. `frontend/src/types.ts` — extend Task type with `type`, `parent_id`, `depends_on`, `unmet_dependencies`.
3. Goals: slightly thicker top border (existing ink color token).

## Acceptance
- Goal shows GOAL pill + heavier top border. Task with `parent_id` shows breadcrumb. Task with two unmet deps shows `BLOCKED BY 2`. Plain tasks render identically to before.

## Standing rules
Branch: `feature/arc-1-hierarchy` from `main`. Do NOT merge to `main` — that's manual after the arc lands.
Test gate before commit: invoke the `test-architect` subagent. Only commit after green.
Commit message: `arc-1: <summary>`. STATUS: DONE on success, STATUS: BLOCKED if tests fail.

# History
