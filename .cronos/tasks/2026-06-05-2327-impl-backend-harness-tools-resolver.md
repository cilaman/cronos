---
agent_mode: auto
agent_model: sonnet
claude_session_id: 636ff754-7c0d-4908-81db-e6e0ecb1c651
created_at: '2026-06-05T23:27:18Z'
depends_on:
- 2026-06-05-2327-design-backend-harness-tools-resolver
feature_key: null
feature_state: null
id: 2026-06-05-2327-impl-backend-harness-tools-resolver
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
state: done
title: impl – backend-harness-tools-resolver
type: task
updated_at: '2026-06-06T00:51:31Z'
waiting_question: null
---

# Brief

CC-v1 impl phase for sub-goal: Backend harness tools resolver.

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
- Agent contract: `.claude/agents/pipeline-implementor.md` (class=implementation).
- Read the prior phase artifact(s) in `.cronos/pipeline/backend-harness-tools-resolver/`.
- Scout report: `.cronos/pipeline/backend-harness-tools-resolver/scout-report-backend-harness-tools-resolver.md`.
- Emit your artifact (class=implementation) into `.cronos/pipeline/backend-harness-tools-resolver/`.
- The impl phase fans out one iteration at a time per the design's iterations[]; run /goal-branch-setup before the first code edit and /goal-task-commit after each.

Then run: /pipeline-gate

# History

```
2026-06-06T00:51:31Z [agent]
I'll start by reading the prior phase artifacts and relevant source files to understand what needs to be implemented.

Now let me check the design report and the actual worker.py stub location before coding.

Now let me check the space store structure and existing imports in worker.py:

Now I have everything I need. Let me run goal-branch-setup first, then implement the changes.

The feature branch is checked out in the main worktree. I'll work in `/data/spaces/cronos-development`. Let me check where `class Worker` starts to place the module-level function:

Now I'll implement iteration I1: add `resolve_tool` as a module-level function and update the `_tools_resolver` closure.

Now add the `resolve_tool` module-level function just before `class Worker`:

Now update the `_tools_resolver` closure to delegate to `resolve_tool`:

Now let me verify the changes look correct:

The implementation looks correct. Now run the I1 validation:

All 94 tests pass. Now implement iteration I2 — the test file. Let me check the existing brief composer test for HarnessNode construction patterns:

Now I'll write the test file for I2:

All 14 tests pass. Now run I3 — the full suite with coverage floor:

2435 tests pass with 84.86% coverage (well above the 60% floor). Now commit the changes and emit the impl-report artifact.

First, let me write the impl report:

Now commit and push the changes:

Committed and pushed. Now run the pipeline gate:

I need to fix the impl-report filename to match the CC-v1 convention for implementation phase (requires `--{iter_id}` suffix). The design has iterations I1-I3; I'll gate on I3 as the final iteration.

Now run the pipeline gate steps:

The impl-report needs additional required fields. Let me check the implementation schema:

Now I'll rewrite the impl-report with all required fields:

Verify passes (exit 0). Now run the state writer:

Both exits are 0. Now commit the updated artifact and finalize:

Now finalize the task:

No uncommitted changes — everything was already committed and pushed via goal-task-commit steps. The task is a goal child, and the commits are on `feature/harness-editor-usability`.

**Step 1 — Completion verified:**
- `resolve_tool` module-level helper implemented in `backend/app/worker.py` (lines 222-249)
- `_tools_resolver` closure updated to delegate to `resolve_tool` (3-line wrapper)
- 14 tests in `backend/tests/test_tools_resolver.py` all pass
- Full suite: 2435 tests, 84.86% coverage — above 60% floor
- Pipeline gate: verify exit 0, state written, pushed to origin

MEMORY[fact]: resolve_tool helper added to backend/app/worker.py at module scope (lines 222-249); replaces the stub _tools_resolver closure at line 672 with a 4-line delegating wrapper. Scans space scope first (agents→skills→commands→context) then global scope; lazy-imports _scan_context from app.api.tools to avoid circular import. Tests at backend/tests/test_tools_resolver.py (14 cases).

STATUS: DONE
```
