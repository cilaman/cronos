"""Cronos pipeline package.

Houses the CC-v1 agent contract, per-class artifact schemas, verifier,
normalizer, regression fixture harness, and the delivery/v1 gate engine
used by the development pipeline.

Key modules:
  - contract: the CC-v1 artifact format
  - gate: the delivery/v1 gate engine (runGate dispatcher and checks)
  - verify: schema validation and cross-field rule checking
  - normalize: artifact normalization and auto-improvement
  - state_writer: pipeline state and telemetry persistence

See ``CONTRACT.md`` (sibling file) for the human-readable specification.
See ``docs/delivery-pipeline/delivery-v1-docs/GATE_ENGINE.md`` for the gate implementation.
"""

from app.pipeline.contract import (
    AGENT_REPORTED_METRICS,
    ARTIFACT_PATH_TEMPLATE,
    CC_VERSION,
    HEADER_FIELDS,
    HEADER_REQUIRED_FIELDS,
    NEXT_CONSUMER_USER_SENTINEL,
    R_RULES,
    REQUIRED_SECTIONS,
    STATUS_VALUES,
    TRACE_OWNED_METRICS,
)
from app.pipeline.normalize import NormalizeResult, normalize
from app.pipeline.verify import (
    CLASS_CONFIG,
    EXIT_ESCALATE,
    EXIT_FAIL,
    EXIT_PROCEED,
    EXIT_RETRY,
    VerifyResult,
    canonical_artifact_relpath,
    verify,
)
from app.pipeline.state_writer import (
    GATE_DECISIONS,
    PIPELINE_STATE_FILENAME,
    PHASES_LOG_FILENAME,
    PIPELINE_STATUSES,
    PhaseEntry,
    PhaseMetrics,
    PhaseVerifyResult,
    finalize_pipeline,
    init_pipeline,
    load_last_phase_log,
    load_state,
    log_path,
    pipeline_dir,
    record_phase_log,
    state_path,
    update_phase,
)
from app.pipeline.auto_improver import (
    AppliedChange,
    ApplierResult,
    SkippedFinding,
    apply_retro_improvements,
    bump_minor,
    read_cc_version,
)
from app.pipeline.gate import GateResult, runGate

__all__ = [
    "AGENT_REPORTED_METRICS",
    "ARTIFACT_PATH_TEMPLATE",
    "AppliedChange",
    "ApplierResult",
    "CC_VERSION",
    "CLASS_CONFIG",
    "EXIT_ESCALATE",
    "EXIT_FAIL",
    "EXIT_PROCEED",
    "EXIT_RETRY",
    "GATE_DECISIONS",
    "GateResult",
    "HEADER_FIELDS",
    "HEADER_REQUIRED_FIELDS",
    "NEXT_CONSUMER_USER_SENTINEL",
    "NormalizeResult",
    "PHASES_LOG_FILENAME",
    "PIPELINE_STATE_FILENAME",
    "PIPELINE_STATUSES",
    "PhaseEntry",
    "PhaseMetrics",
    "PhaseVerifyResult",
    "R_RULES",
    "REQUIRED_SECTIONS",
    "STATUS_VALUES",
    "SkippedFinding",
    "TRACE_OWNED_METRICS",
    "VerifyResult",
    "apply_retro_improvements",
    "bump_minor",
    "canonical_artifact_relpath",
    "finalize_pipeline",
    "init_pipeline",
    "load_last_phase_log",
    "load_state",
    "log_path",
    "normalize",
    "pipeline_dir",
    "read_cc_version",
    "record_phase_log",
    "runGate",
    "state_path",
    "update_phase",
    "verify",
]
