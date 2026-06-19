---
cc_version: '1.0'
agent: pipeline-architect
slug: memory-pointed-challenge
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:project_memory_system
- memory:feedback_pipeline_narrow_k_coverage
- .cronos/pipeline/memory-pointed-challenge/analysis-report-memory-pointed-challenge.md
- .cronos/pipeline/memory-pointed-challenge/scout-report-memory-pointed-challenge.md
- backend/app/memory_parser.py
- backend/app/memory_store.py
- backend/app/worker.py
outputs_produced:
- .cronos/pipeline/memory-pointed-challenge/design-report-memory-pointed-challenge.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/memory_parser.py
  - backend/app/memory_store.py
  - backend/app/worker.py
  excluded:
  - 'frontend/: has_ui=false, no UI in this feature'
  - 'backend/app/trace_parser.py: R7 mandates no change'
  - 'backend/app/agent.py: R8 mandates no change (no prompt template edit)'
  - 'backend/app/memory_store.py: create() already accepts links= (verified); no edit
    needed'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/memory_parser.py
  - backend/tests/test_cronos_remember_parser.py
  validation_command: cd backend && python -m pytest tests/test_cronos_remember_parser.py
    -v --override-ini="addopts="
  max_diff_lines: 250
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/worker.py
  - backend/tests/test_worker_cronos_remember.py
  validation_command: cd backend && python -m pytest tests/test_worker_cronos_remember.py
    -v --override-ini="addopts="
  max_diff_lines: 200
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - backend/tests/test_cronos_remember_coexistence.py
  validation_command: cd backend && python -m pytest tests/test_memory_parser.py tests/test_cronos_remember_coexistence.py
    -v --override-ini="addopts="
  max_diff_lines: 150
  depends_on:
  - I1
  - I2
risks:
- description: 'Adding cronos_remember parsing to memory_parser.py could inadvertently
    change the shared splitlines/fence loop and regress the existing MEMORY: / ```memory
    path, breaking the 26 backward-compat tests (R4).'
  severity: medium
  mitigation: I1 adds parse_cronos_remember_blocks() and CronosRememberBlock as a
    NEW, independent function and dataclass; it must not touch parse_memory_blocks(),
    MemoryBlock, _MEMORY_LINE, _FENCE_OPEN, or _FENCE_CLOSE. I3 runs the full unmodified
    tests/test_memory_parser.py as a regression gate plus a coexistence test proving
    both parsers fire independently on the same text.
- description: The cronos_remember fence body is YAML parsed from attacker-influenceable
    agent output; a malformed or hostile YAML payload could raise inside yaml.safe_load
    or yield unexpected Python types (e.g. metadata as a list, body as an int), crashing
    finalize or corrupting the MemoryItem mapping.
  severity: medium
  mitigation: parse_cronos_remember_blocks() must use yaml.safe_load (never yaml.load),
    wrap the load in try/except and skip the block on any exception or non-mapping
    result, and coerce/validate each field type (name/type/description must be non-empty
    str, metadata must be a dict else dropped). worker.py I2 additionally wraps the
    call in try/except log.exception per R6 so no block can fail the task.
- description: 'Prompt-injection surface: a CRONOS_REMEMBER block lets an agent persist
    arbitrary text into shared space-scoped memory that is later injected verbatim
    into other agents'' # Memory Context, enabling cross-run instruction injection.'
  severity: medium
  mitigation: 'Items are created confirmed=False (unconfirmed, lower retrieval weight
    via existing lifecycle), type is whitelist-validated against MemoryKind (unknown
    type -> block skipped, mirroring _normalize_kind), and name is capped at <=120
    chars. No code is executed at parse or persist time. Broader content sanitization
    is out of scope and noted as a deferred follow-on, consistent with the existing
    MEMORY: path which has the same surface.'
- description: Stuffing metadata as a single JSON string into MemoryItem.links[] (R3)
    may collide with future semantic use of links[] (e.g. memory-to-memory cross-references).
  severity: low
  mitigation: Scout confirmed links[] has no current production usage. The JSON-string
    encoding is self-describing and reversible; if links[] later gains structured
    semantics, a dedicated sentinel_metadata field can be migrated to. Documented
    as a deferred concern in the Next consumer brief.
metrics:
  tool_calls: 11
  files_read: 5
  memory_hits: 2
  iterations_planned: 3
---

## Summary

This design implements the CRONOS_REMEMBER structured sentinel as a deliberately narrow, two-production-file change: `memory_parser.py` gains a new `parse_cronos_remember_blocks()` function plus a `CronosRememberBlock` dataclass (parsing, R1/R2/R5), and `worker.py` gains the field-mapping + persistence integration in both finalize hooks (R3/R6/R7). The iteration DAG is a short serial chain — I1 (parser) → I2 (worker integration) → I3 (backward-compat regression gate) — because the worker integration consumes the parser API and the regression gate must observe both in place. The existing `MEMORY:` path, `trace_parser.py`, and `agent.py` are untouched (R4/R7/R8); `memory_store.create()` already accepts `links=`, so no schema or signature change is required (OQ3 resolved at design time). The key non-obvious tradeoff, captured in the risk register, is that the YAML fence body is parsed from attacker-influenceable agent output and persisted into shared memory — mitigated by `yaml.safe_load`, type validation, type whitelisting, and `confirmed=False` creation.

## Components

### Data
- `CronosRememberBlock` (memory_parser.py): new dataclass — `name: str`, `type: str`, `description: str`, `body: str = ""`, `metadata: dict = {}` (R5).
- `MemoryItem` (models.py): unchanged — existing `title`, `kind`, `body`, `links[]`, `confirmed`, `sources[]` fields accommodate the full sentinel mapping (R3); no migration.

### Backend
- `parse_cronos_remember_blocks(text) -> list[CronosRememberBlock]` (memory_parser.py): new fenced-block parser for ` ```cronos_remember ... ``` `, YAML interior via `yaml.safe_load`, silent-skip on missing required fields / unknown type / malformed YAML / unclosed fence (R1, R2, R5).
- `_finalize_task()` / `_finalize_child()` (worker.py): immediately after the existing `parse_memory_blocks()` call, invoke the new parser, map fields (name→title, type→kind, description+body→body, metadata→JSON in links[]), and persist via `memory_store.create(confirmed=False, sources=...)`; wrapped in try/except `log.exception`; skipped when `memory_store is None` (R3, R6). A comment notes that sentinel-sourced items are not reflected in `RunTrace.memory_written` (R7).
- `memory_store.create()` (memory_store.py): NO CHANGE — already accepts `links: list[str] | None = None` (verified at memory_store.py:212). Listed here only to document that R3's metadata→links[] mapping is unblocked without an edit.
- Bare-sentinel invocation model (R8): extraction is post-run from `final_text` with no tool call, subprocess, or prompt-template edit; satisfied by I2 doing the extraction inside the existing finalize path and by NOT modifying `agent.py` / the write-memory skill.

## Implementation plan

| ID  | Type    | Depends on | Scope files (abridged)                                              | Validation                                                                                          |
|-----|---------|------------|---------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| I1  | backend | -          | backend/app/memory_parser.py, backend/tests/test_cronos_remember_parser.py | cd backend && python -m pytest tests/test_cronos_remember_parser.py -v --override-ini="addopts="     |
| I2  | backend | I1         | backend/app/worker.py, backend/tests/test_worker_cronos_remember.py | cd backend && python -m pytest tests/test_worker_cronos_remember.py -v --override-ini="addopts="     |
| I3  | backend | I1, I2     | backend/tests/test_cronos_remember_coexistence.py                   | cd backend && python -m pytest tests/test_memory_parser.py tests/test_cronos_remember_coexistence.py -v --override-ini="addopts=" |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| New parser code regresses the shared parse loop and breaks the 26 backward-compat MEMORY: tests (R4) | medium | I1 adds an independent function/dataclass touching none of parse_memory_blocks/MemoryBlock/_MEMORY_LINE/_FENCE_OPEN/_FENCE_CLOSE; I3 runs the unmodified existing suite + a coexistence test as a gate. |
| Malformed/hostile YAML in the agent-controlled fence body raises or yields wrong types, crashing finalize or corrupting the mapping | medium | yaml.safe_load only; try/except + skip on exception or non-mapping; per-field type validation; worker I2 try/except log.exception (R6). |
| Prompt-injection surface — sentinel persists arbitrary text into shared memory re-injected into other agents | medium | confirmed=False, MemoryKind whitelist (unknown type skipped), name capped 120 chars, no execution at parse/persist; same surface as existing MEMORY: path. |
| metadata-as-JSON in links[] may collide with future links[] semantics | low | links[] has no current production use (scout-confirmed); encoding is reversible; dedicated field migration path noted if links[] later gains structure. |

## Assumptions

- **PyYAML available**: `yaml.safe_load` is importable in the backend (FastAPI dependency tree); the parser uses it for the fence interior, per the analyst's stated YAML-body assumption.
- **No memory_store edit needed**: `memory_store.create()` already exposes `links: list[str] | None = None` (verified at memory_store.py:212), resolving analyst OQ3 — R3 is implementable without a signature or schema change.
- **New test files only**: I1/I2 create *new* test modules (`test_cronos_remember_parser.py`, `test_worker_cronos_remember.py`) so the existing `test_memory_parser.py` stays byte-for-byte unchanged, satisfying R4's "26 existing tests pass unmodified". I3's scope is a single new coexistence test; it *runs* the existing file but does not modify it.
- **name is advisory (OQ1 deferred)**: `name`→`title` verbatim with no dedup/upsert; find-or-update is explicitly deferred per analysis Scope.
- **No top-level confidence field (OQ2 deferred)**: `confidence` stays at the create() default (1.0); metadata is not mined for a confidence override in this iteration.
- **Coverage floor**: validation commands use `--override-ini="addopts="` to bypass the repo's `--cov-fail-under=60` gate on narrow `-k`/single-file runs (per feedback_pipeline_narrow_k_coverage); the full-suite coverage gate is the test phase's job, not these per-iteration validations.

## Open questions

- None. (Analyst OQ1/OQ2 are resolved as "defer" per ## Scope; OQ3 is resolved by direct verification that create() already accepts links=.)

## Next consumer brief

Read in order: `iterations[]` (the plan), each `iterations[].scope_files` (hard diff boundary — do not write outside it), each `iterations[].validation_command` (run verbatim; it already neutralizes the coverage floor), and `risks[]`.

Cross-iteration invariants NOT derivable from the YAML:
- **I1 must not modify** `parse_memory_blocks`, `MemoryBlock`, `_MEMORY_LINE`, `_FENCE_OPEN`, or `_FENCE_CLOSE` — only ADD the new function + dataclass. R4 is a hard gate.
- **R3 field mapping is owned by I2** (the `memory_store.create()` call site), not by the parser: name→title (verbatim, not first-line-of-body), type→kind (MemoryKind), description+body→body (description, blank line, body; description-only when no body), metadata→`links=[json.dumps(metadata)]` (and `links=[]` when no metadata). I1 only surfaces the raw fields on `CronosRememberBlock`.
- **I2 must add the R7 comment** at the extraction site noting sentinel-persisted items are absent from `RunTrace.memory_written`, and must mirror the existing MEMORY: source convention: `_finalize_task` uses `sources=[f"task:{id}", f"run:{run_index}"]`, `_finalize_child` uses `sources=[f"task:{child_id}"]` (no run index).
- **Do not touch** `trace_parser.py` (R7), `agent.py`/build_prompt (R8), or `memory_store.py` (already supports links=). Any temptation to edit them means re-reading Scope, not editing.
