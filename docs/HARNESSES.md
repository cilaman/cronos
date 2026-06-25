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
6.1. [Loops on agent nodes (G3.1)](#61-loops-on-agent-nodes-g31)
7. [Connecting nodes to real agents and skills](#7-connecting-nodes-to-real-agents-and-skills)
8. [Control-flow nodes: decision, wait, aggregator](#8-control-flow-nodes)
9. [Triggers: how a harness starts](#9-triggers)
10. [Running a harness and watching it execute](#10-running-a-harness)
11. [The run lifecycle and run state](#11-the-run-lifecycle)
12. [Known limitations (read this)](#known-limitations-read-this)
13. [Troubleshooting](#13-troubleshooting)
14. [Quick reference](#14-quick-reference)

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

### Interpolation in prompts

Prompts use Python `string.Template` syntax: `$name` or `${name}`.

```yaml
variables:
  topic: "the memory subsystem"
  lang: "python"
# ...
prompt_template: "Research $topic. Write the fix in ${lang}."
```

### Scope and precedence

1. **Root variables** (`harness.variables`) form the base scope.
2. **Upstream node outputs override root variables** on key collision. After an
   agent node finishes `DONE`, its final text snippet is stored in the scope
   under the **node id**. So `$scout` in a later prompt expands to the scout
   node's final output.
3. **(G3.3) Dotted-path scope enrichment**: After an agent node emits a
   `delivery_status` block, the executor automatically adds dotted-path keys to
   the scope (e.g., `review.fields.verdict`). These are used by decision
   conditions (see [Dotted-path conditions](#dotted-path-conditions-g32)), but
   are **not** available for prompt interpolation (prompts only see flat keys).

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

## 6.1 Loops on agent nodes (G3.1)

An agent node can be configured to run in a **loop** until a convergence condition is met.
This is useful for iterative workflows (e.g., agent keeps writing code until a test passes,
or refining findings until no new issues are found).

Loop configuration goes in the `loop` sub-object of node `data`:

```yaml
data:
  agent_ref: pipeline-implementor
  prompt_template: "Fix the failing test."
  loop:
    until: "test_passing == \"true\""   # condition to exit the loop
    stall:
      - recurring_findings               # exit if findings repeat across attempts
      - no_diff_progress                 # exit if code diff size doesn't grow
    max: 5                               # backstop: max attempts (default 10)
    on_exhaust: escalate                 # what to do if max is hit (default: escalate)
```

**Loop semantics:**

When a node with `loop` configured finishes an attempt:

1. **Check convergence signals** (in order):
   - **`until` condition**: if a boolean expression evaluates to `True`, exit the loop.
     The expression uses the same dotted-path grammar as decision conditions.
   - **`stall: recurring_findings`**: parse the agent's `delivery_status.fields.finding_ids`
     list. If this attempt's findings are identical to the previous attempt's, the loop
     is considered stalled and exits.
   - **`stall: no_diff_progress`**: check `delivery_status.fields.diff_bytes`. If the
     diff size hasn't grown (current ≥ previous), the loop is stalled and exits.
   - **`max` backstop**: if `attempt >= max`, exit (this triggers `on_exhaust`).

2. **On exit**:
   - If `until` condition was met or a stall signal fired, the node completes `DONE`.
   - If `max` is exhausted, the `on_exhaust` action is taken:
     - `escalate` (default): the run is **parked in WAITING** at the node,
       and human intervention is required to unblock.

3. **Resume after restart**: the executor saves loop state (`attempt`, `prior_finding_ids`)
   to `run_state.json` after each attempt. If the process restarts, the loop resumes
   from the last recorded attempt count.

**Example**: a code reviewer that re-runs until the codebase has zero blockers:

```yaml
nodes:
  - id: review-loop
    type: agent
    label: "Iterative code review"
    data:
      agent_ref: pipeline-reviewer
      prompt_template: |
        Review the code changes. Emit a delivery_status block with
        fields: { verdict, blocker_count }.
      loop:
        until: 'review-loop.fields.blocker_count == "0"'
        stall: [recurring_findings, no_diff_progress]
        max: 8
        on_exhaust: escalate
```

The agent emits:
```
```delivery_status
{"status": "needs_fix", "fields": {"verdict": "fail", "blocker_count": 3}}
```
```
on attempt 1, attempt 2 (blocker_count = 1), attempt 3 (blocker_count = 0), and
at attempt 3 the `until` condition matches and the loop exits.

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

#### Agent completion sentinel

When an agent task finishes, the executor reads its completion status and
structured output from one of three channels (in precedence order):

1. **Structured channel (preferred — G3.3)**: a fenced `delivery_status` JSON block at the
   end of the agent's output (CC-v1 agents emit this):
   ```
   ```delivery_status
   {"status": "DONE", "fields": {"verdict": "pass", "has_ui": false}}
   ```
   ```
   - `status`: the primary signal (matching rules for decision edges).
   - `fields`: a dict of structured fields (available as dotted-path keys in scope
     for decision routing — e.g., `review.fields.verdict`).

2. **Legacy structured channel**: a fenced `cronos_status` JSON block:
   ```
   ```cronos_status
   {"status": "DONE", "summary": "Completed without errors", "artifacts": []}
   ```
   ```
   Valid `status` values: `DONE`, `WAIT`, `BLOCKED`. The `summary` field is
   human-readable; `artifacts` is optional. (Deprecated in favour of `delivery_status`.)

3. **Legacy text channel (deprecated)**: a `STATUS: DONE` line. Still supported but
   logs a warning; structured blocks are preferred.

If none is present, the run's `exit_reason` is set to `NO_CRONOS_STATUS`. See
the decision-routing section for how to drive harness control flow on these
signals.

**Scope enrichment** (G3.3 routing unblock): When an agent node reaches `DONE`
with a `delivery_status` block, the executor automatically populates dotted-path
scope keys so downstream decision nodes can reference structured output. This
enables routing on agent output without regex or custom variable manipulation.

The executor's **tools resolver** (`backend/app/worker.py:resolve_tool`) looks up
the `agent_ref` name across multiple sources:

1. **Space-scoped** (under `{space}/.claude/`):
   - Agents in `agents/` (by folder name, case-sensitive)
   - Skills in `skills/` (by folder name or flat file name)
   - Commands in `commands/` (by folder name)
   - Context in `CONTEXT.md` or `contexts/`
2. **Global scope** (under `~/.claude/`), with the same structure

Space-scoped entries **shadow** global entries if there is a name collision. The
resolver returns the first match found (in category order: agents → skills →
commands → context). If a match is found:

- **For skills**: the brief is prefixed with `/<skill-name>`, triggering the
  `claude code /skill-name` invocation.
- **For agents**: the brief starts with `Agent: <agent-name>`.

If the name is not found in either scope, the resolved entry is `None`, and the
brief falls back to `Agent: <ref>` (unchanged behavior).

---

## 8. Control-flow nodes

### Decision — pick one branch

A `decision` node evaluates its **outgoing edges** against a signal derived from
the upstream agent and follows the **first matching edge**. An edge with
`condition: null` is the **default** (fallback) edge.

Signal precedence (`decision.py`, highest first):

1. **`status` from `delivery_status` block** — a fenced-JSON block
   `` ```delivery_status\n{"status": "<value>", ...}\n``` ``
   found in the upstream node's output. The `status` field is matched case-sensitively
   against `edge.condition`. This is the **preferred structured channel** for CC-v1 agents.
2. **`status` from `cronos_status` block** — a fenced-JSON block
   `` ```cronos_status\n{"status": "<value>", ...}\n``` ``
   found in the upstream node's output. The `status` field is matched case-sensitively
   against `edge.condition`. (Deprecated in favour of `delivery_status`.)
3. **`status` from legacy `STATUS:` marker** — a `STATUS: <value>` line (deprecated).
   Matched case-sensitively. Logs a warning if found; structured blocks are preferred.
4. **`exit_reason`** — the run's exit reason string (e.g. `NO_CRONOS_STATUS` when
   no structured block or marker is present).
5. **`regex`** — `re.search(edge.condition, upstream_final_text)`. Python inline
   flags like `(?i)` are allowed. No `/pattern/flags` syntax, no `eval`.
6. **`variable`** / **dotted-path expression** — a whitelisted expression on scope variables
   (see [Dotted-path conditions](#dotted-path-conditions-g32)).

#### Dotted-path conditions (G3.2)

Condition expressions now support **dotted paths** to structured fields from upstream
`delivery_status` blocks. This enables harnesses to route on agent output without
writing custom regex.

Syntax: `<path> <op> <literal>` with optional `&&` (AND) conjunction.

- **Path**: a dotted identifier (e.g., `status`, `review.fields.verdict`,
  `my-node.status`). Hyphens in node ids are allowed (e.g., `my-node-1.fields.x`).
- **Operator**: `==`, `!=`, or `in` (right side: comma-separated values).
- **Value**: a double-quoted string, single-quoted string, or unquoted bare word.
- **Conjunction**: multiple clauses separated by ` && ` (all must hold).

**Dotted-path precedence** (when evaluating):
1. The scope is first populated with **root variables** and **upstream node outputs** (flat keys).
2. After an agent node completes with a `delivery_status` block, the executor
   **enriches the scope** with dotted-path keys:
   - `<node_id>.status` — the `status` field from the block
   - `<node_id>.fields.<name>` — one key per entry in the `fields` object

Example:

```yaml
nodes:
  - id: review
    type: agent
    label: "Code review"
    data:
      agent_ref: pipeline-reviewer
      prompt_template: "Review the code."

  - id: decide-quality
    type: decision
    # ...

edges:
  - id: e1
    source: { node_id: review, port_id: out }
    target: { node_id: decide-quality, port_id: in }
    condition: null

  # Match on the review agent's verdict field:
  - id: e2
    source: { node_id: decide-quality, port_id: yes }
    target: { node_id: ship, port_id: in }
    condition: 'review.fields.verdict == "pass"'

  # Match on review status + multiple fields:
  - id: e3
    source: { node_id: decide-quality, port_id: no }
    target: { node_id: revise, port_id: in }
    condition: 'review.status == "needs_fix" && review.fields.blocker_count in 1,2,3'
```

When the `review` agent finishes with:
```
```delivery_status
{"status": "needs_fix", "fields": {"verdict": "fail", "blocker_count": 2}}
```
```
the scope is enriched with:
- `review.status` = `"needs_fix"`
- `review.fields.verdict` = `"fail"`
- `review.fields.blocker_count` = `"2"`

and edge `e3`'s condition is evaluated to `True`.

**Backward compatibility**: Variable-condition syntax (`has_ui == "true"`) continues
to work for backward compatibility (legacy single-segment scope keys).

If no condition matches and there is no default edge, the decision **fails**
(and fail-fast kicks in) — so always provide a `condition: null` edge.

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
- **Timed wait**: the run sleeps `duration_seconds` and continues. On a process
  restart, the run resumes sleeping only the *remaining* interval and fires
  immediately if the wake time has already passed.

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

## 11. The run lifecycle and run state

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

## 12. Known limitations (read this)

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

If you'd like, items 1–5 are all fixable on the frontend side (align `config`→`data`,
`prompt`→`prompt_template`, `ports` list→dict, edge `label`→`condition`, add a
variable editor). Ask and I can scope that as a follow-up goal.

---

## 13. Troubleshooting

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
- **Run is stuck in WAITING** — either a human wait node or a loop escalation.
  For a human wait, reply to the "Harness run" task to resume (the `max_wait_seconds`
  guardrail will eventually release it if you never reply). For a loop escalation,
  the log message will indicate the reason (e.g., "recurring_findings after 5 attempts").
- **Decision raised "no matching edge and no default edge"** — add an edge with
  `condition: null` as the fallback.
- **Dotted-path condition not matching** — confirm the upstream agent emitted a
  `delivery_status` block with the expected `status` and `fields`. Check the
  agent's task output in the board to verify. Unrecognised paths silently
  evaluate to `False` (fall through to default edge).
- **Loop keeps running or stops unexpectedly** — check the `until` condition
  grammar against the emitted `delivery_status.fields` keys. The condition
  evaluator logs warnings for unrecognised paths. Also verify `stall` checks
  are configured correctly (e.g., agent must emit `finding_ids` or `diff_bytes`
  in the `fields` dict).
- **Manual edits don't show in the editor** — reload the page; the canvas is
  initialised from the harness on load.

---

## 14. Quick reference

**Node `data` cheat sheet**

```yaml
# agent (without loop)
data: { agent_ref: <name>, prompt_template: "... $var ..." }

# agent (with loop) — G3.1
data:
  agent_ref: <name>
  prompt_template: "..."
  loop:
    until: "condition"                 # optional: exit on boolean expression
    stall: [recurring_findings, no_diff_progress]  # optional: exit on stall signals
    max: 5                             # optional: max attempts (default 10)
    on_exhaust: escalate               # optional: action on max hit (default: escalate)

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

**Decision condition grammar:** 

Supports four layers (matched in precedence order):

1. **Dotted-path expression** (G3.2): `<path> <op> <literal>` with optional `&&` AND.
   - Path: `status`, `review.fields.verdict`, `my-node-1.status`
   - Op: `==`, `!=`, `in` (right side: comma-separated list for `in`)
   - Value: quoted string or bare word

   Examples: `review.fields.verdict == "pass"` or `status == "done" && has_ui == "true"`

2. **Regex**: matched against upstream final text; Python inline flags allowed.

3. **Delivery/cronos status block**: match on `{"status": "<value>", ...}` (preferred).

4. **Legacy `STATUS:` marker**: `STATUS: <value>` (deprecated).

Default edge: `condition: null` (fallback when no condition matches).

**Agent completion signals** (G3.3):

Agents should emit a `delivery_status` block (preferred) or legacy `cronos_status`:

```
```delivery_status
{"status": "DONE", "fields": {"verdict": "pass", "blocker_count": 0}}
```
```

The `status` field is matched for decision routing; `fields` are auto-enriched
as dotted-path scope keys (e.g., `agent_id.fields.verdict`).

**Variable syntax:** `$name` / `${name}`. Root vars + upstream node outputs
(keyed by node id); upstream wins on collision; unknown placeholders survive
literally. (Dotted-path scope keys are available for decision routing, not prompt
interpolation.)

---

*Source modules: `backend/app/harnesses/{model,validator,executor,decision,wait,aggregator,interpolate,brief_composer,run_trigger,cron,triggers,store}.py`,
`backend/app/api/harnesses.py`, `backend/app/api/harness_runs.py`, and the
frontend `frontend/src/pages/HarnessEditor.tsx` + `frontend/src/components/harness/*`.*
