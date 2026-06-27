---
class: review
goal_slug: delivery-v2-retro-t1
phase: review
attempt: 1
verdict: needs_fix
finding_class: local
status: done
---

# Review Report — delivery/v2 F2: Tier-1 PR path (attempt 1)

## Summary

Scope is **conformant**: all 7 changed files (`lib/git_pr.py`, `lib/improve.py`,
`schemas/improvement.schema.yaml`, `skills/improve/SKILL.md`, `tests/test_improve.py`,
`tests/test_tier1_no_auto_apply.py`, plus the impl-report) fall inside the design's 5-iter
`scope_files[]` union — no scope escape. The safety contract is excellent: the
fix_type-authoritative classifier (`improve.py`) structurally bars Tier-1 fix_types from the
Tier-0 apply path, and `test_tier1_no_auto_apply.py` asserts byte-identical `agents/`+`skills/`
trees after a back-half run (AC2 satisfied). **Verdict is `needs_fix`** for one blocking
finding: `emit_pr`'s real-`gh` branch — the code that actually produces the headline Tier-1
PR — creates each finding's branch off the *previous* finding's branch tip (not a stable base),
and the entire real-`gh` path ships with **no test** (only the `gh_probe=False` fallback is
covered). The routing/gating/escalation logic is otherwise correct and thoroughly tested
(32 behavioural tests across REQ-001–006).

## Findings

- **F1** — `severity: high`, `class: local`, `blocking: true`,
  `file: packages/delivery-workflow/lib/git_pr.py:91`
  **Evidence:** In the `if has_gh:` path, each PR branch is created with
  `_run(["git", "checkout", "-b", branch], cwd=repo_root)` with no base ref. `run_back_half`
  calls `emit_pr` once per Tier-1 finding sequentially; after finding 1, HEAD is left on
  `delivery-improve-tier1-<id1>`, so finding 2's `git checkout -b <id2>` forks from finding 1's
  branch — its PR diff then contains finding 1's proposal too, breaking "one independent PR per
  finding" (DD-005, AC1/AC4). HEAD is also never restored to the original branch, leaving the
  repo on the last proposal branch. This `if has_gh:` orchestration (checkout/add/commit/push/
  `gh pr create`) has **zero test coverage** — only the `gh_probe=False` fallback is exercised
  (`test_proposed_pr_md_fallback_written`), so the bug slipped through. The path is testable via
  the injected `gh_probe=True` + a monkeypatched `_run`.
  **suggested_action:** Capture a stable base ref once (e.g. `git rev-parse HEAD` or the current
  branch name) and create every proposal branch from it — `git checkout -b <branch> <base>` —
  then `git checkout <base>` (or `git switch -`) after each emission to restore HEAD. Add a test
  with `gh_probe=lambda *_: True` and a fake `_run`/subprocess that records the git/gh argv,
  asserting (a) each branch is created from the same base and (b) HEAD is restored, for a
  2+ finding run.

- **F2** — `severity: low`, `class: local`, `blocking: false`,
  `file: packages/delivery-workflow/skills/improve/SKILL.md:50`
  **Evidence:** Step 2's inline comments route findings to stale step numbers:
  `# routed.tier1 — these go to Step 7 (Tier-1 PR back-half)` and
  `# routed.tier2 — these go to Step 8 (Tier-2 escalation)`. After renumbering, the back-half is
  **Step 6** (which handles *both* tier1 and tier2 via `run_back_half`); there is no Step 8, and
  the report write is Step 7.
  **suggested_action:** Update the two comments to "these go to Step 6 (Tier-1/Tier-2 back-half)".

- **F3** — `severity: low`, `class: local`, `blocking: false`,
  `file: packages/delivery-workflow/lib/improve.py:218`
  **Evidence:** The CLI derives `repo_root = Path(args.retro_artifact).resolve().parent`. The
  retro artifact lives at `.cronos/delivery/<slug>/`, so `repo_root` is that deep subdir, not the
  repository root. It happens to work because `git`/`gh` resolve `.git` upward from any cwd, but
  the variable is mislabeled and brittle (e.g. a future use of `repo_root` as a path join base
  would break).
  **suggested_action:** Either accept an explicit `--repo-root` arg or walk up to the nearest
  `.git` directory; at minimum rename to reflect it is a cwd inside the repo, not the root.

## Verdict

**needs_fix.** One blocking finding (F1): the real-`gh` PR path — the feature's headline
behaviour — has a branch-base bug and no test. F2/F3 are non-blocking nits to fold in while
fixing F1. `finding_class = local`: F1 is an in-place code+test fix requiring no design change.

## Handoff

Address **F1** in `lib/git_pr.py` (stable base ref per branch + HEAD restore) and add a
real-`gh`-path test driving `emit_pr`/`run_back_half` with `gh_probe=True` and a fake runner.
Optionally fold in **F2** (SKILL.md step-number comments) and **F3** (CLI `repo_root` label).
The classifier, eval-gating, Tier-2 escalation, schema additions, and the REQ-005 safety test
are all sound and need no change — keep them as-is on re-implementation.

## delivery_status

```delivery_status
{
  "status": "done",
  "produces": "review",
  "artifact_paths": [".cronos/delivery/delivery-v2-retro-t1/review-report.md"],
  "fields": {
    "verdict": "needs_fix",
    "finding_class": "local",
    "findings_count": 3,
    "findings": [
      { "id": "F1", "severity": "high", "class": "local", "blocking": true,
        "file": "packages/delivery-workflow/lib/git_pr.py:91",
        "evidence": "Real-gh path creates each PR branch with `git checkout -b <branch>` (no base ref); sequential per-finding calls fork from the previous finding's branch, so PRs stack proposals and HEAD is never restored. The entire if-has_gh orchestration is untested (only the gh_probe=False fallback is covered).",
        "suggested_action": "Create every proposal branch from a stable base ref (git checkout -b <branch> <base>) and restore HEAD after each emission; add a gh_probe=True test with a fake _run asserting same-base branching and HEAD restore for a 2+ finding run." },
      { "id": "F2", "severity": "low", "class": "local", "blocking": false,
        "file": "packages/delivery-workflow/skills/improve/SKILL.md:50",
        "evidence": "Step 2 comments route tier1/tier2 to 'Step 7'/'Step 8'; the back-half is Step 6 (handles both tiers) and there is no Step 8.",
        "suggested_action": "Point both comments at Step 6 (Tier-1/Tier-2 back-half)." },
      { "id": "F3", "severity": "low", "class": "local", "blocking": false,
        "file": "packages/delivery-workflow/lib/improve.py:218",
        "evidence": "CLI sets repo_root = Path(args.retro_artifact).resolve().parent, i.e. the .cronos/delivery/<slug>/ subdir, not the repo root; works only because git resolves .git upward.",
        "suggested_action": "Accept an explicit --repo-root or walk up to the nearest .git; at minimum rename the variable to reflect it is a cwd inside the repo." }
    ]
  },
  "open_questions": []
}
```
