from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.trace_parser import (
    RunTrace,
    ToolCallTrace,
    _adopted_name_from_tool,
    _is_read_tool,
    _summarize_input,
    _summarize_output,
    extract_run_trace,
)
from app.trace_store import TraceStore

from .conftest import SPACE_ID

TASK_ID = "2025-01-01-0000-test-task"
_NOW = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
_LATER = datetime(2025, 1, 1, 12, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# _is_read_tool
# ---------------------------------------------------------------------------


def test_is_read_tool_named_tools():
    assert _is_read_tool("Read", "")
    assert _is_read_tool("Grep", "")
    assert _is_read_tool("Glob", "")
    assert _is_read_tool("WebFetch", "")
    assert _is_read_tool("WebSearch", "")


def test_is_read_tool_write_tools():
    assert not _is_read_tool("Write", "")
    assert not _is_read_tool("Edit", "")
    assert not _is_read_tool("Bash", json.dumps({"command": "rm -rf /"}))


def test_is_read_tool_bash_read_commands():
    assert _is_read_tool("Bash", json.dumps({"command": "cat file.txt"}))
    assert _is_read_tool("Bash", json.dumps({"command": "git log --oneline"}))
    assert _is_read_tool("Bash", json.dumps({"command": "git diff HEAD"}))
    assert _is_read_tool("Bash", json.dumps({"command": "ls -la"}))
    assert _is_read_tool("Bash", json.dumps({"command": "find . -name '*.py'"}))


def test_is_read_tool_bash_write_command():
    assert not _is_read_tool("Bash", json.dumps({"command": "echo 'hello' > file.txt"}))
    assert not _is_read_tool("Bash", json.dumps({"command": "npm install"}))


def test_is_read_tool_unknown():
    assert not _is_read_tool("UnknownTool", "")


# ---------------------------------------------------------------------------
# _summarize_input / _summarize_output
# ---------------------------------------------------------------------------


def test_summarize_input_string():
    result = _summarize_input("hello world")
    assert result == "hello world"


def test_summarize_input_dict():
    result = _summarize_input({"file_path": "test.py"})
    assert "file_path" in result
    assert "test.py" in result


def test_summarize_input_truncates():
    long_str = "x" * 600
    result = _summarize_input(long_str)
    assert len(result) <= 501
    assert result.endswith("…")


def test_summarize_output_string():
    result = _summarize_output("some output")
    assert result == "some output"


def test_summarize_output_none():
    assert _summarize_output(None) == ""


def test_summarize_output_list_of_text_blocks():
    content = [{"type": "text", "text": "line one"}, {"type": "text", "text": "line two"}]
    result = _summarize_output(content)
    assert "line one" in result
    assert "line two" in result


def test_summarize_output_truncates():
    long_str = "y" * 1200
    result = _summarize_output(long_str)
    assert len(result) <= 1001
    assert result.endswith("…")


# ---------------------------------------------------------------------------
# extract_run_trace helpers
# ---------------------------------------------------------------------------


def _make_assistant_event(
    tool_uses: list[dict] | None = None,
    text: str = "",
    input_tokens: int = 100,
    output_tokens: int = 50,
    model: str = "claude-sonnet-4-6",
) -> dict:
    content = []
    if text:
        content.append({"type": "text", "text": text})
    for tu in (tool_uses or []):
        content.append(tu)
    return {
        "type": "assistant",
        "message": {
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            "content": content,
        },
    }


def _tool_use_block(name: str, tool_id: str, inp: dict) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": inp}


def _tool_result_event(tool_id: str, content: str = "ok", is_error: bool = False) -> dict:
    return {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "is_error": is_error,
                    "content": content,
                }
            ]
        },
    }


def _base_kwargs() -> dict:
    return dict(
        task_id=TASK_ID,
        space_id=SPACE_ID,
        run_index=0,
        model="default",
        mode="auto",
        started_at=_NOW,
        ended_at=_LATER,
        exit_reason="DONE",
        session_id=None,
        had_crash=False,
    )


# ---------------------------------------------------------------------------
# extract_run_trace — core behaviour
# ---------------------------------------------------------------------------


def test_extract_run_trace_empty():
    trace = extract_run_trace([], **_base_kwargs())
    assert trace.task_id == TASK_ID
    assert trace.space_id == SPACE_ID
    assert trace.total_tool_calls == 0
    assert trace.exploration_ratio == 0.0
    assert trace.turns == []


def test_extract_run_trace_duration():
    trace = extract_run_trace([], **_base_kwargs())
    assert trace.duration_seconds == pytest.approx(60.0)


def test_extract_run_trace_captures_text():
    events = [_make_assistant_event(text="I will now read the file.")]
    trace = extract_run_trace(events, **_base_kwargs())
    assert len(trace.turns) == 1
    assert "I will now read the file." in trace.turns[0].text_snippet


def test_extract_run_trace_captures_model():
    events = [_make_assistant_event(model="claude-opus-4-7")]
    trace = extract_run_trace(events, **_base_kwargs())
    assert trace.real_model == "claude-opus-4-7"


def test_extract_run_trace_tool_calls_counted():
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Read", "tu-1", {"file_path": "a.py"}),
            _tool_use_block("Write", "tu-2", {"file_path": "b.py", "content": "x"}),
        ]),
    ]
    trace = extract_run_trace(events, **_base_kwargs())
    assert trace.total_tool_calls == 2
    assert trace.read_tool_calls == 1
    assert trace.write_tool_calls == 1


def test_extract_run_trace_unique_tools():
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Read", "tu-1", {}),
            _tool_use_block("Read", "tu-2", {}),
            _tool_use_block("Write", "tu-3", {}),
        ]),
    ]
    trace = extract_run_trace(events, **_base_kwargs())
    assert set(trace.unique_tools) == {"Read", "Write"}
    assert trace.unique_tools.index("Read") < trace.unique_tools.index("Write")


def test_extract_run_trace_error_tool_calls():
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Bash", "tu-1", {"command": "bad cmd"}),
        ]),
        _tool_result_event("tu-1", "Permission denied", is_error=True),
    ]
    trace = extract_run_trace(events, **_base_kwargs())
    assert trace.error_tool_calls == 1
    assert trace.tool_calls[0].is_error is True


def test_extract_run_trace_output_summary_captured():
    events = [
        _make_assistant_event(tool_uses=[_tool_use_block("Read", "tu-1", {})]),
        _tool_result_event("tu-1", "file contents here"),
    ]
    trace = extract_run_trace(events, **_base_kwargs())
    assert "file contents here" in trace.tool_calls[0].output_summary


# ---------------------------------------------------------------------------
# exploration_ratio
# ---------------------------------------------------------------------------


def test_extract_run_trace_exploration_ratio_all_reads():
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Read", "tu-1", {}),
            _tool_use_block("Read", "tu-2", {}),
        ]),
    ]
    trace = extract_run_trace(events, **_base_kwargs())
    assert trace.exploration_ratio == pytest.approx(1.0)


def test_extract_run_trace_exploration_ratio_mixed():
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Read", "tu-1", {}),
            _tool_use_block("Write", "tu-2", {}),
        ]),
    ]
    trace = extract_run_trace(events, **_base_kwargs())
    assert trace.exploration_ratio == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# error_recovery_count
# ---------------------------------------------------------------------------


def test_extract_run_trace_error_recovery():
    # Error on Bash → success on Bash within 3 steps
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Bash", "tu-1", {"command": "bad"}),
        ]),
        _tool_result_event("tu-1", "error!", is_error=True),
        _make_assistant_event(tool_uses=[
            _tool_use_block("Bash", "tu-2", {"command": "cat file.txt"}),
        ]),
        _tool_result_event("tu-2", "content"),
    ]
    trace = extract_run_trace(events, **_base_kwargs())
    assert trace.error_recovery_count == 1


def test_extract_run_trace_no_recovery_different_tool():
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Bash", "tu-1", {"command": "bad"}),
        ]),
        _tool_result_event("tu-1", "error!", is_error=True),
        _make_assistant_event(tool_uses=[
            _tool_use_block("Read", "tu-2", {"file_path": "x.py"}),
        ]),
        _tool_result_event("tu-2", "ok"),
    ]
    trace = extract_run_trace(events, **_base_kwargs())
    assert trace.error_recovery_count == 0


# ---------------------------------------------------------------------------
# backtrack_count
# ---------------------------------------------------------------------------


def test_extract_run_trace_backtrack():
    # Write file.py → Read file.py immediately after
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Write", "tu-1", {"file_path": "file.py", "content": "x"}),
        ]),
        _tool_result_event("tu-1", "written"),
        _make_assistant_event(tool_uses=[
            _tool_use_block("Read", "tu-2", {"file_path": "file.py"}),
        ]),
        _tool_result_event("tu-2", "x"),
    ]
    trace = extract_run_trace(events, **_base_kwargs())
    assert trace.backtrack_count == 1


def test_extract_run_trace_no_backtrack_different_file():
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Write", "tu-1", {"file_path": "a.py", "content": "x"}),
        ]),
        _tool_result_event("tu-1", "written"),
        _make_assistant_event(tool_uses=[
            _tool_use_block("Read", "tu-2", {"file_path": "b.py"}),
        ]),
        _tool_result_event("tu-2", "y"),
    ]
    trace = extract_run_trace(events, **_base_kwargs())
    assert trace.backtrack_count == 0


# ---------------------------------------------------------------------------
# session_id propagation
# ---------------------------------------------------------------------------


def test_extract_run_trace_session_from_result():
    events = [
        {"type": "result", "session_id": "sess-abc", "usage": {}},
    ]
    kwargs = _base_kwargs()
    trace = extract_run_trace(events, **kwargs)
    assert trace.session_id == "sess-abc"


def test_extract_run_trace_session_from_system_init():
    events = [
        {"type": "system", "subtype": "init", "session_id": "init-sess"},
    ]
    trace = extract_run_trace(events, **_base_kwargs())
    assert trace.session_id == "init-sess"


# ---------------------------------------------------------------------------
# memory_hit_rate
# ---------------------------------------------------------------------------


def test_memory_hit_rate_no_memory():
    trace = extract_run_trace([], **_base_kwargs())
    assert trace.memory_hit_rate == 0.0


def test_memory_hit_rate_none_injected():
    trace = extract_run_trace([], **_base_kwargs(), memory_injected=None)
    assert trace.memory_hit_rate == 0.0


def test_memory_hit_rate_all_used(tmp_path):
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    for name in ("a.md", "b.md"):
        (mem_dir / name).write_text("content")
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Read", "tu-1", {"file_path": str(mem_dir / "a.md")}),
            _tool_use_block("Read", "tu-2", {"file_path": str(mem_dir / "b.md")}),
        ]),
    ]
    trace = extract_run_trace(
        events, **_base_kwargs(), memory_injected=["a.md", "b.md"]
    )
    assert trace.memory_hit_rate == pytest.approx(1.0)


def test_memory_hit_rate_partial(tmp_path):
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    (mem_dir / "a.md").write_text("x")
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Read", "tu-1", {"file_path": str(mem_dir / "a.md")}),
        ]),
    ]
    trace = extract_run_trace(
        events, **_base_kwargs(), memory_injected=["a.md", "b.md", "c.md", "d.md"]
    )
    assert trace.memory_hit_rate == pytest.approx(0.25)


def test_memory_hit_rate_clamped_to_one(tmp_path):
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    for name in ("a.md", "b.md"):
        (mem_dir / name).write_text("x")
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Read", "tu-1", {"file_path": str(mem_dir / "a.md")}),
            _tool_use_block("Read", "tu-2", {"file_path": str(mem_dir / "b.md")}),
        ]),
    ]
    # Only one file injected but two used — rate must be clamped to 1.0
    trace = extract_run_trace(
        events, **_base_kwargs(), memory_injected=["a.md"]
    )
    assert trace.memory_hit_rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# TraceStore
# ---------------------------------------------------------------------------


def _make_trace(run_index: int = 0) -> RunTrace:
    return RunTrace(
        task_id=TASK_ID,
        space_id=SPACE_ID,
        run_index=run_index,
        session_id=None,
        model="default",
        mode="auto",
        started_at=_NOW,
        ended_at=_LATER,
        duration_seconds=60.0,
        exit_reason="DONE",
    )


async def test_trace_store_save_and_load(tmp_spaces_dir):
    store = TraceStore(tmp_spaces_dir)
    trace = _make_trace(run_index=0)
    await store.save_run(SPACE_ID, TASK_ID, trace)
    loaded = await store.load_run(SPACE_ID, TASK_ID, 0)
    assert loaded is not None
    assert loaded.run_index == 0
    assert loaded.task_id == TASK_ID


async def test_trace_store_load_nonexistent(tmp_spaces_dir):
    store = TraceStore(tmp_spaces_dir)
    result = await store.load_run(SPACE_ID, "no-task", 0)
    assert result is None


async def test_trace_store_load_latest(tmp_spaces_dir):
    store = TraceStore(tmp_spaces_dir)
    await store.save_run(SPACE_ID, TASK_ID, _make_trace(0))
    await store.save_run(SPACE_ID, TASK_ID, _make_trace(1))
    latest = await store.load_latest(SPACE_ID, TASK_ID)
    assert latest is not None
    assert latest.run_index == 1


async def test_trace_store_load_latest_no_traces(tmp_spaces_dir):
    store = TraceStore(tmp_spaces_dir)
    result = await store.load_latest(SPACE_ID, "no-task")
    assert result is None


async def test_trace_store_list_runs(tmp_spaces_dir):
    store = TraceStore(tmp_spaces_dir)
    await store.save_run(SPACE_ID, TASK_ID, _make_trace(0))
    await store.save_run(SPACE_ID, TASK_ID, _make_trace(1))
    runs = await store.list_runs(SPACE_ID, TASK_ID)
    assert len(runs) == 2
    assert runs[0].run_index == 0
    assert runs[1].run_index == 1


async def test_trace_store_list_runs_empty(tmp_spaces_dir):
    store = TraceStore(tmp_spaces_dir)
    runs = await store.list_runs(SPACE_ID, "no-task")
    assert runs == []


async def test_trace_store_count_runs(tmp_spaces_dir):
    store = TraceStore(tmp_spaces_dir)
    assert await store.count_runs(SPACE_ID, TASK_ID) == 0
    await store.save_run(SPACE_ID, TASK_ID, _make_trace(0))
    assert await store.count_runs(SPACE_ID, TASK_ID) == 1
    await store.save_run(SPACE_ID, TASK_ID, _make_trace(1))
    assert await store.count_runs(SPACE_ID, TASK_ID) == 2


async def test_trace_store_delete_task_traces(tmp_spaces_dir):
    store = TraceStore(tmp_spaces_dir)
    await store.save_run(SPACE_ID, TASK_ID, _make_trace(0))
    await store.delete_task_traces(SPACE_ID, TASK_ID)
    assert await store.count_runs(SPACE_ID, TASK_ID) == 0


async def test_trace_store_delete_nonexistent_is_noop(tmp_spaces_dir):
    store = TraceStore(tmp_spaces_dir)
    await store.delete_task_traces(SPACE_ID, "never-existed")


# ---------------------------------------------------------------------------
# _adopted_name_from_tool
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, inp, expected",
    [
        pytest.param("Skill", {"skill": "frontend-design"}, "frontend-design",
                     id="skill-returns-skill-name"),
        pytest.param("Agent", {"subagent_type": "reviewer"}, "reviewer",
                     id="agent-returns-subagent-type"),
        pytest.param("Bash", {"command": "ls -la"}, None,
                     id="builtin-tool-returns-none"),
        pytest.param("Skill", "not-a-dict", None,
                     id="non-dict-input-returns-none"),
        pytest.param("Skill", {"skill": ""}, None,
                     id="empty-skill-value-returns-none"),
        pytest.param("Agent", {}, None,
                     id="agent-missing-subagent-type-returns-none"),
    ],
)
def test_adopted_name_from_tool(name, inp, expected):
    assert _adopted_name_from_tool(name, inp) == expected


# ---------------------------------------------------------------------------
# extract_run_trace — adopted_tool tagging
# ---------------------------------------------------------------------------

_ADOPTED_INDEX = {
    "frontend-design": ("frontend-design", "skill"),
    "reviewer": ("reviewer", "agent"),
}


def test_extract_run_trace_skill_call_tagged_with_adopted_id():
    # Arrange: a Skill tool call whose skill name is in the adopted index.
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Skill", "tu-1", {"skill": "frontend-design"}),
        ]),
    ]

    # Act
    trace = extract_run_trace(
        events, adopted_index=_ADOPTED_INDEX, **_base_kwargs()
    )

    # Assert
    tc = trace.tool_calls[0]
    assert tc.adopted_tool_id == "frontend-design"
    assert tc.adopted_tool_kind == "skill"


def test_extract_run_trace_agent_call_tagged_with_adopted_id():
    # Arrange: an Agent tool call whose subagent_type is in the adopted index.
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Agent", "tu-1", {"subagent_type": "reviewer"}),
        ]),
    ]

    # Act
    trace = extract_run_trace(
        events, adopted_index=_ADOPTED_INDEX, **_base_kwargs()
    )

    # Assert
    tc = trace.tool_calls[0]
    assert tc.adopted_tool_id == "reviewer"
    assert tc.adopted_tool_kind == "agent"


def test_extract_run_trace_builtin_tool_not_tagged():
    # Arrange: built-in tools should never be tagged even with an index present.
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Read", "tu-1", {"file_path": "a.py"}),
            _tool_use_block("Edit", "tu-2", {"file_path": "b.py"}),
            _tool_use_block("Bash", "tu-3", {"command": "ls"}),
        ]),
    ]

    # Act
    trace = extract_run_trace(
        events, adopted_index=_ADOPTED_INDEX, **_base_kwargs()
    )

    # Assert: every built-in call has both adopted fields unset.
    for tc in trace.tool_calls:
        assert tc.adopted_tool_id is None
        assert tc.adopted_tool_kind is None


def test_extract_run_trace_no_adopted_index_leaves_fields_none():
    # Arrange: a Skill call but no adopted_index passed (default None).
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Skill", "tu-1", {"skill": "frontend-design"}),
        ]),
    ]

    # Act
    trace = extract_run_trace(events, **_base_kwargs())

    # Assert
    tc = trace.tool_calls[0]
    assert tc.adopted_tool_id is None
    assert tc.adopted_tool_kind is None


def test_extract_run_trace_skill_not_in_index_leaves_fields_none():
    # Arrange: a Skill call whose name is NOT in the adopted index.
    events = [
        _make_assistant_event(tool_uses=[
            _tool_use_block("Skill", "tu-1", {"skill": "unknown-skill"}),
        ]),
    ]

    # Act
    trace = extract_run_trace(
        events, adopted_index=_ADOPTED_INDEX, **_base_kwargs()
    )

    # Assert
    tc = trace.tool_calls[0]
    assert tc.adopted_tool_id is None
    assert tc.adopted_tool_kind is None


# ---------------------------------------------------------------------------
# parent_run_id
# ---------------------------------------------------------------------------


def test_parent_run_id_defaults_to_none():
    """parent_run_id must default to None when not passed to extract_run_trace."""
    trace = extract_run_trace([], **_base_kwargs())
    assert trace.parent_run_id is None


def test_parent_run_id_populated_when_passed_as_kwarg():
    """parent_run_id must be set on RunTrace when passed as a keyword argument."""
    trace = extract_run_trace([], **_base_kwargs(), parent_run_id="harness-run-123")
    assert trace.parent_run_id == "harness-run-123"


def test_parent_run_id_none_serializes_correctly():
    """parent_run_id=None must round-trip through JSON serialization."""
    trace = extract_run_trace([], **_base_kwargs())
    assert trace.parent_run_id is None
    data = json.loads(trace.model_dump_json())
    assert data["parent_run_id"] is None


def test_parent_run_id_value_serializes_correctly():
    """parent_run_id with a value must round-trip through JSON serialization."""
    trace = extract_run_trace([], **_base_kwargs(), parent_run_id="run-abc")
    data = json.loads(trace.model_dump_json())
    assert data["parent_run_id"] == "run-abc"
    # Deserialize back into a RunTrace
    restored = RunTrace.model_validate(data)
    assert restored.parent_run_id == "run-abc"


def test_parent_run_id_is_keyword_only():
    """parent_run_id must be keyword-only — positional invocation must raise TypeError."""
    import inspect
    sig = inspect.signature(extract_run_trace)
    param = sig.parameters.get("parent_run_id")
    assert param is not None, "parent_run_id parameter missing from extract_run_trace"
    assert param.kind == inspect.Parameter.KEYWORD_ONLY, (
        "parent_run_id must be a keyword-only parameter"
    )


def test_existing_callers_unaffected():
    """Existing call patterns without parent_run_id must continue to work unchanged."""
    # Simulate caller patterns used in worker.py / test_arc5_e2e.py
    trace = extract_run_trace([], **_base_kwargs())
    assert trace.parent_run_id is None

    trace2 = extract_run_trace(
        [],
        task_id=TASK_ID,
        space_id=SPACE_ID,
        run_index=0,
        model="default",
        mode="auto",
        started_at=_NOW,
        ended_at=_LATER,
        exit_reason="DONE",
        session_id=None,
        had_crash=False,
    )
    assert trace2.parent_run_id is None
