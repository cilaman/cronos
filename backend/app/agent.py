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
from .models import MemoryItem, Space, Task

log = logging.getLogger("cronos.agent")

DATA_DIR = Path(os.environ.get("CRONOS_DATA_DIR", "/data"))
CRONOS_SUBDIR = ".cronos"

UPGRADE_WEBHOOK_URL = os.environ.get("UPGRADE_WEBHOOK_URL", "")

STATUS_CONTRACT = """You are an autonomous task executor. The user is not watching in real time.

## How to finish a task

When all work is complete, invoke the **task-finalize** skill as your last action:

  /task-finalize

This skill handles git, memory writing, and the STATUS marker in the correct order.
Do NOT write STATUS: DONE manually — task-finalize does it.

### Exceptions — do not invoke task-finalize for these

If you need user input before continuing:
  <write your question here>
  STATUS: WAIT

If you are genuinely blocked and cannot proceed:
  <explain the blocker here>
  STATUS: BLOCKED

### Fallback (only if task-finalize fails to load)

Write MEMORY lines then STATUS: DONE as your final response:

  MEMORY[fact]: <what was accomplished>
  STATUS: DONE

Rules:
- STATUS must be the VERY LAST LINE. No text after it.
- Write STATUS only once, after all tool calls are done.
- Do NOT use markdown formatting: write STATUS: DONE not **STATUS: DONE**
- Turn limit approaching: use STATUS: WAIT, describe what's done and what remains.
- Plan mode: end with STATUS: WAIT and ask "Shall I implement this plan?"
"""


class Status(str, Enum):
    DONE = "DONE"
    WAIT = "WAIT"
    BLOCKED = "BLOCKED"


_STATUS_LINE = re.compile(r"^\s*\*{0,3}STATUS:\s*(DONE|WAIT|BLOCKED)\*{0,3}\s*$")


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


def _load_adopted_dirs(space_id: str) -> list[tuple[Path, str]]:
    """Return (item_dir, kind) for every adopted tool in the space.

    Skips .trash and any directory without a manifest.yml.
    """
    tools_dir = space_dir_for(space_id) / CRONOS_SUBDIR / "tools"
    if not tools_dir.is_dir():
        return []
    results: list[tuple[Path, str]] = []
    for kind_dir in sorted(tools_dir.iterdir()):
        if not kind_dir.is_dir() or kind_dir.name.startswith("."):
            continue
        for item_dir in sorted(kind_dir.iterdir()):
            if not item_dir.is_dir():
                continue
            if not (item_dir / "manifest.yml").is_file():
                continue
            results.append((item_dir, kind_dir.name))
    return results


def _read_hook_settings(item_dir: Path) -> dict:
    """Read settings (permissions/hooks) from an adopted hook directory.

    Tries all non-manifest files for JSON content with permissions/hooks keys.
    Returns empty dict if nothing parseable is found.
    """
    for f in sorted(item_dir.iterdir()):
        if f.name == "manifest.yml" or not f.is_file():
            continue
        try:
            data = json.loads(f.read_bytes())
            if isinstance(data, dict) and ("permissions" in data or "hooks" in data):
                return data
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
    return {}


def _merge_hook_settings(
    hook_settings_list: list[dict],
    workspace_settings: dict,
) -> dict:
    """Merge adopted hook settings with workspace settings.

    permissions.allow/deny: union, workspace entries first (no duplication).
    hooks.Event: workspace entries first per event, then adopted hook entries.
    Other top-level keys: workspace value wins.
    """
    agg_allow: list[str] = []
    agg_deny: list[str] = []
    agg_hooks: dict[str, list] = {}

    for s in hook_settings_list:
        perms = s.get("permissions", {})
        if isinstance(perms, dict):
            for p in perms.get("allow", []):
                if isinstance(p, str):
                    agg_allow.append(p)
            for p in perms.get("deny", []):
                if isinstance(p, str):
                    agg_deny.append(p)
        raw_hooks = s.get("hooks", {})
        if isinstance(raw_hooks, dict):
            for event, groups in raw_hooks.items():
                if isinstance(groups, list):
                    agg_hooks.setdefault(event, []).extend(groups)

    result = dict(workspace_settings)

    ws_perms = workspace_settings.get("permissions", {})
    ws_allow = list(ws_perms.get("allow", [])) if isinstance(ws_perms, dict) else []
    ws_deny = list(ws_perms.get("deny", [])) if isinstance(ws_perms, dict) else []
    merged_allow = ws_allow + [p for p in agg_allow if p not in ws_allow]
    merged_deny = ws_deny + [p for p in agg_deny if p not in ws_deny]
    if merged_allow or merged_deny:
        merged_perms: dict = {}
        if merged_allow:
            merged_perms["allow"] = merged_allow
        if merged_deny:
            merged_perms["deny"] = merged_deny
        result["permissions"] = merged_perms

    ws_hooks = workspace_settings.get("hooks", {})
    if not isinstance(ws_hooks, dict):
        ws_hooks = {}
    all_events = set(agg_hooks) | set(ws_hooks)
    if all_events:
        merged_hooks: dict = {}
        for event in sorted(all_events):
            ws_ev = list(ws_hooks.get(event, []))
            h_ev = agg_hooks.get(event, [])
            merged_hooks[event] = ws_ev + h_ev
        result["hooks"] = merged_hooks

    return result


def _read_workspace_settings(workspace: Path) -> dict:
    """Read workspace/.claude/settings.json, returning {} if absent or invalid."""
    settings_path = workspace / ".claude" / "settings.json"
    if not settings_path.is_file():
        return {}
    try:
        return json.loads(settings_path.read_bytes())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}


def _write_workspace_settings(workspace: Path, settings: dict) -> None:
    """Write settings to workspace/.claude/settings.json."""
    claude_dir = workspace / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "settings.json").write_text(
        json.dumps(settings, indent=2), encoding="utf-8"
    )


PERMISSION_MODE: dict[str, str] = {
    "plan": "acceptEdits",  # "plan" would inject ExitPlanMode instructions that can't be fulfilled
    "auto": "acceptEdits",
    "ask": "default",
}

PLAN_MODE_TOOLS = "Read,Grep,Glob,Skill,Agent"
DEFAULT_TOOLS = "Read,Edit,Write,Bash,Skill,Agent"

_MODEL_CLI_NAMES: dict[str, str] = {
    "opus-4-8": "claude-opus-4-8",
    "fable-5": "claude-fable-5",
}


def _upgrade_instructions() -> str:
    if not UPGRADE_WEBHOOK_URL:
        return ""
    return (
        "# Upgrading the app\n"
        "When asked to upgrade the application:\n"
        "1. Write your completion summary and STATUS: DONE as the very last line "
        "of your text response (before any tool calls in that turn).\n"
        "2. In the same turn, run the upgrade webhook:\n\n"
        f"  curl -s -X POST {UPGRADE_WEBHOOK_URL}\n\n"
        "The container restart will kill this process immediately after the webhook "
        "fires. STATUS: DONE must already be in your output before the curl runs, "
        "or the run will be marked as crashed."
    )


def build_prompt(
    task: Task,
    user_message: str | None,
    goal_context: str | None = None,
    memory_items: list[MemoryItem] | None = None,
) -> str:
    fresh = task.claude_session_id is None
    if user_message and not fresh:
        return user_message
    msg_section = f"\n# Message\n{user_message}\n" if user_message else ""
    goal_section = f"\n# Goal Context\n{goal_context}\n" if goal_context else ""
    memory_section = ""
    if memory_items:
        lines = ["\n# Memory Context\n"]
        for item in memory_items:
            first_body_line = item.body.split("\n")[0] if item.body else ""
            detail = f": {first_body_line}" if first_body_line and first_body_line != item.title else ""
            lines.append(f"- **{item.title}** ({item.kind.value}){detail}")
        memory_section = "\n".join(lines) + "\n"
    return (
        f"You are working on task `{task.id}`.\n\n"
        f"# Title\n{task.title}\n\n"
        f"# Brief\n{task.brief}\n"
        f"{goal_section}"
        f"{memory_section}"
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
    goal_context: str | None = None,
    memory_items: list[MemoryItem] | None = None,
) -> AgentResult:
    """Spawn claude CLI for one turn of work on `task` and stream its events.

    `on_event` is awaited once per JSON event from claude's stream-json output.
    If `cancel_event` is provided and set during the run, the subprocess is
    terminated and the returned `AgentResult.stopped` is True.
    Returns once the process exits.
    """
    workspace = await workspace_for(task, space)
    prompt = build_prompt(task, user_message, goal_context, memory_items)
    permission_mode = PERMISSION_MODE.get(task.agent_mode, "acceptEdits")
    allowed_tools = PLAN_MODE_TOOLS if task.agent_mode == "plan" else DEFAULT_TOOLS

    # Mount adopted tools; merge hook settings into workspace .claude/settings.json.
    adopted = _load_adopted_dirs(task.space_id)
    adopted_dirs: list[Path] = []
    hook_settings: list[dict] = []
    for item_dir, kind in adopted:
        adopted_dirs.append(item_dir)
        if kind == "hook":
            s = _read_hook_settings(item_dir)
            if s:
                hook_settings.append(s)
    if hook_settings:
        ws_settings = _read_workspace_settings(workspace)
        _write_workspace_settings(workspace, _merge_hook_settings(hook_settings, ws_settings))

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
    ]
    for tool_dir in adopted_dirs:
        cmd += ["--add-dir", str(tool_dir)]
    cmd += [
        "--append-system-prompt",
        STATUS_CONTRACT,
        "--append-system-prompt",
        _upgrade_instructions(),
    ]
    if task.agent_model != "default":
        cli_model = _MODEL_CLI_NAMES.get(task.agent_model, task.agent_model)
        cmd += ["--model", cli_model]
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
        limit=10 * 1024 * 1024,  # 10 MB — large file reads produce >64 KB JSON lines
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
    read_error: Exception | None = None
    got_result = False

    async def handle_line(raw_line: bytes) -> None:
        nonlocal session_id, result_subtype, got_result
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            log.warning("Non-JSON line from claude: %s", line[:200])
            return

        raw_events.append(event)

        # Capture session id from system/init and final result events.
        if isinstance(event, dict):
            if event.get("type") == "system" and event.get("subtype") == "init":
                session_id = event.get("session_id") or session_id
            elif event.get("type") == "result":
                session_id = event.get("session_id") or session_id
                result_subtype = event.get("subtype") or result_subtype
                got_result = True

        # Extract assistant text blocks for our final_text accumulation.
        text = _extract_assistant_text(event)
        if text:
            final_text_parts.append(text)

        await on_event(event)

    # claude emits exactly one terminal `result` event and then exits, so we
    # stop reading as soon as we see it rather than waiting for stdout to reach
    # EOF. A Bash tool may have spawned a background process (dev server,
    # docker compose, uvicorn) that inherited claude's stdout pipe; that orphan
    # keeps the pipe open after claude itself exits, so waiting for EOF would
    # block forever and strand the task in ACTIVE. Each read is also raced
    # against process exit to cover a crash that never emits `result`.
    exited: asyncio.Task[int] = asyncio.ensure_future(proc.wait())
    try:
        while True:
            line_fut: asyncio.Task[bytes] = asyncio.ensure_future(proc.stdout.readline())
            done, _ = await asyncio.wait(
                {line_fut, exited}, return_when=asyncio.FIRST_COMPLETED
            )
            if line_fut in done:
                raw_line = line_fut.result()
                if not raw_line:
                    break  # genuine stdout EOF
                await handle_line(raw_line)
                if got_result:
                    break
                continue
            # Process exited before the next line arrived. Drain whatever is
            # still buffered in the pipe (bounded), then stop — never block on
            # EOF that a leaked background child may be holding off.
            while True:
                try:
                    raw_line = await asyncio.wait_for(line_fut, timeout=0.5)
                except asyncio.TimeoutError:
                    break
                except Exception:
                    break
                if not raw_line:
                    break
                await handle_line(raw_line)
                if got_result:
                    break
                line_fut = asyncio.ensure_future(proc.stdout.readline())
            break
    except Exception as exc:
        read_error = exc
        log.error("Error reading claude stdout for task %s: %s", task.id, exc)
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    finally:
        if not exited.done():
            try:
                await asyncio.wait_for(asyncio.shield(exited), timeout=10)
            except asyncio.TimeoutError:
                log.warning("claude did not exit after run for %s; killing", task.id)
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
        exit_code = await exited
        cancel_task.cancel()
        try:
            await cancel_task
        except (asyncio.CancelledError, Exception):
            pass
        # Bound the stderr drain too: a leaked background child can hold the
        # stderr pipe open, so don't wait on its EOF indefinitely.
        try:
            await asyncio.wait_for(asyncio.shield(stderr_task), timeout=2)
        except asyncio.TimeoutError:
            stderr_task.cancel()
            try:
                await stderr_task
            except (asyncio.CancelledError, Exception):
                pass

    if read_error is not None:
        raise read_error

    stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")[-2000:]

    final_text = "\n\n".join(final_text_parts).strip()
    status, context = parse_status(final_text)
    # Fallback: if the concatenated text buries an earlier STATUS marker, try
    # parsing just the last turn's text in isolation.
    if status is None and final_text_parts:
        status, context = parse_status(final_text_parts[-1])
    # Second fallback: scan all turns in reverse so a STATUS marker from turn N
    # is not lost when later turns pushed it outside the 10-line scan window.
    if status is None and len(final_text_parts) > 1:
        for turn_text in reversed(final_text_parts[:-1]):
            status, context = parse_status(turn_text)
            if status is not None:
                break

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
