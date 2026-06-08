---
cc_version: '1.0'
agent: pipeline-analyst
slug: feature-detail-panel
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:project_merge_2026_06_08
- memory:project_s2_api_impl
- memory:project_s5_board_ui_impl
- memory:project_features_backend_audit
- .cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md
- frontend/src/components/Board.tsx
- frontend/src/components/FeaturesBoard.tsx
- frontend/src/pages/FeaturesPage.tsx
- frontend/src/hooks/useFeatures.ts
- frontend/src/api.ts
outputs_produced:
- .cronos/pipeline/feature-detail-panel/analysis-report-feature-detail-panel.md
blockers: []
next_consumer: design
request: 'CC-v1 analyst phase for: SG2 FeatureDetail Panel + Board Wiring.


  Scout report: `.cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md`


  Scope:

  - `frontend/src/components/FeatureDetail.tsx` (new file)

  - `frontend/src/components/FeaturesBoard.tsx` — wire onOpen to write ?feature=<id>
  to URL

  - `frontend/src/pages/FeaturesPage.tsx` — mount FeatureDetail when ?feature param
  present

  - `frontend/src/components/Board.tsx` — fix shared-backlog card click to deep-link
  to ?feature=<id>


  The FeatureDetail panel must use the hooks from SG1 (useFeature, usePatchFeature,
  useProcessFeature, useSetRealize). Mirror the `Detail.tsx` + `Board.tsx:55-322`
  pattern for panel lifecycle, URL param management, and onClose behavior.'
has_ui: true
coverage_summary:
  searched:
  - frontend/src/components/Board.tsx (detail modal injection pattern lines 74-89
    and 280-321)
  - frontend/src/components/FeaturesBoard.tsx (dead onOpen handler lines 240-271)
  - frontend/src/pages/FeaturesPage.tsx (page structure and URL param management)
  - frontend/src/hooks/useFeatures.ts (existing hooks + SG1 additions confirmed present)
  - frontend/src/api.ts (feature API methods including SG1 getFeature/patchFeature)
  - .cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md
  excluded:
  - 'frontend/src/components/Detail.tsx: fully covered by scout report; not re-read'
  - 'backend/app/api/features.py: backend confirmed complete by scout; no changes
    needed'
  - 'frontend/src/types.ts: FeatureRead fields covered by scout report findings'
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: A FeatureDetail panel component renders feature information (title, feature_key
    badge, feature_state pill, brief) inside a Modal overlay with Esc-key and backdrop-click
    close behavior, mirroring the Detail.tsx modal pattern.
  acceptance_criteria:
  - Given a featureId prop, FeatureDetail fetches the feature via useFeature and renders
    inside a Modal wrapper
  - Pressing Escape or clicking the backdrop calls the onClose callback
  - The header displays feature title as prominent text, a feature_key badge (e.g.
    "ENG-123") when present, and a feature_state pill (backlog/processing/planned/waiting/done)
  - The brief field renders as read-only markdown content
  verifying_phase: review
  confidence: 0.95
- requirement_id: R2
  statement: FeatureDetail supports inline editing of title and brief via usePatchFeature,
    revealed by an edit button that opens a form overlay, with the submit button disabled
    while the mutation is in-flight.
  acceptance_criteria:
  - An edit button in the panel header opens a form overlay pre-populated with current
    title and brief values
  - Submitting the form calls patchFeature({featureId, body:{title, brief}}); on success
    the form closes and the panel data refreshes
  - The submit button is disabled (not hidden) while the mutation is pending
  - Cancelling the form discards changes and closes the overlay without any API call
  verifying_phase: review
  confidence: 0.9
- requirement_id: R3
  statement: FeatureDetail shows a Process button that triggers decomposition via
    useProcessFeature; the button is disabled when feature_state is already PROCESSING
    or DONE.
  acceptance_criteria:
  - Process button renders when feature_state is backlog, planned, or waiting
  - Process button is disabled (not hidden) when feature_state is processing or done
  - Clicking an enabled Process button calls processFeature(featureId); on success
    the panel reflects the updated feature_state
  - While the mutation is in-flight the button is disabled to prevent double-submission
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: FeatureDetail displays a visually distinct amber alert box containing
    the waiting_question text when the feature has a non-null waiting_question field.
  acceptance_criteria:
  - If feature.waiting_question is a non-empty string, an amber-styled callout box
    renders its text above the brief section
  - If feature.waiting_question is null, undefined, or an empty string, no amber box
    is rendered
  verifying_phase: review
  confidence: 0.95
- requirement_id: R5
  statement: FeatureDetail lists the feature's realizing_items in a read-only section
    with an unlink affordance per item that calls useSetRealize to remove the link.
  acceptance_criteria:
  - The realizing items section shows each TaskSummary in realizing_items with its
    title and state
  - If realizing_items is empty, a placeholder message ("No realizing tasks yet")
    is displayed
  - Each item has an unlink button that calls setRealize({featureId, body:{item_id,
    feature_id:null}}); on success the item disappears from the list
  - The unlink button is disabled while the mutation is in-flight
  verifying_phase: review
  confidence: 0.88
- requirement_id: R6
  statement: FeaturesBoard wires card click and Lane onOpen handlers to write ?feature=<id>
    to URL searchParams, replacing the current no-op handlers at lines 252 and 266.
  acceptance_criteria:
  - FeaturesBoard uses useSearchParams and defines setFeatureId that calls setSearchParams({feature:id},
    {replace:true})
  - Lane onOpen prop receives setFeatureId instead of the current no-op
  - Card onClick in the DragOverlay remains a no-op (dragging does not open the panel)
  - FeaturesBoard reads ?feature from searchParams and renders <FeatureDetail featureId={featureId}
    onClose={() => setFeatureId(null)} /> when featureId is non-null
  verifying_phase: test
  confidence: 0.95
- requirement_id: R7
  statement: FeaturesPage mounts FeatureDetail when the ?feature URL param is present,
    and removes the param when the panel is closed, in both ScopedFeaturesPage and
    GlobalFeaturesPage variants.
  acceptance_criteria:
  - ScopedFeaturesPage passes its searchParams ?feature value down or delegates FeatureDetail
    mounting to FeaturesBoard (which manages searchParams directly)
  - GlobalFeaturesPage does not conflict with the ?feature param (its own ?space param
    management is unaffected)
  - Closing the FeatureDetail panel removes ?feature from the URL without navigating
    away from the page
  verifying_phase: review
  confidence: 0.88
- requirement_id: R8
  statement: Board.tsx feature-backlog card click navigates to the Features page with
    ?feature=<id> so the FeatureDetail panel opens directly from the Tasks board.
  acceptance_criteria:
  - Clicking a feature-backlog card calls navigate(`/features?feature=${task.id}`)
    instead of the current navigate("/features")
  - The Tasks board shared-backlog onOpenTask handler is updated to the same deep-link
    pattern
  - For space-scoped views, the navigation includes the spaceId context if applicable
  verifying_phase: review
  confidence: 0.9
metrics:
  tool_calls: 17
  files_read: 6
  memory_hits: 4
---

## Summary

SG2 builds the FeatureDetail right-rail panel and wires it into both the Features board and the Tasks board shared backlog. The backend is fully ready (four endpoints: GET, PATCH edit, PATCH feature-state, POST process; FeatureRead schema with waiting_question merged 2026-06-08). SG1 (api-client-hooks) confirmed complete: `getFeature`, `patchFeature`, `processFeature`, `setRealize` API methods and `useFeature`, `usePatchFeature`, `useProcessFeature`, `useSetRealize` hooks are all present. SG2 scope is frontend-only: one new component (`FeatureDetail.tsx`) plus targeted wiring changes in three existing files. The panel follows the established Task Detail pattern from `Detail.tsx` + `Board.tsx` (Modal wrapper, URL searchParam lifecycle, Esc-close) with feature-specific sections substituted for task-specific ones.

## Scope

### In scope

- `frontend/src/components/FeatureDetail.tsx` — new modal panel component (useFeature fetch, title/brief display + inline edit, feature_state pill, feature_key badge, waiting_question amber box, Process button, realizing_items list with unlink affordance)
- `frontend/src/components/FeaturesBoard.tsx` — replace no-op `onOpen={() => {}}` and card `onClick={() => {}}` with live `setSearchParams` handlers; inject `<FeatureDetail />` modal at bottom of render
- `frontend/src/pages/FeaturesPage.tsx` — ensure `?feature` param lifecycle does not conflict with existing `?space` param; no structural changes required if FeaturesBoard owns the searchParam directly
- `frontend/src/components/Board.tsx` — fix feature-backlog card click to `navigate("/features?feature=<id>")` instead of `navigate("/features")`

### Out of scope

- Backend changes — all four feature endpoints are production-ready; no backend work needed
- Feature state transition UI beyond the Process button — drag-to-state-change is a separate workflow
- Adding new realizing tasks from within the panel — link affordance (adding) is deferred; only unlink is in scope
- Stats/Trace tabs — features do not have agent_mode/agent_model; those tabs do not apply
- ConversationStream / ChatInput — feature history is not in scope for this iteration

### Deferred

- Link (add) affordance in realizing_items: selecting a task to add as realizing item requires a task-search modal; deferred to a follow-up
- Feature state transition buttons (Planned, Done, Backlog): beyond Process, manual state transitions via the panel UI
- ConversationStream: if features accumulate agent conversation history, a conversation tab can be added

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | FeatureDetail modal panel renders feature info with close-on-Esc/backdrop |
| R2 | Inline edit of title and brief via usePatchFeature |
| R3 | Process button triggers decomposition via useProcessFeature |
| R4 | Amber waiting_question box when field is non-null |
| R5 | Realizing items list with per-item unlink via useSetRealize |
| R6 | FeaturesBoard wires onOpen + card click to ?feature=<id> URL param |
| R7 | FeaturesPage mounts FeatureDetail from ?feature param; removes on close |
| R8 | Board.tsx feature-backlog cards deep-link to /features?feature=<id> |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]`
array (the machine-readable source of truth). The body summary below mirrors them
in compact form for the human reader.

- R1 — Modal wraps the panel; Esc/backdrop closes; header has title, feature_key badge, feature_state pill; brief renders as markdown
- R2 — Edit button opens pre-populated form; submit calls patchFeature; button disabled in-flight; cancel discards
- R3 — Process button disabled when state=processing/done; enabled click calls processFeature; in-flight disables
- R4 — Amber box shown when waiting_question is non-empty; absent when null/empty
- R5 — Lists realizing_items with title+state; empty placeholder shown; unlink button per item calls setRealize(null)
- R6 — onOpen and card onClick call setSearchParams({feature:id}); FeatureDetail injected at bottom when ?feature present
- R7 — ?feature param lifecycle does not conflict with ?space; closing removes ?feature from URL
- R8 — Feature backlog card click navigates to /features?feature=<id> instead of /features

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML
`traceability[]` array. Downstream agents read the YAML directly; this section
exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | review | FeatureDetail modal panel renders feature info with close-on-Esc/backdrop |
| R2 | review | Inline edit of title and brief via usePatchFeature |
| R3 | test | Process button triggers decomposition via useProcessFeature |
| R4 | review | Amber waiting_question box when field is non-null |
| R5 | review | Realizing items list with per-item unlink via useSetRealize |
| R6 | test | FeaturesBoard wires onOpen + card click to ?feature=<id> URL param |
| R7 | review | FeaturesPage mounts FeatureDetail from ?feature param; removes on close |
| R8 | review | Board.tsx feature-backlog cards deep-link to /features?feature=<id> |

## Assumptions

- **SG1 hooks are present**: `useFeature`, `usePatchFeature`, `useProcessFeature`, `useSetRealize` confirmed in `frontend/src/hooks/useFeatures.ts`; `getFeature`, `patchFeature`, `processFeature`, `setRealize` confirmed in `frontend/src/api.ts`. No SG1 work needed.
- **FeaturesBoard owns the searchParam**: Following the `Board.tsx` pattern where the board component manages `?task` searchParam and injects `<Detail />`, FeaturesBoard will manage `?feature` and inject `<FeatureDetail />`. FeaturesPage does not need a parallel searchParam read.
- **waiting_question in FeatureRead is reliable**: memory:project_merge_2026_06_08 confirms the field was added in commit f02301b (2026-06-08); useFeature hook returns FeatureRead which includes this field.
- **has_ui=true rationale**: All eight requirements involve React component creation, JSX rendering, and user interaction through the browser UI.
- **Realizing items unlink only (not link)**: `useSetRealize` is called with `feature_id: null` to unlink. Adding new realizing tasks requires a task-search picker beyond this panel's scope; deferred per scope section.
- **Board.tsx navigate target is /features (not space-scoped)**: The current code navigates to `/features` (global features page). The fix navigates to `/features?feature=<id>`. Space-scoped navigation (`/spaces/<id>/features?feature=<id>`) would require passing spaceId through to Board; deferred given current Board.tsx structure.

## Open questions

- None. All referenced modules are confirmed present. Backend is complete. SG1 hooks are available.

## Next consumer brief

**For design agent:**

Read `traceability[]` first — 8 requirements, all frontend-only. `has_ui=true`.

Key design decisions:
1. **Component decomposition**: `FeatureDetail.tsx` will be the main component (~300-500 lines). Consider sub-components: `FeatureStateSection` (state pill + Process button), `RealizingItemsList` (R5), `WaitingQuestionBox` (R4). Mirror `Detail.tsx` section structure.
2. **FeaturesBoard searchParam ownership**: FeaturesBoard at lines 252+266 has dead no-ops that become live `setSearchParams` calls. FeaturesBoard adds `useSearchParams` + renders `<FeatureDetail />` at the JSX bottom (mirror `Board.tsx:318`). FeaturesPage likely needs no changes.
3. **Modal lifecycle**: Use existing `Modal` wrapper component (same as Detail.tsx uses). Esc handler via `useEffect` on `keydown`.
4. **Process button state-gating**: `feature_state` comes from `useFeature` result; disabled condition is `feature.feature_state === "processing" || feature.feature_state === "done" || isProcessing`.
5. **Board.tsx minimal change**: One line change at lines 308-309 — replace `navigate("/features")` with `navigate(\`/features?feature=${task.id}\`)`.

Risk: FeaturesBoard currently uses `useSearchParams` for `?space` in GlobalFeaturesPage but FeaturesBoard does not — confirm no collision before implementation.
