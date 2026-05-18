from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.agent import (
    Status,
    _extract_assistant_text,
    _upgrade_instructions,
    build_prompt,
    parse_status,
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
