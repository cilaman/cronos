"""
lib.conditions — pure condition evaluator for the delivery-workflow package.

Lifted from ``backend/app/harnesses/decision`` so the portable runner and
adapter can evaluate ``when`` edge conditions without importing from ``app.*``.

Supported syntax
----------------
``<path> <op> <literal>``
  where ``<path>`` is a dotted / hyphenated identifier (e.g.
  ``review.fields.verdict``, ``my-node.status``), ``<op>`` is one of
  ``==``, ``!=``, ``in``, and ``<literal>`` is a quoted string or
  unquoted bare word.

``<clause> && <clause> && ...``
  All clauses must hold (short-circuit AND).  Clauses are split on the
  literal four-character sequence `` && ``.

``<and-group> || <and-group> || ...``
  Any AND-group must hold (short-circuit OR).  OR groups are split on
  `` || `` BEFORE splitting on `` && ``, giving OR-of-ANDs precedence
  (equivalent to ``(a && b) || (c && d)``).

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

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Single-clause regex — byte-identical copy from
# backend/app/harnesses/decision.py lines 275-284.
# ---------------------------------------------------------------------------

_EVAL_SINGLE_RE = re.compile(
    r"^\s*"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*)"
    r"\s+(?P<op>==|!=|in)\s+"
    r"(?P<val>"
    r'"(?:[^"\\]|\\.)*"'
    r"|'(?:[^'\\]|\\.)*'"
    r"|\S+"
    r")\s*$"
)


def _eval_single_clause(clause: str, scope: dict[str, str]) -> bool:
    """Evaluate one ``<path> <op> <literal>`` clause against *scope*.

    Returns False (never raises) when the clause does not match the
    whitelisted grammar, so unsupported conditions fall through to the
    default edge.
    """
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

    lhs: str | None = scope.get(var_name)

    if op == "==":
        return lhs == rhs
    if op == "!=":
        return lhs != rhs
    if op == "in":
        # rhs is a comma-separated list: ``val1,val2,val3``
        candidates = [v.strip() for v in rhs.split(",")]
        return lhs in candidates

    # Unreachable given the regex, but defensive:
    log.warning("eval_condition: unknown operator %r in clause %r.", op, clause)
    return False


def eval_condition(condition: str, scope: dict[str, str]) -> bool:
    """Evaluate a whitelisted condition expression against *scope*.

    Supported syntax
    ----------------
    Single clause, AND conjunction (``&&``), and OR disjunction (``||``).
    Precedence: OR-of-ANDs (``a && b || c && d`` ≡ ``(a && b) || (c && d)``).
    Parens-aware tokeniser is deferred to v2.

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
