"""Tests for spec_loader: pins both validation directions per design risk R6.

The §12 worked example (delivery.workflow.yaml) must validate clean.
Deliberately malformed copies must be rejected with a non-empty error message.
"""
import copy
from pathlib import Path

import pytest
import yaml

import spec_loader

PACKAGE_ROOT = Path(__file__).parent.parent
SPEC_PATH = PACKAGE_ROOT / "delivery.workflow.yaml"


# ---------------------------------------------------------------------------
# Happy path — §12 canonical example
# ---------------------------------------------------------------------------


def test_canonical_example_validates_clean():
    """The committed §12 worked example loads and validates without error."""
    spec = spec_loader.load_spec(SPEC_PATH)
    assert spec["apiVersion"] == "delivery/v1"
    assert spec["metadata"]["name"] == "sdlc-delivery"


def test_canonical_example_has_all_node_kinds():
    spec = spec_loader.load_spec(SPEC_PATH)
    kinds = {n["kind"] for n in spec["nodes"]}
    assert kinds == {"agent", "gate", "human", "exec"}


def test_canonical_example_has_expected_node_ids():
    spec = spec_loader.load_spec(SPEC_PATH)
    node_ids = {n["id"] for n in spec["nodes"]}
    assert {"scout", "g-scout", "analyze", "g-analysis", "architect", "implement", "review", "release"} <= node_ids


def test_canonical_example_edges_present():
    spec = spec_loader.load_spec(SPEC_PATH)
    assert len(spec["edges"]) > 0
    # Every edge has from + to
    for edge in spec["edges"]:
        assert "from" in edge
        assert "to" in edge


def test_canonical_example_defaults_budget():
    spec = spec_loader.load_spec(SPEC_PATH)
    assert spec["defaults"]["budget"]["usd_ceiling"] == 25.0
    assert spec["defaults"]["budget"]["on_exceed"] == "escalate"


def test_loads_spec_from_yaml_string():
    """loads_spec accepts a YAML text string and returns the same structure."""
    spec = spec_loader.load_spec(SPEC_PATH)
    text = yaml.dump(spec, default_flow_style=False, allow_unicode=True)
    result = spec_loader.loads_spec(text)
    assert result["apiVersion"] == "delivery/v1"
    assert result["metadata"]["name"] == "sdlc-delivery"


# ---------------------------------------------------------------------------
# Rejection path — malformed specs must be refused
# ---------------------------------------------------------------------------


def _load_clean() -> dict:
    return spec_loader.load_spec(SPEC_PATH)


def test_missing_apiVersion_rejected():
    bad = _load_clean()
    del bad["apiVersion"]
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    assert exc.value.args[0]


def test_wrong_apiVersion_rejected():
    bad = _load_clean()
    bad["apiVersion"] = "delivery/v2"
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    assert exc.value.args[0]


def test_missing_metadata_rejected():
    bad = _load_clean()
    del bad["metadata"]
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    assert exc.value.args[0]


def test_missing_nodes_rejected():
    bad = _load_clean()
    del bad["nodes"]
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    assert exc.value.args[0]


def test_missing_edges_rejected():
    bad = _load_clean()
    del bad["edges"]
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    assert exc.value.args[0]


def test_bad_node_kind_rejected():
    """A node with an unrecognised kind must be rejected."""
    bad = _load_clean()
    # Patch the first node to have an invalid kind
    bad["nodes"][0] = copy.deepcopy(bad["nodes"][0])
    bad["nodes"][0]["kind"] = "invalid-kind"
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    assert exc.value.args[0]


def test_agent_node_missing_produces_rejected():
    """An agent node without `produces` must be rejected."""
    bad = _load_clean()
    for i, node in enumerate(bad["nodes"]):
        if node["kind"] == "agent":
            bad["nodes"][i] = copy.deepcopy(node)
            del bad["nodes"][i]["produces"]
            break
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    assert exc.value.args[0]


def test_agent_node_missing_agent_field_rejected():
    """An agent node without `agent` (the agent ref) must be rejected."""
    bad = _load_clean()
    for i, node in enumerate(bad["nodes"]):
        if node["kind"] == "agent":
            bad["nodes"][i] = copy.deepcopy(node)
            del bad["nodes"][i]["agent"]
            break
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    assert exc.value.args[0]


def test_gate_node_missing_checks_rejected():
    """A gate node without `checks` must be rejected."""
    bad = _load_clean()
    for i, node in enumerate(bad["nodes"]):
        if node["kind"] == "gate":
            bad["nodes"][i] = copy.deepcopy(node)
            del bad["nodes"][i]["checks"]
            break
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    assert exc.value.args[0]


def test_gate_node_unknown_check_type_rejected():
    """A gate check with an unrecognised type must be rejected."""
    bad = _load_clean()
    for i, node in enumerate(bad["nodes"]):
        if node["kind"] == "gate":
            bad["nodes"][i] = copy.deepcopy(node)
            bad["nodes"][i]["checks"][0]["type"] = "unknown_check_type"
            break
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    assert exc.value.args[0]


def test_human_node_missing_prompt_rejected():
    """A human node without `prompt` must be rejected."""
    bad = _load_clean()
    for i, node in enumerate(bad["nodes"]):
        if node["kind"] == "human":
            bad["nodes"][i] = copy.deepcopy(node)
            del bad["nodes"][i]["prompt"]
            break
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    assert exc.value.args[0]


def test_invalid_on_exceed_rejected():
    """defaults.budget.on_exceed must be 'escalate' or 'fail'."""
    bad = _load_clean()
    bad["defaults"]["budget"]["on_exceed"] = "explode"
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    assert exc.value.args[0]


def test_error_message_is_non_empty():
    """Rejected specs always produce a descriptive, non-empty error message."""
    bad = _load_clean()
    bad["apiVersion"] = "wrong/version"
    with pytest.raises(ValueError) as exc:
        spec_loader._validate(bad)
    msg = str(exc.value)
    assert len(msg) > 10, "Error message should be descriptive, not empty or trivial"


# ---------------------------------------------------------------------------
# Security check type — I2 (REQ-003)
# ---------------------------------------------------------------------------

_SECURITY_GATE_NODE = {
    "id": "g-security",
    "kind": "gate",
    "checks": [
        {
            "type": "security",
            "scanners": {
                "sast": "semgrep --config auto --json .",
                "secrets": "gitleaks detect --report-format json --report-path /dev/stdout",
                "deps_python": "pip-audit -r requirements.txt -f json",
                "deps_node": "npm audit --json",
            },
            "fail_on": ["critical", "high"],
            "on_missing_scanner": "fail",
            "reconcile": True,
        }
    ],
}


def _spec_with_security_gate() -> dict:
    """Return a valid in-memory spec that includes a g-security gate node."""
    base = _load_clean()
    base["nodes"].append(_SECURITY_GATE_NODE)
    # add a connector edge so the spec is structurally sound
    base["edges"].append({"from": "g-review", "to": "g-security"})
    return base


def test_security_check_type_validates_clean():
    """A gate node with type=security + all four new fields must validate clean."""
    spec = _spec_with_security_gate()
    # must not raise
    result = spec_loader.loads_spec(
        __import__("yaml").dump(spec, default_flow_style=False, allow_unicode=True)
    )
    assert any(n["id"] == "g-security" for n in result["nodes"])


def test_security_check_minimal_validates_clean():
    """A security check with only type=security (no optional fields) is valid."""
    base = _load_clean()
    base["nodes"].append(
        {"id": "g-sec-min", "kind": "gate", "checks": [{"type": "security"}]}
    )
    base["edges"].append({"from": "g-review", "to": "g-sec-min"})
    result = spec_loader.loads_spec(
        __import__("yaml").dump(base, default_flow_style=False, allow_unicode=True)
    )
    assert any(n["id"] == "g-sec-min" for n in result["nodes"])


def test_security_bad_on_missing_scanner_rejected():
    """on_missing_scanner must be 'skip' or 'fail'; 'warn' is rejected."""
    base = _load_clean()
    bad_node = {
        "id": "g-security-bad",
        "kind": "gate",
        "checks": [
            {
                "type": "security",
                "on_missing_scanner": "warn",  # invalid value
            }
        ],
    }
    base["nodes"].append(bad_node)
    base["edges"].append({"from": "g-review", "to": "g-security-bad"})
    spec_text = __import__("yaml").dump(base, default_flow_style=False, allow_unicode=True)
    with pytest.raises(ValueError) as exc:
        spec_loader.loads_spec(spec_text)
    assert exc.value.args[0]
