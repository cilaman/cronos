# delivery/v1 — Reference

Lookup tables for the delivery-workflow package. For narrative explanation, see the
[User Guide](USER_GUIDE.md).

## Agents

The bundle in [`../agents/`](../agents). Each agent is a thin role + I/O contract; its method
lives in a paired [skill](../skills).

| Agent | Tier | Consumes | Produces (class) | Modifies | Paired skill |
|---|---|---|---|---|---|
| `scout` | Haiku | brief + memory + codebase | `research` | — | — |
| `analyst` | Sonnet | scout report | `analysis` (sets `has_ui`, REQ-ids) | — | `analysis` |
| `frontend-designer` | Sonnet | analysis report | `frontend` | — | `frontend` |
| `architect` | Opus | analysis + FE spec | `design` (DD-ids, `risks[]`) | — | `design` |
| `test-architect` | Opus | design report | `test` (TC-ids) | test files | `test-design` |
| `implementor` | Sonnet | one design iteration | `implementation` | source code | `implement` |
| `reviewer` | Opus | design + impl diff | `review` (verdict, findings) | — | `code-review` |
| `tester` | Sonnet | test suite + built code | `test` | — | — |
| `doc-sync` | Haiku | impl + design + code | `doc` | doc files | `doc` |

Only `test-architect`, `implementor`, and `doc-sync` may edit project files. `reviewer` and
`tester` have **no edit capability** by design.

### Tool allowlists (exact — no wildcards)

| Agent | Tools |
|---|---|
| `scout` | Read, Grep, Glob, Bash |
| `analyst` | Read, Grep, Glob, Bash, Write |
| `frontend-designer` | Read, Grep, Glob, Bash, Write |
| `architect` | Read, Grep, Glob, Bash, Write |
| `test-architect` | Read, Edit, Write, Bash, Grep, Glob |
| `implementor` | Read, Edit, Write, Bash, Grep, Glob |
| `reviewer` | Read, Grep, Glob, Bash, Write |
| `tester` | Read, Bash |
| `doc-sync` | Read, Glob, Bash, Write |

`recon: on` (the node grants the `scout` subagent at startup) applies to `architect`,
`implementor`, and `reviewer`. `Agent` is **never** in an agent's own `tools` list.

## Artifact classes & schemas

Each artifact class has a JSON schema in [`../schemas/`](../schemas) that the `schema` gate
validates against.

| Class | Schema | Emitted by |
|---|---|---|
| `research` | `research.schema.yaml` | scout |
| `analysis` | `analysis.schema.yaml` | analyst |
| `frontend` | `frontend.schema.yaml` | frontend-designer |
| `design` | `design.schema.yaml` | architect |
| `implementation` | `implementation.schema.yaml` | implementor |
| `review` | `review.schema.yaml` | reviewer |
| `test` | `test.schema.yaml` | test-architect, tester |
| `doc` | `doc.schema.yaml` | doc-sync |

The workflow spec itself validates against `delivery.workflow.schema.yaml`.

## `node_status` block (primary) & `delivery_status` (legacy)

Every agent ends with a `node_status` fenced block (the primary routing surface; `delivery_status` also fully supported for backward compatibility):

````
```node_status
{
  "status": "done | blocked | needs_fix | failed",
  "produces": "research | analysis | design | implementation | review | test | doc | frontend",
  "artifact_paths": ["<runtime-given path>"],
  "fields": { ... },              // only the keys this node's routing needs
  "open_questions": [],
  "telemetry": { "tokens": 0, "usd": 0.0, "seconds": 0 }
}
```
````

Common `fields` keys:

| Key | Used by | Meaning |
|---|---|---|
| `has_ui` | analyst | drives the frontend branch |
| `verdict` | reviewer, gates | `pass` / `needs_fix` |
| `finding_class` | reviewer | `local` (→ implementor) or `architectural` (→ architect) |
| `req_ids_covered` / `dd_ids_covered` | analyst, design | traceability ids |
| `files_changed` | implementor | changed file paths |
| `validation_command_passed` | implementor | build/test exit ok |
| `coverage_pct` | tester | test coverage |

## Workflow spec schema

Top-level keys (full schema: [`../schemas/delivery.workflow.schema.yaml`](../schemas/delivery.workflow.schema.yaml)):

| Key | Required | Notes |
|---|---|---|
| `apiVersion` | ✓ | must equal `delivery/v1` |
| `metadata.name` | ✓ | `description` optional |
| `defaults.models` | — | `reasoning` / `build` / `recon` tier aliases |
| `defaults.budget` | — | `usd_ceiling` (required if present), `on_exceed`: `escalate`\|`fail` |
| `nodes` | ✓ | ≥1; each is an Agent / Gate / Human node |
| `edges` | ✓ | `from`, `to`, optional `when` |
| `traceability` | — | `require: [...]`, `artifact: "..."` |

### Node kinds

| Kind | Required fields | Optional fields |
|---|---|---|
| `agent` | `id`, `kind`, `agent`, `produces.class` | `model.use`, `tools[]`, `inputs.from[]`, `recon`, `loop`, `budget.usd_ceiling` |
| `gate` | `id`, `kind`, `checks[]` (≥1) | `on_fail`: `block`\|`retry_upstream`, `loop` |
| `human` | `id`, `kind`, `prompt` | — |

### Gate check types

`schema`, `traceability` (with `of:`), `acceptance`, `build`, `lint`, `types`, `test`,
`diff_vs_acceptance`, `custom`.

### Loop config

| Field | Required | Notes |
|---|---|---|
| `until` | ✓ | condition expression |
| `stall` | — | stall signals, e.g. `recurring_findings`, `no_diff_progress` |
| `max` | — | attempt ceiling (≥1) |
| `on_exhaust` | — | `escalate` \| `fail` |

## Condition grammar (`when` / `loop.until`)

- Identifiers: dotted (`analyze.fields.has_ui`) and hyphenated (`g-scout.decision`).
- Operators: `==`, `!=`, `in`.
- Conjunction: `&&`. Grouping: parentheses.
- Every root identifier must resolve to a node `id`. Referencing recon output is a lint error
  (R11, [`../recon_lint.py`](../recon_lint.py)).

## State files (per run directory)

| File | Contents |
|---|---|
| `state.json` | `WorkflowState`: `spec`, `run_id`, `status`, `budget`, `nodes{}` (per-node `status`, `attempt`, `artifact_paths`, `gate`). Atomic writes. |
| `events.jsonl` | Append-only node-transition log for audit/replay. |

**Resume policy:** `done` → skip · `failed`/torn → re-dispatch · absent → dispatch.

## Host surface (for integrators)

[`../src/delivery_workflow/interface.py`](../src/delivery_workflow/interface.py) — the two ports
(R10b), driven through the `DeliveryRun` facade:

| Member | Signature |
|---|---|
| `NodeExecutor.dispatchAgent` | `(agent_ref, inputs) -> AgentResult` |
| `NodeExecutor.runGate` | `(gate, artifact_paths) -> GateResult` |
| `NodeExecutor.runExec` | `(node_id, command, inputs) -> ExecResult` |
| `HostPort.on_event` | `(event: RunEvent) -> None` (optional; `NullHost` ignores) |
| `StateOps` | `read() -> WorkflowState`, `write(patch: dict) -> None` |
| `TelemetryOps` | `emit(node_id: str, data: dict[str, float]) -> None` |

Edge/loop conditions are runner-internal (`lib.conditions`); `evalCondition` and `escalate`
left the executor surface in R10b.

Result types ([`../src/delivery_workflow/results.py`](../src/delivery_workflow/results.py)):

- `AgentResult(status, artifact_paths, produces, fields, open_questions, telemetry)` —
  `status` ∈ `done | blocked | needs_fix | failed` (`AGENT_STATUS_VOCAB`; close it with
  `agent_result_from_envelope`).
- `GateResult(decision, errors, evidence={})` — `decision` ∈ `proceed | needs_fix | fail | retry`.
- `ExecResult(status, exit_code, stdout_tail, artifact_path, produces)` — `status` ∈ `done | failed`.
- `TelemetryData(tokens, usd, seconds)`.

## Commands

```bash
# Install (editable, with dev deps)
cd packages/delivery-workflow && pip install -e ".[dev]"

# Run the test suite
pytest tests/ -v

# Enforce the import boundary
lint-imports

# Validate a workflow spec
python -c "from spec_loader import load_spec; load_spec('delivery.workflow.yaml')"
```
