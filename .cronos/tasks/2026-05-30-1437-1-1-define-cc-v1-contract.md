---
agent_mode: auto
agent_model: opus
claude_session_id: a5510705-659e-4636-a944-533eac367a7d
created_at: '2026-05-30T14:37:55Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-05-30-1437-1-1-define-cc-v1-contract
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-05-30-1437-pipeline-foundation-cc-v1-contract-schem
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 1.1 Define CC-v1 contract
type: task
updated_at: '2026-06-19T12:17:47Z'
waiting_question: null
---

# Brief

Author `backend/app/pipeline/contract.py` (+ `backend/app/pipeline/CONTRACT.md`). Adapt Agent Contract v1.0 to Cronos. Define: the mandatory YAML artifact header (agent, slug, phase, status[done|partial|blocked|failed], confidence[0-1], inputs_used[], outputs_produced[], blockers[], next_consumer, metrics{tool_calls,files_read,memory_hits}); required markdown sections (Summary, Coverage, Findings|Decisions, Assumptions, Open questions|Blockers, Next consumer brief); the no-prose-parsing rule; slug discipline (agents never re-derive the goal slug); and `CC_VERSION = "1.0"`. Cronos changes vs original: `kb_hits`->`memory_hits`; agents NEVER write duration_s/token_spend (those come from the run trace). Artifacts live at `{space}/.cronos/pipeline/{goal_slug}/<phase>-report-{goal_slug}.md`.

## Acceptance
- contract.py exposes header field list, required-section list, CC_VERSION.
- CONTRACT.md documents header + sections + R1-R7 rule names.
- Importable; no agents referenced yet.

## Reference material (read by absolute path)
- Delivery Notes contract: `/data/spaces/delivery-notes/.ai/framework/agent-contract-v1.md`
- Delivery Notes orchestrator: `/data/spaces/delivery-notes/.claude/agents/pipeline-orchestrator.md`
- Delivery Notes known-issues (F-NN): `/data/spaces/delivery-notes/.ai/framework/known-issues.md`
- Cronos primitives: `backend/app/{agent,worker,goal_sync,storage,models,trace_store,trace_parser,memory_store,memory_retrieval}.py`
- Memory entries `delivery-notes-pipeline` and `delivery-notes-pipeline-cronos-mapping` surface the design rationale via retrieval.

# History

```
2026-05-30T15:10:21Z [agent]
Import smoke check passes. All exposed names are present and have the expected values.

Now I'll finalize via the mandatory `task-finalize` skill.

Step 1 — Verify completion: All three acceptance criteria met:
- `contract.py` exposes `HEADER_FIELDS`, `REQUIRED_SECTIONS`, `R_RULES`, `CC_VERSION = "1.0"` (plus status values, metrics ownership tuples, artifact path template).
- `CONTRACT.md` documents header + sections + R1–R7 rule names.
- Import smoke check confirmed importability; no agents referenced.

Step 3 — Handle git: detect task context.

Task has a parent — this is a goal child task. I'll delegate to `goal-task-commit`.

Step 1 — verify branch.

I'm on a `cronos/*` branch — need to set up the goal feature branch first.

No feature branch exists for this goal yet. This is the first task in the goal — I need to set up the goal branch first.

On `feature/pipeline-foundation-cc-v1-contract-schem`. Now resuming goal-task-commit: run tests, then commit.

Tests pass (1012 passed, 0 failed). Resuming goal-task-commit: stage and commit.

I'll stage only the pipeline source files, leaving the `.coverage` and `__pycache__` artifacts alone.

Commit `7c15965` pushed to `feature/pipeline-foundation-cc-v1-contract-schem`. Resuming task-finalize Step 4 — write memory.

MEMORY[fact]: CC-v1 contract module landed at `backend/app/pipeline/contract.py` + `backend/app/pipeline/CONTRACT.md` (re-exported via `backend/app/pipeline/__init__.py`). Constants: `CC_VERSION="1.0"`, `HEADER_FIELDS` (cc_version, agent, slug, phase, status, confidence, inputs_used, outputs_produced, blockers, next_consumer, metrics), `REQUIRED_SECTIONS` (Summary, Coverage, Findings, Assumptions, Open questions, Next consumer brief), `R_RULES` (R1–R7), `AGENT_REPORTED_METRICS` (tool_calls, files_read, memory_hits), `TRACE_OWNED_METRICS` (duration_s, token_spend), `ARTIFACT_PATH_TEMPLATE = "{space}/.cronos/pipeline/{goal_slug}/{phase}-report-{goal_slug}.md"`. Pure data module, no agents referenced, no runtime behavior.

MEMORY[project]: Pipeline Foundation goal (`feature/pipeline-foundation-cc-v1-contract-schem`) — task 1.1 done 2026-05-30. Cronos deviations from Delivery Notes Agent Contract v1.0: `kb_hits`→`memory_hits` (memory_store substrate replaces `.kb/`), agents NEVER write `duration_s`/`token_spend` (derived from run trace by trace_parser), artifacts at `{space}/.cronos/pipeline/{goal_slug}/...` instead of `.ai/pipeline/{slug}/...`. **Why:** these are load-bearing decisions downstream tasks (1.2 per-class schemas, 1.3 verifier, 1.4 normalizer) must obey. **How to apply:** read `backend/app/pipeline/CONTRACT.md` §7 before working on tasks 1.2–1.5.

MEMORY[procedure]: First task of a Cronos goal → run `goal-branch-setup` to create `feature/<goal_slug>` from `origin/main` and switch the worktree off `cronos/<task-id>`. Slug derivation: strip `YYYY-MM-DD-HHMM-` prefix from the goal ID. Then `goal-task-commit` stages source files only (avoid committing `backend/.coverage` artifact), commits with the task title as subject, and pushes via `CRONOS_GIT_TOKEN` HTTPS auth.

STATUS: DONE
```
