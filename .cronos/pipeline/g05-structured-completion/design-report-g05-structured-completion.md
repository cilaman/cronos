---
cc_version: '1.0'
agent: pipeline-architect
slug: g05-structured-completion
phase: design
status: done
confidence: 0.88
inputs_used:
- memory:project-pipeline-architect-agent
- memory:project-memory-sentinel-completed
- memory:project-parse-status-fix
- memory:project-trace-structure
- .cronos/pipeline/g05-structured-completion/analysis-report-g05-structured-completion.md
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- backend/app/agent.py
- backend/app/memory_parser.py
- backend/app/worker.py
outputs_produced:
- .cronos/pipeline/g05-structured-completion/design-report-g05-structured-completion.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/agent.py
  - backend/app/memory_parser.py
  - backend/app/worker.py
  excluded:
  - frontend/: has_ui=false in upstream analysis
  - backend/app/harnesses/: harness completion uses its own wait/decision protocol
  - backend/app/trace_parser.py: exit_reason string is derived in worker.py, not trace_parser
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/memory_parser.py
  - backend/tests/test_cronos_status_parser.py
  validation_command: cd backend && pytest tests/test_cronos_status_parser.py::TestParseCronosStatusBlock
    -v
  max_diff_lines: 300
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/agent.py
  - backend/tests/test_cronos_status_parser.py
  validation_command: cd backend && pytest tests/test_cronos_status_parser.py -v
  max_diff_lines: 250
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - backend/app/worker.py
  - backend/tests/test_no_cronos_status_exit_reason.py
  validation_command: cd backend && pytest tests/test_no_cronos_status_exit_reason.py
    -v
  max_diff_lines: 200
  depends_on: []
- id: I4
  type: backend
  scope_files:
  - backend/app/agent.py
  validation_command: 'cd backend && python -c "from app.agent import STATUS_CONTRACT;
    assert ''cronos_status'' in STATUS_CONTRACT; assert ''DEPRECATED'' in STATUS_CONTRACT.upper()
    or ''deprecated'' in STATUS_CONTRACT; assert ''\"status\": \"DONE\"'' in STATUS_CONTRACT;
    print(''STATUS_CONTRACT updated'')"'
  max_diff_lines: 200
  depends_on:
  - I2
- id: I5
  type: infra
  scope_files:
  - .claude/skills/task-finalize/SKILL.md
  validation_command: 'grep -q ''cronos_status'' .claude/skills/task-finalize/SKILL.md
    && grep -q ''"status": "DONE"'' .claude/skills/task-finalize/SKILL.md && grep
    -q ''"status": "WAIT"'' .claude/skills/task-finalize/SKILL.md && grep -q ''"status":
    "BLOCKED"'' .claude/skills/task-finalize/SKILL.md && echo ''task-finalize updated'''
  max_diff_lines: 150
  depends_on:
  - I1
risks:
- description: Circular import risk if the implementor naively returns a Status enum
    from memory_parser.py — agent.py would then need to be imported by memory_parser.py,
    but worker.py already imports both modules and agent.py does NOT import memory_parser.py.
  severity: high
  mitigation: 'parse_cronos_status_block() in memory_parser.py MUST return (status_str:
    str | None, summary: str | None) — i.e. a raw string in {''DONE'',''WAIT'',''BLOCKED''}
    or None — never a Status enum. The Status(...) enum conversion happens inside
    parse_status() in agent.py after importing the new function. I1''s test imports
    BOTH backend.app.memory_parser AND backend.app.agent in the same module to catch
    any accidental circular import at collection time.'
- description: 'Line numbers for NO_STATUS sites have drifted from scout commit a724133;
    brief lists ~1107-1108 and ~1431-1432, but grep at current HEAD e6883dc shows
    three sites: lines 119 (in _WorkerProtocolAdapter), 1108, and 1432. Missing the
    line-119 site would leave a silent NO_STATUS path in the harness executor adapter.'
  severity: medium
  mitigation: I3 implementor MUST grep the literal string 'NO_STATUS' (not trust the
    brief's two-site count) and replace EVERY occurrence with 'NO_CRONOS_STATUS'.
    I3's regression test asserts `grep -c 'NO_STATUS\b' backend/app/worker.py == 0`
    and `grep -c 'NO_CRONOS_STATUS' backend/app/worker.py >= 3` to prove all sites
    were updated.
- description: 'The new cronos_status fence could be confused with the existing cronos_remember
    fence; copy-pasting parse_cronos_remember_blocks would carry YAML parsing forward,
    but the G05 brief specifies a JSON payload literal {"status": "DONE", "summary":
    "...", "artifacts": []}.'
  severity: medium
  mitigation: I1 uses distinct fence regex _CS_FENCE_OPEN matching '^```cronos_status\s*$'
    (case-insensitive) and parses the inner payload via json.loads, NOT yaml.safe_load.
    I1's tests include a fixture where both fences appear in the same agent output,
    and assert that the cronos_remember parser ignores cronos_status blocks and vice
    versa.
- description: R4 (STATUS_CONTRACT prompt) and R5 (task-finalize SKILL.md) have verifying_phase=review,
    so a typo or syntactically-invalid JSON example in either file would not be caught
    until review. The example block could silently fail parse_cronos_status_block()
    at runtime.
  severity: medium
  mitigation: I1's test_cronos_status_parser.py includes a test case that imports
    STATUS_CONTRACT from agent.py (after I4 ships) and a literal copy of the SKILL.md
    example block, and asserts parse_cronos_status_block() returns the expected (status,
    summary) for each. This converts the review-phase requirements into test-phase
    assertions transitively. I4 and I5 are ordered after I1 to ensure the parser exists
    when their examples are validated.
- description: Existing test files in backend/tests/ that mock parse_status() output
    (e.g. test_worker_finalize.py, test_agent.py) may break if the function signature
    or import location changes. The brief does not enumerate downstream test files.
  severity: low
  mitigation: 'I2 keeps parse_status()''s public signature unchanged: (text: str)
    -> tuple[Status | None, str | None]. The structured-block path is added BEFORE
    the existing _STATUS_LINE scan but returns the same tuple shape. I2''s validation
    command runs the full test_cronos_status_parser.py module; the implementor is
    expected to run `pytest backend/tests/ -k ''status or parse_status''` as a smoke
    check before claiming done, but this is not part of the formal validation_command.'
metrics:
  tool_calls: 8
  files_read: 5
  memory_hits: 4
  iterations_planned: 5
---

## Summary

G05 replaces the regex-on-prose `STATUS: DONE` transport with a fenced-JSON `cronos_status` block — the same pattern shape (but JSON-payload, not YAML) as the proven `cronos_remember` subsystem in `memory_parser.py`. The plan is 5 iterations across 3 DAG layers: layer 0 fans out to the parser (I1) and the worker exit-reason rename (I3) in parallel; layer 1 wires the parser into `parse_status()` (I2) and updates the `task-finalize` skill (I5); layer 2 updates the `STATUS_CONTRACT` prompt (I4). The load-bearing design decision encoded across all iterations is the import direction — `parse_cronos_status_block()` returns a raw status string, never the `Status` enum — so `memory_parser.py` never imports `agent.py` and the existing `worker.py → memory_parser.py + agent.py` graph stays acyclic.

## Components

### Data
- No persistent data model changes. The `cronos_status` block is parsed-once per agent run; the `summary` field flows through the existing `context` slot in `parse_status()`'s return tuple; the optional `artifacts` field is parsed-but-ignored in this goal (deferred per analyst scope).

### Backend
- `backend/app/memory_parser.py` — add `parse_cronos_status_block(text) -> tuple[str | None, str | None]` and a private `_CS_FENCE_OPEN` regex matching `^```cronos_status\s*$`. Mirror the silent-skip-on-malformed pattern of `parse_cronos_remember_blocks`. Parse the fence body via `json.loads` (NOT `yaml.safe_load`). Required field `status` ∈ {`DONE`, `WAIT`, `BLOCKED`}; optional `summary` (str), optional `artifacts` (list — validated but not returned).
- `backend/app/agent.py::parse_status()` — call `parse_cronos_status_block(text)` first; if it returns a non-None status string, convert via `Status(status_str)` and return `(enum, summary)`. Otherwise fall back to the existing `_STATUS_LINE` reverse scan. Public signature unchanged.
- `backend/app/agent.py::STATUS_CONTRACT` — replace the body with a primary section that shows the `cronos_status` fenced JSON block format for DONE/WAIT/BLOCKED, plus a clearly-labelled `[DEPRECATED fallback]` section retaining the bare `STATUS: X` instructions for backward compatibility.
- `backend/app/worker.py` — replace every occurrence of the literal string `"NO_STATUS"` with `"NO_CRONOS_STATUS"` (grep confirms 3 sites at current HEAD: lines 119, 1108, 1432; line numbers may drift further).

### Skill
- `.claude/skills/task-finalize/SKILL.md` — update Step 5 (DONE path) and Step 1 (WAIT/BLOCKED paths) to emit a `cronos_status` fenced JSON block as the primary completion signal. Retain a brief note that the bare `STATUS: X` last-line form is deprecated but still accepted during transition.

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                          | Validation                                                            |
|-----|----------|------------|-----------------------------------------------------------------|-----------------------------------------------------------------------|
| I1  | backend  | -          | memory_parser.py, tests/test_cronos_status_parser.py            | pytest tests/test_cronos_status_parser.py::TestParseCronosStatusBlock |
| I2  | backend  | I1         | agent.py, tests/test_cronos_status_parser.py                    | pytest tests/test_cronos_status_parser.py -v                          |
| I3  | backend  | -          | worker.py, tests/test_no_cronos_status_exit_reason.py           | pytest tests/test_no_cronos_status_exit_reason.py -v                  |
| I4  | backend  | I2         | agent.py (STATUS_CONTRACT)                                      | python -c "...STATUS_CONTRACT contains cronos_status..."              |
| I5  | infra    | I1         | .claude/skills/task-finalize/SKILL.md                           | grep -q for cronos_status + each status value in SKILL.md             |

Topological layers (parallelizable per layer):
- Layer 0: I1, I3  (parser foundation + worker string rename — independent)
- Layer 1: I2, I5  (wire parser into parse_status + update skill emission — both need I1)
- Layer 2: I4      (update STATUS_CONTRACT prompt — needs I2's wire-up to be coherent with the prompt instructions)

## Risks

| Risk                                                                                                  | Severity | Mitigation                                                                                                                                                                                                                                                                          |
|-------------------------------------------------------------------------------------------------------|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Circular import if parser returns Status enum                                                         | high     | parse_cronos_status_block() returns raw str; agent.py performs Status(...) conversion. I1 test imports both modules together to catch cycles at collection time.                                                                                                                     |
| NO_STATUS line numbers drifted; 3rd site (line 119) missed                                            | medium   | I3 implementor greps the literal "NO_STATUS"; regression test asserts grep count == 0 after change and >= 3 for "NO_CRONOS_STATUS".                                                                                                                                                  |
| cronos_status fence confused with cronos_remember (YAML vs JSON)                                      | medium   | Distinct fence regex `^```cronos_status\s*$`; payload parsed via json.loads (not yaml.safe_load). I1 test fixture includes both fences side-by-side and verifies cross-isolation.                                                                                                    |
| R4/R5 are review-phase only; malformed JSON examples in prompt/SKILL.md slip past tests               | medium   | I1's test file imports STATUS_CONTRACT (post-I4) and a literal copy of the SKILL.md example block, asserts parse_cronos_status_block() returns expected (status, summary) for each. Converts review-phase reqs into transitive test-phase assertions.                                |
| Downstream tests that mock parse_status() may break on signature change                               | low      | parse_status() public signature unchanged: (text: str) -> tuple[Status \| None, str \| None]. Structured-block path added before existing scan, returns same tuple shape.                                                                                                            |

## Assumptions

- The `Status` enum stays in `agent.py` (not moved to `memory_parser.py` or a new shared module). Moving it would touch every existing consumer of `Status` and is out of scope for this goal.
- JSON (not YAML) is the payload format, per the G05 brief literal `{"status": "DONE", "summary": "...", "artifacts": []}`. Mirroring cronos_remember's YAML choice was considered and rejected: JSON is unambiguous for a single-level dict, matches the brief verbatim, and avoids ambiguity with the indent-sensitive YAML grammar.
- The free-text `_STATUS_LINE` fallback path remains in place (per the analyst's deferred scope). I2 does NOT delete the regex; it only adds the structured-block precedence above it.
- I3 ships independently of I1/I2: changing `"NO_STATUS"` → `"NO_CRONOS_STATUS"` is a pure string-literal rename that does not depend on the new parser existing yet. (If structured parsing returns None and free-text returns None, the existing worker logic still derives the exit_reason from `result.status` being None — only the string constant changes.)
- I3's regression test asserts the worker behavior end-to-end via the existing `result.status is None` path; it does not require the new parser to be in place. This is what allows I3 to land in DAG layer 0 in parallel with I1.
- The optional `artifacts` field in the cronos_status block is parsed-and-validated-as-list but NOT returned from `parse_cronos_status_block()` (return shape stays a 2-tuple). The field is reserved for a future iteration that surfaces artifact lists to the trace UI.
- I5's grep-based validation_command is acceptable because R5 has verifying_phase=review; the grep merely confirms the expected literal substrings are present so the review phase has something concrete to read.

## Open questions

- None.

## Next consumer brief

Implementors should read `iterations[]`, `iterations[].scope_files`, `iterations[].validation_command`, and `risks[]` from the YAML header — those are the machine-readable source of truth. Three cross-iteration invariants that are NOT derivable from the per-iteration YAML and MUST be respected:

1. **Import direction (load-bearing):** `parse_cronos_status_block()` in `memory_parser.py` returns `tuple[str | None, str | None]` — a raw status STRING (`"DONE"`, `"WAIT"`, `"BLOCKED"`, or `None`), never a `Status` enum. `agent.py::parse_status()` performs the `Status(s)` enum conversion after importing the function. `memory_parser.py` MUST NOT import `agent.py`. This avoids a circular import (`worker.py` already imports both modules).

2. **Fence + payload format:** the fence regex is `^```cronos_status\s*$` (case-insensitive), distinct from `cronos_remember`. The payload is parsed via `json.loads`, NOT `yaml.safe_load`. Silent-skip on `json.JSONDecodeError`, missing `status` field, or `status` value not in `{"DONE", "WAIT", "BLOCKED"}` — mirroring `parse_cronos_remember_blocks`'s error-handling shape.

3. **NO_STATUS site count is THREE, not two:** the analysis brief listed lines ~1107–1108 and ~1431–1432, but `grep -n 'NO_STATUS' backend/app/worker.py` at HEAD `e6883dc` shows three sites: lines 119, 1108, 1432. I3 implementor MUST grep the literal string and replace ALL occurrences; the regression test asserts `grep -c '\bNO_STATUS\b' == 0` after the change.

I1's test file (`test_cronos_status_parser.py`) is shared with I2: I1 adds the parser unit tests; I2 appends `parse_status()` integration tests that exercise the structured-block + free-text fallback precedence. Both iterations may write to that file — order is enforced by the `depends_on` edge.

One unresolved open question for implementors to answer in their own reports: whether the `artifacts` field should be silently accepted as ANY type (lenient — match cronos_remember body/metadata handling) or strictly rejected when non-list (strict). The design recommends LENIENT (match cronos_remember's `if not isinstance(...): default` pattern) so a future implementor can add the strict check without breaking existing emissions.
