---
name: goal-task-commit
description: Commit and push a completed task's changes to the goal's feature branch. Run after tests pass as the last step of any code-modifying task that belongs to a goal.
license: Internal — Cronos project.
---

# Goal Task Commit

This skill commits and pushes a task's code changes to the root goal's shared feature branch. It runs after tests pass, before the task is marked DONE.

## When to use

Run as the **last action** of any task in a goal that modified code, after:
1. All code changes are complete.
2. Tests pass (invoke `test-architect` to verify).

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

### Step 1: Verify you're on the feature branch

```bash
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

If `ROOT_GOAL_ID` is empty (the resolver returned `(None, None)`), this task is standalone — skip this skill entirely.

```bash
FEATURE_BRANCH="feature/${ROOT_GOAL_SLUG}"
CURRENT_BRANCH=$(git branch --show-current)
echo "Expected: ${FEATURE_BRANCH}  |  Current: ${CURRENT_BRANCH}"
```

If `CURRENT_BRANCH` does not equal `FEATURE_BRANCH` (e.g. you are still on a `cronos/*` branch), run `/goal-branch-setup` first — that skill resolves the same root branch and checks it out.

### Step 2: Run the test suite

Invoke the `test-architect` subagent to confirm tests pass. Do **not** proceed if any tests fail.

### Step 3: Check for changes

```bash
git status --short
```

If there is nothing to commit, the task made no code changes — skip steps 4–5 and mark the task DONE normally.

### Step 4: Stage and commit all changes

```bash
TASK_FILE="/data/spaces/cronos-development/.cronos/tasks/${TASK_ID}.md"
TASK_TITLE=$(grep "^title:" "$TASK_FILE" | sed "s/^title: *//;s/'//g")

git add -A
git status  # review what will be committed

git commit -m "$(cat <<EOF
${TASK_TITLE}

Task: ${TASK_ID}
EOF
)"
```

### Step 5: Push to origin

Push to the root goal's feature branch (guaranteed to be the current branch after step 1):

```bash
SPACE_DIR="/data/spaces/cronos-development"
REMOTE_URL=$(git -C "$SPACE_DIR" remote get-url origin 2>/dev/null || echo "")

# Inject CRONOS_GIT_TOKEN credentials for HTTPS remotes
if [ -n "$CRONOS_GIT_TOKEN" ] && echo "$REMOTE_URL" | grep -q "^https://"; then
    AUTH=$(echo -n "x-access-token:${CRONOS_GIT_TOKEN}" | base64 -w0)
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0="http.extraHeader" \
    GIT_CONFIG_VALUE_0="Authorization: Basic ${AUTH}" \
        git push origin "${FEATURE_BRANCH}"
else
    git push origin "${FEATURE_BRANCH}"
fi
```

### Step 6: Confirm

```bash
git log --oneline -5
```

The latest commit should be your task's changes on `feature/ROOT-GOAL-SLUG`.

## Commit message format

```
<task-title>

Task: <task-id>
```

**Example:**

```
arc-4/2: git_ops — commit, rebase, push, gh-pr helpers

Task: 2026-05-25-0706-arc-4-2-git-ops-commit-rebase-push-gh-pr
```

## If there are no changes

`git status` shows nothing to commit — the task involved analysis, planning, or documentation only. Skip the commit/push and mark DONE normally; no commit is needed.

## Notes

- The branch is named after the **ROOT** goal; sub-goal tasks push to the same shared branch. A task inside a sub-goal always commits to `feature/<root-goal-slug>`, never `feature/<sub-goal-slug>`.
- Always run tests before committing — the feature branch is the integration point for the whole goal, so a broken commit blocks subsequent tasks.
- The commit message intentionally includes the task ID so the git log traces back to Cronos task history.
- For the push, `CRONOS_GIT_TOKEN` is injected automatically by the Cronos runner when the space has a linked remote; if absent, SSH key auth is used.
