---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-19T06:44:03Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-19-0644-memory-replace-fragile-memory-regex-with
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: done
title: 'Memory: Replace fragile MEMORY: regex with structured sentinel'
type: goal
updated_at: '2026-06-19T10:40:28Z'
waiting_question: null
---

# Brief

## Motivation

The `MEMORY:` free-text regex ingestion path in `trace_parser.py` is the same anti-pattern already flagged as a P0 reliability hazard for STATUS: completion detection. The failure mode is identical: markdown-wrapped `MEMORY:` markers are silently dropped. Since a structured sentinel is being adopted for completion detection, the same decision must be applied to memory capture.

## Goal

Replace the fragile `MEMORY:` regex parse with a structured sentinel approach — either a `cronos_remember` tool/skill the agent invokes with structured fields, or a post-task structured-extraction step — so memory capture is as reliable as completion detection.

## Sub-goals

1. **memory-sentinel-impl** — single pipeline slice covering scout → analyst → architect → impl → test → review → doc

## Files in scope

- `backend/app/memory_store.py`
- `backend/app/trace_parser.py`
- `backend/app/agent.py`
- `backend/app/worker.py`
- `.claude/skills/write-memory/`
- `backend/tests/` (affected test files)

# History

```
2026-06-19T09:48:23Z [agent]
Paused: Sub-goal 'memory-sentinel-impl' ended in waiting state. Completed 0, skipped 0 already-done.
```

```
2026-06-19T09:53:12Z [agent]
Paused: Child 'memory-sentinel-impl' is in waiting state and needs attention. Completed 0, skipped 0 already-done.
```

```
2026-06-19T09:53:12Z [agent]
Paused: Child 'memory-sentinel-impl' is in waiting state and needs attention. Completed 0, skipped 0 already-done.
```

```
2026-06-19T10:24:43Z [agent]
All tasks complete. Completed 0, skipped 2 already-done.
```

```
2026-06-19T10:40:28Z [agent]
All tasks complete. Completed 0, skipped 2 already-done.
```
