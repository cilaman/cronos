---
agent_mode: auto
agent_model: haiku
claude_session_id: f26d6b5e-ea2f-4c72-905a-907d0908463b
created_at: '2026-06-05T23:27:18Z'
depends_on:
- 2026-06-05-2327-review-frontend-harness-editor
feature_key: null
feature_state: null
id: 2026-06-05-2327-doc-frontend-harness-editor
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
title: doc – frontend-harness-editor
type: task
updated_at: '2026-06-18T15:28:06Z'
waiting_question: null
---

# Brief

CC-v1 doc phase for sub-goal: Frontend harness editor.

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
- Agent contract: `.claude/agents/pipeline-doc-sync.md` (class=doc).
- Read the prior phase artifact(s) in `.cronos/pipeline/frontend-harness-editor/`.
- Scout report: `.cronos/pipeline/frontend-harness-editor/scout-report-frontend-harness-editor.md`.
- Emit your artifact (class=doc) into `.cronos/pipeline/frontend-harness-editor/`.
- The impl phase fans out one iteration at a time per the design's iterations[]; run /goal-branch-setup before the first code edit and /goal-task-commit after each.

Then run: /pipeline-gate

# History

```
2026-06-06T00:32:16Z [agent]
I'll start by reading the prior phase artifacts to understand what was implemented.

Let me check the current implementation to understand what needs to be documented:

Let me copy the implementation report from the feature branch and set up the pipeline directory:

Now I'll update the documentation to reflect the implementation changes. The key change is that VariableInspector now has comprehensive per-node-type config editing:

Now I'll run the pipeline gate to verify and finalize the doc phase:

I'll execute the pipeline gate to verify the doc-report artifact.

I need to copy my artifacts to the space root where the pipeline expects them. Let me do that:

Now let me run the verifier again to check the artifact:

Now I'll update the pipeline state to record the doc phase completion:

Perfect! The pipeline gate has successfully verified the doc-report artifact and updated the pipeline state. The doc phase is now complete.

## Summary

I've successfully completed the doc phase for the `frontend-harness-editor` pipeline:

**What was implemented (per the impl-report):**
- All 7 acceptance criteria for aligning the harness visual editor with the backend data model
- Node data round-trip through the `data` field (not `config`)
- Per-node-type editable configuration in VariableInspector (agent, trigger, decision, wait, aggregator)
- Variables add/remove UI
- 422 validation error surfacing with formatted messages
- Edge condition round-trip support

**Documentation updated:**
- CLAUDE.md: Updated the VariableInspector.tsx description to reflect its expanded per-node-type config editing capability (previously described as agent-only)

**Gate result:** ✓ PASS — artifact verified, pipeline state recorded

The feature is now ready for user hand-off. All documentation has been updated to reflect the implementation changes.

STATUS: DONE
```
