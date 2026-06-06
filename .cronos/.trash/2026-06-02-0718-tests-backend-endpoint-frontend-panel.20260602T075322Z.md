---
agent_mode: auto
agent_model: sonnet
claude_session_id: null
created_at: '2026-06-02T07:18:50Z'
depends_on: []
id: 2026-06-02-0718-tests-backend-endpoint-frontend-panel
manual_order: 0
parent_id: 2026-06-02-0718-ai-tools-detail-screens
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: Tests – Backend endpoint + frontend panel
type: task
updated_at: '2026-06-02T07:18:50Z'
waiting_question: null
---

# Brief

Add test coverage for the new tool-content backend endpoint and the ToolDetailPanel frontend component.

## Backend tests

File: `backend/tests/test_tool_content.py` (new file)

Use pytest + httpx `AsyncClient`. Tests to write:

1. **Happy path** — `GET /api/spaces/{space_id}/tool-content?path=.claude/agents/tester.md&scope=space` returns 200, `content` is a non-empty string, `category == "agent"`.
2. **Path traversal rejected** — `path=../../etc/passwd` (or `../../../etc/passwd`) returns 400.
3. **Missing file** — a valid-looking path under `.claude/` that doesn't exist returns 404.
4. **Global scope** — a global tool path (under `~/.claude/`) returns 200 or 404 (not 400 or 500) depending on existence.
5. **Category inference** — a path containing `/skills/` returns `category="skill"`.

Use the existing test fixtures/patterns from `backend/tests/` (look at `conftest.py` for the `async_client` fixture and any `tmp_path`/`space_dir` helpers).

## Frontend tests

File: `frontend/src/__tests__/ToolDetailPanel.test.tsx` (new file)

Use vitest + React Testing Library. Tests to write:

1. **Renders tool name and scope** — given a mock `AiToolEntry`, the panel renders the name and scope badge.
2. **Shows loading spinner** while fetch is pending.
3. **Shows content** once the `useToolContent` query resolves (mock the hook).
4. **Calls onClose on Escape key** — fire `keydown` Escape event, assert `onClose` was called.
5. **Calls onClose on backdrop click** — click the semi-transparent backdrop, assert `onClose` was called.

Mock `useToolContent` via `vi.mock('../hooks/useSpaces')`.

## Acceptance

- `cd backend && pytest tests/test_tool_content.py -v` passes.
- `cd frontend && npm test -- --run src/__tests__/ToolDetailPanel.test.tsx` passes.
- No existing tests broken (run full suite to confirm).

# History
