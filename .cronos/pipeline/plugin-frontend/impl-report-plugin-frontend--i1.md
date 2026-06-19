---
cc_version: '1.0'
agent: pipeline-implementor
slug: plugin-frontend--i1
phase: impl
iteration_id: I1
status: done
confidence: 0.97
inputs_used:
- .cronos/pipeline/plugin-frontend/design-report-plugin-frontend.md
- .cronos/pipeline/plugin-frontend/analysis-report-plugin-frontend.md
- frontend/src/types.ts
- frontend/src/api.ts
- frontend/src/__tests__/api.spaceFiles.test.ts
- frontend/src/components/ToolDetailPanel.tsx
- frontend/src/pages/SpaceToolsPage.tsx
outputs_produced:
- .cronos/pipeline/plugin-frontend/impl-report-plugin-frontend--i1.md
- frontend/src/types.ts
- frontend/src/api.ts
- frontend/src/__tests__/api.plugins.test.ts
- frontend/src/components/ToolDetailPanel.tsx
- frontend/src/pages/SpaceToolsPage.tsx
blockers: []
next_consumer: review
files_changed:
- frontend/src/types.ts
- frontend/src/api.ts
- frontend/src/__tests__/api.plugins.test.ts
- frontend/src/components/ToolDetailPanel.tsx
- frontend/src/pages/SpaceToolsPage.tsx
validation_command: cd frontend && npm test && npm run build
validation_command_passed: true
metrics:
  tool_calls: 22
  files_read: 7
  memory_hits: 0
  diff_lines_added: 125
  diff_lines_removed: 2
---

## Summary

Implements I1 from the design DAG: adds 5 TypeScript plugin interfaces to `types.ts`, extends `AiToolEntry.scope` from `"space" | "global"` to `"space" | "global" | "plugin"`, and adds 7 plugin API client functions to `api.ts`. Writes 18 tests in `src/__tests__/api.plugins.test.ts` asserting correct HTTP method, path, and body for each function. Also fixes two downstream TypeScript errors in `ToolDetailPanel.tsx` and `SpaceToolsPage.tsx` where the narrowed `ScopeBadge` prop type `"space" | "global"` was incompatible with the widened `AiToolEntry.scope` union — updated both `ScopeBadge` declarations to `"space" | "global" | "plugin"`.

Full test suite: 1243 passed (77 files). Build: tsc + vite both clean.

## Files changed

| File | Change |
|------|--------|
| `frontend/src/types.ts` | Added `PluginComponent`, `PluginEntry`, `MarketplacePluginEntry`, `MarketplaceEntry`, `PluginsResponse` interfaces; extended `AiToolEntry.scope` to include `"plugin"` |
| `frontend/src/api.ts` | Added `PluginsResponse` to import list; added 7 plugin functions in `// --- plugins ---` section: `plugins`, `installPlugin`, `uninstallPlugin`, `enablePlugin`, `disablePlugin`, `addMarketplace`, `removeMarketplace` |
| `frontend/src/__tests__/api.plugins.test.ts` | NEW: 18 tests asserting method, path, body, and return type for each of the 7 API functions |
| `frontend/src/components/ToolDetailPanel.tsx` | Widened `ScopeBadge` prop type to include `"plugin"` to match `AiToolEntry.scope` |
| `frontend/src/pages/SpaceToolsPage.tsx` | Widened `ScopeBadge` prop type to include `"plugin"` to match `AiToolEntry.scope` |

## Out-of-scope findings

- `ToolDetailPanel.tsx` and `SpaceToolsPage.tsx` each have a local `ScopeBadge` with `scope: "space" | "global"` that caused TypeScript errors once `AiToolEntry.scope` was widened. These are 1-line prop-type fixes necessary to keep the build green — not feature changes, minimal blast radius.

## Assumptions

- `PluginsResponse` is the correct return type for all 6 mutation functions (confirmed by backend `api/plugins.py` `response_model=PluginsResponse` on all 7 endpoints).
- `installPlugin` defaults `scope = "user"` matching the backend `InstallRequest` Pydantic default.
- `removeMarketplace(name)` uses `DELETE /api/plugins/marketplaces/{name}` with URL-encoded name and no request body.

## Open questions

None.

## Next consumer brief

I2 (hooks/usePlugins.ts) and I5 (VariableInspector datalist) can proceed in parallel — both depend on I1 only. I3 (PluginsPanel) depends on I1 + I2. I4 (SpaceToolsPage tab) depends on I3.

Key invariants from I1:
- Query key `['plugins']` must be used exactly (literal array, no variables) in I2's `usePlugins` and all 6 mutation `onSuccess` handlers.
- All 7 `api.*Plugin` / `api.*Marketplace` paths match the backend exactly; do not invent aliases.
- `AiToolEntry.scope` now includes `"plugin"` — consumers downstream of I5 that render scope badges must handle this third value.
