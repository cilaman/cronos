---
class: review
goal_slug: delivery-v2-retro-t1
phase: review
attempt: 2
verdict: pass
finding_class: local
status: done
---

# Review Report — delivery/v2 F2: Tier-1 PR path (attempt 2)

## Summary

Re-review of the attempt-2 fix (`5e78899`, `eec80de`). All three attempt-1 findings are
**resolved** and no new issues were introduced; scope remains conformant (fix touched only
`lib/git_pr.py`, `lib/improve.py`, `skills/improve/SKILL.md`, `tests/test_improve.py`, plus the
impl-report — all inside the design's scope union). **Verdict is `pass`.** The blocking F1
branch-stacking defect is fixed at the root and the previously-untested real-`gh` path now has
direct coverage, including the exact same-base regression test. The Tier-1/Tier-2 routing,
eval-gating, escalate-only semantics, schema additions, and the REQ-005 byte-identical safety
test all remain intact.

## Carry-forward (attempt-1 findings)

- **F1** (was high/blocking) — **resolved.** `lib/git_pr.py:emit_pr` now captures a stable base
  ref (`git rev-parse --abbrev-ref HEAD`) **before** any branch is created, creates each branch
  explicitly from that base (`git checkout -b <branch> <base_ref>`), and restores HEAD in a
  `finally:` block on every path (success or gh failure). An injectable `runner` param was added
  so the gh path is now testable. Coverage added in `tests/test_improve.py::TestGhPath`:
  `test_emit_pr_gh_path_uses_stable_base_ref`, `test_..._restores_head_after_success`,
  `test_..._restores_head_on_failure`, `test_two_findings_branch_from_same_stable_base` (the
  direct branch-stacking regression), and `test_run_back_half_two_findings_all_get_prs`. Id
  retired.

- **F2** (was low) — **resolved.** `skills/improve/SKILL.md` Step-2 comments now route both
  `routed.tier1` and `routed.tier2` to "Step 6 (Tier-1/Tier-2 back-half)"; the stale "Step 7"/
  "Step 8" references are gone. Id retired.

- **F3** (was low) — **resolved.** `lib/improve.py` CLI now accepts `--repo-root` and otherwise
  derives the repo root via `_find_repo_root()` (walks up to the nearest `.git`), replacing the
  fragile `Path(retro_artifact).parent` derivation. Id retired.

## Findings

None. (All attempt-1 findings resolved; no new findings.)

## Verdict

**pass.** No blocking findings remain; F1/F2/F3 are all verified fixed and the real-`gh` path is
now covered by tests. `finding_class = local` (no architectural concerns surfaced).

## Handoff

For the doc writer: F2 (Tier-1 PR path) now produces one independent PR per Tier-1 finding,
each branched from a stable base ref with HEAD restored after every emission — Tier-1
(`agent_prompt`/`skill`/`gate_check`) findings are emitted as proposal-doc PRs (never in-place
writes), gated on green evals; Tier-2 (`schema`/`workflow`) findings are escalate-only; Tier-0
applies in place. The `improve` skill driver classifies all findings up front and merges Tier-0
counts with the back-half's `tier1_pr_urls`/`tier1_findings`/`tier2_escalated` fence fields.

## delivery_status

```delivery_status
{
  "status": "done",
  "produces": "review",
  "artifact_paths": [".cronos/delivery/delivery-v2-retro-t1/review-report.md"],
  "fields": {
    "verdict": "pass",
    "finding_class": "local",
    "findings_count": 0,
    "findings": []
  },
  "open_questions": []
}
```
