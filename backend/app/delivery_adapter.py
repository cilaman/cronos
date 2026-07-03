"""Cronos adapter — NodeExecutor + HostPort implementation for the Cronos backend.

R10c (02-package-boundary.md §2.3): this module lives in the HOST.  The host
owns its own adapter — dependencies point app → package only, so importing
package classes (StateStore, EventLog, TelemetrySink, StateStoreOps, the
result types) from here is the correct direction, while the package itself
carries zero Cronos knowledge.  ``app.*`` imports are normal top-level
imports; this is an app module.

The StateOps read-modify-write + event-log merge logic is NOT defined here —
it lives once, in the package (``delivery_workflow.lib.state.ops.StateStoreOps``),
where its round-trip laws are conformance-tested.  ``CronosStateOps`` below is
that class, re-exported under its historical name.

Design decisions implemented here:
  DD-01  Single module (backend/app/delivery_adapter.py — host-owned, R10c).
  DD-02  dispatchAgent is async def; other ops sync.
  DD-03  Dispatch flow: create_task → goal ACTIVE → poll → trace → AgentResult.
  DD-04  Telemetry: sum per-turn tokens; usd = tokens * token_cost_usd.
  DD-05  (R1) node outcome read from the structured ``trace.node_status``
         envelope (parsed backend-side from the FULL final text); closed
         vocabulary at this boundary; mtime fallback scan demoted to log-only.
  DD-06  runGate delegates to lib.gate.runGate and returns the GateResult
         ONLY — the runner is the single writer of node state (R9/D11).
  DD-07  (retired by R10b) evalCondition left the executor surface entirely —
         condition evaluation is runner-internal (lib.conditions); the
         adapter implements NodeExecutor (work) + HostPort (on_event) only.
  DD-08  state.write patches StateStore; node transitions appended to EventLog.
         Node status/attempt/artifact_paths/gate/fields are written ONLY by
         the runner through this StateOps (01-state-model.md §5.8): runGate
         and runExec perform no state writes of their own — the historical
         out-of-band writes here double-wrote every gate/exec node (D11: the
         adapter wrote needs_fix, the runner overwrote done, and the event
         log carried a phantom needs_fix→done transition).
  DD-09  TelemetrySink wired to StateStore; BudgetExceededSignal → escalate.
  DD-10  on_event(RunBlocked|RunEscalated) parks tracking task → WAITING +
         waiting_question; idempotent.  (R10b: typed events replaced the
         executor escalate() hook; the ``escalate`` method survives as the
         internal parking bridge both event kinds share.)
  DD-11  G6.2 e2e: monkeypatched store + trace_store; sequential dispatch.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from delivery_workflow.events import RunBlocked, RunEscalated
from delivery_workflow.interface import StateOps, TelemetryOps
from delivery_workflow.lib.exec_node import run_exec_command
from delivery_workflow.lib.status_envelope import parse_status_envelope
from delivery_workflow.lib.state.events import EventLog
from delivery_workflow.lib.state.ops import StateStoreOps
from delivery_workflow.lib.state.store import StateStore
from delivery_workflow.lib.telemetry.sink import TelemetrySink
from delivery_workflow.results import (
    AgentResult,
    ExecResult,
    GateResult,
    TelemetryData,
    agent_result_from_envelope,
)

from app.storage import TaskState

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# StateOps implementation
# ---------------------------------------------------------------------------

# The read-modify-write + event-log merge logic lives ONCE, in the package
# (delivery_workflow.lib.state.ops.StateStoreOps), where its round-trip laws
# are conformance-tested.  Cronos has no host-specific StateOps behavior, so
# the historical name is a straight re-export (R10c — no logic duplication).
CronosStateOps = StateStoreOps


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
    """Concrete NodeExecutor + HostPort for the Cronos backend (DD-01/DD-02, R9).

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
        #    the agent finishes on the main loop). run_child returns the child's
        #    loaded RunTrace, or None on infra failure.
        trace = self._run_child(agent_ref, inputs)

        # 2. Telemetry from the trace.
        telem = (
            _telemetry_from_trace(trace, self._token_cost_usd)
            if trace is not None
            else TelemetryData(tokens=0, usd=0.0, seconds=0.0)
        )

        # 3. Structured channel (R1): the backend trace parser extracts the
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
            return agent_result_from_envelope(
                None,
                node_id=node_id,
                telemetry=telem,
                missing_detail="trace.node_status is None",
            )

        # Close the vocabulary at this boundary (R1/D4, target §5.1) through
        # the PACKAGE mapping (results.agent_result_from_envelope — one
        # mapping shared with LocalProcessExecutor, R10e): a fence status
        # outside the AgentResult vocabulary is a protocol error and maps to
        # `failed` with an `unknown_status:<raw>` marker — never silently to
        # done.
        return agent_result_from_envelope(ds, node_id=node_id, telemetry=telem)

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
        from delivery_workflow.lib.gate import runGate as _runGate

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

        Delegates to the package's ONE exec-node implementation
        (``delivery_workflow.lib.exec_node.run_exec_command``, R10e — shared
        with ``LocalProcessExecutor``): exit 0 → ``done``; a non-zero exit →
        ``failed`` (halts the DAG) UNLESS the node sets ``fail_on_nonzero:
        false`` — used by ``testrun`` so a test failure does not halt the
        runner but is instead routed by the downstream ``g-tests`` gate
        (proceed / needs_fix → implement). Output is written as the node's
        artifact so the credited artifact is always the node's own (P2).

        Returns the result ONLY — no state write here (R9/D11, §5.8).  The
        runner persists the exec node's status/artifact_paths/exit_code
        exactly once from this ExecResult (runner/dispatch.py).
        """
        return run_exec_command(
            node_id,
            command,
            inputs,
            cwd=self._space_dir,
            artifact_dir=self._run_dir,
        )

    # ------------------------------------------------------------------
    # on_event (R10b HostPort) — replaces the escalate(node_id, reason) hook
    # ------------------------------------------------------------------

    def on_event(self, event: Any) -> None:
        """HostPort: translate typed RunEvents into Cronos board effects.

        ``RunBlocked`` (a human sign-off parked the run) and ``RunEscalated``
        (loop exhaust / timed wait / iteration cap) park the tracking task
        WAITING with an actionable ``waiting_question`` — via the same
        ``escalate`` bridge the pre-R10b executor hook used, so park message
        formats and idempotency are unchanged.  ``NodeStarted``/
        ``NodeFinished``/``RunFailed``/``RunStalled`` need no mid-run board
        effect here: the delivery driver parks/finalizes the goal from the
        run's terminal Outcome.
        """
        if isinstance(event, RunBlocked):
            self.escalate(
                event.node_id, f"[human] {event.node_id}: {event.question}"
            )
        elif isinstance(event, RunEscalated):
            self.escalate(event.node_id, event.detail)

    def escalate(self, node_id: str, reason: str) -> None:
        """Park the run's tracking task → WAITING with waiting_question=reason.

        Internal parking bridge since R10b (called from ``on_event``; no
        longer part of any executor protocol — the runner emits typed events
        instead).

        Idempotent: if the tracking task is already WAITING the call is a no-op.
        state.status is set to "blocked" (DD-10, R8).

        The runner drives events synchronously.  Under the delivery driver
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
        from delivery_workflow.lib.verify import CLASS_CONFIG
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
