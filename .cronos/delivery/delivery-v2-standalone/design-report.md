---
class: design
agent: architect
goal_slug: delivery-v2-standalone
feature: "F1+F2 — standalone parity (delivery/v2 §5, Phase D)"
phase: design
status: done
has_ui: false
req_ids: [REQ-F1-EXTRACT, REQ-F1-PARITY, REQ-F2-EVALS, REQ-F2-WIRE, REQ-IMPORT-BOUNDARY]
dd_ids: [DD-001, DD-002, DD-003, DD-004, DD-005, DD-006]
next_consumer: implementation
base_branch: feature/delivery-v2
inputs_used:
  - docs/delivery-pipeline/delivery-v2/delivery-v2-spec.md (§2.5, §2.6, §3.4, §3.5, §5, §6, §7 Phase D)
  - packages/delivery-workflow/agents/architect.md + skills/design/SKILL.md
  - backend/app/pipeline/gate.py (_check_security, _run_command, _read_header, _resolve_artifact_path, CHECK_REGISTRY)  # @feature/delivery-v2
  - backend/app/pipeline/run_evals.py (CC-v1 eval harness — kept Cronos-side, NOT ported)  # @feature/delivery-v2
  - packages/delivery-workflow/lib/improve.py + skills/improve/SKILL.md (eval-corpus consumer)  # @feature/delivery-v2
  - packages/delivery-workflow/lib/telemetry/sink.py + backend/app/run_side_effects.py (app→lib import precedent)  # @feature/delivery-v2
  - packages/delivery-workflow/.importlinter + tests/test_import_boundary.py + pyproject.toml
  - backend/pyproject.toml (editable install of delivery-workflow)  # @feature/delivery-v2
  - backend/tests/test_pipeline_gate_security.py + tests/fixtures/gate/security/*  # @feature/delivery-v2
missing_input: .cronos/delivery/delivery-v2-standalone/analysis-report.md  # see Provenance note
---

# Design — F1+F2 standalone parity (delivery/v2 Phase D)

## Provenance note (no analysis report on disk)

The brief points at `.cronos/delivery/delivery-v2-standalone/analysis-report.md`, but **no such
artifact exists** on any branch (the scout/analyst phase for SGD did not run). Rather than block,
this design derives its requirement set directly from the authoritative source the analyst would
have consumed — **delivery/v2-spec §2.5, §2.6, §3.4, §3.5, §5, §6, and §7 Phase D** — plus the
goal's three acceptance criteria. Every iteration traces to ≥1 REQ; every DD traces to ≥1 REQ.
Recon was done by reading the *real implemented state* on `feature/delivery-v2` (where SGA's
`_check_security` and SGC's `improve` back-half already live). **Flagged for the reviewer:** the
upstream analysis artifact is absent; if a g-design gate expects it as a named input, that gate
will need its input list relaxed for this goal, or the analyst phase re-run.

## Base-branch warning (load-bearing)

This goal's working tree (`8a5081a`) is **NOT** based on `feature/delivery-v2`. All of SGA
(`_check_security` in `gate.py:572`), SGB/SGC (`lib/improve.py`, `lib/git_pr.py`, `improve/SKILL.md`,
the security gate tests and fixtures) live on **`feature/delivery-v2`**. The implementor MUST
branch from / rebase onto `feature/delivery-v2` before touching any file below — otherwise
`gate.py` has no `_check_security` to delegate and `lib/improve.py` does not exist. Captured as
**R1**.

---

## Requirement set (derived from spec §5 Phase D + goal ACs)

| REQ | Statement | Source | verifying_phase | Covered by |
|-----|-----------|--------|-----------------|------------|
| **REQ-F1-EXTRACT** | The `_check_security` decision body (scanner-shelling, JSON severity parse, reconcile, finding-class derivation, decision) is extracted to a portable module under `packages/delivery-workflow/lib/` so the Cronos gate and the (Phase-6) standalone runner share **one** implementation. | §2.5, §6 ("Portable eval harness / share check body"), goal AC1 | test | I1, I2 |
| **REQ-F1-PARITY** | The extracted module imports **no** `app.*` / `backend.*`; the Cronos `gate.py:_check_security` becomes a thin delegate preserving the exact `(decision, errors, evidence)` contract and all existing real-subprocess gate tests stay green. | §2.6 (import-boundary AC), §2.5 | test | I1, I2 |
| **REQ-F2-EVALS** | A portable eval-corpus harness exists at `packages/delivery-workflow/lib/evals/`, runnable standalone (`python -m lib.evals`), honouring the `DELIVERY_EVAL_CMD` env override and a default command, returning a structured pass/exit-code result. | §3.4, §3.5 ("portable `lib/evals/` or a new interface op"), §6, goal AC2 | test | I3 |
| **REQ-F2-WIRE** | The F2 self-improvement flow (the `improve` skill, Tier-0 keep/rollback + Tier-1 PR gating) consumes the eval corpus **through** `lib.evals` — one shared mechanism for Cronos and standalone — preserving the existing env-override contract. | §3.5 ("Eval-corpus re-run available to both Cronos and standalone") | test | I4 |
| **REQ-IMPORT-BOUNDARY** | `tests/test_import_boundary.py` stays green: no `app.*` import added to the portable core; the new `lib/security.py` and `lib/evals/` modules are auto-discovered clean. | §2.6, §3.4, goal AC3 | test | I1, I3 |

---

## Architecture decisions

### DD-001 — Portable scanner-shelling lives in `lib/security.py`; gate `_check_security` becomes a thin delegate
*Traces: REQ-F1-EXTRACT, REQ-F1-PARITY.*
**Statement.** Move the scanner execution + JSON severity parse + reconcile + finding-class
derivation + decision logic out of `backend/app/pipeline/gate.py` into a new portable
`packages/delivery-workflow/lib/security.py`, exposing `evaluate_security(check, artifact_paths,
space) -> tuple[decision, errors, evidence]`. `gate.py:_check_security` is reduced to a one-line
delegate; the `CHECK_REGISTRY["security"]` entry is unchanged.
**Rationale.** Spec §2.5 names this exact move ("move scanner-shelling into
`packages/delivery-workflow/lib/` so the Cronos gate and the standalone gate share one
implementation"). The `app.*`→`lib.*` direction is already a shipped pattern
(`backend/app/run_side_effects.py` does `from lib.telemetry import TelemetrySink`), and
`backend/pyproject.toml` editable-installs `delivery-workflow`, so the import resolves in the
Cronos process with no new wiring.
**Tradeoffs.** `lib/security.py` carries its own small subprocess runner + frontmatter reader
(it cannot import `gate._run_command` or `app.pipeline.verify.split_frontmatter` across the
boundary), so those two ~15-line helpers are duplicated. Accepted: duplication is the price of the
import boundary, and the duplicated pieces are trivially testable in isolation.

### DD-002 — The portable runner captures **full** scanner stdout (removes the 2 KB fail-open)
*Traces: REQ-F1-EXTRACT, REQ-F1-PARITY.*
**Statement.** `lib/security.py`'s subprocess helper returns the **complete** scanner stdout to
the JSON parser, not the `proc.stdout[-2000:]` tail that `gate._run_command` keeps. Decision
semantics (`proceed`/`needs_fix`/`fail`/`retry`, severity reconcile, `on_missing_scanner`,
crash→retry) are otherwise preserved byte-for-byte.
**Rationale.** The current `_check_security` does `json.loads(_run_command(...).stdout_tail)`;
a real scanner emitting >2 KB of JSON gets a truncated, unparseable tail → `parsed=None` →
**silently scored "clean"** → fail-open. This was flagged in the prior security review
(needs_fix, 4ccb9a0) and never fixed in `gate.py` (still `[-2000:]` at `gate.py:104`). A *shared*
implementation must not carry a fail-open. Fixing it is a natural, in-scope consequence of owning
the extraction.
**Tradeoffs.** This is the **only** intentional behavioural change vs the current gate. It is
scoped strictly to the security path (other gate checks keep `_run_command`'s tail untouched).
Guarded by an explicit regression test (I1: a scanner emitting >2 KB JSON with a `fail_on`
severity must NOT score clean). Captured as **R2**.

### DD-003 — `evaluate_security` is a drop-in delegate: identical signature, identical return tuple
*Traces: REQ-F1-PARITY.*
**Statement.** `evaluate_security` takes the same `(check: dict, artifact_paths: list[str],
space: Path | None)` and returns the same `(decision: str, errors: list[str], evidence: dict)`
tuple `_check_security` returns today, including the `evidence["security"]` shape that routing
edges read (`effective_finding_class`, `has_fail_on_hit`, `has_missing_fail`, `agent_verdict`,
`scanner_results`, …). The agent-artifact frontmatter is read inside the lib module via a portable
splitter that mirrors `app.pipeline.verify.split_frontmatter` semantics; an unreadable artifact
still yields `retry`.
**Rationale.** A drop-in delegate means **zero** change at the registry and zero change to the
`g-security` routing contract — the entire existing `backend/tests/test_pipeline_gate_security.py`
suite (9 real-subprocess tests) is the regression oracle and must stay green unmodified.
**Tradeoffs.** `lib/security.py` is shaped around the Cronos *check-dict* schema (`scanners`,
`fail_on`, `on_missing_scanner`). That couples it to the gate-check **schema**, not to `app.*` —
acceptable, since the standalone runner's gate engine will speak the same check schema (spec §6).

### DD-004 — Portable eval harness is a thin corpus-command runner, not a port of CC-v1 `run_evals.py`
*Traces: REQ-F2-EVALS.*
**Statement.** `lib/evals/` provides `run_eval_corpus(repo_root=None, *, eval_cmd=None,
env=None, runner=subprocess.run) -> EvalResult` where `EvalResult` carries `passed: bool`,
`exit_code: int`, `command: str`, `output_tail: str`. Command resolution precedence:
`eval_cmd` arg → `DELIVERY_EVAL_CMD` env → default `pytest packages/delivery-workflow/tests/ -q
--no-header`. A `python -m lib.evals [--repo-root P] [--json]` CLI exits with the corpus exit code.
CC-v1's `backend/app/pipeline/run_evals.py` (golden/negative artifacts via `app.pipeline.verify`/
`normalize`) **stays Cronos-side and is NOT ported** — it is bound to the CC-v1 contract.
**Rationale.** delivery/v1's "eval corpus" today *is* its own pytest suite (the improve skill
already shells `pytest packages/delivery-workflow/tests/ -q --no-header`). Spec §3.4/§6 ask for
"a portable `lib/evals/` module **or** a new interface op" — the thin, env-swappable command
runner is the minimal honest abstraction and the natural home for the default + override that are
currently inlined as shell prose. Porting CC-v1's golden/negative machinery would import a
contract delivery/v1 does not have.
**Tradeoffs.** No golden/negative fixture semantics yet — deferred until delivery/v1 grows its own
fixture corpus. The harness is a command-runner seam, not a scorer. Captured as **R5**.

### DD-005 — The `improve` flow consumes the corpus exclusively through `lib.evals`
*Traces: REQ-F2-EVALS, REQ-F2-WIRE.*
**Statement.** `skills/improve/SKILL.md` Step 5 (Tier-0 keep/rollback) and Step 6 (Tier-1 PR
gate) invoke the corpus via `python -m lib.evals` / `from lib.evals import run_eval_corpus`,
replacing the inlined `DELIVERY_EVAL_CMD="${DELIVERY_EVAL_CMD:-pytest …}"` block. The default and
the env override now live in `lib.evals` (single source of truth). `lib/improve.py:run_back_half`
keeps its `evals_passed: bool` input unchanged — the *running* is what moves behind the portable
seam, not the gating.
**Rationale.** "Runnable standalone" (goal AC2) and "available to both Cronos and standalone"
(§3.5) mean one shared mechanism. Centralising the default+override in `lib.evals` is what makes
the standalone runner and the Cronos improve node behave identically.
**Tradeoffs.** Touches the delicate `improve` SKILL prose. Mitigated by keeping the
`DELIVERY_EVAL_CMD` contract byte-identical and validating against the full package suite.
Captured as **R4**.

### DD-006 — New portable modules stay `app.*`-free; import-boundary auto-covers them
*Traces: REQ-IMPORT-BOUNDARY.*
**Statement.** `lib/security.py` and `lib/evals/*` import only stdlib + `lib.*`. The AST scanner
in `tests/test_import_boundary.py` already walks every `*.py` under the package (excluding
`tests/` and `adapters/cronos/`), so the new modules are covered with no test change required;
`test_import_boundary.py` is run as a validation gate on I1 and I3.
**Rationale.** Goal AC3 / §2.6 / §3.4 invariant.
**Tradeoffs.** None.

---

## Iterations (topologically ordered DAG)

Two roots: **I1** (F1 spine) and **I3** (F2 spine) are independent and may run in parallel.
`I1 → I2`; `I3 → I4`.

```
I1 (lib/security.py) ──→ I2 (gate delegate)
I3 (lib/evals/)      ──→ I4 (improve SKILL wiring)
```

### I1 — Portable security evaluator (`lib/security.py`)
- **id:** I1   **type:** backend   **depends_on:** []
- **Traces:** REQ-F1-EXTRACT, REQ-F1-PARITY, REQ-IMPORT-BOUNDARY (DD-001, DD-002, DD-003, DD-006)
- **Work.** Create `lib/security.py` containing: (a) a private subprocess runner capturing **full**
  stdout + tailed stderr + exit code (DD-002); (b) a private frontmatter splitter mirroring
  `split_frontmatter` to read the security-agent header (`verdict`, `finding_class`, `findings`);
  (c) `evaluate_security(check, artifact_paths, space) -> (decision, errors, evidence)` — verbatim
  port of the `gate.py:572-748` decision logic (scanner loop, missing-scanner policy,
  crash→retry, severity reconcile against `fail_on`, `dep`/`code` finding-class derivation,
  agent-verdict precedence `fail > needs_fix > proceed`, evidence dict). Export it from
  `lib/__init__.py` if the package convention does so (check siblings; otherwise leave unexported).
  Write `tests/test_security_lib.py` covering: scanner hit → not-proceed; missing+fail → not-proceed;
  missing+skip → not forced; infra crash → retry; agent verdict precedence; **and the DD-002
  regression: a scanner emitting >2 KB of JSON with a fail_on severity is detected (not "clean")**.
- **scope_files:**
  - `packages/delivery-workflow/lib/security.py` (new)
  - `packages/delivery-workflow/lib/__init__.py` (export only, if convention)
  - `packages/delivery-workflow/tests/test_security_lib.py` (new)
- **validation_command:** `cd packages/delivery-workflow && python -m pytest tests/test_security_lib.py tests/test_import_boundary.py -q`
- **max_diff_lines:** 320

### I2 — Re-point Cronos gate to the portable evaluator
- **id:** I2   **type:** backend   **depends_on:** [I1]
- **Traces:** REQ-F1-EXTRACT, REQ-F1-PARITY (DD-001, DD-003)
- **Work.** In `backend/app/pipeline/gate.py`, replace the `_check_security` body with a delegate
  `return evaluate_security(check, artifact_paths, space)` (`from lib.security import
  evaluate_security`). Delete the now-dead inlined scanner logic. Keep `CHECK_REGISTRY["security"]
  = _check_security` (or register `evaluate_security` directly — keep the named wrapper for
  symmetry with other `_check_*` handlers). Leave `_run_command`, `_read_header`,
  `_resolve_artifact_path` in place — they are still used by the other 8 checks. Add **one**
  regression test to `test_pipeline_gate_security.py`: a fixture scanner emitting >2 KB JSON with a
  HIGH finding routes to `needs_fix` (proves DD-002 through the real gate path).
- **scope_files:**
  - `backend/app/pipeline/gate.py`
  - `backend/tests/test_pipeline_gate_security.py`
- **validation_command:** `cd backend && python -m pytest tests/test_pipeline_gate_security.py -q`
- **max_diff_lines:** 160

### I3 — Portable eval-corpus harness (`lib/evals/`)
- **id:** I3   **type:** backend   **depends_on:** []
- **Traces:** REQ-F2-EVALS, REQ-IMPORT-BOUNDARY (DD-004, DD-006)
- **Work.** Create the `lib/evals/` package: `corpus.py` with the `EvalResult` dataclass +
  `run_eval_corpus(repo_root=None, *, eval_cmd=None, env=None, runner=subprocess.run)` (precedence
  arg → `DELIVERY_EVAL_CMD` → default `pytest packages/delivery-workflow/tests/ -q --no-header`,
  run from `repo_root`); `__init__.py` exporting `run_eval_corpus`, `EvalResult`; `__main__.py`
  CLI (`--repo-root`, `--json`, exit = corpus exit code). Write `tests/test_evals_lib.py` using an
  **injected fake runner** (no real pytest recursion — R5): asserts command-precedence
  (arg/env/default), `passed` true on exit 0 / false on non-zero, and CLI exit-code propagation.
- **scope_files:**
  - `packages/delivery-workflow/lib/evals/__init__.py` (new)
  - `packages/delivery-workflow/lib/evals/corpus.py` (new)
  - `packages/delivery-workflow/lib/evals/__main__.py` (new)
  - `packages/delivery-workflow/tests/test_evals_lib.py` (new)
- **validation_command:** `cd packages/delivery-workflow && python -m pytest tests/test_evals_lib.py tests/test_import_boundary.py -q`
- **max_diff_lines:** 220

### I4 — Wire the `improve` flow onto `lib.evals`
- **id:** I4   **type:** doc   **depends_on:** [I3]
- **Traces:** REQ-F2-WIRE (DD-005)
- **Work.** Edit `skills/improve/SKILL.md` Step 5 + Step 6: replace the inlined
  `DELIVERY_EVAL_CMD="${DELIVERY_EVAL_CMD:-pytest …}"` block with an invocation of the portable
  harness — `python -m lib.evals` (CLI) and the `from lib.evals import run_eval_corpus` Python
  form — and state that the default+override now live in `lib.evals`. Do not weaken any safety
  invariant (snapshot/rollback, tier-0-only, retro-self-edit block). No source `.py` change.
- **scope_files:**
  - `packages/delivery-workflow/skills/improve/SKILL.md`
- **validation_command:** `cd packages/delivery-workflow && grep -q 'lib.evals' skills/improve/SKILL.md && ! grep -q 'DELIVERY_EVAL_CMD:-pytest' skills/improve/SKILL.md && python -m pytest tests/ -q`
- **max_diff_lines:** 60

---

## Risk register

| id | severity | description | mitigation |
|----|----------|-------------|------------|
| **R1** | high | Working tree (`8a5081a`) is not based on `feature/delivery-v2`; `_check_security` and `lib/improve.py` only exist there. Implementing on the wrong base produces a delegate to nothing. | Implementor branches from / rebases onto `feature/delivery-v2` before I1; I2's validation runs the real backend security suite (which imports `lib.security` via the editable install) — a wrong base fails it immediately. |
| **R2** | medium | DD-002 changes scanner-stdout handling (full vs 2 KB tail) — the one intentional behavioural change. A subtle regression could flip a real decision. | Change scoped to the security path only; all other gate checks keep `_run_command`. The full existing `test_pipeline_gate_security.py` is the regression oracle (unmodified) plus one new >2 KB-JSON test in both I1 and I2. |
| **R3** | medium | `lib/security.py` needs its own frontmatter splitter (cannot import `app.pipeline.verify.split_frontmatter`); divergence from gate semantics could mis-read an agent header. | Mirror `split_frontmatter` exactly; cover with the same agent-artifact fixtures the gate tests use; gate's own `_read_header` stays untouched for the other 8 checks. |
| **R4** | medium | `improve/SKILL.md` is delicate prose; a botched Step 5/6 edit could break the documented keep/rollback control flow or the `DELIVERY_EVAL_CMD` contract. | `lib.evals` preserves the env-override + default byte-for-byte; SKILL edit is a minimal command swap; I4 validation re-runs the full package suite and greps for the wiring. |
| **R5** | low | delivery/v1's "eval corpus" is just its own pytest suite; a real `run_eval_corpus` call inside a unit test would recurse into pytest. | `test_evals_lib.py` injects a fake `runner` — no real subprocess; the real corpus run only happens in the improve node. |
| **R6** | low | No upstream analysis-report; REQ-ids derived from spec §5 Phase D + goal ACs. A g-design gate keyed on a named analysis input may complain. | Traceability table maps every REQ to a spec clause; Provenance note flags the gap for the reviewer; relax the gate input list or re-run the analyst if required. |

---

## Traceability cross-check

- Every REQ appears in ≥1 iteration: F1-EXTRACT→I1,I2 · F1-PARITY→I1,I2 · F2-EVALS→I3 · F2-WIRE→I4 · IMPORT-BOUNDARY→I1,I3. ✔
- Every DD traces to ≥1 REQ: DD-001/002/003→F1; DD-004→F2-EVALS; DD-005→F2-EVALS,F2-WIRE; DD-006→IMPORT-BOUNDARY. ✔
- DAG valid: roots {I1, I3}; edges I1→I2, I3→I4; no cycles, no self-loops, all `depends_on` ids exist. ✔
- `iterations_count` = 4 matches `len(iterations[])`. ✔
- `risks_count` = 6 matches `len(risks[])`. ✔
- `dd_ids[]` = [DD-001…DD-006] matches the DD records above. ✔

```delivery_status
{
  "status": "done",
  "produces": "design",
  "artifact_paths": [".cronos/delivery/delivery-v2-standalone/design-report.md"],
  "fields": {
    "iterations_count": 4,
    "iterations_planned": 4,
    "risks_count": 6,
    "dd_ids": ["DD-001", "DD-002", "DD-003", "DD-004", "DD-005", "DD-006"],
    "has_ui": false
  },
  "open_questions": [
    "No upstream analysis-report.md exists for delivery-v2-standalone — REQ set derived from spec §5 Phase D + goal ACs (R6).",
    "Implementor must base work on feature/delivery-v2, not this goal's 8a5081a tree (R1)."
  ],
  "telemetry": {"tokens": 0, "usd": 0, "seconds": 0}
}
```
