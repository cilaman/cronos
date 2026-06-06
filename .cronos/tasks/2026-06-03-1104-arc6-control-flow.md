---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T11:04:55Z'
depends_on:
- 2026-06-03-1104-arc6-executor
id: 2026-06-03-1104-arc6-control-flow
manual_order: 0
parent_id: 2026-06-03-1104-arc-6-harnesses
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: arc6 control flow
type: goal
updated_at: '2026-06-03T21:19:06Z'
waiting_question: null
---

# Brief

# Pipeline goal: 6.3 Control flow node semantics

Pipeline run scaffolded by `/pipeline-scaffold`. Shared branch: `feature/arc-6-harnesses`.
Part of umbrella goal `arc-6-harnesses` (Arc 6 — Harnesses).

## Request

Implement the three control-flow evaluators in the interpreter. These run
**in-process; never a subprocess, never a child task.**

- **Decision:** branch on the upstream Agent signal — STATUS marker (already in
  `AgentResult.status`), regex on `final_text_snippet`, or harness-variable compare.
  Define precedence + missing-signal behaviour; pick the outgoing edge by `condition` label.
- **Wait:** human (map to `TaskState.WAITING` + resume via the existing reply/`pending_messages`
  mechanism), time (resume after N), or upstream signal.
- **Aggregator:** join N upstreams; emit on **all** or **any** (configurable). Define
  partial-failure semantics.
- Reject/bound Decision-edge cycles in the 6.1 validator; add an unbounded-wait guardrail.

Acceptance: a Decision routes to edge A on `STATUS: DONE`, edge B on `STATUS: BLOCKED`;
Aggregator `all` waits for both, `any` fires first; Wait(human) parks in WAITING and
resumes on reply.


## Child tasks (one per CC-v1 phase)

1. scout    — pipeline-scout    (research)
2. analysis — pipeline-analyst  (analysis)
3. design   — pipeline-architect(design)
4. impl     — pipeline-implementor (implementation; may fan out per iteration)
5. test     — tester            (test)
6. review   — pipeline-reviewer (review; may loop on verdict=needs_fix)
7. doc      — pipeline-doc-sync (doc; commit-only — no merge to main)

Each phase task ends by invoking `/pipeline-gate` which closes the gate from
the artifact's YAML header — no prose parsing. The doc task commits via
`/goal-task-commit` (not /goal-finalize); the final merge happens in the Arc 6
integration task.

# History

```
2026-06-03T21:19:06Z [agent]
All tasks complete. Completed 7, skipped 0 already-done.
```
