"""Portable eval-corpus harness for delivery/v1.

run_eval_corpus(repo_root, *, eval_cmd, env, runner) -> EvalResult

Command resolution precedence (highest to lowest):
  1. eval_cmd argument
  2. DELIVERY_EVAL_CMD environment variable
  3. Default: pytest packages/delivery-workflow/tests/ -q --no-header

This is the single source of truth for the eval-corpus default and env override.
Both the Cronos improve node and the standalone runner invoke the corpus here.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

DEFAULT_EVAL_CMD = "pytest packages/delivery-workflow/tests/ -q --no-header"


@dataclass
class EvalResult:
    """Outcome of a run_eval_corpus call."""

    passed: bool
    exit_code: int
    command: str
    output_tail: str = field(default="")


def run_eval_corpus(
    repo_root: str | Path | None = None,
    *,
    eval_cmd: str | None = None,
    env: dict[str, str] | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> EvalResult:
    """Run the delivery/v1 eval corpus and return a structured result.

    Args:
        repo_root: Directory to run the command from. Defaults to cwd.
        eval_cmd: Override the command directly (highest precedence).
        env:      Extra environment variables merged into os.environ.
        runner:   Subprocess callable (injectable for tests; default subprocess.run).

    Returns:
        EvalResult with passed=True iff exit_code == 0.
    """
    # Command resolution: arg > DELIVERY_EVAL_CMD env > default
    if eval_cmd is not None:
        command = eval_cmd
    else:
        command = os.environ.get("DELIVERY_EVAL_CMD", DEFAULT_EVAL_CMD)

    cwd = str(repo_root) if repo_root is not None else None

    run_env = dict(os.environ)
    if env:
        run_env.update(env)

    result = runner(
        command,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=run_env,
    )

    exit_code = result.returncode
    combined = (result.stdout or "") + (result.stderr or "")
    output_tail = combined[-2000:] if len(combined) > 2000 else combined

    return EvalResult(
        passed=exit_code == 0,
        exit_code=exit_code,
        command=command,
        output_tail=output_tail,
    )
