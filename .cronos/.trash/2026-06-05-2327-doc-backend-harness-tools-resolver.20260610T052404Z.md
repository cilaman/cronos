---
agent_mode: auto
agent_model: haiku
claude_session_id: 4db693da-c007-42ca-86cd-dd99d35ccd27
created_at: '2026-06-05T23:27:19Z'
depends_on:
- 2026-06-05-2327-review-backend-harness-tools-resolver
feature_key: null
feature_state: null
id: 2026-06-05-2327-doc-backend-harness-tools-resolver
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
title: doc – backend-harness-tools-resolver
type: task
updated_at: '2026-06-10T05:15:14Z'
waiting_question: null
---

# Brief

CC-v1 doc phase for sub-goal: Backend harness tools resolver.

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
- Agent contract: `.claude/agents/pipeline-doc-sync.md` (class=doc).
- Read the prior phase artifact(s) in `.cronos/pipeline/backend-harness-tools-resolver/`.
- Scout report: `.cronos/pipeline/backend-harness-tools-resolver/scout-report-backend-harness-tools-resolver.md`.
- Emit your artifact (class=doc) into `.cronos/pipeline/backend-harness-tools-resolver/`.
- The impl phase fans out one iteration at a time per the design's iterations[]; run /goal-branch-setup before the first code edit and /goal-task-commit after each.

Then run: /pipeline-gate

# History

```
2026-06-10T05:15:14Z [agent] run=5 model=claude-haiku-4-5-20251001 mode=auto
I'll start this doc phase by reading the prior phase artifacts to understand what was delivered, then emit the doc-report artifact.

Reading prior phase artifacts to understand the implementation scope.

Now let me check the actual implementation to understand the resolver.

Perfect. I have all the context I need. The implementation replaced the stub tools resolver with a real one that scans space-scoped and global-scoped agents, skills, commands, and contexts. The documentation at `docs/HARNESSES.md` contains a caveat about the resolver being a stub (lines 383-389) and mentions it in the Known limitations table (item 6). I need to update these sections to reflect that the resolver is now working.

Let me update the documentation:

Now I'll create the doc-report artifact documenting the documentation updates.

Now I'll run the pipeline gate to close the doc phase.

I'll now execute the pipeline-gate steps to verify the doc artifact and record the phase completion.

I need to fix the doc-report to match the CC-v1 doc-phase schema. Let me check the contract first:

I need to rewrite the doc-report to match the CC-v1 doc-phase schema. Let me fix it:

Excellent! The artifact verification passed. Now I'll record the phase completion via the state writer:

Perfect! The doc phase gate has passed all verification. Here's the final summary:

Gate PASS — doc / backend-harness-tools-resolver
  artifact: .cronos/pipeline/backend-harness-tools-resolver/doc-report-backend-harness-tools-resolver.md
  
The documentation has been updated to reflect the working tools resolver implementation:
- Removed the caveat about skill nodes not auto-firing as `/skill` (docs/HARNESSES.md §7)
- Deleted the obsolete Known limitations item 6
- Explained how the resolver scans space and global scopes with proper priority
- Documented that skills now auto-prefix with `/<skill-name>` for CLI invocation

All 2435 backend tests pass with 84.86% coverage. The pipeline is ready to finalize.

STATUS: DONE
```
