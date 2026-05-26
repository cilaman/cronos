---
name: goal-branch-setup
description: Prepare a git feature branch for a goal. Run as the first action in the first developing task of a goal. Creates feature/GOAL-SLUG from main and checks it out in the current worktree so all task commits land on the shared feature branch.
license: Internal — Cronos project.
---

# Goal Branch Setup

This skill prepares a dedicated git feature branch for a goal. All tasks in the goal commit to this branch; it is merged to `main` only after the goal passes final testing via `/goal-finalize`.

## When to use

Run as the **first action** in any task that:
1. Has a `parent_id` pointing to a goal, AND
2. Will make code changes.

This must be the first action in the **first eligible task** of a goal. Later tasks in the same goal will find the branch already set up and simply check it out.

## Step-by-step procedure

### Step 1: Resolve the goal ID and feature branch name

```bash
# Task ID is the last path segment of the current working directory
TASK_ID=$(basename "$PWD")
TASK_FILE="/data/spaces/cronos-development/.cronos/tasks/${TASK_ID}.md"

# Read parent_id from task frontmatter
GOAL_ID=$(grep "^parent_id:" "$TASK_FILE" | awk '{print $2}' | tr -d "'\"\r")
```

If `GOAL_ID` is empty or `null`, this task is not part of a goal — skip this skill entirely.

```bash
# Derive the slug: strip YYYY-MM-DD-HHMM- prefix
GOAL_SLUG=$(echo "$GOAL_ID" | sed 's/^[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}-[0-9]\{4\}-//')
FEATURE_BRANCH="feature/${GOAL_SLUG}"
SPACE_DIR="/data/spaces/cronos-development"
```

**Example**: goal ID `2026-05-26-2100-git-workflow-skills` → branch `feature/git-workflow-skills`

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
git branch --show-current   # should print feature/GOAL-SLUG
git log --oneline -5        # should show main history (and any prior goal-task commits)
```

You are now on `feature/GOAL-SLUG`. Make your code changes normally — commits here will accumulate across all tasks in this goal.

## Branch naming convention

| Goal ID | Feature branch |
|---------|---------------|
| `2026-05-26-2100-git-workflow-skills` | `feature/git-workflow-skills` |
| `2026-05-25-0705-arc-4-autonomous-todo-autopilot` | `feature/arc-4-autonomous-todo-autopilot` |
| `2026-05-24-1838-arc-2-tree-and-views` | `feature/arc-2-tree-and-views` |

## Notes

- Run **before** any code changes — the whole point is that the first edit goes to the right branch.
- If a later task in the same goal runs this skill, it will simply check out the existing branch (step 2 takes the `exists on origin` path). That is correct and safe.
- Do **not** push the empty branch until there are commits (use `/goal-task-commit` for pushing).
- The `cronos/TASK-ID` branch that the worktree was originally on still exists; switching the worktree does not delete it.
