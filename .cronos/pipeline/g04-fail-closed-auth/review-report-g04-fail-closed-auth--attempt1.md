---
cc_version: "1.0"
agent: pipeline-reviewer
slug: g04-fail-closed-auth--attempt1
phase: review
status: done
confidence: 0.85
inputs_used:
  - memory:fail-closed-auth-conftest-pattern
  - memory:g04-fail-closed-auth-impl
  - .cronos/pipeline/g04-fail-closed-auth/design-report-g04-fail-closed-auth.md
  - .cronos/pipeline/g04-fail-closed-auth/impl-report-g04-fail-closed-auth.md
  - .cronos/pipeline/g04-fail-closed-auth/impl-report-g04-fail-closed-auth--i3.md
  - .cronos/pipeline/g04-fail-closed-auth/test-report-g04-fail-closed-auth.md
  - backend/app/auth.py
  - backend/app/main.py
  - backend/tests/conftest.py
  - backend/tests/test_auth.py
  - backend/tests/test_upgrade_webhook.py
  - backend/tests/test_harness_wiring.py
  - backend/tests/api/test_features_board.py
  - deploy/upgrade-webhook.py
  - README.md
  - Caddyfile.dev
outputs_produced:
  - .cronos/pipeline/g04-fail-closed-auth/review-report-g04-fail-closed-auth--attempt1.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 14
  files_read: 15
  memory_hits: 2
  diff_lines_reviewed: 372
verdict: pass
attempt: 1
findings:
  - id: F1
    severity: medium
    file: backend/tests/conftest.py
    evidence: "observed_changed_set has 18 files; design scope_files union has 7. 11 test files (backend/tests/api/test_features_*.py x9, test_api_harnesses.py, test_harness_wiring.py) outside scope_files each got an identical `monkeypatch.delenv(\"CRONOS_AUTH_DISABLED\", raising=False)` to survive the new conftest autouse default."
    blocking: false
    suggested_action: "Bookkeeping only — no code change needed for pass. For fidelity, architect should amend design I1 scope_files to include the 11 auth-enabling test files (the blast radius of the conftest autouse the design itself mandated), so future scope-escape gates stay meaningful."
---

## Summary

Scope conformance: the 7 declared scope files are all correct; 11 additional test files were modified (disclosed, test-only, mechanically uniform `delenv` one-liners — F1). Verdict is **pass**: all four G04 acceptance criteria are met (unset → 503, explicit `CRONOS_AUTH_DISABLED=true` opt-out with integration tests, File-Browser + Plugin routes protected via `_auth` and covered by a new parametrized test, webhook 403 when `WEBHOOK_SECRET` unset), the dual-auth architecture is documented in README + Caddyfile.dev, and the full suite is green (test gate: 2707 passed / 0 failed / 85.18% coverage). The `require_auth` precedence (opt-out → 503 → 401) matches the design's R1/R2 invariant and `authorized()` is the sole webhook gate with no SECRET bypass path. The single finding (F1, scope escape into test files) is judged non-blocking because the changes are fully disclosed in the impl report, identical, necessary blast-radius of the in-scope conftest change, and carry zero production/security risk. No attempt N-1 to reconcile (fresh chain). Doc may proceed.

## Findings

- **F1** (medium, non-blocking) — Scope escape: 11 test files outside the design `scope_files` union were modified (`backend/tests/api/test_features_*.py` ×9, `test_api_harnesses.py`, `test_harness_wiring.py`). Each adds `monkeypatch.delenv("CRONOS_AUTH_DISABLED", raising=False)` before its credential setenv so the new suite-wide conftest autouse default does not bypass auth in those tests; `test_harness_wiring.py` also rewrites one test that encoded the now-removed "no-env-vars = disabled" contract. Reviewer discretion applied: disclosed (impl `out_of_scope_findings` + Files-changed section), test-only, uniform, and the unavoidable consequence of the design-mandated conftest fixture — recorded as a non-blocking design-scoping gap rather than a gate.

## Verdict

pass — All acceptance criteria satisfied, full suite green, only finding is a disclosed test-only scope-bookkeeping gap (non-blocking).

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union (7 files): auth.py, conftest.py, test_auth.py, upgrade-webhook.py, test_upgrade_webhook.py, README.md, Caddyfile.dev.
- The diff under review is impl commit `f838e71` on `feature/cronos-remediation-plan` (gate `ba7fff5` PROCEED); the review worktree is on a separate task branch, so artifacts and diff were read via `git show feature/cronos-remediation-plan:` and the space working tree.
- Test report (`gate_decision: pass`, 2707/0, 85.18%) was read from the space working tree; it is not yet committed to the feature branch but is present and valid.
- App-layer plaintext credential compare (vs Caddy bcrypt) is acceptable for this single-user personal deployment and is documented as such; G04 does not require bcrypt at the app layer.

## Open questions

- None.

## Next consumer brief

User-visible behavior changed (for the changelog):
- App auth is now **fail-closed**: with `CRONOS_BASIC_AUTH_USER`/`CRONOS_BASIC_AUTH_PASSWORD` unset (or partial/empty), protected endpoints return **HTTP 503** instead of silently allowing access. The only supported bypass is the explicit `CRONOS_AUTH_DISABLED=true` (exact string) for local dev.
- File Browser (`/api/spaces/{id}/files`) and Plugin (`/api/plugins`) routes are confirmed under the shared `require_auth` dependency.
- The upgrade webhook now **rejects all requests with 403 when `WEBHOOK_SECRET` is unset** (mandatory, constant-time compare retained).
- README gained an Authentication section documenting both auth layers (Caddy bcrypt vs. app plaintext); Caddyfile.dev documents the fail-closed contract.

Threat note (per remediation-plan §G04 requirement):
- **Closes:** unauthenticated read of arbitrary workspace files / plugin state on a default or misconfigured deployment where only the Caddy edge was set up (or nothing was) — the app no longer fail-opens; and silent unauthenticated triggering of the host-side upgrade webhook when its secret is unset.
- **Does NOT close:** edge-layer compromise (Caddy `BASIC_AUTH_*` is a separate mechanism, unchanged here); app-layer credentials are still a plaintext (non-bcrypt) compare suitable only for single-user use; no rate-limiting/lockout on Basic-Auth brute force; no protection if `CRONOS_AUTH_DISABLED=true` is set in production by mistake; and it does not bind the backend to loopback-only (the plan's optional "refuse non-loopback without auth" hardening was satisfied by documentation, not enforced in code).
