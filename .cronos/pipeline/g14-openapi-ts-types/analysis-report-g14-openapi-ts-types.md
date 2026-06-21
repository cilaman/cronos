---
cc_version: '1.0'
agent: pipeline-analyst
slug: g14-openapi-ts-types
phase: analysis
status: done
confidence: 0.87
inputs_used:
- memory:project-remediation-board-setup
- memory:project-g02-ci-pipeline-impl
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- .claude/agents/pipeline-analyst.md
- frontend/src/types.ts
outputs_produced:
- .cronos/pipeline/g14-openapi-ts-types/analysis-report-g14-openapi-ts-types.md
blockers: []
next_consumer: design
request: 'G14: OpenAPI→TS type generation (kill types.ts drift). Replace the hand-maintained
  frontend/src/types.ts mirror of backend Pydantic models with auto-generated types
  from the FastAPI OpenAPI schema. After: TS types are generated via openapi-typescript
  (or equivalent) as a build/CI step; the generation script runs in CI (G02 prerequisite)
  and fails on schema drift; the hand-written mirror is removed; type drift becomes
  impossible. This sprint types.ts changed +42 lines manually tracking backend changes
  — the drift risk is real and grows with every new Pydantic model.'
has_ui: false
coverage_summary:
  searched:
  - frontend/src/types.ts (all exports, 694 LOC)
  - frontend/src/ (grep: all files importing from types.ts — 35+ consumers)
  - .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
    (G14 findings)
  - .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md (§G14
    acceptance criteria)
  excluded:
  - backend/app/main.py: FastAPI auto-generates /openapi.json by default; confirmed
      by CLAUDE.md architecture notes and scout
  - frontend/src/api.ts: consumer of types.ts, not a definition site; scope captured
      via import grep
  - node_modules/: build artifacts
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
  - glob_structural
traceability:
- requirement_id: R1
  statement: The backend FastAPI /openapi.json endpoint returns a valid OpenAPI 3.x
    schema that includes component schemas for all API models currently hand-mirrored
    in types.ts.
  acceptance_criteria:
  - GET /openapi.json returns HTTP 200 with Content-Type application/json on a running
    backend instance.
  - The schema includes components.schemas entries covering Task, TaskSummary, Feature,
    Space, Harness, Plugin, and related models present in types.ts.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: openapi-typescript (or equivalent) is added as a devDependency in frontend/package.json
    with a generate:types npm script that reads the OpenAPI schema and writes a TypeScript
    types file.
  acceptance_criteria:
  - npm ci completes without errors after adding the dependency.
  - package.json contains a generate:types script entry invoking openapi-typescript
    (or equivalent) against the backend OpenAPI schema source.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R3
  statement: Running npm run generate:types produces a committed TypeScript types
    file at a canonical path (e.g., frontend/src/generated/api-types.ts) that exports
    types for all schemas in the OpenAPI spec.
  acceptance_criteria:
  - The generated file exists at the canonical path and is tracked in git (not gitignored).
  - The generated file covers all schemas present in the /openapi.json response, with
    no API model omitted.
  - Re-running generate:types is idempotent when the backend schema is unchanged (git
    diff shows no changes).
  verifying_phase: test
  confidence: 0.85
- requirement_id: R4
  statement: frontend/src/types.ts is refactored to remove all API-mirroring type
    definitions that are now covered by the generated file, retaining only UI-specific
    code that cannot be derived from the OpenAPI schema.
  acceptance_criteria:
  - No type definition in types.ts duplicates a schema definition present in the generated
    file.
  - 'Retained UI-specific exports remain accessible: LANES, FEATURE_LANES, canUserTransition,
    canFeatureTransition, AGENT_MODES, AGENT_MODELS, PRESET_SPACE_COLORS, PRESET_SPACE_ICONS,
    NodeType, Position, and other non-schema constants/functions.'
  - tsc --noEmit passes after the split.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R5
  statement: 'All frontend source files (≥35 currently importing from types.ts) are
    updated so each import references the correct source: generated API types from
    the generated file; UI constants and functions from types.ts (or its successor).'
  acceptance_criteria:
  - tsc --noEmit passes with zero errors after the import path migration.
  - vitest run passes with all existing tests green after the migration.
  - No import still references an API-mirroring type that was removed from types.ts.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R6
  statement: A CI drift-check step in .github/workflows/ci.yml regenerates the TypeScript
    types file and fails the build if the committed generated file diverges from the
    live backend schema.
  acceptance_criteria:
  - The CI frontend job includes a step that runs generate:types then verifies no
    git diff on the generated file (or equivalent schema-comparison approach).
  - A deliberate manual edit to the generated file causes the CI check to fail.
  - The drift check passes on main after a successful G14 implementation.
  verifying_phase: review
  confidence: 0.8
- requirement_id: R7
  statement: TypeScript strict-mode compilation and the production frontend build
    both succeed with zero new errors after the migration.
  acceptance_criteria:
  - tsc --noEmit (strict mode) passes with no new errors compared to pre-G14 baseline.
  - npm run build (Vite production build) completes without errors.
  - No @ts-ignore comments or any casts introduced to paper over type gaps from the
    migration.
  verifying_phase: test
  confidence: 0.9
metrics:
  tool_calls: 11
  files_read: 4
  memory_hits: 2
---

## Summary

G14 replaces the 694-LOC hand-maintained `frontend/src/types.ts` — which manually mirrors backend Pydantic models and drifted +42 lines this sprint — with auto-generated TypeScript types derived from the FastAPI OpenAPI schema. The core work is: add `openapi-typescript` tooling, generate and commit a canonical types file, split `types.ts` to retain only UI-specific constants/functions, update 35+ import sites, and wire a CI drift check (into the existing CI workflow shipped by G02). The design agent must choose between generating from a live backend URL (requires backend startup in CI) vs from a committed `openapi.json` snapshot (simpler CI integration); this is the primary architectural decision. Backend work is minimal — `/openapi.json` is already auto-generated by FastAPI and requires no changes. has_ui is false: no user-visible screens change.

## Scope

### In scope
- Adding `openapi-typescript` (or equivalent) as a devDependency in `frontend/package.json`
- Defining a `generate:types` npm script that produces `frontend/src/generated/api-types.ts` (or canonical path TBD by design)
- Refactoring `frontend/src/types.ts` to remove API-mirroring definitions now covered by the generated file
- Updating all ≥35 frontend source files to import from the correct module post-split
- Adding a CI drift check to `.github/workflows/ci.yml` (G02 CI workflow already exists per memory)
- Confirming the `/openapi.json` endpoint covers all needed schemas (verify-only; no backend code changes expected)

### Out of scope
- Backend Pydantic model changes (G14 consumes the schema as-is; model additions are separate features)
- Changing the FastAPI OpenAPI configuration (title, version, tags) beyond what's needed for schema completeness
- Generating API client code (fetch functions, mocks) — only TypeScript type definitions
- Removing runtime transition logic from `types.ts` (USER_TRANSITIONS_SET etc.) — those are UI-correct business logic, not schema drift

### Deferred
- Migrating to a TypeScript-first API client (e.g., `orval`, `openapi-fetch`) that also generates typed fetch functions — a larger refactor; G14 is types-only
- Resolving naming-convention mismatches between OpenAPI snake_case and TypeScript camelCase — generated file uses the same names as the schema; renaming is future polish
- Removing history of the hand-written `types.ts` via `git filter-repo` — not needed for G14's goal

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Backend /openapi.json returns complete schema covering all API models |
| R2 | openapi-typescript added to devDependencies with generate:types script |
| R3 | generate:types produces a committed, idempotent canonical generated file |
| R4 | types.ts refactored to remove API-mirroring definitions, retaining UI-only code |
| R5 | All 35+ import sites updated; tsc and vitest pass after migration |
| R6 | CI drift check fails the build when generated file diverges from live schema |
| R7 | TypeScript strict-mode build and production build pass with zero new errors |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). Compact summary:

- R1 — `GET /openapi.json` returns 200 with `components.schemas` covering Task, Feature, Space, Harness, Plugin families
- R2 — `npm ci` succeeds; `generate:types` script present in package.json
- R3 — Generated file committed at canonical path; idempotent on re-run; covers all schemas
- R4 — No duplicated API types in `types.ts`; UI constants retained; `tsc --noEmit` passes
- R5 — `tsc --noEmit` zero errors; `vitest run` all green; no stale imports to removed types
- R6 — CI step exists; deliberate edit to generated file fails CI; check passes on clean main
- R7 — `tsc --noEmit` strict passes; `npm run build` succeeds; no new `@ts-ignore` or `any`

## Traceability

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Backend /openapi.json returns complete schema covering all API models |
| R2 | test | openapi-typescript added to devDependencies with generate:types script |
| R3 | test | generate:types produces a committed, idempotent canonical generated file |
| R4 | test | types.ts refactored to remove API-mirroring definitions, retaining UI-only code |
| R5 | test | All 35+ import sites updated; tsc and vitest pass after migration |
| R6 | review | CI drift check fails the build when generated file diverges from live schema |
| R7 | test | TypeScript strict-mode build and production build pass with zero new errors |

## Assumptions

- **FastAPI auto-generates /openapi.json**: FastAPI 0.115+ auto-registers this endpoint; no backend code changes are needed to enable it. Confidence 0.95 — CLAUDE.md confirms FastAPI + CLAUDE.md architecture table lists it.
- **G02 CI workflow already shipped**: memory:project-g02-ci-pipeline-impl confirms `.github/workflows/ci.yml` was implemented with backend + frontend jobs (commit 3a086d0). G14's R6 adds a step to the existing frontend job rather than creating a new workflow.
- **types.ts split is feasible without circular imports**: The UI-specific exports (LANES, canUserTransition, etc.) do not transitively depend on API-schema types in a way that prevents clean separation. This was assessed from the top 80 LOC of types.ts; design agent should verify the full 694 LOC before committing to a file layout.
- **openapi-typescript v6+ is the appropriate tool**: It is the most widely adopted, actively maintained TypeScript code generation tool for OpenAPI 3.x. The design agent may choose an alternative (e.g., `swagger-typescript-api`, `@openapi-codegen/typescript-fetch`) if it better fits the project's constraints — this is left as a design decision.
- **CI drift check implementation**: The most common approach (generate + `git diff --exit-code`) requires the backend to be reachable from CI to call `/openapi.json`. If the backend is not started in CI, the alternative is to commit an `openapi.json` snapshot and generate from that; a separate step verifies the snapshot matches the live server. The design agent must choose.
- **has_ui = false**: G14 is a developer toolchain change (type generation, import migration). No user-facing screens, forms, or visual state change. Functionality is identical pre- and post-migration; only the type-check mechanism changes.
- **Confidence capped at 0.87**: Remediation plan rates G14 confidence as "Med-High" due to tooling choice and integration validation. The lower bound on CI drift check implementation (R6, 0.80) pulls overall confidence below 0.90.

## Open questions

- None — all questions are design decisions properly owned by the architect/design agent.

## Next consumer brief

**Design agent**: read `traceability[]` for the 7 requirements, then focus on these decisions:

1. **Tool selection** (R2–R3): Choose between `openapi-typescript` v6 (CLI-based, widely used) and alternatives. Key evaluation: does the chosen tool produce named exports or `components['schemas']['X']` accessor types? Named exports are easier for consumers to migrate to.

2. **Generated file path** (R3): Propose the canonical output path (e.g., `frontend/src/generated/api-types.ts`) and whether the directory is gitignored (generated at build time only) or committed. Committing is simpler for CI drift checks; gitignoring requires all CI steps to run generation first.

3. **CI drift check approach** (R6): Choose between (a) start backend in CI + generate from live URL, or (b) commit `openapi.json` snapshot + generate from file + add a snapshot-freshness check. Option (b) is simpler but adds a second source of truth.

4. **types.ts split layout** (R4): Read the full 694-LOC `types.ts` to map every export to either API-derived or UI-only. Confirm that `LANES`, `FEATURE_LANES`, `canUserTransition`, `canFeatureTransition`, `AGENT_MODES`, `AGENT_MODELS`, `NodeType`, `Position`, `PRESET_SPACE_COLORS`, `PRESET_SPACE_ICONS` are the complete UI-only set before designing the split.

5. **Migration strategy for 35+ import sites** (R5): All files importing from `types.ts` need updating. Most will split their import between the generated file and the retained `types.ts`. A codemods-style approach (sed/ts-morph) or a re-export shim (temporary `types.ts` re-exports everything from both sources) may reduce risk; both are design decisions.

Scope is frontend-heavy; backend touch is verify-only for R1. No blockers.
