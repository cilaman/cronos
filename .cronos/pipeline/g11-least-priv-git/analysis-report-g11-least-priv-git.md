---
cc_version: '1.0'
agent: pipeline-analyst
slug: g11-least-priv-git
phase: analysis
status: done
confidence: 0.82
inputs_used:
- memory:project-remediation-board-setup
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- backend/app/git_ops.py
- .env.example
- deploy/VPS_SETUP.md
- README.md
outputs_produced:
- .cronos/pipeline/g11-least-priv-git/analysis-report-g11-least-priv-git.md
blockers: []
next_consumer: design
request: 'G11: Least-privilege git credentials + push policy. Reduces git credential
  scope so a compromised run can''t write arbitrary content to the repo. After: No
  broad-scope PAT in the default path; credential model is documented. Push uses minimum-scope
  credentials (contents:write per-repo only; no admin/workflow). Push-to-fork + PR
  is considered and documented or implemented. The autopilot_pr review gate is preserved
  (good existing control). A prompt-injected run currently can autonomously push using
  a write-credentialed PAT.'
has_ui: false
coverage_summary:
  searched:
  - backend/app/git_ops.py (credential injection, push_branch, gh_pr_create)
  - .env.example (CRONOS_GIT_TOKEN documentation)
  - deploy/VPS_SETUP.md (SSH deploy key docs)
  - README.md (credential setup references)
  - .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
  excluded:
  - frontend/: no git credential surface exists there
  - backend/tests/: read coverage deferred to architect/impl phases
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: 'The credential model is documented: CRONOS_GIT_TOKEN required scope,
    lifetime, and rotation procedure are stated in .env.example and deploy/VPS_SETUP.md.'
  acceptance_criteria:
  - Given a fresh checkout, when a developer reads .env.example, they see the minimum
    required GitHub PAT scopes (contents:read for clone-only spaces; contents:write
    for push-enabled spaces) and are instructed to exclude admin and workflow scopes.
  - .env.example and deploy/VPS_SETUP.md are updated and consistent with each other.
  - A test or review step confirms the documentation is present and references correct
    scope names.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R2
  statement: Push operations use a separate, narrower credential than clone operations
    wherever different token scopes are technically feasible.
  acceptance_criteria:
  - Given CRONOS_GIT_TOKEN is set to a contents:write-scoped fine-grained PAT, when
    push_branch() is called, git authenticates and pushes successfully.
  - A test verifies that push_branch() passes auth credentials via _auth_env(), not
    via stored git config or .netrc.
  - No broad scope (admin, workflow, repo:full) is required or documented as acceptable
    for normal push use.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R3
  statement: The push-to-fork + PR workflow is evaluated and the chosen policy (push
    to origin branch + open PR via gh CLI, OR push to a fork) is documented with rationale.
  acceptance_criteria:
  - The analysis report or its successor design report records whether push-to-fork
    or push-to-origin-branch was selected and why.
  - The chosen policy is reflected in the implementation of push_branch() and gh_pr_create().
  - The autopilot_pr gate (gh_pr_create) is preserved and not disabled.
  verifying_phase: review
  confidence: 0.75
- requirement_id: R4
  statement: The autopilot_pr review gate (gh_pr_create) is documented as the primary
    human-gate control and is preserved across this change.
  acceptance_criteria:
  - gh_pr_create() continues to function after any credential changes.
  - The security-posture note (G12) or inline code comments state that autopilot_pr
    is the intended review gate.
  - No code path merges a PR automatically; the gate is a PR-open, not a PR-merge.
  verifying_phase: review
  confidence: 0.92
- requirement_id: R5
  statement: CRONOS_GIT_TOKEN is never logged, never included in git subprocess args
    (ps-visible), and never committed to the repo in any form.
  acceptance_criteria:
  - Grep of git_ops.py confirms GIT_CONFIG_VALUE_0 carries the token, not a positional
    arg.
  - The test_no_pat_in_traces guard (backend/tests/test_no_pat_in_traces.py) covers
    the CRONOS_GIT_TOKEN env var pattern in addition to its existing patterns.
  - A negative test confirms the token does not appear in git command log lines (the
    log.info call at git_ops.py:52).
  verifying_phase: test
  confidence: 0.9
- requirement_id: R6
  statement: The credential injection mechanism (_auth_env) is covered by unit tests
    that assert correct Authorization header construction and non-HTTPS URL bypass.
  acceptance_criteria:
  - Given CRONOS_GIT_TOKEN is set, _auth_env() returns an env dict containing GIT_CONFIG_VALUE_0
    with the correct base64-encoded Authorization header.
  - Given the repo URL is SSH (git@...), _auth_env() returns None.
  - Given CRONOS_GIT_TOKEN is unset, _auth_env() returns None.
  verifying_phase: test
  confidence: 0.95
metrics:
  tool_calls: 8
  files_read: 5
  memory_hits: 1
---

## Summary

G11 reduces the blast radius of a prompt-injected agent run by ensuring git credentials are scoped to the minimum required for each operation, that the credential model is documented, and that the `autopilot_pr` review gate is preserved as the human checkpoint on any autonomous push. The existing `_auth_env()` / `GIT_CONFIG_*` injection pattern is already secure from a ps-visibility standpoint; the gap is scope documentation, push-scope enforcement, and test coverage of the credential plumbing. No UI is involved.

## Scope

### In scope
- Document required CRONOS_GIT_TOKEN GitHub PAT scopes in .env.example and deploy/VPS_SETUP.md (distinguish clone-only vs push-enabled)
- Verify and assert that push_branch() uses _auth_env() (not netrc/stored config) for credential injection
- Evaluate push-to-origin-branch vs push-to-fork and record the decision with rationale
- Preserve and document autopilot_pr (gh_pr_create) as the human review gate
- Unit-test _auth_env() for all three cases (token set + HTTPS, token set + SSH, token unset)
- Ensure CRONOS_GIT_TOKEN is excluded from git log lines and trace files

### Out of scope
- GitHub App installation tokens or OAuth device flows (deferred; requires server-side infrastructure)
- Per-space credential storage (single-user design; multi-user is a future ADR item)
- Implementing push-to-fork automatically (decision may be document-only; depends on operator setup)
- frontend/ changes (no git surface there)
- G03 container-level egress controls (separate goal; complementary but independent)

### Deferred
- Per-space or per-user PAT rotation API (requires multi-user architecture; see .env.example comment)
- GitHub App installation token support (short-lived tokens; stronger than PAT; needs server-side OAuth flow)
- Egress-level enforcement that the push target is the expected origin (G03 territory)

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Credential model documented in .env.example + VPS_SETUP.md with scope guidance |
| R2 | Push operations use contents:write-scoped PAT; no broad scope required |
| R3 | Push-to-fork vs push-to-branch policy evaluated and recorded |
| R4 | autopilot_pr gate preserved and documented |
| R5 | CRONOS_GIT_TOKEN never ps-visible, never logged, never committed |
| R6 | _auth_env() covered by unit tests for HTTPS/SSH/unset cases |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — .env.example + VPS_SETUP.md describe minimum scopes (contents:read / contents:write); no admin/workflow scope permitted
- R2 — push_branch() authenticated via _auth_env() env injection; test asserts no positional-arg leakage; contents:write-scoped PAT is sufficient
- R3 — Push policy decision recorded; autopilot_pr preserved regardless of choice
- R4 — gh_pr_create() works post-change; no auto-merge path exists; gate is PR-open only
- R5 — GIT_CONFIG_VALUE_0 carries token, not args; log lines don't include token; trace guard extended
- R6 — Unit tests cover HTTPS+token, SSH+token, and no-token cases for _auth_env()

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | review | Credential model documented in .env.example and deploy/VPS_SETUP.md |
| R2 | test | Push uses contents:write-scoped PAT via env injection only |
| R3 | review | Push-to-fork vs push-to-branch policy evaluated and documented |
| R4 | review | autopilot_pr gate preserved and documented as human checkpoint |
| R5 | test | CRONOS_GIT_TOKEN never ps-visible, logged, or committed |
| R6 | test | _auth_env() unit-tested for all three input cases |

## Assumptions

- `has_ui: false` rationale: G11 is entirely backend + documentation. The credential injection happens in `backend/app/git_ops.py`; no frontend component touches git operations.
- The current PAT injection mechanism (`GIT_CONFIG_*` env vars) is already good from a process-visibility standpoint (not in `ps` args). The gap is scope documentation and test coverage, not a new injection mechanism.
- The scout confirmed `autopilot_pr` is not yet implemented as a function in git_ops.py (no grep match), but `gh_pr_create()` exists and is the semantic equivalent. R4 treats `gh_pr_create()` as the autopilot_pr gate.
- Push-to-origin-branch (current pattern) is the likely documented choice for a single-user personal repo; push-to-fork adds complexity without commensurate security benefit for this threat model. R3 is kept as a review-phase requirement to surface the operator's actual setup.
- `.env.example` already has a partially correct comment on CRONOS_GIT_TOKEN (`Contents:read`). R1 requires this to be extended to cover the push case (contents:write) and to explicitly exclude admin/workflow scopes.
- Confidence is 0.82 (not 0.85) because R3 depends on operator GitHub setup that the implementing agent cannot verify in code — the design agent should flag this as an open decision requiring human input.
- G11 confidence in the remediation plan is Med-High, reflecting the same operator-setup dependency.

## Open questions

- **Q1 (R3):** Does the operator's GitHub setup use a single PAT for clone + push, or separate tokens? The design should surface this as an option and recommend the safest pattern (separate fine-grained PATs with minimal per-repo scope vs one combined token). The implementing agent cannot know this from code alone.
- **Q2 (R2):** Should `push_branch()` accept an explicit `token` override, allowing the caller to pass a narrower push-only credential separate from the clone credential? This would be the cleanest separation but requires an API change to `git_ops.py`. Design agent should evaluate.

## Next consumer brief

**Design agent:** Read `traceability[]` for all 6 requirements and `## Scope` for boundaries.

Key decision points:
1. **R3 is the pivot.** Decide whether to implement push-to-fork (requires fork detection + remote setup) or document push-to-origin-branch with a contents:write-scoped fine-grained PAT. Lean toward documentation-only for a personal single-repo setup; implementation for fork push if the operator has multiple repos. Record as ADR.
2. **R1 + R2 are documentation iterations.** The code already does the right thing mechanically; the gap is scope guidance in .env.example and VPS_SETUP.md.
3. **R5 + R6 are test-first.** Write unit tests for _auth_env() before any code changes; they document the invariant and catch regressions. Extend test_no_pat_in_traces.py to cover CRONOS_GIT_TOKEN patterns.
4. **R4 requires no code change** — just a code comment and doc note preserving gh_pr_create() as intentional.
5. Scope files: `backend/app/git_ops.py`, `.env.example`, `deploy/VPS_SETUP.md`, `backend/tests/test_no_pat_in_traces.py`, and one new test file for `_auth_env()` unit tests.
