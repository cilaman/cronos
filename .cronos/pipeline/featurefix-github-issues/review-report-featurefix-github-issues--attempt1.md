---
cc_version: "1.0"
agent: pipeline-reviewer
slug: featurefix-github-issues--attempt1
phase: review
status: done
confidence: 0.85
inputs_used:
  - memory:project_s1_data_model_impl
  - memory:project_s2_api_impl
  - memory:project_pipeline_reviewer_agent
  - memory:feedback_pipeline_narrow_k_coverage
  - memory:observation_worktree_main_vs_workspace
  - .cronos/pipeline/featurefix-github-issues/design-report-featurefix-github-issues.md
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i1.md
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i2.md
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i3.md
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i4.md
  - .cronos/pipeline/featurefix-github-issues/test-report-featurefix-github-issues.md
  - backend/app/git_issues.py
  - backend/app/feature_hooks.py
  - backend/app/storage.py
  - backend/app/api/features.py
  - backend/app/main.py
  - backend/app/models.py
  - backend/tests/test_git_issues.py
  - backend/tests/test_storage_set_issue_refs.py
  - backend/tests/test_feature_hooks_mirror.py
  - backend/tests/test_features_api_mirror_fire.py
outputs_produced:
  - .cronos/pipeline/featurefix-github-issues/review-report-featurefix-github-issues--attempt1.md
blockers: []
next_consumer: implementation
metrics:
  tool_calls: 22
  files_read: 16
  memory_hits: 5
  diff_lines_reviewed: 1887
verdict: needs_fix
attempt: 1
findings:
  - id: F1
    severity: high
    file: backend/app/main.py:374
    evidence: "Lifespan startup sets `app.state.store = task_store` at line 376 but never calls `feature_hooks.configure_store(task_store)`. Because `feature_hooks._task_store` stays `None` in production, the WARNING branch in mirror_feature_to_github fires on every call and `set_issue_refs` is NEVER invoked. Result: issue_number / issue_url / proposed_issue_path are not persisted to disk in a live deployment."
    blocking: true
    suggested_action: "Add `from . import feature_hooks` (or equivalent) and `feature_hooks.configure_store(task_store)` immediately after `app.state.store = task_store` in backend/app/main.py lifespan. This is a single-line wiring fix. Scope_files for the follow-up iteration must include backend/app/main.py and a smoke test (e.g. backend/tests/test_main_lifespan_configure_store.py) that asserts feature_hooks._task_store is the running TaskStore after startup."
  - id: F2
    severity: high
    file: backend/app/api/features.py:55-65
    evidence: "`async def _fire_mirror(...): await mirror_feature_to_github(...)` — direct await, not asyncio.create_task. I4's `test_mirror_slow_mock_blocks_response` confirms a 0.2s sleep in the mirror delays POST /api/features by >=0.1s. Design risk #6 ('60s subprocess timeout could block FastAPI scheduler under burst edits') was supposed to be mitigated by S2 making _fire_mirror fire-and-forget; that mitigation does NOT hold."
    blocking: true
    suggested_action: "Either (a) make _fire_mirror schedule the mirror via `asyncio.create_task(mirror_feature_to_github(...))` with error logging via add_done_callback (preferred — matches design assumption R12 / risk #6 mitigation), or (b) reopen the architecture decision and accept that mutating feature/fix endpoints can block up to 60s on the gh subprocess (then update analysis traceability + design risks). Option (a) is the minimal scope fix; it touches backend/app/api/features.py only and the I4 timing tests (test_features_api_mirror_fire.py) must be flipped to assert non-blocking behaviour."
  - id: F3
    severity: high
    file: .cronos/pipeline/featurefix-github-issues/test-report-featurefix-github-issues.md:13
    evidence: "gate_decision: fail — 8 failures + 6 collection errors, all of the form `ImportError: cannot import name 'FeatureState' from 'app.models'`. On the feature/features-and-fixes branch (commit aedd455) FeatureState IS exported from app.models (verified via `git show aedd455:backend/app/models.py`). On main FeatureState is absent. This is strong evidence the tester ran against main (or another tree without S1/S2 merged), not against the branch carrying S1+S2+S3. The failures are not S3 defects but a phase-orchestration error."
    blocking: true
    suggested_action: "Re-run the test gate explicitly checked out at commit aedd455 (feature/features-and-fixes head) or a worktree branched from it. Confirm: (i) all 6 collection errors disappear (test_feature_board / model / numbering / persistence / serialization / transitions collect cleanly because FeatureState is importable), (ii) the 4 test_feature_realizes failures and 4 test_feature_storage_schema failures resolve (these depend on S1 storage migrations also missing on main), (iii) the new S3 test files (test_git_issues, test_storage_set_issue_refs, test_feature_hooks_mirror, test_features_api_mirror_fire — 55 tests total) all pass. Until the tester runs against the correct tree, the gate signal for S3 is unusable."
  - id: F4
    severity: medium
    file: backend/app/feature_hooks.py:117
    evidence: "Hook executes `proposed_path.write_text(md_content, encoding='utf-8')` inside an async function with no run_in_executor wrapping. The MD write blocks the event loop for the duration of the disk write. Same applies to issues_dir.mkdir(parents=True, exist_ok=True) at line 113. Under normal load this is microseconds, but combined with the direct-await mirror in F2 it adds to the API latency budget."
    blocking: false
    suggested_action: "Acceptable for MVP; document the synchronous file IO in the hook docstring. If/when F2 is fixed to fire-and-forget, the MD write is no longer in the request path and this concern dissolves. No code change required at this iteration."
  - id: F5
    severity: medium
    file: backend/app/git_issues.py:32
    evidence: "`gh_issue_upsert` calls `detect_github_remote(space_dir)` (await async helper) on every invocation. Each mirror fire spawns `git remote -v` + parsing in subprocess (per app.git_ops.detect_github_remote). Under burst edits (the same risk #6 scenario) this adds another subprocess hop per fire. The result is also not cached across consecutive fires for the same space."
    blocking: false
    suggested_action: "Optionally memoize detect_github_remote per space_dir on a short TTL (e.g. functools.lru_cache via a wrapper, or a module-level dict keyed by space_dir). Not required for correctness — the gh CLI itself also performs a remote lookup — but a useful micro-optimisation when F2 is addressed."
  - id: F6
    severity: medium
    file: backend/tests/test_feature_hooks_mirror.py:131
    evidence: "test_md_written_before_gh_upsert patches `Path.write_text` globally and uses `call_order.index('write_text')` / `call_order.index('upsert')` — but `index()` returns the FIRST occurrence, so the test would still pass if there were a stray earlier write_text call from elsewhere. The R6 ordering claim is correct but the test would be more robust asserting `call_order == ['write_text', 'upsert']` (or filtering to the specific path)."
    blocking: false
    suggested_action: "Tighten the ordering assertion: filter call_order to only entries that pertain to the issues directory MD path, or assert `call_order[:2] == ['write_text', 'upsert']`. Non-blocking — current implementation is correct under the I3 hook body."
  - id: F7
    severity: low
    file: .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i1.md:25
    evidence: "metrics.diff_lines_added = 367 vs design max_diff_lines = 350 (4.8% over). I3 metrics.diff_lines_added = 588 vs max_diff_lines = 400 (47% over). The I3 overage is concentrated in the test file (453 lines), not production code (~135 lines)."
    blocking: false
    suggested_action: "No action — the cap is advisory; required test coverage for R6/R7/R8/R9/R11 cannot be compressed below the floor reached. Document the deliberate overshoot in any retro-class report; consider raising max_diff_lines in future feature_hooks-style iterations to 600 to reduce false alarms."
  - id: F8
    severity: low
    file: backend/app/feature_hooks.py:142
    evidence: "When `_task_store is None`, the WARNING log message says 'set_issue_refs skipped for task=%s' but does not include the reason or feature_key. In production the warning will fire on every mirror call (until F1 is fixed) and the log will be noisy and uninformative about which task wrote a stale proposed_issue_path."
    blocking: false
    suggested_action: "Append reason and feature_key to the warning: `log.warning('mirror_feature_to_github: _task_store not configured — set_issue_refs skipped for task=%s reason=%s feature_key=%s', task.id, reason, task.feature_key)`. Trivial diff against feature_hooks.py."
---

## Summary

S3 implements the one-way GitHub issue mirror with disciplined scope: the commit aedd455 touches exactly the 7 files in the design's `scope_files[]` union (git_issues.py, feature_hooks.py, storage.py, plus 4 test files). All 11 traceability requirements (R1-R11) have correct production-code shapes and unit-test coverage on the feature branch. However, three blocking findings prevent a pass: (F1) main.py does not call `feature_hooks.configure_store`, so `set_issue_refs` will never fire in production despite all tests passing in isolation — issue refs are silently dropped; (F2) `_fire_mirror` uses direct `await` instead of `asyncio.create_task`, so design risk #6's stated mitigation (fire-and-forget keeping API responses <100ms when gh sleeps 5s) is violated and mutating endpoints will block up to 60s on the gh subprocess; (F3) the test gate ran against the wrong branch (main lacks S1's FeatureState export) so its `fail` signal is uninterpretable as evidence about S3. Verdict: needs_fix — F1 and F2 are recoverable inside the existing pipeline budget (`attempt: 1` of 5); F3 requires the orchestrator to re-target the tester against feature/features-and-fixes.

## Findings

- F1 (high, blocking): main.py lifespan missing configure_store(task_store) wiring — issue refs not persisted in production.
- F2 (high, blocking): _fire_mirror uses direct await — design risk #6 mitigation violated, endpoints can block up to 60s.
- F3 (high, blocking): test report failures and collection errors trace to the tester running against the wrong branch (main, not feature/features-and-fixes); gate signal unusable.
- F4 (medium, non-blocking): synchronous file IO inside async hook — acceptable for MVP, dissolves when F2 fixed.
- F5 (medium, non-blocking): detect_github_remote re-invoked on every mirror fire — optional memoization.
- F6 (medium, non-blocking): R6 ordering test could be tightened.
- F7 (low, non-blocking): I1/I3 diff_lines_added overruns max_diff_lines advisory cap.
- F8 (low, non-blocking): WARNING log message in _task_store=None branch could include reason and feature_key.

## Verdict

needs_fix. Three blocking findings (F1 main.py wiring, F2 fire-and-forget mitigation, F3 tester ran against wrong branch) must be addressed before doc proceeds; all are recoverable inside the current `attempt: 1 of 5` review budget and do not require architect rescope.

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union (the 7 files listed in I1-I4). The CLAUDE.md modification visible in `git diff 45c5b92..aedd455` is from the intermediate S2 doc-sync commit (40c10b0), NOT from S3 (aedd455) — verified via `git show --stat aedd455`. No scope escape.
- The S3 work lives on branch `feature/features-and-fixes` (commit aedd455). The main branch and the current review workspace (cronos/2026-06-03-1631-pipeline-reviewer-features-fixes-s3-gith) both lack the S1+S2+S3 changes. File contents were inspected via `git show aedd455:<path>`.
- Test report failure interpretation (F3) rests on: (a) FeatureState IS present in backend/app/models.py at aedd455, (b) FeatureState is absent on main, (c) the tester reports `ImportError: cannot import name 'FeatureState'`. Therefore the tester ran against a tree without S1's models.py changes.
- Design risk #6 mitigation ("S2 already fires the mirror via _fire_mirror as an asyncio background task") was an assumption by the architect about S2. Inspection of api/features.py shows S2 did NOT implement fire-and-forget — _fire_mirror is a direct await. This is the root of F2.
- The narrow per-iteration pytest invocations all reported `validation_command_passed: true` per memory:feedback_pipeline_narrow_k_coverage convention (suppressing --cov-fail-under=60 via --override-ini="addopts="). The reviewer does not re-run the suite.

## Open questions

- None.

## Next consumer brief

Implementor (re-spawn with `attempt: 2`): address F1, F2, F3 in that order.

1. F1 fix: in backend/app/main.py lifespan (around line 374-376), import feature_hooks and call `feature_hooks.configure_store(task_store)` right after `app.state.store = task_store`. Add a smoke test asserting `feature_hooks._task_store is task_store` after lifespan startup. New scope_files: backend/app/main.py + backend/tests/test_main_lifespan_configure_store.py.

2. F2 fix: in backend/app/api/features.py, change `_fire_mirror` to schedule via `asyncio.create_task(mirror_feature_to_github(...))` and attach an error logger via `add_done_callback`. Update test_features_api_mirror_fire.py: flip `test_mirror_slow_mock_blocks_response` to assert response returns in <100ms while a slow mock runs in background; add a new test verifying the background task observably executes (e.g. via an asyncio.Event the mock sets). New scope_files: backend/app/api/features.py + backend/tests/test_features_api_mirror_fire.py.

3. F3 fix: orchestrator-level — re-spawn the tester (Phase 6) on a checkout/worktree at `feature/features-and-fixes` head (commit aedd455 or later). Confirm the new test-report shows the 6 collection errors and 8 schema/realizes failures resolve and the 55 new S3 tests (15 git_issues + 7 storage_set_issue_refs + 12 feature_hooks_mirror + 21 features_api_mirror_fire) all pass.

After F1+F2 land and F3's tester re-run reports gate_decision: pass, the next reviewer attempt should converge to pass.
