---
name: goal-branch-setup
description: Prepare a git feature branch for a goal. Run as the first action in the first developing task of a goal. Creates feature/ROOT-GOAL-SLUG from main and checks it out in the current worktree so all task commits across the goal tree land on the shared feature branch.
license: Internal — Cronos project.
---

# Goal Branch Setup

This skill prepares a dedicated git feature branch for the **root** goal of a goal tree. All tasks under that root goal — including any sub-goals — commit to this single branch; it is merged to `main` only after the root goal passes final testing via `/goal-finalize`.

## When to use

Run as the **first action** in any task that:
1. Has a `parent_id` (i.e. is part of a goal tree, possibly via a sub-goal), AND
2. Will make code changes (i.e. is a *development* task).

This must be the first action in the **first eligible task** of a goal tree. Later tasks in the same tree — whether direct children of the root or descendants under a sub-goal — will find the branch already set up and simply check it out.

The feature branch is named after the **root** goal of the tree, never an intermediate sub-goal. Sub-goals do **not** create their own branches; they resolve the same `feature/<root-goal-slug>` and check it out.

Only run for *development* goals that deliver changes to the git repository. Planning/analysis-only goals need no branch.

## Canonical root-goal resolution

All three git skills (`goal-branch-setup`, `goal-task-commit`, `goal-finalize`) use this exact snippet to walk the `parent_id` chain up to the topmost goal, so they stay consistent. Copy it verbatim — do not paraphrase.

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

## Step-by-step procedure

### Step 1: Resolve the root-goal ID and feature branch name

```bash
# Task ID is the last path segment of the current working directory
TASK_ID=$(basename "$PWD")
```

Run the canonical resolver to find the topmost goal in the parent chain:

```bash
read ROOT_GOAL_ID ROOT_GOAL_SLUG <<EOF
$(python3 - "$TASK_ID" <<'PY'
import sys, urllib.request, json, re
def _get_task(tid):
    with urllib.request.urlopen(f"http://backend:8000/api/tasks/{tid}") as r:
        return json.loads(r.read())
def resolve_root_goal(task_id):
    node, root = _get_task(task_id), None
    while node.get("parent_id"):
        node = _get_task(node["parent_id"])
        root = node
    if root is None:
        return None, None
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-\d{4}-", "", root["id"])
    return root["id"], slug
rid, rslug = resolve_root_goal(sys.argv[1])
print(rid or "", rslug or "")
PY
)
EOF
```

If `ROOT_GOAL_ID` is empty (the resolver returned `(None, None)`), this task is **standalone** — it has no parent goal at all — so skip this skill entirely.

```bash
FEATURE_BRANCH="feature/${ROOT_GOAL_SLUG}"
SPACE_DIR="/data/spaces/cronos-development"
```

**Example**: root goal ID `2026-05-26-2100-git-workflow-skills` → branch `feature/git-workflow-skills`. A sub-goal task whose immediate parent is a sub-goal `2026-05-27-0900-some-subgoal` (itself a child of the above root) **still** resolves to `feature/git-workflow-skills`.

### Step 2: Fetch and create or retrieve the feature branch

```bash
# Fetch latest refs from origin
git -C "$SPACE_DIR" fetch origin --prune

# Check whether the feature branch exists on origin
if git -C "$SPACE_DIR" show-ref --verify --quiet "refs/remotes/origin/${FEATURE_BRANCH}"; then
    # Branch exists on origin — ensure a local tracking branch is present
    git -C "$SPACE_DIR" branch --track "${FEATURE_BRANCH}" "origin/${FEATURE_BRANCH}" 2>/dev/null || true
    echo "Using existing feature branch ${FEATURE_BRANCH} from origin"
else
    # Detect the default integration branch (main / master)
    DEFAULT_BRANCH=$(git -C "$SPACE_DIR" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null \
        | sed 's|refs/remotes/origin/||' || echo "main")
    # Create the feature branch from the latest default branch
    git -C "$SPACE_DIR" branch "${FEATURE_BRANCH}" "origin/${DEFAULT_BRANCH}"
    echo "Created feature branch ${FEATURE_BRANCH} from origin/${DEFAULT_BRANCH}"
fi
```

### Step 3: Check out the feature branch in this worktree

The worktree was created on `cronos/TASK-ID`. Switch it to the shared feature branch so your commits go there instead.

```bash
git checkout "${FEATURE_BRANCH}"
```

### Step 4: Verify

```bash
git branch --show-current   # should print feature/ROOT-GOAL-SLUG
git log --oneline -5        # should show main history (and any prior goal-task commits)
```

You are now on `feature/ROOT-GOAL-SLUG`. Make your code changes normally — commits here will accumulate across **all** tasks (and sub-goal tasks) in this root goal tree.

## Branch naming convention

| Root goal ID | Feature branch |
|---------|---------------|
| `2026-05-26-2100-git-workflow-skills` | `feature/git-workflow-skills` |
| `2026-05-25-0705-arc-4-autonomous-todo-autopilot` | `feature/arc-4-autonomous-todo-autopilot` |
| `2026-05-24-1838-arc-2-tree-and-views` | `feature/arc-2-tree-and-views` |

## Notes

- Run **before** any code changes — the whole point is that the first edit goes to the right branch.
- The feature branch is always named after the **root** goal. Sub-goals do **not** create their own branch — every task under the root, no matter how deeply nested, resolves to and checks out the same `feature/<root-goal-slug>`.
- Only run for *development* goals that deliver changes to the git repository. Planning/analysis-only goals need no branch.
- Standalone tasks (no `parent_id`, returning `(None, None)` from the resolver) are explicitly skipped.
- If a later task in the same goal tree runs this skill, it will simply check out the existing branch (step 2 takes the `exists on origin` path). That is correct and safe.
- Do **not** push the empty branch until there are commits (use `/goal-task-commit` for pushing).
- The `cronos/TASK-ID` branch that the worktree was originally on still exists; switching the worktree does not delete it.
