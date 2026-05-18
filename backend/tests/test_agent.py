from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.agent import (
    STATUS_CONTRACT,
    Status,
    _extract_assistant_text,
    _upgrade_instructions,
    build_prompt,
    parse_status,
    run_agent,
    space_dir_for,
    workspace_for,
)
from app.models import Task, TaskState


# ---------------------------------------------------------------------------
# parse_status
# ---------------------------------------------------------------------------


def test_parse_status_done():
    status, ctx = parse_status("All done.\n\nSTATUS: DONE")
    assert status == Status.DONE
    assert ctx == "All done."


def test_parse_status_wait():
    status, ctx = parse_status("What is your preference?\n\nSTATUS: WAIT")
    assert status == Status.WAIT
    assert ctx == "What is your preference?"


def test_parse_status_blocked():
    status, ctx = parse_status("Cannot proceed without creds.\n\nSTATUS: BLOCKED")
    assert status == Status.BLOCKED
    assert ctx == "Cannot proceed without creds."


def test_parse_status_trailing_whitespace():
    status, ctx = parse_status("Done.\nSTATUS: DONE   ")
    assert status == Status.DONE


def test_parse_status_leading_whitespace_on_marker():
    status, ctx = parse_status("Done.\n  STATUS: DONE")
    assert status == Status.DONE


def test_parse_status_no_marker():
    status, ctx = parse_status("I finished everything.")
    assert status is None
    assert ctx is None


def test_parse_status_empty_string():
    status, ctx = parse_status("")
    assert status is None
    assert ctx is None


def test_parse_status_whitespace_only():
    status, ctx = parse_status("   \n\n  ")
    assert status is None
    assert ctx is None


def test_parse_status_uses_last_marker():
    text = "STATUS: WAIT\nMore text.\nSTATUS: DONE"
    status, ctx = parse_status(text)
    assert status == Status.DONE


def test_parse_status_context_skips_blank_lines():
    text = "The answer is 42.\n\n\nSTATUS: DONE"
    status, ctx = parse_status(text)
    assert status == Status.DONE
    assert ctx == "The answer is 42."


def test_parse_status_no_context_line():
    status, ctx = parse_status("STATUS: DONE")
    assert status == Status.DONE
    assert ctx is None


# ---------------------------------------------------------------------------
# space_dir_for
# ---------------------------------------------------------------------------


def test_space_dir_for_default():
    path = space_dir_for("my-space")
    assert path.name == "my-space"
    assert "spaces" in path.parts


def test_space_dir_for_uses_data_dir_env(tmp_path):
    with patch.dict(os.environ, {"CRONOS_DATA_DIR": str(tmp_path)}):
        from importlib import reload
        import app.agent as agent_module
        reload(agent_module)
        path = agent_module.space_dir_for("test-space")
        assert path == tmp_path / "spaces" / "test-space"
        reload(agent_module)


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


def _make_task(*, session_id: str | None = None) -> Task:
    now = datetime.now(tz=timezone.utc)
    return Task(
        id="task-abc",
        space_id="space-xyz",
        title="Write tests",
        state=TaskState.ACTIVE,
        created_at=now,
        updated_at=now,
        claude_session_id=session_id,
        brief="Add unit tests for agent module.",
    )


def test_build_prompt_fresh_task_no_message():
    task = _make_task()
    prompt = build_prompt(task, None)
    assert "task-abc" in prompt
    assert "Write tests" in prompt
    assert "Add unit tests" in prompt
    assert "Message" not in prompt


def test_build_prompt_fresh_task_with_message():
    task = _make_task()
    prompt = build_prompt(task, "Please start with parse_status.")
    assert "task-abc" in prompt
    assert "Message" in prompt
    assert "Please start with parse_status." in prompt


def test_build_prompt_resume_with_message():
    task = _make_task(session_id="sess-123")
    prompt = build_prompt(task, "Continue where you left off.")
    assert prompt == "Continue where you left off."


def test_build_prompt_resume_no_message():
    task = _make_task(session_id="sess-123")
    prompt = build_prompt(task, None)
    assert "task-abc" in prompt
    assert "Write tests" in prompt


def test_build_prompt_includes_status_contract_reminder():
    task = _make_task()
    prompt = build_prompt(task, None)
    assert "STATUS contract" in prompt


# ---------------------------------------------------------------------------
# _upgrade_instructions
# ---------------------------------------------------------------------------


def test_upgrade_instructions_no_url():
    with patch.dict(os.environ, {"UPGRADE_WEBHOOK_URL": ""}, clear=False):
        import importlib
        import app.agent as agent_module
        importlib.reload(agent_module)
        result = agent_module._upgrade_instructions()
        assert "not set" in result
        importlib.reload(agent_module)


def test_upgrade_instructions_with_url():
    with patch.dict(
        os.environ,
        {"UPGRADE_WEBHOOK_URL": "http://localhost:9137/upgrade", "UPGRADE_WEBHOOK_SECRET": ""},
        clear=False,
    ):
        import importlib
        import app.agent as agent_module
        importlib.reload(agent_module)
        result = agent_module._upgrade_instructions()
        assert "http://localhost:9137/upgrade" in result
        assert "curl" in result
        importlib.reload(agent_module)


def test_upgrade_instructions_with_secret():
    with patch.dict(
        os.environ,
        {
            "UPGRADE_WEBHOOK_URL": "http://localhost:9137/upgrade",
            "UPGRADE_WEBHOOK_SECRET": "my-secret",
        },
        clear=False,
    ):
        import importlib
        import app.agent as agent_module
        importlib.reload(agent_module)
        result = agent_module._upgrade_instructions()
        assert "my-secret" in result
        importlib.reload(agent_module)


# ---------------------------------------------------------------------------
# _extract_assistant_text
# ---------------------------------------------------------------------------


def test_extract_assistant_text_from_valid_event():
    event = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "Hello world"},
            ]
        },
    }
    result = _extract_assistant_text(event)
    assert result == "Hello world"


def test_extract_assistant_text_multiple_blocks():
    event = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "Part one"},
                {"type": "tool_use", "name": "Bash", "id": "t1"},
                {"type": "text", "text": " part two"},
            ]
        },
    }
    result = _extract_assistant_text(event)
    assert result == "Part one part two"


def test_extract_assistant_text_wrong_type():
    event = {"type": "user", "message": {"content": [{"type": "text", "text": "hi"}]}}
    result = _extract_assistant_text(event)
    assert result is None


def test_extract_assistant_text_not_dict():
    assert _extract_assistant_text("not a dict") is None  # type: ignore[arg-type]


def test_extract_assistant_text_no_content():
    event = {"type": "assistant", "message": {"content": []}}
    assert _extract_assistant_text(event) is None


def test_extract_assistant_text_no_message():
    event = {"type": "assistant"}
    assert _extract_assistant_text(event) is None


def test_extract_assistant_text_content_not_list():
    event = {"type": "assistant", "message": {"content": "raw string"}}
    assert _extract_assistant_text(event) is None


# ---------------------------------------------------------------------------
# workspace_for (no-git path)
# ---------------------------------------------------------------------------


async def test_workspace_for_no_space_creates_dir(tmp_path):
    import app.agent as agent_module
    original = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path
    try:
        task = _make_task()
        path = await workspace_for(task, space=None)
        assert path.exists()
        assert path.is_dir()
        assert "task-abc" in str(path)
    finally:
        agent_module.DATA_DIR = original


async def test_workspace_for_space_no_git_url_creates_dir(tmp_path):
    from app.models import Space
    import app.agent as agent_module
    original = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path
    try:
        task = _make_task()
        now = datetime.now(tz=timezone.utc)
        space = Space(
            id="space-xyz",
            name="Test",
            color="#123456",
            created_at=now,
            updated_at=now,
            git_repo_url=None,
            git_branch=None,
        )
        path = await workspace_for(task, space=space)
        assert path.exists()
    finally:
        agent_module.DATA_DIR = original


# ---------------------------------------------------------------------------
# STATUS_CONTRACT content
# ---------------------------------------------------------------------------


def test_status_contract_includes_plan_mode_wait_rule():
    """Plan-mode rule: end plan summary with STATUS: WAIT and a question."""
    # The plan-mode guidance must be present so the agent's system prompt
    # tells it to ask for approval after presenting a plan.
    assert "plan mode" in STATUS_CONTRACT.lower()
    assert "STATUS: WAIT" in STATUS_CONTRACT
    # The rule should explicitly tell the agent not to wait for the user to
    # ask before emitting the marker.
    contract_lower = STATUS_CONTRACT.lower()
    assert "plan" in contract_lower and "wait" in contract_lower
    # Sanity: existing rules still present.
    assert "STATUS: DONE" in STATUS_CONTRACT
    assert "STATUS: BLOCKED" in STATUS_CONTRACT


def test_status_contract_plan_rule_mentions_question_after_plan():
    """Plan-mode guidance should reference asking a question right after the plan."""
    # The exact phrasing from the contract: "emit STATUS: WAIT immediately
    # after the plan" (or similar). We check that the rule is anchored to
    # plan presentation.
    lowered = STATUS_CONTRACT.lower()
    assert "plan" in lowered
    # Either "immediately" or "approval" or "shall i implement" should appear
    # near the plan-mode guidance to make the rule actionable.
    plan_section_present = (
        "immediately" in lowered
        or "approval" in lowered
        or "shall i implement" in lowered
    )
    assert plan_section_present, (
        "Plan-mode rule should give the agent a concrete cue for when to "
        "emit STATUS: WAIT"
    )


# ---------------------------------------------------------------------------
# _upgrade_instructions: DONE-before-curl ordering
# ---------------------------------------------------------------------------


def test_upgrade_instructions_tells_agent_done_before_curl():
    """The instructions must place STATUS: DONE BEFORE the curl call.

    Previously the agent was told to fire the webhook then write DONE; this
    caused the SIGKILL from the container restart to land before DONE was
    flushed, so the run was misclassified as crashed.
    """
    with patch.dict(
        os.environ,
        {"UPGRADE_WEBHOOK_URL": "http://localhost:9137/upgrade", "UPGRADE_WEBHOOK_SECRET": ""},
        clear=False,
    ):
        import importlib
        import app.agent as agent_module
        importlib.reload(agent_module)
        try:
            result = agent_module._upgrade_instructions()
            # Both STATUS: DONE and curl mentioned.
            assert "STATUS: DONE" in result
            assert "curl" in result
            # The STATUS: DONE instruction must appear BEFORE the curl invocation.
            done_idx = result.find("STATUS: DONE")
            curl_idx = result.find("curl")
            assert done_idx < curl_idx, (
                "STATUS: DONE must be instructed BEFORE the curl in upgrade "
                f"instructions (got done_idx={done_idx}, curl_idx={curl_idx})"
            )
            # The instruction text should make the ordering explicit.
            lowered = result.lower()
            assert "before" in lowered, (
                "Upgrade instructions should explicitly tell the agent to "
                "write DONE BEFORE firing the webhook"
            )
        finally:
            importlib.reload(agent_module)


def test_upgrade_instructions_warns_about_marker_landing_first():
    """The instructions should warn that without DONE first, the run is crashed."""
    with patch.dict(
        os.environ,
        {"UPGRADE_WEBHOOK_URL": "http://example/upgrade", "UPGRADE_WEBHOOK_SECRET": ""},
        clear=False,
    ):
        import importlib
        import app.agent as agent_module
        importlib.reload(agent_module)
        try:
            result = agent_module._upgrade_instructions()
            # Some kind of "or it'll be crashed" warning so the agent
            # understands the risk of getting the order wrong.
            assert "crashed" in result.lower() or "kill" in result.lower()
        finally:
            importlib.reload(agent_module)


# ---------------------------------------------------------------------------
# run_agent: third-pass parse_status fallback across all turns
# ---------------------------------------------------------------------------


class _FakeStream:
    """Async stream that yields pre-baked byte lines, then EOF."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._lines:
            raise StopAsyncIteration
        return self._lines.pop(0)

    async def read(self, _n: int) -> bytes:
        return b""


class _FakeProc:
    def __init__(self, stdout_lines: list[bytes], exit_code: int = 0) -> None:
        self.stdout = _FakeStream(stdout_lines)
        self.stderr = _FakeStream([])
        self._exit_code = exit_code
        self.returncode = exit_code

    async def wait(self) -> int:
        return self._exit_code

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass


def _assistant_event(text: str) -> bytes:
    payload = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }
    return (json.dumps(payload) + "\n").encode("utf-8")


async def test_run_agent_third_pass_fallback_finds_marker_in_early_turn(tmp_path):
    """STATUS marker from turn 1 must be recovered when later turns bury it.

    The previous behavior would only inspect the concatenated tail (10 lines)
    and the last turn's text. With many short turns after the marker, the
    STATUS line is pushed outside both scan windows and was lost. The new
    third-pass fallback iterates all earlier turns in reverse.
    """
    import app.agent as agent_module

    # Turn 1 contains the STATUS marker, far from the end of concatenated text.
    turn1 = "All clean.\nSTATUS: DONE"
    # Many later short turns push turn1 well outside the 10-line tail scan.
    later_turns = [f"chatty line {i}" for i in range(20)]

    stdout_lines = [_assistant_event(turn1)] + [
        _assistant_event(t) for t in later_turns
    ]

    task = _make_task()
    # Avoid touching real disk for workspace lookup.
    original_data_dir = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path

    events_seen: list[dict] = []

    async def on_event(event: dict) -> None:
        events_seen.append(event)

    fake_proc = _FakeProc(stdout_lines, exit_code=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return fake_proc

    try:
        with patch(
            "app.agent.asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ):
            result = await run_agent(task, user_message=None, on_event=on_event)
    finally:
        agent_module.DATA_DIR = original_data_dir

    # The marker is in an early turn and must still be detected.
    assert result.status == Status.DONE
    # And the concatenated final_text should not be empty.
    assert result.final_text


async def test_run_agent_last_turn_fallback_still_works(tmp_path):
    """Sanity: the existing last-turn fallback continues to function."""
    import app.agent as agent_module

    # Concatenation buries the marker (sandwiched between turns), but the
    # LAST turn contains the marker on its own — original fallback path.
    turn1 = "intro text"
    turn2 = "wrap up.\nSTATUS: DONE"
    stdout_lines = [_assistant_event(turn1), _assistant_event(turn2)]

    task = _make_task()
    original_data_dir = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path

    async def on_event(event: dict) -> None:
        pass

    fake_proc = _FakeProc(stdout_lines, exit_code=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return fake_proc

    try:
        with patch(
            "app.agent.asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ):
            result = await run_agent(task, user_message=None, on_event=on_event)
    finally:
        agent_module.DATA_DIR = original_data_dir

    assert result.status == Status.DONE


async def test_run_agent_no_marker_anywhere_returns_none(tmp_path):
    """When no turn has STATUS, all three passes fail and status stays None."""
    import app.agent as agent_module

    stdout_lines = [
        _assistant_event("nothing"),
        _assistant_event("here"),
        _assistant_event("either"),
    ]

    task = _make_task()
    original_data_dir = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path

    async def on_event(event: dict) -> None:
        pass

    fake_proc = _FakeProc(stdout_lines, exit_code=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return fake_proc

    try:
        with patch(
            "app.agent.asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ):
            result = await run_agent(task, user_message=None, on_event=on_event)
    finally:
        agent_module.DATA_DIR = original_data_dir

    assert result.status is None


async def test_run_agent_third_pass_picks_latest_earlier_turn(tmp_path):
    """When multiple earlier turns have STATUS, reverse-scan picks the latest one."""
    import app.agent as agent_module

    # Turn 1 has WAIT; Turn 2 has DONE; many later filler turns push both
    # markers out of the tail-and-last-turn windows.
    turn_with_wait = "question?\nSTATUS: WAIT"
    turn_with_done = "later resolved.\nSTATUS: DONE"
    filler_turns = [f"filler {i}" for i in range(15)]

    stdout_lines = (
        [_assistant_event(turn_with_wait), _assistant_event(turn_with_done)]
        + [_assistant_event(t) for t in filler_turns]
    )

    task = _make_task()
    original_data_dir = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path

    async def on_event(event: dict) -> None:
        pass

    fake_proc = _FakeProc(stdout_lines, exit_code=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return fake_proc

    try:
        with patch(
            "app.agent.asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ):
            result = await run_agent(task, user_message=None, on_event=on_event)
    finally:
        agent_module.DATA_DIR = original_data_dir

    # Reverse-scan should hit the most recent earlier turn first → DONE.
    assert result.status == Status.DONE
