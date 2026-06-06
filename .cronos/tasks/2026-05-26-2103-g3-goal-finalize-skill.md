---
agent_mode: auto
agent_model: default
claude_session_id: 2d1bb97a-0ac0-46e9-a24c-ef1132b95ce3
created_at: '2026-05-26T21:03:00Z'
depends_on:
- 2026-05-26-2101-g1-goal-branch-setup-skill
- 2026-05-26-2102-g2-goal-task-commit-skill
id: 2026-05-26-2103-g3-goal-finalize-skill
manual_order: 3
parent_id: 2026-05-26-2100-git-workflow-skills
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'g3: Create goal-finalize skill'
type: task
updated_at: '2026-06-02T21:33:35Z'
waiting_question: null
---

# Brief

Create the `goal-finalize` skill at `.claude/skills/goal-finalize/SKILL.md`.

This skill is invoked as the **final action** in a goal's last task (or in a dedicated integration/finalization task). It:
1. Runs the full backend test suite against the feature branch state.
2. On failure: reports failing tests and stops — the goal is NOT merged.
3. On success: rebases `feature/GOAL-SLUG` onto `origin/main`, then merges it into `main` with a no-fast-forward merge commit.
4. Pushes `main` to origin (with `CRONOS_GIT_TOKEN` credentials when the remote is HTTPS).

# History

Implemented as part of task `2026-05-26-2051-create-git-goal`. Skill file written to `.claude/skills/goal-finalize/SKILL.md`.

```
2026-05-26T21:10:19Z [user]
Commit all outputs of this goal to main and push
```

```
2026-05-26T21:15:37Z [agent] run=0 model=claude-sonnet-4-6 mode=auto agents=tester
Let me explore the existing skill structure to understand the conventions used.

Now let me check the existing test setup and git configuration to write accurate skill instructions.

Now I have enough context. Let me look at how goals link to feature branches.

The skill files exist in the main project. Let me read them.

The skill file already exists at the main project location. The message "Commit all outputs of this goal to main and push" means I should now execute the `/goal-finalize` process for goal `g3`. Let me invoke the skill.

The skill isn't registered, so I'll execute the steps from `goal-finalize/SKILL.md` directly.

**Step 1: Resolve the goal and feature branch**

**Step 2: Fetch latest refs and check feature branch exists**

Good — `.claude/settings.json` doesn't exist on `main` yet, so the cherry-pick should be clean. Now let me create the feature branch, cherry-pick, and run tests.

**Step 3: Create feature branch and cherry-pick the skills commit**

The working tree has uncommitted changes from `c209c42` (already on main). I'll stash them to cleanly create the feature branch.

The feature branch is created. Now **Step 3: Run the full test suite**.

All 906 tests pass. **Step 4: Rebase onto latest main, then merge.**

Branch is already up-to-date with `origin/main` since it was created from `main`. **Step 5: Merge into main.**

`main` is checked out in another worktree. I'll do the merge there.

**Step 6: Push main to origin with CRONOS_GIT_TOKEN**

**Step 7: Confirm**

All done. Here's what happened:

1. **Tests**: 906/906 backend tests passed (81% coverage) on `feature/git-workflow-skills`
2. **Cherry-pick**: The skills commit (`514fa88`) was cleanly cherry-picked onto a fresh `feature/git-workflow-skills` branch from `main`
3. **Merge**: `feature/git-workflow-skills` merged into `main` with `--no-ff` as merge commit `dbe9c4a`
4. **Push**: `main` pushed to `origin` (`c209c42..dbe9c4a`)

The three skill files (`goal-branch-setup`, `goal-task-commit`, `goal-finalize`) plus `.claude/settings.json` are now live on `main`.

STATUS: DONE
```
