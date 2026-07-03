"""lib/exec_node — run an ``exec`` node's shell command to completion (R10e).

The one implementation of exec-node semantics, shared by every executor (the
Cronos adapter at ``backend/app/delivery_adapter.py`` and the in-package
``LocalProcessExecutor``) — promoted out of the host adapter so the logic
lives exactly once (02-package-boundary.md §2.3, no-duplication rule):

- An ``exec`` node has no LLM turn: the runner blocks on this synchronously,
  so a long command (a test suite) runs in-foreground with nothing to
  background — removing the orphan-and-hang trap that stranded the LLM tester
  agent (P1).
- Exit 0 → ``done``.  Non-zero exit → ``failed`` UNLESS the node sets
  ``fail_on_nonzero: false`` — used by ``testrun`` so a test failure does not
  halt the runner but is instead routed by the downstream ``g-tests`` gate.
- Captured output is written as the node's own artifact
  (``<artifact_dir>/<node_id>-output.md``) so the credited artifact is always
  the node's own (P2).

The executor returns the ExecResult ONLY — the runner is the single writer of
the exec node's status/artifact_paths/exit_code (R9, 01-state-model.md §5.8).

Trust model: a workflow spec is TRUSTED INPUT (like a Makefile).  The command
runs with ``shell=True`` in the working directory with the caller's
environment (filtered only by ``lib.security.build_subprocess_env``) — never
run a spec you do not trust; this module is not a sandbox.

No app.* imports allowed (enforced by .importlinter).
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from delivery_workflow.lib.security import build_subprocess_env
from delivery_workflow.results import ExecResult

log = logging.getLogger(__name__)

#: Default per-command timeout (seconds) when the node declares none.
DEFAULT_EXEC_TIMEOUT = 900


def run_exec_command(
    node_id: str,
    command: str,
    inputs: dict[str, Any],
    *,
    cwd: Path,
    artifact_dir: Path,
) -> ExecResult:
    """Run *command* to completion in *cwd* and capture its output.

    *inputs* carries the node data the runner forwards
    (``runner/dispatch.py``): ``produces`` (class descriptor),
    ``fail_on_nonzero`` (default True) and ``timeout`` (seconds, default
    ``DEFAULT_EXEC_TIMEOUT``).  The captured output is written to
    ``<artifact_dir>/<node_id>-output.md`` (best-effort; a write failure is
    logged and the result carries ``artifact_path=None``).
    """
    prod = inputs.get("produces")
    produces = prod.get("class") if isinstance(prod, dict) else prod

    fail_on_nonzero = inputs.get("fail_on_nonzero", True)
    exec_timeout = DEFAULT_EXEC_TIMEOUT
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
            cwd=str(cwd),
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

    # Write captured output as the node's own artifact (P2).
    artifact_path: str | None = None
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        art = artifact_dir / f"{node_id}-output.md"
        art.write_text(output, encoding="utf-8")
        artifact_path = str(art)
    except Exception:
        log.exception(
            "run_exec_command: failed to write artifact for node %r", node_id
        )

    status = "done" if (exit_code == 0 or not fail_on_nonzero) else "failed"

    return ExecResult(
        status=status,  # type: ignore[arg-type]  # "done" | "failed" only
        exit_code=exit_code,
        stdout_tail=output[-2000:],
        artifact_path=artifact_path,
        produces=produces,
    )
