from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

log = logging.getLogger(__name__)

#: Closed AgentResult status vocabulary enforced at the dispatchAgent boundary
#: (R1/D4, 01-state-model.md §5.1).  The fence transport format stays open
#: (``lib/node_status.py``); ``agent_result_from_envelope`` below is where an
#: unknown status becomes ``failed`` with an ``unknown_status:<raw>`` marker
#: instead of silently flowing to ``done`` via runner/dispatch.py's
#: else-branch.  Package semantics, shared by every executor (the Cronos
#: adapter at ``backend/app/delivery_adapter.py`` and the in-package
#: ``LocalProcessExecutor``) — promoted here in R10e so no host re-implements
#: the mapping.
AGENT_STATUS_VOCAB = frozenset({"done", "blocked", "needs_fix", "failed"})


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


def agent_result_from_envelope(
    envelope: Any,
    *,
    node_id: str,
    telemetry: TelemetryData | None = None,
    missing_detail: str | None = None,
) -> AgentResult:
    """Map a parsed ``node_status`` envelope to a closed-vocabulary AgentResult.

    THE closed-vocabulary boundary (R1/D4, 01-state-model.md §5.1), used by
    every executor so the mapping lives exactly once:

    - *envelope* ``None`` (no fence found) → ``failed`` with an explicit
      ``open_questions`` entry naming the node.  *missing_detail* (optional)
      is appended in parentheses so hosts can say WHERE they looked (e.g. the
      Cronos adapter's ``trace.node_status is None``).
    - A status outside ``AGENT_STATUS_VOCAB`` → ``failed`` with an
      ``unknown_status:<raw>`` marker prepended to the envelope's own
      open questions — never silently ``done``.  Envelope artifact_paths /
      produces / fields are KEPT for diagnosis.
    - A known status passes through with normalized payload fields.

    *envelope* may be a mapping (the Cronos trace parser's dict) or any object
    with ``status`` / ``artifact_paths`` / ``produces`` / ``fields`` /
    ``open_questions`` attributes (``lib.node_status.NodeStatusBlock``).
    """
    telem = telemetry if telemetry is not None else TelemetryData(
        tokens=0, usd=0.0, seconds=0.0
    )

    if envelope is None:
        detail = f" ({missing_detail})" if missing_detail else ""
        return AgentResult(
            status="failed",
            artifact_paths=[],
            produces="",
            fields={},
            open_questions=[
                f"No node_status fence found in agent output for node "
                f"'{node_id}'{detail}"
            ],
            telemetry=telem,
        )

    if isinstance(envelope, Mapping):
        get = envelope.get
    else:  # NodeStatusBlock-shaped object
        def get(key: str, default: Any = None) -> Any:
            return getattr(envelope, key, default)

    raw_status = get("status")
    status = raw_status.strip().lower() if isinstance(raw_status, str) else ""
    raw_paths = get("artifact_paths")
    artifact_paths = (
        [str(p) for p in raw_paths] if isinstance(raw_paths, list) else []
    )
    produces = str(get("produces") or "")
    raw_fields = get("fields")
    fields = dict(raw_fields) if isinstance(raw_fields, dict) else {}
    raw_questions = get("open_questions")
    open_questions = (
        [str(q) for q in raw_questions] if isinstance(raw_questions, list) else []
    )

    if status not in AGENT_STATUS_VOCAB:
        log.warning(
            "agent_result_from_envelope[%s]: unknown node_status %r — mapping "
            "to 'failed' (closed vocabulary: %s).",
            node_id, raw_status, sorted(AGENT_STATUS_VOCAB),
        )
        return AgentResult(
            status="failed",
            artifact_paths=artifact_paths,
            produces=produces,
            fields=fields,
            open_questions=[f"unknown_status:{raw_status}"] + open_questions,
            telemetry=telem,
        )

    return AgentResult(
        status=status,  # type: ignore[arg-type]  # membership-checked above
        artifact_paths=artifact_paths,
        produces=produces,
        fields=fields,
        open_questions=open_questions,
        telemetry=telem,
    )


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
