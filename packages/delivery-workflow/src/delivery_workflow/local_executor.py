"""delivery_workflow.local_executor — the reference runtime (R10e, 02 §2.3).

``LocalProcessExecutor`` is the package-shipped ``NodeExecutor`` that makes
the standalone story real: it spawns ``claude -p <brief>`` (configurable argv
template) per agent node in a working directory, reads the ``node_status``
fence from the child's stdout with the package's own parser
(``lib.node_status``), and closes the status vocabulary through the SAME
mapping the Cronos boundary applies (``results.agent_result_from_envelope`` —
one mapping, two executors, zero duplication).  Gates delegate to
``lib.gate.runGate``; exec nodes run through ``lib.exec_node.run_exec_command``.

``LocalHostPort`` is the matching ``HostPort``: it prints one structured JSON
line per ``RunEvent`` (to stderr by default, keeping stdout free for the
CLI's Outcome JSON).  A blocked run parks by *returning* — the CLI
(``python -m delivery_workflow``) reports the sign-off question and exits with
a distinct code; ``--resume human-answer …`` re-enters through the same typed
grammar every host uses.

Zero host knowledge, zero app.* imports (enforced by .importlinter) — this
module plus ``__main__.py`` IS the "runnable without Cronos" deliverable.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence, TextIO

from delivery_workflow.briefs import (
    load_agent_definition,
    return_contract,
    upstream_scope_section,
)
from delivery_workflow.lib.exec_node import run_exec_command
from delivery_workflow.lib.node_status import parse_node_status
from delivery_workflow.results import (
    AgentResult,
    ExecResult,
    GateResult,
    TelemetryData,
    agent_result_from_envelope,
)

if TYPE_CHECKING:  # pragma: no cover — typing only
    from delivery_workflow.events import RunEvent

#: Default agent invocation: ``claude -p <brief>``.  Every element of the
#: template is copied verbatim after substituting the ``{brief}`` /
#: ``{agent_ref}`` / ``{node_id}`` placeholders (plain string replacement —
#: no format() so briefs containing braces are safe).
DEFAULT_ARGV_TEMPLATE: tuple[str, ...] = ("claude", "-p", "{brief}")

#: Default per-agent-child timeout, seconds.
DEFAULT_AGENT_TIMEOUT = 3600.0


def _fill(template_arg: str, **subst: str) -> str:
    out = template_arg
    for key, value in subst.items():
        out = out.replace("{" + key + "}", value)
    return out


def compose_brief(agent_ref: str, inputs: dict[str, Any]) -> str:
    """Compose the child brief for one agent node.

    Mirrors what a host brief-composer provides: identity (agent/node/
    attempt), the bundled role definition (which carries the routing-critical
    ``fields`` protocol, e.g. the analyst's ``has_ui``), the typed upstream
    scope, the declared artifact class, and the node_status return-contract
    instruction (closed vocabulary).  The shared sections come from
    ``delivery_workflow.briefs`` so the two composers cannot drift.
    """
    node_id = str(inputs.get("node_id") or agent_ref)
    attempt = inputs.get("attempt", 1)
    prod = inputs.get("produces")
    produces = prod.get("class") if isinstance(prod, dict) else prod
    scope = inputs.get("scope") or {}

    lines = [
        f"You are agent '{agent_ref}' executing workflow node '{node_id}'"
        f" (attempt {attempt}).",
        "Work in the current directory.",
        "",
    ]
    role = load_agent_definition(agent_ref)
    if role:
        lines += [role, ""]
    if produces:
        lines += [f"This node produces an artifact of class: {produces}", ""]
    scope_section = upstream_scope_section(scope)
    if scope_section:
        lines += [scope_section, ""]
    lines += [return_contract(produces)]
    return "\n".join(lines)


class LocalProcessExecutor:
    """Reference NodeExecutor: one ``claude -p`` subprocess per agent node.

    Parameters
    ----------
    workdir:
        Directory the agent children and exec commands run in (their cwd).
    argv_template:
        Argv for the agent child; ``{brief}`` / ``{agent_ref}`` / ``{node_id}``
        placeholders are substituted per dispatch.  Default: ``claude -p
        {brief}``.
    agent_timeout:
        Seconds before an agent child is killed (→ ``failed`` AgentResult).
    run_dir:
        Where exec-node output artifacts land; defaults to
        ``<workdir>/.delivery-run`` (the CLI's state directory).
    """

    def __init__(
        self,
        workdir: str | Path,
        *,
        argv_template: Sequence[str] = DEFAULT_ARGV_TEMPLATE,
        agent_timeout: float = DEFAULT_AGENT_TIMEOUT,
        run_dir: str | Path | None = None,
    ) -> None:
        self.workdir = Path(workdir)
        self.run_dir = (
            Path(run_dir) if run_dir is not None
            else self.workdir / ".delivery-run"
        )
        self._argv_template = tuple(argv_template)
        if not any("{brief}" in a for a in self._argv_template):
            raise ValueError(
                "argv_template must carry a '{brief}' placeholder — the child "
                f"would never receive its instructions: {self._argv_template!r}"
            )
        self._agent_timeout = float(agent_timeout)

    # ------------------------------------------------------------------
    # NodeExecutor
    # ------------------------------------------------------------------

    def dispatchAgent(
        self, agent_ref: str, inputs: dict[str, Any]
    ) -> AgentResult:
        """Spawn the agent child, parse its node_status fence, close the vocab.

        Process-level failures are honest ``failed`` results (never silent
        ``done``): a missing binary, a timeout, and a non-zero exit each carry
        an explicit ``open_questions`` marker.  On exit 0 the FULL stdout is
        parsed with ``lib.node_status.parse_node_status`` and mapped through
        the shared closed-vocabulary boundary
        (``results.agent_result_from_envelope``) — no fence → ``failed``,
        unknown status → ``failed`` with ``unknown_status:<raw>``.
        """
        node_id = str(inputs.get("node_id") or agent_ref)
        brief = compose_brief(agent_ref, inputs)
        argv = [
            _fill(a, brief=brief, agent_ref=agent_ref, node_id=node_id)
            for a in self._argv_template
        ]

        started = time.monotonic()
        try:
            proc = subprocess.run(
                argv,
                cwd=str(self.workdir),
                capture_output=True,
                text=True,
                timeout=self._agent_timeout,
            )
        except FileNotFoundError:
            return self._process_failure(
                node_id,
                f"agent binary not found: {argv[0]!r} — install it or point "
                "the argv template (--claude-cmd) at an existing executable",
                started,
            )
        except subprocess.TimeoutExpired:
            return self._process_failure(
                node_id,
                f"agent process for node '{node_id}' timed out after "
                f"{self._agent_timeout:g}s",
                started,
            )

        elapsed = time.monotonic() - started
        telem = TelemetryData(tokens=0, usd=0.0, seconds=elapsed)

        if proc.returncode != 0:
            questions = [
                f"agent process for node '{node_id}' exited "
                f"{proc.returncode}"
            ]
            stderr_tail = (proc.stderr or "").strip()[-500:]
            if stderr_tail:
                questions.append(f"stderr tail: {stderr_tail}")
            return AgentResult(
                status="failed",
                artifact_paths=[],
                produces="",
                fields={},
                open_questions=questions,
                telemetry=telem,
            )

        block = parse_node_status(proc.stdout or "")
        return agent_result_from_envelope(
            block,
            node_id=node_id,
            telemetry=telem,
            missing_detail="child stdout carried no fence",
        )

    def runGate(
        self, gate: dict[str, Any], artifact_paths: list[str]
    ) -> GateResult:
        """Delegate to the package gate engine (``lib.gate.runGate``).

        Relative artifact paths are resolved against the workdir.  No state
        writes here — the runner is the single writer of the gate node's
        status/gate detail (R9, 01-state-model.md §5.8).
        """
        from delivery_workflow.lib.gate import runGate as _runGate

        abs_paths = [
            str(p) if Path(p).is_absolute() else str(self.workdir / p)
            for p in artifact_paths
        ]
        result = _runGate(
            dict(gate),
            abs_paths,
            space=self.workdir,
            gate_id=str(gate.get("id", "")),
        )
        return GateResult(
            decision=result.decision,
            errors=list(result.errors),
            evidence=dict(result.evidence),
        )

    def runExec(
        self, node_id: str, command: str, inputs: dict[str, Any]
    ) -> ExecResult:
        """Run the exec node's command via the shared ``lib.exec_node`` helper."""
        return run_exec_command(
            node_id, command, inputs, cwd=self.workdir, artifact_dir=self.run_dir
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _process_failure(
        self, node_id: str, question: str, started: float
    ) -> AgentResult:
        return AgentResult(
            status="failed",
            artifact_paths=[],
            produces="",
            fields={},
            open_questions=[question],
            telemetry=TelemetryData(
                tokens=0, usd=0.0, seconds=time.monotonic() - started
            ),
        )


# ---------------------------------------------------------------------------
# LocalHostPort — structured progress lines
# ---------------------------------------------------------------------------


def _snake(name: str) -> str:
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


class LocalHostPort:
    """HostPort printing one structured JSON line per RunEvent.

    Lines go to *stream* (default: stderr, so the CLI's stdout stays a clean
    Outcome-JSON channel):

        {"event": "node_started", "node_id": "scout", "attempt": 1}

    A blocked run needs no action here — the runner parks it and the caller
    (CLI/host) reports the ``blocked`` Outcome; resumption flows through the
    typed ``--resume`` grammar.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream if stream is not None else sys.stderr

    def on_event(self, event: "RunEvent") -> None:
        payload = {"event": _snake(type(event).__name__), **asdict(event)}
        print(json.dumps(payload, default=str), file=self._stream, flush=True)
