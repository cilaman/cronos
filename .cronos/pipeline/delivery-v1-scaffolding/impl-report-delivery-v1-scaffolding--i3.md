---
cc_version: "1.0"
agent: pipeline-implementor
slug: delivery-v1-scaffolding--i3
phase: impl
status: done
confidence: 0.95
inputs_used:
  - memory:delivery-v1-scaffolding-i2-done
  - .cronos/pipeline/delivery-v1-scaffolding/design-report-delivery-v1-scaffolding.md
  - .cronos/pipeline/delivery-v1-scaffolding/impl-report-delivery-v1-scaffolding--i2.md
  - docs/delivery-pipeline/delivery-v1-docs/delivery-v1-spec.md
  - packages/delivery-workflow/pyproject.toml
iteration_id: I3
files_changed:
  - packages/delivery-workflow/schemas/delivery.workflow.schema.yaml
  - packages/delivery-workflow/delivery.workflow.yaml
  - packages/delivery-workflow/spec_loader.py
  - packages/delivery-workflow/tests/test_spec_loader.py
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/delivery-v1-scaffolding/impl-report-delivery-v1-scaffolding--i3.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 12
  files_read: 6
  memory_hits: 2
  diff_lines_added: 650
  diff_lines_removed: 0
---

## Summary

I3 implements the workflow spec schema + loader layer for `packages/delivery-workflow/`. `schemas/delivery.workflow.schema.yaml` is a JSON Schema draft-07 schema covering the full `delivery/v1` spec vocabulary: top-level `apiVersion`/`metadata`/`defaults`/`nodes`/`edges`/`traceability`, plus `definitions` for `AgentNode` (required: id, kind, agent, produces; optional: model, tools, inputs, budget, recon, loop), `GateNode` (required: id, kind, checks; optional: on_fail, loop), `HumanNode` (required: id, kind, prompt), `LoopConfig`, and `Edge`. `delivery.workflow.yaml` is the §12 SDLC worked example (19 nodes across all three kinds, 23 edges with conditional `when:` clauses) that loads and validates clean. `spec_loader.py` exposes `load_spec(path)` and `loads_spec(text)` — both validate via `jsonschema.Draft7Validator`, raising `ValueError` with a descriptive error list on failure. All 19 tests in `test_spec_loader.py` pass, pinning both directions: the §12 example validates clean, and eight distinct malformed copies (missing required fields, wrong `apiVersion`, bad node kind, bad check type, bad `on_exceed`) are each rejected with a non-empty error message.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| packages/delivery-workflow/schemas/delivery.workflow.schema.yaml | created | +223 / 0 | JSON Schema draft-07 for `delivery/v1` spec instances; validates apiVersion, metadata, nodes (oneOf agent/gate/human), edges, traceability |
| packages/delivery-workflow/delivery.workflow.yaml | created | +168 / 0 | §12 SDLC worked example: 19 nodes (agent/gate/human), 23 edges, defaults.budget, loop configs on review and g-tests nodes |
| packages/delivery-workflow/spec_loader.py | created | +52 / 0 | `load_spec(path)`, `loads_spec(text)`, `_validate(data)` — lazy-cached schema load + `Draft7Validator`; descriptive `ValueError` on any schema violation |
| packages/delivery-workflow/tests/test_spec_loader.py | created | +207 / 0 | 19 tests: 6 happy-path (§12 validates, structure, string-roundtrip) + 13 rejection (missing/wrong apiVersion, metadata, nodes, edges, bad kind, bad check type, missing required fields per kind, bad on_exceed) |

## Out-of-scope findings

- None.

## Assumptions

- `recon: on` / `recon: off` in YAML is parsed by pyyaml as boolean (`True`/`False`) per YAML 1.1 booleans. The schema defines `recon: {type: boolean}` accordingly. The worked example uses unquoted `recon: on` which correctly becomes `True` after `yaml.safe_load`.
- `jsonschema.Draft7Validator` is used explicitly (rather than `jsonschema.validate`) to preserve all validation errors for multi-error reporting via `iter_errors()`, giving callers a complete error list rather than a stop-at-first error.
- The `definitions` key is used (not `$defs`) per JSON Schema draft-07 conventions supported by jsonschema 4.x.
- The schema caches the loaded dict in `_schema` module-level to avoid re-reading from disk on every call; the cache is process-scoped (safe for test reuse since the schema is read-only).
- `additionalProperties: false` is set on all named node schemas to ensure that nodes from one kind do not accidentally match another kind's schema — critical for the `oneOf` discriminator on `kind` to be unambiguous.
- The `checks[].type` enum covers all check types shown in §5 (schema, traceability, acceptance, build, lint, types, test, diff_vs_acceptance, custom); the `of` field is an unconstrained string to allow any traceability arc identifier (REQ, DD, TC, etc.).

## Open questions

- None.

## Next consumer brief

Rerun: `cd packages/delivery-workflow && python -m pytest tests/test_spec_loader.py -v` — 19 tests, all green. Key invariant for downstream I4: the schema validates `produces.class` as an unconstrained string (any artifact class is valid at the spec level); I4 provides the per-class schemas that constrain what each class's `delivery_status.fields` must contain. The spec loader is intentionally separate from the artifact-class schemas — a workflow spec is valid even if it references class names that don't yet have a per-class schema.
