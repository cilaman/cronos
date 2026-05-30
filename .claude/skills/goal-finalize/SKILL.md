---
name: goal-finalize
description: Test the complete goal and merge the feature branch to main. Run as the final action when all child tasks are done. Runs the full test suite, rebases onto main, merges, and pushes.
license: Internal — Cronos project.
---

# Goal Finalize

This skill is the merge gate for a goal. It runs the full test suite against the feature branch, and — only on green — rebases onto `main`, merges with a no-fast-forward commit, and pushes. If tests fail, the goal stays open and no merge happens.

## When to use

Run as the **final action** in a goal's last task (or a dedicated integration task) when:
1. All child tasks are DONE.
2. All child tasks have committed their changes via `/goal-task-commit`.

## Step-by-step procedure

### Step 1: Resolve the goal and feature branch

```bash
TASK_ID=$(basename "$PWD")
TASK_FILE="/data/spaces/cronos-development/.cronos/tasks/${TASK_ID}.md"
GOAL_ID=$(grep "^parent_id:" "$TASK_FILE" | awk '{print $2}' | tr -d "'\"\r")
GOAL_SLUG=$(echo "$GOAL_ID" | sed 's/^[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}-[0-9]\{4\}-//')
FEATURE_BRANCH="feature/${GOAL_SLUG}"
SPACE_DIR="/data/spaces/cronos-development"
GOAL_TITLE=$(grep "^title:" "/data/spaces/cronos-development/.cronos/tasks/${GOAL_ID}.md" | sed "s/^title: *//;s/'//g")
```

### Step 2: Fetch latest refs

```bash
git -C "$SPACE_DIR" fetch origin --prune
```

### Step 3: Run the pipeline eval gate

Before the full test suite, run the CC-v1 eval harness as a fast regression check:

```bash
cd /data/spaces/cronos-development/backend && python -m app.pipeline.run_evals --all
```

This runs all golden fixtures (must pass verify()) and all negative fixtures (must fail verify() after normalize()). Exit code 0 = pass, 1 = regression detected.

**If evals fail**: Stop here. A golden fixture regressing means a change to the contract, schemas, normalizer, or verifier broke a known-good artifact. A negative fixture starting to pass means the verifier no longer catches a hard-fail condition. Neither is safe to merge. Report the failures clearly, create a follow-up task to fix the regression, then re-run `/goal-finalize`.

**If evals pass**: Continue.

### Step 4: Run the full test suite

Invoke the `test-architect` subagent to run all tests against the feature branch state.

**If tests fail**: Stop here. Report the failing tests clearly. Do NOT proceed to merge. The goal stays open; create a follow-up task to fix the failures, then re-run `/goal-finalize`.

**If tests pass**: Continue.

### Step 5: Rebase the feature branch onto latest main

```bash
git -C "$SPACE_DIR" checkout "${FEATURE_BRANCH}"
git -C "$SPACE_DIR" rebase "origin/main"
```

**If rebase conflicts occur**:
```bash
git -C "$SPACE_DIR" rebase --abort
```
Report the conflicting files. Do NOT merge. The user must resolve conflicts manually, then re-run this skill.

### Step 6: Merge to main

```bash
# Switch to main and pull latest
git -C "$SPACE_DIR" checkout main
git -C "$SPACE_DIR" pull origin main

# Merge with a no-fast-forward merge commit
git -C "$SPACE_DIR" merge --no-ff "${FEATURE_BRANCH}" -m "$(cat <<EOF
Merge ${FEATURE_BRANCH}: ${GOAL_TITLE}

Goal: ${GOAL_ID}
EOF
)"
```

### Step 7: Push main to origin

```bash
REMOTE_URL=$(git -C "$SPACE_DIR" remote get-url origin 2>/dev/null || echo "")

if [ -n "$CRONOS_GIT_TOKEN" ] && echo "$REMOTE_URL" | grep -q "^https://"; then
    AUTH=$(echo -n "x-access-token:${CRONOS_GIT_TOKEN}" | base64 -w0)
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0="http.extraHeader" \
    GIT_CONFIG_VALUE_0="Authorization: Basic ${AUTH}" \
        git -C "$SPACE_DIR" push origin main
else
    git -C "$SPACE_DIR" push origin main
fi
```

### Step 8: Confirm

```bash
git -C "$SPACE_DIR" log --oneline -5
```

The merge commit should be visible at the top of main's history.

## If tests fail — what to report

```
Tests FAILED on feature/${FEATURE_BRANCH}. Goal NOT merged to main.

Failing tests:
- [list each failing test/file]

Next steps: Create a follow-up task in goal ${GOAL_ID} to fix the failures,
then re-run /goal-finalize once all tests pass.
```

## If rebase conflicts — what to report

```
Rebase of ${FEATURE_BRANCH} onto origin/main has conflicts in:
- [list conflicting files]

Rebase aborted. The feature branch is unchanged.

Next steps: Resolve conflicts manually in the feature branch, push the
resolved state, then re-run /goal-finalize.
```

## Notes

- The `--no-ff` merge creates a single visible merge commit in `main`'s history, making the goal's contribution easy to identify with `git log --merges`.
- The feature branch is NOT deleted after merge — it remains for audit/revert purposes.
- After this skill succeeds, the final task and goal can both be marked DONE.
