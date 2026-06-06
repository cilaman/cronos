---
cc_version: "1.0"
agent: pipeline-reviewer
slug: featurefix-github-issues--attempt2
phase: review
status: done
confidence: 0.9
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
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i5.md
  - .cronos/pipeline/featurefix-github-issues/test-report-featurefix-github-issues.md
  - .cronos/pipeline/featurefix-github-issues/review-report-featurefix-github-issues--attempt1.md
  - backend/app/main.py
  - backend/app/api/features.py
  - backend/app/feature_hooks.py
  - backend/tests/test_main_lifespan_configure_store.py
  - backend/tests/test_features_api_mirror_fire.py
outputs_produced:
  - .cronos/pipeline/featurefix-github-issues/review-report-featurefix-github-issues--attempt2.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 14
  files_read: 13
  memory_hits: 5
  diff_lines_reviewed: 323
verdict: pass
attempt: 2
findings:
  - id: F4
    severity: medium
    file: backend/app/feature_hooks.py:117
    evidence: "Hook still calls `proposed_path.write_text(md_content, encoding='utf-8')` synchronously inside an async function (no run_in_executor wrapping). With F2 now fixed (fire-and-forget via asyncio.create_task), this MD write is no longer on the request path, so the latency concern raised in attempt 1 has dissolved — the write executes in a background task. Documenting the residual sync IO would still be courteous but is no longer a regression risk."
    blocking: false
    suggested_action: "No code change required. F2's fire-and-forget fix in I5 removes the MD write from the request critical path. Optionally add a one-line docstring note on mirror_feature_to_github clarifying that the synchronous IO is intentionally tolerated because the entire coroutine runs as a background task."
  - id: F5
    severity: medium
    file: backend/app/git_issues.py:32
    evidence: "`gh_issue_upsert` still calls `detect_github_remote(space_dir)` (subprocess) on every invocation. Not cached. Same concern as attempt 1; severity unchanged."
    blocking: false
    suggested_action: "Optional micro-optimization: memoize detect_github_remote per space_dir on a short TTL. No correctness impact; not required for merge."
  - id: F6
    severity: medium
    file: backend/tests/test_feature_hooks_mirror.py:131
    evidence: "test_md_written_before_gh_upsert still uses `call_order.index('write_text')` / `call_order.index('upsert')`. Test was not tightened. Current implementation in feature_hooks.py is correct (R6 ordering holds), so the test is not actively failing or hiding a bug."
    blocking: false
    suggested_action: "Optional follow-up: tighten the assertion to `call_order[:2] == ['write_text', 'upsert']` or filter to the issues-directory MD path. Non-blocking, test scope only."
  - id: F7
    severity: low
    file: .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i1.md:25
    evidence: "I1 diff_lines_added=367 vs max_diff_lines=350 (4.8% over); I3 diff_lines_added=588 vs max_diff_lines=400 (47% over, concentrated in the 453-line test file). I5 diff_lines_added=291 vs max_diff_lines=250 (16% over). Overruns are concentrated in test files where coverage requirements cannot be compressed."
    blocking: false
    suggested_action: "No action — the cap is advisory. Document the overshoot in retro and consider raising the cap for hook-heavy iterations in future design templates."
  - id: F8
    severity: low
    file: backend/app/feature_hooks.py:153-157
    evidence: "WARNING log message for the `_task_store is None` branch reads `mirror_feature_to_github: _task_store not configured — set_issue_refs skipped for task=%s`. With F1 now fixed in production this branch should never fire under normal startup; the noise concern raised in attempt 1 is largely moot. Severity downgraded but the suggestion to include feature_key/reason still applies if/when this branch ever fires (e.g. tests that mutate _task_store)."
    blocking: false
    suggested_action: "Optional: include `reason` and `task.feature_key` in the warning. Non-blocking; F1's lifespan wiring fix means this branch is essentially unreachable in production."
---

## Summary

Attempt 2 closes the S3 review loop with `verdict: pass`. All three attempt-1 blockers have been resolved on `feature/features-and-fixes` at commit c41f7ac via the I5 review-fix iteration (a fifth design-allowed iteration explicitly scoped to address F1/F2). F1 (main.py wiring) is fixed by adding `from . import feature_hooks` and `feature_hooks.configure_store(task_store)` immediately after `app.state.store = task_store` in the lifespan startup (verified via `git show c41f7ac:backend/app/main.py` lines 37 and 378); F2 (fire-and-forget mirror) is fixed by converting `_fire_mirror` from `async def`+`await` to a synchronous `def` that schedules `asyncio.create_task(mirror_feature_to_github(...))` with an error-logging `add_done_callback` (verified at backend/app/api/features.py:60-89); F3 (tester branch targeting) is fixed externally by re-running the tester against feature/features-and-fixes@c41f7ac yielding gate_decision=pass, 2318p/0f/0e, 84.77% coverage. Scope conformance is clean: the S3 file set (10 files across S3's i1-i5 commits) matches the design's `scope_files[]` union exactly — no escape. Remaining findings (F4-F8) are all non-blocking and were non-blocking in attempt 1; F4 effectively dissolved when F2 was fixed. Verdict: pass — proceed to doc.

## Findings

- F1 (attempt 1, blocking): **resolved** in I5 (commit c41f7ac). main.py:378 now calls `feature_hooks.configure_store(task_store)` after `app.state.store = task_store`; smoke tests in test_main_lifespan_configure_store.py (6/6 passing) assert both static source presence and functional `fh._task_store is task_store` after lifespan startup. Not carried forward.
- F2 (attempt 1, blocking): **resolved** in I5 (commit c41f7ac). api/features.py:60-89 — `_fire_mirror` is now `def` (sync), schedules `asyncio.create_task(mirror_feature_to_github(...))`, attaches `add_done_callback(_log_mirror_error)` that logs exceptions at ERROR level. Tests `test_mirror_non_blocking_response_with_slow_mock` and `test_mirror_background_task_observably_executes` confirm the response returns in <150ms while the mirror sleeps 0.2s in background. Not carried forward.
- F3 (attempt 1, blocking): **resolved** by orchestrator re-targeting the tester at feature/features-and-fixes@c41f7ac. New test-report-featurefix-github-issues.md shows gate_decision=pass, 2318 passed / 0 failed / 0 errors / 84.77% coverage. Not carried forward.
- F4 (medium, non-blocking): synchronous MD write inside async hook — no longer on request path (F2 fix moved it to a background task). Carried forward at same id with evidence updated.
- F5 (medium, non-blocking): detect_github_remote not memoized — optional micro-opt; same as attempt 1. Carried forward.
- F6 (medium, non-blocking): R6 ordering test could be tightened — same as attempt 1; not addressed but doesn't hide a bug. Carried forward.
- F7 (low, non-blocking): max_diff_lines overruns concentrated in test files — same as attempt 1; advisory cap. Carried forward, with I5's 16% overshoot added to the evidence.
- F8 (low, non-blocking): _task_store=None WARNING could include reason+feature_key — now essentially unreachable in production thanks to F1 fix; severity unchanged but practical impact reduced. Carried forward.

## Verdict

pass. All three attempt-1 blockers resolved on commit c41f7ac (F1 + F2 in I5; F3 via tester re-run); five non-blocking carry-forwards (F4-F8) remain as quality nits and do not gate progression to doc. Scope contract honoured: observed file set (10 files) ⊆ design `scope_files[]` union across I1-I5.

## Assumptions

- The compound slug `featurefix-github-issues--attempt2` passed by the orchestrator is verbatim; `parent_slug = featurefix-github-issues`.
- The scope contract is the union of `scope_files[]` from design iterations I1-I5 (10 distinct files). I5 was added to the design after attempt 1 specifically to absorb the F1+F2 fixes — this is the architect's chosen path, not a scope escape.
- Test gate signal (gate_decision=pass, 2318p/0f/0e, 84.77% cov) is trusted as evidence of full-suite correctness because the test-report's `## Summary` explicitly names commit c41f7ac on feature/features-and-fixes and lists the resolved attempt-1 failure modes.
- File contents inspected via `git show c41f7ac:<path>` because the reviewer's worktree is on a different branch; same protocol as attempt 1.
- F8 severity remains `low` despite practical impact dropping after F1 fix — kept at low rather than downgraded further because the log line itself was not touched in I5.

## Open questions

- None.

## Next consumer brief

Doc agent (Phase 8 / pipeline-doc-sync): S3 ships the one-way GitHub issue mirror.

User-visible behaviour changes:
1. Creating a feature/fix task in a space with `git_repo_url` set now mirrors a GitHub issue (via `gh issue create`) and persists `issue_number` + `issue_url` on the Task. When `gh` is unavailable or the call fails, an MD fallback is written to `.cronos/issues/{task_id}.md` and `proposed_issue_path` is set instead.
2. Editing title or brief on a mirrored feature triggers a `gh issue edit` (with stale-issue fallback to a fresh MD file).
3. Moving a mirrored feature to FeatureState.DONE triggers `gh issue close` for the upstream issue.
4. All four mutating endpoints (POST /api/features, PATCH /{id}, PATCH /{id}/feature-state, POST /{id}/process) now schedule the mirror as a background asyncio task — API responses are no longer blocked on the gh subprocess.
5. Lifespan startup now wires `feature_hooks.configure_store(task_store)` so issue refs are persisted to disk in production.

CHANGELOG/README hooks: mention `.cronos/issues/{task_id}.md` fallback path and document that `gh` CLI authentication (e.g. via `gh auth login`) is a prerequisite for the live-mirror path.

No frontend/UI changes (has_ui=false per analysis report).
