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

# ---------------------------------------------------------------------------
# node_status envelope transport parser (R1 / D6)
# ---------------------------------------------------------------------------
# Deliberate, documented duplication of the package-side parser
# (delivery_workflow.lib.node_status): trace_parser stays dependency-free of
# the delivery-workflow package so every backend entry point can parse traces
# without pulling in workflow machinery (R1 documented decision; the package
# is now a real installed distribution, so this is a coupling choice, not a
# sys.path constraint). Transport-only: it returns the raw fence dict
# and does not validate the status vocabulary — the vocabulary is closed at
# the adapter boundary (CronosAdapter.dispatchAgent), never here.

_STATUS_FENCE_RE = re.compile(
    r"```(?:node_status|delivery_status)\s*\n(.*?)```",
    re.DOTALL,
)

# Strict variant for the turn-tolerance surfaces (earlier assistant turns,
# Write tool content): current agents are taught ``node_status`` only — a
# legacy ``delivery_status`` fence on those surfaces can only be a quote of
# ANOTHER run's output and must never classify this run.
_NODE_STATUS_FENCE_RE = re.compile(
    r"```node_status\s*\n(.*?)```",
    re.DOTALL,
)


def parse_node_status_fence(text: str) -> dict[str, Any] | None:
    """Return the last complete node_status/delivery_status fenced envelope.

    Scans *text* for fenced blocks named ``node_status`` (preferred, emitted
    by workflow agents) or ``delivery_status`` (legacy CC-v1). The **last**
    complete fence wins — agents write prose first and the fence last.
    Returns ``None`` when no fence is present or the winning fence is not
    valid JSON / not a JSON object.
    """
    matches = _STATUS_FENCE_RE.findall(text or "")
    if not matches:
        return None
    try:
        data = json.loads(matches[-1].strip())
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def final_assistant_text(raw_events: list[dict[str, Any]]) -> str:
    """Return the FULL text of the last non-empty assistant turn.

    Kept for ``final_text_snippet`` (UI) and non-delivery callers.  The
    node_status envelope is selected by ``parse_node_status_from_events``
    below, which is turn-tolerant instead of final-message-only.

    Tool-only turns produce no text and never overwrite an earlier non-empty
    turn ("last non-empty wins").
    """
    final = ""
    for event in raw_events or []:
        if not isinstance(event, dict) or event.get("type") != "assistant":
            continue
        msg = event.get("message") or {}
        content = msg.get("content") or []
        if not isinstance(content, list):
            continue
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        text = "\n".join(parts)
        if text.strip():
            final = text
    return final


def _trailing_fence_envelope(content: Any) -> dict[str, Any] | None:
    """Return the envelope when *content* ENDS with a complete node_status fence.

    The strict matcher for the turn-tolerance surfaces (earlier assistant
    turns, Write tool content).  Only a ``node_status`` fence at the very
    tail counts (trailing whitespace allowed after the closing backticks) —
    a fence quoted mid-text (the brief's contract example restated in a
    planning turn, a MEMORY.md citing it, a 4-backtick quote block) is never
    credited, and neither is a legacy ``delivery_status`` fence (only ever
    seen quoted from OTHER runs' output on these surfaces).
    """
    if not isinstance(content, str):
        return None
    matches = list(_NODE_STATUS_FENCE_RE.finditer(content))
    if not matches:
        return None
    last = matches[-1]
    if last.end() != len(content.rstrip()):
        return None
    try:
        data = json.loads(last.group(1).strip())
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _envelope_references_path(envelope: dict[str, Any], file_path: Any) -> bool:
    """True when the envelope's ``artifact_paths`` names *file_path* itself.

    Segment-boundary suffix match in either direction: agents Write with
    absolute paths but list workspace-relative artifact paths (or vice
    versa).
    """
    if not isinstance(file_path, str):
        return False
    written = file_path.strip().removeprefix("./")
    if not written:
        return False
    paths = envelope.get("artifact_paths")
    if not isinstance(paths, list):
        return False
    for entry in paths:
        if not isinstance(entry, str):
            continue
        listed = entry.strip().removeprefix("./")
        if not listed:
            continue
        if (
            written == listed
            or written.endswith("/" + listed)
            or listed.endswith("/" + written)
        ):
            return True
    return False


def parse_node_status_from_events(
    raw_events: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    """Select the run's node_status envelope from the full event stream.

    Returns ``(envelope, transport)`` where transport is ``'assistant_text'``,
    ``'written_artifact'`` or ``None``.  Single selection rule shared by
    ``extract_run_trace`` (``RunTrace.node_status``) and the delivery child
    finalization (Kanban state, D13) — the two consumers can never disagree
    about which envelope classifies the run.

    LLM fence compliance is probabilistic: trailing housekeeping turns
    (memory compaction, git finalization) routinely push the fence out of
    the FINAL assistant message, so selection is turn-tolerant.  Tolerance
    must not credit fences the main agent never genuinely emitted, so
    sidechain events (``parent_tool_use_id`` set — Task-tool subagents
    interleaved into stream-json) are skipped entirely, and the channels
    apply in precedence order:

    1. ``'assistant_text'``, final turn — the last fence anywhere in the
       last non-empty main-thread turn, legacy ``delivery_status`` accepted:
       identical to the old final-text selection.
    2. ``'assistant_text'``, earlier turns — the LAST earlier turn that ENDS
       with a ``node_status`` fence.  The tail anchor and the node_status-only
       name reject the brief's contract example restated in planning turns
       and fences quoted from OTHER runs' output — both inert under
       final-turn-only selection, so they must stay inert here.
    3. ``'written_artifact'`` — the LAST Write tool input whose content ENDS
       with a ``node_status`` fence whose ``artifact_paths`` names the
       written file itself.  Role definitions teach agents to end their
       artifact with the fence and to list every produced file, so a genuine
       artifact tail is self-referencing — a memory/doc note that merely
       quotes the contract example (empty ``artifact_paths``) is not.  The
       content is agent-authored in THIS run's event stream, so there is no
       cross-run misattribution (the R1 sin was crediting OTHER runs' files
       via filesystem mtime scans — this reads only the transcript, never
       the filesystem).  Edit inputs are never considered (fragment risk).
    """
    turn_texts: list[str] = []
    artifact_envelope: dict[str, Any] | None = None
    for event in raw_events or []:
        if not isinstance(event, dict) or event.get("type") != "assistant":
            continue
        if event.get("parent_tool_use_id"):
            continue
        msg = event.get("message") or {}
        content = msg.get("content") or []
        if not isinstance(content, list):
            continue
        text_parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                text_parts.append(block.get("text", ""))
            elif btype == "tool_use" and block.get("name") == "Write":
                inp = block.get("input")
                if isinstance(inp, dict):
                    candidate = _trailing_fence_envelope(inp.get("content"))
                    if candidate is not None and _envelope_references_path(
                        candidate, inp.get("file_path")
                    ):
                        artifact_envelope = candidate
        text = "\n".join(text_parts)
        if text.strip():
            turn_texts.append(text)
    if turn_texts:
        envelope = parse_node_status_fence(turn_texts[-1])
        if envelope is not None:
            return envelope, "assistant_text"
        for text in reversed(turn_texts[:-1]):
            envelope = _trailing_fence_envelope(text)
            if envelope is not None:
                return envelope, "assistant_text"
    if artifact_envelope is not None:
        return artifact_envelope, "written_artifact"
    return None, None

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
    # R1 (D6): structured node_status/delivery_status envelope selected by
    # parse_node_status_from_events (turn-tolerant with quoted-example and
    # sidechain guards: final turn, else a fence ENDING an earlier main-thread
    # turn, else a self-referencing fence ENDING Write tool content) — the
    # single classification channel for delivery-workflow nodes. None when
    # the agent emitted no (valid) fence. final_text_snippet above stays a UI
    # nicety and is never load-bearing for classification.
    node_status: dict[str, Any] | None = None
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

    # Final text: FULL text of the last non-empty assistant turn ("last
    # non-empty wins" — the previous inline tracking overwrote with EMPTY when
    # the last turn was tool-only, R1 latent-bug fix). UI snippet only — the
    # node_status envelope is selected turn-tolerantly from the whole event
    # stream by parse_node_status_from_events, so a fence emitted in an
    # earlier turn (or at the tail of a Written artifact) survives trailing
    # housekeeping turns and snippet truncation (D6).
    final_text = final_assistant_text(raw_events)

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
        final_text_snippet=_truncate(final_text, 2000),
        had_crash=had_crash,
        node_status=parse_node_status_from_events(raw_events)[0],
        memory_injected=memory_injected or [],
        memory_used=mem_used,
        memory_written=mem_written,
        memory_hit_rate=min(1.0, len(mem_used) / max(1, len(memory_injected or []))),
        parent_run_id=parent_run_id,
    )
