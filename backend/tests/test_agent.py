from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.agent import (
    STATUS_CONTRACT,
    Status,
    _MODEL_CLI_NAMES,
    _ensure_workspace_trusted,
    _extract_assistant_text,
    _load_adopted_dirs,
    _merge_hook_settings,
    _read_hook_settings,
    _read_workspace_settings,
    _upgrade_instructions,
    _write_workspace_settings,
    build_prompt,
    parse_status,
    run_agent,
    space_dir_for,
    workspace_for,
)
from app.models import Task, TaskState
from app.storage import VALID_AGENT_MODELS


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


def test_parse_status_bold_done():
    status, ctx = parse_status("All done.\n\n**STATUS: DONE**")
    assert status == Status.DONE
    assert ctx == "All done."


def test_parse_status_bold_wait():
    status, ctx = parse_status("What color?\n\n**STATUS: WAIT**")
    assert status == Status.WAIT
    assert ctx == "What color?"


def test_parse_status_bold_blocked():
    status, ctx = parse_status("No creds.\n\n**STATUS: BLOCKED**")
    assert status == Status.BLOCKED
    assert ctx == "No creds."


def test_parse_status_triple_bold_done():
    status, ctx = parse_status("Done.\n***STATUS: DONE***")
    assert status == Status.DONE


def test_parse_status_bold_does_not_match_mid_bold():
    # Only leading/trailing stars — mixed formatting shouldn't accidentally match
    status, ctx = parse_status("**bold sentence STATUS: DONE inline**")
    assert status is None


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
    """With no webhook URL configured, the instructions must be empty."""
    with patch.dict(os.environ, {"UPGRADE_WEBHOOK_URL": ""}, clear=False):
        import importlib
        import app.agent as agent_module
        importlib.reload(agent_module)
        try:
            result = agent_module._upgrade_instructions()
            assert result == "", (
                "When UPGRADE_WEBHOOK_URL is unset, no upgrade instructions "
                "should be injected into the system prompt"
            )
        finally:
            importlib.reload(agent_module)


def test_upgrade_instructions_with_url():
    with patch.dict(
        os.environ,
        {"UPGRADE_WEBHOOK_URL": "http://localhost:9137/upgrade"},
        clear=False,
    ):
        import importlib
        import app.agent as agent_module
        importlib.reload(agent_module)
        try:
            result = agent_module._upgrade_instructions()
            assert "http://localhost:9137/upgrade" in result
            assert "curl" in result
        finally:
            importlib.reload(agent_module)


def test_upgrade_instructions_does_not_leak_secret_header():
    """MED-006: the system prompt must NOT contain `X-Upgrade-Secret`.

    Embedding the shared secret (or even the header name with a placeholder)
    in the agent's system prompt leaks it to the model provider and to any
    transcript that logs the prompt. The fix removes the
    `UPGRADE_WEBHOOK_SECRET` read entirely and emits a curl without the
    `-H "X-Upgrade-Secret: ..."` header; authorization is enforced by
    network ACL (Docker bridge only) instead.

    This test fails the moment anyone re-introduces the header — whether
    they hard-code it, read it back from the environment, or templatize it.
    """
    with patch.dict(
        os.environ,
        {
            "UPGRADE_WEBHOOK_URL": "http://dummy.local/upgrade",
            # Set the secret env var too: if a regression re-adds the
            # env read, the secret value would land in `result`.
            "UPGRADE_WEBHOOK_SECRET": "super-secret-value-should-not-appear",
        },
        clear=False,
    ):
        import importlib
        import app.agent as agent_module
        importlib.reload(agent_module)
        try:
            result = agent_module._upgrade_instructions()
            # The URL must still be present — sanity that we exercised the
            # non-empty branch.
            assert "http://dummy.local/upgrade" in result
            # Case-insensitive check on the header name: catches any casing
            # variant a regression might introduce.
            assert "x-upgrade-secret" not in result.lower(), (
                "Agent system prompt must not contain the `X-Upgrade-Secret` "
                "header (MED-006). Embedding it leaks the secret into the "
                "model context."
            )
            # And the secret value itself must not appear either.
            assert "super-secret-value-should-not-appear" not in result, (
                "Agent system prompt leaked the UPGRADE_WEBHOOK_SECRET value "
                "into the curl command (MED-006). The secret must never be "
                "read by app/agent.py."
            )
        finally:
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


def test_upgrade_instructions_uses_plain_status_done():
    """The upgrade instructions must use plain STATUS: DONE, not **STATUS: DONE**.

    Bold markdown around the marker causes the regex to fail to match, leaving
    the task in WAITING state even though the agent wrote the marker correctly.
    This was the root cause of every upgrade task ending in WAITING.
    """
    with patch.dict(
        os.environ,
        {"UPGRADE_WEBHOOK_URL": "http://localhost:9137/upgrade"},
        clear=False,
    ):
        import importlib
        import app.agent as agent_module
        importlib.reload(agent_module)
        try:
            result = agent_module._upgrade_instructions()
            assert "**STATUS: DONE**" not in result, (
                "_upgrade_instructions() must not use **STATUS: DONE** (bold markdown). "
                "The regex only matches plain STATUS: DONE."
            )
            assert "STATUS: DONE" in result
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

    async def readline(self) -> bytes:
        if not self._lines:
            return b""
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


# ---------------------------------------------------------------------------
# run_agent: must not hang when claude exits but stdout pipe stays open
# (a Bash tool left a background process holding the inherited pipe).
# ---------------------------------------------------------------------------


def _result_event(subtype: str = "success") -> bytes:
    payload = {"type": "result", "subtype": subtype, "session_id": "sess-1"}
    return (json.dumps(payload) + "\n").encode("utf-8")


class _PipeHeldOpenStream:
    """Yields queued lines, then blocks forever on the next read.

    Models a stdout/stderr pipe kept open by a leaked background child after
    the claude process itself has exited.
    """

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)

    async def readline(self) -> bytes:
        if self._lines:
            return self._lines.pop(0)
        await asyncio.Event().wait()  # never resolves
        return b""  # pragma: no cover

    async def read(self, _n: int) -> bytes:
        if self._lines:
            return self._lines.pop(0)
        await asyncio.Event().wait()  # never resolves
        return b""  # pragma: no cover


class _ExitsButPipeOpenProc:
    """Process whose wait() resolves while stdout (and optionally stderr) stay
    open — the exact condition that used to hang run_agent forever."""

    def __init__(
        self,
        stdout_lines: list[bytes],
        *,
        exit_code: int = 0,
        exit_delay: float = 0.05,
        block_stderr: bool = False,
    ) -> None:
        self.stdout = _PipeHeldOpenStream(stdout_lines)
        self.stderr = _PipeHeldOpenStream([]) if block_stderr else _FakeStream([])
        self._exit_code = exit_code
        self._exit_delay = exit_delay
        self.returncode: int | None = None

    async def wait(self) -> int:
        await asyncio.sleep(self._exit_delay)
        self.returncode = self._exit_code
        return self._exit_code

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass


async def test_run_agent_returns_when_result_seen_despite_open_pipe(tmp_path):
    """Agent emits STATUS: DONE + result, then a leaked child holds stdout open.

    Previously run_agent waited for stdout EOF, which never came, so the task
    stayed stuck in ACTIVE. It must now stop on the terminal `result` event.
    """
    import app.agent as agent_module

    stdout_lines = [_assistant_event("done.\nSTATUS: DONE"), _result_event()]
    task = _make_task()
    original_data_dir = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path

    async def on_event(event: dict) -> None:
        pass

    fake_proc = _ExitsButPipeOpenProc(stdout_lines, exit_code=0, block_stderr=True)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return fake_proc

    try:
        with patch(
            "app.agent.asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ):
            result = await asyncio.wait_for(
                run_agent(task, user_message=None, on_event=on_event), timeout=10
            )
    finally:
        agent_module.DATA_DIR = original_data_dir

    assert result.status == Status.DONE
    assert result.exit_code == 0


async def test_run_agent_returns_when_process_exits_without_result(tmp_path):
    """Crash path: no `result` event and stdout never EOFs, but the process
    exits. run_agent must observe the exit and return instead of hanging."""
    import app.agent as agent_module

    stdout_lines = [_assistant_event("working on it...")]
    task = _make_task()
    original_data_dir = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path

    async def on_event(event: dict) -> None:
        pass

    fake_proc = _ExitsButPipeOpenProc(stdout_lines, exit_code=1, exit_delay=0.05)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return fake_proc

    try:
        with patch(
            "app.agent.asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ):
            result = await asyncio.wait_for(
                run_agent(task, user_message=None, on_event=on_event), timeout=10
            )
    finally:
        agent_module.DATA_DIR = original_data_dir

    assert result.status is None
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Adopted tools: _load_adopted_dirs
# ---------------------------------------------------------------------------


def test_load_adopted_dirs_empty_when_no_tools_dir(tmp_path):
    import app.agent as agent_module
    original = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path
    try:
        (tmp_path / "spaces" / "myspace").mkdir(parents=True)
        assert _load_adopted_dirs("myspace") == []
    finally:
        agent_module.DATA_DIR = original


def test_load_adopted_dirs_returns_items(tmp_path):
    import app.agent as agent_module
    original = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path
    try:
        skill_dir = tmp_path / "spaces" / "myspace" / ".cronos" / "tools" / "skill" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.yml").write_text("kind: skill\nname: my-skill\n")
        (skill_dir / "SKILL.md").write_text("# My skill")

        result = _load_adopted_dirs("myspace")
        assert len(result) == 1
        assert result[0][0] == skill_dir
        assert result[0][1] == "skill"
    finally:
        agent_module.DATA_DIR = original


def test_load_adopted_dirs_skips_trash(tmp_path):
    import app.agent as agent_module
    original = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path
    try:
        # Real adopted item
        skill_dir = tmp_path / "spaces" / "s" / ".cronos" / "tools" / "skill" / "foo"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.yml").write_text("kind: skill\n")

        # Trash directory (starts with ".")
        trash = tmp_path / "spaces" / "s" / ".cronos" / "tools" / ".trash" / "skill" / "foo-old"
        trash.mkdir(parents=True)
        (trash / "manifest.yml").write_text("kind: skill\n")

        result = _load_adopted_dirs("s")
        assert len(result) == 1
        assert result[0][0] == skill_dir
    finally:
        agent_module.DATA_DIR = original


def test_load_adopted_dirs_skips_dir_without_manifest(tmp_path):
    import app.agent as agent_module
    original = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path
    try:
        no_manifest = tmp_path / "spaces" / "s" / ".cronos" / "tools" / "skill" / "orphan"
        no_manifest.mkdir(parents=True)
        (no_manifest / "SKILL.md").write_text("# skill without manifest")

        assert _load_adopted_dirs("s") == []
    finally:
        agent_module.DATA_DIR = original


# ---------------------------------------------------------------------------
# Adopted tools: _read_hook_settings
# ---------------------------------------------------------------------------


def test_read_hook_settings_empty_when_no_json_file(tmp_path):
    hook_dir = tmp_path / "hook-item"
    hook_dir.mkdir()
    (hook_dir / "manifest.yml").write_text("kind: hook\n")
    (hook_dir / "myhook.md").write_text("# this is markdown, not JSON")
    assert _read_hook_settings(hook_dir) == {}


def test_read_hook_settings_empty_when_json_has_no_relevant_keys(tmp_path):
    hook_dir = tmp_path / "hook-item"
    hook_dir.mkdir()
    (hook_dir / "manifest.yml").write_text("kind: hook\n")
    (hook_dir / "settings.md").write_text('{"other_key": "value"}')
    assert _read_hook_settings(hook_dir) == {}


def test_read_hook_settings_finds_permissions(tmp_path):
    hook_dir = tmp_path / "hook-item"
    hook_dir.mkdir()
    (hook_dir / "manifest.yml").write_text("kind: hook\n")
    settings = {"permissions": {"allow": ["Bash(npm:*)"]}}
    (hook_dir / "settings.md").write_text(json.dumps(settings))
    assert _read_hook_settings(hook_dir) == settings


def test_read_hook_settings_finds_hooks(tmp_path):
    hook_dir = tmp_path / "hook-item"
    hook_dir.mkdir()
    (hook_dir / "manifest.yml").write_text("kind: hook\n")
    settings = {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"command": "echo hi"}]}]}}
    (hook_dir / "settings.md").write_text(json.dumps(settings))
    assert _read_hook_settings(hook_dir) == settings


# ---------------------------------------------------------------------------
# Adopted tools: _merge_hook_settings
# ---------------------------------------------------------------------------


def test_merge_hook_settings_no_hooks_returns_workspace_unchanged():
    ws = {"permissions": {"allow": ["Bash(*)"]}}
    assert _merge_hook_settings([], ws) == ws


def test_merge_hook_settings_empty_workspace_returns_hook_settings():
    hook = {"permissions": {"allow": ["Bash(npm:*)"]}}
    result = _merge_hook_settings([hook], {})
    assert result["permissions"]["allow"] == ["Bash(npm:*)"]


def test_merge_hook_settings_union_of_allow():
    ws = {"permissions": {"allow": ["Read(*)"]}}
    hook = {"permissions": {"allow": ["Bash(npm:*)", "Read(*)"]}}
    result = _merge_hook_settings([hook], ws)
    allow = result["permissions"]["allow"]
    assert "Read(*)" in allow
    assert "Bash(npm:*)" in allow
    # No duplicates
    assert allow.count("Read(*)") == 1


def test_merge_hook_settings_workspace_wins_on_duplicate_allow():
    ws = {"permissions": {"allow": ["Bash(*)", "Read(*)"]}}
    hook = {"permissions": {"allow": ["Bash(*)", "Write(*)"]}}
    result = _merge_hook_settings([hook], ws)
    allow = result["permissions"]["allow"]
    # Workspace entries appear first
    assert allow[0] == "Bash(*)"
    assert allow[1] == "Read(*)"
    # Hook-only entry appended
    assert "Write(*)" in allow
    # No duplicate Bash(*)
    assert allow.count("Bash(*)") == 1


def test_merge_hook_settings_merges_hooks_events():
    ws_group = {"matcher": "*", "hooks": [{"command": "ws-cmd"}]}
    hook_group = {"matcher": "Bash", "hooks": [{"command": "hook-cmd"}]}
    ws = {"hooks": {"PreToolUse": [ws_group]}}
    hook = {"hooks": {"PreToolUse": [hook_group]}}
    result = _merge_hook_settings([hook], ws)
    event_list = result["hooks"]["PreToolUse"]
    # Workspace entry first
    assert event_list[0] == ws_group
    assert event_list[1] == hook_group


def test_merge_hook_settings_hook_only_event_included():
    hook = {"hooks": {"PostToolUse": [{"matcher": "*", "hooks": [{"command": "post-cmd"}]}]}}
    result = _merge_hook_settings([hook], {})
    assert "PostToolUse" in result["hooks"]


def test_merge_hook_settings_other_keys_workspace_wins():
    ws = {"model": "claude-opus"}
    hook = {"model": "claude-haiku", "permissions": {"allow": ["Read(*)"]}}
    result = _merge_hook_settings([hook], ws)
    assert result["model"] == "claude-opus"


# ---------------------------------------------------------------------------
# Adopted tools: workspace settings read/write
# ---------------------------------------------------------------------------


def test_read_workspace_settings_absent_returns_empty(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    assert _read_workspace_settings(ws) == {}


def test_read_workspace_settings_reads_json(tmp_path):
    ws = tmp_path / "workspace"
    (ws / ".claude").mkdir(parents=True)
    settings = {"permissions": {"allow": ["Read(*)"]}}
    (ws / ".claude" / "settings.json").write_text(json.dumps(settings))
    assert _read_workspace_settings(ws) == settings


def test_write_workspace_settings_creates_file(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    settings = {"permissions": {"allow": ["Bash(*)"]}}
    _write_workspace_settings(ws, settings)
    content = json.loads((ws / ".claude" / "settings.json").read_text())
    assert content == settings


def test_write_workspace_settings_creates_claude_dir(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    _write_workspace_settings(ws, {"hooks": {}})
    assert (ws / ".claude" / "settings.json").is_file()


# ---------------------------------------------------------------------------
# _ensure_workspace_trusted: seed CLI project trust
# ---------------------------------------------------------------------------


def test_ensure_workspace_trusted_adds_entry(tmp_path):
    """Trust flag is written for the workspace and every add-dir."""
    cfg = tmp_path / ".claude.json"
    cfg.write_text(json.dumps({"oauthAccount": {"emailAddress": "x@y.z"}}))
    ws = tmp_path / "spaces" / "cronos-development"
    tool = tmp_path / "tools" / "my-skill"
    _ensure_workspace_trusted(cfg, [ws, tool])
    data = json.loads(cfg.read_text())
    # Existing auth content is preserved (read-modify-write, not clobbered).
    assert data["oauthAccount"] == {"emailAddress": "x@y.z"}
    assert data["projects"][str(ws)]["hasTrustDialogAccepted"] is True
    assert data["projects"][str(tool)]["hasTrustDialogAccepted"] is True


def test_ensure_workspace_trusted_creates_missing_config(tmp_path):
    """A missing .claude.json is created with the trust entry."""
    cfg = tmp_path / ".claude.json"
    ws = tmp_path / "workspace"
    _ensure_workspace_trusted(cfg, [ws])
    data = json.loads(cfg.read_text())
    assert data["projects"][str(ws)]["hasTrustDialogAccepted"] is True


def test_ensure_workspace_trusted_idempotent_no_rewrite(tmp_path):
    """When already trusted, the file is not rewritten (mtime unchanged)."""
    cfg = tmp_path / ".claude.json"
    ws = tmp_path / "workspace"
    cfg.write_text(json.dumps({"projects": {str(ws): {"hasTrustDialogAccepted": True}}}))
    before = cfg.stat().st_mtime_ns
    _ensure_workspace_trusted(cfg, [ws])
    assert cfg.stat().st_mtime_ns == before


def test_ensure_workspace_trusted_preserves_other_project_fields(tmp_path):
    """Sibling fields on an existing project entry survive the trust update."""
    cfg = tmp_path / ".claude.json"
    ws = tmp_path / "workspace"
    cfg.write_text(
        json.dumps(
            {"projects": {str(ws): {"hasTrustDialogAccepted": False, "history": ["a"]}}}
        )
    )
    _ensure_workspace_trusted(cfg, [ws])
    entry = json.loads(cfg.read_text())["projects"][str(ws)]
    assert entry["hasTrustDialogAccepted"] is True
    assert entry["history"] == ["a"]


def test_ensure_workspace_trusted_tolerates_corrupt_config(tmp_path):
    """A corrupt config is left untouched and does not raise."""
    cfg = tmp_path / ".claude.json"
    cfg.write_text("{not json")
    _ensure_workspace_trusted(cfg, [tmp_path / "workspace"])
    assert cfg.read_text() == "{not json"


# ---------------------------------------------------------------------------
# run_agent: adopted tool --add-dir injection
# ---------------------------------------------------------------------------


async def test_run_agent_adopted_skill_adds_dir_to_cmd(tmp_path):
    """Adopted skill dir must appear as --add-dir after the workspace dir."""
    import app.agent as agent_module

    # Create adopted skill directory
    skill_dir = tmp_path / "spaces" / "space-xyz" / ".cronos" / "tools" / "skill" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "manifest.yml").write_text("kind: skill\nname: my-skill\n")
    (skill_dir / "SKILL.md").write_text("# My skill")

    task = _make_task()
    original = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path

    captured: list = []

    async def fake_exec(*args, **kwargs):
        captured.extend(args)
        return _FakeProc([], exit_code=0)

    async def on_event(e):
        pass

    try:
        with patch("app.agent.asyncio.create_subprocess_exec", side_effect=fake_exec):
            await run_agent(task, user_message=None, on_event=on_event)
    finally:
        agent_module.DATA_DIR = original

    assert "--add-dir" in captured
    assert str(skill_dir) in captured

    # Adopted dir must appear AFTER the workspace --add-dir
    workspace_path = str(tmp_path / "spaces" / "space-xyz" / ".cronos" / "workspaces" / "task-abc")
    ws_idx = captured.index(workspace_path)
    skill_idx = captured.index(str(skill_dir))
    assert skill_idx > ws_idx


async def test_run_agent_no_adopted_tools_no_extra_add_dir(tmp_path):
    """When no tools dir exists, only the workspace --add-dir must appear."""
    import app.agent as agent_module

    (tmp_path / "spaces" / "space-xyz").mkdir(parents=True)
    task = _make_task()
    original = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path

    captured: list = []

    async def fake_exec(*args, **kwargs):
        captured.extend(args)
        return _FakeProc([], exit_code=0)

    async def on_event(e):
        pass

    try:
        with patch("app.agent.asyncio.create_subprocess_exec", side_effect=fake_exec):
            await run_agent(task, user_message=None, on_event=on_event)
    finally:
        agent_module.DATA_DIR = original

    # Only one --add-dir (the workspace)
    add_dir_count = captured.count("--add-dir")
    assert add_dir_count == 1


async def test_run_agent_hook_writes_settings_json(tmp_path):
    """Adopted hook must write merged settings.json into workspace/.claude/."""
    import app.agent as agent_module

    hook_dir = tmp_path / "spaces" / "space-xyz" / ".cronos" / "tools" / "hook" / "pre-tool"
    hook_dir.mkdir(parents=True)
    (hook_dir / "manifest.yml").write_text("kind: hook\nname: pre-tool\n")
    hook_settings = {"permissions": {"allow": ["Bash(npm:*)"]}}
    (hook_dir / "settings.md").write_text(json.dumps(hook_settings))

    task = _make_task()
    original = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path

    async def fake_exec(*args, **kwargs):
        return _FakeProc([], exit_code=0)

    async def on_event(e):
        pass

    try:
        with patch("app.agent.asyncio.create_subprocess_exec", side_effect=fake_exec):
            await run_agent(task, user_message=None, on_event=on_event)
    finally:
        agent_module.DATA_DIR = original

    ws_settings_path = (
        tmp_path / "spaces" / "space-xyz" / ".cronos" / "workspaces" / "task-abc"
        / ".claude" / "settings.json"
    )
    assert ws_settings_path.is_file()
    content = json.loads(ws_settings_path.read_text())
    assert content["permissions"]["allow"] == ["Bash(npm:*)"]


async def test_run_agent_workspace_settings_override_hook(tmp_path):
    """Existing workspace settings.json overrides hook on duplicate allow entries."""
    import app.agent as agent_module

    # Set up hook
    hook_dir = tmp_path / "spaces" / "space-xyz" / ".cronos" / "tools" / "hook" / "pre-tool"
    hook_dir.mkdir(parents=True)
    (hook_dir / "manifest.yml").write_text("kind: hook\nname: pre-tool\n")
    hook_settings = {"permissions": {"allow": ["Bash(npm:*)", "Write(*)"]}}
    (hook_dir / "settings.md").write_text(json.dumps(hook_settings))

    task = _make_task()
    original = agent_module.DATA_DIR
    agent_module.DATA_DIR = tmp_path

    # Pre-create workspace with its own settings
    ws_dir = tmp_path / "spaces" / "space-xyz" / ".cronos" / "workspaces" / "task-abc"
    ws_dir.mkdir(parents=True)
    ws_claude = ws_dir / ".claude"
    ws_claude.mkdir()
    ws_existing = {"permissions": {"allow": ["Read(*)", "Bash(npm:*)"]}}
    (ws_claude / "settings.json").write_text(json.dumps(ws_existing))

    async def fake_exec(*args, **kwargs):
        return _FakeProc([], exit_code=0)

    async def on_event(e):
        pass

    try:
        with patch("app.agent.asyncio.create_subprocess_exec", side_effect=fake_exec):
            await run_agent(task, user_message=None, on_event=on_event)
    finally:
        agent_module.DATA_DIR = original

    content = json.loads((ws_claude / "settings.json").read_text())
    allow = content["permissions"]["allow"]
    # Workspace entries are first
    assert allow[0] == "Read(*)"
    assert allow[1] == "Bash(npm:*)"
    # Hook-only entry appended (not a dup with workspace)
    assert "Write(*)" in allow
    # No duplicate Bash(npm:*)
    assert allow.count("Bash(npm:*)") == 1


# ---------------------------------------------------------------------------
# fable-5 model support
# ---------------------------------------------------------------------------


def test_valid_agent_models_includes_fable5():
    assert "fable-5" in VALID_AGENT_MODELS


def test_model_cli_names_maps_fable5():
    assert _MODEL_CLI_NAMES["fable-5"] == "claude-fable-5"


# ---------------------------------------------------------------------------
# build_prompt: memory injection (R6) — full body must reach the agent
# ---------------------------------------------------------------------------


def _make_memory_item(
    *,
    title: str,
    body: str = "",
    kind: str = "fact",
) -> "MemoryItem":
    from datetime import timezone
    from app.models import MemoryItem, MemoryKind

    return MemoryItem(
        id="mem-1",
        scope="global",
        kind=MemoryKind(kind),
        title=title,
        body=body,
        confirmed=True,
        confidence=1.0,
        score=0.5,
        last_used_at=datetime.now(tz=timezone.utc),
        ref_count=1,
    )


def test_build_prompt_memory_full_body_all_lines_present():
    """R6: build_prompt() with a multi-line body emits ALL lines in the prompt."""
    task = _make_task()
    item = _make_memory_item(
        title="My procedure",
        body="Line one\nLine two\nLine three",
        kind="procedure",
    )
    prompt = build_prompt(task, None, memory_items=[item])

    assert "Line one" in prompt
    assert "Line two" in prompt
    assert "Line three" in prompt
    # The title and kind appear as the bullet header
    assert "**My procedure**" in prompt
    assert "(procedure)" in prompt


def test_build_prompt_memory_body_equals_title_still_emits_body():
    """R6: when body's first line equals the title, the body is STILL included.

    The old bug: first-line-equals-title caused the detail to be omitted.
    After the fix the full body always follows the bullet header.
    """
    task = _make_task()
    title = "Deploy procedure"
    item = _make_memory_item(
        title=title,
        body=f"{title}\nStep 1: pull\nStep 2: restart",
        kind="procedure",
    )
    prompt = build_prompt(task, None, memory_items=[item])

    # All body lines must appear
    assert "Step 1: pull" in prompt
    assert "Step 2: restart" in prompt
    # The title appears as the bullet header and inside the body — both fine
    assert f"**{title}**" in prompt


def test_build_prompt_memory_empty_body_no_trailing_colon():
    """R6: when body is empty, bullet is emitted without trailing colon or blank."""
    task = _make_task()
    item = _make_memory_item(title="Simple fact", body="", kind="fact")
    prompt = build_prompt(task, None, memory_items=[item])

    assert "**Simple fact** (fact)" in prompt
    # No stray ": " after the closing paren when body is absent
    assert "**Simple fact** (fact):" not in prompt
