---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T09:08:41Z'
depends_on: []
id: 2026-06-03-0908-arc-5-a-discovery-tool-sources-yml-index
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: done
title: 'Arc 5/A — Discovery: tool_sources.yml + indexed scan'
type: goal
updated_at: '2026-06-03T12:18:54Z'
waiting_question: null
---

# Brief

Read-only discovery. Refresh shallow-clones enabled sources into `/data/.cronos/discovery_sources/<slug>/`, walks the four `.claude/` patterns, upserts SQLite `discovered_tools` (`source_url, source_slug, kind, name, relative_path, description, source_sha, last_seen`; PK `(source_slug, kind, name)`). Description via existing `_extract_description` in `backend/app/api/tools.py:32-80`. Surface as a "Discover" tab on the tools page.

| # | Task | depends_on |
|---|------|-----------|
| A1 | `tool_sources.yml` loader + schema | — |
| A2 | discovery module: clone + walk + parse | [A1] |
| A3 | `discovered_tools` SQLite index + upsert | [A2] |
| A4 | refresh + list API + periodic scheduler | [A3] |
| A5 | Frontend: Discover tab on tools page | [A4] |

# History

```
2026-06-03T12:18:54Z [agent]
All tasks complete. Completed 5, skipped 0 already-done.
```
