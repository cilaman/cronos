---
cc_version: '1.0'
agent: pipeline-analyst
slug: g01-green-main
phase: analysis
status: done
confidence: 0.95
inputs_used:
- memory:test-no-pat-traces-guard
- memory:pipeline-analyst-agent
- memory:cc-v1-contract-module
- memory:integration-baseline
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .claude/agents/pipeline-analyst.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- backend/tests/test_no_pat_in_traces.py
- .gitignore
- backend/app/trace_redact.py
outputs_produced:
- .cronos/pipeline/g01-green-main/analysis-report-g01-green-main.md
blockers: []
next_consumer: design
request: 'G01: Green main + repo hygiene. Fix the single failing test in main and
  strip ~2,500 committed runtime files from git tracking. Files in scope: backend/tests/test_no_pat_in_traces.py,
  .gitignore, backend/app/trace_redact.py. Fix approach: (1) add .gitignore rules
  for runtime subdirs, (2) git rm -r --cached those dirs (keep files on disk), (3)
  fix the guard test — repoint it at the working tree OR add an allowlist for the
  known canary/example fixtures. Inspect .cronos/pipeline/, .cronos/issues/, .cronos/qa/
  before deciding whether to untrack them (they may mix definitions with runtime state).
  Keep .cronos/space.yml and .cronos/harnesses/ tracked.'
has_ui: false
coverage_summary:
  searched:
  - backend/tests/test_no_pat_in_traces.py (full read — guard logic + canary test)
  - backend/app/trace_redact.py (full read — SECRET_PATTERNS, _PATTERNS, redact_trace_dict)
  - .gitignore (full read — existing exclusion rules)
  - .cronos/ (ls of all subdirectories + git ls-files count)
  - .cronos/pipeline/, .cronos/issues/, .cronos/qa/ (ls to classify content)
  - .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md (§G01
    full read)
  - .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
    (§G01 findings)
  excluded:
  - frontend/: no UI changes for this goal
  - backend/app/agent.py: trace capture points are out of scope for G01 (deferred
      to R4)
  - .cronos/harnesses/: confirmed kept tracked; no inspection needed
  strategies:
  - memory_retrieval
  - read_targeted
  - glob_structural
traceability:
- requirement_id: R1
  statement: The .gitignore file must exclude all pure runtime .cronos/ subdirectories
    so they are never committed.
  acceptance_criteria:
  - Given the updated .gitignore, running `git status` on a fresh trace/task/workspace
    file shows it as untracked (not staged for commit).
  - '.gitignore must cover: .cronos/tasks/, .cronos/workspaces/, .cronos/traces/,
    .cronos/stats/, .cronos/memory/, .cronos/.trash/, .cronos/test-reports/, .cronos/harness-runs/,
    .cronos/test-coverage.md.'
  - .cronos/space.yml, .cronos/harnesses/, .cronos/pipeline/, .cronos/issues/, .cronos/qa/
    remain tracked (no ignore rule for them).
  verifying_phase: test
  confidence: 0.98
- requirement_id: R2
  statement: All currently-tracked pure runtime files under the above subdirs must
    be removed from the git index without deleting them from disk.
  acceptance_criteria:
  - After `git rm -r --cached` for each runtime subdir, `git ls-files .cronos/ | wc
    -l` drops from ~2,514 to config-only entries (single/low double digits).
  - Files remain present on disk after the operation (running instance is unaffected).
  - A commit containing the .gitignore changes and the index removal can be created
    cleanly (no staged deletions of config files).
  verifying_phase: test
  confidence: 0.97
- requirement_id: R3
  statement: The _scan_files() function in test_no_pat_in_traces.py must not fall
    back to scanning on-disk files when git ls-files succeeds but returns no tracked
    traces.
  acceptance_criteria:
  - When git ls-files exits 0 with empty stdout (no tracked traces), _scan_files()
    returns an empty list — not a rglob scan of on-disk files.
  - test_committed_traces_contain_no_pat passes on a clean checkout after R1+R2 land
    (no offenders).
  - The canary sub-test test_no_pat_in_traces__detects_canary still passes unchanged
    (it uses CRONOS_TRACES_DIR env override, unaffected by this fix).
  - 'The fallback to rglob is preserved for the failure cases: git not available (FileNotFoundError)
    or git timeout.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R4
  statement: The trace_redact.py module must export a complete and correct set of
    patterns sufficient for both the guard test and future content redaction.
  acceptance_criteria:
  - 'SECRET_PATTERNS (list[re.Pattern]) covers all GitHub PAT prefixes: ghp_, gho_,
    ghs_, ghr_, github_pat_; URL-embedded tokens; and x-access-token PATs.'
  - redact_trace_dict() is documented or annotated as the canonical redaction entry
    point for trace capture.
  - 'No new patterns are required (verified against current content: patterns already
    match the canary token format).'
  verifying_phase: review
  confidence: 0.9
metrics:
  tool_calls: 11
  files_read: 6
  memory_hits: 4
---

## Summary

G01 fixes Cronos's one failing test by removing ~2,500 committed runtime files from git
tracking and patching the test's fallback logic. The failing test
(`test_committed_traces_contain_no_pat`) fires because committed `.cronos/traces/` JSONs
contain PAT-shaped placeholder strings that the model wrote while building the redaction
feature; the root cause is that traces are committed at all. The fix has three parts:
add `.gitignore` rules for pure runtime `.cronos/` subdirs (R1), remove them from the
git index with `git rm -r --cached` without deleting on-disk files (R2), and patch
`_scan_files()` so that "git ls-files returns empty" is treated as "nothing to scan"
rather than falling back to a full disk rglob (R3). `trace_redact.py` is in scope for
verification but needs no substantive code changes (R4). Directories `.cronos/pipeline/`,
`.cronos/issues/`, and `.cronos/qa/` were inspected and are classified as intentional
definitional artifacts that must remain tracked.

## Scope

### In scope

- `.gitignore` — add exclusion rules for 8 runtime `.cronos/` subdirs + `test-coverage.md`
- Shell operation: `git rm -r --cached` for each runtime subdir (part of the commit)
- `backend/tests/test_no_pat_in_traces.py` — fix `_scan_files()` early-return when git succeeds with empty output
- `backend/app/trace_redact.py` — verify patterns and redact_trace_dict() are correct (no code change expected)
- Classify and decide on `.cronos/pipeline/`, `.cronos/issues/`, `.cronos/qa/` (decision made in this report: keep tracked)

### Out of scope

- `backend/app/agent.py` — trace capture pipeline and where `redact_trace_dict()` is called; changing the capture point requires wider refactor, belongs to a separate goal
- `.cronos/harnesses/` — confirmed tracked; no changes
- `.cronos/space.yml` — confirmed tracked; no changes
- History rewrite (`git filter-repo`) to purge old blobs from git history
- Any frontend or API changes

### Deferred

- Comprehensive application of `redact_trace_dict()` to all agent stdout/stderr at capture time in `agent.py` — the "optional, recommended" scrub from §G01. This is a G05-adjacent concern (structured completion) and is out of scope for the surgical G01 fix.
- Coverage of additional secret formats (e.g., GitLab CI tokens, npm tokens) — current patterns cover the failing-test scenario; extension is a separate decision.

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Add `.gitignore` rules for 8 runtime `.cronos/` subdirs and `test-coverage.md` |
| R2 | Remove tracked runtime files from git index (keep on disk) via `git rm -r --cached` |
| R3 | Fix `_scan_files()` fallback: treat empty `git ls-files` as "no tracked traces", not a disk scan trigger |
| R4 | Verify `trace_redact.py` exports complete patterns and correct redaction entry point |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]`
array (the machine-readable source of truth). The body summary below mirrors them
in compact form for the human reader.

- R1 — `.gitignore` covers tasks/, workspaces/, traces/, stats/, memory/, .trash/, test-reports/, harness-runs/, test-coverage.md; pipeline/, issues/, qa/, harnesses/, space.yml NOT excluded; git status treats new runtime files as untracked.
- R2 — `git ls-files .cronos/ | wc -l` drops from ~2,514 to config-only count; files remain on disk; commit succeeds cleanly.
- R3 — `test_committed_traces_contain_no_pat` passes with zero tracked traces; canary test unchanged and still green; rglob fallback preserved only for git-not-available cases.
- R4 — SECRET_PATTERNS covers all 6 PAT formats; redact_trace_dict() is the canonical redaction function; no code change required (review confirms correctness).

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML
`traceability[]` array. Downstream agents read the YAML directly; this section
exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | .gitignore must exclude all pure runtime .cronos/ subdirectories |
| R2 | test | Runtime files removed from git index without disk deletion |
| R3 | test | _scan_files() returns empty list when git ls-files succeeds with no output |
| R4 | review | trace_redact.py exports complete and correct patterns |

## Assumptions

- **`.cronos/pipeline/` → KEEP TRACKED.** Inspected: 40+ subdirectories contain CC-v1 pipeline report artifacts (scout, analysis, design, impl, test, review, doc reports). These are intentional goal-delivery work products, not runtime exhaust. Pipeline-state.json / phases-log.jsonl inside those dirs are minor runtime state but insufficient reason to untrack the whole directory; separating them sub-dir by sub-dir is disproportionate effort and deferred.
- **`.cronos/issues/` → KEEP TRACKED.** Inspected: 5 markdown files documenting specific issues (feature-dialogue, overflowing-lanes, fable-5-model, feature-fix-state-divergency, file-browser). These are intentional issue records, not runtime exhaust.
- **`.cronos/qa/` → KEEP TRACKED.** Inspected: 4 audit report files (features-backend-audit.md, features-frontend-audit.md, features-test-audit.md, refactoring-goals-created.md). These are intentional quality assurance documents.
- **has_ui: false rationale.** All changes are to `.gitignore`, one test file, and verification of a utility module. No React components, pages, or user-visible UI state involved.
- **The fallback logic bug is confirmed.** When `.cronos/traces/` is untracked, `git ls-files .cronos/traces/` returns exit 0 + empty stdout. The current `_scan_files()` condition `if result.returncode == 0 and result.stdout.strip()` evaluates to False → falls through to `return list(traces_dir.rglob("*.json"))` → scans all on-disk files → test still fails. R3 must fix this.
- **trace_redact.py needs no code changes.** Current patterns (7 compiled patterns covering all GitHub PAT prefixes, URL-embedded tokens, x-access-token) are correct and match the canary token format. The `redact_trace_dict()` function is already the right API; the apply-at-capture-time concern is deferred.
- **git rm --cached is non-destructive to the running instance.** Files remain on disk; only the git index changes. The live Cronos container reads files from the filesystem, not from git objects.

## Open questions

- None.

## Next consumer brief

**Design agent reads:** `traceability[]` for R1–R4, `## Scope` for boundaries, `## Assumptions` for the pipeline/issues/qa classification decision.

**Key decisions already made (no re-investigation needed):**
- `.cronos/pipeline/`, `.cronos/issues/`, `.cronos/qa/` → KEEP TRACKED (see Assumptions)
- `.cronos/tasks/`, `.cronos/workspaces/`, `.cronos/traces/`, `.cronos/stats/`, `.cronos/memory/`, `.cronos/.trash/`, `.cronos/test-reports/`, `.cronos/harness-runs/`, `.cronos/test-coverage.md` → UNTRACK

**Design iteration guidance:**
- I1 (safe to implement immediately): `.gitignore` additions + `git rm -r --cached` + commit
- I2 (depends on I1 landing): fix `_scan_files()` fallback → add early return when `result.returncode == 0 and not result.stdout.strip()` returns `[]`
- I3 (no code change): verify `trace_redact.py` correctness by reading it (review phase)
- The `git rm --cached` operation is non-standard for an implementor; design should decide whether to embed it as a Bash step within the I1 implementation or note it as a manual prerequisite.

**Risk flags:**
- If `.cronos/traces/` is not completely untracked before R3 lands, the test still fails. R1+R2 must be committed first.
- The rglob fallback in `_scan_files()` serves the canary test (CRONOS_TRACES_DIR env). The R3 fix must not touch the `os.environ.get("CRONOS_TRACES_DIR")` branch (lines 26–27) — only the `if result.returncode == 0 and result.stdout.strip()` path.
