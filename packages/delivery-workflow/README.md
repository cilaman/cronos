# delivery-workflow

Portable delivery/v1 workflow executor library — the foundational package for the delivery pipeline system. Provides a 6-operation executor interface, workflow spec loading, state management, and telemetry accumulation.

## Overview

The delivery/v1 pipeline is a multi-agent orchestration system where agents (e.g., scout, analyst, architect, implementor, reviewer, doc-sync, tester) execute sequentially over a workflow specification. This package defines the portable core that any runtime can adopt to execute delivery pipelines.

**Key responsibilities:**
- Define the executor interface (6 operations typed as runtime-checkable Protocols)
- Load and validate workflow specs (`delivery.workflow.yaml`) against JSON-Schema
- Parse agent return envelopes (`node_status` primary, `delivery_status` legacy)
- Manage execution state (read/write, atomic updates, resume policy)
- Accumulate telemetry (tokens, USD, duration) with budget ceiling enforcement
- Provide a null implementation for testing

## Bundle Layout

```
packages/delivery-workflow/
├── interface.py              # 6-op executor Protocol + StateOps / TelemetryOps
├── results.py               # AgentResult, GateResult, TelemetryData
├── state_types.py           # BudgetState, NodeState, WorkflowState
├── null_runtime.py          # NullRuntime stub (raises NotImplementedError)
├── spec_loader.py           # Load and validate delivery.workflow.yaml
│
├── lib/                      # Portable libraries (no app.* imports)
│   ├── delivery_status.py    # Parse delivery_status blocks from agent output
│   ├── node_status.py      # Parse node_status blocks from agent output (primary envelope)
│   ├── git_pr.py            # PR emission helper — git/gh subprocess, PROPOSED_PR.md fallback
│   ├── improve.py           # Tier-1/Tier-2 back-half applier (classifier + PR routing)
│   ├── security.py          # Security check evaluator — scanner execution, JSON parsing, decision logic
│   ├── evals/               # Portable eval corpus runner (no CC-v1 coupling)
│   │   ├── __init__.py      # Exports EvalResult and run_eval_corpus()
│   │   ├── corpus.py        # EvalResult dataclass and run_eval_corpus() implementation
│   │   └── __main__.py      # CLI: python -m lib.evals [--repo-root] [--json]
│   ├── state/
│   │   ├── store.py         # StateStore: read/write state.json atomically
│   │   └── events.py        # EventLog: append-only events.jsonl
│   └── telemetry/
│       ├── sink.py          # TelemetrySink: accumulate tokens/USD with ceiling
│       └── __init__.py
│
├── runner/                   # Abstract runner (Phase 6+)
├── adapters/
│   └── cronos/              # Cronos ExecutorInterface implementation (G6.1)
│       ├── adapter.py       # CronosAdapter (6 ops) + helpers
│       ├── fixtures/        # Test fixtures (e.g., sdlc_ping.yaml)
│       ├── README.md        # Operation mapping and integration guide
│       └── __init__.py      # Module marker
│
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

## Executor Interface (6 Operations)

The core abstraction is `ExecutorInterface`, a runtime-checkable Protocol defining the operations a runtime must implement to execute a delivery pipeline:

```python
@runtime_checkable
class ExecutorInterface(Protocol):
    state: StateOps                      # Read and write execution state
    telemetry: TelemetryOps              # Record telemetry per node
    
    def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult
    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult
    def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool
    def escalate(self, node_id: str, reason: str) -> None
```

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
- `inputs`: dict with keys like `prompt`, `goal_slug`, `task_id`, etc.

**Returns:** `AgentResult` with fields:
- `success: bool`
- `result: str` (agent's final_text / stdout)
- `exit_reason: str` (status marker or failure reason)

**Implementation:** Runtime-specific. Cronos spawns `claude code -s <space> <agent_ref>` subprocess; Phase 6 will invoke a web API.

### Gate Verification

```python
def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult
```

**Inputs:**
- `gate`: gate configuration (e.g., `{"kind": "verify", ...}`)
- `artifact_paths`: list of file paths to verify

**Returns:** `GateResult` with fields:
- `verdict: str` ("pass" | "fail" | "escalate")
- `details: str` (explanation)

**Implementation:** Invokes the backend verifier (e.g., `backend/app/pipeline/verify.py`) to validate deliverables.

### Condition Evaluation

```python
def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool
```

**Inputs:**
- `expr`: condition expression (e.g., `"exit_reason == 'SUCCESS'"`)
- `scope`: variables available in the expression

**Returns:** boolean result

**Implementation:** Evaluates the condition against the scope. Cronos will reuse the decision logic from harness control flow.

### Escalation

```python
def escalate(self, node_id: str, reason: str) -> None
```

**Inputs:**
- `node_id`: ID of the node encountering a recoverable error
- `reason`: escalation reason

**Returns:** None (escalation is a signal; handling is runtime-specific)

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
from lib.git_pr import emit_pr

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
from lib.improve import classify_findings, render_proposal, run_back_half

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
python -m lib.improve <retro_artifact> \
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
from lib.security import evaluate_security

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
from lib.evals import run_eval_corpus, EvalResult

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
python -m lib.evals [--repo-root /path] [--json]
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

The Cronos backend adopts delivery/v1 via `CronosAdapter` in `packages/delivery-workflow/adapters/cronos/adapter.py`.

**6 operations mapped to Cronos backend:**

| Operation | Implementation |
|---|---|
| `dispatchAgent` | Create child task, poll state, load trace, parse node_status (primary) or delivery_status (legacy) → `AgentResult` |
| `runGate` | Delegate to `app.pipeline.gate.runGate()` → `GateResult` with decision/errors/evidence |
| `evalCondition` | Delegate to `lib.conditions.eval_condition()` for conditional routing |
| `state.read/write` | `CronosStateOps` → `lib/state/StateStore` atomic read/write + EventLog audit trail |
| `telemetry.emit` | `CronosTelemetryOps` → `lib/telemetry/TelemetrySink` accumulate tokens/USD with ceiling |
| `escalate` | Park tracking task → WAITING + waiting_question for human intervention |

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

See `adapters/cronos/README.md` for detailed operation mapping and integration points.

### Phase 6 Standalone Runtime (Future)

A separate orchestrator (Phase 6+) will:
- Implement `ExecutorInterface` to invoke a Cronos API endpoint for agent dispatch
- Use `lib/state/StateStore` for full persistence to `state.json`
- Use `lib/telemetry/TelemetrySink` with a configured state_store for atomic budget tracking
- Handle resume/retry/escalation locally

## Testing

The package includes 347 tests:

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
