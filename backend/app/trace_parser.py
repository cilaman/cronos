from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Read-only tool heuristic — used to compute exploration_ratio
# ---------------------------------------------------------------------------

_READ_TOOLS = frozenset({"Read", "Grep", "Glob", "WebFetch", "WebSearch"})

_BASH_READ_PREFIXES = (
    "cat ", "head ", "tail ", "find ", "ls ", "wc ", "diff ",
    "git log", "git show", "git diff", "git status",
)


def _is_read_tool(name: str, input_summary: str) -> bool:
    if name in _READ_TOOLS:
        return True
    if name == "Bash":
        cmd = input_summary.lstrip("{").lstrip('"command"').lstrip('"').lstrip(":").strip()
        try:
            parsed = json.loads(input_summary) if input_summary.startswith("{") else {}
            cmd = parsed.get("command", input_summary)
        except Exception:
            cmd = input_summary
        cmd = cmd.lstrip()
        return any(cmd.startswith(p) for p in _BASH_READ_PREFIXES)
    return False


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[:n] + "…"


def _summarize_input(inp: Any) -> str:
    if isinstance(inp, str):
        return _truncate(inp, 500)
    try:
        return _truncate(json.dumps(inp, ensure_ascii=False), 500)
    except Exception:
        return _truncate(str(inp), 500)


_MEMORY_FILE_RE = re.compile(r"[/\\]memory[/\\]([^/\\]+\.md)$")
_FILE_PATH_RE = re.compile(r'"file_path"\s*:\s*"([^"]+)"')

_MEMORY_READ_TOOLS = frozenset({"Read"})
_MEMORY_WRITE_TOOLS = frozenset({"Write", "Edit"})


def _adopted_name_from_tool(name: str, inp: Any) -> str | None:
    """Return the adopted tool/skill name from a Skill or Agent invocation input."""
    if not isinstance(inp, dict):
        return None
    if name == "Skill":
        return inp.get("skill") or None
    if name == "Agent":
        return inp.get("subagent_type") or None
    return None


def _memory_slug(path: str) -> str | None:
    """Return the filename if path points to a memory file, else None."""
    m = _MEMORY_FILE_RE.search(path)
    return m.group(1) if m else None


def _summarize_output(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return _truncate(content, 1000)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return _truncate("\n".join(parts), 1000)
    try:
        return _truncate(json.dumps(content, ensure_ascii=False), 1000)
    except Exception:
        return _truncate(str(content), 1000)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ToolCallTrace(BaseModel):
    tool_call_index: int
    tool_use_id: str
    name: str
    input_summary: str
    output_summary: str | None = None
    is_error: bool = False
    turn_index: int
    elapsed_seconds: float | None = None
    adopted_tool_id: str | None = None
    adopted_tool_kind: str | None = None


class AssistantTurnTrace(BaseModel):
    turn_index: int
    text_snippet: str
    has_thinking: bool
    tool_calls: list[str] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


class RunTrace(BaseModel):
    task_id: str
    space_id: str
    run_index: int
    session_id: str | None
    model: str
    real_model: str | None = None
    mode: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    exit_reason: str
    turns: list[AssistantTurnTrace] = Field(default_factory=list)
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)
    # Summary signals
    total_tool_calls: int = 0
    unique_tools: list[str] = Field(default_factory=list)
    error_tool_calls: int = 0
    read_tool_calls: int = 0
    write_tool_calls: int = 0
    exploration_ratio: float = 0.0
    error_recovery_count: int = 0
    backtrack_count: int = 0
    final_text_snippet: str = ""
    had_crash: bool = False
    # Memory tracking
    memory_injected: list[str] = Field(default_factory=list)
    memory_used: list[str] = Field(default_factory=list)
    memory_written: list[str] = Field(default_factory=list)
    memory_hit_rate: float = 0.0
    # Harness linkage — set when this run was spawned from inside a harness
    parent_run_id: str | None = None


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def extract_run_trace(
    raw_events: list[dict[str, Any]],
    *,
    task_id: str,
    space_id: str,
    run_index: int,
    model: str,
    mode: str,
    started_at: datetime,
    ended_at: datetime,
    exit_reason: str,
    session_id: str | None,
    had_crash: bool,
    memory_injected: list[str] | None = None,
    adopted_index: dict[str, tuple[str, str]] | None = None,
    parent_run_id: str | None = None,
) -> RunTrace:
    """Parse stream-json events into a structured RunTrace."""
    turns: list[AssistantTurnTrace] = []
    tool_calls: list[ToolCallTrace] = []

    # Map tool_use_id -> index in tool_calls for result matching
    id_to_index: dict[str, int] = {}

    tool_call_index = 0
    turn_index = 0
    final_text = ""
    real_model: str | None = None

    # Track unique tools in appearance order
    seen_tools: list[str] = []
    seen_tools_set: set[str] = set()

    for event in raw_events:
        if not isinstance(event, dict):
            continue
        etype = event.get("type")

        if etype == "system" and event.get("subtype") == "init":
            session_id = event.get("session_id") or session_id

        elif etype == "assistant":
            msg = event.get("message") or {}
            if real_model is None:
                real_model = msg.get("model") or None
            usage = msg.get("usage") or {}
            content = msg.get("content") or []

            text_parts: list[str] = []
            has_thinking = False
            turn_tool_ids: list[str] = []

            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(block.get("text", ""))
                    elif btype == "thinking":
                        has_thinking = True
                    elif btype == "tool_use":
                        tool_use_id = str(block.get("id") or f"_{tool_call_index}")
                        name = str(block.get("name") or "unknown")
                        inp = block.get("input")
                        input_summary = _summarize_input(inp)

                        if name not in seen_tools_set:
                            seen_tools.append(name)
                            seen_tools_set.add(name)

                        adopted_tool_id: str | None = None
                        adopted_tool_kind: str | None = None
                        if adopted_index:
                            adopted_name = _adopted_name_from_tool(name, inp)
                            if adopted_name is not None:
                                entry = adopted_index.get(adopted_name)
                                if entry is not None:
                                    adopted_tool_id, adopted_tool_kind = entry

                        tc = ToolCallTrace(
                            tool_call_index=tool_call_index,
                            tool_use_id=tool_use_id,
                            name=name,
                            input_summary=input_summary,
                            turn_index=turn_index,
                            adopted_tool_id=adopted_tool_id,
                            adopted_tool_kind=adopted_tool_kind,
                        )
                        id_to_index[tool_use_id] = len(tool_calls)
                        tool_calls.append(tc)
                        turn_tool_ids.append(tool_use_id)
                        tool_call_index += 1

            full_text = "\n".join(text_parts)
            final_text = full_text  # keep updating; last non-empty wins
            turn = AssistantTurnTrace(
                turn_index=turn_index,
                text_snippet=_truncate(full_text, 2000),
                has_thinking=has_thinking,
                tool_calls=turn_tool_ids,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            )
            turns.append(turn)
            turn_index += 1

        elif etype == "user":
            msg = event.get("message") or {}
            content = msg.get("content") or []
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        tool_use_id = str(block.get("tool_use_id") or "")
                        is_error = bool(block.get("is_error"))
                        result_content = block.get("content")
                        output_summary = _summarize_output(result_content)
                        idx = id_to_index.get(tool_use_id)
                        if idx is not None:
                            tc = tool_calls[idx]
                            tool_calls[idx] = tc.model_copy(update={
                                "output_summary": output_summary,
                                "is_error": is_error,
                            })

        elif etype == "result":
            session_id = event.get("session_id") or session_id

    # ---------------------------------------------------------------------------
    # Compute quality signals
    # ---------------------------------------------------------------------------
    total = len(tool_calls)
    error_count = sum(1 for tc in tool_calls if tc.is_error)
    read_count = sum(
        1 for tc in tool_calls if _is_read_tool(tc.name, tc.input_summary)
    )
    write_count = total - read_count

    exploration_ratio = round(read_count / total, 3) if total else 0.0

    # error_recovery_count: (error → same tool name → success) subsequences
    recovery_count = 0
    for i in range(len(tool_calls) - 1):
        if tool_calls[i].is_error:
            for j in range(i + 1, min(i + 4, len(tool_calls))):
                if (
                    tool_calls[j].name == tool_calls[i].name
                    and not tool_calls[j].is_error
                ):
                    recovery_count += 1
                    break

    # backtrack_count: write → read-same-file within 3 steps
    backtrack_count = 0
    for i, tc in enumerate(tool_calls):
        if _is_read_tool(tc.name, tc.input_summary):
            continue
        # tc is a write; check if any of the next 3 calls reads the same path
        try:
            write_path = json.loads(tc.input_summary).get("file_path", "") if tc.input_summary.startswith("{") else ""
        except Exception:
            write_path = ""
        if not write_path:
            continue
        for j in range(i + 1, min(i + 4, len(tool_calls))):
            next_tc = tool_calls[j]
            if _is_read_tool(next_tc.name, next_tc.input_summary) and write_path in next_tc.input_summary:
                backtrack_count += 1
                break

    # Compute memory tracking fields
    mem_used: list[str] = []
    mem_written: list[str] = []
    seen_mem_used: set[str] = set()
    seen_mem_written: set[str] = set()
    for tc in tool_calls:
        m = _FILE_PATH_RE.search(tc.input_summary)
        if not m:
            continue
        slug = _memory_slug(m.group(1))
        if not slug:
            continue
        if tc.name in _MEMORY_READ_TOOLS and slug not in seen_mem_used:
            mem_used.append(slug)
            seen_mem_used.add(slug)
        elif tc.name in _MEMORY_WRITE_TOOLS and slug not in seen_mem_written:
            mem_written.append(slug)
            seen_mem_written.add(slug)

    return RunTrace(
        task_id=task_id,
        space_id=space_id,
        run_index=run_index,
        session_id=session_id,
        model=model,
        real_model=real_model,
        mode=mode,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=round((ended_at - started_at).total_seconds(), 2),
        exit_reason=exit_reason,
        turns=turns,
        tool_calls=tool_calls,
        total_tool_calls=total,
        unique_tools=seen_tools,
        error_tool_calls=error_count,
        read_tool_calls=read_count,
        write_tool_calls=write_count,
        exploration_ratio=exploration_ratio,
        error_recovery_count=recovery_count,
        backtrack_count=backtrack_count,
        final_text_snippet=_truncate(final_text, 500),
        had_crash=had_crash,
        memory_injected=memory_injected or [],
        memory_used=mem_used,
        memory_written=mem_written,
        memory_hit_rate=min(1.0, len(mem_used) / max(1, len(memory_injected or []))),
        parent_run_id=parent_run_id,
    )
