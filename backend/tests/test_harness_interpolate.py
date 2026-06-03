"""Tests for backend/app/harnesses/interpolate.py."""

import pytest

from app.harnesses.interpolate import interpolate


# ---------------------------------------------------------------------------
# Basic substitution from root_vars
# ---------------------------------------------------------------------------

def test_basic_root_vars():
    text, unresolved = interpolate(
        "Hello, $name! You are $age years old.",
        root_vars={"name": "Alice", "age": "30"},
        upstream_outputs={},
    )
    assert text == "Hello, Alice! You are 30 years old."
    assert unresolved == []


def test_basic_root_vars_braced():
    """${name} form should work identically."""
    text, unresolved = interpolate(
        "Hello, ${name}!",
        root_vars={"name": "Bob"},
        upstream_outputs={},
    )
    assert text == "Hello, Bob!"
    assert unresolved == []


# ---------------------------------------------------------------------------
# Basic substitution from upstream_outputs
# ---------------------------------------------------------------------------

def test_basic_upstream_outputs():
    text, unresolved = interpolate(
        "Result: $result",
        root_vars={},
        upstream_outputs={"result": "success"},
    )
    assert text == "Result: success"
    assert unresolved == []


def test_upstream_outputs_mixed_with_root():
    text, unresolved = interpolate(
        "$greeting from $node",
        root_vars={"greeting": "Hello"},
        upstream_outputs={"node": "node-1"},
    )
    assert text == "Hello from node-1"
    assert unresolved == []


# ---------------------------------------------------------------------------
# Upstream wins on key collision
# ---------------------------------------------------------------------------

def test_collision_upstream_wins():
    """When root_vars and upstream_outputs share a key, upstream_outputs wins."""
    text, unresolved = interpolate(
        "Language: $lang",
        root_vars={"lang": "Python"},
        upstream_outputs={"lang": "TypeScript"},
    )
    assert text == "Language: TypeScript"
    assert unresolved == []


def test_collision_upstream_wins_multiple_keys():
    """Multiple colliding keys all resolve to the upstream value."""
    text, unresolved = interpolate(
        "$a and $b and $c",
        root_vars={"a": "root-a", "b": "root-b", "c": "root-c"},
        upstream_outputs={"b": "upstream-b", "c": "upstream-c"},
    )
    assert text == "root-a and upstream-b and upstream-c"
    assert unresolved == []


# ---------------------------------------------------------------------------
# Unresolved placeholders returned in second tuple element
# ---------------------------------------------------------------------------

def test_unresolved_placeholders():
    text, unresolved = interpolate(
        "Hello $name, your score is $score",
        root_vars={"name": "Charlie"},
        upstream_outputs={},
    )
    # safe_substitute leaves unresolved placeholders intact
    assert "$score" in text
    assert "Charlie" in text
    assert unresolved == ["score"]


def test_multiple_unresolved_placeholders():
    text, unresolved = interpolate(
        "$a $b $c",
        root_vars={},
        upstream_outputs={},
    )
    assert unresolved == ["a", "b", "c"]


def test_unresolved_deduplicated():
    """Same placeholder appearing multiple times is listed once."""
    text, unresolved = interpolate(
        "$x plus $x equals two-$x",
        root_vars={},
        upstream_outputs={},
    )
    assert unresolved == ["x"]


def test_no_unresolved_when_all_provided():
    text, unresolved = interpolate(
        "$x $y",
        root_vars={"x": "1"},
        upstream_outputs={"y": "2"},
    )
    assert text == "1 2"
    assert unresolved == []


# ---------------------------------------------------------------------------
# Empty template works
# ---------------------------------------------------------------------------

def test_empty_template():
    text, unresolved = interpolate(
        "",
        root_vars={"foo": "bar"},
        upstream_outputs={"baz": "qux"},
    )
    assert text == ""
    assert unresolved == []


# ---------------------------------------------------------------------------
# Empty dicts work
# ---------------------------------------------------------------------------

def test_empty_dicts_no_placeholders():
    text, unresolved = interpolate(
        "No placeholders here.",
        root_vars={},
        upstream_outputs={},
    )
    assert text == "No placeholders here."
    assert unresolved == []


def test_empty_dicts_with_placeholders():
    text, unresolved = interpolate(
        "Missing: $thing",
        root_vars={},
        upstream_outputs={},
    )
    assert "$thing" in text
    assert unresolved == ["thing"]


def test_both_dicts_empty_empty_template():
    text, unresolved = interpolate("", {}, {})
    assert text == ""
    assert unresolved == []


# ---------------------------------------------------------------------------
# Return type: always a tuple of (str, list[str])
# ---------------------------------------------------------------------------

def test_return_type():
    result = interpolate("$x", {"x": "v"}, {})
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], list)


def test_unresolved_sorted():
    """Unresolved names should be returned in sorted order."""
    text, unresolved = interpolate(
        "$zebra $apple $mango",
        root_vars={},
        upstream_outputs={},
    )
    assert unresolved == ["apple", "mango", "zebra"]
