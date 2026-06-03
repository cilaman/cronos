"""Tests for adopted-tool statistics: AdoptedToolRunStats and compute_adopted_tool_uses."""
from __future__ import annotations

import pytest

from app.stats import AdoptedToolRunStats, RunStats, compute_adopted_tool_uses
from datetime import UTC, datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeTC:
    """Minimal stand-in for ToolCallTrace."""

    def __init__(
        self,
        adopted_tool_id: str | None = None,
        adopted_tool_kind: str | None = None,
        is_error: bool = False,
    ) -> None:
        self.adopted_tool_id = adopted_tool_id
        self.adopted_tool_kind = adopted_tool_kind
        self.is_error = is_error


def _make_run(
    adopted_tool_uses: dict | None = None,
    exit_reason: str = "DONE",
) -> RunStats:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    return RunStats(
        run_index=0,
        started_at=now,
        ended_at=now,
        duration_seconds=60.0,
        model="default",
        mode="auto",
        exit_reason=exit_reason,
        adopted_tool_uses=adopted_tool_uses or {},
    )


# ---------------------------------------------------------------------------
# compute_adopted_tool_uses — basic tallying
# ---------------------------------------------------------------------------


def test_compute_adopted_empty():
    result = compute_adopted_tool_uses([], "DONE")
    assert result == {}


def test_compute_adopted_no_adopted_calls():
    tc = _FakeTC(adopted_tool_id=None)
    result = compute_adopted_tool_uses([tc], "DONE")
    assert result == {}


def test_compute_adopted_single_clean_call():
    tc = _FakeTC(adopted_tool_id="my-agent", adopted_tool_kind="agent")
    result = compute_adopted_tool_uses([tc], "DONE")
    assert "my-agent" in result
    entry = result["my-agent"]
    assert entry.calls == 1
    assert entry.errors == 0
    assert entry.kind == "agent"
    assert entry.human_rescue is False


def test_compute_adopted_error_call():
    tc = _FakeTC(adopted_tool_id="my-agent", adopted_tool_kind="agent", is_error=True)
    result = compute_adopted_tool_uses([tc], "DONE")
    entry = result["my-agent"]
    assert entry.calls == 1
    assert entry.errors == 1


def test_compute_adopted_mixed_calls():
    tcs = [
        _FakeTC(adopted_tool_id="my-agent", adopted_tool_kind="agent"),
        _FakeTC(adopted_tool_id="my-agent", adopted_tool_kind="agent"),
        _FakeTC(adopted_tool_id="my-agent", adopted_tool_kind="agent", is_error=True),
    ]
    result = compute_adopted_tool_uses(tcs, "DONE")
    entry = result["my-agent"]
    assert entry.calls == 3
    assert entry.errors == 1


def test_compute_adopted_multiple_tools():
    tcs = [
        _FakeTC(adopted_tool_id="agent-a", adopted_tool_kind="agent"),
        _FakeTC(adopted_tool_id="skill-b", adopted_tool_kind="skill"),
        _FakeTC(adopted_tool_id="agent-a", adopted_tool_kind="agent", is_error=True),
    ]
    result = compute_adopted_tool_uses(tcs, "DONE")
    assert result["agent-a"].calls == 2
    assert result["agent-a"].errors == 1
    assert result["skill-b"].calls == 1
    assert result["skill-b"].errors == 0


def test_compute_adopted_kind_from_first_occurrence():
    tcs = [
        _FakeTC(adopted_tool_id="my-tool", adopted_tool_kind="skill"),
        _FakeTC(adopted_tool_id="my-tool", adopted_tool_kind="skill"),
    ]
    result = compute_adopted_tool_uses(tcs, "DONE")
    assert result["my-tool"].kind == "skill"


# ---------------------------------------------------------------------------
# compute_adopted_tool_uses — human_rescue heuristic
# ---------------------------------------------------------------------------


def test_human_rescue_not_set_on_done():
    tc = _FakeTC(adopted_tool_id="my-agent", adopted_tool_kind="agent")
    result = compute_adopted_tool_uses([tc], "DONE")
    assert result["my-agent"].human_rescue is False


def test_human_rescue_set_when_wait_and_last_call_was_adopted():
    tcs = [
        _FakeTC(adopted_tool_id="my-agent", adopted_tool_kind="agent"),
    ]
    result = compute_adopted_tool_uses(tcs, "WAIT")
    assert result["my-agent"].human_rescue is True


def test_human_rescue_not_set_when_last_non_error_is_not_adopted():
    tcs = [
        _FakeTC(adopted_tool_id="my-agent", adopted_tool_kind="agent"),
        _FakeTC(adopted_tool_id=None),  # last non-error is built-in
    ]
    result = compute_adopted_tool_uses(tcs, "WAIT")
    assert result["my-agent"].human_rescue is False


def test_human_rescue_skips_error_calls_at_end():
    tcs = [
        _FakeTC(adopted_tool_id="my-agent", adopted_tool_kind="agent"),
        _FakeTC(adopted_tool_id="my-agent", adopted_tool_kind="agent", is_error=True),
    ]
    result = compute_adopted_tool_uses(tcs, "WAIT")
    # Last non-error call is the first one (adopted), so rescue is True
    assert result["my-agent"].human_rescue is True


def test_human_rescue_only_set_for_last_non_error_adopted_tool():
    tcs = [
        _FakeTC(adopted_tool_id="agent-a", adopted_tool_kind="agent"),
        _FakeTC(adopted_tool_id="agent-b", adopted_tool_kind="agent"),
    ]
    result = compute_adopted_tool_uses(tcs, "WAIT")
    assert result["agent-a"].human_rescue is False
    assert result["agent-b"].human_rescue is True  # last non-error call


def test_human_rescue_not_set_for_other_exit_reasons():
    for reason in ("DONE", "BLOCKED", "STOPPED", "CRASHED"):
        tc = _FakeTC(adopted_tool_id="my-agent", adopted_tool_kind="agent")
        result = compute_adopted_tool_uses([tc], reason)
        assert result["my-agent"].human_rescue is False, f"human_rescue should be False for {reason}"


# ---------------------------------------------------------------------------
# RunStats — adopted_tool_uses field
# ---------------------------------------------------------------------------


def test_run_stats_default_adopted_tool_uses():
    run = _make_run()
    assert run.adopted_tool_uses == {}


def test_run_stats_stores_adopted_tool_uses():
    entry = AdoptedToolRunStats(calls=3, errors=1, kind="agent", human_rescue=False)
    run = _make_run(adopted_tool_uses={"my-agent": entry})
    assert run.adopted_tool_uses["my-agent"].calls == 3
    assert run.adopted_tool_uses["my-agent"].errors == 1


def test_run_stats_roundtrip_via_model_dump():
    entry = AdoptedToolRunStats(calls=2, errors=0, kind="skill", human_rescue=True)
    run = _make_run(adopted_tool_uses={"my-skill": entry})
    data = run.model_dump(mode="json")
    restored = RunStats.model_validate(data)
    assert restored.adopted_tool_uses["my-skill"].calls == 2
    assert restored.adopted_tool_uses["my-skill"].kind == "skill"
    assert restored.adopted_tool_uses["my-skill"].human_rescue is True
