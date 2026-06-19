---
cc_version: '1.0'
agent: pipeline-doc-sync
slug: backend-harness-tools-resolver
phase: doc
status: done
confidence: 1.0
inputs_used:
  - .cronos/pipeline/backend-harness-tools-resolver/impl-report-backend-harness-tools-resolver--i3.md
  - .cronos/pipeline/backend-harness-tools-resolver/test-report-backend-harness-tools-resolver.md
  - .cronos/pipeline/backend-harness-tools-resolver/review-report-backend-harness-tools-resolver--attempt1.md
  - docs/HARNESSES.md
  - backend/app/worker.py
  - backend/app/harnesses/brief_composer.py
  - backend/app/harnesses/executor.py
outputs_produced:
  - .cronos/pipeline/backend-harness-tools-resolver/doc-report-backend-harness-tools-resolver.md
  - docs/HARNESSES.md
blockers: []
next_consumer: user
intentionally_not_updated:
  - path: CLAUDE.md
    reason: No API changes, Pydantic models, or architecture changes — only worker module scope and test suite. Architecture documentation in CLAUDE.md is still accurate.
  - path: backend/app/harnesses/brief_composer.py
    reason: Verified read-only. Implementation leverages existing _is_skill behavior; no changes needed.
  - path: backend/app/harnesses/executor.py
    reason: Verified read-only. Agent entry flows from resolver to compose_brief unchanged; no executor code changes.
metrics:
  tool_calls: 5
  files_read: 7
  memory_hits: 0
  docs_updated: 1
  docs_considered: 4
---

## Summary

Updated `docs/HARNESSES.md` to reflect the working tools resolver implementation. Removed the caveat about skill nodes not auto-firing as `/skill` (§7, lines 381–389) and deleted the corresponding Known limitations entry (item 6). The resolver implementation in `backend/app/worker.py` (function `resolve_tool`, lines 223–249) now searches space-scoped and global `.claude` directories, correctly resolves agents, skills, commands, and contexts, and enables skill briefs to be prefixed with `/<skill-name>` automatically. Documentation now accurately reflects this behaviour.

## Updated docs

| File | Changes | Rationale |
|------|---------|-----------|
| `docs/HARNESSES.md` §7 "Connecting nodes to real agents and skills" | Replaced caveat about stub resolver (lines 381–389) with explanation of how the resolver works: space-scoped entries shadow global, agents/skills/commands/contexts resolved in category order, skills auto-prefix with `/<skill-name>`, agents embed `Agent: <ref>`. | The stub resolver is now a real implementation that passes all 14 acceptance tests. Users need to know the scope priority and expected brief format. |
| `docs/HARNESSES.md` Known limitations table | Deleted item 6 ("Skill nodes don't auto-fire as `/skill`") — the root cause (stub resolver returning `None`) is fixed. Items 1–5 remain. | The limitation no longer exists; scope is still frontend contract mismatches, not backend functionality. |

## Intentionally not updated

The following documentation files were considered but not updated:

| File | Reason |
|------|--------|
| `CLAUDE.md` | No changes to API contracts, Pydantic models, or architecture. The entry at "Key modules" for `backend/app/harnesses/brief_composer.py` and the executor description remain accurate. The `resolve_tool` helper is an implementation detail internal to `worker.py`. |
| `backend/app/harnesses/brief_composer.py` | Verified read-only. The `_is_skill` function already correctly detects `"skills/"` in the resolved entry's path, producing the skill prefix without code changes. |
| `backend/app/harnesses/executor.py` | Verified read-only. The `agent_entry` returned by `tools_resolver` flows unchanged into `compose_brief` at line 758, requiring no executor changes. |

## Assumptions

- The resolver is now in production use via the `_tools_resolver` closure at `worker.py:672–675`. The documentation update assumes this is stable and fully tested (14 test cases pass, 2435 total tests, 84.86% coverage).
- No API contracts, Pydantic models, or frontend types were changed in the implementation phase, so no schema documentation updates are needed.
- The resolver implementation is deterministic and correct: space scope scans agents → skills → commands → context in that order before falling back to global scope, matching the test matrix.

## Open questions

None.

## Next consumer brief

Documentation is now aligned with the implemented resolver. The caveat about degraded skill detection has been removed, and users are informed that skills will auto-fire via `/<skill-name>` prefix. All 2435 tests pass; 84.86% coverage. Ready for gate closure.
