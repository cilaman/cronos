---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T09:08:41Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-03-0908-arc-5-b-adoption-vendor-mount-merge-upst
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'Arc 5/B — Adoption: vendor + mount + merge upstream'
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

Adopt a discovered item: copy file/skill-dir to `{space}/.cronos/tools/<kind>/<name>/`; write `manifest.yml` (`source_url, source_slug, source_path, source_sha, adopted_at, base_sha, local_sha, evolved, kind, name`). Mount adopted dirs into agent runs via extra `--add-dir`. On refresh: advance + locally edited → auto-create 3-way merge task; pristine + advance → silent auto-upgrade.

| # | Task | depends_on |
|---|------|-----------|
| B1 | adoption module + manifest + watcher | [A3] |
| B2 | API: adopt / unadopt / list adopted | [B1] |
| B3 | mount adopted tools into agent runs | [B1] |
| B4 | upstream-advance + 3-way merge task | [A4, B1] |
| B5 | Frontend: Adopt button + Adopted view | [B2] |

**First child (B1) depends on Goal A / Task A3 being DONE.**

# History

```
2026-06-03T13:48:25Z [agent]
All tasks complete. Completed 5, skipped 0 already-done.
```
