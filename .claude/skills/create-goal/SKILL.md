---
name: create-goal
description: Create a Cronos goal with child tasks via the backend API. Use when asked to prepare a goal, set up a feature goal, or organize a set of tasks under a goal in the Cronos board.
license: Internal — Cronos project.
---

# Create Goal

Creates a goal and its child tasks in the Cronos task board by POSTing to the backend API. Works from any workspace container — no auth needed on the internal port.

## API

```
POST http://backend:8000/api/tasks
Content-Type: application/json
```

The backend is always reachable at `http://backend:8000` from inside a Cronos workspace. **Do not write task files directly to disk** — the file watcher does not propagate new files across containers reliably; always use the API.

## Field reference

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `space_id` | string | yes | e.g. `"cronos-development"` |
| `title` | string | yes | Short imperative title |
| `brief` | string | yes | Markdown — include what, why, and acceptance criteria |
| `type` | string | yes | `"goal"` for the parent, `"task"` for child tasks |
| `parent_id` | string | child tasks only | The goal's `id` returned from the first POST |
| `priority` | int | no | 1–5, default 3. Use 2 for normal dev work |
| `agent_mode` | string | no | `"auto"` (default), `"plan"`, or `"ask"` |
| `agent_model` | string | no | `"default"`, `"sonnet"`, `"opus"`, `"haiku"` |

## Procedure

Use Python (not curl) — shell quoting breaks on multi-line briefs.

```python
import urllib.request, json

def api_post(payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://backend:8000/api/tasks",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# 1. Create the goal
goal = api_post({
    "space_id": "cronos-development",
    "title": "Your goal title",
    "brief": """What this goal achieves and why.

## Child tasks

1. First task description
2. Second task description""",
    "type": "goal",
    "priority": 2,
    "agent_mode": "auto",
})
GOAL_ID = goal["id"]
print(f"Goal: {GOAL_ID}")

# 2. Create child tasks
for t in [
    {"title": "First task", "brief": "What to do.\n\n## Acceptance\n\n- ..."},
    {"title": "Second task", "brief": "What to do.\n\n## Acceptance\n\n- ..."},
]:
    t.update({"space_id": "cronos-development", "type": "task",
               "parent_id": GOAL_ID, "priority": 2, "agent_mode": "auto"})
    r = api_post(t)
    print(f"  Task: {r['id']} -- {r['title']}")
```

## Verify

```bash
curl -s "http://backend:8000/api/tasks?space_id=cronos-development" \
  | python3 -c "
import sys, json
for t in json.load(sys.stdin).get('backlog', []):
    print(('  ' if t.get('parent_id') else '') + f\"[{t['type']}] {t['id']}  {t['title']}\")
"
```

## Writing good briefs

- **Goal brief**: motivation, background, list of child task names.
- **Task brief**: exact file paths, line numbers, code snippets for every change; Acceptance section with testable criteria. The executing agent must not need to do additional research.
- **Dependencies**: add `"depends_on": ["<task-A-id>"]` to a task that must wait for another.
- **Model**: `"agent_model": "opus"` for tasks requiring deep reasoning; `"default"` for mechanical changes.
