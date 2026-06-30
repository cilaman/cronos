# delivery-workflow — User Documentation

User-facing documentation for the **delivery/v1** pipeline: a portable, multi-agent
system that takes a feature request through research → design → build → verify → docs,
with deterministic gates and human sign-offs between phases.

This is the companion to the package [`README.md`](../README.md) (which is reference-level
material on the executor protocol and internal types). Start here if you want to *use* the
pipeline rather than read the source.

## Pick your reading path

| You want to… | Read |
|---|---|
| Understand what the pipeline is and how a run flows | [User Guide → Part 1: Concepts](USER_GUIDE.md#part-1--concepts) |
| Kick off a delivery and shepherd it through the gates | [User Guide → Part 2: Operating a pipeline](USER_GUIDE.md#part-2--operating-a-pipeline) |
| Write or customize your own `delivery.workflow.yaml` | [User Guide → Part 3: Authoring a workflow](USER_GUIDE.md#part-3--authoring-a-workflow-spec) |
| Run delivery/v1 on a *new* runtime (not Cronos) | [User Guide → Part 4: Integrating a runtime](USER_GUIDE.md#part-4--integrating-a-runtime) |
| Look up an agent, gate check, artifact class, or condition operator | [Reference](reference.md) |

## At a glance

- **9 agents** across five stages — scout, analyst, frontend-designer, architect,
  test-architect, implementor, reviewer, tester, doc-sync.
- **Gates** between every agent — deterministic checks (schema, traceability, build, lint,
  types, tests) that the runtime *re-executes*; it never trusts an agent's self-report.
- **Human sign-offs** at three points — scope, design, and release.
- **Convergence loops** — the review and test phases repeat until they pass or stall.
- **Budget ceiling** — per-node token/USD telemetry; breaching the ceiling escalates to a human.
- **Portable** — the agents, skills, and the workflow spec carry no runtime-specific paths.
  Today the pipeline runs on **Cronos**; any runtime that implements the 6-operation executor
  interface can run it.

> **Status note.** The **Cronos runtime is shipped and verified** (an end-to-end SDLC run
> from scout to release). The **standalone runner is a future phase** — see
> [Part 4](USER_GUIDE.md#part-4--integrating-a-runtime). Where this matters, the guide says so.
