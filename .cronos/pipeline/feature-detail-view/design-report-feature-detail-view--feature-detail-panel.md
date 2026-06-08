---
cc_version: '1.0'
agent: pipeline-architect
slug: feature-detail-view--feature-detail-panel
phase: design
status: done
confidence: 0.82
inputs_used:
- memory:project_features_backend_audit
- memory:project_s2_api_impl
- memory:project_s5_board_ui_impl
- memory:project_merge_2026_06_08
- memory:project_architecture_key_modules
- memory:project_pipeline_architect_agent
- memory:feedback_pipeline_narrow_k_coverage
- .cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md
- .cronos/pipeline/feature-detail-view/impl-report-feature-detail-view--i1.md
- frontend/src/api.ts
- frontend/src/hooks/useFeatures.ts
- frontend/src/components/FeaturesBoard.tsx
- frontend/src/components/Board.tsx
- frontend/src/components/Detail.tsx
- frontend/src/components/Lane.tsx
- frontend/src/pages/FeaturesPage.tsx
- frontend/src/types.ts
outputs_produced:
- .cronos/pipeline/feature-detail-view/design-report-feature-detail-view--feature-detail-panel.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/api.ts (current feature methods + missing surface)
  - frontend/src/hooks/useFeatures.ts (SG1-shipped hooks; runtime broken without api.ts
    surface)
  - frontend/src/components/FeaturesBoard.tsx (dead onOpen at line 252; clickHandler
    at 266)
  - frontend/src/components/Board.tsx (URL searchParams + setOpenId + Detail injection
    pattern at 318)
  - frontend/src/components/Board.tsx:303-313 (Features Backlog block — currently
    navigates to /features only)
  - frontend/src/components/Detail.tsx (modal/header/Esc/inline-edit reference pattern)
  - frontend/src/components/Lane.tsx (onOpen signature is (id: string) => void)
  - frontend/src/pages/FeaturesPage.tsx (Scoped + Global page wrappers — modal already
    injected via FeaturesBoard)
  - frontend/src/types.ts (FeatureRead absent on main; FeatureBoard at line 77)
  excluded:
  - backend/: surface complete per scout finding
  - frontend/src/pages/ routing: existing /features and /spaces/:spaceId/features
      routes carry the panel via searchParam; no router changes
  - test files: tester phase scope, not design
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: frontend
  scope_files:
  - frontend/src/types.ts
  - frontend/src/api.ts
  validation_command: cd frontend && npm run build
  max_diff_lines: 200
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/components/__tests__/FeatureDetail.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/FeatureDetail.test.tsx
  max_diff_lines: 600
  depends_on:
  - I1
- id: I3
  type: frontend
  scope_files:
  - frontend/src/components/FeaturesBoard.tsx
  - frontend/src/components/__tests__/FeaturesBoard.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/FeaturesBoard.test.tsx
  max_diff_lines: 300
  depends_on:
  - I2
- id: I4
  type: frontend
  scope_files:
  - frontend/src/components/Board.tsx
  - frontend/src/components/__tests__/Board.features-backlog.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Board.features-backlog.test.tsx
  max_diff_lines: 150
  depends_on:
  - I1
- id: I5
  type: frontend
  scope_files:
  - frontend/src/components/FeaturesBoard.tsx
  - frontend/src/pages/FeaturesPage.tsx
  validation_command: cd frontend && npm run build && npm test -- src/components/__tests__/FeaturesBoard.test.tsx
  max_diff_lines: 200
  depends_on:
  - I2
  - I3
risks:
- description: SG1's impl-report claims api.ts + types.ts were updated with FeatureRead,
    getFeature, patchFeature, processFeature, setRealize, but commit 781d634 only
    shipped useFeatures.ts changes — main is currently broken at runtime (hooks reference
    api.getFeature etc. that do not exist). Any tests that do not mock '../api' will
    surface this immediately.
  severity: high
  mitigation: 'I1 is mandatory and runs first (no deps). It restores the missing FeatureRead
    interface in types.ts and the four api.ts methods to match the exact shapes that
    useFeatures.ts already consumes (useFeature returns FeatureRead, usePatchFeature
    accepts {title?, brief?}, useSetRealize accepts {item_id, feature_id: string|null}).
    Validation command ''cd frontend && npm run build'' will fail loudly if any signature
    drifts from the hook call sites. Cite scout finding #2 and git log 781d634 in
    I1''s impl-report.'
- description: FeatureDetail.tsx is large (~400-600 LOC mirroring Detail.tsx). If
    the implementor copies too much of Detail.tsx verbatim (e.g., agent_mode/priority/hierarchy/stats/trace/files
    panels), the diff explodes and the panel will reference fields FeatureRead does
    not have, causing TypeScript build failures.
  severity: medium
  mitigation: 'I2''s scope_files is the new component plus its test only — no edits
    to Detail.tsx. The implementor brief must list the explicit OMIT set: agent_mode
    dropdown, priority dropdown, mode/model dropdown, HierarchySection, ParentPicker,
    DependencyPicker, StatsPanel, TracePanel, FilesPanel, ChatInput, ConversationStream,
    tabs. The component is single-pane (no tabs). max_diff_lines=600 budgets this
    but is a hard ceiling; if I2 exceeds, decompose into I2a (skeleton + brief + state
    badge) and I2b (Process button + realizing_items).'
- description: Triple-key invalidation contract (R4 per useFeatures.ts:6-12) requires
    every feature mutation to invalidate [features, spaceId], [board, spaceId], [spaces].
    usePatchFeature/useProcessFeature/useSetRealize already do this in the SG1 hooks
    via result.space_id. If FeatureDetail wires a button that calls api.* directly
    (bypassing the hooks), the shared Backlog on the Tasks board will desync silently.
  severity: medium
  mitigation: 'FeatureDetail.tsx MUST call mutations via the hooks usePatchFeature/useProcessFeature/useSetRealize
    — never api.patchFeature directly. I2''s test must assert at least one mutation
    onSuccess path invalidates [''feature'', id] AND the triple-key (mock useQueryClient.invalidateQueries
    and check calls). Document this rule in ## Next consumer brief.'
- description: Board.tsx:308-309 currently does navigate('/features') from the Features
    Backlog cards on the Tasks board. The new contract is navigate(`/features?feature=${task.id}`).
    If the implementor changes the onClick but leaves onOpenTask (or vice versa),
    the deep-link works for click but not for the Enter-key open path (Card forwards
    onOpenTask for keyboard activation per Lane.tsx:107).
  severity: low
  mitigation: I4's scope is exactly two callsites at Board.tsx:308 and 309 — both
    must change in the same iteration. Test asserts both Card prop callsites navigate
    to /features?feature={id}. max_diff_lines=150 forces minimality.
- description: FeaturesPage.tsx already injects <FeaturesBoard> for both Scoped and
    Global wrappers; the design puts the FeatureDetail mount inside FeaturesBoard
    (mirroring Board.tsx:318). If the implementor instead mounts FeatureDetail inside
    FeaturesPage.tsx, the global-page space-selector flow gets a second source of
    truth for ?feature= and may double-render.
  severity: low
  mitigation: 'I5 explicitly assigns mount ownership to FeaturesBoard.tsx (matching
    Board.tsx). FeaturesPage.tsx changes in I5 are limited to: confirm useSearchParams
    import is not duplicated, and no FeatureDetail import. Document this single-mount
    invariant in ## Next consumer brief.'
metrics:
  tool_calls: 12
  files_read: 11
  memory_hits: 7
  iterations_planned: 5
---

## Summary

This design wires a `FeatureDetail` modal panel for feature/fix cards by mirroring the existing Task `Detail.tsx` + `Board.tsx` URL-searchParam pattern. The plan is 5 frontend iterations forming a wide DAG (I1 root, I2/I4 in layer 1 parallel to each other, I3 in layer 2 depending on I2, I5 final integration depending on I2+I3). The critical risk surfaced by reading prior artifacts: SG1's impl-report claims it added `FeatureRead`, `getFeature`, `patchFeature`, `processFeature`, `setRealize` to `frontend/src/api.ts` and `frontend/src/types.ts`, but git commit `781d634` only shipped `useFeatures.ts` — main is currently broken at runtime. I1 closes that gap before any UI iteration touches the panel. The detail panel itself is single-pane (no tabs): title+brief inline edit, feature_state and feature_key badges, waiting_question amber box, Process button, and a read-only realizing_items list with per-row unlink via `useSetRealize`. The Tasks-board Features-Backlog cards (Board.tsx:308-309) are upgraded to deep-link `/features?feature={id}` so the panel opens directly instead of just navigating to the page.

## Components

### Data
- No data-layer changes. Backend (`backend/app/api/features.py:180-327`, `backend/app/models.py:199-225`) is complete and stable. `FeatureRead` already includes `waiting_question` (merged 2026-06-08 in commit f02301b).

### Backend
- No backend changes. All four endpoints (GET, PATCH edit, PATCH /feature-state, POST /process, PATCH /realize) are production-ready per scout finding #1.

### Frontend
- `frontend/src/types.ts` — restore `FeatureRead` interface (must mirror `backend/app/models.py:199-225`, including `waiting_question`, `feature_state`, `feature_key`, `realizes`, `issue_number`, `issue_url`, `proposed_issue_path`, and `realizing_items: TaskSummary[]`).
- `frontend/src/api.ts` — restore four feature methods: `getFeature(id)`, `patchFeature(id, {title?, brief?})`, `processFeature(id)`, `setRealize(featureId, {item_id, feature_id: string|null})`. Match call signatures already consumed by `useFeatures.ts:71-136`.
- `frontend/src/components/FeatureDetail.tsx` — NEW. Single-pane modal: header (close button, feature_state badge, feature_key badge), title+brief inline edit (via `usePatchFeature`), waiting_question amber box when present, Process button (calls `useProcessFeature.mutate(featureId)`; disabled when `feature_state === 'processing'`), Realizing-goals section listing `realizing_items[]` with per-row unlink button (`useSetRealize.mutate({featureId, body: {item_id, feature_id: null}})`). Reuses the same `Modal` wrapper, header layout primitives, and Esc-key handler as `Detail.tsx:830-845`.
- `frontend/src/components/FeaturesBoard.tsx` — replace dead `onOpen={() => {}}` (line 252) with `onOpen={setOpenFeatureId}`; replace dead `onClick={() => {}}` (line 266) with the same; add `useSearchParams` import; mount `<FeatureDetail featureId={openFeatureId} onClose={...} />` at the bottom of the component tree (mirroring `Board.tsx:318`).
- `frontend/src/pages/FeaturesPage.tsx` — verify it does not import `FeatureDetail` (single-mount invariant — panel is mounted inside `FeaturesBoard`, not the page).
- `frontend/src/components/Board.tsx:308-309` — change `onClick={() => navigate("/features")}` and `onOpenTask={() => navigate("/features")}` to `navigate(\`/features?feature=${task.id}\`)` so Tasks-board Features-Backlog cards deep-link to the detail panel.

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                                       | Validation                                                                                       |
|-----|----------|------------|------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| I1  | frontend | -          | frontend/src/types.ts, frontend/src/api.ts                                   | cd frontend && npm run build                                                                     |
| I2  | frontend | I1         | frontend/src/components/FeatureDetail.tsx, .../__tests__/FeatureDetail.test.tsx | cd frontend && npm test -- src/components/__tests__/FeatureDetail.test.tsx                       |
| I3  | frontend | I2         | frontend/src/components/FeaturesBoard.tsx, .../__tests__/FeaturesBoard.test.tsx | cd frontend && npm test -- src/components/__tests__/FeaturesBoard.test.tsx                       |
| I4  | frontend | I1         | frontend/src/components/Board.tsx, .../__tests__/Board.features-backlog.test.tsx | cd frontend && npm test -- src/components/__tests__/Board.features-backlog.test.tsx              |
| I5  | frontend | I2, I3     | frontend/src/components/FeaturesBoard.tsx, frontend/src/pages/FeaturesPage.tsx | cd frontend && npm run build && npm test -- src/components/__tests__/FeaturesBoard.test.tsx     |

DAG layers (Kahn order):
- Layer 0: I1 (the unblock)
- Layer 1: I2 (FeatureDetail), I4 (Board deep-link) — run in parallel
- Layer 2: I3 (FeaturesBoard wiring) — depends on I2 only
- Layer 3: I5 (integration cleanup + single-mount confirmation)

## Risks

| Risk                                                                                                                                                                                                  | Severity | Mitigation                                                                                                                                                                                                              |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| SG1 impl-report claims api.ts + types.ts shipped but git 781d634 only has useFeatures.ts; main is broken at runtime.                                                                                  | high     | I1 is mandatory layer-0 work; `npm run build` will hard-fail if any signature drifts from useFeatures.ts:71-136 call sites. Cite scout finding #2 in I1 impl-report.                                                      |
| FeatureDetail.tsx grows by accidental copy of Detail.tsx panels (agent_mode, hierarchy, stats, trace, files, ConversationStream, ChatInput).                                                          | medium   | I2 scope_files excludes Detail.tsx; max_diff_lines=600; brief lists explicit OMIT set. If exceeded, decompose I2 → I2a/I2b.                                                                                              |
| FeatureDetail bypasses triple-key invalidation by calling api.* directly instead of hooks.                                                                                                            | medium   | FeatureDetail must call usePatchFeature / useProcessFeature / useSetRealize; I2 test asserts ['feature', id] AND triple-key invalidation on mutation success.                                                            |
| Board.tsx:308-309 partial change (onClick fixed but onOpenTask not, or vice versa) leaves keyboard-open path broken.                                                                                  | low      | I4 scope is the two callsites at Board.tsx:308 and 309; test asserts both prop callsites navigate to `/features?feature={id}`.                                                                                            |
| FeatureDetail mounted in both FeaturesPage and FeaturesBoard → double render with ?feature= state.                                                                                                    | low      | I5 enforces single-mount-in-FeaturesBoard invariant; FeaturesPage.tsx must not import FeatureDetail.                                                                                                                     |

## Assumptions

- **SG1 ship gap is real, not a stale workspace.** Verified by `git log --oneline -10` (781d634 is HEAD, message "test: api-client-hooks — useFeature, ...") plus `Grep("getFeature|patchFeature|...", frontend/src/api.ts)` returning zero hits and `Grep("FeatureRead", frontend/src/types.ts)` returning zero hits. The useFeatures.ts hooks reference `api.getFeature`, `api.patchFeature`, `api.processFeature`, `api.setRealize` directly (lines 74, 92, 108, 130), and import `FeatureRead` from `../types` (line 3). Without I1, any component importing useFeatures (including the existing FeaturesBoard for `useFeatureBoard`) will refuse to type-check.
- **Modal-on-page with `?feature=<id>` URL searchparam** is the right mechanism — matches `Board.tsx:74-89, 318` exactly, is already in use across the codebase, and is what FeaturesPage.tsx implicitly expects (`useSearchParams` is already imported there for the `space` param).
- **No new top-level page or route is needed.** Existing routes `/features` and `/spaces/:spaceId/features` both end at FeaturesPage → FeaturesBoard; the panel is a sibling JSX block inside FeaturesBoard, not a route.
- **Single-pane, no tabs.** Detail.tsx's tab bar exists because tasks have stats/trace/files-specific content. FeatureRead carries none of those fields; tabs would create dead UI surface. Brief + state + realizing_items + waiting_question fit one scrollable pane.
- **realizing_items unlink-only, no linking.** Scout assumption #5 confirms linking is out of detail-panel scope; the design surfaces unlink (the destructive action that ends a relationship the user is currently viewing) but defers linking to the source-side picker on the realizing task.
- **The orchestrator brief's mention of `architect-report-feature-detail-panel.md` is a typo.** CC-v1 verifier expects `design-report-{slug}.md`. Using the canonical name; will not pass verifier otherwise.

## Open questions

- None blocking. Two minor questions for the implementor to resolve at impl time, neither blocks design:
  1. Should the Process button confirm-dialog before firing (S4 decomposition is expensive)? Recommend yes; matches Detail.tsx delete-button pattern at line 849.
  2. Should the waiting_question amber box include a reply input or be display-only? Recommend display-only for this iteration; reply UX is a follow-up scope (would require a new backend endpoint).

## Next consumer brief

**For implementors and orchestrator:**

- Read iterations[] from YAML — that is the source of truth. The `## Implementation plan` table is a human mirror.
- **I1 is non-negotiable and must complete before any panel-rendering iteration.** Without it, `npm run build` cannot pass anywhere downstream. The signatures I1 must produce are dictated by useFeatures.ts:71-136, not by guesswork: `getFeature(id: string): Promise<FeatureRead>`, `patchFeature(id: string, body: {title?: string; brief?: string}): Promise<FeatureRead>`, `processFeature(id: string): Promise<FeatureRead>`, `setRealize(featureId: string, body: {item_id: string; feature_id: string | null}): Promise<FeatureRead>`. The `FeatureRead` interface must include `id`, `space_id`, `state`, `feature_state`, `feature_key`, `realizes`, `issue_number`, `issue_url`, `proposed_issue_path`, `waiting_question`, `realizing_items: TaskSummary[]` plus the inherited Task fields enumerated in scout finding #1.
- **Cross-iteration invariant (load-bearing):** FeatureDetail.tsx must mutate ONLY via hooks (`usePatchFeature`, `useProcessFeature`, `useSetRealize`), never via `api.patchFeature` etc. directly. This preserves the R4 triple-key invalidation contract documented in `useFeatures.ts:6-12` (invalidates `[features, spaceId]`, `[board, spaceId]`, `[spaces]`) plus the per-feature key `[feature, id]`. Bypassing the hooks silently desyncs the Tasks-board Features-Backlog mirror.
- **Single-mount invariant:** `<FeatureDetail>` is rendered exactly once, inside `FeaturesBoard.tsx` (mirroring `Board.tsx:318`). `FeaturesPage.tsx` MUST NOT import or render it.
- **Shared URL param string:** the literal `feature` (lowercase) is the URL searchParam key used by FeaturesBoard, FeaturesPage (reading), and Board.tsx:308-309 (writing). All three must use the same key verbatim.
- See `## Risks` for the SG1 ship gap (high severity, mitigated by I1). The risk register, not the analysis report, is the authoritative list — there is no upstream analysis report (mode=standalone; scout report is the only upstream input).
