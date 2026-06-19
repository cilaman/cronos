---
agent_mode: auto
agent_model: sonnet
claude_session_id: ece60566-6382-4adc-b423-2926d6b32402
created_at: '2026-05-30T14:37:55Z'
depends_on:
- 2026-05-30-1437-1-4-normalizer
feature_key: null
feature_state: null
id: 2026-05-30-1437-1-5-regression-fixture-harness
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
title: 1.5 Regression fixture harness
type: task
updated_at: '2026-06-19T12:17:47Z'
waiting_question: null
---

# Brief

Create `backend/app/pipeline/fixtures/` with golden (valid) and negative (must-fail-after-normalize) artifacts for each class, and a pytest suite under `backend/tests/` asserting goldens pass verify and negatives still fail AFTER normalize. This is the eval baseline that gates all later contract/schema/normalizer changes.

## Acceptance
- pytest green: goldens pass, negatives fail post-normalize.
- Counts toward the 60% coverage floor.

## Reference material (read by absolute path)
- Delivery Notes contract: `/data/spaces/delivery-notes/.ai/framework/agent-contract-v1.md`
- Delivery Notes orchestrator: `/data/spaces/delivery-notes/.claude/agents/pipeline-orchestrator.md`
- Delivery Notes known-issues (F-NN): `/data/spaces/delivery-notes/.ai/framework/known-issues.md`
- Cronos primitives: `backend/app/{agent,worker,goal_sync,storage,models,trace_store,trace_parser,memory_store,memory_retrieval}.py`
- Memory entries `delivery-notes-pipeline` and `delivery-notes-pipeline-cronos-mapping` surface the design rationale via retrieval.

# History

```
2026-05-30T15:52:32Z [agent]
I'll start by reading the existing pipeline code and reference materials to understand what fixtures I need to create.

Let me look at the actual workspace directly.

The pipeline files are on the feature branch. I need to merge/rebase the feature branch into this worktree. Let me read the key files first.

I need to check out the feature branch in this worktree to get the pipeline code from previous tasks.

The feature branch is used by another worktree. Let me read the pipeline files directly from that worktree.

Now let me read the contract and schemas to understand all the rules.

Let me read one schema for reference and look at the existing test files to understand patterns.

Let me read the remaining schemas to build complete golden fixtures.

Now I have all the information I need. Let me create the fixture directory structure and all files.

Now let me create the negative fixtures. Starting with research negatives:

Now let me create the test file:

Now let me run the tests to see if they pass:

All 23 tests pass. The coverage failure is from running only this file in isolation. Let me run the full test suite to confirm the 60% floor is met:

All 1144 tests pass with 81.93% coverage. Now let me commit the changes to the feature branch:

Committed. Now let me run the task finalization skill.

This is a goal child task. The changes were already committed to the feature branch (`feature/pipeline-foundation-cc-v1-contract-schem`) directly in the feature worktree. Invoking goal-task-commit for the push step:

The commit is in place on the feature branch. Now I'll push it:

Pushed successfully. Now writing memory and emitting STATUS.

MEMORY[fact]: CC-v1 regression fixture harness landed at `backend/app/pipeline/fixtures/` — 7 golden artifacts (one per class: research/analysis/design/implementation/test/review/doc) and 14 negative fixtures (2 per class) targeting hard-fail conditions normalize() cannot heal (wrong cc_version, missing required fields, R3/R4/R-impl-5/R-val-1/R-val-3/R-rev-2/R-rev-4/R-doc-3/R-doc-4 violations, trace-owned metrics). Test suite at `backend/tests/test_pipeline_fixtures.py` — 23 tests parametrized over the manifest. All 1144 tests pass, 81.93% coverage.

STATUS: DONE
```
