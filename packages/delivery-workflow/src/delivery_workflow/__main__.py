"""python -m delivery_workflow — the standalone CLI (R10e, 02 §2.3).

Runs a delivery/v1 workflow spec with NO host anywhere in the process:
``spec_loader`` → ``compiler_a`` → the ``DeliveryRun`` facade, driven by the
in-package ``LocalProcessExecutor`` (spawns ``claude -p <brief>`` per agent
node) and persisted through the package ``StateStore``/``EventLog`` in
``<workdir>/.delivery-run/``.

Subcommands
-----------
run      Start a run (or re-enter a parked one with ``--resume``).
outcome  Pure read: print the persisted run's Outcome JSON, no side effects.
cancel   Persist run status ``cancelled`` (terminal until a fresh run).

Exit codes are honest per Outcome kind — see EXIT_CODES / ``--help``.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

#: One exit code per Outcome kind (01-state-model.md §5.6 closed taxonomy,
#: plus the pure-read non-terminal ``running``).  Documented in --help and in
#: the package README; scripts branch on these instead of parsing stdout.
EXIT_CODES: dict[str, int] = {
    "done": 0,
    "blocked": 10,
    "stalled": 20,
    "failed": 30,
    "escalated": 40,
    "cancelled": 50,
    "running": 60,
}
#: Bad usage / unloadable spec / missing state (argparse also uses 2).
EXIT_USAGE = 2
#: The package rejected the resume/cancel event (ResumeError): the event does
#: not match the persisted run state.  Nothing was written.
EXIT_EVENT_REJECTED = 3

_EXIT_CODE_DOC = """\
exit codes (per Outcome kind):
  0   done       workflow completed
  10  blocked    parked on a human sign-off — resume with:
                 run <spec> --workdir <dir> --resume human-answer \\
                     --node <id> --text '...' [--verdict approve|reject]
  20  stalled    terminated without full coverage (see stall record in JSON)
  30  failed     a node failed (resume with --resume retry-failed)
  40  escalated  loop/timed-wait/iteration-cap/budget halt
                 (--resume nothing | retry-failed | raise-budget)
  50  cancelled  run was cancelled (terminal; start a fresh workdir)
  60  running    non-terminal (outcome read mid-flight / after a crash)
  2   usage error / unloadable spec / no persisted run
  3   resume or cancel event rejected (does not match the persisted state)

The Outcome is printed to stdout as one JSON object; structured progress
events stream to stderr as JSON lines.

Workflow specs are trusted input: exec nodes run arbitrary shell commands in
--workdir with your environment (tokens included), and agent nodes spawn the
configured --claude-cmd. Only run specs you trust — the runner is no sandbox.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m delivery_workflow",
        description=(
            "Standalone delivery/v1 workflow runner — no host required. "
            "Agent nodes spawn 'claude -p <brief>' (configurable via "
            "--claude-cmd); run state persists in <workdir>/.delivery-run/."
        ),
        epilog=_EXIT_CODE_DOC,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def _common(p: argparse.ArgumentParser) -> None:
        p.add_argument("spec", help="path to the delivery/v1 workflow YAML")
        p.add_argument(
            "--workdir", required=True,
            help="working directory for agents/exec nodes; run state lives "
                 "in <workdir>/.delivery-run/",
        )

    run_p = sub.add_parser(
        "run",
        help="start a run, or re-enter a parked one with --resume",
        epilog=_EXIT_CODE_DOC,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _common(run_p)
    run_p.add_argument(
        "--run-id", default="",
        help="identity stamped into a fresh state.json (default: workdir name)",
    )
    run_p.add_argument(
        "--claude-cmd", default="claude -p {brief}",
        help="agent child argv template (shlex-split); '{brief}' is replaced "
             "by the composed node brief, '{agent_ref}'/'{node_id}' are also "
             "available (default: %(default)r)",
    )
    run_p.add_argument(
        "--agent-timeout", type=float, default=3600.0,
        help="seconds before an agent child is killed (default: %(default)s)",
    )
    run_p.add_argument(
        "--resume",
        choices=["human-answer", "retry-failed", "raise-budget", "nothing"],
        help="re-enter the persisted run with one typed resume event instead "
             "of starting",
    )
    run_p.add_argument(
        "--node", help="human-answer: the parked sign-off node id "
                       "(default: the Outcome's park point)",
    )
    run_p.add_argument(
        "--text", default="", help="human-answer: the answer text",
    )
    run_p.add_argument(
        "--verdict", choices=["approve", "reject"], default="approve",
        help="human-answer verdict (default: %(default)s)",
    )
    run_p.add_argument(
        "--nodes", default="all",
        help="retry-failed: comma-separated node ids, or 'all' "
             "(default: %(default)s)",
    )
    run_p.add_argument(
        "--ceiling", type=float,
        help="raise-budget: the new USD ceiling",
    )

    outcome_p = sub.add_parser(
        "outcome", help="pure read: print the persisted run's Outcome JSON",
    )
    _common(outcome_p)

    cancel_p = sub.add_parser(
        "cancel", help="cancel the persisted run (terminal)",
    )
    _common(cancel_p)

    return parser


def _load_graph(spec: str) -> Any:
    from delivery_workflow import compiler_a
    from delivery_workflow.spec_loader import load_spec

    return compiler_a.compile(load_spec(Path(spec)))


def _make_state_ops(workdir: Path) -> Any:
    from delivery_workflow.lib.state.events import EventLog
    from delivery_workflow.lib.state.ops import StateStoreOps
    from delivery_workflow.lib.state.store import StateStore

    run_dir = workdir / ".delivery-run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return StateStoreOps(StateStore(run_dir), EventLog(run_dir))


class _CliUsageError(Exception):
    """Bad flag combination — reported as EXIT_USAGE by main()."""


def _build_resume_event(args: argparse.Namespace, run: Any) -> Any:
    """Translate --resume flags into one typed package resume event."""
    from delivery_workflow.runner import (
        HumanAnswer,
        Nothing,
        RaiseBudget,
        RetryFailed,
    )

    if args.resume == "human-answer":
        node_id = args.node
        if not node_id:
            # Default to the Outcome's park point (the same blocked-human
            # query resume() validates against).
            node_id = run.outcome().node_id
        if not node_id:
            raise _CliUsageError(
                "--resume human-answer needs --node (the run is not parked "
                "on a sign-off node)"
            )
        return HumanAnswer(node_id=node_id, text=args.text, verdict=args.verdict)
    if args.resume == "retry-failed":
        nodes = args.nodes.strip()
        if nodes == "all":
            return RetryFailed("all")
        return RetryFailed([n.strip() for n in nodes.split(",") if n.strip()])
    if args.resume == "raise-budget":
        if args.ceiling is None:
            raise _CliUsageError("--resume raise-budget needs --ceiling")
        return RaiseBudget(new_usd_ceiling=args.ceiling)
    return Nothing()


def _usage(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return EXIT_USAGE


def _report(outcome: Any) -> int:
    """Print the Outcome JSON to stdout; return its exit code."""
    print(json.dumps(asdict(outcome), default=str))
    if outcome.kind == "blocked" and outcome.node_id:
        print(
            f"run blocked on sign-off '{outcome.node_id}': "
            f"{outcome.question or '(no prompt)'}\n"
            f"resume with: run <spec> --workdir <dir> --resume human-answer "
            f"--node {outcome.node_id} --text '...' "
            f"[--verdict approve|reject]",
            file=sys.stderr,
        )
    return EXIT_CODES.get(outcome.kind, EXIT_CODES["failed"])


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    from delivery_workflow.delivery_run import DeliveryRun
    from delivery_workflow.runner.resume import ResumeError

    try:
        graph = _load_graph(args.spec)
    except (OSError, ValueError) as exc:
        return _usage(f"cannot load spec {args.spec!r}: {exc}")

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    state_ops = _make_state_ops(workdir)

    if args.command == "run":
        from delivery_workflow.local_executor import (
            LocalHostPort,
            LocalProcessExecutor,
        )

        executor = LocalProcessExecutor(
            workdir,
            argv_template=shlex.split(args.claude_cmd),
            agent_timeout=args.agent_timeout,
            run_dir=workdir / ".delivery-run",
        )
        run = DeliveryRun(
            graph,
            executor=executor,
            state_ops=state_ops,
            host=LocalHostPort(),
            run_id=args.run_id or workdir.name,
        )
        try:
            if args.resume:
                outcome = run.resume(_build_resume_event(args, run))
            else:
                outcome = run.start()
        except _CliUsageError as exc:
            return _usage(str(exc))
        except ResumeError as exc:
            print(f"resume rejected: {exc}", file=sys.stderr)
            return EXIT_EVENT_REJECTED
        except FileNotFoundError as exc:
            return _usage(f"no persisted run to resume in {workdir}: {exc}")
        return _report(outcome)

    # outcome / cancel — pure reads / state-only writes: no executor needed.
    from delivery_workflow.null_runtime import NullRuntime

    run = DeliveryRun(
        graph, executor=NullRuntime(), state_ops=state_ops,
    )
    try:
        if args.command == "outcome":
            return _report(run.outcome())
        # cancel
        return _report(run.cancel())
    except FileNotFoundError:
        return _usage(f"no persisted run found in {workdir / '.delivery-run'}")
    except ResumeError as exc:
        print(f"cancel rejected: {exc}", file=sys.stderr)
        return EXIT_EVENT_REJECTED


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess tests
    raise SystemExit(main())
