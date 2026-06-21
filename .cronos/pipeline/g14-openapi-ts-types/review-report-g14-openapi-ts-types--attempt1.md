---
cc_version: "1.0"
agent: pipeline-reviewer
slug: g14-openapi-ts-types--attempt1
phase: review
status: done
confidence: 0.85
inputs_used:
  - memory:pipeline-reviewer-agent
  - memory:pipeline-narrow-k-coverage
  - .cronos/pipeline/g14-openapi-ts-types/design-report-g14-openapi-ts-types.md
  - .cronos/pipeline/g14-openapi-ts-types/impl-report-g14-openapi-ts-types--i1.md
  - .cronos/pipeline/g14-openapi-ts-types/impl-report-g14-openapi-ts-types--i2.md
  - .cronos/pipeline/g14-openapi-ts-types/impl-report-g14-openapi-ts-types--i3.md
  - .cronos/pipeline/g14-openapi-ts-types/impl-report-g14-openapi-ts-types--i4.md
  - .cronos/pipeline/g14-openapi-ts-types/pipeline-state.json
  - backend/app/export_openapi.py
  - .github/workflows/ci.yml
  - frontend/src/types.ts
  - frontend/package.json
  - frontend/openapi.json
  - backend/app/models.py
  - frontend/src/components/Card.tsx
outputs_produced:
  - .cronos/pipeline/g14-openapi-ts-types/review-report-g14-openapi-ts-types--attempt1.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 14
  files_read: 14
  memory_hits: 2
  diff_lines_reviewed: 520
verdict: pass
attempt: 1
findings:
  - id: F1
    severity: medium
    file: frontend/src/types.ts:160
    evidence: "10 types retained hand-written (Task, TaskSummary, GlobalStats, TaskStats, RunTrace, MemoryItem, HarnessNode, AiToolEntry, HookEntry, PermissionEntry). 7 ARE backed by OpenAPI component schemas but kept hand-written for optionality/shape divergence. The CI drift gate (I4) only diffs openapi.json + generated/api-types.ts, so these hand-written types can still drift silently — the goal's 'type drift becomes impossible' is only partially met."
    blocking: false
    suggested_action: "Track a follow-up to re-derive the 7 schema-backed retained types via intersection aliases (e.g. `export type TaskStats = Omit<components['schemas']['TaskStats'], 'runs'> & { runs: RunTrace[] }`) or add a type-level conformance test, so they too are covered by the drift gate."
  - id: F2
    severity: medium
    file: frontend/src/components/Card.tsx:353
    evidence: "Backend TaskSummary/TaskRead.unmet_dependencies is `string[]` (openapi.json), but the retained frontend type declares `Array<{id,title}>` and Card.tsx:353/644 renders `blockedBy.map((d) => d.title)`. G14 surfaced a real backend↔frontend contract mismatch: the tooltip likely renders `undefined` at runtime. Pre-existing; out of G14 scope (design excluded Pydantic-model changes)."
    blocking: false
    suggested_action: "File a follow-up to reconcile unmet_dependencies: either enrich the backend TaskSummary response to {id,title} objects (and regenerate the snapshot) or fix Card.tsx to render the string ids. Do not fix in this goal — it is out of the I3 scope_files boundary."
---

## Summary

Scope conformance: **yes** — the observed changed set (export_openapi.py, test_export_openapi.py, package.json, package-lock.json, openapi.json, generated/api-types.ts, types.ts, ci.yml) is a subset of the design `iterations[].scope_files` union; no scope escape. **Verdict: pass** — the implementation faithfully executes the gate-approved committed-snapshot re-export shim design: the `./generated/api-types` import surface is consumed only through `types.ts` (verified: no other file imports it), the CI drift gate is present in both jobs, and the export script is import-side-effect-safe. No test report was supplied (only analysis/design/implementation phases recorded), so the review judged code statically and relied on each impl report's `validation_command_passed: true` (I3 reports full `tsc -b` + build + 1289 vitest green). The two findings are medium, non-blocking residual-risk items for follow-up, not regressions.

## Findings

- **F1** (medium, non-blocking) — `frontend/src/types.ts:160`: 7 schema-backed types retained hand-written and excluded from the drift gate; goal acceptance criterion "drift impossible" only partially met. Conformant with the gate-approved design risk-1 mitigation (retain on shape divergence), hence non-blocking.
- **F2** (medium, non-blocking) — `frontend/src/components/Card.tsx:353`: G14 surfaced a pre-existing backend↔frontend `unmet_dependencies` shape mismatch (`string[]` vs `{id,title}[]`). Out of G14 scope; the implementor correctly retained the hand-written type rather than break consumers.

## Verdict

pass. The diff conforms to the design scope with no escapes, the drift gate and generation pipeline are correctly wired, and the retained hand-written types are a documented, design-sanctioned exception; the two findings are non-blocking follow-ups.

## Assumptions

- No test-report artifact exists (`test-report-g14-openapi-ts-types.md` absent; pipeline-state records only analysis/design/implementation). Per the reviewer contract, absence alone does not downgrade the verdict — and the one new executable module (`export_openapi.py`) ships its own 8-test file (I1), while I3's refactor was validated against the full existing suite. Review judged code only, not a re-run validation outcome.
- Scope contract taken from design `iterations[].scope_files[]` union (I1–I4).
- The retention rationales for the 10 hand-written types were spot-verified against `openapi.json` (e.g. `GlobalStats.required: []`, `TaskSummary.unmet_dependencies: string[]`) and are genuine optionality/shape divergences, not work-avoidance.
- The diff was reviewed against `feature/cronos-remediation-plan` (where the G14 changes live); this review worktree is branched from `main` and does not itself carry the changes.

## Open questions

- None.

## Next consumer brief

For doc-sync: G14 ships OpenAPI→TS type generation. User-/dev-visible changes: (1) `backend/app/export_openapi.py` dumps the live FastAPI schema to the committed `frontend/openapi.json`; (2) `npm run generate:types` regenerates `frontend/src/generated/api-types.ts` via `openapi-typescript`; (3) `frontend/src/types.ts` now re-exports 22 backend types as aliases of generated schemas while retaining 10 documented UI/divergent types — all 97 consumers still import from `./types` unchanged; (4) CI now fails on schema drift via two checks (backend diffs `openapi.json`, frontend diffs the generated file). Document the `generate:types` workflow and the "never import from `./generated` directly" convention. Note the two open follow-ups (F1: cover retained schema-backed types; F2: reconcile `unmet_dependencies` shape) as known limitations, not part of this delivery.
