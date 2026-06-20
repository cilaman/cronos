---
cc_version: '1.0'
agent: pipeline-analyst
slug: g05-structured-completion
phase: analysis
status: done
confidence: 0.92
inputs_used:
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- .claude/agents/pipeline-analyst.md
- backend/app/agent.py
- backend/app/memory_parser.py
- .claude/skills/task-finalize/SKILL.md
- backend/app/trace_parser.py
- backend/app/worker.py
outputs_produced:
- .cronos/pipeline/g05-structured-completion/analysis-report-g05-structured-completion.md
blockers: []
next_consumer: design
request: 'G05: Structured completion sentinel (retire free-text STATUS). Replace the
  regex-parsed free-text STATUS: DONE transport with a fenced-JSON block mirroring
  the cronos_remember pattern already in the codebase. After: completion no longer
  depends on prose formatting (markdown/casing/last-line position); a run that omits
  the block is a detected, reported condition — not a silent WAIT misfile; tests cover
  DONE/WAIT/BLOCKED/missing via the structured channel; free-text fallback is removed
  or flag-gated with a deprecation note.'
has_ui: false
coverage_summary:
  searched:
  - backend/app/agent.py (parse_status, _STATUS_LINE, STATUS_CONTRACT)
  - backend/app/memory_parser.py (parse_cronos_remember_blocks — the pattern to replicate)
  - backend/app/worker.py (exit_reason derivation, status None handling)
  - backend/app/trace_parser.py (exit_reason field usage)
  - .claude/skills/task-finalize/SKILL.md (Step 5 emission contract)
  - .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
  - .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
  excluded:
  - frontend/ — no UI surface for this change
  - backend/app/harnesses/ — harness executor handles its own wait logic, not completion
    sentinel
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: A new parse_cronos_status_block(text) function is added to backend/app/memory_parser.py
    alongside parse_cronos_remember_blocks, parsing the first cronos_status fenced
    JSON block with required field "status" in {DONE, WAIT, BLOCKED} and optional
    fields "summary" (str) and "artifacts" (list); returns (Status.X, summary) on
    success, (None, None) on missing or malformed block.
  acceptance_criteria:
  - 'Given agent output containing a cronos_status fenced block with {"status": "DONE",
    "summary": "ok"}, parse_cronos_status_block() returns (Status.DONE, "ok").'
  - Given a cronos_status block with status WAIT and a summary string, returns (Status.WAIT,
    <summary>).
  - Given a cronos_status block with status BLOCKED and a summary string, returns
    (Status.BLOCKED, <summary>).
  - Given output with no cronos_status fenced block, returns (None, None).
  - Given a cronos_status block with invalid JSON or missing status field, returns
    (None, None) — silently skipped, mirroring parse_cronos_remember_blocks error
    handling.
  - Given a cronos_status block with a status value not in {DONE, WAIT, BLOCKED},
    returns (None, None).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: parse_status() in backend/app/agent.py calls parse_cronos_status_block()
    before the free-text _STATUS_LINE regex scan; if the structured block yields a
    non-None status, that result is returned immediately (structured takes precedence
    over free-text).
  acceptance_criteria:
  - 'Given output containing both a cronos_status block with status=DONE and a free-text
    STATUS: WAIT line, parse_status() returns (Status.DONE, <summary>).'
  - 'Given output with only a free-text STATUS: DONE marker (no structured block),
    parse_status() still returns (Status.DONE, <context>) — backward-compatible transition
    fallback.'
  - The context value returned for a structured block is the "summary" field from
    the JSON, not a heuristically extracted preceding line.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R3
  statement: When neither a cronos_status block nor a free-text STATUS marker is found
    in the agent output, the resulting trace records exit_reason="NO_CRONOS_STATUS"
    (replacing the current "NO_STATUS") so the missing sentinel is a visible, distinct
    condition in task traces and logs — not a silent auto-WAIT misfile.
  acceptance_criteria:
  - 'Given a run with no status marker and exit_code=0, the trace stored to disk contains
    exit_reason: NO_CRONOS_STATUS (not NO_STATUS).'
  - The worker.py log call when result.status is None includes the string NO_CRONOS_STATUS
    so it is grep-findable in container logs.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R4
  statement: 'The STATUS_CONTRACT prompt string in backend/app/agent.py is updated
    to describe the cronos_status fenced-JSON block as the primary completion signal
    for DONE, WAIT, and BLOCKED states; the existing bare STATUS: X last-line instructions
    are retained only in a clearly marked deprecated fallback section.'
  acceptance_criteria:
  - The STATUS_CONTRACT string in agent.py contains the literal text "cronos_status"
    and a JSON example with status, summary, and artifacts fields.
  - WAIT and BLOCKED paths in STATUS_CONTRACT also show the structured block format.
  - The existing fallback section is preserved but labelled as deprecated (e.g. "[DEPRECATED
    fallback — use cronos_status block instead]").
  verifying_phase: review
  confidence: 0.9
- requirement_id: R5
  statement: '.claude/skills/task-finalize/SKILL.md Step 5 is updated to emit a cronos_status
    fenced JSON block {"status": "DONE", "summary": "...", "artifacts": [...]} as
    the completion signal; Step 1 WAIT and BLOCKED paths are also updated to emit
    corresponding structured blocks.'
  acceptance_criteria:
  - 'Step 5 in SKILL.md shows a cronos_status fenced block with status=DONE as the
    primary emission, not a bare STATUS: DONE line.'
  - 'Step 1 WAIT path shows {"status": "WAIT", "summary": "<question here>"} in a
    cronos_status block.'
  - 'Step 1 BLOCKED path shows {"status": "BLOCKED", "summary": "<blocker here>"}
    in a cronos_status block.'
  verifying_phase: review
  confidence: 0.9
- requirement_id: R6
  statement: 'A new test file backend/tests/test_cronos_status_parser.py provides
    unit tests for parse_cronos_status_block() and the updated parse_status() covering
    all four AC-required cases: DONE/WAIT/BLOCKED via structured block; missing block
    returns (None, None); malformed JSON silently skipped; structured block takes
    precedence over co-present free-text marker.'
  acceptance_criteria:
  - pytest backend/tests/test_cronos_status_parser.py passes with no failures.
  - At least one test case per status value (DONE, WAIT, BLOCKED) via cronos_status
    fenced block.
  - At least one test for missing block — parse_cronos_status_block() returns (None,
    None).
  - At least one test for malformed or invalid JSON in the block — silently returns
    (None, None).
  - At least one test for structured block taking precedence when free-text STATUS
    marker also appears in the same text.
  verifying_phase: test
  confidence: 0.95
metrics:
  tool_calls: 12
  files_read: 8
  memory_hits: 0
---

## Summary

G05 replaces the fragile regex-on-prose `STATUS: DONE` completion transport with a
fenced-JSON `cronos_status` block — the same pattern already proven by the
`cronos_remember` memory subsystem in `backend/app/memory_parser.py`. The new
parser (`parse_cronos_status_block`) is added alongside `parse_cronos_remember_blocks`;
`parse_status()` in `agent.py` tries the structured block first; the `task-finalize`
skill and `STATUS_CONTRACT` prompt are updated to emit the new format; and absence of
any marker becomes the distinct `"NO_CRONOS_STATUS"` trace field rather than a silent
auto-WAIT misfile. Free-text parsing is preserved as a deprecated transition fallback
and remains in place until a follow-on cleanup removes it.

## Scope

### In scope
- New `parse_cronos_status_block()` function in `backend/app/memory_parser.py`
- Updated `parse_status()` in `backend/app/agent.py` (structured-first precedence)
- Updated `STATUS_CONTRACT` prompt in `backend/app/agent.py` (block format description)
- Updated exit_reason string in `backend/app/worker.py` (NO_STATUS → NO_CRONOS_STATUS)
- Updated `.claude/skills/task-finalize/SKILL.md` Step 1 and Step 5 emission instructions
- New `backend/tests/test_cronos_status_parser.py` unit test file

### Out of scope
- Removal of the free-text `_STATUS_LINE` regex path (deferred; transition period)
- Changes to `frontend/` (no UI surface for this feature)
- Changes to `backend/app/harnesses/` (harness completion uses a separate wait/decision protocol)
- Changes to `backend/app/trace_parser.py` (the exit_reason string update in worker.py is sufficient)
- Any changes to `AgentResult` dataclass fields (not required; worker.py derives exit_reason inline)

### Deferred
- Full removal of the free-text `_STATUS_LINE` fallback path (follow-on after all agents
  have migrated to emitting `cronos_status` blocks)
- Persisting `artifacts[]` from the structured block to the task trace / UI (the field is
  parsed and available but not surfaced beyond the context string in this goal)
- Updating harness agents to use the structured format (out of harness scope)

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Add `parse_cronos_status_block()` to `memory_parser.py` mirroring `parse_cronos_remember_blocks` |
| R2 | Update `parse_status()` in `agent.py` to try structured block first (structured > free-text) |
| R3 | Absent sentinel → `exit_reason = "NO_CRONOS_STATUS"` (not silent "NO_STATUS" auto-WAIT) |
| R4 | Update `STATUS_CONTRACT` prompt in `agent.py` to describe `cronos_status` block as primary |
| R5 | Update `task-finalize/SKILL.md` Steps 1 and 5 to emit structured `cronos_status` blocks |
| R6 | Add `test_cronos_status_parser.py` covering DONE/WAIT/BLOCKED/missing/malformed/precedence |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]`
array (the machine-readable source of truth). Compact summary:

- R1 — `parse_cronos_status_block()` returns correct Status enum for DONE/WAIT/BLOCKED;
  returns `(None, None)` for missing block, malformed JSON, or invalid status value
- R2 — structured block takes precedence over free-text in `parse_status()`; free-text
  fallback still works when no block is present
- R3 — zero-status + exit_code=0 run records `exit_reason: NO_CRONOS_STATUS` in trace
  and worker log
- R4 — `STATUS_CONTRACT` contains `cronos_status` block example for DONE/WAIT/BLOCKED;
  old format retained in deprecated fallback section only
- R5 — `task-finalize/SKILL.md` Step 5 shows structured DONE block; Step 1 shows
  structured WAIT/BLOCKED blocks
- R6 — new test file passes with ≥6 test cases covering all AC items

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML
`traceability[]` array. Downstream agents read the YAML directly; this section
exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | `parse_cronos_status_block()` parses `cronos_status` fenced JSON with required `status` field |
| R2 | test | `parse_status()` in `agent.py` uses structured block first, free-text as fallback |
| R3 | test | Missing marker yields `exit_reason = "NO_CRONOS_STATUS"` in trace, not silent WAIT misfile |
| R4 | review | `STATUS_CONTRACT` prompt describes `cronos_status` block as primary signal |
| R5 | review | `task-finalize/SKILL.md` Steps 1 and 5 emit `cronos_status` structured blocks |
| R6 | test | New test file covers all four AC-required cases (DONE/WAIT/BLOCKED/missing) and more |

## Assumptions

- `parse_cronos_status_block()` uses JSON (not YAML) for the block payload, because the
  G05 brief explicitly specifies `{ "status": "DONE", "summary": "…", "artifacts": [] }`
  — a JSON literal. YAML is used by `parse_cronos_remember_blocks` but JSON is simpler
  for the single-level structure of a status block.
- The `artifacts` field is parsed and validated as a list but not surfaced beyond the
  (Status, summary) return tuple in this phase; it is stored as a future-use field.
- `exit_reason = "NO_CRONOS_STATUS"` is set in `worker.py` (not in `agent.py` or
  `trace_parser.py`) because that is where the existing `"NO_STATUS"` string is derived
  (lines 1107–1108 and 1431–1432 of `worker.py`). Only the string constant changes;
  no structural change to worker logic is needed.
- The transition-period free-text fallback remains active in the first iteration of G05
  so existing agents that emit bare `STATUS: DONE` still work. A cleanup task can gate
  or remove it afterward.
- `has_ui = false`: G05 makes no UI changes. The `exit_reason` string change is reflected
  in the existing trace detail panel in the frontend, but no frontend source files are
  modified.
- The scout report was authored at commit `a724133`; the current HEAD is `e6883dc`. The
  scout confirmed G05 symbols exist at those paths; line numbers may have drifted —
  the implementor must re-verify before editing.

## Open questions

None.

## Next consumer brief

**Design agent should:**

1. Read `traceability[]` first — 6 requirements, all backend + skill, no UI.
2. `has_ui = false` — no frontend sub-track needed.
3. The critical design decision is the exact import direction for `parse_cronos_status_block()`:
   the function needs `Status` from `backend/app/agent.py`, but it lives in
   `backend/app/memory_parser.py`. Confirm this does not introduce a circular import
   (check the actual import chain: `agent.py` does not import `memory_parser.py` directly;
   `worker.py` imports both; so moving Status import into `memory_parser.py` or passing
   the status string as a raw str and letting parse_status() do the enum conversion are
   both valid design options).
4. R3 requires a 2-site string-constant change in `worker.py` (lines ~1107–1108 and
   ~1431–1432) — these are string literals, not logic changes, so the scope is minimal.
5. R4 and R5 are textual (prompt and SKILL.md); the design can emit these as a single
   iteration or bundle them with R1/R2.
6. Suggested iteration ordering: [R1 parser + R6 tests] → [R2 parse_status update] →
   [R3 worker exit_reason] → [R4 STATUS_CONTRACT + R5 SKILL.md]. Tests should gate each
   backend change.
7. Watch out: `parse_status()` has three fallback call sites in `agent.py` (lines 553,
   556–557, 560–563) — the structured block parse should run once on `final_text` before
   the multi-turn scan loop, not inside the loop, to avoid redundant parsing.
