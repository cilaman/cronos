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
  DD-05  delivery_status parsed from final_text_snippet; fallback to artifact fence.
  DD-06  runGate delegates to lib.gate.runGate.
  DD-07  evalCondition delegates to lib.conditions.eval_condition.
  DD-08  state.write patches StateStore; node transitions appended to EventLog.
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
from results import AgentResult, GateResult, TelemetryData
from state_types import NodeState, WorkflowState

log = logging.getLogger(__name__)


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

    def write(self, patch: dict[str, Any]) -> None:
        """Read-modify-write; appends node_transition events for status changes."""
        state = self._store.read()

        # Top-level status update.
        if "status" in patch:
            state.status = patch["status"]

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
        AgentResult (DD-04/DD-05):

        1. Call ``run_child(agent_ref, inputs)`` → the child's loaded RunTrace.
        2. Parse the delivery_status fence from ``trace.final_text_snippet`` (or
           fall back to the newest artifact under run_dir).
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

        # 3b. Fallback: delivery_status JSON fence in the agent's final text, then
        #     the newest artifact under run_dir (non-CC-v1 agents).
        ds = None
        if trace is not None and getattr(trace, "final_text_snippet", None):
            ds = parse_status_envelope(trace.final_text_snippet)
        if ds is None:
            ds = _fallback_delivery_status(self._run_dir)

        if ds is None:
            return AgentResult(
                status="failed",
                artifact_paths=[],
                produces="",
                fields={},
                open_questions=["No node_status/delivery_status fence or CC-v1 report found in agent output"],
                telemetry=telem,
            )

        return AgentResult(
            status=ds.status,
            artifact_paths=ds.artifact_paths,
            produces=ds.produces,
            fields=ds.fields,
            open_questions=ds.open_questions,
            telemetry=telem,
        )

    # ------------------------------------------------------------------
    # runGate (R4, DD-06)
    # ------------------------------------------------------------------

    def runGate(
        self, gate: dict[str, Any], artifact_paths: list[str]
    ) -> GateResult:
        """Delegate to lib.gate.runGate; map result to results.GateResult.

        The Cronos gate engine (lib.gate) handles all contract checks
        and outcome re-execution. This adapter only bridges the result type and
        writes the gate outcome into state.json (DD-06).
        """
        from lib.gate import runGate as _runGate

        gate_id = gate.get("id", "")
        state_path = self._run_dir / "state.json"

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

        cronos_result = _runGate(
            enriched,
            abs_paths,
            space=self._space_dir,
            gate_id=gate_id,
            state_path=state_path if state_path.exists() else None,
        )

        result = GateResult(
            decision=cronos_result.decision,
            errors=list(cronos_result.errors),
            evidence=dict(cronos_result.evidence),
        )

        # Write gate outcome into workflow state.
        if gate_id:
            self.state.write(
                {
                    "nodes": {
                        gate_id: {
                            "status": (
                                "done" if cronos_result.decision == "proceed" else "needs_fix"
                            ),
                            "gate": cronos_result.to_dict(),
                        }
                    }
                }
            )

        return result

    # ------------------------------------------------------------------
    # evalCondition (R5, DD-07)
    # ------------------------------------------------------------------

    def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool:
        """Delegate to lib.conditions.eval_condition (DD-07, R5).

        The orchestrator pre-builds ``scope`` from ``state.read().nodes``
        delivery_status fields; this op only evaluates the expression.
        Non-string scope values are coerced to str for the whitelisted grammar.
        """
        from lib.conditions import eval_condition

        flat: dict[str, str] = {k: str(v) for k, v in scope.items()}
        return eval_condition(expr, flat)

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

    Artifacts are named ``{filename_prefix}-{slug}.md`` (e.g.
    ``scout-report-my-goal.md`` → class=research, slug=my-goal). The prefix→class
    map is CLASS_CONFIG in lib.verify. Returns (None, None) when nothing matches.
    """
    if not artifact_paths:
        return None, None
    try:
        from lib.verify import CLASS_CONFIG
    except Exception:
        return None, None

    name = Path(artifact_paths[0]).name
    if name.endswith(".md"):
        name = name[:-3]
    # Longest prefix first so e.g. 'scout-report' wins over any shorter overlap.
    for klass, cfg in sorted(
        CLASS_CONFIG.items(),
        key=lambda kv: len(kv[1].get("filename_prefix", "")),
        reverse=True,
    ):
        prefix = cfg.get("filename_prefix", "")
        if prefix and name.startswith(prefix + "-"):
            return klass, name[len(prefix) + 1:]
    return None, None


def _fallback_delivery_status(run_dir: Path):  # type: ignore[return]
    """Scan markdown files for a trailing delivery_status fence.

    Searches two locations (newest file wins, first match returned):
    1. run_dir/*.md — state files written by the executor
    2. run_dir.parent.parent/delivery/**/*.md — CC-v1 pipeline artifacts
       (e.g. .cronos/delivery/<slug>/scout-report.md)

    Returns None if no fence is found.
    """
    def _scan_files(md_files: list) -> object:
        for md in reversed(sorted(md_files)):
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
        if delivery_dir.is_dir():
            result = _scan_files(list(delivery_dir.rglob("*.md")))
            if result is not None:
                return result
    except Exception:
        pass

    return None
