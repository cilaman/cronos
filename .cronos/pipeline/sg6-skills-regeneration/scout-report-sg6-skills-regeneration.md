---
cc_version: "1.0"
agent: pipeline-scout
slug: sg6-skills-regeneration
phase: scout
status: done
confidence: 0.92
inputs_used:
  - memory:project_pipeline_cronos_mapping
  - memory:project_delivery_v1_cronos_adapter_design
  - memory:project_pipeline_scaffold_skill
  - .claude/skills/create-goal/SKILL.md
  - .claude/skills/create-task/SKILL.md
  - backend/app/delivery_driver.py
  - backend/app/run_executor.py
  - backend/app/worker.py
  - backend/app/models.py
  - .claude/skills/pipeline-gate/SKILL.md
  - packages/delivery-workflow/delivery.workflow.yaml
outputs_produced:
  - .cronos/pipeline/sg6-skills-regeneration/scout-report-sg6-skills-regeneration.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/ (delivery_driver.py, run_executor.py, worker.py, models.py)
    - .claude/skills/ (create-goal, create-task, pipeline-gate)
    - packages/delivery-workflow/ (workflow YAML structure)
  excluded:
    - frontend/: UI presentation not relevant to skill logic
    - delivery-notes space: external reference; focus on cronos-native
    - harness executor: orthogonal to CC-v1 pipeline skills (different problem domain)
  strategies:
    - memory_retrieval
    - glob_structural
    - read_targeted
brief: "Perform memory-first reconnaissance of the Cronos codebase to identify: (1) CC-v1 pipeline structure hardcoded in create-goal/create-task skills; (2) delivery workflow binding mechanism; (3) runner dispatch in worker.py; (4) risk surface of migrating to create-delivery-goal skill that delegates workflow structure to the runner."
metrics:
  tool_calls: 12
  files_read: 8
  memory_hits: 3
---

## Summary

SG6 skills regeneration targets three stale skills (`create-goal`, `create-task`, `pipeline-scaffold`) that hardcode CC-v1 pipeline structure (scout/analyst/architect/impl/test/review/doc tasks with fixed deps) instead of delegating workflow orchestration to the delivery-workflow runner. The runner is already in place: it detects a `<!-- delivery-workflow: {spec_path} -->` sentinel in the goal brief, reads the workflow spec (YAML), and spawns agents according to the spec rather than hardcoded task DAG. SG6 must create a new `create-delivery-goal` skill that emits this sentinel and references an external workflow spec, leaving `create-goal` and `create-task` for simpler non-pipeline goals. Key risks: four existing agents and lifecycle skills reference the old hardcoded pattern; migration requires careful deprecation and path coexistence during transition.

## Coverage

### Searched
- `.claude/skills/create-goal/SKILL.md` — feature goal hardcoding (lines 49–72 document the six-phase pattern)
- `.claude/skills/create-task/SKILL.md` — leaf task creation
- `.claude/skills/pipeline-gate/SKILL.md` — per-phase gate verification
- `backend/app/delivery_driver.py` — runner dispatch sentinel detection (lines 37–61)
- `backend/app/run_executor.py` — pre-dispatch routing to runner vs topo children (lines 944–964)
- `backend/app/models.py` — Task model fields (no workflow field present yet)
- `packages/delivery-workflow/delivery.workflow.yaml` — workflow spec structure

### Excluded
- frontend/: UI presentation not relevant to skill logic
- delivery-notes space: external reference; focus on cronos-native
- harness executor: orthogonal to CC-v1 pipeline skills (different problem domain)

### Strategies
- memory_retrieval: 3 entries found + consumed (pipeline mapping, v1 adapter design, scaffold skill)
- glob_structural: targeted paths for skills + backend dispatchers
- read_targeted: full reads of skill files; partial reads of executor/driver

## Findings

### 1. Current create-goal skill hardcoding (antipattern)

**File:** `.claude/skills/create-goal/SKILL.md`, lines 49–72

The skill documents the **CC-v1 pipeline structure** as the canonical feature goal pattern:
- One shared `scout` task at the goal level (haiku), runs first
- Six sub-goals, each with a sequential 6-phase pipeline:
  - analyst (sonnet) → architect (opus) → impl (sonnet) → test (sonnet) → review (opus) → doc (haiku)
- Cross-sub-goal ordering enforced via sibling `depends_on` (line 71: "set `depends_on` on **Sub-Goal B itself**")
- Each phase task brief must reference scout report, agent contract file, artifact path, and end with `/pipeline-gate`

**Example code (lines 155–215):** Python snippet that directly POSTs:
- one goal
- one shared scout task
- N sub-goals, each with 6 phase tasks plus hardcoded `depends_on` DAG

**Risk:** This pattern locks workflow structure at **goal creation time**, embedding 42+ lines of boilerplate into the skill and requiring agents to re-implement identical briefs.

### 2. Runner dispatcher already in place

**File:** `backend/app/delivery_driver.py`, lines 38–61

Detects sentinel:
```python
DELIVERY_WORKFLOW_SENTINEL_PATTERN = re.compile(
    r"^<!--\s*delivery-workflow:\s*([^\s>]+)\s*-->$",
    re.MULTILINE,
)

def detect_delivery_workflow_spec(brief: str) -> str | None:
    """Return the spec_path from the delivery-workflow sentinel in *brief*."""
    m = DELIVERY_WORKFLOW_SENTINEL_PATTERN.search(brief)
    if m:
        return m.group(1).strip()
    return None
```

Format: `<!-- delivery-workflow: {spec_path} -->` on its own line in goal brief.

**File:** `backend/app/run_executor.py`, lines 944–964

Pre-dispatch routing:
```python
# Delivery-workflow pre-dispatch: detect sentinel and delegate.
_spec_path = detect_delivery_workflow_spec(goal.brief or "")
if _spec_path is not None:
    log.info("run_goal: sentinel detected in goal %s — delegating to delivery_driver", goal_id)
    # ... resolve paths, call run_delivery_goal(goal_id, spec_path, ...)
    return
# ---------------------------------------------------------------
# Fall through: execute as native Cronos goal (topo sort children).
ordered_child_ids = _topo_children_local(goal_id, self.store)
```

**Implication:** If goal brief contains sentinel, dispatcher **skips topo-sort children logic entirely** and delegates to `run_delivery_goal()` which reads the workflow spec YAML and orchestrates via the runner.

### 3. Workflow spec structure

**File:** `packages/delivery-workflow/delivery.workflow.yaml`, lines 1–80+ (sample)

YAML structure:
```yaml
apiVersion: delivery/v1
metadata:
  name: sdlc-delivery
defaults:
  models:
    reasoning: opus
    build: sonnet
    recon: haiku
nodes:
  - id: scout
    kind: agent
    agent: scout
    model: {use: recon}
    produces: {class: research}
  - id: g-scout
    kind: gate
    checks: [{type: schema}]
  - id: analyze
    kind: agent
    agent: analyst
    model: {use: build}
    inputs: {from: [scout]}
    produces: {class: analysis}
  # ... more nodes
edges:
  - from: scout
    to: g-scout
  - from: g-scout
    to: analyze
  # ...
```

**Key observations:**
- Nodes are typed (agent, gate, human, aggregator, etc.)
- Agent nodes specify the agent name (`agent: scout`), model source (`{use: recon}`), and produce type (`{class: research}`)
- Inputs/outputs declarative (line 30: `inputs: {from: [scout]}`)
- Gate nodes list checks (schema, traceability, acceptance)
- Workflow is data-driven, not hardcoded in Python

### 4. Task model (no workflow field yet)

**File:** `backend/app/models.py`, lines 46–76

The `Task` model has:
- `id, space_id, title, state, created_at, updated_at`
- `brief, history, pending_messages`
- `agent_mode, agent_model, priority, manual_order, type, parent_id, depends_on`
- Feature/fix fields (`feature_state, feature_key, realizes, issue_number, issue_url, proposed_issue_path`)
- NO `workflow_binding`, `workflow_ref`, or `workflow_spec` field

**Implication:** Currently the workflow spec path is embedded in the goal **brief** (as sentinel), not stored as a separate field. This is intentional: keeps the model simple, treats workflow binding as a metadata annotation rather than a structured property. The dispatcher parses it from brief text at runtime.

### 5. Three skills need evolution

**Current situation:**

1. **create-goal** (lines 1–250): Hardcodes six-phase pattern + Python boilerplate to create all 7 phase tasks + sibling deps
2. **create-task** (lines 1–90): Simple leaf task creation; referenced from create-goal example code
3. **pipeline-scaffold** (task 3.3, per memory): Creates goal + 7 phase tasks + pipeline-state.json + phases-log.jsonl; identical pattern to create-goal but also initializes state files

All three use **identical hardcoded logic**: determine slug, create goal, create scout task, loop 6 phases × N sub-goals creating tasks with phase-specific agent models and briefs.

**Migration path:**

- **create-delivery-goal** (NEW): Accept workflow spec path + space/title/brief, inject sentinel into brief, POST goal (without child tasks), hand orchestration to runner
- **create-goal** (DEPRECATED but kept): Keep for non-pipeline goals (simple coordination, ops checklists)
- **create-task** (unchanged): Leaf task creation; no removal needed
- **pipeline-scaffold** (likely retired): Functionality absorbed into create-delivery-goal or pipeline initialization task

### 6. Usage in v2 agents

**Search result:** No direct references to "create-goal skill" or "create-task skill" found in `.claude/agents/` files.

This means:
- Agents do NOT call these skills from their briefs
- Skills are invoked via manual `/create-goal` or via human-orchestrated task creation
- **No agent-to-skill breaking dependency** — regeneration will not break agent contract

However, **lifecycle skill impact:**
- `goal-branch-setup`, `goal-task-commit`, `goal-finalize` rely on task DAG structure (child tasks, `depends_on`, phase ordering)
- If `create-delivery-goal` delegates orchestration to runner, child tasks are **created by the runner dynamically**, not by the skill
- These lifecycle skills may need per-goal-type routing (classic DAG vs delivery-workflow)

### 7. Risk surface

**High-risk migration targets:**

1. **Lifecycle skills** (goal-branch-setup, goal-task-commit, goal-finalize):
   - Assume tasks exist in predictable DAG shape
   - Runner creates tasks asynchronously; timing and ordering differ
   - **Mitigation:** Detect workflow sentinel in goal brief; adapt behavior accordingly (e.g., branch setup waits for runner to enqueue first child, or disables git branch lifecycle for runner goals)

2. **Existing pipeline goals** (delivery-v1/v2 related tasks, Arc 6/7/8 phases):
   - Currently created via create-goal or manual task creation
   - Migrating to sentinel + workflow spec requires:
     - Re-creating goal with sentinel injected
     - Copying workflow spec to space root
     - Deleting old child tasks (or skipping them if runner skips pre-existing DONE children)
   - **Mitigation:** Coexistence: keep create-goal working; new goals use create-delivery-goal; old goals continue on topo-sort path

3. **pipeline-scaffold skill** (task 3.3, memory notes):
   - Used in Cronos Phase 0 to init 7-task pipeline
   - If deprecating in favor of create-delivery-goal, must ensure no active goals depend on it
   - **Mitigation:** Mark as deprecated; move logic to create-delivery-goal or a new pipeline-init-goal skill

4. **Agent model wiring** (agent.py, line ~200):
   - Worker stores `current_task_id` when invoking subagents
   - Runner dispatch may create child tasks that this logic does not anticipate
   - **Mitigation:** Verify runner child task creation does not collide with worker state tracking

### 8. Deployment approach: before/after example

**Before (hardcoded):**

```python
# User calls skill
api_post({
    "space_id": "cronos-development",
    "type": "goal",
    "title": "Feature: Data Model",
    "brief": "Add feature_state and related fields…"
    # Skill then creates 1 goal + 1 scout + 2 sub-goals × 6 phases = 13 tasks
    # Each task hardcodes brief with agent contract file, artifact path, phase-specific model
})
```

**After (runner-driven):**

```python
# User calls new skill
api_post({
    "space_id": "cronos-development",
    "type": "goal",
    "title": "Feature: Data Model",
    "brief": """Add feature_state and related fields…

<!-- delivery-workflow: .cronos/workflows/feature-data-model.workflow.yaml -->"""
    # Skill posts ONLY the goal (no child tasks)
    # run_executor detects sentinel, loads workflow spec, runner spawns tasks as it progresses
})
```

Workflow spec (`.cronos/workflows/feature-data-model.workflow.yaml`):
```yaml
apiVersion: delivery/v1
nodes:
  - id: scout
    kind: agent
    agent: scout
    model: {use: recon}
    produces: {class: research}
  - id: g-scout
    kind: gate
    checks: [{type: schema}]
  - id: analyze
    kind: agent
    agent: analyst
    model: {use: build}
    inputs: {from: [scout]}
    produces: {class: analysis}
  # ... 6 phases ...
edges:
  - from: scout
    to: g-scout
  - from: g-scout
    to: analyze
  # ... phase chain ...
```

### 9. Memory alignment

Three memory entries validated against current code:

1. **project_pipeline_cronos_mapping** (2026-05-30): "pipeline phases → child tasks in a goal DAG; worker runs them in topological order via depends_on." ✓ Confirmed in run_executor.py:967 `_topo_children_local(goal_id, self.store)`.

2. **project_delivery_v1_cronos_adapter_design** (2026-06-25): "delivery/v1 pipeline runs at SPACE ROOT…"; delivery-driver dispatches on sentinel detection. ✓ Confirmed in delivery_driver.py:38–61 and run_executor.py:944–964.

3. **project_pipeline_scaffold_skill** (2026-05-30): "pipeline-scaffold creates 1 goal + 7 phase tasks…"; memory notes skill replaced by create-delivery-goal approach. ✓ Confirmed create-goal lines 155–215 use same pattern.

All memory inputs remain accurate; code has not regressed since SG5.

## Assumptions

- **Sentinel format frozen**: `<!-- delivery-workflow: {spec_path} -->` is byte-identical across delivery_driver.py (line 38), run_executor.py (line 946), and all tests. No planned changes per SG4 design-report. **Justification:** SG4 (executor+runner) is completed and merged; sentinel format is part of the hand-off contract.

- **Workflow spec always at space root**: runner resolves spec_path relative to `space_dir` (delivery_driver.py:line 73, parameter list). `spec_path` is user-supplied in sentinel. **Justification:** delivery.workflow.yaml lives in space root (packages/delivery-workflow/); migration will mirror this structure for each space.

- **No Task model field addition required**: workflow binding remains brief-resident (sentinel), not a structured field. **Justification:** Simpler schema, no DB migration, brief is already mutable. If future phases require workflow field, it can be added without breaking create-delivery-goal.

- **Lifecycle skills adapt, not replace**: goal-branch-setup, goal-task-commit, goal-finalize continue to exist; they detect workflow sentinel and adjust behavior (wait for runner child tasks, or skip git lifecycle for runner goals). **Justification:** SG4 dispatch was intentionally non-invasive; lifecycle skills are orthogonal (git workflow, not task orchestration).

## Open questions

- **What should create-delivery-goal specify about workflow templates?** Should it accept a `--template` flag (e.g., `--template=cc-v1-sdlc`) to inject a default workflow spec path, or should users always provide an explicit `--spec-path`? Affects UX/documentation.

- **How to migrate existing pipeline goals?** If a goal was created with create-goal (hardcoded tasks), can it be retrofit to use a sentinel + workflow spec, or must it be re-created? Backward-compat strategy TBD.

- **pipeline-scaffold retirement timeline?** Should it be deprecated immediately (docs + mark as legacy), or kept as an alternative in parallel until all goals are migrated?

- **Lifecycle skill version bump?** If goal-branch-setup/goal-task-commit/goal-finalize are modified to detect/handle runner goals, should their version be incremented in `.claude/skills/` metadata, or treated as internal refactor?

## Next consumer brief

**Analysis phase should determine:**

1. Whether lifecycle skills (goal-branch-setup, goal-task-commit, goal-finalize) require modification for workflow-bound goals, or if runner handles child task lifecycle orthogonally to git operations.

2. Template/spec-path UX: should create-delivery-goal include preset templates (cc-v1-sdlc, cc-v1-custom) or require explicit spec path?

3. Backward-compat path: keep create-goal for non-pipeline goals only? Deprecation message in docs?

4. Risk mitigation strategy for existing pipeline goals (4+ active goals using hardcoded 7-task pattern): can they continue, or must they be migrated?

5. Whether pipeline-scaffold should be retired or refactored into create-delivery-goal + helper.

**Key decision point:** Can create-delivery-goal + runner handle **all** existing pipeline goals (arc-6, delivery-v1/v2, SG1–SG6), or does SG6 need phase-2 migration work on legacy goals?
