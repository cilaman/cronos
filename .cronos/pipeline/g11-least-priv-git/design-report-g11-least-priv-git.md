---
cc_version: '1.0'
agent: pipeline-architect
slug: g11-least-priv-git
phase: design
status: done
confidence: 0.82
inputs_used:
- memory:project-remediation-board-setup
- memory:cc-v1-contract-module
- .cronos/pipeline/g11-least-priv-git/analysis-report-g11-least-priv-git.md
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- backend/app/git_ops.py
- backend/app/trace_redact.py
- backend/tests/test_no_pat_in_traces.py
- backend/tests/test_git_ops.py
- backend/tests/test_autopilot_pr.py
- .env.example
- deploy/VPS_SETUP.md
- README.md
outputs_produced:
- .cronos/pipeline/g11-least-priv-git/design-report-g11-least-priv-git.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/git_ops.py
  - backend/app/trace_redact.py
  - backend/tests/test_git_ops.py
  - backend/tests/test_no_pat_in_traces.py
  - backend/tests/test_autopilot_pr.py
  - .env.example
  - deploy/VPS_SETUP.md
  - README.md
  excluded:
  - 'frontend/: no git credential surface exists there'
  - 'backend/app/autopilot_pr.py: review-gate logic confirmed PR-open-only, but out
    of the brief''s scope_files (R4 comment lands in git_ops.py gh_pr_create)'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/tests/test_git_ops_auth_env.py
  - backend/tests/test_no_pat_in_traces.py
  validation_command: cd backend && pytest tests/test_git_ops_auth_env.py tests/test_no_pat_in_traces.py
    -v
  max_diff_lines: 220
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/git_ops.py
  validation_command: cd backend && pytest tests/test_git_ops.py tests/test_git_ops_auth_env.py
    tests/test_autopilot_pr.py -v
  max_diff_lines: 90
  depends_on:
  - I1
- id: I3
  type: infra
  scope_files:
  - .env.example
  validation_command: grep -qiE 'contents:write' .env.example && grep -qiE 'admin'
    .env.example && grep -qiE 'workflow' .env.example
  max_diff_lines: 70
  depends_on: []
- id: I4
  type: infra
  scope_files:
  - deploy/VPS_SETUP.md
  - README.md
  validation_command: grep -qiE 'contents:write' deploy/VPS_SETUP.md && grep -qiE
    'least.privilege|credential model' deploy/VPS_SETUP.md && grep -qiE 'credential'
    README.md
  max_diff_lines: 160
  depends_on: []
risks:
- description: R3 push policy depends on the operator's actual GitHub/PAT setup (single
    combined token vs separate fine-grained PATs), which cannot be verified from code.
    A doc that mandates a setup the operator does not have could break clone/push
    on the live VPS.
  severity: medium
  mitigation: I4 documents push-to-origin-branch + autopilot PR as the chosen policy
    and presents the credential model as the recommended pattern (separate clone vs
    push fine-grained PATs) WITHOUT changing the single-CRONOS_GIT_TOKEN code path;
    the existing combined-token flow keeps working. Open question Q1 stays open for
    the operator.
- description: I2 is intended as comment-only documentation in git_ops.py. An implementor
    could over-reach and add a `token=` override parameter to push_branch()/_auth_env()
    (analyst Q2), changing the public signature and breaking autopilot_pr callers.
  severity: medium
  mitigation: scope_files for I2 is limited to backend/app/git_ops.py and the validation_command
    re-runs test_git_ops.py + test_autopilot_pr.py; the Next consumer brief explicitly
    forbids signature/behaviour changes — comments and docstrings only.
- description: CRONOS_GIT_TOKEN could leak into the git command log line (git_ops.py:52
    log.info) or into trace JSONs, defeating least-privilege by exposing the credential.
  severity: low
  mitigation: I1 adds a negative test asserting the token value never appears in caplog
    when push_branch runs with auth env (token rides GIT_CONFIG_VALUE_0, never argv);
    SECRET_PATTERNS in trace_redact.py already redact ghp_/github_pat_/gho_/ghs_/ghr_/x-access-token
    forms, so I1 asserts coverage rather than adding new patterns.
- description: I3/I4 validation_commands are grep string-matches that could pass on
    an incidental occurrence of a keyword rather than a real credential-model section.
  severity: low
  mitigation: Each grep validation requires multiple co-occurring anchored tokens
    (e.g. both 'contents:write' AND 'admin' AND 'workflow' for .env.example), so an
    incidental single match cannot satisfy it; the review phase re-reads the prose
    for correctness.
metrics:
  tool_calls: 12
  files_read: 10
  memory_hits: 2
  iterations_planned: 4
---

## Summary

G11 hardens git credential scope so a prompt-injected run cannot escalate beyond the existing `autopilot_pr` PR-open gate. The code is already mechanically sound — `_auth_env()` injects the PAT via `GIT_CONFIG_*` env (never argv), `push_branch()` already uses it, and `trace_redact.SECRET_PATTERNS` already redact every GitHub PAT form — so the real gaps are scope **documentation**, **test coverage** of the credential plumbing, and a recorded **push-policy decision**. The DAG is deliberately wide: three independent layer-0 iterations (one test, two docs) plus one comment-only code iteration depending on the tests. The load-bearing tradeoff (captured in the risk register) is that R3 hinges on operator GitHub setup the agent cannot inspect, so the chosen policy is documented and recommended — not silently enforced via a code/signature change.

## ADR — push policy decision (R3)

**Decision: push-to-origin-branch + open a PR via `autopilot_pr` → `gh_pr_create()`. Do NOT implement push-to-fork.**

Rationale: Cronos is an explicitly single-user, single-account personal platform (`git_ops.py:84-92`). Push-to-fork buys isolation only across *distinct accounts*; with one operator and one account it adds fork-detection + dual-remote plumbing for no reduction in blast radius. The blast radius is instead bounded by (a) scoping the PAT to `contents:write` on specific repos only — never `admin`/`workflow` — and (b) the `autopilot_pr` gate, which opens a PR and never auto-merges (`autopilot_pr.run_post_done_flow` → `git_ops.gh_pr_create`, PR-open only). Push-to-fork is recorded as a *deferred* option for a future multi-operator design. This decision satisfies R3 acceptance criterion 1 (the design report records the choice and why); I4 reflects it in the operator docs; the code already implements push-to-origin-branch.

## Components

### Data
- (none) — G11 introduces no schema, model, or migration changes.

### Backend
- `backend/app/git_ops.py::_auth_env` — unchanged behaviour; gains a least-privilege scope note in the `_GIT_TOKEN_ENV` comment block (clone=contents:read, push=contents:write, never admin/workflow).
- `backend/app/git_ops.py::push_branch` — unchanged behaviour; already injects credentials via `_auth_env(url)`; gains a one-line comment confirming the narrow-scope contract.
- `backend/app/git_ops.py::gh_pr_create` — unchanged behaviour; gains a comment stating it is the intentional `autopilot_pr` human review gate (PR-open, never merge).
- `backend/app/trace_redact.py::SECRET_PATTERNS` — read-only reference; already covers all token forms (no change; asserted by I1).
- `backend/tests/test_git_ops_auth_env.py` (new) — unit tests for `_auth_env()` (HTTPS+token, SSH+token, token-unset) and `push_branch()` credential-injection + token-not-in-log assertions.
- `backend/tests/test_no_pat_in_traces.py` — extended to assert the `CRONOS_GIT_TOKEN` value forms are caught by `SECRET_PATTERNS`.

### Frontend
<!-- Omitted: has_ui=false in the analysis report; no git credential surface in frontend/. -->

## Implementation plan

| ID  | Type    | Depends on | Scope files (abridged)                                      | Validation                                                                 |
|-----|---------|------------|-------------------------------------------------------------|-----------------------------------------------------------------------------|
| I1  | backend | -          | backend/tests/test_git_ops_auth_env.py, test_no_pat_in_traces.py | cd backend && pytest tests/test_git_ops_auth_env.py tests/test_no_pat_in_traces.py -v |
| I2  | backend | I1         | backend/app/git_ops.py                                      | cd backend && pytest tests/test_git_ops.py tests/test_git_ops_auth_env.py tests/test_autopilot_pr.py -v |
| I3  | infra   | -          | .env.example                                                | grep -qiE 'contents:write' .env.example && grep -qiE 'admin' && 'workflow'  |
| I4  | infra   | -          | deploy/VPS_SETUP.md, README.md                              | grep -qiE 'contents:write' deploy/VPS_SETUP.md && 'least.privilege' && README 'credential' |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| R3 push policy depends on un-inspectable operator GitHub/PAT setup; a mandated setup could break the live VPS | medium | Document + recommend the credential model without changing the single-token code path; keep Q1 open for the operator |
| I2 over-reach: implementor adds a `token=` override, changing public signatures and breaking autopilot_pr callers | medium | scope_files limited to git_ops.py; validation re-runs test_autopilot_pr.py; brief forbids signature/behaviour change (comments only) |
| CRONOS_GIT_TOKEN leaks into git log line (git_ops.py:52) or trace JSONs | low | I1 negative test asserts token absent from caplog; SECRET_PATTERNS already redact every token form (assert, don't add) |
| I3/I4 grep validations pass on incidental keyword matches | low | Each validation requires multiple co-occurring anchored tokens; review phase re-reads prose |

## Assumptions

- The slug is used verbatim from the task prompt (`g11-least-priv-git`); single slug → `parent_slug == slug`; artifact lives beside the analysis report at the space-root pipeline dir.
- `has_ui=false` is carried forward from analysis — no frontend iterations.
- The existing PAT injection (`GIT_CONFIG_*` env, not argv) is already ps-safe and is NOT being re-engineered; G11 documents + tests it. This is the analyst's explicit finding.
- `autopilot_pr` is implemented in `backend/app/autopilot_pr.py` (`run_post_done_flow`), not in `git_ops.py`; `gh_pr_create()` is the PR-open seam it calls. The R4 inline comment is placed on `gh_pr_create()` because `git_ops.py` is the only in-scope source file per the brief; `autopilot_pr.py` is intentionally excluded from scope_files.
- `.env.example` already documents `CRONOS_GIT_TOKEN` with a `Contents:read` note (lines 31-41); I3 extends rather than replaces it (add push/contents:write case + explicit admin/workflow exclusion + rotation pointer).
- `deploy/VPS_SETUP.md` currently documents a read-only SSH **deploy key** (§5.1) for `git fetch`; the HTTPS PAT credential model for push is a distinct, missing section that I4 adds (it does not contradict the deploy-key path).
- Confidence is capped at the analysis report's 0.82 because R3 depends on operator setup the pipeline cannot verify in code.

## Open questions

- **Q1 (R3, operator decision):** Does the operator use one combined `CRONOS_GIT_TOKEN` for clone+push, or separate fine-grained PATs? I4 recommends separate per-repo `contents:read`/`contents:write` PATs but must not break the single-token path. The operator confirms during review; no code change blocks on this.

## Next consumer brief

Read `iterations[]`, then per entry `scope_files`, `validation_command`, `depends_on`. Layer 0 runs I1, I3, I4 in parallel; I2 runs after I1.

- **I2 is comment/docstring-only.** Do NOT change any function signature, return type, or runtime behaviour in `git_ops.py` — no `token=` parameter (analyst Q2 is rejected for this minimal-scope goal). The validation re-runs `test_autopilot_pr.py` precisely to catch accidental behaviour drift.
- **Cross-iteration invariant:** the new test file MUST be named exactly `backend/tests/test_git_ops_auth_env.py` — I1 creates it and I2's `validation_command` references it literally.
- **R5 is assert-not-add:** `trace_redact.SECRET_PATTERNS` already redacts every GitHub PAT form; I1 asserts that coverage (and that the token never reaches argv/log) rather than introducing new regex.
- **Push policy is decided** (see `## ADR`): push-to-origin-branch + PR. I4 documents it; do not implement push-to-fork.
- Carry the `## ADR` decision text into the I4 doc sections so R3 acceptance criteria 1 and 2 both resolve.
