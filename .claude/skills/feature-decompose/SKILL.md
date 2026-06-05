---
name: feature-decompose
description: Decomposes a Cronos feature or fix task into a realizing goal with child tasks. Called by the worker when a feature/fix task enters PROCESSING state. Reads the feature brief, designs a goal structure, POSTs the root goal + child tasks via the Cronos API, and links the goal to the feature via the realizes relationship BEFORE creating any child tasks.
license: Internal — Cronos project.
---

# Feature Decompose

This skill is invoked by `worker._run_feature_decompose` when a `feature` or `fix` task
reaches `feature_state=PROCESSING`. It turns the feature brief into a concrete Cronos goal
with ordered child tasks and links that goal back to the originating feature via the
`realizes` relationship.

## When to use

Invoke this skill when:
1. You are executing a Cronos feature or fix task in PROCESSING state, AND
2. The task brief describes what needs to be built (product scope), AND
3. You need to translate that product scope into an actionable implementation goal.

Do **NOT** invoke it for plain goals (type=goal) or tasks that already have a realizing
goal. Do not invoke it to plan pipeline phases — for that use [[pipeline-scaffold]].

## Inputs

The calling worker passes two pieces of context via the agent prompt:

| Input | Source | Notes |
|---|---|---|
| `feature_id` | Passed as the `realizes` argument in the agent prompt | ID of the feature/fix task to link (e.g. `2026-06-03-1631-some-feature`). |
| `feature_brief` | Read from `GET /api/features/{feature_id}` | Full task brief — product description, acceptance criteria, scope hints. |

The invoking prompt will contain the literal text `Use the feature-decompose skill` and
supply the `feature_id` as the `realizes` argument so you can identify the feature.

## What it produces

1. **A root goal** (`type=goal`) with a title derived from the feature title and a detailed
   brief describing the implementation approach.
2. **The `realizes` link** — established BEFORE any child task is created (race condition
   mitigation: done-detection in `feature_sync.propagate_to_feature` skips PLANNED to DONE
   when the realizing set is empty, so the link must exist before children are enqueued).
3. **Child tasks** (`type=task`) under the root goal, each with:
   - Clear title and implementation brief.
   - `depends_on` wired in topological order.
   - Appropriate `agent_model` and `agent_mode`.
4. **STATUS:DONE** on success; **STATUS:WAIT** or **STATUS:BLOCKED** on failure.

## Procedure

Full step-by-step runbook is in [[decompose.md]].

Summary:

1. Read the feature task from the API (`GET /api/features/{feature_id}`).
2. Analyze the brief: identify scope, design a goal + child tasks structure.
3. POST the root goal (`POST /api/tasks` with `type=goal`, `space_id` from the feature).
4. **IMMEDIATELY** call `PATCH /api/features/{feature_id}/realize` with `item_id=<root_goal_id>`
   to establish the `realizes` link BEFORE creating any child tasks. This ordering is
   mandatory per design (I9 race condition mitigation).
5. POST each child task under the root goal in dependency order.
6. Emit `STATUS:DONE`.

## Failure modes

| Condition | Status | Rationale |
|---|---|---|
| Feature brief too vague to decompose | `STATUS:WAIT` | Need human clarification; surface question in output |
| Feature is a duplicate of an existing realizing goal | `STATUS:BLOCKED` | Incoherent — cannot create a duplicate realizing goal |
| Feature brief is self-contradictory or impossible | `STATUS:BLOCKED` | Incoherent scope; log reason |
| Backend API returns 4xx/5xx on any POST | `STATUS:BLOCKED` | Infrastructure failure; log HTTP status + response body |
| `PATCH /api/features/{feature_id}/realize` fails | `STATUS:BLOCKED` | Cannot establish realizes link; do NOT create child tasks |

## API contract

All API calls use `http://backend:8000` (reachable from any Cronos workspace container).
Use Python `urllib.request` — not `curl` (shell quoting breaks on multi-line briefs).

### Read the feature

```python
import urllib.request, json

def api_get(path):
    with urllib.request.urlopen(f"http://backend:8000{path}") as r:
        return json.loads(r.read())

feature = api_get(f"/api/features/{feature_id}")
space_id = feature["space_id"]
title    = feature["title"]
brief    = feature["brief"]
```

### POST the root goal

```python
def api_post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"http://backend:8000{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

goal = api_post("/api/tasks", {
    "space_id": space_id,
    "title": f"Implement: {title}",
    "brief": goal_brief,   # composed from feature brief + implementation plan
    "type": "goal",
    "priority": 2,
    "agent_mode": "auto",
    "agent_model": "default",
})
goal_id = goal["id"]
```

### Set the realizes link — BEFORE child tasks

```python
def api_patch(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"http://backend:8000{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# MANDATORY: set realizes link before creating any child tasks
api_patch(f"/api/features/{feature_id}/realize", {
    "item_id": goal_id,
    "feature_id": feature_id,
})
```

### POST child tasks

```python
task_ids = {}
for task_spec in child_tasks:   # ordered by depends_on
    t = api_post("/api/tasks", {
        "space_id": space_id,
        "title": task_spec["title"],
        "brief": task_spec["brief"],
        "type": "task",
        "parent_id": goal_id,
        "depends_on": [task_ids[dep] for dep in task_spec.get("depends_on_keys", [])],
        "priority": 2,
        "agent_mode": "auto",
        "agent_model": task_spec.get("model", "default"),
    })
    task_ids[task_spec["key"]] = t["id"]
```

## Output signals

Emit one of the following as the **last line** of output:

- `STATUS:DONE` — root goal + realizes link + all child tasks created successfully.
- `STATUS:WAIT <question>` — need human input before decomposition can proceed.
- `STATUS:BLOCKED <reason>` — feature is incoherent, duplicate, or API call failed.

The worker (`_run_feature_decompose`) reads the STATUS line to decide the next
`feature_state` transition:
- DONE + `realizing_items >= 1` → `PLANNED`
- DONE + `realizing_items == 0` → `WAITING` (anomaly; should not happen if skill ran correctly)
- WAIT → `WAITING` (question forwarded to `feature.waiting_question`)
- BLOCKED → `WAITING` (reason forwarded as `feature.waiting_question`)

## Slug derivation note

The feature branch slug (used by `feature_sync` done-detection) is derived from `feature.id`
by stripping the leading `YYYY-MM-DD-HHMM-` prefix:

```python
import re
PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}-")
slug = PREFIX_RE.sub("", feature_id) or feature_id
branch = f"feature/{slug}"
```

This regex must match the derivation in `backend/app/feature_sync.py` exactly.
