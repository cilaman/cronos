---
cc_version: "1.0"
agent: pipeline-implementor
slug: g14-openapi-ts-types--i3
phase: impl
status: done
confidence: 0.93
inputs_used:
  - .cronos/pipeline/g14-openapi-ts-types/design-report-g14-openapi-ts-types.md
  - .cronos/pipeline/g14-openapi-ts-types/impl-report-g14-openapi-ts-types--i2.md
  - frontend/src/types.ts
  - frontend/src/generated/api-types.ts
iteration_id: I3
files_changed:
  - frontend/src/types.ts
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/g14-openapi-ts-types/impl-report-g14-openapi-ts-types--i3.md
blockers: []
next_consumer: I4
metrics:
  tool_calls: 18
  files_read: 12
  memory_hits: 0
  diff_lines_added: 98
  diff_lines_removed: 75
---

## Summary

I3 rewrites `frontend/src/types.ts` to use generated-schema aliases where shapes are fully compatible, while retaining hand-written definitions for types whose shape diverges from the backend schema in ways that would break consuming code outside the scope_files.

22 types are aliased from `components['schemas'][X]` in `./generated/api-types`:
- State enums: `TaskState`, `FeatureState`, `MemoryKind`
- Harness primitives: `NodeType`, `Position`, `NodeRef`, `RoutedTo`
- Activity/trace: `Activity`, `ToolCallTrace`, `AssistantTurnTrace`
- Plugin types (5): `PluginComponent`, `PluginEntry`, `MarketplacePluginEntry`, `MarketplaceEntry`, `PluginsResponse`
- Tool adoption: `AdoptionManifest`
- Test reporting: `TestCase`, `TestSuite`, `TestReportSummary`, `TestReport`
- Name-mapped: `AdoptedTool` = `AdoptedToolEntry`, `TaskFile` = `FileEntry`

10 types are retained as hand-written due to shape divergence:
- `TaskSummary` — unmet_dependencies shape diverges (backend `list[str]` vs frontend `{id,title}[]`)
- `Task` — same unmet_dependencies issue + parent_title/realized_by/realized_by_count not in schema
- `GlobalStats` — tool_use_summary/exit_reason_counts optional in schema, consumers use without `?.`
- `TaskStats` — runs optional and avg_memory_hit_rate required in schema; consumers depend on opposite
- `RunTrace` — turns/tool_calls/unique_tools optional in schema; TracePanel.tsx accesses without `?.`
- `MemoryItem` — sources required; MemoryPage.tsx accesses without `?.`
- `HarnessNode` — ports/data optional in schema; harness editor accesses without `?.`
- `AiToolEntry` — scope is narrower union `"space"|"global"|"plugin"` for ScopeBadge type safety
- `HookEntry`, `PermissionEntry` — scope narrower union

## Validation

Validation command: `cd frontend && npx tsc --noEmit && npm run build && npm test`
- `npx tsc --noEmit` → exit 0 (no errors)
- `npm run build` → exit 0 (Vite build successful, 1187 modules)
- `npm test` → exit 0 (1289 tests pass, 80 test files)

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/types.ts | modified | +98 / -75 | alias 22 compatible types from generated schema; retain 10 hand-written |

## Out-of-scope findings

- None.

## Assumptions

- The 22 aliased types have been verified for shape compatibility: all required fields map correctly, no optionality mismatches in paths accessed by consumers.
- `TaskFile` = `FileEntry` is safe — `FileEntry.category` is `string` in schema; consumers cast to `FileCategory` union where needed via separate runtime checks.
- `AdoptedTool` = `AdoptedToolEntry` — the legacy name is preserved via alias for all 97 import sites.
- Consumer files (outside scope_files) were not modified — all shape divergences were handled by retaining hand-written definitions.

## Open questions

- None.

## Next consumer brief

I4 adds drift-detection steps to `.github/workflows/ci.yml`:
- Backend job: run `python -m app.export_openapi && git diff --exit-code frontend/openapi.json`
- Frontend job: run `npm run generate:types && git diff --exit-code src/generated/api-types.ts`
Both checks fail CI if the committed snapshot diverges from what the live backend produces.
