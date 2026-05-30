"""Tests for app.pipeline.state_writer.

Covers:
- init_pipeline: creates pipeline-state.json with CC_VERSION + empty phases-log.jsonl
- record_phase_log: appends JSONL lines with all required fields
- update_phase: writes phase entry + recomputes telemetry
- finalize_pipeline: updates top-level status
- load_state / load_last_phase_log: read helpers
- PhaseMetrics.from_trace: extracts metrics from RunTrace
- Idempotent telemetry recomputation (no double-count on repeated update)
- FileNotFoundError when state not initialised
- Atomic writes: .tmp file is not left behind
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.pipeline.contract import CC_VERSION
from app.pipeline.state_writer import (
    PHASES_LOG_FILENAME,
    PIPELINE_STATE_FILENAME,
    PhaseEntry,
    PhaseMetrics,
    PhaseVerifyResult,
    finalize_pipeline,
    init_pipeline,
    load_last_phase_log,
    load_state,
    log_path,
    pipeline_dir,
    record_phase_log,
    state_path,
    update_phase,
)
from app.trace_parser import AssistantTurnTrace, RunTrace, ToolCallTrace


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GOAL_SLUG = "my-feature"
_TS = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_trace(
    *,
    task_id: str = "task-1",
    space_id: str = "space-1",
    run_index: int = 0,
    duration_seconds: float = 10.0,
    turns: list[AssistantTurnTrace] | None = None,
    tool_calls: list[ToolCallTrace] | None = None,
    total_tool_calls: int = 5,
    read_tool_calls: int = 3,
    memory_used: list[str] | None = None,
) -> RunTrace:
    return RunTrace(
        task_id=task_id,
        space_id=space_id,
        run_index=run_index,
        session_id="sess-1",
        model="claude-sonnet-4-6",
        mode="auto",
        started_at=_TS,
        ended_at=_TS,
        duration_seconds=duration_seconds,
        exit_reason="result",
        turns=turns or [],
        tool_calls=tool_calls or [],
        total_tool_calls=total_tool_calls,
        read_tool_calls=read_tool_calls,
        write_tool_calls=total_tool_calls - read_tool_calls,
        memory_used=memory_used or [],
    )


def _make_turns(input_tokens: int = 100, output_tokens: int = 50,
                cache_read: int = 20, cache_creation: int = 10) -> list[AssistantTurnTrace]:
    return [
        AssistantTurnTrace(
            turn_index=0,
            text_snippet="",
            has_thinking=False,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
        )
    ]


def _make_phase(
    name: str = "scout",
    status: str = "done",
    gate_decision: str = "proceed",
    task_id: str = "task-1",
    run_index: int = 0,
    metrics: PhaseMetrics | None = None,
) -> PhaseEntry:
    return PhaseEntry(
        phase=name,
        status=status,
        agent="pipeline-scout",
        task_id=task_id,
        run_index=run_index,
        artifact_path=f".cronos/pipeline/{GOAL_SLUG}/scout-report-{GOAL_SLUG}.md",
        verify_result=PhaseVerifyResult(
            passed=gate_decision == "proceed",
            gate_decision=gate_decision,
            gate_reason="ok",
        ),
        metrics=metrics or PhaseMetrics(),
    )


# ---------------------------------------------------------------------------
# init_pipeline
# ---------------------------------------------------------------------------

class TestInitPipeline:
    def test_creates_state_file(self, tmp_path):
        state = init_pipeline(tmp_path, GOAL_SLUG)
        sp = state_path(tmp_path, GOAL_SLUG)
        assert sp.exists()
        loaded = json.loads(sp.read_text())
        assert loaded["cc_version"] == CC_VERSION
        assert loaded["goal_slug"] == GOAL_SLUG
        assert loaded["status"] == "running"
        assert loaded["phases"] == {}

    def test_creates_empty_phases_log(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        lp = log_path(tmp_path, GOAL_SLUG)
        assert lp.exists()
        assert lp.read_text(encoding="utf-8") == ""

    def test_cc_version_in_state(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        state = load_state(tmp_path, GOAL_SLUG)
        assert state["cc_version"] == CC_VERSION

    def test_custom_status(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG, status="awaiting_approval")
        state = load_state(tmp_path, GOAL_SLUG)
        assert state["status"] == "awaiting_approval"

    def test_request_text_stored(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG, request_text="Add dark mode")
        state = load_state(tmp_path, GOAL_SLUG)
        assert state["request_text"] == "Add dark mode"

    def test_custom_created_at(self, tmp_path):
        ts = "2026-01-01T00:00:00+00:00"
        init_pipeline(tmp_path, GOAL_SLUG, created_at=ts)
        state = load_state(tmp_path, GOAL_SLUG)
        assert state["created_at"] == ts

    def test_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "spaces" / "my-space"
        init_pipeline(nested, GOAL_SLUG)
        assert state_path(nested, GOAL_SLUG).exists()

    def test_returns_state_dict(self, tmp_path):
        state = init_pipeline(tmp_path, GOAL_SLUG)
        assert isinstance(state, dict)
        assert state["goal_slug"] == GOAL_SLUG

    def test_telemetry_initialised_to_zeros(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        state = load_state(tmp_path, GOAL_SLUG)
        t = state["telemetry"]
        assert t["total_duration_s"] == 0.0
        assert t["total_token_spend"] == 0
        assert t["phases_completed"] == 0

    def test_overwrite_existing_state(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG, request_text="first")
        init_pipeline(tmp_path, GOAL_SLUG, request_text="second")
        state = load_state(tmp_path, GOAL_SLUG)
        assert state["request_text"] == "second"

    def test_phases_log_not_overwritten_if_exists(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        lp = log_path(tmp_path, GOAL_SLUG)
        lp.write_text('{"phase":"scout"}\n', encoding="utf-8")
        init_pipeline(tmp_path, GOAL_SLUG)
        # pre-existing log content should be preserved
        assert lp.read_text(encoding="utf-8") == '{"phase":"scout"}\n'


# ---------------------------------------------------------------------------
# record_phase_log
# ---------------------------------------------------------------------------

class TestRecordPhaseLog:
    def test_appends_one_line(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        record_phase_log(tmp_path, GOAL_SLUG,
                         phase="scout", status="done", gate_decision="proceed",
                         task_id="t1", run_index=0)
        lp = log_path(tmp_path, GOAL_SLUG)
        lines = [l for l in lp.read_text().splitlines() if l.strip()]
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["phase"] == "scout"
        assert entry["status"] == "done"
        assert entry["gate_decision"] == "proceed"
        assert entry["task_id"] == "t1"
        assert entry["run_index"] == 0
        assert "timestamp" in entry

    def test_multiple_appends(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        for phase in ("scout", "analysis", "design"):
            record_phase_log(tmp_path, GOAL_SLUG,
                             phase=phase, status="done", gate_decision="proceed",
                             task_id=f"t-{phase}", run_index=0)
        lp = log_path(tmp_path, GOAL_SLUG)
        lines = [l for l in lp.read_text().splitlines() if l.strip()]
        assert len(lines) == 3
        phases = [json.loads(l)["phase"] for l in lines]
        assert phases == ["scout", "analysis", "design"]

    def test_custom_timestamp(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        ts = "2026-01-15T10:30:00+00:00"
        record_phase_log(tmp_path, GOAL_SLUG,
                         phase="scout", status="done", gate_decision="proceed",
                         task_id="t1", run_index=0, timestamp=ts)
        lp = log_path(tmp_path, GOAL_SLUG)
        entry = json.loads(lp.read_text().strip())
        assert entry["timestamp"] == ts

    def test_creates_dir_if_missing(self, tmp_path):
        space = tmp_path / "no-init-space"
        record_phase_log(space, GOAL_SLUG,
                         phase="scout", status="done", gate_decision="proceed",
                         task_id="t1", run_index=0)
        lp = log_path(space, GOAL_SLUG)
        assert lp.exists()

    def test_failed_gate_recorded(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        record_phase_log(tmp_path, GOAL_SLUG,
                         phase="scout", status="failed", gate_decision="fail",
                         task_id="t1", run_index=2)
        entry = json.loads(log_path(tmp_path, GOAL_SLUG).read_text().strip())
        assert entry["gate_decision"] == "fail"
        assert entry["run_index"] == 2


# ---------------------------------------------------------------------------
# update_phase
# ---------------------------------------------------------------------------

class TestUpdatePhase:
    def test_writes_phase_into_state(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        phase = _make_phase("scout")
        update_phase(tmp_path, GOAL_SLUG, phase)
        state = load_state(tmp_path, GOAL_SLUG)
        assert "scout" in state["phases"]

    def test_phase_fields_stored(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        metrics = PhaseMetrics(duration_s=15.5, token_spend=1000, tool_calls=8,
                               files_read=4, memory_hits=2)
        phase = _make_phase("scout", metrics=metrics)
        update_phase(tmp_path, GOAL_SLUG, phase)
        stored = load_state(tmp_path, GOAL_SLUG)["phases"]["scout"]
        assert stored["metrics"]["duration_s"] == 15.5
        assert stored["metrics"]["token_spend"] == 1000
        assert stored["metrics"]["tool_calls"] == 8
        assert stored["metrics"]["files_read"] == 4
        assert stored["metrics"]["memory_hits"] == 2

    def test_telemetry_updated(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        metrics = PhaseMetrics(duration_s=10.0, token_spend=500, tool_calls=5,
                               files_read=3, memory_hits=1)
        update_phase(tmp_path, GOAL_SLUG, _make_phase("scout", metrics=metrics))
        state = load_state(tmp_path, GOAL_SLUG)
        t = state["telemetry"]
        assert t["total_duration_s"] == 10.0
        assert t["total_token_spend"] == 500
        assert t["total_tool_calls"] == 5
        assert t["total_files_read"] == 3
        assert t["total_memory_hits"] == 1
        assert t["phases_completed"] == 1

    def test_telemetry_accumulates_across_phases(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        update_phase(tmp_path, GOAL_SLUG,
                     _make_phase("scout", metrics=PhaseMetrics(duration_s=5.0, token_spend=100, tool_calls=3)))
        update_phase(tmp_path, GOAL_SLUG,
                     _make_phase("analysis", metrics=PhaseMetrics(duration_s=8.0, token_spend=200, tool_calls=6)))
        t = load_state(tmp_path, GOAL_SLUG)["telemetry"]
        assert t["total_duration_s"] == 13.0
        assert t["total_token_spend"] == 300
        assert t["phases_completed"] == 2

    def test_telemetry_not_double_counted_on_repeat_update(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        metrics = PhaseMetrics(duration_s=5.0, token_spend=100)
        phase = _make_phase("scout", metrics=metrics)
        update_phase(tmp_path, GOAL_SLUG, phase)
        update_phase(tmp_path, GOAL_SLUG, phase)  # same phase again
        t = load_state(tmp_path, GOAL_SLUG)["telemetry"]
        assert t["total_duration_s"] == 5.0  # not 10.0
        assert t["total_token_spend"] == 100  # not 200

    def test_returns_updated_state(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        result = update_phase(tmp_path, GOAL_SLUG, _make_phase("scout"))
        assert isinstance(result, dict)
        assert "scout" in result["phases"]

    def test_raises_if_not_initialised(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="init_pipeline"):
            update_phase(tmp_path, GOAL_SLUG, _make_phase("scout"))

    def test_failed_gate_counts_phases_failed(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        update_phase(tmp_path, GOAL_SLUG, _make_phase("scout", gate_decision="fail"))
        t = load_state(tmp_path, GOAL_SLUG)["telemetry"]
        assert t["phases_failed"] == 1
        assert t["phases_completed"] == 0

    def test_escalate_gate_counts_phases_escalated(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        update_phase(tmp_path, GOAL_SLUG, _make_phase("scout", gate_decision="escalate"))
        t = load_state(tmp_path, GOAL_SLUG)["telemetry"]
        assert t["phases_escalated"] == 1

    def test_verify_result_stored(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        verify = PhaseVerifyResult(
            passed=True,
            errors=[],
            warnings=["minor drift"],
            normalize_fixes=["blocker_string_wrap"],
            gate_decision="proceed",
            gate_reason="all checks passed",
        )
        phase = PhaseEntry(
            phase="scout", status="done",
            verify_result=verify,
            metrics=PhaseMetrics(),
        )
        update_phase(tmp_path, GOAL_SLUG, phase)
        stored_vr = load_state(tmp_path, GOAL_SLUG)["phases"]["scout"]["verify_result"]
        assert stored_vr["passed"] is True
        assert stored_vr["warnings"] == ["minor drift"]
        assert stored_vr["normalize_fixes"] == ["blocker_string_wrap"]
        assert stored_vr["gate_decision"] == "proceed"

    def test_header_summary_stored(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        phase = PhaseEntry(
            phase="analysis", status="done",
            verify_result=PhaseVerifyResult(gate_decision="proceed"),
            metrics=PhaseMetrics(),
            header_summary={"has_ui": True, "confidence": 0.9, "traceability_count": 5},
        )
        update_phase(tmp_path, GOAL_SLUG, phase)
        stored = load_state(tmp_path, GOAL_SLUG)["phases"]["analysis"]["header_summary"]
        assert stored["has_ui"] is True
        assert stored["traceability_count"] == 5

    def test_atomic_write_no_tmp_leftover(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        update_phase(tmp_path, GOAL_SLUG, _make_phase("scout"))
        sp = state_path(tmp_path, GOAL_SLUG)
        tmp_file = sp.with_suffix(".tmp")
        assert not tmp_file.exists()


# ---------------------------------------------------------------------------
# finalize_pipeline
# ---------------------------------------------------------------------------

class TestFinalizePipeline:
    def test_sets_completed_status(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        finalize_pipeline(tmp_path, GOAL_SLUG, status="completed")
        assert load_state(tmp_path, GOAL_SLUG)["status"] == "completed"

    def test_sets_failed_status(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        finalize_pipeline(tmp_path, GOAL_SLUG, status="failed")
        assert load_state(tmp_path, GOAL_SLUG)["status"] == "failed"

    def test_preserves_phases(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        update_phase(tmp_path, GOAL_SLUG, _make_phase("scout"))
        finalize_pipeline(tmp_path, GOAL_SLUG, status="completed")
        state = load_state(tmp_path, GOAL_SLUG)
        assert "scout" in state["phases"]

    def test_returns_updated_state(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        result = finalize_pipeline(tmp_path, GOAL_SLUG)
        assert result["status"] == "completed"

    def test_raises_if_not_initialised(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="init_pipeline"):
            finalize_pipeline(tmp_path, GOAL_SLUG)


# ---------------------------------------------------------------------------
# load_state / load_last_phase_log
# ---------------------------------------------------------------------------

class TestLoadHelpers:
    def test_load_state_returns_none_if_missing(self, tmp_path):
        assert load_state(tmp_path, GOAL_SLUG) is None

    def test_load_state_reads_existing(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        state = load_state(tmp_path, GOAL_SLUG)
        assert state is not None
        assert state["goal_slug"] == GOAL_SLUG

    def test_load_last_phase_log_returns_none_if_missing(self, tmp_path):
        assert load_last_phase_log(tmp_path, GOAL_SLUG) is None

    def test_load_last_phase_log_returns_none_if_empty(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        assert load_last_phase_log(tmp_path, GOAL_SLUG) is None

    def test_load_last_phase_log_returns_last_entry(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        record_phase_log(tmp_path, GOAL_SLUG,
                         phase="scout", status="done", gate_decision="proceed",
                         task_id="t1", run_index=0)
        record_phase_log(tmp_path, GOAL_SLUG,
                         phase="analysis", status="done", gate_decision="proceed",
                         task_id="t2", run_index=0)
        last = load_last_phase_log(tmp_path, GOAL_SLUG)
        assert last["phase"] == "analysis"
        assert last["task_id"] == "t2"

    def test_load_last_phase_log_fields(self, tmp_path):
        init_pipeline(tmp_path, GOAL_SLUG)
        ts = "2026-06-01T09:00:00+00:00"
        record_phase_log(tmp_path, GOAL_SLUG,
                         phase="scout", status="partial", gate_decision="retry",
                         task_id="t-abc", run_index=3, timestamp=ts)
        last = load_last_phase_log(tmp_path, GOAL_SLUG)
        assert last["phase"] == "scout"
        assert last["status"] == "partial"
        assert last["gate_decision"] == "retry"
        assert last["task_id"] == "t-abc"
        assert last["run_index"] == 3
        assert last["timestamp"] == ts


# ---------------------------------------------------------------------------
# PhaseMetrics.from_trace
# ---------------------------------------------------------------------------

class TestPhaseMetricsFromTrace:
    def test_duration_extracted(self):
        trace = _make_trace(duration_seconds=42.7)
        m = PhaseMetrics.from_trace(trace)
        assert m.duration_s == 42.7

    def test_duration_rounded(self):
        trace = _make_trace(duration_seconds=3.14159265)
        m = PhaseMetrics.from_trace(trace)
        assert m.duration_s == 3.14

    def test_token_spend_sums_all_categories(self):
        turns = _make_turns(input_tokens=100, output_tokens=50, cache_read=20, cache_creation=10)
        trace = _make_trace(turns=turns)
        m = PhaseMetrics.from_trace(trace)
        assert m.token_spend == 180  # 100+50+20+10

    def test_token_spend_multi_turn(self):
        turns = [
            AssistantTurnTrace(turn_index=0, text_snippet="", has_thinking=False,
                               input_tokens=100, output_tokens=50),
            AssistantTurnTrace(turn_index=1, text_snippet="", has_thinking=False,
                               input_tokens=200, output_tokens=80),
        ]
        trace = _make_trace(turns=turns)
        m = PhaseMetrics.from_trace(trace)
        assert m.token_spend == 430  # (100+50) + (200+80)

    def test_tool_calls_from_trace(self):
        trace = _make_trace(total_tool_calls=12)
        m = PhaseMetrics.from_trace(trace)
        assert m.tool_calls == 12

    def test_files_read_from_trace(self):
        trace = _make_trace(read_tool_calls=7)
        m = PhaseMetrics.from_trace(trace)
        assert m.files_read == 7

    def test_memory_hits_from_memory_used(self):
        trace = _make_trace(memory_used=["feedback_a.md", "project_b.md", "user_c.md"])
        m = PhaseMetrics.from_trace(trace)
        assert m.memory_hits == 3

    def test_empty_trace(self):
        trace = _make_trace(duration_seconds=0.0, total_tool_calls=0,
                            read_tool_calls=0, memory_used=[])
        m = PhaseMetrics.from_trace(trace)
        assert m.duration_s == 0.0
        assert m.token_spend == 0
        assert m.tool_calls == 0
        assert m.files_read == 0
        assert m.memory_hits == 0


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

class TestPathHelpers:
    def test_pipeline_dir(self, tmp_path):
        d = pipeline_dir(tmp_path, "my-slug")
        assert d == tmp_path / ".cronos" / "pipeline" / "my-slug"

    def test_state_path(self, tmp_path):
        sp = state_path(tmp_path, "my-slug")
        assert sp == tmp_path / ".cronos" / "pipeline" / "my-slug" / PIPELINE_STATE_FILENAME

    def test_log_path(self, tmp_path):
        lp = log_path(tmp_path, "my-slug")
        assert lp == tmp_path / ".cronos" / "pipeline" / "my-slug" / PHASES_LOG_FILENAME


# ---------------------------------------------------------------------------
# Integration: full pipeline lifecycle
# ---------------------------------------------------------------------------

class TestPipelineLifecycle:
    def test_full_run(self, tmp_path):
        """Init → two phases → finalize → verify state is coherent."""
        init_pipeline(tmp_path, GOAL_SLUG, request_text="Add search feature")

        # Phase 1: scout
        trace1 = _make_trace(
            task_id="scout-task",
            run_index=0,
            duration_seconds=12.5,
            turns=_make_turns(100, 60, 0, 0),
            total_tool_calls=8,
            read_tool_calls=6,
            memory_used=["user_profile.md"],
        )
        m1 = PhaseMetrics.from_trace(trace1)
        phase1 = PhaseEntry(
            phase="scout",
            status="done",
            agent="pipeline-scout",
            task_id="scout-task",
            run_index=0,
            started_at="2026-01-01T10:00:00+00:00",
            completed_at="2026-01-01T10:00:12+00:00",
            artifact_path=f".cronos/pipeline/{GOAL_SLUG}/scout-report-{GOAL_SLUG}.md",
            verify_result=PhaseVerifyResult(passed=True, gate_decision="proceed",
                                            gate_reason="status=done"),
            metrics=m1,
        )
        update_phase(tmp_path, GOAL_SLUG, phase1)
        record_phase_log(tmp_path, GOAL_SLUG,
                         phase="scout", status="done", gate_decision="proceed",
                         task_id="scout-task", run_index=0)

        # Phase 2: analysis
        trace2 = _make_trace(
            task_id="analysis-task",
            run_index=0,
            duration_seconds=20.0,
            turns=_make_turns(200, 80, 0, 0),
            total_tool_calls=10,
            read_tool_calls=7,
            memory_used=["user_profile.md", "project_arch.md"],
        )
        m2 = PhaseMetrics.from_trace(trace2)
        phase2 = PhaseEntry(
            phase="analysis",
            status="done",
            agent="pipeline-analyst",
            task_id="analysis-task",
            run_index=0,
            verify_result=PhaseVerifyResult(passed=True, gate_decision="proceed"),
            metrics=m2,
            header_summary={"has_ui": False, "traceability_count": 4},
        )
        update_phase(tmp_path, GOAL_SLUG, phase2)
        record_phase_log(tmp_path, GOAL_SLUG,
                         phase="analysis", status="done", gate_decision="proceed",
                         task_id="analysis-task", run_index=0)

        # Finalize
        finalize_pipeline(tmp_path, GOAL_SLUG, status="completed")

        # Verify pipeline-state.json
        final = load_state(tmp_path, GOAL_SLUG)
        assert final["status"] == "completed"
        assert final["cc_version"] == CC_VERSION
        assert set(final["phases"].keys()) == {"scout", "analysis"}

        tel = final["telemetry"]
        assert tel["total_duration_s"] == 32.5  # 12.5 + 20.0
        assert tel["total_token_spend"] == (160 + 280)  # (100+60) + (200+80)
        assert tel["total_tool_calls"] == 18
        assert tel["total_files_read"] == 13
        assert tel["total_memory_hits"] == 3  # 1 + 2
        assert tel["phases_completed"] == 2

        # Verify phases-log.jsonl
        last = load_last_phase_log(tmp_path, GOAL_SLUG)
        assert last["phase"] == "analysis"
        assert last["gate_decision"] == "proceed"
