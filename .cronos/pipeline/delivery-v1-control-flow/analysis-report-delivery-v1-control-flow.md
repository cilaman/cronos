---
cc_version: '1.0'
agent: pipeline-analyst
slug: delivery-v1-control-flow
phase: analysis
status: done
confidence: 0.95
has_ui: false
request: 'Analyst phase for SG3 – Loop Convergence, evalCondition & Cronos run_trace
  Wiring (G3.1–G3.3). G3.1: loop convergence policy — exit on until condition OR stall
  signal (recurring_findings / no_diff_progress) OR budget ceiling; on_exhaust escalates.
  G3.2: sandboxed evalCondition evaluating spec §7 conditions (verdict == pass, has_ui
  == true, finding_class == architectural) against a read-only scope. G3.3 (P0): fix
  Cronos executor passing run_trace=None to evalCondition; pass upstream delivery_status
  fields into scope so conditional edge routing is live.'
inputs_used:
- .cronos/pipeline/delivery-v1/scout-report-delivery-v1.md
- docs/delivery-pipeline/delivery-v1-docs/delivery-v1-spec.md
- docs/delivery-pipeline/delivery-v1-docs/delivery-v1-build-plan.md
- backend/app/harnesses/executor.py
- backend/app/harnesses/decision.py
- backend/app/harnesses/run_state.py
- backend/app/harnesses/model.py
- backend/app/memory_parser.py
- backend/app/agent.py
outputs_produced:
- .cronos/pipeline/delivery-v1-control-flow/analysis-report-delivery-v1-control-flow.md
blockers: []
next_consumer: design
metrics:
  tool_calls: 14
  files_read: 9
  memory_hits: 0
coverage_summary:
  searched:
  - backend/app/harnesses/executor.py (BFS loop, decision node, run_trace wiring)
  - backend/app/harnesses/decision.py (resolve_signal, edge_matches, _eval_variable_condition)
  - backend/app/harnesses/run_state.py (NodeState, RunState structure)
  - backend/app/harnesses/model.py (HarnessNode, NodeType)
  - backend/app/memory_parser.py (parse_cronos_status_block)
  - backend/app/agent.py (parse_status, STATUS_CONTRACT)
  - docs/delivery-pipeline/delivery-v1-docs/delivery-v1-spec.md (§6 loop semantics,
    §7 edge language, §8 structured return, §12 worked example)
  - docs/delivery-pipeline/delivery-v1-docs/delivery-v1-build-plan.md (Phase 3 acceptance
    criteria)
  - .cronos/pipeline/delivery-v1/scout-report-delivery-v1.md (gap analysis)
  excluded:
  - backend/app/pipeline/ (CC-v1 verifier — not changed by G3)
  - backend/app/worker.py (not modified by G3; G6.1 adapter work is out-of-scope)
  - frontend/ (has_ui=false)
  strategies:
  - read_targeted
  - grep_symbol
  - grep_keyword
traceability:
- requirement_id: R1
  statement: A loop-bearing agent node MUST be representable in the harness model.
    HarnessNode.data MUST support a loop sub-object with until (str), stall (list[str]),
    max (int), and on_exhaust (str) fields. The harness validator MUST NOT reject
    agent nodes that carry a recognized loop dict.
  acceptance_criteria:
  - 'validator.validate_graph() accepts a harness where nodes[0].data[''loop''] =
    {''until'': ''review.fields.verdict == \''pass\'''', ''stall'': [''recurring_findings''],
    ''max'': 5, ''on_exhaust'': ''escalate''} without raising.'
  - 'Round-trip: store a loop-bearing harness, reload it, verify data[''loop''] survives
    serialization.'
  verifying_phase: test
- requirement_id: R2
  statement: 'The executor loop handler MUST exit on whichever fires first: (a) until
    condition evaluates True via evalCondition, (b) any stall signal in data.loop.stall
    fires, (c) attempt count reaches max. The numeric max is a safety backstop, not
    the primary exit criterion.'
  acceptance_criteria:
  - A loop-bearing agent that satisfies its until condition on the first attempt exits
    after one iteration (no retry).
  - A loop-bearing agent that never satisfies until but fires a stall signal escalates
    rather than running to max.
  - A loop-bearing agent with max=2 that neither satisfies until nor fires stall escalates
    on the third attempt.
  verifying_phase: test
- requirement_id: R3
  statement: The recurring_findings stall signal MUST fire when the set of finding
    F-ids from the current attempt is non-empty AND identical to the set from the
    immediately prior attempt. F-ids are persisted in NodeState.prior_finding_ids
    between iterations.
  acceptance_criteria:
  - Two consecutive loop iterations both yielding F-ids {'F-001', 'F-002'} trigger
    recurring_findings and transition the run to WAITING.
  - First attempt with F-ids {'F-001'}, second attempt with F-ids {'F-001', 'F-002'}
    (non-identical) does NOT trigger recurring_findings.
  - First attempt with empty F-ids does NOT trigger recurring_findings even if second
    attempt also has empty F-ids.
  verifying_phase: test
- requirement_id: R4
  statement: The no_diff_progress stall signal MUST fire when the diff byte-size in
    delivery_status.fields.diff_bytes for the current attempt is not strictly less
    than the diff byte-size from the prior attempt. If diff_bytes is absent from delivery_status,
    this stall check is skipped for that iteration.
  acceptance_criteria:
  - Two consecutive attempts each reporting diff_bytes=1200 trigger no_diff_progress.
  - Attempt 1 reporting diff_bytes=2000, attempt 2 reporting diff_bytes=1200 do NOT
    trigger no_diff_progress.
  - Attempt without diff_bytes in delivery_status fields does not trigger no_diff_progress.
  verifying_phase: test
- requirement_id: R5
  statement: on_exhaust='escalate' MUST transition the harness run goal to TaskState.WAITING
    with a descriptive waiting_question naming the node, attempt count, and stall/exhaust
    reason. The run MUST NOT be silently marked done or failed.
  acceptance_criteria:
  - When max=2 and on_exhaust='escalate', after the third failed iteration the run
    transitions to WAITING state with waiting_question set.
  - The waiting_question string includes the node id and attempt count.
  - The run status is not 'done' or 'failed' after escalation.
  verifying_phase: test
- requirement_id: R6
  statement: NodeState MUST be extended with attempt (int, default 0) and prior_finding_ids
    (list[str], default []) fields. These MUST round-trip through NodeState serialization
    (to_dict / from_dict) without loss.
  acceptance_criteria:
  - NodeState(status='done', attempt=3, prior_finding_ids=['F-001']).to_dict() round-trips
    via from_dict correctly.
  - Legacy JSON without attempt or prior_finding_ids deserializes without error (defaults
    to 0 and []).
  verifying_phase: test
- requirement_id: R7
  statement: evalCondition MUST parse and evaluate dotted-path conditions of the form
    <node_id>.<field_path> <op> <literal>, where field_path is 'fields.<name>', 'decision',
    or 'status', and op is one of ==, !=, in. node_id may contain hyphens. Simple
    (non-dotted) identifiers MUST continue to work for backward compatibility.
  acceptance_criteria:
  - 'evalCondition("review.fields.verdict == ''pass''", {''review.fields.verdict'':
    ''pass''}) returns True.'
  - 'evalCondition("g-analysis.decision == ''proceed''", {''g-analysis.decision'':
    ''proceed''}) returns True (hyphenated node_id).'
  - 'evalCondition("myvar == ''x''", {''myvar'': ''x''}) returns True (backward-compat
    simple identifier).'
  verifying_phase: test
- requirement_id: R8
  statement: evalCondition MUST support the && boolean conjunction operator to compose
    exactly two simple conditions in a single expression. Both operands must be True
    for the conjunction to be True.
  acceptance_criteria:
  - 'evalCondition("a.fields.x == ''p'' && b.decision == ''proceed''", {''a.fields.x'':
    ''p'', ''b.decision'': ''proceed''}) returns True.'
  - 'evalCondition("a.fields.x == ''p'' && b.decision == ''proceed''", {''a.fields.x'':
    ''p'', ''b.decision'': ''fail''}) returns False.'
  verifying_phase: test
- requirement_id: R9
  statement: evalCondition MUST support unquoted boolean literals true and false (case-insensitive)
    on the right-hand side. Scope values that are the string 'true' or 'false' MUST
    compare correctly against these literals.
  acceptance_criteria:
  - 'evalCondition("analyze.fields.has_ui == true", {''analyze.fields.has_ui'': ''true''})
    returns True.'
  - 'evalCondition("analyze.fields.has_ui == false", {''analyze.fields.has_ui'': ''false''})
    returns True.'
  - 'evalCondition("analyze.fields.has_ui == true", {''analyze.fields.has_ui'': ''false''})
    returns False.'
  verifying_phase: test
- requirement_id: R10
  statement: evalCondition MUST reject any expression not matching the supported grammar
    (dotted-path comparison + && conjunction). Unsupported expressions MUST log a
    WARNING and return False. No eval(), no arbitrary code execution.
  acceptance_criteria:
  - evalCondition("__import__('os').system('rm -rf /')", {}) returns False without
    raising.
  - A WARNING log entry is emitted for every rejected expression.
  verifying_phase: test
- requirement_id: R11
  statement: All nine edge conditions in spec §12 worked example MUST evaluate to
    the correct boolean when the scope is populated with representative values.
  acceptance_criteria:
  - g-scout.decision == 'proceed' with scope g-scout.decision=proceed → True.
  - g-analysis.decision == 'proceed' with scope g-analysis.decision=proceed → True.
  - analyze.fields.has_ui == true with scope analyze.fields.has_ui=true → True.
  - analyze.fields.has_ui == false with scope analyze.fields.has_ui=false → True.
  - g-design.decision == 'proceed' with scope g-design.decision=proceed → True.
  - review.fields.verdict == 'pass' with scope review.fields.verdict=pass → True.
  - review.fields.verdict == 'needs_fix' && review.fields.finding_class == 'local'
    with matching scope → True.
  - review.fields.verdict == 'needs_fix' && review.fields.finding_class == 'architectural'
    with matching scope → True.
  - g-tests.decision == 'needs_fix' with scope g-tests.decision=needs_fix → True.
  verifying_phase: test
- requirement_id: R12
  statement: After each agent node completes, the executor MUST attempt to parse a
    delivery_status fenced JSON block from the agent's final output. On successful
    parse it MUST enrich the scope with scope['<node_id>.status'], scope['<node_id>.fields.<k>']
    for each entry in fields, before the downstream decision node evaluates edges.
    The existing scope[node_id] = final_text_snippet assignment MUST be preserved.
  acceptance_criteria:
  - 'After a stub agent emits delivery_status {fields: {verdict: ''pass''}}, scope[''review.fields.verdict'']
    == ''pass''.'
  - scope['review'] (raw text) is still set alongside the dotted-path keys.
  - An agent that emits no delivery_status block leaves scope unchanged (no KeyError).
  verifying_phase: test
- requirement_id: R13
  statement: 'A conditional edge with condition ''review.fields.verdict == pass''
    placed downstream of an agent node emitting delivery_status {fields: {verdict:
    pass}} MUST route to the pass-branch successor, not the default edge.'
  acceptance_criteria:
  - An executor integration test with a stub review agent emitting verdict=pass routes
    to the pass successor node.
  - The default edge is NOT taken when a condition-bearing edge matches.
  verifying_phase: test
- requirement_id: R14
  statement: 'A new parser function parse_delivery_status_block(text: str) -> dict
    | None MUST be added. It MUST recognize ```delivery_status fences, parse JSON
    body, accept blocks missing optional fields (open_questions, telemetry, artifact_paths),
    and return None for unclosed fences, malformed JSON, or missing required status
    field. It MUST NOT validate status against the cronos_status {DONE,WAIT,BLOCKED}
    enum.'
  acceptance_criteria:
  - 'parse_delivery_status_block with {status: done, produces: review, fields: {}}
    (no telemetry) returns the dict.'
  - parse_delivery_status_block with unclosed fence returns None.
  - parse_delivery_status_block with malformed JSON returns None.
  - parse_delivery_status_block with status='done' (lowercase) returns the dict (not
    rejected as non-DONE).
  verifying_phase: test
- requirement_id: R15
  statement: A decision node with one condition-bearing edge and one default edge
    (condition=None) MUST NOT follow the default edge when the scope contains a value
    matching the condition-bearing edge's expression.
  acceptance_criteria:
  - Decision node with condition 'review.fields.verdict == pass' and scope['review.fields.verdict']='pass'
    routes to condition-bearing edge, not default.
  - Decision node with the same condition but scope['review.fields.verdict']='needs_fix'
    routes to default edge.
  verifying_phase: test
---

## Summary

This analysis covers build-plan tasks **G3.1** (loop convergence policy), **G3.2** (sandboxed `evalCondition`), and **G3.3** (Cronos `run_trace` wiring — P0 routing unblock). All fifteen requirements are pure backend changes in `backend/app/harnesses/`. No frontend work.

**G3.3 is the critical-path P0 blocker**: in `executor.py:1009` the line `run_trace: RunTrace | None = None` is hardcoded and always passes None to `evaluate_decision`. This means every conditional edge in every Cronos harness falls through to the default edge regardless of agent output — the `condition` field is dead code today. G3.3 depends on G3.2 (which must extend `evalCondition` to handle dotted-path scope keys), and both depend on the `delivery_status` sentinel format defined by G0.3.

---

## Scope

**In scope (G3.1–G3.3):**
- `backend/app/harnesses/executor.py` — loop handler inside `_execute_agent_node`, scope enrichment from `delivery_status`
- `backend/app/harnesses/decision.py` — `_eval_variable_condition` replacement with dotted-path + `&&` support
- `backend/app/harnesses/run_state.py` — `NodeState` extension with `attempt` + `prior_finding_ids`
- `backend/app/memory_parser.py` — new `parse_delivery_status_block` function

**Out of scope:**
- `backend/app/worker.py` (Cronos adapter formalization — G6.1)
- `backend/app/pipeline/` (CC-v1 verifier — not changed by G3)
- `frontend/` (`has_ui: false`)
- Agent re-authoring to emit `delivery_status` (G5.1)
- Traceability matrix (G4.1)

---

## Current state analysis

### Loop model
**There is no loop model.** The BFS executor performs a single-pass traversal. `HarnessNode.data` has no `loop` key. No attempt counter, no stall detection, no `until` condition evaluation exists anywhere.

### evalCondition grammar (decision.py)
The current `_eval_variable_condition()` regex only handles `<simple_identifier> <op> <literal>` where `simple_identifier = [A-Za-z_][A-Za-z0-9_]*`. It does NOT support:
- Dotted-path field access: `review.fields.verdict`
- Boolean conjunction: `&&`
- Boolean literals: `true`, `false`
- Hyphenated node IDs: `g-analysis`

### run_trace wiring (the P0 gap)
`executor.py:1005–1009`:
```python
# The executor does not cache RunTrace objects; the decision evaluator will
# fall through to the regex / variable layers.
run_trace: RunTrace | None = None
```
With `run_trace=None`: layers 2 (exit_reason) and 3 (regex) are skipped; layer 4 (variable) attempts `_eval_variable_condition("review.fields.verdict == 'pass'", scope)` but fails the regex (dotted path) and returns False. **Every conditional edge falls through to default.**

### delivery_status parser
The existing `parse_cronos_status_block` (fence: `` ```cronos_status ``) returns `(status, summary)` only and validates status ∈ `{DONE,WAIT,BLOCKED}`. The spec §8 `delivery_status` block (lowercase status, `fields` dict) has no parser.

### NodeState / RunState
`NodeState` has: `status`, `child_task_id`, `output`, `reason`, `started_at`, `ended_at`, `wake_at`. No `attempt` counter, no `prior_finding_ids` list.

---

## Requirements

### G3.1 — Loop convergence policy

**R1** — `HarnessNode.data` MUST support a `loop` sub-object with `until`, `stall[]`, `max`, and `on_exhaust` fields. The validator MUST NOT reject agent nodes carrying a recognized `loop` dict.

**R2** — The executor loop handler MUST exit on whichever fires first: (a) `until` evaluates True via `evalCondition`, (b) any stall signal fires, (c) `attempt == max`. The numeric `max` is a backstop only.

**R3** — The `recurring_findings` stall signal MUST fire when the F-id set from the current attempt is non-empty AND identical to the F-id set from the prior attempt. F-ids are persisted in `NodeState.prior_finding_ids`.

**R4** — The `no_diff_progress` stall signal MUST fire when `delivery_status.fields.diff_bytes` for the current attempt is not strictly less than the prior attempt's value. If `diff_bytes` is absent, the check is skipped.

**R5** — `on_exhaust='escalate'` MUST transition the run to `TaskState.WAITING` with a descriptive `waiting_question`. The run MUST NOT be silently marked done or failed.

**R6** — `NodeState` MUST gain `attempt: int = 0` and `prior_finding_ids: list[str] = []`, both persisting through `to_dict`/`from_dict`.

### G3.2 — evalCondition (sandboxed)

**R7** — `evalCondition` MUST parse dotted-path conditions `<node_id>.<field_path> <op> <literal>`, where `field_path ∈ {decision, status, fields.<name>}`, and `node_id` may contain hyphens.

**R8** — `evalCondition` MUST support `&&` conjunction of exactly two sub-expressions.

**R9** — `evalCondition` MUST support unquoted `true`/`false` boolean literals on the RHS.

**R10** — Expressions not matching the whitelist MUST log WARNING and return False. No `eval()`.

**R11** — All nine edge conditions in spec §12 worked example MUST evaluate correctly.

### G3.3 — Cronos run_trace wiring (P0)

**R12** — After each agent node completes, the executor MUST parse `delivery_status` from agent output and enrich scope: `scope["<node_id>.fields.<k>"]`, `scope["<node_id>.status"]`. The existing `scope[node_id] = final_text_snippet` MUST be preserved.

**R13** — A conditional edge on `review.fields.verdict == 'pass'` MUST demonstrably route to the pass branch when the upstream agent emits a matching `delivery_status`.

**R14** — A new `parse_delivery_status_block(text: str) -> dict | None` function MUST be added. It recognizes `` ```delivery_status `` fences, parses JSON, tolerates missing optional fields, and does NOT validate against `{DONE,WAIT,BLOCKED}`.

**R15** — A decision node with a matching condition-bearing edge MUST NOT follow the default edge.

---

## Acceptance criteria

See `traceability` header array — each row carries a `acceptance_criteria` list matched to its `requirement_id`. All 15 requirements verify in the `test` phase.

---

## Traceability

| Req | Source | Verifying phase |
|---|---|---|
| R1 | G3.1 | test |
| R2 | G3.1 | test |
| R3 | G3.1 | test |
| R4 | G3.1 | test |
| R5 | G3.1 | test |
| R6 | G3.1 | test |
| R7 | G3.2 | test |
| R8 | G3.2 | test |
| R9 | G3.2 | test |
| R10 | G3.2 | test |
| R11 | G3.2 | test |
| R12 | G3.3 | test |
| R13 | G3.3 | test |
| R14 | G3.3 | test |
| R15 | G3.3 | test |

---

## Assumptions

1. G0.3 (`delivery_status` format definition) is either already complete or will be finalized before G3.3 implementation begins. The format used here matches spec §8 verbatim.
2. The `delivery_status` fenced sentinel is distinct from `cronos_status` (different fence label); both can coexist in the same codebase without collision.
3. Dotted-path scope keys (e.g. `"review.fields.verdict"`) do not conflict with `interpolate.py`'s `Template.safe_substitute` — dots are not valid in Template identifiers, so dotted keys are safely invisible to interpolation.
4. F-ids (`"F-001"` etc.) are emitted by agents in `delivery_status.fields["finding_ids"]` (list of strings) or `delivery_status.fields["findings"]` (list of dicts with `"id"` keys). The loop handler extracts them from either form.
5. The `no_diff_progress` stall is best-effort for v1: agents that do not emit `diff_bytes` simply skip the check. G5.1 agent re-authoring will add it.

---

## Open questions

1. **Loop re-entry and resume reconciliation**: The outer-loop-wrapper approach (looping inside `_execute_agent_node` rather than re-enqueuing via BFS) avoids modifying BFS state. The architect should confirm this is preferred over a queue-level re-enqueue approach.
2. **F-id extraction heuristic**: Should `parse_delivery_status_block` extract F-ids from `fields.finding_ids` (list[str]) or `fields.findings` (list[{id:...}])? Recommend supporting both, precedence `finding_ids > findings[].id`.
3. **`&&` parsing boundary**: The evaluator splits on literal ` && `. A string literal containing ` && ` (e.g. `myvar == 'a && b'`) would break. This is not required by any §12 example; recommend documenting the limitation rather than solving it in v1.

---

## Next consumer brief

**Consumer:** `pipeline-architect` — design phase for `delivery-v1-control-flow`

**What to design:**

The architect receives 15 testable requirements across three independent workstreams (G3.1/G3.2/G3.3) with the following file scope:
- `backend/app/harnesses/executor.py` — loop handler + scope enrichment (G3.1 + G3.3)
- `backend/app/harnesses/decision.py` — evalCondition grammar extension (G3.2)
- `backend/app/harnesses/run_state.py` — NodeState extension (G3.1 R6)
- `backend/app/memory_parser.py` — delivery_status parser (G3.3 R14)

**Key design decisions for the architect:**

1. **Loop implementation strategy**: Recommend outer-loop-wrapper inside `_execute_agent_node` (loop entirely within a single BFS step) rather than re-enqueuing into the BFS queue. Avoids modifying cancel-race guards, resume logic, and BFS in-degree tracking.
2. **Scope key namespace**: Dotted-path keys (`"review.fields.verdict"`) coexist with existing flat keys (`"review"`) in `dict[str, str]` — no type change needed.
3. **evalCondition entry point**: Replace `_eval_variable_condition` with a new `eval_condition(condition, scope)` at the same call site in `edge_matches()`. Grammar: split on ` && `, then for each operand apply extended regex `[A-Za-z0-9_][A-Za-z0-9_.-]*\s+(==|!=|in)\s+...` (allows dots and hyphens in name).
4. **delivery_status parser**: Add `parse_delivery_status_block(text: str) -> dict | None` to `backend/app/memory_parser.py` alongside `parse_cronos_status_block`. Fence label: `` ```delivery_status ``.
5. **Scope enrichment timing**: After step 8 in `_execute_agent_node` (after `new_state == TaskState.DONE` check), call `parse_delivery_status_block(trace.final_text_snippet)` and populate dotted-path scope keys before returning.
6. **G3.3 is P0**: The architect should order iterations so G3.3 (delivery_status parser + scope enrichment + evalCondition dotted paths) lands first — it unlocks all routing and is the critical-path blocker for the whole control story.
