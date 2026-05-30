"""Cronos pipeline package.

Houses the CC-v1 agent contract, per-class artifact schemas, verifier,
normalizer, and regression fixture harness used by the development pipeline.

See ``CONTRACT.md`` (sibling file) for the human-readable specification.
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

__all__ = [
    "AGENT_REPORTED_METRICS",
    "ARTIFACT_PATH_TEMPLATE",
    "CC_VERSION",
    "CLASS_CONFIG",
    "EXIT_ESCALATE",
    "EXIT_FAIL",
    "EXIT_PROCEED",
    "EXIT_RETRY",
    "HEADER_FIELDS",
    "HEADER_REQUIRED_FIELDS",
    "NEXT_CONSUMER_USER_SENTINEL",
    "R_RULES",
    "REQUIRED_SECTIONS",
    "STATUS_VALUES",
    "TRACE_OWNED_METRICS",
    "VerifyResult",
    "canonical_artifact_relpath",
    "verify",
]
