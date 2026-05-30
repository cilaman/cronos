---
name: pipeline-gate
description: Close the gate on one CC-v1 pipeline phase. Resolves the artifact path mechanically from goal_slug + phase, runs normalize then verify, records the result into pipeline-state.json + phases-log.jsonl, and emits STATUS: DONE on pass or STATUS: BLOCKED on fail/escalate so the Cronos worker does not advance the DAG.
license: Internal — Cronos project.
---

# Pipeline Gate

This skill is the Cronos analogue of Delivery Notes' `post_phase_verify` helper. It is invoked from a **gate task** sitting between two pipeline-phase agents — its job is to mechanically verify the upstream agent's artifact and either greenlight downstream phases (STATUS: DONE) or halt them (STATUS: BLOCKED). It never reads markdown prose to make decisions; every gate outcome derives from the artifact's YAML header via `app.pipeline.verify`.

## When to use

Invoke this skill as the **only** step of any gate task that follows a pipeline-phase agent run (scout / analyst / architect / implementor / tester / reviewer / doc-sync). The upstream agent has already written its CC-v1 artifact under `{space}/.cronos/pipeline/{goal_slug}/`. The gate task's job is to verify that artifact and update pipeline state — not to re-read the artifact body, not to re-run the agent.

## Required inputs

The gate task brief must supply, in any clearly labelled form (frontmatter, `key=value` list, or a JSON block):

| Field | Required | Example | Notes |
|---|---|---|---|
| `goal_slug` | yes | `pipeline-foundation-cc-v1-contract-schem` | Parent goal slug — the directory under `.cronos/pipeline/`. Must equal `header.slug.split('--',1)[0]`. |
| `phase` | yes | `analysis` | CC-v1 **class** identifier: one of `research`, `analysis`, `design`, `implementation`, `test`, `review`, `doc`. Drives schema + filename prefix. |
| `agent_name` | yes | `pipeline-analyst` | Free-form name of the upstream agent — recorded into pipeline-state for audit; not used for routing. |
| `upstream_task_id` | yes | `2026-05-30-1437-2-2-pipeline-analyst-agent` | Cronos task id of the agent run that produced the artifact (NOT this gate task). Used to load the run trace. |
| `run_index` | optional | `0` | Run index inside that task's trace dir. Defaults to the latest. |
| `iteration_id` | only `phase=implementation` | `I3` | Architect-assigned id (matches `^I[0-9]+$`). Composes the fan-out slug `{goal_slug}--{iteration_id.lower()}`. |
| `attempt` | only `phase=review` | `1` | 1-based review attempt index. Composes the fan-out slug `{goal_slug}--attempt{N}`. |

If a required field is missing or unparseable, **do NOT search the filesystem** for the artifact — emit `STATUS: BLOCKED` with a one-line reason ("missing input: <field>") and stop. The pipeline-scaffold skill is responsible for handing you a complete brief.

---

## Step 1 — Resolve the canonical slug + artifact path (mechanical)

The verifier already encodes the path rule (`canonical_artifact_relpath` in `backend/app/pipeline/verify.py`). Do not duplicate it; just compose the slug correctly per class:

| Phase class | Slug |
|---|---|
| `research`, `analysis`, `design`, `test`, `doc` | `${GOAL_SLUG}` |
| `implementation` | `${GOAL_SLUG}--${ITERATION_ID,,}` (lowercase iter id) |
| `review` | `${GOAL_SLUG}--attempt${ATTEMPT}` |

Set environment variables for the rest of the skill:

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')

# From the gate task brief — these MUST be set by the scaffold skill.
export GOAL_SLUG=...        # e.g. pipeline-foundation-cc-v1-contract-schem
export PHASE=...            # research|analysis|design|implementation|test|review|doc
export AGENT_NAME=...       # e.g. pipeline-analyst
export UPSTREAM_TASK_ID=... # task id of the agent run that produced the artifact
export RUN_INDEX=...        # optional; empty = latest
export ITERATION_ID=...     # only when PHASE=implementation
export ATTEMPT=...          # only when PHASE=review

case "$PHASE" in
  implementation) export SLUG="${GOAL_SLUG}--$(echo "$ITERATION_ID" | tr '[:upper:]' '[:lower:]')" ;;
  review)         export SLUG="${GOAL_SLUG}--attempt${ATTEMPT}" ;;
  *)              export SLUG="${GOAL_SLUG}" ;;
esac

export SPACE_DIR
```

The expected artifact path is `${SPACE_DIR}/.cronos/pipeline/${GOAL_SLUG}/<prefix>-${SLUG}.md` where `<prefix>` is `scout-report` / `analysis-report` / `design-report` / `impl-report` / `test-report` / `review-report` / `doc-report` per `CLASS_CONFIG`. **You do not need to `ls` it** — the verifier exits `3 (retry)` if the file is missing at the expected path, which the gate treats as BLOCKED.

---

## Step 2 — Run normalize + verify (one CLI call)

```bash
cd "${SPACE_DIR}/backend"
python -m app.pipeline.verify \
    --agent "$PHASE" \
    --slug "$SLUG" \
    --space "$SPACE_DIR" \
    --normalize \
    --json > /tmp/pipeline-gate-verify.json
export VERIFY_EXIT=$?
cat /tmp/pipeline-gate-verify.json
```

Exit codes (`backend/app/pipeline/verify.py`):

| Exit | Outcome | Gate decision |
|---|---|---|
| `0` | proceed | PASS — advance |
| `1` | fail | BLOCK — schema / cross-field / R-rule violations |
| `2` | escalate | BLOCK — agent self-escalated (status in {blocked, failed}) |
| `3` | retry | BLOCK — artifact missing / unreadable / malformed |

The JSON payload includes `artifact_path` (workspace-relative), `outcome`, `passed`, `errors[]`, `warnings[]`, and (if `--normalize` ran) a `normalize` block listing applied fixes. **Use that JSON only — do not read the artifact body to make a decision.**

---

## Step 3 — Record state + log via state_writer

Both the PASS path and the BLOCK path call exactly the same writers (`update_phase` + `record_phase_log` from `app.pipeline.state_writer`). The only difference is the `gate_decision` recorded and the STATUS line emitted at the end of your response.

Run **one** Python block that handles every outcome (proceed / fail / escalate / retry):

```bash
cd "${SPACE_DIR}/backend"
python <<'PY'
import asyncio, json, os, sys
from pathlib import Path

from app.pipeline.state_writer import (
    init_pipeline, update_phase, record_phase_log,
    PhaseEntry, PhaseMetrics, PhaseVerifyResult,
    state_path,
)
from app.trace_store import TraceStore

SPACE_DIR        = os.environ["SPACE_DIR"]
SPACE_ID         = Path(SPACE_DIR).name
GOAL_SLUG        = os.environ["GOAL_SLUG"]
PHASE            = os.environ["PHASE"]              # CC-v1 class
AGENT_NAME       = os.environ["AGENT_NAME"]
UPSTREAM_TASK_ID = os.environ["UPSTREAM_TASK_ID"]
RUN_INDEX        = os.environ.get("RUN_INDEX") or ""

with open("/tmp/pipeline-gate-verify.json") as fh:
    v = json.load(fh)

outcome      = v.get("outcome", "fail")
passed       = bool(v.get("passed", False))
artifact_rel = v.get("artifact_path", "")
errors       = list(v.get("errors", []))
warnings     = list(v.get("warnings", []))
norm_fixes   = []
if isinstance(v.get("normalize"), dict):
    norm_fixes = list(v["normalize"].get("fixes_applied", []))

# Defensive: if no pipeline-state.json exists yet (scaffold did not run
# Phase 0 init for some reason), create it so this gate can still record.
sp = state_path(SPACE_DIR, GOAL_SLUG)
if not sp.exists():
    init_pipeline(SPACE_DIR, GOAL_SLUG, status="running")

# Load the upstream agent's run trace to derive trace-owned metrics
# (duration_s, token_spend, tool_calls, files_read, memory_hits).
async def _load_trace():
    store = TraceStore(Path(SPACE_DIR).parent)
    if RUN_INDEX:
        return await store.load_run(SPACE_ID, UPSTREAM_TASK_ID, int(RUN_INDEX))
    return await store.load_latest(SPACE_ID, UPSTREAM_TASK_ID)

trace = asyncio.run(_load_trace())
metrics = PhaseMetrics.from_trace(trace) if trace is not None else PhaseMetrics()
run_index = trace.run_index if trace is not None else 0

# Map verify outcome (proceed/escalate/retry/fail) -> state_writer
# gate_decision vocabulary (same four values).
gate_decision = outcome if outcome in {"proceed", "escalate", "retry", "fail"} else "fail"
gate_reason   = "all checks passed" if passed else "; ".join(errors)[:500]

# Phase status mirrors the gate for the worker's eyes:
#   proceed  -> done       (downstream may continue)
#   anything -> blocked    (DAG halts for human / retry)
phase_status = "done" if gate_decision == "proceed" else "blocked"

verify_result = PhaseVerifyResult(
    passed=passed,
    errors=errors,
    warnings=warnings,
    normalize_fixes=norm_fixes,
    gate_decision=gate_decision,
    gate_reason=gate_reason,
)

phase_entry = PhaseEntry(
    phase=PHASE,
    status=phase_status,
    agent=AGENT_NAME,
    task_id=UPSTREAM_TASK_ID,
    run_index=run_index,
    artifact_path=artifact_rel,
    verify_result=verify_result,
    metrics=metrics,
)

update_phase(SPACE_DIR, GOAL_SLUG, phase_entry)
record_phase_log(
    SPACE_DIR, GOAL_SLUG,
    phase=PHASE,
    status=phase_status,
    gate_decision=gate_decision,
    task_id=UPSTREAM_TASK_ID,
    run_index=run_index,
)

# Summary for the gate task's stdout — kept short, no prose-parsing of the
# artifact, just the structured verify result.
print(f"GATE {gate_decision.upper()} — {PHASE} / {GOAL_SLUG}")
print(f"  artifact: {artifact_rel}")
if errors:
    print(f"  errors  : {len(errors)}")
    for e in errors[:5]:
        print(f"    - {e}")
if warnings:
    print(f"  warnings: {len(warnings)}")
if norm_fixes:
    print(f"  normalize: {len(norm_fixes)} fix(es) applied")
PY
export PY_EXIT=$?
```

---

## Step 3b — Retro memory write-back (only when PHASE=retro and gate passes)

When `PHASE=retro` **and** `VERIFY_EXIT == 0` **and** `PY_EXIT == 0`, run the
memory writer to persist each finding from the retro artifact as a global
Cronos memory item. This is the mechanism that closes the self-improvement loop:
findings surface in future pipeline runs via `app.memory_retrieval.retrieve`.

Skip this step entirely for any other phase — it is retro-specific.

```bash
if [ "$PHASE" = "retro" ] && [ "$VERIFY_EXIT" -eq 0 ] && [ "$PY_EXIT" -eq 0 ]; then
  cd "${SPACE_DIR}/backend"
  python -m app.pipeline.retro_memory_writer \
      --space "${SPACE_DIR}" \
      --slug  "${GOAL_SLUG}" > /tmp/retro-memory-writer.out 2>&1
  export MEM_EXIT=$?
  cat /tmp/retro-memory-writer.out
  if [ "$MEM_EXIT" -ne 0 ]; then
    echo "retro memory write-back failed (exit $MEM_EXIT) — lessons not persisted but gate still PASS"
  fi
fi
```

The memory writer failure is **non-blocking** — if it fails, the gate still emits
`STATUS: DONE` (the retro artifact itself passed verification; memory write-back is
a best-effort side effect). Log the failure for human review but do not downgrade
to `STATUS: BLOCKED`.

---

## Step 4 — Emit STATUS as the last line of your response

The Cronos worker (`backend/app/agent.py::parse_status`) routes the gate task by reading the final `STATUS:` line. Pick **one**:

- **PASS path**: `VERIFY_EXIT == 0` **and** `PY_EXIT == 0` → write one summary line ("gate PASS — <phase> / <goal_slug>") and emit `STATUS: DONE`.
- **BLOCK path**: any non-zero exit, or `outcome != "proceed"` → echo the first 5 blockers from `/tmp/pipeline-gate-verify.json` and emit `STATUS: BLOCKED`.

**Never** emit `STATUS: WAIT` from this skill. WAIT means "human, answer my question"; the gate either passed or did not. A retryable verify failure (`outcome=retry`, exit 3) is still BLOCKED — the worker keeps downstream tasks in backlog and a human (or the scaffold's retry policy) decides whether to re-run the upstream agent.

Example PASS tail:

```
gate PASS — analysis / pipeline-foundation-cc-v1-contract-schem
  artifact: .cronos/pipeline/pipeline-foundation-cc-v1-contract-schem/analysis-report-pipeline-foundation-cc-v1-contract-schem.md

STATUS: DONE
```

Example BLOCK tail (verifier fail):

```
gate BLOCKED — analysis / pipeline-foundation-cc-v1-contract-schem (verify exit 1)
  - R6: header.slug='pipeline-foundation' does not equal orchestrator slug='pipeline-foundation-cc-v1-contract-schem'
  - missing required section (## Acceptance criteria)

STATUS: BLOCKED
```

Example BLOCK tail (artifact missing, exit 3):

```
gate BLOCKED — design / my-feature (verify exit 3)
  - artifact not found at expected path: .cronos/pipeline/my-feature/design-report-my-feature.md

STATUS: BLOCKED
```

---

## Why STATUS controls DAG progression

Cronos parses the last `STATUS:` line of every agent run (`backend/app/agent.py::parse_status`) and routes the task accordingly:

- `STATUS: DONE` → task → `done`. `goal_sync.propagate_to_parent` re-enqueues the goal, which activates the next task in dependency order. Downstream phases proceed.
- `STATUS: BLOCKED` → task → `waiting` (with the blocker reason as `waiting_question`). Tasks that `depends_on` this gate **stay in backlog** because dependencies require `done`. The pipeline halts at the failed gate — the worker never silently advances past a fail.

This is the closure of Delivery Notes' F-13 in Cronos shape: every phase advance is gated by a separate task whose only job is `verify_outputs` + state-write. There is no path where a malformed artifact slips into the next phase.

---

## What this skill does NOT do

- Re-run the upstream agent (that is the orchestrator/scaffold's job on retry).
- Read the artifact body to "double-check" the agent's claims (the verifier is authoritative; reading prose would re-introduce F-13).
- Search the filesystem for the artifact (the path is mechanical; missing-at-expected-path is a gate-fail signal, not a recovery trigger).
- Cherry-pick which blockers to report (record **all** errors[] from verify into pipeline-state — `update_phase` stores them on `verify_result.errors`).
- Touch the upstream task's git state (the upstream agent already committed; the gate is a read-and-record step).
- Compute `duration_s` / `token_spend` from anywhere other than the run trace (those are TRACE_OWNED_METRICS per `app.pipeline.contract`; `PhaseMetrics.from_trace` is the only legal source).

---

## Quick reference

```text
artifact path : {space}/.cronos/pipeline/{goal_slug}/<prefix>-<slug>.md
state file    : {space}/.cronos/pipeline/{goal_slug}/pipeline-state.json
log file      : {space}/.cronos/pipeline/{goal_slug}/phases-log.jsonl
verify CLI    : python -m app.pipeline.verify --agent <class> --slug <slug> --space <space> --normalize --json
exit codes    : 0=proceed  1=fail  2=escalate  3=retry
writers       : app.pipeline.state_writer.{init_pipeline, update_phase, record_phase_log}
trace API     : app.trace_store.TraceStore.{load_run, load_latest}
metrics API   : app.pipeline.state_writer.PhaseMetrics.from_trace(RunTrace)
slug rule     : <goal_slug> | <goal_slug>--<iter_id.lower()> | <goal_slug>--attempt<N>
```
