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
  - path: README.md
    reason: High-level ops docs; no explicit mention of STATUS format needed at that scope
  - path: TESTING.md
    reason: Unit test guide; internal format changes are transparent to test-authoring
  - path: .claude/agents/
    reason: Agent contract definitions are updated by impl phase, not doc-sync scope
  - path: .claude/skills/task-finalize/SKILL.md
    reason: Already updated by impl phase with new block format; doc-sync does not edit skill source
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

## Updated docs

| File | Section(s) |
|------|-----------|
| `CLAUDE.md` | Key modules table: updated descriptions for `backend/app/agent.py`, `backend/app/trace_parser.py`, `backend/app/memory_parser.py`, `backend/app/harnesses/decision.py` |
| `docs/HARNESSES.md` | §7 Connecting nodes: added "Agent completion sentinel" subsection |
| `docs/HARNESSES.md` | §8 Control-flow nodes: expanded Decision node signal precedence from 4 to 5 layers |
| `docs/HARNESSES.md` | §8 Control-flow nodes: updated agent completion guidance and decision examples |
| `docs/HARNESSES.md` | §13 Quick reference: updated Decision condition grammar to include cronos_status block |

## Intentionally not updated

- path: README.md
  reason: High-level ops guide focuses on deployment/auth/logs; completion sentinel is agent-internal
- path: TESTING.md
  reason: Unit test guide; implementation format changes are transparent to test-authoring
- path: .claude/agents/
  reason: Agent definitions are updated by impl phase, not doc-sync scope
- path: .claude/skills/task-finalize/SKILL.md
  reason: Skill source already updated by impl phase; doc-sync does not edit source files

## Coverage

### Key documentation updates

**CLAUDE.md Key modules table** (4 entries updated):
- `backend/app/agent.py`: Now documents `parse_status()` checks structured
  `cronos_status` block first, falls back to deprecated `STATUS:` line with warning.
- `backend/app/trace_parser.py`: Now states it parses structured blocks (primary)
  and legacy fields, plus `NO_CRONOS_STATUS` exit reason.
- `backend/app/memory_parser.py`: Now includes `parse_cronos_status_block()`
  alongside the other parsing functions.
- `backend/app/harnesses/decision.py`: Signal precedence now includes cronos_status
  block as top priority.

**docs/HARNESSES.md updates**:
- §7 (Connecting nodes): Added "Agent completion sentinel" subsection detailing
  both channels (structured preferred, legacy deprecated), valid status values,
  and the `NO_CRONOS_STATUS` exit reason.
- §8 (Decision node): Expanded signal precedence from 4 to 5 layers; cronos_status
  block inserted as layer 1; legacy STATUS marker moved to layer 2; added example
  JSON block and guidance on handling missing markers via exit_reason.
- §13 (Quick reference): Decision condition grammar now mentions cronos_status
  blocks and legacy STATUS markers.

## Assumptions

- Users authoring agents/harnesses will read CLAUDE.md for module overview and
  docs/HARNESSES.md for harness-specific semantics; both are kept current.
- Implementation has wired up parsing and routing; documentation reflects that.
- Signal precedence (cronos_status > legacy STATUS > exit_reason > regex >
  variable) is enforced in decision.py and documented here.

## Open questions

- None.

## Next consumer brief

G05 is complete. The structured completion sentinel is implemented, tested,
reviewed, and documented. Harness authors can emit completion status via
the `cronos_status` fenced-JSON block (preferred) or legacy `STATUS:` marker
(deprecated with warning). Decision nodes route on status value with 5-layer
signal precedence. Runs missing both markers report `exit_reason=NO_CRONOS_STATUS`,
usable as a decision condition for error handling.

Documentation is sufficient for harness authoring and agent development.
