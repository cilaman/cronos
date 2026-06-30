---
cc_version: '1.0'
agent: pipeline-analyst
slug: sg7-standalone-rungate-portability-defer
phase: analysis
status: done
confidence: 0.88
inputs_used:
- memory:project_pipeline_gate_skill
- memory:project_pipeline_verifier
- memory:delivery-v2-standalone_design
- .cronos/pipeline/sg7-standalone-rungate-portability-defer/scout-report-sg7-standalone-rungate-portability-defer.md
- backend/app/pipeline/gate.py
- backend/app/pipeline/verify.py
- packages/delivery-workflow/.importlinter
- packages/delivery-workflow/adapters/cronos/adapter.py
- backend/tests/test_pipeline_verify.py
- backend/tests/test_pipeline_gate.py
- backend/tests/test_pipeline_gate_security.py
outputs_produced:
- .cronos/pipeline/sg7-standalone-rungate-portability-defer/analysis-report-sg7-standalone-rungate-portability-defer.md
blockers: []
next_consumer: design
request: 'Spec 7 — Standalone runGate portability


  After SG4/SG5, the only remaining app-coupling in the runner is `runGate`. The gate
  operation (gate.py) imports from `app.pipeline.verify` (2 symbols: line 25-26 of
  gate.py).


  Everything else is already portable:

  - state.read/write → lib/state (portable)

  - telemetry.emit + budget kill-switch → lib/telemetry (portable)

  - evalCondition → lib/conditions (SG3 lifts this)

  - dispatchAgent → trace_parser.py has zero app imports

  - escalate → via state.write (portable)

  - events → adapter no-ops/logs for standalone


  ### Action (two options)


  **Option A (preferred): lift verify.py + schemas/ to lib/**

  Move `backend/app/pipeline/verify.py` -> `packages/delivery-workflow/lib/verify.py`

  Move `backend/app/pipeline/schemas/` -> `packages/delivery-workflow/lib/schemas/`

  Update gate.py to import from lib.verify

  Re-export from app.pipeline.verify for backward compat


  **Option B: shell-out**

  StandaloneAdapter.runGate shells out to the same verify commands (subprocess call
  to the gate CLI)


  ### Why deferrable

  Standalone uses headless `claude -p` (bills to separate metered credit after June
  15 2026). The runner''s budget ceiling (telemetry.emit -> BudgetExceededSignal ->
  escalate) is the kill-switch -- already in lib/telemetry.

  Building standalone is a separate future effort; this spec records what it needs
  so nothing in SG4/SG5 blocks it.


  ### References

  - `backend/app/pipeline/gate.py` -- the 2 app imports to sever

  - `backend/app/pipeline/verify.py` -- the verification logic to lift

  - `backend/app/pipeline/schemas/` -- 7 schema files to lift

  - `packages/delivery-workflow/lib/` -- destination'
has_ui: false
coverage_summary:
  searched:
  - backend/app/pipeline/
  - packages/delivery-workflow/lib/
  - packages/delivery-workflow/adapters/
  - backend/tests/
  excluded:
  - frontend/: backend-only feature
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
  - glob_structural
  - traceability_mapping
traceability:
- requirement_id: R1
  statement: contract.py is lifted to packages/delivery-workflow/lib/contract.py and
    the original backend/app/pipeline/contract.py becomes a re-export stub.
  acceptance_criteria:
  - Given the lift, when any module under lib/, runner/, or adapters/ imports constants
    from lib.contract, then no app.* import chain is traversed.
  - Given backward-compat consumers (normalize.py, __init__.py, state_writer.py),
    when they import from app.pipeline.contract, then they receive the same values
    via the re-export stub.
  - importlinter lint passes with zero forbidden-module violations after the move.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R2
  statement: verify.py is lifted to packages/delivery-workflow/lib/verify.py with
    its SCHEMAS_DIR resolved relative to its new location, and the original backend/app/pipeline/verify.py
    becomes a re-export stub.
  acceptance_criteria:
  - Given lib/verify.py, when load_schema(class_name) is called, then it resolves
    schemas/ relative to lib/verify.py's own __file__, not the old backend/app/pipeline
    path.
  - Given backend/app/pipeline/verify.py (stub), when any of its exported symbols
    (split_frontmatter, verify, EXIT_PROCEED, canonical_artifact_relpath) are imported,
    then they resolve to the lib.verify implementations.
  - All existing tests in test_pipeline_verify.py (1323 lines) continue to pass without
    import changes -- the stub re-export is transparent.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R3
  statement: The 8 CC-v1 schema YAML files are lifted to packages/delivery-workflow/lib/schemas/
    so lib/verify.py can resolve them without an app.pipeline path dependency.
  acceptance_criteria:
  - Given lib/schemas/, when lib/verify.py calls load_schema('analysis'), then it
    loads from packages/delivery-workflow/lib/schemas/analysis.schema.yaml.
  - All 8 schema files (research, analysis, design, implementation, test, review,
    doc, retro) are present under lib/schemas/ with byte-identical content to their
    backend/app/pipeline/schemas/ originals.
  - lib/schemas/ is the single canonical source; backend/app/pipeline/verify.py stub
    sets SCHEMAS_DIR to point to lib/schemas/ so no duplicate maintenance is required.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R4
  statement: gate.py's two app.pipeline.verify imports (lines 25-26) are updated to
    import from lib.verify, severing the last app.pipeline coupling in the gate engine.
  acceptance_criteria:
  - Given gate.py after the change, when grep searches for 'from app.pipeline' in
    gate.py, then zero matches are found.
  - Given gate.py importing from lib.verify, when split_frontmatter and verify are
    called in _read_header() and _check_schema(), then they behave identically to
    before.
  - All existing tests in test_pipeline_gate.py (744 lines) and test_pipeline_gate_security.py
    (290 lines) continue to pass.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R5
  statement: CronosAdapter.runGate in adapters/cronos/adapter.py continues to function
    correctly through the refactored gate.py which now internally imports from lib.verify.
  acceptance_criteria:
  - Given CronosAdapter.runGate's deferred import (from app.pipeline.gate import runGate
    as _runGate), when runGate is called, then it delegates to gate.py which now internally
    imports from lib.verify -- no call-site changes required in adapter.py.
  - 'The importlinter rule is satisfied: adapters/ does not import lib.verify or app.pipeline.verify
    directly.'
  verifying_phase: test
  confidence: 0.85
- requirement_id: R6
  statement: The delivery-workflow importlinter CI gate passes after the lift, confirming
    that lib/ and runner/ have zero forbidden app.* import chains.
  acceptance_criteria:
  - Given the updated codebase, when lint-imports is run in packages/delivery-workflow/,
    then the [importlinter:contract:no-app-imports] rule reports zero violations.
  - The no-app-imports rule source_modules (lib, runner) are free of app.* or backend.*
    imports at both static-analysis and runtime-import level.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R7
  statement: All backend callers of app.pipeline.contract and app.pipeline.verify
    (normalize.py, __init__.py, state_writer.py, run_evals.py, gate.py before R4)
    continue to resolve without modification, importing through the re-export stubs.
  acceptance_criteria:
  - Given backend/app/pipeline/__init__.py and normalize.py importing from app.pipeline.contract
    and app.pipeline.verify, when the backend test suite runs, then zero ImportError
    or AttributeError exceptions occur due to the stub refactor.
  - pytest test_pipeline_verify.py, test_pipeline_gate.py, test_pipeline_normalize.py,
    and test_pipeline_fixtures.py all pass without any import-path changes in those
    test files.
  verifying_phase: test
  confidence: 0.9
metrics:
  tool_calls: 20
  files_read: 11
  memory_hits: 3
---

## Summary

This spec records the structural prerequisites for a future standalone runner that operates without access to the Cronos app container. The only remaining app-coupled symbols in the gate engine are the two `app.pipeline.verify` imports in `backend/app/pipeline/gate.py` (lines 25-26: `split_frontmatter` and `verify`). Option A -- lifting `contract.py`, `verify.py`, and the 8 CC-v1 schema YAML files into `packages/delivery-workflow/lib/` -- is confirmed as the correct path. It satisfies the existing importlinter contract (`no-app-imports` on `lib` and `runner`), enables in-process gate validation in the future standalone runner, and backward-compat re-export stubs ensure zero breakage for the five existing callers in the Cronos backend. This work is correctly deferred: nothing in SG4/SG5 is blocked by it, and the standalone runner has not yet launched.

## Scope

### In scope
- Lift `backend/app/pipeline/contract.py` to `packages/delivery-workflow/lib/contract.py`
- Lift `backend/app/pipeline/verify.py` to `packages/delivery-workflow/lib/verify.py` with SCHEMAS_DIR re-anchored to `__file__`
- Lift all 8 CC-v1 schema YAML files to `packages/delivery-workflow/lib/schemas/`
- Replace `backend/app/pipeline/contract.py` and `backend/app/pipeline/verify.py` with re-export stubs
- Update `backend/app/pipeline/gate.py` lines 25-26 to import from `lib.verify`
- Verify importlinter passes (no-app-imports rule) after the lift
- Ensure all existing backend test files pass without modification (transparent re-export)

### Out of scope
- Moving `gate.py` itself to `runner/` or `lib/` (open question resolved in design phase)
- Creating a StandaloneAdapter or any standalone runner implementation
- Modifying `adapters/cronos/adapter.py` -- its deferred `from app.pipeline.gate import runGate` remains as-is
- Schema content changes or schema versioning policy

### Deferred
- Physical relocation of `gate.py` from `backend/app/pipeline/` to `packages/delivery-workflow/runner/` -- until standalone runner architecture is finalized
- StandaloneAdapter.runGate implementation (the actual standalone runner build)
- Schema versioning strategy / single-source-of-truth enforcement between backend schemas and lib/schemas/

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Lift contract.py to lib/ with re-export stub in app.pipeline |
| R2 | Lift verify.py to lib/ with SCHEMAS_DIR re-anchored and re-export stub in app.pipeline |
| R3 | Lift 8 CC-v1 schema YAML files to lib/schemas/ |
| R4 | Update gate.py lines 25-26 to import from lib.verify |
| R5 | Confirm CronosAdapter.runGate call path works through the refactored gate.py |
| R6 | importlinter no-app-imports CI gate passes after the lift |
| R7 | All backend callers of app.pipeline.contract and app.pipeline.verify resolve via re-export stubs |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 -- lib.contract importable with no app.* chain; re-export stub transparent to existing callers; importlinter clean
- R2 -- lib.verify's load_schema resolves to lib/schemas/; stub re-exports all 4 public symbols; test_pipeline_verify.py passes unchanged
- R3 -- All 8 schema files present in lib/schemas/ with byte-identical content; lib/schemas/ is the single canonical source
- R4 -- Zero "from app.pipeline" in gate.py after change; split_frontmatter and verify behave identically; test_pipeline_gate*.py passes
- R5 -- CronosAdapter.runGate deferred import path untouched; end-to-end gate call succeeds through lib.verify-backed gate.py
- R6 -- lint-imports reports zero forbidden violations in delivery-workflow package after lift
- R7 -- Backend test suite (normalize, fixtures, verify, gate) passes without import-path changes in any test file

## Traceability

The full requirement to acceptance criteria to verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | contract.py is lifted to lib/ with re-export stub in app.pipeline |
| R2 | test | verify.py is lifted to lib/ with SCHEMAS_DIR re-anchored and re-export stub |
| R3 | test | 8 CC-v1 schema YAML files are lifted to lib/schemas/ |
| R4 | test | gate.py lines 25-26 updated to import from lib.verify |
| R5 | test | CronosAdapter.runGate call path works through lib.verify-backed gate.py |
| R6 | test | importlinter no-app-imports rule passes after the lift |
| R7 | test | All backend callers resolve via re-export stubs without modification |

## Assumptions

- **Option A (lift) is confirmed over Option B (shell-out).** The importlinter contract (`no-app-imports` on `lib` and `runner`) structurally forbids runtime imports of `app.*` from lib/runner, making shell-out an incomplete solution -- it defers coupling to subprocess runtime rather than eliminating it.
- **Backward compatibility is non-negotiable.** Five callers in the backend (`gate.py`, `normalize.py`, `__init__.py`, `state_writer.py`, `run_evals.py`) import from `app.pipeline.verify` or `app.pipeline.contract`; re-export stubs must make the refactor transparent.
- **gate.py stays in backend/app/pipeline/ for now.** The move to `runner/` is an architectural decision deferred to the design phase.
- **lib/schemas/ is a new subdirectory, not a merge with packages/delivery-workflow/schemas/.** The existing delivery-workflow schemas/ directory contains delivery-workflow-native schemas (delivery.workflow.schema.yaml, improvement.schema.yaml, frontend.schema.yaml). The CC-v1 schemas land in `lib/schemas/` as a distinct namespace.
- **has_ui=false rationale:** This is entirely a backend/package refactor -- file motion, import rewiring, and importlinter compliance. No user-facing screens or forms are involved.
- **importlinter is actively enforced.** Direct reading of `.importlinter` confirms the `no-app-imports` rule covers both `lib` and `runner` source modules with `app` and `backend` as forbidden targets.

## Open questions

- **Single source of truth for schema YAML:** After the lift, should `backend/app/pipeline/verify.py` stub re-anchor its `SCHEMAS_DIR` to point to `lib/schemas/` (eliminating dual maintenance), or are both copies kept in sync? The design agent should resolve this -- option (a), re-anchoring the stub's SCHEMAS_DIR, is strongly preferred.
- **gate.py layer assignment:** Design must decide whether gate.py stays in `app.pipeline` (updated imports only), moves to `runner/` (enforces full layering), or moves to `lib/` (importable without app context). This determines what the standalone runner can import at load time.

## Next consumer brief

Read `traceability[]` for the full requirement list and `## Scope` for explicit boundaries. Key decision points for the design agent:

1. **Schema single-source-of-truth** (Open question 1): decide whether lib/verify.py's SCHEMAS_DIR re-anchor eliminates the backend/app/pipeline/schemas/ copy or both coexist. The re-export stub design should encode this decision.
2. **gate.py layer assignment** (Open question 2): choose the final layer (app.pipeline / runner / lib). This is the primary architectural question -- it determines whether a future StandaloneAdapter can import gate.py without an app context at all.
3. **Re-export stub public surface:** lib/verify.py must export at minimum `split_frontmatter`, `verify`, `EXIT_PROCEED`, `canonical_artifact_relpath` (confirmed from grep of backend callers). Design should enumerate the full surface to avoid partial re-export breakage.
4. **Iteration ordering constraint:** R1 (contract) before R2 (verify, depends on contract) before R3 (schemas, needed by verify) before R4 (gate.py update). R5 and R6 are verification steps post R1-R4. R7 spans all iterations.
5. **Test files are hard constraints:** test_pipeline_verify.py (1323 lines), test_pipeline_gate.py (744 lines), test_pipeline_gate_security.py (290 lines) must pass without import-path changes in the test files themselves -- transparent re-export is not optional.
