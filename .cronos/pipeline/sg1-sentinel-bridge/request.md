Spec 1 — `node_status`/`delivery_status` → `cronos_status` bridge

Fixes #2: delivery tasks finish with `delivery_status: done` or `node_status: done` but the worker sees WAITING.

### Root cause
`agent.py::parse_status` only checks for `cronos_status` and bare `STATUS:` lines. The delivery pipeline emits `delivery_status: done` fenced blocks, which aren't handled. All unrecognized output → task stays WAITING forever.

### Required change
In `backend/app/agent.py::parse_status`, add 4-tier resolution (additive):
1. `node_status` (new; highest priority; Spec 2 adds the parser)
2. `cronos_status` (existing legacy board signal)  
3. `delivery_status` (existing legacy delivery signal — already has a parser in memory_parser.py)
4. `STATUS:` (existing deprecated free-text last line)

Status vocab (case-insensitive): {done, wait, blocked, needs_fix, failed}
- done → DONE
- wait → WAIT (with waiting_question from summary or open_questions[0])
- blocked → BLOCKED (waiting_question from summary/open_questions[0])
- failed → BLOCKED
- needs_fix → DONE for runner-tagged tasks; BLOCKED for all others

The runner tags child tasks it dispatches so the bridge knows to apply needs_fix→DONE only for routed tasks.

### Tests
Unit: test_parse_status_bridge.py — each vocab value → expected Status; multi-fence precedence; malformed JSON → (None, None); absent → falls through. Integration: finalize a task whose text contains node_status:done or delivery_status:done → DONE not WAITING. Regression: existing cronos_status and STATUS: tests stay green.

References: spec §1.1–§1.6; `backend/app/agent.py` lines 84+ (Status enum), parse_status function; `backend/app/memory_parser.py` (existing parsers).

