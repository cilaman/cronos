---
cc_version: '1.0'
agent: pipeline-analyst
slug: arc6-harness-model
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:project_architecture_key_modules
- memory:project_pipeline_schemas
- memory:project_arc6_board_setup
- .cronos/pipeline/arc6-harness-model/scout-report-arc6-harness-model.md
- backend/app/pipeline/CONTRACT.md
- backend/app/pipeline/verify.py
- backend/app/pipeline/schemas/analysis.schema.yaml
outputs_produced:
- .cronos/pipeline/arc6-harness-model/analysis-report-arc6-harness-model.md
blockers: []
next_consumer: design
request: "Build the harness data layer. New package `backend/app/harnesses/` (`model.py`,\
  \ `store.py`)\nwith a Pydantic model + YAML round-trip.\n\n- `HarnessNode`: `id`,\
  \ `type` (`agent|trigger|decision|wait|aggregator`), `position {x,y}`,\n  `ports`\
  \ (named in/out socket ids), `data: dict` (type-specific config — e.g. an agent\n\
  \  node's `agent_ref` + `prompt_template` + `variable_bindings`), `label`. Include\n\
  \  position/ports/data from the start so frontend subgoals extend additively, never\
  \ revise.\n- `HarnessEdge`: `id`, `source` (node+port), `target` (node+port), optional\
  \ `condition` label.\n  `Harness`: `name`, `description`, `nodes[]`, `edges[]`,\
  \ `variables: dict`, `version`.\n- Persist at `{space}/.cronos/harnesses/<name>.yml`\
  \ (source of truth); atomic write\n  (tmpfile + `os.replace`) per space_storage.py.\
  \ Path-safe filename; name uniqueness.\n- Validator: graph is a DAG (no cycles),\
  \ edges reference existing nodes/ports, only\n  allowed types. **Adapt** (do not\
  \ reuse verbatim) the cycle logic in storage.py\n  (`_dep_cycle_path` / `validate_depends_on`)\
  \ to node/edge structures.\n- CRUD `backend/app/api/harnesses.py` wired into main.py,\
  \ following DI+auth in\n  api/tasks.py: `GET/POST/PUT/DELETE /api/spaces/{id}/harnesses[/<name>]`.\n\
  \  Invalid graph => 422. Resolve YAML round-trip fidelity vs editor as second writer\n\
  \  (last-writer-wins) and concurrent CRUD vs a live run.\n\nAcceptance: POST a 3-node/2-edge\
  \ harness -> GET round-trips losslessly; a cycle or\ndangling edge -> 422; on-disk\
  \ YAML matches the API payload."
has_ui: false
coverage_summary:
  searched:
  - backend/app/pipeline/CONTRACT.md
  - backend/app/pipeline/verify.py
  - backend/app/pipeline/schemas/analysis.schema.yaml
  - backend/app/models.py (via scout)
  - backend/app/storage.py (via scout)
  - backend/app/space_storage.py (via scout)
  - backend/app/api/tasks.py (via scout)
  - backend/app/main.py (via scout)
  excluded:
  - frontend/: has_ui=false; no UI changes in this sub-goal scope
  - backend/app/agent.py: agent execution scope, not storage or API design
  - backend/app/worker.py: background executor; not data layer
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: 'The package backend/app/harnesses/ must contain model.py defining HarnessNode,
    HarnessEdge, and Harness as Pydantic BaseModel classes with all fields specified
    in the request: HarnessNode has id, type (enum: agent|trigger|decision|wait|aggregator),
    position {x, y}, ports (named in/out socket ids), data: dict, and label; HarnessEdge
    has id, source (node id + port id), target (node id + port id), and optional condition
    label; Harness has name, description, nodes[], edges[], variables: dict, and version.'
  acceptance_criteria:
  - Given a valid dict payload, when constructing HarnessNode, HarnessEdge, and Harness
    via Pydantic, then all fields are present, typed correctly, and serializable to
    dict/JSON without data loss.
  - HarnessNode.type rejects any value outside {agent, trigger, decision, wait, aggregator}
    with a Pydantic ValidationError.
  - HarnessEdge.condition is optional (None by default) and is preserved in round-trip
    serialization.
  - Harness includes created_at and updated_at datetime fields populated on construction
    and update.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: HarnessNode.position must accept both x and y as numeric fields (int
    or float), and HarnessNode.ports must accept a dict mapping port names to port
    descriptors; these fields must be present from the initial model definition so
    that frontend subgoals extend the model additively without revision.
  acceptance_criteria:
  - 'Given a HarnessNode construction with position={x: 10.5, y: 20.0} and ports={in0:
    {}, out0: {}}, when the model is validated, then position.x, position.y, and each
    port entry are accessible by name.'
  - A HarnessNode model with an empty ports dict ({}) passes validation.
  - A HarnessNode model missing position raises a Pydantic ValidationError.
  verifying_phase: test
  confidence: 0.93
- requirement_id: R3
  statement: HarnessNode.data must be a dict field that accepts arbitrary type-specific
    configuration (e.g., agent_ref, prompt_template, variable_bindings for agent-type
    nodes), defaulting to an empty dict when not provided.
  acceptance_criteria:
  - 'Given a HarnessNode of type=agent with data={agent_ref: ''pipeline-scout'', prompt_template:
    ''{{input}}'', variable_bindings: {}}, when the model is validated, then data
    is preserved exactly in round-trip serialization.'
  - A HarnessNode with data={} passes validation.
  - A HarnessNode with data omitted defaults to {} (not None or missing).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R4
  statement: 'The Harness model must implement a @model_validator(mode=''after'')
    that enforces: (a) all edge source/target node ids reference nodes in nodes[],
    (b) all edge source/target port ids reference ports defined on their respective
    nodes, and (c) no duplicate node ids or edge ids within the same Harness.'
  acceptance_criteria:
  - Given a Harness with an edge whose source node_id does not exist in nodes[], when
    the model is validated, then a Pydantic ValidationError is raised referencing
    the missing node.
  - Given a Harness with an edge whose source port_id does not exist in the source
    node's ports dict, when the model is validated, then a Pydantic ValidationError
    is raised referencing the missing port.
  - Given a Harness with two nodes sharing the same id, when the model is validated,
    then a Pydantic ValidationError is raised.
  - Given a valid Harness where all edges reference existing nodes and ports, then
    validation passes without error.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R5
  statement: 'The Harness graph must be validated as a DAG: no directed cycles are
    permitted through the edge graph. The cycle detection must adapt (not copy verbatim)
    the BFS algorithm from storage.py (_dep_cycle_path / validate_depends_on) to operate
    over HarnessNode/HarnessEdge structures, implemented in backend/app/harnesses/.'
  acceptance_criteria:
  - Given a 3-node harness with edges A->B, B->C, C->A (cycle), when validate_graph()
    is called, then a validation error is raised identifying the cycle.
  - Given a 3-node harness with edges A->B, A->C (fan-out, no cycle), when validate_graph()
    is called, then validation passes.
  - Given a single-node harness with a self-loop edge (source node id == target node
    id), when validate_graph() is called, then a validation error is raised.
  - The cycle detection function is defined in backend/app/harnesses/ and operates
    on node/edge structures rather than depending on storage.py internals.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R6
  statement: 'backend/app/harnesses/store.py must define HarnessStore with an asyncio.Lock,
    an in-memory index keyed by (space_id, harness_name), and CRUD methods: create,
    get, list, update, delete. Each mutating method must acquire the async Lock before
    modifying the index.'
  acceptance_criteria:
  - Given concurrent POST requests for the same space with the same harness name,
    when both attempt to create, then only one succeeds and the other receives a name-conflict
    error.
  - HarnessStore.get(space_id, name) returns None when no harness with that name exists
    for that space.
  - HarnessStore.list(space_id) returns all harnesses for the given space and an empty
    list when none exist.
  - HarnessStore uses asyncio.Lock for all mutating operations, consistent with the
    SpaceStore pattern in space_storage.py.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R7
  statement: Harnesses must persist to disk at {space}/.cronos/harnesses/<filename>.yml
    using atomic write (tmpfile + os.replace), following the pattern in storage.py.
    The filename must be derived from the harness name via a slugify function producing
    a path-safe identifier; name uniqueness must be enforced per space before write.
  acceptance_criteria:
  - Given a POST that creates a harness with name='My Harness!', the file is written
    to .cronos/harnesses/my-harness.yml (slugified, special chars removed).
  - Given two harnesses in the same space with names that slugify identically, the
    second write uses a collision suffix to avoid overwriting.
  - 'Atomic write guarantee: if the process is interrupted mid-write, the existing
    .yml file is not corrupted (tmpfile + os.replace pattern).'
  - A harness file written by POST can be loaded from disk and round-trips to the
    identical Harness model with no field loss or type coercion.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R8
  statement: 'The YAML representation of a Harness must be losslessly round-trippable:
    serializing a Harness to YAML and deserializing back must produce an identical
    Harness model. The on-disk YAML must contain exactly the same data as the API
    response payload.'
  acceptance_criteria:
  - Given a POST that creates a 3-node/2-edge harness, when the on-disk .yml file
    is loaded and parsed, then the resulting Harness model equals the API response
    model field-by-field.
  - Datetime fields (created_at, updated_at) are serialized as ISO 8601 strings and
    deserialized back to datetime objects without precision loss.
  - dict fields (data, variables) with nested values round-trip without type coercion
    (e.g., int remains int, not string).
  verifying_phase: test
  confidence: 0.9
- requirement_id: R9
  statement: 'backend/app/api/harnesses.py must implement a FastAPI APIRouter with
    five endpoints: GET /api/spaces/{space_id}/harnesses (list), POST /api/spaces/{space_id}/harnesses
    (create), GET /api/spaces/{space_id}/harnesses/{name} (fetch), PUT /api/spaces/{space_id}/harnesses/{name}
    (update), DELETE /api/spaces/{space_id}/harnesses/{name} (delete). DI must follow
    the Request.app.state pattern from api/tasks.py.'
  acceptance_criteria:
  - GET /api/spaces/{space_id}/harnesses returns 200 with [] when no harnesses exist
    for the space.
  - POST /api/spaces/{space_id}/harnesses with a valid payload returns 201 and the
    created Harness.
  - GET /api/spaces/{space_id}/harnesses/{name} for an existing harness returns 200
    and the Harness.
  - GET /api/spaces/{space_id}/harnesses/{name} for a non-existent name returns 404.
  - DELETE /api/spaces/{space_id}/harnesses/{name} removes the harness from the store
    and disk; subsequent GET returns 404.
  - All endpoints retrieve HarnessStore via request.app.state consistent with the
    DI pattern in api/tasks.py.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R10
  statement: 'POST and PUT /api/spaces/{space_id}/harnesses[/{name}] must return HTTP
    422 when the submitted graph is invalid: a cycle in the edge graph, a dangling
    edge referencing a non-existent node or port, or a node with a type outside the
    allowed enum all produce 422 Unprocessable Entity.'
  acceptance_criteria:
  - Given a POST body with edges forming a cycle (A->B->C->A), the response is 422
    with an error message identifying the cycle.
  - Given a POST body with an edge whose target node_id does not exist in nodes[],
    the response is 422 with a message referencing the dangling edge.
  - Given a POST body with a node whose type is not in {agent, trigger, decision,
    wait, aggregator}, the response is 422.
  - Given a PUT body that introduces a cycle into a previously valid harness, the
    response is 422 and the harness on disk is unchanged.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R11
  statement: POST /api/spaces/{space_id}/harnesses must return HTTP 409 when a harness
    with the same name already exists in that space; a harness with the same name
    in a different space must not trigger a conflict.
  acceptance_criteria:
  - Given an existing harness named 'my-flow' in space S, when POST /api/spaces/S/harnesses
    is called with name='my-flow', then the response is 409 Conflict.
  - Given an existing harness named 'my-flow' in space S, when POST /api/spaces/T/harnesses
    is called with name='my-flow' (different space T), then the response is 201 (no
    cross-space conflict).
  verifying_phase: test
  confidence: 0.9
- requirement_id: R12
  statement: The harnesses router must be registered in backend/app/main.py with the
    same auth dependencies as other API routers (HTTP Basic Auth via the _auth dependency
    list), following the app.include_router pattern used for other space-scoped routers.
  acceptance_criteria:
  - After router registration, GET /api/spaces/{space_id}/harnesses without auth credentials
    returns 401.
  - After router registration, GET /api/spaces/{space_id}/harnesses with valid credentials
    returns 200 (or 404 for an unknown space).
  - The harness router endpoints are visible in the FastAPI OpenAPI schema at /docs.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R13
  statement: 'PUT /api/spaces/{space_id}/harnesses/{name} must follow last-writer-wins
    semantics for concurrent CRUD: no optimistic locking or ETag enforcement. If two
    concurrent PUT requests target the same harness, the later atomic write wins without
    returning an error.'
  acceptance_criteria:
  - Two sequential PUT requests to the same harness both return 200; the second response
    reflects the second payload.
  - No 409 is returned for concurrent PUT requests (last-writer-wins, not conflict-detected).
  - The last-writer-wins behavior is documented in a docstring or comment in harnesses.py.
  verifying_phase: review
  confidence: 0.88
- requirement_id: R14
  statement: 'The acceptance scenario must pass end-to-end: POST a 3-node/2-edge harness,
    GET it back and verify round-trip losslessness, then verify the on-disk YAML matches
    the API payload.'
  acceptance_criteria:
  - 'Given POST /api/spaces/{id}/harnesses with {nodes: [A, B, C], edges: [A->B, B->C]},
    the response body contains all three nodes and both edges with all fields intact.'
  - Given GET /api/spaces/{id}/harnesses/{name} after the above POST, the response
    body is field-for-field identical to the POST response body (same ids, positions,
    data dicts, timestamps).
  - Given the .cronos/harnesses/<name>.yml file on disk after the POST, parsing it
    with yaml.safe_load and constructing a Harness model produces the identical model
    as the GET response.
  verifying_phase: test
  confidence: 0.93
metrics:
  tool_calls: 7
  files_read: 4
  memory_hits: 3
---

## Summary

This feature introduces the harness data layer: a new `backend/app/harnesses/` package containing Pydantic models (`HarnessNode`, `HarnessEdge`, `Harness`), a YAML-backed store (`HarnessStore`) with atomic persistence, a DAG validator adapted from the storage.py cycle-detection BFS, and a CRUD REST API (`/api/spaces/{id}/harnesses`) wired into main.py. The design follows established Cronos patterns — atomic YAML writes from storage.py, async-Lock in-memory index from SpaceStore, DI via `request.app.state` from api/tasks.py, 422 for graph validation failures — so that frontend subgoals can extend the model additively without revising core data structures. All 14 requirements are derived directly from the request text and acceptance criteria; confidence is 0.92 with no blockers.

## Scope

### In scope
- Pydantic model definitions: `HarnessNode` (id, type enum, position, ports, data, label), `HarnessEdge` (id, source node+port, target node+port, optional condition), `Harness` (name, description, nodes[], edges[], variables, version, created_at, updated_at)
- Cross-field model validation via `@model_validator(mode="after")`: unique node/edge ids, edges reference real nodes and ports
- DAG cycle detection adapted from `_dep_cycle_path` / `validate_depends_on` in storage.py to operate on node/edge structures
- YAML round-trip persistence at `{space}/.cronos/harnesses/<slug>.yml` with atomic write (tmpfile + os.replace)
- Path-safe filename generation (slugify + collision suffix) and name uniqueness enforcement per space
- `HarnessStore` with asyncio.Lock, in-memory index by (space_id, harness_name), and CRUD methods
- REST API: `GET/POST /api/spaces/{id}/harnesses` and `GET/PUT/DELETE /api/spaces/{id}/harnesses/{name}`
- HTTP error mapping: 404 (not found), 409 (name conflict), 422 (graph validation failure)
- Router registration in `main.py` with auth dependencies

### Out of scope
- Frontend components (no UI in this sub-goal; frontend subgoals extend model additively later)
- Harness execution / run engine (executor phase)
- Git versioning or soft-delete / archive of harnesses
- Import/export to other graph formats (BPMN, Mermaid, etc.)
- Harness templates or cloning

### Deferred
- File-watcher integration for disk-change reindex (consistent with SpaceStore pattern; add in follow-on task after API layer is stable)
- Conflict detection for concurrent CRUD vs a live run (last-writer-wins documented in this phase; executor phase may add locking)
- Optimistic concurrency control (ETag / version-based conflict detection) — add as follow-on if live-run conflicts prove problematic

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Define HarnessNode, HarnessEdge, Harness Pydantic models with all request-specified fields |
| R2 | HarnessNode.position (x, y) and HarnessNode.ports (dict) are required from initial definition |
| R3 | HarnessNode.data is a dict field defaulting to {} for type-specific configuration |
| R4 | Harness model validator enforces edge node/port references and unique ids |
| R5 | DAG cycle detection adapted from storage.py BFS to harness node/edge structures |
| R6 | HarnessStore with async Lock, in-memory index by (space_id, name), CRUD methods |
| R7 | Atomic YAML persistence at .cronos/harnesses/ with path-safe filenames and name uniqueness |
| R8 | YAML round-trip is lossless: on-disk YAML matches API payload field-for-field |
| R9 | CRUD REST API: GET/POST /api/spaces/{id}/harnesses and GET/PUT/DELETE .../harnesses/{name} |
| R10 | Invalid graph (cycle, dangling edge, bad type) on POST/PUT returns HTTP 422 |
| R11 | Duplicate harness name within same space on POST returns HTTP 409 |
| R12 | Harness router registered in main.py with auth dependencies |
| R13 | Concurrent PUT follows last-writer-wins; behavior documented in code |
| R14 | Acceptance scenario: POST 3-node/2-edge, GET round-trips losslessly, disk YAML matches |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — All HarnessNode/HarnessEdge/Harness fields present and correctly typed; type enum and optional condition validated
- R2 — position x/y and ports dict are required; empty ports valid; missing position raises ValidationError
- R3 — data dict defaults to {}; arbitrary nested config preserved exactly in round-trip
- R4 — Edges referencing missing nodes/ports raise ValidationError; duplicate node ids raise ValidationError
- R5 — A->B->C->A cycle raises error; A->B, A->C (fan-out) passes; self-loop raises error
- R6 — Concurrent creates with same name: only one succeeds; list returns [] for empty space; async Lock used
- R7 — Special chars slugified; collision suffix on slug collision; atomic write prevents corruption
- R8 — POST response == GET response field-for-field; on-disk YAML parses to identical model; datetimes and dicts lossless
- R9 — All five endpoints respond with correct status codes; 404 for missing; 201 for create; DI via request.app.state
- R10 — Cycle, dangling edge, or invalid type all return 422; PUT with cycle leaves disk unchanged
- R11 — Same name in same space returns 409; same name in different space returns 201
- R12 — Unauthenticated returns 401; authenticated returns 200/404; endpoints visible in OpenAPI schema
- R13 — Two sequential PUTs both return 200; no 409 on concurrent PUTs; last-writer-wins documented
- R14 — POST 3-node/2-edge, GET returns identical body, disk YAML parses to identical model

## Traceability

The full requirement -> acceptance criteria -> verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Define HarnessNode, HarnessEdge, and Harness Pydantic models with all request-specified fields |
| R2 | test | HarnessNode.position (x, y) and .ports (dict) are required fields present from initial definition |
| R3 | test | HarnessNode.data is a dict field defaulting to {} for type-specific configuration |
| R4 | test | Harness @model_validator enforces edge-to-node/port references and id uniqueness |
| R5 | test | DAG cycle detection adapted from storage.py BFS to harness node/edge structures |
| R6 | test | HarnessStore with async Lock, in-memory index by (space_id, name), CRUD methods |
| R7 | test | Atomic YAML persistence at .cronos/harnesses/ with path-safe filenames and name uniqueness |
| R8 | test | YAML round-trip is lossless: on-disk YAML matches API payload field-for-field |
| R9 | test | CRUD REST API: all five endpoints respond with correct status codes and DI pattern |
| R10 | test | Invalid graph (cycle, dangling edge, bad node type) on POST/PUT returns HTTP 422 |
| R11 | test | Duplicate harness name within same space on POST returns HTTP 409 |
| R12 | test | Harness router registered in main.py with auth dependencies |
| R13 | review | Concurrent PUT follows last-writer-wins; behavior documented in code |
| R14 | test | Acceptance scenario: POST 3-node/2-edge, GET round-trips losslessly, disk YAML matches |

## Assumptions

- has_ui=false rationale: the request explicitly scopes this sub-goal to `backend/app/harnesses/` (model.py, store.py) and `backend/app/api/harnesses.py`; it states "frontend subgoals extend additively" implying frontend is a separate future sub-goal.
- Harnesses are space-scoped: each harness lives at `{space}/.cronos/harnesses/<slug>.yml` isolated per space, consistent with how tasks are scoped per space in storage.py.
- version field in Harness is a string (e.g. "1.0") for human-readable format versioning, not an auto-increment integer; present from the start as the request specifies it.
- Port descriptors in HarnessNode.ports are untyped dicts (not a separate PortDescriptor model) for the first iteration; frontend sub-goals may refine this additively.
- created_at and updated_at fields are added following the existing Cronos datetime pattern (models.py, space_storage.py) even though not explicitly listed in the request; needed for audit and implied by "YAML round-trip fidelity."
- last-writer-wins concurrency for CRUD is consistent with how SpaceStore and TaskStore operate; the request explicitly calls this out as a design resolution.
- The cycle detector is re-implemented in backend/app/harnesses/ (not imported from storage.py) as the request explicitly states "adapt (do not reuse verbatim)" to avoid coupling harness layer to task-storage internals.
- HarnessStore is initialized on app startup and attached to app.state (like SpaceStore), then injected via request.app.state in the API layer.

## Open questions

- None. The request text and scout findings together fully define the scope, patterns, and acceptance criteria. All design decisions (last-writer-wins, slugify for filenames, BFS cycle detection adaptation, DI pattern) have clear precedents in the existing codebase documented in the scout report.

## Next consumer brief

Read first: `traceability[]` (14 requirements, all test-verified except R13 which is review-verified), `has_ui: false` (no frontend design), and `## Scope` for explicit deferred items.

Key design decision points:

- **Package layout**: `backend/app/harnesses/__init__.py`, `model.py` (Pydantic models + NodeType enum), `store.py` (HarnessStore + atomic write + slugify), and `backend/app/api/harnesses.py` (router). Consider a separate `validator.py` for the DAG cycle detection to keep model.py clean.
- **Cycle detection adaptation**: The BFS from `storage.py:126-179` traverses `node.depends_on` (list of ids); the harness adaptation traverses outbound edges for each node: `[e.target_node for e in edges if e.source_node == current]`. The data structures differ enough to warrant a new function rather than a copy. Implement in store.py or validator.py, not as a Pydantic model_validator (graph traversal is cleaner outside Pydantic).
- **Model validator layering**: Field-level checks (type enum, position presence) belong in Pydantic. Cross-entity checks (edge references valid nodes/ports, unique ids) belong in Harness model_validator. DAG cycle check belongs in HarnessStore.create/update (not in Pydantic) because it requires full graph traversal.
- **Error mapping**: graph validation error -> 422; HarnessNotFound -> 404; name conflict -> 409. Consistent with tasks.py:365-406.
- **Risk area**: YAML round-trip fidelity for mixed-type dict fields. Verify that yaml.safe_dump + yaml.safe_load preserves int/float/bool types inside data and variables dicts. Use yaml.safe_dump with default_flow_style=False for readable YAML.
