Spec 6 — Skills regeneration

Fixes #1: agents building pipelines using the stale create-goal skill that hardcodes CC-v1 six-phase tree (analyst → architect → impl → test → review → doc per sub-goal).

Under the runner this shape is obsolete: a delivery goal is ONE goal bound to the sdlc-delivery workflow, and per-agent child tasks are created dynamically by the runner's dispatchAgent.

### Required changes

1. **Strip CC-v1 pipeline section from `.claude/skills/create-goal/SKILL.md`**
   - Remove: the "Feature goal (CC-v1 pipeline structure)" section with its analyst/architect/impl/test/review/doc hardcoding
   - Keep: the API/field reference, the simple goal structure, the git workflow section
   - These remain for ad-hoc/coordination/ops goals

2. **Strip CC-v1 references from `.claude/skills/create-task/SKILL.md`** (if it references pipeline phases)
   - Keep: API/field reference, general task creation

3. **New skill: `.claude/skills/create-delivery-goal/SKILL.md`**
   - Creates one goal with `workflow_binding: sdlc-delivery` (or equivalent field) 
   - Does NOT enumerate phases, agents, gates, or depends_on
   - References delivery.workflow.yaml as the single source of truth for structure
   - Includes note: "The runner's dispatchAgent creates child tasks dynamically; do not pre-create them"
   - Add "use POST /api/tasks; no custom scripts" guidance for agents spawning sub-work

4. **Update v2 agent contracts** — any .md agent files in `.claude/agents/` that reference pipeline phases or suggest spawning phase tasks should be updated to reference the runner and `create-delivery-goal`

### Contract test
After creating a delivery goal with the new skill: exactly 1 goal created, 0 pre-created phase tasks, worker immediately routes to runner (not _topo_children).

### References
- `.claude/skills/create-goal/SKILL.md` — the skill to prune
- `.claude/skills/create-task/SKILL.md` — may need similar pruning
- `delivery.workflow.yaml` — the single source of truth for delivery structure
- `backend/app/worker.py` — the runner dispatch path (SG4 adds this)

