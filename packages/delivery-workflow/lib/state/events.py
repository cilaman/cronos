from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EventLog:
    """Append-only events.jsonl log for a workflow run directory."""

    def __init__(self, run_dir: Path) -> None:
        self._path = run_dir / "events.jsonl"

    def append(self, event: dict[str, Any]) -> None:
        """Append one JSON event line; auto-injects 'ts' (ISO-8601 UTC) if absent."""
        if "ts" not in event:
            event = {**event, "ts": datetime.now(timezone.utc).isoformat()}
        line = json.dumps(event, separators=(",", ":"))
        with self._path.open("a") as fh:
            fh.write(line + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        """Return all recorded events; empty list if log does not exist yet."""
        if not self._path.exists():
            return []
        events = []
        for line in self._path.read_text().splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
        return events
