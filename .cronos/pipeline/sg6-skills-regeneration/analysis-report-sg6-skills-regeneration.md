---
cc_version: '1.0'
agent: pipeline-analyst
slug: sg6-skills-regeneration
phase: analysis
status: done
confidence: 0.9
inputs_used:
- memory:project_pipeline_cronos_mapping
- memory:project_pipeline_scaffold_skill
- memory:project_delivery_v1_cronos_adapter_design
- .cronos/pipeline/sg6-skills-regeneration/scout-report-sg6-skills-regeneration.md
- .claude/skills/create-goal/SKILL.md
- .claude/skills/create-task/SKILL.md
- .claude/skills/pipeline-scaffold/SKILL.md
- backend/app/delivery_driver.py
- backend/app/run_executor.py
outputs_produced:
- .cronos/pipeline/sg6-skills-regeneration/analysis-report-sg6-skills-regeneration.md
blockers: []
next_consumer: design
request: "Spec 6 — Skills regeneration\n\nFixes #1: agents building pipelines using\
  \ the stale create-goal skill that hardcodes CC-v1 six-phase tree (analyst → architect\
  \ → impl → test → review → doc per sub-goal).\n\nUnder the runner this shape is\
  \ obsolete: a delivery goal is ONE goal bound to the sdlc-delivery workflow, and\
  \ per-agent child tasks are created dynamically by the runner’s dispatchAgent.\n\
  \n### Required changes\n\n1. **Strip CC-v1 pipeline section from `.claude/skills/create-goal/SKILL.md`**\n\
  \   - Remove: the \"Feature goal (CC-v1 pipeline structure)\" section with its analyst/architect/impl/test/review/doc\
  \ hardcoding\n   - Keep: the API/field reference, the simple goal structure, the\
  \ git workflow section\n   - These remain for ad-hoc/coordination/ops goals\n\n\
  2. **Strip CC-v1 references from `.claude/skills/create-task/SKILL.md`** (if it\
  \ references pipeline phases)\n   - Keep: API/field reference, general task creation\n\
  \n3. **New skill: `.claude/skills/create-delivery-goal/SKILL.md`**\n   - Creates\
  \ one goal with `workflow_binding: sdlc-delivery` (or equivalent field)\n   - Does\
  \ NOT enumerate phases, agents, gates, or depends_on\n   - References delivery.workflow.yaml\
  \ as the single source of truth for structure\n   - Includes note: \"The runner's\
  \ dispatchAgent creates child tasks dynamically; do not pre-create them\"\n   -\
  \ Add \"use POST /api/tasks; no custom scripts\" guidance for agents spawning sub-work\n\
  \n4. **Update v2 agent contracts** -- any .md agent files in `.claude/agents/` that\
  \ reference pipeline phases or suggest spawning phase tasks should be updated to\
  \ reference the runner and `create-delivery-goal`\n\n### Contract test\nAfter creating\
  \ a delivery goal with the new skill: exactly 1 goal created, 0 pre-created phase\
  \ tasks, worker immediately routes to runner (not _topo_children).\n\n### References\n\
  - `.claude/skills/create-goal/SKILL.md` -- the skill to prune\n- `.claude/skills/create-task/SKILL.md`\
  \ -- may need similar pruning\n- `delivery.workflow.yaml` -- the single source of\
  \ truth for delivery structure\n- `backend/app/worker.py` -- the runner dispatch\
  \ path (SG4 adds this)"
has_ui: false
coverage_summary:
  searched:
  - .claude/skills/create-goal/
  - .claude/skills/create-task/
  - .claude/skills/pipeline-scaffold/
  - .claude/agents/
  - backend/app/delivery_driver.py
  - backend/app/run_executor.py
  excluded:
  - frontend/: no UI changes in this feature
  - backend/app/harnesses/: orthogonal to skill file regeneration
  - packages/delivery-workflow/: structure confirmed by scout; no changes required
      here
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_keyword
  - traceability_mapping
traceability:
- requirement_id: R1
  statement: The CC-v1 six-phase pipeline section (lines 49-215 in create-goal/SKILL.md)
    is removed from .claude/skills/create-goal/SKILL.md, leaving the API reference,
    simple goal structure, git workflow, and verify sections intact.
  acceptance_criteria:
  - Given the updated SKILL.md, when searched for 'Feature goal (CC-v1 pipeline structure)'
    or analyst/architect/impl/test/review/doc phase enumerations, the pattern is absent.
  - The API field reference table, simple goal structure example, Writing good briefs,
    and Git workflow for development goals sections remain present and unmodified.
  - The 'Procedure -- feature goal (CC-v1 pipeline structure)' Python code block is
    absent from the file.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: .claude/skills/create-task/SKILL.md contains no references to CC-v1 pipeline
    phases, phase task models, or per-phase agent names.
  acceptance_criteria:
  - Given the current create-task/SKILL.md, when searched for 'pipeline', 'CC-v1',
    'analyst', 'architect', 'impl phase', 'review phase', or 'doc phase', no matches
    are found.
  - If no such references exist in the current file, R2 is satisfied by confirmation
    with no edit required.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R3
  statement: A new skill file .claude/skills/create-delivery-goal/SKILL.md exists
    that guides creation of a single delivery goal by injecting the delivery-workflow
    sentinel into the goal brief, without pre-creating any child tasks.
  acceptance_criteria:
  - 'The file exists at .claude/skills/create-delivery-goal/SKILL.md with valid YAML
    frontmatter containing name: create-delivery-goal and a description.'
  - 'The skill instructs the caller to POST exactly one task of type: goal to the
    API, with the delivery-workflow sentinel on its own line in the brief.'
  - The skill explicitly states that the caller must NOT pre-create scout, analyst,
    architect, impl, test, review, or doc child tasks -- the runner's dispatchAgent
    creates child tasks dynamically from the workflow spec.
  - The skill references delivery.workflow.yaml or the space-relative path to the
    workflow spec as the single source of truth for workflow structure.
  - 'The skill documents the sentinel format: <!-- delivery-workflow: {spec_path}
    --> on its own line, where spec_path is relative to the space root.'
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: The create-delivery-goal skill includes an API usage example that posts
    a single goal (no phase task loop, no depends_on pre-wiring).
  acceptance_criteria:
  - The SKILL.md contains a Procedure or API section with a Python example that posts
    a single goal and no sub-tasks.
  - 'The example code includes the delivery-workflow sentinel in the brief field and
    sets type: goal.'
  - No loop over phases (analyst/architect/impl/test/review/doc) appears in the example
    code.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R5
  statement: .claude/skills/pipeline-scaffold/SKILL.md is marked deprecated or retired,
    with a replacement pointer to create-delivery-goal.
  acceptance_criteria:
  - The file's frontmatter or opening paragraph includes a deprecation notice directing
    users to /create-delivery-goal.
  - The deprecation notice explains that pre-creating 7 phase tasks is superseded
    by the runner-driven approach.
  - 'Alternatively: the file is removed entirely and create-delivery-goal/SKILL.md
    documents the migration path.'
  verifying_phase: review
  confidence: 0.85
- requirement_id: R6
  statement: No file in .claude/agents/ directly instructs spawning CC-v1 phase tasks
    as a pre-creation step when setting up a delivery goal.
  acceptance_criteria:
  - When all .claude/agents/*.md files are searched for pipeline-scaffold, create-goal
    as a skill invocation, or analyst/architect/impl/test/review/doc task pre-creation
    patterns in delivery goal context, no matches are found.
  - If any agent file contains such references, they are removed or redirected to
    create-delivery-goal.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R7
  statement: 'After using create-delivery-goal, the Cronos worker routes the goal
    to the delivery runner: exactly 1 goal exists, 0 pre-created phase child tasks,
    and run_executor.py detects the sentinel and calls run_delivery_goal().'
  acceptance_criteria:
  - Given a goal brief containing the delivery-workflow sentinel, detect_delivery_workflow_spec()
    returns a non-None spec path.
  - The _topo_children_local() branch is NOT entered; execution delegates to run_delivery_goal().
  - The Cronos board shows 1 goal and 0 pre-created child tasks immediately after
    goal creation.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R8
  statement: 'The create-delivery-goal skill documents the coexistence contract: create-goal
    and lifecycle skills continue to function unchanged for non-delivery goals.'
  acceptance_criteria:
  - The new SKILL.md includes a When to use section distinguishing delivery goals
    (use create-delivery-goal) from coordination/ops goals (use create-goal).
  - The SKILL.md does not modify or replace the lifecycle skills and explicitly notes
    they apply to non-delivery goals.
  verifying_phase: review
  confidence: 0.88
metrics:
  tool_calls: 10
  files_read: 6
  memory_hits: 3
---

## Summary

SG6 retires the stale CC-v1 six-phase task-pre-creation pattern from `create-goal` and `pipeline-scaffold`, introduces a new `create-delivery-goal` skill that injects a delivery-workflow sentinel into the goal brief (triggering the runner), and confirms that no `.claude/agents/` files require changes. The runner dispatch is already in place: `run_executor.py` detects `<!-- delivery-workflow: {spec_path} -->` and calls `run_delivery_goal()` before entering `_topo_children_local`. All changes are to `.claude/skills/` documentation files only; no backend code modifications are required.

## Scope

### In scope
- Remove the "Feature goal (CC-v1 pipeline structure)" section and its Python boilerplate (lines 49-215) from `.claude/skills/create-goal/SKILL.md`
- Confirm `.claude/skills/create-task/SKILL.md` has no CC-v1 phase references (currently clean per direct read)
- Create `.claude/skills/create-delivery-goal/SKILL.md` with sentinel-injection procedure, runner handoff explanation, and coexistence note
- Deprecate or retire `.claude/skills/pipeline-scaffold/SKILL.md`
- Confirm no `.claude/agents/` files reference phase pre-creation for delivery goals (currently clean per grep)

### Out of scope
- Changes to `backend/app/run_executor.py` or `delivery_driver.py` -- runner dispatch is complete (SG4)
- Changes to lifecycle skills (`goal-branch-setup`, `goal-task-commit`, `goal-finalize`) -- they remain for non-delivery goals
- Changes to `packages/delivery-workflow/delivery.workflow.yaml` -- reference spec, not modified here
- DB schema changes -- workflow binding lives in the brief as a sentinel, no `workflow_binding` field needed
- Frontend changes -- no UI is involved

### Deferred
- Per-goal-type routing within lifecycle skills (detect sentinel, adapt git lifecycle for runner-driven goals)
- Template/preset mechanism for `create-delivery-goal` (e.g. --template=cc-v1-sdlc)
- Migration guidance for existing pipeline goals created with the old hardcoded pattern

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Remove CC-v1 six-phase pipeline section from `create-goal/SKILL.md` |
| R2 | Confirm `create-task/SKILL.md` has no CC-v1 phase references (currently clean) |
| R3 | Create `create-delivery-goal/SKILL.md` with sentinel-injection procedure |
| R4 | Include single-goal API example (no phase pre-creation) in new skill |
| R5 | Deprecate or retire `pipeline-scaffold/SKILL.md` |
| R6 | Confirm `.claude/agents/*.md` files contain no phase pre-creation instructions |
| R7 | Contract test: 1 goal created, 0 child tasks, worker routes to runner |
| R8 | Document coexistence: `create-goal` and lifecycle skills unchanged for non-delivery goals |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]`
array (the machine-readable source of truth). The body summary below mirrors them
in compact form for the human reader.

- R1 -- `create-goal/SKILL.md` has no CC-v1 phase section; API table, simple goal, git workflow sections remain intact
- R2 -- `create-task/SKILL.md` has no pipeline phase references (confirm; no edit if already clean)
- R3 -- `create-delivery-goal/SKILL.md` exists with sentinel format documented, runner handoff note, no phase pre-creation
- R4 -- SKILL.md Python example posts 1 goal with sentinel in brief; no phase task loop present
- R5 -- `pipeline-scaffold/SKILL.md` carries deprecation notice pointing to `create-delivery-goal`
- R6 -- All `.claude/agents/*.md` files are clean of phase pre-creation instructions for delivery goals
- R7 -- Worker routes to `run_delivery_goal()`, not `_topo_children_local()`, for sentinel-bearing goals; 0 pre-created tasks visible on board
- R8 -- `create-delivery-goal` documents non-delivery goal boundary; lifecycle skills not modified

## Traceability

The full requirement -> acceptance criteria -> verifying_phase map is the YAML
`traceability[]` array. Downstream agents read the YAML directly; this section
exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Remove CC-v1 six-phase pipeline section from `create-goal/SKILL.md` |
| R2 | test | Confirm `create-task/SKILL.md` has no CC-v1 phase references |
| R3 | test | Create `create-delivery-goal/SKILL.md` with sentinel-injection procedure |
| R4 | test | Include single-goal API example (no phase pre-creation) in new skill |
| R5 | review | Deprecate or retire `pipeline-scaffold/SKILL.md` |
| R6 | test | Confirm `.claude/agents/*.md` files contain no phase pre-creation instructions |
| R7 | test | Contract test: 1 goal, 0 child tasks, worker routes to runner |
| R8 | review | Document coexistence contract in `create-delivery-goal/SKILL.md` |

## Assumptions

- `create-task/SKILL.md` is already clean: the current file (90 lines) is pure leaf-task creation with no CC-v1 phase references. R2 is a confirmation, not an edit task. Rationale: direct read confirmed absence of any pipeline, phase, or CC-v1 terms.
- No `.claude/agents/*.md` files require edits: grep across all 10 agent files found zero references to `create-goal`, `pipeline-scaffold`, or CC-v1 phase enumeration in the context of delivery goal setup. R6 is a confirmation pass.
- Sentinel format is frozen: `<!-- delivery-workflow: {spec_path} -->` is the byte-identical binding between the skill and `delivery_driver.py:DELIVERY_WORKFLOW_SENTINEL_PATTERN`. SG4 is merged; this format is not changed by SG6.
- Lifecycle skills are out of scope for SG6: `goal-branch-setup`, `goal-task-commit`, and `goal-finalize` serve non-delivery goals and the request does not ask for their modification.
- `pipeline-scaffold` deprecation (not deletion) is preferred: in-place deprecation notice preserves historical reference while redirecting new usage. The design agent may choose deletion if no active goals depend on it.
- has_ui=false rationale: all changes are to `.claude/skills/*.md` documentation files only; no UI components, API endpoints, or database schema are touched.

## Open questions

- Should `pipeline-scaffold/SKILL.md` be deleted or marked deprecated with a redirect? Either satisfies R5; design agent should decide based on whether in-flight goals still invoke it.
- Should `create-delivery-goal` accept `spec_path` as a parameter or suggest the canonical `packages/delivery-workflow/delivery.workflow.yaml` path as default? The design agent should determine the right UX.

## Next consumer brief

Read `traceability[]` for the full requirement set and `## Scope` for boundaries. Key design decisions:

1. R1 and R5 are the only destructive edits to existing files: removing lines 49-215 from `create-goal/SKILL.md` and adding deprecation to `pipeline-scaffold/SKILL.md`. Plan as two separate iterations to allow targeted review.
2. R3+R4+R8 together constitute the single new file (`create-delivery-goal/SKILL.md`). The sentinel format is `<!-- delivery-workflow: {spec_path} -->` sourced from `delivery_driver.py:DELIVERY_WORKFLOW_SENTINEL_PATTERN`. The Python example must copy the `api_post()` helper from `create-goal/SKILL.md` lines 84-95 (simple goal variant) and add only the sentinel to the brief field.
3. R2 and R6 are confirmation passes with no code changes -- collapse into a single low-cost verification iteration.
4. R7 is a behavioral contract test -- design agent must plan a test-phase task that creates a sentinel-bearing goal via the API and verifies the board shows 0 pre-created child tasks and `detect_delivery_workflow_spec()` returns non-None.
5. No UI sub-track needed (`has_ui=false`). No backend code changes needed. All iterations touch only `.claude/skills/` files.
6. Deferred risk: lifecycle skills may need sentinel-detection logic if delivery-goal git lifecycle differs from classic goals -- this is accepted as out of scope for SG6.
