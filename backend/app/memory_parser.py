from __future__ import annotations

import re
from dataclasses import dataclass

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
