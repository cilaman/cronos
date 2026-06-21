---
cc_version: "1.0"
agent: pipeline-reviewer
slug: g12-lightweight-docs--attempt1
phase: review
status: done
confidence: 0.86
inputs_used:
  - .cronos/pipeline/g12-lightweight-docs/design-report-g12-lightweight-docs.md
  - .cronos/pipeline/g12-lightweight-docs/impl-report-g12-lightweight-docs.md
  - .cronos/pipeline/g12-lightweight-docs/test-report-g12-lightweight-docs.md
  - README.md
  - docs/adr/001-markdown-as-truth.md
  - docs/adr/002-sqlite-durability.md
outputs_produced:
  - .cronos/pipeline/g12-lightweight-docs/review-report-g12-lightweight-docs--attempt1.md
blockers: []
next_consumer: implementation
metrics:
  tool_calls: 12
  files_read: 6
  memory_hits: 0
  diff_lines_reviewed: 138
verdict: needs_fix
attempt: 1
findings:
  - id: F1
    severity: medium
    file: docs/adr/002-sqlite-durability.md:59
    evidence: "ADR states 'The lease TTL must comfortably exceed the maximum expected agent run duration; the current default is 90 minutes.' Actual default is LEASE_TTL=300 (5 min) in backend/app/worker.py:50. Long runs survive via heartbeats (HEARTBEAT_INTERVAL=15s, reaper HEARTBEAT_TIMEOUT=30s), not a long TTL — the stated number (18x off) and the causal model are both wrong."
    blocking: true
    suggested_action: "In docs/adr/002-sqlite-durability.md Consequences/Decision, change '90 minutes' to '300 seconds (5 minutes, CRONOS_LEASE_TTL)' and reframe: the worker renews heartbeat_at every 15s during a run; the reaper reclaims a lease whose heartbeat is stale by >30s. Liveness across long agent runs comes from heartbeat renewal, not from a TTL exceeding run duration."
  - id: F2
    severity: low
    file: docs/adr/002-sqlite-durability.md:37
    evidence: "ADR describes the table as storing '(task_id, worker_id, acquired_at, expires_at, heartbeat_at)'. Actual schema (backend/app/storage.py:550) is (task_id TEXT PRIMARY KEY, owner TEXT, lease_expiry REAL, heartbeat_at REAL) — no worker_id (it is `owner`), no acquired_at, and expires_at is `lease_expiry`."
    blocking: false
    suggested_action: "Align the column list in docs/adr/002-sqlite-durability.md to the real schema: (task_id, owner, lease_expiry, heartbeat_at), or qualify it as an illustrative shape rather than the exact DDL."
---

## Summary

Scope conformance: YES — the G12 impl (commit 402d449) touched exactly `README.md`, `docs/adr/001-markdown-as-truth.md`, `docs/adr/002-sqlite-durability.md`, all within the design `iterations[].scope_files[]` union; no backend/frontend/test files changed. The test gate passed (2858p / 0f / 0e, 85.77% coverage), and the README `## Security posture` section is accurate and within the personal-project scope (G03/G06 correctly hedged as "designed (planned)", G04/G11 present-tense as "active", explicit no-formal-disclosure note present). However, ADR 002 makes two factual claims that contradict the implemented G08 code: a lease-TTL default of "90 minutes" (actual `LEASE_TTL=300`s) with an inverted durability model, and an incorrect `task_leases` column list. Since the goal's purpose is accurate, discoverable documentation of deliberate choices, the wrong durability number (F1) is a blocking factual error; verdict is needs_fix for a one-ADR correction.

## Findings

- **F1** (medium, blocking): `docs/adr/002-sqlite-durability.md:59` — lease TTL stated as "90 minutes"; actual default is 300 s, and long runs are bridged by heartbeats, not a long TTL. Inaccurate in the ADR whose subject is the durability substrate.
- **F2** (low, non-blocking): `docs/adr/002-sqlite-durability.md:37` — `task_leases` column list does not match the real schema (`owner`/`lease_expiry`, no `worker_id`/`acquired_at`/`expires_at`).

## Verdict

needs_fix. The README and ADR 001 are accurate and in scope, but ADR 002 documents the G08 durability substrate with a verifiably false default (90 min vs 300 s) and an inverted heartbeat/TTL model; a one-iteration correction to ADR 002 (F1, plus F2 while there) resolves it.

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union (README.md, docs/adr/001-markdown-as-truth.md, docs/adr/002-sqlite-durability.md).
- G12 diff isolated to commit 402d449; the cumulative `main...HEAD` README diff also contains G04/G10/G11 sections from prior merged goals, which are out of G12 scope and not reviewed here.
- Test report present with `gate_decision: pass`; full suite green at 2858 tests, so no test-gate-driven blocking finding.
- README security-posture acceptance criteria (G03/G04/G06/G11 named, hedging discipline, personal-project + no-formal-disclosure note) verified directly against the rendered section.

## Open questions

- None.

## Next consumer brief

Re-run the implementor on iteration **I3** (`docs/adr/002-sqlite-durability.md`) only. Address **F1** (blocking): replace the "90 minutes" lease-TTL claim with the real default `300 s` (`CRONOS_LEASE_TTL`, `backend/app/worker.py:50`) and reframe the durability model around heartbeat renewal (15 s interval, 30 s reaper timeout) rather than a TTL exceeding run duration. While editing, also fix **F2** (non-blocking): correct the `task_leases` column list to `(task_id, owner, lease_expiry, heartbeat_at)`. No other files need to change; README.md and ADR 001 are accepted as-is. Keep the change inside the I3 scope boundary (`docs/adr/002-sqlite-durability.md`) and preserve the Nygard headings required by the I3 validation grep.
