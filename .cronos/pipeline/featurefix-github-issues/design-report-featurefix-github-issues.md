---
cc_version: '1.0'
agent: pipeline-architect
slug: featurefix-github-issues
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:project_s1_data_model_impl
- memory:project_s2_api_impl
- memory:project_architecture_key_modules
- memory:project_pipeline_foundation_merged
- memory:project_pipeline_schemas
- .cronos/pipeline/featurefix-github-issues/request.md
- .cronos/pipeline/featurefix-github-issues/scout-report-featurefix-github-issues.md
- .cronos/pipeline/featurefix-github-issues/analysis-report-featurefix-github-issues.md
- backend/app/git_ops.py
- backend/app/autopilot_pr.py
- backend/app/storage.py
- backend/app/pipeline/schemas/design.schema.yaml
outputs_produced:
- .cronos/pipeline/featurefix-github-issues/design-report-featurefix-github-issues.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/git_ops.py
  - backend/app/autopilot_pr.py
  - backend/app/storage.py
  - backend/app/pipeline/schemas/design.schema.yaml
  excluded:
  - 'frontend/: has_ui=false; S3 has no UI surface'
  - 'backend/app/worker.py: closure colocated in feature_hooks per analysis decision
    (no worker.py edit)'
  - 'backend/app/api/features.py structural changes: S2 already wired _fire_mirror
    at four sites (R10 review-only)'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/git_issues.py
  - backend/tests/test_git_issues.py
  validation_command: cd backend && pytest tests/test_git_issues.py -v
  max_diff_lines: 350
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/storage.py
  - backend/tests/test_storage_set_issue_refs.py
  validation_command: cd backend && pytest tests/test_storage_set_issue_refs.py -v
  max_diff_lines: 200
  depends_on: []
- id: I3
  type: backend
  scope_files:
  - backend/app/feature_hooks.py
  - backend/tests/test_feature_hooks_mirror.py
  validation_command: cd backend && pytest tests/test_feature_hooks_mirror.py -v
  max_diff_lines: 400
  depends_on:
  - I1
  - I2
- id: I4
  type: backend
  scope_files:
  - backend/tests/test_features_api_mirror_fire.py
  validation_command: cd backend && pytest tests/test_features_api_mirror_fire.py
    -v
  max_diff_lines: 250
  depends_on:
  - I3
- id: I5
  type: backend
  scope_files:
  - backend/app/main.py
  - backend/app/api/features.py
  - backend/tests/test_main_lifespan_configure_store.py
  - backend/tests/test_features_api_mirror_fire.py
  validation_command: cd backend && pytest tests/test_main_lifespan_configure_store.py
    tests/test_features_api_mirror_fire.py -v --override-ini="addopts="
  max_diff_lines: 250
  depends_on:
  - I3
  - I4
  notes: |
    Review-fix iteration (added after review-report-featurefix-github-issues--attempt1
    returned verdict=needs_fix). Addresses two blocking findings:

    - F1 (main.py:374 wiring): in the FastAPI lifespan, after
      `app.state.store = task_store`, call `feature_hooks.configure_store(task_store)`
      so `_task_store` is set in production. Add smoke test asserting
      `feature_hooks._task_store is task_store` after lifespan startup.

    - F2 (api/features.py:55-65 _fire_mirror): replace direct `await
      mirror_feature_to_github(...)` with `asyncio.create_task(...)` and attach an
      `add_done_callback` that logs any exception via the module logger. Mutating
      feature/fix endpoints must return without awaiting the mirror coroutine
      (design risk #6 mitigation). Update test_features_api_mirror_fire.py: the
      existing `test_mirror_slow_mock_blocks_response` (which asserts blocking)
      must be flipped to assert non-blocking — API response returns in <100ms
      while a slow mock (asyncio.sleep ≥0.2s) runs in background. Add a test
      verifying the background task observably executes (e.g. via an
      asyncio.Event the mock sets before returning).

    F3 from the review report is an orchestrator-level concern (re-target the
    tester against feature/features-and-fixes) — not implementor scope.
risks:
- description: gh issue create stdout format may vary across gh CLI versions (URL-only
    vs. with leading text); brittle URL parsing could silently return None and force
    a fallback even on success.
  severity: medium
  mitigation: I1 implementation MUST parse stdout with a permissive regex r'https?://[^\s]+/issues/(\d+)'
    against every line (not just the last), and unit tests in I1 MUST cover both URL-only
    and multi-line stdout shapes via mocked create_subprocess_exec.
- description: MD-write-before-gh ordering (R6) is easy to invert during refactor;
    if gh is called first the fallback may be skipped on transient timeout, violating
    R6 acceptance criterion.
  severity: medium
  mitigation: I3 test_feature_hooks_mirror.py MUST include an explicit ordering test
    (patch both Path.write_text and git_issues.gh_issue_upsert, assert write_text
    call comes first via mock call_args_list). Code review (R6/R8 verifying_phase=review)
    confirms inside the hook body.
- description: Swallowing all gh exceptions inside the hook can mask real errors (e.g.,
    a malformed Task) and produce silent data loss without an audit trail.
  severity: medium
  mitigation: I3 hook body MUST emit log.warning with task.id + reason on every caught
    exception, and tests MUST assert via caplog that exceptions produce a WARNING
    record. R8 is a review-phase requirement; reviewer will check that try/except
    is bounded to the gh + write region, not the entire function.
- description: Stale issue_number scenario (R11) — when gh issue edit returns non-zero,
    hook clears issue_number and persists proposed_issue_path; next edit will create
    a NEW issue, leaving the stale one open on GitHub forever.
  severity: low
  mitigation: Accepted per request scope (one-way mirror; no two-way reconciliation).
    I1 test MUST assert (None, None) return on rc!=0; I3 test MUST assert that set_issue_refs
    is then called with issue_number=None and proposed_issue_path=str(path). The 'orphan
    upstream issue' tradeoff is documented in the hook docstring.
- description: feature_hooks.py imports storage.TaskStore (for set_issue_refs); the
    global store singleton resolution differs between worker and FastAPI request contexts
    and could create an import cycle.
  severity: low
  mitigation: I3 MUST receive the store via the call-site parameter (already part
    of the S2 _fire_mirror signature per analysis R10) — not via a module-level import
    of a singleton. Test in I3 uses an in-memory TaskStore fixture passed as a constructor
    arg to confirm no global lookup.
- description: 60-second subprocess timeout on every mirror fire can block the FastAPI
    event loop's task scheduler under burst edits; if a user renames a feature 10
    times in 30s the worker thread could backlog.
  severity: low
  mitigation: S2 already fires the mirror via _fire_mirror as an asyncio background
    task (analysis confirms fire-and-forget). I4 MUST include a test that POST /api/features
    returns within 100ms even when gh_issue_upsert is monkeypatched to sleep 5s, confirming
    the API response path is not awaited on the gh call.
metrics:
  tool_calls: 9
  files_read: 8
  memory_hits: 5
  iterations_planned: 4
---

## Summary

S3 implements one-way GitHub issue mirroring for feature/fix tasks via three additive surfaces and one cross-cutting test. The plan is split into four iterations: I1 builds the new `git_issues.py` module (gh_issue_upsert + gh_issue_close + reused detect_github_remote import) with its unit tests; I2 adds `set_issue_refs` to `storage.TaskStore` as a near-verbatim copy of `set_pr_refs`; I3 fills the `mirror_feature_to_github` hook body in `feature_hooks.py` (MD-fallback-first ordering, gh call, persistence, conditional closure on state_change+DONE); I4 adds an end-to-end API test confirming the four `_fire_mirror` call sites in `api/features.py` invoke the hook with the correct reason string and that the API response is not blocked on the gh subprocess. I1 and I2 are independent (group 0); I3 depends on both; I4 depends on I3.

## Components

### Data
- `backend/app/storage.py` — extends `TaskStore` with a single new mutator `set_issue_refs(task_id, *, issue_number, issue_url, proposed_issue_path) -> Task`, modelled line-for-line on `set_pr_refs` (storage.py:802-824). Acquires `self._lock`, raises `TaskNotFound`, calls `model_copy` with `updated_at=datetime.now(tz=UTC)`, `atomic_write`, `_reindex_locked`.

### Backend
- `backend/app/git_issues.py` (new) — `gh_issue_upsert(space_dir, *, title, body, labels, issue_number) -> tuple[int|None, str|None]` and `gh_issue_close(space_dir, issue_number) -> bool`. Both guard via `shutil.which("gh")`, use `asyncio.create_subprocess_exec`, body via stdin bytes, 60s `asyncio.wait_for` timeout with `proc.kill()` + `await proc.wait()`, catch `FileNotFoundError`. URL extraction via permissive regex `r'https?://[^\s]+/issues/(\d+)'`. Imports `detect_github_remote` from `app.git_ops` (no reimplementation per R4).
- `backend/app/feature_hooks.py` — replaces the S2 no-op stub body of `mirror_feature_to_github`. Order: (1) early-return if `space.git_repo_url is None` OR `task.type` not in `("feature","fix")`; (2) `mkdir` `.cronos/issues/`; (3) write MD fallback to `.cronos/issues/{task.id}.md`; (4) call `gh_issue_upsert`; (5) call `set_issue_refs` with either `(issue_num, issue_url, None)` on gh success or `(None, None, str(proposed_path))` on gh None; (6) if `reason=="state_change"` AND `task.feature_state == FeatureState.DONE` AND `task.issue_number is not None`, await `gh_issue_close`. One broad `try/except` wraps the whole body; always returns `None`.
- `backend/app/api/features.py` — NO code edits in S3. The four `_fire_mirror` call sites are already wired by S2 (memory:project_s2_api_impl, analysis R10 = review-phase only). I4 adds tests confirming the wiring is correct.

### Frontend
<!-- Omitted: has_ui=false per analysis report; S3 has no UI surface. -->

## Implementation plan

| ID  | Type    | Depends on | Scope files (abridged)                                                 | Validation                                                       |
|-----|---------|------------|------------------------------------------------------------------------|------------------------------------------------------------------|
| I1  | backend | -          | backend/app/git_issues.py, backend/tests/test_git_issues.py            | cd backend && pytest tests/test_git_issues.py -v                 |
| I2  | backend | -          | backend/app/storage.py, backend/tests/test_storage_set_issue_refs.py   | cd backend && pytest tests/test_storage_set_issue_refs.py -v     |
| I3  | backend | I1, I2     | backend/app/feature_hooks.py, backend/tests/test_feature_hooks_mirror.py | cd backend && pytest tests/test_feature_hooks_mirror.py -v       |
| I4  | backend | I3         | backend/tests/test_features_api_mirror_fire.py                         | cd backend && pytest tests/test_features_api_mirror_fire.py -v   |

### Requirement → iteration coverage

| R#  | Iteration(s)   | Verifying phase | Note                                                                                         |
|-----|----------------|-----------------|----------------------------------------------------------------------------------------------|
| R1  | I1             | test            | gh_issue_upsert create/edit branching; (None, None) on rc!=0; shutil.which guard             |
| R2  | I1             | review          | asyncio.create_subprocess_exec + stdin body + 60s timeout + FileNotFoundError caught         |
| R3  | I1             | test            | gh_issue_close returns bool; never raises                                                    |
| R4  | I1             | review          | `from app.git_ops import detect_github_remote` (single import line, no reimplementation)     |
| R5  | I2             | test            | set_issue_refs mirrors set_pr_refs exactly                                                   |
| R6  | I3             | test            | MD write strictly before gh call; set_issue_refs with correct args per branch                |
| R7  | I3             | test            | gh_issue_close fires only when reason=state_change + FeatureState.DONE + issue_number set    |
| R8  | I3             | review          | Broad try/except in hook body; function always returns None                                  |
| R9  | I3             | test            | git_repo_url=None skips gh; MD fallback still written and persisted                          |
| R10 | I4             | review          | POST→create, title/brief PATCH→edit, state PATCH (both routes)→state_change via _fire_mirror |
| R11 | I1 (return value) + I3 (fallback persistence) | test | Stale issue_number → gh edit rc!=0 → (None,None) → MD fallback + set_issue_refs(None) |

All 11 requirements from analysis `traceability[]` are covered. R2/R4/R8/R10 are `verifying_phase=review`; the reviewer reads the impl diff produced by I1/I3 — no separate iteration needed for review-only requirements.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| gh issue create stdout format variance across gh CLI versions could force false fallback | medium | I1 uses permissive regex against every stdout line; unit tests cover URL-only and multi-line shapes |
| MD-before-gh ordering (R6) easy to invert; would skip fallback on transient gh timeout | medium | I3 explicit ordering test patches both write_text and gh_issue_upsert, asserts call order via mock call_args_list |
| Swallowing all gh exceptions masks real errors (silent data loss) | medium | I3 hook logs WARNING with task.id + reason; tests assert caplog records; review confirms try/except scope is bounded |
| Stale upstream issue orphaned on GitHub when issue_number cleared after gh edit failure | low | Accepted scope per request (one-way mirror, no reconciliation); documented in hook docstring; I1+I3 tests assert the (None,None) → MD fallback flow |
| feature_hooks → storage import cycle via global singleton | low | store passed as parameter at _fire_mirror call site (per S2 R10); I3 test uses in-memory TaskStore fixture as constructor arg |
| 60s subprocess timeout under burst edits could block FastAPI scheduler | low | _fire_mirror is fire-and-forget asyncio task (per S2); I4 asserts API response <100ms even when gh sleeps 5s |

## Assumptions

- The implementor operates on branch `feature/features-and-fixes` (commits b511f1b + 45c5b92 already present per memory:project_s1_data_model_impl and memory:project_s2_api_impl). S2-introduced files (`feature_hooks.py`, `api/features.py` with `_fire_mirror`) exist on that branch even though they are absent on `main`. I3 and I4 will not be implementable on `main` directly.
- `_fire_mirror` from S2 passes `(task, space, reason, store)` (or equivalent) to `mirror_feature_to_github`. If S2 passes a different store-acquisition mechanism, I3 adapts the hook signature accordingly — the analysis R10 explicitly confirms the funnel exists and is the only mirror entry point.
- `FeatureState.DONE` exists on the feature branch (S1 commit b511f1b per memory). I3 imports `FeatureState` from `app.models`.
- MD fallback format per analysis assumption: `# {feature_key}: {title}\n\n{brief}\n`. `task.feature_key` is set by S1 create flow and immutable. No YAML frontmatter (consistency with autopilot_pr.py:176 plain-markdown style).
- `proposed_issue_path` mutual-exclusion invariant with `issue_number` (set when issue_number is None; cleared when issue_number is set) is enforced inside the hook body, not inside `set_issue_refs` — the storage method is a dumb setter.
- The pytest validation commands in each iteration's `validation_command` are run from the workspace root via `cd backend && pytest ...`. The coverage floor (`--cov-fail-under=60` per pyproject) is a project-global gate, NOT a per-iteration gate; the tester job (Phase 6) runs the full suite. Per memory:feedback_pipeline_narrow_k_coverage, narrow per-iteration pytest invocations omit the global coverage gate and are valid for iteration acceptance.
- I4 (API call-site assertion test) does not edit `api/features.py`; it only adds a test file that imports and exercises the existing FastAPI app via `TestClient` / `httpx.AsyncClient` with monkeypatched `feature_hooks.mirror_feature_to_github` to count calls and inspect reason strings.

## Open questions

- None.

## Next consumer brief

Implementor: read `iterations[]` and pick the entry whose id matches your fan-out slot. Hard rules:

1. `scope_files[]` is a strict diff boundary — do not edit any file outside it. I1 owns `git_issues.py` (new) only. I2 owns one method addition in `storage.py` only. I3 owns the hook body in `feature_hooks.py` only. I4 owns one new test file only — no edits to `api/features.py`.
2. Cross-iteration invariants the YAML cannot express: (a) the regex used by I1 for URL extraction is `r'https?://[^\s]+/issues/(\d+)'` — I3 tests must not assume a different shape; (b) the MD path format is `.cronos/issues/{task.id}.md` (use `task.id`, NOT `task.feature_key`, per scout finding §5); (c) the `set_issue_refs` parameter order is `(task_id, *, issue_number, issue_url, proposed_issue_path)` — keyword-only after task_id, matching `set_pr_refs`.
3. Layer 0 (I1 + I2) can run in parallel — orchestrator should fan out two implementors. Layer 1 (I3) waits on both. Layer 2 (I4) waits on I3.
4. Per memory:feedback_pipeline_narrow_k_coverage, your `validation_command_passed: true` reflects the narrow pytest invocation. The full-suite + coverage gate runs in Phase 6 (tester).
5. Per memory:observation_worktree_main_vs_workspace, implementor edits land in the main worktree; cp to the workspace worktree before goal-task-commit.
