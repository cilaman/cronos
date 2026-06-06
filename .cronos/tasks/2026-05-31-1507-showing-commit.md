---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-31T15:07:52Z'
depends_on: []
id: 2026-05-31-1507-showing-commit
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: showing commit
type: goal
updated_at: '2026-06-01T11:53:03Z'
waiting_question: null
---

# Brief

# Pipeline goal: Show running commit and upgrade time in the sidebar

Pipeline run scaffolded by `/pipeline-scaffold`. Verbatim request is at
`.cronos/pipeline/{goal_slug}/request.md`; live state at
`.cronos/pipeline/{goal_slug}/pipeline-state.json`.

## Request

Show, in the GUI sidebar next to the CRONOS text in the top-left corner, the git commit that is currently running, so the operator can see at a glance whether the deployed app is in sync with current main.

It would also be valuable to show a timestamp of when the GUI and the backend were last upgraded.

Notes / acceptance:
- The running commit must reflect what is actually deployed (baked at build/upgrade time), not a value read from a working tree.
- Ideally the commit is comparable against origin/main (e.g. a short SHA, optionally linking to the commit on GitHub).
- Surface upgrade/build timestamps for both the frontend (GUI) and backend.
- The deployed app is rebuilt from origin/main by upgrade.sh, so any build-stamp wiring must flow through the upgrade + docker build path.

## Child tasks (one per CC-v1 phase)

1. scout    — pipeline-scout    (research)
2. analysis — pipeline-analyst  (analysis)
3. design   — pipeline-architect(design)
4. impl     — pipeline-implementor (implementation; may fan out per iteration)
5. test     — tester            (test)
6. review   — pipeline-reviewer (review; may loop on verdict=needs_fix)
7. doc      — pipeline-doc-sync (doc; terminal)

Each phase task ends by invoking `/pipeline-gate` which closes the gate from
the artifact's YAML header — no prose parsing.

# History

```
2026-05-31T16:09:53Z [agent]
Paused: Child 'pipeline-reviewer: Show running commit and upgrade time in the sidebar' ended in waiting state. Completed 4, skipped 1 already-done.
```

```
2026-06-01T11:53:03Z [agent]
All tasks complete. Completed 1, skipped 6 already-done.
```
