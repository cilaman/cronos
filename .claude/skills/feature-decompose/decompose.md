# Feature Decompose -- Step-by-Step Runbook

This runbook is the detailed procedure referenced by `SKILL.md`. Execute every step in
order. Do not skip steps; each has a rationale tied to the feature-sync contract.

## Prerequisites

- You have been invoked with `Use the feature-decompose skill` in the prompt.
- The prompt contains a `realizes=<feature_id>` argument identifying the feature.
- The Cronos backend is reachable at `http://backend:8000`.

## Step 1 -- Read the feature task

```python
import urllib.request, json, re, sys

FEATURE_ID = "<feature_id from prompt>"   # e.g. 2026-06-03-1631-add-csv-export

def api_get(path):
    with urllib.request.urlopen(f"http://backend:8000{path}") as r:
        return json.loads(r.read())

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

feature = api_get(f"/api/features/{FEATURE_ID}")
SPACE_ID  = feature["space_id"]
TITLE     = feature["title"]
BRIEF     = feature["brief"]
print(f"Feature: {FEATURE_ID}")
print(f"Space:   {SPACE_ID}")
print(f"Title:   {TITLE}")
```

**Failure condition**: if the GET returns 404 or the task `type` is not `feature` or `fix`,
emit `STATUS:BLOCKED cannot find feature {feature_id}` and stop.

## Step 2 -- Check for existing realizes link

```python
existing_items = feature.get("realizing_items", [])
if existing_items:
    # A realizes link already exists -- do not create a duplicate goal.
    print(f"STATUS:BLOCKED feature {FEATURE_ID} already has {len(existing_items)} realizing item(s); decomposition skipped to avoid duplication")
    sys.exit(0)
```

## Step 3 -- Analyze the brief and design the goal structure

Read `BRIEF` carefully. Identify:

1. **What** must be built (the product outcome).
2. **Scope**: which files/modules/APIs are involved.
3. **Decomposition**: how to split the work into sequential or parallel child tasks.

For simple features (single-file changes, one clear unit of work):
- One root goal, 2-4 child tasks.

For features requiring multiple layers (backend + API + tests):
- One root goal, tasks ordered backend to API to tests (each depends_on prior).

For significant new functionality spanning multiple slices:
- Consider using [[create-goal]] feature-goal structure (sub-goals per slice).
- But keep it simple unless the feature genuinely needs multiple sub-goals.

**If the brief is too vague to decompose** (no clear outcome, no scope, conflicting
requirements): emit `STATUS:WAIT What does <feature title> need to accomplish? Please
clarify: <specific question>` and stop.

**If the feature is self-contradictory or impossible**: emit
`STATUS:BLOCKED <reason>` and stop.

## Step 4 -- POST the root goal

```python
goal_brief = (
    f"Implements feature: {TITLE}\n\n"
    f"## Context\n\n{BRIEF}\n\n"
    "## Implementation plan\n\n"
    "<write implementation plan here: list child tasks and their purpose>\n\n"
    "## Acceptance\n\n"
    "- All child tasks complete.\n"
    "- Feature transitions to DONE when branch is merged.\n"
)

goal = api_post("/api/tasks", {
    "space_id": SPACE_ID,
    "title": f"Implement: {TITLE}",
    "brief": goal_brief,
    "type": "goal",
    "priority": 2,
    "agent_mode": "auto",
    "agent_model": "default",
})
GOAL_ID = goal["id"]
print(f"Created root goal: {GOAL_ID}")
```

## Step 5 -- Set the realizes link (MANDATORY before child tasks)

This step is the critical ordering constraint. The `realizes` link MUST be established
before any child task is created. This prevents a race condition where a child task
finishes before the link exists and `feature_sync.propagate_to_feature` fires
done-detection on an empty realizing set.

```python
api_patch(f"/api/features/{FEATURE_ID}/realize", {
    "item_id": GOAL_ID,
    "feature_id": FEATURE_ID,
})
print(f"Set realizes: {GOAL_ID} realizes {FEATURE_ID}")
```

**Failure condition**: if this PATCH fails (4xx/5xx), emit
`STATUS:BLOCKED failed to set realizes link on {GOAL_ID}: <HTTP error>` and stop.
Do NOT create any child tasks if this step fails.

## Step 6 -- POST child tasks in dependency order

Post each child task. Use `depends_on` to enforce sequential execution where needed.

```python
task_ids = {}

def create_task(key, title, brief, depends_on_keys=None, model="default"):
    deps = [task_ids[k] for k in (depends_on_keys or [])]
    t = api_post("/api/tasks", {
        "space_id": SPACE_ID,
        "title": title,
        "brief": brief,
        "type": "task",
        "parent_id": GOAL_ID,
        "depends_on": deps,
        "priority": 2,
        "agent_mode": "auto",
        "agent_model": model,
    })
    task_ids[key] = t["id"]
    print(f"  Created task [{key}]: {t['id']} -- {title}")
    return t

# Example for a backend + test feature:
create_task("impl",  "Implement <feature name>",  "<detailed implementation brief>")
create_task("tests", "Write tests for <feature>", "<test brief>", depends_on_keys=["impl"])
```

**Failure condition**: if any POST returns 4xx/5xx, emit
`STATUS:BLOCKED failed to create child task '<title>': <HTTP error>` and stop.

## Step 7 -- Emit STATUS:DONE

```python
print(f"Decomposed feature {FEATURE_ID} into goal {GOAL_ID} with {len(task_ids)} child tasks.")
print("STATUS:DONE")
```

## Summary of mandatory ordering

```
GET /api/features/{feature_id}           <- read feature
POST /api/tasks (type=goal)              <- create root goal -> get GOAL_ID
PATCH /api/features/{feature_id}/realize <- set realizes (BEFORE child tasks!)
POST /api/tasks (type=task) x N          <- create child tasks
STATUS:DONE
```

**Never** reorder step 5 (realize PATCH) to after step 6 (child task creation).
The done-detection guard in `feature_sync.propagate_to_feature` requires the
`realizing_items` list to be non-empty before any child terminal transition fires.

## Failure mode quick reference

| When | Emit |
|------|------|
| Feature not found (404) | `STATUS:BLOCKED cannot find feature {id}` |
| Already has realizing goal | `STATUS:BLOCKED already realized; skipping` |
| Brief too vague | `STATUS:WAIT <specific clarifying question>` |
| Incoherent/impossible brief | `STATUS:BLOCKED <reason>` |
| Goal POST fails | `STATUS:BLOCKED failed to create root goal: <error>` |
| Realize PATCH fails | `STATUS:BLOCKED failed to set realizes link: <error>` |
| Child task POST fails | `STATUS:BLOCKED failed to create task '<title>': <error>` |
| Success | `STATUS:DONE` |
