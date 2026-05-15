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

from .models import Task

log = logging.getLogger("cronos.agent")

WORKSPACES_DIR = Path(os.environ.get("CRONOS_DATA_DIR", "/data")) / "workspaces"

STATUS_CONTRACT = """\
You are an autonomous task executor. The user is not watching the chat in
real time. End EVERY response with exactly one of these markers on its own
final line:

  STATUS: DONE        - the task is fully complete
  STATUS: WAIT        - you need information from the user; the line ABOVE
                        the marker must be a single clear question
  STATUS: BLOCKED     - you cannot proceed; the line ABOVE the marker must
                        explain why

Do not emit a status marker until the final line of your final message.
Until you are completely sure the task is done, do not output STATUS: DONE.
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
    """
    if not text:
        return None, None
    lines = text.rstrip().splitlines()
    if not lines:
        return None, None
    m = _STATUS_LINE.match(lines[-1])
    if not m:
        return None, None
    status = Status(m.group(1))
    context: str | None = None
    for line in reversed(lines[:-1]):
        s = line.strip()
        if s:
            context = s
            break
    return status, context


def workspace_for(task_id: str) -> Path:
    path = WORKSPACES_DIR / task_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_prompt(task: Task, user_message: str | None) -> str:
    if user_message:
        return user_message
    return (
        f"You are working on task `{task.id}`.\n\n"
        f"# Title\n{task.title}\n\n"
        f"# Brief\n{task.brief}\n\n"
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


EventCallback = Callable[[dict], Awaitable[None]]


async def run_agent(
    task: Task,
    *,
    user_message: str | None,
    on_event: EventCallback,
) -> AgentResult:
    """Spawn claude CLI for one turn of work on `task` and stream its events.

    `on_event` is awaited once per JSON event from claude's stream-json output.
    Returns once the process exits.
    """
    workspace = workspace_for(task.id)
    prompt = build_prompt(task, user_message)

    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        "Read,Edit,Write,Bash",
        "--add-dir",
        str(workspace),
        "--append-system-prompt",
        STATUS_CONTRACT,
    ]
    if task.claude_session_id:
        cmd += ["--resume", task.claude_session_id]

    log.info("Spawning claude for task %s (resume=%s)", task.id, bool(task.claude_session_id))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=workspace,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    session_id: str | None = None
    final_text_parts: list[str] = []
    raw_events: list[dict] = []
    stderr_chunks: list[bytes] = []

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

    assert proc.stdout is not None
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

        # Extract assistant text blocks for our final_text accumulation.
        text = _extract_assistant_text(event)
        if text:
            final_text_parts.append(text)

        await on_event(event)

    exit_code = await proc.wait()
    await stderr_task
    stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")[-2000:]

    final_text = "\n\n".join(final_text_parts).strip()
    status, context = parse_status(final_text)

    log.info(
        "claude exited code=%d status=%s session=%s text_len=%d",
        exit_code, status, session_id, len(final_text),
    )

    return AgentResult(
        exit_code=exit_code,
        session_id=session_id,
        final_text=final_text,
        stderr_tail=stderr,
        status=status,
        context=context,
        raw_events=raw_events,
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
