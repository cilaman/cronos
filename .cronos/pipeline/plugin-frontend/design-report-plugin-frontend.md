---
cc_version: '1.0'
agent: pipeline-architect
slug: plugin-frontend
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:plugin-management-board-setup
- memory:pipeline-architect-agent
- .cronos/pipeline/plugin-frontend/analysis-report-plugin-frontend.md
- frontend/src/types.ts
- frontend/src/api.ts
- frontend/src/hooks/useHarnesses.ts
- frontend/src/pages/SpaceToolsPage.tsx
- frontend/src/components/harness/VariableInspector.tsx
- frontend/src/pages/HarnessEditor.tsx
- frontend/src/components/DiscoveryPanel.tsx
outputs_produced:
- .cronos/pipeline/plugin-frontend/design-report-plugin-frontend.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/types.ts
  - frontend/src/api.ts
  - frontend/src/hooks/useHarnesses.ts
  - frontend/src/pages/SpaceToolsPage.tsx
  - frontend/src/components/harness/VariableInspector.tsx
  - frontend/src/pages/HarnessEditor.tsx
  - frontend/src/components/DiscoveryPanel.tsx
  - .cronos/pipeline/plugin-frontend/analysis-report-plugin-frontend.md
  excluded:
  - 'backend/app/api/plugins.py: backend delivered upstream; API contract already
    captured in analysis traceability[]'
  - 'backend/app/tools/plugins.py: CLI wrapper, out of frontend slice scope'
  - frontend test files are authored inside each iteration's scope (implementor-owned),
    not pre-read
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: frontend
  title: Types + API client (R1, R2) — pure additive foundation
  scope_files:
  - frontend/src/types.ts
  - frontend/src/api.ts
  - frontend/src/__tests__/api.plugins.test.ts
  validation_command: cd frontend && npx vitest run src/__tests__/api.plugins.test.ts
  max_diff_lines: 300
  depends_on: []
  acceptance_criteria:
  - 'R1: types.ts exports PluginComponent ({ name: string; kind: ''agent'' | ''skill''
    | ''command'' }).'
  - 'R1: types.ts exports PluginEntry (id, name, marketplace?, version?, scope, enabled,
    components: PluginComponent[], installPath?, installedAt?, lastUpdated?) matching
    backend Pydantic defaults (nullable fields optional; enabled boolean).'
  - 'R1: types.ts exports MarketplacePluginEntry (pluginId, name, description: string
    | null, marketplaceName: string | null, source: string | null, installCount: number).'
  - 'R1: types.ts exports MarketplaceEntry ({ name: string; source: string }) and
    PluginsResponse ({ installed: PluginEntry[]; available: MarketplacePluginEntry[];
    marketplaces: MarketplaceEntry[] }).'
  - 'R1: the AiToolEntry.scope union is extended to ''"space" | "global" | "plugin"''.'
  - 'R2: api.ts adds seven functions on the existing `api` object — plugins() → GET
    /api/plugins; installPlugin(pluginId, scope) → POST /api/plugins/install {plugin_id,
    scope}; uninstallPlugin(pluginId) → POST /api/plugins/uninstall; enablePlugin(pluginId)
    → POST /api/plugins/enable; disablePlugin(pluginId) → POST /api/plugins/disable;
    addMarketplace(source) → POST /api/plugins/marketplaces {source}; removeMarketplace(name)
    → DELETE /api/plugins/marketplaces/{name}.'
  - 'R2: plugins() returns Promise<PluginsResponse>; all six mutation functions return
    Promise<PluginsResponse>.'
  - Test src/__tests__/api.plugins.test.ts asserts each of the 7 functions issues
    the correct method + path + body (mock the shared request helper / fetch), following
    the existing src/__tests__/api.spaceFiles.test.ts and api.harness.test.ts patterns.
- id: I2
  type: frontend
  title: usePlugins hooks (R3) — query + 6 mutations with cache invalidation
  scope_files:
  - frontend/src/hooks/usePlugins.ts
  - frontend/src/hooks/__tests__/usePlugins.test.tsx
  validation_command: cd frontend && npx vitest run src/hooks/__tests__/usePlugins.test.tsx
  max_diff_lines: 250
  depends_on:
  - I1
  acceptance_criteria:
  - 'R3: usePlugins() returns useQuery({ queryKey: [''plugins''], queryFn: api.plugins
    }).'
  - 'R3: six mutation hooks exist — useInstallPlugin, useUninstallPlugin, useEnablePlugin,
    useDisablePlugin, useAddMarketplace, useRemoveMarketplace — each wrapping the
    matching api.ts function in useMutation.'
  - 'R3: every mutation calls queryClient.invalidateQueries({ queryKey: [''plugins'']
    }) in onSuccess.'
  - 'R3: file uses named exports and TanStack Query v5 object syntax, mirroring frontend/src/hooks/useHarnesses.ts.'
  - Test src/hooks/__tests__/usePlugins.test.tsx asserts usePlugins issues the query
    and that each mutation invalidates ['plugins'] on success (spy on queryClient.invalidateQueries),
    mirroring src/hooks/__tests__/useHarnesses.test.tsx.
- id: I3
  type: frontend
  title: PluginsPanel component (R4) — Installed / Available / Marketplaces
  scope_files:
  - frontend/src/components/PluginsPanel.tsx
  - frontend/src/components/__tests__/PluginsPanel.test.tsx
  validation_command: cd frontend && npx vitest run src/components/__tests__/PluginsPanel.test.tsx
  max_diff_lines: 600
  depends_on:
  - I1
  - I2
  acceptance_criteria:
  - 'R4: three sections — Installed, Available, Marketplaces — each rendering an empty-state
    message when its list is empty; all data sourced from usePlugins().'
  - 'R4: each installed plugin card has an enable/disable toggle calling useEnablePlugin/useDisablePlugin
    based on entry.enabled.'
  - 'R4: uninstall is gated by a window.confirm() (or equivalent inline confirm state)
    before calling useUninstallPlugin.'
  - 'R4: each installed card has an expandable component list; component kinds map
    to icons agent → 🤖, skill → ⚡, command → ⌘.'
  - 'R4: available cards render one per PluginsResponse.available with an install
    button calling useInstallPlugin.'
  - 'R4: marketplaces section lists each MarketplaceEntry with a remove button (useRemoveMarketplace)
    and an add-by-source-URL input form (useAddMarketplace).'
  - 'R4: section header / empty-state visuals are implemented LOCALLY inside PluginsPanel.tsx
    (DiscoveryPanel does NOT export SectionHeader/SectionEmptyState — see risk register);
    reuse existing Tailwind tokens (surface-1, border-hairline, ink-muted) to match
    DiscoveryPanel styling without importing from it.'
  - 'Test src/components/__tests__/PluginsPanel.test.tsx renders the panel with mocked
    usePlugins data covering: populated + empty states for all three sections, enable/disable
    toggle wiring, confirmed uninstall, component-list expand with icons, install
    button, marketplace add + remove.'
- id: I4
  type: frontend
  title: SpaceToolsPage plugins tab (R5)
  scope_files:
  - frontend/src/pages/SpaceToolsPage.tsx
  - frontend/src/pages/__tests__/SpaceToolsPage.test.tsx
  validation_command: cd frontend && npx vitest run src/pages/__tests__/SpaceToolsPage.test.tsx
  max_diff_lines: 200
  depends_on:
  - I3
  acceptance_criteria:
  - 'R5: Tab type union is ''"installed" | "discover" | "plugins"'' and TABS has a
    third entry { id: ''plugins'', label: ''Plugins'' }.'
  - 'R5: when activeTab === ''plugins'', <PluginsPanel /> is rendered.'
  - 'R5: the space selector stays hidden for the plugins tab (extend the existing
    ''only show selector for installed'' guard so ''plugins'' is also excluded); PluginsPanel
    takes no spaceId (plugins are container-global).'
  - 'Test src/pages/__tests__/SpaceToolsPage.test.tsx (extend existing file): asserts
    the Plugins tab renders, selecting it mounts PluginsPanel, and the space selector
    is not visible on the plugins tab.'
- id: I5
  type: frontend
  title: VariableInspector agent_ref datalist (R6) + HarnessEditor prop wiring
  scope_files:
  - frontend/src/components/harness/VariableInspector.tsx
  - frontend/src/pages/HarnessEditor.tsx
  - frontend/src/components/harness/__tests__/VariableInspector.test.tsx
  validation_command: cd frontend && npx vitest run src/components/harness/__tests__/VariableInspector.test.tsx
  max_diff_lines: 250
  depends_on:
  - I1
  acceptance_criteria:
  - 'R6: VariableInspectorProps gains an optional `spaceId?: string`, threaded down
    to the AgentConfig sub-component.'
  - 'R6: when spaceId is provided, AgentConfig fetches api.spaceTools(spaceId) and
    renders an HTML <datalist> containing one <option> per returned agent and skill
    name (including plugin components with namespaced names like ''plugin-name:skill-name'').'
  - 'R6: the agent_ref <input> has a `list` attribute referencing the datalist''s
    id; free-text entry is preserved (input remains a plain text input).'
  - 'R6: when spaceId is absent or tools are still loading, the datalist is empty
    and no error is thrown (graceful degradation).'
  - 'R6: HarnessEditor.tsx passes spaceId={spaceId} to the <VariableInspector> call
    site (spaceId is already available from useParams at the top of HarnessEditor)
    — this is the documented out-of-original-scope caller update widened into this
    iteration.'
  - 'Test src/components/harness/__tests__/VariableInspector.test.tsx (extend existing
    file): asserts datalist renders options from mocked api.spaceTools when spaceId
    is set, the input has the matching list attribute, free-text still updates agent_ref,
    and no crash when spaceId is undefined.'
risks:
- description: PluginsPanel is briefed to 'reuse existing SectionHeader/SectionEmptyState
    styling', but DiscoveryPanel.tsx exports only the DiscoveryPanel function — those
    helpers are module-local and cannot be imported. Editing DiscoveryPanel.tsx to
    export them would breach the I3 scope boundary.
  severity: medium
  mitigation: I3 implements section-header and empty-state visuals LOCALLY inside
    PluginsPanel.tsx using the same Tailwind tokens (surface-1, border-hairline, ink-muted);
    DiscoveryPanel.tsx is deliberately kept out of I3 scope_files. Acceptance criterion
    on I3 makes this explicit.
- description: R6 needs HarnessEditor.tsx to pass spaceId to VariableInspector. Because
    the prop is optional, omitting the wiring still type-checks and builds green,
    but the datalist would silently never populate (dead feature).
  severity: medium
  mitigation: HarnessEditor.tsx is added to I5 scope_files and an I5 acceptance criterion
    asserts the spaceId={spaceId} prop is wired at the call site (HarnessEditor.tsx
    line ~363); the VariableInspector test exercises the populated-datalist path so
    the integration is covered.
- description: Backend plugin endpoints/models were delivered on feature/implement-plugin-management
    (and analysis/backend artifacts landed on feature/implement-claude-code-plugin-management).
    If the frontend slice is committed onto a branch that does not carry the backend,
    GET /api/plugins 404s at runtime even though type-checks and mocked tests pass.
  severity: medium
  mitigation: Frontend tests mock api.plugins/api.spaceTools so correctness is independent
    of backend presence; the implementor and goal-finalize step must verify (git log)
    that the frontend work lands on the same feature branch that carries backend/app/api/plugins.py
    before merge to main.
- description: 'TanStack Query staleness: if any of the six mutation hooks omits invalidateQueries([''plugins''])
    in onSuccess, the PluginsPanel shows stale install/enable state after a mutation.'
  severity: low
  mitigation: I2 acceptance criterion + test spy on queryClient.invalidateQueries
    assert every one of the six mutations invalidates the ['plugins'] key on success.
metrics:
  tool_calls: 16
  files_read: 8
  memory_hits: 2
  iterations_planned: 5
---

## Summary

This frontend-only slice layers a plugin-management UI onto the already-delivered backend (7 REST endpoints + Pydantic models). The work is purely additive and decomposes into a clean, mostly-wide DAG: a foundation iteration adds the five TypeScript interfaces and the seven API client functions (I1), after which the React Query hooks (I2) and the `VariableInspector` datalist (I5) proceed in parallel; the `PluginsPanel` component (I3) consumes both types and hooks, and the `SpaceToolsPage` tab (I4) consumes the panel. The non-obvious tradeoffs captured in the risk register are that `SectionHeader`/`SectionEmptyState` are not exported by `DiscoveryPanel` (so styling must be re-implemented locally rather than imported), and that the optional `spaceId` prop for R6 can silently no-op if `HarnessEditor` wiring is skipped — which is why `HarnessEditor.tsx` is folded into I5's scope.

## Components

### Data
- `PluginComponent`, `PluginEntry`, `MarketplacePluginEntry`, `MarketplaceEntry`, `PluginsResponse` (frontend TS interfaces in `types.ts`): mirror the backend Pydantic plugin models verbatim.
- `AiToolEntry.scope` union extension (`+ "plugin"`): lets tool entries originating from installed plugins carry a distinct scope.

### Backend
- None in this slice — the 7 `/api/plugins` endpoints and Pydantic models were delivered upstream (`impl-report-plugin-backend-core--i1`, `impl-report-plugin-api-integration--i1`). This slice only consumes them.

### Frontend
- `api.ts` plugin client functions: `plugins`, `installPlugin`, `uninstallPlugin`, `enablePlugin`, `disablePlugin`, `addMarketplace`, `removeMarketplace`.
- `hooks/usePlugins.ts` (NEW): `usePlugins` query + 6 mutation hooks with `['plugins']` invalidation.
- `components/PluginsPanel.tsx` (NEW): three-section (Installed / Available / Marketplaces) plugin management UI.
- `pages/SpaceToolsPage.tsx`: third "Plugins" tab rendering `<PluginsPanel />`, space selector hidden.
- `components/harness/VariableInspector.tsx`: `<datalist>`-backed `agent_ref` input fed by `api.spaceTools()`.
- `pages/HarnessEditor.tsx`: threads existing `spaceId` into `<VariableInspector spaceId={spaceId} />` (caller wiring for R6).

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                                        | Validation                                                                |
|-----|----------|------------|-------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| I1  | frontend | -          | types.ts, api.ts, __tests__/api.plugins.test.ts                               | cd frontend && npx vitest run src/__tests__/api.plugins.test.ts           |
| I2  | frontend | I1         | hooks/usePlugins.ts, hooks/__tests__/usePlugins.test.tsx                       | cd frontend && npx vitest run src/hooks/__tests__/usePlugins.test.tsx     |
| I3  | frontend | I1, I2     | components/PluginsPanel.tsx, components/__tests__/PluginsPanel.test.tsx        | cd frontend && npx vitest run src/components/__tests__/PluginsPanel.test.tsx |
| I4  | frontend | I3         | pages/SpaceToolsPage.tsx, pages/__tests__/SpaceToolsPage.test.tsx              | cd frontend && npx vitest run src/pages/__tests__/SpaceToolsPage.test.tsx |
| I5  | frontend | I1         | harness/VariableInspector.tsx, pages/HarnessEditor.tsx, harness/__tests__/VariableInspector.test.tsx | cd frontend && npx vitest run src/components/harness/__tests__/VariableInspector.test.tsx |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| DiscoveryPanel does not export SectionHeader/SectionEmptyState; importing them would breach I3 scope. | medium | I3 re-implements those visuals locally in PluginsPanel.tsx with the same Tailwind tokens; DiscoveryPanel.tsx stays out of scope. |
| Optional `spaceId` prop for R6 silently no-ops if HarnessEditor wiring is skipped (still builds green). | medium | HarnessEditor.tsx added to I5 scope; acceptance criterion + test assert the prop is wired and the datalist populates. |
| Frontend slice may land on a branch lacking the backend plugin endpoints → runtime 404 despite green mocked tests. | medium | Tests mock api.plugins/api.spaceTools; implementor + goal-finalize must verify (git log) the frontend lands on the branch carrying backend/app/api/plugins.py before merge. |
| A mutation hook missing invalidateQueries(['plugins']) leaves PluginsPanel stale. | low | I2 acceptance + test spy assert all six mutations invalidate the ['plugins'] key on success. |

## Assumptions

- **Decomposition over single iteration**: the task brief noted one iteration "is likely sufficient", but per the architect contract (one logical change unit per iteration, prefer a wide DAG) and the analyst's explicit recommended ordering, the work is split into five self-validating iterations. Each iteration owns its own test file so its `validation_command` is runnable in isolation.
- **Test files are implementor-owned**: every iteration's `scope_files` includes the test file the implementor must author/extend; the analyst excluded tests from its scope as "implementor/test phase owned". `SpaceToolsPage.test.tsx` and `VariableInspector.test.tsx` already exist and are extended in place (I4, I5).
- **I5 depends on I1 only**: the datalist consumes the existing `api.spaceTools()`, but R6 references the `"plugin"` scope literal added in I1; declaring `depends_on: [I1]` keeps it type-safe while still allowing I2/I5 to run in parallel (Kahn layer 1).
- **Container-global plugins**: `GET /api/plugins` is not space-scoped, so `usePlugins()` calls `api.plugins()` directly and `PluginsPanel` takes no `spaceId` (matches analyst assumption); the space selector is hidden on the plugins tab.
- **Confirmation UX**: uninstall confirmation uses `window.confirm()` (or inline confirm state) — no modal library, consistent with existing DiscoveryPanel patterns.

## Open questions

- None blocking. (The analyst's path-discrepancy question is resolved: this artifact is written at the verifier-canonical `.cronos/pipeline/plugin-frontend/design-report-plugin-frontend.md`, matching the analysis report's location, not the `plugin-management/` path in the brief.)

## Next consumer brief

Read `iterations[]`, then each entry's `scope_files`, `validation_command`, and `acceptance_criteria` — that is the executable plan. DAG layers (Kahn): layer 0 = I1; layer 1 = I2, I5 (parallel); layer 2 = I3; layer 3 = I4.

Cross-iteration invariants NOT derivable from the YAML alone:
1. The query key is the literal `['plugins']` everywhere (I2 hooks, any I3 reads) — must match byte-for-byte for invalidation to work.
2. The seven API paths and body shapes in I1 are the contract the backend already exposes (`/api/plugins`, `/install`, `/uninstall`, `/enable`, `/disable`, `/marketplaces`, `/marketplaces/{name}` with bodies `{plugin_id, scope}` and `{source}`) — do not invent new paths.
3. I3 must NOT import `SectionHeader`/`SectionEmptyState` from `DiscoveryPanel` (not exported) — implement locally. See risk 1.
4. I5 must wire `spaceId` at the `HarnessEditor` call site (line ~363) or R6 is a dead feature. See risk 2.
