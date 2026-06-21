---
cc_version: '1.0'
agent: pipeline-doc-sync
slug: g05-structured-completion
phase: doc
status: done
confidence: 0.95
inputs_used:
  - .cronos/pipeline/g05-structured-completion/impl-report-g05-structured-completion--i5.md
  - .cronos/pipeline/g05-structured-completion/review-report-g05-structured-completion--attempt1.md
  - CLAUDE.md
  - docs/HARNESSES.md
outputs_produced:
  - .cronos/pipeline/g05-structured-completion/doc-report-g05-structured-completion.md
  - CLAUDE.md
  - docs/HARNESSES.md
intentionally_not_updated:
  - README.md (high-level ops docs; no explicit mention of STATUS format needed)
  - TESTING.md (unit test guide; internal format changes, no test-authoring impact)
  - .claude/agents/* (agent contract definitions; updated by impl, not doc scope)
  - .claude/skills/task-finalize/SKILL.md (already updated by impl phase with new block format)
blockers: []
next_consumer: null
metrics:
  tool_calls: 8
  files_read: 4
  memory_hits: 0
  docs_updated: 2
---

## Summary

Documented the G05 structured completion sentinel implementation across the main
architecture and harness documentation. Updated module descriptions in CLAUDE.md
and signal precedence / agent completion sections in docs/HARNESSES.md to
reflect the new `cronos_status` fenced-JSON block format (primary channel) and
the deprecated `STATUS:` fallback. Added a new subsection explaining the
completion sentinel block structure and the `NO_CRONOS_STATUS` exit reason.

All documentation changes are now in place; the implementation is complete and
documented.

## Files updated

| File | Change |
|------|--------|
| `CLAUDE.md` | Updated `backend/app/memory_parser.py` description to include `parse_cronos_status_block()` function |
| `CLAUDE.md` | Updated `backend/app/trace_parser.py` description to mention structured `cronos_status` blocks (primary) and legacy `STATUS:` fields, plus `NO_CRONOS_STATUS` exit reason |
| `CLAUDE.md` | Updated `backend/app/agent.py` description to document `parse_status()` behavior (structured block first, fallback with warning) |
| `CLAUDE.md` | Updated `backend/app/harnesses/decision.py` description to clarify signal precedence includes cronos_status block |
| `docs/HARNESSES.md` | Expanded Decision node signal precedence section (lines 411–425) to detail 5-layer hierarchy: cronos_status block > legacy STATUS marker > exit_reason > regex > variable condition |
| `docs/HARNESSES.md` | Rewrote agent completion guidance (§7) to explain both structured and legacy channels and `NO_CRONOS_STATUS` exit reason |
| `docs/HARNESSES.md` | Updated quick-reference Decision condition grammar to mention cronos_status block and legacy STATUS marker |

## Coverage

### Updated sections

- **CLAUDE.md Key modules table**: Four module descriptions clarified to document
  the new structured completion channel and its interaction with downstream
  systems (decision routing, exit reason reporting, signal precedence).

- **docs/HARNESSES.md § 8 (Control-flow nodes)**:
  - Signal precedence expanded from 4 to 5 layers (cronos_status block inserted
    as highest priority).
  - Agent completion guidance added (new subsection "Agent completion sentinel")
    explaining block format, valid status values, channel preference, and the
    `NO_CRONOS_STATUS` exit reason for missing markers.
  - Example `cronos_status` block included inline.

- **docs/HARNESSES.md § 13 (Quick reference)**:
  - Decision condition grammar updated to include cronos_status block and legacy
    STATUS marker.

### Intentionally not updated

- `README.md`: High-level ops guide focuses on deployment, auth, and logs. The
  completion sentinel is an agent-internal contract; not relevant to operators.
- `TESTING.md`: Unit test authoring guide; the implementation's format changes
  are transparent to test writing.
- `.claude/agents/*`: Agent definitions (contract/model metadata) are not doc
  scope; they were updated during implementation.
- `.claude/skills/task-finalize/SKILL.md`: Already updated by the impl phase;
  doc-sync reads but does not edit skill source files.

## Assumptions

- Users authoring agents/harnesses will read CLAUDE.md for module overview and
  docs/HARNESSES.md for harness-specific semantics; both have been kept current.
- The implementation has already wired up the actual parsing and signal routing;
  documentation reflects that completed behavior.
- Signal precedence order (cronos_status > legacy STATUS > exit_reason > regex >
  variable) is the one enforced in decision.py and is the canonical precedence.

## Open questions

- None.

## Next consumer brief

G05 is complete. The structured completion sentinel is implemented, tested,
reviewed, and documented. Harness authors can now emit completion status via
the `cronos_status` fenced-JSON block (preferred) or the legacy `STATUS:`
marker (deprecated with warning). Decision nodes route on the status value
with a clear 5-layer signal precedence. Any run missing both markers reports
exit_reason = `NO_CRONOS_STATUS`, which can also be used as a decision
condition for error handling.

Documentation is sufficient for harness authoring and agent development. No
further doc work is required for this goal.
