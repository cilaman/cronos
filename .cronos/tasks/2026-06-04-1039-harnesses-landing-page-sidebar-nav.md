---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-04T10:39:23Z'
depends_on: []
id: 2026-06-04-1039-harnesses-landing-page-sidebar-nav
manual_order: 0
parent_id: 2026-06-04-1039-harnesses-page-top-level-nav-landing-pag
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: Harnesses landing page + sidebar nav
type: goal
updated_at: '2026-06-04T11:17:49Z'
waiting_question: null
---

# Brief

Frontend-only feature slice.

Add a top-level `/harnesses` route with a space-picker landing page, and make the Harnesses sidebar link always visible.

Files in scope:
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/router.tsx`
- new `frontend/src/pages/HarnessesPage.tsx`
- `frontend/src/pages/__tests__/` (tests)

# History

```
2026-06-04T10:42:50Z [agent]
Paused: Cannot start task: unmet dependencies: 2026-06-04-1039-scout-harnesses-page Completed 0, skipped 0 already-done.
```

```
2026-06-04T10:51:58Z [agent]
Stopped. Completed 0, skipped 0 already-done.
```

```
2026-06-04T10:52:29Z [agent]
Paused: Child 'analyst – harnesses-page' is in waiting state and needs attention. Completed 0, skipped 0 already-done.
```

```
2026-06-04T11:17:49Z [agent]
All tasks complete. Completed 4, skipped 1 already-done.
```
