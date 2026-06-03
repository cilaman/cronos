Build the runtime in `backend/app/harnesses/executor.py`. A run is a Task (`type=goal`);
**only Agent nodes become child tasks.**

- **Do NOT reuse `_run_goal` wholesale** (only recurse/`run_agent` branches exist). Build
  a **new stateful DAG interpreter** walking the graph: at an Agent node, materialise/enqueue
  a child Task and await its terminal state (reuse `run_agent` + `_finalize_child` + the
  topo-sort from `_topo_children` [worker.py:51]). Stub control-flow nodes as pass-through
  here (6.3 implements them) so a linear all-Agent harness runs end to end.
- **Agent binding:** compose `agent_ref` + `prompt_template` + resolved `variable_bindings`
  into the child Task `brief` (skills get a `/<name>` prefix); resolve `agent_ref` against
  api/tools.py. No new `--agent` flag.
- **Variable/data passing:** define how an upstream node's output (child
  `RunTrace.final_text_snippet` / STATUS) flows into a downstream node's `prompt_template`
  variables.
- **`parent_run_id`:** optional field on `RunTrace` (trace_parser.py:110); thread through
  `extract_run_trace`, set on each Agent child, persist in the trace JSON without breaking
  TracePanel.tsx.
- Run state (per-node status, chosen edges, child ids) persists at
  `{space}/.cronos/harness-runs/<run_id>.json` (restart-safe).
- Address worker contention: a run holds the space's single serial worker
  (worker_pool.py) for its whole duration — avoid starving normal tasks.

Acceptance: a 3-node linear harness expands to a goal + 3 child tasks in topo order; each
child's `parent_run_id` = run id; an upstream output is interpolated into the next prompt;
run-state file reflects per-node status.

