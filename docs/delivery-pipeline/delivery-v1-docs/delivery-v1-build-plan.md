# delivery/v1 — Build Plan (Cronos goal tree)

> Sequenced **foundation before capability**, **contracts before implementations**. Each goal
> carries acceptance criteria as checkboxes. Bakes in the settled forks.

| Field | Value |
|---|---|
| Spec | `delivery/v1` — see `delivery-v1-spec.md` |
| Home | `packages/delivery-workflow/` (in the Cronos repo; extract to its own repo on standalone-runner / 2nd consumer) |
| Bundle | single, config-driven, behind the executor interface (one copy, both runtimes) |
| Runtime priority | Cronos adapter **first**; standalone runner deferred |
| Canonical form | clean `delivery/v1` spec; the visual harness editor is a projection of it |
| Milestone (done) | **G6.2** — the worked SDLC example runs end-to-end on the Cronos runtime |
| Exemplar (done) | `reviewer` agent + `code-review` skill (the harvest-then-author mold) |

**Critical path to G6.2:** G0.1 → G0.3 → G1.1 → G2.1 → G2.2 → G3.1 → G3.3 → G6.1 → G6.2.
**Parallelizable off the critical path:** agent re-authoring (G5.x) needs only the contracts
(G0.3); it can run alongside the engine work (Phases 2–4). Traceability (Phase 4) and the
Cronos metrics adoption (G1.3) feed the milestone but don't block the engine.

---

## Phase 0 — Scaffolding & contract

**G0.1 · Package skeleton + import boundary** — *depends: none*
The home for everything, with the decoupling guarantee made physical (fork 5).
- [ ] `packages/delivery-workflow/` exists with its own manifest and the layout from spec §2
- [ ] CI import-linter rule fails the build if the package imports `app.*` / any Cronos internal
- [ ] CI green on the empty-but-structured package

**G0.2 · Executor interface (6-op protocol)** — *depends: G0.1*
The portability boundary as a contract (spec §1).
- [ ] protocol defines `dispatchAgent · runGate · evalCondition · state.read/write · telemetry.emit · escalate` with typed signatures
- [ ] `AgentResult` / `GateResult` / `WorkflowState` types defined
- [ ] a `NullRuntime` stub implements the protocol (compiles; raises NotImplemented) for tests

**G0.3 · Spec loader + schemas + return parser** — *depends: G0.1*
- [ ] JSON-Schema for `delivery.workflow.yaml`; loader rejects malformed specs with clear errors
- [ ] artifact-class schemas: research / analysis / design / frontend / implementation / review / test / doc
- [ ] de-branded `delivery_status` fenced-block parser (the Cronos `cronos_status` reader is one conformant consumer)
- [ ] the worked example (§12) loads and validates clean

---

## Phase 1 — Foundation: state & telemetry  *(everything downstream reads this)*

**G1.1 · `lib/state`** — *depends: G0.2, G0.3*
- [ ] `state.read()` / `state.write(patch)` implement the interface ops over a file
- [ ] `events.jsonl` append-only log; every node transition recorded
- [ ] state shape matches spec §9 (nodes, gate result, attempt, budget, telemetry)
- [ ] **resume**: a half-finished run reconstructs from `state.json` without re-running completed nodes

**G1.2 · `lib/telemetry`** — *depends: G0.2*
- [ ] `telemetry.emit(node, {tokens, usd, seconds})` implements the interface op
- [ ] cumulative `usd_spent` maintained; the budget ceiling is readable
- [ ] a budget breach surfaces a signal the harness can act on

**G1.3 · Cronos adopts the lib — fixes the dead-metrics bug** — *depends: G1.1, G1.2*
> v1's `pipeline-state.json` metrics are all zero (`PhaseMetrics.from_trace` gets no trace). This kills that.
- [ ] a real Cronos pipeline run shows **non-zero** `duration_s` / `usd` / `tokens` / `tool_calls` in state
- [ ] retro's `efficiency` scoring reads real numbers, not zeros
- [ ] the worker-side budget kill-switch has live `usd` to read

---

## Phase 2 — Gates  *(the core maturation)*

**G2.1 · `runGate` + contract checks** — *depends: G0.3, G1.1*
- [ ] `runGate` returns `{decision, errors, evidence}` (spec §5)
- [ ] schema / traceability / acceptance checks pass/fail correctly on fixtures
- [ ] decision ∈ {proceed, needs_fix, fail, retry}; written to state

**G2.2 · Outcome checks (re-execute the claim)** — *depends: G2.1* — **highest leverage**
> Confidence: high on build/lint/test; **medium on `diff_vs_acceptance`** (hard to make deterministic — start heuristic, document its limits).
- [ ] build / lint / types / test checks run the **real toolchain** and gate on exit code
- [ ] a self-reported `validation_command_passed: true` over a genuinely failing build is **caught**
- [ ] `g-review` routes on the `verdict` field, not merely on artifact well-formedness
- [ ] `diff_vs_acceptance` has a first heuristic, with its limits written down

---

## Phase 3 — Control: convergence loops + routing

**G3.1 · Loop policy (convergence, not count)** — *depends: G1.1, G2.1*
- [ ] a loop exits on its `until` condition, on a `stall` signal, or on `budget` — whichever fires first
- [ ] `recurring_findings` detected via stable F-ids; `no_diff_progress` via diff size between attempts
- [ ] `on_exhaust` escalates (never silently ships); `max` is a backstop only

**G3.2 · `evalCondition` (sandboxed)** — *depends: G0.3*
- [ ] evaluates spec §7 conditions (`verdict == pass`, `has_ui == true`, `finding_class == architectural`, …)
- [ ] sandboxed: comparisons + boolean logic over allowed fields only; rejects anything else
- [ ] every edge in the worked example evaluates

**G3.3 · Cronos `run_trace` wiring (routing unblock)** — *depends: G3.2* — **P0**
> v1's executor passes `run_trace=None`, so conditional edges can't see agent output — routing is inert.
- [ ] the Cronos executor passes the upstream structured return into `evalCondition`
- [ ] a conditional edge (route on review verdict) demonstrably branches on real output
- [ ] the harness `condition` field is no longer dead

---

## Phase 4 — Traceability

**G4.1 · `traceability-matrix` artifact** — *depends: G0.3*
- [ ] matrix schema + an emitted matrix on a real run
- [ ] ids flow: REQ (analysis) → DD (design) → TC (tests) → paths (impl) → docs (doc)
- [ ] normalize no longer **drops** `traceability_*` strategies (the v1 enum gap closed)

**G4.2 · Traceability gate checks** — *depends: G4.1, G2.1*
- [ ] the check fails when a required link (REQ→DD, DD→TC, …) is missing
- [ ] `g-analysis` (trace REQ) and `g-design` (trace DD) enforce coverage
- [ ] this is the substrate for ripple/invalidation (explicitly v2)

---

## Phase 5 — Agents (harvest-then-author) + recon  *(parallelizable from Phase 2 on)*

**G5.1 · Agent re-authoring — thin agent + paired skill, decoupled** — *depends: G0.3 (contracts), G3.1 (loops own what agents shed)*
- [x] `reviewer` + `code-review` skill — the exemplar/mold (401 → 63 + 100 lines)
- [ ] `implementor` + `architect` (the heavy, coupled ones) authored next
- [ ] `scout`, `analyst`, `frontend-designer`, `test-architect`, `tester`, `doc-sync` authored
- [ ] every agent: **no** `.cronos` paths / Cronos API / `verify.py` / `STATUS:` sentinel; emits `delivery_status`; carries **no** loop or routing logic
- [ ] each agent ≤ ~80 lines; the verbose craft lives in a paired skill

**G5.2 · Recon capability (intra-node)** — *depends: G5.1, G3.2*
- [ ] `scout` dispatchable via the `Agent` tool with a task brief; returns a transient map
- [ ] recon output is **not** a gated artifact and **not** a DAG node
- [ ] lint/assert: **no edge condition references recon output** (recon can never reroute)
- [ ] recon emits telemetry (cost visible, counts to budget)

---

## Phase 6 — Cronos runtime & end-to-end  *(Cronos-first)*

**G6.1 · Cronos adapter — the 6 ops over the worker/task model** — *depends: G1.3, G2.2, G3.1, G3.3*
- [ ] all six interface ops implemented over Cronos (spec §11 table)
- [ ] `dispatchAgent` scaffolds goal+tasks with `depends_on`; `runGate` → gate-task + verify + outcome re-exec
- [ ] state/telemetry via `lib/`; `escalate` → task `waiting`

**G6.2 · End-to-end SDLC run — MILESTONE** — *depends: G4.2, G5.2, G6.1*
- [ ] a feature request runs scout → … → release with gates, loops, the `has_ui` branch, and human checkpoints
- [ ] a review `needs_fix · architectural` routes to the architect; `local` routes to the implementor (**real routing**)
- [ ] an outcome-gate failure (failing build/test) blocks and loops correctly
- [ ] `state.json` + `events.jsonl` reconstruct the full run; budget respected
- [ ] **=== delivery/v1 done on Cronos ===**

---

## Phase 7 — Deferred (later, explicitly)

**G7.1 · Standalone CC-plugin runner** — *depends: G6.2*
> Confidence: medium — keep on the **GA substrate** (`/goal` + hooks); add a dynamic-workflow backend for parallel fan-out later.
- [ ] the six ops implemented standalone (subagents + `/goal` + hooks); the **same bundle** runs unchanged
- [ ] the worked example runs outside Cronos with the YAML present (no visual editor)

**G7.2 · Plugin packaging + repo extraction** — *depends: G7.1*
- [ ] `plugin.json` bundles agents + skills + hooks + runner + spec; `claude plugin install` works
- [ ] `git subtree split` extracts `packages/delivery-workflow/` with history (the fork-5 trigger)

---

## Risks to watch (carry into the relevant goals)

- **G2.2 `diff_vs_acceptance`** — the one outcome check that may resist determinism. If it can't be made meaningful, it's theatre; demote it to advisory rather than gating.
- **G3.3 `run_trace`** — until this lands, *no* conditional routing works in Cronos; it gates the whole control story, so treat it as a true P0, not a Phase-3 nicety.
- **G7.1 standalone on a preview** — do not let portability depend on Dynamic Workflows (research preview); GA substrate first.
- **Memory subsystem** (not a goal here, but adjacent) — recon's value (G5.2) and scout's value are contingent on it; its known bugs (boost-from-zero, decay-never-called, title-only retrieval) cap the payoff until fixed.
