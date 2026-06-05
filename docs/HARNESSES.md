# Using Harnesses in Cronos

A **harness** is a directed graph (a DAG) that orchestrates several Claude Code
agent runs into one automated workflow. Instead of creating tasks by hand one at
a time, you draw (or write) a graph of nodes — *run this agent, then decide,
then wait for a human, then run two agents in parallel, then collect the
results* — and Cronos executes the whole thing for you, creating a child task
per agent step and driving them to completion.

This document explains how harnesses actually work today, end-to-end, with a
real worked example you can copy and run.

> **Read this first — why the visual editor feels broken.**
> If you opened the visual editor and found you could drag nodes but could *not*
> connect them to real agents, add variables, or set values, that is **not your
> mistake**. The visual editor in its current state cannot persist most node
> configuration (see [Known limitations](#known-limitations-read-this)). The
> **reliable way to author a working harness today is by editing the harness
> YAML file directly, or via the REST API** — both are fully supported by the
> executor. This guide teaches that path, and tells you exactly which parts of
> the UI you can and cannot rely on.

---

## Table of contents

1. [Mental model](#1-mental-model)
2. [Where harnesses live](#2-where-harnesses-live)
3. [The data model](#3-the-data-model)
4. [Real-life example: a research → review → implement pipeline](#4-real-life-example)
5. [Authoring a harness (YAML + API)](#5-authoring-a-harness)
6. [Variables and interpolation](#6-variables-and-interpolation)
7. [Connecting nodes to real agents and skills](#7-connecting-nodes-to-real-agents-and-skills)
8. [Control-flow nodes: decision, wait, aggregator](#8-control-flow-nodes)
9. [Triggers: how a harness starts](#9-triggers)
10. [Running a harness and watching it execute](#10-running-a-harness)
11. [The run lifecycle and run state](#11-the-run-lifecycle)
12. [Known limitations (read this)](#known-limitations-read-this)
13. [Troubleshooting](#12-troubleshooting)
14. [Quick reference](#13-quick-reference)

---

## 1. Mental model

A harness has three layers:

```
  HARNESS GRAPH (definition)           EXECUTOR (runtime)              CRONOS BOARD (result)
  ┌─────────────────────────┐         ┌────────────────────┐         ┌──────────────────────┐
  │ trigger → agent → agent  │  ──►    │ runtime-gated BFS   │  ──►    │ "Harness run: X" goal │
  │            ↓             │         │ walks the DAG,      │         │   ├─ child task (node)│
  │         decision         │         │ creates one child   │         │   ├─ child task (node)│
  │          ↙   ↘           │         │ task per agent node │         │   └─ ...              │
  │      agent   agent       │         │ runs each agent,    │         │                      │
  │          ↘   ↙           │         │ persists run state  │         │                      │
  │        aggregator        │         └────────────────────┘         └──────────────────────┘
  └─────────────────────────┘
```

- **You define** a graph of nodes and edges (the harness YAML).
- **The executor** (`backend/app/harnesses/executor.py`) walks the graph with a
  runtime-gated breadth-first search. A node becomes "ready" when *all* of its
  predecessors have finished. Ready nodes are processed in sorted-id order for
  determinism.
- **Each `agent` node** becomes a real Cronos **child task** under a parent
  "Harness run" task. The agent runs, and the executor records whether it
  reached `DONE`.
- **Control-flow nodes** (`decision`, `wait`, `aggregator`) do not run agents —
  they steer the graph.
- **Fail-fast**: if any agent node ends in a non-`DONE` state, every remaining
  node is marked `skipped` (`reason=upstream_failed`) and the run ends `failed`.

The five node types:

| Type         | Purpose                                                              | Runs an agent? |
|--------------|---------------------------------------------------------------------|:--------------:|
| `trigger`    | Entry point. Manual, cron-scheduled, webhook, file-change, or task-state-change. | No |
| `agent`      | Invokes an agent/skill as a child task with an interpolated prompt.  | **Yes** |
| `decision`   | Picks exactly one outgoing edge based on the upstream signal.        | No |
| `wait`       | Pauses the run — either for a fixed duration or for a human reply.   | No |
| `aggregator` | Joins several upstream branches (`all` or `any`).                    | No |

---

## 2. Where harnesses live

Each harness is a single YAML file inside the space:

```
{space_dir}/.cronos/harnesses/<slugified-name>.yml
```

The name is slugified for the filename (lowercased, non-alphanumerics → `-`),
but harnesses are addressed by their **display name** everywhere in the API and
UI. Run history and run state live alongside:

```
{space_dir}/.cronos/harness-runs/<harness>-index.json   # run history index
{space_dir}/.cronos/harness-runs/<run_id>.json          # per-run state snapshot
```

You can edit the `.yml` file by hand; the store reloads it. After a manual edit,
re-fetch the harness in the UI (reload the editor page) so the canvas reflects
your changes.

---

## 3. The data model

Source of truth: `backend/app/harnesses/model.py`.

### Harness (top level)

```yaml
name: my-harness            # display name (also the API id)
description: ""
version: "1.0"
variables: {}               # dict[str, str] — root variable scope
nodes: []                   # list of nodes (see below)
edges: []                   # list of edges (see below)
created_at: "..."           # ISO-8601 UTC (managed for you)
updated_at: "..."           # ISO-8601 UTC (managed for you)
```

### Node

```yaml
- id: agent-1               # unique within the harness (R1)
  type: agent               # agent | trigger | decision | wait | aggregator
  label: "Scout"            # shown on the canvas; also the child-task title
  position: { x: 200, y: 0 } # canvas coordinates (floats)
  ports:                    # dict keyed by port-id (NOT a list!)
    in:  { direction: input }
    out: { direction: output }
  data:                     # node-specific config — THIS is where agent_ref etc. go
    agent_ref: pipeline-scout
    prompt_template: "Research $topic and report findings."
```

Two things trip people up here, so they are worth stating loudly:

- **`ports` is a dict**, keyed by port id (`in`, `out`, `yes`, `no`, …). Each
  value is a free-form dict. It is **not** a list. An empty `[]` is rejected by
  validation.
- **All node configuration goes in `data`**, not in a field called `config`. The
  executor reads `data["agent_ref"]` and `data["prompt_template"]`. (The
  frontend uses a `config` field internally — see
  [Known limitations](#known-limitations-read-this).)

### Edge

```yaml
- id: e1
  source: { node_id: trigger-1, port_id: out }
  target: { node_id: agent-1,   port_id: in }
  condition: null           # null = unconditional; a string = a guard (decision only)
```

Validation rules enforced on save (`model.py` + `validator.py`):

| Rule | Meaning |
|------|---------|
| R1   | Node ids are unique. |
| R2   | Edge ids are unique. |
| R3   | Every edge endpoint references an existing node id. |
| R4   | Every edge endpoint references a port id that exists in that node's `ports` dict. |
| R5   | The graph is a DAG — no cycles, no self-loops. |
| R6   | A human `wait` node must define `max_wait_seconds`. |
| R7   | An event `trigger` (one with a `kind`) must supply its per-kind required fields. |

If any rule fails, the create/update API returns **422** and the harness is not
saved.

---

## 4. Real-life example

Goal: *"Whenever I ask, research a topic, let me review the findings, then
implement the change."*

This harness uses a manual trigger, two agent nodes, a human wait node for your
review, one variable (`topic`), and unconditional edges. It is fully runnable
today.

```yaml
name: research-then-build
description: "Scout a topic, pause for human review, then implement."
version: "1.0"

variables:
  topic: "the memory subsystem"

nodes:
  - id: trigger-1
    type: trigger
    label: "Manual start"
    position: { x: 0, y: 0 }
    ports:
      out: { direction: output }
    data: {}                       # no `kind` ⇒ manual/cron-style trigger

  - id: scout
    type: agent
    label: "Scout the codebase"
    position: { x: 0, y: 150 }
    ports:
      in:  { direction: input }
      out: { direction: output }
    data:
      agent_ref: pipeline-scout
      prompt_template: |
        Research $topic in this codebase. Produce a short report of the
        relevant files, current behaviour, and risks.

  - id: review
    type: wait
    label: "Human review"
    position: { x: 0, y: 300 }
    ports:
      in:  { direction: input }
      out: { direction: output }
    data:
      mode: human
      waiting_question: "Review the scout report. Reply 'go' to implement."
      max_wait_seconds: 86400      # required for human waits (R6) — 24h guardrail

  - id: build
    type: agent
    label: "Implement the change"
    position: { x: 0, y: 450 }
    ports:
      in:  { direction: input }
      out: { direction: output }
    data:
      agent_ref: pipeline-implementor
      prompt_template: |
        Based on the scout findings for $topic, implement the change.

edges:
  - id: e1
    source: { node_id: trigger-1, port_id: out }
    target: { node_id: scout,     port_id: in }
    condition: null
  - id: e2
    source: { node_id: scout,  port_id: out }
    target: { node_id: review, port_id: in }
    condition: null
  - id: e3
    source: { node_id: review, port_id: out }
    target: { node_id: build,  port_id: in }
    condition: null
```

What happens when you run it:

1. The trigger fires; `scout` becomes ready (in-degree 0 after the trigger).
2. The executor creates a child task **"Scout the codebase"** with the brief
   built from `agent_ref` + the interpolated `prompt_template`
   (`$topic` → `the memory subsystem`), runs it, and waits for `DONE`.
3. `review` is a **human wait** — the run parks. The parent "Harness run" task
   moves to **WAITING** with your `waiting_question`. The harness stops here.
4. You **reply to the waiting task** (any message). On the next worker tick the
   harness resumes from the wait node's outgoing edges.
5. `build` becomes ready, runs the implementor agent, and the run finishes
   `DONE`.

---

## 5. Authoring a harness

There are two reliable authoring paths. Both produce the same YAML file.

### Path A — REST API (recommended for repeatable setup)

Create:

```bash
curl -u "$USER:$PASS" \
  -X POST "http://localhost:8080/api/spaces/$SPACE_ID/harnesses" \
  -H "Content-Type: application/json" \
  -d @research-then-build.json
```

The JSON body is the harness object minus `created_at`/`updated_at` (the server
sets those). Endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `GET`    | `/api/spaces/{space_id}/harnesses`           | List harnesses |
| `POST`   | `/api/spaces/{space_id}/harnesses`           | Create (422 on invalid graph, 409 on name clash) |
| `GET`    | `/api/spaces/{space_id}/harnesses/{name}`    | Fetch one |
| `PUT`    | `/api/spaces/{space_id}/harnesses/{name}`    | Replace (preserves `created_at`) |
| `DELETE` | `/api/spaces/{space_id}/harnesses/{name}`    | Delete (409 if a run is active) |

> Tip: to convert the YAML above into the JSON body, any `yaml→json` tool works,
> or author the body directly in JSON. The field names are identical.

### Path B — edit the YAML file directly

Write the file to `{space_dir}/.cronos/harnesses/research-then-build.yml` with
exactly the schema from [§3](#3-the-data-model). Reload the editor page to see
it. This is the fastest path while iterating locally.

### What about the visual editor?

You can use the editor to **lay out** the graph (drag node types from the
palette, position them, draw edges) and to **trigger runs / watch execution**.
But it currently does **not** reliably save node `data` (agent_ref, prompt),
variables, or edge conditions, and saving freshly-dragged nodes fails outright.
Treat the editor as a viewer + run console, and author configuration in YAML or
via the API. See [Known limitations](#known-limitations-read-this).

---

## 6. Variables and interpolation

Source: `backend/app/harnesses/interpolate.py`.

Prompts use Python `string.Template` syntax: `$name` or `${name}`.

```yaml
variables:
  topic: "the memory subsystem"
  lang: "python"
# ...
prompt_template: "Research $topic. Write the fix in ${lang}."
```

Scope and precedence:

1. **Root variables** (`harness.variables`) form the base scope.
2. **Upstream node outputs override root variables** on key collision. After an
   agent node finishes `DONE`, its output (the agent's final text snippet) is
   stored in the scope under the **node id**. So `$scout` in a later prompt
   expands to the scout node's final output.

```yaml
# In the `build` node, reference the scout node's output:
prompt_template: |
  The scout reported:
  $scout

  Now implement the fix for $topic.
```

Unresolved placeholders are **left intact** (`$missing` stays literally
`$missing`) and logged as a warning — they do not crash the run. This is
`safe_substitute` behaviour.

> Because upstream outputs are keyed by node id, give your agent nodes
> meaningful ids if you intend to interpolate their output downstream.

---

## 7. Connecting nodes to real agents and skills

An `agent` node invokes an agent or skill via two `data` fields:

```yaml
data:
  agent_ref: pipeline-scout       # name of an agent or skill available in the space
  prompt_template: "..."          # the instruction, with $variable placeholders
```

When the node runs, the executor:

1. Interpolates `prompt_template` against the variable scope.
2. Composes the child-task **brief** (`brief_composer.py`):
   - For a **skill**: the brief starts with `/<skill-name>` (the CLI's skill
     trigger), then the prompt.
   - For a plain **agent**: the brief starts with `Agent: <agent_ref>`, then the
     prompt.
3. Creates a child task under the run, with `title = node.label`, and runs it.

`agent_ref` can be any agent or skill registered in the space — e.g.
`pipeline-scout`, `pipeline-analyst`, `pipeline-implementor`, `test-architect`,
or a skill like `frontend-design`. (See the registered agents/skills tables in
`CLAUDE.md`.)

> **Current caveat — skill vs agent detection is degraded.** The worker wires
> the executor's tool resolver to a stub that always returns "not found"
> (`worker.py`, `_tools_resolver → None`). The practical effect: the brief is
> composed via the *unresolved* path, so it embeds `Agent: <ref>` as plain text
> rather than emitting the `/<skill-name>` skill-trigger prefix. Plain-agent
> prompts work (the ref is named in the brief), but skill nodes will **not**
> auto-fire as a `/skill`. Until the resolver is implemented, prefer plain
> agents in agent nodes, or put the `/skill` invocation directly at the top of
> `prompt_template` yourself.

---

## 8. Control-flow nodes

### Decision — pick one branch

A `decision` node evaluates its **outgoing edges** against a signal derived from
the upstream agent and follows the **first matching edge**. An edge with
`condition: null` is the **default** (fallback) edge.

Signal precedence (`decision.py`, highest first):

1. **`status`** — a `STATUS: <value>` marker found in the upstream node's output.
   Matched case-sensitively against `edge.condition`.
2. **`exit_reason`** — the run's exit reason string.
3. **`regex`** — `re.search(edge.condition, upstream_final_text)`. Python inline
   flags like `(?i)` are allowed. No `/pattern/flags` syntax, no `eval`.
4. **`variable`** — a whitelisted expression on scope variables.

Variable-condition grammar (no `eval`): `<name> <op> <literal>` where `op` is
`==`, `!=`, or `in` (comma-separated list for `in`):

```yaml
edges:
  - id: d-yes
    source: { node_id: decide, port_id: yes }   # decision nodes expose yes/no ports
    target: { node_id: build,  port_id: in }
    condition: 'has_ui == "true"'
  - id: d-no
    source: { node_id: decide, port_id: no }
    target: { node_id: docs,   port_id: in }
    condition: null                              # default branch
```

To drive a decision from an agent, have the upstream agent end its output with a
marker, e.g. `STATUS: needs_ui`, and set the matching edge `condition:
needs_ui`. If no condition matches and there is no default edge, the decision
**fails** (and fail-fast kicks in) — so always provide a `condition: null` edge.

### Wait — pause the run

```yaml
# Human wait (parks until you reply to the WAITING task):
data:
  mode: human
  waiting_question: "Approve?"     # shown on the waiting task
  max_wait_seconds: 86400          # REQUIRED (R6)

# Timed wait (sleeps, then continues automatically):
data:
  mode: timed
  duration_seconds: 300
```

- **Human wait**: the executor parks the run, the parent task becomes
  **WAITING**, and `waiting_node_id` is recorded. **Reply to the task** to
  resume; traversal continues from the wait node's outgoing edges.
- **Timed wait**: the run sleeps `duration_seconds` and continues. Note: on a
  process restart, a timed wait re-sleeps the full duration (MVP behaviour).

### Aggregator — join branches

```yaml
data:
  mode: all   # fire when ALL predecessors are done; any failure fails the aggregator
  # or
  mode: any   # fire when the FIRST predecessor is done; fail only if all fail
```

Use an aggregator as the join point for a fan-out (e.g. two parallel agent
branches that must both finish before a final step). Aggregator output is
verdict-only; it does not merge the branch outputs into a single value.

---

## 9. Triggers

A `trigger` node is the graph's entry point. The `data.kind` field decides the
trigger flavour. **No `kind`** ⇒ a manual/cron trigger.

### Manual / cron

```yaml
# Manual: empty data — fire it from the UI Run button or POST /run.
data: {}

# Cron: schedule with a 5-field cron expression.
data:
  expression: "0 9 * * *"        # every day at 09:00
  timezone: "Europe/Prague"      # optional IANA tz; defaults to UTC
```

Cron triggers are evaluated by a background loop. Missed ticks (process offline)
are **not** back-filled. Malformed expressions are logged and skipped, not
crashed.

### Event triggers (require `kind` + per-kind fields, R7)

```yaml
# Webhook — fire via an authenticated HTTP POST.
data:
  kind: webhook
  webhook_path: "deploy-done"    # required
  auth_token: "<a long random token>"   # required; stored plaintext — keep YAML private

# File change — fire when matching files change in the space.
data:
  kind: file-change
  watch_pattern: ".cronos/tasks/*.md"   # required (glob, PurePath.match; ** supported)
  debounce_seconds: 0.5                  # optional (default 0.5)

# Task state change — fire when a task transitions to a state.
data:
  kind: task-state-change
  watched_state: "DONE"          # optional (default DONE)
```

Webhook call:

```bash
curl -u "$USER:$PASS" \
  -X POST "http://localhost:8080/api/spaces/$SPACE_ID/harnesses/$NAME/webhook" \
  -H "Authorization: Bearer <auth_token>" \
  -H "Content-Type: application/json" \
  -d '{"any":"payload"}'
```

Returns `202` with `{"run_ids": [...]}`. Identical payloads within
`debounce_seconds` are de-duplicated (empty `run_ids`). A wrong/missing token
returns `401`.

---

## 10. Running a harness

### From the UI

Open the harness in the editor and click **Run** (top-right). The run starts
immediately, the run overlay shows live node status, and the **Run History**
panel (left) lists past runs. Click a run to replay it; click a node with a
child task to open the child task drawer.

### From the API

```bash
curl -u "$USER:$PASS" \
  -X POST "http://localhost:8080/api/spaces/$SPACE_ID/harnesses/$NAME/run"
# → 202 { "run_id": "...", "harness_id": "...", "triggered_at": "..." }
```

List run history:

```bash
curl -u "$USER:$PASS" \
  "http://localhost:8080/api/spaces/$SPACE_ID/harnesses/$NAME/runs"
```

Inspect / cancel a specific run:

```bash
curl -u "$USER:$PASS" "http://localhost:8080/api/harness-runs/$RUN_ID"
curl -u "$USER:$PASS" -X POST "http://localhost:8080/api/harness-runs/$RUN_ID/cancel"
# Live SSE stream of node transitions:
#   GET /api/harness-runs/$RUN_ID/stream
```

You cannot delete a harness while it has a `running` run (the API returns 409).

---

## 11. The run lifecycle

When a run is triggered (UI, API, cron, webhook, or event):

1. A parent **"Harness run: \<name\>"** task is created and an entry is appended
   to the run index (`status: running`).
2. The task is transitioned to **ACTIVE** and enqueued on the space worker.
3. The worker recognises it as a harness run, loads the harness, builds a
   `HarnessExecutor`, and calls `execute()`.
4. The executor walks the DAG. For each `agent` node it creates a child task,
   runs the agent, and records the node result. Run state is persisted to
   `{space_dir}/.cronos/harness-runs/{run_id}.json` after every node — so a run
   can **resume** after a restart.
5. Terminal status:
   - **done** — all nodes completed.
   - **failed** — an agent node ended non-`DONE` (remaining nodes `skipped`).
   - **WAITING** — parked at a human wait; reply to the task to resume.
   - **cancelled** — you cancelled it; the executor stops at the next node
     boundary.

Each node carries `status` (`pending`/`in_progress`/`done`/`failed`/`skipped`),
`child_task_id`, `output`, and `started_at`/`ended_at` timestamps.

---

## Known limitations (read this)

These are the concrete reasons the harness feature feels unusable from the UI
today. They are **frontend ↔ backend contract mismatches** — the backend
executor is sound; the visual editor cannot feed it valid data.

| # | Symptom | Root cause | Workaround |
|---|---------|------------|------------|
| 1 | **Saving a graph with newly-dragged nodes fails** ("Save failed — check the graph for errors"). | Freshly-dragged nodes serialize `ports` as an empty **list** `[]`, but the backend `HarnessNode.ports` is a **dict**. Pydantic rejects the list → 422. (`harnessMapping.ts` `fromReactFlow`: `ports: orig?.ports ?? []`.) | Author/edit the YAML directly; define `ports` as a dict. |
| 2 | **agent_ref / prompt typed in the inspector never reach the agent.** | The frontend writes node config under a `config` field; the backend model reads `data`. Extra fields are ignored by Pydantic, so `data` stays empty. (`types.ts` `HarnessNode.config` vs `model.py` `HarnessNode.data`.) | Set `data.agent_ref` and `data.prompt_template` in YAML/API. |
| 3 | **The prompt field does nothing even if config were saved.** | The inspector writes `config.prompt`; the executor reads `data["prompt_template"]`. Name mismatch. | Use `prompt_template` in YAML/API. |
| 4 | **You cannot add or edit variables in the UI.** | `VariableInspector` only renders *existing* variables, and the editor passes `onVariableChange={() => {}}` (a no-op). There is no "add variable" control, and `fromReactFlow` preserves the original variables unchanged. | Edit `variables:` in YAML, or `PUT` the harness via API. |
| 5 | **Decision edge conditions can't be set in the UI.** | The frontend edge model has a `label` field; the backend edge has `condition`. The mapping reads/writes `label`, so `condition` is never populated. | Set `condition` on edges in YAML/API. |
| 6 | **Skill nodes don't auto-fire as `/skill`.** | The worker passes a stub tool resolver that always returns `None` (`worker.py`), so the brief composer can't detect skills. | Use plain agents, or put `/skill-name` at the top of `prompt_template`. |

If you'd like, these are all fixable on the frontend side (align `config`→`data`,
`prompt`→`prompt_template`, `ports` list→dict, edge `label`→`condition`, add a
variable editor) plus a real `tools_resolver` in the worker. Ask and I can
scope that as a follow-up goal.

---

## 12. Troubleshooting

- **422 on create/update** — a validation rule failed. Check: `ports` is a dict;
  edge endpoints reference existing node + port ids (R3/R4); no cycle (R5);
  human waits have `max_wait_seconds` (R6); event triggers have their required
  fields (R7).
- **Run ends immediately as `failed`** — an early agent node didn't reach
  `DONE`. Open its child task (drawer in the editor, or the board) to see why.
  Everything downstream will be `skipped` with `reason=upstream_failed`.
- **`$topic` shows up literally in the agent's task** — the variable isn't in
  scope. Confirm it's under `variables:` (root) or that you spelled the upstream
  node id correctly (outputs are keyed by node id).
- **Run is stuck in WAITING** — that's a human wait node. Reply to the
  "Harness run" task to resume. The `max_wait_seconds` guardrail will eventually
  release it if you never reply.
- **Decision raised "no matching edge and no default edge"** — add an edge with
  `condition: null` as the fallback.
- **Manual edits don't show in the editor** — reload the page; the canvas is
  initialised from the harness on load.

---

## 13. Quick reference

**Node `data` cheat sheet**

```yaml
# agent
data: { agent_ref: <name>, prompt_template: "... $var ..." }

# trigger (manual/cron)
data: {}                                   # manual
data: { expression: "0 9 * * *", timezone: "UTC" }   # cron

# trigger (event) — needs kind + required fields
data: { kind: webhook, webhook_path: p, auth_token: t }
data: { kind: file-change, watch_pattern: "glob/**", debounce_seconds: 0.5 }
data: { kind: task-state-change, watched_state: DONE }

# decision — routing is on the EDGES via `condition`; node data is empty
data: {}

# wait
data: { mode: human, waiting_question: "?", max_wait_seconds: 86400 }
data: { mode: timed, duration_seconds: 300 }

# aggregator
data: { mode: all }   # or: mode: any
```

**Ports by node type (handle ids drawn by the canvas)**

| Node       | Inputs | Outputs       |
|------------|--------|---------------|
| trigger    | —      | `out`         |
| agent      | `in`   | `out`         |
| decision   | `in`   | `yes`, `no`   |
| wait       | `in`   | `out`         |
| aggregator | `in` (N edges allowed) | `out` |

**Decision condition grammar:** `<var> == "x"`, `<var> != "x"`, `<var> in a,b,c`
— or a regex string (matched against upstream final text) — or match a
`STATUS: <value>` marker. `condition: null` = default edge.

**Variable syntax:** `$name` / `${name}`. Root vars + upstream node outputs
(keyed by node id); upstream wins on collision; unknown placeholders survive
literally.

---

*Source modules: `backend/app/harnesses/{model,validator,executor,decision,wait,aggregator,interpolate,brief_composer,run_trigger,cron,triggers,store}.py`,
`backend/app/api/harnesses.py`, `backend/app/api/harness_runs.py`, and the
frontend `frontend/src/pages/HarnessEditor.tsx` + `frontend/src/components/harness/*`.*
