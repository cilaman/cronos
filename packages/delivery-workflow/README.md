# delivery-workflow

Portable delivery/v1 workflow executor — a standalone, host-agnostic engine for multi-agent delivery pipelines. Hosts drive the `DeliveryRun` facade and consume the closed `Outcome` taxonomy + typed `RunEvent`s; the package ships its own reference runtime (`LocalProcessExecutor`) and CLI, so the pipeline runs with **no host at all**.

## Overview

The delivery/v1 pipeline is a multi-agent orchestration system where agents (e.g., scout, analyst, architect, implementor, reviewer, doc-sync, tester) execute over a workflow specification with gates, loops, human sign-offs, and typed edge conditions. This package IS the execution engine; hosts (the Cronos backend, CI, cron, your laptop) supply only a `NodeExecutor` (how to run node work), a `StateOps` (where state persists), and optionally a `HostPort` (where events go).

**Key responsibilities:**
- The `DeliveryRun` facade (`start` / `resume` / `outcome` / `cancel`) — the ONLY host surface
- The closed `Outcome` taxonomy (done / stalled / failed / blocked / escalated / cancelled) and typed `RunEvent` grammar
- The two ports (`NodeExecutor`, `HostPort`) + `StateOps` with conformance-tested round-trip laws
- Load and validate workflow specs (`delivery.workflow.yaml`) against JSON-Schema; compile to IR
- Parse agent return envelopes (`node_status` primary, `delivery_status` legacy) and close the agent-status vocabulary (`agent_result_from_envelope`)
- Reference runtime + standalone CLI (`python -m delivery_workflow`)
- Accumulate telemetry (tokens, USD, duration) with budget ceiling enforcement

## Standalone usage (no host required)

```bash
pip install -e packages/delivery-workflow    # or: pip install delivery-workflow

# Start a run: agent nodes spawn `claude -p <brief>` in --workdir; state
# persists in <workdir>/.delivery-run/ (state.json + events.jsonl).
python -m delivery_workflow run spec.yaml --workdir ./myrun

# A human sign-off parks the run (exit code 10, question on stderr).
# Resume with the same typed grammar every host uses:
python -m delivery_workflow run spec.yaml --workdir ./myrun \
    --resume human-answer --node signoff-scope --text "approved" --verdict approve
python -m delivery_workflow run spec.yaml --workdir ./myrun --resume retry-failed
python -m delivery_workflow run spec.yaml --workdir ./myrun --resume raise-budget --ceiling 50
python -m delivery_workflow run spec.yaml --workdir ./myrun --resume nothing

# Pure read of the persisted Outcome (JSON on stdout); cancel is terminal.
python -m delivery_workflow outcome spec.yaml --workdir ./myrun
python -m delivery_workflow cancel  spec.yaml --workdir ./myrun
```

The agent invocation is configurable: `--claude-cmd 'claude -p {brief}'` (shlex-split; `{brief}` / `{agent_ref}` / `{node_id}` placeholders). Progress streams to stderr as JSON lines (`{"event": "node_started", ...}`); stdout carries exactly one Outcome JSON object.

**Workflow specs are trusted input** — treat them like Makefiles: `exec` nodes run arbitrary shell commands in `--workdir` with your full environment (including any tokens such as `CLAUDE_CODE_OAUTH_TOKEN`), and agent nodes spawn the configured `--claude-cmd`. Only run specs you trust; the runner is not a sandbox.

**Exit codes are honest per Outcome kind** (also in `--help`):

| code | meaning |
|------|---------|
| 0    | `done` — workflow completed |
| 10   | `blocked` — parked on a human sign-off (resume with `--resume human-answer`) |
| 20   | `stalled` — terminated without full coverage (stall record in the JSON) |
| 30   | `failed` — a node failed (`--resume retry-failed`) |
| 40   | `escalated` — loop / timed-wait / iteration-cap / budget halt |
| 50   | `cancelled` — terminal until a fresh run |
| 60   | `running` — non-terminal (outcome read mid-flight) |
| 2    | usage error / unloadable spec / no persisted run |
| 3    | resume or cancel event rejected (does not match the persisted state) |

`LocalProcessExecutor` reads each child's `node_status` fence with the package's own parser and closes the status vocabulary through the **same** `agent_result_from_envelope` mapping the Cronos adapter uses — one mapping, every executor.

## Bundle Layout

```
packages/delivery-workflow/          # package root: pyproject.toml, plugin.json, tests/, docs/
└── src/delivery_workflow/       # the importable distribution (R10a src layout)
    ├── __main__.py               # Standalone CLI: python -m delivery_workflow run|outcome|cancel
    ├── delivery_run.py           # DeliveryRun facade (start / resume / outcome / cancel)
    ├── outcome.py                # Closed Outcome taxonomy + outcome_from_state()
    ├── events.py                 # Typed RunEvent grammar, NullHost, safe_emit
    ├── interface.py              # The two ports (NodeExecutor, HostPort) + StateOps / TelemetryOps
    ├── local_executor.py         # LocalProcessExecutor (spawns `claude -p`) + LocalHostPort
├── results.py               # AgentResult/GateResult/ExecResult + agent_result_from_envelope (closed vocab)
├── state_types.py           # BudgetState, NodeState, WorkflowState
├── null_runtime.py          # NullRuntime stub (raises NotImplementedError)
├── spec_loader.py           # Load and validate delivery.workflow.yaml
├── compiler_a.py            # spec dict → IRGraph
│
├── lib/                      # Portable libraries (no app.* imports)
│   ├── delivery_status.py    # Parse delivery_status blocks from agent output
│   ├── node_status.py      # Parse node_status blocks from agent output (primary envelope)
│   ├── conditions.py        # Typed edge/loop condition evaluator (runner-internal)
│   ├── exec_node.py         # run_exec_command(): the one exec-node implementation
│   ├── git_pr.py            # PR emission helper — git/gh subprocess, PROPOSED_PR.md fallback
│   ├── improve.py           # Tier-1/Tier-2 back-half applier (classifier + PR routing)
│   ├── security.py          # Security check evaluator — scanner execution, JSON parsing, decision logic
│   ├── evals/               # Portable eval corpus runner (no CC-v1 coupling)
│   │   ├── __init__.py      # Exports EvalResult and run_eval_corpus()
│   │   ├── corpus.py        # EvalResult dataclass and run_eval_corpus() implementation
│   │   └── __main__.py      # CLI: python -m delivery_workflow.lib.evals [--repo-root] [--json]
│   ├── state/
│   │   ├── store.py         # StateStore: read/write state.json atomically
│   │   ├── events.py        # EventLog: append-only events.jsonl
│   │   ├── ops.py           # StateStoreOps: THE StateOps implementation (hosts reuse it)
│   │   └── conformance.py   # Round-trip laws every StateOps must satisfy
│   └── telemetry/
│       ├── sink.py          # TelemetrySink: accumulate tokens/USD with ceiling
│       └── __init__.py
│
├── runner/                   # Work-list walker: core, dispatch, loop, scope + resume.py (typed re-entry)
├── schemas/                  # JSON-Schema validation
│   ├── delivery.workflow.schema.yaml
│   ├── research.schema.yaml
│   ├── analysis.schema.yaml
│   ├── design.schema.yaml
│   ├── frontend.schema.yaml
│   ├── implementation.schema.yaml
│   ├── review.schema.yaml
│   ├── test.schema.yaml
│   ├── doc.schema.yaml
│   ├── retro.schema.yaml
│   └── improvement.schema.yaml
│
├── tests/                    # 347 tests covering all modules
├── hooks/                    # Extensibility points (Phase 6+)
├── pyproject.toml
└── .importlinter             # Import boundary enforcement
```

## Host boundary (R10b): DeliveryRun facade + two ports

Hosts drive a run exclusively through the `DeliveryRun` facade and consume the
closed `Outcome` taxonomy plus typed `RunEvent`s — never `WorkflowState`
internals:

```python
from delivery_workflow import DeliveryRun, HumanAnswer

run = DeliveryRun(spec_path_or_graph, executor=my_executor, state_ops=my_ops, host=my_host)
outcome = run.start()                                   # -> Outcome(kind=done|stalled|failed|blocked|escalated|cancelled)
outcome = run.resume(HumanAnswer("signoff-scope", "yes", "approve"))
outcome = run.outcome()                                 # pure read, for UIs
outcome = run.cancel()                                  # persists status='cancelled'
```

The old `ExecutorInterface` is split into two ports:

```python
@runtime_checkable
class NodeExecutor(Protocol):            # executes node work
    def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult
    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult
    def runExec(self, node_id: str, command: str, inputs: dict[str, Any]) -> ExecResult

@runtime_checkable
class HostPort(Protocol):                # receives typed run events
    def on_event(self, event: RunEvent) -> None
    # RunEvent = NodeStarted | NodeFinished | RunBlocked | RunStalled
    #          | RunFailed | RunEscalated
```

`evalCondition` left the executor surface entirely — edge/loop condition
evaluation is runner-internal (`delivery_workflow.lib.conditions`); `escalate`
was replaced by `HostPort.on_event`.

### StateOps Protocol

```python
@runtime_checkable
class StateOps(Protocol):
    def read(self) -> WorkflowState
    def write(self, patch: dict[str, Any]) -> None
```

**Responsibility:** Manage the execution state of a workflow run. `read()` returns the current state (spec, run_id, node statuses, attempts, artifact paths, telemetry, budget). `write(patch)` applies a partial update atomically.

**Used by:**
- Both runtimes (Cronos, Phase 6 standalone) at each node transition
- `lib/state/store.py` provides a reference implementation using `state.json`

### TelemetryOps Protocol

```python
@runtime_checkable
class TelemetryOps(Protocol):
    def emit(self, node_id: str, data: dict[str, float]) -> None
```

**Responsibility:** Record per-node telemetry (tokens, USD, seconds). The `TelemetrySink` implementation accumulates `usd_spent` and raises `BudgetExceededSignal` if the ceiling is breached.

**Used by:**
- Both runtimes at the end of each agent/gate node
- `lib/telemetry/sink.py` provides the reference `TelemetrySink` class

### Agent Dispatch

```python
def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult
```

**Inputs:**
- `agent_ref`: string identifier (e.g., "pipeline-scout", "pipeline-architect")
- `inputs`: dict the runner forwards (`scope`, `node_id`, `attempt`, `model`, `produces`, `tools`, `recon`, `inputs`)

**Returns:** `AgentResult` with fields `status` (closed vocabulary: `done` / `blocked` / `needs_fix` / `failed`), `artifact_paths`, `produces`, `fields`, `open_questions`, `telemetry`.

Every executor closes the status vocabulary through the shared
`results.agent_result_from_envelope` mapping: no `node_status` fence →
`failed`; a status outside the vocabulary → `failed` with an
`unknown_status:<raw>` marker — never silently `done`.

**Implementations:** the Cronos adapter (`backend/app/delivery_adapter.py`, host-owned) creates a child task and reads its run trace; the in-package `LocalProcessExecutor` spawns `claude -p <brief>` and parses stdout.

### Gate Verification

```python
def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult
```

**Inputs:**
- `gate`: gate configuration (e.g., `{"kind": "verify", ...}`)
- `artifact_paths`: list of file paths to verify

**Returns:** `GateResult` with fields `decision` ("proceed" | "needs_fix" | "fail" | "retry"), `errors`, `evidence`.

**Implementation:** Invokes the packaged verifier (`delivery_workflow.lib.verify` via `delivery_workflow.lib.gate`) to validate deliverables. Both shipped executors delegate to `lib.gate.runGate`.

### Condition Evaluation (runner-internal since R10b)

Edge `when` and loop `until` expressions are evaluated by
`delivery_workflow.lib.conditions.eval_condition` inside the runner — hosts do
not implement condition evaluation.  The Cronos harness grammar
(`app.harnesses.decision`) delegates to the same module, so semantics are
identical on both paths.

### Host notification (`HostPort.on_event`, replaces `escalate`)

The runner emits typed events: `NodeStarted`/`NodeFinished` around each
dispatch, `RunBlocked(node_id, question)` for human sign-off parks,
`RunStalled(detail)` with the machine-readable stall record,
`RunFailed(node_id, reason)`, and `RunEscalated(kind, node_id, detail)` for
loop exhaust / timed waits / the global iteration cap.  Delivery is
fire-and-forget: a raising host callback is logged and swallowed.

**Implementation:** Routes the escalation to observability or human intervention. Cronos will log to structured output.

## Workflow State (`WorkflowState`)

The state shape, persisted to `state.json`:

```python
@dataclass
class WorkflowState:
    spec: str | dict                # The workflow spec (YAML or parsed)
    run_id: str                     # Unique run identifier
    status: str                     # "pending" | "running" | "done" | "failed"
    budget: BudgetState            # USD ceiling and cumulative spend
    nodes: dict[str, NodeState]    # Per-node status, attempts, telemetry, artifacts
```

Each `NodeState` tracks:
```python
@dataclass
class NodeState:
    status: str                         # "pending" | "running" | "done" | "failed"
    attempt: int                        # Retry count
    gate: dict[str, Any] | None        # Gate result
    artifact_paths: list[str]           # Produced artifacts
    telemetry: dict[str, float] | None # {tokens, usd, seconds, ...}
```

### Resume Policy

When a run resumes (e.g., after a crash or upgrade), `lib/state` uses this policy:
- **Done nodes:** skip (idempotent)
- **Failed/torn nodes:** re-dispatch (retry from scratch)
- **Absent nodes:** dispatch (first time)

Atomic writes to `state.json` (tempfile + `os.replace`) ensure consistency.

## Libraries


### `lib/node_status`

**Primary agent return envelope parser** — parses `node_status` fenced JSON blocks from agent output (the general-purpose envelope introduced in SG2).

```markdown
node_status
{
  "status": "done | blocked | needs_fix | failed",
  "artifact_paths": ["path/to/report.md"],
  "produces": "research | analysis | design | implementation | review | test | doc | frontend",
  "fields": {
    "verdict": "pass | needs_fix",
    "has_ui": true,
    "files_changed": ["src/x.py"]
  },
  "open_questions": []
}
```

Returns a typed `NodeStatusBlock` object with status, artifact paths, and routing fields. Agents migrated to `node_status` (all 12 canonical agents as of SG2) now use this envelope; the runtime prefers parsing `node_status` over the legacy `delivery_status`.

### `lib/delivery_status` (legacy)

**Legacy agent return envelope parser** — parses `delivery_status` fenced blocks from agent output. Fully supported as a tier-3 fallback for backward compatibility. No deprecation warning — runtimes should handle both fence types indefinitely.

Parses `delivery_status` blocks:

```markdown
delivery_status
phase: design
status: done
artifacts_produced: ["doc.md", "spec.yaml"]
tokens_used: 8240
```

Returns a typed `DeliveryStatus` object with phase, status, artifacts, and token counts.


### `lib/git_pr`

**Portable git/gh PR helper** for emitting Tier-1 improvement proposals (spec §3.2, DD-002). Provides `emit_pr()` which creates a GitHub PR via the `gh` CLI when available, or writes a fallback `PROPOSED_PR.md` when unavailable.

**Key features:**
- Captures a stable base ref before creating any branch (prevents branch-stacking across findings)
- Always restores HEAD to the original branch after emission (success or failure)
- Subprocess-only, zero `app.*`/`backend.*` imports — fully portable
- Injectable `runner` and `gh_probe` parameters for testing without real git/gh

```python
from delivery_workflow.lib.git_pr import emit_pr

url_or_path = emit_pr(
    title="tier1-improvement(F1): agent_prompt — clearer instructions",
    body="## Tier-1 Improvement Proposal\n...",
    finding_id="F1",
    branch="delivery-improve-tier1-F1",
    repo_root="/data/repo",
    proposals_dir="/data/repo/.cronos/improvement-tier1/",
)
# Returns: "https://github.com/user/repo/pull/123" or "/data/repo/.cronos/improvement-tier1/proposed-pr-F1.md"
```

### `lib/improve`

**Tier-1/Tier-2 back-half applier** for delivery/v1 self-improvement (spec §3.2–3.5, DD-001–003). Routes retro findings into three tiers and applies the correct action per tier:
- **Tier 0:** auto-applied in-place (snapshot → apply → eval → keep/rollback; handled elsewhere)
- **Tier 1:** emit a PR (proposal document, never in-place source edit)
- **Tier 2:** escalate to human (no file write, no branch)

**Public API:**
```python
from delivery_workflow.lib.improve import classify_findings, render_proposal, run_back_half

# 1. Classify findings by fix_type (fix_type is authoritative, not declared tier)
routed = classify_findings(findings)  # → Routed(tier0=[], tier1=[...], tier2=[...])

# 2. Render PR title/body for a Tier-1 finding
title, body = render_proposal(finding)

# 3. Run the Tier-1/Tier-2 back-half (emits PRs when evals pass)
result = run_back_half(
    tier1=routed.tier1,
    tier2=routed.tier2,
    evals_passed=True,  # Only emit Tier-1 PRs if evals exit 0
    repo_root="/data/repo",
    proposals_dir="/data/repo/.cronos/improvement-tier1/",
)
# → BackHalfResult(tier1_pr_urls=["..."], tier1_findings=["F1"], tier2_escalated=["A1"], errors=[])
```

**CLI usage:**
```bash
python -m delivery_workflow.lib.improve <retro_artifact> \
    --evals-passed [true|false] \
    --proposals-dir <path> \
    [--repo-root <path>]
# Prints JSON: {tier1_pr_urls, tier1_findings, tier2_escalated, errors}
```

**Key design:**
- `classify_findings()` is the sole router (fix_type-authoritative)
- Tier-0 consume only `tier0` list; back-half consumes `tier1`/`tier2` (structural safety guarantee for REQ-005)
- No PR is emitted if `evals_passed=False` (REQ-002)
- All writes are additive proposal documents, never in-place source edits

### `lib/security`

**Security check evaluator** — extracts scanner execution and decision logic from the Cronos `gate.py` into a portable module, shared by both Cronos and the Phase-6 standalone runner.

**Public API:**
```python
from delivery_workflow.lib.security import evaluate_security

decision, errors, evidence = evaluate_security(
    check={
        "scanners": ["bandit", "semgrep"],
        "fail_on": ["HIGH"],
        "on_missing_scanner": "skip",
    },
    artifact_paths=["artifact.md"],
    space=Path("."),
)
# decision: "proceed" | "needs_fix" | "fail" | "retry"
# evidence dict includes: effective_finding_class, has_fail_on_hit, agent_verdict, scanner_results, ...
```

**Key features:**
- Runs real security scanners (bandit, semgrep, etc.) and parses JSON output
- **Full JSON parsing** (not truncated) — fixes DD-002 fail-open bug where >2 KB scanner output was silently scored clean
- Reconciles scanner findings with agent verdict from security-reviewer artifact
- Maps findings to decision (proceed/needs_fix/fail) based on severity and fail_on policy
- Handles missing scanners per policy (fail/skip/warn)
- Infra crashes (scanner not found, JSON parse error) trigger auto-retry
- Zero `app.*` imports — fully portable

**Signature:**
- `evaluate_security(check: dict, artifact_paths: list[str], space: Path | None) -> tuple[str, list[str], dict]`
- Returns the same contract as Cronos `gate.py:_check_security` for drop-in delegation

### `lib/evals`

**Portable eval corpus runner** — invokes a test/validation command and returns structured results. Enables Cronos gate, improve flow, and Phase-6 standalone runner to share one eval mechanism.

**Public API:**
```python
from delivery_workflow.lib.evals import run_eval_corpus, EvalResult

result = run_eval_corpus(
    repo_root="/path/to/repo",
    eval_cmd="pytest packages/delivery-workflow/tests/ -q",  # or None to use default
    env={"DELIVERY_EVAL_CMD": "pytest ... -k custom"},       # or None
    runner=subprocess.run,  # injectable for testing
)
# result: EvalResult(passed=True, exit_code=0, command="...", output_tail="...")
```

**CLI:**
```bash
python -m delivery_workflow.lib.evals [--repo-root /path] [--json]
# Exits with corpus exit code; --json prints EvalResult as JSON
```

**Command precedence:** `eval_cmd` arg → `DELIVERY_EVAL_CMD` env → default `pytest packages/delivery-workflow/tests/ -q --no-header`

**Key features:**
- Single source of truth for default + override (no more inlined shell prose in improve SKILL)
- Structured `EvalResult` dataclass with passed flag, exit code, and output
- Environment variable override for standalone + Cronos parity
- Fully portable; no `app.*` imports

**Used by:** `lib/improve.py` (Tier-0 keep/rollback decision) and `improve/SKILL.md` (Step 5 corpus evaluation)

### `lib/state`

**`StateStore`** — CRUD for `state.json`:

```python
store = StateStore(Path("/run/dir"))
state = store.read()              # WorkflowState
state.budget.usd_spent = 100.0
store.write(state)                # Atomic write (tempfile + os.replace)
```

**Resume support:** `resume_node_status(node_state)` returns "skip", "re-dispatch", or "dispatch" based on node history.

**`EventLog`** — Append-only `events.jsonl` for audit trails and replay.

### `lib/telemetry`

**`TelemetrySink`** — Accumulates per-node telemetry with optional persistence:

```python
sink = TelemetrySink(usd_ceiling=100.0, state_store=store)

# Agent finishes; record tokens/USD/seconds
sink.emit("agent_01", {"tokens": 5000, "usd": 0.15, "seconds": 42})

# Budget breach raises signal
sink.emit("agent_02", {"tokens": 1000000, "usd": 50.0, "seconds": 10})
# → BudgetExceededSignal(51.5, 100.0)
```

If a `StateStore` is provided, `emit()` persists the node's telemetry to `state.json` atomically. Otherwise, telemetry accumulates in memory (transient sink).

## Runtimes: Cronos & Phase 6

### Cronos Runtime (G6.1 — Current)

The Cronos backend adopts delivery/v1 via `CronosAdapter` in `backend/app/delivery_adapter.py` — **host code, not part of this package** (R10c, 02-package-boundary.md §2.3). The host imports the package's `StateStore`/`EventLog`/`TelemetrySink`/`StateStoreOps` and result types; the package carries zero Cronos knowledge.

**Port surface mapped to the Cronos backend** (`NodeExecutor` + `HostPort` split, R10b — plus the state/telemetry ops):

| Operation | Implementation |
|---|---|
| `dispatchAgent` | Create child task, poll state, load trace, parse node_status (primary) or delivery_status (legacy) → `AgentResult` |
| `runGate` | Delegate to `delivery_workflow.lib.gate.runGate()` → `GateResult` with decision/errors/evidence |
| (conditions) | Runner-internal via `lib.conditions.eval_condition()` — not an adapter op since R10b |
| `state.read/write` | `lib/state/ops.StateStoreOps` (package-native; re-exported by the host as `CronosStateOps`) → atomic read/write + EventLog audit trail |
| `telemetry.emit` | `CronosTelemetryOps` → `lib/telemetry/TelemetrySink` accumulate tokens/USD with ceiling |
| `on_event` | `RunBlocked`/`RunEscalated` park the tracking task → WAITING + waiting_question |

**Features:**
- ✓ Async dispatch loop with configurable poll interval + timeout
- ✓ Delivery status parsing from trace (primary) + artifact fallback
- ✓ Budget enforcement: `BudgetExceededSignal` → escalate
- ✓ Atomic state: read-modify-write with `StateStore` + append-only event log
- ✓ Idempotent escalation: no-op if task already WAITING
- ✓ Gate result persistence to state.json

**Status:**
- ✓ G6.1: All 6 ops + 60+ tests across 7 test files
- ✓ G6.2: End-to-end SDLC milestone verified (scout → release with gates, loops, routing)
- ✓ Review: PASS (commit 3432044)
- ✓ Test: PASS (commit cf3a91f)

See `backend/app/delivery_adapter.py` (module docstring) for detailed operation mapping and integration points.

### Standalone runtime (shipped — R10e)

The package's own reference runtime (see "Standalone usage" above):
- `LocalProcessExecutor` implements `NodeExecutor` by spawning `claude -p <brief>` per agent node (configurable argv template), delegating gates to `lib.gate` and exec nodes to `lib.exec_node`
- `LocalHostPort` implements `HostPort` by printing JSON progress lines
- `python -m delivery_workflow` wires spec_loader → compiler_a → `DeliveryRun` with `StateStoreOps` persistence in `<workdir>/.delivery-run/`
- Resume / retry / budget / cancel flow through the same typed grammar every host uses

## Testing

**The conformance suite (`tests/conformance/`) is the compatibility gate**: it
drives the SHIPPED `delivery.workflow.yaml` through the real
loader → compiler → `DeliveryRun` facade with real disk persistence and
scripted park→resume lifecycles, asserting Outcomes, dispatch counts, and the
StateOps round-trip law (mirror-vs-disk). Any change to runner semantics,
persistence, or the host surface must keep it green — it runs with zero
Cronos imports, exactly as a third-party host would.

Highlighted suites:

- **test_package_skeleton.py** — module structure, imports
- **test_import_boundary.py** — AST verification that no `app.*` imports leak into portable core (auto-verifies new `lib/security.py` and `lib/evals/` modules)
- **test_interface_nullruntime.py** — Protocol compliance, `NullRuntime` raises `NotImplementedError`
- **test_spec_loader.py** — spec loading, validation against schema, malformed rejection
- **test_schemas.py** — artifact-class schemas (research, analysis, design, etc.)
- **test_node_status.py** — parsing `node_status` blocks (primary)
- **test_delivery_status.py** — parsing `delivery_status` blocks (legacy)
- **test_security_lib.py** — `lib/security.py` scanner execution, JSON parsing, missing-scanner policy, agent-verdict precedence, DD-002 regression (>2 KB JSON must parse, not score clean)
- **test_evals_lib.py** — `lib/evals` corpus runner, command precedence (arg→env→default), passed flag, exit-code propagation, CLI smoke tests
- **test_state.py** — `StateStore` read/write, atomic updates, resume policy
- **test_telemetry.py** — `TelemetrySink` accumulation, budget ceiling, persistence
- **test_tier1_no_auto_apply.py** — REQ-005 hard safety: agents/skills files byte-identical after Tier-1 run
- **test_improve.py** — Tier-1/Tier-2 routing, no-PR-on-red, one-PR-per-finding, Tier-2 escalate-only, fence fields
- **test_delivery_run_facade.py** — DeliveryRun lifecycle, typed-event delivery, cancel semantics, Outcome derivation
- **test_local_executor.py** — the reference runtime: fence parse, closed-vocab mapping, timeout/nonzero-exit/no-binary failure paths
- **test_cli_standalone.py** — subprocess CLI smoke with a fake `claude` on PATH: run → park → resume → done, retry-failed, cancel, exit codes, and the no-`app`-in-`sys.modules` purity pin

Run with:
```bash
cd packages/delivery-workflow
pip install -e ".[dev]"
pytest tests/ -v
```

## Import Boundary

The package is isolated from Cronos internals via `import-linter`:

```
forbidden: app.* (Cronos backend)
forbidden: backend.* (legacy)
```

Violations caught by:
1. **CI job** (`.github/workflows/ci.yml`): runs `lint-imports` after pytest
2. **AST test** (`test_import_boundary.py`): scans all .py files for `import app` or `import backend`

This ensures the portable core can be adopted by any runtime without coupling to Cronos.

## Installation

**Monorepo (development):**
```bash
pip install -e packages/delivery-workflow
```

**Backend dev dependencies:**
```bash
cd backend
pip install -e ".[dev]"  # includes -e ../packages/delivery-workflow
```

**As a published package (future):**
```bash
pip install delivery-workflow
```

## Next Steps

- **Phase 6 (I7.6+):** Implement standalone runner with `StateStore` persistence and full USD cost tracking
- **Phase 6 (I7.7):** Wire `lib/state` into `backend/app/pipeline/` for atomic state checkpoints
- **Phase 7:** Integrate Phase 6 standalone runtime; retire Cronos event-loop iteration
