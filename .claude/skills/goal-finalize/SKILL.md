---
name: goal-finalize
description: Test the complete goal and merge the feature branch to main. Run as the final action when all child tasks of the root goal are done. Runs the full test suite, rebases onto main, merges, pushes, and deletes the feature branch.
license: Internal — Cronos project.
---

# Goal Finalize

This skill is the merge gate for the **root** goal of a goal tree. It runs the full test suite against the feature branch, and — only on green — rebases onto `main`, merges with a no-fast-forward commit, pushes, and then deletes the feature branch locally and on origin. If tests fail or the rebase aborts, the goal stays open, no merge happens, and the feature branch is left untouched.

## When to use

Run as the **final action** in the **root** goal's last task (or a dedicated integration task) when:
1. All child tasks (across the whole goal tree, including sub-goals) are DONE.
2. All child tasks have committed their changes via `/goal-task-commit`.

This skill finalises at the **root** goal level only. If the current task's resolved root goal differs from the goal whose children are being finalised, that is fine — the skill always merges the root goal's branch, so every nested sub-goal under the same root rides on a single merge.

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

### Step 1: Resolve the root goal and feature branch

```bash
TASK_ID=$(basename "$PWD")
```

Run the canonical resolver to find the topmost goal in the parent chain:

```bash
read ROOT_GOAL_ID ROOT_GOAL_SLUG <<EOF
$(python3 - "$TASK_ID" <<'PY2'
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
PY2
)
EOF
```

If `ROOT_GOAL_ID` is empty (the resolver returned `(None, None)`), this task is **standalone** — it has no parent goal at all — so there is nothing to finalise. Stop here.

```bash
FEATURE_BRANCH="feature/${ROOT_GOAL_SLUG}"
SPACE_DIR="/data/spaces/cronos-development"
GOAL_TITLE=$(grep "^title:" "/data/spaces/cronos-development/.cronos/tasks/${ROOT_GOAL_ID}.md" | sed "s/^title: *//;s/'//g")
```

The feature branch is always named after the **root** goal. Sub-goal slugs are never used.

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
Report the conflicting files. Do NOT merge. The user must resolve conflicts manually, then re-run this skill. The feature branch must remain — do not run Step 8.

### Step 6: Merge to main

```bash
# Switch to main and pull latest
git -C "$SPACE_DIR" checkout main
git -C "$SPACE_DIR" pull origin main

# Merge with a no-fast-forward merge commit
git -C "$SPACE_DIR" merge --no-ff "${FEATURE_BRANCH}" -m "$(cat <<EOF
Merge ${FEATURE_BRANCH}: ${GOAL_TITLE}

Goal: ${ROOT_GOAL_ID}
EOF
)"
```

### Step 7: Push main to origin

```bash
REMOTE_URL=$(git -C "$SPACE_DIR" remote get-url origin 2>/dev/null || echo "")

if [ -n "$CRONOS_GIT_TOKEN" ] && [[ "$REMOTE_URL" == https://* ]]; then
    AUTH=$(echo -n "x-access-token:${CRONOS_GIT_TOKEN}" | base64 -w0)
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0="http.extraHeader" \
    GIT_CONFIG_VALUE_0="Authorization: Basic ${AUTH}" \
        git -C "$SPACE_DIR" push origin main
else
    git -C "$SPACE_DIR" push origin main
fi
```

### Step 8: Delete the merged feature branch (local + origin)

Only run this step after Steps 5–7 have succeeded (rebase clean, merge created, push to origin accepted). If any earlier step bailed out, skip this and leave the branch in place.

```bash
# Delete the merged feature branch locally
git -C "$SPACE_DIR" branch -d "${FEATURE_BRANCH}"

# Delete it on origin (token-injected for HTTPS remotes, mirroring the push block)
REMOTE_URL=$(git -C "$SPACE_DIR" remote get-url origin 2>/dev/null || echo "")
if [ -n "$CRONOS_GIT_TOKEN" ] && [[ "$REMOTE_URL" == https://* ]]; then
    AUTH=$(echo -n "x-access-token:${CRONOS_GIT_TOKEN}" | base64 -w0)
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0="http.extraHeader" \
    GIT_CONFIG_VALUE_0="Authorization: Basic ${AUTH}" \
        git -C "$SPACE_DIR" push origin --delete "${FEATURE_BRANCH}"
else
    git -C "$SPACE_DIR" push origin --delete "${FEATURE_BRANCH}"
fi
```

Use `branch -d` (safe delete — refuses if not merged), **not** `-D`. Since we just merged in Step 6 and pushed in Step 7, `-d` will succeed; if it refuses, that signals the merge did not actually land. In that case, stop and report rather than force-deleting.

### Step 9: Confirm

```bash
git -C "$SPACE_DIR" log --oneline -5
```

The merge commit should be visible at the top of main's history, and `feature/${ROOT_GOAL_SLUG}` should no longer appear in `git branch -a` (neither locally nor as `remotes/origin/...`).

## If tests fail — what to report

```
Tests FAILED on ${FEATURE_BRANCH}. Goal NOT merged to main.

Failing tests:
- [list each failing test/file]

Next steps: Create a follow-up task in goal ${ROOT_GOAL_ID} to fix the failures,
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

- Origin URL must not be printed because it inlines the PAT and would be captured into trace JSONs.
- The `--no-ff` merge creates a single visible merge commit in `main`'s history, making the goal's contribution easy to identify with `git log --merges`.
- After a successful merge+push the feature branch is deleted locally and on origin; the `--no-ff` merge commit on `main` preserves the full audit trail and revert point.
- The branch is preserved whenever the skill bails out — failed evals, failed tests, or aborted rebase. Deletion is strictly the last step on the green path.
- The feature branch name comes from the **root** goal slug, not any intermediate sub-goal. A sub-goal task running `/goal-finalize` still merges and deletes the root goal's branch.
- After this skill succeeds, the final task and the root goal can both be marked DONE.
