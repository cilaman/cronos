---
name: design
description: Method for decomposing requirements into an implementation DAG — DAG composition rules, depends_on topological validation, DD-id assignment, risk register method, and recon invocation pattern. Loaded by the architect agent.
---

# design

How to design an implementation DAG. The `architect` agent owns the role and the hard rules; this skill owns the method.

## 0. Recon pass (when prior_design is present)
When re-designing after a review finding of class `architectural`, invoke scout before proceeding:
```
result = Agent("scout", brief="<one-sentence question about the design gap identified in the review>")
# Treat result as transient grounding context ONLY — do not add to artifact_paths
# Emit telemetry: telemetry.emit({tokens: ..., usd: ..., seconds: ...})
```
This is granted by `recon: on` in the workflow node; do NOT add `Agent` to the agent's `tools` list.
See `packages/delivery-workflow/recon/README.md` for the full isolation contract.

## 1. Memory-first preflight
Scan injected memory before reading any file. Prior design decisions and architectural standards are binding constraints.

## 2. Establish the requirement set
From the analysis artifact: extract every REQ-id and its acceptance criteria. These are the scope — every design decision must trace to at least one REQ.

## 3. Compose the iteration DAG
For each coherent unit of work:
1. Create an `iterations[]` entry with a unique `id` (I1, I2, ...).
2. Set `type` (infra | backend | frontend | test | doc).
3. Set `scope_files[]` — the **complete** list of files the implementor may touch. This is a hard boundary.
4. Set `depends_on[]` — ids of iterations that must complete before this one begins.
5. Write a `validation_command` that verifies the iteration in isolation.
6. Set `max_diff_lines` — the expected size budget.

**DAG validity rules:**
- No cycles (verify by topological sort).
- No self-loops.
- Every id in any `depends_on[]` exists in `iterations[]`.
- The DAG has at least one root (iteration with empty `depends_on`).

## 4. Assign DD-ids
For each material design decision (tech choice, boundary, interface, tradeoff), write a `DD-NNN` record:
- `id`: DD-NNN (zero-padded, sequential)
- `statement`: the decision, one sentence
- `rationale`: why this over the alternative
- `tradeoffs`: what you give up

Every DD must trace to at least one REQ-id.

## 5. Write the risk register
For each identified risk:
- `description`: what could go wrong
- `severity`: critical | high | medium | low
- `mitigation`: concrete action to reduce the risk

Minimum one risk per design. No risks listed = a likely incomplete risk search.

## 6. Traceability cross-check
Before emitting:
- [ ] Every REQ-id appears in at least one iteration's rationale or scope.
- [ ] Every DD traces to at least one REQ.
- [ ] `iterations_count` in delivery_status matches `len(iterations[])`.
- [ ] `risks_count` matches `len(risks[])`.
- [ ] `dd_ids[]` matches the full set of DD-NNN ids in the artifact.
