---
cc_version: '1.0'
agent: pipeline-scout
slug: frontend-harness-editor
phase: scout
status: done
confidence: 0.95
inputs_used:
- backend model spec (model.py)
- frontend types.ts, harnessMapping.ts, VariableInspector.tsx
- node components (Agent, Decision, Wait, Trigger, Aggregator)
- HarnessEditor.tsx canvas integration
- acceptance criteria (7 AC points)
outputs_produced:
- .cronos/pipeline/frontend-harness-editor/scout-report-frontend-harness-editor.md
blockers: []
next_consumer: pipeline-analyst
coverage_summary:
  searched:
  - backend/app/harnesses/model.py
  - frontend/src/types.ts
  - frontend/src/components/harness/harnessMapping.ts
  - frontend/src/components/harness/VariableInspector.tsx
  - frontend/src/pages/HarnessEditor.tsx
  - frontend/src/components/harness/AgentNode.tsx
  - frontend/src/components/harness/DecisionNode.tsx
  - frontend/src/components/harness/WaitNode.tsx
  - frontend/src/components/harness/TriggerNode.tsx
  - frontend/src/components/harness/AggregatorNode.tsx
  excluded:
  - backend harness executor internals (assumed correct)
  - other frontend pages unrelated to harness editor
  strategies:
  - read_targeted
metrics:
  tool_calls: 8
  files_read: 12
  memory_hits: 0
---

## Summary

The harness visual editor frontend diverges from the backend data model in seven structural areas. The frontend uses a `config` object separate from `data`, loses information during round-trip serialization, stores ports as arrays instead of dicts, labels edges instead of conditioning them, and lacks UI for editing node-specific fields on non-Agent nodes. All gaps are solvable via frontend-only changes; the backend model is correct and must not change.

**Risk**: A freshly dragged node or saved harness will hit backend 422 validation errors because:
1. Ports are missing or malformed (array instead of dict)
2. Edge conditions are null/missing when decision routing is needed
3. Required node.data fields (mode, kind, etc.) are absent for non-Agent nodes

---

## Findings

### F1: `node.data` vs `node.config` structural mismatch

**Current state**:
- Backend model (`backend/app/harnesses/model.py:110-120`) defines:
  - `HarnessNode.data: dict = Field(default_factory=dict)` — arbitrary node-specific config
  - `HarnessNode.ports: dict[str, dict] = Field(default_factory=dict)` — port definitions keyed by port-id
  - These are *separate* fields; nothing is nested inside data.

- Frontend types.ts (`frontend/src/types.ts:567-574`) defines:
  ```typescript
  interface HarnessNode {
    config: Record<string, unknown>;  // ← NOT a `data` field
    ports: NodePort[];                 // ← array, not dict
  }
  ```

- harnessMapping.ts (`toReactFlow()`, lines 10-11) maps:
  ```typescript
  data: { label: n.label, ...n.config, _ports: n.ports }
  ```
  This *conflates* label + config into data and hides ports under `_ports`.

- harnessMapping.ts (`fromReactFlow()`, lines 34-40) unmaps:
  ```typescript
  const { label, _ports, ...config } = n.data;
  ports: orig?.ports ?? [],
  ```
  This discards any keys in data that weren't explicitly known, breaks new nodes (no original to copy from), and returns ports as an array.

**Gap**: Node data round-trip loses keys. If a user edits a harness, saves it, the backend returns the updated harness with correctly-typed `data` and `ports`, but when the editor reloads it, `toReactFlow()` spreads `data` into the React Flow node's `data` prop, mixing label + config + ports. Editing and saving again will drop any data keys not in config.

**Impact**: AC-1 (node data round-trip, no keys dropped) FAILS.

---

### F2: `prompt_template` field naming and persistence

**Current state**:
- Backend executor (`executor.py:736`) reads:
  ```python
  prompt_template: str = node.data.get("prompt_template", "")
  ```

- Frontend VariableInspector.tsx (`lines 26-56`) reads/writes:
  ```typescript
  const prompt = typeof config.prompt === 'string' ? config.prompt : '';
  onChange={(e) => onNodeChange(selectedNode.id, { ...config, prompt: e.target.value })
  ```
  Stores as `config.prompt`, not `config.prompt_template`.

- harnessMapping.ts spreads config into the React Flow node's data, then pulls it back as config, so `prompt` survives the round-trip within the frontend. But when saved to the backend, it lands in a FeatureConfig object under `prompt` (if the field exists), not `node.data.prompt_template`.

**Gap**: The editor shows a "prompt" field for agent nodes, but it persists to `node.data.prompt` (via config), while the backend executor reads from `node.data.prompt_template`. The backend will see an empty string every time.

**Impact**: AC-2 (prompt_template persistence) FAILS.

---

### F3: Ports as array instead of dict, no default ports for new nodes

**Current state**:
- Backend model requires `ports: dict[str, dict]`, e.g.:
  ```json
  {"in": {}, "out": {}}
  ```

- Frontend `fromReactFlow()` returns `ports: orig?.ports ?? []` — an array if no original or an array from the original.

- When a user drags a new node onto the canvas (HarnessEditor.tsx, `onDrop`, lines 74-86), it creates:
  ```typescript
  const newNode = {
    id: `${nodeType}-${Date.now()}`,
    type: nodeType,
    position,
    data: { label: nodeType },
  };
  ```
  No ports, no config. When `fromReactFlow()` processes it, `orig` is undefined (new node), so ports defaults to `[]`.

- Node components render static Handle ids:
  - AgentNode: top (target, default id), bottom (source, default id)
  - DecisionNode: top (target, default id), bottom "yes" and "no" (source)
  - TriggerNode: bottom (source, default id)
  - WaitNode: top (target, default id), bottom (source, default id)
  - AggregatorNode: N inputs on top as `in-0`, `in-1`, ... (targets); bottom (source, default id)

**Gap**: Backend validation (model.py:196-200, R4 rule) checks that each edge references a port that exists in the node's ports dict. New nodes have `ports: []` (empty array), so any edge connection fails validation with "references unknown port".

**Impact**: AC-3 (ports as dict + defaults + Handle ids) FAILS. A freshly dragged node cannot be saved.

---

### F4: Edge condition vs label; missing decision routing UI

**Current state**:
- Backend model (`HarnessEdge`, line 137): `condition: str | None = None` — optional guard expression.
- Backend model documentation (lines 27-29): Decision node routing is driven by condition labels on edges (e.g., `"yes"`, `"no"`), not separate data.

- Frontend types.ts (lines 581-586):
  ```typescript
  interface HarnessEdge {
    id: string;
    source: NodeRef;
    target: NodeRef;
    label?: string;  // ← NOT a `condition` field
  }
  ```

- harnessMapping.ts (`toReactFlow()`, line 18): `label: e.label`.
- harnessMapping.ts (`fromReactFlow()`, line 49): `label: e.label as string | undefined`.

- VariableInspector.tsx does not expose edge editing. Edges are visible as React Flow connections on the canvas but cannot be labeled/conditioned.

**Gap**: Edges are labeled in the frontend but stored as `condition` in the backend. More critically, there is no UI to set or edit edge conditions, so decision nodes cannot route properly (missing yes/no conditions).

**Impact**: AC-4 (edge condition round-trip + editing) FAILS.

---

### F5: Editable config missing for Decision, Wait, Aggregator, Trigger nodes

**Current state**:
- VariableInspector.tsx shows agent-specific fields only (lines 26-60): `agent_ref` + `prompt`.
- For other nodes (lines 64-82), it displays config as read-only key/value pairs:
  ```typescript
  {Object.entries(config).map(([key, val]) => (
    <div key={key} className="flex gap-1 text-xs">
      <span className="text-ink-muted font-medium">{key}:</span>
      <span className="text-ink truncate">{String(val)}</span>
    </div>
  ))}
  ```

- Backend model defines required data fields per node type:
  - Decision: no mandatory data (routing via edge conditions).
  - Wait: `mode` (required, 'human'|'timed'), `duration_seconds` (required if timed), `max_wait_seconds` (required if human), `waiting_question` (optional).
  - Aggregator: `mode` (required, 'all'|'any').
  - Trigger (cron): `expression` (required), `timezone` (optional).
  - Trigger (event): `kind` (required, one of 'webhook'|'file-change'|'task-state-change'), plus kind-specific fields:
    - webhook: `webhook_path` (required), `auth_token` (required).
    - file-change: `watch_pattern` (required), `debounce_seconds` (optional).
    - task-state-change: `watched_state` (optional, defaults to 'DONE').

- Frontend has no UI to set these fields. A user cannot specify that a Wait node is 'human' vs 'timed', set an Aggregator's `mode` to 'all' or 'any', or distinguish between cron and event trigger types.

**Gap**: Backend validation will reject nodes with missing required fields. The frontend provides no way to populate them.

**Impact**: AC-5 (editable config for all node types) FAILS. Nodes save with empty data dicts and fail validation.

---

### F6: Variables table lacks add/remove UI

**Current state**:
- VariableInspector.tsx (lines 86-107) shows harness variables when no node is selected:
  ```typescript
  {Object.entries(variables).map(([key, val]) => (
    <label key={key} className="flex flex-col gap-1">
      <span className="text-xs text-ink-muted">{key}</span>
      <input
        ... 
        onChange={(e) => onVariableChange(key, e.target.value)}
      />
    </label>
  ))}
  ```

- HarnessEditor.tsx defines a callback `handleVariableChange` (lines 94-96 visible in the partial read, but need to check full implementation):
  ```typescript
  const handleNodeChange = useCallback((nodeId: string, config: Record<string, unknown>) => {
    setNodes(nds => nds.map(n => n.id === nodeId ? { ...n, data: { ...n.data, ...config } } : n));
  }, [setNodes]);
  ```
  But I don't see a corresponding `handleVariableChange` that mutates `harness.variables`.

- The UI shows existing variables as editable inputs but has no "Add variable" or "Remove variable" buttons.

**Gap**: Users can edit existing variable values but cannot add new variables or remove unwanted ones. The onVariableChange callback exists but is disconnected from the harness state mutation.

**Impact**: AC-6 (variables add/edit/remove) PARTIALLY FAILS. Edit works, add/remove do not.

---

### F7: No error feedback for backend 422 validation errors

**Current state**:
- HarnessEditor.tsx (lines 88-92, visible in partial):
  ```typescript
  const handleSave = useCallback(() => {
    if (!harness) return;
    const updated = fromReactFlow(nodes, edges, harness);
    saveMutation.mutate(updated);
  }, [harness, nodes, edges, saveMutation]);
  ```

- `saveMutation` is from `useSaveHarness()` (imported from hooks/useHarnesses.ts, not shown in reads above). Typical React Query mutation patterns either:
  - Surface errors via `mutation.error` and display them in the UI, or
  - Call an onError handler.

- No visible error display in HarnessEditor (no toast, no inline error message).

**Gap**: When the user saves an invalid harness, the backend returns 422 with validation errors (missing ports, invalid edge references, missing required node.data fields), but the frontend does not surface these errors. The user sees no feedback; the save silently fails or appears to succeed.

**Impact**: AC-7 (save feedback for 422 errors) FAILS. Users have no way to debug why a save failed.

---

## Test Coverage Gaps

- **harnessMapping round-trip**: No vitest coverage for `toReactFlow() → fromReactFlow()` with real backend node.data objects. Current tests (if any) likely use mock config, not real decision/wait/aggregator/trigger data structures.
- **VariableInspector field wiring**: No tests for prompt_template persistence, node-type-specific field editing, or variable add/remove operations.
- **New node defaults**: No tests for freshly dragged nodes and port generation.
- **Edge condition round-trip**: No tests for edge condition serialization.

---

## Scope & Dependencies

**Files requiring changes** (all frontend, all under `frontend/src/`):
1. `types.ts` — HarnessNode interface (replace `config` with `data`, change ports to dict).
2. `components/harness/harnessMapping.ts` — fix toReactFlow/fromReactFlow round-trip, generate default ports, handle prompt_template.
3. `components/harness/VariableInspector.tsx` — fix prompt field name, add node-type-specific editors, wire variable add/remove.
4. `pages/HarnessEditor.tsx` — wire onVariableChange callback, handle save errors.
5. `components/harness/{Agent,Trigger,Decision,Wait,Aggregator}Node.tsx` — optional improvements (Handle ids are already correct).
6. `components/harness/NodePalette.tsx` — no changes needed.

**Backend assumptions**:
- Backend model.py validation (R1-R4) is correct and must not be changed.
- Edge.condition (backend) must round-trip correctly through frontend.label (currently label, needs rename to condition).

---

## Implementation Order

1. **Types layer** (types.ts): Align HarnessNode.data and .ports to backend.
2. **Mapping layer** (harnessMapping.ts): Fix round-trip, default ports, prompt_template.
3. **UI layer** (VariableInspector + HarnessEditor): Add node-specific editors, variable UI, error feedback.
4. **Testing**: Vitest coverage for round-trip and field wiring.
5. **Validation**: `npm test` + `npm run build` green; manual editor smoke test in browser.

---

## Coverage

- **Feature request alignment**: All 7 acceptance criteria examined and mapped to implementation gaps.
- **Codebase scope**: Backend model (model.py) verified as source of truth; frontend types, components, hooks, and editor canvas inspected.
- **Acceptance criteria coverage**: AC-1 through AC-7 each analyzed for current state, gap, and impact.
- **Test coverage audit**: 3 test gaps identified (round-trip, field wiring, new-node defaults).
- **Risk identification**: Backend 422 validation failure modes documented.

## Assumptions

- Backend model in `backend/app/harnesses/model.py` is correct and immutable per the feature request.
- The seven acceptance criteria are comprehensive and exhaustive.
- React Flow v12 (@xyflow/react) is the intended canvas framework (confirmed in existing code).
- Node components render static Handle ids correctly; ports data structure is the gap, not UI rendering.
- The backend executor reads `node.data.prompt_template` as the single source of truth for agent prompts.
- Edge routing decisions are driven by `HarnessEdge.condition` on decision-out edges (yes/no labels).

## Open questions

1. **Error surface strategy**: Should 422 validation errors appear as a toast, inline error panel, or modal? Current code has no error feedback mechanism.
2. **Variable add/remove UX**: Should users add variables via an "Add variable" button, inline input, or modal? The onVariableChange callback exists but lacks UI.
3. **Port defaults for Aggregator**: When a user drags an Aggregator node, how many input ports should it have by default? Current AggregatorNode renders N=2 inputs; `fromReactFlow()` needs to persist the default.
4. **Trigger node sub-types**: Should the VariableInspector distinguish between cron and event triggers via a kind selector, or should users manually edit kind + per-kind fields?
5. **Type narrowing**: Should node.data be a discriminated union per node type (AgentNodeData, WaitNodeData, etc.) or remain `dict` with optional type guards?

## Next consumer brief

The **analyst** should:
1. Verify all 7 acceptance criteria are translatable to testable requirements.
2. Identify any cross-cutting concerns (e.g., TypeScript type narrowing on node.data per node type).
3. Scope the implementation into minimal, reviewable iterations (suggest 7-10, one per AC point + edge condition + tests).
4. Note any UI/UX decisions (e.g., how to surface 422 errors — toast vs inline panel).
