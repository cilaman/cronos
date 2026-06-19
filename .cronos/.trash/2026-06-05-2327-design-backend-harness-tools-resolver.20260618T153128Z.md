---
agent_mode: auto
agent_model: opus
claude_session_id: ae475898-a8e0-437c-bbf8-f65611a01271
created_at: '2026-06-05T23:27:18Z'
depends_on:
- 2026-06-05-2327-analysis-backend-harness-tools-resolver
feature_key: null
feature_state: null
id: 2026-06-05-2327-design-backend-harness-tools-resolver
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
title: design – backend-harness-tools-resolver
type: task
updated_at: '2026-06-18T15:28:06Z'
waiting_question: null
---

# Brief

CC-v1 design phase for sub-goal: Backend harness tools resolver.

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
- Agent contract: `.claude/agents/pipeline-architect.md` (class=design).
- Read the prior phase artifact(s) in `.cronos/pipeline/backend-harness-tools-resolver/`.
- Scout report: `.cronos/pipeline/backend-harness-tools-resolver/scout-report-backend-harness-tools-resolver.md`.
- Emit your artifact (class=design) into `.cronos/pipeline/backend-harness-tools-resolver/`.
- The impl phase fans out one iteration at a time per the design's iterations[]; run /goal-branch-setup before the first code edit and /goal-task-commit after each.

Then run: /pipeline-gate

# History

```
2026-06-06T00:42:03Z [agent]
Delegating to the pipeline-architect agent for the design phase.

Design phase complete. Now invoking the pipeline gate.

Verify passed (exit 0). Now recording state.

Gate passed cleanly. Phase is not `retro` so Steps 3b/3c skip.

gate PASS — design / backend-harness-tools-resolver
  artifact: .cronos/pipeline/backend-harness-tools-resolver/design-report-backend-harness-tools-resolver.md

STATUS: DONE
```
