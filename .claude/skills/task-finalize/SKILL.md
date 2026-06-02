---
name: task-finalize
description: Finalize a completed task — verify completion, handle git, write memory, emit STATUS marker. MANDATORY last step of every task. Self-improving: when given feedback about a previous run problem, edit this SKILL.md first, then finalize.
license: Internal — Cronos project.
---

# Task Finalize

**Invoke this skill as the last action of every task.** It replaces manual STATUS: DONE writing — handles git, memory, and status in the right order.

---

## When invoked with feedback about a previous run problem

If you were told that a **previous run of this skill had a problem** (wrong branch, git failure, memory not written, wrong state, etc.), fix the skill first:

1. Read the feedback and identify which step was wrong or missing.
2. Edit this SKILL.md to fix the instruction.
3. If another skill is implicated (goal-task-commit, write-memory, etc.), edit it too.
4. Commit the improvement:
   ```bash
   git add .claude/skills/
   git commit -m "improve task-finalize: <one-line description of the fix>"
   ```
5. Continue with Step 1 below to finalize the current task.

---

## Step 1 — Verify completion

Before proceeding, confirm the task objectives were met:

- Review the original task brief you were given at the start.
- Were all stated requirements implemented or addressed?
- Do tests pass (if code was changed)?

**If the task is incomplete**, describe what remains on the line above, then end with `STATUS: WAIT` or `STATUS: BLOCKED`. **Skip Steps 2–4.**

---

## Step 2 — Check trace history (only if task was previously WAITING)

If this task was re-activated from WAITING state, quickly scan prior traces to understand why it failed:

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
ls "${SPACE_DIR}/.cronos/traces/${TASK_ID}/" 2>/dev/null | tail -5
```

If prior traces exist, read the latest via the API:

```bash
curl -s "http://backend:8000/api/tasks/${TASK_ID}/traces/latest" | python3 -c "import json,sys; t=json.load(sys.stdin); print('exit_reason:', t.get('exit_reason'), '| error_tool_calls:', t.get('error_tool_calls', 0))"
```

Common patterns:
- `NO_STATUS` — agent forgot STATUS: DONE in a prior run (the problem this skill solves)
- `CRASHED` — unhandled error; check error_tool_calls count
- `WAIT` — agent explicitly paused in the prior run

Note any systemic pattern in memory (Step 4) if it will help future runs.

---

## Step 3 — Handle git

Detect task context (goal child vs standalone):

```bash
TASK_ID=$(basename "$PWD")
python3 -c "
import urllib.request, json
with urllib.request.urlopen('http://backend:8000/api/tasks/${TASK_ID}') as r:
    t = json.loads(r.read())
parent = t.get('parent_id', '')
print('PARENT:' + parent if parent else 'STANDALONE')
"
```

**A. Goal child task** (output starts with `PARENT:`) — delegate to goal-task-commit:

```
/goal-task-commit
```

`goal-task-commit` automatically resolves the **root** goal's feature branch by walking the `parent_id` chain, so tasks nested under sub-goals need no special handling.

**B. Standalone task on a repo-linked space** — check for changes and commit:

```bash
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
git -C "$SPACE_DIR" status --short
```

If there are uncommitted changes:

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
TASK_TITLE=$(grep "^title:" "${SPACE_DIR}/.cronos/tasks/${TASK_ID}.md" | sed "s/^title: *//;s/'//g")

git -C "$SPACE_DIR" add -A
git -C "$SPACE_DIR" status  # review staged changes

git -C "$SPACE_DIR" commit -m "$(cat <<GITEOF
${TASK_TITLE}

Task: ${TASK_ID}
GITEOF
)"

REMOTE_URL=$(git -C "$SPACE_DIR" remote get-url origin 2>/dev/null || echo "")
if [ -n "$CRONOS_GIT_TOKEN" ] && echo "$REMOTE_URL" | grep -q "^https://"; then
    AUTH=$(echo -n "x-access-token:${CRONOS_GIT_TOKEN}" | base64 -w0)
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0="http.extraHeader" \
    GIT_CONFIG_VALUE_0="Authorization: Basic ${AUTH}" \
        git -C "$SPACE_DIR" push origin HEAD
else
    git -C "$SPACE_DIR" push origin HEAD
fi
```

**C. No changes / analysis-only task** — `git status --short` returns empty. Skip commit and push.

---

## Step 4 — Write memory

Write 1–3 MEMORY lines summarizing what was accomplished. **Required for STATUS: DONE.**

Choose the type that best fits:
```
MEMORY[fact]: <what was built, changed, or configured — name specific files/modules>
MEMORY[procedure]: <repeatable process — command sequence or decision steps>
MEMORY[observation]: <pattern, pitfall, or insight others should know>
MEMORY[reference]: <specific file path, API endpoint, or resource worth revisiting>
```

Good things to capture: files modified and why, API patterns discovered, commands that worked, pitfalls encountered, architectural decisions made.

---

## Step 5 — Emit STATUS: DONE

**STATUS: DONE must be the absolute last line of your response. Nothing after it.**

After writing your MEMORY lines, output:

```
STATUS: DONE
```

---

## Self-improvement protocol

This skill should evolve based on real-world failures. When you discover a problem or receive feedback:

1. **Identify the root cause** — which step or instruction was wrong?
2. **Edit the relevant SKILL.md** — fix the instruction that caused the problem.
3. **Add a new step** if the scenario was not covered.
4. **Remove or simplify** steps that are never triggered or consistently cause confusion.
5. **Commit the improvement**:
   ```bash
   git add .claude/skills/task-finalize/ .claude/skills/<other-affected-skill>/
   git commit -m "improve task-finalize: <what was wrong and how it is fixed>"

   REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
   if [ -n "$CRONOS_GIT_TOKEN" ] && echo "$REMOTE_URL" | grep -q "^https://"; then
       AUTH=$(echo -n "x-access-token:${CRONOS_GIT_TOKEN}" | base64 -w0)
       GIT_CONFIG_COUNT=1 \
       GIT_CONFIG_KEY_0="http.extraHeader" \
       GIT_CONFIG_VALUE_0="Authorization: Basic ${AUTH}" \
           git push origin HEAD
   else
       git push origin HEAD
   fi
   ```

<!-- Changelog: add entries here as the skill evolves (newest first) -->
