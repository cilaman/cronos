from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class TelemetryData:
    tokens: int
    usd: float
    seconds: float


@dataclass
class AgentResult:
    status: Literal["done", "blocked", "needs_fix", "failed"]
    artifact_paths: list[str]
    produces: str
    fields: dict[str, Any]
    open_questions: list[str]
    telemetry: TelemetryData


@dataclass
class GateResult:
    decision: Literal["proceed", "needs_fix", "fail", "retry"]
    errors: list[str]
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecResult:
    """Outcome of an ``exec`` node — a shell command run to completion (no LLM).

    status is ``done`` on exit 0, else ``failed``. ``artifact_path`` is the file the
    executor wrote the captured output to (None if it could not be written).
    """
    status: Literal["done", "failed"]
    exit_code: int
    stdout_tail: str = ""
    artifact_path: str | None = None
    produces: str | None = None
