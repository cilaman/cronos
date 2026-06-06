from __future__ import annotations

import re
from typing import Any

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "REDACTED-GITHUB-PAT"),
    (re.compile(r"ghp_[A-Za-z0-9_]{20,}"), "REDACTED-GHP"),
    (re.compile(r"gho_[A-Za-z0-9_]{20,}"), "REDACTED-GHO"),
    (re.compile(r"ghs_[A-Za-z0-9_]{20,}"), "REDACTED-GHS"),
    (re.compile(r"ghr_[A-Za-z0-9_]{20,}"), "REDACTED-GHR"),
    (re.compile(r"https://[^@\s]+@github\.com"), "https://REDACTED@github.com"),
    (re.compile(r"x-access-token:[A-Za-z0-9_]{20,}"), "x-access-token:REDACTED"),
]


def _redact_secrets(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_trace_dict(obj: Any) -> Any:
    """Recursively redact secret patterns from all string leaves of a dict/list."""
    if isinstance(obj, str):
        return _redact_secrets(obj)
    if isinstance(obj, dict):
        return {k: redact_trace_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_trace_dict(item) for item in obj]
    return obj
