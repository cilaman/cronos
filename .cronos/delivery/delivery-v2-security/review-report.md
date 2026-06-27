---
class: review
agent: reviewer
goal_slug: delivery-v2-security
feature: "F1 — security-review node (delivery/v2 §2)"
phase: review
attempt: 1
status: done
verdict: needs_fix
finding_class: local
reviewed_commit: 387ac70
design_ref: .cronos/delivery/delivery-v2-security/design-report.md
impl_ref: .cronos/delivery/delivery-v2-security/impl-report.md
findings:
  - id: F1
    severity: high
    class: local
    blocking: true
    file: backend/app/pipeline/gate.py:649
    evidence: >-
      _run_command returns only stdout_tail = proc.stdout[-2000:]. _check_security does
      json.loads(result.stdout_tail.strip()). A real scanner (semgrep --config auto --json,
      npm audit --json, pip-audit -f json, gitleaks → /dev/stdout) emits multi-KB JSON and
      exits 1 when it finds vulnerabilities. The tail is a non-JSON fragment → json.loads
      raises → parsed=None. The crash/retry guard is `parsed is None and exit_code not in
      (0,1)`, so exit 1 is NOT caught; items=[], severity_hits=[], and the scanner is recorded
      `status: "clean"`. Real CVEs/secrets → has_fail_on_hit=False → gate returns "proceed".
      Fail-open on the gate's whole purpose (DD-001). No test covers >2000-char/unparseable
      output; the hermetic fixtures emit tiny valid JSON so the path is never exercised.
    suggested_action: >-
      Make the parse fail-closed: when stdout is non-empty AND json.loads fails AND exit_code
      != 0 (including 1), do NOT classify "clean" — return "retry" (or contribute needs_fix),
      recording the unparseable output as evidence. Preserve the existing "empty stdout +
      exit 0 = clean" path. Add a regression test feeding a scanner whose JSON output exceeds
      2000 chars with exit 1 and assert decision != "proceed". The complete fix also needs a
      full-stdout channel from _run_command (e.g. an untruncated stdout field) so true
      severities survive — note it for the Phase-6 _run_command extraction (R6).
  - id: F2
    severity: medium
    class: local
    blocking: false
    file: backend/app/pipeline/gate.py:732
    evidence: >-
      When an agent artifact IS resolved and _read_header succeeds but the frontmatter lacks a
      `verdict` field, agent_verdict=None. not_proceed only tests `== "needs_fix"` / scanner
      hits / missing-fail, so a None verdict with clean scanners falls through to "proceed".
      _check_g_review (the exemplar) fails-closed here: missing/invalid verdict → "fail".
      For a fail-closed security gate (DD-007) the inconsistency is a fail-open under a
      malformed agent artifact. The docstring even states "proceed — agent verdict==pass", but
      the code never requires == "pass".
    suggested_action: >-
      Distinguish the two modes. If NO artifact_path resolved → standalone-scanner mode, keep
      allowing proceed (tested, intended). If an artifact WAS resolved and parsed but verdict
      is missing/not in {pass,needs_fix,fail} → fail-closed (needs_fix or fail), mirroring
      _check_g_review. Add a test for "artifact present, no verdict field, clean scanners →
      not proceed".
inputs_used:
  - .cronos/delivery/delivery-v2-security/design-report.md
  - .cronos/delivery/delivery-v2-security/impl-report.md (read from feature/delivery-v2)
  - packages/delivery-workflow/agents/reviewer.md (shape exemplar)
  - packages/delivery-workflow/skills/code-review/SKILL.md (method)
  - git diff 8a5081a..feature/delivery-v2 (the I1–I4 implementation diff)
---

# Security Review — F1 security-review node (delivery/v2), attempt 1

## Summary

Scope conformance: **yes** — all 12 changed source files (plus the impl-report artifact) fall
inside the union of the design's `iterations[].scope_files`; no scope escape, `test_schemas.py`
untouched (REQ-003 AC3), and the only `backend/` change is `gate.py`, so the import boundary
(REQ-007) stays green. Every acceptance criterion is met structurally: the `security-reviewer`
agent and `security-review` skill mirror the reviewer shape with no hardcoded paths and the 10
method sections; `security` is added to the gate-check enum with its four sub-fields; the
`security`/`g-security` nodes, the loop (`max: 3`, `on_exhaust: escalate`), and the four routing
edges are wired with `g-review → security` replacing the direct `g-review → testrun`. The work is
high quality and well-tested for what it tests. **Verdict is `needs_fix` on a single load-bearing
defect (F1): the gate JSON-parses `_run_command`'s 2000-char `stdout_tail`, so any real scanner
emitting larger output and exiting 1 is silently recorded `clean` — a fail-open on the security
gate's entire reason for existing — and no test exercises that path.** Test adequacy is otherwise
good (9 hermetic real-subprocess gate tests, 3 schema tests, 16 wiring tests), but the
large-output and missing-verdict edge paths (F1, F2) ship without coverage. R7 (gate-derived
`finding_class` not persisted into the node's `fields` for the routing edges) is an explicitly
accepted, disclosed Phase-6 deferral, not a finding.

## Findings

- **F1 — `high`, `local`, blocking — `backend/app/pipeline/gate.py:649`.** Scanner output is
  JSON-parsed from the tail-truncated `stdout_tail` (last 2000 chars). Real `--json` scanners
  emit multi-KB output and exit 1 on findings; the truncated fragment fails `json.loads`, the
  `exit_code not in (0,1)` retry guard skips exit 1, and the scanner is recorded `status: "clean"`
  → gate `proceed` despite real vulnerabilities. Fail-open, untested. Fix: fail-closed on
  non-empty-unparseable-non-zero output + regression test; longer-term give `_run_command` an
  untruncated stdout channel.

- **F2 — `medium`, `local`, non-blocking — `backend/app/pipeline/gate.py:732`.** An agent artifact
  that resolves and parses but carries no `verdict` field yields `agent_verdict=None` and falls
  through to `proceed` on clean scanners, where the exemplar `_check_g_review` fails-closed. Guard
  the resolved-artifact-with-missing-verdict case while preserving the intended standalone (no
  artifact) scanner mode.

## Verdict

**needs_fix.** A single blocking finding (F1) — the security gate fails open on real scanner
output because it parses a 2000-char-truncated buffer. Everything else is in scope, structurally
complete, and adequately tested; F2 is a non-blocking robustness nit to fix in the same pass.

## Handoff

`finding_class = local` → route to **implement**. Address **F1** at `gate.py:649` (fail-closed on
non-empty/unparseable/non-zero scanner output, add a >2000-char-output regression test) and,
ideally in the same pass, **F2** at `gate.py:732` (fail-closed on a resolved artifact missing its
`verdict`, keeping the standalone-no-artifact path). No design change is required — both fixes are
local to `_check_security`. The R7 `finding_class` propagation remains an accepted Phase-6
follow-up and is out of scope for this fix.

```delivery_status
{
  "status": "done",
  "produces": "review",
  "artifact_paths": [".cronos/delivery/delivery-v2-security/review-report.md"],
  "fields": {
    "verdict": "needs_fix",
    "finding_class": "local",
    "findings": [
      { "id": "F1", "severity": "high", "class": "local", "blocking": true,
        "file": "backend/app/pipeline/gate.py:649",
        "evidence": "json.loads on _run_command's 2000-char stdout_tail; real scanner JSON exceeds it and exits 1, so the unparseable tail is recorded status='clean' (exit 1 skips the retry guard) → gate proceeds despite real findings. Fail-open; untested.",
        "suggested_action": "Fail-closed when stdout is non-empty AND json.loads fails AND exit_code != 0 (retry or needs_fix), preserving empty-stdout+exit0=clean; add a >2000-char-output regression test; give _run_command an untruncated stdout channel for full-fidelity parsing." },
      { "id": "F2", "severity": "medium", "class": "local", "blocking": false,
        "file": "backend/app/pipeline/gate.py:732",
        "evidence": "Resolved+parsed agent artifact with no 'verdict' field → agent_verdict=None falls through to proceed on clean scanners; _check_g_review fails-closed on this. Docstring claims 'proceed — agent verdict==pass' but code never requires ==pass.",
        "suggested_action": "If an artifact resolved but verdict is missing/invalid → fail-closed (needs_fix/fail) mirroring _check_g_review; keep allowing proceed only in standalone (no artifact resolved) scanner mode; add a test." }
    ]
  },
  "open_questions": []
}
```
