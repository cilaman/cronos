Build the harness data layer. New package `backend/app/harnesses/` (`model.py`, `store.py`)
with a Pydantic model + YAML round-trip.

- `HarnessNode`: `id`, `type` (`agent|trigger|decision|wait|aggregator`), `position {x,y}`,
  `ports` (named in/out socket ids), `data: dict` (type-specific config — e.g. an agent
  node's `agent_ref` + `prompt_template` + `variable_bindings`), `label`. Include
  position/ports/data from the start so frontend subgoals extend additively, never revise.
- `HarnessEdge`: `id`, `source` (node+port), `target` (node+port), optional `condition` label.
  `Harness`: `name`, `description`, `nodes[]`, `edges[]`, `variables: dict`, `version`.
- Persist at `{space}/.cronos/harnesses/<name>.yml` (source of truth); atomic write
  (tmpfile + `os.replace`) per space_storage.py. Path-safe filename; name uniqueness.
- Validator: graph is a DAG (no cycles), edges reference existing nodes/ports, only
  allowed types. **Adapt** (do not reuse verbatim) the cycle logic in storage.py
  (`_dep_cycle_path` / `validate_depends_on`) to node/edge structures.
- CRUD `backend/app/api/harnesses.py` wired into main.py, following DI+auth in
  api/tasks.py: `GET/POST/PUT/DELETE /api/spaces/{id}/harnesses[/<name>]`.
  Invalid graph ⇒ 422. Resolve YAML round-trip fidelity vs editor as second writer
  (last-writer-wins) and concurrent CRUD vs a live run.

Acceptance: POST a 3-node/2-edge harness → GET round-trips losslessly; a cycle or
dangling edge → 422; on-disk YAML matches the API payload.

