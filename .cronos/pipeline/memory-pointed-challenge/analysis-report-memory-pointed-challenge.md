---
cc_version: '1.0'
agent: pipeline-analyst
slug: memory-pointed-challenge
phase: analysis
status: done
confidence: 0.9
inputs_used:
- memory:project_memory_system
- memory:project_parse_status_fix
- memory:project_trace_structure
- .cronos/pipeline/memory-pointed-challenge/scout-report-memory-pointed-challenge.md
- backend/app/memory_parser.py
- backend/app/trace_parser.py
- backend/app/worker.py
- backend/app/models.py
outputs_produced:
- .cronos/pipeline/memory-pointed-challenge/analysis-report-memory-pointed-challenge.md
blockers: []
next_consumer: design
request: 'Memory structured sentinel. Decompose the memory ingestion replacement into
  testable requirements: 1. What structured fields must a CRONOS_REMEMBER sentinel
  carry? (type, body, description, name, metadata) 2. How does the agent invoke it
  — inline sentinel vs post-task extraction step? 3. Backward compatibility: what
  happens to existing MEMORY: patterns in agent prompts and tests? 4. Which files
  change (trace_parser.py, memory_store.py, agent.py, worker.py)? 5. What does a skill
  or tool wrapper look like vs a bare sentinel?'
has_ui: false
coverage_summary:
  searched:
  - backend/app/memory_parser.py (regex patterns, parse_memory_blocks, MemoryBlock
    dataclass)
  - backend/app/trace_parser.py (memory_written tracking, _memory_slug, RunTrace fields)
  - backend/app/worker.py (lines 1195-1213 _finalize_task, lines 1337-1354 _finalize_child)
  - backend/app/models.py (MemoryItem schema lines 364-378, MemoryKind enum)
  excluded:
  - frontend/: no UI involvement in this feature
  - backend/app/memory_retrieval.py: scoring/ranking unchanged in scope
  - backend/tests/: test phase will validate; no re-read needed for requirements
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: 'The CRONOS_REMEMBER sentinel carries five named fields: name (required
    string ≤120 chars), type (required enum: fact|procedure|observation|reference),
    description (required one-line string), body (optional multi-line string), and
    metadata (optional YAML key-value mapping).'
  acceptance_criteria:
  - Given a fenced CRONOS_REMEMBER block with all five fields, the parser extracts
    name, type, description, body, and metadata with correct Python types.
  - Given a block missing any of name, type, or description, the block is silently
    skipped and no exception is raised.
  - Given an unknown type value (e.g. 'note'), the block is skipped (consistent with
    _normalize_kind behavior in parse_memory_blocks).
  - Given metadata as a YAML mapping, the parsed result is a Python dict preserving
    all keys and values.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R2
  statement: 'The CRONOS_REMEMBER sentinel uses a fenced block format: an opening
    line matching ```cronos_remember (case-insensitive) and a closing line matching
    ``` alone, with YAML-structured field content between them.'
  acceptance_criteria:
  - Given agent output containing ```cronos_remember...```, parse_cronos_remember_blocks()
    returns one CronosRememberBlock.
  - Given ```CRONOS_REMEMBER (uppercase fence), the block is recognized (case-insensitive
    match).
  - 'Given agent output containing both a MEMORY: line and a CRONOS_REMEMBER block,
    parse_memory_blocks() and parse_cronos_remember_blocks() each return their own
    result independently.'
  - Given an unclosed cronos_remember fence (no closing ```), the block is silently
    discarded.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R3
  statement: 'Parsed CRONOS_REMEMBER fields map to MemoryItem fields: name→title;
    type→kind (MemoryKind enum); description and body→MemoryItem.body (description
    on first line, blank line separator, then body content); metadata key-value pairs
    are JSON-serialized and appended as a single string to MemoryItem.links[].'
  acceptance_criteria:
  - Given name='key insight about X', MemoryItem.title is 'key insight about X' (verbatim,
    not truncated first-line of body).
  - Given type='fact', MemoryItem.kind is MemoryKind.FACT.
  - 'Given description=''Short summary'' and body=''Full detail

    more lines'', MemoryItem.body is ''Short summary


    Full detail

    more lines''.'
  - Given description='Short summary' and no body field, MemoryItem.body is 'Short
    summary'.
  - 'Given metadata={''confidence'': ''high'', ''source'': ''observation''}, MemoryItem.links
    contains exactly one entry: the JSON serialization of that dict.'
  - Given no metadata field, MemoryItem.links is empty (not None).
  verifying_phase: test
  confidence: 0.85
- requirement_id: R4
  statement: 'Existing MEMORY: inline markers and ```memory fenced blocks remain parseable
    with no behavioral change; parse_memory_blocks() is not modified.'
  acceptance_criteria:
  - All 26 existing test cases in backend/tests/test_memory_parser.py pass without
    modification.
  - parse_memory_blocks() signature, return type (list[MemoryBlock]), and MemoryBlock
    dataclass are unchanged.
  - 'Agent output containing both MEMORY: markers and CRONOS_REMEMBER blocks is processed
    by each parser independently, producing results from both.'
  verifying_phase: test
  confidence: 0.98
- requirement_id: R5
  statement: 'A new parse_cronos_remember_blocks(text: str) -> list[CronosRememberBlock]
    function and CronosRememberBlock dataclass are added to backend/app/memory_parser.py
    alongside the existing parse_memory_blocks() function.'
  acceptance_criteria:
  - parse_cronos_remember_blocks is importable from app.memory_parser.
  - 'CronosRememberBlock dataclass has attributes: name (str), type (str), description
    (str), body (str, default ''''), metadata (dict, default {}).'
  - parse_cronos_remember_blocks('') returns an empty list.
  - parse_cronos_remember_blocks(text_with_no_cronos_blocks) returns an empty list.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R6
  statement: worker.py calls parse_cronos_remember_blocks() in both _finalize_task()
    and _finalize_child() immediately after the existing parse_memory_blocks() call,
    persisting each valid block to memory_store.create() with confirmed=False and
    sources=[task:<id>, run:<index>].
  acceptance_criteria:
  - Given agent final_text containing a valid CRONOS_REMEMBER block, memory_store.create()
    is called once for that block using the R3 field mapping.
  - If parse_cronos_remember_blocks() raises an exception, it is caught, logged (log.exception),
    and the task continues normally without re-raising.
  - 'If memory_store is None, CRONOS_REMEMBER block parsing is skipped entirely (no-op,
    consistent with existing MEMORY: guard at worker.py:1196).'
  - 'In _finalize_child(), sources=[f''task:{child_id}''] (no run_index) — consistent
    with existing MEMORY: handling for child tasks.'
  verifying_phase: test
  confidence: 0.9
- requirement_id: R7
  statement: 'trace_parser.py requires no changes for CRONOS_REMEMBER MVP: memory_written[]
    tracks only explicit Write-tool file paths and is unchanged; the gap between sentinel-sourced
    items (not in memory_written) is documented via a comment in worker.py.'
  acceptance_criteria:
  - trace_parser.py is not modified.
  - RunTrace.memory_written remains limited to items written via the Write tool to
    a memory/ directory path.
  - A comment in worker.py at the CRONOS_REMEMBER extraction site notes that sentinel-persisted
    items are not reflected in RunTrace.memory_written.
  verifying_phase: review
  confidence: 0.88
- requirement_id: R8
  statement: 'Invocation model: agents embed CRONOS_REMEMBER fenced blocks in their
    final text output (bare inline sentinel); no tool call, subprocess, or dedicated
    post-task extraction turn is introduced; the write-memory skill (file-based) remains
    a separate path that is not affected.'
  acceptance_criteria:
  - Given agent output containing a CRONOS_REMEMBER block in final_text, worker.py
    extracts it without issuing any tool call or spawning any subprocess.
  - The write-memory skill continues to write .md files to the memory/ directory;
    these files appear in RunTrace.memory_written via the existing Write-tool tracking.
  - No agent prompt template is modified by this feature (agent.py build_prompt()
    is unchanged).
  - memory_store.py create() signature is unchanged or only addends links parameter;
    no schema migration is required.
  verifying_phase: review
  confidence: 0.88
metrics:
  tool_calls: 8
  files_read: 5
  memory_hits: 3
---

## Summary

The CRONOS_REMEMBER structured sentinel replaces the free-form `MEMORY:` ingestion pattern with a named-field fenced block that maps cleanly onto the `MemoryItem` schema. The sentinel is embedded in the agent's final text output (no tool call required) and extracted post-run by `worker.py`. The `MEMORY:` pattern is preserved unchanged for backward compatibility — all 26 existing parser tests must pass unmodified. The change set is deliberately narrow: `memory_parser.py` gains a new function and dataclass; `worker.py` adds two call sites (one per finalize hook); `trace_parser.py`, `agent.py`, and `memory_store.py` are untouched for MVP.

## Scope

### In scope
- CRONOS_REMEMBER fenced block format definition (fields: name, type, description, body, metadata)
- New `parse_cronos_remember_blocks()` function and `CronosRememberBlock` dataclass in `memory_parser.py`
- `worker.py` integration in `_finalize_task()` and `_finalize_child()`
- Field mapping from sentinel to MemoryItem (name→title, type→kind, description+body→body, metadata→links[])
- Backward compatibility: `MEMORY:` patterns and all 26 existing parser tests unchanged

### Out of scope
- Frontend UI for reviewing CRONOS_REMEMBER-sourced memory items
- Inline shorthand format (e.g., `CRONOS_REMEMBER[fact](name=slug): text`) — deferred
- Changes to memory retrieval scoring, confidence lifecycle, or TTL
- `memory_store.py` schema changes — existing MemoryItem fields accommodate all sentinel fields
- Name-based deduplication (find-or-update by name) — deferred

### Deferred
- Inline shorthand syntax (single-line CRONOS_REMEMBER without YAML body)
- Name-based deduplication: upsert an existing MemoryItem when the same `name` is re-emitted
- Metadata-driven confidence or TTL overrides at parse time
- `RunTrace.memory_sentinel_count` field in trace_parser.py to count sentinel-sourced items

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Sentinel carries five named fields: name (req), type (req), description (req), body (opt), metadata (opt) |
| R2 | Fenced block syntax: ` ```cronos_remember ... ``` ` (case-insensitive; unclosed fences discarded) |
| R3 | Field mapping: name→title, type→kind enum, description+body→body, metadata→JSON in links[] |
| R4 | Backward compat: parse_memory_blocks() unchanged; all 26 existing parser tests pass |
| R5 | New parse_cronos_remember_blocks() and CronosRememberBlock dataclass added to memory_parser.py |
| R6 | worker.py calls new parser in _finalize_task() and _finalize_child(); exceptions caught; None-store skipped |
| R7 | trace_parser.py unchanged; sentinel-sourced items not in memory_written[] (gap documented in comment) |
| R8 | Bare sentinel in final_text (no tool call); write-memory skill path unaffected; agent.py unchanged |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — All five fields parsed; blocks missing required fields silently skipped; unknown type values skipped
- R2 — Case-insensitive fence matched; MEMORY: and CRONOS_REMEMBER coexist in same text; unclosed fence discarded
- R3 — name→title verbatim; type→MemoryKind enum; description+body concatenated with blank separator; metadata JSON in links[]
- R4 — 26 existing tests pass unmodified; parse_memory_blocks() signature and MemoryBlock unchanged
- R5 — parse_cronos_remember_blocks() importable; CronosRememberBlock has name/type/description/body/metadata attributes
- R6 — memory_store.create() called per valid block with R3 mapping; exceptions caught; None-store → no-op
- R7 — trace_parser.py not modified; gap between sentinel items and memory_written[] documented via comment
- R8 — Extraction is post-run without tool call; write-memory skill unaffected; build_prompt() unchanged

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Sentinel carries five named fields: name, type, description, body, metadata |
| R2 | test | Fenced block syntax: ```cronos_remember ``` (case-insensitive; unclosed discarded) |
| R3 | test | Field mapping: name→title, type→kind enum, description+body→body, metadata→links[] JSON |
| R4 | test | Backward compat: parse_memory_blocks() unchanged, 26 existing tests pass |
| R5 | test | New parse_cronos_remember_blocks() and CronosRememberBlock in memory_parser.py |
| R6 | test | worker.py calls new parser in both finalize hooks; exceptions caught; None-store skipped |
| R7 | review | trace_parser.py unchanged; sentinel gap documented in worker.py comment |
| R8 | review | Bare sentinel in final_text; write-memory skill unaffected; agent.py unchanged |

## Assumptions

- **has_ui=false rationale**: The sentinel is parsed from agent text output (a backend-only post-run extraction step). No user interaction or screen rendering is involved.
- **YAML format for fenced block body**: CRONOS_REMEMBER block interior is YAML. PyYAML (`yaml.safe_load`) is available in the FastAPI backend. The parser must handle YAML parse errors gracefully — malformed blocks are silently skipped with a log warning.
- **metadata maps to links[]**: `MemoryItem.links[]` is a list of strings with no existing production usage detected. Storing metadata as a single JSON-serialized string is a pragmatic fit. If links semantics conflict with future usage, the design phase should propose an alternative field.
- **memory_store.create() can accept links parameter**: The current create() signature (scope, kind, title, body, confirmed, sources) does not include `links`. Adding `links: list[str] = []` as an optional keyword argument is a non-breaking change the implementor must verify.
- **Exception swallowing is correct**: Consistent with existing MEMORY: handling (worker.py:1212), a malformed CRONOS_REMEMBER block must never fail the task. Silent drop with `log.exception` is the correct behavior.
- **Scope limited to two files**: Scout findings confirm the full ingestion pipeline is self-contained in memory_parser.py (parsing) and worker.py (integration). No other files in the ingestion path need changes.

## Open questions

- **OQ1**: Should `name` enable deduplication (find-or-update semantics) or is it purely an advisory title? If deduplication is required, memory_store needs a `find_by_name()` or `upsert_by_name()` API and worker.py needs upsert logic — approximately 2 additional requirements. Recommendation: defer to follow-on; treat `name` as advisory title for this iteration.
- **OQ2**: Should `metadata` support a top-level `confidence` key that overrides MemoryItem.confidence at creation (default 1.0)? If yes, the design agent should define a dedicated `confidence` field at the sentinel top level rather than burying it in metadata — cleaner schema, avoids ambiguous metadata parsing.
- **OQ3**: Is `memory_store.create()` signature change backward-safe? The implementor must read memory_store.create() before coding R6. If the function has call sites that would need updating, flag before implementing.

## Next consumer brief

**For the design agent:**

1. **Read first**: `traceability[]` (requirements + acceptance criteria) and `## Scope` for explicit exclusions. R1–R5 are implementor input; R7–R8 are reviewer gates.
2. **Narrowest viable design**: Changes are bounded to `memory_parser.py` (new function + dataclass, ~50 LOC) and `worker.py` (two call sites, ~15 LOC). `trace_parser.py`, `agent.py`, and `memory_store.py` are out of scope unless OQ3 forces a `links` parameter addition.
3. **YAML parse error is the primary risk**: yaml.safe_load() raises on malformed YAML inside a cronos_remember fence. The design must specify exactly how this error is caught and at what level (inside the parser function vs. inside the worker for-loop).
4. **OQ3 is load-bearing for R3**: If memory_store.create() does not accept `links`, the metadata→links[] mapping in R3 is blocked. The design phase must resolve this before the implementation iteration that covers R3.
5. **R4 is a hard gate**: The 26 existing tests must pass with no modification. The design must not propose any change to parse_memory_blocks(), MemoryBlock, _MEMORY_LINE, _FENCE_OPEN, or _FENCE_CLOSE.
