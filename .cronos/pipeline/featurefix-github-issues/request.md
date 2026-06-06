# S3 — GitHub Issue one-way mirror

**Title:** `Features&Fixes/S3 — GitHub issue mirror (one-way)` · **has_ui:** no · **dep:** S2

New `backend/app/git_issues.py`, like `gh_pr_create` (git_ops.py:417-464) + the MD fallback
(autopilot_pr.py:116-137).
- `gh_issue_upsert(space_dir, *, title, body, labels, issue_number) -> (int|None, str|None)`:
  `issue_number is None` → `gh issue create --label feature|fix` (parse number+url); else
  `gh issue edit <n>`. Reuse the `shutil.which("gh")` guard, `create_subprocess_exec`, 60s timeout,
  graceful-None, and `detect_github_remote()`.
- `gh_issue_close(space_dir, issue_number)` for feature→done.
- Fallback (no remote / `gh` None): write `.cronos/issues/{feature_id}.md` + persist `proposed_issue_path`.
- `store.set_issue_refs(task_id, *, issue_number, issue_url, proposed_issue_path)` (mirror `set_pr_refs`).
- **Fires** after the local MD write succeeds, on create + any title/brief/feature_state change. Swallow
  all `gh` exceptions at the call site (worker.py:430-431 pattern); never block the response.

**Scope files:** `git_issues.py` (new), storage.py (`set_issue_refs`), `api/features.py` (call sites).
**Acceptance:** create with `gh` → number/url persisted, label applied; update → same issue edited (no
dup); `gh` absent / non-GitHub → `.cronos/issues/{id}.md` + `proposed_issue_path`, no error; a stale
`issue_number` degrades to MD fallback without crashing.

---

## Standing Rules (apply to all phases)

**Branch:** all phase work commits to `feature/features-and-fixes` (from `main` if
missing; never branch from another base, never merge to `main`). Use [[goal-task-commit]]
after review passes.
**Locked design:** apply the parent goal's **Locked decisions** + **Locked design notes 1–7** verbatim
(reuse `Task` with `feature`/`fix`; `feature_state` machine; per-space `FEAT-`/`FIX-`; `realizes` field;
one-way `gh` mirror, MD canonical; git-linked only). No new SQLite tables (index columns only), no Redis,
no HTTP issue API.
**Test gate:** the pipeline's `test`+`review` phases gate — pytest (≥60%) and vitest/`tsc --strict`
must pass before `doc`; commit only on a `pass` verdict. **STATUS/gating** is owned by [[pipeline-gate]].

