---
name: security-review
description: Method for reviewing an implementation diff for security vulnerabilities against a design trust model — memory preflight, the scan sweeps (secrets, injection, traversal, access control, XSS, insecure storage, config), the OWASP/CWE mapping, the severity ladder, code-vs-dependency-vs-design routing, the finding format, false-positive triage, and carry-forward discipline. Loaded by the security-reviewer agent.
---

# security-review

How to security-review a diff against a design's trust model. The `security-reviewer` agent owns
the role and the hard rules; this skill owns the method. You are the LLM half — the `g-security`
gate re-executes scanners after you, so your job is precise, evidence-backed *observation and
triage*, not a guarantee.

## 1. Memory-first preflight
Before scanning, read the injected memory context. Treat prior security incidents, established
auth conventions, and crypto/secret-handling standards as **binding constraints**: a diff that
reintroduces a previously-fixed vulnerability or violates a standard is a finding (≥ `high`;
`critical`/`blocking` if it is an auth/crypto/injection regression).

## 2. Establish the trust model
From the design, identify: the auth/authz boundaries, what input is attacker-controlled vs.
trusted, the security-sensitive surface (authentication, authorization/RBAC, cryptography, secret
handling, DB migrations, deserialization, file/path handling, outbound requests). A change to any
of these is reviewed at a higher bar — a finding in a trust-boundary file defaults one severity
higher than the same pattern in inert code.

## 3. Scan the diff (read-only)
For each changed file: read it, then `git diff --unified=5 main...HEAD -- <file>` to scope to
what changed. Run the targeted sweeps below over the **changed set** (broad whole-repo audit is
not your job — you review the diff). Absence of a match is a *positive* observation worth noting.

```bash
# Hardcoded secrets (exclude obvious test/example/placeholder)
grep -rnE "(password|secret|api_key|token|private_key|access_key)\s*[:=]\s*['\"][^'\"$\{]{6,}" <files> \
  | grep -viE "test|example|sample|placeholder|dummy"

# Shell / command injection
grep -rnE "os\.system\(|subprocess\.(call|run|Popen)[^)]*shell\s*=\s*True" <files>

# eval / exec on dynamic input
grep -rnE "\beval\(|\bexec\(|pickle\.loads|yaml\.load\(" <files>

# SQL built by interpolation (potential SQLi)
grep -rnE "(execute|query)\s*\(\s*f[\"']|\.format\(|%\s*\(" <files> | grep -iE "select|insert|update|delete"

# Path traversal (request data into open/join)
grep -rnE "open\s*\(.*request\.|os\.path\.join\s*\(.*request\.|\.\./" <files>

# Access control: CORS, debug flags, route auth
grep -rnE "allow_origins\s*=\s*\[?\s*['\"]\*|CORSMiddleware|debug\s*=\s*True|DEBUG\s*=\s*True" <files>
grep -rnE "@router\.(get|post|put|delete|patch)" <files>     # check each new route for an auth Depends()

# Frontend: XSS + insecure storage + leaked secrets in logs
grep -rnE "dangerouslySetInnerHTML|innerHTML\s*=" <files>
grep -rnE "localStorage\.(set|get)Item.*([Tt]oken|[Pp]assword)|console\.(log|debug)\(.*([Tt]oken|[Pp]assword)" <files>
```

Navigate callers with Grep/Glob only as needed to judge exploitability in context. **Do not run
the dependency or SAST scanners yourself** — that is the gate's authority (`g-security`). You may
*observe* an obviously stale pinned version and flag it for the gate to confirm.

## 4. Map each finding to a standard
Tag every finding with the OWASP Top-10 (2021) category and a CWE id. This is not decoration — it
makes findings auditable and gives the implementor a precise fix target.

| Pattern observed | OWASP | CWE |
|---|---|---|
| Missing/!-checked authz on a route, IDOR | A01 Broken Access Control | CWE-862 / CWE-639 |
| Plaintext secret, weak/again crypto, secret in logs | A02 Cryptographic Failures | CWE-798 / CWE-327 |
| SQLi, command injection, XSS | A03 Injection | CWE-89 / CWE-78 / CWE-79 |
| Trust-boundary / auth-model flaw | A04 Insecure Design | CWE-657 |
| CORS `*`, debug on, container privileged | A05 Security Misconfiguration | CWE-16 |
| Known-vulnerable dependency | A06 Vulnerable & Outdated Components | CWE-1104 |
| Weak session/token handling, missing rate limit | A07 Auth Failures | CWE-287 |
| Unsafe deserialization (`pickle`, `yaml.load`) | A08 Integrity Failures | CWE-502 |
| Missing security logging on auth events | A09 Logging Failures | CWE-778 |
| Unvalidated outbound URL from user input | A10 SSRF | CWE-918 |

## 5. Severity ladder
- **critical** — remote code execution, auth bypass, SQLi/command injection on attacker input,
  secret leak of a live credential, unsafe deserialization of untrusted data. Default blocking.
- **high** — IDOR/missing authz on a sensitive route, stored XSS, hardcoded secret, CORS `*` on a
  credentialed API, a known critical/high CVE in a shipped dependency. Default blocking.
- **medium** — reflected XSS behind low likelihood, missing security header, debug flag in a
  non-prod path, a moderate-severity CVE. Non-blocking by default; blocking if it compounds a
  trust-boundary change.
- **low** — defense-in-depth gap, hardening opportunity. Never blocking.
- **info** — a pattern matched but context makes it safe (e.g. the "secret" is a test fixture).
  Record it with the reason it is safe; never blocking.

### Always-blocking (overrides defaults)
- Any finding in an auth/crypto/authz/migration file at `high` or above.
- A prior blocking finding carried forward unresolved.
- A secret that is a real credential (not a placeholder), regardless of file.

## 6. Classify each finding — this drives routing
- **code** — fixable in place by the implementor without a design change: parameterize the query,
  escape the output, add the `Depends(auth)`, remove the hardcoded secret, tighten the CORS list,
  drop the debug flag. **This is the default for most findings.**
- **dependency** — a vulnerable package. The fix is a version bump or replacement, still in the
  implementor's lane (routes to `implement`), but classed separately so the gate's dep-audit
  output is the corroborating authority.
- **design** — the *model* is wrong: authentication is absent where the design assumed it,
  a trust boundary is misplaced, an entire authz layer is missing, the data-flow lets attacker
  input reach a sink the design never accounted for. A code edit cannot resolve it — it routes to
  `architect`. **Reserve this for what a fix genuinely cannot resolve; when in doubt, `code`.**

## 7. Decide the verdict
`pass` iff no blocking finding; otherwise `needs_fix`. Set report-level `finding_class` =
`design` if any blocking finding is `design`, else `dependency` if any blocking finding is a
vulnerable package, else `code`. Escalation on a stalled or over-budget loop is the harness's
decision, not a verdict you emit.

## 8. False-positive triage (you are gated by scanners — be honest, not noisy)
The gate re-runs SAST and dep-audit and **reconciles**. Two failure modes to avoid:
- **Crying wolf** — flagging a matched pattern that is not exploitable. Demote to `info` with the
  reason. Noise erodes the value of your blocking findings.
- **False all-clear** — implying the diff is clean on dimensions only a scanner can verify
  (CVEs, full taint coverage). Never assert a clean dependency tree or "no injection anywhere";
  report what you scanned and let the gate confirm the rest.
If a scanner later finds something you missed, that is a signal your method has a gap — the same
finding should refine this skill (the self-improvement loop feeds on exactly these misses).

## 9. Re-review (carry-forward) discipline
On re-review, for each prior `blocking: true` finding, determine from the new diff whether it was
addressed: **resolved** → note in the Summary, retire the id; **not addressed** → carry forward
with the **same S-id**, severity held or escalated, append "(carried from prior review)" to
`evidence`; **partial** → carry forward, `evidence` describing what remains. Fresh findings take
the next unused S-id above the highest prior id. Stable ids are what let the harness recognise a
recurring finding.

## 10. Write the review artifact
Body sections, in order:
- **Summary** — ≤ 5 sentences: trust-surface touched (yes/no), the verdict and its single most
  load-bearing reason, security-test-adequacy note, what changed since the prior review.
- **Findings** — one bullet per finding, mirroring the structured return (id, severity, OWASP/CWE,
  `file:line`, evidence, action). No novel facts here; everything decision-relevant is in the
  return.
- **Verdict** — the word, then ≤ 2 sentences.
- **Handoff** — on `pass`: residual `info`/`low` items for awareness. On `needs_fix`: which
  S-ids to address and where. Do not restate routing — the harness owns it.

## Guardrails
You never modify source, tests, configuration, or any upstream artifact — your output is the
review. You never run the dependency or SAST scanners (the gate does). Your Bash is read-only.
You never decide what runs next.
