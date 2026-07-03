"""LocalProcessExecutor + LocalHostPort + the promoted closed-vocab mapping (R10e).

The reference runtime behind the standalone CLI (02-package-boundary.md §2.3):
agent children are real subprocesses (sys.executable stubs — no fake claude on
PATH needed here), the node_status fence is parsed with the package's own
``lib.node_status`` parser, and the status vocabulary is closed through the
SAME ``results.agent_result_from_envelope`` mapping the Cronos adapter uses —
one mapping, two executors.

Zero app.*/backend imports anywhere in this suite (package CI installs only
this package).
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from delivery_workflow.events import (
    NodeFinished,
    NodeStarted,
    RunBlocked,
    RunEscalated,
    RunStalled,
)
from delivery_workflow.lib.exec_node import run_exec_command
from delivery_workflow.lib.node_status import parse_node_status
from delivery_workflow.local_executor import (
    DEFAULT_ARGV_TEMPLATE,
    LocalHostPort,
    LocalProcessExecutor,
    compose_brief,
)
from delivery_workflow.results import (
    AGENT_STATUS_VOCAB,
    TelemetryData,
    agent_result_from_envelope,
)

# ---------------------------------------------------------------------------
# Child-process stubs: python -c code; the brief arrives as argv[1] (a "{brief}"
# tail element) so quoting inside the code stays trivial.
# ---------------------------------------------------------------------------

_FENCE_DONE = (
    'print(\'```node_status\\n{"status": "done", "artifact_paths": ["out.md"],'
    ' "produces": "research", "fields": {"ok": true},'
    ' "open_questions": []}\\n```\')'
)
_FENCE_UNKNOWN = (
    'print(\'```node_status\\n{"status": "wait", "artifact_paths": ["x.md"],'
    ' "fields": {"why": "still waiting"}, "open_questions": ["blocked on X"]}'
    "\\n```')"
)


def _executor(tmp_path: Path, code: str, **kwargs) -> LocalProcessExecutor:
    return LocalProcessExecutor(
        tmp_path,
        argv_template=(sys.executable, "-c", code, "{brief}"),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# dispatchAgent
# ---------------------------------------------------------------------------


class TestDispatchAgent:
    def test_fence_parsed_and_mapped(self, tmp_path):
        ex = _executor(tmp_path, _FENCE_DONE)
        result = ex.dispatchAgent("worker", {"node_id": "scout", "attempt": 1})
        assert result.status == "done"
        assert result.artifact_paths == ["out.md"]
        assert result.produces == "research"
        assert result.fields == {"ok": True}
        assert result.open_questions == []
        assert result.telemetry.seconds > 0

    def test_unknown_status_maps_to_failed_with_marker(self, tmp_path):
        ex = _executor(tmp_path, _FENCE_UNKNOWN)
        result = ex.dispatchAgent("worker", {"node_id": "scout"})
        assert result.status == "failed"
        assert result.open_questions[0] == "unknown_status:wait"
        # Envelope payload kept for diagnosis.
        assert result.artifact_paths == ["x.md"]
        assert result.fields == {"why": "still waiting"}
        assert "blocked on X" in result.open_questions

    def test_no_fence_maps_to_failed(self, tmp_path):
        ex = _executor(tmp_path, "print('chatter, no fence')")
        result = ex.dispatchAgent("worker", {"node_id": "scout"})
        assert result.status == "failed"
        assert "No node_status fence found" in result.open_questions[0]
        assert "'scout'" in result.open_questions[0]

    def test_nonzero_exit_is_failed_even_with_fence(self, tmp_path):
        ex = _executor(
            tmp_path, _FENCE_DONE + "\nimport sys\nsys.exit(3)"
        )
        result = ex.dispatchAgent("worker", {"node_id": "scout"})
        assert result.status == "failed"
        assert "exited 3" in result.open_questions[0]

    def test_nonzero_exit_carries_stderr_tail(self, tmp_path):
        ex = _executor(
            tmp_path,
            "import sys\nprint('boom detail', file=sys.stderr)\nsys.exit(1)",
        )
        result = ex.dispatchAgent("worker", {"node_id": "scout"})
        assert result.status == "failed"
        assert any("boom detail" in q for q in result.open_questions)

    def test_timeout_is_failed(self, tmp_path):
        ex = _executor(
            tmp_path, "import time\ntime.sleep(5)", agent_timeout=0.3
        )
        result = ex.dispatchAgent("worker", {"node_id": "scout"})
        assert result.status == "failed"
        assert "timed out" in result.open_questions[0]

    def test_missing_binary_is_failed(self, tmp_path):
        ex = LocalProcessExecutor(
            tmp_path,
            argv_template=("definitely-not-a-real-binary-xyz", "{brief}"),
        )
        result = ex.dispatchAgent("worker", {"node_id": "scout"})
        assert result.status == "failed"
        assert "not found" in result.open_questions[0]

    def test_child_runs_in_workdir_and_receives_brief(self, tmp_path):
        # The child echoes its cwd and asserts the brief arrived via argv.
        code = (
            "import sys, os, json\n"
            "brief = sys.argv[1]\n"
            "assert 'node_status' in brief and 'worker' in brief\n"
            "print('```node_status')\n"
            "print(json.dumps({'status': 'done',"
            " 'fields': {'cwd': os.getcwd()}}))\n"
            "print('```')\n"
        )
        ex = _executor(tmp_path, code)
        result = ex.dispatchAgent("worker", {"node_id": "scout"})
        assert result.status == "done"
        assert Path(result.fields["cwd"]).resolve() == tmp_path.resolve()

    def test_template_without_brief_placeholder_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="brief"):
            LocalProcessExecutor(tmp_path, argv_template=("claude",))

    def test_default_template_is_claude_p(self):
        assert DEFAULT_ARGV_TEMPLATE == ("claude", "-p", "{brief}")


class TestComposeBrief:
    def test_brief_carries_identity_scope_and_return_contract(self):
        brief = compose_brief(
            "worker",
            {
                "node_id": "analyze",
                "attempt": 2,
                "produces": {"class": "analysis"},
                "scope": {"scout": {"fields": {"has_ui": True}}},
            },
        )
        assert "'worker'" in brief and "'analyze'" in brief
        assert "attempt 2" in brief
        assert "analysis" in brief
        assert '"has_ui": true' in brief  # scope JSON
        assert "```node_status" in brief
        for status in sorted(AGENT_STATUS_VOCAB):
            assert status in brief


# ---------------------------------------------------------------------------
# runGate / runExec
# ---------------------------------------------------------------------------


class TestRunGateAndExec:
    def test_gate_delegates_to_lib_gate(self, tmp_path):
        ex = _executor(tmp_path, _FENCE_DONE)
        result = ex.runGate({"id": "g-x", "checks": []}, [])
        assert result.decision == "proceed"

    def test_gate_unknown_check_type_fails(self, tmp_path):
        ex = _executor(tmp_path, _FENCE_DONE)
        result = ex.runGate(
            {"id": "g-x", "checks": [{"type": "no-such-check"}]}, []
        )
        assert result.decision == "fail"
        assert any("unknown check type" in e for e in result.errors)

    def test_exec_zero_exit_done_with_artifact(self, tmp_path):
        ex = _executor(tmp_path, _FENCE_DONE)
        result = ex.runExec("testrun", "echo hello", {})
        assert result.status == "done"
        assert result.exit_code == 0
        assert "hello" in result.stdout_tail
        art = Path(result.artifact_path)
        assert art.name == "testrun-output.md"
        assert art.parent == ex.run_dir

    def test_exec_nonzero_exit_failed(self, tmp_path):
        ex = _executor(tmp_path, _FENCE_DONE)
        result = ex.runExec("build", "exit 3", {})
        assert result.status == "failed"
        assert result.exit_code == 3

    def test_exec_fail_on_nonzero_false_is_done(self, tmp_path):
        ex = _executor(tmp_path, _FENCE_DONE)
        result = ex.runExec("testrun", "exit 1", {"fail_on_nonzero": False})
        assert result.status == "done"
        assert result.exit_code == 1

    def test_shared_exec_helper_timeout(self, tmp_path):
        result = run_exec_command(
            "slow", "sleep 5", {"timeout": 1},
            cwd=tmp_path, artifact_dir=tmp_path / "run",
        )
        assert result.status == "failed"
        assert result.exit_code == -1
        assert "timed out" in result.stdout_tail


# ---------------------------------------------------------------------------
# The promoted closed-vocab mapping (shared with the Cronos adapter)
# ---------------------------------------------------------------------------


class TestAgentResultFromEnvelope:
    def test_accepts_node_status_block_objects(self):
        block = parse_node_status(
            "```node_status\n"
            '{"status": "needs_fix", "artifact_paths": ["r.md"],'
            ' "produces": "review", "fields": {"verdict": "needs_fix"},'
            ' "open_questions": ["fix Y"]}\n'
            "```"
        )
        result = agent_result_from_envelope(block, node_id="review")
        assert result.status == "needs_fix"
        assert result.artifact_paths == ["r.md"]
        assert result.fields == {"verdict": "needs_fix"}
        assert result.open_questions == ["fix Y"]

    def test_accepts_plain_mappings(self):
        result = agent_result_from_envelope(
            {"status": " DONE ", "artifact_paths": ["a.md"]}, node_id="n"
        )
        assert result.status == "done"  # stripped + lowercased
        assert result.artifact_paths == ["a.md"]

    def test_missing_envelope_names_the_node(self):
        result = agent_result_from_envelope(None, node_id="scout")
        assert result.status == "failed"
        assert result.open_questions == [
            "No node_status fence found in agent output for node 'scout'"
        ]

    def test_missing_detail_is_appended_in_parentheses(self):
        # The Cronos adapter passes 'trace.node_status is None' — the promoted
        # mapping must reproduce the adapter's historical message exactly.
        result = agent_result_from_envelope(
            None, node_id="scout", missing_detail="trace.node_status is None"
        )
        assert result.open_questions == [
            "No node_status fence found in agent output for node 'scout' "
            "(trace.node_status is None)"
        ]

    def test_unknown_status_never_maps_to_done(self):
        result = agent_result_from_envelope(
            {"status": "partial", "open_questions": ["hm"]}, node_id="n"
        )
        assert result.status == "failed"
        assert result.open_questions == ["unknown_status:partial", "hm"]

    def test_telemetry_passthrough_and_default(self):
        telem = TelemetryData(tokens=5, usd=0.1, seconds=2.0)
        assert (
            agent_result_from_envelope(
                {"status": "done"}, node_id="n", telemetry=telem
            ).telemetry
            is telem
        )
        default = agent_result_from_envelope({"status": "done"}, node_id="n")
        assert default.telemetry == TelemetryData(tokens=0, usd=0.0, seconds=0.0)

    def test_vocabulary_is_the_closed_agent_result_literal(self):
        assert AGENT_STATUS_VOCAB == frozenset(
            {"done", "blocked", "needs_fix", "failed"}
        )


# ---------------------------------------------------------------------------
# LocalHostPort
# ---------------------------------------------------------------------------


class TestLocalHostPort:
    def test_prints_one_json_line_per_event(self):
        stream = io.StringIO()
        host = LocalHostPort(stream=stream)
        host.on_event(NodeStarted(node_id="scout", attempt=1))
        host.on_event(NodeFinished(node_id="scout", status="done"))
        host.on_event(RunBlocked(node_id="signoff", question="Ship?"))
        host.on_event(RunStalled(detail={"kind": "gate_exhausted"}))
        host.on_event(
            RunEscalated(kind="loop", node_id="g-x", detail="exhausted")
        )
        lines = [json.loads(line) for line in stream.getvalue().splitlines()]
        assert [entry["event"] for entry in lines] == [
            "node_started",
            "node_finished",
            "run_blocked",
            "run_stalled",
            "run_escalated",
        ]
        assert lines[0] == {"event": "node_started", "node_id": "scout", "attempt": 1}
        assert lines[2]["question"] == "Ship?"
        assert lines[3]["detail"] == {"kind": "gate_exhausted"}
