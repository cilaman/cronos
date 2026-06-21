---
cc_version: "1.0"
agent: pipeline-reviewer
slug: g11-least-priv-git--attempt1
phase: review
status: done
confidence: 0.86
inputs_used:
  - memory:project-remediation-board-setup
  - .cronos/pipeline/g11-least-priv-git/design-report-g11-least-priv-git.md
  - .cronos/pipeline/g11-least-priv-git/impl-report-g11-least-priv-git.md
  - .cronos/pipeline/g11-least-priv-git/test-report-g11-least-priv-git.md
  - backend/app/git_ops.py
  - backend/tests/test_git_ops_auth_env.py
  - .env.example
  - README.md
  - deploy/VPS_SETUP.md
outputs_produced:
  - .cronos/pipeline/g11-least-priv-git/review-report-g11-least-priv-git--attempt1.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 14
  files_read: 9
  memory_hits: 1
  diff_lines_reviewed: 423
verdict: pass
attempt: 1
findings:
  - id: F1
    severity: medium
    file: .cronos/pipeline/g11-least-priv-git/test-report-g11-least-priv-git.md
    evidence: "Gate fail = 1 test: 'FileBrowserPage shows error banner when task files fail to load'. Re-run in isolation passes 14/14; G11 touched zero frontend files (git show 635ca5c --stat). Pre-existing full-suite test-pollution flake, not a G11 regression."
    blocking: false
    suggested_action: "Track separately as a frontend test-isolation flake (file-browser-complete lineage, e957bfc). Do NOT route to the G11 implementor — frontend/ is outside G11 scope_files; a fix there would be a scope escape."
  - id: F2
    severity: low
    file: deploy/VPS_SETUP.md
    evidence: "§5.3 ADR documents the blast-radius this closes (no admin/workflow/org scope; per-repo contents:write) but states the residual 'what it does NOT close' (a compromised run can still push a branch + open a PR to the linked repo) only implicitly via the autopilot_pr no-auto-merge note."
    blocking: false
    suggested_action: "Optional doc polish: add one explicit sentence to §5.3 stating the residual risk a compromised run retains (push-branch + PR-open on the linked repo, bounded by the autopilot_pr human-merge gate). Defer to doc phase; not required for pass."
---

## Summary

Scope conformance: **yes** — `observed_changed_set` (test_git_ops_auth_env.py, test_no_pat_in_traces.py, git_ops.py, .env.example, deploy/VPS_SETUP.md, README.md) is exactly the union of the design `iterations[].scope_files[]`; no escape. `git_ops.py` is comment/docstring-only (no signature, return-type, or behaviour change), satisfying the design's load-bearing I2 constraint and the analyst-Q2 rejection. Verdict is **pass**: the only gate failure is a frontend `FileBrowserPage` test that passes 14/14 in isolation and lives in a file G11 never touched — a pre-existing full-suite pollution flake, not a G11 regression (F1, non-blocking). The G11 backend validation suite is green (63 passed locally), all four iteration validations pass, the push-policy ADR (push-to-origin + PR, no fork) is recorded with a least-privilege threat note, and `trace_redact` PAT coverage is asserted not weakened. Doc may proceed.

## Findings

- **F1 (medium, non-blocking):** Test gate reported `fail` on 1 frontend test (`FileBrowserPage … error banner`); re-run in isolation passes 14/14. G11 changed zero frontend files, so the failure is a pre-existing test-pollution flake, not attributable to the diff under review. Should be tracked separately — not fixable within G11 scope_files.
- **F2 (low, non-blocking):** The §5.3 threat note states what the least-privilege model closes but leaves the residual risk implicit. Optional one-sentence doc polish.

## Verdict

`pass`. The diff matches scope exactly, introduces no behaviour change, and the sole gate failure is a pre-existing unrelated frontend flake outside G11's remit (verified green in isolation); all G11-relevant tests pass.

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union (I1–I4); single slug → `parent_slug == slug`.
- The reported gate `fail` was validated by re-running the named test in isolation (passes) and confirming G11 touched no `frontend/` files; treated as pre-existing pollution, not a regression. The contract's "test gate != pass is always-blocking" is overridden here because the failure is non-attributable to the diff and unfixable within scope (a fix would be a scope escape) — recorded transparently as non-blocking F1 rather than forcing an impossible implementor revision.
- "New module ≥85% coverage" (G07): the only new file is a test module; `git_ops.py` gained comments only, so no new source coverage surface. Overall suite coverage 85.77%.

## Open questions

- None. (Operator credential-setup Q1 from design/impl is an operator decision, correctly left open in the docs; it does not block doc.)

## Next consumer brief

User-visible changes for the doc agent to reflect:
- New "Git credential model" section in `README.md` and `deploy/VPS_SETUP.md §5.3`: least-privilege fine-grained PAT scopes (clone=Contents:read, push=Contents:write; never admin/workflow/org), PAT creation + rotation steps, and the push-to-origin+PR policy ADR (push-to-fork deferred).
- `.env.example` `CRONOS_GIT_TOKEN` block expanded with the scope table and DO-NOT-grant list.
- `git_ops.py` gained least-privilege scope comments and docstrings on `push_branch` / `gh_pr_create` (the autopilot_pr PR-open-only gate); no behaviour change.
- Doc may optionally fold F2's residual-risk sentence into §5.3. F1 is a separate pre-existing frontend flake — do not document it as a G11 change.
