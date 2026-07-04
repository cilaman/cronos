from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import signal
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from . import git_ops
from .logging_config import bind_run_context
from .memory_parser import (
    parse_cronos_status_block,
    parse_delivery_status_block,
    parse_node_status_block,
)
from .models import MemoryItem, Space, Task

log = logging.getLogger("cronos.agent")

DATA_DIR = Path(os.environ.get("CRONOS_DATA_DIR", "/data"))
CRONOS_SUBDIR = ".cronos"

UPGRADE_WEBHOOK_URL = os.environ.get("UPGRADE_WEBHOOK_URL", "")

# Global cap on concurrent claude CLI subprocesses across every space worker.
# Each run (Opus + bundled Node + any test subprocess it spawns) is memory-heavy;
# without a ceiling, N active spaces stack N processes against the container's
# cgroup memory limit and trip the OOM-killer (agent exit -9 / SIGKILL). All
# workers share one backend process/event loop, so a module-level semaphore is
# shared across them. Tune per-VPS via CRONOS_MAX_CONCURRENT_AGENTS.
_MAX_CONCURRENT_AGENTS = max(1, int(os.environ.get("CRONOS_MAX_CONCURRENT_AGENTS", "2")))
_AGENT_SLOTS = asyncio.Semaphore(_MAX_CONCURRENT_AGENTS)

# V8 old-space heap ceiling (MB) for the bundled Node CLI. Defense-in-depth only:
# a cgroup OOM is driven by total RSS (much of it off-heap, plus the separate
# pytest process), so this guards against unbounded heap growth but does NOT by
# itself prevent a -9. Keep it generous; never set it aggressively low.
_NODE_MAX_OLD_SPACE_MB = os.environ.get("CRONOS_NODE_MAX_OLD_SPACE_MB", "2048")

# The {long_job_signal} placeholder names each contract's own completion
# signal for the too-long-for-one-turn case: a `WAIT` status block would be
# outside the delivery node_status vocabulary and classify the node failed
# (unknown_status:wait), so the delivery variant must say "blocked" instead.
_ONE_SHOT_PREAMBLE = """You are an autonomous task executor. The user is not watching in real time.

## One-shot turn — no background work, no scheduled wakeups

Each turn runs as a single one-shot process. When the turn ends the process exits;
there is NO mechanism to wake you when a background job finishes. Therefore:

- Run tests, builds, and servers **synchronously in the foreground** and wait for them.
- **Never** use Bash `run_in_background` (or `&` / `nohup` / `disown` / `setsid`) for
  work whose result you need, and then end the turn — the child is orphaned, nothing
  reaps it, and the task hangs in WAITING forever waiting on a process nobody watches.
- Long suites are fine in the foreground (the Bash timeout is raised for this). If a
  job is genuinely too long for one turn, finish what you can and {long_job_signal}
  describing the remaining step — do NOT background it and exit.

"""

_CRONOS_FINISH = """## How to finish a task

When all work is complete, invoke the **task-finalize** skill as your last action:

  /task-finalize

This skill handles git, memory writing, and the STATUS marker in the correct order.
Do NOT write the completion block manually — task-finalize does it.

### Completion signal format

Emit a fenced JSON block as your final output. This is the **primary** completion signal:

```cronos_status
{"status": "DONE", "summary": "Brief description of what was accomplished."}
```

For WAIT (need user input before continuing):
```cronos_status
{"status": "WAIT", "summary": "What you need from the user."}
```

For BLOCKED (cannot proceed):
```cronos_status
{"status": "BLOCKED", "summary": "What is blocking you and why."}
```

Fields:
- `status`: required — one of `DONE`, `WAIT`, `BLOCKED` (uppercase)
- `summary`: optional string — brief description (used as waiting question / blocker reason)
- `artifacts`: optional list — file paths produced (reserved for future use)

Rules:
- The `cronos_status` block must appear after all tool calls are done.
- Emit it only once per response.
- Do NOT wrap it in additional markdown formatting.
- **Always end a turn with a status block — even on partial completion.** If work
  remains, emit `WAIT` summarizing what is done and what is left; never end silently
  (a turn with no marker parks the task and, absent a human, wastes a resume cycle).
- Turn limit approaching: emit STATUS WAIT block describing what's done and what remains.
- Plan mode: emit WAIT block and ask "Shall I implement this plan?"

### [DEPRECATED fallback — only if task-finalize fails AND the block format is unavailable]

The bare `STATUS:` line form is deprecated and will be removed in a future version.
Use it only as a last resort when the fenced block cannot be emitted:

  MEMORY[fact]: <what was accomplished>
  STATUS: DONE

  STATUS: WAIT   (if waiting for user input — question on the line above)
  STATUS: BLOCKED   (if blocked — reason on the line above)

Deprecated rules:
- STATUS must be the VERY LAST LINE. No text after it.
- Write STATUS only once.
- Do NOT use markdown formatting: write STATUS: DONE not **STATUS: DONE**
"""

STATUS_CONTRACT = (
    _ONE_SHOT_PREAMBLE.format(long_job_signal="emit a `WAIT` status block")
    + _CRONOS_FINISH
)

_DELIVERY_FINISH = """## How to finish a delivery node

You are executing ONE node of a delivery workflow. Your completion signal is a
fenced `node_status` JSON block emitted as the LAST thing in your final
message, exactly once:

```node_status
{"status": "done", "artifact_paths": [], "produces": "<artifact class>", "fields": {}, "open_questions": []}
```

`status` MUST be one of:
- `done` — work complete and the artifact written.
- `needs_fix` — a judged artifact needs another fix round (verdict fields route the loop).
- `blocked` — you need a human decision or input; put the question in `open_questions`.
- `failed` — unrecoverable.

Rules:
- List every file you created or modified in `artifact_paths`.
- Do NOT invoke /task-finalize and do NOT emit a `cronos_status` block — the
  `node_status` fence replaces both for this task.
- The fence must appear after all tool calls are done, only once, not wrapped
  in additional markdown formatting.
"""

DELIVERY_NODE_CONTRACT = (
    _ONE_SHOT_PREAMBLE.format(
        long_job_signal='emit a `node_status` fence with status "blocked" '
        "and an `open_questions` entry"
    )
    + _DELIVERY_FINISH
)


class Status(str, Enum):
    DONE = "DONE"
    WAIT = "WAIT"
    BLOCKED = "BLOCKED"


def _killpg(proc: "asyncio.subprocess.Process", sig: int) -> None:
    """Signal the child's whole process group, reaping backgrounded grandchildren.

    The claude CLI is spawned with ``start_new_session=True`` so it leads its own
    process group. A plain ``proc.kill()`` targets only the claude PID, leaving any
    process it backgrounded (pytest, a dev server) orphaned and holding the stdout
    pipe open. Killing the group reaps those too. All lookups are best-effort — a
    race where the process already exited is not an error.
    """
    try:
        pgid = os.getpgid(proc.pid)
    except Exception:
        # Best-effort: process already gone (ProcessLookupError/OSError), or a
        # test double whose .pid isn't a real int (TypeError). Never raise.
        return
    try:
        os.killpg(pgid, sig)
    except Exception:
        pass


_STATUS_LINE = re.compile(r"^\s*\*{0,3}STATUS:\s*(DONE|WAIT|BLOCKED)\*{0,3}\s*$")

_VOCAB_MAP = {
    "done": Status.DONE,
    "wait": Status.WAIT,
    "blocked": Status.BLOCKED,
    "failed": Status.BLOCKED,
    # needs_fix is context-sensitive — handled in _map_vocab
}


def _map_vocab(raw: str, is_runner_task: bool) -> Status | None:
    """Map a 5-value delivery/node vocab string to a Cronos Status.

    Lowercases ``raw`` first (single normalization point).  Returns None for
    any value outside the 5-vocab set so the 4-tier dispatch falls through to
    the next tier cleanly.

    Vocab map: done→DONE, wait→WAIT, blocked→BLOCKED, failed→BLOCKED,
    needs_fix→DONE (if is_runner_task) else BLOCKED.
    """
    lowered = raw.lower() if raw else ""
    if lowered == "needs_fix":
        # Wired (OQ-1 resolved): delivery-runner child tasks are detected in
        # _run_agent_body via the delivery-node sentinel and call parse_status
        # with is_runner_task=True, so needs_fix → DONE (routable); every other
        # task keeps needs_fix → BLOCKED.
        return Status.DONE if is_runner_task else Status.BLOCKED
    return _VOCAB_MAP.get(lowered)


def parse_status(
    text: str, *, is_runner_task: bool = False
) -> tuple[Status | None, str | None]:
    """Return (status, context_line) parsed from the agent's final text.

    4-tier precedence (first non-None Status wins):

    1. ``node_status`` fenced JSON block — new Sentinel Bridge tier; status
       mapped via ``_map_vocab``.
    2. ``cronos_status`` fenced JSON block — primary Cronos channel; status
       must be one of {DONE, WAIT, BLOCKED} (uppercase); used directly via
       ``Status(status_str)`` — NOT routed through ``_map_vocab``.
    3. ``delivery_status`` fenced JSON block — Delivery/v2 bridge tier; status
       mapped via ``_map_vocab``.
    4. Free-text ``STATUS:`` line scan — deprecated fallback; emits a warning.

    Context (waiting_question / blocker reason) is ``block.summary`` for tiers
    1–3, or the immediately preceding non-blank line for tier 4 (unchanged).

    ``is_runner_task`` (keyword-only, default False) toggles ``needs_fix``
    mapping: True → DONE (runner child task, dispatchAgent poll terminates);
    False → BLOCKED (all other tasks).  See TODO(OQ-1 sg1-sentinel-bridge) in
    ``_map_vocab`` for the deferred wiring spec.
    """
    if not text:
        return None, None

    # Tier 1: node_status block (new Sentinel Bridge channel)
    ns_status, ns_summary = parse_node_status_block(text)
    if ns_status is not None:
        mapped = _map_vocab(ns_status, is_runner_task)
        if mapped is not None:
            return mapped, ns_summary

    # Tier 2: cronos_status block (primary Cronos channel; stays untouched)
    status_str, summary = parse_cronos_status_block(text)
    if status_str is not None:
        return Status(status_str), summary

    # Tier 3: delivery_status block (Delivery/v2 bridge channel)
    ds_block = parse_delivery_status_block(text)
    if ds_block is not None:
        ds_status = ds_block.get("status")
        if isinstance(ds_status, str):
            mapped = _map_vocab(ds_status, is_runner_task)
            if mapped is not None:
                ds_summary = ds_block.get("summary")
                return mapped, ds_summary if isinstance(ds_summary, str) else None

    # Tier 4: deprecated free-text STATUS: line scan (R5 — behavior unchanged)
    lines = text.rstrip().splitlines()
    if not lines:
        return None, None
    scan_from = max(0, len(lines) - 10)
    for i in range(len(lines) - 1, scan_from - 1, -1):
        m = _STATUS_LINE.match(lines[i])
        if m:
            log.warning(
                "parse_status: free-text STATUS: line is deprecated; "
                "use a ```cronos_status fenced JSON block instead"
            )
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


def _claude_json_path() -> Path:
    """Location of the Claude CLI global config (holds auth + per-project trust)."""
    home = os.environ.get("HOME") or "/home/cronos"
    return Path(home) / ".claude.json"


def _ensure_workspace_trusted(claude_json_path: Path, dirs: list[Path]) -> None:
    """Mark each dir as a trusted project in the Claude CLI global config.

    Without this the CLI logs "this workspace has not been trusted" and silently
    ignores the workspace's .claude/settings.json permissions.allow entries — which
    starves agents of tools and stalls delivery gates. Idempotent and best-effort:
    only writes when a trust flag is missing/false, tolerates a missing/corrupt
    config, and swallows I/O errors so trust-seeding never blocks a run.
    """
    try:
        try:
            data = json.loads(claude_json_path.read_bytes())
        except FileNotFoundError:
            data = {}
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return
        if not isinstance(data, dict):
            return
        projects = data.setdefault("projects", {})
        if not isinstance(projects, dict):
            return
        changed = False
        for d in dirs:
            key = str(d)
            entry = projects.get(key)
            if not isinstance(entry, dict):
                entry = {}
                projects[key] = entry
            if entry.get("hasTrustDialogAccepted") is not True:
                entry["hasTrustDialogAccepted"] = True
                changed = True
        if not changed:
            return
        tmp = claude_json_path.with_suffix(claude_json_path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, claude_json_path)
    except OSError as exc:
        log.warning("could not seed workspace trust in %s: %s", claude_json_path, exc)


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
            lines.append(f"- **{item.title}** ({item.kind.value})")
            if item.body:
                lines.append(item.body)
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
    async with bind_run_context(run_id=task.id, task_id=task.id):
        return await _run_agent_body(
            task,
            user_message=user_message,
            on_event=on_event,
            cancel_event=cancel_event,
            space=space,
            goal_context=goal_context,
            memory_items=memory_items,
        )


async def _run_agent_body(
    task: Task,
    *,
    user_message: str | None,
    on_event: EventCallback,
    cancel_event: asyncio.Event | None = None,
    space: Space | None = None,
    goal_context: str | None = None,
    memory_items: list[MemoryItem] | None = None,
) -> AgentResult:
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

    # Trust the space root (it owns .claude/settings.json — the project key the
    # CLI actually validates against) plus the workspace and every --add-dir, so
    # the CLI honours their permissions.allow instead of silently dropping them.
    # The workspace/worktree always nests inside the space root, so the root key
    # is the one that matters; the extra entries are harmless (helper dedupes).
    _ensure_workspace_trusted(
        _claude_json_path(),
        [space_dir_for(task.space_id), workspace, *adopted_dirs],
    )

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
    # A delivery-workflow runner child task (brief carries the delivery-node
    # sentinel) finishes with a ``node_status`` fence — the only completion
    # signal the delivery classifier reads — so it gets the delivery contract
    # instead of the cronos_status one. The same flag routes needs_fix → DONE
    # in the parse_status calls below.
    is_delivery_node = "<!-- delivery-node:" in (task.brief or "")

    cmd += [
        "--append-system-prompt",
        DELIVERY_NODE_CONTRACT if is_delivery_node else STATUS_CONTRACT,
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

    # Cap the bundled Node CLI's V8 heap (defense-in-depth; see _NODE_MAX_OLD_SPACE_MB).
    # Preserve any operator-supplied NODE_OPTIONS and only add the flag if absent.
    child_env = {**os.environ}
    node_opts = child_env.get("NODE_OPTIONS", "")
    if "--max-old-space-size" not in node_opts:
        child_env["NODE_OPTIONS"] = (
            f"{node_opts} --max-old-space-size={_NODE_MAX_OLD_SPACE_MB}".strip()
        )

    # Bound how many claude subprocesses run at once across all space workers so
    # concurrent runs can't stack RSS into the cgroup OOM-killer (exit -9). The
    # slot is released in the read-loop's finally once the process has exited and
    # its pipes are drained (the memory-heavy window). Guard the spawn itself so a
    # failure to launch never leaks a slot.
    await _AGENT_SLOTS.acquire()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workspace,
            env=child_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=10 * 1024 * 1024,  # 10 MB — large file reads produce >64 KB JSON lines
            # New session/process group so any job the agent backgrounds (pytest, a
            # dev server) can be reaped as a group on kill/turn-end instead of being
            # orphaned to init and stranding the run (see _killpg).
            start_new_session=True,
        )
    except BaseException:
        _AGENT_SLOTS.release()
        raise

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
            _killpg(proc, signal.SIGTERM)
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                log.warning("claude did not exit on SIGTERM for %s; killing", task.id)
                _killpg(proc, signal.SIGKILL)
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
        _killpg(proc, signal.SIGKILL)
    finally:
        if not exited.done():
            try:
                await asyncio.wait_for(asyncio.shield(exited), timeout=10)
            except asyncio.TimeoutError:
                log.warning("claude did not exit after run for %s; killing", task.id)
                _killpg(proc, signal.SIGKILL)
        exit_code = await exited
        # The claude PID has exited; sweep the process group once more to reap any
        # job it backgrounded (pytest, a dev server) that outlived it and would
        # otherwise linger holding the pipes open (see _killpg / start_new_session).
        _killpg(proc, signal.SIGKILL)
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
        # Process has exited and its pipes are drained — release the concurrency
        # slot so a queued run can spawn. Runs exactly once (single try/finally).
        _AGENT_SLOTS.release()

    if read_error is not None:
        raise read_error

    stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")[-2000:]

    # A delivery-workflow runner child task routes ``needs_fix`` → DONE so the
    # runner can read the verdict from the artifact and loop back, rather than
    # parking the child WAITING and halting the run.  All other tasks keep
    # needs_fix → BLOCKED.
    final_text = "\n\n".join(final_text_parts).strip()
    status, context = parse_status(final_text, is_runner_task=is_delivery_node)
    # Fallback: if the concatenated text buries an earlier STATUS marker, try
    # parsing just the last turn's text in isolation.
    if status is None and final_text_parts:
        status, context = parse_status(final_text_parts[-1], is_runner_task=is_delivery_node)
    # Second fallback: scan all turns in reverse so a STATUS marker from turn N
    # is not lost when later turns pushed it outside the 10-line scan window.
    if status is None and len(final_text_parts) > 1:
        for turn_text in reversed(final_text_parts[:-1]):
            status, context = parse_status(turn_text, is_runner_task=is_delivery_node)
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
