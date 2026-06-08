---
agent_mode: auto
agent_model: sonnet
claude_session_id: null
created_at: '2026-06-07T10:49:05Z'
depends_on:
- 2026-06-07-1049-backend-features-audit
- 2026-06-07-1049-frontend-ux-wiring-audit
- 2026-06-07-1049-test-coverage-audit
feature_key: null
feature_state: null
id: 2026-06-07-1049-synthesize-create-refactoring-goals
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1049-features-fixes-deep-qa-review
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: Synthesize & Create Refactoring Goals
type: task
updated_at: '2026-06-07T10:49:05Z'
waiting_question: null
---

# Brief

Read the three audit reports produced by the sibling tasks, synthesize the findings
into focused refactoring goals, and create those goals in the Cronos board via the API.

## Input files

Read all three audit reports:
- `/data/spaces/cronos-development/.cronos/qa/features-backend-audit.md`
- `/data/spaces/cronos-development/.cronos/qa/features-frontend-audit.md`
- `/data/spaces/cronos-development/.cronos/qa/features-test-audit.md`

## Synthesis guidance

Group findings into cohesive refactoring goals. Each goal should:
- Have a single clear scope (don't mix backend storage bugs with frontend UX)
- Be independently deliverable (no circular deps between refactoring goals)
- Represent ~1–5 days of focused implementation work

Suggested grouping (adjust based on actual audit findings):

**Group 1 — Critical Bug Fixes** (backend bugs that break production)
  → One goal, high priority (1–2), contains a small number of focused bug-fix tasks

**Group 2 — Feature Detail View** (missing frontend panel + API wiring)
  → One CC-v1 pipeline goal (scout → analyst → architect → impl → test → review → doc)
  → Scope: detail modal/panel, GET /api/features/{id} wiring, edit title/brief UI

**Group 3 — Feature Card UX Improvements** (badges, waiting_question display, consistency)
  → One CC-v1 pipeline goal
  → Scope: feature_key badge, issue link, realizing count chip, shared Backlog card parity

**Group 4 — Process & Realize Workflow UX** (missing action buttons)
  → One CC-v1 pipeline goal
  → Scope: "Process" button, realize link/unlink UI, decomposition progress indicator

**Group 5 — Test Coverage Gaps** (untested critical paths)
  → One goal with test-writing tasks (no CC-v1 pipeline needed)

Only create groups with findings. Merge groups if findings are minor. Skip groups if the
audit found no issues in that area.

## Creating goals via API

Use Python (urllib only, no curl):

```python
import urllib.request, json

SPACE = "cronos-development"

def api_post(payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://backend:8000/api/tasks", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())
```

For bug-fix / test goals, use the **simple goal** structure (goal + flat tasks).
For UI/API feature goals, use the **CC-v1 pipeline structure** (goal + scout + sub-goals with
analyst → architect → impl → test → review → doc, each ending with `/pipeline-gate`).

See the create-goal skill at `.claude/skills/create-goal/SKILL.md` for the full pipeline template.

## Output

After creating all goals via API, print a summary table:

```
Goal ID | Title | Type | Priority | Child Tasks
```

Write this summary to `/data/spaces/cronos-development/.cronos/qa/refactoring-goals-created.md`.

## Acceptance

- All three audit reports read
- Findings grouped into ≥2 and ≤6 refactoring goals
- Each goal created via API with clear brief and appropriate priority
- Goals with code changes use CC-v1 pipeline structure; bug-fix/test goals use simple structure
- Summary written to the output file

Then run /task-finalize

# History
