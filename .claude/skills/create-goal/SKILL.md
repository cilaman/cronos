---
name: create-goal
description: Create a Cronos goal with child tasks via the backend API. Use when asked to prepare a goal, set up a feature goal, or organize a set of tasks under a goal in the Cronos board.
license: Internal — Cronos project.
---

# Create Goal

Creates a goal and its child tasks in the Cronos task board by POSTing to the backend API. Works from any workspace container — authenticate using the `CRONOS_INTERNAL_TOKEN` environment variable as a Bearer token.

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
| `type` | string | yes | `"goal"` for the parent/sub-goals, `"task"` for leaf tasks |
| `parent_id` | string | child tasks/goals only | The parent's `id` returned from the prior POST |
| `depends_on` | list[str] | no | IDs of tasks that must complete first |
| `priority` | int | no | 1–5, default 3. Use 2 for normal dev work |
| `agent_mode` | string | no | `"auto"` (default), `"plan"`, or `"ask"` |
| `agent_model` | string | no | `"default"`, `"sonnet"`, `"opus"`, `"haiku"` |

## Choosing a goal structure (coordination/ops only)

### Simple goal (coordination / ops tasks)

Use flat child tasks when the goal is purely organizational — e.g. a release checklist, a migration runbook, a set of independent fixes. Each child task is a leaf with a detailed brief an agent can execute directly.

```
Goal
├── Task A
├── Task B
└── Task C
```


## Procedure — simple goal

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
curl -s -H "Authorization: Bearer $CRONOS_INTERNAL_TOKEN" "http://backend:8000/api/tasks?space_id=cronos-development" \
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

## Writing good briefs

- **Goal brief**: motivation, background, list of sub-goal/task names.
- **Task brief**: exact file paths, line numbers, code snippets for every change; Acceptance section with testable criteria. The executing agent must not need to do additional research.
- **Dependencies**: `"depends_on": ["<task-id>"]`. For sequential sub-goals, set `depends_on` on the **sub-goal itself** (not on its children) to enforce execution order via `_topo_children`.
- **Model**: pick `"agent_model"` per task complexity — `"opus"` for heavy design/review work, `"haiku"` for light research/doc work, `"sonnet"` otherwise.

### Git workflow for development goals

A root-level development goal that delivers code changes to the git repository uses a **single shared feature branch** for its entire goal tree:

- The feature branch is named `feature/<root-goal-slug>` (slug = goal ID with the `YYYY-MM-DD-HHMM-` prefix stripped). Sub-goals **do not** create their own branches — they all share the root's branch.
- The **first code-modifying task** in the goal tree runs `/goal-branch-setup` to create and check out this branch.
- **Every code-changing task** ends with `/goal-task-commit`, which pushes to `feature/<root-goal-slug>` regardless of how deeply the task is nested under sub-goals.
- The **final integration task** of the root goal runs `/goal-finalize`, which rebases onto `main`, merges with `--no-ff`, pushes, and then deletes the feature branch locally and on origin.
- Non-development goals (planning, analysis, research) need no branch — skip the git skills entirely.
