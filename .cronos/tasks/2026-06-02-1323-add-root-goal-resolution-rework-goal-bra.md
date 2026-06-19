---
agent_mode: auto
agent_model: opus
claude_session_id: 5715a2e5-4428-42c4-9c07-bc81c151209b
created_at: '2026-06-02T13:23:30Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-02-1323-add-root-goal-resolution-rework-goal-bra
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-02-1322-standardise-git-feature-branch-lifecycle
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Add root-goal resolution + rework goal-branch-setup
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

Make `goal-branch-setup` resolve the feature branch from the **root** goal, not the immediate parent.

## File
`.claude/skills/goal-branch-setup/SKILL.md`

## Changes

1. **Add a canonical root-goal resolution helper** as a new section near the top of the procedure. Use exactly this snippet (all three git skills will copy it verbatim so they stay consistent):

```python
# Canonical root-goal resolution — walk the parent_id chain to the TOPMOST goal.
import urllib.request, json
def _get_task(tid):
    with urllib.request.urlopen(f"http://backend:8000/api/tasks/{tid}") as r:
        return json.loads(r.read())
def resolve_root_goal(task_id):
    """Return (root_goal_id, root_goal_slug) or (None, None) if the task is standalone."""
    node, root = _get_task(task_id), None
    while node.get("parent_id"):
        node = _get_task(node["parent_id"])
        root = node
    if root is None:
        return None, None
    import re
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-\d{4}-", "", root["id"])
    return root["id"], slug
```

2. **Replace Step 1** (currently derives `GOAL_SLUG` from the immediate `parent_id` via `sed`). Instead:
   - `TASK_ID=$(basename "$PWD")`
   - call `resolve_root_goal(TASK_ID)` to get `ROOT_GOAL_ID` and the slug.
   - `FEATURE_BRANCH="feature/<root-goal-slug>"`.
   - If `resolve_root_goal` returns `(None, None)` the task is standalone → skip the skill entirely.

3. **Clarify root-vs-sub-goal behaviour** in the "When to use" and "Notes" sections:
   - The feature branch is named after the **root** goal. Sub-goals do NOT create their own branch — they resolve the same `feature/<root-goal-slug>` and check it out.
   - Add a sentence: "Only run for *development* goals that deliver changes to the git repository. Planning/analysis-only goals need no branch."

4. Keep Steps 2–4 (fetch / create-or-retrieve / checkout / verify) but ensure they use the root-derived `FEATURE_BRANCH`.

## Acceptance
- The skill resolves the branch from the topmost goal in the parent chain.
- A sub-goal task and a root-goal task in the same goal tree both land on the identical `feature/<root-goal-slug>` branch.
- Standalone tasks (no parent) are explicitly skipped.
- The resolution snippet is present verbatim so tasks 2 and 3 can reuse it.

This is a markdown-only edit; commit the skill file via the goal feature-branch workflow.

# History

```
2026-06-02T13:58:30Z [agent]
This is the first task in the goal, so I need to set up the feature branch first, then edit the skill file.

Feature branch is ready. Now I'll edit the SKILL.md file per the brief.

Let me verify the resolver snippet stays exact (no escape mangling).

Workspace is now on the feature branch. Let me commit via the goal-task-commit skill.

This is a markdown-only change to a skill file — no code tests are relevant. Proceeding to commit.

Commit pushed. Now finalizing the task.

All brief requirements met: canonical resolver snippet present verbatim, Step 1 reworked to use it, sub-goal vs root-goal behavior clarified, standalone tasks explicitly skipped, Steps 2–4 use root-derived FEATURE_BRANCH. Already committed (`89c5eb0`) and pushed via goal-task-commit.

MEMORY[fact]: `.claude/skills/goal-branch-setup/SKILL.md` reworked (commit `89c5eb0` on `feature/standardise-git-feature-branch-lifecycle`) to resolve the feature branch from the **root** goal via canonical `resolve_root_goal(task_id)` Python helper that walks `parent_id` chain through `GET http://backend:8000/api/tasks/{id}`. Step 1 now calls the resolver instead of reading immediate `parent_id`; returns `(None, None)` for standalone tasks → skill skipped. Snippet block (lines 27-44) is verbatim so tasks 2 and 3 of goal `2026-06-02-1322-standardise-git-feature-branch-lifecycle` can paste-copy it into `goal-task-commit` and `goal-finalize`.

MEMORY[observation]: A sub-goal task whose immediate parent is itself a sub-goal must still resolve to `feature/<root-goal-slug>`. The reworked goal-branch-setup achieves this by walking the chain until `parent_id` is null; the resulting root goal id has its `YYYY-MM-DD-HHMM-` prefix stripped via `re.sub(r"^\d{4}-\d{2}-\d{2}-\d{4}-", "", root["id"])`. Planning/analysis-only goals are excluded from the skill by the explicit "Only run for development goals that deliver changes to the git repository" guard in the When-to-use section.

STATUS: DONE
```
