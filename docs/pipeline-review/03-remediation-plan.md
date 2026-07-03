# Delivery/v2 — Remediation Plan

Sequenced so every step ships independently with both suites green, per your working rule. Dependencies are explicit; the one hard ordering constraint is **R2 before R5** (condition-aware resume cannot work while `fields` don't survive persistence). Sizes are relative (S/M/L), not hours. Defect IDs reference `00-assessment.md §2`; design targets reference `01-state-model.md §5` and `02-package-boundary.md`.

A note on ordering strategy, since there is a real fork: the package rename (R10a) touches every file and could plausibly go **first** so all behavioral diffs land on the final layout. I recommend against it: R1–R3 are small, local, and relieve the acute daily pain (false failures, dead routing); paying the rename tax on three small diffs later is cheaper than delaying the pain relief. If you instead expect a long remediation window with many contributors/agents, invert and do R10a first — that is the only scenario where it wins.

---

## R1 — Fix the result channel (kills D6, D4, D13) — size S, no deps

Parse the status envelope from the **full** `final_text` inside `extract_run_trace` (it holds the untruncated text at `trace_parser.py:187-256`) and store the parsed block as a structured `node_status: dict | None` on `RunTrace`. `CronosAdapter.dispatchAgent` reads that field; `final_text_snippet` stops being load-bearing. While there, fix the adjacent latent bug: `final_text = full_text` overwrites with empty when the last assistant turn is tool-only, contradicting its own "last non-empty wins" comment (`trace_parser.py:255-256`) — guard on non-empty.

At the same boundary, close the vocabulary (target §5.1): a fence status outside `{done, blocked, needs_fix, failed}` maps to `failed` with `open_questions=["unknown_status:<raw>"]` — never silently to `done` (`runner/dispatch.py:143-154` keeps its shape; the adapter stops feeding it raw strings). Derive the child task's Kanban state from the **same** parsed envelope (infra exceptions still force WAITING), ending the board-vs-node contradiction.

Demote the mtime fallback scan (`adapter.py:_fallback_delivery_status`) to log-only for two releases, then delete. Acceptance: repro D4 and D8 flip to "not reproduced"; a child whose final message is 10k chars of prose + fence classifies `done`.

## R2 — Persistence round-trip law (kills D2) — size S, no deps

Add `fields` (and `telemetry`) to `_serialize`/`_deserialize` (`lib/state/store.py:41-63, 25-31`) and to `CronosStateOps.write` (`adapter.py:99-135`). Ship a package-provided **StateOps conformance test** ("everything the runner writes reads back identically") and run it against both existing implementations — the harness `_StateOps` already passes; `CronosStateOps` will fail until patched, which is the point. Acceptance: repro D2 flips.

## R3 — Typed scope and conditions (kills D3) — size S-M, no deps

Scope carries typed scalars; serialization canonicalizes (`true`/`false`, numbers unquoted); `eval_condition` compares typed values and gains `exists(path)`; the `None != rhs → True` behavior for missing keys becomes `False` with a warning (breaking change to the grammar — audit the shipped spec's edges, all of which are satisfied by the new semantics since they compare present keys). Update `agents/analyst.md` example only if you choose string booleans instead; recommended: fix the evaluator, not twelve agent prompts. Acceptance: repro D3 flips; `has_ui` routing works pre-resume.

## R4 — Spec-conformance suite (green-tests countermeasure) — size M, deps R2

The executable answer to "548 passing tests, nine broken behaviors": drive the shipped `delivery.workflow.yaml` end-to-end through scripted park→resume cycles against **real** `StateStore` persistence and a scripted executor, asserting per scenario (a) the exact executed-node set, (b) the terminal `Outcome`, (c) state round-trip equality. Seed scenarios: the D1 sign-off branch case, the D5 starved-tail case, the D7 timed-wait case, a full happy path, a `needs_fix→implement` fix-loop. Mark not-yet-fixed expectations `xfail` and flip them as R5–R8 land — the suite then doubles as the remediation progress meter. Wire it into CI (clean-environment principle: this is exactly the class of failure that only surfaces off the authoring machine).

## R5 — Condition-aware resume seeding (kills D1) — size M, deps R2+R3

Replace the blanket in_degree decrement in `runner/core.py:116-134` with edge replay: for each persisted-`done` node, evaluate its outgoing `when` conditions against the rebuilt (now complete, typed) scope and decrement only fired edges; persist the fired-edge set so replay is idempotent across multiple resumes. Acceptance: repro D1 flips; conformance scenario "sign-off with has_ui=false" executes `architect` and not `frontend`.

## R6 — Completeness invariant + `stalled` outcome (kills D5, D12; implements OD-3) — size M, deps R5

On work-list drain, the runner proves completeness (every node executed to terminal status or excluded by a recorded evaluated-false edge) or returns the new `stalled` status with `starved_nodes` (target §5.2). Exhausted gate fix-loops terminate as `stalled(gate_exhausted, node)` — reversing the engineered dead-end at `core.py:253-265`. Then delete on the driver side: `_stalled_gate_ids`, `_stalled_gate_reason`, `_resume_from_stalled_gate`, and `stalled_gate_resumes.json`. Acceptance: repro D5 flips; a verdict-routed run past a `needs_fix` g-review decision finishes DONE (D12 false positive gone).

## R7 — Resume as package API (kills D7, D10; implements OD-1/OD-2) — size L, deps R6

Implement `DeliveryRun.resume(event)` with the event grammar from target §5.3: `HumanAnswer(node, text, approve|reject)` stores the answer in `fields.answer`, routes reject via the optional `on_reject` edge else stalls; `RetryFailed` re-arms failed nodes with an attempt ceiling **in state** (deleting `failed_resumes.json` and `_resume_from_failed`); `escalated` becomes resumable via `RetryFailed`/`RaiseBudget`. Wire the host side: `run_goal`'s delivery branch finally passes `user_message` (`run_executor.py:966-1017`), and the UI gains an explicit approve/reject affordance for `kind=signoff` waits so verdicts stop being inferred from message existence. Delete `_resume_from_blocked`. Acceptance: repro D9(escalated) flips; answering a sign-off with "no — change X" routes the reject path and X reaches the re-run node's brief.

## R8 — Loop and join arithmetic (kills D8, D9) — size S-M, deps R4 (for regression cover)

Single `attempt` owner (dispatch increments, `loop.py:98` deleted); joins tracked by fired-edge set keyed `(source, target, iteration)` instead of decrement-with-clamp (`core.py:341-345`); wire `reset_downstream_nodes` from the loop-back path (its absence becomes *persistent* staleness once R2 lands) or fold its logic into the back-edge reset. Acceptance: repros D6(loop) and D7(join) in the script flip; `loop.max=4` yields four executions.

## R9 — Single writer per node field (kills D11) — size S, deps R6

Delete the adapter's state writes in `runGate` (`adapter.py:425-445`) and `runExec` (`adapter.py:513-527`); the runner becomes the sole writer through `StateOps`, and a gate's non-proceed decision is written once, by the runner, as node status `needs_fix` with detail in `gate`. Event log then shows real transitions only. Acceptance: event log for a failing gate contains exactly one transition.

## R10 — Boundary restructure (kills D15, D16) — size L, deps R6+R7

Per `02-package-boundary.md`: (a) importable `delivery_workflow` package, delete all three `sys.path` shims; (b) `DeliveryRun` facade + `NodeExecutor`/`HostPort` split, `evalCondition` withdrawn from the executor surface; (c) Cronos adapter relocates to `backend/app/delivery_adapter.py`; (d) both hosts (delivery driver **and** harness path) consume the shared `Outcome → TaskState` table — deleting `state_mapping.py`'s bidirectional tables and the harness `failed→DONE` collapse; (e) `LocalProcessExecutor` + `python -m delivery_workflow run` CLI = the standalone deliverable, exercised by the conformance suite with no Cronos import anywhere in its process.

## R11 — Cleanup pass (kills D14) — size S, deps none (do alongside R10)

Delete: dead CC-v1 `delivery` branch in `dispatchAgent` (`adapter.py:322-330`) and the `{"trace": …, "delivery": None}` wrapper; the never-written `"cancelled"` guard value — or implement real cancellation via `DeliveryRun.cancel` (recommended: implement, the driver already holds a `cancel_event` it can only honor between dispatches today); the stale `lib.verify → app.pipeline.normalize` importlinter exception and the dead `--normalize` CLI path (`lib/verify.py:1409`).

---

## Anti-patterns to enforce during the work

These are the accretion mechanisms this review caught in the act; each is cheap to police in review or with a lint rule. No new `_resume_from_*` functions in the driver — resume semantics belong to the package, and a fourth heuristic means a missing `resume` event type. No new sidecar counter files — bounded retries live in persisted state. No raising `final_text_snippet` limits or widening the fallback scan — the channel is structured after R1, and any pressure to touch it again means an agent template stopped emitting the fence, which is the thing to fix. No new host code that reads `WorkflowState.nodes` — hosts consume `Outcome`/`RunEvent` only; the moment a host needs node internals, the package is missing an event.

## Progress meter

The included `repro_delivery_v2.py` doubles as the acceptance gate: at HEAD it prints nine `DEFECT CONFIRMED`; the plan is complete when all nine print `not reproduced` **and** the R4 conformance suite passes un-xfailed. Suggested tracking: check the script into the repo (`packages/delivery-workflow/tests/regression/`) and convert each section into a pytest as its remediation step lands, so the defects can never silently return.
