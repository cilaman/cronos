---
cc_version: '1.0'
agent: pipeline-analyst
slug: featurefix-github-issues
phase: analysis
status: done
confidence: 0.9
inputs_used:
- memory:project_s1_data_model_impl
- memory:project_s2_api_impl
- memory:project_architecture_key_modules
- memory:project_pipeline_foundation_merged
- .cronos/pipeline/featurefix-github-issues/scout-report-featurefix-github-issues.md
- backend/app/git_ops.py
- backend/app/autopilot_pr.py
- backend/app/storage.py
- backend/app/worker.py
- backend/app/models.py
- backend/app/api/features.py
- backend/app/feature_hooks.py
outputs_produced:
- .cronos/pipeline/featurefix-github-issues/analysis-report-featurefix-github-issues.md
blockers: []
next_consumer: design
request: "New `backend/app/git_issues.py`, like `gh_pr_create` (git_ops.py:417-464)\
  \ + the MD fallback\n(autopilot_pr.py:116-137).\n- `gh_issue_upsert(space_dir, *,\
  \ title, body, labels, issue_number) -> (int|None, str|None)`:\n  `issue_number\
  \ is None` -> `gh issue create --label feature|fix` (parse number+url); else\n \
  \ `gh issue edit <n>`. Reuse the `shutil.which(\"gh\")` guard, `create_subprocess_exec`,\
  \ 60s timeout,\n  graceful-None, and `detect_github_remote()`.\n- `gh_issue_close(space_dir,\
  \ issue_number)` for feature->done.\n- Fallback (no remote / `gh` None): write `.cronos/issues/{feature_id}.md`\
  \ + persist `proposed_issue_path`.\n- `store.set_issue_refs(task_id, *, issue_number,\
  \ issue_url, proposed_issue_path)` (mirror `set_pr_refs`).\n- **Fires** after the\
  \ local MD write succeeds, on create + any title/brief/feature_state change. Swallow\n\
  \  all `gh` exceptions at the call site (worker.py:430-431 pattern); never block\
  \ the response.\n\n**Scope files:** `git_issues.py` (new), storage.py (`set_issue_refs`),\
  \ `api/features.py` (call sites).\n**Acceptance:** create with `gh` -> number/url\
  \ persisted, label applied; update -> same issue edited (no\ndup); `gh` absent /\
  \ non-GitHub -> `.cronos/issues/{id}.md` + `proposed_issue_path`, no error; a stale\n\
  `issue_number` degrades to MD fallback without crashing."
has_ui: false
coverage_summary:
  searched:
  - backend/app/git_ops.py
  - backend/app/autopilot_pr.py
  - backend/app/storage.py
  - backend/app/worker.py
  - backend/app/models.py
  - backend/app/api/features.py
  - backend/app/feature_hooks.py
  excluded:
  - frontend/: has_ui=false; request explicitly marks no UI
  - tests/: coverage floor enforced separately; test authorship is design/review phase
  - backend/app/git_issues.py: does not exist yet; S3 creates it
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: A new module git_issues.py provides async gh_issue_upsert(space_dir,
    *, title, body, labels, issue_number) -> tuple[int|None, str|None] that creates
    a GitHub issue when issue_number is None and edits the existing issue when issue_number
    is an int.
  acceptance_criteria:
  - Given gh is on PATH and issue_number is None, gh issue create is invoked with
    --label from labels and stdout is parsed to extract (issue_number, issue_url).
  - Given gh is on PATH and issue_number is an int, gh issue edit <n> is invoked and
    the function returns (issue_number, issue_url) on returncode 0.
  - Given gh exits non-zero, the function returns (None, None) and logs a WARNING
    without raising.
  - Given shutil.which('gh') returns None, the function returns (None, None) immediately
    without spawning a subprocess.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R2
  statement: 'gh_issue_upsert reuses the subprocess pattern from gh_pr_create in git_ops.py:
    asyncio.create_subprocess_exec, body via stdin, 60-second timeout with proc.kill()
    on TimeoutError, and FileNotFoundError caught.'
  acceptance_criteria:
  - The subprocess is created with asyncio.create_subprocess_exec, not subprocess.run
    or subprocess.Popen.
  - The body is passed as stdin bytes so multi-line content is safe.
  - Given the 60-second timeout elapses, proc.kill() is called, proc.wait() is awaited,
    and (None, None) is returned.
  - FileNotFoundError is caught and returns (None, None).
  verifying_phase: review
  confidence: 0.92
- requirement_id: R3
  statement: A new module git_issues.py provides async gh_issue_close(space_dir, issue_number)
    -> bool that closes the specified GitHub issue via gh issue close.
  acceptance_criteria:
  - Given gh is on PATH and returncode is 0, the function returns True.
  - Given gh is absent or exits non-zero, the function returns False and logs a WARNING.
  - Given any exception, the function catches it, logs WARNING, and returns False
    without raising.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: git_issues.py reuses detect_github_remote() imported from git_ops as
    the guard for whether a GitHub remote exists — no reimplementation.
  acceptance_criteria:
  - git_issues.py imports or calls detect_github_remote from app.git_ops.
  - When detect_github_remote returns None, gh calls inside gh_issue_upsert are not
    made.
  verifying_phase: review
  confidence: 0.95
- requirement_id: R5
  statement: storage.TaskStore gains a new async set_issue_refs(task_id, *, issue_number,
    issue_url, proposed_issue_path) -> Task method mirroring the set_pr_refs pattern
    at line 802.
  acceptance_criteria:
  - The method acquires self._lock, fetches the task by task_id, raises TaskNotFound
    if missing.
  - The method calls task.model_copy with updated issue_number, issue_url, proposed_issue_path,
    and updated_at=datetime.now(tz=UTC).
  - The method calls atomic_write and _reindex_locked before returning the updated
    task.
  - 'Parameter types are: issue_number: int|None, issue_url: str|None, proposed_issue_path:
    str|None.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R6
  statement: feature_hooks.mirror_feature_to_github writes a local MD file at .cronos/issues/{task.id}.md
    before any gh call, then calls gh_issue_upsert and persists results via store.set_issue_refs.
  acceptance_criteria:
  - The directory .cronos/issues/ is created with mkdir(parents=True, exist_ok=True)
    before gh_issue_upsert is invoked.
  - Given gh succeeds (issue_num is not None), set_issue_refs is called with issue_number=issue_num,
    issue_url=issue_url, proposed_issue_path=None.
  - Given gh fails or is absent (issue_num is None), set_issue_refs is called with
    issue_number=None, issue_url=None, proposed_issue_path=str(proposed_path).
  verifying_phase: test
  confidence: 0.9
- requirement_id: R7
  statement: mirror_feature_to_github calls gh_issue_close when reason is 'state_change'
    and task.feature_state is FeatureState.DONE and task.issue_number is not None.
  acceptance_criteria:
  - Given reason='state_change' and feature_state=FeatureState.DONE and issue_number
    is not None, gh_issue_close(space_dir, task.issue_number) is awaited.
  - Given feature_state is not DONE or issue_number is None, gh_issue_close is not
    called.
  - Given gh_issue_close raises, the exception is swallowed; the function still returns
    None.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R8
  statement: 'mirror_feature_to_github is fire-and-forget: all gh exceptions are caught
    inside the hook body and the function always returns None regardless of gh outcome.'
  acceptance_criteria:
  - A broad try/except wraps all gh calls inside the hook body.
  - The function returns None in both the success path and all error paths.
  - The _fire_mirror funnel in api/features.py does not add its own exception catch
    around the hook call.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R9
  statement: When space.git_repo_url is None (non-GitHub or no repo), gh is skipped
    entirely but the MD fallback at .cronos/issues/{task.id}.md is still written and
    proposed_issue_path is persisted.
  acceptance_criteria:
  - Given space.git_repo_url is None, detect_github_remote is not called and no subprocess
    is spawned.
  - The MD file is still written to .cronos/issues/{task.id}.md.
  - set_issue_refs is called with proposed_issue_path set and issue_number=None.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R10
  statement: 'All four _fire_mirror call sites already in api/features.py (from S2)
    pass the correct reason string: ''create'' on POST, ''edit'' on title/brief PATCH,
    ''state_change'' on both state PATCH endpoints.'
  acceptance_criteria:
  - POST /api/features calls _fire_mirror with reason='create'.
  - PATCH /api/features/{id} for title/brief edits calls _fire_mirror with reason='edit'.
  - Both PATCH /api/features/{id} state-transition endpoints call _fire_mirror with
    reason='state_change'.
  - No endpoint calls mirror_feature_to_github directly; all calls route through _fire_mirror
    (concentration requirement R13 from S2).
  verifying_phase: review
  confidence: 0.95
- requirement_id: R11
  statement: A stale issue_number (persisted but corresponding GitHub issue deleted)
    degrades gracefully to the MD fallback without crashing; the API endpoint returns
    2xx to the client.
  acceptance_criteria:
  - Given issue_number is set but gh issue edit exits non-zero, gh_issue_upsert returns
    (None, None).
  - The MD fallback is then written and proposed_issue_path is persisted via set_issue_refs.
  - The API endpoint that triggered the mirror still returns its normal 200/2xx response.
  verifying_phase: test
  confidence: 0.88
metrics:
  tool_calls: 14
  files_read: 8
  memory_hits: 4
---

## Summary

S3 implements one-way GitHub issue mirroring for feature/fix tasks. A new `git_issues.py` module provides two async functions (`gh_issue_upsert` for create/edit, `gh_issue_close` for closure) modelled directly on `gh_pr_create` in `git_ops.py`. `storage.TaskStore` gains `set_issue_refs`, mirroring the existing `set_pr_refs` method. `feature_hooks.mirror_feature_to_github` — currently a no-op stub on the feature branch — gets its body implemented: it writes a local MD fallback first, then conditionally calls the gh CLI, and persists results atomically. All four `_fire_mirror` call sites in `api/features.py` are already wired by S2; S3 replaces only the hook body, adds the storage method, and creates the new module.

## Scope

### In scope
- New `backend/app/git_issues.py` module with `gh_issue_upsert` and `gh_issue_close`
- `storage.TaskStore.set_issue_refs` method (mirrors `set_pr_refs`)
- `feature_hooks.mirror_feature_to_github` body implementation (replaces S2 no-op stub)
- MD fallback write to `.cronos/issues/{task.id}.md` when gh is absent or fails
- Issue closure (`gh issue close`) triggered on `feature_state=FeatureState.DONE` inside the hook
- Reuse of `detect_github_remote()` from `git_ops.py` as the GitHub guard

### Out of scope
- `api/features.py` structural changes — the four `_fire_mirror` call sites are already in place from S2; S3 does not add or remove endpoints
- Worker.py changes — closure fires inside `mirror_feature_to_github` on `reason='state_change'`, not via a worker post-DONE hook
- Any frontend UI changes — `has_ui=false` per request
- Retry or persistent queue for failed gh calls — fire-and-forget only
- `enqueue_feature_decomposition` in `feature_hooks.py` — S4 stub; S3 must not touch it
- `_auth_env` injection — not needed; `gh` CLI manages its own OAuth token

### Deferred
- Two-way sync (GitHub issue state back to Cronos)
- Label management beyond single "feature" / "fix" label
- Issue templates, milestone assignment, or project board placement
- Re-queueing failed mirrors for eventual consistency

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | gh_issue_upsert creates or edits a GitHub issue via gh CLI and returns (number, url) or (None, None) |
| R2 | gh_issue_upsert uses asyncio.create_subprocess_exec, stdin body, 60s timeout, FileNotFoundError guard |
| R3 | gh_issue_close closes a GitHub issue and returns bool success/failure without raising |
| R4 | git_issues.py reuses detect_github_remote() from git_ops — no reimplementation |
| R5 | storage.TaskStore.set_issue_refs persists issue_number, issue_url, proposed_issue_path atomically |
| R6 | mirror_feature_to_github writes MD fallback before gh call and calls set_issue_refs with result |
| R7 | mirror_feature_to_github calls gh_issue_close when reason=state_change and feature_state=DONE |
| R8 | mirror_feature_to_github is fire-and-forget: always returns None, all gh exceptions swallowed |
| R9 | When space.git_repo_url is None, gh is skipped but MD fallback is still written and persisted |
| R10 | All four _fire_mirror call sites in api/features.py pass the correct reason string |
| R11 | A stale issue_number degrades gracefully to MD fallback with no unhandled exception |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — create path invokes `gh issue create`; edit path invokes `gh issue edit <n>`; any failure returns (None, None)
- R2 — asyncio.create_subprocess_exec; body via stdin bytes; proc.kill() on 60s timeout; FileNotFoundError caught
- R3 — returns True on rc=0; False (no raise) on failure or absence; WARNING logged
- R4 — detect_github_remote imported from git_ops; gh skipped when it returns None
- R5 — acquires lock, model_copy update, atomic_write, _reindex_locked; raises TaskNotFound on missing task
- R6 — MD written before gh call; set_issue_refs called with (number, url, None) on success or (None, None, path) on fallback
- R7 — gh_issue_close awaited only on reason=state_change AND feature_state=DONE AND issue_number set
- R8 — broad try/except in hook body; _fire_mirror funnel does not add its own catch
- R9 — git_repo_url=None skips gh; MD fallback still written and proposed_issue_path persisted
- R10 — POST→'create', title/brief PATCH→'edit', state PATCH (both routes)→'state_change'; all via _fire_mirror
- R11 — gh edit rc!=0 returns (None, None); MD fallback written; API endpoint returns 2xx

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | gh_issue_upsert creates or edits a GitHub issue and returns (number, url) or (None, None) |
| R2 | review | gh_issue_upsert reuses asyncio subprocess pattern verbatim from gh_pr_create |
| R3 | test | gh_issue_close returns bool; all failures return False without raising |
| R4 | review | detect_github_remote reused from git_ops — not reimplemented in git_issues |
| R5 | test | set_issue_refs acquires lock, model_copy, atomic_write, _reindex_locked |
| R6 | test | MD fallback written before gh call; set_issue_refs called with correct args per outcome |
| R7 | test | gh_issue_close fires only on reason=state_change + feature_state=DONE + issue_number set |
| R8 | review | mirror_feature_to_github always returns None; all gh exceptions swallowed at hook body |
| R9 | test | git_repo_url=None skips gh; MD fallback still written and persisted |
| R10 | review | Four _fire_mirror call sites pass correct reason strings (confirmed from S2 commit) |
| R11 | test | Stale issue_number degrades to MD fallback; no unhandled exception; API returns 2xx |

## Assumptions

- S1 data model (`issue_number`, `issue_url`, `proposed_issue_path` on `Task`; `FeatureState` enum with DONE value) is already on the `feature/features-and-fixes` branch (commit b511f1b) — confirmed by reading the branch's models.py directly.
- S2 `feature_hooks.py` no-op stub and all four `_fire_mirror` call sites in `api/features.py` are already committed (commit 45c5b92) — confirmed by reading the branch files. S3 replaces the hook body only.
- `set_issue_refs` does not yet exist in `storage.py` on the feature branch — confirmed by grep. S3 adds it.
- has_ui=false rationale: request explicitly states `has_ui: no`; all S3 scope files are backend modules with no React/HTML/CSS involvement.
- `proposed_issue_path` is set when and only when `issue_number` is None after `gh_issue_upsert` (gh absent, non-GitHub remote, or gh failure). This mutual-exclusion invariant is enforced in R6.
- Issue closure fires inside `mirror_feature_to_github` on `reason='state_change'` + `feature_state=DONE`, not in a worker post-DONE hook. This keeps all issue logic in one module and avoids modifying worker.py.
- `_auth_env` from `git_ops.py` is for git credential injection and is not needed for the `gh` CLI, which manages its own OAuth token. git_issues.py does not import it.
- MD fallback format: `# {feature_key}: {title}\n\n{brief}\n` (plain markdown, no YAML frontmatter), consistent with the PR fallback style in autopilot_pr.py:70.
- `feature_key` (e.g. "FEAT-001") is immutable once set in S1 create flow; it is safe to embed in the MD fallback header.

## Open questions

- None.

## Next consumer brief

Design agent: read `traceability[]` for the requirements ground truth, `has_ui: false` to skip UI sub-track, and `## Scope` for hard boundaries.

Key decision points:

1. **git_issues.py CLI invocations:** Create path: `gh issue create --title ... --label ... --body-file -` with body via stdin. Edit path: `gh issue edit <n> --title ... --body-file -`. Issue number extraction from create stdout: `re.search(r'/issues/(\d+)', line)`. Confirm `--body-file -` works for `gh issue edit` (it does per gh CLI docs).

2. **set_issue_refs insertion:** Add immediately after `set_pr_refs` (storage.py line 824 on feature branch). Near-verbatim copy with `pr_url`/`proposed_pr_path` replaced by `issue_number`/`issue_url`/`proposed_issue_path`.

3. **MD write ordering (R6):** MD must be written before gh subprocess is spawned. Design iteration must enforce this; a post-gh write ordering fails R6.

4. **Closure co-location (R7):** `gh_issue_close` fires inside `mirror_feature_to_github` when `reason='state_change'` and `feature_state == FeatureState.DONE`. No worker.py changes needed.

5. **Test surface priority:** R1, R3, R5, R6, R7, R9, R11 are `verifying_phase: test` — these are the primary targets for the test iteration. Use `unittest.mock.patch('asyncio.create_subprocess_exec')` for gh path tests; `tmp_path` fixture for MD fallback tests; in-memory `TaskStore` for R5.

6. **Stale issue_number behavior (R11):** When `gh issue edit <n>` exits non-zero, `gh_issue_upsert` returns `(None, None)`. The hook then writes a new MD fallback and clears `issue_number` in storage (set_issue_refs with issue_number=None). On the next edit, the hook will call `gh issue create` again (creating a new issue). Confirm this "re-create on next edit" semantics with the request text — it says "stale issue_number degrades to MD fallback without crashing", which is satisfied.
