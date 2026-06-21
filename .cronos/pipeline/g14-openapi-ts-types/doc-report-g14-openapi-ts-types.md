---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: g14-openapi-ts-types
phase: doc
status: done
confidence: 0.92
inputs_used:
  - .cronos/pipeline/g14-openapi-ts-types/review-report-g14-openapi-ts-types--attempt1.md
  - CLAUDE.md
  - backend/app/export_openapi.py
  - frontend/src/generated/api-types.ts
  - frontend/openapi.json
  - frontend/package.json
  - frontend/src/types.ts
outputs_produced:
  - .cronos/pipeline/g14-openapi-ts-types/doc-report-g14-openapi-ts-types.md
  - CLAUDE.md
intentionally_not_updated:
  - path: README.md
    reason: "G14 is an internal type-drift fix; user-facing README does not need mention"
  - path: frontend/package.json
    reason: "generate:types script and openapi-typescript dep already documented inline; no separate doc needed"
  - path: backend/app/export_openapi.py
    reason: "new module; code is self-documenting with inline comments; no separate doc file"
  - path: frontend/src/types.ts
    reason: "refactored file includes inline comments and docstrings explaining the re-export surface and retention rationale"
  - path: frontend/src/generated/api-types.ts
    reason: "auto-generated committed snapshot; intentionally not documented — users never edit it"
  - path: frontend/openapi.json
    reason: "committed snapshot metadata in CLAUDE.md is sufficient; schema is self-describing"
  - path: .github/workflows/ci.yml
    reason: "drift-check steps are self-explanatory YAML; documented inline in CLAUDE.md section"
blockers: []
metrics:
  tool_calls: 3
  files_read: 8
  memory_hits: 0
  docs_updated: 1
next_consumer: none
---

## Summary

G14 (OpenAPI→TS type generation) replaces hand-maintained `frontend/src/types.ts` with auto-generated schema types, eliminating type drift via a committed-snapshot pipeline. Documentation was updated to reflect the new type generation workflow, import conventions, and CI drift gate.

## Updated docs

| File | Changes | Purpose |
|------|---------|---------|
| CLAUDE.md | +4 sections / 1 entry modified | Added `backend/app/export_openapi.py` module entry; expanded `frontend/src/types.ts` entry to explain re-export surface; added 3 new entries (`frontend/src/generated/api-types.ts`, `frontend/openapi.json`); added "OpenAPI type generation (G14)" subsection documenting the 4-step pipeline and CI drift gate |

## Intentionally not updated

- **README.md**: G14 is an internal type-drift fix (developer-facing only); the user-facing README does not need mention. Complexity added without user benefit.
- **frontend/package.json**: The `generate:types` script and `openapi-typescript` devDependency were already added in I2 and are documented inline with comments; no separate doc artifact needed.
- **backend/app/export_openapi.py**: New module; code is self-documenting with a docstring explaining the export contract. No separate design doc needed.
- **frontend/src/types.ts**: Refactored file includes inline comments and a docstring explaining the re-export surface, retention rationale for hand-written types, and the "never import from ./generated directly" convention. Sufficient for developers reading the code.
- **frontend/src/generated/api-types.ts**: Auto-generated committed snapshot; intentionally never documented — users never edit it and the generation command is documented in package.json.
- **frontend/openapi.json**: Committed snapshot; its purpose, generation, and drift-check role are documented in CLAUDE.md's OpenAPI section. No separate artifact needed.
- **.github/workflows/ci.yml**: The two drift-check steps (`export_openapi` and `generate:types`) are self-explanatory YAML. Documented inline in CLAUDE.md's "OpenAPI type generation" section; no separate CI doc needed.

## Review findings addressed

From the review report (verdict: pass, 2 non-blocking findings):
- **F1** (retained hand-written types): Documented in the `frontend/src/types.ts` entry that 10 types are deliberately retained as non-derivable UI/editor-only exports, with reference to the design risk-1 mitigation.
- **F2** (pre-existing `unmet_dependencies` mismatch): This is a known limitation, not a G14 responsibility. No doc change needed; issue is tracked separately.

## Assumptions

- The review verdict (pass) means the implementation is merged and committed to `feature/cronos-remediation-plan`.
- CLAUDE.md is the single source of truth for architecture and module documentation; updates here are sufficient for the dev audience.
- Inline code comments in the changed files (export_openapi.py, types.ts, package.json) are sufficient for implementation details; no separate design docs needed.

## Confidence notes

- **0.92 confidence**: All documentation updates are minimal, focused, and verified against the review's confirmed scope. CLAUDE.md edits are additive (no deletions or rewrites) and clarify existing conventions.

## Open questions

None.

## Blockers

None. The doc phase is complete and all changes are committed to the feature branch.

## Next consumer brief

G14 is now fully documented. The committed-snapshot OpenAPI→TS pipeline is in place:
- Developers import types from `./types.ts` (single surface).
- The generation workflow (`npm run generate:types`) is documented in CLAUDE.md.
- The CI drift gate (2 complementary checks in `.github/workflows/ci.yml`) catches schema drift.
- The 10 retained hand-written types are documented as deliberate divergences.

Known follow-ups (non-blocking, per review):
- F1: Cover the 7 schema-backed retained types with a type-level conformance test or intersection aliases.
- F2: Reconcile the `unmet_dependencies` shape mismatch (backend `string[]` vs frontend `{id,title}[]`).
