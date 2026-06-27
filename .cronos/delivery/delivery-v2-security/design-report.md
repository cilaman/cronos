---
class: design
agent: architect
goal_slug: delivery-v2-security
feature: "F1 — security-review node (delivery/v2 §2)"
phase: design
status: done
has_ui: false
req_ids: [REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007]
dd_ids: [DD-001, DD-002, DD-003, DD-004, DD-005, DD-006, DD-007, DD-008, DD-009, DD-010]
next_consumer: implementation
inputs_used:
  - .cronos/delivery/delivery-v2-security/analysis-report.md  # primary input (REQ-001..REQ-007)
  - docs/delivery-pipeline/delivery-v2/delivery-v2-spec.md (§2)
  - docs/delivery-pipeline/delivery-v2/agents/security-reviewer.md (draft)
  - docs/delivery-pipeline/delivery-v2/skills/security-review/SKILL.md (draft)
  - packages/delivery-workflow/agents/reviewer.md (shape exemplar)
  - packages/delivery-workflow/delivery.workflow.yaml
  - packages/delivery-workflow/schemas/delivery.workflow.schema.yaml
  - packages/delivery-workflow/spec_loader.py + tests/test_spec_loader.py
  - packages/delivery-workflow/tests/test_import_boundary.py
  - backend/app/pipeline/gate.py (_check_build, _check_g_review, _run_command, CHECK_REGISTRY, runGate)
  - backend/app/harnesses/decision.py (eval_condition grammar: ==, !=, in, &&)
---

# Design — F1 security-review node (delivery/v2)

Primary input: **`.cronos/delivery/delivery-v2-security/analysis-report.md`** (REQ-001…REQ-007,
`has_ui=false`). The analysis (scout phase not run) is itself grounded in spec §2. This design
converts those 7 requirements into a topologically-ordered, scope-bounded `iterations[]` DAG with
per-iteration `validation_command`s, DD records, and a risk register, and **resolves the two open
design questions the analysis handed to the architect** (DD-007 CI-mode detection; DD-008 scanner
set). Every iteration traces to ≥1 REQ; every DD traces to ≥1 REQ.

## Requirement set (from the analysis report)

| REQ | Summary | verifying_phase | Covered by |
|-----|---------|-----------------|------------|
| REQ-001 | `security-reviewer` agent at canonical package path; `reviewer` shape; no Edit; no hardcoded paths; `delivery_status` review fence | review | I1 |
| REQ-002 | `security-review` skill at canonical package path; 10 method sections; no hardcoded paths | review | I1 |
| REQ-003 | `security` in gate-check enum + sub-fields (`scanners`,`fail_on`,`on_missing_scanner`,`reconcile`); `test_schemas.py` untouched | test | I2 |
| REQ-004 | `_check_security` in `CHECK_REGISTRY`; re-executes scanners via `_run_command`; `fail_on`/`on_missing_scanner`/`reconcile`; missing⇏proceed; crash→retry | test | I3 |
| REQ-005 | `security` + `g-security` nodes; loop (max 3, escalate); 4 routing edges; no direct `g-review→testrun` | test | I4 |
| REQ-006 | Real-subprocess gate test (no mocks): fixture vuln dep + planted secret; missing-scanner asserts not-proceed | test | I3 |
| REQ-007 | Import-boundary invariant green; no `app.*` import in `packages/` | test | I1 (constraint), R6 |

---

## Resolved open questions (handed to the architect by the analysis)

**OQ-1 — How does the handler detect "CI mode" for the `on_missing_scanner` default?**
**Resolved (DD-007): an explicit per-check config field, not environment sniffing.** The
`on_missing_scanner` value lives in the gate-check spec in `delivery.workflow.yaml`
(`g-security` sets `on_missing_scanner: fail`). The handler reads `check.get("on_missing_scanner",
"fail")` — default `fail` (fail-closed). No `CI=true` env detection inside `_check_security`: env
coupling would make the gate non-deterministic and hard to unit-test, and contradicts the
project's "the gate config is the single source of truth" posture. A local/dev workflow can set
`on_missing_scanner: skip` in its own spec; CI uses the committed `fail`.

**OQ-2 — Scanner choice (semgrep vs bandit, gitleaks, pip-audit, npm audit) given the CI env.**
**Resolved (DD-008): config-driven scanner map, fail-closed on absence.** Verified: **none of
semgrep / bandit / gitleaks / pip-audit are installed in this environment; only `npm` is present.**
Therefore the design does NOT hardwire a scanner: each entry in `check["scanners"]` is an optional
command string, and absence is handled by `on_missing_scanner` (DD-007). The canonical
`g-security` spec lists `sast` (semgrep `--config auto`, with **bandit** `-r . -f json` documented
as the Python-only fallback), `secrets` (gitleaks), `deps_python` (pip-audit), `deps_node`
(npm audit) — but the handler treats every one as skippable-by-policy, so the pipeline never hard
-depends on a tool that isn't installed. Real-subprocess testing uses hermetic detector scripts
(DD-009), never the live tools.

---

## Design decisions

### DD-001 — Security is two halves: LLM agent node + gate that re-executes real scanners
**Statement.** Implement `security` (agent, LLM judgment) and `g-security` (gate re-executing
SAST/secret/dependency scanners) — mirroring the `review` / `g-build` split; never an LLM-only
gate. **Rationale.** A release-blocking gate must not trust an LLM self-report (false negatives
pass a real CVE; §2.1). `g-build` already re-executes the command rather than trusting
`validation_command_passed`; security follows the same "re-execute the claim" rule.
**Tradeoffs.** Two nodes; agent/gate can disagree (handled by reconcile, DD-006). Accepted.
**Traces:** REQ-001, REQ-004.

### DD-002 — finding_class = {code, dependency, design}; FOUR separate routing edges
**Statement.** The agent emits `finding_class ∈ {code, dependency, design}`. Routing uses **four
separate edges** from `g-security`: `proceed→testrun`, `needs_fix & code→implement`,
`needs_fix & dependency→implement`, `needs_fix & design→architect`. `code` and `dependency` are
**distinct edges** (both targeting `implement`), not collapsed. Misconfiguration ⇒ `code`.
**Rationale.** The edge grammar (`decision.py:eval_condition`) has no OR, so each routing target is
its own edge — exactly how `review` uses separate `local`/`architectural` edges (spec §2.3; analysis
REQ-005 scope note: *"two separate edges for code and dependency"*). Separate edges also keep the
gate's derived-class signal (DD-006) legible per target.
**Tradeoffs.** Rejected the grammar-valid `finding_class in 'code,dependency'` single-edge collapse
(I verified it parses) — it diverges from REQ-005 AC4's "all 4 routing edges present" and the
spec's stated shape, so requirement fidelity wins over edge-count golf. One more edge; negligible.
**Traces:** REQ-005.

### DD-003 — Placement: after `g-review` passes, before `testrun`
**Statement.** Rewire the existing `g-review →(review.fields.verdict == 'pass') testrun` edge to
target `security`; flow becomes `g-review → security → g-security → testrun`. No direct
`g-review → testrun` edge remains (REQ-005 AC3). **Rationale.** Code quality settles first, so
security reviews code that isn't about to be restructured (§2.2). A security `needs_fix→implement`
re-triggers the review loop on the next pass — accepted and arguably correct (a security fix should
be re-reviewed; the re-pass diff is small). **Tradeoffs.** One extra review pass on a security fix.
Parallel `review`+`security` (Option B) rejected for v2 — no fan-in/join primitive exists.
**Traces:** REQ-005.

### DD-004 — Schema: extend the gate-check item, keep `additionalProperties: false`
**Statement.** In `delivery.workflow.schema.yaml`: add `security` to the check-`type` enum **and**
add `scanners` (object, `additionalProperties: {type: string}`), `fail_on` (array of string),
`on_missing_scanner` (enum `[skip, fail]`), `reconcile` (boolean) to the check item; keep
`additionalProperties: false`. **Rationale.** `spec_loader._validate` runs Draft-07 over the whole
workflow; the check item is currently closed to `{type, of}`, so the `g-security` YAML (I4) would
fail `test_spec_loader::test_canonical_example_validates_clean` without this. **Hard ordering
dependency: I4 depends_on I2.** `test_schemas.py` (artifact-class schemas) is untouched (REQ-003
AC3). **Tradeoffs.** The four fields become syntactically permitted on every check type (inert on
non-security checks). Accepted as minimal-churn; a `oneOf` SecurityCheck variant is heavier and
unjustified for four optional fields. **Traces:** REQ-003, REQ-005.

### DD-005 — `_check_security` lives in `backend/app/pipeline/gate.py`, not the portable core
**Statement.** Implement the gate body in Cronos's `gate.py:CHECK_REGISTRY`; shell scanners through
the existing `_run_command` boundary (REQ-004 AC4: no bare `subprocess` in the handler). Do **not**
add scanner logic to `packages/delivery-workflow/` for v2. **Rationale.** Scanners are env tools
(`_check_security` shells out exactly as `_check_build`). The portable `lib/` extraction is
confidence-MEDIUM and "depends on the Phase-6 gate-engine shape, which doesn't exist yet" (§2.5).
Keeping the body in `gate.py` ships F1 now **and** keeps the import-boundary green — the package
gains no `app.*` import (REQ-007). **Tradeoffs.** Re-share into the portable runner at Phase 6
(recorded follow-up, R6). Accepted. **Traces:** REQ-004, REQ-007.

### DD-006 — Gate decision contract (precedence + reconcile + finding_class population)
**Statement.** `_check_security` reads the security agent's artifact (verdict, `finding_class`,
`findings[]` — mirroring `_check_g_review`'s artifact read) **and** re-executes the configured
scanners, then:
- **`proceed`** iff agent `verdict == pass` **and** no scanner reports a `fail_on` severity **and**
  no required scanner is missing-under-`fail`.
- **`needs_fix`** if agent `verdict == needs_fix` **OR** any scanner reports a `fail_on` severity.
  The gate **derives and persists** the effective routing `finding_class` into the `security`
  node's `fields.finding_class` so the four DD-002 edges always have a value on `needs_fix`:
  precedence **design** (agent-only — scanners can't see design flaws) **> dependency**
  (dep-scanner hit) **> code** (SAST/secret hit, or agent code finding). When the agent already set
  a class, it is honoured; a scanner-only hit the agent missed is classed by its scanner
  (dep→`dependency`, sast/secret→`code`) — both route to `implement`, so routing is robust.
- **Missing scanner binary** (exit 127 / "not found"): record as evidence; under
  `on_missing_scanner: fail` → never `proceed` (contributes `needs_fix`/`fail`, REQ-004 AC2); under
  `skip` → recorded and skipped.
- **`reconcile: true`**: an agent `critical`/`high` finding no scanner corroborates is kept and
  tagged `unverified`; a scanner hit the agent missed is a finding (and an F2 signal).
- **`retry`** on hard scanner infrastructure failure (crash / unparseable output, distinct from a
  finding) — short-circuits per `runGate` (REQ-004 AC3).
**Rationale.** Severity precedence mirrors `runGate` (`fail > needs_fix > proceed`, retry
short-circuits). Agent supplies reasoning (exploitability, design); scanners supply ground truth
(CVEs, entropy). **Tradeoffs.** Exit-code ambiguity (pip-audit/npm/gitleaks exit non-zero on both
"found" and "error") forces JSON parsing not exit-code-only gating (R3); persisting a derived class
into the agent namespace is a small executor contract noted in R7. Accepted. **Traces:** REQ-004,
REQ-005, REQ-006.

### DD-007 — `on_missing_scanner` is an explicit config field (default `fail`), not env CI-sniffing
*(Resolves OQ-1.)* **Statement.** Handler reads `check.get("on_missing_scanner", "fail")`; the
`g-security` YAML sets `fail`. No `CI` env detection in the handler body. **Rationale.** Config is
the single source of truth; env coupling breaks determinism and unit-testability and contradicts
the gate's pure-function shape. Fail-closed default protects CI; dev specs can opt into `skip`.
**Tradeoffs.** A dev who wants leniency must edit their spec rather than rely on an env var.
Accepted. **Traces:** REQ-004, REQ-006.

### DD-008 — Config-driven scanner map; fail-closed on absence (no hardwired tool)
*(Resolves OQ-2.)* **Statement.** `check["scanners"]` is an optional `name→command` map; the
canonical `g-security` lists `sast`/`secrets`/`deps_python`/`deps_node`, each treated as
skippable-by-policy (DD-007). Python SAST default = semgrep `--config auto`, with **bandit**
`-r . -f json` documented as the no-network Python-only fallback. **Rationale.** Verified none of
semgrep/bandit/gitleaks/pip-audit are installed here (only `npm`); hardwiring any one would make
the gate un-runnable. Config-driven + fail-closed lets the operator match their environment without
code change. **Tradeoffs.** A misconfigured/empty scanner map under `skip` could pass with zero
real scanning — mitigated by the `fail` default and the missing-scanner evidence record (R4).
**Traces:** REQ-004.

### DD-009 — Hermetic scanner fixtures for the real-subprocess test (not live network scanners)
**Statement.** REQ-006's real-subprocess test runs `_check_security` against a committed fixture
dir (a `requirements.txt` pinning a known-vulnerable package + a file with a **clearly-fake**
planted secret) using committed detector scripts that emit real tool-shaped JSON + real exit codes;
the missing-scanner test points one configured scanner at a guaranteed-absent binary and asserts
the decision is **not** `proceed` under `on_missing_scanner: fail`. **No mocking of `_run_command`
or `subprocess.run`** (REQ-006 AC1). **Rationale.** The live scanners are absent and pip-audit/
npm-audit hit the network CVE DB (non-deterministic, offline-hostile in CI). Hermetic detector
scripts exercise the **real** `_run_command` path — genuinely "not a mocked gate result", closing
the v1 P1 — while staying deterministic and offline. **Tradeoffs.** Validates the gate's
parse/severity/reconcile/missing logic, not the third-party scanners' own detection accuracy.
Accepted — the only way to a deterministic real-subprocess test in this environment.
**Traces:** REQ-006.

### DD-010 — Security loop on the agent node (mirrors `review`'s loop)
**Statement.** `security` node carries
`loop: {until: "security.fields.verdict == 'pass'", stall: [recurring_findings, no_diff_progress], max: 3, on_exhaust: escalate}`.
**Rationale.** Same bounded self-correcting loop as `review` (REQ-005 AC2 / §2.6). `max: 3` bounds
the fix loop; `recurring_findings` (a re-appearing stable S-id) is the stall signal; over-cap
escalates to a human. **Tradeoffs.** A genuinely-hard issue exhausts the loop and escalates —
correct, not a regression. **Traces:** REQ-005.

---

## Iterations (topologically ordered DAG)

```
I1 (agent+skill)  ─┐
I2 (schema)       ─┼─►  I4 (workflow wiring)
I3 (gate+test)    ─┘
```
Roots `I1`, `I2`, `I3` are mutually independent (parallelisable). `I4` is the integration capstone
joining all three. No cycles, no self-loops, every `depends_on` id exists, ≥1 root.

### I1 — Port the security-reviewer agent + security-review skill into the package
- **type:** doc
- **depends_on:** []
- **scope_files:**
  - `packages/delivery-workflow/agents/security-reviewer.md`
  - `packages/delivery-workflow/skills/security-review/SKILL.md`
- **what (REQ-001, REQ-002, REQ-007):** Move the two §2 drafts from
  `docs/delivery-pipeline/delivery-v2/` into the package, conformed to the `reviewer` shape: thin
  agent that **loads the paired `security-review` skill**; `delivery_status` fence with
  `fields.verdict ∈ {pass,needs_fix}` and `fields.finding_class ∈ {code,dependency,design}` and a
  `findings[]` array (REQ-001 AC3); `tools: Read, Grep, Glob, Bash, Write` (NO Edit — Bash
  read-only); **no hardcoded paths** (sever the old `security-officer` `REPO_ROOT=/data/spaces/...`
  coupling). The skill must keep its 10 method sections (REQ-002 AC2). The drafts are already close
  — verify and adapt, do not rewrite. Markdown only ⇒ no `app.*` import added (REQ-007).
- **validation_command:** `cd packages/delivery-workflow && python -m pytest tests/test_import_boundary.py -q && grep -q delivery_status agents/security-reviewer.md && grep -qi 'security-review' agents/security-reviewer.md && ! grep -REn '/data/spaces|REPO_ROOT=' agents/security-reviewer.md skills/security-review/SKILL.md`
- **max_diff_lines:** 240

### I2 — Add the `security` check type + its fields to the workflow schema
- **type:** backend
- **depends_on:** []
- **scope_files:**
  - `packages/delivery-workflow/schemas/delivery.workflow.schema.yaml`
  - `packages/delivery-workflow/tests/test_spec_loader.py`
- **what (REQ-003):** Per DD-004 — add `security` to the gate-check `type` enum; add `scanners`
  (object→string), `fail_on` (array of string), `on_missing_scanner` (enum `[skip, fail]`),
  `reconcile` (boolean) to the check item; keep `additionalProperties: false`. Add a self-contained
  `test_spec_loader.py` test that builds an in-memory spec with a `g-security` gate carrying a
  `security` check + all four fields and asserts `spec_loader.loads_spec` validates it clean, plus a
  negative asserting a bad `on_missing_scanner` value (e.g. `"warn"`) is rejected. Do **not** touch
  `test_schemas.py` (REQ-003 AC3).
- **validation_command:** `cd packages/delivery-workflow && python -m pytest tests/test_spec_loader.py tests/test_schemas.py -q`
- **max_diff_lines:** 90

### I3 — Implement `_check_security` + register it + real-subprocess gate test & fixtures
- **type:** backend
- **depends_on:** []
- **scope_files:**
  - `backend/app/pipeline/gate.py`
  - `backend/tests/test_pipeline_gate_security.py`
  - `backend/tests/fixtures/gate/security/requirements.txt`
  - `backend/tests/fixtures/gate/security/planted_secret.py`
  - `backend/tests/fixtures/gate/security/fake_secrets_scanner.py`
  - `backend/tests/fixtures/gate/security/fake_deps_scanner.py`
- **what (REQ-004, REQ-006):**
  1. Implement `_check_security(check, artifact_paths, space) -> (decision, errors, evidence)` per
     DD-006/DD-007/DD-008 and register `"security": _check_security` in `CHECK_REGISTRY`. Run each
     `check["scanners"]` command via `_run_command` (REQ-004 AC4 — no bare `subprocess`); classify
     each result as finding / clean / missing (exit 127 or "not found") / infra-crash; parse JSON
     for `fail_on` severities; read the agent artifact (reuse `_read_header` / the delivery_status
     parse, mirroring `_check_g_review`) for `verdict`+`finding_class`+`findings`; reconcile and
     derive/persist the routing `finding_class` (DD-006). Precedence `fail > needs_fix > proceed`,
     `retry` on infra-crash, `on_missing_scanner` default `fail` (DD-007).
  2. **Fixtures (DD-009):** `requirements.txt` pins a known-vulnerable package; `planted_secret.py`
     holds a **clearly-fake** secret (`PLANTED-SECRET-FOR-GATE-TEST` sentinel — NOT a real-looking
     AWS/OpenAI key, to avoid GitHub push protection, R5); `fake_secrets_scanner.py` emits
     gitleaks-shaped JSON + exit 1 on the sentinel; `fake_deps_scanner.py` emits pip-audit-shaped
     JSON + exit 1 for the vulnerable pin.
  3. **Tests:** REQ-006 AC1/AC2 — point `_check_security` at the fake detector commands against the
     fixture dir; assert `decision != "proceed"` with the secret hit classed `code` and the dep hit
     classed `dependency` (real subprocess via `_run_command`, NOT a mocked GateResult). REQ-006
     AC3 / REQ-004 AC2 — point one scanner at a guaranteed-absent binary
     (`cronos-no-such-scanner-xyz ...`) with `on_missing_scanner: fail` and assert `decision !=
     "proceed"`; with `skip` assert it is recorded but does not by itself force needs_fix. REQ-004
     AC3 — an infra-crash command (non-zero exit, no parseable findings) ⇒ `retry`. Also: agent
     `verdict==needs_fix` + clean scanners ⇒ needs_fix (design path; reconcile keeps it).
- **validation_command:** `cd backend && python -m pytest tests/test_pipeline_gate_security.py -q`
- **max_diff_lines:** 360

### I4 — Wire `security` + `g-security` nodes + the 4 routing edges into the workflow
- **type:** backend
- **depends_on:** [I1, I2, I3]
- **scope_files:**
  - `packages/delivery-workflow/delivery.workflow.yaml`
  - `packages/delivery-workflow/tests/test_workflow_security_node.py`
- **what (REQ-005):**
  - Add node `security` (`kind: agent`, `agent: security-reviewer`, `model: {use: reasoning}`,
    `tools: [Read, Grep, Glob, Bash, Write]`, `inputs: {from: [implement, architect]}`,
    `produces: {class: review}`, `recon: on`) with the **loop** from DD-010.
  - Add node `g-security` (`kind: gate`) with one `security` check: `scanners`
    (sast/secrets/deps_python/deps_node), `fail_on: [critical, high]`, `on_missing_scanner: fail`,
    `reconcile: true`.
  - **Rewire** the existing edge `g-review →(review.fields.verdict == 'pass') testrun` to target
    `security` (no direct `g-review → testrun` remains — REQ-005 AC3).
  - Add the connector + the **4 routing edges** (DD-002):
    1. `{from: security,   to: g-security}`
    2. `{from: g-security, to: testrun,   when: "g-security.decision == 'proceed'"}`
    3. `{from: g-security, to: implement, when: "g-security.decision == 'needs_fix' && security.fields.finding_class == 'code'"}`
    4. `{from: g-security, to: implement, when: "g-security.decision == 'needs_fix' && security.fields.finding_class == 'dependency'"}`
    5. `{from: g-security, to: architect, when: "g-security.decision == 'needs_fix' && security.fields.finding_class == 'design'"}`
    (edges 2–5 are the four routing edges of REQ-005; edge 1 is the agent→gate connector.)
  - Add `test_workflow_security_node.py`: assert the loaded spec contains both nodes; the loop
    (max 3, on_exhaust escalate); the four routing edges; the rewired `g-review → security` entry
    and **no** `g-review → testrun` edge; that `agents/security-reviewer.md` exists (ties to I1);
    and that `spec_loader.load_spec` still validates the canonical workflow clean (ties to I2).
- **validation_command:** `cd packages/delivery-workflow && python -m pytest tests/test_spec_loader.py tests/test_workflow_security_node.py -q`
- **max_diff_lines:** 100

---

## Risk register

| ID | Description | Severity | Mitigation |
|----|-------------|----------|------------|
| R1 | Real scanners (semgrep/bandit/gitleaks/pip-audit) are **absent** in dev/CI (verified; only `npm` present); a naive test depending on them is un-runnable or network-flaky. | high | DD-008 config-driven + fail-closed; DD-009 hermetic committed detector scripts + a guaranteed-absent binary for the missing case; never depend on a live CVE DB in the test. |
| R2 | Schema `additionalProperties: false` rejects the new security check fields → `test_spec_loader` breaks the moment the `g-security` YAML lands. | high | DD-004 + `I4 depends_on I2`: extend the check-item schema **before** wiring the YAML; ordering enforced by the DAG. |
| R3 | Exit-code ambiguity: pip-audit / npm audit / gitleaks exit non-zero on **both** "found" and "error", so exit-code-only gating mis-fires. | medium | DD-006: parse JSON to determine findings/severities; reserve `retry` for unparseable/crash; treat exit 127 / "not found" as **missing**, not a finding. |
| R4 | Reconcile false-negative: gate passes because the agent said `pass` while required scanners were silently skipped (missing or empty map). | medium | DD-006 + DD-007 + REQ-006 AC3 test: a missing scanner under `fail` is recorded and is **not** a pass; default `fail`. |
| R5 | A realistic-looking planted secret in the fixture trips GitHub push protection at commit/finalize (cf. prior trace-secret-scanning block). | medium | DD-009: use an obviously-synthetic `PLANTED-SECRET-FOR-GATE-TEST` sentinel the committed detector matches but real secret scanners/GitHub do not flag. |
| R6 | Keeping `_check_security` only in `gate.py` defers portable-runner parity; moving it to `lib/` now risks the import-boundary test. | low | DD-005: keep it in `backend/app/pipeline/gate.py` for v2 (markdown-only I1 touches the portable core → boundary stays green); record the `lib/` extraction as a Phase-6 follow-up (§2.5). |
| R7 | finding_class routing: a scanner-only hit the agent missed leaves `security.fields.finding_class` unset under the four separate `==` edges, risking a stuck route. | medium | DD-006: the gate **derives and persists** an effective `finding_class` (design>dependency>code) into the security node's fields on any `needs_fix`, so a routing edge always matches; fallback if the executor disallows the cross-namespace write — the loop re-runs the agent, which re-emits the class. Implementor must confirm the executor merges gate-derived fields. |

---

## Traceability cross-check
- Every REQ-001…REQ-007 appears in an iteration's scope/`what` (see the requirement table + per-iteration tags).
- Every DD (DD-001…DD-010) traces to ≥1 REQ (see each DD's **Traces** line).
- Both open questions handed to the architect are resolved (OQ-1→DD-007, OQ-2→DD-008).
- `iterations_planned` = 4 = `len(iterations[])` (I1–I4).
- `risks_count` = 7 = `len(risks[])` (R1–R7).
- `dd_ids[]` = DD-001…DD-010 (10 ids), matching the frontmatter.
- DAG validity: roots {I1, I2, I3}; single sink I4 `depends_on [I1, I2, I3]`; no cycle, no self-loop, all referenced ids exist.

```delivery_status
{
  "status": "done",
  "produces": "design",
  "artifact_paths": [".cronos/delivery/delivery-v2-security/design-report.md"],
  "fields": {
    "iterations_planned": 4,
    "iterations_count": 4,
    "risks_count": 7,
    "has_ui": false,
    "dd_ids": ["DD-001", "DD-002", "DD-003", "DD-004", "DD-005", "DD-006", "DD-007", "DD-008", "DD-009", "DD-010"]
  },
  "open_questions": [],
  "telemetry": {"tokens": 0, "usd": 0.0, "seconds": 0.0}
}
```
