---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: delivery-v1-control-flow
phase: doc
status: done
confidence: 0.95
inputs_used:
  - backend/app/harnesses/executor.py
  - backend/app/harnesses/decision.py
  - backend/app/harnesses/run_state.py
  - backend/app/memory_parser.py
  - .cronos/pipeline/delivery-v1-control-flow/impl-report-delivery-v1-control-flow--i1.md
  - docs/HARNESSES.md
docs_updated:
  - docs/HARNESSES.md
intentionally_not_updated: []
---

## Summary

Updated `docs/HARNESSES.md` to document three new features from G3.1–G3.3 implementation:

**G3.1 — Loop Convergence Policy**
- Added new §6.1 "Loops on agent nodes (G3.1)" explaining loop semantics, convergence signals
  (`until`, `recurring_findings`, `no_diff_progress`, `max`), and `on_exhaust` action.
- Included worked example of iterative code review with loop configuration.
- Documented resume-safety via persisted loop state (`attempt`, `prior_finding_ids`).

**G3.2 — `eval_condition` (Sandboxed)**
- Expanded §8 "Control-flow nodes" > "Decision — pick one branch" with new subsection
  "Dotted-path conditions (G3.2)".
- Documented dotted-path syntax (`<path> <op> <literal>`), hyphens in node ids,
  `&&` AND conjunctions, and the four-layer signal precedence.
- Explained scope enrichment (automatic dotted-path key population after `delivery_status`).
- Added comprehensive example showing how agents route on structured output.

**G3.3 — Cronos `run_trace` Wiring (P0 Routing Unblock)**
- Updated "Agent completion sentinel" section to prioritise `delivery_status` block
  (CC-v1 preferred channel) over legacy `cronos_status`.
- Added explanation of scope enrichment process (`<node_id>.status` + `<node_id>.fields.<name>`).
- Documented that dotted-path keys are available for decision routing but NOT for
  prompt interpolation (scope stays `dict[str, str]`).

## Documentation changes

| Section | Change |
|---------|--------|
| §6 Variables and interpolation | Split into subsections; added note about dotted-path enrichment being decision-only |
| §6.1 Loops on agent nodes (NEW) | Full section covering loop config, semantics, convergence signals, examples |
| §7 Agent completion sentinel | Reordered signal precedence: `delivery_status` → `cronos_status` → legacy `STATUS:` |
| §8 Decision → Dotted-path conditions (NEW) | Subsection with grammar, precedence, and worked example |
| §13 Troubleshooting | Added entries for loop escalation, dotted-path matching failures, stall checks |
| §14 Quick reference | Updated node `data` cheat sheet to include loop config; updated condition grammar docs |
| Table of contents | Added §6.1 entry; renumbered trailing sections (§12 Known limitations, §13–14) |

## Scope discipline

- **In scope**: Documentation of new harness executor and decision features.
- **Out of scope**: Frontend editor fixes (item #1–5 in Known limitations remain unchanged — they are tracked separately as a follow-up goal).
- **No code changes** in this phase.

## Verification

- Verified all examples compile and match the implementation's supported syntax
  (dotted paths with hyphens, `&&` conjunctions, delivery_status field enrichment).
- Confirmed documentation aligns with implementation commit f924575:
  - Loop fields and convergence policy match `_execute_agent_node` logic.
  - Dotted-path condition grammar matches `_EVAL_SINGLE_RE` regex in `decision.py`.
  - Scope enrichment process matches `_enrich_scope_from_delivery_status` in `executor.py`.
- No regressions in existing sections; backward-compatibility notes preserved.

## Quality notes

- Used consistent terminology with the implementation (G3.1–G3.3 callouts, "Cronos run_trace wiring").
- Added "P0" priority tag to G3.3 (matches goal brief).
- Examples are runnable with the current executor (no TODO/future-work syntax).
- Quick reference section fully updated with new loop syntax and signal precedence.
