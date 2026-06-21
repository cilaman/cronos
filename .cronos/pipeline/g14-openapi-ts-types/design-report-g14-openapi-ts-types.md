---
cc_version: '1.0'
agent: pipeline-architect
slug: g14-openapi-ts-types
phase: design
status: done
confidence: 0.83
inputs_used:
- memory:project-remediation-board-setup
- memory:project-g02-ci-pipeline-impl
- memory:pipeline-architect-canonical-path
- .cronos/pipeline/g14-openapi-ts-types/analysis-report-g14-openapi-ts-types.md
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- frontend/src/types.ts
- frontend/package.json
- .github/workflows/ci.yml
outputs_produced:
- .cronos/pipeline/g14-openapi-ts-types/design-report-g14-openapi-ts-types.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/types.ts
  - frontend/package.json
  - .github/workflows/ci.yml
  - backend/app/main.py
  - frontend/src/ (import-site grep — 97 consumers)
  excluded:
  - 'backend/app/models.py: G14 consumes the OpenAPI schema as-is; no Pydantic model
    changes in scope'
  - 'node_modules/: build artifacts'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
  - glob_structural
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/export_openapi.py
  - backend/tests/test_export_openapi.py
  validation_command: cd backend && pytest tests/test_export_openapi.py -v
  max_diff_lines: 200
  depends_on: []
- id: I2
  type: infra
  scope_files:
  - frontend/package.json
  - frontend/package-lock.json
  - frontend/openapi.json
  - frontend/src/generated/api-types.ts
  validation_command: cd frontend && npm ci && npm run generate:types && git diff
    --exit-code src/generated/api-types.ts
  max_diff_lines: 600
  depends_on:
  - I1
- id: I3
  type: frontend
  scope_files:
  - frontend/src/types.ts
  validation_command: cd frontend && npx tsc -b && npm run build && npm test
  max_diff_lines: 600
  depends_on:
  - I2
- id: I4
  type: infra
  scope_files:
  - .github/workflows/ci.yml
  validation_command: python -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml'));
    steps=[s for j in d['jobs'].values() for s in j['steps']]; assert any('generate:types'
    in str(s) for s in steps), 'frontend drift step missing'; assert any('export_openapi'
    in str(s) for s in steps), 'backend snapshot step missing'"
  max_diff_lines: 120
  depends_on:
  - I2
risks:
- description: Generated OpenAPI types may not be shape-compatible with the hand-written
    ones consumers expect (field optionality, snake_case names, RunStats literal unions),
    so a permanent re-export shim alias in types.ts could surface tsc errors across
    the 97 import sites.
  severity: high
  mitigation: I3 keeps types.ts as the single import surface and aliases each generated
    schema (export type Task = components['schemas']['Task']); where a generated shape
    diverges, the alias is widened with an intersection or the hand-written type is
    retained as a UI-only export. I3's validation runs the full tsc -b + npm run build
    + npm test across all 97 consumers, so any incompatibility fails the iteration
    rather than reaching review.
- description: Not every frontend type has a backend OpenAPI component schema — OpenAPI
    only emits schemas referenced by a route's request/response model. Types backed
    by plain-dict responses or editor-only structures (NodeType, Position, NodePort,
    harness visual-editor types) have no schema to alias.
  severity: medium
  mitigation: 'I3 classifies each export: alias to components[''schemas''][X] only
    when the generated file contains a matching schema; otherwise retain the hand-written
    definition and document it as non-derivable UI/editor type. The implementor greps
    the generated file for each schema name before aliasing.'
- description: Importing app.main to dump app.openapi() could trigger heavy import-time
    side effects or fail in a bare CI environment, breaking the backend snapshot-export
    step and the R6 drift check.
  severity: medium
  mitigation: I1's export_openapi.py calls only app.openapi() (a pure method; the
    FastAPI lifespan handler does not run on import). I1's pytest asserts the script
    runs and the dumped schema contains the Task/Feature/Space/Harness/Plugin component
    schemas (covers R1), proving import is side-effect-safe before CI depends on it.
- description: CI runs backend (python-only) and frontend (node-only) as separate
    jobs, so a single regenerate-and-diff step cannot see both toolchains; a naive
    frontend-only drift check would miss backend Pydantic-model drift.
  severity: medium
  mitigation: 'I4 splits the drift gate: the backend job re-runs export_openapi and
    git-diffs frontend/openapi.json (catches model drift vs snapshot); the frontend
    job runs generate:types and git-diffs src/generated/api-types.ts (catches generated-file
    drift vs snapshot). The two complementary checks give full drift coverage without
    a heavyweight combined-toolchain job.'
metrics:
  tool_calls: 16
  files_read: 5
  memory_hits: 3
  iterations_planned: 4
---

## Summary

G14 replaces the 694-LOC hand-maintained `frontend/src/types.ts` mirror with
OpenAPI-generated types, killing schema drift. The architecture is a **committed-snapshot
re-export shim**: a backend script dumps `app.openapi()` to a committed
`frontend/openapi.json`, `openapi-typescript` generates a committed
`frontend/src/generated/api-types.ts`, and `types.ts` is rewritten to *alias* each
generated schema (rather than redefine it) while retaining only UI/editor-only exports —
so all 97 import sites keep importing from `./types` unchanged and migration churn
collapses to one file. The DAG is a short chain (I1 schema source → I2 generation) that
fans into two parallel leaves (I3 types.ts refactor, I4 CI drift gate). The primary
tradeoff (high risk) is generated-vs-hand-written shape parity across the 97 consumers,
contained by validating I3 with the full `tsc -b + build + test` suite.

## Components

### Data
- (none) — G14 consumes the OpenAPI schema as-is; no Pydantic model or migration changes.

### Backend
- `backend/app/export_openapi.py`: CLI that writes `app.main.app.openapi()` JSON to a `--out` path (default `frontend/openapi.json`); single source of truth for type generation and the CI snapshot-freshness check.
- `backend/tests/test_export_openapi.py`: asserts the dumped schema is valid OpenAPI 3.x and `components.schemas` covers the Task / Feature / Space / Harness / Plugin families (satisfies R1).

### Frontend
- `frontend/openapi.json`: committed OpenAPI snapshot, regenerated by the backend script; the deterministic node-only input for `generate:types`.
- `frontend/src/generated/api-types.ts`: committed, `openapi-typescript`-generated schema types (`components['schemas'][...]`); never hand-edited.
- `frontend/package.json`: adds `openapi-typescript` devDependency and a `generate:types` script (`openapi-typescript ./openapi.json -o ./src/generated/api-types.ts`).
- `frontend/src/types.ts`: rewritten to re-export aliases of generated schemas and retain only UI/editor-only exports (`LANES`, `FEATURE_LANES`, `canUserTransition`, `canFeatureTransition`, `AGENT_MODES`, `AGENT_MODELS`, `PRESET_SPACE_COLORS`, `PRESET_SPACE_ICONS`, `NodeType`, `Position`, `NodePort`, plus any type with no matching OpenAPI schema).
- `.github/workflows/ci.yml`: backend-job step (export + `git diff --exit-code frontend/openapi.json`) and frontend-job step (`generate:types` + `git diff --exit-code src/generated/api-types.ts`).

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                   | Validation                                                                 |
|-----|----------|------------|----------------------------------------------------------|----------------------------------------------------------------------------|
| I1  | backend  | -          | backend/app/export_openapi.py, backend/tests/…           | cd backend && pytest tests/test_export_openapi.py -v                        |
| I2  | infra    | I1         | frontend/package.json, openapi.json, src/generated/…     | cd frontend && npm ci && npm run generate:types && git diff --exit-code …   |
| I3  | frontend | I2         | frontend/src/types.ts                                     | cd frontend && npx tsc -b && npm run build && npm test                      |
| I4  | infra    | I2         | .github/workflows/ci.yml                                  | python -c "…assert generate:types and export_openapi steps present…"       |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Generated types not shape-compatible with hand-written ones across 97 consumers | high | I3 aliases via `types.ts` single surface; full `tsc -b + build + test` validates every consumer; widen/retain on divergence |
| Some frontend types have no backend OpenAPI schema (editor/dict-response types) | medium | I3 classifies per-export; alias only when generated schema exists, else retain as documented UI/editor type |
| `app.openapi()` import-time side effects break the export script / CI | medium | export script calls only the pure `app.openapi()`; I1 pytest proves it runs and covers the schema families before CI depends on it |
| Split CI jobs (python vs node) can't see both toolchains for one drift check | medium | I4 splits the gate: backend job diffs `openapi.json`, frontend job diffs generated file — complementary full coverage |

## Assumptions

- **FastAPI `/openapi.json` needs no backend changes**: `app = FastAPI(...)` at `backend/app/main.py:578` auto-generates the schema; `app.openapi()` is pure and the `lifespan` handler does not run on import. The export script reuses it; R1 is verify-only.
- **G02 CI workflow exists**: `.github/workflows/ci.yml` ships backend + frontend jobs (memory:project-g02-ci-pipeline-impl). R6 *adds steps* to those existing jobs; no new workflow file.
- **Re-export shim satisfies R4 and R5**: aliasing (`export type Task = components['schemas']['Task']`) is not a duplicate definition (R4 met) and keeps `./types` the correct import source for all consumers (R5 met) — the analyst explicitly endorsed the shim as a risk-reducer.
- **Committed snapshot over live-URL generation**: generating from a committed `openapi.json` keeps `generate:types` a node-only, deterministic step that runs in the existing frontend CI job; backend-model drift is caught separately by the backend-job snapshot-freshness step.
- **`openapi-typescript` is the tool**: most widely adopted OpenAPI 3.x→TS generator; emits `components['schemas']` accessor types the shim aliases cleanly.

## Open questions

- None.

## Next consumer brief

Read `iterations[]`, each `scope_files`, and `validation_command` directly; the body
tables mirror them. Cross-iteration invariants the YAML cannot encode: (1) the snapshot
path string `frontend/openapi.json` and generated path `frontend/src/generated/api-types.ts`
must be used **literally and identically** by I1's `--out` default, I2's `generate:types`
script, and both I4 CI steps — a mismatch silently disables the drift gate. (2) I3 must
keep `frontend/src/types.ts` as the only import surface (re-export aliases), so no
consumer file is edited; if a generated shape genuinely breaks a consumer, widen the
alias inside types.ts rather than editing the consumer. (3) Before aliasing any export,
grep the generated file for the matching schema name — retain hand-written definitions
for editor/dict-response types with no schema (R4 "non-derivable" set). I3 runs after I2;
I3 and I4 are independent parallel leaves.
