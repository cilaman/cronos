"""
delivery_status fenced-block parser.

Parses the de-branded structured-return sentinel emitted by delivery/v1 agents:

    ```delivery_status
    {
      "status": "done",
      "artifact_paths": [...],
      "produces": "research",
      "fields": {...},
      "open_questions": [],
      "telemetry": {"tokens": 8240, "usd": 0.124, "seconds": 34}
    }
    ```

Coexists with the Cronos worker's cronos_status parser — they parse different fences.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from results import TelemetryData

_FENCE_RE = re.compile(
    r"```delivery_status\s*\n(.*?)```",
    re.DOTALL,
)

ArtifactClass = Literal[
    "research", "analysis", "design", "frontend",
    "implementation", "review", "test", "doc",
]

DeliveryStatus = Literal["done", "blocked", "needs_fix", "failed"]


@dataclass
class DeliveryStatusBlock:
    status: DeliveryStatus
    artifact_paths: list[str]
    produces: str
    fields: dict[str, Any]
    open_questions: list[str]
    telemetry: TelemetryData


def parse_delivery_status(text: str) -> DeliveryStatusBlock | None:
    """Return the first delivery_status block found in *text*, or None."""
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
    if status not in ("done", "blocked", "needs_fix", "failed"):
        return None

    telemetry_raw = data.get("telemetry", {})
    telemetry = TelemetryData(
        tokens=int(telemetry_raw.get("tokens", 0)),
        usd=float(telemetry_raw.get("usd", 0.0)),
        seconds=float(telemetry_raw.get("seconds", 0.0)),
    )

    return DeliveryStatusBlock(
        status=status,
        artifact_paths=list(data.get("artifact_paths", [])),
        produces=str(data.get("produces", "")),
        fields=dict(data.get("fields", {})),
        open_questions=list(data.get("open_questions", [])),
        telemetry=telemetry,
    )
