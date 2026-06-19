---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-05T23:27:18Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-05-2327-harness-editor-usability
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
state: backlog
title: Harness editor usability
type: goal
updated_at: '2026-06-10T05:10:59Z'
waiting_question: null
---

# Brief

# Harness editor usability

Close the gap between the harness **visual editor** and the harness **runtime contract**
so a user can actually build a working harness end-to-end: drag nodes, connect them to
real agents/skills, set variables and per-node config, save without silent 422s, and run.

## Why
The editor currently lets you draw a graph but the saved payload diverges from the backend
data model (`backend/app/harnesses/model.py`, the source of truth), and the runtime cannot
resolve agent/skill references. Net effect: harnesses look editable but do not work.
Do NOT change the backend Pydantic models — align the frontend to them; only the runtime
tools-resolver stub is a backend change.

## Root-cause inventory (all must be fixed)
Frontend (Slice A):
1. Node `config` ↔ backend `node.data` round-trip is lossy (harnessMapping + VariableInspector).
2. Agent prompt is stored as `config.prompt`; runtime reads `node.data.prompt_template`
   (`backend/app/harnesses/executor.py:736`).
3. `ports` is emitted as a list (even `[]`); backend requires `dict[str, dict]` → save 422.
   New nodes also lack default ports and the Handle `id`s the node components expect.
4. Edge condition is stored as `label`; backend uses `HarnessEdge.condition: str|None`.
5. Only AgentNode has editable config; decision/wait/aggregator/trigger config is not editable.
6. `onVariableChange` is a no-op at the editor level; variables cannot be added/edited/removed.
7. Backend validation 422s on save are swallowed silently — no user feedback.

Backend (Slice B):
8. `_tools_resolver` in `backend/app/worker.py:470-471` is a stub returning `None`, so agent
   and skill nodes never resolve to an `AiToolEntry` and briefs are composed without the
   agent header / skill `/<name>` prefix.

## Structure
- Slice A — Frontend harness editor (CC-v1 pipeline).
- Slice B — Backend harness tools resolver (CC-v1 pipeline, sequential after Slice A).
- Final integration task runs /goal-finalize on the shared feature branch.

Shared feature branch: `feature/<root-goal-slug>`.

# History

```
2026-06-05T23:30:24Z [agent]
Paused: Sub-goal 'Backend harness tools resolver' ended in waiting state. Completed 0, skipped 0 already-done.
```
