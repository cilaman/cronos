---
agent_mode: auto
agent_model: haiku
claude_session_id: 7e9610d3-b737-45f8-afbe-8e5410c88f31
created_at: '2026-06-05T23:27:18Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-05-2327-scout-frontend-harness-editor
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
title: scout – frontend-harness-editor
type: task
updated_at: '2026-06-18T15:28:06Z'
waiting_question: null
---

# Brief

CC-v1 scout phase for sub-goal: Frontend harness editor.

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
- Agent contract: `.claude/agents/pipeline-scout.md` (class=research).
- Read the prior phase artifact(s) in `.cronos/pipeline/frontend-harness-editor/`.
- Scout report: `.cronos/pipeline/frontend-harness-editor/scout-report-frontend-harness-editor.md`.
- Emit your artifact (class=research) into `.cronos/pipeline/frontend-harness-editor/`.
- The impl phase fans out one iteration at a time per the design's iterations[]; run /goal-branch-setup before the first code edit and /goal-task-commit after each.

Then run: /pipeline-gate

# History

```
2026-06-05T23:38:40Z [agent]
I'll scout the frontend harness editor to understand the gaps between the visual editor and backend data model. Let me start by examining the backend model and current frontend implementation.

Now I'll write a comprehensive scout report analyzing the gaps between the frontend editor and backend model.

Now I'll close the scout phase by running the pipeline gate. Let me use the pipeline-gate skill.

I'll invoke the pipeline-gate skill to close the scout phase.

I'll execute the pipeline-gate skill to verify and record the scout phase. Let me start by resolving the environment and running the verification.

I need to fix the scout report to comply with the CC-v1 research class schema. Let me update it with the required sections and header fields.

Now I'll record the phase state and log the gate passing.

Perfect! The scout phase has been verified and recorded successfully.

## Summary

The **scout phase for frontend-harness-editor** is complete:

**Gate result**: PROCEED ✓
- Artifact verified at: `.cronos/pipeline/frontend-harness-editor/scout-report-frontend-harness-editor.md`
- All CC-v1 research-class validation rules passed
- Phase state recorded to pipeline-state.json

**Scout findings**: 7 major gaps identified between the frontend harness editor and backend data model:

1. **F1**: node.data vs node.config structural mismatch (toReactFlow/fromReactFlow round-trip loses keys)
2. **F2**: prompt_template field naming (VariableInspector writes `config.prompt` instead of `config.prompt_template`)
3. **F3**: Ports as array instead of dict, no default ports for new nodes (backend validation will fail on newly dragged nodes)
4. **F4**: Edge condition vs label; missing decision routing UI (no way to set yes/no conditions on decision branches)
5. **F5**: Editable config missing for non-Agent nodes (Decision, Wait, Aggregator, Trigger nodes show read-only config)
6. **F6**: Variables table lacks add/remove UI (can edit values but not add/remove variables)
7. **F7**: No error feedback for backend 422 validation errors (save failures fail silently)

**Next phase**: The analyst will decompose these findings into testable requirements and design implementation iterations.

gate PASS — scout / frontend-harness-editor
  artifact: .cronos/pipeline/frontend-harness-editor/scout-report-frontend-harness-editor.md

STATUS: DONE
```
