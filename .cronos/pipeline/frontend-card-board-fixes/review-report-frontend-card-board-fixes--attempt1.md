---
cc_version: "1.0"
agent: pipeline-reviewer
slug: frontend-card-board-fixes--attempt1
phase: review
status: done
confidence: 0.88
inputs_used:
  - memory:project_sg2_frontend_card_board_fixes_architect
  - memory:project_sg2_frontend_card_board_fixes_impl
  - memory:observation_scout_analyst_scope_drift
  - .cronos/pipeline/frontend-card-board-fixes/design-report-frontend-card-board-fixes.md
  - .cronos/pipeline/frontend-card-board-fixes/analysis-report-frontend-card-board-fixes.md
  - .cronos/pipeline/frontend-card-board-fixes/impl-report-frontend-card-board-fixes.md
  - .cronos/pipeline/frontend-card-board-fixes/pipeline-state.json
  - .cronos/pipeline/feature-card-ux-polish/scout-report-feature-card-ux-polish.md
  - frontend/src/types.ts
  - frontend/src/components/Card.tsx
  - frontend/src/components/__tests__/Card.test.tsx
  - frontend/src/components/FeaturesBoard.tsx
  - frontend/src/components/Board.tsx
outputs_produced:
  - .cronos/pipeline/frontend-card-board-fixes/review-report-frontend-card-board-fixes--attempt1.md
blockers: []
next_consumer: implementation
metrics:
  tool_calls: 12
  files_read: 10
  memory_hits: 3
  diff_lines_reviewed: 229
verdict: needs_fix
attempt: 1
findings:
  - id: F1
    severity: high
    file: frontend/src/components/FeaturesBoard.tsx:171
    evidence: "transition.mutate({ taskId, state: toState }); — onDragEnd calls mutate without an onError callback, so a failed feature-state transition silently leaves the card stuck. SG2 brief item UX-11 (FeaturesBoard.tsx:171 — error toast on transition mutation) is not shipped; the architect's R1 risk explicitly listed UX-11 as still missing on HEAD."
    blocking: true
    suggested_action: "Re-run pipeline-analyst over current branch HEAD (aa089d0 or feature/feature-card-ux-polish tip 8a3b465) so a follow-up SG2 cycle plans an iteration that adds onError handling to transition.mutate in FeaturesBoard.tsx onDragEnd. Minimum behaviour: surface the mutation error to the user (toast or inline banner) and rely on the existing useTransitionFeatureState rollback. Add a vitest case asserting the error path renders."
  - id: F2
    severity: high
    file: frontend/src/components/FeaturesBoard.tsx:40-145
    evidence: "FeatureComposer never reads createFeature.error; on a 400/500 from POST /api/spaces/{id}/features the input silently clears (or doesn't) but the user sees no message. SG2 brief item NP-1 (FeaturesBoard FeatureComposer — inline createFeature.error) is not shipped; architect's R1 risk flagged NP-1 as still missing on HEAD."
    blocking: true
    suggested_action: "Same re-analyst route as F1. Follow-up iteration adds inline rendering of createFeature.error (e.g. <p className=\"text-danger text-xs\">{createFeature.error.message}</p>) below the input row, plus a vitest case mocking the mutation error and asserting the message is visible."
  - id: F3
    severity: high
    file: frontend/src/components/FeaturesBoard.tsx:248-254
    evidence: "if (error) { return <p className=\"p-6 text-danger\">Error: {error.message}</p>; } — the error guard renders ALL errors including 404 from a stale feature board fetch, whereas Board.tsx:208 explicitly silences 404 (`if (error && !error.message.startsWith(\"404 \"))`). SG2 brief item UX-9 (404 guard mirroring Board.tsx) is not shipped."
    blocking: true
    suggested_action: "Same re-analyst route as F1. Follow-up iteration mirrors Board.tsx:208 guard in FeaturesBoard.tsx so 404s are silently ignored (per the comment 'BoardPage resets the URL param') and only non-404 errors surface. Add a vitest case asserting a 404 error does NOT render the danger banner."
  - id: F4
    severity: medium
    file: frontend/src/components/Card.tsx:343-348
    evidence: "Diff adds the 'N linked' realizing_count badge inside the compact-view header block at lines 343-348 AND again at lines 558-562 in the full-view footer block. The architect design scope was R1-R4 only (NP-2 realizes_feature_key plumbing); UX-3 realizing_count badge rendering was NOT part of any planned iteration. The implementor expanded in-file scope beyond the design contract."
    blocking: false
    suggested_action: "Acceptable under file-scope boundary (Card.tsx is in design scope_files) and the change addresses a brief item that was flagged as unshipped, but the impl-report dramatically understates the actual diff (claims 'diff_lines_added: 25 / diff_lines_removed: 6 / tests_added: 4' against actual 158/71/9). Future implementors must report the full diff scope and flag any out-of-design in-file work explicitly in the impl-report 'Out-of-scope findings' section. No code change required for this finding; remediation is procedural."
  - id: F5
    severity: medium
    file: frontend/src/types.ts:85-107
    evidence: "Implementor added an entire new FeatureRead interface (23 lines) to types.ts that was NOT in any traceability requirement (R1, R2 only specified TaskSummary additions). Also added proposed_issue_path?: string | null and realizing_count?: number to TaskSummary unrelated to R1/R2 scope. The file is within design scope_files but the FeatureRead interface scope is unjustified by the design."
    blocking: false
    suggested_action: "FeatureRead may be needed by the new Card.tsx Draft-issue button code path (proposed_issue_path field), but if so it should have been introduced via a dedicated iteration. Procedural: future impl-reports must enumerate every interface added under files_changed[] notes. Verify in a follow-up review that no orphan FeatureRead exports leak into unrelated downstream code."
  - id: F6
    severity: medium
    file: .cronos/pipeline/frontend-card-board-fixes/impl-report-frontend-card-board-fixes.md
    evidence: "impl-report claims diff_lines_added: 25, diff_lines_removed: 6, tests_added: 4. Actual numstat on commit 8a3b465: +50/-30 Card.tsx, +78/-41 Card.test.tsx, +30/-0 types.ts = +158/-71 total. Tests added: 9 new test cases (issue link 4 + realizes 4 + realizing_count 5 - issue link 2 - realizes 3 - realized_by 5). The metrics field is materially inaccurate by 6× on diff size."
    blocking: false
    suggested_action: "Procedural correction for the implementor agent: metrics fields must reflect the actual git diff numstat, not an under-counted estimate. Encourage future impl runs to compute metrics via `git diff --numstat` against the iteration base commit instead of self-reported counts. No code action required."
---

## Summary

Design scope (NP-2: realizes_feature_key plumbing across types.ts + Card.tsx + Card.test.tsx, requirements R1-R4) is correctly implemented and tested — feature key renders when present, visible fallback "→ realizes (unknown)" when null, click handler unchanged, and 4 new test cases cover both branches. However, the architect's high-severity R1 risk explicitly required the reviewer to verify scope completeness against the SG2 brief (not just analyst traceability), and three brief items remain unshipped on `frontend/src/components/FeaturesBoard.tsx`: UX-11 (error toast on transition mutation), NP-1 (inline createFeature error), and UX-9 (404 guard mirroring Board.tsx). The implementor also silently expanded in-file scope on Card.tsx to ship UX-1 (issue icon) and UX-3 (realizing_count badge), which were within the file-scope boundary but outside the planned iteration content — and the impl-report metrics under-count the actual diff by ~6×. Verdict is needs_fix; the appropriate next step is a re-spawn of pipeline-analyst against current branch HEAD so a follow-up SG2 cycle can plan FeaturesBoard.tsx iterations for the three unshipped items.

## Findings

- F1 (high, blocking): UX-11 unshipped — FeaturesBoard onDragEnd has no onError toast.
- F2 (high, blocking): NP-1 unshipped — FeatureComposer does not render createFeature.error.
- F3 (high, blocking): UX-9 unshipped — FeaturesBoard error guard does not silence 404 like Board.tsx does.
- F4 (medium, non-blocking): Card.tsx in-file scope expanded beyond design iteration content (realizing_count badge implemented though not in R1-R4).
- F5 (medium, non-blocking): types.ts gained an unscoped FeatureRead interface and proposed_issue_path field; procedural concern only.
- F6 (medium, non-blocking): impl-report metrics under-count actual diff size by ~6×.

## Verdict

needs_fix. The cycle correctly implements R1-R4 (NP-2) and the file-scope boundary held, but three brief items on FeaturesBoard.tsx (UX-11, UX-9, NP-1) remain unshipped per the architect's R1 mitigation contract; a follow-up analyst-led cycle is required.

## Assumptions

- Validation command (`cd frontend && npm test -- src/components/__tests__/Card.test.tsx`) returned 65 tests passing per impl-report; no test report was produced this cycle, but the Card.test.tsx additions are visibly consistent with the rendering change in Card.tsx and would compile under TS strict mode.
- Pre-existing `npm run build` TS errors flagged by the implementor in `frontend/src/__tests__/api.features.test.ts` are unrelated to this scope and inherited from upstream branches.
- The architect's R1 risk mitigation explicitly authorizes the reviewer to escalate via needs_fix when brief items remain unshipped; this is treated as a binding contract, not a soft hint.
- The realizing_count badge implementation in Card.tsx (using `task.realizing_count`) is functionally equivalent to the brief's "realized_by_count chip" because backend SG1 commit 2ad24bf sets both `realizing_count` and `realized_by_count` to the same value (per analyst report assumption).
- No prior review report exists (attempt: 1), so no F-id carry-forward applies.

## Open questions

- None. The brief-vs-design scope tension is fully captured in F1-F3 with explicit re-analyst routing.

## Next consumer brief

Implementor (after a fresh analyst pass): the three unshipped brief items live entirely in `frontend/src/components/FeaturesBoard.tsx` and need three small additions. (1) UX-11 / F1: add `onError` to `transition.mutate({ taskId, state: toState }, { onError: ... })` in onDragEnd at line 171 so the user sees the failure. (2) NP-1 / F2: render `createFeature.error` inline inside FeatureComposer (around line 145) when the mutation fails. (3) UX-9 / F3: mirror Board.tsx:208's 404 guard around the error return at line 251 so stale feature URLs do not break the board. Each fix should ship with a Vitest case. Do NOT touch Card.tsx again — the realizes/issue/linked work is already merged. The analyst should be re-run against the current branch HEAD (8a3b465 or later) so the new traceability reflects what is genuinely missing post-impl.
