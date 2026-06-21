---
cc_version: '1.0'
agent: pipeline-doc-sync
slug: g11-least-priv-git
phase: doc
status: done
confidence: 0.95
inputs_used:
  - .cronos/pipeline/g11-least-priv-git/impl-report-g11-least-priv-git.md
  - .cronos/pipeline/g11-least-priv-git/review-report-g11-least-priv-git--attempt1.md
  - README.md
  - .env.example
  - deploy/VPS_SETUP.md
  - backend/app/git_ops.py
outputs_produced:
  - .cronos/pipeline/g11-least-priv-git/doc-report-g11-least-priv-git.md
  - README.md
  - .env.example
  - deploy/VPS_SETUP.md
blockers: []
next_consumer: null
intentionally_not_updated:
  - path: deploy/VPS_SETUP.md
    reason: "F2 residual-risk sentence optional polish: §5.3 already bounds residual risk via autopilot_pr PR-gate note"
metrics:
  tool_calls: 8
  files_read: 6
  memory_hits: 0
  docs_updated: 3
---

## Summary

G11 documentation is complete and accurate on `feature/cronos-remediation-plan`.
The implementation added three documentation sections covering least-privilege PAT
scopes, creation steps, and the push-to-origin+PR policy ADR. In-code comments on
`git_ops.py` (`_GIT_TOKEN_ENV`, `_auth_env()`, `push_branch()`, `gh_pr_create()`)
document the credential-injection mechanism. No CLAUDE.md updates needed — G11
scope is isolated to ops and credential setup, not codebase architecture.

**Docs updated:** 3 (README.md, .env.example, deploy/VPS_SETUP.md).
**Intentionally not updated:** 1 (F2 residual-risk sentence as non-blocking optional).

## Updated docs

Three documentation files were updated on `feature/cronos-remediation-plan` (commit 635ca5c) to document the least-privilege git credential model and push policy:

1. **README.md** — Added "Git credential model" section with scope table and autopilot_pr note.
2. **.env.example** — Extended CRONOS_GIT_TOKEN block with GitHub/GitLab setup guidance and do-not-grant list.
3. **deploy/VPS_SETUP.md** — Added §5.3 "Git push credentials" with push policy ADR, PAT creation steps, and credential rotation.

## Coverage

**`README.md` — new "Git credential model" section**
- Least-privilege scope table (clone=Contents:read, push=Contents:write)
- Never grant admin/workflow/org scopes
- Reference to VPS_SETUP.md §5.3 and .env.example for full details
- Note on autopilot_pr PR-gate (never auto-merges)
- ✓ Verified: docs/GIT_CREDENTIAL_MODEL section added (commit 635ca5c)

**`.env.example` — expanded CRONOS_GIT_TOKEN block**
- GitHub setup steps (fine-grained token creation)
- Scope guidance (Contents:Read for clone, Contents:Write for push)
- Reference to VPS_SETUP.md §5.3 for detailed PAT creation
- GitLab guidance (project/group access token with write_repository)
- Future path note (GitHub App installation tokens)
- ✓ Verified: lines ~31–50 expanded with GitHub/GitLab/future guidance (commit 635ca5c)

**`deploy/VPS_SETUP.md` — new §5.3 "Git push credentials"**
- Push policy ADR: push-to-origin+PR, never auto-merge (autopilot_pr gate)
- Rationale: push-to-fork is only useful for multi-operator; single-operator model uses push-to-origin
- Least-privilege credential model: fine-grained PAT per repo, Contents:write only
- Explicit "Do NOT grant" list (admin, workflow, org scopes)
- Step-by-step PAT creation via GitHub UI (Repository access → Contents:Write)
- VPS configuration (add to .env, restart backend)
- Token rotation steps
- Future GitHub App path noted but deferred
- ✓ Verified: §5.3 added (commit 635ca5c) with all required subsections

**`backend/app/git_ops.py` — in-code comments & docstrings**
- `_GIT_TOKEN_ENV` constant with note on least-privilege scope
- `_auth_env()` docstring: explains Authorization: Basic header injection
- `push_branch()` docstring: clarifies env parameter for _auth_env() result
- `gh_pr_create()` docstring: confirms PR-open-only, no auto-merge
- ✓ Verified: comments added, no signature/behaviour changes (commit 635ca5c)

## Findings

- **No blocking issues.** All three user-facing docs sections are complete,
  accurate, and correctly reference each other.
- **No CLAUDE.md updates needed.** G11 is purely ops/credential setup; CLAUDE.md
  documents architecture, which G11 does not change.
- **Credibility notes:** Test coverage (test_git_ops_auth_env.py,
  test_no_pat_in_traces.py) asserts that the PAT never appears in ps output or
  logs, validating the `GIT_CONFIG_*` env injection mechanism described in the
  docs.

## Assumptions

- The feature/cronos-remediation-plan branch is the canonical source for G11
  implementation (verified: impl + test + review commits merged there).
- "Docs updated" count excludes test files (test_git_ops_auth_env.py,
  test_no_pat_in_traces.py) and impl-phase artifacts (analysis/design/impl/test/review reports).
- Least-privilege PAT creation is assumed to be the operator's responsibility
  (per docs); Cronos itself has no PAT-generation UI.

## Open questions

- None. (Operator credential Q1 — one PAT vs. separate clone/push PATs — is
  documented as an operator decision in §5.3, not a blocker.)

## Intentionally not updated

1. **§5.3 residual-risk sentence (F2, low, non-blocking):** Review finding F2
   noted that §5.3 implicitly states a compromised run can still push a branch
   + open a PR (bounded by autopilot_pr), but doesn't make this explicit in one
   sentence. The existing ADR + autopilot_pr note is sufficient; adding a
   residual-risk callout is optional polish, deferred. The threat is already
   bounded by the documented PR-gate (never auto-merge).

## Next consumer brief

Pipeline complete. Merge `feature/cronos-remediation-plan` to `main` and
document in deployment runbooks / ops wikis if needed. G11 coverage:

- Operators now have a clear least-privilege PAT model (clone:read, push:write
  per-repo; never admin/workflow/org).
- Push policy is documented as push-to-origin+PR (no auto-merge); future
  multi-operator deployments can evaluate push-to-fork.
- Credential injection mechanism is verifiable in source (GIT_CONFIG_* env vars
  + trace redaction patterns).
