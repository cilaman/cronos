"""Tests for lib.evals — portable eval-corpus harness.

All tests use an injected fake runner (no real pytest recursion — R5).
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from lib.evals import EvalResult, run_eval_corpus
from lib.evals.corpus import DEFAULT_EVAL_CMD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_runner(exit_code: int, stdout: str = "", stderr: str = ""):
    """Return a fake subprocess.run callable that returns a fixed result."""
    captured: list[dict] = []

    def runner(cmd, **kwargs):
        captured.append({"cmd": cmd, "kwargs": kwargs})
        return SimpleNamespace(returncode=exit_code, stdout=stdout, stderr=stderr)

    runner.captured = captured  # type: ignore[attr-defined]
    return runner


# ---------------------------------------------------------------------------
# Command resolution precedence
# ---------------------------------------------------------------------------


def test_eval_cmd_arg_takes_highest_precedence(monkeypatch):
    """eval_cmd argument overrides DELIVERY_EVAL_CMD env and the default."""
    monkeypatch.setenv("DELIVERY_EVAL_CMD", "pytest other/")
    runner = make_runner(0)
    result = run_eval_corpus(eval_cmd="my-custom-cmd", runner=runner)
    assert result.command == "my-custom-cmd"
    assert runner.captured[0]["cmd"] == "my-custom-cmd"


def test_delivery_eval_cmd_env_used_when_no_arg(monkeypatch):
    """DELIVERY_EVAL_CMD env var is used when eval_cmd arg is not given."""
    monkeypatch.setenv("DELIVERY_EVAL_CMD", "pytest custom-suite/")
    runner = make_runner(0)
    result = run_eval_corpus(runner=runner)
    assert result.command == "pytest custom-suite/"


def test_default_command_used_when_no_arg_and_no_env(monkeypatch):
    """Default command used when neither eval_cmd arg nor env var is set."""
    monkeypatch.delenv("DELIVERY_EVAL_CMD", raising=False)
    runner = make_runner(0)
    result = run_eval_corpus(runner=runner)
    assert result.command == DEFAULT_EVAL_CMD
    assert "packages/delivery-workflow/tests/" in result.command


# ---------------------------------------------------------------------------
# passed flag based on exit code
# ---------------------------------------------------------------------------


def test_exit_0_sets_passed_true():
    runner = make_runner(0)
    result = run_eval_corpus(runner=runner)
    assert result.passed is True
    assert result.exit_code == 0


def test_exit_nonzero_sets_passed_false():
    runner = make_runner(1, stderr="1 failed")
    result = run_eval_corpus(runner=runner)
    assert result.passed is False
    assert result.exit_code == 1


def test_exit_code_preserved():
    runner = make_runner(42)
    result = run_eval_corpus(runner=runner)
    assert result.exit_code == 42


# ---------------------------------------------------------------------------
# repo_root wiring
# ---------------------------------------------------------------------------


def test_repo_root_passed_as_cwd(tmp_path):
    runner = make_runner(0)
    run_eval_corpus(repo_root=tmp_path, runner=runner)
    assert runner.captured[0]["kwargs"]["cwd"] == str(tmp_path)


def test_repo_root_none_passes_none_cwd():
    runner = make_runner(0)
    run_eval_corpus(repo_root=None, runner=runner)
    assert runner.captured[0]["kwargs"]["cwd"] is None


# ---------------------------------------------------------------------------
# output_tail field
# ---------------------------------------------------------------------------


def test_output_tail_included_in_result():
    runner = make_runner(1, stdout="FAILED test_foo", stderr="short error")
    result = run_eval_corpus(runner=runner)
    assert "FAILED test_foo" in result.output_tail


def test_output_tail_truncated_to_2000_chars():
    long_output = "x" * 5000
    runner = make_runner(0, stdout=long_output)
    result = run_eval_corpus(runner=runner)
    assert len(result.output_tail) <= 2000


# ---------------------------------------------------------------------------
# EvalResult dataclass
# ---------------------------------------------------------------------------


def test_eval_result_fields():
    r = EvalResult(passed=True, exit_code=0, command="pytest", output_tail="ok")
    assert r.passed is True
    assert r.exit_code == 0
    assert r.command == "pytest"
    assert r.output_tail == "ok"


def test_eval_result_default_output_tail():
    r = EvalResult(passed=False, exit_code=1, command="pytest")
    assert r.output_tail == ""


# ---------------------------------------------------------------------------
# CLI exit-code propagation (smoke test via subprocess)
# ---------------------------------------------------------------------------


PACKAGE_DIR = Path(__file__).parent.parent


def test_cli_exits_with_corpus_exit_code(tmp_path):
    """CLI exits with the corpus exit code — verifies __main__.py wiring."""
    import subprocess as sp
    env = {**os.environ, "DELIVERY_EVAL_CMD": f"{sys.executable} -c 'import sys; sys.exit(0)'"}
    proc = sp.run(
        [sys.executable, "-m", "lib.evals", "--repo-root", str(tmp_path)],
        capture_output=True,
        cwd=str(PACKAGE_DIR),
        env=env,
    )
    assert proc.returncode == 0


def test_cli_json_flag_emits_json(tmp_path):
    """CLI --json flag prints a valid JSON object to stdout."""
    import json as _json
    import subprocess as sp
    env = {**os.environ, "DELIVERY_EVAL_CMD": f"{sys.executable} -c 'import sys; sys.exit(0)'"}
    proc = sp.run(
        [sys.executable, "-m", "lib.evals", "--json"],
        capture_output=True,
        text=True,
        cwd=str(PACKAGE_DIR),
        env=env,
    )
    data = _json.loads(proc.stdout)
    assert "passed" in data
    assert "exit_code" in data
    assert "command" in data
