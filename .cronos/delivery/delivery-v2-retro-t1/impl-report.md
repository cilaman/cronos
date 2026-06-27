---
class: implementation
goal_slug: delivery-v2-retro-t1
phase: implement
status: done
iterations_completed: [I1, I2, I3, I4, I5]
validation_command_passed: true
---

# Implementation Report — delivery/v2 F2: Tier-1 PR path

## Summary

All 5 iterations executed in topological order (I1 → I3 → I2 → I5 → I4). 324 tests pass
(no regressions). Import boundary clean. All validation commands pass.

**Review-fix (attempt 2):** Addressed all 3 reviewer findings — F1 (blocking): stable base ref
capture + `git checkout -b <branch> <base>` + `finally` HEAD restore in `emit_pr`; injectable
`runner` parameter added; 5 new gh-path tests cover stable-base branching, HEAD restore on
success/failure, 2-finding sequential run, and end-to-end `run_back_half` with real `emit_pr`
+ fake runner. F2: corrected stale step-number comments in SKILL.md Step 2. F3: CLI now
derives repo_root via `.git` walk-up (`_find_repo_root`) or explicit `--repo-root` arg.

---

## Iterations

### I1 — Portable git/gh PR helper
- **File created:** `packages/delivery-workflow/lib/git_pr.py`
- **Scope:** `emit_pr(title, body, finding_id, *, branch, repo_root, proposals_dir, gh_probe=None) -> str`
  — `_slug_branch()`, `_run()`, `_gh_available()` helper. Subprocess-only, zero app/backend imports.
- **Validation:** fallback path smoke-test + `test_import_boundary.py` — 2 passed
- **Commit:** `impl-sgc-I1` (5c6ad12)

### I2 — Classifier + Tier-1/Tier-2 back-half applier
- **File created:** `packages/delivery-workflow/lib/improve.py`
- **Scope:** `Routed`, `BackHalfResult`, `classify_findings()` (fix_type-authoritative), `render_proposal()`,
  `run_back_half()`, `__main__` CLI.
- **Key behaviour:** Tier-1 PR gate on `evals_passed`; Tier-2 escalation is ungated; `pr_emitter` injectable.
- **Validation:** inline smoke-test (classifier + back-half on red-evals) — passed
- **Commit:** `impl-sgc-I2` (2328ccf)

### I3 — Extend improvement artifact schema
- **File modified:** `packages/delivery-workflow/schemas/improvement.schema.yaml` (additive)
- **Added fields:** `tier1_pr_urls`, `tier1_findings`, `tier2_escalated` (each array of string)
- **Preserved:** `tier0_applied`, `tier0_rolled_back`, `errors`
- **Validation:** schema integrity check + `test_schemas.py` — 135 passed
- **Commit:** `impl-sgc-I3` (b491129)

### I4 — Wire back-half into improve/SKILL.md driver
- **File modified:** `packages/delivery-workflow/skills/improve/SKILL.md` (additive)
- **Added:** Step 2 classifier rewiring (consumes `routed.tier0` only); Step 6 back-half invocation
  (eval corpus → `python -m lib.improve` / Python call); Step 7 extended fence + `## Tier-1 PRs`
  and `## Tier-2 Escalated` report sections.
- **Preserved:** all SGB Tier-0 prose (snapshot/rollback/eval/fixture/threshold steps intact)
- **Validation:** content-check assertions — passed
- **Commit:** `impl-sgc-I4` (a13d648)

### I5 — Tier-1 safety + behavioural tests
- **Files created:**
  - `packages/delivery-workflow/tests/test_tier1_no_auto_apply.py` (REQ-005 hard safety)
  - `packages/delivery-workflow/tests/test_improve.py` (REQ-001/002/003/004/006)
- **Coverage:** 32 tests — all classifier routing, no-PR-on-red, one-PR-per-finding with stub emitter,
  PROPOSED_PR.md fallback, byte-identical source files after run, Tier-2 no-file-write, fence fields.
- **Validation:** `pytest tests/test_tier1_no_auto_apply.py tests/test_improve.py -q` — 32 passed
- **Commit:** `impl-sgc-I5` (8771c1f)

---

## REQ traceability

| REQ | Status | Verified by |
|-----|--------|------------|
| REQ-001 | done | `test_improve.py::TestClassifyFindings` |
| REQ-002 | done | `test_improve.py::TestNoPROnRedEvals` |
| REQ-003 | done | `test_improve.py::TestOnePRPerFinding` |
| REQ-004 | done | `test_improve.py::TestTier2EscalateOnly` |
| REQ-005 | done | `test_tier1_no_auto_apply.py::TestSourceFilesUnchangedAfterRunBackHalf` |
| REQ-006 | done | `test_improve.py::TestBackHalfResultFields` |
| REQ-007 | done | `skills/improve/SKILL.md` `## Tier-1 PRs` + `## Tier-2 Escalated` sections |

---

## Risk register outcome

| Risk | Outcome |
|------|---------|
| R1 (Tier-1 leak) | Mitigated: fix_type-authoritative classifier + REQ-005 test asserts byte-identical files |
| R2 (stale-base clobber) | Mitigated: all edits additive; I4 validation confirms Tier-0 prose survives |
| R3 (real git/gh in tests) | Mitigated: pr_emitter, gh_probe, eval_runner all injectable |
| R4 (portability leak) | Mitigated: proposals_dir is caller-supplied; no `.cronos/` literal in lib/ |
| R5 (proposal doc not patch) | Documented in PR body; design as-intended |
| R6 (redundant eval runs) | Mitigated: skill shares single eval verdict with both Tier-0 and back-half |

---

## Full suite result

```
324 passed in 3.24s  (attempt 2 — includes 5 new gh-path tests)
```

---

## delivery_status

```delivery_status
{
  "status": "done",
  "produces": "implementation",
  "artifact_paths": [".cronos/delivery/delivery-v2-retro-t1/impl-report.md"],
  "fields": {
    "iterations_completed": ["I1", "I2", "I3", "I4", "I5"],
    "validation_command_passed": true,
    "files_changed": [
      "packages/delivery-workflow/lib/git_pr.py",
      "packages/delivery-workflow/lib/improve.py",
      "packages/delivery-workflow/schemas/improvement.schema.yaml",
      "packages/delivery-workflow/skills/improve/SKILL.md",
      "packages/delivery-workflow/tests/test_tier1_no_auto_apply.py",
      "packages/delivery-workflow/tests/test_improve.py"
    ],
    "diff_lines_added": 763,
    "diff_lines_removed": 29
  },
  "open_questions": []
}
```
