---
cc_version: "1.0"
agent: pipeline-scout
slug: arc6-executor
phase: scout
status: done
confidence: 0.88
inputs_used:
  - backend/app/harnesses/model.py
  - backend/app/harnesses/store.py
  - backend/app/harnesses/validator.py
  - backend/app/worker.py
  - backend/app/trace_parser.py
  - backend/app/models.py
  - backend/app/storage.py
  - backend/app/agent.py
  - backend/app/api/tools.py
  - backend/app/api/harnesses.py
outputs_produced:
  - .cronos/pipeline/arc6-executor/scout-report-arc6-executor.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/harnesses/
    - backend/app/worker.py (run_agent, _finalize_child, _run_goal, _topo_children)
    - backend/app/trace_parser.py (RunTrace, extract_run_trace)
    - backend/app/storage.py (task creation, state transitions)
    - backend/app/models.py (Task fields)
    - backend/app/api/tools.py (agent tool resolution)
  excluded:
    - frontend/: not relevant to backend executor implementation
    - tools/ submodule: adoption-specific; agent resolution covered by tools.py
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted

brief: "Research the harness executor implementation needed for arc6-executor. The feature request is to build a stateful DAG interpreter in backend/app/harnesses/executor.py..."

metrics:
  tool_calls: 15
  files_read: 11
  memory_hits: 0
---

## Summary

The arc6-executor implementation requires a new `backend/app/harnesses/executor.py` module that orchestrates harness runs as goal-like hierarchies. The design reuses existing worker infrastructure (run_agent, _finalize_child, _topo_children) to execute Agent nodes as child Tasks, while control-flow nodes (trigger, decision, wait, aggregator) pass through as stubs. Key dependencies include Task creation via TaskStore.create() with brief interpolation, RunTrace.parent_run_id field addition, and run-state persistence under `.cronos/harness-runs/`. The executor must serialize run execution at the worker pool level to avoid contention.

## Coverage

### Searched
- **backend/app/harnesses/** — model.py (NodeType enum, Harness structure), store.py (YAML persistence), validator.py (DAG cycle detection)
- **backend/app/worker.py** — _topo_children (line 75-113: sibling dependency ordering), run_agent (line 293, called for each child), _finalize_child (line 657-739: child task finalization), _run_goal (line 741-956: sequential child orchestration pattern)
- **backend/app/trace_parser.py** — RunTrace model (line 123-152), extract_run_trace (line 159-379: event parsing and memory tracking)
- **backend/app/storage.py** — Task.create() (line 630-676: new task creation with space_id, title, brief, agent fields), state machine (WORKER_TRANSITIONS: ACTIVE→{WAITING,DONE})
- **backend/app/models.py** — Task fields (space_id, title, brief, state, agent_mode, agent_model, parent_id, depends_on, type='goal')
- **backend/app/api/tools.py** — _scan_category (line 140-141: resolves agents from space/.claude/agents and global ~/.claude/agents)

### Excluded
- frontend/: not relevant to harness executor backend design
- tools/adoption.py, tools/discovery.py: adoption-specific; agent resolution already handled by tools.py scanning

### Strategies
- memory_retrieval: checked memory context; no prior arc6 executor notes found
- glob_structural: identified harnesses/, worker.py, trace_parser.py, storage.py as core modules
- grep_symbol: no variable interpolation patterns found in existing codebase (not yet implemented)
- read_targeted: deep-read all relevant files to extract API contracts and patterns

## Findings

### 1. Harness Architecture (model.py, store.py)

**Node types** (NodeType enum, line 24-31):
- `agent`: executable by run_agent
- `trigger`, `decision`, `wait`, `aggregator`: control-flow; stub as pass-through for arc6.3

**Harness model** (line 75-96):
- `nodes: list[HarnessNode]` — id, type, position, ports, data (arbitrary config), label
- `edges: list[HarnessEdge]` — source/target node refs, optional condition guard
- `variables: dict` — root-level variable definitions; used for interpolation into child prompts

**Storage** (store.py, line 122-315):
- Persists to `{space_dir}/.cronos/harnesses/{slug}.yml`
- HarnessStore.get() and HarnessStore.list() for retrieval
- No run-state tracking (new executor module must own that)

### 2. Worker Lifecycle & Reusable Functions

**_topo_children** (worker.py:75-113):
- Returns child task IDs in topological order respecting sibling depends_on links
- Falls back to manual_order on cycle detection
- Signature: `_topo_children(goal_id: str, store: TaskStore) → list[str]`
- **Reuse**: Call this for Agent node ordering within a harness (after filtering non-Agent nodes)

**run_agent** (worker.py:293):
- Signature: `await run_agent(task, user_message=None, on_event=on_event_callable, cancel_event=asyncio.Event, space=Space|None, goal_context=str|None, memory_items=list|None) → AgentResult`
- Returns AgentResult with: status (Status enum), final_text, exit_code, session_id, raw_events
- **Reuse**: Call for each Agent node; pass interpolated brief as task.brief, goal_context if needed

**_finalize_child** (worker.py:657-739):
- Finalizes a child task after run_agent completes or fails
- Handles STATUS parsing, state transitions (ACTIVE→{WAITING,DONE}), memory block extraction
- Signature: `await _finalize_child(child_id, result: AgentResult|None, run_exception: str|None, started_at: datetime) → TaskState`
- Returns final TaskState (DONE, WAITING, etc.)
- **Reuse**: Call after each Agent node's run_agent

**_run_goal pattern** (worker.py:741-956):
- Drains pending goal-level messages
- Loops ordered_child_ids, checks state (skip if done/archived), transitions to ACTIVE
- For sub-goals: recurses _run_goal; for tasks: calls run_agent then _finalize_child
- Publishes lifecycle events (goal_child_start, goal_child_end, run_start, run_end)
- Tracks completed/skipped/failed children and synthesizes goal summary
- **Reuse**: Executor can follow this pattern: fetch harness, walk DAG in topo order, materialize Agent nodes as child tasks, await completion, synthesize run summary

### 3. Task Creation (storage.py, models.py)

**TaskStore.create()** (storage.py:630-676):
```python
async def create(
    self,
    *,
    space_id: str,
    title: str,
    brief: str,
    agent_model: AgentModel = "default",
    agent_mode: AgentMode = "auto",
    priority: int = 3,
    type: str = "task",
    parent_id: str | None = None,
    depends_on: list[str] | None = None,
) → Task
```
- Creates a new task with auto-generated task_id (from title + timestamp)
- Initializes state=BACKLOG, can set parent_id for hierarchy
- **For executor**: Create child Task with type="task", parent_id=run_goal_id, brief=interpolated_prompt

**Task fields** (models.py:33-55):
- id, space_id, title, state, agent_model, agent_mode, brief, history, pending_messages
- parent_id (for hierarchy), depends_on (sibling deps)
- No parent_run_id field yet; must add to RunTrace (not Task)

### 4. RunTrace Structure & parent_run_id Field (trace_parser.py)

**Current RunTrace model** (line 123-152):
- task_id, space_id, run_index, session_id, model, mode, started_at, ended_at
- turns (AssistantTurnTrace[]), tool_calls (ToolCallTrace[])
- final_text_snippet, memory_injected, memory_used, memory_written
- **Missing: parent_run_id**

**extract_run_trace** (line 159-379):
- Parses raw stream-json events into structured RunTrace
- Computes quality signals (exploration_ratio, error_recovery_count, backtrack_count)
- **Modification needed**: Add parent_run_id parameter to extract_run_trace and persist in RunTrace

**Field location**: parent_run_id should be optional field on RunTrace (alongside task_id, space_id) to track which harness run spawned this child task.

### 5. Agent Tool Resolution (api/tools.py)

**_scan_category** (line 140-141):
- Scans `{space_dir}/.claude/agents/` and global `~/.claude/agents/`
- Returns list[AiToolEntry] with name, path, description, scope, modified_at

**get_space_tools** (line 129-174):
- Full endpoint response includes agents, commands, skills, context_files
- **For executor**: When harness node has agent_ref="pipeline-scout", resolve to path via _scan_category lookup, then embed in child Task.brief or agent_model override

**No new flag needed**: Agent binding is via brief interpolation, not --agent flag. Skills (with /<name> prefix) are already supported in brief text.

### 6. Variable Interpolation Patterns

**Status**: Not yet implemented in the codebase.

**Recommendation** (per brief requirements):
- Harness.variables dict stores root-level bindings: `{"key": "value"}`
- For each Agent node, interpolate node.data["prompt_template"] using:
  - Harness.variables (root scope)
  - Upstream node output: `{upstream_node_id.final_text}` or `{upstream_node_id.STATUS}` from RunTrace.final_text_snippet or exit_reason
- Python template approach: f-strings or string.Template with safe_substitute
- Store interpolated prompt in child Task.brief when creating the child

**Example interpolation**:
```
node.data["prompt_template"] = "Build the component described in {upstream.output}. Use {lang} syntax."
# After interpolation:
child_task.brief = "Build the component described in [previous node output]. Use Python syntax."
```

### 7. Run State Persistence (new file pattern)

**Current persistence patterns**:
- Tasks: `{space_dir}/.cronos/tasks/{task_id}.md` (frontmatter + markdown)
- Harnesses: `{space_dir}/.cronos/harnesses/{slug}.yml` (YAML)
- Traces: `{space_dir}/.cronos/traces/{task_id}/{run_index}.json` (JSON, if trace_store enabled)

**For executor**: Create run-state file at `{space_dir}/.cronos/harness-runs/{run_id}.json`:
```json
{
  "run_id": "<goal_id>",
  "harness_name": "example-harness",
  "status": "in_progress",
  "started_at": "2026-06-03T12:34:56Z",
  "nodes_executed": {
    "node1": {"status": "done", "child_task_id": "abc123", "output": "..."},
    "node2": {"status": "in_progress", "child_task_id": "def456"}
  },
  "edges_traversed": [
    {"source": "node1", "target": "node2", "status": "active"}
  ],
  "variables": {"key": "resolved_value"}
}
```
- Persisted atomically (tmpfile + os.replace) after each node completion
- Restart-safe: load and resume from last completed node
- Enables run UI visualization

### 8. Control-Flow Node Stubs (arc6.3 implementation)

**Node types requiring stubs**:
- `trigger`: Entry point; check data["condition"] (or skip, just pass to edges)
- `decision`: Evaluate node.data["guard"] expression against variables; choose outgoing edge
- `wait`: Sleep/pause; node.data["duration_seconds"] or manual resume
- `aggregator`: Merge outputs from multiple predecessors (stub: concatenate final_text_snippets)

**For arc6.2 (executor only)**: Stub all control-flow nodes as no-op passthroughs:
```python
if node.type in ("trigger", "decision", "wait", "aggregator"):
    # Skip execution; publish run event and proceed to next nodes in topo order
    await publish({type: "node_skipped", node_id: node.id})
    continue
```

### 9. Worker Pool Contention & Serial Execution

**Current contention model** (worker.py):
- Single Worker per space (worker_pool.py manages the pool)
- Tasks enqueued via worker.enqueue(task_id)
- Worker._queue processes FIFO

**For harness runs**:
- A harness run (goal with N Agent child tasks) holds the worker for the entire duration
- Worker serializes: runs one harness fully before dequeuing next task
- No changes to worker_pool needed; inherit single-queue FIFO serialization

**Locking pattern**:
- Worker._run_goal already locks via single async loop (no explicit lock needed for task creation)
- Parent goal ID = run_id; all child tasks set parent_id = run_id
- Goal state machine ensures no re-entry once ACTIVE

**Contention risk**: If harness run takes long time, other queued tasks wait. Mitigated by:
- Run state file enables pause/resume across process restarts
- goal-finalize skill can interrupt long runs (handled by stop_current event)

## Assumptions
- Agent binding via brief interpolation; no new task field for agent override. Harness node.data can embed agent name in prompt_template or via agent_mode override on child Task.
- Control-flow nodes (trigger, decision, wait, aggregator) are stubbed as no-ops in arc6.2; full logic deferred to arc6.3.
- RunTrace.parent_run_id is optional field; populated when child task is executed inside a harness run.
- Variable interpolation uses Python f-strings or string.Template; scope is root Harness.variables plus upstream node outputs (from RunTrace).
- Run state file format is JSON (not YAML) for atomic partial updates and easier JSON parsing.
- Worker serialization already prevents contention; harness runs are treated as goals with child tasks.

## Open questions
- None.

## Next consumer brief

**Analyst should examine**:
1. **Brief field interpolation**: Confirm whether agent_ref binding requires new Task field or is purely brief-text-embedded.
2. **Upstream output passing**: Validate variable scoping (does each node see only immediate predecessor output, or full execution trace?).
3. **Control-flow stubs for arc6.2**: Clarify whether trigger/decision/wait/aggregator must publish lifecycle events or can be silent no-ops.
4. **Run state file location**: Confirm `.cronos/harness-runs/` path and whether it should be indexed/queried or is internal-only.
5. **Parent task dependencies**: When harness is run inside a goal, should each Agent child task inherit goal-level depends_on constraints, or only sibling harness dependencies?

**Implementation priorities**:
- Create executor.py with HarnessExecutor class
- Add parent_run_id field to RunTrace (optional, string)
- Implement Agent node → Task materialization with brief interpolation
- Add run state file persistence with atomic writes
- Integrate executor into worker._run_goal for goals with type="harness_run" (or detect harness_id field)
