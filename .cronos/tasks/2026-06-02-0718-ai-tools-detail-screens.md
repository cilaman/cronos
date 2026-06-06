---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-02T07:18:50Z'
depends_on: []
id: 2026-06-02-0718-ai-tools-detail-screens
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: AI Tools Detail Screens
type: goal
updated_at: '2026-06-02T08:26:24Z'
waiting_question: null
---

# Brief

Add detailed view screens for AI tools on the AI Tools page. When a user clicks a tool card, they see a structured detail panel with the tool's full file content, name, description, path, scope, modification time, category, and frontmatter metadata.

## Background

The current `SpaceToolsPage.tsx` (`frontend/src/pages/SpaceToolsPage.tsx`) renders `ToolCard` components in a category grid. Each card shows truncated metadata (name, description snippet, path, scope badge, modified_at) but there is no way to drill into a tool and read its full content.

The backend endpoint `GET /api/spaces/{space_id}/tools` returns `AiToolEntry` objects with `name`, `path`, `description`, `scope`, `modified_at`. There is no endpoint to fetch the full file content of an individual tool.

## Child tasks

1. Backend – Tool content endpoint
2. Frontend – Tool detail panel (slide-over drawer)
3. Frontend – URL-based navigation (deep-link via query params)
4. Tests – Backend + frontend coverage

# History

```
2026-06-02T08:26:24Z [agent]
All tasks complete. Completed 4, skipped 0 already-done.
```
