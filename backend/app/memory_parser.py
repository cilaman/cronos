from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import yaml

_VALID_KINDS = frozenset({"fact", "procedure", "observation", "reference"})

_MEMORY_LINE = re.compile(
    r"^\s*MEMORY(?:\[([a-z]+)\])?:\s*(.+)",
    re.IGNORECASE,
)
_FENCE_OPEN = re.compile(r"^```memory(?:\s+([a-z]+))?\s*$", re.IGNORECASE)
_FENCE_CLOSE = re.compile(r"^```\s*$")


@dataclass
class MemoryBlock:
    content: str
    kind_hint: str | None = None  # "fact", "procedure", "observation", "reference", or None


def _normalize_kind(raw: str | None) -> str | None:
    if raw and raw.lower() in _VALID_KINDS:
        return raw.lower()
    return None


def parse_memory_blocks(text: str) -> list[MemoryBlock]:
    """Parse MEMORY: markers and ```memory fenced blocks from agent output.

    Supported inline formats:
        MEMORY: <content>
        MEMORY[fact]: <content>
        MEMORY[procedure]: <content>
        MEMORY[observation]: <content>
        MEMORY[reference]: <content>

    Supported fenced formats:
        ```memory
        <multi-line content>
        ```
        ```memory procedure
        <multi-line content>
        ```

    Blocks are returned in document order. Unknown kind hints are treated as None.
    """
    if not text:
        return []

    blocks: list[MemoryBlock] = []
    lines = text.splitlines()
    in_fence = False
    fence_kind: str | None = None
    fence_content_lines: list[str] = []

    for line in lines:
        if not in_fence:
            m = _FENCE_OPEN.match(line)
            if m:
                in_fence = True
                fence_kind = _normalize_kind(m.group(1))
                fence_content_lines = []
                continue
            m = _MEMORY_LINE.match(line)
            if m:
                kind_hint = _normalize_kind(m.group(1))
                content = m.group(2).strip()
                if content:
                    blocks.append(MemoryBlock(content=content, kind_hint=kind_hint))
        else:
            if _FENCE_CLOSE.match(line):
                in_fence = False
                content = "\n".join(fence_content_lines).strip()
                if content:
                    blocks.append(MemoryBlock(content=content, kind_hint=fence_kind))
            else:
                fence_content_lines.append(line)

    return blocks


_DS_FENCE_OPEN = re.compile(r"^```delivery_status\s*$", re.IGNORECASE)


def parse_delivery_status_block(text: str) -> dict | None:
    """Parse the first ```delivery_status fenced JSON block from agent output.

    Returns the parsed dict if found and valid JSON, None otherwise.
    Tolerates missing optional fields; does NOT validate the ``status`` value
    against the ``{DONE, WAIT, BLOCKED}`` set — all string values are accepted.
    If ``status`` is present it is normalised to lowercase for consistent scope
    key comparisons (``scope["<node>.status"] = "done"``).

    Silently skips blocks that are unclosed or contain malformed JSON.
    Only the first well-formed block is returned.
    """
    if not text:
        return None

    lines = text.splitlines()
    in_fence = False
    fence_lines: list[str] = []

    for line in lines:
        if not in_fence:
            if _DS_FENCE_OPEN.match(line):
                in_fence = True
                fence_lines = []
        else:
            if _FENCE_CLOSE.match(line):
                try:
                    data = json.loads("\n".join(fence_lines))
                except (json.JSONDecodeError, ValueError):
                    return None
                if not isinstance(data, dict):
                    return None
                # Normalise status to lowercase for scope-key comparisons.
                if "status" in data and isinstance(data["status"], str):
                    data["status"] = data["status"].lower()
                return data
            else:
                fence_lines.append(line)

    return None


_NS_FENCE_OPEN = re.compile(r"^```node_status\s*$", re.IGNORECASE)


def parse_node_status_block(text: str) -> tuple[str | None, str | None]:
    """Parse the first ```node_status fenced JSON block from agent output.

    Mirrors ``parse_delivery_status_block`` exactly: lenient on extra fields,
    lowercases the ``status`` field, returns ``summary`` only when it is a
    string.  Returns ``(status_lower, summary)`` on success or ``(None, None)``
    on missing block, unclosed fence, or malformed JSON.

    Schema assumption: ``{"status": "<value>", "summary": "<optional>", ...}``.
    No ``node_id`` or other field is required at the bridge boundary.  Unknown
    extra fields are silently ignored — keeping the parser forward-compatible
    with future producer changes.
    """
    if not text:
        return None, None

    lines = text.splitlines()
    in_fence = False
    fence_lines: list[str] = []

    for line in lines:
        if not in_fence:
            if _NS_FENCE_OPEN.match(line):
                in_fence = True
                fence_lines = []
        else:
            if _FENCE_CLOSE.match(line):
                try:
                    data = json.loads("\n".join(fence_lines))
                except (json.JSONDecodeError, ValueError):
                    return None, None
                if not isinstance(data, dict):
                    return None, None
                status = data.get("status")
                if not isinstance(status, str):
                    return None, None
                # Normalise to lowercase — defensive double-normalise mirrors
                # parse_delivery_status_block (line 122-123).
                status = status.lower()
                summary = data.get("summary")
                if not isinstance(summary, str):
                    summary = None
                return status, summary
            else:
                fence_lines.append(line)

    return None, None


_CR_FENCE_OPEN = re.compile(r"^```cronos_remember\s*$", re.IGNORECASE)

_CS_FENCE_OPEN = re.compile(r"^```cronos_status\s*$", re.IGNORECASE)
_VALID_STATUSES = frozenset({"DONE", "WAIT", "BLOCKED"})


@dataclass
class CronosRememberBlock:
    name: str
    type: str
    description: str
    body: str = ""
    metadata: dict = field(default_factory=dict)


def parse_cronos_status_block(text: str) -> tuple[str | None, str | None]:
    """Parse the first ```cronos_status fenced JSON block from agent output.

    Returns (status_str, summary) where status_str is one of 'DONE', 'WAIT',
    'BLOCKED' and summary is the optional summary string (or None). Returns
    (None, None) if no valid block is found.

    Silently skips blocks that are unclosed, have malformed JSON, are missing
    the required 'status' field, or have an unknown status value.
    The payload is parsed via json.loads (not yaml.safe_load).
    The optional 'artifacts' field is accepted but not returned.
    """
    if not text:
        return None, None

    lines = text.splitlines()
    in_fence = False
    fence_lines: list[str] = []

    for line in lines:
        if not in_fence:
            if _CS_FENCE_OPEN.match(line):
                in_fence = True
                fence_lines = []
        else:
            if _FENCE_CLOSE.match(line):
                try:
                    data = json.loads("\n".join(fence_lines))
                except (json.JSONDecodeError, ValueError):
                    return None, None
                if not isinstance(data, dict):
                    return None, None
                status = data.get("status")
                if not isinstance(status, str) or status not in _VALID_STATUSES:
                    return None, None
                summary = data.get("summary")
                if not isinstance(summary, str):
                    summary = None
                return status, summary
            else:
                fence_lines.append(line)

    return None, None


def parse_cronos_remember_blocks(text: str) -> list[CronosRememberBlock]:
    """Parse CRONOS_REMEMBER fenced blocks from agent output.

    Blocks are returned in document order. Silently skips blocks that are
    unclosed, have malformed YAML, are missing required fields (name, type,
    description), or have an unknown type value.
    """
    if not text:
        return []

    blocks: list[CronosRememberBlock] = []
    lines = text.splitlines()
    in_fence = False
    fence_lines: list[str] = []

    for line in lines:
        if not in_fence:
            if _CR_FENCE_OPEN.match(line):
                in_fence = True
                fence_lines = []
        else:
            if _FENCE_CLOSE.match(line):
                in_fence = False
                try:
                    data = yaml.safe_load("\n".join(fence_lines))
                except Exception:
                    continue
                if not isinstance(data, dict):
                    continue
                name = data.get("name")
                cr_type = data.get("type")
                description = data.get("description")
                if not (
                    isinstance(name, str) and name.strip()
                    and isinstance(cr_type, str) and cr_type.lower() in _VALID_KINDS
                    and isinstance(description, str) and description.strip()
                ):
                    continue
                body = data.get("body", "")
                if not isinstance(body, str):
                    body = ""
                metadata = data.get("metadata", {})
                if not isinstance(metadata, dict):
                    metadata = {}
                blocks.append(CronosRememberBlock(
                    name=name[:120],
                    type=cr_type.lower(),
                    description=description.strip(),
                    body=body,
                    metadata=metadata,
                ))
            else:
                fence_lines.append(line)

    return blocks
