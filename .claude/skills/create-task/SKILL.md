---
name: create-task
description: Create a single Cronos task via the backend API. Use when asked to add a task, create a ticket, or add a work item to the Cronos board (without creating a full goal structure).
license: Internal — Cronos project.
---

# Create Task

Creates a single task in the Cronos task board by POSTing to the backend API. For creating a goal with multiple child tasks, use `/create-goal` instead.

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
| `type` | string | no | `"task"` (default), `"goal"`, or `"issue"` |
| `parent_id` | string | no | ID of a goal this task belongs to |
| `depends_on` | array | no | List of task IDs that must complete first |
| `priority` | int | no | 1–5, default 3. Use 2 for normal dev work |
| `agent_mode` | string | no | `"auto"` (default), `"plan"`, or `"ask"` |
| `agent_model` | string | no | `"default"`, `"sonnet"`, `"opus"`, `"haiku"` |

## Procedure

Use Python (not curl) — shell quoting breaks on multi-line briefs.

```python
import urllib.request, json

payload = {
    "space_id": "cronos-development",
    "title": "Your task title here",
    "brief": """Describe what needs to be done and why.

## Acceptance

- Criterion one.
- Criterion two.""",
    "type": "task",
    "priority": 2,
    "agent_mode": "auto",
    # Optional fields:
    # "parent_id": "2026-05-29-1642-some-goal-id",
    # "depends_on": ["2026-05-29-1645-some-other-task"],
    # "agent_model": "opus",
}

data = json.dumps(payload).encode()
req = urllib.request.Request(
    "http://backend:8000/api/tasks",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req) as resp:
    task = json.loads(resp.read())

print(f"Created: {task['id']} -- {task['title']}")
```

## Verify

```bash
curl -s "http://backend:8000/api/tasks?space_id=cronos-development" \
  | python3 -c "
import sys, json
for t in json.load(sys.stdin).get('backlog', []):
    print(f\"[{t['type']}] {t['id']}  {t['title']}\")
"
```

## Tips for good briefs

- Include exact file paths and line numbers for every change required.
- Add an **Acceptance** section with testable criteria so the executing agent has no ambiguity.
- Use `"agent_model": "opus"` for tasks requiring deep reasoning; `"default"` or `"sonnet"` for mechanical changes.
- Use `"agent_mode": "plan"` for tasks where you want the agent to show a plan before executing.
- If this task depends on another completing first, pass `"depends_on": ["<task-id>"]`.
