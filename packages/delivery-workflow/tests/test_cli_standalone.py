"""Standalone CLI smoke tests (R10e — 02-package-boundary.md §2.3).

``python -m delivery_workflow run spec.yaml --workdir DIR`` IS the standalone
deliverable: these tests drive it end-to-end in REAL subprocesses with a FAKE
``claude`` binary on PATH (a shell stub emitting a valid node_status fence) —
no Cronos anywhere in any process, park→resume through the CLI's typed
``--resume`` grammar, honest exit codes per Outcome kind.

Also pins the standalone-purity acceptance: importing the whole host surface
(``delivery_workflow`` + ``local_executor`` + ``__main__``) never drags
``app`` into ``sys.modules``.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from delivery_workflow.__main__ import (
    EXIT_CODES,
    EXIT_EVENT_REJECTED,
    EXIT_USAGE,
    build_parser,
)

SRC_DIR = Path(__file__).resolve().parents[1] / "src"

SMOKE_SPEC = """\
apiVersion: delivery/v1
metadata:
  name: cli-smoke
nodes:
  - id: work
    kind: agent
    agent: worker
    produces:
      class: research
  - id: approve
    kind: human
    prompt: "Ship it?"
  - id: finish
    kind: exec
    command: "echo finished"
edges:
  - {from: work, to: approve}
  - {from: approve, to: finish}
"""

FENCE_DONE = (
    '{"status": "done", "artifact_paths": ["out.md"], "produces": "research",'
    ' "fields": {"ok": true}, "open_questions": []}'
)
FENCE_FAILED = (
    '{"status": "failed", "artifact_paths": [], "produces": "",'
    ' "fields": {"error": "scripted failure"}, "open_questions": []}'
)


def _write_fake_claude(bin_dir: Path, fence_json: str) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "claude"
    stub.write_text(
        "#!/bin/sh\n"
        "cat <<'EOF'\n"
        "agent chatter...\n"
        "```node_status\n"
        f"{fence_json}\n"
        "```\n"
        "EOF\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)


def _cli(
    *args: str, bin_dir: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run ``python -m delivery_workflow …`` in a fresh process."""
    env = dict(os.environ)
    if bin_dir is not None:
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    # Ensure the package resolves even when not pip-installed in this env.
    env["PYTHONPATH"] = f"{SRC_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}"
    return subprocess.run(
        [sys.executable, "-m", "delivery_workflow", *args],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


@pytest.fixture()
def smoke(tmp_path: Path) -> dict[str, Path]:
    spec = tmp_path / "spec.yaml"
    spec.write_text(SMOKE_SPEC, encoding="utf-8")
    bin_dir = tmp_path / "bin"
    _write_fake_claude(bin_dir, FENCE_DONE)
    return {"spec": spec, "workdir": tmp_path / "wd", "bin": bin_dir}


def _outcome_json(proc: subprocess.CompletedProcess[str]) -> dict:
    # stdout carries exactly one JSON object (progress lines go to stderr).
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------------------
# The full lifecycle: run → park (blocked) → resume approve → done.
# ---------------------------------------------------------------------------


class TestRunParkResumeCycle:
    def test_full_cycle(self, smoke):
        spec, wd, bin_dir = smoke["spec"], smoke["workdir"], smoke["bin"]

        # 1. Fresh run: the agent node succeeds (fake claude fence), the
        #    human node parks the run → exit code 10, question reported.
        first = _cli("run", str(spec), "--workdir", str(wd), bin_dir=bin_dir)
        assert first.returncode == EXIT_CODES["blocked"], first.stderr
        outcome = _outcome_json(first)
        assert outcome["kind"] == "blocked"
        assert outcome["node_id"] == "approve"
        assert outcome["question"] == "Ship it?"
        assert "Ship it?" in first.stderr  # the CLI reports the question
        # Structured progress lines streamed to stderr.
        events = [
            json.loads(line)["event"]
            for line in first.stderr.splitlines()
            if line.startswith("{")
        ]
        assert "node_started" in events and "run_blocked" in events
        # State persisted in the workdir.
        assert (wd / ".delivery-run" / "state.json").exists()
        assert (wd / ".delivery-run" / "events.jsonl").exists()

        # 2. A bare re-run is sealed (no double dispatch): same park, same code.
        again = _cli("run", str(spec), "--workdir", str(wd), bin_dir=bin_dir)
        assert again.returncode == EXIT_CODES["blocked"]
        assert _outcome_json(again)["kind"] == "blocked"

        # 3. Resume through the CLI's typed grammar → exec node runs → done.
        resumed = _cli(
            "run", str(spec), "--workdir", str(wd),
            "--resume", "human-answer", "--node", "approve",
            "--text", "ship it", "--verdict", "approve",
            bin_dir=bin_dir,
        )
        assert resumed.returncode == 0, resumed.stderr
        assert _outcome_json(resumed)["kind"] == "done"
        # The exec node really ran in the workdir.
        artifact = wd / ".delivery-run" / "finish-output.md"
        assert "finished" in artifact.read_text(encoding="utf-8")

        # 4. outcome subcommand: pure read of the terminal.
        read = _cli("outcome", str(spec), "--workdir", str(wd))
        assert read.returncode == 0
        assert _outcome_json(read)["kind"] == "done"

        # 5. cancel on a done run is refused (nothing left to cancel).
        cancelled = _cli("cancel", str(spec), "--workdir", str(wd))
        assert cancelled.returncode == EXIT_EVENT_REJECTED
        assert "cancel rejected" in cancelled.stderr

    def test_resume_node_defaults_to_the_park_point(self, smoke):
        spec, wd, bin_dir = smoke["spec"], smoke["workdir"], smoke["bin"]
        _cli("run", str(spec), "--workdir", str(wd), bin_dir=bin_dir)
        resumed = _cli(
            "run", str(spec), "--workdir", str(wd),
            "--resume", "human-answer", "--text", "yes",
            bin_dir=bin_dir,
        )
        assert resumed.returncode == 0, resumed.stderr
        assert _outcome_json(resumed)["kind"] == "done"


class TestFailedAndRetry:
    def test_failed_run_exits_30_and_retry_failed_reenters(self, tmp_path):
        spec = tmp_path / "spec.yaml"
        spec.write_text(SMOKE_SPEC, encoding="utf-8")
        wd = tmp_path / "wd"
        bad_bin = tmp_path / "bad-bin"
        good_bin = tmp_path / "good-bin"
        _write_fake_claude(bad_bin, FENCE_FAILED)
        _write_fake_claude(good_bin, FENCE_DONE)

        first = _cli("run", str(spec), "--workdir", str(wd), bin_dir=bad_bin)
        assert first.returncode == EXIT_CODES["failed"]
        outcome = _outcome_json(first)
        assert outcome["kind"] == "failed"
        assert outcome["node_id"] == "work"

        # RetryFailed('all') through the CLI, with a now-working agent: the
        # re-armed node succeeds and the run parks at the sign-off.
        retried = _cli(
            "run", str(spec), "--workdir", str(wd),
            "--resume", "retry-failed",
            bin_dir=good_bin,
        )
        assert retried.returncode == EXIT_CODES["blocked"], retried.stderr
        assert _outcome_json(retried)["kind"] == "blocked"


class TestCancel:
    def test_cancel_parked_run_is_terminal(self, smoke):
        spec, wd, bin_dir = smoke["spec"], smoke["workdir"], smoke["bin"]
        _cli("run", str(spec), "--workdir", str(wd), bin_dir=bin_dir)

        cancelled = _cli("cancel", str(spec), "--workdir", str(wd))
        assert cancelled.returncode == EXIT_CODES["cancelled"]
        assert _outcome_json(cancelled)["kind"] == "cancelled"

        # start() is sealed on a cancelled run; resume raises → exit 3.
        rerun = _cli("run", str(spec), "--workdir", str(wd), bin_dir=bin_dir)
        assert rerun.returncode == EXIT_CODES["cancelled"]
        resumed = _cli(
            "run", str(spec), "--workdir", str(wd),
            "--resume", "human-answer", "--node", "approve", "--text", "y",
            bin_dir=bin_dir,
        )
        assert resumed.returncode == EXIT_EVENT_REJECTED
        assert "resume rejected" in resumed.stderr


# ---------------------------------------------------------------------------
# Usage / help / exit-code documentation.
# ---------------------------------------------------------------------------


class TestUsage:
    def test_help_documents_the_exit_codes(self):
        proc = _cli("run", "--help")
        assert proc.returncode == 0
        for kind, code in EXIT_CODES.items():
            assert kind in proc.stdout, f"exit-code doc missing {kind!r}"
            assert str(code) in proc.stdout

    def test_unloadable_spec_is_usage_error(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("apiVersion: nope\n", encoding="utf-8")
        proc = _cli("run", str(bad), "--workdir", str(tmp_path / "wd"))
        assert proc.returncode == EXIT_USAGE
        assert "cannot load spec" in proc.stderr

    def test_outcome_without_a_run_is_usage_error(self, tmp_path):
        spec = tmp_path / "spec.yaml"
        spec.write_text(SMOKE_SPEC, encoding="utf-8")
        proc = _cli("outcome", str(spec), "--workdir", str(tmp_path / "wd"))
        assert proc.returncode == EXIT_USAGE
        assert "no persisted run" in proc.stderr

    def test_raise_budget_requires_ceiling(self, smoke):
        spec, wd, bin_dir = smoke["spec"], smoke["workdir"], smoke["bin"]
        _cli("run", str(spec), "--workdir", str(wd), bin_dir=bin_dir)
        proc = _cli(
            "run", str(spec), "--workdir", str(wd),
            "--resume", "raise-budget",
        )
        assert proc.returncode == EXIT_USAGE
        assert "--ceiling" in proc.stderr

    def test_exit_codes_cover_the_closed_outcome_taxonomy(self):
        from delivery_workflow.outcome import OutcomeKind
        from typing import get_args

        assert set(EXIT_CODES) == set(get_args(OutcomeKind))
        assert EXIT_CODES["done"] == 0
        nonzero = {v for k, v in EXIT_CODES.items() if k != "done"}
        assert 0 not in nonzero
        assert len(nonzero) == len(EXIT_CODES) - 1  # all distinct

    def test_parser_builds(self):
        parser = build_parser()
        args = parser.parse_args(
            ["run", "spec.yaml", "--workdir", "wd", "--resume", "nothing"]
        )
        assert args.command == "run" and args.resume == "nothing"


# ---------------------------------------------------------------------------
# Standalone purity: no app.* anywhere in the process (acceptance §2.3).
# ---------------------------------------------------------------------------


class TestNoCronosAnywhere:
    def test_app_not_in_sys_modules_after_importing_the_host_surface(self):
        import delivery_workflow  # noqa: F401
        import delivery_workflow.__main__  # noqa: F401
        import delivery_workflow.local_executor  # noqa: F401

        assert "app" not in sys.modules
        assert not any(m.startswith("app.") for m in sys.modules)

    def test_fresh_process_import_carries_no_app(self):
        code = (
            "import delivery_workflow, delivery_workflow.__main__, "
            "delivery_workflow.local_executor, sys\n"
            "assert 'app' not in sys.modules\n"
            "assert not any(m.startswith('app.') for m in sys.modules)\n"
            "print('pure')\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{SRC_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}"
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=60, env=env,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "pure"
