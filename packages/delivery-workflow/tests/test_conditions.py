"""Parity tests for lib.conditions.eval_condition.

Covers all 5 operators (==, !=, in, &&, ||) with positive + negative cases,
multi-clause conjunctions, mixed AND/OR, edge cases (empty string, bad grammar).
"""
from lib.conditions import eval_condition


# ---------------------------------------------------------------------------
# == operator
# ---------------------------------------------------------------------------

def test_eq_match():
    assert eval_condition("status == done", {"status": "done"}) is True


def test_eq_no_match():
    assert eval_condition("status == done", {"status": "fail"}) is False


def test_eq_missing_key():
    assert eval_condition("status == done", {}) is False


# ---------------------------------------------------------------------------
# != operator
# ---------------------------------------------------------------------------

def test_ne_match():
    assert eval_condition("status != done", {"status": "fail"}) is True


def test_ne_no_match():
    assert eval_condition("status != done", {"status": "done"}) is False


# ---------------------------------------------------------------------------
# in operator
# ---------------------------------------------------------------------------

def test_in_match_first():
    assert eval_condition("cls in code,dependency", {"cls": "code"}) is True


def test_in_match_second():
    assert eval_condition("cls in code,dependency", {"cls": "dependency"}) is True


def test_in_no_match():
    assert eval_condition("cls in code,dependency", {"cls": "design"}) is False


def test_in_three_items():
    # Three items in the RHS list
    assert eval_condition("cls in code,dependency,design", {"cls": "design"}) is True


# ---------------------------------------------------------------------------
# && (AND conjunction)
# ---------------------------------------------------------------------------

def test_and_all_true():
    scope = {"verdict": "needs_fix", "cls": "local"}
    assert eval_condition("verdict == needs_fix && cls == local", scope) is True


def test_and_first_false():
    scope = {"verdict": "pass", "cls": "local"}
    assert eval_condition("verdict == needs_fix && cls == local", scope) is False


def test_and_second_false():
    scope = {"verdict": "needs_fix", "cls": "architectural"}
    assert eval_condition("verdict == needs_fix && cls == local", scope) is False


def test_and_three_clauses():
    scope = {"a": "1", "b": "2", "c": "3"}
    assert eval_condition("a == 1 && b == 2 && c == 3", scope) is True


def test_and_three_clauses_one_false():
    scope = {"a": "1", "b": "X", "c": "3"}
    assert eval_condition("a == 1 && b == 2 && c == 3", scope) is False


# ---------------------------------------------------------------------------
# || (OR disjunction)
# ---------------------------------------------------------------------------

def test_or_first_true():
    assert eval_condition("status == done || status == pass", {"status": "done"}) is True


def test_or_second_true():
    assert eval_condition("status == done || status == pass", {"status": "pass"}) is True


def test_or_neither_true():
    assert eval_condition("status == done || status == pass", {"status": "fail"}) is False


def test_or_both_true():
    scope = {"a": "x", "b": "y"}
    assert eval_condition("a == x || b == y", scope) is True


# ---------------------------------------------------------------------------
# Mixed && and || (OR-of-ANDs precedence)
# ---------------------------------------------------------------------------

def test_mixed_or_of_ands_first_group_matches():
    # (decision == needs_fix && cls == code) || (decision == needs_fix && cls == dependency)
    scope = {"decision": "needs_fix", "cls": "code"}
    expr = "decision == needs_fix && cls == code || decision == needs_fix && cls == dependency"
    assert eval_condition(expr, scope) is True


def test_mixed_or_of_ands_second_group_matches():
    scope = {"decision": "needs_fix", "cls": "dependency"}
    expr = "decision == needs_fix && cls == code || decision == needs_fix && cls == dependency"
    assert eval_condition(expr, scope) is True


def test_mixed_or_of_ands_neither_matches():
    scope = {"decision": "needs_fix", "cls": "design"}
    expr = "decision == needs_fix && cls == code || decision == needs_fix && cls == dependency"
    assert eval_condition(expr, scope) is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_condition_returns_false():
    assert eval_condition("", {}) is False


def test_unsupported_grammar_returns_false():
    assert eval_condition("status > done", {"status": "done"}) is False


def test_quoted_value_eq():
    assert eval_condition("status == 'done'", {"status": "done"}) is True


def test_dotted_path():
    assert eval_condition("review.fields.verdict == pass", {"review.fields.verdict": "pass"}) is True


def test_hyphenated_path():
    assert eval_condition("g-security.decision == proceed", {"g-security.decision": "proceed"}) is True
