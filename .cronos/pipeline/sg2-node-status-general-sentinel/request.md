Spec 2 — `node_status` general sentinel

Generalize the delivery_status envelope. The name `delivery_status` conflates a general transport with an SDLC domain. HarnessExecutor already parses delivery_status for routing scope (executor.py:822, `_enrich_scope_from_delivery_status` :1347) — proving it's already a misnomer.

`node_status` is correct because the emitter is always an agent executing a node, and it matches the executor's scope-key namespace (`node_id.fields.verdict`).

### What to generalize
The STATUS BLOCK ENVELOPE is general: `{status, produces, artifact_paths, open_questions, fields}`. The `fields` key stays open and workflow-defined — a data-pipeline harness emits the same envelope with different fields. Do NOT standardize a verdict vocabulary; only the envelope is universal.

### Implementation
1. Add `node_status` parser in `packages/delivery-workflow/lib/node_status.py` (same style as lib/delivery_status.py)
2. Wire as tier-0 in `backend/app/agent.py::parse_status` (additive; the SG1 bridge already handles tiers 1-4)
3. Migrate the 38 delivery emitters from `delivery_status` to `node_status` 
4. cronos_status: do NOT migrate the board population — flip opportunistically only when touched for other reasons; never a forced mass-migration

### References
- `packages/delivery-workflow/lib/` — where the parser lives
- `backend/app/agent.py::parse_status` — the single chokepoint (SG1 already modified it)
- `backend/app/memory_parser.py` — existing delivery_status and cronos_status parsers
- `packages/delivery-workflow/agents/` — the 38+ delivery agent .md files that emit delivery_status

