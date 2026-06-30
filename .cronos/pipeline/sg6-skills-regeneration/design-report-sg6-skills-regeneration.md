---
cc_version: '1.0'
agent: pipeline-architect
slug: sg6-skills-regeneration
phase: design
status: done
confidence: 0.88
inputs_used:
- memory:project_pipeline_cronos_mapping
- memory:project_pipeline_scaffold_skill
- memory:project_delivery_v1_cronos_adapter_design
- .cronos/pipeline/sg6-skills-regeneration/analysis-report-sg6-skills-regeneration.md
- .cronos/pipeline/sg6-skills-regeneration/scout-report-sg6-skills-regeneration.md
- .claude/skills/create-goal/SKILL.md
- .claude/skills/create-task/SKILL.md
- .claude/skills/pipeline-scaffold/SKILL.md
- backend/app/delivery_driver.py
- backend/app/run_executor.py
- backend/tests/test_delivery_driver.py
outputs_produced:
- .cronos/pipeline/sg6-skills-regeneration/design-report-sg6-skills-regeneration.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - .claude/skills/create-goal/
  - .claude/skills/create-task/
  - .claude/skills/pipeline-scaffold/
  - .claude/agents/
  - backend/app/delivery_driver.py
  - backend/app/run_executor.py
  - backend/tests/test_delivery_driver.py
  - packages/delivery-workflow/
  excluded:
  - frontend/: has_ui=false; no UI surfaces
  - backend/app/harnesses/: orthogonal subsystem (harness runner, not delivery runner)
  - backend/app/storage.py and schema layer: no Task model changes (sentinel rides
      in brief)
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_keyword
iterations:
- id: I1
  type: infra
  scope_files:
  - .claude/skills/create-goal/SKILL.md
  validation_command: test ! "$(grep -cE '(CC-v1 pipeline structure|Procedure -- feature
    goal|Feature goal \(CC-v1 pipeline structure\)|pipeline-implementor|pipeline-architect)'
    /data/spaces/cronos-development/.claude/skills/create-goal/SKILL.md)" -gt 0 &&
    grep -q 'Field reference' /data/spaces/cronos-development/.claude/skills/create-goal/SKILL.md
    && grep -q 'Git workflow for development goals' /data/spaces/cronos-development/.claude/skills/create-goal/SKILL.md
  max_diff_lines: 250
  depends_on: []
- id: I2
  type: infra
  scope_files:
  - .claude/skills/create-delivery-goal/SKILL.md
  validation_command: 'test -f /data/spaces/cronos-development/.claude/skills/create-delivery-goal/SKILL.md
    && grep -q ''^name: create-delivery-goal'' /data/spaces/cronos-development/.claude/skills/create-delivery-goal/SKILL.md
    && grep -qE ''<!--\s*delivery-workflow:'' /data/spaces/cronos-development/.claude/skills/create-delivery-goal/SKILL.md
    && grep -q ''do not pre-create'' /data/spaces/cronos-development/.claude/skills/create-delivery-goal/SKILL.md
    && grep -q ''When to use'' /data/spaces/cronos-development/.claude/skills/create-delivery-goal/SKILL.md
    && grep -q ''packages/delivery-workflow/delivery.workflow.yaml'' /data/spaces/cronos-development/.claude/skills/create-delivery-goal/SKILL.md'
  max_diff_lines: 300
  depends_on: []
- id: I3
  type: infra
  scope_files:
  - .claude/skills/pipeline-scaffold/SKILL.md
  validation_command: grep -qiE '(DEPRECATED|RETIRED|superseded)' /data/spaces/cronos-development/.claude/skills/pipeline-scaffold/SKILL.md
    && grep -q '/create-delivery-goal' /data/spaces/cronos-development/.claude/skills/pipeline-scaffold/SKILL.md
  max_diff_lines: 80
  depends_on:
  - I2
- id: I4
  type: backend
  scope_files:
  - backend/tests/test_create_delivery_goal_contract.py
  validation_command: cd /data/spaces/cronos-development/backend && pytest tests/test_create_delivery_goal_contract.py
    -v --override-ini="addopts="
  max_diff_lines: 200
  depends_on:
  - I2
- id: I5
  type: backend
  scope_files:
  - backend/tests/test_skill_files_phase_cleanliness.py
  validation_command: cd /data/spaces/cronos-development/backend && pytest tests/test_skill_files_phase_cleanliness.py
    -v --override-ini="addopts="
  max_diff_lines: 150
  depends_on:
  - I1
  - I2
  - I3
risks:
- description: I1's destructive edit to create-goal/SKILL.md (removing lines 49-72
    prose section and lines 125-216 Python procedure) accidentally deletes the surrounding
    'Field reference' table, the simple-goal Procedure, or the 'Git workflow for development
    goals' section. The file is the canonical user-facing reference; over-pruning
    regresses the non-pipeline goal UX.
  severity: high
  mitigation: Iteration validation_command for I1 grep-asserts BOTH the absence of
    CC-v1 phase markers AND the presence of 'Field reference' and 'Git workflow for
    development goals' anchors before the iteration can pass. Implementor must preserve
    lines 1-46 (header + API + Field reference + Simple goal section), lines 74-123
    (simple-goal Procedure including api_post helper), and lines 218-249 (Verify +
    Writing good briefs + Git workflow). Only lines ~47-72 (Feature goal section)
    and ~125-216 (Procedure -- feature goal Python block) are removed; section 'Choosing
    a goal structure' must be re-headlined or trimmed to 'Choosing a goal structure
    (coordination/ops only)' so the remaining content stays coherent.
- description: The sentinel format in create-delivery-goal/SKILL.md drifts from delivery_driver.py:DELIVERY_WORKFLOW_SENTINEL_PATTERN
    (e.g. extra whitespace, missing line anchors, wrong comment style). detect_delivery_workflow_spec()
    then silently returns None and the runner never fires, falling through to _topo_children_local
    with zero child tasks (a no-op goal that looks complete on the board).
  severity: critical
  mitigation: 'I4 contract test executes detect_delivery_workflow_spec() against the
    exact sentinel string that I2''s example code emits, asserting a non-None spec_path.
    The skill''s documented sentinel format MUST be a copy-paste of the literal ''<!--
    delivery-workflow: {spec_path} -->'' (with the placeholder shown but the surrounding
    characters byte-identical to DELIVERY_WORKFLOW_SENTINEL_PATTERN). I4 imports DELIVERY_WORKFLOW_SENTINEL_PATTERN
    from backend.app.delivery_driver and tests both an inline literal and a regex-extracted
    example pulled from the SKILL.md file itself.'
- description: I2's Python example diverges from the api_post helper pattern in create-goal/SKILL.md
    (lines 82-95) -- e.g. forgets the Bearer token from CRONOS_INTERNAL_TOKEN, uses
    curl instead of urllib, or hardcodes a space_id. Agents reading the skill copy-paste
    the broken example and post fails or mis-routes.
  severity: medium
  mitigation: 'I2 must lift the api_post() helper verbatim from create-goal/SKILL.md
    lines 82-95 (no edits). The Python example adds only: (a) the sentinel line to
    the brief string, (b) a single api_post() call, (c) NO child-task loop. Reviewer
    cross-checks I2''s helper against create-goal/SKILL.md''s helper byte-for-byte.
    I5 cleanliness test asserts I2''s example contains ''urllib.request'' and the
    literal sentinel marker.'
- description: R2/R6 are confirmation passes the analyst marked as 'currently clean'
    from a grep snapshot. A future change to create-task/SKILL.md or any .claude/agents/*.md
    could regress before SG6 merges, making the confirmation stale. Without an enforced
    regression guard, the same drift can re-occur after SG6.
  severity: medium
  mitigation: I5 promotes R2 and R6 into a permanent regression test (test_skill_files_phase_cleanliness.py)
    that greps create-task/SKILL.md for ('pipeline', 'CC-v1', 'analyst', 'architect',
    'impl phase', 'review phase', 'doc phase') and asserts zero matches, and greps
    every .claude/agents/*.md for the narrow strings ('pipeline-scaffold', '/create-goal')
    and asserts zero matches. The test runs in CI; future drift is caught at PR time,
    not by re-running scout.
- description: Deprecating pipeline-scaffold (I3) rather than deleting it leaves a
    working-but-stale skill discoverable via `/pipeline-scaffold`. An agent unaware
    of the deprecation invokes it and creates a 7-phase pre-created task DAG that
    the runner will then duplicate when it sees the sentinel-less goal.
  severity: medium
  mitigation: I3 places the deprecation notice in both (a) the frontmatter description
    field (which Claude Code surfaces in the skill picker) and (b) the opening paragraph
    of the body, in bold. The notice explicitly tells callers 'do not invoke this
    skill for new goals' and points to /create-delivery-goal. pipeline-scaffold's
    existing Procedure section is left intact so historical pipelines can still be
    understood, but the body opens with the redirect. Hard-delete is deferred to a
    follow-up goal after a deprecation window confirms no live invocations.
- description: I4 contract test depends on a Cronos backend being reachable at http://backend:8000
    (the standard skill assumption). If pytest runs in an environment without the
    backend service, the test either hangs or reports a misleading connection error
    rather than testing the skill contract.
  severity: low
  mitigation: I4 does NOT call the live backend. It is a unit-level contract test
    that (a) reads .claude/skills/create-delivery-goal/SKILL.md, (b) extracts the
    documented sentinel format and example brief via regex, and (c) calls detect_delivery_workflow_spec()
    directly with that brief string, asserting non-None. No HTTP calls. Optionally
    I4 also uses a TaskStore in-memory fixture to verify that posting a brief with
    the extracted sentinel through the storage layer creates exactly one task with
    type=goal and no child tasks (no HTTP, no worker).
metrics:
  tool_calls: 10
  files_read: 8
  memory_hits: 3
  iterations_planned: 5
---

## Summary

SG6 retires the hardcoded CC-v1 six-phase goal-pre-creation pattern from the skills layer in favor of a sentinel-driven, runner-orchestrated delivery goal. The design splits into five iterations: two infra edits to existing skill files (I1 prune `create-goal`, I3 deprecate `pipeline-scaffold`), one new skill file (I2 `create-delivery-goal`), and two regression tests (I4 sentinel contract test, I5 cross-file phase-language cleanliness). The DAG is wide: I1 and I2 run in parallel at layer 0; I3 (which redirects to the new skill), I4 (which validates the new skill's sentinel), and I5 (which guards all three) sit at layer 1+. No backend code changes — the runner dispatch is already merged in SG4. Open questions resolved: pipeline-scaffold is **deprecated in-place** (not deleted) and `spec_path` is a **required, explicitly-documented argument** with `packages/delivery-workflow/delivery.workflow.yaml` shown as the canonical default in the example.

## Components

### Data
- (no data changes) — workflow binding rides in the goal brief as a sentinel; no Task model fields, no schema migrations, no storage extensions.

### Backend
- (no backend code changes) — `backend/app/delivery_driver.py:detect_delivery_workflow_spec()` and `backend/app/run_executor.py:run_goal()` pre-dispatch routing are already in place from SG4.
- `backend/tests/test_create_delivery_goal_contract.py` (new): unit-level contract test verifying the SKILL.md's documented sentinel format is byte-compatible with `DELIVERY_WORKFLOW_SENTINEL_PATTERN`.
- `backend/tests/test_skill_files_phase_cleanliness.py` (new): regression guard greps `create-task/SKILL.md` and all `.claude/agents/*.md` for phase-pre-creation patterns; permanently locks R2 and R6 results.

### Skills (the user-facing surface SG6 actually reshapes)
- `.claude/skills/create-goal/SKILL.md` (edit): strip the "Feature goal (CC-v1 pipeline structure)" prose (lines ~47-72) and the "Procedure -- feature goal" Python block (lines ~125-216). Preserve API table, simple-goal procedure with api_post helper, Verify, Writing good briefs, and Git workflow sections.
- `.claude/skills/pipeline-scaffold/SKILL.md` (edit): add a deprecation notice in the frontmatter description and a bold redirect block at the top of the body pointing to `/create-delivery-goal`. Body procedure is left intact for historical reference.
- `.claude/skills/create-delivery-goal/SKILL.md` (new): canonical skill for creating one delivery goal. Includes YAML frontmatter (`name: create-delivery-goal`), "When to use" section (delivery goals vs coordination/ops goals — R8), "Sentinel format" section documenting `<!-- delivery-workflow: {spec_path} -->`, "Procedure" with single Python `api_post()` call (no child-task loop, sentinel in brief), explicit "Do NOT pre-create scout/analyst/architect/impl/test/review/doc tasks" rule, and a Verify section showing 1 goal + 0 children on the board.

## Implementation plan

| ID  | Type  | Depends on | Scope files (abridged)                                            | Validation (abridged)                                                                                |
|-----|-------|------------|-------------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| I1  | infra | -          | .claude/skills/create-goal/SKILL.md                               | grep absent: CC-v1 phase markers; grep present: Field reference + Git workflow anchors               |
| I2  | infra | -          | .claude/skills/create-delivery-goal/SKILL.md                      | file exists + frontmatter + sentinel literal + "do not pre-create" + canonical spec path             |
| I3  | infra | I2         | .claude/skills/pipeline-scaffold/SKILL.md                         | grep present: DEPRECATED/superseded marker + /create-delivery-goal redirect                          |
| I4  | backend | I2         | backend/tests/test_create_delivery_goal_contract.py               | pytest passes; detect_delivery_workflow_spec() returns non-None from the SKILL.md example brief      |
| I5  | backend | I1, I2, I3 | backend/tests/test_skill_files_phase_cleanliness.py               | pytest passes; create-task + .claude/agents/*.md greps return zero matches for phase-creation strings|

Topological layers: **L0 = {I1, I2}**, **L1 = {I3, I4}** (both depend only on I2), **L2 = {I5}** (depends on all prior). Implementors at the same layer run in parallel.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| I1 over-pruning create-goal/SKILL.md deletes surrounding sections (Field reference, simple-goal Procedure, Git workflow) | high | I1 validation greps for required anchors; implementor must preserve lines 1-46, 74-123, 218-249 (only ~47-72 and ~125-216 are removed) |
| Sentinel format in I2 drifts from delivery_driver.py:DELIVERY_WORKFLOW_SENTINEL_PATTERN, silently breaking runner routing | critical | I4 contract test imports the regex from backend.app.delivery_driver and asserts the SKILL.md's example brief produces a non-None spec_path |
| I2's Python example diverges from create-goal's api_post helper pattern (wrong auth header, curl instead of urllib, hardcoded space_id) | medium | I2 lifts api_post verbatim from create-goal/SKILL.md lines 82-95; reviewer cross-checks byte-for-byte; I5 asserts urllib.request + literal sentinel appear in I2 |
| R2/R6 grep-only confirmation today regresses tomorrow without a permanent guard | medium | I5 promotes both checks into CI-resident regression tests against create-task/SKILL.md and .claude/agents/*.md |
| Deprecated pipeline-scaffold remains invokable; an unaware agent uses it and races the runner | medium | I3 puts the deprecation in the frontmatter description (skill-picker visible) AND in bold at the top of the body, pointing to /create-delivery-goal; hard-delete is deferred to a follow-up |
| I4 contract test depends on a live backend if implemented naively | low | I4 is a pure unit test: reads SKILL.md, extracts the example brief via regex, calls detect_delivery_workflow_spec() directly; no HTTP, no live backend |

## Assumptions

- **No backend code changes are required.** `backend/app/delivery_driver.py:detect_delivery_workflow_spec()` and `backend/app/run_executor.py:run_goal()` pre-dispatch (lines 943-964) are already merged from SG4. SG6 is exclusively a skills-layer and test-layer change.
- **Sentinel format is frozen** to `<!-- delivery-workflow: {spec_path} -->` (MULTILINE-anchored). I2 documents this literal verbatim; I4 contract test imports the regex from `backend.app.delivery_driver` and uses it as the oracle. No new regex is introduced.
- **`create-task/SKILL.md` is genuinely clean today** (analyst direct read, confirmed by a second-pass grep on the file). R2 is therefore a confirmation pass that I5 converts to a permanent regression test rather than a destructive edit.
- **`.claude/agents/*.md` files contain phase **names** (because they ARE phase agents) but NOT phase **pre-creation instructions**.** A naive grep for "analyst" or "architect" returns broad matches; the narrow grep in I5 targets `pipeline-scaffold` and `/create-goal` invocation strings, which are the actual antipatterns. This distinction is load-bearing — the implementor must use the narrow grep set, not the broad one.
- **OQ-1 resolved → deprecate, not delete.** Pipeline-scaffold/SKILL.md is preserved with a top-of-file deprecation banner. Rationale: (a) historical context on Cronos Phase 0 semantics (slug derivation, request.md mirror, pipeline-state.json init) remains useful as migration reference; (b) hard-delete is destructive and reviewable as a separate goal after a deprecation window confirms zero live invocations; (c) deprecation is one focused edit vs delete + cross-reference scrub.
- **OQ-2 resolved → `spec_path` is a required, explicit argument with a documented canonical default.** The skill's Procedure shows `packages/delivery-workflow/delivery.workflow.yaml` as the recommended path and instructs the caller to override only for spaces shipping a custom workflow. Rationale: (a) keeps the sentinel string byte-explicit (no hidden defaults that drift); (b) makes the workflow binding visible to anyone reading the goal brief on the board; (c) a hardcoded default would invite stale paths if the canonical workflow moves.
- **No lifecycle skill changes (OUT of scope per analyst).** `goal-branch-setup`, `goal-task-commit`, `goal-finalize` continue to function unchanged for non-delivery goals. Runner-driven delivery goals' git lifecycle is handled separately (deferred follow-up); SG6 does not modify these skills.

## Open questions

- None. The analyst's two open questions are resolved in `## Assumptions` (OQ-1 → deprecate; OQ-2 → required arg with canonical default shown).

## Next consumer brief

Implementors should read the YAML `iterations[]` array (not this body) for scope and validation. Five iterations across two topological layers; L0 (I1, I2) runs in parallel.

Cross-iteration invariants the YAML does not capture:
1. **Sentinel string is shared between I2 and I4** — it MUST be the exact literal `<!-- delivery-workflow: {spec_path} -->` (with `{spec_path}` shown as a placeholder, not substituted). I4 imports `DELIVERY_WORKFLOW_SENTINEL_PATTERN` from `backend.app.delivery_driver` and uses it as the oracle. If I2's documented format and I4's oracle disagree, both fail.
2. **api_post() helper is shared between I2 and create-goal/SKILL.md** — I2's Python example must lift lines 82-95 of create-goal/SKILL.md verbatim (the urllib + Bearer-token helper). Do not paraphrase. The reviewer will cross-check byte-for-byte.
3. **I1's prune boundaries are line-sensitive** — preserve lines 1-46 (header + API + Field reference + Simple goal heading), 74-123 (simple-goal Procedure including api_post), 218-249 (Verify + Writing good briefs + Git workflow). Remove only lines ~47-72 ("Feature goal" prose section) and ~125-216 ("Procedure -- feature goal" Python block). The "Choosing a goal structure" heading may need re-titling to keep the remaining content coherent.
4. **I5 grep set for R6 is narrow, not broad** — search `.claude/agents/*.md` for the literal strings `pipeline-scaffold` and `/create-goal` (invocation patterns), NOT for `analyst|architect|impl|review|doc` (those are agent names and will produce false positives across every pipeline-* agent file).

No open question blocks implementation. Gate decision: **PROCEED**.
