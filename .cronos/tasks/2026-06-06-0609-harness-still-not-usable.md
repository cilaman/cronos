---
agent_mode: auto
agent_model: default
claude_session_id: 30532ff0-ad28-4df1-b99e-c62f87cee9d0
created_at: '2026-06-06T06:09:45Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-06-0609-harness-still-not-usable
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Harness still not usable
type: task
updated_at: '2026-06-13T06:30:16Z'
waiting_question: null
---

# Brief

In the editor upon creating a new harness I am not able to do anything, i.e. drag and drop of elements does not work, i cannot create variables, nothing. Plese also investigate whether it is possible to wire the Agent graph element of the harness to a real agent in Cronos.

# History

```
2026-06-06T06:24:11Z [agent] run=0 model=claude-sonnet-4-6 mode=auto agents=explore
I'll investigate the current state of the harness editor to understand what's broken after the recent usability merge.

Let me read the actual HarnessEditor code to verify and plan the exact fixes needed.

Now let me check the VariableInspector to understand the variable creation issue more specifically.

Let me also check the types to understand `HarnessNode` and what ports format is expected.

I can see the two bugs clearly now:

1. **Drag-and-drop**: `onDrop`/`onDragOver` are on a wrapper `div` containing ReactFlow, but React Flow intercepts drag events internally — these handlers need to be props on `<ReactFlow>` directly.
2. **Clicking newly-dropped nodes**: `selectedNode` is looked up from `harness?.nodes` (the saved harness), so freshly dragged nodes (not yet saved) won't show config in the inspector.

Let me fix both.

Now fix the drag-and-drop by moving the handlers to the `<ReactFlow>` component:

Now let me verify the changes look correct:

Changes look good. Now let me run the frontend tests to make sure nothing is broken.

The tests fire `drop` events on the wrapper `canvas` div, but the handler is now on ReactFlow. Let me check the test setup to understand the correct selector.

The mock already correctly attaches `onDragOver`/`onDrop` to the ReactFlow div. The tests just need to fire events on `data-testid="react-flow"` directly instead of its parent. Let me fix both failing tests:

Now fix the acceptance test:

All 1109 tests pass. Now let me commit the fix and address the agent wiring question.

Pushed. Now let me upgrade the running instance.

**Summary of fixes:**

**Bug 1 — Drag-and-drop broken** (`HarnessEditor.tsx:322`): The `onDrop`/`onDragOver` handlers were on a wrapper `div` containing ReactFlow. React Flow's internal DOM intercepts drag events before they bubble to the parent. Fix: moved both handlers as direct props on `<ReactFlow>`.

**Bug 2 — Clicking newly-dropped nodes shows no config** (`HarnessEditor.tsx:221`): `selectedNode` was looked up only from `harness?.nodes` (the saved server state). Freshly-dragged nodes exist in React Flow state but not in the saved harness. Fix: falls back to the live `nodes` array and constructs a `HarnessNode` from the RF node data.

**Agent wiring to real Cronos agents**: Yes, this works. In an Agent node's config, set `agent_ref` to the name of any registered agent in your space (e.g. `test-architect`, `tester`, `pipeline-scout`). The executor resolves it against the space's AI tools registry at runtime and composes the brief accordingly. The agent must exist as a `.md` file in `.claude/agents/` in the space.

STATUS: DONE
```
