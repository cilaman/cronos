---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-29T17:29:46Z'
depends_on: []
id: 2026-05-29-1729-update-agent-definitions-to-claude-opus
manual_order: 0
parent_id: 2026-05-29-1642-opus-4-8-support
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: Update agent definitions to claude-opus-4-8
type: task
updated_at: '2026-05-29T17:29:46Z'
waiting_question: null
---

# Brief

Update the two registered agent definition files that currently hardcode `claude-opus-4-7` to use `claude-opus-4-8` instead.

## Files to change

1. `.claude/agents/test-architect.md` line 4 — change `model: claude-opus-4-7` to `model: claude-opus-4-8`
2. `.claude/agents/security-officer.md` line 4 — change `model: claude-opus-4-7` to `model: claude-opus-4-8`

## Acceptance

- Both files have `model: claude-opus-4-8` in their frontmatter.
- Running `grep -r "claude-opus-4-7" .claude/agents/` returns no matches.

# History
