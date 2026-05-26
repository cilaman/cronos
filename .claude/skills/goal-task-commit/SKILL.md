---
name: goal-task-commit
description: Commit and push a completed task's changes to the goal's feature branch. Run after tests pass as the last step of any code-modifying task that belongs to a goal.
license: Internal — Cronos project.
---

# Goal Task Commit

This skill commits and pushes a task's code changes to the goal's shared feature branch. It runs after tests pass, before the task is marked DONE.

## When to use

Run as the **last action** of any task in a goal that modified code, after:
1. All code changes are complete.
2. Tests pass (invoke `test-architect` to verify).

## Step-by-step procedure

### Step 1: Verify you're on the feature branch

```bash
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"
```

The branch should be `feature/GOAL-SLUG`. If you're on a `cronos/*` branch, run `/goal-branch-setup` first.

### Step 2: Run the test suite

Invoke the `test-architect` subagent to confirm tests pass. Do **not** proceed if any tests fail.

### Step 3: Check for changes

```bash
git status --short
```

If there is nothing to commit, the task made no code changes — skip steps 4–5 and mark the task DONE normally.

### Step 4: Stage and commit all changes

```bash
TASK_ID=$(basename "$PWD")
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

```bash
FEATURE_BRANCH=$(git branch --show-current)
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

The latest commit should be your task's changes on `feature/GOAL-SLUG`.

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

- Always run tests before committing — the feature branch is the integration point for the whole goal, so a broken commit blocks subsequent tasks.
- The commit message intentionally includes the task ID so the git log traces back to Cronos task history.
- For the push, `CRONOS_GIT_TOKEN` is injected automatically by the Cronos runner when the space has a linked remote; if absent, SSH key auth is used.
