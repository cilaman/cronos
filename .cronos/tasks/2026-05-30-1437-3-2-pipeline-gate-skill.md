---
agent_mode: auto
agent_model: opus
claude_session_id: 3ae53076-57d9-4416-821d-9188f460ac0b
created_at: '2026-05-30T14:37:55Z'
depends_on:
- 2026-05-30-1437-3-1-pipeline-state-phases-log-writer
feature_key: null
feature_state: null
id: 2026-05-30-1437-3-2-pipeline-gate-skill
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-05-30-1437-orchestration-logging-glue-scaffold-gate
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 3.2 pipeline-gate skill
type: task
updated_at: '2026-06-19T12:17:47Z'
waiting_question: null
---

# Brief

Create `.claude/skills/pipeline-gate/SKILL.md` — the Cronos analogue of `post_phase_verify`. Resolves the expected artifact path from goal_slug+phase, runs normalize then verify, and: on pass writes a phases-log event + updates pipeline-state and emits `STATUS: DONE`; on fail/escalate emits `STATUS: BLOCKED` with the verifier blockers so the worker does not advance the DAG.

## Acceptance
- Pass path advances; fail path forces STATUS: BLOCKED. Path derived mechanically (no dir search).

## Reference material (read by absolute path)
- Delivery Notes contract: `/data/spaces/delivery-notes/.ai/framework/agent-contract-v1.md`
- Delivery Notes orchestrator: `/data/spaces/delivery-notes/.claude/agents/pipeline-orchestrator.md`
- Delivery Notes known-issues (F-NN): `/data/spaces/delivery-notes/.ai/framework/known-issues.md`
- Cronos primitives: `backend/app/{agent,worker,goal_sync,storage,models,trace_store,trace_parser,memory_store,memory_retrieval}.py`
- Memory entries `delivery-notes-pipeline` and `delivery-notes-pipeline-cronos-mapping` surface the design rationale via retrieval.

# History

```
2026-05-30T19:16:08Z [agent]
Good — now I have state_writer in my workspace. Let me look at the existing agent files to understand naming conventions and the contract.

Now I have enough context. Let me also check how `space_id` is resolved in current skills, since the gate skill needs to know the space root.

Now I'll write the `pipeline-gate` skill.

Good — only the legitimate bash line-continuation backslashes remain. Let me read key parts to confirm the file is correct.

Let me verify one concern — that `NormalizeResult.to_dict()` actually exposes `fixes_applied`:

Good — `fixes_applied` is exposed. Now let me also do a quick smoke test of the verifier CLI on a fictitious slug to confirm exit-code-3 behaviour when the artifact is missing (proving the "no dir search" path works mechanically):

Skill is complete and underlying primitives smoke-tested. Now let me finalize the task — commit, write memory, emit STATUS.

Step 1 — Completion verified: SKILL.md created at the correct path, slug resolution + normalize+verify+state-write + STATUS gating all implemented. Smoke tests on verify (exit 3 on missing) and state_writer (telemetry rollup) both pass. Acceptance criteria met.

Step 2 — Skip (first run, no prior trace).

Step 3 — Goal child. Let me check parent and handle the worktree-conflict scenario.

Feature branch pushed. Now write memory.

Committed `.claude/skills/pipeline-gate/SKILL.md` as `b4e6728`, fast-forwarded `feature/orchestration-logging-glue-scaffold-gate` to it, and pushed to origin. Memory + index updated.

MEMORY[fact]: `.claude/skills/pipeline-gate/SKILL.md` created (task 3.2, commit `b4e6728` on `feature/orchestration-logging-glue-scaffold-gate`). Cronos analogue of Delivery Notes `post_phase_verify`: takes `goal_slug`+`phase`+`agent_name`+`upstream_task_id` from gate-task brief, composes slug mechanically per class (bare / `--{iter}` for impl / `--attempt{N}` for review), shells `python -m app.pipeline.verify --normalize --json`, then runs a single Python block that loads the upstream trace via `TraceStore`, builds `PhaseMetrics.from_trace`, and calls `update_phase` + `record_phase_log` from `app.pipeline.state_writer`. Exit 0 → STATUS: DONE; 1/2/3 → STATUS: BLOCKED with the verifier's `errors[]`. Never reads artifact prose, never searches filesystem (verifier exit 3 is the missing-artifact signal).

MEMORY[procedure]: When the goal feature branch is locked in a sibling worktree (another task's workspace), commit on the local `cronos/TASK-ID` branch in this workspace, then fast-forward the feature ref with `git update-ref refs/heads/feature/<slug> HEAD <old-tip>` (the `<old-tip>` 4-arg form makes the update conditional and safe), then push the feature branch to origin. Works only when the local commit is a strict descendant of the feature branch tip — verify with `git merge-base` first.

STATUS: DONE
```
