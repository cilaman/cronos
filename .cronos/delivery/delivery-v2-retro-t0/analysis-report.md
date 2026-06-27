---
class: analysis
goal_slug: delivery-v2-retro-t0
feature: F2 — retro node + Tier-0 self-improvement
phase: analyze
status: done
has_ui: false
req_ids: [REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007]
next_consumer: design
---

# Analysis Report — delivery/v2 F2: retro node + Tier-0 auto-apply

## Summary

F2 adds retrospective analysis and Tier-0 self-improvement to the delivery/v1 pipeline. The feature
is backend/CLI-only (`has_ui: false`): it touches four files in `packages/delivery-workflow/` (agents,
skills, workflow YAML, schema) and creates one new skill. No frontend component is touched. All source
material is available: the draft retro agent and skill are complete at
`docs/delivery-pipeline/delivery-v2/`; `auto_improver.py` is production-ready and requires no changes.
Seven requirements cover the full scope. One open question must be resolved before design: the output
class of the `improve` node (see §Open Questions).

---

## Requirements

### REQ-001 — Retro agent targeted to delivery/v1 state semantics

**Statement:** The retro agent artifact (`packages/delivery-workflow/agents/retro.md`) must specify
delivery/v1 run state (`state.json` + `events.jsonl`) as its primary inputs and must NOT reference
CC-v1 artifacts (`pipeline-state.json`, `phases-log.jsonl`, `verify.py`).

**Acceptance criteria:**
1. `retro.md` names `state.json` (WorkflowState: spec, run_id, status, budget, nodes{}) and
   `events.jsonl` (temporal node-transition log) as the authoritative run-ledger inputs.
2. `retro.md` does not mention `pipeline-state.json`, `phases-log.jsonl`, or `verify.py`.
3. `retro.md` instructs the agent to load `packages/delivery-workflow/skills/retro/SKILL.md` for
   its complete method.

**Verifying phase:** review  
**Confidence:** 0.98 — draft at `docs/delivery-pipeline/delivery-v2/agents/retro.md` is 82 lines
and correct; porting to canonical path is the full implementation.

---

### REQ-002 — Five-dimension scoring rubric in the retro skill

**Statement:** The retro skill (`packages/delivery-workflow/skills/retro/SKILL.md`) must define the
five-dimension scoring rubric (planning, error_handling, efficiency, completion, communication), each
producing an integer 1–5, derived from per-node trace fields already structured by `trace_parser`.

**Acceptance criteria:**
1. Skill defines all five dimensions with 1–5 integer scales and clear floor/ceiling anchors.
2. Skill maps trace fields — `exploration_ratio`, `backtrack_count`, `error_recovery_count`,
   `total_tool_calls`, `exit_reason`, `had_crash` — to per-dimension scoring criteria.
3. Retro artifacts carry all five scores in `delivery_status.fields.scores`
   (`planning`, `error_handling`, `efficiency`, `completion`, `communication`, each ∈ {1,2,3,4,5}).

**Verifying phase:** test  
**Confidence:** 0.98 — draft skill at `docs/delivery-pipeline/delivery-v2/skills/retro/SKILL.md`
is 140 lines and self-described as complete; implementation is verbatim copy to canonical path.

---

### REQ-003 — Finding classification via tier/fix_type decision tree

**Statement:** Every finding in a retro artifact must carry `tier ∈ {0,1,2}` and `fix_type` from
the delivery/v1 enum, assigned via the seven-row decision tree in the retro skill, such that tier
and fix_type always agree.

**Acceptance criteria:**
1. `fix_type ∈ {fixture, threshold}` implies `tier=0`; `{gate_check, agent_prompt, skill}` implies
   `tier=1`; `{schema, workflow}` implies `tier=2`. No other combinations are valid.
2. Every finding carries all six required fields: `id` (F\<N\>, unique, stable across runs),
   `severity` ∈ {critical,high,medium,low}, `tier`, `fix_type`, `target` (per-tier form),
   `evidence` (≤500 chars — trace excerpt or artifact snippet, never vague prose),
   `suggested_action` (one-line, act-without-re-reading-repo instruction).
3. The retro skill documents the decision tree (ask in order; first match wins) and the tier
   agreement rule.

**Verifying phase:** review  
**Confidence:** 0.97 — decision tree is fully specified in the draft skill; REQ-003 validates it is
faithfully ported.

---

### REQ-004 — Tier-0 recipe discipline

**Statement:** Tier-0 findings must carry a machine-readable `recipe` field enabling the `improve`
applier to apply the change without human interpretation; tier-1 and tier-2 findings must not carry
a recipe.

**Acceptance criteria:**
1. `fixture` findings: `recipe = {content: "<exact file content>"}` — the file to write verbatim.
2. `threshold` findings: `recipe = {old: <old_value>, new: <new_value>}` — the bounded change.
3. `recipe` is null or absent for all tier-1 (`gate_check`, `agent_prompt`, `skill`) and tier-2
   (`schema`, `workflow`) findings.
4. Findings targeting `agent:retro` or `skill:retro` are explicitly barred from tier-0 (hard rule
   9 in the retro agent).

**Verifying phase:** test  
**Confidence:** 0.97 — recipe structure is explicit in the scout report and draft skill; the
agent's hard rules already encode the retro self-targeting prohibition.

---

### REQ-005 — improve skill wrapping auto_improver.py

**Statement:** A new skill at `packages/delivery-workflow/skills/improve/SKILL.md` must invoke
`auto_improver.py` with the retro artifact's Tier-0 findings, handle all three exit codes
(0=applied, 1=rolled-back, 2=error), and emit a `delivery_status` fence reporting
`tier0_applied`, `tier0_rolled_back`, and `errors`.

**Acceptance criteria:**
1. Skill reads the retro artifact from the runtime-supplied path (read-only; does not edit it).
2. Skill invokes `auto_improver.py` (production-ready at `backend/app/pipeline/auto_improver.py`)
   passing the retro artifact so the applier can extract Tier-0 findings and their `recipe` fields.
3. `delivery_status` carries `tier0_applied: int`, `tier0_rolled_back: int`, `errors: list[str]`.
4. On exit code 0: report applied count and list applied targets. On exit code 1: report rolled-back
   count and surface eval failure detail. On exit code 2: surface error and set status=failed.

**Verifying phase:** test  
**Confidence:** 0.90 — auto_improver.py interface is clear (snapshot/rollback, exit codes); the
precise invocation args for delivery/v1 (vs CC-v1 `--slug`/`--space` flags) must be confirmed
against the actual auto_improver.py CLI signature during design.

---

### REQ-006 — retro/g-retro/improve nodes wired in delivery.workflow.yaml

**Statement:** Three new nodes (retro, g-retro, improve) and their edges must be appended to
`packages/delivery-workflow/delivery.workflow.yaml` after the existing `release` node.

**Acceptance criteria:**
1. `retro` node: `kind: agent`, `produces: {class: retro}`, `model: reasoning`, no recon; edge
   from `release` with `when: "release.fields.signed_off == true"`.
2. `g-retro` node: `kind: gate`, `checks: [{type: schema}]`; edge to `improve` with
   `when: "g-retro.decision == 'proceed'"`.
3. `improve` node: `kind: agent`, `model: build`, `inputs: {from: [g-retro, retro]}`; terminal
   (no outgoing edge). `produces` class: see Open Questions.
4. Edges defined: `release→retro`, `retro→g-retro`, `g-retro→improve`.
5. YAML is valid (passes schema gate) and the new nodes do not disturb existing nodes or edges.

**Verifying phase:** review  
**Confidence:** 0.92 — node kinds, edges, and conditions are specified in the scout; open question
on `improve` output class is the only unresolved detail (see §Open Questions for the recommendation).

---

### REQ-007 — retro class added to delivery workflow schema

**Statement:** The `retro` class must be registered in `packages/delivery-workflow/schemas/delivery.workflow.schema.yaml` so the schema gate (`g-retro`) accepts node artifacts declaring `produces: {class: retro}`.

**Acceptance criteria:**
1. `delivery.workflow.schema.yaml` accepts `retro` as a valid value wherever node `produces.class`
   is validated.
2. A node declaring `produces: {class: retro}` passes schema validation with no errors.
3. The schema gate (`g-retro`) does not reject a well-formed retro artifact on class grounds alone.

**Verifying phase:** test  
**Confidence:** 0.95 — the schema extension is mechanical; the `class` field already exists in the
schema, only the allowed value set needs updating.

---

## has_ui

**`has_ui: false`**

All changes are confined to `packages/delivery-workflow/` (agents, skills, YAML files). No React
component, page, route, or API endpoint consumed only by the frontend is introduced or modified.
The `frontend-designer` node is not triggered.

---

## Scope

Files that will be created or modified:

| File | Action |
|------|--------|
| `packages/delivery-workflow/agents/retro.md` | Create (port from `docs/delivery-pipeline/delivery-v2/agents/retro.md`) |
| `packages/delivery-workflow/skills/retro/SKILL.md` | Create (copy verbatim from `docs/delivery-pipeline/delivery-v2/skills/retro/SKILL.md`) |
| `packages/delivery-workflow/skills/improve/SKILL.md` | Create (new; wraps auto_improver.py) |
| `packages/delivery-workflow/delivery.workflow.yaml` | Modify (append retro/g-retro/improve nodes + edges) |
| `packages/delivery-workflow/schemas/delivery.workflow.schema.yaml` | Modify (add `retro` to class enum) |

Files NOT in scope:
- `backend/app/pipeline/auto_improver.py` — production-ready; no changes
- `.claude/agents/pipeline-retro.md` — CC-v1 artifact; not touched
- `.claude/skills/evaluate-run/SKILL.md` — CC-v1 artifact; not touched
- Any existing node in `delivery.workflow.yaml`

---

## Traceability table

| REQ | Acceptance criteria | Verifying phase |
|-----|---------------------|-----------------|
| REQ-001 | retro.md inputs = state.json + events.jsonl; no CC-v1 refs; loads retro skill | review |
| REQ-002 | 5 dimensions defined; trace fields mapped; scores in delivery_status | test |
| REQ-003 | tier/fix_type agreement; 6 finding fields; decision tree in skill | review |
| REQ-004 | recipe for tier-0; absent for tier-1+; retro/skill:retro barred from tier-0 | test |
| REQ-005 | improve skill reads retro; invokes auto_improver.py; 3 exit codes; delivery_status | test |
| REQ-006 | 3 new nodes with correct kinds/models/inputs; 3 new edges with when conditions | review |
| REQ-007 | retro class in schema; schema gate accepts retro artifact | test |

---

## Assumptions

- `auto_improver.py` is production-ready and its snapshot/rollback mechanism is trusted; no changes.
- The draft retro skill (`docs/delivery-pipeline/delivery-v2/skills/retro/SKILL.md`) is complete and
  accurate; the implementation copies it verbatim to the canonical path.
- The `delivery.workflow.yaml` `release` node will eventually emit `fields.signed_off == true`;
  this edge condition is specced in the scout and accepted as correct.
- `state.json` is the authoritative ledger; `events.jsonl` gives temporal order.
- The retro node runs once per pipeline run; no loop is needed (retro is a terminal analytical pass).

---

## Open questions

**OQ-1 (blocking for REQ-006): improve node output class**

The `improve` node applies Tier-0 recipes and is terminal. What should it declare as `produces.class`?

Options:
- `improvement` (new class — requires adding to schema + new schema file)
- No `produces` (terminal applier, treated as a gate analogue — simpler; no schema addition needed)

**Recommendation (to be confirmed by architect):** Omit `produces` on the `improve` node. The improve
node is not a document producer — its output is the set of mutated fixture/threshold files in
`packages/delivery-workflow/`, which are tracked by git, not by the workflow ledger. This avoids a
new schema, keeps the schema gate unnecessary after `improve`, and is consistent with how a gate node
works (gates are terminal in practice). The `delivery_status` fence from the improve node can still
carry `tier0_applied` + `tier0_rolled_back` for the runner's ledger without a `produces` declaration.

If the architect disagrees and a schema is needed, REQ-007 naturally extends to cover the
`improvement` class in addition to `retro`.

**OQ-2 (non-blocking): auto_improver.py invocation interface for delivery/v1**

The scout identifies `python -m backend.app.pipeline.auto_improver --slug {slug} --space {space}` as
the likely invocation. The design phase must verify the actual CLI args against
`backend/app/pipeline/auto_improver.py` and confirm whether delivery/v1 retro artifacts are already
in the expected format (findings[] with recipe fields) or require a translation layer.

---

## Confidence

**0.95** — High confidence in scope, requirements, and interfaces. REQ-001–004 are fully specified
from complete draft artifacts. REQ-005–007 are well-bounded; the only true blocker is OQ-1 (improve
output class), which can be resolved in design without requiring analysis rework.
