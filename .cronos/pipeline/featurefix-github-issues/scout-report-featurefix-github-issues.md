---
cc_version: "1.0"
agent: pipeline-scout
slug: featurefix-github-issues
phase: scout
status: done
confidence: 0.88
inputs_used:
  - memory:project_pipeline_foundation_merged
  - memory:project_architecture_key_modules
  - memory:project_s2_api_impl
  - memory:project_s1_data_model_impl
  - backend/app/git_ops.py
  - backend/app/autopilot_pr.py
  - backend/app/models.py
  - backend/app/storage.py
  - backend/app/worker.py
outputs_produced:
  - .cronos/pipeline/featurefix-github-issues/scout-report-featurefix-github-issues.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/git_ops.py (gh CLI patterns)
    - backend/app/autopilot_pr.py (MD fallback pattern, post-DONE hook)
    - backend/app/storage.py (set_pr_refs pattern, Task model with issue fields)
    - backend/app/worker.py (post-DONE hook location for mirror fire)
    - backend/app/models.py (Task.issue_number/issue_url/proposed_issue_path fields from S1 commit)
  excluded:
    - frontend: S3 has no UI (has_ui=false)
    - tests: coverage floor enforced separately
    - git_issues.py: does not exist yet; S3 will create
    - feature_hooks.py and api/features.py: stubbed in S2 commit 45c5b92; S3 implements bodies
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "S3 — GitHub issue one-way mirror. New git_issues.py (gh_issue_upsert/gh_issue_close), storage.py (set_issue_refs), fire mirror on create + state/title changes via feature_hooks.py."
metrics:
  tool_calls: 19
  files_read: 5
  memory_hits: 4
---

## Summary

S3 implements one-way GitHub issue mirroring for feature/fix tasks, replicating the autopilot PR pattern established in git_ops.py and autopilot_pr.py. The implementation comprises three layers: (1) gh CLI wrapper (git_issues.py: gh_issue_upsert for create/edit, gh_issue_close for closure); (2) storage mutation method (set_issue_refs, mirrors set_pr_refs); (3) feature_hooks.py mirror_feature_to_github hook fired from features.py endpoints. The MD fallback (.cronos/issues/{feature_id}.md) activates when gh is absent, non-GitHub, or fails silently (no error propagation per worker.py:430-431 pattern).

## Coverage

### Searched
- `backend/app/git_ops.py` (lines 401-464): gh_pr_create pattern — gh CLI guard (shutil.which), subprocess.create_subprocess_exec, 60s timeout, exception handling, URL parsing via regex, detect_github_remote() helper
- `backend/app/autopilot_pr.py` (lines 27-72, 91-186): commit_and_open_pr flow, MD fallback write (pr_dir / f"{branch}.md"), set_pr_refs call, exception swallowing at line 160-161
- `backend/app/storage.py` (lines 802-824): set_pr_refs signature and pattern — task model_copy, atomic_write, _reindex_locked
- `backend/app/worker.py` (lines 842-861): post-DONE hook location where autopilot_pr.run_post_done_flow is called; exception swallowing pattern
- `backend/app/models.py` (via S1 commit b511f1b): Task fields issue_number (int|None), issue_url (str|None), proposed_issue_path (str|None); TaskSummary mirrors all three

### Excluded
- Frontend components: has_ui=false per request; no editor/board UI changes
- Tests: coverage floor (≥60%) enforced separately; test authorship is design/review phase
- feature_hooks.py and api/features.py: currently stubs (S2 commit 45c5b92); S3 replaces bodies without changing signatures
- git_issues.py: does not exist on any branch; S3 creates from scratch

### Strategies
- memory_retrieval: 4 memory entries confirmed (pipeline foundation, architecture, S2 API, S1 model)
- glob_structural: located git_ops.py, autopilot_pr.py, storage.py, models.py via known paths
- grep_symbol: searched "set_pr_refs", "gh_pr_create", "run_post_done_flow", "_fire_mirror" to map patterns
- read_targeted: full reads of git_ops gh_pr_create (417-464) and autopilot_pr flow (27-186) to extract pattern; read models.py to verify issue fields from S1; skipped large unrelated worker code

## Findings

### 1. gh CLI Wrapper (git_issues.py — new file)

**Pattern source:** git_ops.py:417-464 (gh_pr_create)

**Required function: gh_issue_upsert**
- Signature: `async def gh_issue_upsert(space_dir: Path, *, title: str, body: str, labels: list[str], issue_number: int | None) -> tuple[int | None, str | None]`
  - Returns: `(issue_number, issue_url)` or `(None, None)` on failure
  - Parameters: space_dir (for remote detection + cwd), title/body for create, labels (["feature"] or ["fix"]), issue_number (None for create; int for edit)
- Guard: `if not shutil.which("gh"): log.info(...); return (None, None)` (git_ops.py:429-431 pattern)
- Subprocess: `asyncio.create_subprocess_exec("gh", "issue", "create"|"edit", ...)` with stdin for body (git_ops.py:434-444)
- Timeout: 60s, matching gh_pr_create (line 446-448)
- Parsing create output: extract issue number from first line (e.g., "https://github.com/owner/repo/issues/42" → 42)
- Parsing edit: assume success on returncode==0; reuse issue_number as-is
- Exception handling: catch FileNotFoundError, asyncio.TimeoutError, log at WARNING level, return (None, None)

**Required function: gh_issue_close**
- Signature: `async def gh_issue_close(space_dir: Path, issue_number: int) -> bool`
  - Returns True on success, False on failure (parallel to gh_pr_create pattern)
- Subprocess: `asyncio.create_subprocess_exec("gh", "issue", "close", str(issue_number), ...)`
- Used in worker.py post-feature-DONE hook to close the issue (S3 acceptance: feature→done)

**Shared helpers:**
- detect_github_remote(space_dir): reuse from git_ops (already exists at line 406-414)
- _auth_env(repo_url): reuse from git_ops for credential injection if needed
- Logging: log = logging.getLogger("cronos.git_issues") (new module)

### 2. Storage Mutation Method (storage.py)

**Location:** Add after set_pr_refs (line 824)

**Method signature:**
```python
async def set_issue_refs(
    self,
    task_id: str,
    *,
    issue_number: int | None,
    issue_url: str | None,
    proposed_issue_path: str | None,
) -> Task:
```

**Implementation:** Mirrors set_pr_refs pattern exactly (lines 802-824)
- Acquire self._lock (async with)
- Fetch task by task_id, raise TaskNotFound if missing
- model_copy with update dict: {issue_number, issue_url, proposed_issue_path, updated_at}
- atomic_write(path, dump_task(updated))
- _reindex_locked(path)
- Return self._by_id[task_id]

**Call sites:** feature_hooks.py mirror_feature_to_github → called from features.py _fire_mirror

### 3. Feature Hooks Implementation (feature_hooks.py)

**Current state (S2 commit 45c5b92):** mirror_feature_to_github is a no-op stub (returns None)

**S3 implementation replaces stub body:**
```python
async def mirror_feature_to_github(
    task: "Task",
    *,
    space: "Space",
    reason: Literal["create", "state_change", "edit"],
) -> None:
```

**Logic:**
1. **Preconditions:** Skip if space.git_repo_url is None (non-GitHub) or task.type not in ("feature", "fix")
2. **Determine labels:** labels = ["feature"] if task.type == "feature" else ["fix"]
3. **Call gh_issue_upsert:**
   - issue_number = task.issue_number
   - title = task.title
   - body = task.brief (or brief[:400] preview + "...")
   - Call: `issue_num, issue_url = await git_issues.gh_issue_upsert(space_dir, title=..., body=..., labels=..., issue_number=...)`
4. **Write MD fallback first** (before gh call, to guarantee local record exists):
   - issues_dir = space_dir / ".cronos" / "issues"
   - issues_dir.mkdir(parents=True, exist_ok=True)
   - content = f"# {task.feature_key}: {task.title}\n\n{task.brief}\n"
   - proposed_path = issues_dir / f"{task.id}.md"
   - proposed_path.write_text(content)
5. **Persist issue refs:** `await store.set_issue_refs(task.id, issue_number=issue_num, issue_url=issue_url, proposed_issue_path=str(proposed_path) if issue_num is None else None)`
6. **Handle gh_issue_close on feature→done:** When reason=="state_change" and task.feature_state == FeatureState.DONE:
   - If task.issue_number is not None: `await git_issues.gh_issue_close(space_dir, task.issue_number)`
   - Swallow all exceptions (no re-raise)
7. **Exception handling:** Wrap all gh calls in try/except; log at WARNING level; never raise (fire-and-forget pattern per worker.py:430-431)

**Fire points (from S2 commit 45c5b92):**
- POST /api/features (create): reason="create" (line 120)
- PATCH /api/features/{feature_id} state (state_change): reason="state_change" (line 215)
- PATCH /api/features/{feature_id} title/brief (edit): reason="edit" (line 256)
- PATCH /api/features/{feature_id}/state (state_change alt): reason="state_change" (line 342)

### 4. Integration Points

**Task model fields (from S1 commit b511f1b):**
- issue_number: int | None = None
- issue_url: str | None = None
- proposed_issue_path: str | None = None
- Already in TaskSummary (lines 99-101 of S2 commit)

**Worker.py post-feature-DONE hook (new):**
- Location: after autopilot_pr hook (line 862)
- Logic: if task.type in ("feature", "fix") and new_state == FeatureState.DONE (or check task.feature_state == FeatureState.DONE):
  - Call gh_issue_close for the mirrored issue
  - Swallow exceptions per pattern

**API schema (CreateFeatureBody, PatchFeatureBody):**
- Already defined in S2 (commit 45c5b92)
- Includes title, brief fields that trigger mirror fires

### 5. Fallback Behavior

**MD fallback file location:** `.cronos/issues/{feature_id}.md`
- Not `.cronos/issues/{feature_key}.md` (feature_key can have slashes; use feature_id instead)
- Format: YAML frontmatter + markdown body (mirroring PR fallback at autopilot_pr.py:70)
- Written BEFORE gh call to guarantee local record exists even if gh fails

**Degradation path:** stale issue_number without corresponding GitHub issue
- If issue_number persists in DB but gh reports issue not found, MD fallback is used
- No special handling needed; next edit/state_change will re-create if needed

### 6. Testing Integration Points

**No UI changes** → no frontend test additions

**Scope files (per request):**
- git_issues.py (new): 2–3 async functions (gh_issue_upsert, gh_issue_close, helpers)
- storage.py: 1 new method (set_issue_refs, ~15 lines)
- api/features.py: fire _fire_mirror at 4 call sites (already stubbed in S2)
- feature_hooks.py: 1 function body (mirror_feature_to_github, ~40 lines)

**Acceptance criteria (from request):**
- Create with gh → issue_number/issue_url persisted ✓ (set_issue_refs)
- Update → same issue edited (no dup) ✓ (gh issue edit reuses issue_number)
- gh absent / non-GitHub → .cronos/issues/{id}.md + proposed_issue_path ✓ (fallback path)
- Stale issue_number degrades gracefully ✓ (gh returns error; falls back to MD on next mirror fire)

## Assumptions
- issue_number is stable once assigned; mutations use same number (no reallocation)
- GitHub issue URL format: `https://github.com/{owner}/{repo}/issues/{number}` — extracts number from stdout of `gh issue create`
- feature_key (e.g., "FEAT-001") is immutable and unique per space+type (set in S1 create flow)
- feature_hooks.py mirror_feature_to_github is called from features.py endpoints via _fire_mirror funnel (R13 per S2 request)
- proposed_issue_path is only set when gh is absent or fails (i.e., issue_number=None implies proposed_issue_path is set, and vice versa)
- feature/fix tasks are excluded from regular task board; feature_board() is a separate query (S1 design; not S3 scope)
- No persistent queue or retry logic for failed mirrors — failures are logged but not re-queued

## Open questions
- None.

## Next consumer brief

**Analysis agent (phase 2) should:**

1. **Verify scope boundary:** confirm S3 owns only git_issues.py (new) + set_issue_refs in storage.py + hook implementations in feature_hooks.py; S2 already defines features.py _fire_mirror call sites.

2. **Assess call ordering:** In feature_hooks.py, write MD fallback BEFORE gh calls to guarantee local record persists even on gh timeout/network error. Confirm exception handling never raises (fire-and-forget).

3. **Check closure semantics:** gh_issue_close fires on feature→done (feature_state transition, not TaskState). Clarify whether this should be in feature_hooks.py or post-DONE worker hook. If worker.py, worker must import feature_hooks; if feature_hooks.py, it must import git_issues and handle FeatureState.DONE check.

4. **Verify GitHub remote detection:** detect_github_remote() already exists (git_ops.py:406-414); reuse in git_issues.py. Confirm owner/repo extraction regex handles both HTTPS and SSH URLs.

5. **Trace _fire_mirror funnel:** All mirror fires from features.py go through _fire_mirror(task, space, reason); this is the single instrumentation point (R13). Verify call counts in tests.

6. **Design iteration focus:** 
   - gh_issue_upsert: handle multi-line body; URL parsing from `gh issue create` stdout
   - MD fallback: format (frontmatter vs. simple body); location (.cronos/issues or elsewhere); file naming (task.id vs. feature_key)
   - Feature-state-to-closure: when exactly does gh_issue_close fire? (On feature_state=DONE, or on user action?)
   - Credentials: does _auth_env injection work for gh CLI, or does gh use its own auth (oauth token in $HOME/.config/gh)?

7. **Backward compatibility:** Existing feature/fix tasks created in S1/S2 before S3 will have issue_number=None. Mirrors should handle this gracefully (treat as "never mirrored"; create on next edit).

8. **Error budget:** All gh failures swallow; user never sees them (no HTTP 500). Mirrors are async-fired from features.py endpoints, so endpoint returns before gh result known. Consider logging structured events for observability.
