from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from . import git_ops
from .models import Space, Task

log = logging.getLogger("cronos.agent")

DATA_DIR = Path(os.environ.get("CRONOS_DATA_DIR", "/data"))
CRONOS_SUBDIR = ".cronos"

UPGRADE_WEBHOOK_URL = os.environ.get("UPGRADE_WEBHOOK_URL", "")
UPGRADE_WEBHOOK_SECRET = os.environ.get("UPGRADE_WEBHOOK_SECRET", "")

STATUS_CONTRACT = """\
You are an autonomous task executor. The user is not watching in real time.

When you have finished all your work, end your FINAL response with exactly one
status marker on its own last line:

  STATUS: DONE        - the task is fully complete
  STATUS: WAIT        - you need information from the user; the line ABOVE
                        the marker must be a single clear question
  STATUS: BLOCKED     - you cannot proceed; the line ABOVE must explain why

Rules:
- The STATUS marker MUST be the very last line you output. No text after it.
- Write STATUS only once, in the final wrap-up after all tool calls are done.
- If you cannot finish the task in this session (e.g. turn limit approaching),
  use STATUS: WAIT and describe exactly what was completed and what still
  remains so the next run can pick up from there.
- Use STATUS: DONE only when the task is truly and fully complete.
"""


class Status(str, Enum):
    DONE = "DONE"
    WAIT = "WAIT"
    BLOCKED = "BLOCKED"


_STATUS_LINE = re.compile(r"^\s*STATUS:\s*(DONE|WAIT|BLOCKED)\s*$")


def parse_status(text: str) -> tuple[Status | None, str | None]:
    """Return (status, context_line) parsed from the agent's final text.

    The context_line is the immediately preceding non-blank line, used as the
    waiting question for STATUS: WAIT or the blocker reason for STATUS: BLOCKED.

    Scans backwards through the last several lines so that a stray trailing
    sentence from the model does not hide an otherwise valid STATUS marker.
    """
    if not text:
        return None, None
    lines = text.rstrip().splitlines()
    if not lines:
        return None, None
    # Scan the tail of the response (up to 10 lines) for the last STATUS marker.
    scan_from = max(0, len(lines) - 10)
    for i in range(len(lines) - 1, scan_from - 1, -1):
        m = _STATUS_LINE.match(lines[i])
        if m:
            status = Status(m.group(1))
            context: str | None = None
            for line in reversed(lines[:i]):
                s = line.strip()
                if s:
                    context = s
                    break
            return status, context
    return None, None


def space_dir_for(space_id: str) -> Path:
    return DATA_DIR / "spaces" / space_id


async def workspace_for(task: Task, space: Space | None = None) -> Path:
    """Return the working directory for `task`'s next run.

    For repo-linked spaces this is a per-task git worktree on branch
    `cronos/{task_id}` (created lazily if missing). For unlinked spaces it's
    a plain dir, unchanged from previous behavior.
    """
    sdir = space_dir_for(task.space_id)
    if space is not None and space.git_repo_url and space.git_branch:
        try:
            return await git_ops.ensure_task_worktree(
                sdir, task.id, base_branch=space.git_branch
            )
        except git_ops.GitError:
            log.exception(
                "Failed to create worktree for %s; falling back to plain dir",
                task.id,
            )
    path = sdir / CRONOS_SUBDIR / "workspaces" / task.id
    path.mkdir(parents=True, exist_ok=True)
    return path


PERMISSION_MODE: dict[str, str] = {
    "plan": "acceptEdits",  # "plan" would inject ExitPlanMode instructions that can't be fulfilled
    "auto": "acceptEdits",
    "ask": "default",
}

PLAN_MODE_TOOLS = "Read,Grep,Glob,Skill,Agent"
DEFAULT_TOOLS = "Read,Edit,Write,Bash,Skill,Agent"


def _upgrade_instructions() -> str:
    if not UPGRADE_WEBHOOK_URL:
        return (
            "# Upgrading the app\n"
            "UPGRADE_WEBHOOK_URL is not set. You cannot trigger an upgrade from "
            "inside the container. Ask the user to run `upgrade.sh` manually on "
            "the host, or follow VPS_SETUP.md §10.2 to install the upgrade webhook."
        )
    secret_header = (
        f'-H "X-Upgrade-Secret: {UPGRADE_WEBHOOK_SECRET}"'
        if UPGRADE_WEBHOOK_SECRET
        else ""
    )
    return (
        "# Upgrading the app\n"
        "When asked to upgrade the application, run:\n\n"
        f"  curl -s -X POST {secret_header} {UPGRADE_WEBHOOK_URL}\n\n"
        "This calls a host-side webhook that runs `upgrade.sh` (git pull + "
        "docker compose up --build + systemctl restart). The containers will "
        "restart; the current agent session will be terminated as part of the "
        "restart. Confirm to the user that the upgrade has been triggered before "
        "the session ends."
    )


def build_prompt(task: Task, user_message: str | None) -> str:
    fresh = task.claude_session_id is None
    if user_message and not fresh:
        return user_message
    msg_section = f"\n# Message\n{user_message}\n" if user_message else ""
    return (
        f"You are working on task `{task.id}`.\n\n"
        f"# Title\n{task.title}\n\n"
        f"# Brief\n{task.brief}\n"
        f"{msg_section}\n"
        "A per-task workspace has been mounted as your working directory; create\n"
        "all files there. Begin work now, and remember the STATUS contract.\n"
    )


@dataclass
class AgentResult:
    exit_code: int
    session_id: str | None
    final_text: str
    stderr_tail: str
    status: Status | None = None
    context: str | None = None
    raw_events: list[dict] = field(default_factory=list)
    stopped: bool = False
    result_subtype: str | None = None


EventCallback = Callable[[dict], Awaitable[None]]


async def run_agent(
    task: Task,
    *,
    user_message: str | None,
    on_event: EventCallback,
    cancel_event: asyncio.Event | None = None,
    space: Space | None = None,
) -> AgentResult:
    """Spawn claude CLI for one turn of work on `task` and stream its events.

    `on_event` is awaited once per JSON event from claude's stream-json output.
    If `cancel_event` is provided and set during the run, the subprocess is
    terminated and the returned `AgentResult.stopped` is True.
    Returns once the process exits.
    """
    workspace = await workspace_for(task, space)
    prompt = build_prompt(task, user_message)
    permission_mode = PERMISSION_MODE.get(task.agent_mode, "acceptEdits")
    allowed_tools = PLAN_MODE_TOOLS if task.agent_mode == "plan" else DEFAULT_TOOLS

    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        permission_mode,
        "--allowedTools",
        allowed_tools,
        "--add-dir",
        str(workspace),
        "--append-system-prompt",
        STATUS_CONTRACT,
        "--append-system-prompt",
        _upgrade_instructions(),
    ]
    if task.agent_model != "default":
        cmd += ["--model", task.agent_model]
    if task.claude_session_id:
        cmd += ["--resume", task.claude_session_id]

    log.info(
        "Spawning claude for task %s (resume=%s, mode=%s, model=%s)",
        task.id, bool(task.claude_session_id), task.agent_mode, task.agent_model,
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=workspace,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    session_id: str | None = None
    result_subtype: str | None = None
    final_text_parts: list[str] = []
    raw_events: list[dict] = []
    stderr_chunks: list[bytes] = []
    stopped = False

    async def drain_stderr() -> None:
        assert proc.stderr is not None
        while True:
            chunk = await proc.stderr.read(4096)
            if not chunk:
                return
            stderr_chunks.append(chunk)
            # Keep at most ~16KiB of stderr in memory.
            total = sum(len(c) for c in stderr_chunks)
            if total > 16_384:
                # Drop oldest chunks until under threshold.
                while total > 16_384 and len(stderr_chunks) > 1:
                    total -= len(stderr_chunks.pop(0))

    stderr_task = asyncio.create_task(drain_stderr())

    async def kill_on_cancel() -> None:
        if cancel_event is None:
            return
        await cancel_event.wait()
        nonlocal stopped
        stopped = True
        log.info("Cancellation requested for task %s; terminating claude", task.id)
        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                log.warning("claude did not exit on SIGTERM for %s; killing", task.id)
                proc.kill()
        except ProcessLookupError:
            pass

    cancel_task = asyncio.create_task(kill_on_cancel())

    assert proc.stdout is not None
    try:
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                log.warning("Non-JSON line from claude: %s", line[:200])
                continue

            raw_events.append(event)

            # Capture session id from system/init and final result events.
            if isinstance(event, dict):
                if event.get("type") == "system" and event.get("subtype") == "init":
                    session_id = event.get("session_id") or session_id
                elif event.get("type") == "result":
                    session_id = event.get("session_id") or session_id
                    result_subtype = event.get("subtype") or result_subtype

            # Extract assistant text blocks for our final_text accumulation.
            text = _extract_assistant_text(event)
            if text:
                final_text_parts.append(text)

            await on_event(event)
    finally:
        exit_code = await proc.wait()
        cancel_task.cancel()
        try:
            await cancel_task
        except (asyncio.CancelledError, Exception):
            pass
        await stderr_task

    stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")[-2000:]

    final_text = "\n\n".join(final_text_parts).strip()
    status, context = parse_status(final_text)
    # Fallback: if the concatenated text buries an earlier STATUS marker, try
    # parsing just the last turn's text in isolation.
    if status is None and final_text_parts:
        status, context = parse_status(final_text_parts[-1])

    log.info(
        "claude exited code=%d status=%s subtype=%s session=%s text_len=%d stopped=%s",
        exit_code, status, result_subtype, session_id, len(final_text), stopped,
    )

    return AgentResult(
        exit_code=exit_code,
        session_id=session_id,
        final_text=final_text,
        stderr_tail=stderr,
        status=status,
        context=context,
        raw_events=raw_events,
        stopped=stopped,
        result_subtype=result_subtype,
    )


def _extract_assistant_text(event: dict) -> str | None:
    """Pull text content out of an `assistant`-typed stream-json event."""
    if not isinstance(event, dict):
        return None
    if event.get("type") != "assistant":
        return None
    msg = event.get("message")
    if not isinstance(msg, dict):
        return None
    content = msg.get("content")
    if not isinstance(content, list):
        return None
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            t = block.get("text")
            if isinstance(t, str):
                parts.append(t)
    if not parts:
        return None
    return "".join(parts)
