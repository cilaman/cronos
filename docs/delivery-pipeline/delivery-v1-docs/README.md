# delivery/v1 — Design Documentation Package

A portable IT-delivery workflow built on Claude Code — usable inside Cronos *and* standalone as
a plugin. This is the complete, validated design set.

**Status:** internally consistent as of June 2026. Cross-checked for agent names, verdict
values, interface-op names, human-gating, `finding_class`, and the control-vs-data edge
distinction. Superseded v0 material is intentionally excluded.

---

## What's here — and the order to read it

**1. `delivery-v1-spec.md`** — the canonical specification (single source of truth). Executor
interface, bundle layout, workflow schema, node kinds, the agent I/O contract (§4.1),
recon-on-demand (§4.2), schema-vs-outcome gates, convergence loops, the condition language,
structured completion, state/telemetry, traceability, the two runtimes, and a full worked SDLC
example (§12). **Read first.**

**2. `delivery-v1-build-plan.md`** — the phased Cronos goal tree (foundation-first), each goal
with acceptance-criteria checkboxes, the critical path, and the risk register. The actionable
roadmap. **Read second.**

**3. Diagrams** (black-and-white Mermaid; open in any Mermaid viewer):
- `delivery-v1-architecture.mermaid` — the layers: spec + bundle -> executor interface ->
  Cronos and standalone runtimes (the portability boundary).
- `delivery-v1-runtime-flow.mermaid` — a delivery run's control flow: control-vs-data edges,
  outcome gates, convergence loops, human gates.
- `delivery-v1-execution-sequence.mermaid` — the executor driving one loop node through the six
  interface ops.

**4. `delivery-workflow/`** — the agent bundle, in its real directory layout:
- `agents/reviewer.md` — the thin, decoupled reviewer (the harvest-then-author exemplar: 401
  v1 lines -> 63).
- `skills/code-review/SKILL.md` — the paired craft skill the reviewer loads.

The other eight agents are **not yet authored**; `reviewer` is the mold they follow
(build-plan G5.1).

---

## Decisions baked in (the settled forks)

- Canonical form is this clean `delivery/v1` spec; the Cronos visual harness editor becomes a
  *projection* of it.
- **One** config-driven agent bundle behind the executor interface (one copy, both runtimes).
- **Cronos runtime first**; the standalone plugin runner is deferred.
- The package lives at `packages/delivery-workflow/` inside the Cronos repo now, with a CI
  import-boundary rule; extract to its own repo when the standalone runner ships or a second
  consumer appears.

---

## Open risks to verify early (from the build plan)

- **Cronos `run_trace` wiring (P0)** — until edges can see upstream output, no conditional
  routing works in Cronos. (G3.3)
- **`diff_vs_acceptance`** — the one outcome gate that may resist determinism; demote to
  advisory if it can't be made meaningful. (G2.2)
- **Memory subsystem** — recon and scout's value is capped by its known bugs (boost-from-zero,
  decay-never-called, title-only retrieval) until fixed.
- **Cronos adapter mapping (G6.1)** — where the spec meets the real worker/task model; the most
  likely place for friction the contracts can't reveal. G6.2 proves it end-to-end.

---

## Provenance

Derived from a review of the Cronos CC-v1 pipeline (github.com/cilaman/cronos): 11 agents,
typed artifacts, a state file, an event log, YAML harnesses. delivery/v1 keeps the sound parts
(model tiering, tool-allowlist guardrails, deterministic schema gates, the retro
self-improvement loop) and fixes the gaps (outcome gates vs schema gates, convergence loops vs
fixed-N, portable state/telemetry, first-class traceability, and decoupling from Cronos
internals).
