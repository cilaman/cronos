# CC-v1 Pipeline Known Issues

Findings that affect the Cronos CC-v1 pipeline framework.  Each finding has an
F-number local to this catalog (F-01, F-02, …).  Parallel findings in the
Delivery Notes harness use the same F-NN convention but with a separate
sequence.

Entries are appended by the `pipeline-issue` helper
(`app.pipeline.known_issues.append_issue`).  The retro-phase agent is the
primary caller; human operators may also append entries via the CLI
(`python -m app.pipeline.known_issues`).

---

## F-01 — Verifier exit 3 (missing artifact) emits no agent name in error text

**Status**: Open (2026-05-30) | **Affects**: pipeline-gate skill, all phases
**Severity**: Low

When `verify.py` exits with code 3 (artifact file not found) the structured
JSON output lists the missing path but does not name the agent that should have
written it.  Gate-task logs are therefore slightly harder to triage — the
operator must cross-reference the phase → agent mapping manually.

**Workaround**: Cross-reference `CLASS_CONFIG[phase]["agent"]` in
`backend/app/pipeline/verify.py` to find the expected agent name.

---

## F-02 — `pipeline-scaffold` slug collision is silent

**Status**: Open (2026-05-30) | **Affects**: pipeline-scaffold skill
**Severity**: Medium

The pipeline-scaffold skill does not check whether a goal with the derived slug
already exists before calling `POST /api/goals`.  If two features share the
same slug (e.g. both produce `"my-feature"`), the second scaffold run creates a
duplicate goal with the same slug, leaving pipeline-state.json on the first
goal's path and the second goal unreachable through normal pipeline tooling.

**Workaround**: Choose unique, descriptive feature request titles.  A slug
collision can be detected by checking `GET /api/goals?slug=<slug>` before
scaffolding.

---
