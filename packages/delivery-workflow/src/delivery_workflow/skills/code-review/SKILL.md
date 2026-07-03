---
name: code-review
description: Method for reviewing an implementation diff against a design scope contract — memory preflight, scope-escape detection, the severity ladder, architectural-vs-local classification, the finding format, verdict coherence, and carry-forward discipline. Loaded by the reviewer agent.
---

# code-review

How to review a diff against a design. The `reviewer` agent owns the role and the hard rules;
this skill owns the method.

## 1. Memory-first preflight
Before searching code, scan the injected memory context. Treat relevant entries (naming
conventions, prior incident fixes, architectural standards, security/contract rules) as
**binding constraints**: a diff that violates one is a finding (≥ `medium`; `blocking` if the
divergence is unsafe or contract-breaking).

## 2. Establish the scope contract
From the design's `iterations[]`, compute the **allowed scope** = the union of every
iteration's `scope_files[]`. From the implementation report(s), compute the **observed changed
set** = the union of `files_changed[]`.

**Scope-escape check (always blocking):** any changed file outside the allowed scope is a
scope escape — `severity: high` (`critical` if security-sensitive: auth, crypto, migrations,
RBAC), `blocking: true`. Re-verify across the *union*; a per-iteration check misses
cross-iteration drift. Class it `local` unless the escape reveals the design omitted a needed
file (then `architectural`).

## 3. Inspect the diff
For each changed file: read it, then `git diff --unified=5 main...HEAD -- <file>` to scope to
what actually changed. Navigate callers/tests with Grep/Glob only as needed to judge a change
in context — broad reconnaissance is recon's job, not yours.

## 4. Judge test adequacy (you have no test results)
Tests run *after* review, so results don't exist yet, and you don't read the full suite. From
the **diff**, judge coverage adequacy: does each new branch or behaviour ship with a
corresponding test change? Missing tests for new branching logic → `high`; missing low-impact
tests → `medium`. Never run a suite.

## 5. Identify findings
Each finding: `id` (F<N>, unique, stable across re-reviews), `severity`, `class`
(architectural|local), `blocking` (real bool), `file` (`path:line`, forward slashes),
`evidence` (≤ 500 chars — a concrete snippet/hunk, never "looks suspicious"),
`suggested_action` (what to do, concretely — never "consider X").

### Severity ladder
- **critical** — data loss, security regression (auth bypass, RCE, IDOR), corrupting
  migration, secret leak, scope escape into security paths. Default blocking.
- **high** — functional regression on the golden path, missing tests for new branching, scope
  escape, contract drift breaking downstream. Default blocking.
- **medium** — maintainability, edge-path wrong-behaviour, naming/contract drift, missing
  low-impact tests. Non-blocking by default; blocking if it compounds a known issue.
- **low** — cosmetic, opinion-level. Never blocking.

### Always-blocking (overrides defaults)
- Scope escape.
- An implementation left as "done" with its own `validation_command_passed: false`.
- A prior blocking finding carried forward unresolved.

## 6. Classify each finding — architectural vs local (this drives routing)
- **local** — the implementor fixes it in place without touching the design: a bug in the
  changed code, a missing test, a naming nit, an over-reaching scope escape. This is the
  default for most findings.
- **architectural** — fixing it requires changing the *design*: the approach is wrong, a
  DD interface/contract is inadequate, the iteration plan can't satisfy a requirement, a
  `risks[]` entry materialised, or the same issue keeps recurring because the design
  under-specifies it.
- **When in doubt, choose `local`.** Routing to the architect is the expensive path; reserve
  it for what a code fix genuinely cannot resolve.

## 7. Decide the verdict
`pass` iff no blocking finding; otherwise `needs_fix`. Set report-level `finding_class =
architectural` if any blocking finding is architectural, else `local`. Escalation on a
stalled or over-budget loop is the harness's decision, not a verdict you emit.

## 8. Re-review (carry-forward) discipline
On re-review, for each prior `blocking: true` finding, determine from the new diff whether it
was addressed:
- **Resolved** → note in the Summary ("F3 resolved by edit to x.py:42"); do not carry forward;
  retire the id.
- **Not addressed** → carry forward with the **same F-id**, severity held or escalated, append
  "(carried from prior review)" to `evidence`.
- **Partial** → carry forward, severity possibly downgraded, `evidence` describing what
  remains.

Fresh findings take the next unused F-id above the highest prior id. Stable ids are what let
the harness recognise a *recurring* finding.

## 9. Write the review artifact
Body sections, in order:
- **Summary** — ≤ 5 sentences: scope conformance (yes/no), the verdict and its single most
  load-bearing reason, test-adequacy note, what changed since the prior review (if any).
- **Findings** — one bullet per finding, mirroring the structured return. No novel facts here;
  everything decision-relevant lives in the return.
- **Verdict** — the word, then ≤ 2 sentences.
- **Handoff** — on `pass`: the user-visible behaviour change, for the doc writer. On
  `needs_fix`: which F-ids to address and where. Do not restate routing — the harness owns it.

## Guardrails
You never modify source, tests, configuration, or any upstream artifact — your output is the
review. You never run the test suite. You never decide what runs next.
