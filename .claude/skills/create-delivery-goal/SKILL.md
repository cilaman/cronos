---
name: create-delivery-goal
description: Create a Cronos delivery goal that binds to the delivery workflow runner. Use when creating a goal that should be orchestrated by the delivery-workflow runner (not a coordination/ops goal). Do NOT pre-create phase tasks — the runner creates them from the workflow spec.
license: Internal — Cronos project.
---

# Create Delivery Goal

Creates a single delivery goal on the Cronos board by POSTing to the backend API with a `<!-- delivery-workflow: {spec_path} -->` sentinel in the brief. The sentinel causes the Cronos worker to invoke the delivery-workflow runner instead of the normal sub-task execution path — **do not pre-create scout/analyst/architect/impl/test/review/doc tasks**.

## When to use

Use this skill when:
- You are creating a goal that should be driven by the delivery-workflow runner (e.g. a multi-phase delivery pipeline for a feature or fix).
- The workflow spec exists at a known path (default: `packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml`).

Use `/create-goal` instead for:
- Coordination / ops goals (release checklists, migration runbooks, ad-hoc fix groups).
- Goals with manually-managed child tasks.

## Sentinel format

The delivery-workflow sentinel is a single HTML comment line embedded anywhere in the goal brief:

```
<!-- delivery-workflow: packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml -->
```

The sentinel must appear on its own line. `spec_path` is relative to the space root. The canonical delivery workflow spec is `packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml`; override this only when the space ships a custom workflow.

**Do NOT pre-create** scout / analyst / architect / impl / test / review / doc tasks — the runner reads `delivery.workflow.yaml` and creates child tasks itself. Pre-created tasks will race the runner and produce duplicate work.

## API

```
POST http://backend:8000/api/tasks
Content-Type: application/json
```

The backend is always reachable at `http://backend:8000` from inside a Cronos workspace. Authenticate using the `CRONOS_INTERNAL_TOKEN` environment variable as a Bearer token.

## Field reference

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `space_id` | string | yes | e.g. `"cronos-development"` |
| `title` | string | yes | Short imperative title |
| `brief` | string | yes | Markdown + sentinel line — see Procedure |
| `type` | string | yes | `"goal"` |
| `priority` | int | no | 1–5, default 3. Use 2 for normal dev work |
| `agent_mode` | string | no | `"auto"` (default) |
| `agent_model` | string | no | `"default"`, `"sonnet"`, `"opus"`, `"haiku"` |

## Procedure

Use Python (not curl) — shell quoting breaks on multi-line briefs.

```python
import os
import urllib.request, json

def api_post(payload: dict) -> dict:
    data = json.dumps(payload).encode()
    token = os.environ.get("CRONOS_INTERNAL_TOKEN", "")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        "http://backend:8000/api/tasks",
        data=data,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# Create the delivery goal (no child tasks — the runner handles them)
goal = api_post({
    "space_id": "cronos-development",
    "title": "My Delivery Goal",
    "brief": """What this goal achieves and why.

## Scope

- file_a.py — describe the change
- file_b.tsx — describe the change

<!-- delivery-workflow: packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml -->""",
    "type": "goal",
    "priority": 2,
    "agent_mode": "auto",
})
GOAL_ID = goal["id"]
print(f"Delivery goal created: {GOAL_ID}")
# Do NOT create child tasks. The runner will create them from the workflow spec.
```

## Verify

After running the script, check that exactly one goal was created and no child tasks exist yet:

```bash
curl -s -H "Authorization: Bearer $CRONOS_INTERNAL_TOKEN" \
  "http://backend:8000/api/tasks?space_id=cronos-development" \
  | python3 -c "
import sys, json
tasks = json.load(sys.stdin)
for lane in tasks.values():
    if not isinstance(lane, list): continue
    for t in lane:
        indent = '  ' if t.get('parent_id') else ''
        print(indent + f\"[{t['type']}] {t['id']}  {t['title']}\")
"
```

Expected output: **1 goal, 0 child tasks** (the runner creates child tasks when it first processes the goal).
