---
cc_version: '1.0'
agent: pipeline-implementor
slug: g11-least-priv-git
phase: impl
status: done
confidence: 0.88
iteration_id: I1
files_changed:
- backend/tests/test_git_ops_auth_env.py
- backend/tests/test_no_pat_in_traces.py
- backend/app/git_ops.py
- .env.example
- deploy/VPS_SETUP.md
- README.md
validation_command_passed: true
inputs_used:
- .cronos/pipeline/g11-least-priv-git/design-report-g11-least-priv-git.md
- backend/app/git_ops.py
- backend/app/trace_redact.py
- backend/tests/test_no_pat_in_traces.py
- backend/tests/test_git_ops.py
- backend/tests/test_autopilot_pr.py
- .env.example
- deploy/VPS_SETUP.md
- README.md
outputs_produced:
- .cronos/pipeline/g11-least-priv-git/impl-report-g11-least-priv-git.md
- backend/tests/test_git_ops_auth_env.py
- backend/tests/test_no_pat_in_traces.py
- backend/app/git_ops.py
- .env.example
- deploy/VPS_SETUP.md
- README.md
blockers: []
next_consumer: review
metrics:
  tool_calls: 22
  files_read: 9
  memory_hits: 2
  iterations_completed: 4
  diff_lines_added: 414
  diff_lines_removed: 9
---

## Summary

G11 least-privilege git credential hardening implemented across 4 iterations.
No code behaviour was changed — the implementation is documentation, tests, and
comments only, matching the design's explicit intent. All 4 iteration validation
commands pass.

**Scope compliance:** All changes are within the scope_files listed in the design.
No function signatures, return types, or runtime behaviour were modified in
`git_ops.py`. The `test_autopilot_pr.py` suite passes unchanged, confirming no
behaviour drift.

**Key findings from the audit (I2):**
- `_auth_env()` already uses `GIT_CONFIG_*` env vars (never argv) — the PAT
  is invisible to `ps` output and never appears in log output.
- `push_branch()` already calls `_auth_env()` and passes the env to git.
- `gh_pr_create()` is already a PR-open-only gate (never merges).
- `trace_redact.SECRET_PATTERNS` already covers all 5 token forms (ghp_,
  github_pat_, gho_, ghs_, ghr_) and the x-access-token: form.
- The token does NOT appear in `GIT_CONFIG_VALUE_0` (it is base64-encoded
  as part of `Authorization: Basic <base64(x-access-token:TOKEN)>`).

## Files changed

| File | Change type | Description |
|------|-------------|-------------|
| `backend/tests/test_git_ops_auth_env.py` | new | 9 tests for `_auth_env()` + `push_branch()` credential injection and token-not-in-log assertions |
| `backend/tests/test_no_pat_in_traces.py` | extended | 2 new tests asserting SECRET_PATTERNS cover `x-access-token:TOKEN` and both CRONOS_GIT_TOKEN PAT forms |
| `backend/app/git_ops.py` | comments only | Least-privilege scope note in `_GIT_TOKEN_ENV` block; docstring additions to `push_branch()` and `gh_pr_create()` |
| `.env.example` | docs | Extended CRONOS_GIT_TOKEN block with least-privilege table, DO NOT grant list, GitHub setup steps |
| `deploy/VPS_SETUP.md` | docs | New §5.3 "Git push credentials" — push policy ADR, least-privilege table, PAT creation steps, rotation, future GitHub App path |
| `README.md` | docs | New "Git credential model" section with scope table and autopilot_pr PR-gate note |

## Out-of-scope findings

- `backend/app/autopilot_pr.py` — confirmed PR-open-only behaviour; no change
  needed (out of scope_files per design R4 note).
- `trace_redact.SECRET_PATTERNS` — confirmed complete coverage; no new patterns
  added (design: assert, not add).
- No signature/behaviour change to `push_branch()` `token=` parameter — analyst
  Q2 was rejected for this minimal-scope goal.

## Assumptions

- The existing `os.environ.copy()` in `_auth_env()` means `CRONOS_GIT_TOKEN`
  appears in the subprocess env; this is expected (the test was adjusted to
  check only `GIT_CONFIG_VALUE_0`, not all env values).
- Fine-grained PAT `Contents:write` is sufficient for both `git push` and
  `gh pr create` (the `gh` CLI uses its own auth token, not CRONOS_GIT_TOKEN).
- The narrow validation commands required `--override-ini="addopts="` to bypass
  the 60% coverage floor (matching the design guidance and feedback memory);
  `validation_command_passed` reflects the result of those narrow runs.

## Open questions

- **Q1 (operator decision, carried from design):** Does the operator use one
  combined `CRONOS_GIT_TOKEN` for clone+push, or separate fine-grained PATs?
  §5.3 recommends separate PATs but does not break the single-token path.

## Next consumer brief

Review phase: verify that `backend/app/git_ops.py` contains only comment/docstring
changes (no signature or behaviour drift), that `test_autopilot_pr.py` passes
unchanged, that `.env.example` contains `contents:write`, `admin`, and `workflow`
keywords, and that `deploy/VPS_SETUP.md` contains `§5.3` with `least-privilege`
and `contents:write`. Run: `cd backend && pytest tests/test_git_ops.py
tests/test_git_ops_auth_env.py tests/test_autopilot_pr.py -v --override-ini="addopts="`.
