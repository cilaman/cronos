---
agent_mode: auto
agent_model: opus
claude_session_id: 0b5c8bbf-b34a-4486-bfdf-1aeda5d6eb9f
created_at: '2026-06-05T23:27:19Z'
depends_on:
- 2026-06-05-2327-test-backend-harness-tools-resolver
feature_key: null
feature_state: null
id: 2026-06-05-2327-review-backend-harness-tools-resolver
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-05-2327-backend-harness-tools-resolver
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: review – backend-harness-tools-resolver
type: task
updated_at: '2026-06-19T12:17:49Z'
waiting_question: null
---

# Brief

CC-v1 review phase for sub-goal: Backend harness tools resolver.

## Feature request (full scope this slice must deliver)
Implement the harness runtime tools-resolver so agent and skill nodes resolve to a
real `AiToolEntry`, and briefs are composed with the correct agent header / skill prefix.

Acceptance criteria:
1. **Real resolver.** Replace the stub `_tools_resolver` at `backend/app/worker.py:470-471`
   (signature `(space_id: str, agent_ref: str) -> AiToolEntry | None`) with a real implementation.
   REUSE the existing scanners — do not re-implement scanning: `_scan_category` and `_scan_skills`
   in `backend/app/tools/scanner.py`, and `_scan_context` in `backend/app/api/tools.py`. Resolve by
   matching `agent_ref` against agent, skill, command and context entries, searching the space-scoped
   `.claude` directory and the global scope. Return `None` on no match.
2. **Wiring.** The resolver is already passed into `HarnessExecutor` and called at
   `backend/app/harnesses/executor.py:753`; confirm the resolved `agent_entry` flows into
   `compose_brief` so the agent header is added.
3. **Skill prefix.** When `agent_ref` resolves to a skill (path under `.claude/skills/`), the resolved
   entry must let `brief_composer._is_skill` detect it so the brief is prefixed with `/<skill-name>`
   (see `backend/app/harnesses/brief_composer.py`). Verify agent vs skill vs plain-ref behaviour.
4. **Tests.** Add pytest covering: agent match, skill match (asserts `/` prefix in composed brief),
   command/context match, miss → `None`, and space-vs-global scoping. Keep the 60% coverage floor:
   `cd backend && pytest tests/ --cov=app --cov-report=term-missing`.

Backend-only changes under `backend/app/`. Do not modify the harness Pydantic models.

## Scope (files this slice is allowed to touch)
backend/app/worker.py (the _tools_resolver function only), reusing backend/app/tools/scanner.py and backend/app/api/tools.py scanners; backend/app/harnesses/brief_composer.py (read-only reference); new backend/tests/ files

## Phase instructions
- Agent contract: `.claude/agents/pipeline-reviewer.md` (class=review).
- Read the prior phase artifact(s) in `.cronos/pipeline/backend-harness-tools-resolver/`.
- Scout report: `.cronos/pipeline/backend-harness-tools-resolver/scout-report-backend-harness-tools-resolver.md`.
- Emit your artifact (class=review) into `.cronos/pipeline/backend-harness-tools-resolver/`.
- The impl phase fans out one iteration at a time per the design's iterations[]; run /goal-branch-setup before the first code edit and /goal-task-commit after each.

Then run: /pipeline-gate

When you end up in STATUS: BLOCKED and you need to respawn implementor in order to FIX findings, you have the permission to do so. You can re-spawn implementor and tester up to 3 times in order to satisfy passing requirements

# History

```
2026-06-06T01:01:58Z [agent]
Now let me inspect the actual code that landed - the implementor's claim is at backend/app/worker.py.

I have the existing task list. Continuing the review work — task #2 is in_progress. Let me inspect the source files in the workspace (which is at HEAD `c42df8c`, before impl) and the related files at the impl commit.

Now let me check the worker.py source in the workspace (where the actual implementation should land), and confirm the current state at the test commit:

Let me run the tests to confirm they pass at the current state:

Wiring is confirmed read-only and untouched. R5 holds.

Now let me also verify the verifier rules and double-check the validation_command_passed claim:

Review complete. Implementation cleanly satisfies all 6 requirements: scope is respected (only worker.py + new test file touched), all design invariants hold, test gate passed at 84.86% coverage. No blocking findings — only two cosmetic items (unused `import pytest`, absolute-vs-relative import style). Verdict: **pass**.

Now self-verify the artifact before running the gate:

Artifact verified (exit 0, PROCEED). Now closing the gate.

The supplied `upstream_task_id` points to the test phase, but the gate is for the `review` phase whose artifact I just produced in this run. Using my own task id as upstream so trace-derived metrics map to the correct phase.

Verify passed (exit 0, outcome=proceed). Now recording state via state_writer.

Pipeline state recorded — review phase is now marked `done` with `gate_decision=proceed`. Phase is not retro, so Steps 3b/3c are skipped.

gate PASS — review / backend-harness-tools-resolver
  artifact: .cronos/pipeline/backend-harness-tools-resolver/review-report-backend-harness-tools-resolver--attempt1.md
  verdict: pass (no blocking findings; 2 low-severity cosmetic items recorded)

STATUS: DONE
```
