---
cc_version: '1.0'
agent: pipeline-architect
slug: g01-green-main
phase: design
status: done
confidence: 0.9
inputs_used:
- memory:test-no-pat-traces-guard
- memory:cc-v1-contract-module
- memory:integration-baseline
- .cronos/pipeline/g01-green-main/analysis-report-g01-green-main.md
- backend/tests/test_no_pat_in_traces.py
- backend/app/trace_redact.py
- .gitignore
outputs_produced:
- .cronos/pipeline/g01-green-main/design-report-g01-green-main.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/tests/test_no_pat_in_traces.py
  - backend/app/trace_redact.py
  - .gitignore
  - backend/tests/test_trace_redact.py
  excluded:
  - 'frontend/: has_ui=false, no UI changes'
  - 'backend/app/agent.py: trace-capture refactor deferred per analysis OUT-of-scope'
  - '.cronos/harnesses/, .cronos/pipeline/, .cronos/issues/, .cronos/qa/, .cronos/space.yml:
    kept tracked per analysis decision'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: infra
  scope_files:
  - .gitignore
  validation_command: git check-ignore -q .cronos/traces .cronos/tasks .cronos/workspaces
    .cronos/stats .cronos/memory .cronos/.trash .cronos/test-reports .cronos/harness-runs
    .cronos/test-coverage.md && [ "$(git ls-files .cronos/tasks .cronos/workspaces
    .cronos/traces .cronos/stats .cronos/memory .cronos/.trash .cronos/test-reports
    .cronos/harness-runs | wc -l)" = 0 ] && [ -n "$(git ls-files .cronos/space.yml
    .cronos/harnesses/)" ]
  max_diff_lines: 60
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/tests/test_no_pat_in_traces.py
  validation_command: cd backend && pytest tests/test_no_pat_in_traces.py -v
  max_diff_lines: 40
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - backend/app/trace_redact.py
  validation_command: cd backend && pytest tests/test_trace_redact.py tests/test_no_pat_in_traces.py
    -v
  max_diff_lines: 30
  depends_on: []
risks:
- description: If .cronos/traces/ is not fully untracked before the R3 guard fix lands,
    git ls-files still returns committed traces and test_committed_traces_contain_no_pat
    keeps failing. Ordering between the untrack op (I1) and the test fix (I2) is load-bearing.
  severity: high
  mitigation: I2 declares depends_on:[I1]; the orchestrator runs I1 in layer 0 and
    I2 only after I1 commits. I1's validation_command asserts git ls-files of the
    8 runtime dirs is empty before I2 runs.
- description: A glob-based git rm (e.g. git rm -r --cached .cronos/) would untrack
    space.yml, harnesses/, pipeline/, issues/, qa/ — legit config and definitional
    artifacts that must stay tracked.
  severity: high
  mitigation: I1 enumerates exactly the 8 runtime dirs + test-coverage.md in both
    the .gitignore rules and the git rm -r --cached command — never a .cronos/* glob.
    I1's validation_command positively asserts space.yml and harnesses/ remain tracked
    (git ls-files non-empty).
- description: git rm -r --cached run in the wrong worktree/branch could untrack files
    on main or stage ~2,500 deletions against an unintended ref.
  severity: medium
  mitigation: --cached is non-destructive on disk (the running instance reads the
    filesystem, not git objects). The implementor runs the op only inside its feature-branch
    workspace worktree and confirms git branch --show-current is the goal feature
    branch before executing.
- description: The R3 fix could accidentally alter the CRONOS_TRACES_DIR rglob branch
    (lines 26-27) and break the canary test test_no_pat_in_traces__detects_canary.
  severity: medium
  mitigation: I2 touches only the `if result.returncode == 0 and result.stdout.strip()`
    branch, adding an explicit early `return []` when git succeeds with empty stdout;
    the env-override branch and the FileNotFoundError/TimeoutExpired fallback are
    left byte-for-byte unchanged. I2's validation runs the whole file so the canary
    sub-test must stay green.
- description: The git rm -r --cached operation produces ~2,500 staged index deletions,
    which an implementor scope/diff check could misread as a massive out-of-budget
    change for a scope_files list of one file.
  severity: medium
  mitigation: I1's only content edit is to .gitignore (max_diff_lines:60 governs that).
    The staged index deletions are not edits to scope_files content and are expected
    — documented explicitly in the Next consumer brief so the implementor reports
    files_changed:[.gitignore] and treats the cached removals as an intended Bash
    side effect, not a scope violation.
metrics:
  tool_calls: 12
  files_read: 4
  memory_hits: 3
  iterations_planned: 3
---

## Summary

G01 turns `main` green by stripping ~2,500 committed runtime files from git tracking
and patching the one failing guard test, in three minimal-scope iterations. I1 (infra,
layer 0) adds `.gitignore` rules for the 8 pure-runtime `.cronos/` subdirs plus
`test-coverage.md` and runs `git rm -r --cached` to drop them from the index while
keeping every file on disk. I2 (backend, depends on I1) fixes `_scan_files()` so that
"git ls-files succeeds with empty output" early-returns `[]` instead of falling through
to a full on-disk `rglob`, which is the actual reason the test still fails once traces
are untracked. I3 (backend, independent of I1/I2) is a docstring-only annotation marking
`redact_trace_dict()` as the canonical redaction entry point, satisfying R4 with no
behavioural change. The DAG is two-wide at layer 0 (I1 ‖ I3) with I2 gated on I1; the
load-bearing tradeoff — captured in the risk register — is that I1 must land before I2
or the guard test stays red.

## Components

### Data
- `.gitignore`: add exclusion rules for the 8 runtime `.cronos/` subdirs and `test-coverage.md`; the git index removal of those paths is committed alongside.

### Backend
- `backend/tests/test_no_pat_in_traces.py` → `_scan_files()`: add an early `return []` when `git ls-files` exits 0 with empty stdout, so an untracked-traces repo scans nothing instead of rglob'ing on-disk files.
- `backend/app/trace_redact.py` → `redact_trace_dict()`: annotate as the canonical redaction entry point for trace capture (docstring only; patterns already correct and complete for all 6 PAT formats + URL + x-access-token).

## Implementation plan

| ID  | Type    | Depends on | Scope files (abridged)                  | Validation                                                              |
|-----|---------|------------|-----------------------------------------|------------------------------------------------------------------------|
| I1  | infra   | -          | .gitignore (+ git rm -r --cached op)    | git check-ignore + git ls-files assertions on 8 runtime dirs vs config |
| I2  | backend | I1         | backend/tests/test_no_pat_in_traces.py  | cd backend && pytest tests/test_no_pat_in_traces.py -v                  |
| I3  | backend | -          | backend/app/trace_redact.py             | cd backend && pytest tests/test_trace_redact.py tests/test_no_pat_in_traces.py -v |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Traces not untracked before guard fix → test stays red | high | I2 depends_on I1; I1 validation asserts 0 tracked runtime files before I2 runs |
| Glob git rm untracks space.yml/harnesses/pipeline/issues/qa | high | I1 enumerates exact 8 dirs + test-coverage.md; validation asserts space.yml & harnesses/ still tracked |
| git rm --cached in wrong worktree/branch | medium | --cached is disk-safe; implementor verifies feature branch before running |
| R3 fix breaks the CRONOS_TRACES_DIR canary branch | medium | Edit only the git-success branch; canary sub-test re-run in I2 validation |
| ~2,500 staged deletions misread as out-of-budget diff | medium | Only .gitignore is a content edit; cached deletions documented as intended Bash side effect |

## Assumptions

- **Slug verbatim.** `g01-green-main` is used exactly as passed; parent_slug == slug (no `--` fan-out).
- **Untrack set is exactly the analyst's list.** The 8 dirs (`.cronos/tasks/`, `.cronos/workspaces/`, `.cronos/traces/`, `.cronos/stats/`, `.cronos/memory/`, `.cronos/.trash/`, `.cronos/test-reports/`, `.cronos/harness-runs/`) plus `.cronos/test-coverage.md`; `.cronos/pipeline/`, `.cronos/issues/`, `.cronos/qa/`, `.cronos/harnesses/`, `.cronos/space.yml` stay tracked (analysis §Assumptions, confirmed).
- **No trace_redact code change is needed.** `SECRET_PATTERNS` already covers `github_pat_`, `ghp_`, `gho_`, `ghs_`, `ghr_`, URL-embedded tokens, and `x-access-token` (verified by reading the module); R4's only concrete deliverable is the "canonical entry point" annotation on `redact_trace_dict()`.
- **The git operation belongs inside I1's implementor.** `git rm -r --cached <8 dirs> .cronos/test-coverage.md` is run as a Bash step in I1, committed together with the `.gitignore` edit — not deferred as a manual prerequisite (analysis §Next consumer brief left this open; resolved here as embedded).
- **`test_trace_redact.py` exists** and is the right validation target for I3 (confirmed present in backend/tests/).
- **Commands are repo-root-relative.** Validation commands run from the workspace/worktree root (the git root); no absolute space path is hardcoded.

## Open questions

- None.

## Next consumer brief

Read `iterations[]`, each `scope_files`, `validation_command`, and `depends_on` directly from the YAML. Layer 0 = {I1, I3} (run in parallel); I2 runs only after I1 commits.

**I1 implementor — non-standard, read carefully:** edit `.gitignore` to add the 8 runtime dirs + `.cronos/test-coverage.md`, then run `git rm -r --cached .cronos/tasks .cronos/workspaces .cronos/traces .cronos/stats .cronos/memory .cronos/.trash .cronos/test-reports .cronos/harness-runs .cronos/test-coverage.md` as a Bash step. This stages ~2,500 deletions — that is EXPECTED and is NOT a scope violation; report `files_changed: [.gitignore]` (the only content edit) and note the cached removals as an intended side effect. NEVER use a `.cronos/*` glob. Confirm `git branch --show-current` is the goal feature branch first. `--cached` keeps files on disk, so the running instance is undisturbed.

**I2 implementor — surgical:** in `_scan_files()`, change only the git-success path so that when `result.returncode == 0` and `result.stdout.strip()` is empty it returns `[]` (no tracked traces ⇒ nothing to scan). Do NOT touch the `os.environ.get("CRONOS_TRACES_DIR")` rglob branch (lines 26-27) or the `except (FileNotFoundError, TimeoutExpired)` fallback — both must stay byte-for-byte to keep the canary green.

**I3 implementor — docstring only:** add an annotation to `redact_trace_dict()` (and/or a module docstring) declaring it the canonical redaction entry point for trace capture. No pattern or behaviour changes.

**Cross-iteration invariant:** the exact untrack set in I1's `.gitignore` must equal the set in I1's `git rm` command and must exclude `space.yml`, `harnesses/`, `pipeline/`, `issues/`, `qa/`. Definition of done = remediation-plan §G01 acceptance: `pytest` green on fresh clone, `git ls-files .cronos/ | wc -l` config-only, canary still fires, `space.yml` + harness defs tracked.
