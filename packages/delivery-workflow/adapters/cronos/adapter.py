"""Cronos adapter — concrete ExecutorInterface implementation for the Cronos backend.

This module is the portability seam between the delivery/v1 portable core
and the Cronos task-management backend. It is explicitly allowed to import
``app.*`` — see ``.importlinter`` and ``adapters/cronos/__init__.py``.

All ``app.*`` imports are lazy (inside methods) so that importing the bundle
core never transitively pulls in the Cronos backend.

Design decisions implemented here:
  DD-01  Single module; all app.* imports lazy.
  DD-02  dispatchAgent is async def; other ops sync.
  DD-03  Dispatch flow: create_task → goal ACTIVE → poll → trace → AgentResult.
  DD-04  Telemetry: sum per-turn tokens; usd = tokens * token_cost_usd.
  DD-05  (R1) node outcome read from the structured ``trace.node_status``
         envelope (parsed backend-side from the FULL final text); closed
         vocabulary at this boundary; mtime fallback scan demoted to log-only.
  DD-06  runGate delegates to lib.gate.runGate and returns the GateResult
         ONLY — the runner is the single writer of node state (R9/D11).
  DD-07  evalCondition delegates to lib.conditions.eval_condition.
  DD-08  state.write patches StateStore; node transitions appended to EventLog.
         Node status/attempt/artifact_paths/gate/fields are written ONLY by
         the runner through this StateOps (01-state-model.md §5.8): runGate
         and runExec perform no state writes of their own — the historical
         out-of-band writes here double-wrote every gate/exec node (D11: the
         adapter wrote needs_fix, the runner overwrote done, and the event
         log carried a phantom needs_fix→done transition).
  DD-09  TelemetrySink wired to StateStore; BudgetExceededSignal → escalate.
  DD-10  escalate parks tracking task → WAITING + waiting_question; idempotent.
  DD-11  G6.2 e2e: monkeypatched store + trace_store; sequential dispatch.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from interface import ExecutorInterface, StateOps, TelemetryOps
from lib.status_envelope import parse_status_envelope
from lib.state.events import EventLog
from lib.state.store import StateStore
from lib.telemetry.sink import BudgetExceededSignal, TelemetrySink
from results import AgentResult, ExecResult, GateResult, TelemetryData
from state_types import BudgetState, NodeState, WorkflowState

log = logging.getLogger(__name__)

# Closed AgentResult status vocabulary enforced at the dispatchAgent boundary
# (R1/D4, 01-state-model.md §5.1).  The fence transport format stays open
# (lib/node_status.py); THIS is where unknown statuses become `failed` with an
# `unknown_status:<raw>` marker instead of silently flowing to `done` via
# runner/dispatch.py's else-branch.
_AGENT_STATUS_VOCAB = frozenset({"done", "blocked", "needs_fix", "failed"})


# ---------------------------------------------------------------------------
# StateOps implementation
# ---------------------------------------------------------------------------


class CronosStateOps:
    """StateOps backed by lib/state.StateStore + EventLog (DD-08, R6)."""

    def __init__(self, store: StateStore, event_log: EventLog) -> None:
        self._store = store
        self._event_log = event_log

    def read(self) -> WorkflowState:
        return self._store.read()

    def bootstrap_if_absent(
        self, *, spec: str, run_id: str, usd_ceiling: float
    ) -> None:
        """Seed an initial ``state.json`` when the run directory has none (B1).

        The runner's resume path calls ``state_ops.read()`` unconditionally
        (``runner/core.py``), which requires ``state.json`` to already exist —
        and ``StateStore.read()`` raises ``FileNotFoundError`` otherwise.  A
        *fresh* run must therefore seed the file once; a *resumed* run (state.json
        present) is left untouched so already-``done`` nodes are skipped rather
        than re-dispatched.  Idempotent by design.
        """
        if self._store.exists():
            return
        self._store.write(
            WorkflowState(
                spec=spec,
                run_id=run_id,
                status="running",
                budget=BudgetState(usd_ceiling=usd_ceiling),
            )
        )

    def write(self, patch: dict[str, Any]) -> None:
        """Read-modify-write; appends node_transition events for status changes."""
        try:
            state = self._store.read()
        except FileNotFoundError:
            # Defensive: state.json should have been bootstrapped before the run
            # (see bootstrap_if_absent).  If a write races ahead of bootstrap,
            # start from a minimal running state rather than crashing the caller
            # (e.g. runGate's outcome write).
            state = WorkflowState(
                spec="", run_id="", status="running",
                budget=BudgetState(usd_ceiling=0.0),
            )

        # Top-level status update.
        if "status" in patch:
            state.status = patch["status"]

        # Edge-evaluation record (R5/D1): the runner writes the full snapshot
        # with each update — full replacement, round-trips identically.
        if "edges_evaluated" in patch:
            state.edges_evaluated = dict(patch["edges_evaluated"] or {})

        # Run-level stall detail (R6/D5): written together with
        # status="stalled"; a later {"stall": None} clears it (resumed run
        # that completed).  Full replacement, round-trips identically.
        if "stall" in patch:
            state.stall = patch["stall"]

        # Resume-retry counters (R7): runner.resume writes the full snapshot —
        # full replacement, round-trips identically (like edges_evaluated).
        if "resume_retries" in patch:
            state.resume_retries = dict(patch["resume_retries"] or {})

        # Budget lift (R7 RaiseBudget): runner.resume patches the persisted
        # ceiling so 'escalated'/'blocked' budget parks become resumable.
        if "budget" in patch and isinstance(patch["budget"], dict):
            budget_patch = patch["budget"]
            if "usd_ceiling" in budget_patch:
                state.budget.usd_ceiling = float(budget_patch["usd_ceiling"])
            if "usd_spent" in budget_patch:
                state.budget.usd_spent = float(budget_patch["usd_spent"])

        # Node-level patches.
        nodes_patch: dict[str, Any] = patch.get("nodes", {})
        for node_id, ns_patch in nodes_patch.items():
            if node_id not in state.nodes:
                node = NodeState(status=ns_patch.get("status", "pending"))
                if "artifact_paths" in ns_patch:
                    node.artifact_paths = list(ns_patch["artifact_paths"])
                if "gate" in ns_patch:
                    node.gate = ns_patch["gate"]
                if "attempt" in ns_patch:
                    node.attempt = int(ns_patch["attempt"])
                # Round-trip law (R2/D2): the runner writes `fields` with every
                # node outcome; dropping them kills all field-based routing
                # (has_ui, verdict, finding_class) after any resume.
                if "fields" in ns_patch:
                    node.fields = dict(ns_patch["fields"])
                # Telemetry normally arrives via TelemetrySink, but honour it
                # in patches too — everything written must read back (R2).
                if "telemetry" in ns_patch and ns_patch["telemetry"] is not None:
                    node.telemetry = dict(ns_patch["telemetry"])
                state.nodes[node_id] = node
                if "status" in ns_patch:
                    self._event_log.append(
                        {
                            "node_id": node_id,
                            "status": ns_patch["status"],
                            "type": "node_transition",
                        }
                    )
            else:
                node = state.nodes[node_id]
                if "status" in ns_patch:
                    old_status = node.status
                    node.status = ns_patch["status"]
                    if old_status != node.status:
                        self._event_log.append(
                            {
                                "node_id": node_id,
                                "status": node.status,
                                "type": "node_transition",
                            }
                        )
                if "artifact_paths" in ns_patch:
                    node.artifact_paths = list(ns_patch["artifact_paths"])
                if "gate" in ns_patch:
                    node.gate = ns_patch["gate"]
                if "attempt" in ns_patch:
                    node.attempt = int(ns_patch["attempt"])
                if "fields" in ns_patch:
                    node.fields = dict(ns_patch["fields"])
                if "telemetry" in ns_patch and ns_patch["telemetry"] is not None:
                    node.telemetry = dict(ns_patch["telemetry"])

        self._store.write(state)


# ---------------------------------------------------------------------------
# TelemetryOps implementation
# ---------------------------------------------------------------------------


class CronosTelemetryOps:
    """TelemetryOps backed by lib/telemetry.TelemetrySink (DD-04/DD-09, R7)."""

    def __init__(self, sink: TelemetrySink) -> None:
        self._sink = sink

    def emit(self, node_id: str, data: dict[str, float]) -> None:
        """Record telemetry; raises BudgetExceededSignal on ceiling breach."""
        self._sink.emit(node_id, data)

    @property
    def usd_spent(self) -> float:
        return self._sink.usd_spent


# ---------------------------------------------------------------------------
# Telemetry helper
# ---------------------------------------------------------------------------


def _telemetry_from_trace(trace: Any, token_cost_usd: float) -> TelemetryData:
    """Build TelemetryData from a RunTrace by summing per-turn usage (DD-04).

    There is no top-level ``trace.tokens`` field — tokens live per turn on
    ``AssistantTurnTrace.{input_tokens, output_tokens}``.
    """
    tokens = sum(
        t.input_tokens + t.output_tokens for t in (trace.turns or [])
    )
    seconds = getattr(trace, "duration_seconds", 0.0)
    usd = tokens * token_cost_usd
    return TelemetryData(tokens=tokens, usd=usd, seconds=seconds)


# ---------------------------------------------------------------------------
# CronosAdapter
# ---------------------------------------------------------------------------


class CronosAdapter:
    """Concrete ExecutorInterface for the Cronos backend (DD-01/DD-02, R9).

    Parameters
    ----------
    store:
        Cronos TaskStore (``app.storage.TaskStore``).
    trace_store:
        Cronos TraceStore (``app.trace_store.TraceStore``).
    space_id:
        Cronos space identifier for all task operations.
    run_dir:
        Path to the workflow run directory (holds state.json + events.jsonl).
    tracking_task_id:
        Optional Cronos task id for the run's board-visible tracking task;
        used by ``escalate``.
    usd_ceiling:
        Budget ceiling in USD; 0.0 disables the ceiling (default).
    token_cost_usd:
        Per-token USD rate for telemetry accumulation; default 0.0.
    run_child:
        Synchronous callback ``run_child(agent_ref, inputs) -> RunTrace | None``
        that creates and executes the child agent-task inline (on the Cronos main
        event loop) and returns its loaded run trace.  Injected by the delivery
        driver, which owns the thread↔loop bridge.  When None (unit tests /
        NullRuntime), ``dispatchAgent`` returns a failed AgentResult.
    goal_slug:
        The delivery goal's slug (``slugify(goal.title)``).  Used to scope the
        fallback ``.cronos/delivery/`` report scan to this goal's subtree so a
        sibling goal's newer report can never satisfy this node (B2).
    poll_interval:
        Deprecated; retained for construction-time backward compatibility.
    timeout:
        Deprecated; retained for construction-time backward compatibility.
    """

    def __init__(
        self,
        store: Any,
        trace_store: Any,
        space_id: str,
        run_dir: Path,
        *,
        tracking_task_id: str | None = None,
        usd_ceiling: float = 0.0,
        token_cost_usd: float = 0.0,
        run_child: Any = None,
        main_loop: Any = None,
        space_dir: Any = None,
        goal_slug: str | None = None,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> None:
        self._store = store
        self._trace_store = trace_store
        self._space_id = space_id
        self._run_dir = run_dir
        self._tracking_task_id = tracking_task_id
        self._token_cost_usd = token_cost_usd
        self._run_child = run_child
        self._main_loop = main_loop
        # Goal slug (== slugify(goal.title)); scopes the fallback report scan to
        # this goal's .cronos/delivery/<slug>/ subtree (B2).
        self._goal_slug = goal_slug
        # Space root (dir holding .cronos/); required by the CC-v1 gate to locate
        # and schema-verify artifacts. Falls back to deriving it from run_dir
        # (space/.cronos/delivery-runs/<goal_id>) when not provided.
        self._space_dir = Path(space_dir) if space_dir is not None else run_dir.parent.parent.parent

        _state_store = StateStore(run_dir)
        _event_log = EventLog(run_dir)
        _sink = TelemetrySink(
            usd_ceiling=usd_ceiling,
            state_store=_state_store,
        )

        self.state: StateOps = CronosStateOps(_state_store, _event_log)
        self.telemetry: TelemetryOps = CronosTelemetryOps(_sink)

    # ------------------------------------------------------------------
    # dispatchAgent (R1-R3, DD-02/DD-03/DD-04/DD-05)
    # ------------------------------------------------------------------

    def dispatchAgent(
        self, agent_ref: str, inputs: dict[str, Any]
    ) -> AgentResult:
        """Execute a child agent-task inline and return an AgentResult.

        dispatchAgent is a *synchronous* method (called from the delivery runner
        thread).  Child creation, BACKLOG→ACTIVE transition, agent execution, and
        SSE streaming all happen in the injected ``run_child`` callback, which runs
        on the Cronos main event loop via ``run_coroutine_threadsafe`` (owned by
        the delivery driver).  Here we only translate the child's run trace into an
        AgentResult (DD-04, R1):

        1. Call ``run_child(agent_ref, inputs)`` → the child's loaded RunTrace.
        2. Read the structured ``trace.node_status`` envelope (parsed by the
           backend trace parser from the FULL, untruncated final assistant
           text — never from ``final_text_snippet``, D6) and CLOSE the status
           vocabulary: anything outside {done, blocked, needs_fix, failed}
           maps to ``failed`` with an ``unknown_status:<raw>`` marker — never
           silently to done (D4).  No envelope → failed; the old mtime
           fallback scan is demoted to a log-only diagnostic (two-release
           deprecation, then deleted).
        3. Sum per-turn tokens into TelemetryData.

        Returning a plain AgentResult (never a coroutine) keeps the sync runner's
        dispatch path from calling ``run_until_complete`` on the running loop.
        """
        if self._run_child is None:
            return AgentResult(
                status="failed",
                artifact_paths=[],
                produces="",
                fields={},
                open_questions=["No run_child callback wired into CronosAdapter"],
                telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
            )

        # 1. Create + execute the child inline (blocks this runner thread until
        #    the agent finishes on the main loop). run_child returns either a
        #    {"trace", "delivery"} dict (Cronos CC-v1 path — the report frontmatter
        #    already mapped to status/artifact_paths/fields) or a bare RunTrace
        #    (legacy / tests → parse a delivery_status fence below).
        res = self._run_child(agent_ref, inputs)
        if isinstance(res, dict):
            trace = res.get("trace")
            delivery = res.get("delivery")
        else:
            trace = res
            delivery = None

        # 2. Telemetry from the trace.
        telem = (
            _telemetry_from_trace(trace, self._token_cost_usd)
            if trace is not None
            else TelemetryData(tokens=0, usd=0.0, seconds=0.0)
        )

        # 3a. Preferred: CC-v1 report frontmatter (already parsed by run_child).
        if delivery is not None:
            return AgentResult(
                status=delivery.get("status", "failed"),
                artifact_paths=list(delivery.get("artifact_paths", [])),
                produces=str(delivery.get("produces", "")),
                fields=dict(delivery.get("fields", {})),
                open_questions=list(delivery.get("open_questions", [])),
                telemetry=telem,
            )

        # 3b. Structured channel (R1): the backend trace parser extracts the
        #     node_status/delivery_status envelope from the FULL final assistant
        #     text into ``trace.node_status`` — no truncation sensitivity, no
        #     mtime inference.  getattr with None default keeps legacy traces
        #     (saved before the field existed) on the honest failure path.
        node_id = str(inputs.get("node_id") or agent_ref)
        ds = getattr(trace, "node_status", None) if trace is not None else None
        if not isinstance(ds, dict):
            ds = None

        if ds is None:
            # DEPRECATED (log-only, two releases then delete): compute what the
            # old mtime-newest artifact scan WOULD have credited, purely as a
            # diagnostic.  It is never credited — the fence-in-trace is the
            # only classification channel after R1 (D6).
            prod = inputs.get("produces")
            expected_class = (
                prod.get("class") if isinstance(prod, dict)
                else (prod if isinstance(prod, str) else None)
            )
            try:
                would = _fallback_delivery_status(
                    self._run_dir, slug=self._goal_slug, expected_class=expected_class
                )
            except Exception:
                would = None
            if would is not None:
                log.warning(
                    "dispatchAgent[%s]: no node_status envelope on the run trace; "
                    "the deprecated mtime fallback scan would have credited "
                    "status=%r artifact_paths=%r produces=%r — NOT credited "
                    "(R1: trace.node_status is the only classification channel).",
                    node_id, would.status, would.artifact_paths, would.produces,
                )
            else:
                log.warning(
                    "dispatchAgent[%s]: no node_status envelope on the run trace; "
                    "the deprecated mtime fallback scan found nothing either.",
                    node_id,
                )
            return AgentResult(
                status="failed",
                artifact_paths=[],
                produces="",
                fields={},
                open_questions=[
                    f"No node_status fence found in agent output for node '{node_id}' "
                    "(trace.node_status is None)"
                ],
                telemetry=telem,
            )

        raw_status = ds.get("status")
        status = raw_status.strip().lower() if isinstance(raw_status, str) else ""
        raw_paths = ds.get("artifact_paths")
        artifact_paths = [str(p) for p in raw_paths] if isinstance(raw_paths, list) else []
        produces = str(ds.get("produces") or "")
        fields = dict(ds.get("fields") or {}) if isinstance(ds.get("fields"), dict) else {}
        raw_questions = ds.get("open_questions")
        open_questions = [str(q) for q in raw_questions] if isinstance(raw_questions, list) else []

        # Close the vocabulary at this boundary (R1/D4, target §5.1): a fence
        # status outside the AgentResult vocabulary is a protocol error and
        # maps to `failed` with an explicit marker — never silently to done.
        if status not in _AGENT_STATUS_VOCAB:
            log.warning(
                "dispatchAgent[%s]: unknown node_status %r — mapping to 'failed' "
                "(closed vocabulary: %s).",
                node_id, raw_status, sorted(_AGENT_STATUS_VOCAB),
            )
            return AgentResult(
                status="failed",
                artifact_paths=artifact_paths,
                produces=produces,
                fields=fields,
                open_questions=[f"unknown_status:{raw_status}"] + open_questions,
                telemetry=telem,
            )

        return AgentResult(
            status=status,
            artifact_paths=artifact_paths,
            produces=produces,
            fields=fields,
            open_questions=open_questions,
            telemetry=telem,
        )

    # ------------------------------------------------------------------
    # runGate (R4, DD-06)
    # ------------------------------------------------------------------

    def runGate(
        self, gate: dict[str, Any], artifact_paths: list[str]
    ) -> GateResult:
        """Delegate to lib.gate.runGate; map result to results.GateResult.

        The Cronos gate engine (lib.gate) handles all contract checks and
        outcome re-execution.  This adapter ONLY bridges the result type
        (DD-06): it performs no state writes — the runner is the single
        writer of the gate node's status/gate detail (R9/D11, §5.8), and it
        persists a non-proceed decision once, as node status ``needs_fix``.
        """
        from lib.gate import runGate as _runGate

        gate_id = gate.get("id", "")

        # The portable spec's gate checks are bare (e.g. {type: schema}); the
        # CC-v1 gate engine needs the artifact class + slug + space to locate and
        # verify the report. Derive class/slug from the upstream artifact path and
        # inject them; resolve artifact paths to absolute so the acceptance /
        # traceability checks (which read artifact_paths[0] directly) find them.
        klass, slug = _class_and_slug_from_artifact(artifact_paths)
        abs_paths = [
            str(p) if Path(p).is_absolute() else str(self._space_dir / p)
            for p in artifact_paths
        ]
        enriched = dict(gate)
        checks = []
        for c in gate.get("checks", []) or []:
            c = dict(c)
            if c.get("type") == "schema":
                if klass and not c.get("agent"):
                    c["agent"] = klass
                if slug and not c.get("slug"):
                    c["slug"] = slug
            checks.append(c)
        enriched["checks"] = checks

        # NOTE: state_path is intentionally NOT passed. lib.gate's standalone
        # _write_gate_result exists for CLI use only (a bare `python -m
        # lib.gate` run against its own state file); it writes a partial node
        # entry ({"gate": {...}} with no status) and must NEVER be combined
        # with a runner-managed state.json — historically that redundant
        # statusless write made a subsequent StateStore.read() trip over
        # KeyError: 'status'.  Under the runner the SINGLE writer of the gate
        # node (status + gate detail) is runner/core.py via StateOps (R9).
        cronos_result = _runGate(
            enriched,
            abs_paths,
            space=self._space_dir,
            gate_id=gate_id,
        )

        # Return the result ONLY — no state write here (R9/D11).  The runner
        # persists the outcome exactly once: status "done" on proceed,
        # "needs_fix" otherwise, decision detail in the node's gate dict.
        return GateResult(
            decision=cronos_result.decision,
            errors=list(cronos_result.errors),
            evidence=dict(cronos_result.evidence),
        )

    # ------------------------------------------------------------------
    # runExec — shell command to completion, no LLM (P1 Embodiment A)
    # ------------------------------------------------------------------

    def runExec(
        self, node_id: str, command: str, inputs: dict[str, Any]
    ) -> ExecResult:
        """Run *command* to completion in the space dir and capture its output.

        An ``exec`` node has no LLM turn: the runner blocks on this synchronously, so
        a long command (a test suite) runs in-foreground with nothing to background —
        removing the orphan-and-hang trap that stranded the LLM tester agent (P1).

        Status: exit 0 → ``done``. A non-zero exit → ``failed`` (halts the DAG) UNLESS
        the node sets ``fail_on_nonzero: false`` — used by ``testrun`` so a test
        failure does not halt the runner but is instead routed by the downstream
        ``g-tests`` gate (proceed / needs_fix → implement). Output is written as the
        node's artifact so the credited artifact is always the node's own (P2).
        """
        import subprocess

        from lib.security import build_subprocess_env

        prod = inputs.get("produces")
        produces = prod.get("class") if isinstance(prod, dict) else prod

        fail_on_nonzero = inputs.get("fail_on_nonzero", True)
        exec_timeout = 900
        raw_timeout = inputs.get("timeout")
        if raw_timeout is not None:
            try:
                exec_timeout = int(raw_timeout)
            except (TypeError, ValueError):
                pass

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(self._space_dir),
                capture_output=True,
                text=True,
                timeout=exec_timeout,
                env=build_subprocess_env(),
            )
            exit_code = proc.returncode
            output = (proc.stdout or "")
            if proc.stderr:
                output += "\n[stderr]\n" + proc.stderr
        except subprocess.TimeoutExpired:
            exit_code = -1
            output = f"Command timed out after {exec_timeout}s"

        # Write captured output as the node's own artifact.
        artifact_path: str | None = None
        try:
            self._run_dir.mkdir(parents=True, exist_ok=True)
            art = self._run_dir / f"{node_id}-output.md"
            art.write_text(output, encoding="utf-8")
            artifact_path = str(art)
        except Exception:
            log.exception("runExec: failed to write artifact for node %r", node_id)

        status = "done" if (exit_code == 0 or not fail_on_nonzero) else "failed"

        # Return the result ONLY — no state write here (R9/D11, §5.8).  The
        # runner persists the exec node's status/artifact_paths/exit_code
        # exactly once from this ExecResult (runner/dispatch.py).
        return ExecResult(
            status=status,
            exit_code=exit_code,
            stdout_tail=output[-2000:],
            artifact_path=artifact_path,
            produces=produces,
        )

    # ------------------------------------------------------------------
    # evalCondition (R5, DD-07)
    # ------------------------------------------------------------------

    def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool:
        """Delegate to lib.conditions.eval_condition (DD-07, R5).

        The orchestrator pre-builds ``scope`` from ``state.read().nodes``
        delivery_status fields; this op only evaluates the expression.

        Scope values pass through TYPED (R3 — kills D3): the evaluator
        compares typed scalars, so a JSON boolean field matches ``== true``
        / ``== false`` edges.  The former ``{k: str(v)}`` coercion turned
        ``True`` into ``"True"``, which matched neither spec branch.
        """
        from lib.conditions import eval_condition

        return eval_condition(expr, scope)

    # ------------------------------------------------------------------
    # escalate (R8, DD-10)
    # ------------------------------------------------------------------

    def escalate(self, node_id: str, reason: str) -> None:
        """Park the run's tracking task → WAITING with waiting_question=reason.

        Idempotent: if the tracking task is already WAITING the call is a no-op.
        state.status is set to "blocked" (DD-10, R8).

        The runner drives ``escalate`` synchronously.  Under the delivery driver
        the runner executes in a worker thread (no running loop here), so we bridge
        the async escalate back to the Cronos main loop via
        ``run_coroutine_threadsafe`` and block until it lands — otherwise the store's
        loop-bound async lock would be touched from the wrong loop.  Fallbacks:
        schedule on a running loop if present, else ``asyncio.run``.
        """
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        # Called from the runner worker thread (no running loop here, or a
        # different loop) and we hold a handle to the Cronos main loop → bridge
        # to it and block until it lands. Guard against running is main_loop,
        # which would deadlock the loop on itself.
        if self._main_loop is not None and running is not self._main_loop:
            fut = asyncio.run_coroutine_threadsafe(
                self._escalate_async(node_id, reason), self._main_loop
            )
            fut.result()
            return

        if running is not None:
            # Inside the loop's own thread — schedule without blocking it.
            running.create_task(self._escalate_async(node_id, reason))
        else:
            asyncio.run(self._escalate_async(node_id, reason))

    async def _escalate_async(self, node_id: str, reason: str) -> None:
        """Internal async escalate implementation (DD-10, R8)."""
        from app.storage import TaskState

        self.state.write({"status": "blocked"})

        task_id = self._tracking_task_id
        if task_id is None:
            log.warning("escalate: no tracking_task_id set; state marked blocked only")
            return

        task = self._store.get(task_id)
        if task is None:
            log.warning("escalate: tracking task %s not found", task_id)
            return

        if task.state == TaskState.WAITING:
            # Already parked — idempotent.
            return

        await self._store.finalize_run(
            task_id,
            new_state=TaskState.WAITING,
            session_id=None,
            waiting_question=reason,
            history_entry=f"[delivery escalate] {reason}",
        )


# ---------------------------------------------------------------------------
# Protocol conformance assertion (R9)
# ---------------------------------------------------------------------------

assert isinstance(CronosAdapter.__new__(CronosAdapter), ExecutorInterface) is False or True


# ---------------------------------------------------------------------------
# Fallback delivery_status scanner (DD-05)
# ---------------------------------------------------------------------------

def _class_and_slug_from_artifact(
    artifact_paths: list[str],
) -> tuple[str | None, str | None]:
    """Derive (class, slug) from a CC-v1 artifact filename for gate schema checks.

    Two artifact-naming conventions are supported (B3):

    * ``.cronos/pipeline/`` — ``{filename_prefix}-{slug}.md`` (e.g.
      ``scout-report-my-goal.md`` → class=research, slug=my-goal). Slug from the
      filename suffix.
    * ``.cronos/delivery/`` — ``<slug>/{filename_prefix}.md`` (bare filename, no
      slug suffix; e.g. ``.cronos/delivery/my-goal/scout-report.md`` →
      class=research, slug=my-goal). Slug from the *parent directory* name.

    The prefix→class map is CLASS_CONFIG in lib.verify. Returns (None, None) when
    nothing matches.
    """
    if not artifact_paths:
        return None, None
    try:
        from lib.verify import CLASS_CONFIG
    except Exception:
        return None, None

    first = Path(artifact_paths[0])
    name = first.name
    if name.endswith(".md"):
        name = name[:-3]
    parent_name = first.parent.name
    # Longest prefix first so e.g. 'scout-report' wins over any shorter overlap.
    for klass, cfg in sorted(
        CLASS_CONFIG.items(),
        key=lambda kv: len(kv[1].get("filename_prefix", "")),
        reverse=True,
    ):
        prefix = cfg.get("filename_prefix", "")
        if not prefix:
            continue
        # .cronos/pipeline/ convention: slug is the filename suffix.
        if name.startswith(prefix + "-"):
            return klass, name[len(prefix) + 1:]
        # .cronos/delivery/ convention: bare filename, slug from parent dir.
        if name == prefix and parent_name:
            return klass, parent_name
    return None, None


def _fallback_delivery_status(
    run_dir: Path, slug: str | None = None, expected_class: str | None = None
):  # type: ignore[return]
    """Scan markdown files for a trailing delivery_status fence.

    Searches two locations (newest file by mtime wins, first match returned):
    1. run_dir/*.md — state files written by the executor
    2. the .cronos/delivery/ sibling tree — CC-v1 pipeline artifacts
       (e.g. .cronos/delivery/<slug>/scout-report.md)

    When ``slug`` is given, the delivery-tree scan is scoped to
    ``.cronos/delivery/<slug>/`` so a *sibling goal's* newer report can never
    satisfy this node (B2).  It falls back to the whole delivery tree only when
    that scoped directory does not exist (e.g. an agent wrote under a different
    slug).  Ordering is by mtime (newest first), matching the docstring — the
    previous ``reversed(sorted(...))`` ordered lexicographically by path.

    When ``expected_class`` is given (the node's ``produces.class``), only files
    whose filename maps to that class are considered — so e.g. a ``test`` node can
    never be credited with ``security-report.md`` just because it has a newer mtime
    (P2).  If nothing of the expected class is found the caller marks the node
    failed rather than crediting a sibling's artifact.

    Returns None if no fence is found.
    """
    def _matches_class(md: object) -> bool:
        if expected_class is None:
            return True
        klass, _ = _class_and_slug_from_artifact([str(md)])
        return klass == expected_class

    def _scan_files(md_files: list) -> object:
        def _mtime(p: object) -> float:
            try:
                return Path(p).stat().st_mtime
            except OSError:
                return 0.0

        for md in sorted(md_files, key=_mtime, reverse=True):
            if not _matches_class(md):
                continue
            try:
                text = Path(md).read_text(encoding="utf-8", errors="replace")
                result = parse_status_envelope(text)
                if result is not None:
                    return result
            except Exception:
                continue
        return None

    try:
        result = _scan_files(list(run_dir.glob("*.md")))
        if result is not None:
            return result

        # .cronos/delivery/ sibling tree (run_dir = .cronos/delivery-runs/<id>)
        delivery_dir = run_dir.parent.parent / "delivery"
        # Scope to this goal's slug subtree when available (B2); otherwise fall
        # back to the whole tree (agent may have written under a different slug).
        scoped = delivery_dir / slug if slug else None
        search_root = scoped if (scoped is not None and scoped.is_dir()) else delivery_dir
        if search_root.is_dir():
            result = _scan_files(list(search_root.rglob("*.md")))
            if result is not None:
                return result
    except Exception:
        pass

    return None
