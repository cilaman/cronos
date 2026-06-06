---
cc_version: "1.0"
agent: pipeline-reviewer
slug: featurefix-board-ui--attempt1
phase: review
status: done
confidence: 0.9
inputs_used:
  - memory:project_s1_data_model_impl
  - memory:project_s2_api_impl
  - memory:project_s4_worker_decompose_impl
  - memory:project_s5_board_ui_impl
  - memory:project_arc_features_fixes_board_setup
  - memory:project_pipeline_reviewer_agent
  - memory:feedback_pipeline_narrow_k_coverage
  - memory:observation_worktree_main_vs_workspace
  - .cronos/pipeline/featurefix-board-ui/design-report-featurefix-board-ui.md
  - .cronos/pipeline/featurefix-board-ui/impl-report-featurefix-board-ui--i1.md
  - .cronos/pipeline/featurefix-board-ui/impl-report-featurefix-board-ui--i2.md
  - .cronos/pipeline/featurefix-board-ui/impl-report-featurefix-board-ui--i3.md
  - .cronos/pipeline/featurefix-board-ui/impl-report-featurefix-board-ui--i4.md
  - .cronos/pipeline/featurefix-board-ui/impl-report-featurefix-board-ui--i5.md
  - .cronos/pipeline/featurefix-board-ui/impl-report-featurefix-board-ui--i6.md
  - .cronos/pipeline/featurefix-board-ui/impl-report-featurefix-board-ui--i7.md
  - .cronos/pipeline/featurefix-board-ui/impl-report-featurefix-board-ui--i8.md
  - .cronos/pipeline/featurefix-board-ui/impl-report-featurefix-board-ui--i9.md
  - .cronos/pipeline/featurefix-board-ui/test-report-featurefix-board-ui.md
  - frontend/src/types.ts
  - frontend/src/api.ts
  - frontend/src/hooks/useFeatures.ts
  - frontend/src/components/Lane.tsx
  - frontend/src/components/Card.tsx
  - frontend/src/components/FeaturesBoard.tsx
  - frontend/src/components/Board.tsx
  - frontend/src/components/Sidebar.tsx
  - frontend/src/router.tsx
  - frontend/src/pages/FeaturesPage.tsx
outputs_produced:
  - .cronos/pipeline/featurefix-board-ui/review-report-featurefix-board-ui--attempt1.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 26
  files_read: 21
  memory_hits: 8
  diff_lines_reviewed: 1982
verdict: pass
attempt: 1
findings:
  - id: F1
    severity: low
    file: frontend/src/pages/FeaturesPage.tsx:11
    evidence: "`useState(() => readBoardSpaceFilter())` snapshots the persisted space-filter once at mount. If the user switches active space via sidebar without unmounting FeaturesPage, the board does not re-read the filter. BoardPage uses the same pattern, so this is consistent with the codebase, but a future cross-page space-context refactor should address both pages together."
    blocking: false
    suggested_action: "Track as follow-up: when an active-space React context is introduced (mentioned but absent per I6 finding), migrate both FeaturesPage and BoardPage to consume it so cross-page space switching is reactive."
  - id: F2
    severity: low
    file: frontend/src/components/Board.tsx:290
    evidence: "`{featureBacklog.length > 0 && (...)}` — the Features Backlog column is fully removed from the DOM when the backend returns an empty array. Users on a fresh space see no affordance pointing at the Features board; combined with the new sidebar Features link this is OK, but a zero-state header (\"No backlog features yet\") would aid discovery."
    blocking: false
    suggested_action: "Optional: render a small header-only stub even when empty, or rely on the sidebar Features link. Defer to UX review; no functional defect."
  - id: F3
    severity: low
    file: frontend/src/components/Card.tsx:557
    evidence: "`realized_by` items are rendered as raw task IDs prefixed `← {itemId}` because TaskSummary on the frontend stores IDs only (not titles). The feature-detail endpoint returns full TaskSummary objects in `realizing_items`, but the board's TaskSummary type uses `string[]`. Cards therefore show opaque IDs to users."
    blocking: false
    suggested_action: "Future iteration: extend FeatureBoard backend response to include title-resolved `realized_by_items` (or fetch on hover/expand). Out of scope for S5; doc agent should note this in the changelog as a known limitation."
  - id: F4
    severity: low
    file: frontend/src/types.ts:125
    evidence: "Design report body wrote `realizes[]` plural (\"clone parent-link chip pattern for each realizes[] entry\"), but I1 set `realizes?: string | null` (scalar) matching the backend (verified: feature/features-and-fixes backend/app/models.py:72 `realizes: str | None`). Implementation matches backend reality; the design's plural notation was imprecise."
    blocking: false
    suggested_action: "No code change required. If a future feature needs multi-realization, both backend and frontend types must change in lockstep. Doc agent should describe `realizes` as a single optional task-id pointer."
---

## Summary

S5 ships a 5-lane Features Kanban (`/features`, `/spaces/:spaceId/features`) alongside the existing Tasks board, with a shared read-only Backlog column on the Tasks board, sidebar `Kanban`→`Tasks` rename, and a new `Features` nav link. All 9 iterations report `status: done` and `validation_command_passed: true`. The observed_changed_set across impl reports is exactly equal to the union of `iterations[].scope_files[]` (16 files: 7 source, 9 spec — zero scope escape). Independent verification on `feature/features-and-fixes` shows `npx tsc --noEmit` exit 0 and `npx vitest run` 1071/1071 tests pass across 67 files. The test-report `gate_decision: fail` is a branch-confusion artifact (tester ran pytest against `main`, which lacks the S1-S4 backend foundation; the failing imports `FeatureState` and `branch_exists_on_origin` exist and pass on `feature/features-and-fixes`); re-running the named failing modules on the feature branch confirms 8/8 pass. All three top-severity design risks (R14 lane disjointness, R13 shared-Backlog outside DndContext, R4 triple-key invalidation) are mitigated and explicitly tested.

## Findings

- F1 (low, non-blocking) — FeaturesPage persisted-spaceId snapshot is not reactive to sidebar space switches; matches BoardPage pattern, future refactor.
- F2 (low, non-blocking) — Shared Backlog column is omitted entirely when backend returns empty; cosmetic discoverability nit.
- F3 (low, non-blocking) — `realized_by` chips render raw task IDs because TaskSummary stores IDs only; known limitation, doc-it-out.
- F4 (low, non-blocking) — Design body plural notation `realizes[]` differs from scalar implementation; implementation matches backend reality, doc clarification only.

## Verdict

pass. Scope is perfectly disciplined (zero escape), all 9 iterations are green, all design risk mitigations are present and tested, independent re-run on the feature branch confirms tsc-clean + 1071/1071 vitest-green; the test-report fail decision is an environment artifact (wrong branch) and does not indicate a real S5 defect.

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union (16 files across I1-I9).
- The implementation lives on `feature/features-and-fixes` (commit 299ab85); the workspace cwd is on `main` which does not have the S1-S4 backend foundation. Per memory `observation_worktree_main_vs_workspace`, this is an acceptable orchestrator pattern — impl agents pushed the diff to the feature branch directly.
- Test-report failures are 100% backend ImportError on symbols (`FeatureState`, `branch_exists_on_origin`) that exist on `feature/features-and-fixes` (verified) but not on `main` (verified). The 8 schema/realizes runtime failures cascade from the same missing model — they pass when re-run on the feature branch (verified: `pytest tests/test_feature_storage_schema.py tests/test_feature_realizes.py` exits with 8 passed in 3.56s on the feature-branch worktree).
- Frontend test counts in impl reports were re-verified by running the full vitest suite on the feature-branch worktree: 1071/1071 across 67 files (matches I9's claim).
- I8 vs I9 narrative discrepancy about who applied the Board.tsx onHideLane fix is presentational only — the committed code at Board.tsx:276 uses the I9-style wrapper cast `onHideLane ? (s) => onHideLane(s as TaskState) : undefined`, which is type-safe and consistent with the Board.tsx Props interface keeping `onHideLane?: (state: TaskState) => void`.

## Open questions

- None.

## Next consumer brief

For the doc agent: S5 adds a Features kanban at `/features` (and `/spaces/:spaceId/features`) with 5 lanes (Backlog/Processing/Planned/Waiting/Done) and DnD between legal feature-state transitions (mirrors backend `FEATURE_USER_TRANSITIONS`). Sidebar renames `Kanban`→`Tasks` and adds `Features`. The existing Tasks board gains a read-only Features Backlog column at the bottom; clicking a card navigates to /features. New cards types `feature` (emerald) and `fix` (rose) get badge styles plus `feature_key` chip, `issue_url` icon link, `→ realizes {id}` chip, and `← {id}` realized_by chips. Backend contract unchanged (S1-S4 already shipped on `feature/features-and-fixes`). Known limitations to surface in changelog: realized_by chips show raw task IDs (F3), shared Features Backlog column is hidden when empty (F2), `realizes` is a single optional pointer not an array (F4). No blockers; the test-report fail was an environment artifact (tester ran against main, missing S1-S4 backend imports) — clarify in the changelog or in a tester-fix follow-up that this S5 doc-phase advance is justified by independent feature-branch verification.
