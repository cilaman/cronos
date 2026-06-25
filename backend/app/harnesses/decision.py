"""
backend/app/harnesses/decision — Decision node evaluator.

Given a Decision harness node and the execution context (predecessor node
states, variable scope, and the most-recent agent RunTrace), this module
determines which outgoing edge id should be followed.

Signal layers (highest priority first)
---------------------------------------
1. ``"status"`` — the predecessor agent's STATUS marker / AgentResult.status.
   Resolved from the predecessor NodeState with ``status == 'done'`` (its
   ``output`` field is checked for ``STATUS: <value>`` pattern), or via the
   exit_reason for terminal process-level states.
2. ``"exit_reason"`` — the literal ``RunTrace.exit_reason`` string
   (e.g. ``"done"``, ``"error"``, ``"timeout"``).
3. ``"regex"`` — ``re.search`` applied to ``RunTrace.final_text_snippet``.
   Python inline flags (``(?i)`` etc.) are supported; no ``eval()``,
   no ``/pattern/flags`` syntax.
4. ``"variable"`` — whitelisted expression on scope variables.
   Supported operators: ``==``, ``!=``, ``in``.  No ``eval()``.

Default edge
-------------
An edge with ``condition=None`` is the unconditional fallback followed when no
other edge's condition evaluates to True.

R9 compliance
--------------
This module contains no subprocess calls, no asyncio.create_subprocess_* calls,
no os.system calls, and no ``await store.create(...)`` calls for control-flow
nodes.
"""

from __future__ import annotations

import re
import logging
from typing import Any

from .model import HarnessEdge, HarnessNode
from .run_state import NodeState
from ..trace_parser import RunTrace

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status marker extraction
# ---------------------------------------------------------------------------

# Matches ``STATUS: <value>`` anywhere in a text block, case-sensitive on
# the ``STATUS:`` keyword (matching the convention used by task-finalize skill).
_STATUS_MARKER_RE = re.compile(r"STATUS:\s*(\S+)")


def _extract_status_marker(text: str) -> str | None:
    """Return the STATUS marker value from *text*, or None if not found."""
    m = _STATUS_MARKER_RE.search(text)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_signal(
    predecessors_state: dict[str, NodeState],
    run_trace: RunTrace | None,
) -> tuple[str, Any]:
    """Determine the dominant signal layer and its value.

    Scans predecessor node states and the run trace to find the highest-priority
    signal available, returning a ``(layer, value)`` tuple.

    Layers in priority order:
      - ``"status"`` — STATUS marker from predecessor output or exit_reason
      - ``"exit_reason"`` — RunTrace.exit_reason string
      - ``"regex"`` — RunTrace.final_text_snippet (the value is the snippet;
        matching is performed in ``edge_matches``)
      - ``"variable"`` — scope variable values (the value is the scope dict;
        matching is performed in ``edge_matches``)
      - ``"none"`` — no signal is available (caller should use default edge)

    Parameters
    ----------
    predecessors_state:
        Mapping of node_id → NodeState for all predecessor nodes that have
        already completed.  Typically contains exactly one entry for a
        Decision node with a single incoming Agent edge.
    run_trace:
        The RunTrace of the most-recently executed predecessor agent, or None
        if no agent predecessor is available.

    Returns
    -------
    tuple[str, Any]
        ``(layer_name, signal_value)``
    """
    # Layer 1: status — try to extract a STATUS marker from any done predecessor.
    for node_id, ns in predecessors_state.items():
        if ns.status == "done" and ns.output:
            status_value = _extract_status_marker(ns.output)
            if status_value is not None:
                log.debug(
                    "resolve_signal: found STATUS marker '%s' in predecessor '%s' output.",
                    status_value, node_id,
                )
                return ("status", status_value)

    # Layer 2: exit_reason — use the trace's exit_reason if available.
    if run_trace is not None and run_trace.exit_reason:
        log.debug(
            "resolve_signal: using exit_reason='%s'.", run_trace.exit_reason
        )
        return ("exit_reason", run_trace.exit_reason)

    # Layer 3: regex — the signal value is the final_text_snippet; edge_matches
    # performs the re.search.
    if run_trace is not None and run_trace.final_text_snippet:
        log.debug("resolve_signal: using final_text_snippet (regex layer).")
        return ("regex", run_trace.final_text_snippet)

    # Layer 4: variable — signal value is the scope dict; edge_matches parses
    # the condition expression.  We return ("variable", None) here and pass
    # scope separately through evaluate_decision so edge_matches has access.
    # Returning ("variable", None) signals that variable-layer matching should
    # be attempted if any scope variables exist.
    log.debug("resolve_signal: no status/exit_reason/text signal; falling back to variable layer.")
    return ("variable", None)


def edge_matches(
    edge: HarnessEdge,
    signal: tuple[str, Any],
    scope: dict[str, str],
) -> bool:
    """Return True if *edge* matches the given *signal* in the given *scope*.

    Parameters
    ----------
    edge:
        The candidate outgoing edge.  If ``edge.condition`` is None, this is the
        default edge — callers should handle the default-edge fallback separately
        (this function returns False for a ``condition=None`` edge so the caller
        can distinguish "matched" from "is default").
    signal:
        The ``(layer, value)`` tuple returned by ``resolve_signal``.
    scope:
        Current variable scope.  Used only for the ``"variable"`` layer.

    Returns
    -------
    bool
        True if the edge condition matches the signal.
    """
    if edge.condition is None:
        # Default edge — never "matches" a signal; it is the fallback.
        return False

    layer, value = signal

    if layer == "status":
        # Exact case-sensitive match.
        return edge.condition == value

    if layer == "exit_reason":
        # Exact case-sensitive match.
        return edge.condition == value

    if layer == "regex":
        # re.search with Python inline flags (e.g. ``(?i)`` prefix).
        # No eval(); no /pattern/flags syntax.
        snippet: str = value or ""
        try:
            return bool(re.search(edge.condition, snippet))
        except re.error as exc:
            log.warning(
                "edge '%s' has invalid regex condition '%s': %s",
                edge.id, edge.condition, exc,
            )
            return False

    if layer == "variable":
        # Whitelisted grammar: ``<path> <op> <literal>`` where op ∈ {==, !=, in}.
        # Dotted/hyphenated paths and && conjunctions supported.  No eval().
        return eval_condition(edge.condition, scope)

    # Unknown layer — no match.
    return False


def evaluate_decision(
    node: HarnessNode,
    predecessors_state: dict[str, NodeState],
    scope: dict[str, str],
    run_trace: RunTrace | None,
    outgoing_edges: list[HarnessEdge],
) -> str:
    """Choose the outgoing edge to follow from a Decision node.

    Evaluates all outgoing edges against the resolved signal using the
    four-layer precedence defined in ``resolve_signal`` / ``edge_matches``.
    Returns the edge id of the first matching edge, or the default edge id
    if no condition matches.

    Parameters
    ----------
    node:
        The Decision node being evaluated.  Used for logging only.
    predecessors_state:
        Mapping of predecessor node_id → NodeState.
    scope:
        Current variable scope.
    run_trace:
        RunTrace of the most-recently completed predecessor agent, or None.
    outgoing_edges:
        All outgoing HarnessEdge objects whose ``source.node_id == node.id``.

    Returns
    -------
    str
        The chosen edge id.

    Raises
    ------
    ValueError
        If no matching edge AND no default edge is found.  (Harnesses should
        always have a default edge; validate_graph is expected to enforce this
        in a future validation rule.)
    """
    signal = resolve_signal(predecessors_state, run_trace)
    log.debug(
        "evaluate_decision: node='%s' signal=(%s, %r) edges=%d",
        node.id, signal[0], signal[1], len(outgoing_edges),
    )

    default_edge: HarnessEdge | None = None
    for edge in outgoing_edges:
        if edge.condition is None:
            # Record the first default edge as fallback.
            if default_edge is None:
                default_edge = edge
            continue
        if edge_matches(edge, signal, scope):
            log.debug(
                "evaluate_decision: node='%s' matched edge '%s' (condition=%r).",
                node.id, edge.id, edge.condition,
            )
            return edge.id

    # No condition-bearing edge matched; fall back to default.
    if default_edge is not None:
        log.debug(
            "evaluate_decision: node='%s' using default edge '%s'.",
            node.id, default_edge.id,
        )
        return default_edge.id

    raise ValueError(
        f"Decision node '{node.id}': no matching edge and no default edge "
        f"(condition=None) found among {[e.id for e in outgoing_edges]}."
    )


# ---------------------------------------------------------------------------
# Condition evaluator — dotted-path, hyphenated ids, && conjunction (no eval)
# ---------------------------------------------------------------------------

# Matches a single ``<path> <op> <value>`` clause.
# <path> supports: simple names, dotted paths, hyphenated node-ids.
#   Examples: ``status``, ``review.fields.verdict``, ``my-node.status``
# <op>: ==, !=, in
# <value>: double-quoted, single-quoted, or unquoted bare word

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

# Legacy single-segment regex kept for backward compatibility reference.
_VAR_COND_RE = re.compile(
    r"""^\s*
        (?P<name>[A-Za-z_][A-Za-z0-9_]*)   # variable name
        \s+
        (?P<op>==|!=|in)                    # operator
        \s+
        (?P<val>                            # right-hand value
            "(?:[^"\\]|\\.)*"              # double-quoted string
            |'(?:[^'\\]|\\.)*'             # single-quoted string
            |\S+                           # unquoted bare word / number
        )
    \s*$""",
    re.VERBOSE,
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
    ``<path> <op> <literal>``
      where ``<path>`` is a dotted / hyphenated identifier (e.g.
      ``review.fields.verdict``, ``my-node.status``), ``<op>`` is one of
      ``==``, ``!=``, ``in``, and ``<literal>`` is a quoted string or
      unquoted bare word (including ``true`` / ``false``).

    ``<clause> && <clause> && ...``
      All clauses must hold (short-circuit AND).  Clauses are split on the
      literal four-character sequence `` && ``.

    **V1 limitation**: splitting on `` && `` will mis-tokenise a clause
    whose quoted string literal itself contains `` && ``.  No spec §12
    worked-example edge needs this, so it is documented here rather than
    fixed — a quoting-aware tokeniser is a known v2 follow-up.

    No ``eval()`` is used.  Unrecognised expressions return ``False`` and
    log a ``WARNING``.  Sandbox-escape attempts (e.g.
    ``__import__('os').system(…)``) fail the grammar check and return
    ``False`` without execution.
    """
    if not condition:
        log.warning("eval_condition: empty condition string; returning False.")
        return False

    clauses = condition.split(" && ")
    for clause in clauses:
        if not _eval_single_clause(clause.strip(), scope):
            return False
    return True


def _eval_variable_condition(condition: str, scope: dict[str, str]) -> bool:
    """Backward-compatible wrapper — delegates to eval_condition.

    Kept so external callers that imported this private function directly
    continue to work.  New code should call ``eval_condition`` directly.
    """
    return eval_condition(condition, scope)
