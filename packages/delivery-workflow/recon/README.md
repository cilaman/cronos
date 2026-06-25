# Recon isolation contract

This file is the single source of truth for the **recon-on-demand** capability
(delivery/v1 §4.2). It is referenced by the `design`, `implement`, and `code-review`
skills — the three nodes that carry `recon: on`.

## What recon is

Recon is an intra-node invocation of the `scout` agent for a **transient**, focused
research map. It answers a single iteration-scoped or diff-scoped question before the
calling node starts its main work. It is **not** a DAG node, **not** a gated artifact,
and **never** visible to `evalCondition`.

## Invocation pattern

```python
result = Agent("scout", brief="<one-sentence research question scoped to this iteration/diff>")
# result is transient grounding context — do NOT add it to artifact_paths
telemetry.emit({"tokens": ..., "usd": ..., "seconds": ...})
```

This pattern appears verbatim in the `design`, `implement`, and `code-review` skills.

## Who can invoke recon

Only nodes that declare `recon: on` in the workflow spec. The runtime grants `Agent`
tool access for that node alone. **Do not add `Agent` to an agent's `tools:` list.**

## What recon output is

- Transient working context for the calling node in its current run.
- Optionally written to `recon/<node-id>-<timestamp>.md` for debugging — this path is
  **excluded from the gated artifact set**.
- Telemetry from the recon call is attributed to the parent node and counts against its
  `budget.usd_ceiling`.

## What recon output is NOT

- A gated artifact (not in `artifact_paths`).
- A DAG node (no `id` in `nodes[]`).
- Visible to `evalCondition` — any edge condition referencing recon output is a lint
  error (see `../recon_lint.py`).

## R11 lint rule

Every root identifier in an `edges[].when` string must resolve to a node id from
`nodes[*].id`. Since recon output has no node id, any attempt to reference it in an
edge condition fails this check with a clear error message.

Reference implementation: `packages/delivery-workflow/recon_lint.py`.
Test: `packages/delivery-workflow/tests/test_recon_edge_lint.py`.
