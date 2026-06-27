---
class: analysis
goal_slug: delivery-v2-security
feature: F1 — security-review node
has_ui: false
req_ids: [REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007]
next_consumer: design
---

# Analysis Report — delivery/v2 F1: security-review node

## Research basis

The scout report at `.cronos/delivery/delivery-v2-security/scout-report.md` was not produced (the
scout phase was not executed). This analysis is grounded instead in the spec authored with
codebase reconnaissance: `docs/delivery-pipeline/delivery-v2/delivery-v2-spec.md` (confidence
HIGH — spec §0 explicitly enumerates all pre-existing artefacts and their current locations after
reading them directly). Additionally, the following files were read directly during this analysis:

- `packages/delivery-workflow/agents/` — current agent set (no `security-reviewer.md` present)
- `packages/delivery-workflow/skills/` — current skill set (no `security-review/` present)
- `docs/delivery-pipeline/delivery-v2/agents/security-reviewer.md` — draft agent
- `docs/delivery-pipeline/delivery-v2/skills/security-review/SKILL.md` — draft skill
- `packages/delivery-workflow/schemas/delivery.workflow.schema.yaml` — current enum (no `security`)
- `packages/delivery-workflow/delivery.workflow.yaml` — current graph (no security nodes)
- `backend/app/pipeline/gate.py` — `_run_command`, `CHECK_REGISTRY` (no `security` handler)
- `.claude/agents/security-officer.md` — harvest source (335 lines, Cronos-coupled)

## Existing implementation (do not re-derive)

| Artefact | Status | Location |
|---|---|---|
| Draft security-reviewer agent | **exists** | `docs/delivery-pipeline/delivery-v2/agents/security-reviewer.md` |
| Draft security-review skill | **exists** | `docs/delivery-pipeline/delivery-v2/skills/security-review/SKILL.md` |
| `_run_command` subprocess boundary | **exists** | `gate.py:87` |
| `CHECK_REGISTRY` pattern | **exists** | `gate.py:631` — 9 handlers registered |
| `_check_g_review` (routing-from-verdict pattern) | **exists** | `gate.py:572` |
| `security-officer.md` harvest source | **exists** | `.claude/agents/security-officer.md` |

## Gaps (what this feature must add)

All 7 gaps are distinct deliverables with no existing implementation:

1. `packages/delivery-workflow/agents/security-reviewer.md` — not at canonical package path
2. `packages/delivery-workflow/skills/security-review/SKILL.md` — not at canonical package path
3. `security` check type in schema enum — absent from closed enum in `delivery.workflow.schema.yaml`
4. `_check_security` handler in `gate.py` — not in `CHECK_REGISTRY`
5. `security`/`g-security` nodes + edges in `delivery.workflow.yaml` — not in graph
6. Real-subprocess gate test for the security check — no test exercises a real scanner subprocess (known-vulnerable dep + planted secret paths untested; this was a P1 from v1 review)
7. Import-boundary invariant — must stay green; adding `app.*` imports to `packages/` would break it

---

## Requirements

### REQ-001 — security-reviewer agent at canonical package path

The `security-reviewer` agent definition must exist at
`packages/delivery-workflow/agents/security-reviewer.md`, adapted from the draft in
`docs/delivery-pipeline/delivery-v2/agents/security-reviewer.md`. It must mirror the `reviewer`
agent shape: thin definition (role + hard rules), all paths runtime-supplied, no hardcoded space
paths, loads the paired `security-review` skill, carries a `delivery_status` fence, has no Edit
tool.

**Acceptance criteria**
1. `packages/delivery-workflow/agents/security-reviewer.md` exists and has valid YAML frontmatter
   with `name: security-reviewer` and `tools` list that omits `Edit`.
2. The agent definition references the `security-review` skill by name and does not contain any
   hardcoded path strings (no `/data/spaces/`, no `REPO_ROOT=`, no literal space IDs).
3. The example `delivery_status` fence in the definition uses the `review` class and carries
   `verdict`, `finding_class`, and `findings[]` fields.

**verifying_phase**: review  
**confidence**: 0.95

---

### REQ-002 — security-review skill at canonical package path

The `security-review` skill must exist at
`packages/delivery-workflow/skills/security-review/SKILL.md`, adapted from the draft in
`docs/delivery-pipeline/delivery-v2/skills/security-review/SKILL.md`. It must carry the full
method: the grep sweeps, OWASP/CWE taxonomy table, severity ladder, code/dependency/design
routing classification rubric, false-positive triage rules, carry-forward discipline for
re-reviews, and the review artifact structure.

**Acceptance criteria**
1. `packages/delivery-workflow/skills/security-review/SKILL.md` exists and its frontmatter has
   `name: security-review`.
2. The skill contains the 10 method sections (preflight, trust model, scan sweeps, OWASP/CWE
   mapping, severity ladder, routing classification, verdict decision, false-positive triage,
   carry-forward discipline, artifact format) matching the spec §2.3 taxonomy.
3. No hardcoded paths appear in any grep sweep command or example.

**verifying_phase**: review  
**confidence**: 0.95

---

### REQ-003 — `security` added to gate-check type enum in schema

The closed `type` enum in `packages/delivery-workflow/schemas/delivery.workflow.schema.yaml`
(currently: `schema|traceability|acceptance|build|lint|types|test|diff_vs_acceptance|custom`) must
include `security` as a first-class value. The schema must also declare the `security`-specific
sub-fields (`scanners`, `fail_on`, `on_missing_scanner`, `reconcile`) so that a check with
`type: security` is schema-valid and a check with an unknown type remains schema-invalid.

**Acceptance criteria**
1. `"security"` appears in the enum list in `delivery.workflow.schema.yaml` at the same level as
   existing type strings.
2. A schema-validation call against a check block `{type: security, scanners: {...}, fail_on:
   [critical, high], on_missing_scanner: fail, reconcile: true}` returns valid (no errors).
3. The existing `test_schemas.py` tests still pass without modification.

**verifying_phase**: test  
**confidence**: 0.90

---

### REQ-004 — `_check_security` handler implemented and registered in `gate.py`

A `_check_security` function must be implemented in `backend/app/pipeline/gate.py` and registered
as `"security": _check_security` in `CHECK_REGISTRY`. It must re-execute real scanners through the
existing `_run_command` subprocess boundary (no inline `subprocess` calls), honour the `fail_on`
severity list, the `on_missing_scanner` policy (`fail` | `skip`), and the `reconcile` flag.
Decision logic: scanner hit at a `fail_on` severity → `needs_fix` with derived `finding_class`
(dep-scanner hit → `dependency`; SAST/secret hit → `code`). Scanner binary missing in CI mode
(`on_missing_scanner: fail`) → `needs_fix` or `fail` — never `proceed`. Scanner infrastructure
crash → `retry`. The function must return `(decision, errors, evidence)` matching the existing
handler signature.

**Acceptance criteria**
1. `CHECK_REGISTRY` contains the key `"security"` mapped to `_check_security`.
2. When a configured scanner is not installed and `on_missing_scanner: fail`, the handler does not
   return `"proceed"` — it returns `"needs_fix"` or `"fail"` with an explanatory error.
3. A simulated scanner crash (non-zero exit, no findings) returns `"retry"`, not `"needs_fix"`.
4. All calls to external tools go through `_run_command`, not through additional `subprocess`
   calls in the handler body.

**verifying_phase**: test  
**confidence**: 0.92

---

### REQ-005 — `security`/`g-security` nodes + edges + loop block in `delivery.workflow.yaml`

The workflow graph in `packages/delivery-workflow/delivery.workflow.yaml` must include:
- A `security` agent node with `agent: security-reviewer`, positioned after `g-review` (before
  `testrun`), carrying a `loop` block (`until: "security.fields.verdict == 'pass'"`, `max: 3`,
  `on_exhaust: escalate`).
- A `g-security` gate node with `checks: [{type: security, ...}]`.
- Four routing edges from `g-security`: to `testrun` on proceed, to `implement` on
  `needs_fix`+`finding_class==code`, to `implement` on `needs_fix`+`finding_class==dependency`,
  to `architect` on `needs_fix`+`finding_class==design`.
- The existing edge `from: g-review, to: testrun` must be replaced by `from: g-review, to:
  security` (the security node now sits between review and testrun).

**Acceptance criteria**
1. Both `security` and `g-security` node IDs appear in the `nodes:` list of `delivery.workflow.yaml`.
2. The `security` node's `loop.max` is 3 and `loop.on_exhaust` is `escalate`.
3. No direct edge from `g-review` to `testrun` remains (the security pair intercepts it).
4. The workflow YAML passes schema validation against `delivery.workflow.schema.yaml` with all 4
   routing edges present.

**verifying_phase**: test  
**confidence**: 0.90

---

### REQ-006 — Real-subprocess gate test for the security check

The gate test suite must include at least one test that exercises `_check_security` (or the Cronos
adapter gate) against a real subprocess invocation — not a mocked gate result. The test must
use a fixture repository (temp dir) that contains: (a) a Python or Node dependency known to be
vulnerable at the `critical` or `high` level, or a `requirements.txt` / `package.json` with a
pinned old version that `pip-audit` / `npm audit` flag, AND (b) a planted secret matching the
grep pattern for hardcoded credentials. A second test must assert that a missing scanner binary
with `on_missing_scanner: fail` does NOT return a `proceed` decision.

This explicitly closes the P1 carried forward from the v1 review: *"e2e mocks the gate result
rather than exercising a real subprocess."*

**Acceptance criteria**
1. A test invokes `_check_security` (or the Cronos adapter path) with a real fixture directory;
   it does not mock `_run_command` or `subprocess.run`.
2. The test asserts `decision != "proceed"` when a planted secret or vulnerable dependency is
   present.
3. A separate test asserts `decision not in ("proceed",)` when a scanner is absent and
   `on_missing_scanner: fail` is set.

**verifying_phase**: test  
**confidence**: 0.88

---

### REQ-007 — Import-boundary invariant preserved

No implementation step for F1 must add an import of any `app.*` module (i.e., any symbol from
`backend/app/`) into any file under `packages/delivery-workflow/`. The existing
`tests/test_import_boundary.py` enforces this and must continue to pass green.

**Acceptance criteria**
1. `tests/test_import_boundary.py` passes without modification after all F1 changes are applied.
2. `packages/delivery-workflow/` contains no `from app.` or `import app.` statements in any Python
   source file after implementation.

**verifying_phase**: test  
**confidence**: 0.98

---

## `has_ui` determination

`has_ui = false`. F1 is entirely backend/pipeline — a new agent asset, a skill asset, a gate
handler, and a workflow graph change. No frontend page, route, component, or API endpoint consumed
only by the frontend is touched or created. The delivery.workflow.yaml change is a pipeline data
file, not UI configuration.

---

## Traceability table

| REQ | Acceptance criteria | Verifying phase |
|---|---|---|
| REQ-001 | Agent at package path; no Edit tool; no hardcoded paths; delivery_status fence with review class | review |
| REQ-002 | Skill at package path; 10 sections present; no hardcoded paths | review |
| REQ-003 | `security` in enum; valid check block accepted; `test_schemas.py` still passes | test |
| REQ-004 | `_check_security` in `CHECK_REGISTRY`; missing scanner → not-proceed; crash → retry; uses `_run_command` | test |
| REQ-005 | Both nodes in YAML; loop block correct; no direct g-review→testrun edge; schema validates | test |
| REQ-006 | Real subprocess (no mocks) against fixture with vulnerable dep + secret; missing-scanner path asserts not-proceed | test |
| REQ-007 | `test_import_boundary.py` green; no `app.*` imports in `packages/` | test |

---

## Scope notes for the architect

- **No new API endpoints** — `_check_security` registers into the existing `CHECK_REGISTRY` dict;
  no new FastAPI routes are needed.
- **Draft agents/skills need minimal adaptation** — the drafts in `docs/delivery-pipeline/delivery-v2/` are high-quality and need path-coupling removed, not rewrites.
- **Gate handler design is constrained** — must follow the `(decision, errors, evidence)` tuple
  return signature used by all existing handlers; must use `_run_command` (not bare subprocess);
  scanner choice (semgrep vs bandit, gitleaks, pip-audit, npm audit) is a design decision the
  architect should resolve given the CI environment.
- **`on_missing_scanner` policy** — default `fail` in CI mode is load-bearing for REQ-006 AC3;
  the architect must specify how the handler detects "CI mode" (environment variable vs explicit
  config field).
- **Workflow edge count** — 4 routing edges from `g-security` per spec §2.3; the `||`-less
  condition grammar means two separate edges for `code` and `dependency` both routing to
  `implement`.
- **Open design question from spec §8.1**: sequential security (after g-review, before testrun,
  as specified here) vs. parallel join (not recommended for v2 — requires a new join primitive).
  Requirements assume sequential placement per the spec recommendation.
