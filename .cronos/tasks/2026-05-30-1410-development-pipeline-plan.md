---
agent_mode: auto
agent_model: opus-4-8
claude_session_id: 49a6ddf0-e3bc-4321-b082-e4181f45729e
created_at: '2026-05-30T14:10:56Z'
depends_on: []
id: 2026-05-30-1410-development-pipeline-plan
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Development pipeline plan
type: task
updated_at: '2026-06-04T10:26:43Z'
waiting_question: null
---

# Brief

In Delivery Notes space there are agents orchestrated by pipeline-orchestrator agent. These agents are not tailored to be run within Cronos. Please propose alike pipeline, that
- will provide veryfiable and repeatable outputs
- will work in any space in Cronos
- will log progress just like the pipeline in Delivery Notes does
- will be self improving - This is very very important

Propose how to create such as harnes / pipeline / workflow and prepare and save a plan, that will realize this (The plan should define cronos goals and tasks)

# History

```
2026-05-30T14:22:03Z [agent] run=0 model=claude-opus-4-8 mode=plan agents=explore
I'll start by exploring the Delivery Notes space to understand the existing pipeline-orchestrator agent and its orchestrated agents.

The data dir here is empty (worktree). Let me query the backend API to find the Delivery Notes space and its agents.

I need network or filesystem access to the Delivery Notes space. Let me try the API call (it needs approval).

I can read the Delivery Notes space. Let me explore its full structure to understand the framework, all agents, and the self-improvement mechanism.

Read tool works on explicit paths even though search is blocked. Let me read the framework contract and key files in parallel.

This is a sophisticated Agent Contract v1.0 system. Let me now understand the self-improvement mechanism and a sample sub-agent, plus survey the Cronos side in parallel.

I now have a thorough picture of both systems. Before writing, one scoping decision affects what "done" means here.

No answer — I'll proceed with the recommended approach: save a complete plan document with fully-specified goals/tasks, leaving board creation as your follow-up. Writing the plan now.

Plan saved to `DEVELOPMENT_PIPELINE_PLAN.md`. Now running the mandatory finalize step.

Standalone planning task; the plan document is the deliverable. Committing it to the task branch.

`git add` needs an approval that isn't being granted in this run, so I can't complete the commit autonomously. The plan document is saved in the workspace regardless. Let me record a memory of the key non-obvious findings, then finalize.

I investigated the Delivery Notes Agent Contract v1.0 harness (pipeline-orchestrator + framework) and Cronos's own primitives (goal/task DAG, worker, run traces, memory, skills), then wrote a complete build plan to `DEVELOPMENT_PIPELINE_PLAN.md`.

**Key proposal:** don't port the monolithic 700-line orchestrator — Cronos's goal/task DAG + worker *is* the orchestrator. The plan maps every phase to a child task gated by `depends_on`, adds a thin CC-v1 contract + verifier/normalizer, a `pipeline-gate` skill (the `post_phase_verify` analogue), a `pipeline-scaffold` skill that builds the DAG in any space, and a self-improvement flywheel (retro phase → known-issues → fix-as-data → fixture + memory write-back → contract version bump). This structurally fixes Delivery Notes' F-26 (protocol bypass) and sidesteps F-24 (worktree).

It addresses all four requirements and is defined as **4 sequential Cronos goals** (foundation → phase agents → orchestration glue → self-improvement) with fully-specified child tasks (briefs, deps, agent mode/model).

Two notes:
- The plan file is saved, but `git add`/`commit` required an approval that wasn't granted in this run, so the deliverable is uncommitted on the task branch — commit it manually when ready.
- I didn't create the goals live in the board (the scoping question was cancelled; I defaulted to "save plan only"). The plan's §5 is structured so `create-goal` can consume it directly if you want me to instantiate it.

MEMORY[reference]: The Delivery Notes space (`/data/spaces/delivery-notes/`) hosts a mature Agent Contract v1.0 pipeline harness — `.claude/agents/pipeline-orchestrator.md`, `.ai/framework/agent-contract-v1.md`, `known-issues.md` (F-NN catalog), `verify_outputs.py`, `normalize_outputs.py`, `run_evals.py`, `schemas/`.

MEMORY[project]: Cronos-native pipeline plan (`DEVELOPMENT_PIPELINE_PLAN.md`, 2026-05-30) maps pipeline phases to a goal/task DAG rather than porting the monolithic orchestrator; structured as 4 sequential goals (G1 contract+verifier, G2 phase agents, G3 scaffold+gate+logging, G4 self-improvement loop).

MEMORY[observation]: In this task harness, `ls`/`find`/`Glob` are blocked outside the task workspace, but the **Read tool works on explicit absolute paths** (e.g. reading other spaces' files like `/data/spaces/delivery-notes/...`). Backend API calls (curl/python urllib to `backend:8000`) and `git add`/`commit` require an approval that was not auto-granted in this run.

STATUS: DONE
```

```
2026-05-30T14:35:54Z [user]
Instantiate the plan - the mode was changed from planning to auto
```

```
2026-05-30T14:38:20Z [agent] run=1 model=claude-opus-4-8 mode=auto
The mode is now auto and you want the plan instantiated. Let me read the create-goal skill to use the correct API format, then create the goals.

Mode is auto now. I'll instantiate the 4 goals and their child tasks in the `cronos-development` space via the API, wiring intra- and cross-goal dependencies. Let me write the instantiation script with self-contained briefs (since the plan file lives only in this workspace, briefs reference the readable Delivery Notes source files).

All 4 goals and 23 tasks created. Let me verify the dependency wiring was accepted (intra-goal task deps and cross-goal goal deps).

Plan fully instantiated in the `cronos-development` board. All dependencies verified correct.

**Created: 4 goals + 23 child tasks** (all in backlog, none auto-running)

- **Goal 1 — Pipeline Foundation** (no deps): 1.1 contract → 1.2 schemas → 1.3 verifier → 1.4 normalizer → 1.5 fixtures
- **Goal 2 — Phase agents** (deps: G1): scout → analyst → architect → implementor → reviewer → doc-sync; tester-adapt branches off architect
- **Goal 3 — Orchestration glue** (deps: G1): state-writer → gate skill → scaffold skill (also deps G2) → branch-wiring → smoke run
- **Goal 4 — Self-improvement loop** (deps: G2 + G3): retro agent → {known-issues, memory write-back} → auto-applier → evals gate → versioning

Cross-goal gating is wired at the goal level (G2/G3 wait for G1; G4 waits for G2+G3), and each phase task chains to its predecessor, so the worker will execute them in the intended topological order once activated.

To start: activate **Goal 1** (`2026-05-30-1437-pipeline-foundation-cc-v1-contract-schem`) — it's the only one with no unmet dependencies. Briefs are self-contained and point to the Delivery Notes source files and Cronos modules, since the plan document itself lives only in this task's workspace.

Note: the earlier `git add/commit` of `DEVELOPMENT_PIPELINE_PLAN.md` still needs manual approval — the plan file and `instantiate_pipeline.py` are uncommitted in this workspace.

STATUS: DONE
```
