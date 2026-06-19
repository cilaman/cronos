---
agent_mode: auto
agent_model: opus
claude_session_id: fc38b2f0-09a7-4148-b0cb-6ba18481ccdc
created_at: '2026-05-30T14:37:55Z'
depends_on:
- 2026-05-30-1437-3-4-feature-branch-wiring
feature_key: null
feature_state: null
id: 2026-05-30-1437-3-5-end-to-end-smoke-run
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
title: 3.5 end-to-end smoke run
type: task
updated_at: '2026-06-19T12:17:47Z'
waiting_question: null
---

# Brief

Scaffold + run a trivial feature request in a scratch space. Assert: every artifact passes verify, the DAG advances on green, and a deliberately-broken artifact halts the DAG (STATUS: BLOCKED). Capture evidence in the pipeline-state.json + phases-log.jsonl.

## Acceptance
- Green run completes all phases; broken-artifact run halts at the gate.

## Reference material (read by absolute path)
- Delivery Notes contract: `/data/spaces/delivery-notes/.ai/framework/agent-contract-v1.md`
- Delivery Notes orchestrator: `/data/spaces/delivery-notes/.claude/agents/pipeline-orchestrator.md`
- Delivery Notes known-issues (F-NN): `/data/spaces/delivery-notes/.ai/framework/known-issues.md`
- Cronos primitives: `backend/app/{agent,worker,goal_sync,storage,models,trace_store,trace_parser,memory_store,memory_retrieval}.py`
- Memory entries `delivery-notes-pipeline` and `delivery-notes-pipeline-cronos-mapping` surface the design rationale via retrieval.

# History

```
2026-05-30T19:52:42Z [agent]
Let me explore the feature branch's pipeline infrastructure.

Now I understand the pipeline. Let me look at the verifier and existing fixtures to craft valid artifacts.

Now I'll mark task 1 complete and check the actual fixture verification works first to validate my approach.

Plan is to drive the scaffold-init + per-phase gate flow locally against a scratch space (not the real Cronos board) — that exercises verify + state_writer end-to-end, which is what the acceptance criteria measure. Let me start.

Now I'll write a smoke driver script that exercises the full gate flow (verify CLI + state_writer) against a scratch space with hand-crafted artifacts.

Found it — the goldens use bare `fixture-test` for review (not the fan-out `--attempt1`). I need to also rewrite the YAML `slug:` line directly. Let me fix the driver.

Both runs pass all assertions. Green: all 7 phases proceed, log has 7 lines, telemetry shows 7 completed / 0 failed. Broken: halts at design (cc_version='9.9' rejected), only 3 phases recorded, telemetry 2 completed / 1 failed.

Now let me capture the evidence files and write a smoke-run report.

Now let me write the smoke-run report.

Total 144KB — fine to commit as evidence. Let me commit on the feature branch.

Now I need to push the feature branch using the token, per the project memory.

Let me check what state my own workspace is in (the cherry-picked files were staged here only to make the smoke runnable, but the actual smoke evidence is already on the feature branch).

This is a goal child task but the feature branch lives in a different worktree (per the `procedure_goal_branch_worktree_conflict` memory). I've already committed and pushed to `feature/orchestration-logging-glue-scaffold-gate` via `git -C`. The cherry-picked files in this workspace were just to make the test runnable locally. Let me also snapshot the workspace branch so the task's working state is preserved.

Now write the memory entry for this work.

The existing project memory is already loaded from `/root/.claude/projects/-data-spaces-cronos-development/memory/` (per the system context). I'll add a project-level memory entry there so future tasks in the goal can reference this smoke run.

Smoke run complete. Both scenarios pass all assertions:

**Green** (`smoke/green-space/`): 7 phases (research → analysis → design → impl → test → review → doc), every gate `gate_decision=proceed`, `status=done`. `pipeline-state.json` telemetry `{phases_completed: 7, phases_failed: 0}`; `phases-log.jsonl` 7 ordered proceed lines.

**Broken** (`smoke/broken-space/`): design artifact has `cc_version: '9.9'` instead of `'1.0'`. Verify exits 1, gate records `gate_decision=fail` + `status=blocked`. DAG halts at design — no impl/test/review/doc artifacts exist. Telemetry `{phases_completed: 2, phases_failed: 1}`.

Driver, evidence, and report pushed to `feature/orchestration-logging-glue-scaffold-gate` (commit `f6034bc`), workspace snapshotted on the per-task branch, project memory updated.

MEMORY[project]: Task 3.5 smoke run merged into feature/orchestration-logging-glue-scaffold-gate (f6034bc). Driver at smoke/run_smoke.py exercises verify CLI + state_writer end-to-end; both green (7/7 proceed) and broken-design (cc_version='9.9' → halt at design) scenarios pass without needing the Cronos worker.

MEMORY[observation]: When testing the pipeline with the in-repo goldens, the review/test/doc fixtures use bare `slug: fixture-test` (not the fan-out `--attempt1`) because the regression harness exercises them under the bare slug. Substring replacement isn't enough — need a YAML-aware rewrite (`re.sub(r"(?m)^slug:\s*\S+\s*$", ...)`) or the verifier's R6 rule fires on slug mismatch.

STATUS: DONE
```
