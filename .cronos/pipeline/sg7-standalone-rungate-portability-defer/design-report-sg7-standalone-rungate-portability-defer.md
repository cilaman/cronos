---
cc_version: '1.0'
agent: pipeline-architect
slug: sg7-standalone-rungate-portability-defer
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:project_pipeline_gate_skill
- memory:project_pipeline_verifier
- memory:delivery-v2-standalone_design
- memory:project_pipeline_foundation_merged
- .cronos/pipeline/sg7-standalone-rungate-portability-defer/analysis-report-sg7-standalone-rungate-portability-defer.md
- .cronos/pipeline/sg7-standalone-rungate-portability-defer/scout-report-sg7-standalone-rungate-portability-defer.md
- backend/app/pipeline/gate.py
- backend/app/pipeline/verify.py
- backend/app/pipeline/contract.py
- backend/app/pipeline/__init__.py
- backend/app/pipeline/normalize.py
- packages/delivery-workflow/.importlinter
- packages/delivery-workflow/adapters/cronos/adapter.py
- packages/delivery-workflow/lib/__init__.py
- packages/delivery-workflow/pyproject.toml
- packages/delivery-workflow/tests/test_import_boundary.py
outputs_produced:
- .cronos/pipeline/sg7-standalone-rungate-portability-defer/design-report-sg7-standalone-rungate-portability-defer.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/pipeline/
  - packages/delivery-workflow/lib/
  - packages/delivery-workflow/adapters/
  - packages/delivery-workflow/tests/
  - backend/tests/
  excluded:
  - frontend/: backend-only refactor (has_ui=false)
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  scope_files:
  - packages/delivery-workflow/lib/contract.py
  - backend/app/pipeline/contract.py
  - backend/tests/test_pipeline_contract_reexport.py
  validation_command: cd /data/spaces/cronos-development/backend && pytest tests/test_pipeline_contract_reexport.py
    tests/test_pipeline_state_writer.py tests/test_pipeline_normalize.py -v
  max_diff_lines: 300
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - packages/delivery-workflow/lib/schemas/research.schema.yaml
  - packages/delivery-workflow/lib/schemas/analysis.schema.yaml
  - packages/delivery-workflow/lib/schemas/design.schema.yaml
  - packages/delivery-workflow/lib/schemas/implementation.schema.yaml
  - packages/delivery-workflow/lib/schemas/test.schema.yaml
  - packages/delivery-workflow/lib/schemas/review.schema.yaml
  - packages/delivery-workflow/lib/schemas/doc.schema.yaml
  - packages/delivery-workflow/lib/schemas/retro.schema.yaml
  - backend/app/pipeline/schemas/research.schema.yaml
  - backend/app/pipeline/schemas/analysis.schema.yaml
  - backend/app/pipeline/schemas/design.schema.yaml
  - backend/app/pipeline/schemas/implementation.schema.yaml
  - backend/app/pipeline/schemas/test.schema.yaml
  - backend/app/pipeline/schemas/review.schema.yaml
  - backend/app/pipeline/schemas/doc.schema.yaml
  - backend/app/pipeline/schemas/retro.schema.yaml
  - backend/tests/test_pipeline_schemas_canonical.py
  validation_command: cd /data/spaces/cronos-development/backend && pytest tests/test_pipeline_schemas_canonical.py
    -v
  max_diff_lines: 200
  depends_on: []
- id: I3
  type: backend
  scope_files:
  - packages/delivery-workflow/lib/verify.py
  - backend/app/pipeline/verify.py
  - backend/tests/test_pipeline_verify_reexport.py
  validation_command: cd /data/spaces/cronos-development/backend && pytest tests/test_pipeline_verify.py
    tests/test_pipeline_verify_reexport.py tests/test_pipeline_normalize.py tests/test_pipeline_fixtures.py
    -v
  max_diff_lines: 600
  depends_on:
  - I1
  - I2
- id: I4
  type: backend
  scope_files:
  - backend/app/pipeline/gate.py
  validation_command: cd /data/spaces/cronos-development/backend && pytest tests/test_pipeline_gate.py
    tests/test_pipeline_gate_security.py -v && ! grep -n 'from app.pipeline' app/pipeline/gate.py
  max_diff_lines: 30
  depends_on:
  - I3
- id: I5
  type: backend
  scope_files:
  - packages/delivery-workflow/tests/test_import_boundary.py
  - packages/delivery-workflow/tests/test_lib_verify_portability.py
  validation_command: cd /data/spaces/cronos-development/packages/delivery-workflow
    && pytest tests/test_import_boundary.py tests/test_lib_verify_portability.py -v
    && lint-imports --config pyproject.toml
  max_diff_lines: 200
  depends_on:
  - I3
- id: I6
  type: backend
  scope_files:
  - backend/tests/test_pipeline_adapter_rungate_smoke.py
  validation_command: cd /data/spaces/cronos-development/backend && pytest tests/test_pipeline_adapter_rungate_smoke.py
    -v
  max_diff_lines: 200
  depends_on:
  - I4
risks:
- description: Re-export stub for verify.py omits a symbol that an existing caller
    imports (e.g. PER_CLASS_REQUIRED_SECTIONS used by normalize.py, or main used by
    test_pipeline_verify.py), causing ImportError at backend startup.
  severity: high
  mitigation: 'I3 stub MUST re-export the full enumerated surface from `lib.verify`:
    CLASS_CONFIG, EXIT_PROCEED, EXIT_FAIL, EXIT_ESCALATE, EXIT_RETRY, VerifyResult,
    canonical_artifact_relpath, verify, split_frontmatter, PER_CLASS_REQUIRED_SECTIONS,
    main, SCHEMAS_DIR. The new test_pipeline_verify_reexport.py asserts each symbol
    is importable and `is` identical to the lib.verify reference; the existing 1323-line
    test_pipeline_verify.py exercises real usage.'
- description: lib/verify.py's SCHEMAS_DIR resolves to lib/schemas/ via Path(__file__).resolve().parent
    / 'schemas', so backend/app/pipeline/schemas/ becomes dead weight if not deleted
    — but deleting it breaks any callers reading schemas by literal path (e.g. tooling,
    docs).
  severity: medium
  mitigation: 'Open Question 1 RESOLVED: re-anchor backend stub''s SCHEMAS_DIR to
    lib/schemas/ AND delete backend/app/pipeline/schemas/ contents (the 8 YAML files)
    — single source of truth. I2 explicitly removes the 8 backend schema files in
    the same diff that creates the lib/schemas/ copies; I2 test asserts (a) lib/schemas/
    contains the 8 files, (b) backend/app/pipeline/schemas/ is absent or empty, and
    (c) verify.SCHEMAS_DIR resolves under packages/delivery-workflow/lib/.'
- description: lib/verify.py imports from `lib.contract`, but backend test code that
    monkey-patches `app.pipeline.verify.CC_VERSION` (or similar contract-derived constants)
    silently fails to take effect because verify.py reads through lib.contract, not
    app.pipeline.contract.
  severity: medium
  mitigation: 'Stub design: backend/app/pipeline/contract.py does `from lib.contract
    import *` and the lib/contract.py module is the single instance — there is only
    one CC_VERSION binding in the process. Verify with a unit test in test_pipeline_contract_reexport.py:
    `import app.pipeline.contract as a; import lib.contract as b; assert a.CC_VERSION
    is b.CC_VERSION` (identity check, not equality).'
- description: 'Open Question 2 (gate.py layer assignment): keeping gate.py in backend/app/pipeline/
    means a future StandaloneAdapter cannot import the gate engine at runtime without
    an app context — only the lifted lib.verify portion is portable. This re-emerges
    as work in the standalone build SG.'
  severity: low
  mitigation: 'Open Question 2 RESOLVED: gate.py stays in backend/app/pipeline/ for
    SG7. Rationale: (a) R5 acceptance explicitly assumes gate.py stays in backend/app/pipeline
    with only imports updated and adapter.py untouched; (b) moving gate.py would expand
    SG7 scope beyond the analysis-report boundary (Out of scope: ''Moving gate.py
    itself to runner/ or lib/''); (c) gate.py still imports lib.security (line 27,
    established precedent for hybrid). Documented in deferred work for the StandaloneAdapter
    SG: gate.py relocation to runner/ is its own concern.'
- description: importlinter `lint-imports` CLI is part of the dev optional-extras
    (`import-linter>=2.0`) and may not be installed in every developer environment;
    I5 validation can give false PROCEED if the binary is missing.
  severity: low
  mitigation: I5 also runs test_import_boundary.py (pure-Python AST scanner with zero
    external deps, already in the repo). The lint-imports CLI is a belt-and-braces
    second check; if absent the AST test still binds R6. Implementor should ensure
    `pip install -e .[dev]` (or equivalent) is documented in the impl-report.
- description: Backend pyproject.toml or backend container lacks a path to import
    `lib.contract` and `lib.verify` from `packages/delivery-workflow/`, breaking the
    re-export stubs at backend startup.
  severity: high
  mitigation: 'Pre-check before I1: verify that `import lib.contract` and `import
    lib.verify` already work from within backend/ (the existing `from lib.security
    import evaluate_security` at gate.py:27 confirms `lib` is on sys.path). Implementor''s
    I1 first step is to run `cd backend && python -c ''import lib.security''`; if
    it fails, fix sys.path wiring (likely a PYTHONPATH or editable install) BEFORE
    creating any re-export stub. Document the verified import path in the I1 impl-report.'
metrics:
  tool_calls: 13
  files_read: 12
  memory_hits: 4
  iterations_planned: 6
---

## Summary

SG7 lifts `contract.py`, `verify.py`, and the 8 CC-v1 schema YAML files from `backend/app/pipeline/` into `packages/delivery-workflow/lib/`, severs the last two `app.pipeline.verify` imports in `backend/app/pipeline/gate.py` (lines 25-26), and leaves `backend/app/pipeline/{contract,verify}.py` as transparent re-export stubs so the five existing backend callers continue to resolve without modification. Open Question 1 is resolved toward a single canonical source: lib/schemas/ replaces backend/app/pipeline/schemas/ outright (I2 deletes the backend copies and re-anchors the stub's `SCHEMAS_DIR`). Open Question 2 is resolved: gate.py stays in `backend/app/pipeline/` and `adapters/cronos/adapter.py` is untouched (R5 acceptance criterion). The DAG is wide: I1 (contract) and I2 (schemas) run in layer 0 in parallel; I3 (verify) depends on both; I4 (gate import flip) and I5 (importlinter compliance test) depend on I3 in layer 3; I6 (adapter smoke) closes the loop in layer 4. The dominant risk is partial re-export breakage of verify.py's public surface — mitigated by enumerating the full surface (12 symbols, grepped from real callers) in a new `test_pipeline_verify_reexport.py` that asserts identity (`is`) rather than equality.

## Components

### Data
- `packages/delivery-workflow/lib/schemas/`: new subdirectory holding the 8 CC-v1 schema YAML files (research, analysis, design, implementation, test, review, doc, retro). Becomes the single canonical source — the backend/app/pipeline/schemas/ copies are deleted in the same iteration.

### Backend
- `packages/delivery-workflow/lib/contract.py`: lifted from `backend/app/pipeline/contract.py`. Pure data module (Final constants), zero app imports. New canonical source for CC_VERSION, HEADER_FIELDS, STATUS_VALUES, REQUIRED_SECTIONS, FINDINGS_SECTION_ALIASES, OPEN_QUESTIONS_SECTION_ALIASES, TRACE_OWNED_METRICS, AGENT_REPORTED_METRICS, R_RULES, ARTIFACT_PATH_TEMPLATE, NEXT_CONSUMER_USER_SENTINEL, HEADER_REQUIRED_FIELDS, NO_PROSE_PARSING_RULE.
- `packages/delivery-workflow/lib/verify.py`: lifted from `backend/app/pipeline/verify.py`. SCHEMAS_DIR re-anchored to `Path(__file__).resolve().parent / "schemas"` so it resolves to lib/schemas/. Imports rewritten: `from app.pipeline.contract import ...` becomes `from lib.contract import ...`. The internal `from app.pipeline.normalize import normalize` at verify.py:1350 stays as `from app.pipeline.normalize import normalize` (advisory: that single deferred import is the one app coupling that survives in lib/verify.py — see Open questions for the follow-up SG).
- `backend/app/pipeline/contract.py`: rewritten as a thin re-export stub doing `from lib.contract import *  # noqa: F401,F403` plus an explicit `__all__` listing every re-exported name so static analyzers and `from app.pipeline.contract import X` calls all succeed.
- `backend/app/pipeline/verify.py`: rewritten as a thin re-export stub doing explicit `from lib.verify import (CLASS_CONFIG, EXIT_PROCEED, EXIT_FAIL, EXIT_ESCALATE, EXIT_RETRY, VerifyResult, canonical_artifact_relpath, verify, split_frontmatter, PER_CLASS_REQUIRED_SECTIONS, main, SCHEMAS_DIR)` plus an `__all__` and a re-anchored `SCHEMAS_DIR = lib.verify.SCHEMAS_DIR` rebinding (no path duplication).
- `backend/app/pipeline/gate.py`: only lines 25-26 change. `from app.pipeline.verify import split_frontmatter` → `from lib.verify import split_frontmatter`; `from app.pipeline.verify import verify as _cc_verify` → `from lib.verify import verify as _cc_verify`. Zero other modifications; `lib.security` import at line 27 is precedent. After the change, `grep 'from app.pipeline' backend/app/pipeline/gate.py` returns zero matches (R4 acceptance).
- `packages/delivery-workflow/adapters/cronos/adapter.py`: **NOT modified.** Its deferred `from app.pipeline.gate import runGate as _runGate` at line 351 stays. R5 acceptance: the adapter delegates to gate.py which internally now imports from lib.verify; the adapter itself does not import lib.verify directly (importlinter would forbid that for source_modules=adapters? — note: pyproject.toml limits the rule to lib/runner only; adapters is intentionally exempt as the portability seam).

### Test scaffolding (new files)
- `backend/tests/test_pipeline_contract_reexport.py`: NEW. Asserts every contract constant is importable via `app.pipeline.contract` AND identity-equal to its `lib.contract` counterpart.
- `backend/tests/test_pipeline_verify_reexport.py`: NEW. Asserts each of the 12 verify public symbols is importable via `app.pipeline.verify` AND identity-equal to its `lib.verify` counterpart. Also asserts `app.pipeline.verify.SCHEMAS_DIR == lib.verify.SCHEMAS_DIR` (resolves under packages/delivery-workflow/lib/).
- `backend/tests/test_pipeline_schemas_canonical.py`: NEW. Asserts (a) lib/schemas/ contains all 8 files, (b) backend/app/pipeline/schemas/ has zero .yaml files (or directory absent), (c) `load_schema('analysis')` reads from lib/schemas/analysis.schema.yaml.
- `packages/delivery-workflow/tests/test_lib_verify_portability.py`: NEW. Imports lib.verify and lib.contract in isolation, asserts they import without triggering any app.* module load (uses sys.modules introspection: `assert 'app' not in sys.modules` after import).
- `backend/tests/test_pipeline_adapter_rungate_smoke.py`: NEW. End-to-end smoke: instantiate CronosAdapter, build a minimal gate spec with a schema-class check, point at a valid pipeline artifact, assert runGate returns decision='proceed' — confirms the full app.pipeline.gate → lib.verify call chain works.

## Implementation plan

| ID  | Type    | Depends on | Scope files (abridged)                                  | Validation                                                                                                                            |
|-----|---------|------------|---------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| I1  | backend | -          | lib/contract.py, app/pipeline/contract.py (stub), test  | pytest test_pipeline_contract_reexport.py test_pipeline_state_writer.py test_pipeline_normalize.py                                    |
| I2  | backend | -          | lib/schemas/*.yaml (8), delete app/pipeline/schemas/*, test | pytest test_pipeline_schemas_canonical.py                                                                                          |
| I3  | backend | I1, I2     | lib/verify.py, app/pipeline/verify.py (stub), test       | pytest test_pipeline_verify.py test_pipeline_verify_reexport.py test_pipeline_normalize.py test_pipeline_fixtures.py                  |
| I4  | backend | I3         | app/pipeline/gate.py (2-line import flip)               | pytest test_pipeline_gate.py test_pipeline_gate_security.py && grep -n 'from app.pipeline' app/pipeline/gate.py returns nothing       |
| I5  | backend | I3         | tests/test_import_boundary.py (verify), test_lib_verify_portability.py (new) | pytest test_import_boundary.py test_lib_verify_portability.py && lint-imports --config pyproject.toml                |
| I6  | backend | I4         | test_pipeline_adapter_rungate_smoke.py (new)            | pytest test_pipeline_adapter_rungate_smoke.py                                                                                         |

DAG layers (Kahn's algorithm groupings):
- Layer 0: I1, I2 (parallel — both independent)
- Layer 1: I3 (consumes lib.contract from I1 and lib/schemas/ from I2)
- Layer 2: I4, I5 (parallel — both consume I3; I4 = gate import flip, I5 = importlinter + portability test)
- Layer 3: I6 (end-to-end adapter smoke, depends on I4's gate.py)

Requirement → iteration coverage matrix:
- R1 (contract lift + stub) → I1
- R2 (verify lift + stub, SCHEMAS_DIR re-anchored) → I3
- R3 (8 schemas lifted, lib/schemas/ canonical) → I2
- R4 (gate.py lines 25-26 import flip) → I4
- R5 (CronosAdapter.runGate end-to-end through lib.verify) → I6 (adapter.py NOT touched — verified by the smoke test, not by a code change)
- R6 (importlinter no-app-imports passes) → I5
- R7 (all backend callers resolve via stubs) → spans I1, I3 (each iteration's validation re-runs the full caller suite: state_writer, normalize, fixtures, verify, gate)

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Re-export stub omits a verify.py symbol → ImportError at backend startup | high | I3 stub re-exports the full 12-symbol enumerated surface; new test asserts each symbol's identity-equality to lib.verify reference |
| backend/app/pipeline/schemas/ becomes dead-weight or breaks literal-path callers | medium | I2 deletes the 8 backend YAML files in the same diff; I2 test asserts directory empty/absent and verify.SCHEMAS_DIR under lib/ |
| Dual binding of contract constants (CC_VERSION etc.) breaks monkey-patch tests | medium | Stub uses `from lib.contract import *` so single instance; new test asserts `app.pipeline.contract.CC_VERSION is lib.contract.CC_VERSION` |
| Open Q2: gate.py stays in backend/app/pipeline/ → StandaloneAdapter still cannot import gate engine | low | RESOLVED: gate.py stays; R5 acceptance and Out-of-scope explicitly bound this. Documented as a follow-up concern for the StandaloneAdapter build SG |
| lint-imports CLI missing in dev env → I5 false PROCEED | low | I5 also runs test_import_boundary.py (pure-Python AST scanner, zero deps, already in repo) as the authoritative R6 check |
| backend sys.path lacks `packages/delivery-workflow/` → stubs ImportError at startup | high | Pre-check at start of I1: confirm `python -c 'import lib.security'` works from backend/ (precedent already in gate.py:27). If broken, fix sys.path wiring BEFORE writing any stub |

## Assumptions

- **Open Question 1 resolved toward single source of truth.** lib/schemas/ becomes canonical; backend/app/pipeline/schemas/ is deleted outright in I2. Justification: the analysis report's `## Next consumer brief` flags option (a) — re-anchor — as strongly preferred, and dual maintenance is a known anti-pattern that re-emerges with every schema bump.
- **Open Question 2 resolved toward gate.py stays in backend/app/pipeline/.** R5 acceptance criterion explicitly assumes gate.py remains where it is and adapter.py is untouched. Moving gate.py to runner/ or lib/ would expand SG7 scope beyond the analysis-report `Out of scope` boundary and is correctly deferred to the StandaloneAdapter build SG.
- **`lib` is already on sys.path for backend.** Confirmed by `gate.py:27` (`from lib.security import evaluate_security`) which has been working in production since SG2; the new `from lib.verify import ...` and `from lib.contract import ...` paths use the same mechanism.
- **The single internal `from app.pipeline.normalize import normalize` inside verify.py:1350 is an acceptable residual.** It is a deferred import inside a CLI-only `--normalize` branch and does not breach importlinter (the rule's source_modules are lib/runner, and that line lives in lib/verify.py after the lift — but the call is gated behind argparse so static analysis tolerates the lazy import). If importlinter complains, a follow-up SG can lift normalize.py too; for SG7 we accept this single residual and document it in the I3 impl-report. **If importlinter fails on this line at I5, implementor must escalate (status=blocked) rather than silently rewriting normalize.py outside scope.**
- **has_ui=false propagates.** No frontend iterations; no UI surface in scope.
- **backward-compat is non-negotiable.** No test file in `backend/tests/` may have its import paths rewritten by any iteration. The stub is the contract; the implementor's diff must change zero lines in test_pipeline_verify.py, test_pipeline_normalize.py, test_pipeline_state_writer.py, test_pipeline_fixtures.py, test_pipeline_gate.py, or test_pipeline_gate_security.py.

## Open questions

- **Lazy import of normalize from lib/verify.py:1350.** Static-analysis import-linter behavior on a deferred import inside `if args.normalize:` is implementation-dependent. If I5 reports a violation here, the implementor must escalate (status=blocked) — do NOT silently rewrite normalize.py to live in lib/, which would expand SG7 scope. The follow-up StandaloneAdapter build SG is the right place to lift normalize.py.
- **adapters/ source_modules and the import-linter rule.** The actual `.importlinter` file at packages/delivery-workflow/.importlinter lists `source_modules = lib, runner` (NOT adapters), but `pyproject.toml`'s `[[tool.importlinter.contracts]]` block lists only `["lib", "runner"]` as well. If lint-imports reads the `.importlinter` file in preference to pyproject.toml, the existing config is consistent. If both are loaded, the implementor should confirm in I5 which one wins.

## Next consumer brief

Implementors: read `iterations[].scope_files` and `iterations[].validation_command` from the YAML — those are your hard boundaries and pass criteria. Cross-iteration invariants not derivable from YAML:

1. **The 12-symbol enumerated re-export surface for lib.verify is binding** (Risk #1). I3's stub MUST re-export exactly: `CLASS_CONFIG, EXIT_PROCEED, EXIT_FAIL, EXIT_ESCALATE, EXIT_RETRY, VerifyResult, canonical_artifact_relpath, verify, split_frontmatter, PER_CLASS_REQUIRED_SECTIONS, main, SCHEMAS_DIR`. The grep evidence is in `## Components` (Backend → backend/app/pipeline/verify.py bullet).
2. **`from lib.contract import *` for the contract stub is intentional** — the dual-binding risk (Risk #3) requires that there be a single instance of CC_VERSION et al. in the process; identity check is the test.
3. **adapter.py is untouched.** Any iteration that modifies `packages/delivery-workflow/adapters/cronos/adapter.py` violates R5 acceptance and Out-of-scope. The smoke test at I6 confirms the adapter still works via gate.py's internal route to lib.verify.
4. **Open Question 1 RESOLVED:** delete backend/app/pipeline/schemas/*.yaml in I2 (do not keep dual copies).
5. **Open Question 2 RESOLVED:** gate.py stays in backend/app/pipeline/; do not move it.
6. **Unresolved open question (lazy import at verify.py:1350):** if importlinter fails on this in I5, ESCALATE (status=blocked). Do NOT lift normalize.py to fix it — that expands scope beyond SG7's analysis-report boundary.
7. **Pre-check before I1:** confirm `cd /data/spaces/cronos-development/backend && python -c 'import lib.security'` succeeds. If not, fix sys.path wiring BEFORE writing any stub (Risk #6).

```delivery_status
status: done
produces: pipeline-design-report
artifact_paths:
  - .cronos/pipeline/sg7-standalone-rungate-portability-defer/design-report-sg7-standalone-rungate-portability-defer.md
fields:
  iterations_planned: 6
  layer_count: 4
  open_questions_resolved: 2
  risks_total: 6
  risks_high: 2
  risks_critical_unmitigated: 0
open_questions:
  - "If importlinter flags the lazy `from app.pipeline.normalize import normalize` at lib/verify.py:1350, escalate — do not silently lift normalize.py."
```
