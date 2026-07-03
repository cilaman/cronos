"""delivery_workflow.delivery_run — the DeliveryRun facade (R10b, 02 §2.2).

The ONLY thing hosts call::

    run = DeliveryRun(spec_or_graph, executor=..., state_ops=..., host=...)
    outcome = run.start()                      # fresh run or crash re-entry
    outcome = run.resume(HumanAnswer(...))     # typed re-entry (R7 grammar)
    outcome = run.outcome()                    # pure read, for UIs
    outcome = run.cancel()                     # writes the run 'cancelled'

Every method returns (or raises around) the closed ``Outcome`` taxonomy
(``delivery_workflow.outcome``, 01 §5.6) — hosts never see ``WorkflowState``
internals.  Mid-run notifications flow through the ``HostPort`` given at
construction (typed ``RunEvent``s, ``delivery_workflow.events``).

The facade DELEGATES: ``start`` → ``runner.run``, ``resume`` →
``runner.resume`` — both stay importable for the package's own tests and for
one deprecation window of pre-facade host code; they are not a supported host
surface.

Cancellation (R11 recommendation, implemented here): ``cancel()`` writes the
previously-phantom ``'cancelled'`` run status through StateOps.  The runner's
per-tick cancel-race guard halts a live run at the next tick boundary; the
top-of-run sealed-re-entry guard refuses a bare ``run()`` on it; and
``resume()`` on a cancelled run raises ``ResumeError`` — a cancelled run is
terminal until a fresh run replaces its state.

No app.* imports allowed (enforced by .importlinter).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from delivery_workflow.ir import IRGraph
from delivery_workflow.outcome import Outcome, outcome_from_state

if TYPE_CHECKING:  # pragma: no cover — typing only
    from delivery_workflow.interface import HostPort, NodeExecutor, StateOps
    from delivery_workflow.runner.resume import ResumeEvent

log = logging.getLogger(__name__)


class DeliveryRun:
    """Facade over one persisted workflow run (02-package-boundary.md §2.2).

    Parameters
    ----------
    spec_or_graph:
        A compiled ``IRGraph``, or a spec path (``str`` / ``Path``) loaded
        through the real ``spec_loader.load_spec → compiler_a.compile`` chain.
    executor:
        The host's ``NodeExecutor`` (dispatchAgent / runGate / runExec).
    state_ops:
        The host's ``StateOps`` (must satisfy the ``lib.state.conformance``
        round-trip law).  Required — a DeliveryRun without persistence cannot
        be parked, resumed, observed or cancelled.
    host:
        Optional ``HostPort``; receives typed ``RunEvent``s.  ``None`` means
        the host does not care about mid-run notifications.
    run_id:
        Identity stamped into a freshly-bootstrapped state (ignored when the
        run directory already holds one).
    """

    def __init__(
        self,
        spec_or_graph: "IRGraph | str | Path",
        *,
        executor: "NodeExecutor",
        state_ops: "StateOps",
        host: "HostPort | None" = None,
        run_id: str = "",
    ) -> None:
        if state_ops is None:
            raise ValueError(
                "DeliveryRun requires a StateOps — without persistence a run "
                "cannot park, resume, or be observed"
            )
        self.graph = _resolve_graph(spec_or_graph)
        self.executor = executor
        self.state_ops = state_ops
        self.host = host
        self.run_id = run_id

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> Outcome:
        """Execute the run (fresh, or a crash re-entry on a ``running`` state).

        Bootstraps ``state.json`` when the StateOps exposes the optional
        ``bootstrap_if_absent`` hook (as ``lib.state.ops.StateStoreOps`` does) — mirroring
        the pre-facade driver so hosts stop carrying that call themselves.
        A persisted halted status (``blocked``/``escalated``/``stalled``/
        ``cancelled``) is sealed for ``start()`` (runner top-of-run guard):
        the returned Outcome reports the park unchanged; re-enter with
        ``resume()``.
        """
        self._bootstrap_if_supported()
        from delivery_workflow.runner import run as _run

        final = _run(
            graph=self.graph,
            executor=self.executor,
            state_ops=self.state_ops,
            host=self.host,
        )
        return outcome_from_state(final, self.graph)

    def resume(self, event: "ResumeEvent", **kwargs: Any) -> Outcome:
        """Apply one typed resume *event* (R7 grammar) and re-enter the run.

        Raises ``ResumeError`` when the event does not match the persisted
        state (nothing is written in that case).  Keyword arguments (e.g.
        ``max_retries``) pass through to ``runner.resume``.
        """
        from delivery_workflow.runner import resume as _resume

        final = _resume(
            self.graph,
            self.executor,
            self.state_ops,
            event,
            host=self.host,
            **kwargs,
        )
        return outcome_from_state(final, self.graph)

    def outcome(self) -> Outcome:
        """Pure read: the Outcome of the persisted state (UIs poll this)."""
        return outcome_from_state(self.state_ops.read(), self.graph)

    def cancel(self) -> Outcome:
        """Cancel the run: persist run status ``cancelled``.

        A live runner halts at its next tick boundary (cancel-race guard);
        ``start()`` on the persisted state halts immediately (sealed
        re-entry); ``resume()`` raises ``ResumeError``.  Idempotent on an
        already-cancelled run.  Refused on a ``done`` run — there is nothing
        left to cancel, and silently rewriting a completed run's terminal
        would corrupt history.
        """
        from delivery_workflow.runner.resume import ResumeError

        state = self.state_ops.read()
        if state.status == "done":
            raise ResumeError(
                "cannot cancel a run that already completed ('done')"
            )
        if state.status == "cancelled":
            return Outcome(kind="cancelled")
        self.state_ops.write({"status": "cancelled"})
        log.info(
            "DeliveryRun.cancel: run %r cancelled (was %r).",
            self.run_id or state.run_id, state.status,
        )
        return Outcome(kind="cancelled")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _bootstrap_if_supported(self) -> None:
        """Seed an initial persisted state when the StateOps supports it.

        ``bootstrap_if_absent`` is deliberately NOT part of the StateOps
        protocol (in-memory implementations are always "bootstrapped");
        duck-type it exactly like the pre-facade driver did.
        """
        bootstrap: Callable[..., None] | None = getattr(
            self.state_ops, "bootstrap_if_absent", None
        )
        if callable(bootstrap):
            budget_meta = self.graph.metadata.get("budget", {})
            bootstrap(
                spec=self.graph.metadata.get("name", ""),
                run_id=self.run_id,
                usd_ceiling=float(budget_meta.get("usd_ceiling", 0.0)),
            )


def _resolve_graph(spec_or_graph: "IRGraph | str | Path") -> IRGraph:
    """Accept a compiled IRGraph, or load+compile a spec path."""
    if isinstance(spec_or_graph, IRGraph):
        return spec_or_graph
    from delivery_workflow import compiler_a
    from delivery_workflow.spec_loader import load_spec

    return compiler_a.compile(load_spec(Path(spec_or_graph)))
