# `delivery/v1` — Portable Delivery Workflow Specification

> Status: draft for review. Canonical form is runtime-agnostic. The **executor
> interface** (§1) is the portability boundary — not the YAML. A workflow runs
> anywhere a conformant executor exists.

---

## 0. Principles (what makes this "mature")

1. **The interface is the boundary, not the file.** A YAML harness is declarative
   data; something must interpret it. Portability comes from a portable *executor*
   that implements §1, not from the YAML being present.
2. **One agent bundle.** The same `agents/ skills/ hooks/` run in every runtime,
   config-driven. No forked "standalone copy."
3. **Outcome gates ≠ schema gates.** A schema gate proves an artifact is
   *well-formed*. An outcome gate proves the *claim* — by re-executing it. A mature
   gate never trusts a self-reported pass.
4. **Loops converge, they don't count.** Exit on a pass-condition **or** a stall
   signal **or** a budget ceiling. The numeric cap is a backstop, not the policy.
5. **Traceability is a first-class artifact.** REQ→DD→TC→code→docs, machine-readable.
   It is what turns "based on previous outputs" into something a gate can verify and
   a controller can ripple-invalidate on.
6. **Telemetry is mandatory.** Every node emits `{tokens, usd, seconds}`. The budget
   kill-switch and the retro scorer both read it. (In Cronos v1 these are currently
   all zero — see §9; adopting the portable lib fixes that.)

---

## 1. The portability boundary — executor interface

A runtime is **conformant** iff it implements these operations. Cronos implements
them over its worker/task model; the standalone plugin implements them over CC
subagents + `/goal` + hooks. The spec and bundle never call a runtime directly —
only this interface.

```
dispatchAgent(agent_ref, inputs) -> AgentResult
    # Run one agent in isolation. Returns the structured return (§8), not prose.
    # AgentResult = { status, artifact_paths[], produces, fields{}, open_questions[], telemetry }

runGate(gate, artifact_paths) -> GateResult
    # Execute a gate's checks (§5). For outcome checks the runtime MUST re-execute,
    # never read a self-reported flag.
    # GateResult = { decision: proceed|needs_fix|fail|retry, errors[], evidence{} }

evalCondition(expr, scope) -> bool
    # Evaluate an edge/loop condition (§7) against a read-only scope of structured
    # returns + gate decisions. Sandboxed; no arbitrary code execution.

state.read() -> WorkflowState
state.write(patch) -> void
    # The manifest (§9). Append-only event log is written here too.

telemetry.emit(node_id, { tokens, usd, seconds }) -> void
    # Cumulative usd is what the budget ceiling reads.

escalate(node_id, reason) -> void
    # Hand control to a human checkpoint. Halts dependents until resolved.
```

Conformance is the whole portability story: pass a `delivery/v1` spec + bundle to
any object implementing these six, and it runs.

---

## 2. The bundle (what ships)

Repo-location-agnostic. Identical internals whether this sits at
`packages/delivery-workflow/` in the Cronos repo or in its own repo.

```
delivery-workflow/
├── delivery.workflow.yaml         # the spec instance (canonical graph, NO x/y editor cruft)
├── schemas/                       # JSON-Schema for each artifact class + for the spec itself
├── agents/                        # the single bundle: scout.md, …, doc-sync.md
├── skills/                        # gate, scaffold, traceability, write-memory, …
├── hooks/                         # PreToolUse / PostToolUse gate hooks (standalone runtime)
├── lib/state/                     # PORTABLE state.json + events.jsonl writer (both runtimes use)
├── lib/telemetry/                 # portable telemetry sink interface
├── runner/                        # the STANDALONE executor (implements §1 over CC + /goal + hooks)
├── adapters/cronos/               # the CRONOS executor (implements §1 over Cronos worker/tasks)
├── plugin.json                    # CC plugin manifest (agents+skills+hooks+runner)
└── pyproject.toml | package.json  # own manifest → enforces the import boundary
```

The **plugin** = `agents + skills + hooks + runner + spec`, installable as one unit.
The **Cronos embedding** = `agents + skills + spec + adapters/cronos`, consumed by the
existing worker.

---

## 3. Workflow spec schema

```yaml
apiVersion: delivery/v1
metadata:
  name: sdlc-delivery
  description: Spec/design → build → verify → docs, with bounded re-design loops.

defaults:
  models:                      # tiering is policy, overridable per node
    reasoning: opus
    build: sonnet
    recon: haiku
  budget:
    usd_ceiling: 25.0          # hard stop for the whole run; telemetry.emit drives it
    on_exceed: escalate        # escalate | fail

nodes:   [ … see §4 … ]
edges:   [ … see §7 … ]
traceability:                  # §10 — gate-checkable coverage requirements
  require: [ REQ->DD, DD->TC, TC->CODE, CODE->DOC ]
  artifact: traceability-matrix
```

---

## 4. Node kinds

Three kinds. (A Cronos `trigger` node maps to an `entry` here; the canonical form
drops editor-only fields like `position`.)

```yaml
# AGENT — judgment/generation in an isolated context
- id: analyze
  kind: agent
  agent: analyst
  model: { use: reasoning }            # resolves via defaults.models
  tools: [Read, Grep, Glob, Bash, Write]   # allowlist IS the guardrail (e.g. reviewer has no Edit)
  inputs: { from: [scout] }            # which upstream artifacts to read
  produces: { class: analysis }        # typed output → schemas/analysis.schema.json
  budget: { usd_ceiling: 3.0 }
  recon: off                           # optional — see §4.2; 'on' permits dispatching the scout subagent intra-node

# GATE — verification. See §5 for schema-vs-outcome.
- id: gate-analysis
  kind: gate
  checks:
    - { type: schema }                 # artifact well-formed (verify.py-style)
    - { type: traceability, of: REQ }  # every requirement has an id + acceptance
    - { type: acceptance }             # acceptance criteria present & well-formed
  on_fail: block                       # block (halt DAG) | retry_upstream

# HUMAN — checkpoint
- id: signoff-design
  kind: human
  prompt: "Right design? Approve to proceed to build."
  # gated by its incoming edge's `when:` (see §12) — a human gates like any node; no separate `on:`
```

---

## 4.1 Agent roster & I/O contract (sdlc-delivery)

For the worked example (§12). Every agent additionally emits the structured return
(`delivery_status`, §8) and appends to `state.json` + `events.jsonl` + telemetry via the
runtime — omitted per row. **Modifies** = existing project files the agent writes; its own
report is a *new* artifact, listed under Produces.

| Agent (stage) | Consumes — reads | Produces — new artifact | Modifies — existing files |
|---|---|---|---|
| **scout** (recon) | a `brief` (request distilled to an immutable research question) + injected memory context + codebase | `scout-report` (`research`) | — none (read-only) |
| **analyst** (analysis) | scout-report; feature request | `analysis-report` (`analysis`): `has_ui`, scope, requirements, acceptance, REQ-ids | — none |
| **frontend-designer** (design, only if `has_ui`) | analysis-report | `frontend` (mockups + FE spec) | — none |
| **architect** (detailed design) | analysis-report; FE spec (if UI); re-design loop: review findings | `design-report` (`design`): `iterations[]` DAG, DD-ids, `risks[]` | — none; re-design revises its own design-report |
| **test-architect** (test design) | design-report; acceptance | test suite + plan (`test`) | the test suite |
| **implementor** (build) | design-report — one `iterations[]` entry | `impl-report` (`implementation`): `files_changed` | source code (only writer of app source) |
| **reviewer** (review, loop) | the diff; design-report (scope) | `review-report--attempt{N}` (`review`): `verdict`, `finding_class`, `findings[]` | — none (no Edit tool) |
| **tester** (test exec, after review-pass, loop) | the test suite; built code | `test-report` (`test`): pass/fail, coverage; POSTs `TestReport` | — none (Read + Bash) |
| **doc-sync** (docs) | impl-report; design-report; code | `doc-report` (`doc`) | documentation files |

**Scout's input is a `brief`, not the raw request** — a request-derived research question, so
scout is request-scoped, not request-blind. Its two jobs: a mandatory memory-first preflight
(`memory_hits`) and targeted codebase recon, distilled into the report that grounds the analyst.

**The Modifies column is the guardrail map:** exactly three agents write existing files —
test-architect (tests), implementor (source), doc-sync (docs) — over disjoint trees. The two
agents that *judge* quality (reviewer, tester) modify nothing, so they cannot patch what they
evaluate. Tool-allowlist-as-guardrail, made explicit.

---

## 4.2 Recon-on-demand (intra-node, no routing leak)

The upfront `scout` node gives a *feature-level* map that grounds the analyst — but it is
generic to all downstream agents and goes **stale** as the build mutates the code. So `scout`
is **dual-purpose**: besides the upfront node, it is a **dispatchable recon subagent** (the
same agent in `agents/`, reached via the `Agent` tool) that selected agents call at their own
startup with a *task-specific* brief, getting back a fresh, focused map on a cheap model.

When a node sets `recon: on`, the runtime grants the scout-dispatch capability for that node
alone — so an agent's own `tools` list need not declare `Agent`, and the bundle agents stay
portable (the workflow, not the agent, decides who may recon).

Who gets it (`recon: on`), and why — the value is uneven:
- **implementor** — strongest case: runs per `iterations[]` entry against a *changing*
  codebase, so a fresh, iteration-scoped map each time is worth the cost.
- **reviewer** — moderate: a map of invariants / related code around the diff.
- **architect** — moderate, mainly on the **re-design** pass: see what the implementation
  actually did versus the design before reassessing.
- analyst (already consumes the upfront scout), frontend-designer, doc-sync, tester → `off`.

**The constraint that keeps this safe — recon is intra-node only:**
- its output is **transient working context** for the calling agent; it is **not** a gated
  store artifact and **not** a node in the DAG;
- it **must not** influence edges or routing — `evalCondition` never sees recon output; a
  recon call that changes *what runs next* is a spec violation;
- it **emits telemetry** (cost is visible and counts against the run budget) but produces no
  gated artifact. An optional transient map may be written under `recon/` for debugging,
  explicitly outside the gated artifact set.

Recon-inside-a-node is fine; recon-that-reroutes is not — this preserves deterministic
orchestration (control flow stays in the harness) while giving expensive agents fresh, cheap
grounding. Caveat: it *amplifies* the memory subsystem's importance, since task-specific
briefs retrieve more sharply than a feature-level one. Pattern precedent: the test-architect
already dispatches the tester via the `Agent` tool.

---

## 5. Gate semantics — schema vs outcome (the core maturation)

A gate runs an ordered list of **checks**. Two families:

| Check | Family | What it does | Trust model |
|---|---|---|---|
| `schema` | contract | Artifact validates against its class schema + cross-field/R-rules | reads the artifact header only |
| `traceability` | contract | Required id-links present and resolvable | reads the matrix |
| `acceptance` | contract | Acceptance criteria present, IDed, testable | reads the artifact |
| `build` | **outcome** | Re-runs the build; non-zero exit ⇒ fail | **re-executes; ignores reported flags** |
| `lint` / `types` | **outcome** | Re-runs linter / type-checker | re-executes |
| `test` | **outcome** | Re-runs the suite; reads the real runner exit + coverage | re-executes |
| `diff_vs_acceptance` | **outcome** | Checks the actual diff covers the claimed criteria | inspects the diff |
| `custom` | either | Project hook | declared |

**The rule that defines maturity:** an outcome check **must re-execute the claim**.
The v1 gate verifies an `impl-report`'s YAML header (`validation_command_passed: true`
is trusted as written) and only the separate `test` phase independently runs anything.
In `delivery/v1`, `runGate` re-runs the validation command and the suite itself, and a
review gate routes on the *verdict field inside the artifact*, not merely on the
artifact being well-formed. Schema-pass and outcome-pass are distinct decisions and are
never conflated.

`GateResult.decision ∈ { proceed, needs_fix, fail, retry }`. `proceed` advances;
`needs_fix` feeds a loop; `fail` escalates; `retry` means missing/unreadable input.

---

## 6. Loop semantics — convergence, not count

```yaml
- id: review
  kind: agent
  agent: reviewer
  tools: [Read, Grep, Glob, Bash, Write]   # no Edit — cannot patch mid-review
  loop:
    until: "review.fields.verdict == 'pass'"      # the success condition
    stall:                                         # ANY true ⇒ stalled ⇒ escalate
      - recurring_findings        # same F-ids resurface across attempts
      - no_diff_progress          # the diff stops shrinking between attempts
    max: 5                        # backstop only
    on_exhaust: escalate          # escalate | fail
```

Exit on `until` **OR** any `stall` signal **OR** the run-level `budget`. The numeric
`max` is a safety backstop, not the termination logic. (v1 terminates purely on
`attempt == 5`, with no stall detection — this replaces that.) Findings keep stable
F-ids across attempts so `recurring_findings` is computable.

---

## 7. Condition / edge language

Edges carry real conditions evaluated by `evalCondition` against a sandboxed,
read-only scope: `{ <node_id>.decision, <node_id>.fields.*, <node_id>.status }`.
No arbitrary code; a whitelist of comparisons + boolean logic only.

```yaml
edges:
  - { from: g-analysis,    to: signoff-scope, when: "g-analysis.decision == 'proceed'" }
  - { from: signoff-scope, to: frontend,      when: "analyze.fields.has_ui == true" }   # conditional branch
  - { from: review,        to: doc,       when: "review.fields.verdict == 'pass'" }
  - { from: review,        to: architect, when: "review.fields.verdict == 'needs_fix' && review.fields.finding_class == 'architectural'" }
  - { from: review,        to: implement, when: "review.fields.verdict == 'needs_fix' && review.fields.finding_class == 'local'" }
```

The branch on `verdict`/`finding_class` is the **triage** from the design graph: local
findings re-route to the implementor, architectural ones re-route to the architect.
This is exactly what v1's broken routing can't express — the Cronos executor passes
`run_trace=None`, so edge conditions can't see upstream output. Making `evalCondition`'s
scope real on the Cronos side is the unlock (a Cronos-adapter task, tracked separately).

---

## 8. Structured completion & structured return

Every node emits **two** outputs:

- the **durable artifact** (content) → the store, typed by `produces.class`;
- the **structured return** (control signal) → a fenced sentinel the runtime parses.

De-branded sentinel (the runner accepts it generically; the Cronos worker's existing
`cronos_status` parser is one conformant reader):

````
```delivery_status
{
  "status": "done | blocked | needs_fix | failed",
  "artifact_paths": ["…/design-report-…md"],
  "produces": "design",
  "fields": { "verdict": "needs_fix", "finding_class": "architectural", "has_ui": false,
              "req_ids_covered": ["REQ-001","REQ-002"] },
  "open_questions": [],
  "telemetry": { "tokens": 41233, "usd": 0.62, "seconds": 88 }
}
```
````

`fields` is the routing surface `evalCondition` reads. `telemetry` feeds `telemetry.emit`.
Free-text `STATUS:` lines are not part of `delivery/v1` (v1's gate skill still emits them
against an already-deprecated parser — de-brand and drop on migration).

---

## 9. State & telemetry (portable lib)

`state.json` manifest (a clean superset of v1's `pipeline-state.json`):

```jsonc
{
  "spec": "delivery/v1",
  "run_id": "…", "status": "running",
  "budget": { "usd_ceiling": 25.0, "usd_spent": 4.31 },   // kill-switch reads this
  "nodes": {
    "review": {
      "status": "looping", "attempt": 2,
      "gate": { "decision": "needs_fix", "errors": [] },
      "artifact_paths": ["…attempt2.md"],
      "telemetry": { "tokens": 41233, "usd": 0.62, "seconds": 88 }   // NON-zero, unlike v1
    }
  }
}
```

`events.jsonl` is the append-only log. The lib lives in the bundle (`lib/state/`,
`lib/telemetry/`) and **both runtimes use it** — which means Cronos *adopts* it,
incidentally fixing the dead-metrics bug (v1's `PhaseMetrics.from_trace` returns zeros
because no trace loads). Telemetry source differs per runtime behind `telemetry.emit`:
Cronos → trace store; standalone → CC usage / Agent SDK.

---

## 10. Traceability contract

A first-class artifact (`traceability-matrix`), not prose. Minimal row:

```
REQ-002  ->  DD-014  ->  [TC-007, TC-008]  ->  [backend/app/x.py, …]  ->  [docs/y.md]
```

Gates check the `traceability.require` links resolve. This is also the substrate for
**ripple/invalidation** (v2): when `DD-014` changes, look up everything referencing it,
mark stale, re-trigger exactly those nodes. (`traceability_mapping` is now properly
recognized as a canonical research strategy; the normalizer and verifier enums include it.)

---

## 11. The two runtimes (one interface, two implementations)

| Interface op | Cronos adapter (built first) | Standalone CC-plugin runner (deferred) |
|---|---|---|
| `dispatchAgent` | scaffold goal + agent task | CC subagent via Task tool |
| `runGate` | gate-task → `verify.py` **+ re-exec outcome checks** | hook + re-run cmd/tests |
| `evalCondition` | executor edge cond (**needs `run_trace` wired**) | runner branch on `fields` |
| `state.read/write` | `lib/state` → file (Cronos adopts) | `lib/state` → file |
| `telemetry.emit` | trace store → `lib/telemetry` | CC usage / SDK → `lib/telemetry` |
| `escalate` | task → waiting (`waiting_question`) | `/goal` exhaust → human prompt |

Standalone control loop = a `run-delivery` skill orchestrating subagents with `/goal`
per loop and hooks as gates — deliberately on the **GA substrate**, not Dynamic Workflows
(still a research preview). A dynamic-workflow backend for parallel fan-out is a later,
swappable implementation of the same interface.

---

## 12. Worked example — the SDLC workflow

```yaml
apiVersion: delivery/v1
metadata: { name: sdlc-delivery }
defaults:
  models: { reasoning: opus, build: sonnet, recon: haiku }
  budget: { usd_ceiling: 25.0, on_exceed: escalate }

nodes:
  - { id: scout,     kind: agent, agent: scout,     model: {use: recon},     produces: {class: research} }
  - { id: g-scout,   kind: gate,  checks: [{type: schema}] }

  - { id: analyze,   kind: agent, agent: analyst,   model: {use: build},     inputs: {from: [scout]},  produces: {class: analysis} }
  - { id: g-analysis,kind: gate,  checks: [{type: schema},{type: traceability, of: REQ},{type: acceptance}] }
  - { id: signoff-scope, kind: human, prompt: "Right thing to build?" }

  - { id: frontend,  kind: agent, agent: frontend-designer,  model: {use: build},     inputs: {from: [analyze]}, produces: {class: frontend} }   # reached only when has_ui
  - { id: architect, kind: agent, agent: architect, model: {use: reasoning}, inputs: {from: [analyze, frontend]}, produces: {class: design}, recon: on }   # frontend input only when has_ui; recon mainly for the re-design pass
  - { id: g-design,  kind: gate,  checks: [{type: schema},{type: traceability, of: DD}] }
  - { id: signoff-design, kind: human, prompt: "Right design?" }

  - { id: testarch,  kind: agent, agent: test-architect,     model: {use: reasoning}, inputs: {from: [architect]}, produces: {class: test} }

  - { id: implement, kind: agent, agent: implementor, model: {use: build}, tools: [Read,Edit,Write,Bash,Grep,Glob], inputs: {from: [architect]}, produces: {class: implementation}, recon: on }   # fresh per-iteration map of the changing code
  - { id: g-build,   kind: gate,  checks: [{type: build},{type: lint},{type: types}] }     # OUTCOME — re-executed

  - { id: review,    kind: agent, agent: reviewer,  model: {use: reasoning}, tools: [Read,Grep,Glob,Bash,Write],   # no Edit
      inputs: {from: [implement, architect]}, produces: {class: review}, recon: on,
      loop: { until: "review.fields.verdict == 'pass'", stall: [recurring_findings, no_diff_progress], max: 5, on_exhaust: escalate } }
  - { id: g-review,  kind: gate,  checks: [{type: schema},{type: diff_vs_acceptance}] }     # routes on verdict, not just well-formed

  - { id: testrun,   kind: agent, agent: tester,            model: {use: build}, tools: [Read,Bash], inputs: {from: [testarch]}, produces: {class: test} }
  - { id: g-tests,   kind: gate,  checks: [{type: test}],                                   # OUTCOME — real runner exit
      loop: { until: "g-tests.decision == 'proceed'", stall: [no_diff_progress], max: 3, on_exhaust: escalate } }

  - { id: doc,       kind: agent, agent: doc-sync, model: {use: recon}, inputs: {from: [implement]}, produces: {class: doc} }
  - { id: g-doc,     kind: gate,  checks: [{type: schema}] }
  - { id: release,   kind: human, prompt: "Sign-off to release." }

edges:
  - { from: scout,     to: g-scout }
  - { from: g-scout,   to: analyze,   when: "g-scout.decision == 'proceed'" }
  - { from: analyze,   to: g-analysis }
  - { from: g-analysis,to: signoff-scope, when: "g-analysis.decision == 'proceed'" }
  - { from: signoff-scope, to: frontend,  when: "analyze.fields.has_ui == true" }
  - { from: signoff-scope, to: architect, when: "analyze.fields.has_ui == false" }
  - { from: frontend,  to: architect }
  - { from: architect, to: g-design }
  - { from: g-design,  to: signoff-design, when: "g-design.decision == 'proceed'" }
  - { from: signoff-design, to: testarch }
  - { from: signoff-design, to: implement }
  - { from: implement, to: g-build }
  - { from: g-build,   to: review,    when: "g-build.decision == 'proceed'" }
  - { from: review,    to: g-review }
  - { from: g-review,  to: testrun,   when: "review.fields.verdict == 'pass'" }
  - { from: g-review,  to: implement, when: "review.fields.verdict == 'needs_fix' && review.fields.finding_class == 'local'" }
  - { from: g-review,  to: architect, when: "review.fields.verdict == 'needs_fix' && review.fields.finding_class == 'architectural'" }   # re-design loop
  - { from: testrun,   to: g-tests }
  - { from: g-tests,   to: doc,       when: "g-tests.decision == 'proceed'" }
  - { from: g-tests,   to: implement, when: "g-tests.decision == 'needs_fix'" }
  - { from: doc,       to: g-doc }
  - { from: g-doc,     to: release,   when: "g-doc.decision == 'proceed'" }

traceability:
  require: [ REQ->DD, DD->TC, TC->CODE, CODE->DOC ]
  artifact: traceability-matrix
```

---

## Open implementation questions (tracked, not decided)

- **Cronos `run_trace` wiring** for `evalCondition` — the routing unlock; its own P0.
- **Where the Cronos adapter lives** — `adapters/cronos/` in the bundle vs inside the
  Cronos backend (leaning: in the bundle, so the bundle stays the single source).
- **`diff_vs_acceptance`** — heuristic vs a structured criteria→diff mapping (start heuristic).
- **Ripple/invalidation** — explicitly v2; the traceability matrix is the prerequisite laid now.
