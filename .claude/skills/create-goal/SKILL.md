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
| `type` | string | yes | `"goal"` for the parent/sub-goals, `"task"` for leaf tasks |
| `parent_id` | string | child tasks/goals only | The parent's `id` returned from the prior POST |
| `depends_on` | list[str] | no | IDs of tasks that must complete first |
| `priority` | int | no | 1–5, default 3. Use 2 for normal dev work |
| `agent_mode` | string | no | `"auto"` (default), `"plan"`, or `"ask"` |
| `agent_model` | string | no | `"default"`, `"sonnet"`, `"opus"`, `"haiku"` |

## Choosing a goal structure

### Simple goal (coordination / ops tasks)

Use flat child tasks when the goal is purely organizational — e.g. a release checklist, a migration runbook, a set of independent fixes. Each child task is a leaf with a detailed brief an agent can execute directly.

```
Goal
├── Task A
├── Task B
└── Task C
```

### Feature goal (builds or changes product functionality)

When the goal delivers a feature — new UI, new API endpoint, a significant refactor — use the **CC-v1 pipeline structure**: one shared scout task at the goal level, then one sub-goal per feature slice, each containing the six pipeline phases.

```
Goal
├── Task: scout  (shared, runs first; agent_model: haiku)
├── Sub-Goal: Feature slice A
│   ├── Task: analyst   (depends_on: [scout_id];     agent_model: sonnet)
│   ├── Task: architect (depends_on: [analyst_id];   agent_model: opus)
│   ├── Task: impl      (depends_on: [architect_id]; agent_model: sonnet)
│   ├── Task: test      (depends_on: [impl_id];      agent_model: sonnet)
│   ├── Task: review    (depends_on: [test_id];      agent_model: opus)
│   └── Task: doc       (depends_on: [review_id];    agent_model: haiku)
├── Sub-Goal: Feature slice B  (analyst depends_on: [doc_id_of_A] if sequential)
│   └── analyst → architect → impl → test → review → doc
└── Sub-Goal: Feature slice C
    └── analyst → architect → impl → test → review → doc
```

**Rules:**
- One scout at goal level — never duplicate it per sub-goal (same codebase, one scan).
- Sub-goals are independent feature slices (e.g. backend endpoint, frontend component, routing).
- Do NOT create a separate "Tests" task — the `test` phase inside each sub-goal covers it.
- Sequential sub-goals: set `depends_on` on the **analyst** of slice B to point at the **doc** task of slice A.
- Each pipeline task brief must: (1) reference the scout report path, (2) name the CC-v1 agent contract file (`.claude/agents/pipeline-{agent}.md`), (3) specify the artifact output path, (4) end with `/pipeline-gate`.

## Procedure — simple goal

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

## Procedure — feature goal (CC-v1 pipeline structure)

```python
import urllib.request, json

SPACE = "cronos-development"
GOAL_SLUG = "my-feature-slug"   # kebab-case, used in artifact paths
PIPELINE_DIR = f".cronos/pipeline/{GOAL_SLUG}"

def api_post(payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://backend:8000/api/tasks", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# 1. Top-level goal
goal = api_post({
    "space_id": SPACE, "type": "goal", "priority": 2,
    "title": "My Feature Goal",
    "brief": "…motivation and list of sub-goals…",
})
GOAL_ID = goal["id"]

# 2. Shared scout (all sub-goals' analysts depend on it)
scout = api_post({
    "space_id": SPACE, "type": "task", "parent_id": GOAL_ID,
    "priority": 2, "agent_model": "haiku", "agent_mode": "auto",
    "title": f"scout – {GOAL_SLUG}",
    "brief": f"""CC-v1 scout phase. Research all files relevant to this feature.

Emit `scout-report-{GOAL_SLUG}.md` (class=research) at `{PIPELINE_DIR}/scout-report-{GOAL_SLUG}.md`.

Then run: /pipeline-gate""",
})
SCOUT_ID = scout["id"]

# 3. Sub-goals with pipeline phases
PHASES = [
    ("analyst",   "sonnet", "analyst"),
    ("architect", "opus",   "architect"),
    ("impl",      "sonnet", "implementor"),
    ("test",      "sonnet", "tester"),
    ("review",    "opus",   "reviewer"),
    ("doc",       "haiku",  "doc-sync"),
]

# Define slices; for sequential ordering, analyst of slice N+1 depends on doc of slice N
slices = [
    {"slug": "slice-a", "title": "Sub-Goal A", "brief": "…", "scope": "file_a.py, file_b.py"},
    {"slug": "slice-b", "title": "Sub-Goal B", "brief": "…", "scope": "file_c.tsx"},
]

prev_last_task_id = SCOUT_ID  # first analyst depends on scout

for sl in slices:
    sg = api_post({
        "space_id": SPACE, "type": "goal", "parent_id": GOAL_ID,
        "priority": 2, "title": sl["title"], "brief": sl["brief"],
    })
    SG_ID = sg["id"]

    prev_phase_id = prev_last_task_id
    for phase, model, agent_name in PHASES:
        t = api_post({
            "space_id": SPACE, "type": "task", "parent_id": SG_ID,
            "priority": 2, "agent_model": model, "agent_mode": "auto",
            "depends_on": [prev_phase_id],
            "title": f"{phase} – {sl['slug']}",
            "brief": f"""CC-v1 {phase} phase for: {sl['title']}.

Read scout report: `{PIPELINE_DIR}/scout-report-{GOAL_SLUG}.md`
Scope: {sl['scope']}
Agent contract: `.claude/agents/pipeline-{agent_name}.md`
Artifact: `{PIPELINE_DIR}/{phase}-report-{sl['slug']}.md`

Then run: /pipeline-gate""",
        })
        print(f"  [{sl['slug']}] {phase}: {t['id']}")
        prev_phase_id = t["id"]

    prev_last_task_id = prev_phase_id  # next slice's analyst depends on this slice's doc
```

## Verify

```bash
curl -s "http://backend:8000/api/tasks?space_id=cronos-development" \
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
- **Pipeline task brief**: always include (1) scout report path, (2) agent contract file, (3) artifact output path, (4) `/pipeline-gate` at the end.
- **Dependencies**: `"depends_on": ["<task-id>"]` — each pipeline phase depends on the prior phase.
- **Model**: `"agent_model": "opus"` for architect and reviewer; `"haiku"` for scout and doc; `"sonnet"` for analyst, impl, test.

### Git workflow for development goals

A root-level development goal that delivers code changes to the git repository uses a **single shared feature branch** for its entire goal tree:

- The feature branch is named `feature/<root-goal-slug>` (slug = goal ID with the `YYYY-MM-DD-HHMM-` prefix stripped). Sub-goals **do not** create their own branches — they all share the root's branch.
- The **first code-modifying task** in the goal tree runs `/goal-branch-setup` to create and check out this branch.
- **Every code-changing task** ends with `/goal-task-commit`, which pushes to `feature/<root-goal-slug>` regardless of how deeply the task is nested under sub-goals.
- The **final integration task** of the root goal runs `/goal-finalize`, which rebases onto `main`, merges with `--no-ff`, pushes, and then deletes the feature branch locally and on origin.
- Non-development goals (planning, analysis, research) need no branch — skip the git skills entirely.
