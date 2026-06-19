---
agent_mode: auto
agent_model: opus
claude_session_id: 30b853c7-04d0-4d17-ab6c-2f75286ef220
created_at: '2026-06-05T23:27:18Z'
depends_on:
- 2026-06-05-2327-analysis-frontend-harness-editor
feature_key: null
feature_state: null
id: 2026-06-05-2327-design-frontend-harness-editor
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-05-2327-frontend-harness-editor
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: design – frontend-harness-editor
type: task
updated_at: '2026-06-18T15:28:06Z'
waiting_question: null
---

# Brief

CC-v1 design phase for sub-goal: Frontend harness editor.

## Feature request (full scope this slice must deliver)
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

## Scope (files this slice is allowed to touch)
frontend/src/types.ts, frontend/src/components/harness/harnessMapping.ts, frontend/src/components/harness/VariableInspector.tsx, frontend/src/pages/HarnessEditor.tsx, frontend/src/components/harness/{Agent,Trigger,Decision,Wait,Aggregator}Node.tsx, frontend/src/components/harness/NodePalette.tsx, and their vitest specs

## Phase instructions
- Agent contract: `.claude/agents/pipeline-architect.md` (class=design).
- Read the prior phase artifact(s) in `.cronos/pipeline/frontend-harness-editor/`.
- Scout report: `.cronos/pipeline/frontend-harness-editor/scout-report-frontend-harness-editor.md`.
- Emit your artifact (class=design) into `.cronos/pipeline/frontend-harness-editor/`.
- The impl phase fans out one iteration at a time per the design's iterations[]; run /goal-branch-setup before the first code edit and /goal-task-commit after each.

Then run: /pipeline-gate

# History

```
2026-06-05T23:46:23Z [agent]
Architect succeeded. Now closing the gate.

Gate PASS — design phase recorded. PHASE != retro so Step 3b/3c skipped.

gate PASS — design / frontend-harness-editor
  artifact: .cronos/pipeline/frontend-harness-editor/design-report-frontend-harness-editor.md
  normalize: 3 fix(es) applied (unknown strategy synonyms dropped — non-blocking)

STATUS: DONE
```
