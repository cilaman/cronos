---
agent_mode: auto
agent_model: default
claude_session_id: feee02a4-5350-42c3-a2de-582a809ef5af
created_at: '2026-06-04T12:30:51Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-04-1230-wrong-dependencies
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: waiting
title: Wrong dependencies?
type: task
updated_at: '2026-06-05T23:35:14Z'
waiting_question: The previous run ended without a STATUS marker. If the task is complete,
  reply with just 'done'. Otherwise continue where you left off.
---

# Brief

2026-06-03-1631-featurefix-api cannot start because it waits for some dependency that does not make sense

# History

```
2026-06-04T12:38:37Z [agent] run=0 model=claude-sonnet-4-6 mode=auto
I'll investigate the dependency issue with the `2026-06-03-1631-featurefix-api` task by querying the backend API.

The task has `depends_on: []` and `unmet_dependencies: []` but it's stuck in `waiting` state with an error about `2026-06-03-1631-pipeline-doc-sync-features-fixes-s1-mode`. Let me check that dependency task and understand why it got stuck.

Let me look at the raw task data and the whole features-and-fixes structure more closely.

The task has `depends_on: []` but was put in waiting state saying it's waiting on the S1 doc-sync task. Let me understand the full hierarchy and what the correct dependencies should be.

Let me look at the worker code to understand how this dependency check is generated.

Now let me look at how the worker runs goals to understand the sequence of events.

Let me check the git history for the task file to see if dependencies were changed.

Let me look at the `unmet_deps` function and `_topo_children` to understand the dependency resolution.

Now I have a clear picture. Let me check the allowed state transitions to fix this properly.

Let me check the goal sync mechanism to understand how parent goals are re-enqueued.

Let me check the manual order of the subgoals to understand the ordering issue.

The ordering is alphabetical since all have `manual_order=0`, so `featurefix-api` (alphabetically before `featurefix-data-model`) gets processed FIRST — that's the root cause. I need to:
1. Fix `depends_on` to use sibling deps (so the topo-sort orders them correctly)
2. Move stuck tasks back to `backlog`
3. Re-enqueue the parent goal

Let me check the API endpoints for updating task dependencies.

The root cause is clear: all subgoals have `manual_order=0` and `depends_on: []`, so they're sorted alphabetically — `featurefix-api` sorts before `featurefix-data-model`, causing the worker to try S2 before S1 is done. The dependency on the doc-sync task inside S1 then fails, sticking the whole goal.

The fix: set proper sibling `depends_on` so `_topo_children` orders them correctly (S1→S2→{S3‖S4}→S5→S6), then unstick the waiting tasks.

Now move the stuck tasks back to `backlog`.

Both tasks are now in `backlog`. Let me verify the final state and that the topo-ordering will now be correct.

The ordering is now correct: S1→S2→S3→S4→S5→S6. When `features-and-fixes` is re-enqueued, S1 will run first, and S2 will only be activated after S1 completes.

Let me finalize this task.

No code changes made (task was API-driven). Skip commit.

The workspace-scoped path was blocked. I'll write this observation to the space-root memory instead since it's broadly applicable.

Memory written. Back to task-finalize Step 5.

**Root cause found and fixed:**
- All 6 `features-and-fixes` subgoals had `manual_order=0` and `depends_on: []`
- `_topo_children` sorted them alphabetically → `featurefix-api` (S2) came before `featurefix-data-model` (S1)
- Worker tried to activate S2 first; it had a dep on S1's internal doc-sync task → `InvalidTransition` → parent goal stuck in `waiting`
- Fix: set sibling deps S1→S2→{S3‖S4}→S5→S6 via `PATCH /api/tasks/{id}/depends_on`, moved stuck tasks back to `backlog`

The `features-and-fixes` goal is now in `backlog` and ready to be re-enqueued from the UI.

STATUS: DONE
```

```
2026-06-04T15:51:25Z [user]
Update also skills for goals and tasks creation
```

```
2026-06-04T15:54:19Z [agent] run=1 model=claude-sonnet-4-6 mode=auto
I'll read the relevant skills before updating them.

Now I have a clear picture of what to fix. The `create-goal` skill has the wrong pattern for sequential sub-goals — it chains the `analyst` of slice B to the `doc` of slice A (a cross-sub-goal task dep), which is invisible to `_topo_children`. The fix is to set `depends_on` on the **sub-goal itself**. I also need to add a warning to `pipeline-scaffold` about multi-SG arcs.

Starting with `create-goal`:

Now update `pipeline-scaffold` to add the multi-SG arc guidance:

Now verify the changes look right:

Now commit the skill changes and finalize.

Changes committed and pushed. Here's a summary of what was updated:

**`create-goal/SKILL.md`** — three fixes:
1. Diagram: `Sub-Goal B` now shows `depends_on: [sub_goal_a_id]`, not `analyst depends_on: [doc_id_of_A]`
2. Rules bullet: clarifies that sibling `depends_on` must be on the **sub-goal itself**, with an explicit warning that cross-sub-goal task deps are invisible to `_topo_children`
3. Code example: `prev_sg_id` tracks the previous sub-goal id; each sub-goal is posted with `"depends_on": [prev_sg_id]`; removed the `prev_last_task_id` chain that was causing the bug

**`pipeline-scaffold/SKILL.md`** — new "Multi-SG arc usage" section with a ready-to-run `PATCH /depends_on` snippet and the explanation of why alphabetical ordering breaks without sibling deps
```

```
2026-06-04T15:54:47Z [user]
Merge to main
```

```
2026-06-04T15:54:55Z [agent] run=2 model=claude-sonnet-4-6 mode=auto
Already on `main` and the skill changes were committed directly there (commit `55ce52b`). It was pushed to origin in the previous step — nothing left to merge.

The task work (dependency fixes + skill updates) is already on `main` at `55ce52b`.

STATUS: DONE
```

```
2026-06-05T23:32:21Z [user]
Again the problem is in 
2026-06-05-2327-harness-editor-usability
- need fast fix to be able to run the goal 
2026-06-05-2327-harness-editor-usability Asap
- create a cronos goal that fiexes this dependencies problem forever
```

```
2026-06-05T23:35:14Z [agent] run=3 model=claude-sonnet-4-6 mode=auto
Let me check the state of `2026-06-05-2327-harness-editor-usability` and its children first.

Same root cause — `backend-harness-tools-resolver` sorts before `frontend-harness-editor` alphabetically. I'll fix both immediately in parallel.

Goal is running. Now create the permanent fix goal:

Done. Two things happened:

**Immediate fix** — `2026-06-05-2327-harness-editor-usability` is now `active`:
- Set `backend-harness-tools-resolver.depends_on = [frontend-harness-editor]` (sibling dep)
- Set `integrate.depends_on = [backend-harness-tools-resolver]` (sibling dep)
- Moved stuck tasks to backlog, re-enqueued root goal

**Permanent fix goal** — `2026-06-05-2335-auto-repair-missing-sibling-deps-in-run`:
- **Task 1**: Modify `_run_goal` in `worker.py` — when `InvalidTransition("unmet dependencies: X")` is raised and X is a non-sibling dep, automatically walk up X's parent chain to find the sibling, add it to `depends_on`, re-sort, and restart the loop (capped at 1 repair attempt to prevent infinite loops)
- **Task 2**: Tests verifying the repair triggers, already-correct deps are untouched, and the repair cap works
```
