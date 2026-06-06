---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-04T10:39:23Z'
depends_on: []
id: 2026-06-04-1039-harnesses-page-top-level-nav-landing-pag
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: 'Harnesses page: top-level nav + landing page'
type: goal
updated_at: '2026-06-04T11:33:41Z'
waiting_question: null
---

# Brief

Add a top-level Harnesses page to the Cronos left sidebar so that harnesses are always accessible from the nav, regardless of whether a space is currently selected.

## Motivation

Arc 6 delivered the full harness infrastructure (CRUD API, executor, visual editor, run history, SSE overlay) but the only entry point is space-specific: `/spaces/:spaceId/harnesses`. This means:
- The Harnesses nav link only shows when a space is active
- There is no global harnesses entry point in the sidebar

## Goal

Make Harnesses a first-class top-level nav item:
1. Sidebar always shows "Harnesses" link (not gated on spaceId)
2. Link goes to `/harnesses` — a top-level page showing all spaces and their harnesses
3. The page includes a space selector, harness list, and quick-access buttons to the editor and runs views

## Sub-goals

1. **Harnesses landing page + sidebar nav** — frontend-only: new HarnessesPage, router updates, sidebar updates
2. **Tests + merge to main** — run tests, verify coverage, merge feature branch to main

# History

```
2026-06-04T10:42:50Z [agent]
Paused: Sub-goal 'Harnesses landing page + sidebar nav' ended in waiting state. Completed 0, skipped 0 already-done.
```

```
2026-06-04T10:46:55Z [agent]
Paused: Child 'Harnesses landing page + sidebar nav' is in waiting state and needs attention. Completed 0, skipped 0 already-done.
```

```
2026-06-04T10:52:05Z [agent]
Paused: Child 'Harnesses landing page + sidebar nav' is in waiting state and needs attention. Completed 0, skipped 0 already-done.
```

```
2026-06-04T10:52:29Z [agent]
Paused: Sub-goal 'Harnesses landing page + sidebar nav' ended in waiting state. Completed 0, skipped 0 already-done.
```

```
2026-06-04T11:33:41Z [agent]
All tasks complete. Completed 1, skipped 2 already-done.
```
