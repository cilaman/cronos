---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-30T14:37:55Z'
depends_on:
- 2026-05-30-1437-pipeline-phase-agents-under-cc-v1
- 2026-05-30-1437-orchestration-logging-glue-scaffold-gate
feature_key: null
feature_state: null
id: 2026-05-30-1437-self-improvement-loop-retro-known-issues
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Self-improvement loop (retro -> known-issues -> fix-as-data -> evals)
type: goal
updated_at: '2026-06-19T12:17:47Z'
waiting_question: null
---

# Brief

Close the flywheel so every run makes the next better, in this space AND every other space. Retrospective phase -> known-issues catalog -> fix captured as data (normalize rule / verifier rule / prompt / contract change) -> golden+negative fixture + MEMORY write-back + CC version bump, gated by the Goal-1 evals.

## Child tasks
1. retro phase agent 2. known-issues store 3. memory write-back 4. auto-improvement applier 5. evals + CI gate 6. contract versioning + changelog

## Reference material (read by absolute path)
- Delivery Notes contract: `/data/spaces/delivery-notes/.ai/framework/agent-contract-v1.md`
- Delivery Notes orchestrator: `/data/spaces/delivery-notes/.claude/agents/pipeline-orchestrator.md`
- Delivery Notes known-issues (F-NN): `/data/spaces/delivery-notes/.ai/framework/known-issues.md`
- Cronos primitives: `backend/app/{agent,worker,goal_sync,storage,models,trace_store,trace_parser,memory_store,memory_retrieval}.py`
- Memory entries `delivery-notes-pipeline` and `delivery-notes-pipeline-cronos-mapping` surface the design rationale via retrieval.

# History

```
2026-05-30T23:30:51Z [agent]
All tasks complete. Completed 6, skipped 0 already-done.
```
