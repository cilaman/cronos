---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-05T23:27:18Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-05-2327-frontend-harness-editor
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-05-2327-harness-editor-usability
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Frontend harness editor
type: goal
updated_at: '2026-06-18T15:28:06Z'
waiting_question: null
---

# Brief

Align the harness visual editor to the backend data model so saved harnesses
are valid and runnable. The backend model in `backend/app/harnesses/model.py` is the source of
truth and MUST NOT be changed.

Acceptance criteria:
1. **Node data round-trip.** `frontend/src/components/harness/harnessMapping.ts` `toReactFlow()`
   maps backend `node.data` into the editor and `fromReactFlow()` maps editor state back into
   `node.data` (NOT a separate `config` key). No keys are dropped in either direction. Update
   `frontend/src/types.ts` so the node type exposes `data` consistently.
2. **prompt_template.** The agent prompt field persists to `node.data.prompt_template` (what the
   runtime reads at `backend/app/harnesses/executor.py:736`). `VariableInspector.tsx` currently
   reads/writes `config.prompt` — fix it.
3. **ports as dict + defaults + Handle ids.** `fromReactFlow()` emits `ports` as `dict[str,dict]`
   (never a list, never `[]`). New nodes get default ports matching the Handle `id`s their node
   component renders: DecisionNode (`yes`,`no`), AgentNode/TriggerNode/WaitNode (single in/out),
   AggregatorNode (N inputs + single out). A freshly dragged node must save without a 422.
4. **Edge condition round-trip + editing.** `HarnessEdge.condition: str|None` (backend) maps to/from
   the editor edge. Decision-out edges expose an editable condition (`yes`/`no`/default = null).
5. **Editable config for ALL node types**, not just Agent: decision condition, wait
   `max_wait_seconds` + mode, aggregator `mode` (all/any), trigger kind + per-kind fields.
6. **Variables add/edit/remove.** Wire `onVariableChange` through `HarnessEditor.tsx` so it mutates
   `harness.variables`; add UI to add and remove variable rows. Saved harness has the variables.
7. **Save feedback.** Surface backend 422 validation errors in the editor (inline or toast) instead
   of failing silently.

All changes are frontend-only under `frontend/src/`. Add/extend vitest coverage for harnessMapping
round-trip and VariableInspector field wiring. Run `cd frontend && npm test` and `npm run build`.

# History

```
2026-06-06T00:32:16Z [agent]
All tasks complete. Completed 7, skipped 0 already-done.
```
