"""
lib.conditions — pure, typed condition evaluator for the delivery-workflow package.

Lifted from ``backend/app/harnesses/decision`` so the portable runner and
adapter can evaluate ``when`` edge conditions without importing from ``app.*``.

Supported syntax
----------------
``<path> <op> <literal>``
  where ``<path>`` is a dotted / hyphenated identifier (e.g.
  ``review.fields.verdict``, ``my-node.status``), ``<op>`` is one of
  ``==``, ``!=``, ``in``, and ``<literal>`` is a quoted string or
  unquoted bare word.

``exists(<path>)`` / ``!exists(<path>)``
  Presence guard (R3): True iff ``<path>`` is a key in the scope
  (``!exists`` negates).  This is the explicit replacement for the removed
  v1 footgun where a *missing* key satisfied every ``!=`` clause.

``<clause> && <clause> && ...``
  All clauses must hold (short-circuit AND).  Clauses are split on the
  literal four-character sequence `` && ``.

``<and-group> || <and-group> || ...``
  Any AND-group must hold (short-circuit OR).  OR groups are split on
  `` || `` BEFORE splitting on `` && ``, giving OR-of-ANDs precedence
  (equivalent to ``(a && b) || (c && d)``).

Typed scope semantics (R3 — kills D3)
-------------------------------------
The scope may carry **typed scalars** (``bool``/``int``/``float``/``str``,
plus ``None``), not just strings.  Comparison rules per LHS type:

- ``str``    — byte-for-byte comparison against the literal text, exactly
  as in v1.  The backend harness path builds all-string scopes; its
  behavior for present keys is unchanged.
- ``bool``   — compared against the *canonical* JSON form: ``true`` /
  ``false`` (lowercase, matching what agents emit in node_status fences
  and what ``delivery.workflow.yaml`` edges write).  ``str(True)`` is
  never consulted, so ``"True"`` does NOT match a bool.
- ``int``/``float`` — compared numerically when the literal parses as a
  number (``3 == 3.0``); otherwise against the canonical unquoted string
  form (``str(3)`` → ``"3"``).
- ``None``   — canonical form ``"null"`` (JSON canonical).

**Missing keys** (R3 breaking change): a clause whose ``<path>`` is not a
key in the scope evaluates to ``False`` for EVERY operator — including
``!=`` — and logs a WARNING.  v1 evaluated ``None != rhs`` as True, which
made every ``!=`` edge fire whenever persistence lost the fields (D2).
Route on presence explicitly with ``exists(<path>)``.

**V1 limitation**: splitting on `` && `` / `` || `` will mis-tokenise a
clause whose quoted string literal itself contains those character
sequences.  No current delivery.workflow.yaml edge needs this, so it is
documented here rather than fixed — a quoting-aware tokeniser is a known
v2 follow-up.

No ``eval()`` is used.  Unrecognised expressions return ``False`` and log
a ``WARNING``.  Sandbox-escape attempts fail the grammar check and return
``False`` without execution.
"""

from __future__ import annotations

import re
import logging
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Single-clause regex — path/op/literal grammar shared with
# backend/app/harnesses/decision.py (which now delegates here).
# ---------------------------------------------------------------------------

_PATH_PATTERN = r"[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*"

_EVAL_SINGLE_RE = re.compile(
    r"^\s*"
    r"(?P<name>" + _PATH_PATTERN + r")"
    r"\s+(?P<op>==|!=|in)\s+"
    r"(?P<val>"
    r'"(?:[^"\\]|\\.)*"'
    r"|'(?:[^'\\]|\\.)*'"
    r"|\S+"
    r")\s*$"
)

# exists(<path>) / !exists(<path>) presence guard (R3).
_EXISTS_RE = re.compile(
    r"^\s*(?P<neg>!)?\s*exists\(\s*(?P<name>" + _PATH_PATTERN + r")\s*\)\s*$"
)

# Conservative numeric literal recognition — deliberately rejects "inf",
# "nan", and other float() accepted spellings so bare words stay strings.
_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?$")


# ---------------------------------------------------------------------------
# Canonical serialization of typed scope scalars (R3)
# ---------------------------------------------------------------------------


def canonical_scalar(value: Any) -> str:
    """Canonical string form of a typed scope scalar.

    booleans → ``true`` / ``false``; numbers unquoted (``3``, ``3.5``);
    ``None`` → ``null``; strings pass through.  This is the single
    serialization rule for rendering a typed scope value to text (JSON
    canonical form) and the form condition literals compare against for
    non-string LHS values.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def canonicalize_scope(scope: dict[str, Any]) -> dict[str, str]:
    """Render a typed scope to canonical strings (for logs / interpolation).

    Not used by ``eval_condition`` itself — the evaluator compares typed
    values — but hosts that need a purely textual view of the scope must
    use this instead of ``str()`` so booleans render ``true``/``false``.
    """
    return {k: canonical_scalar(v) for k, v in scope.items()}


# ---------------------------------------------------------------------------
# Typed comparison
# ---------------------------------------------------------------------------


def _parse_number(text: str) -> int | float | None:
    """Parse *text* as an int or float literal; None when not numeric."""
    if _INT_RE.match(text):
        try:
            return int(text)
        except ValueError:  # pragma: no cover - regex guarantees parse
            return None
    if _FLOAT_RE.match(text):
        try:
            return float(text)
        except ValueError:  # pragma: no cover - regex guarantees parse
            return None
    return None


def _scalar_eq(lhs: Any, rhs_text: str) -> bool:
    """One typed equality between a scope value and the RHS literal text.

    - str LHS: exact string comparison (v1 semantics, harness-compatible).
    - bool LHS: canonical ``true``/``false`` comparison.
    - int/float LHS: numeric comparison when the literal is numeric,
      canonical-string comparison otherwise.
    - everything else (None, exotic types): canonical-string comparison.
    """
    if isinstance(lhs, str):
        return lhs == rhs_text
    if isinstance(lhs, bool):
        return canonical_scalar(lhs) == rhs_text
    if isinstance(lhs, (int, float)):
        num = _parse_number(rhs_text)
        if num is not None:
            return float(lhs) == float(num)
        return canonical_scalar(lhs) == rhs_text
    return canonical_scalar(lhs) == rhs_text


def _eval_single_clause(clause: str, scope: dict[str, Any]) -> bool:
    """Evaluate one clause (``<path> <op> <literal>`` or ``exists(<path>)``).

    Returns False (never raises) when the clause does not match the
    whitelisted grammar, so unsupported conditions fall through to the
    default edge.
    """
    m_exists = _EXISTS_RE.match(clause)
    if m_exists is not None:
        present = m_exists.group("name") in scope
        return (not present) if m_exists.group("neg") else present

    m = _EVAL_SINGLE_RE.match(clause)
    if m is None:
        log.warning(
            "eval_condition: clause %r does not match whitelisted grammar; returning False.",
            clause,
        )
        return False

    var_name: str = m.group("name")
    op: str = m.group("op")
    raw_val: str = m.group("val")

    # Decode quoted string or bare word.
    if (raw_val.startswith('"') and raw_val.endswith('"')) or (
        raw_val.startswith("'") and raw_val.endswith("'")
    ):
        rhs = raw_val[1:-1]
    else:
        rhs = raw_val

    # Missing key → False for every operator (R3 breaking change; v1
    # evaluated ``None != rhs`` as True, which fired every ``!=`` edge
    # whenever the key was lost).  Route on presence with exists(<path>).
    if var_name not in scope:
        log.warning(
            "eval_condition: %r not in scope — clause %r is False "
            "(use exists(%s) to route on presence).",
            var_name, clause, var_name,
        )
        return False

    lhs: Any = scope[var_name]

    if op == "==":
        return _scalar_eq(lhs, rhs)
    if op == "!=":
        return not _scalar_eq(lhs, rhs)
    if op == "in":
        # rhs is a comma-separated list: ``val1,val2,val3``
        candidates = [v.strip() for v in rhs.split(",")]
        return any(_scalar_eq(lhs, c) for c in candidates)

    # Unreachable given the regex, but defensive:
    log.warning("eval_condition: unknown operator %r in clause %r.", op, clause)
    return False


def eval_condition(condition: str, scope: dict[str, Any]) -> bool:
    """Evaluate a whitelisted condition expression against *scope*.

    Supported syntax
    ----------------
    Single clause, ``exists(<path>)`` / ``!exists(<path>)`` presence
    guards, AND conjunction (``&&``), and OR disjunction (``||``).
    Precedence: OR-of-ANDs (``a && b || c && d`` ≡ ``(a && b) || (c && d)``).
    Parens-aware tokeniser is deferred to v2.

    The scope may carry typed scalars (bool/int/float/str); see the module
    docstring for the comparison rules.  A clause referencing a key missing
    from the scope is False for every operator and logs a WARNING.

    No ``eval()`` is used.  Unrecognised expressions return ``False`` and
    log a ``WARNING``.
    """
    if not condition:
        log.warning("eval_condition: empty condition string; returning False.")
        return False

    # Split on `` || `` first (OR of AND-groups).
    or_groups = condition.split(" || ")
    for or_group in or_groups:
        and_clauses = or_group.split(" && ")
        if all(_eval_single_clause(c.strip(), scope) for c in and_clauses):
            return True
    return False
