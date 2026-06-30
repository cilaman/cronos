"""
node_status fenced-block parser.

Parses the general-purpose structured-return sentinel emitted by workflow nodes:

    ```node_status
    {
      "status": "done",
      "artifact_paths": [...],
      "produces": "research",
      "fields": {...},
      "open_questions": []
    }
    ```

This is the workflow-neutral envelope. The ``status`` field accepts any
non-empty string (lowercased on parse) — the vocabulary is open and
caller-defined.  No ``telemetry`` field is carried; this is intentional
because node_status is a general transport envelope, not a delivery-domain
artifact.  See the design notes for SG2 (sg2-node-status-general-sentinel).

App-free: imports only stdlib and no backend modules. Mirrors
lib/delivery_status.py shape minus the telemetry field.

Coexists with delivery_status.py: both parsers look for different fence
markers (``node_status`` vs ``delivery_status``).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

_FENCE_RE = re.compile(
    r"```node_status\s*\n(.*?)```",
    re.DOTALL,
)


@dataclass
class NodeStatusBlock:
    """Structured return from a node_status fenced JSON block.

    Fields:
    - status: any non-empty string, lowercased (e.g. "done", "wait", "blocked",
      "needs_fix", "failed" — or any caller-defined value).
    - artifact_paths: paths to files produced by this node.
    - produces: short descriptor of what was produced (e.g. "research").
    - fields: open dict of workflow-defined key/value pairs.
    - open_questions: unresolved items for downstream consumers.

    Intentionally omits ``telemetry``: node_status is a general transport
    envelope, not a delivery-domain artifact. Confirmed no telemetry consumer
    reads NodeStatusBlock.telemetry (grep-verified at design time).
    """

    status: str
    artifact_paths: list[str]
    produces: str
    fields: dict[str, Any]
    open_questions: list[str]


def parse_node_status(text: str) -> NodeStatusBlock | None:
    """Return the first node_status block found in *text*, or None.

    Accepts any non-empty ``status`` string (open vocabulary). Returns None
    when no block is present, the fence is malformed, or the JSON is invalid.
    """
    match = _FENCE_RE.search(text)
    if match is None:
        return None
    raw = match.group(1).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    status = data.get("status")
    if not isinstance(status, str) or not status:
        return None

    return NodeStatusBlock(
        status=status.lower(),
        artifact_paths=list(data.get("artifact_paths", [])),
        produces=str(data.get("produces", "")),
        fields=dict(data.get("fields", {})),
        open_questions=list(data.get("open_questions", [])),
    )
