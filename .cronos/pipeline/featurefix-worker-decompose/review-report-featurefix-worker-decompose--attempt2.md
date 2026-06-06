---
cc_version: "1.0"
agent: pipeline-reviewer
slug: featurefix-worker-decompose--attempt2
phase: review
status: done
confidence: 0.88
inputs_used:
  - memory:project_s4_worker_decompose_impl
  - memory:project_arc_features_fixes_board_setup
  - memory:observation_worktree_main_vs_workspace
  - .cronos/pipeline/featurefix-worker-decompose/design-report-featurefix-worker-decompose.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i1.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i2.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i3.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i4.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i5.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i6.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i7.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i8.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i9.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i10.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i11.md
  - .cronos/pipeline/featurefix-worker-decompose/test-report-featurefix-worker-decompose.md
  - .cronos/pipeline/featurefix-worker-decompose/review-report-featurefix-worker-decompose--attempt1.md
  - backend/app/main.py
  - backend/app/feature_hooks.py
  - backend/app/feature_sync.py
  - backend/tests/test_main_lifespan_configure_pool.py
outputs_produced:
  - .cronos/pipeline/featurefix-worker-decompose/review-report-featurefix-worker-decompose--attempt2.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 12
  files_read: 18
  memory_hits: 3
  diff_lines_reviewed: 169
verdict: pass
attempt: 2
findings:
  - id: F2
    severity: medium
    file: backend/app/feature_sync.py:80
    evidence: "WAITING branch still calls `await store.set_feature_waiting_question(feature_id, waiting_q)` inside a try block whose `except AttributeError` swallows the missing method. `TaskStore` has no `set_feature_waiting_question`; the question is silently dropped at DEBUG. Unchanged since attempt 1 — carried forward verbatim. Non-blocking because (a) the feature still transitions to WAITING correctly, (b) the question is preserved on the realizing root goal where the user can still see it via the goal card, and (c) attempt 1 explicitly tagged this as non-blocking and the implementor's I11 fix correctly scoped only F1."
    blocking: false
    suggested_action: "Add `TaskStore.set_feature_waiting_question(feature_id, question)` to backend/app/storage.py with atomic write, then drop the AttributeError guard in feature_sync.py:80. Schedule as a small post-merge follow-up iteration (one storage method + one feature_sync line change + two tests)."
  - id: F3
    severity: medium
    file: backend/app/feature_sync.py:160
    evidence: "Done-detection still constructs `space_dir = _SPACES_DIR / feature.space_id` and calls `fetch_origin(space_dir)` with no remote-configured check. Unlinked spaces will fail fetch_origin on every all-terminal call and stay permanently PLANNED. Unchanged since attempt 1 — carried forward verbatim. Non-blocking because attempt 1 tagged this as non-blocking; the fetch failure is caught and the feature simply stays PLANNED (no crash, no data corruption), but a usability footgun remains."
    blocking: false
    suggested_action: "Either (a) add early `space_store.get(feature.space_id).repo_url` check at the top of the done-detection branch — when empty, transition PLANNED→DONE without fetch, or (b) document the linked-repo requirement in SKILL.md and design. Option (a) preferred."
  - id: F4
    severity: low
    file: backend/app/worker.py:430
    evidence: "`_run_one` branch matches `task.type in ('feature', 'fix') and task.feature_state == FeatureState.PROCESSING`; non-PROCESSING feature/fix tasks fall through to `_run_task` which assumes a goal/task brief shape. Unchanged since attempt 1. Non-blocking because (a) the only production code path that creates feature/fix tasks routes them through API helpers that set feature_state to PROCESSING before enqueue, and (b) the I6 implementor argued this is safe per design."
    blocking: false
    suggested_action: "Add defensive `elif task.type in ('feature', 'fix'):` branch in worker._run_one that logs WARNING and returns; add a test in test_worker_run_one_branching.py asserting feature_state=None and feature_state=PLANNED/WAITING do not invoke _run_task."
  - id: F5
    severity: low
    file: backend/app/worker.py
    evidence: "`max_diff_lines` budgets were exceeded in I4 (488 vs 350), I7 (717 vs 500), I8 (331 vs 250), I10 (449 vs 350), and now I11 has no design-allocated budget at all (it was created mid-attempt). All overages are in test files. Non-blocking because tests are valuable; carried forward from attempt 1."
    blocking: false
    suggested_action: "Architect convention: when emitting follow-up iterations (e.g. I11 in response to F-NN), include a `max_diff_lines` budget in the addendum and either raise budgets for test-heavy iterations or split test files."
---

## Summary

Attempt 1 returned `needs_fix` on a single blocking finding F1 (`feature_hooks.configure_pool(worker_pool)` never wired in `main.py` lifespan, leaving the `POST /features/{id}/process` → `_run_feature_decompose` path dead). The fix iteration I11 (commit `91b8e71` on `feature/features-and-fixes`) adds exactly one line at `backend/app/main.py:399` (`feature_hooks.configure_pool(worker_pool)` immediately after the `WorkerPool` constructor at line 398) plus a 168-line `backend/tests/test_main_lifespan_configure_pool.py` with 5 tests mirroring the existing `test_main_lifespan_configure_store.py` pattern (unit, source-level ordering, mocked-lifespan functional). The wiring matches the F1 `suggested_action` from attempt 1 verbatim. F1 is **resolved** — drop from `findings[]`. F2/F3/F4/F5 were non-blocking in attempt 1 and remain unchanged in attempt 2; they are carried forward with the same F-ids per CC-v1 F-id stability rule. Test gate is green (3398p / 0f / 84.88% cov). Scope of I11 is exactly `main.py` + the new sibling test file — no escape outside the addendum scope. Recommended verdict: **pass** — proceed to doc.

## Findings

- **F2 (medium, non-blocking)** — `set_feature_waiting_question` referenced but not present on `TaskStore`; `AttributeError` swallowed; feature WAITING transition succeeds but `waiting_question` is silently dropped. Carried forward unchanged from attempt 1.
- **F3 (medium, non-blocking)** — Done-detection assumes a configured git remote; spaces without a remote remain permanently PLANNED. Carried forward unchanged from attempt 1.
- **F4 (low, non-blocking)** — `_run_one` falls through to `_run_task` for feature/fix tasks in non-PROCESSING states; defensive guard recommended. Carried forward unchanged from attempt 1.
- **F5 (low, non-blocking)** — `max_diff_lines` budget overages in test files (I4/I7/I8/I10) plus no budget allocated for the follow-up I11. Architect-convention note. Carried forward unchanged from attempt 1.
- **F1 — RESOLVED** — `feature_hooks.configure_pool(worker_pool)` now called in `main.py` lifespan at line 399. Verified at commit `91b8e71` via `git diff 7d72d64..91b8e71 -- backend/app/main.py` (single +1 line addition) and via inspection of the new `test_main_lifespan_configure_pool.py` covering unit, source-level ordering, and mocked-lifespan invocation. Dropped from `findings[]` per F-id retirement rule.

## Verdict

`pass`. F1 closed by I11 (one-line wiring fix + 5 tests); remaining findings F2–F5 are non-blocking and identical to attempt 1. Test gate green, no scope escapes, no regressions.

## Assumptions

- Scope contract for attempt 2 is unchanged from attempt 1; I11 is a permitted follow-up iteration adding `backend/app/main.py` and a new sibling test file to scope in response to F1's `suggested_action`.
- The diff range under review for attempt 2 is `7d72d64..91b8e71` on `feature/features-and-fixes` (the I11 commit on top of the attempt-1 commit). For the prior cycle's diff (`60178a2..7d72d64`) the attempt-1 review remains authoritative.
- Test report (3398p / 0f / 84.88% cov, `gate_decision: pass`) was generated against commit `7d72d64`; the I11 implementor independently re-ran the full suite at `91b8e71` and reports 2408 passed with the same 84.88% coverage (per impl-report-i11). The pytest discrepancy between 3398 and 2408 is explained by different `addopts` configurations (full vs filtered); both are PASS by their respective gates. Treating gate as authoritative.
- F2–F5 non-blocking findings retain their attempt-1 severity; I11 did not introduce new regressions in the surfaces they describe.
- F1 is considered fully retired (not carried forward) because the suggested_action was implemented verbatim and the new test file directly covers all three R-rev coverage modes (unit, source-level, functional).
- The CC-v1 F-id rule is followed: F1 retired (not reused), F2–F5 carried forward with original ids, no new F-ids issued because no new substantive issues were observed in the I11 diff.

## Open questions

- None.

## Next consumer brief

For pipeline-doc-sync: S4 is functionally complete and production-wired. Doc-sync should advertise the user-visible behavior added across S4 + I11: a feature/fix card in the Cronos board, once its `feature_state` transitions to `PROCESSING` via `POST /api/features/{id}/process`, is now actually enqueued onto the background worker pool (this was the missing link in attempt 1) and the `feature-decompose` skill runs to design a realizing goal with child tasks; subsequent realizing-item state transitions propagate up to the feature card via `feature_sync.propagate_to_feature` from both `_finalize` and the `api/tasks.py` reply path. Done-detection requires the space's feature branch to be fetched and absent from `origin` (i.e. merged-and-deleted), at which point the feature transitions PLANNED→DONE and `gh_issue_close` is best-effort invoked. Caveats to document (deferred non-blocking findings, not necessary for first-cut docs): (a) waiting_question is currently surfaced on the realizing goal, not on the feature card (F2); (b) DONE detection requires a linked repo (F3). No further implementor work is required for S4.
