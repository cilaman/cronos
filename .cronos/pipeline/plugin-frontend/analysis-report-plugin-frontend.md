---
cc_version: '1.0'
agent: pipeline-analyst
slug: plugin-frontend
phase: analysis
status: done
confidence: 0.93
inputs_used:
- memory:pipeline-analyst-agent
- memory:analyst-frontend-card-board-fixes
- .cronos/pipeline/plugin-management/scout-report-plugin-management.md
- .cronos/pipeline/plugin-management/impl-report-plugin-backend-core--i1.md
- .cronos/pipeline/plugin-api-integration/impl-report-plugin-api-integration--i1.md
- frontend/src/types.ts
- frontend/src/api.ts
- frontend/src/hooks/useHarnesses.ts
- frontend/src/pages/SpaceToolsPage.tsx
- frontend/src/components/harness/VariableInspector.tsx
- backend/app/api/plugins.py
- backend/app/models.py
- .claude/agents/pipeline-analyst.md
outputs_produced:
- .cronos/pipeline/plugin-frontend/analysis-report-plugin-frontend.md
blockers: []
next_consumer: design
request: 'Implement the frontend plugin management UI: types, API helpers, React Query
  hooks, PluginsPanel component, SpaceToolsPage tab, and VariableInspector agent_ref
  picker.'
has_ui: true
coverage_summary:
  searched:
  - frontend/src/types.ts
  - frontend/src/api.ts
  - frontend/src/hooks/useHarnesses.ts
  - frontend/src/pages/SpaceToolsPage.tsx
  - frontend/src/components/harness/VariableInspector.tsx
  - backend/app/api/plugins.py
  - backend/app/models.py
  - .cronos/pipeline/plugin-management/scout-report-plugin-management.md
  - .cronos/pipeline/plugin-management/impl-report-plugin-backend-core--i1.md
  - .cronos/pipeline/plugin-api-integration/impl-report-plugin-api-integration--i1.md
  excluded:
  - frontend/src/components/DiscoveryPanel.tsx: styling conventions documented by
      scout; no targeted read needed
  - backend/app/tools/plugins.py: CLI wrapper; API contract already captured via api/plugins.py
      read
  - frontend tests: owned by implementor/test phases
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: types.ts must export five new TypeScript interfaces (PluginComponent,
    PluginEntry, MarketplacePluginEntry, MarketplaceEntry, PluginsResponse) mirroring
    the backend Pydantic models verbatim, and the AiToolEntry.scope union must be
    extended to include 'plugin'.
  acceptance_criteria:
  - 'PluginComponent has `name: string` and `kind: ''agent'' | ''skill'' | ''command''`.'
  - PluginEntry has id, name, marketplace, version, scope, enabled, components (PluginComponent[]),
    installPath, installedAt, lastUpdated — all optional fields match backend defaults
    (marketplace/version/installPath/installedAt/lastUpdated nullable/undefined; enabled
    defaults true).
  - MarketplacePluginEntry has pluginId, name, description (nullable), marketplaceName
    (nullable), source (nullable), installCount (number).
  - 'MarketplaceEntry has name: string and source: string.'
  - 'PluginsResponse has installed: PluginEntry[], available: MarketplacePluginEntry[],
    marketplaces: MarketplaceEntry[].'
  - AiToolEntry.scope union is '"space" | "global" | "plugin"'.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: 'api.ts must add seven API client functions: plugins() fetching GET /api/plugins;
    installPlugin(pluginId, scope) POSTing /api/plugins/install; uninstallPlugin(pluginId)
    POSTing /api/plugins/uninstall; enablePlugin(pluginId) POSTing /api/plugins/enable;
    disablePlugin(pluginId) POSTing /api/plugins/disable; addMarketplace(source) POSTing
    /api/plugins/marketplaces; removeMarketplace(name) DELETEing /api/plugins/marketplaces/{name}.
    All mutation functions return Promise<PluginsResponse>.'
  acceptance_criteria:
  - api.plugins() issues GET /api/plugins and returns Promise<PluginsResponse>.
  - api.installPlugin(pluginId, scope) issues POST /api/plugins/install with body
    {plugin_id, scope}.
  - api.addMarketplace(source) issues POST /api/plugins/marketplaces with body {source}.
  - api.removeMarketplace(name) issues DELETE /api/plugins/marketplaces/${name} (no
    body).
  - All seven functions are exported from the api object (consistent with existing
    spaceTools, adoptTool patterns).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R3
  statement: Create frontend/src/hooks/usePlugins.ts with a usePlugins() query hook
    and six mutation hooks (useInstallPlugin, useUninstallPlugin, useEnablePlugin,
    useDisablePlugin, useAddMarketplace, useRemoveMarketplace); all mutations must
    invalidate the ['plugins'] query key on success.
  acceptance_criteria:
  - 'usePlugins() returns useQuery({ queryKey: [''plugins''], queryFn: api.plugins
    }).'
  - 'Each of the six mutation hooks wraps the corresponding api.ts function in useMutation
    and calls queryClient.invalidateQueries({ queryKey: [''plugins''] }) in onSuccess.'
  - 'File follows useHarnesses.ts naming conventions: named exports, TanStack Query
    v5 object syntax.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R4
  statement: Create frontend/src/components/PluginsPanel.tsx with three sections —
    Installed, Available, and Marketplaces — each with appropriate empty-state messaging;
    installed plugin cards show enable/disable toggle, uninstall with confirmation,
    and an expandable component list using 🤖/⚡/⌘ icons; available plugin cards show
    an install button; the marketplaces section provides an add-by-URL form and remove
    buttons; all data comes from usePlugins().
  acceptance_criteria:
  - Installed section renders one card per PluginsResponse.installed entry; each card
    has an enable/disable toggle that calls useEnablePlugin/useDisablePlugin.
  - Uninstall action is gated by a confirmation prompt before calling useUninstallPlugin.
  - 'Each installed plugin card has an expandable component list; component kinds
    map to icons: agent → 🤖, skill → ⚡, command → ⌘.'
  - Available section renders one card per PluginsResponse.available entry with an
    install button calling useInstallPlugin.
  - Marketplaces section renders existing marketplaces with remove buttons (useRemoveMarketplace)
    and an input form to add a new marketplace by source URL (useAddMarketplace).
  - All three sections show empty-state text when their respective lists are empty.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R5
  statement: SpaceToolsPage.tsx must add 'plugins' to the Tab type union and TABS
    array, render <PluginsPanel /> when activeTab === 'plugins', and keep the space
    selector hidden for the plugins tab (plugins are container-global).
  acceptance_criteria:
  - Tab type is '"installed" | "discover" | "plugins"'.
  - 'TABS array has three entries; the third is { id: ''plugins'', label: ''Plugins''
    }.'
  - When activeTab === 'plugins', <PluginsPanel /> is rendered and the space selector
    is not visible.
  verifying_phase: review
  confidence: 0.95
- requirement_id: R6
  statement: 'VariableInspector.tsx AgentConfig sub-component must back the agent_ref
    text input with an HTML <datalist> populated from api.spaceTools() agents and
    skills (including plugin components with namespaced names like ''plugin-name:skill-name'');
    VariableInspector must accept an optional spaceId?: string prop threaded down
    to AgentConfig; free-text entry must be preserved.'
  acceptance_criteria:
  - 'VariableInspectorProps interface includes spaceId?: string.'
  - When spaceId is provided, AgentConfig fetches space tools and renders a <datalist>
    containing all agent and skill names.
  - The agent_ref <input> has a list attribute referencing the datalist id.
  - When spaceId is absent or tools are loading, the datalist is empty (graceful degradation,
    no error).
  verifying_phase: review
  confidence: 0.88
metrics:
  tool_calls: 37
  files_read: 11
  memory_hits: 2
---

## Summary

This slice implements the frontend-only plugin management UI on top of the already-delivered backend (7 REST endpoints at `/api/plugins` + Pydantic models on `feature/implement-plugin-management`). The work is additive: five new TypeScript interfaces, seven new API client functions, a new React Query hook file, a new `PluginsPanel` component, one tab addition to `SpaceToolsPage`, and one `<datalist>` enhancement in `VariableInspector`. No routing or sidebar changes are needed — the Plugins tab lives under the existing `/tools` AI Tools page.

## Scope

### In scope
- `frontend/src/types.ts`: add `PluginComponent`, `PluginEntry`, `MarketplacePluginEntry`, `MarketplaceEntry`, `PluginsResponse` interfaces; extend `AiToolEntry.scope` union with `"plugin"`
- `frontend/src/api.ts`: add seven plugin API client functions
- `frontend/src/hooks/usePlugins.ts` (NEW): `usePlugins` query + six mutation hooks
- `frontend/src/components/PluginsPanel.tsx` (NEW): three-section plugin management UI
- `frontend/src/pages/SpaceToolsPage.tsx`: add `"plugins"` tab entry and conditional render
- `frontend/src/components/harness/VariableInspector.tsx`: `<datalist>` picker for `agent_ref`

### Out of scope
- Backend API (`backend/app/api/plugins.py`, `backend/app/tools/plugins.py`, `backend/app/models.py`): already implemented and tested on `feature/implement-plugin-management`
- New routes or sidebar navigation entries: no new routes needed; Plugins tab is reached via the existing AI Tools page
- CSS/Tailwind design system additions: existing tokens (surface-1, border-hairline, ink-muted, etc.) are sufficient
- Plugin trust/security enforcement: enforced at backend layer (regex validation, asyncio.Lock); no additional frontend validation required
- Plugin install progress streaming: install is synchronous (mutation completes when CLI exits); no SSE or polling needed in MVP

### Deferred
- Plugin update/upgrade flow (no CLI equivalent in v2.1.181)
- Plugin component detail view (inline content rendering)
- Marketplace browsing with search/filter (MVP shows all available from configured marketplaces)

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Add 5 TypeScript interfaces to types.ts + extend AiToolEntry.scope |
| R2 | Add 7 API client functions to api.ts |
| R3 | Create usePlugins.ts with query + 6 mutation hooks |
| R4 | Create PluginsPanel.tsx with Installed/Available/Marketplaces sections |
| R5 | Add "plugins" tab to SpaceToolsPage |
| R6 | Back VariableInspector agent_ref input with spaceTools datalist |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]`
array (the machine-readable source of truth). The body summary below mirrors them
in compact form for the human reader.

- R1 — types.ts exports PluginComponent/PluginEntry/MarketplacePluginEntry/MarketplaceEntry/PluginsResponse; AiToolEntry.scope includes "plugin"; all field types match backend models exactly
- R2 — seven named API functions present in api.ts; all endpoint paths, HTTP methods, and body shapes match the backend router at backend/app/api/plugins.py
- R3 — usePlugins.ts exports usePlugins (query) + 6 mutation hooks; all mutations invalidate ['plugins'] on success; follows TanStack Query v5 object syntax
- R4 — PluginsPanel renders 3 sections; installed cards have enable/disable toggle and confirmed uninstall; components expand with 🤖/⚡/⌘; available cards have install button; marketplaces section has add form + remove; all sections have empty states
- R5 — Tab type includes "plugins"; TABS has 3 entries; PluginsPanel renders when activeTab === "plugins"; space selector hidden for plugins tab
- R6 — VariableInspectorProps has spaceId?; AgentConfig renders datalist from api.spaceTools() when spaceId present; agent_ref input has list attribute; graceful degradation when spaceId absent

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML
`traceability[]` array. Downstream agents read the YAML directly; this section
exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | types.ts exports 5 new interfaces; AiToolEntry.scope extended |
| R2 | test | api.ts exports 7 plugin API client functions |
| R3 | test | usePlugins.ts: query + 6 mutations, all invalidate ['plugins'] |
| R4 | review | PluginsPanel: 3 sections, full CRUD, empty states, component icons |
| R5 | review | SpaceToolsPage: plugins tab added, PluginsPanel conditional render |
| R6 | review | VariableInspector: spaceId prop, datalist-backed agent_ref input |

## Assumptions

- **has_ui=true**: All 6 requirements involve React component rendering, user interaction (toggles, confirmation dialogs, form inputs), or visual state changes.
- **Backend already delivered**: The 7 REST endpoints and Pydantic models are on `feature/implement-plugin-management` (impl-report-plugin-backend-core--i1 and impl-report-plugin-api-integration--i1 both status=done). The frontend implementor must ensure it also works on that branch.
- **No scope in AiToolEntry.scope yet**: Current `frontend/src/types.ts` line 411 declares `scope: "space" | "global"` — the `"plugin"` literal is missing and must be added (R1).
- **VariableInspector has no spaceId prop**: The component's current props interface (`VariableInspectorProps`) lacks `spaceId`. This prop must be added here and plumbed from the parent `HarnessEditor.tsx` (not in this slice's scope boundary, but HarnessEditor already has `spaceId` from its route param; the implementor should thread it through).
- **Plugins are container-global**: The `GET /api/plugins` endpoint is not space-scoped (`/api/plugins`, not `/api/spaces/{id}/plugins`). The PluginsPanel component therefore needs no spaceId prop; `usePlugins()` calls `api.plugins()` directly.
- **api.plugins() placement**: New plugin functions should be grouped after the existing adoption/discovery section in `api.ts`, following the established inline comment convention (`// --- plugins ---`).

## Open questions

1. **Task brief path discrepancy**: The task brief instructs emitting the artifact at `.cronos/pipeline/plugin-management/analysis-report-plugin-frontend.md`, but the verifier's `canonical_artifact_relpath("analysis", "plugin-frontend")` computes `.cronos/pipeline/plugin-frontend/analysis-report-plugin-frontend.md`. This artifact is written at the canonical computed path. If the gate uses `GOAL_SLUG=plugin-frontend` and `PHASE=analyst`, the verifier will look for it at the canonical path — so this should be correct.

2. **HarnessEditor spaceId threading for R6**: Adding `spaceId?` to `VariableInspectorProps` is within this scope, but updating `HarnessEditor.tsx` to pass the prop is outside the declared scope boundary. The implementor should flag this as a minimal caller update — it is a 1-line addition to `HarnessEditor.tsx` but out of the hard boundary. Design agent should decide whether to widen the scope or treat it as a documented dependency.

## Next consumer brief

Read `traceability[]` and `has_ui` first (both `true` and non-trivial UI logic).

Key design decisions for the architect:
1. **Iteration ordering**: R1 and R2 (types + api.ts) are pure additive changes with no UI; they are fast prerequisites. R3 (hooks) depends on R1+R2. R4 (PluginsPanel) depends on R1+R2+R3. R5 (tab) depends on R4. R6 (datalist) depends on R1 (for `AiToolEntry` with `"plugin"` scope). A clean 3-tier DAG: (R1,R2) → (R3, R6) → (R4) → (R5).
2. **R6 scope risk**: VariableInspector's `spaceId` must be threaded from HarnessEditor. The implementor will need a minimal 1-line change in `HarnessEditor.tsx` (which is out of the declared scope boundary). The architect should either widen the scope or create a standalone wrapper. Recommend widening scope to include `HarnessEditor.tsx` for this single prop addition.
3. **R4 confirmation dialog**: Use a simple `window.confirm()` or inline toggle state — no modal library required given existing patterns in DiscoveryPanel.
4. **Styling anchor**: Reuse `SectionHeader` from `DiscoveryPanel.tsx` (exported component). Implementor must check whether it is already exported or needs a local copy.
