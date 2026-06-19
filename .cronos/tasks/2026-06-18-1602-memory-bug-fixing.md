---
agent_mode: auto
agent_model: default
claude_session_id: 107df155-20a3-4dc7-b6f0-8c25684e2e9b
created_at: '2026-06-18T16:02:27Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-18-1602-memory-bug-fixing
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 1
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: done
title: Memory bug fixing
type: task
updated_at: '2026-06-18T16:07:23Z'
waiting_question: null
---

# Brief

Prepare Goals for memory bugfix. The goals must use cc v1 pipeline for sub goals. Commit all bug fixes (also across multiple goals) to one single feature branch.

Critical — correctness bugs that defeat the system's purpose

1. Multiplicative boost from zero is mathematically dead — confidence: certain (proven)

boost() computes min(score * 1.2, 10.0). New items are created with score=0.0, and 0.0 × 1.2 = 0.0, forever. Confirmed both numerically and against live data: 112/124 items sit at score=0.00; only the 12 seed items (created 2026-05-27 with non-zero scores) ever rose to 10.0. Every organically-written memory is pinned at zero.

The damage is the cascade:


Index ordering "by score" is meaningless — nearly everything ties at 0.00.
should_prune() flags score < 0.1 as prunable, so every organic memory becomes prune-eligible the instant its TTL lapses, regardless of how often it was used. The score meant to protect valuable memories does the opposite.


Fix: one line — additive (score + increment), floored (max(score, 0.5) * 1.2), or seed create() with score > 0. The lifecycle test only ever exercises boost(1.0, …), never boost(0.0, …) — a test blind spot exactly where the bug lives.

2. decay() is dead code — confidence: certain

The half-life decay function the entire score concept depends on is defined and never called anywhere. Scores are therefore static: seeds frozen at 10.0, organics frozen at 0.0. Combined with #1, the score field is non-functional as both a ranking and an aging signal — it is decorative. Either wire decay in (cleanest: apply at read-time inside get(), no sweep needed) or delete it and stop implying scores age.

3. Injection drops the body — confidence: certain

build_prompt() emits - **{title}** ({kind}) plus, only if it differs from the title, the first line of the body. Because title is the first body line truncated to 120 chars, for most items they are identical and only the title is injected. File paths, commit hashes, and step-by-step procedures — the entire reason to store a body — never reach the agent. This is the biggest practical loss of value and the cheapest fix with the highest ROI.

Interaction: a perverse retention profile — confidence: high

The three bugs above compound. Items never retrieved keep ttl=None and live forever (junk accumulates). Useful-but-seasonal items get a 7-day TTL on first retrieval and are archived 7 days after their last use — and score-0 means usage history can't save them. The system preferentially culls the memories that proved useful and hoards the ones that never matched.

# History

```
2026-06-18T16:07:23Z [agent] run=0 model=claude-sonnet-4-6 mode=auto
I'll start by reading the memory store code to understand the bugs, then set up the CC v1 pipeline goal structure.

Now I have a clear picture of all three bugs. Let me check the pipeline-scaffold skill and look at how previous goals were structured.

Now I'll run the pipeline-scaffold to create the CC v1 pipeline goal structure for the memory bug fixes.

The pipeline goal is scaffolded. Now let me verify the structure and finalize this task.

The pipeline goal `2026-06-18-1606-memory-bug-fixing` is created with all 7 CC v1 phase tasks wired in the correct dependency order (scout → analysis → design → impl → test → review → doc). Now I'll finalize this task.

## Step 1 — Verify completion

The task asked to prepare CC v1 pipeline Goals for the memory bugfixes. I created goal `2026-06-18-1606-memory-bug-fixing` with all 7 CC v1 phase tasks (scout → analysis → design → impl → test → review → doc), with proper dependencies wired and the feature branch `feature/memory-bug-fixing` specified in the impl brief. Complete.

## Step 3 — Handle git

The changes are only `.cronos/memory/` score-boost files (runtime data from memory access) and pipeline state files. Let me check for the pipeline state files I created:

## Step 4 — Write memory

MEMORY[fact]: Scaffolded CC v1 pipeline goal `2026-06-18-1606-memory-bug-fixing` (slug=memory-bug-fixing) for 3 critical memory system bugs: (1) multiplicative boost from zero in memory_lifecycle.py::boost(), (2) decay() dead code never called, (3) agent.py::build_prompt() drops memory body. Goal has 7 phase tasks wired scout→analysis→design→impl→test→review→doc. All fixes target feature branch `feature/memory-bug-fixing`. Pipeline state at .cronos/pipeline/memory-bug-fixing/.

MEMORY[observation]: When scaffolding a pipeline goal as a standalone task, the pipeline state files (.cronos/pipeline/{slug}/) get committed to whatever branch the main worktree is on — not necessarily main. If the main worktree is on a feature branch, verify the pipeline state files will be accessible when agents run.

STATUS: DONE
```
